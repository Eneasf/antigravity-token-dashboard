"""
Dedicated Local Telemetry Vault, Hybrid Lossless Archival & Lineage Topology.

Adheres to:
- ADR-001: Safe Read-Only SQLite Access (`?mode=ro`, uri=True).
- ADR-002: Pure-Python Wire Protobuf Decoding (zero protoc/compiler dependencies).
- ADR-018: Dedicated Local Telemetry Vault, Hybrid Lossless Archival & Lineage Topology.
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.parse

from src.aggregator import (
    compute_turn_cost,
    get_model_display_name,
    get_model_rates,
    load_pricing,
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
    get_conversation_title,
    get_workspace_mapping,
    parse_wire_fields,
)


DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "antigravity_vault.db"


def init_vault(vault_path: Union[str, Path] = DEFAULT_VAULT_PATH) -> sqlite3.Connection:
    """
    Initialize the Antigravity Telemetry Vault SQLite database and schema.

    Creates tables if not exists:
    - conversations_archive: session metadata, costs, timestamps, lineage.
    - steps_archive: hybrid text + raw protobuf blobs, token telemetry.
    - tool_calls_archive: indexed individual tool invocations and previews.
    - skills_archive: indexed skill references and execution triggers.
    - log_events_archive: deduplicated 429 exhaustion and lifecycle events.
    - vault_sync_state: high-watermark pointers for incremental ingestion.

    Returns open, initialized sqlite3.Connection with PRAGMA busy_timeout set.
    """
    vault_file = Path(vault_path).resolve()
    vault_file.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(vault_file), timeout=5.0)
    conn.execute("PRAGMA busy_timeout = 5000;")
    cur = conn.cursor()

    # 1. conversations_archive
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations_archive (
            convo_id TEXT PRIMARY KEY,
            parent_convo_id TEXT,
            workspace_name TEXT,
            workspace_path TEXT,
            title TEXT,
            trajectory_id TEXT,
            cascade_id TEXT,
            turn_count INTEGER DEFAULT 0,
            total_input_tokens INTEGER DEFAULT 0,
            total_output_tokens INTEGER DEFAULT 0,
            cached_tokens INTEGER DEFAULT 0,
            thinking_tokens INTEGER DEFAULT 0,
            estimated_cost_usd REAL DEFAULT 0.0,
            first_turn_ts TEXT,
            last_turn_ts TEXT,
            raw_metadata_blob BLOB,
            synced_at TEXT
        );
        """
    )

    # 2. steps_archive (Hybrid: searchable TEXT + lossless raw BLOBs, zero pickle)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS steps_archive (
            convo_id TEXT,
            step_idx INTEGER,
            step_type INTEGER,
            status INTEGER,
            timestamp TEXT,
            model_id TEXT,
            model_name TEXT,
            prompt_tokens_uncached INTEGER DEFAULT 0,
            cached_tokens INTEGER DEFAULT 0,
            total_input_tokens INTEGER DEFAULT 0,
            output_tokens_total INTEGER DEFAULT 0,
            thinking_tokens INTEGER DEFAULT 0,
            answer_tokens INTEGER DEFAULT 0,
            cache_hit_ratio_pct REAL DEFAULT 0.0,
            payload_text TEXT,
            tool_calls_json TEXT,
            error_text TEXT,
            raw_metadata_blob BLOB,
            raw_step_payload_blob BLOB,
            raw_error_details_blob BLOB,
            response_id TEXT,
            agent_id TEXT,
            session_id TEXT,
            PRIMARY KEY (convo_id, step_idx)
        );
        """
    )

    # 3. tool_calls_archive
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tool_calls_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            convo_id TEXT,
            step_idx INTEGER,
            call_id TEXT,
            tool_name TEXT,
            tool_action TEXT,
            tool_summary TEXT,
            arguments_json TEXT,
            result_summary TEXT,
            timestamp TEXT
        );
        """
    )

    # 4. skills_archive
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS skills_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            convo_id TEXT,
            step_idx INTEGER,
            skill_name TEXT,
            skill_path TEXT,
            activation_type TEXT,
            timestamp TEXT
        );
        """
    )

    # 5. log_events_archive (Deduplicated 429 exhaustion and lifecycle events)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS log_events_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_fingerprint TEXT UNIQUE,
            timestamp TEXT,
            timestamp_iso TEXT,
            level TEXT,
            event_type TEXT,
            raw_line TEXT,
            code INTEGER,
            reason TEXT,
            file_offset INTEGER
        );
        """
    )

    # 6. vault_sync_state
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vault_sync_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        );
        """
    )

    # 7. weekly_cycles_archive (Historical weekly cycles trends, tokens, costs, overage, BVI)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS weekly_cycles_archive (
            cycle_key TEXT PRIMARY KEY,
            cycle_start_utc TEXT NOT NULL,
            cycle_end_utc TEXT NOT NULL,
            label TEXT NOT NULL,
            total_turns INTEGER DEFAULT 0,
            total_input_tokens INTEGER DEFAULT 0,
            cached_tokens INTEGER DEFAULT 0,
            prompt_tokens_uncached INTEGER DEFAULT 0,
            total_output_tokens INTEGER DEFAULT 0,
            total_processed_tokens INTEGER DEFAULT 0,
            cache_hit_ratio_pct REAL DEFAULT 0.0,
            estimated_cost_usd REAL DEFAULT 0.0,
            estimated_cost_gbp REAL DEFAULT 0.0,
            actual_overage_credits INTEGER DEFAULT 0,
            actual_overage_usd REAL DEFAULT 0.0,
            actual_overage_gbp REAL DEFAULT 0.0,
            peak_bvi REAL DEFAULT 0.0,
            is_current_cycle INTEGER DEFAULT 0,
            updated_at TEXT
        );
        """
    )

    # 8. subscription_history_archive (Historical plan tiers, pricing, and quota boundaries)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS subscription_history_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tier TEXT NOT NULL,
            name TEXT NOT NULL,
            monthly_price_gbp REAL,
            monthly_price_usd REAL,
            renewal_day INTEGER,
            valid_from TEXT NOT NULL UNIQUE,
            valid_to TEXT,
            gemini_5h_capacity_usd REAL,
            gemini_weekly_capacity_usd REAL,
            claude_5h_capacity_usd REAL,
            claude_weekly_capacity_usd REAL,
            burst_5h_tokens INTEGER,
            created_at TEXT
        );
        """
    )

    # Performance Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_conversations_parent ON conversations_archive(parent_convo_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_conversations_workspace ON conversations_archive(workspace_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_steps_convo_id ON steps_archive(convo_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_steps_step_type ON steps_archive(step_type);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_steps_model_id ON steps_archive(model_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tool_calls_convo_step ON tool_calls_archive(convo_id, step_idx);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tool_calls_name ON tool_calls_archive(tool_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_skills_convo_step ON skills_archive(convo_id, step_idx);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_skills_name ON skills_archive(skill_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_log_events_iso ON log_events_archive(timestamp_iso);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_weekly_cycles_start ON weekly_cycles_archive(cycle_start_utc);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sub_history_from ON subscription_history_archive(valid_from);")

    conn.commit()
    return conn


def get_vault_connection(vault_path: Union[str, Path] = DEFAULT_VAULT_PATH) -> sqlite3.Connection:
    """
    Open connection to vault SQLite database with 5.0s timeout and busy_timeout PRAGMA.
    Initializes database and tables if not already present.
    """
    vault_file = Path(vault_path).resolve()
    return init_vault(vault_file)


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
                    except Exception:
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
    except Exception:
        pass

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
    except Exception:
        pass

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
        except Exception:
            return []
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    return []


def sync_conversations_to_vault(
    antigravity_dir: Union[str, Path] = DEFAULT_ANTIGRAVITY_DIR,
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    max_conversations: Optional[int] = None,
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
        'scanned_databases': int
    }
    """
    agy_path = Path(antigravity_dir).resolve()
    vault_conn = get_vault_connection(vault_path)
    cur = vault_conn.cursor()

    # Load high-watermarks
    cur.execute("SELECT convo_id, MAX(step_idx) FROM steps_archive GROUP BY convo_id")
    high_watermarks: Dict[str, int] = {row[0]: row[1] for row in cur.fetchall()}

    # Discover upstream DBs
    conv_dir = agy_path / "conversations"
    db_paths: List[Path] = []
    discovered_count = 0
    if conv_dir.exists():
        try:
            db_paths = list(conv_dir.glob("*.db"))
            db_paths.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
            discovered_count = len(db_paths)
            if max_conversations is not None:
                db_paths = db_paths[:max_conversations]
        except (PermissionError, OSError):
            db_paths = []
            discovered_count = 0

    # Parse workspace summaries
    pb_file = agy_path / "agyhub_summaries_proto.pb"
    summaries = parse_agyhub_summaries(pb_file)
    fallback_ws_map = get_workspace_mapping(agy_path)
    pricing_models = load_pricing()

    steps_synced_count = 0
    tool_calls_synced_count = 0
    conversations_synced_set = set()
    parent_child_links: Dict[str, str] = {}  # child_convo_id -> parent_convo_id

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
                except Exception:
                    pass
            tc_json = str(payload_details.get("tool_calls_json") or "[]")
            resp_id = str(telemetry.get("response_id") or "")
            agent_id = str(telemetry.get("agent_id") or "")
            sess_id = str(telemetry.get("session_id") or "")

            cur.execute(
                """
                INSERT OR REPLACE INTO steps_archive (
                    convo_id, step_idx, step_type, status, timestamp,
                    model_id, model_name, prompt_tokens_uncached, cached_tokens,
                    total_input_tokens, output_tokens_total, thinking_tokens,
                    answer_tokens, cache_hit_ratio_pct, payload_text,
                    tool_calls_json, error_text, raw_metadata_blob,
                    raw_step_payload_blob, raw_error_details_blob,
                    response_id, agent_id, session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            steps_synced_count += 1

            # Populate tool_calls_archive
            tool_calls = payload_details.get("tool_calls", [])
            for tc in tool_calls:
                cur.execute(
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
            skills = payload_details.get("skills_referenced", [])
            for sk in skills:
                cur.execute(
                    """
                    INSERT INTO skills_archive (
                        convo_id, step_idx, skill_name, skill_path,
                        activation_type, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        convo_id,
                        idx,
                        sk,
                        f"skills/{sk}/SKILL.md",
                        "referenced",
                        ts_str,
                    ),
                )

            # Subagent Lineage Discovery from step payload details
            for spawned_id in payload_details.get("subagents_spawned", []):
                if spawned_id and spawned_id != convo_id:
                    parent_child_links[spawned_id] = convo_id

            for recip_id in payload_details.get("subagent_recipients", []):
                if recip_id and recip_id != convo_id:
                    parent_child_links[recip_id] = convo_id

            sender_id = payload_details.get("sender_id")
            if sender_id and sender_id != convo_id:
                parent_child_links[convo_id] = sender_id

    # Precise lineage resolution across tool_calls_archive and steps_archive
    # 1. From invoke_subagent tool calls in tool_calls_archive
    subagent_id_pattern = re.compile(
        r'(?:"conversationId"|subagent_id)["\':\s=]*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
        re.IGNORECASE,
    )
    cur.execute(
        """
        SELECT convo_id, result_summary, arguments_json
        FROM tool_calls_archive
        WHERE tool_name = 'invoke_subagent'
        """
    )
    for caller_id, res_sum, args_json in cur.fetchall():
        combined = (res_sum or "") + " " + (args_json or "")
        for m in subagent_id_pattern.finditer(combined):
            child_id = m.group(1)
            if child_id != caller_id:
                parent_child_links[child_id] = caller_id

    # 2. From send_message tool calls in tool_calls_archive
    cur.execute(
        """
        SELECT convo_id, arguments_json
        FROM tool_calls_archive
        WHERE tool_name = 'send_message'
        """
    )
    for caller_id, args_json in cur.fetchall():
        for m in re.finditer(r'"Recipient":\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', args_json or ""):
            child_id = m.group(1)
            if child_id != caller_id:
                parent_child_links[child_id] = caller_id

    # 3. From mock test or fallback invoke_subagent steps
    cur.execute(
        """
        SELECT convo_id, payload_text
        FROM steps_archive
        WHERE payload_text LIKE '%invoke_subagent%subagent_id=%'
        """
    )
    for parent_id, p_text in cur.fetchall():
        m = re.search(r'invoke_subagent[^\n\r]*subagent_id="([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', p_text or "")
        if m:
            child_id = m.group(1)
            if child_id != parent_id:
                parent_child_links[child_id] = parent_id

    # 4. From incoming agent messages in steps_archive (where child receives message from parent)
    cur.execute(
        """
        SELECT convo_id, payload_text
        FROM steps_archive
        WHERE payload_text LIKE '%sender=%'
        """
    )
    for child_id, p_text in cur.fetchall():
        sm = re.search(r"\[Message\][^\n\r]*sender=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", p_text or "")
        if sm:
            sender_id = sm.group(1)
            # Only attribute if child_id is not already an orchestrator that spawned children
            if sender_id != child_id and child_id not in parent_child_links.values():
                parent_child_links[child_id] = sender_id

    # Update conversations_archive records
    cur.execute("SELECT DISTINCT convo_id FROM steps_archive")
    all_convo_ids = [r[0] for r in cur.fetchall()]

    for cid in all_convo_ids:
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

        cur.execute(
            """
            INSERT INTO conversations_archive (
                convo_id, parent_convo_id, workspace_name, workspace_path,
                title, trajectory_id, turn_count,
                total_input_tokens, total_output_tokens, cached_tokens,
                thinking_tokens, estimated_cost_usd, first_turn_ts,
                last_turn_ts, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(convo_id) DO UPDATE SET
                parent_convo_id = COALESCE(excluded.parent_convo_id, conversations_archive.parent_convo_id),
                workspace_name = COALESCE(excluded.workspace_name, conversations_archive.workspace_name),
                workspace_path = COALESCE(excluded.workspace_path, conversations_archive.workspace_path),
                title = COALESCE(excluded.title, conversations_archive.title),
                trajectory_id = COALESCE(excluded.trajectory_id, conversations_archive.trajectory_id),
                turn_count = excluded.turn_count,
                total_input_tokens = excluded.total_input_tokens,
                total_output_tokens = excluded.total_output_tokens,
                cached_tokens = excluded.cached_tokens,
                thinking_tokens = excluded.thinking_tokens,
                estimated_cost_usd = excluded.estimated_cost_usd,
                first_turn_ts = excluded.first_turn_ts,
                last_turn_ts = excluded.last_turn_ts,
                synced_at = excluded.synced_at
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
                now_iso,
            ),
        )

    # Propagate all discovered parent_child_links
    cur.execute("UPDATE conversations_archive SET parent_convo_id = NULL")
    for child_id, parent_id in parent_child_links.items():
        cur.execute(
            """
            UPDATE conversations_archive
            SET parent_convo_id = ?
            WHERE convo_id = ?
            """,
            (parent_id, child_id),
        )

    vault_conn.commit()
    vault_conn.close()

    return {
        "conversations_synced": len(conversations_synced_set),
        "steps_synced": steps_synced_count,
        "tool_calls_synced": tool_calls_synced_count,
        "discovered_databases": discovered_count,
        "scanned_databases": len(db_paths),
    }


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

                ts = parse_glog_timestamp(line, year=year)
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
    except Exception:
        pass
    finally:
        try:
            vault_conn.close()
        except Exception:
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
    from src.weekly_trends import sync_weekly_trends_to_vault as _sync
    return _sync(
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
    from src.weekly_trends import get_weekly_trends as _get
    return _get(
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

    conn = get_vault_connection(vault_path)
    cur = conn.cursor()

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


