"""
Dedicated Local Telemetry Vault, Hybrid Lossless Archival & Lineage Topology.

Adheres to:
- ADR-001: Safe Read-Only SQLite Access (`?mode=ro`, uri=True).
- ADR-002: Pure-Python Wire Protobuf Decoding (zero protoc/compiler dependencies).
- ADR-018: Dedicated Local Telemetry Vault, Hybrid Lossless Archival & Lineage Topology.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.parse

logger = logging.getLogger(__name__)

from src.aggregator import (
    compute_turn_cost,
    get_model_display_name,
    get_model_rates,
    load_pricing,
    parse_timestamp,
)
from src.log_reader import (
    DEFAULT_LOG_PATH,
    EXHAUSTION_PATTERN,
    GLOG_TIMESTAMP_PATTERN,
    parse_glog_timestamp,
)
from antigravity_telemetry import (
    DEFAULT_ANTIGRAVITY_DIR,
    extract_error_details,
    extract_step_payload_details,
    extract_step_telemetry,
    extract_trajectory_metadata,
    get_conversation_title,
    get_workspace_mapping,
    parse_wire_fields,
)


from src.vault_schema import (
    DEFAULT_VAULT_PATH,
    get_vault_connection,
    init_vault,
)
from antigravity_telemetry.reader import extract_wire_latency_ms
from src.weekly_trends import (
    get_weekly_trends as _get_weekly_trends_impl,
    sync_weekly_trends_to_vault as _sync_weekly_trends_to_vault_impl,
)

# Strict skill slug pattern: alphanumeric start, 2-64 chars of [a-zA-Z0-9_-]
SKILL_SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}$")


def parse_agyhub_summaries(pb_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Decode conversation session records from `agyhub_summaries_proto.pb`.

    Uses pure-Python wire protobuf decoding to extract:
    - convo_id: UUID
    - title: Human-readable task/prompt title
    - workspace_path: Decoded and unquoted local file path
    - workspace_name: Basename of workspace directory
    - trajectory_id: Session UUID
    """
    if not pb_path.exists():
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    try:
        data = pb_path.read_bytes()
    except Exception:
        return {}

    # Wire protobuf parse
    try:
        top_fields = parse_wire_fields(data)
        for fnum, ftype, fval in top_fields:
            if ftype != "bytes":
                continue
            subfields = parse_wire_fields(fval)
            cid = ""
            title = ""
            trajectory_id = ""
            ws_path = ""
            ws_name = ""

            for sf, st, sv in subfields:
                if sf == 1 and isinstance(sv, bytes):
                    try:
                        candidate_cid = sv.decode("utf-8", errors="ignore")
                        if len(candidate_cid) == 36 and candidate_cid.count("-") == 4:
                            cid = candidate_cid
                    except (UnicodeDecodeError, AttributeError):
                        pass
                elif sf == 2 and isinstance(sv, bytes):
                    # Inspect inner summary payload
                    s2_fields = parse_wire_fields(sv)
                    for s2f, s2t, s2v in s2_fields:
                        if s2f == 1 and isinstance(s2v, bytes):
                            title = s2v.decode("utf-8", errors="replace")
                        elif s2f == 4 and isinstance(s2v, bytes):
                            trajectory_id = s2v.decode("utf-8", errors="replace")
                        elif s2f in (9, 17) and isinstance(s2v, bytes):
                            # Contains nested workspace URI
                            f_nested = parse_wire_fields(s2v)
                            for nf, nt, nv in f_nested:
                                if nf == 1 and isinstance(nv, bytes):
                                    uri_str = nv.decode("utf-8", errors="replace")
                                    if uri_str.startswith("file://"):
                                        raw_clean = uri_str[len("file://"):]
                                        unquoted = urllib.parse.unquote(raw_clean)
                                        ws_path = unquoted
                                        ws_name = os.path.basename(unquoted) or unquoted

            if cid:
                results[cid] = {
                    "convo_id": cid,
                    "title": title,
                    "trajectory_id": trajectory_id,
                    "workspace_path": ws_path,
                    "workspace_name": ws_name,
                }
    except (ValueError, IndexError, AttributeError) as exc:
        logger.debug("Error parsing protobuf summary payload: %s", exc)

    # Regex fallback pass to ensure no conversation UUID or URI is missed
    try:
        uuid_pattern = rb"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
        for m in re.finditer(uuid_pattern, data):
            cid = m.group(0).decode("utf-8")
            chunk = data[m.end(): m.end() + 350]
            ws_match = re.search(rb"file://(/[^\"\n\r\x00-\x1f]+)", chunk)
            if ws_match:
                uri_path = ws_match.group(1).decode("utf-8", errors="replace")
                # Protobuf byte tags after URL may be attached; trim ASCII controls or non-path endings
                uri_path = re.sub(r"[\x00-\x1f\x7f-\xff].*$", "", uri_path)
                # Strip trailing protobuf field tags like 'B%' or digits
                uri_path = re.sub(r"[A-Z%]+$", "", uri_path)
                unquoted = urllib.parse.unquote(uri_path)
                ws_name = os.path.basename(unquoted) or unquoted
                if cid not in results:
                    results[cid] = {
                        "convo_id": cid,
                        "title": "",
                        "trajectory_id": "",
                        "workspace_path": unquoted,
                        "workspace_name": ws_name,
                    }
                else:
                    if not results[cid]["workspace_path"]:
                        results[cid]["workspace_path"] = unquoted
                    if not results[cid]["workspace_name"]:
                        results[cid]["workspace_name"] = ws_name
    except (ValueError, IndexError, AttributeError) as exc:
        logger.debug("Error regex scanning conversation IDs: %s", exc)

    return results


def _read_convo_db_steps(
    db_path: Path,
    high_watermark_step_idx: Optional[int] = None,
    max_retries: int = 3,
    retry_delay_seconds: float = 0.05,
) -> List[Tuple[Any, ...]]:
    """
    Read steps from an Antigravity conversation database adhering to ADR-001.
    Connects strictly with `file:{db_path}?mode=ro`, uri=True.
    """
    if not db_path.exists():
        return []

    uri = f"file:{db_path.resolve()}?mode=ro"
    query = """
        SELECT idx, step_type, status, metadata, error_details, step_payload
        FROM steps
    """
    params: List[Any] = []
    if high_watermark_step_idx is not None:
        query += " WHERE idx > ?"
        params.append(high_watermark_step_idx)
    query += " ORDER BY idx ASC"

    for attempt in range(max_retries):
        conn = None
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=5.0)
            conn.execute("PRAGMA busy_timeout = 5000;")
            cur = conn.cursor()
            cur.execute(query, params)
            return cur.fetchall()
        except sqlite3.OperationalError:
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay_seconds * (2 ** attempt))
                continue
            return []
        except (sqlite3.Error, OSError) as exc:
            logger.debug("Error reading conversation steps from %s: %s", db_path, exc)
            return []
        finally:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass

    return []


def _read_convo_db_trajectory_blob(
    db_path: Path,
    max_retries: int = 3,
    retry_delay_seconds: float = 0.05,
) -> Optional[bytes]:
    """Read trajectory_metadata_blob from an Antigravity conversation database adhering to ADR-001."""
    if not db_path.exists():
        return None

    uri = f"file:{db_path.resolve()}?mode=ro"
    for attempt in range(max_retries):
        conn = None
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=5.0)
            conn.execute("PRAGMA busy_timeout = 5000;")
            cur = conn.cursor()
            cur.execute("SELECT data FROM trajectory_metadata_blob WHERE id = 'main'")
            row = cur.fetchone()
            return row[0] if row and row[0] else None
        except sqlite3.OperationalError:
            if attempt < max_retries - 1:
                import time
                time.sleep(retry_delay_seconds * (2 ** attempt))
                continue
            return None
        except (sqlite3.Error, OSError) as exc:
            logger.debug("Error reading trajectory metadata blob from %s: %s", db_path, exc)
            return None
        finally:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass

    return None


def _execute_sql_with_retry(
    cursor: sqlite3.Cursor,
    sql: str,
    parameters: Union[Tuple, List] = (),
    max_retries: int = 5,
    base_delay: float = 0.1,
) -> sqlite3.Cursor:
    """Execute SQL statement with exponential backoff on sqlite3.OperationalError (database is locked)."""
    for attempt in range(max_retries):
        try:
            return cursor.execute(sql, parameters)
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
            else:
                raise
    return cursor


def _commit_with_retry(
    conn: sqlite3.Connection,
    max_retries: int = 5,
    base_delay: float = 0.1,
) -> None:
    """Commit connection with exponential backoff on sqlite3.OperationalError (database is locked)."""
    for attempt in range(max_retries):
        try:
            conn.commit()
            return
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
            else:
                raise


