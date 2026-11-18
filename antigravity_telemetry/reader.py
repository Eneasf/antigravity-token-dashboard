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
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.parse

from .parser import extract_step_telemetry, extract_trajectory_metadata, parse_wire_fields


DEFAULT_ANTIGRAVITY_DIR = Path.home() / ".gemini" / "antigravity"

_SUMMARIES_DB_TITLE_CACHE: Dict[str, Tuple[Tuple[int, int], Dict[str, str]]] = {}


def _get_conversation_summaries_titles(base_dir: Path) -> Dict[str, str]:
    """Read human-readable titles/previews from conversation_summaries.db in read-only mode."""
    cs_db = base_dir / "conversation_summaries.db"
    if not cs_db.exists():
        return {}
    try:
        st = cs_db.stat()
        fp = (st.st_mtime_ns, st.st_size)
        cache_key = str(cs_db.resolve())
        cached = _SUMMARIES_DB_TITLE_CACHE.get(cache_key)
        if cached is not None and cached[0] == fp:
            return cached[1]
    except OSError:
        return {}

    titles: Dict[str, str] = {}
    conn = None
    try:
        uri = f"file:{cs_db.resolve()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000;")
        cur = conn.cursor()
        cur.execute("SELECT conversation_id, title, preview FROM conversation_summaries")
        for cid, raw_title, raw_preview in cur.fetchall():
            if not cid:
                continue
            clean_title = (raw_title or "").strip()
            if clean_title:
                titles[cid] = clean_title
            elif raw_preview:
                first_line = next((ln.strip() for ln in str(raw_preview).splitlines() if ln.strip()), "")
                if first_line:
                    titles[cid] = first_line[:80].strip()
        _SUMMARIES_DB_TITLE_CACHE[cache_key] = (fp, titles)
    except (sqlite3.Error, OSError):
        return {}
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
    return titles


def get_conversation_title(
    convo_id: str,
    antigravity_dir: Union[Path, str] = DEFAULT_ANTIGRAVITY_DIR,
) -> str:
    """Read human-readable title from annotations/<convo_id>.pbtxt or conversation_summaries.db if available."""
    base_dir = Path(antigravity_dir)
    pbtxt_path = base_dir / "annotations" / f"{convo_id}.pbtxt"
    if pbtxt_path.exists():
        try:
            content = pbtxt_path.read_text(encoding="utf-8", errors="replace")
            match = re.search(r'title:\s*"([^"]+)"', content)
            if match and match.group(1).strip():
                return match.group(1).strip()
        except OSError as exc:
            sys.stderr.write(f"[antigravity_telemetry] Error reading pbtxt {pbtxt_path}: {exc}\n")

    db_titles = _get_conversation_summaries_titles(base_dir)
    if convo_id in db_titles and db_titles[convo_id]:
        return db_titles[convo_id]

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
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        sys.stderr.write(f"[antigravity_telemetry] Error reading workspace mapping from {pb_path}: {exc}\n")

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


def _parse_timestamp_field(b: bytes) -> Optional[float]:
    """Parse a google.protobuf.Timestamp message bytes into epoch seconds float."""
    if not b:
        return None
    try:
        sub = parse_wire_fields(b)
        seconds = 0
        nanos = 0
        has_seconds = False
        for sfnum, sftype, sval in sub:
            if sfnum == 1 and sftype == "varint":
                seconds = sval
                has_seconds = True
            elif sfnum == 2 and sftype == "varint":
                nanos = sval
        if has_seconds or nanos > 0:
            return float(seconds) + (float(nanos) / 1e9)
    except Exception:
        pass
    return None


