"""
antigravity_telemetry.reader: Safe read-only reader for local Antigravity telemetry stores.

Adheres to:
- ADR-001: Safe Read-Only SQLite Access (`?mode=ro`, uri=True).
- Event Sourcing & Projection Invariant: upstream SQLite is sole system of record.
"""

from pathlib import Path
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.parse

from .parser import extract_step_telemetry, parse_wire_fields


DEFAULT_ANTIGRAVITY_DIR = Path.home() / ".gemini" / "antigravity"


def get_conversation_title(
    convo_id: str,
    antigravity_dir: Union[Path, str] = DEFAULT_ANTIGRAVITY_DIR,
) -> str:
    """Read human-readable title from annotations/<convo_id>.pbtxt if available."""
    base_dir = Path(antigravity_dir)
    pbtxt_path = base_dir / "annotations" / f"{convo_id}.pbtxt"
    if not pbtxt_path.exists():
        return f"Conversation {convo_id[:8]}"

    try:
        content = pbtxt_path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r'title:\s*"([^"]+)"', content)
        if match:
            return match.group(1)
    except Exception:
        pass

    return f"Conversation {convo_id[:8]}"


def get_workspace_mapping(
    antigravity_dir: Union[Path, str] = DEFAULT_ANTIGRAVITY_DIR,
) -> Dict[str, str]:
    """
    Extract conversation -> workspace URI mapping from agyhub_summaries_proto.pb.
    Returns mapping of conversation UUID -> workspace directory / repo name.
    """
    base_dir = Path(antigravity_dir)
    pb_path = base_dir / "agyhub_summaries_proto.pb"
    if not pb_path.exists():
        return {}

    mapping = {}
    try:
        content = pb_path.read_bytes()
        uuid_pattern = rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        matches = list(re.finditer(uuid_pattern, content))
        for m in matches:
            convo_id = m.group(0).decode("utf-8")
            start = m.end()
            chunk = content[start : start + 300]
            ws_match = re.search(rb"file://(/[^\"\n\r\x00-\x1f]+)", chunk)
            if ws_match:
                ws_path = ws_match.group(1).decode("utf-8", errors="replace")
                mapping[convo_id] = os.path.basename(ws_path) or ws_path
    except Exception:
        pass

    return mapping


def clean_workspace_path(raw_uri: str) -> Tuple[str, str]:
    """
    Clean a raw workspace URI into (clean_path, project_name).
    Decodes URL escaping and strips file:// scheme.
    """
    if not raw_uri:
        return "", "Unknown Workspace"
    unquoted = urllib.parse.unquote(raw_uri)
    path = unquoted
    if path.startswith("file://"):
        path = path[7:]
    path = path.rstrip("/")
    name = os.path.basename(path) or path or "Unknown Workspace"
    return path, name


def read_conversation_turns(
    db_path: Union[Path, str],
    max_retries: int = 3,
    retry_delay_seconds: float = 0.1,
) -> List[Dict[str, Any]]:
    """
    Safely read all model generation turns (step_type = 15) from a conversation SQLite database.
    Always uses read-only URI mode (?mode=ro).
    Handles active Electron checkpoint and lock transitions with retry backoff and busy_timeout.
    """
    p = Path(db_path)
    if not p.exists():
        return []

    turns: List[Dict[str, Any]] = []
    uri = f"file:{p.resolve()}?mode=ro"

    for attempt in range(max_retries):
        conn = None
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=5.0)
            cur = conn.cursor()
            cur.execute("PRAGMA busy_timeout = 5000;")

            # Step type 15 is PLANNER_RESPONSE (model generation)
            cur.execute("SELECT idx, step_type, metadata FROM steps WHERE step_type = 15 ORDER BY idx ASC")
            rows = cur.fetchall()

            for idx, stype, metadata_blob in rows:
                telemetry = extract_step_telemetry(metadata_blob)
                if telemetry:
                    telemetry["step_idx"] = idx
                    telemetry["convo_id"] = p.stem
                    turns.append(telemetry)

            return turns
        except sqlite3.OperationalError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay_seconds * (2 ** attempt))
                continue
            return []
        except Exception:
            return []
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    return turns