def sync_conversations_to_vault(
    antigravity_dir: Union[str, Path] = DEFAULT_ANTIGRAVITY_DIR,
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    max_conversations: Optional[int] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    High-watermark incremental sync from upstream Antigravity SQLite DBs to Vault.

    Adheres strictly to ADR-001:
    - Never opens upstream DBs for writing (`?mode=ro`, uri=True).
    - Inspects existing MAX(step_idx) per convo_id in steps_archive.
    - Decodes step telemetry, payload details, error details.
    - Populates steps_archive, tool_calls_archive, skills_archive.
    - Attributes workspaces from agyhub_summaries_proto.pb via unquoting.
    - Resolves parent-child subagent lineage bidirectionally.

    Returns:
    {
        'conversations_synced': int,
        'steps_synced': int,
        'tool_calls_synced': int,
        'discovered_databases': int,
        'scanned_databases': int,
        'vault_bytes': int
    }
    """
    sync_start_time = time.time()
    now_iso = datetime.now(timezone.utc).isoformat()

    agy_path = Path(antigravity_dir).resolve()
    vault_conn = get_vault_connection(vault_path)
    vault_conn.execute("PRAGMA busy_timeout = 60000;")
    cur = vault_conn.cursor()

    # Load last sync mtime
    last_sync_mtime: Optional[float] = None
    backfill_complete: bool = False
    try:
        cur.execute(
            "SELECT key, value FROM vault_sync_state WHERE key IN ('conversations_last_sync_mtime', 'conversations_backfill_complete')"
        )
        for k_row, v_row in cur.fetchall():
            if k_row == "conversations_last_sync_mtime" and v_row is not None:
                last_sync_mtime = float(v_row)
            elif k_row == "conversations_backfill_complete" and v_row == "1":
                backfill_complete = True
    except Exception:
        last_sync_mtime = None

    # Discover upstream DBs before scanning steps_archive high-watermarks
    conv_dir = agy_path / "conversations"
    db_paths: List[Path] = []
    discovered_count = 0
    scanned_count = 0
    if conv_dir.exists():
        try:
            db_paths = list(conv_dir.glob("*.db"))
            discovered_count = len(db_paths)
            db_paths.sort(key=lambda p: (p.stat().st_mtime if p.exists() else 0, p.name), reverse=True)
            if not force and last_sync_mtime is not None:
                def _is_newer(p: Path) -> bool:
                    try:
                        return p.stat().st_mtime > last_sync_mtime
                    except (OSError, PermissionError):
                        return False
                db_paths = [p for p in db_paths if _is_newer(p)]
            scanned_count = len(db_paths)
            if max_conversations is not None:
                db_paths = db_paths[:max_conversations]
                scanned_count = len(db_paths)
        except (PermissionError, OSError):
            db_paths = []
            discovered_count = 0
            scanned_count = 0

    cur.execute("SELECT COUNT(*) FROM conversations_archive")
    archive_count = (cur.fetchone() or [0])[0]
    max_step_rowid = (cur.execute("SELECT COALESCE(MAX(rowid), 0) FROM steps_archive").fetchone() or [0])[0]

    # Ultra-fast no-op return when 0 DBs changed since last_sync_mtime (zero vault mutations)
    if not force and last_sync_mtime is not None and scanned_count == 0 and (archive_count > 0 or max_step_rowid == 0):
        vault_conn.close()
        return {
            "conversations_synced": 0,
            "steps_synced": 0,
            "tool_calls_synced": 0,
            "discovered_databases": discovered_count,
            "scanned_databases": 0,
            "vault_bytes": Path(vault_path).stat().st_size if Path(vault_path).exists() else 0,
        }

    # Load high-watermarks only for candidate db_paths (or all if force)
    if db_paths and not force and len(db_paths) <= 200:
        cand_ids = [p.stem for p in db_paths]
        ph = ",".join("?" for _ in cand_ids)
        cur.execute(
            f"SELECT convo_id, MAX(step_idx) FROM steps_archive WHERE convo_id IN ({ph}) GROUP BY convo_id",
            cand_ids,
        )
        high_watermarks: Dict[str, int] = {row[0]: row[1] for row in cur.fetchall()}
    else:
        cur.execute("SELECT convo_id, MAX(step_idx) FROM steps_archive GROUP BY convo_id")
        high_watermarks = {row[0]: row[1] for row in cur.fetchall()}
    vault_conn.commit()

    # Parse workspace summaries
    pb_file = agy_path / "agyhub_summaries_proto.pb"
    summaries = parse_agyhub_summaries(pb_file)
    fallback_ws_map = get_workspace_mapping(agy_path)
    pricing_models = load_pricing()

    steps_synced_count = 0
    tool_calls_synced_count = 0
    conversations_synced_set = set()
    parent_child_links: Dict[str, str] = {}  # child_convo_id -> parent_convo_id
    authoritative_parents: Dict[str, str] = {}  # child_convo_id -> authoritative parent_convo_id from protobuf
    known_root_ids: set = set()  # convo_ids verified as root orchestrators (is_subagent == False, parent_convo_id == "")
    convo_trajectory_meta: Dict[str, Dict[str, Any]] = {}
    convo_raw_blobs: Dict[str, Optional[bytes]] = {}

    uuid_pattern = re.compile(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        re.IGNORECASE,
    )
    sender_pattern = re.compile(
        r"sender=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        re.IGNORECASE,
    )
    parent_prompt_pattern = re.compile(
        r'parent["\',:\s]+(?:id["\':\s]+)?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
        re.IGNORECASE,
    )

    now_iso = datetime.now(timezone.utc).isoformat()

    for db_path in db_paths:
        convo_id = db_path.stem
        raw_traj_blob = _read_convo_db_trajectory_blob(db_path)
        convo_raw_blobs[convo_id] = raw_traj_blob
        if raw_traj_blob:
            traj_meta = extract_trajectory_metadata(raw_traj_blob)
            convo_trajectory_meta[convo_id] = traj_meta
            auth_pid = (traj_meta.get("parent_convo_id") or "").strip()
            is_sub_meta = bool(
                traj_meta.get("is_subagent")
                or auth_pid
                or traj_meta.get("subagent_type")
            )
            if auth_pid and auth_pid != convo_id:
                authoritative_parents[convo_id] = auth_pid
                parent_child_links[convo_id] = auth_pid
            elif not is_sub_meta:
                known_root_ids.add(convo_id)

        hw = high_watermarks.get(convo_id)

        rows = _read_convo_db_steps(db_path, high_watermark_step_idx=hw)
        if not rows and convo_id in high_watermarks:
            # Already synced up to high-watermark
            continue

        if rows:
            conversations_synced_set.add(convo_id)

        for idx, stype, status, meta_blob, err_blob, payload_blob in rows:
            telemetry = extract_step_telemetry(meta_blob) or {}
            payload_details = extract_step_payload_details(payload_blob, step_type=stype)
            error_text = extract_error_details(err_blob)
            lat_metrics = extract_wire_latency_ms(meta_blob) if meta_blob else {}
            ttft_val = lat_metrics.get("ttft_ms")
            latency_val = lat_metrics.get("latency_ms")

            # Extract fields for steps_archive
            ts_str = telemetry.get("timestamp") or ""
            model_id_val = telemetry.get("model_id")
            model_id_str = str(model_id_val) if model_id_val is not None else ""
            model_name_str = get_model_display_name(model_id_str, pricing_models) if model_id_str else ""
            prompt_uncached = int(telemetry.get("prompt_tokens_uncached") or 0)
            cached_toks = int(telemetry.get("cached_tokens") or 0)
            total_input = int(telemetry.get("total_input_tokens") or 0)
            out_total = int(telemetry.get("output_tokens_total") or 0)
            thinking_toks = int(telemetry.get("thinking_tokens") or 0)
            answer_toks = int(telemetry.get("answer_tokens") or 0)
            hit_ratio = float(telemetry.get("cache_hit_ratio_pct") or 0.0)
            p_text = str(payload_details.get("payload_text") or "")
            if not p_text and payload_blob:
                try:
                    p_text = payload_blob.decode("utf-8", errors="replace")
                except (UnicodeDecodeError, AttributeError):
                    pass
            tc_json = str(payload_details.get("tool_calls_json") or "[]")
            resp_id = str(telemetry.get("response_id") or "")
            agent_id = str(telemetry.get("agent_id") or "")
            sess_id = str(telemetry.get("session_id") or "")

            # Structured error & rate limit extraction (ADR-088)
            rate_limit_flag = 0
            err_code = ""
            combined_err = (error_text or "") + " " + (p_text or "")
            if "429" in combined_err or "RESOURCE_EXHAUSTED" in combined_err or "quota exceeded" in combined_err.lower():
                rate_limit_flag = 1
                err_code = "RESOURCE_EXHAUSTED"
            elif "PERMISSION_DENIED" in combined_err or "403" in combined_err:
                err_code = "PERMISSION_DENIED"
            elif error_text:
                err_code = "ERROR"

            _execute_sql_with_retry(
                cur,
                """
                INSERT OR REPLACE INTO steps_archive (
                    convo_id, step_idx, step_type, status, timestamp,
                    model_id, model_name, prompt_tokens_uncached, cached_tokens,
                    total_input_tokens, output_tokens_total, thinking_tokens,
                    answer_tokens, cache_hit_ratio_pct, payload_text,
                    tool_calls_json, error_text, raw_metadata_blob,
                    raw_step_payload_blob, raw_error_details_blob,
                    response_id, agent_id, session_id, rate_limit_flag, error_code,
                    ttft_ms, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    convo_id,
                    idx,
                    stype,
                    status,
                    ts_str,
                    model_id_str,
                    model_name_str,
                    prompt_uncached,
                    cached_toks,
                    total_input,
                    out_total,
                    thinking_toks,
                    answer_toks,
                    hit_ratio,
                    p_text,
                    tc_json,
                    error_text,
                    sqlite3.Binary(meta_blob) if meta_blob else None,
                    sqlite3.Binary(payload_blob) if payload_blob else None,
                    sqlite3.Binary(err_blob) if err_blob else None,
                    resp_id,
                    agent_id,
                    sess_id,
                    rate_limit_flag,
                    err_code,
                    ttft_val,
                    latency_val,
                ),
            )
            steps_synced_count += 1

            # Populate tool_calls_archive
            tool_calls = payload_details.get("tool_calls", [])
            for tc in tool_calls:
                _execute_sql_with_retry(
                    cur,
                    """
                    INSERT INTO tool_calls_archive (
                        convo_id, step_idx, call_id, tool_name,
                        tool_action, tool_summary, arguments_json,
                        result_summary, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        convo_id,
                        idx,
                        tc.get("call_id", ""),
                        tc.get("tool_name", ""),
                        tc.get("tool_action", ""),
                        tc.get("tool_summary", ""),
                        tc.get("arguments_json", ""),
                        tc.get("result_summary", ""),
                        ts_str,
                    ),
                )
                tool_calls_synced_count += 1

            # Populate skills_archive
            skills = payload_details.get("skills_referenced") or []
            for sk in skills:
                if not isinstance(sk, str) or not SKILL_SLUG_PATTERN.match(sk.strip()):
                    continue
                sk_clean = sk.strip()
                _execute_sql_with_retry(
                    cur,
                    """
                    INSERT INTO skills_archive (
                        convo_id, step_idx, skill_name, skill_path,
                        activation_type, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        convo_id,
                        idx,
                        sk_clean,
                        f"skills/{sk_clean}/" + "SKILL.md",
                        "referenced",
                        ts_str,
                    ),
                )

            # Subagent Lineage Discovery from step payload details
            for spawned_id in payload_details.get("subagents_spawned", []):
                if spawned_id and spawned_id != convo_id and spawned_id not in known_root_ids:
                    parent_child_links[spawned_id] = convo_id

            for recip_id in payload_details.get("subagent_recipients", []):
                if (
                    recip_id
                    and recip_id != convo_id
                    and recip_id not in known_root_ids
                    and recip_id not in authoritative_parents
                    and recip_id not in parent_child_links.values()
                    and parent_child_links.get(convo_id) != recip_id
                ):
                    parent_child_links[recip_id] = convo_id

            sender_id = payload_details.get("sender_id")
            if (
                sender_id
                and sender_id != convo_id
                and convo_id not in known_root_ids
                and convo_id not in authoritative_parents
                and sender_id not in authoritative_parents
                and parent_child_links.get(sender_id) != convo_id
                and convo_id not in parent_child_links.values()
            ):
                parent_child_links[convo_id] = sender_id

    cur.execute("SELECT COUNT(*) FROM conversations_archive")
    archive_count = (cur.fetchone() or [0])[0]

    # Fast path: skip distinct convo_id aggregate re-computation and lineage discovery
    if len(conversations_synced_set) == 0 and not force:
        if archive_count > 0:
            _execute_sql_with_retry(
                cur,
                """
                INSERT INTO vault_sync_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                ("conversations_last_sync_mtime", str(sync_start_time), now_iso),
            )
            _commit_with_retry(vault_conn)
            vault_conn.close()

            stats = {
                "conversations_synced": 0,
                "steps_synced": steps_synced_count,
                "tool_calls_synced": tool_calls_synced_count,
                "discovered_databases": discovered_count,
                "scanned_databases": scanned_count,
            }
            stats["vault_bytes"] = Path(vault_path).stat().st_size if Path(vault_path).exists() else 0
            return stats

    if force:
        cur.execute("SELECT DISTINCT convo_id FROM steps_archive")
        target_convo_ids = set(r[0] for r in cur.fetchall())
    else:
        target_convo_ids = set(conversations_synced_set)
        if not backfill_complete or archive_count == 0:
            cur.execute("SELECT COUNT(DISTINCT convo_id) FROM steps_archive")
            steps_convo_count = (cur.fetchone() or [0])[0]
            if archive_count < steps_convo_count:
                cur.execute(
                    """
                    SELECT DISTINCT s.convo_id
                    FROM steps_archive s
                    LEFT JOIN conversations_archive c ON s.convo_id = c.convo_id
                    WHERE c.convo_id IS NULL
                    """
                )
                for r in cur.fetchall():
                    target_convo_ids.add(r[0])
            _execute_sql_with_retry(
                cur,
                """
                INSERT INTO vault_sync_state (key, value, updated_at)
                VALUES ('conversations_backfill_complete', '1', ?)
                ON CONFLICT(key) DO UPDATE SET value = '1', updated_at = excluded.updated_at
                """,
                (now_iso,),
            )

    if target_convo_ids:
        cur.execute(
            "SELECT convo_id, raw_metadata_blob FROM conversations_archive WHERE raw_metadata_blob IS NOT NULL"
        )
        for ex_cid, ex_blob in cur.fetchall():
            if ex_cid not in convo_trajectory_meta and ex_blob:
                ex_meta = extract_trajectory_metadata(ex_blob)
                convo_trajectory_meta[ex_cid] = ex_meta
                convo_raw_blobs.setdefault(ex_cid, ex_blob)
                ex_pid = (ex_meta.get("parent_convo_id") or "").strip()
                ex_is_sub = bool(
                    ex_meta.get("is_subagent")
                    or ex_pid
                    or ex_meta.get("subagent_type")
                )
                if ex_pid and ex_pid != ex_cid:
                    authoritative_parents[ex_cid] = ex_pid
                    parent_child_links[ex_cid] = ex_pid
                elif not ex_is_sub:
                    known_root_ids.add(ex_cid)

        # Precise lineage resolution across tool_calls_archive and steps_archive
        # 1. From invoke_subagent tool calls in tool_calls_archive
        subagent_id_pattern = re.compile(
            r'(?:"conversationId"|subagent_id)["\':\s=]*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
            re.IGNORECASE,
        )
        if force or len(target_convo_ids) > 500:
            cur.execute(
                """
                SELECT convo_id, result_summary, arguments_json
                FROM tool_calls_archive
                WHERE tool_name = 'invoke_subagent'
                """
            )
        else:
            placeholders = ",".join("?" for _ in target_convo_ids)
            cur.execute(
                f"""
                SELECT convo_id, result_summary, arguments_json
                FROM tool_calls_archive
                WHERE tool_name = 'invoke_subagent' AND convo_id IN ({placeholders})
                """,
                list(target_convo_ids),
            )
        parsed_transcript_callers = set()
        for caller_id, res_sum, args_json in cur.fetchall():
            combined = (res_sum or "") + " " + (args_json or "")

            # Structural fix: Fallback to reading the lossless transcript_full.jsonl to bypass DB truncation limits
            transcript_full_path = Path(antigravity_dir) / "brain" / caller_id / ".system_generated" / "logs" / "transcript_full.jsonl"
            parsed_from_file = caller_id in parsed_transcript_callers
            if not parsed_from_file and transcript_full_path.exists():
                try:
                    with open(transcript_full_path, "r", encoding="utf-8") as f:
                        full_text = f.read().replace('\\"', '"')
                        for m in subagent_id_pattern.finditer(full_text):
                            child_id = m.group(1)
                            if child_id != caller_id and child_id not in known_root_ids:
                                parent_child_links[child_id] = caller_id
                                parsed_from_file = True
                    parsed_transcript_callers.add(caller_id)
                except (OSError, UnicodeDecodeError) as exc:
                    logger.debug("Error reading transcript %s: %s", transcript_full_path, exc)

            # Fallback to the DB string if the log file is unavailable or unparseable
            if not parsed_from_file:
                for m in subagent_id_pattern.finditer(combined):
                    child_id = m.group(1)
                    if child_id != caller_id and child_id not in known_root_ids:
                        parent_child_links[child_id] = caller_id

        # 2. From send_message tool calls in tool_calls_archive
        if force or len(target_convo_ids) > 500:
            cur.execute(
                """
                SELECT convo_id, arguments_json
                FROM tool_calls_archive
                WHERE tool_name = 'send_message'
                """
            )
        else:
            cur.execute(
                f"""
                SELECT convo_id, arguments_json
                FROM tool_calls_archive
                WHERE tool_name = 'send_message' AND convo_id IN ({placeholders})
                """,
                list(target_convo_ids),
            )
        for caller_id, args_json in cur.fetchall():
            for m in re.finditer(r'"Recipient":\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', args_json or ""):
                child_id = m.group(1)
                if child_id != caller_id:
                    # Do not invert the lineage if the recipient is already known to be a parent
                    # (e.g. a subagent sending a message back to its orchestrator)
                    if (
                        child_id not in known_root_ids
                        and child_id not in authoritative_parents
                        and child_id not in parent_child_links.values()
                        and parent_child_links.get(caller_id) != child_id
                    ):
                        parent_child_links[child_id] = caller_id

        # 3. From mock test or fallback invoke_subagent steps
        if force or len(target_convo_ids) > 500:
            cur.execute(
                """
                SELECT convo_id, payload_text
                FROM steps_archive
                WHERE payload_text LIKE '%invoke_subagent%subagent_id=%'
                """
            )
        else:
            cur.execute(
                f"""
                SELECT convo_id, payload_text
                FROM steps_archive
                WHERE payload_text LIKE '%invoke_subagent%subagent_id=%' AND convo_id IN ({placeholders})
                """,
                list(target_convo_ids),
            )
        for parent_id, p_text in cur.fetchall():
            m = re.search(r'invoke_subagent[^\n\r]*subagent_id="([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', p_text or "")
            if m:
                child_id = m.group(1)
                if child_id != parent_id and child_id not in known_root_ids:
                    parent_child_links[child_id] = parent_id

        # 3b. Native /swarm members.json discovery (authoritative coordinator -> worker links)
        brain_root = Path(antigravity_dir) / "brain"
        if brain_root.exists():
            for members_file in sorted(brain_root.glob("*/.system_generated/swarm/members.json")):
                try:
                    m_data = json.loads(members_file.read_text(encoding="utf-8"))
                    members = m_data.get("members", []) if isinstance(m_data, dict) else []
                    coord_id = next(
                        (
                            str(m.get("conversation_id")).strip()
                            for m in members
                            if isinstance(m, dict) and m.get("role") == "coordinator" and m.get("conversation_id")
                        ),
                        members_file.parent.parent.parent.name,
                    )
                    if not coord_id:
                        continue
                    known_root_ids.add(coord_id)
                    authoritative_parents.pop(coord_id, None)
                    parent_child_links.pop(coord_id, None)
                    for m in members:
                        if not isinstance(m, dict) or m.get("role") == "coordinator":
                            continue
                        w_cid = str(m.get("conversation_id") or "").strip()
                        w_name = str(m.get("name") or "worker").strip()
                        if not w_cid or w_cid == coord_id:
                            continue
                        known_root_ids.discard(w_cid)
                        authoritative_parents[w_cid] = coord_id
                        parent_child_links[w_cid] = coord_id
                        w_meta = convo_trajectory_meta.setdefault(w_cid, {})
                        w_meta["parent_convo_id"] = coord_id
                        w_meta["is_subagent"] = True
                        if not w_meta.get("agent_name") or w_meta.get("agent_name") == "default":
                            w_meta["agent_name"] = w_name
                        if not w_meta.get("subagent_role"):
                            w_meta["subagent_role"] = f"Swarm Worker ({w_name})"
                except (OSError, json.JSONDecodeError, TypeError) as exc:
                    logger.debug("Error reading swarm members %s: %s", members_file, exc)

        # 4. From incoming agent messages in steps_archive (where child receives message from parent)
        if force or len(target_convo_ids) > 500:
            cur.execute(
                """
                SELECT convo_id, payload_text
                FROM steps_archive
                WHERE payload_text LIKE '%sender=%'
                """
            )
        else:
            cur.execute(
                f"""
                SELECT convo_id, payload_text
                FROM steps_archive
                WHERE payload_text LIKE '%sender=%' AND convo_id IN ({placeholders})
                """,
                list(target_convo_ids),
            )
        for child_id, p_text in cur.fetchall():
            sm = re.search(r"\[Message\][^\n\r]*sender=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", p_text or "")
            if sm:
                sender_id = sm.group(1)
                # Only attribute if child_id is not already a root or an orchestrator that spawned children
                if (
                    sender_id != child_id
                    and child_id not in known_root_ids
                    and child_id not in authoritative_parents
                    and sender_id not in authoritative_parents
                    and child_id not in parent_child_links.values()
                    and parent_child_links.get(sender_id) != child_id
                ):
                    parent_child_links[child_id] = sender_id

        for root_cid in known_root_ids:
            parent_child_links.pop(root_cid, None)
        for auth_cid, auth_pid in authoritative_parents.items():
            parent_child_links[auth_cid] = auth_pid

        # Update conversations_archive records
        for cid in target_convo_ids:
            cur.execute(
                """
                SELECT
                    COUNT(CASE WHEN step_type = 15 THEN 1 END) AS turn_cnt,
                    COALESCE(SUM(total_input_tokens), 0) AS in_toks,
                    COALESCE(SUM(output_tokens_total), 0) AS out_toks,
                    COALESCE(SUM(cached_tokens), 0) AS c_toks,
                    COALESCE(SUM(thinking_tokens), 0) AS th_toks,
                    MIN(CASE WHEN timestamp != '' THEN timestamp END) AS first_ts,
                    MAX(CASE WHEN timestamp != '' THEN timestamp END) AS last_ts
                FROM steps_archive
                WHERE convo_id = ?
                """,
                (cid,),
            )
            stats = cur.fetchone()
            turn_cnt = stats[0] if stats else 0
            in_toks = stats[1] if stats else 0
            out_toks = stats[2] if stats else 0
            c_toks = stats[3] if stats else 0
            th_toks = stats[4] if stats else 0
            first_ts = stats[5] if stats else None
            last_ts = stats[6] if stats else None

            cur.execute(
                """
                SELECT total_input_tokens, cached_tokens
                FROM steps_archive
                WHERE convo_id = ? AND step_type = 15 AND total_input_tokens > 0
                ORDER BY step_idx ASC
                LIMIT 1
                """,
                (cid,),
            )
            t1_row = cur.fetchone()
            t1_in_toks = int(t1_row[0] or 0) if t1_row else 0
            t1_c_toks = int(t1_row[1] or 0) if t1_row else 0

            # Calculate estimated cost USD
            cur.execute(
                """
                SELECT model_id, prompt_tokens_uncached, cached_tokens, output_tokens_total
                FROM steps_archive
                WHERE convo_id = ? AND step_type = 15
                """,
                (cid,),
            )
            cost_usd = 0.0
            for m_id, uncached_p, c_p, out_p in cur.fetchall():
                rates = get_model_rates(m_id, pricing_models)
                cost_usd += compute_turn_cost(
                    {
                        "prompt_tokens_uncached": uncached_p,
                        "cached_tokens": c_p,
                        "output_tokens_total": out_p,
                    },
                    rates,
                )

            # Attribute workspace and titles
            summary_info = summaries.get(cid, {})
            title = summary_info.get("title") or get_conversation_title(cid, agy_path)
            ws_name = summary_info.get("workspace_name") or fallback_ws_map.get(cid)
            ws_path = summary_info.get("workspace_path")
            traj_id = summary_info.get("trajectory_id")

            # Lineage parent
            parent_id = parent_child_links.get(cid)

            # Agent persona and subagent attributes
            traj_meta = convo_trajectory_meta.get(cid)
            raw_blob = convo_raw_blobs.get(cid)
            if traj_meta is None:
                cur.execute(
                    "SELECT raw_metadata_blob, agent_name, agent_description, is_subagent, subagent_role FROM conversations_archive WHERE convo_id = ?",
                    (cid,),
                )
                ex_row = cur.fetchone()
                if ex_row and ex_row[0]:
                    raw_blob = ex_row[0]
                    traj_meta = extract_trajectory_metadata(raw_blob)
                elif ex_row:
                    traj_meta = {
                        "agent_name": ex_row[1] or "default",
                        "agent_description": ex_row[2] or "",
                        "is_subagent": bool(ex_row[3]),
                        "subagent_role": ex_row[4] or "",
                    }
                else:
                    traj_meta = {}

            agent_name = traj_meta.get("agent_name") or "default"
            agent_desc = traj_meta.get("agent_description") or ""
            is_sub = 1 if (
                traj_meta.get("is_subagent")
                or traj_meta.get("parent_convo_id")
                or traj_meta.get("subagent_type")
            ) else 0
            sub_role = traj_meta.get("subagent_role") or ""
            if cid in known_root_ids:
                parent_id = None
            elif not parent_id and traj_meta.get("parent_convo_id"):
                parent_id = traj_meta["parent_convo_id"]

            _execute_sql_with_retry(
                cur,
                """
                INSERT INTO conversations_archive (
                    convo_id, parent_convo_id, workspace_name, workspace_path,
                    title, trajectory_id, turn_count,
                    total_input_tokens, total_output_tokens, cached_tokens,
                    thinking_tokens, estimated_cost_usd, first_turn_ts,
                    last_turn_ts, raw_metadata_blob, synced_at,
                    agent_name, agent_description, is_subagent, subagent_role,
                    turn1_input_tokens, turn1_cached_tokens
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(convo_id) DO UPDATE SET
                    parent_convo_id = CASE
                        WHEN excluded.is_subagent = 0 AND excluded.raw_metadata_blob IS NOT NULL AND (excluded.parent_convo_id IS NULL OR excluded.parent_convo_id = '')
                        THEN NULL
                        WHEN excluded.parent_convo_id IS NOT NULL AND excluded.parent_convo_id != ''
                        THEN excluded.parent_convo_id
                        ELSE conversations_archive.parent_convo_id
                    END,
                    workspace_name = COALESCE(excluded.workspace_name, conversations_archive.workspace_name),
                    workspace_path = COALESCE(excluded.workspace_path, conversations_archive.workspace_path),
                    title = CASE
                        WHEN excluded.title IS NOT NULL AND excluded.title != '' AND (conversations_archive.title IS NULL OR conversations_archive.title = '' OR conversations_archive.title LIKE 'Conversation %')
                        THEN excluded.title
                        ELSE COALESCE(excluded.title, conversations_archive.title)
                    END,
                    trajectory_id = COALESCE(excluded.trajectory_id, conversations_archive.trajectory_id),
                    turn_count = excluded.turn_count,
                    total_input_tokens = excluded.total_input_tokens,
                    total_output_tokens = excluded.total_output_tokens,
                    cached_tokens = excluded.cached_tokens,
                    thinking_tokens = excluded.thinking_tokens,
                    estimated_cost_usd = excluded.estimated_cost_usd,
                    first_turn_ts = excluded.first_turn_ts,
                    last_turn_ts = excluded.last_turn_ts,
                    raw_metadata_blob = COALESCE(excluded.raw_metadata_blob, conversations_archive.raw_metadata_blob),
                    synced_at = excluded.synced_at,
                    agent_name = COALESCE(excluded.agent_name, conversations_archive.agent_name),
                    agent_description = COALESCE(excluded.agent_description, conversations_archive.agent_description),
                    is_subagent = COALESCE(excluded.is_subagent, conversations_archive.is_subagent),
                    subagent_role = COALESCE(excluded.subagent_role, conversations_archive.subagent_role),
                    turn1_input_tokens = CASE WHEN excluded.turn1_input_tokens > 0 THEN excluded.turn1_input_tokens ELSE COALESCE(conversations_archive.turn1_input_tokens, 0) END,
                    turn1_cached_tokens = CASE WHEN excluded.turn1_input_tokens > 0 THEN excluded.turn1_cached_tokens ELSE COALESCE(conversations_archive.turn1_cached_tokens, 0) END
                """,
                (
                    cid,
                    parent_id,
                    ws_name,
                    ws_path,
                    title,
                    traj_id,
                    turn_cnt,
                    in_toks,
                    out_toks,
                    c_toks,
                    th_toks,
                    round(cost_usd, 6),
                    first_ts,
                    last_ts,
                    raw_blob,
                    now_iso,
                    agent_name,
                    agent_desc,
                    is_sub,
                    sub_role,
                    t1_in_toks,
                    t1_c_toks,
                ),
            )

        # Propagate all discovered parent_child_links
        if force:
            _execute_sql_with_retry(cur, "UPDATE conversations_archive SET parent_convo_id = NULL")
            existing_parents: Dict[str, Optional[str]] = {}
        else:
            cur.execute("SELECT convo_id, parent_convo_id FROM conversations_archive")
            existing_parents = {r[0]: r[1] for r in cur.fetchall()}
            if known_root_ids:
                for root_cid in known_root_ids:
                    if existing_parents.get(root_cid) is not None:
                        _execute_sql_with_retry(
                            cur,
                            "UPDATE conversations_archive SET parent_convo_id = NULL WHERE convo_id = ?",
                            (root_cid,),
                        )
        for child_id, parent_id in parent_child_links.items():
            if child_id in known_root_ids:
                continue
            if not force and existing_parents.get(child_id) == parent_id:
                continue
            _execute_sql_with_retry(
                cur,
                """
                UPDATE conversations_archive
                SET parent_convo_id = ?
                WHERE convo_id = ?
                """,
                (parent_id, child_id),
            )

    # Record conversations_last_sync_mtime
    _execute_sql_with_retry(
        cur,
        """
        INSERT INTO vault_sync_state (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = excluded.updated_at
        """,
        ("conversations_last_sync_mtime", str(sync_start_time), now_iso),
    )

    _commit_with_retry(vault_conn)
    vault_conn.close()

    stats = {
        "conversations_synced": len(conversations_synced_set),
        "steps_synced": steps_synced_count,
        "tool_calls_synced": tool_calls_synced_count,
        "discovered_databases": discovered_count,
        "scanned_databases": scanned_count,
    }
    stats["vault_bytes"] = Path(vault_path).stat().st_size if Path(vault_path).exists() else 0
    return stats


def backfill_vault_agent_metadata(
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    antigravity_dir: Union[str, Path] = DEFAULT_ANTIGRAVITY_DIR,
) -> int:
    """
    Idempotent one-pass backfill for existing vaults (Milestone 64 / ADR-078).
    Populates raw_metadata_blob, agent_name, agent_description, is_subagent, and subagent_role
    for historical conversations in conversations_archive.
    Returns count of updated records.
    """
    v_file = Path(vault_path).resolve()
    if not v_file.exists():
        return 0

    conn = get_vault_connection(v_file)
    cur = conn.cursor()

    cur.execute("SELECT convo_id, raw_metadata_blob, agent_name, is_subagent FROM conversations_archive")
    rows = cur.fetchall()

    agy_dir = Path(antigravity_dir).resolve()
    conv_dir = agy_dir / "conversations"

    updated_count = 0
    for cid, existing_blob, existing_agent, existing_sub in rows:
        raw_blob = existing_blob
        if not raw_blob and conv_dir.exists():
            db_file = conv_dir / f"{cid}.db"
            if db_file.exists():
                raw_blob = _read_convo_db_trajectory_blob(db_file)

        if not raw_blob:
            continue

        traj_meta = extract_trajectory_metadata(raw_blob)
        agent_name = traj_meta.get("agent_name") or "default"
        agent_desc = traj_meta.get("agent_description") or ""
        parent_id = (traj_meta.get("parent_convo_id") or "").strip()
        is_sub = 1 if (
            traj_meta.get("is_subagent")
            or parent_id
            or traj_meta.get("subagent_type")
        ) else 0
        sub_role = traj_meta.get("subagent_role") or ""
        resolved_title = get_conversation_title(cid, agy_dir)

        _execute_sql_with_retry(
            cur,
            """
            UPDATE conversations_archive
            SET
                raw_metadata_blob = COALESCE(?, raw_metadata_blob),
                agent_name = ?,
                agent_description = ?,
                is_subagent = ?,
                subagent_role = ?,
                parent_convo_id = CASE
                    WHEN ? != '' THEN ?
                    WHEN ? = 0 THEN NULL
                    ELSE parent_convo_id
                END,
                title = CASE
                    WHEN (title IS NULL OR title = '' OR title LIKE 'Conversation %') AND ? NOT LIKE 'Conversation %'
                    THEN ?
                    ELSE title
                END
            WHERE convo_id = ?
            """,
            (raw_blob, agent_name, agent_desc, is_sub, sub_role, parent_id, parent_id, is_sub, resolved_title, resolved_title, cid),
        )
        updated_count += 1

    _commit_with_retry(conn)
    conn.close()
    return updated_count


def sync_log_events_to_vault(
    log_path: Union[str, Path] = DEFAULT_LOG_PATH,
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
) -> Dict[str, Any]:
    """
    Tail and ingest discrete 429 exhaustion and lifecycle events into log_events_archive.

    Resilient to log file truncations on IDE restart:
    - Compares current file size against last offset stored in `vault_sync_state`.
    - If file size < last offset, detects truncation and resets offset to 0.
    - Generates SHA-256 fingerprint for deduplicated event insertions.
    """
    path = Path(log_path).resolve()
    if not path.exists():
        return {"events_synced": 0, "offset": 0, "truncated": False}

    try:
        current_size = path.stat().st_size
    except Exception:
        return {"events_synced": 0, "offset": 0, "truncated": False}

    vault_conn = get_vault_connection(vault_path)
    try:
        cur = vault_conn.cursor()

        state_key = f"log_offset:{str(path)}"
        cur.execute("SELECT value FROM vault_sync_state WHERE key = ?", (state_key,))
        row = cur.fetchone()
        last_offset = int(row[0]) if row else 0

        truncated = False
        if current_size < last_offset:
            truncated = True
            last_offset = 0

        events_synced = 0
        new_offset = last_offset
        year = datetime.now(timezone.utc).year
        try:
            is_default_log = path == DEFAULT_LOG_PATH.resolve()
        except OSError:
            is_default_log = False

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(last_offset)
            while True:
                line_offset = f.tell()
                line = f.readline()
                if not line:
                    new_offset = line_offset
                    break

                stripped = line.strip()
                if not stripped:
                    continue

                ts = parse_glog_timestamp(line, year=year, local_tz=True if is_default_log else None)
                ts_iso = ts.isoformat() if ts else None

                # Extract level
                level = "INFO"
                if line and line[0] in ("I", "W", "E", "F"):
                    level_map = {"I": "INFO", "W": "WARNING", "E": "ERROR", "F": "FATAL"}
                    level = level_map.get(line[0], "INFO")

                # Determine event type & code
                event_type = "LOG"
                code = None
                reason = None

                if EXHAUSTION_PATTERN.search(line):
                    event_type = "RESOURCE_EXHAUSTED"
                    code = 429
                    reason = "RESOURCE_EXHAUSTED"
                elif level in ("ERROR", "FATAL") or "error" in line.lower():
                    event_type = "ERROR"
                elif any(kw in line.lower() for kw in ("start", "stop", "shutdown", "listen", "init", "ready")):
                    event_type = "LIFECYCLE"

                # Generate unique fingerprint
                fp_input = f"{ts_iso or ''}:{stripped}"
                fingerprint = hashlib.sha256(fp_input.encode("utf-8")).hexdigest()

                cur.execute(
                    """
                    INSERT OR IGNORE INTO log_events_archive (
                        event_fingerprint, timestamp, timestamp_iso,
                        level, event_type, raw_line, code, reason, file_offset
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fingerprint,
                        ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "",
                        ts_iso,
                        level,
                        event_type,
                        stripped,
                        code,
                        reason,
                        line_offset,
                    ),
                )
                if cur.rowcount > 0:
                    events_synced += 1

        # Record high-watermark offset
        cur.execute(
            """
            INSERT INTO vault_sync_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (state_key, str(new_offset), datetime.now(timezone.utc).isoformat()),
        )
        vault_conn.commit()
    except (sqlite3.Error, OSError) as exc:
        logger.warning("Error syncing log events to vault: %s", exc)
    finally:
        try:
            vault_conn.close()
        except sqlite3.Error:
            pass

    return {
        "events_synced": events_synced,
        "offset": new_offset,
        "truncated": truncated,
    }


def sync_weekly_trends_to_vault(
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    pricing_models: Optional[Dict[str, Any]] = None,
    ledger_path: Union[str, Path] = Path(__file__).resolve().parent.parent / "data" / "exhaustion_ledger.json",
    reference_time: Optional[datetime] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Sync weekly cycle aggregates from steps_archive and exhaustion_ledger.json
    into weekly_cycles_archive in the Vault.
    Delegates to src.weekly_trends.sync_weekly_trends_to_vault.
    """
    return _sync_weekly_trends_to_vault_impl(
        vault_path=vault_path,
        pricing_models=pricing_models,
        ledger_path=ledger_path,
        reference_time=reference_time,
        force=force,
    )


def get_weekly_trends(
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    limit_weeks: int = 12,
    fallback_turns: Optional[List[Dict[str, Any]]] = None,
    pricing_models: Optional[Dict[str, Any]] = None,
    ledger_path: Union[str, Path] = Path(__file__).resolve().parent.parent / "data" / "exhaustion_ledger.json",
    reference_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Retrieve historical weekly cycles from weekly_cycles_archive in the Vault.
    Delegates to src.weekly_trends.get_weekly_trends.
    """
    return _get_weekly_trends_impl(
        vault_path=vault_path,
        limit_weeks=limit_weeks,
        fallback_turns=fallback_turns,
        pricing_models=pricing_models,
        ledger_path=ledger_path,
        reference_time=reference_time,
    )


def sync_subscription_to_vault(
    pricing_config_or_path: Optional[Union[Dict[str, Any], Path, str]] = None,
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Sync subscription history intervals and active plan state from config/pricing.json
    into `subscription_history_archive` and `vault_sync_state` in the Vault.
    """
    from src.temporal import DEFAULT_PRICING_FILE
    cfg_path = Path(pricing_config_or_path) if pricing_config_or_path else DEFAULT_PRICING_FILE
    if isinstance(pricing_config_or_path, dict):
        cfg = pricing_config_or_path
    elif cfg_path.exists():
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    else:
        return {"synced": 0, "active_tier": "unknown"}

    sub = cfg.get("subscription", {})
    history = cfg.get("subscription_history", [])
    now_iso = datetime.now(timezone.utc).isoformat()

    sub_raw = json.dumps({"sub": sub, "history": history}, sort_keys=True)
    sub_hash = hashlib.sha256(sub_raw.encode("utf-8")).hexdigest()[:16]

    conn = get_vault_connection(vault_path)
    cur = conn.cursor()

    if not force:
        try:
            cur.execute("SELECT value FROM vault_sync_state WHERE key = 'subscription:config_hash'")
            cached_hash = cur.fetchone()
            if cached_hash and cached_hash[0] == sub_hash:
                cur.execute("SELECT COUNT(*) FROM subscription_history_archive")
                count_row = cur.fetchone()
                if count_row and count_row[0] > 0:
                    conn.close()
                    return {"synced": 0, "active_tier": sub.get("tier", "unknown")}
        except Exception:
            pass

    synced_count = 0
    valid_froms = [entry.get("valid_from", "") for entry in history if entry.get("valid_from")]
    if valid_froms:
        placeholders = ",".join(["?"] * len(valid_froms))
        cur.execute(f"DELETE FROM subscription_history_archive WHERE valid_from NOT IN ({placeholders})", valid_froms)

    for entry in history:
        ql = entry.get("quota_limits", {})
        cur.execute(
            """
            INSERT INTO subscription_history_archive (
                tier, name, monthly_price_gbp, monthly_price_usd, renewal_day,
                valid_from, valid_to, gemini_5h_capacity_usd, gemini_weekly_capacity_usd,
                claude_5h_capacity_usd, claude_weekly_capacity_usd, burst_5h_tokens, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(valid_from) DO UPDATE SET
                tier = excluded.tier,
                name = excluded.name,
                monthly_price_gbp = excluded.monthly_price_gbp,
                monthly_price_usd = excluded.monthly_price_usd,
                renewal_day = excluded.renewal_day,
                valid_to = excluded.valid_to,
                gemini_5h_capacity_usd = excluded.gemini_5h_capacity_usd,
                gemini_weekly_capacity_usd = excluded.gemini_weekly_capacity_usd,
                claude_5h_capacity_usd = excluded.claude_5h_capacity_usd,
                claude_weekly_capacity_usd = excluded.claude_weekly_capacity_usd,
                burst_5h_tokens = excluded.burst_5h_tokens,
                created_at = excluded.created_at
            """,
            (
                entry.get("tier", ""),
                entry.get("name", ""),
                float(entry.get("monthly_price_gbp") or 0.0),
                float(entry.get("monthly_price_usd") or 0.0),
                int(entry.get("renewal_day") or 24),
                entry.get("valid_from", ""),
                entry.get("valid_to"),
                float(ql.get("gemini_5h_capacity_usd") or 0.0),
                float(ql.get("gemini_weekly_capacity_usd") or 0.0),
                float(ql.get("claude_5h_capacity_usd") or 0.0),
                float(ql.get("claude_weekly_capacity_usd") or 0.0),
                int(ql.get("burst_5h_tokens") or 0),
                now_iso,
            ),
        )
        synced_count += 1

    # Record active state pointers in vault_sync_state
    sub_ql = sub.get("quota_limits", {})
    state_updates = [
        ("subscription:current_tier", str(sub.get("tier", ""))),
        ("subscription:current_name", str(sub.get("name", ""))),
        ("subscription:monthly_price_gbp", str(sub.get("monthly_price_gbp", 0.0))),
        ("subscription:monthly_price_usd", str(sub.get("monthly_price_usd", 0.0))),
        ("subscription:gemini_5h_capacity_usd", str(sub_ql.get("gemini_5h_capacity_usd", 0.0))),
        ("subscription:gemini_weekly_capacity_usd", str(sub_ql.get("gemini_weekly_capacity_usd", 0.0))),
        ("subscription:claude_5h_capacity_usd", str(sub_ql.get("claude_5h_capacity_usd", 0.0))),
        ("subscription:claude_weekly_capacity_usd", str(sub_ql.get("claude_weekly_capacity_usd", 0.0))),
        ("subscription:config_hash", sub_hash),
    ]
    for k, v in state_updates:
        cur.execute(
            """
            INSERT INTO vault_sync_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (k, v, now_iso),
        )

    conn.commit()
    conn.close()

    return {
        "synced": synced_count,
        "active_tier": sub.get("tier", "unknown"),
    }


class VaultMarker(tuple):
    """3-element tuple (first_mark, depth, compaction_count) that unpacks as 2 elements for backwards compatibility."""
    def __new__(cls, first_mark: int, depth: int, compaction_count: int = 1):
        return super().__new__(cls, (first_mark, depth))

    def __init__(self, first_mark: int, depth: int, compaction_count: int = 1):
        self.first_mark = first_mark
        self.depth = depth
        self.compaction_count = compaction_count
        self.epoch = compaction_count + 1


class TruncationResult(tuple):
    """3-element tuple (has_truncated, first_mark, depth) that unpacks as 3 elements with epoch attributes."""
    def __new__(cls, has_truncated: bool, first_mark: Optional[int], depth: Optional[int], compaction_count: int = 0):
        return super().__new__(cls, (has_truncated, first_mark, depth))

    def __init__(self, has_truncated: bool, first_mark: Optional[int], depth: Optional[int], compaction_count: int = 0):
        self.has_truncated = has_truncated
        self.first_mark = first_mark
        self.depth = depth
        self.compaction_count = compaction_count
        self.epoch = (compaction_count + 1) if has_truncated else 1


def get_vault_truncation_markers(
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
) -> Dict[str, Tuple[int, int]]:
    """
    Query steps_archive for CONTEXT_SUMMARY truncation markers.
    Strictly read-only (?mode=ro, uri=True, ADR-001).
    Returns dict: convo_id -> VaultMarker(first_truncation_step, depth_at_truncation, compaction_count).
    """
    vault_file = Path(vault_path).resolve()
    if not vault_file.exists():
        return {}

    markers: Dict[str, Tuple[int, int]] = {}
    uri = f"file:{vault_file}?mode=ro"
    conn = None
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=60.0)
        conn.execute("PRAGMA busy_timeout = 60000;")
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='steps_archive'")
        if not cur.fetchone():
            return {}

        cols = {col[1] for col in cur.execute("PRAGMA table_info(steps_archive)").fetchall()}
        prefix_conditions = (
            "payload_text LIKE '<CONTEXT_SUMMARY>%' OR payload_text LIKE ' <CONTEXT_SUMMARY>%' "
            "OR payload_text LIKE '\n<CONTEXT_SUMMARY>%' OR payload_text LIKE '\r\n<CONTEXT_SUMMARY>%'"
        )
        if "step_type" in cols:
            condition = (
                f"(step_type = 23 OR ("
                f"step_type NOT IN (14, 15, 17, 23, 90, 101, 132) "
                f"AND ({prefix_conditions})"
                f"))"
            )
        else:
            condition = f"({prefix_conditions})"

        query = f"""
        WITH marks AS (
            SELECT convo_id, COUNT(*) AS comp_count, MIN(step_idx) AS first_mark
            FROM steps_archive
            WHERE {condition}
            GROUP BY convo_id
        )
        SELECT m.convo_id, m.first_mark,
          (SELECT MAX(COALESCE(prompt_tokens_uncached,0)+COALESCE(cached_tokens,0))
             FROM steps_archive s WHERE s.convo_id=m.convo_id AND s.step_idx < m.first_mark) AS depth,
          m.comp_count
        FROM marks m;
        """
        cur.execute(query)
        rows = cur.fetchall()
        for cid, fmark, depth, c_count in rows:
            if depth is None or depth <= 0:
                cur2 = conn.cursor()
                cur2.execute(
                    "SELECT MAX(COALESCE(prompt_tokens_uncached,0)+COALESCE(cached_tokens,0)) FROM steps_archive WHERE convo_id=?",
                    (cid,),
                )
                max_row = cur2.fetchone()
                depth = max_row[0] if max_row and max_row[0] else 1
            markers[cid] = VaultMarker(int(fmark), int(depth), int(c_count or 1))
    except (sqlite3.Error, OSError) as exc:
        logger.debug("Error scanning first truncation markers: %s", exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass

    return markers


# Strict regex pattern for genuine system context summary headers (ADR-070).
# Rejects substrings embedded in tool calls, diffs, or chat discussions.
STRICT_CONTEXT_SUMMARY_PATTERN = re.compile(
    r"^\s*<CONTEXT_SUMMARY>(?:\s|\n|\r|compressed|\b)",
    re.IGNORECASE,
)


def scan_conversation_truncation(
    db_path: Union[str, Path],
    max_retries: int = 3,
    retry_delay_seconds: float = 0.1,
) -> TruncationResult:
    """
    Scan an upstream conversation SQLite database for genuine context compaction checkpoints.
    Strictly read-only (?mode=ro, uri=True, ADR-001).
    Returns TruncationResult(has_truncated, first_truncation_step, depth_at_truncation, compaction_count).
    """
    p = Path(db_path)
    if not p.exists():
        return TruncationResult(False, None, None, 0)

    uri = f"file:{p.resolve()}?mode=ro"
    for attempt in range(max_retries):
        conn = None
        try:
            conn = sqlite3.connect(uri, uri=True, timeout=60.0)
            conn.execute("PRAGMA busy_timeout = 60000;")
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='steps'")
            if not cur.fetchone():
                return TruncationResult(False, None, None, 0)

            cols = {col[1] for col in cur.execute("PRAGMA table_info(steps)").fetchall()}
            compaction_steps = []

            if "step_type" in cols:
                # 1. Authoritative Antigravity compaction: step_type = 23 (CHECKPOINT)
                cur.execute("SELECT idx FROM steps WHERE step_type = 23 ORDER BY idx ASC")
                compaction_steps = [int(r[0]) for r in cur.fetchall()]

                # 2. Strict system header fallback for non-standard/synthetic fixtures:
                # Explicitly excludes step_type 14 (USER_INPUT), 15 (PLANNER_RESPONSE),
                # 17 (SESSION_INIT), 90 (AGENT_STATE), 101 (BACKGROUND_TASK/MESSAGE), 132 (TOOL_CALL).
                payload_cols = [c for c in ("step_payload", "metadata") if c in cols]
                if payload_cols:
                    select_sql = ", ".join(payload_cols)
                    cur.execute(
                        f"SELECT idx, {select_sql} FROM steps "
                        "WHERE step_type NOT IN (14, 15, 17, 23, 90, 101, 132) "
                        "ORDER BY idx ASC"
                    )
                    for row in cur.fetchall():
                        s_idx = row[0]
                        for p_data in row[1:]:
                            if p_data is not None:
                                text = p_data.decode("utf-8", errors="ignore") if isinstance(p_data, bytes) else str(p_data or "")
                                if STRICT_CONTEXT_SUMMARY_PATTERN.match(text):
                                    if int(s_idx) not in compaction_steps:
                                        compaction_steps.append(int(s_idx))
            elif "step_payload" in cols or "metadata" in cols:
                # Fallback for tables without step_type column: enforce strict prefix match
                payload_cols = [c for c in ("step_payload", "metadata") if c in cols]
                select_sql = ", ".join(payload_cols)
                cur.execute(f"SELECT idx, {select_sql} FROM steps ORDER BY idx ASC")
                for row in cur.fetchall():
                    s_idx = row[0]
                    for p_data in row[1:]:
                        if p_data is not None:
                            text = p_data.decode("utf-8", errors="ignore") if isinstance(p_data, bytes) else str(p_data or "")
                            if STRICT_CONTEXT_SUMMARY_PATTERN.match(text):
                                if int(s_idx) not in compaction_steps:
                                    compaction_steps.append(int(s_idx))

            if not compaction_steps:
                return TruncationResult(False, None, None, 0)

            compaction_steps.sort()
            comp_count = len(compaction_steps)
            first_mark = compaction_steps[0]

            # Find max depth before first_mark
            cur.execute("SELECT idx, metadata FROM steps WHERE step_type = 15 AND idx < ? ORDER BY idx ASC", (first_mark,))
            prior_steps = cur.fetchall()
            max_depth = 0
            for s_idx, m_blob in prior_steps:
                tel = extract_step_telemetry(m_blob)
                if tel:
                    d = tel.get("prompt_tokens_uncached", 0) + tel.get("cached_tokens", 0)
                    if d > max_depth:
                        max_depth = d

            if max_depth <= 0:
                cur.execute("SELECT idx, metadata FROM steps WHERE step_type = 15 ORDER BY idx ASC")
                all_steps = cur.fetchall()
                for s_idx, m_blob in all_steps:
                    tel = extract_step_telemetry(m_blob)
                    if tel:
                        d = tel.get("prompt_tokens_uncached", 0) + tel.get("cached_tokens", 0)
                        if d > max_depth:
                            max_depth = d

            depth = max_depth if max_depth > 0 else 1
            return TruncationResult(True, first_mark, int(depth), comp_count)
        except sqlite3.OperationalError as exc:
            if attempt < max_retries - 1:
                time.sleep(retry_delay_seconds * (2 ** attempt))
                continue
            logger.debug("OperationalError scanning conversation truncation in %s: %s", db_path, exc)
            return TruncationResult(False, None, None, 0)
        except (sqlite3.Error, OSError) as exc:
            logger.debug("Error scanning conversation truncation in %s: %s", db_path, exc)
            return TruncationResult(False, None, None, 0)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
    return TruncationResult(False, None, None, 0)


def sync_quota_snapshot_to_vault(
    live_quota: Optional[Dict[str, Any]],
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    timestamp_utc: Optional[str] = None,
    active_status: str = "SAFE_IN_QUOTA",
) -> Dict[str, Any]:
    """
    Persist deduplicated live quota snapshots from RetrieveUserQuotaSummary into
    `quota_snapshots_archive` in the Vault (Milestone 93).

    Only inserts a new row when at least one bucket's remaining_fraction, reset_time,
    or active_status has changed compared to the latest stored snapshot.
    """
    if not live_quota or not isinstance(live_quota, dict):
        return {"inserted": False, "reason": "unavailable"}
    if not live_quota.get("available") and "gemini_5h" not in live_quota and "gemini" not in live_quota:
        return {"inserted": False, "reason": "unavailable"}

    gem_nested = live_quota.get("gemini") if isinstance(live_quota.get("gemini"), dict) else {}
    cg_nested = live_quota.get("claude_gpt") if isinstance(live_quota.get("claude_gpt"), dict) else {}

    g5 = live_quota.get("gemini_5h") or gem_nested.get("five_hour") or {}
    gw = live_quota.get("gemini_weekly") or gem_nested.get("weekly") or {}
    c5 = live_quota.get("claude_5h") or cg_nested.get("five_hour") or {}
    cw = live_quota.get("claude_weekly") or cg_nested.get("weekly") or {}

    def _frac(bucket: Dict[str, Any]) -> Optional[float]:
        val = bucket.get("remaining_fraction")
        if val is not None:
            return round(float(val), 7)
        rem_pct = bucket.get("remaining_pct")
        if rem_pct is not None:
            return round(float(rem_pct) / 100.0, 7)
        return None

    def _used_pct(bucket: Dict[str, Any], rem_frac: Optional[float]) -> Optional[float]:
        if bucket.get("used_pct") is not None:
            return round(float(bucket["used_pct"]), 4)
        if rem_frac is not None:
            return round(max(0.0, (1.0 - rem_frac) * 100.0), 4)
        return None

    g5_rem = _frac(g5)
    g5_used = _used_pct(g5, g5_rem)
    g5_reset = str(g5.get("reset_time") or "")

    gw_rem = _frac(gw)
    gw_used = _used_pct(gw, gw_rem)
    gw_reset = str(gw.get("reset_time") or "")

    c5_rem = _frac(c5)
    c5_used = _used_pct(c5, c5_rem)
    c5_reset = str(c5.get("reset_time") or "")

    cw_rem = _frac(cw)
    cw_used = _used_pct(cw, cw_rem)
    cw_reset = str(cw.get("reset_time") or "")

    if active_status == "SAFE_IN_QUOTA":
        if gw_rem is not None and gw_rem <= 0.001:
            active_status = "WEEKLY_EXHAUSTED"
        elif g5_rem is not None and g5_rem <= 0.0:
            active_status = "BURNING_AI_CREDITS"

    # When a 5h bucket is unused (remaining == 1.0), Connect-RPC shifts its resetTime
    # forward on every poll (now + 5h). Normalize 100% 5h reset times in the fingerprint
    # so idle 5h tracks do not trigger duplicate snapshot rows.
    g5_fp_reset = "" if (g5_rem is not None and g5_rem >= 1.0) else g5_reset
    c5_fp_reset = "" if (c5_rem is not None and c5_rem >= 1.0) else c5_reset

    state_tuple = (
        g5_rem, g5_fp_reset,
        gw_rem, gw_reset,
        c5_rem, c5_fp_reset,
        cw_rem, cw_reset,
        active_status,
    )
    state_hash = hashlib.sha256(json.dumps(state_tuple).encode("utf-8")).hexdigest()[:24]
    ts_iso = timestamp_utc or datetime.now(timezone.utc).isoformat()

    conn = None
    try:
        conn = get_vault_connection(vault_path, busy_timeout=60000)
        cur = conn.cursor()

        # Check latest snapshot state to skip consecutive identical polls
        cur.execute(
            """
            SELECT id, snapshot_fingerprint, timestamp_utc, gemini_weekly_remaining, gemini_weekly_reset_utc, gemini_5h_remaining
            FROM quota_snapshots_archive
            ORDER BY timestamp_utc DESC, id DESC
            LIMIT 1
            """
        )
        last_row = cur.fetchone()
        if last_row and last_row[1] and str(last_row[1]).startswith(state_hash):
            return {"inserted": False, "fingerprint": last_row[1]}

        prev_snap_dict = None
        if last_row:
            prev_snap_dict = {
                "id": last_row[0],
                "timestamp_utc": last_row[2],
                "gemini_weekly_remaining": last_row[3],
                "gemini_weekly_reset_utc": last_row[4],
                "gemini_5h_remaining": last_row[5],
            }

        # Include ts_iso suffix only if an earlier non-adjacent snapshot had the same hash
        cur.execute(
            "SELECT 1 FROM quota_snapshots_archive WHERE snapshot_fingerprint = ?",
            (state_hash,),
        )
        fp_unique = state_hash if not cur.fetchone() else f"{state_hash}:{ts_iso}"

        _execute_sql_with_retry(
            cur,
            """
            INSERT OR IGNORE INTO quota_snapshots_archive (
                snapshot_fingerprint, timestamp_utc,
                gemini_5h_remaining, gemini_5h_used_pct, gemini_5h_reset_utc,
                gemini_weekly_remaining, gemini_weekly_used_pct, gemini_weekly_reset_utc,
                claude_5h_remaining, claude_5h_used_pct, claude_5h_reset_utc,
                claude_weekly_remaining, claude_weekly_used_pct, claude_weekly_reset_utc,
                active_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fp_unique,
                ts_iso,
                g5_rem, g5_used, g5_reset,
                gw_rem, gw_used, gw_reset,
                c5_rem, c5_used, c5_reset,
                cw_rem, cw_used, cw_reset,
                active_status,
            ),
        )
        inserted = cur.rowcount > 0

        bonus_recorded = None
        if inserted and prev_snap_dict:
            from src.quota_regime import (
                DEFAULT_EXHAUSTION_LEDGER_PATH,
                _atomic_write_json,
                check_early_weekly_reset_bonus,
            )
            curr_snap_dict = {
                "id": cur.lastrowid,
                "timestamp_utc": ts_iso,
                "gemini_weekly_remaining": gw_rem,
                "gemini_weekly_reset_utc": gw_reset,
                "gemini_5h_remaining": g5_rem,
            }
            bonus = check_early_weekly_reset_bonus(prev_snap_dict, curr_snap_dict)
            if bonus:
                bonus_recorded = bonus
                _execute_sql_with_retry(
                    cur,
                    """
                    INSERT OR IGNORE INTO log_events_archive (
                        event_fingerprint, timestamp, timestamp_iso, level,
                        event_type, raw_line, code, reason, file_offset
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"bonus-{bonus['id']}",
                        bonus["timestamp_iso"],
                        bonus["timestamp_iso"],
                        "I",
                        "QUOTA_RESET_BONUS",
                        bonus["description"],
                        200,
                        "QUOTA_RESET_BONUS",
                        0,
                    ),
                )
                if Path(vault_path).resolve() == DEFAULT_VAULT_PATH.resolve():
                    try:
                        if DEFAULT_EXHAUSTION_LEDGER_PATH.exists():
                            with open(DEFAULT_EXHAUSTION_LEDGER_PATH, "r", encoding="utf-8") as lf:
                                ledger_data = json.load(lf)
                            target_list = (
                                ledger_data.get("incidents")
                                if isinstance(ledger_data, dict) and isinstance(ledger_data.get("incidents"), list)
                                else (ledger_data if isinstance(ledger_data, list) else None)
                            )
                            if isinstance(target_list, list) and not any(
                                isinstance(x, dict) and (x.get("id") == bonus["id"] or x.get("incident_id") == bonus["id"])
                                for x in target_list
                            ):
                                bonus_dt = parse_timestamp(bonus.get("timestamp_iso"))
                                prev_reset_dt = parse_timestamp(bonus.get("prev_weekly_reset_utc"))
                                hour_display = (
                                    bonus_dt.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M:%S UTC")
                                    if bonus_dt is not None
                                    else ""
                                )
                                turns_count = 0
                                models_breakdown: Dict[str, int] = {}
                                if bonus_dt is not None:
                                    cycle_start_dt = (
                                        prev_reset_dt.astimezone(timezone.utc) - timedelta(days=7)
                                        if prev_reset_dt is not None
                                        else bonus_dt.astimezone(timezone.utc) - timedelta(days=7)
                                    )
                                    cycle_start_str = cycle_start_dt.strftime("%Y-%m-%dT%H:%M:%S")
                                    try:
                                        model_rows = cur.execute(
                                            """
                                            SELECT COALESCE(NULLIF(model_name, ''), NULLIF(model_id, ''), 'Unknown') AS model_label,
                                                   COUNT(*) AS cnt
                                            FROM steps_archive
                                            WHERE step_type IN (15, 23)
                                              AND (
                                                  step_type = 15
                                                  OR COALESCE(prompt_tokens_uncached, 0) + COALESCE(cached_tokens, 0) + COALESCE(output_tokens_total, 0) > 0
                                              )
                                              AND timestamp >= ?
                                              AND timestamp <= ?
                                            GROUP BY model_label
                                            ORDER BY cnt DESC, model_label ASC
                                            """,
                                            (cycle_start_str, bonus["timestamp_iso"]),
                                        ).fetchall()
                                        for m_label, m_cnt in model_rows:
                                            cnt_int = int(m_cnt or 0)
                                            if cnt_int > 0:
                                                models_breakdown[str(m_label)] = cnt_int
                                                turns_count += cnt_int
                                    except sqlite3.Error as sq_exc:
                                        logger.debug("Skipping bonus turn breakdown lookup: %s", sq_exc)

                                target_list.append({
                                    "id": bonus["id"],
                                    "incident_id": bonus["id"],
                                    "timestamp_iso": bonus["timestamp_iso"],
                                    "hour_timestamp": bonus["hour_bucket"],
                                    "hour_bucket": bonus["hour_bucket"],
                                    "hour_display": hour_display,
                                    "start_utc": bonus["timestamp_iso"],
                                    "end_utc": bonus["timestamp_iso"],
                                    "code": 200,
                                    "reason": "QUOTA_RESET_BONUS",
                                    "event_type": "QUOTA_RESET_BONUS",
                                    "level": "I",
                                    "turns_count": turns_count,
                                    "credits_burned": 0,
                                    "credit_burn_usd": 0.0,
                                    "credit_burn_gbp": 0.0,
                                    "bonus_pct_forgiven": bonus["bonus_pct_forgiven"],
                                    "bonus_credits_forgiven": bonus["bonus_credits_forgiven"],
                                    "bonus_value_usd": bonus["bonus_value_usd"],
                                    "bonus_value_gbp": bonus["bonus_value_gbp"],
                                    "pre_reset_5h_rem_pct": bonus["pre_reset_5h_rem_pct"],
                                    "post_reset_5h_rem_pct": bonus["post_reset_5h_rem_pct"],
                                    "delta_5h_pct": bonus["delta_5h_pct"],
                                    "prev_weekly_reset_utc": bonus["prev_weekly_reset_utc"],
                                    "new_weekly_reset_utc": bonus["new_weekly_reset_utc"],
                                    "models": models_breakdown,
                                    "description": bonus["description"],
                                })
                                _atomic_write_json(DEFAULT_EXHAUSTION_LEDGER_PATH, ledger_data)
                    except (OSError, json.JSONDecodeError) as l_exc:
                        logger.warning("Failed appending early reset bonus to exhaustion ledger: %s", l_exc)

        _commit_with_retry(conn)
        res_out: Dict[str, Any] = {"inserted": inserted, "fingerprint": fp_unique, "timestamp_utc": ts_iso}
        if bonus_recorded:
            res_out["early_reset_bonus"] = bonus_recorded
        return res_out
    except (sqlite3.Error, OSError) as exc:
        logger.warning("Error syncing quota snapshot to vault: %s", exc)
        return {"inserted": False, "error": str(exc)}
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass


_QUOTA_FALLBACK_SPECS = (
    ("gemini_weekly", "gemini", "weekly", "gemini_weekly_remaining", "gemini_weekly_used_pct", "gemini_weekly_reset_utc", "gemini-weekly", "Weekly Limit Remaining"),
    ("gemini_5h", "gemini", "five_hour", "gemini_5h_remaining", "gemini_5h_used_pct", "gemini_5h_reset_utc", "gemini-5h", "Five Hour Limit Remaining"),
    ("claude_weekly", "claude_gpt", "weekly", "claude_weekly_remaining", "claude_weekly_used_pct", "claude_weekly_reset_utc", "3p-weekly", "Weekly Limit Remaining"),
    ("claude_5h", "claude_gpt", "five_hour", "claude_5h_remaining", "claude_5h_used_pct", "claude_5h_reset_utc", "3p-5h", "Five Hour Limit Remaining"),
)


def load_latest_quota_snapshot_fallback(
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    reference_time: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """
    Read the latest non-expired server quota snapshot from `quota_snapshots_archive` in RO mode.

    Used when Connect-RPC (`language_server`) is temporarily offline during boot or shutdown so
    weekly reset anchors and calibrated headroom survive transient outages without mutating Vault.
    """
    v_file = Path(vault_path).resolve()
    if not v_file.exists():
        return None

    ref_dt = reference_time or datetime.now(timezone.utc)
    if ref_dt.tzinfo is None:
        ref_dt = ref_dt.replace(tzinfo=timezone.utc)
    else:
        ref_dt = ref_dt.astimezone(timezone.utc)

    conn: Optional[sqlite3.Connection] = None
    try:
        uri = f"file:{urllib.parse.quote(str(v_file))}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000;")
        rows = conn.execute(
            """
            SELECT
                timestamp_utc,
                gemini_5h_remaining, gemini_5h_used_pct, gemini_5h_reset_utc,
                gemini_weekly_remaining, gemini_weekly_used_pct, gemini_weekly_reset_utc,
                claude_5h_remaining, claude_5h_used_pct, claude_5h_reset_utc,
                claude_weekly_remaining, claude_weekly_used_pct, claude_weekly_reset_utc
            FROM quota_snapshots_archive
            ORDER BY timestamp_utc DESC, id DESC
            LIMIT 10
            """
        ).fetchall()
    except sqlite3.Error as exc:
        logger.debug("Vault quota fallback query unavailable: %s", exc)
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass

    for row in rows:
        parsed: Dict[str, Any] = {
            "available": True,
            "source": "vault_fallback",
            "fallback_timestamp_utc": row["timestamp_utc"],
            "description": "",
            "gemini_weekly": None,
            "gemini_5h": None,
            "claude_weekly": None,
            "claude_5h": None,
            "tracks": {},
        }
        has_active_bucket = False
        for key, track_id, slot, rem_col, used_col, reset_col, b_id, display_name in _QUOTA_FALLBACK_SPECS:
            reset_iso = row[reset_col] or ""
            rem_raw = row[rem_col]
            if not reset_iso or rem_raw is None:
                continue
            reset_dt = parse_timestamp(str(reset_iso))
            if reset_dt is None:
                continue
            if reset_dt.tzinfo is None:
                reset_dt = reset_dt.replace(tzinfo=timezone.utc)
            else:
                reset_dt = reset_dt.astimezone(timezone.utc)
            if reset_dt <= ref_dt:
                continue

            rem_frac = round(max(0.0, min(1.0, float(rem_raw))), 4)
            rem_pct = round(rem_frac * 100.0, 1)
            used_raw = row[used_col]
            used_pct = round(max(0.0, min(100.0, float(used_raw))), 1) if used_raw is not None else round(max(0.0, 100.0 - rem_pct), 1)
            window_name = "weekly" if slot == "weekly" else "5h"
            bucket_info = {
                "bucket_id": b_id,
                "display_name": display_name,
                "description": "",
                "window": window_name,
                "remaining_fraction": rem_frac,
                "remaining_pct": rem_pct,
                "used_fraction": round(used_pct / 100.0, 4),
                "used_pct": used_pct,
                "reset_time": str(reset_iso),
            }
            parsed[key] = bucket_info
            track_entry = parsed["tracks"].setdefault(track_id, {"five_hour": None, "weekly": None})
            track_entry[slot] = bucket_info
            has_active_bucket = True

        if has_active_bucket:
            return parsed

    return None


def backfill_step_latency_metrics(
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    conn: Optional[sqlite3.Connection] = None,
    batch_size: int = 5000,
) -> int:
    """
    Fast, idempotent backfill of ttft_ms and latency_ms for step_type = 15 rows
    in steps_archive where ttft_ms IS NULL and raw_metadata_blob IS NOT NULL.
    Batches updates with WAL mode and busy_timeout.
    """
    close_conn = False
    if conn is None:
        conn = get_vault_connection(vault_path)
        close_conn = True

    try:
        cur = conn.cursor()
        if close_conn:
            cur.execute("PRAGMA busy_timeout = 60000;")
            cur.execute("PRAGMA journal_mode = WAL;")

        # Ensure columns exist
        cur.execute("PRAGMA table_info(steps_archive)")
        cols = {r[1] for r in cur.fetchall()}
        if "ttft_ms" not in cols:
            cur.execute("ALTER TABLE steps_archive ADD COLUMN ttft_ms REAL")
        if "latency_ms" not in cols:
            cur.execute("ALTER TABLE steps_archive ADD COLUMN latency_ms REAL")

        cur.execute(
            """
            SELECT convo_id, step_idx, raw_metadata_blob
            FROM steps_archive
            WHERE step_type = 15
              AND ttft_ms IS NULL
              AND raw_metadata_blob IS NOT NULL
            """
        )
        rows = cur.fetchall()
        if not rows:
            return 0

        updates = []
        updated_count = 0
        for convo_id, step_idx, raw_blob in rows:
            lat = extract_wire_latency_ms(raw_blob)
            ttft = lat.get("ttft_ms")
            latency = lat.get("latency_ms")
            ttft_val = ttft if ttft is not None else -1.0
            lat_val = latency if latency is not None else -1.0
            updates.append((ttft_val, lat_val, convo_id, step_idx))
            if len(updates) >= batch_size:
                cur.executemany(
                    "UPDATE steps_archive SET ttft_ms = ?, latency_ms = ? WHERE convo_id = ? AND step_idx = ?",
                    updates,
                )
                conn.commit()
                updated_count += len(updates)
                updates.clear()

        if updates:
            cur.executemany(
                "UPDATE steps_archive SET ttft_ms = ?, latency_ms = ? WHERE convo_id = ? AND step_idx = ?",
                updates,
            )
            conn.commit()
            updated_count += len(updates)
            updates.clear()

        return updated_count
    finally:
        if close_conn:
            try:
                conn.close()
            except sqlite3.Error:
                pass