def extract_wire_latency_ms(raw_blob: Optional[Union[bytes, memoryview]]) -> Dict[str, Optional[float]]:
    """
    Safely parse raw protobuf wire bytes (raw_metadata_blob) without external protobuf overhead.

    Extracts:
    - Top-level Field 1: created_at Timestamp (field 1: seconds varint, field 2: nanos varint)
    - Top-level Field 6: request_sent_at Timestamp
    - Top-level Field 7: first_response_at / first token Timestamp
    - Top-level Field 8: completed_at Timestamp
    - Top-level Field 26: repeated streaming chunk event message containing nested Field 1 Timestamp

    Computes:
    - ttft_ms: round((t_first - t_req) * 1000.0, 2) where t_req is Field 6 (or Field 1 fallback)
      and t_first is Field 7 (or earliest Field 26 timestamp >= t_req). Clamped to 0 < ttft_ms < 600000.
    - latency_ms: round((t_done - t_req) * 1000.0, 2) where t_done is Field 8 (or latest Field 26
      timestamp >= t_req). Clamped to 0 < latency_ms < 1800000.
    """
    if not raw_blob:
        return {"ttft_ms": None, "latency_ms": None}

    blob_bytes = bytes(raw_blob) if isinstance(raw_blob, memoryview) else raw_blob
    if not isinstance(blob_bytes, bytes) or len(blob_bytes) == 0:
        return {"ttft_ms": None, "latency_ms": None}

    try:
        top_fields = parse_wire_fields(blob_bytes)
        t_created = None
        t_req = None
        t_first = None
        t_done = None
        f26_timestamps: List[float] = []

        for fnum, ftype, val in top_fields:
            if ftype != "bytes":
                continue
            if fnum == 1:
                t_created = _parse_timestamp_field(val)
            elif fnum == 6:
                t_req = _parse_timestamp_field(val)
            elif fnum == 7:
                t_first = _parse_timestamp_field(val)
            elif fnum == 8:
                t_done = _parse_timestamp_field(val)
            elif fnum == 26:
                ts = _parse_timestamp_field(val)
                if ts is not None and ts > 0:
                    f26_timestamps.append(ts)
                else:
                    try:
                        for sfn, swt, sval in parse_wire_fields(val):
                            if swt == "bytes":
                                ts_sub = _parse_timestamp_field(sval)
                                if ts_sub is not None and ts_sub > 0:
                                    f26_timestamps.append(ts_sub)
                                else:
                                    for ssfn, sswt, ssval in parse_wire_fields(sval):
                                        if sswt == "bytes":
                                            ts_nested = _parse_timestamp_field(ssval)
                                            if ts_nested is not None and ts_nested > 0:
                                                f26_timestamps.append(ts_nested)
                    except Exception:
                        pass

        req = t_req if t_req is not None else t_created
        valid_f26 = [t for t in f26_timestamps if req is None or t >= req] if f26_timestamps else []

        first = t_first
        if first is None and valid_f26:
            first = min(valid_f26)

        done = t_done
        if done is None and valid_f26:
            done = max(valid_f26)
        elif done is not None and valid_f26:
            done = max(done, max(valid_f26))

        ttft_ms = None
        latency_ms = None

        if req is not None:
            if first is not None:
                diff_ms = (first - req) * 1000.0
                if 0.0 < diff_ms < 600000.0:  # 10 min ceiling
                    ttft_ms = round(diff_ms, 2)
            if done is not None:
                diff_ms = (done - req) * 1000.0
                if 0.0 < diff_ms < 1800000.0:  # 30 min ceiling
                    latency_ms = round(diff_ms, 2)

        return {"ttft_ms": ttft_ms, "latency_ms": latency_ms}
    except Exception:
        return {"ttft_ms": None, "latency_ms": None}


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
                    lat_metrics = extract_wire_latency_ms(metadata_blob)
                    telemetry["ttft_ms"] = lat_metrics["ttft_ms"]
                    telemetry["latency_ms"] = lat_metrics["latency_ms"]
                    turns.append(telemetry)

            return turns
        except sqlite3.OperationalError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay_seconds * (2 ** attempt))
                continue
            return []
        except (sqlite3.Error, OSError) as exc:
            sys.stderr.write(f"[antigravity_telemetry] Error reading conversation turns from {db_path}: {exc}\n")
            return []
        finally:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error as exc:
                    sys.stderr.write(f"[antigravity_telemetry] Error closing SQLite connection: {exc}\n")

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
            "trajectory_id": p.stem,
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

            if row and row[0]:
                traj = extract_trajectory_metadata(row[0])
            else:
                traj = extract_trajectory_metadata(None)

            ws_path, ws_name = clean_workspace_path(traj.get("raw_workspace_uri") or "")
            return {
                "convo_id": p.stem,
                "trajectory_id": traj.get("convo_id") or p.stem,
                "workspace_path": ws_path,
                "workspace_name": ws_name,
                "git_branch": traj.get("git_branch") or "main",
                "db_path": str(p),
                "agent_name": traj.get("agent_name") or "default",
                "agent_description": traj.get("agent_description") or "",
                "agent_config_uri": traj.get("agent_config_uri") or "",
                "is_subagent": bool(
                    traj.get("is_subagent")
                    or traj.get("parent_convo_id")
                    or traj.get("subagent_type")
                ),
                "parent_convo_id": traj.get("parent_convo_id") or "",
                "subagent_type": traj.get("subagent_type") or "",
                "subagent_role": traj.get("subagent_role") or "",
            }
        except sqlite3.OperationalError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay_seconds * (2 ** attempt))
                continue
            break
        except (sqlite3.Error, OSError) as exc:
            sys.stderr.write(f"[antigravity_telemetry] Error reading metadata from {db_path}: {exc}\n")
            break
        finally:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error as exc:
                    sys.stderr.write(f"[antigravity_telemetry] Error closing SQLite connection: {exc}\n")

    return {
        "convo_id": p.stem,
        "trajectory_id": p.stem,
        "workspace_path": "",
        "workspace_name": "Unknown Workspace",
        "git_branch": "main",
        "db_path": str(p),
        "agent_name": "default",
        "agent_description": "",
        "agent_config_uri": "",
        "is_subagent": False,
        "parent_convo_id": "",
        "subagent_type": "",
        "subagent_role": "",
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
    # Sort by modification time descending with filename tie-breaker for deterministic extraction
    db_paths.sort(key=lambda p: (p.stat().st_mtime if p.exists() else 0, p.name), reverse=True)

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
                "agent_name": auth_meta.get("agent_name", "default"),
                "agent_description": auth_meta.get("agent_description", ""),
                "agent_config_uri": auth_meta.get("agent_config_uri", ""),
                "is_subagent": auth_meta.get("is_subagent", False),
                "parent_convo_id": auth_meta.get("parent_convo_id", ""),
                "subagent_type": auth_meta.get("subagent_type", ""),
                "subagent_role": auth_meta.get("subagent_role", ""),
            })
        except (OSError, sqlite3.Error, KeyError) as exc:
            sys.stderr.write(f"[antigravity_telemetry] Error discovering conversation {db_path}: {exc}\n")
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