def read_single_conversation_metadata(
    db_path: Union[Path, str],
    max_retries: int = 3,
    retry_delay_seconds: float = 0.1,
) -> Dict[str, Any]:
    """
    Extract authoritative metadata from trajectory_metadata_blob in a single conversation SQLite DB.
    Always uses read-only URI mode (?mode=ro).
    Handles active locks with retries.
    """
    p = Path(db_path)
    if not p.exists():
        return {
            "convo_id": p.stem,
            "workspace_path": "",
            "workspace_name": "Unknown Workspace",
            "git_branch": "main",
            "db_path": str(p),
        }

    uri = f"file:{p.resolve()}?mode=ro"
    for attempt in range(max_retries):
        conn = None
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=5.0)
            cur = conn.cursor()
            cur.execute("PRAGMA busy_timeout = 5000;")
            cur.execute("SELECT data FROM trajectory_metadata_blob WHERE id = 'main'")
            row = cur.fetchone()

            raw_ws = None
            git_branch = None
            convo_id = p.stem

            if row and row[0]:
                blob = row[0]
                fields = parse_wire_fields(blob)
                f_map = {fn: val for fn, wt, val in fields}

                # Field 1: subfields
                if 1 in f_map and isinstance(f_map[1], bytes):
                    sub = {sfn: sval for sfn, swt, sval in parse_wire_fields(f_map[1])}
                    if 1 in sub and isinstance(sub[1], bytes):
                        raw_ws = sub[1].decode("utf-8", errors="replace")
                    if 4 in sub and isinstance(sub[4], bytes):
                        git_branch = sub[4].decode("utf-8", errors="replace")

                # Field 7: fallback workspace URI
                if not raw_ws and 7 in f_map and isinstance(f_map[7], bytes):
                    raw_ws = f_map[7].decode("utf-8", errors="replace")

                # Field 6: convo_id
                if 6 in f_map and isinstance(f_map[6], bytes):
                    c_id = f_map[6].decode("utf-8", errors="replace")
                    if c_id:
                        convo_id = c_id

            ws_path, ws_name = clean_workspace_path(raw_ws or "")
            return {
                "convo_id": convo_id,
                "workspace_path": ws_path,
                "workspace_name": ws_name,
                "git_branch": git_branch or "main",
                "db_path": str(p),
            }
        except sqlite3.OperationalError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay_seconds * (2 ** attempt))
                continue
            break
        except Exception:
            break
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    return {
        "convo_id": p.stem,
        "workspace_path": "",
        "workspace_name": "Unknown Workspace",
        "git_branch": "main",
        "db_path": str(p),
    }


def read_conversation_metadata(
    db_path: Optional[Union[Path, str]] = None,
    antigravity_dir: Union[Path, str] = DEFAULT_ANTIGRAVITY_DIR,
) -> Union[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """
    Extract authoritative workspace path, clean project name, and active Git branch.
    If db_path is a file, returns metadata for that single conversation DB.
    If db_path is None or a directory, scans all conversation databases and returns
    a mapping of convo_id -> metadata dictionary.
    """
    if db_path is not None:
        p = Path(db_path)
        if p.is_file():
            return read_single_conversation_metadata(p)
        conv_dir = p if p.is_dir() else (p / "conversations")
    else:
        conv_dir = Path(antigravity_dir) / "conversations"

    results: Dict[str, Dict[str, Any]] = {}
    if not conv_dir.exists():
        return results

    for p in conv_dir.glob("*.db"):
        meta = read_single_conversation_metadata(p)
        results[meta["convo_id"]] = meta

    return results


def discover_all_conversations(
    antigravity_dir: Union[Path, str] = DEFAULT_ANTIGRAVITY_DIR,
    max_conversations: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Discover all conversation databases sorted by modification time (most recent first).
    Attaches authoritative workspace path, clean project name, and active Git branch.
    Returns list of metadata dictionaries.
    """
    base_dir = Path(antigravity_dir)
    conv_dir = base_dir / "conversations"
    if not conv_dir.exists():
        return []

    db_paths = list(conv_dir.glob("*.db"))
    # Sort by modification time descending
    db_paths.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

    workspace_mapping = get_workspace_mapping(base_dir)
    results: List[Dict[str, Any]] = []
    target_paths = db_paths if max_conversations is None else db_paths[:max_conversations]

    for path in target_paths:
        convo_id = path.stem
        try:
            stat = path.stat()
            auth_meta = read_single_conversation_metadata(path)
            ws_name = auth_meta.get("workspace_name")
            if not ws_name or ws_name == "Unknown Workspace":
                ws_name = workspace_mapping.get(convo_id, "Unknown Workspace")

            results.append({
                "convo_id": convo_id,
                "db_path": str(path),
                "title": get_conversation_title(convo_id, base_dir),
                "workspace": ws_name,
                "workspace_path": auth_meta.get("workspace_path", ""),
                "workspace_name": ws_name,
                "git_branch": auth_meta.get("git_branch", "main"),
                "last_modified": stat.st_mtime,
                "size_bytes": stat.st_size,
            })
        except Exception:
            continue

    return results


def read_all_turns(
    antigravity_dir: Optional[Union[Path, str]] = None,
    max_conversations: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Safely discover all conversation databases and read all model generation turns.
    Returns a flat list of turn dictionaries conforming to TELEMETRY_SPEC.md.
    """
    target_dir = Path(antigravity_dir) if antigravity_dir is not None else DEFAULT_ANTIGRAVITY_DIR
    convos = discover_all_conversations(target_dir, max_conversations=max_conversations)
    all_turns: List[Dict[str, Any]] = []
    for meta in convos:
        db_p = Path(meta["db_path"])
        turns = read_conversation_turns(db_p)
        if turns:
            all_turns.extend(turns)
    return all_turns
