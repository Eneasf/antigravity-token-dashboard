"""
Dedicated Local Telemetry Vault Schema & Initialization.

Defines the canonical SQLite schema for the Antigravity Telemetry Vault,
table definitions, migrations, and index structures. Extracted to eliminate
circular import dependencies between `src/vault.py` and `src/weekly_trends.py`.

Adheres to:
- ADR-001: Safe Read-Only SQLite Access (?mode=ro, uri=True).
- ADR-018: Dedicated Local Telemetry Vault DB.
- ADR-039: Historical Vault Trends & Weekly Cycles Archive.
- ADR-078: Agent Persona Telemetry & Lineage Attribution.
- ADR-081: SQLite Concurrency Resilience (WAL mode, busy_timeout).
"""

from pathlib import Path
import sqlite3
from typing import Union

DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "antigravity_vault.db"


def init_vault(vault_path: Union[str, Path] = DEFAULT_VAULT_PATH, busy_timeout: int = 60000) -> sqlite3.Connection:
    """
    Initialize the Antigravity Telemetry Vault SQLite database and schema.

    Creates tables if not exists:
    - conversations_archive: session metadata, costs, timestamps, lineage.
    - steps_archive: hybrid text + raw protobuf blobs, token telemetry.
    - tool_calls_archive: indexed individual tool invocations and previews.
    - skills_archive: indexed skill references and execution triggers.
    - log_events_archive: deduplicated 429 exhaustion and lifecycle events.
    - vault_sync_state: high-watermark pointers for incremental ingestion.
    - weekly_cycles_archive: historical weekly cycle aggregates and overage costs.
    - subscription_history_archive: plan tiers, pricing, and quota boundaries.

    Returns open, initialized sqlite3.Connection with PRAGMA busy_timeout set.
    """
    if str(vault_path) == ":memory:":
        conn = sqlite3.connect(":memory:", timeout=60.0)
    else:
        vault_file = Path(vault_path).resolve()
        vault_file.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(vault_file), timeout=60.0)
    conn.execute(f"PRAGMA busy_timeout = {busy_timeout};")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    cur = conn.cursor()

    try:
        cur.execute("SELECT value FROM vault_sync_state WHERE key = 'schema_version'")
        sv = cur.fetchone()
        if sv and sv[0] == "m94_v2":
            cur.execute("PRAGMA table_info(steps_archive)")
            scols = {r[1] for r in cur.fetchall()}
            cur.execute("PRAGMA table_info(conversations_archive)")
            ccols = {r[1] for r in cur.fetchall()}
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quota_regime_events_archive'")
            has_regime_table = cur.fetchone() is not None
            if (
                "ttft_ms" in scols
                and "latency_ms" in scols
                and "rate_limit_flag" in scols
                and "turn1_input_tokens" in ccols
                and "turn1_cached_tokens" in ccols
                and has_regime_table
            ):
                cur.execute(
                    """
                    SELECT 1 FROM skills_archive
                    WHERE skill_name IS NULL
                       OR skill_name NOT GLOB '[a-zA-Z0-9]*'
                       OR skill_name GLOB '*[^a-zA-Z0-9_-]*'
                       OR skill_name LIKE '%' || char(10) || '%'
                       OR length(skill_name) < 2
                       OR length(skill_name) > 64
                    LIMIT 1;
                    """
                )
                if cur.fetchone() is not None:
                    cur.execute(
                        """
                        DELETE FROM skills_archive
                        WHERE skill_name IS NULL
                           OR skill_name NOT GLOB '[a-zA-Z0-9]*'
                           OR skill_name GLOB '*[^a-zA-Z0-9_-]*'
                           OR skill_name LIKE '%' || char(10) || '%'
                           OR length(skill_name) < 2
                           OR length(skill_name) > 64;
                        """
                    )
                    conn.commit()
                return conn
    except sqlite3.Error:
        pass

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
            synced_at TEXT,
            agent_name TEXT DEFAULT 'default',
            agent_description TEXT,
            is_subagent INTEGER DEFAULT 0,
            subagent_role TEXT,
            turn1_input_tokens INTEGER DEFAULT 0,
            turn1_cached_tokens INTEGER DEFAULT 0
        );
        """
    )

    # Ensure columns exist for upgraded vaults (Milestone 64 / ADR-078 & Milestone 98)
    cur.execute("PRAGMA table_info(conversations_archive)")
    existing_cols = {r[1] for r in cur.fetchall()}
    if "agent_name" not in existing_cols:
        cur.execute("ALTER TABLE conversations_archive ADD COLUMN agent_name TEXT DEFAULT 'default'")
    if "agent_description" not in existing_cols:
        cur.execute("ALTER TABLE conversations_archive ADD COLUMN agent_description TEXT")
    if "is_subagent" not in existing_cols:
        cur.execute("ALTER TABLE conversations_archive ADD COLUMN is_subagent INTEGER DEFAULT 0")
    if "subagent_role" not in existing_cols:
        cur.execute("ALTER TABLE conversations_archive ADD COLUMN subagent_role TEXT")
    if "turn1_input_tokens" not in existing_cols:
        cur.execute("ALTER TABLE conversations_archive ADD COLUMN turn1_input_tokens INTEGER DEFAULT 0")
    if "turn1_cached_tokens" not in existing_cols:
        cur.execute("ALTER TABLE conversations_archive ADD COLUMN turn1_cached_tokens INTEGER DEFAULT 0")

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
            rate_limit_flag INTEGER DEFAULT 0,
            error_code TEXT,
            ttft_ms REAL,
            latency_ms REAL,
            PRIMARY KEY (convo_id, step_idx)
        );
        """
    )

    # Ensure columns exist for upgraded vaults (Milestone 90 / ADR-088 & Milestone 94)
    cur.execute("PRAGMA table_info(steps_archive)")
    existing_step_cols = {r[1] for r in cur.fetchall()}
    if "rate_limit_flag" not in existing_step_cols:
        cur.execute("ALTER TABLE steps_archive ADD COLUMN rate_limit_flag INTEGER DEFAULT 0")
    if "error_code" not in existing_step_cols:
        cur.execute("ALTER TABLE steps_archive ADD COLUMN error_code TEXT")
    if "ttft_ms" not in existing_step_cols:
        cur.execute("ALTER TABLE steps_archive ADD COLUMN ttft_ms REAL")
    if "latency_ms" not in existing_step_cols:
        cur.execute("ALTER TABLE steps_archive ADD COLUMN latency_ms REAL")

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

    # Compound & Partial Indexes (Milestone 90 / ADR-087 / ADR-088)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_steps_convo_id_ts ON steps_archive(convo_id, timestamp);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_steps_step_type_ts ON steps_archive(step_type, timestamp, model_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_steps_error_text ON steps_archive(timestamp) WHERE error_text IS NOT NULL AND error_text != '';")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_steps_rate_limit ON steps_archive(timestamp) WHERE rate_limit_flag = 1;")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_log_events_code_type_ts ON log_events_archive(code, event_type, timestamp_iso);")

    # 9. Reference Dictionaries (Milestone 90 / ADR-089)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ref_step_types (
            step_type INTEGER PRIMARY KEY,
            code_name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL
        );
        """
    )
    ref_step_data = [
        (5, "REPLACE_FILE_CONTENT", "TOOL", "Direct file replacement tool execution"),
        (7, "GREP_SEARCH", "TOOL", "Direct grep search tool execution"),
        (8, "VIEW_FILE", "TOOL", "Direct file inspection tool execution"),
        (9, "LIST_DIR", "TOOL", "Direct directory listing tool execution"),
        (14, "USER_INPUT", "USER", "User prompt, uploaded attachments, or instructions"),
        (15, "PLANNER_RESPONSE", "MODEL", "Model reasoning, thinking tokens, and candidate output"),
        (17, "WRITE_TO_FILE", "TOOL", "Direct file creation/write tool execution"),
        (21, "RUN_COMMAND", "TOOL", "Direct shell command execution"),
        (23, "CHECKPOINT", "SYSTEM", "Context window compaction / summary checkpoint"),
        (33, "SEARCH_WEB", "TOOL", "Direct web search execution"),
        (38, "CALL_MCP_TOOL", "TOOL", "External MCP tool execution"),
        (90, "AGENT_STATE", "SYSTEM", "Agent internal state snapshot"),
        (101, "BACKGROUND_MESSAGE", "SUBAGENT", "Inter-agent message or task completion notification"),
        (127, "INVOKE_SUBAGENT", "SUBAGENT", "Subagent delegation invocation"),
        (132, "TOOL_EXECUTION", "TOOL", "Execution of agent tools and shell commands"),
        (138, "ASK_QUESTION", "USER", "Interactive user prompt modal dialog"),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO ref_step_types (step_type, code_name, category, description) VALUES (?, ?, ?, ?)",
        ref_step_data,
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ref_status_codes (
            code INTEGER PRIMARY KEY,
            standard_name TEXT NOT NULL,
            domain TEXT NOT NULL,
            description TEXT NOT NULL,
            is_error INTEGER DEFAULT 0,
            is_rate_limit INTEGER DEFAULT 0
        );
        """
    )
    ref_status_data = [
        (1, "INITIALIZING", "STEP_STATUS", "Step initiated, awaiting runtime start", 0, 0),
        (2, "RUNNING", "STEP_STATUS", "Step actively running", 0, 0),
        (3, "COMPLETED", "STEP_STATUS", "Step completed successfully", 0, 0),
        (4, "INVALID_INPUT", "STEP_STATUS", "Step failed due to schema or argument validation", 1, 0),
        (5, "AWAITING_INPUT", "STEP_STATUS", "Step paused waiting for user input or subagent", 0, 0),
        (6, "CANCELLED", "STEP_STATUS", "Step cancelled by user or timeout", 1, 0),
        (7, "EXECUTION_ERROR", "STEP_STATUS", "Tool, model, or command failure", 1, 0),
        (8, "SKIPPED", "STEP_STATUS", "Step skipped by execution plan", 0, 0),
        (9, "TERMINATED", "STEP_STATUS", "Step terminated prematurely", 1, 0),
        (200, "OK", "HTTP", "Successful API response", 0, 0),
        (400, "BAD_REQUEST", "HTTP", "Invalid API request or arguments", 1, 0),
        (401, "UNAUTHENTICATED", "HTTP", "Missing or invalid credentials", 1, 0),
        (403, "PERMISSION_DENIED", "HTTP", "Access forbidden or quota exhausted", 1, 0),
        (429, "RESOURCE_EXHAUSTED", "HTTP", "Rate limit or burst quota capacity depleted", 1, 1),
        (500, "INTERNAL_ERROR", "HTTP", "Internal server error", 1, 0),
        (503, "SERVICE_UNAVAILABLE", "HTTP", "Provider model temporarily overloaded", 1, 0),
        (504, "DEADLINE_EXCEEDED", "HTTP", "Gateway or RPC timeout", 1, 0),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO ref_status_codes (code, standard_name, domain, description, is_error, is_rate_limit) VALUES (?, ?, ?, ?, ?, ?)",
        ref_status_data,
    )

    # 10. Canonical Analytical Views (Milestone 90 / ADR-090, updated with ergonomic aliases)
    cur.execute("DROP VIEW IF EXISTS v_hourly_token_velocity;")
    cur.execute("DROP VIEW IF EXISTS v_turns;")
    cur.execute(
        """
        CREATE VIEW v_turns AS
        SELECT
            convo_id,
            step_idx,
            step_idx AS turn_idx,
            timestamp,
            model_id,
            model_name,
            model_name AS model,
            status,
            prompt_tokens_uncached,
            cached_tokens,
            total_input_tokens,
            output_tokens_total,
            output_tokens_total AS total_output_tokens,
            thinking_tokens,
            (prompt_tokens_uncached + cached_tokens + output_tokens_total) AS total_tokens,
            rate_limit_flag,
            error_code,
            error_text,
            ttft_ms,
            latency_ms
        FROM steps_archive
        WHERE step_type = 15;
        """
    )

    cur.execute(
        """
        CREATE VIEW v_hourly_token_velocity AS
        SELECT
            strftime('%Y-%m-%d %H:00:00', timestamp) AS hour_utc,
            model_name,
            model_name AS model,
            COUNT(*) AS turn_count,
            COUNT(*) AS total_turns,
            SUM(total_input_tokens) AS total_input,
            SUM(cached_tokens) AS total_cached,
            SUM(output_tokens_total) AS total_output
        FROM v_turns
        GROUP BY 1, 2;
        """
    )

    cur.execute("DROP VIEW IF EXISTS v_active_sessions;")
    cur.execute(
        """
        CREATE VIEW v_active_sessions AS
        SELECT
            convo_id,
            title,
            first_turn_ts AS session_start,
            last_turn_ts AS session_end,
            ROUND((julianday(last_turn_ts) - julianday(first_turn_ts)) * 86400.0, 1) AS duration_seconds,
            turn_count,
            turn_count AS total_turns,
            total_input_tokens,
            total_output_tokens,
            cached_tokens,
            thinking_tokens,
            estimated_cost_usd,
            is_subagent,
            agent_name,
            subagent_role,
            COALESCE(turn1_input_tokens, 0) AS turn1_input_tokens,
            COALESCE(turn1_cached_tokens, 0) AS turn1_cached_tokens
        FROM conversations_archive
        WHERE first_turn_ts IS NOT NULL;
        """
    )

    cur.execute("DROP VIEW IF EXISTS v_rate_limit_events;")
    cur.execute(
        """
        CREATE VIEW v_rate_limit_events AS
        SELECT
            l.timestamp_iso AS event_time,
            l.code,
            l.reason,
            c.convo_id,
            c.title,
            c.agent_name,
            c.subagent_role
        FROM log_events_archive l
        LEFT JOIN conversations_archive c
            ON l.timestamp_iso BETWEEN c.first_turn_ts AND c.last_turn_ts
        WHERE l.code = 429;
        """
    )

    # 10b. Live Quota Snapshots Archive & Burn Intervals View (Milestone 93)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS quota_snapshots_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_fingerprint TEXT UNIQUE,
            timestamp_utc TEXT NOT NULL,
            gemini_5h_remaining REAL,
            gemini_5h_used_pct REAL,
            gemini_5h_reset_utc TEXT,
            gemini_weekly_remaining REAL,
            gemini_weekly_used_pct REAL,
            gemini_weekly_reset_utc TEXT,
            claude_5h_remaining REAL,
            claude_5h_used_pct REAL,
            claude_5h_reset_utc TEXT,
            claude_weekly_remaining REAL,
            claude_weekly_used_pct REAL,
            claude_weekly_reset_utc TEXT,
            active_status TEXT DEFAULT 'SAFE_IN_QUOTA'
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_quota_snapshots_ts ON quota_snapshots_archive(timestamp_utc);")

    # 10c. Quota Regime & Burn-Rate Drift Events Archive (Milestone 97)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS quota_regime_events_archive (
            event_id TEXT PRIMARY KEY,
            detected_at_utc TEXT NOT NULL,
            event_type TEXT NOT NULL,
            review_status TEXT DEFAULT 'PENDING_REVIEW',
            confirmed_at_utc TEXT,
            snapshot_range TEXT,
            turns_analyzed INTEGER DEFAULT 0,
            delta_5h_pct REAL DEFAULT 0.0,
            delta_weekly_pct REAL DEFAULT 0.0,
            drift_ratio REAL DEFAULT 1.0,
            coupling_ratio REAL DEFAULT 4.0,
            solved_5h_api_usd REAL DEFAULT 25.0,
            solved_weekly_api_usd REAL DEFAULT 100.0,
            summary TEXT,
            prev_baseline_json TEXT,
            observed_metrics_json TEXT,
            model_breakdown_json TEXT
        );
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_quota_regime_events_ts ON quota_regime_events_archive(detected_at_utc);")

    cur.execute("DROP VIEW IF EXISTS v_quota_burn_intervals;")
    cur.execute(
        """
        CREATE VIEW v_quota_burn_intervals AS
        WITH ordered_snapshots AS (
            SELECT
                id,
                timestamp_utc AS end_utc,
                LAG(timestamp_utc) OVER (ORDER BY timestamp_utc ASC, id ASC) AS start_utc,
                gemini_5h_remaining AS end_5h_rem,
                LAG(gemini_5h_remaining) OVER (ORDER BY timestamp_utc ASC, id ASC) AS start_5h_rem,
                gemini_5h_reset_utc,
                LAG(gemini_5h_reset_utc) OVER (ORDER BY timestamp_utc ASC, id ASC) AS prev_5h_reset_utc,
                gemini_weekly_remaining AS end_weekly_rem,
                LAG(gemini_weekly_remaining) OVER (ORDER BY timestamp_utc ASC, id ASC) AS start_weekly_rem,
                gemini_weekly_reset_utc,
                LAG(gemini_weekly_reset_utc) OVER (ORDER BY timestamp_utc ASC, id ASC) AS prev_weekly_reset_utc,
                active_status
            FROM quota_snapshots_archive
        )
        SELECT
            start_utc,
            end_utc,
            ROUND((start_5h_rem - end_5h_rem) * 100.0, 5) AS delta_5h_pct,
            ROUND((start_weekly_rem - end_weekly_rem) * 100.0, 5) AS delta_weekly_pct,
            CASE
                WHEN (start_weekly_rem - end_weekly_rem) > 0.000001
                THEN ROUND((start_5h_rem - end_5h_rem) / (start_weekly_rem - end_weekly_rem), 4)
                ELSE NULL
            END AS ratio_5h_to_weekly,
            ROUND(start_5h_rem * 100.0, 4) AS start_5h_rem_pct,
            ROUND(end_5h_rem * 100.0, 4) AS end_5h_rem_pct,
            ROUND(start_weekly_rem * 100.0, 4) AS start_weekly_rem_pct,
            ROUND(end_weekly_rem * 100.0, 4) AS end_weekly_rem_pct,
            gemini_5h_reset_utc,
            gemini_weekly_reset_utc,
            active_status
        FROM ordered_snapshots
        WHERE start_utc IS NOT NULL
          AND (
              (start_5h_rem > end_5h_rem AND COALESCE(gemini_5h_reset_utc, '') = COALESCE(prev_5h_reset_utc, ''))
              OR (start_weekly_rem > end_weekly_rem AND COALESCE(gemini_weekly_reset_utc, '') = COALESCE(prev_weekly_reset_utc, ''))
          );
        """
    )

    # 11. Idempotent backfill of rate_limit_flag for existing error rows
    cur.execute(
        """
        UPDATE steps_archive
        SET rate_limit_flag = 1, error_code = 'RESOURCE_EXHAUSTED'
        WHERE rate_limit_flag = 0
          AND (
              error_text LIKE '%RESOURCE_EXHAUSTED%'
              OR error_text LIKE '%429%'
              OR payload_text LIKE '%RESOURCE_EXHAUSTED%'
          );
        """
    )

    # 11b. Idempotent self-heal of log_events_archive.timestamp and Turn-1 ambient prompt weight
    try:
        cur.execute(
            """
            UPDATE log_events_archive
            SET timestamp = timestamp_iso
            WHERE (timestamp IS NULL OR timestamp = '')
              AND timestamp_iso IS NOT NULL
              AND timestamp_iso != '';
            """
        )
        cur.execute(
            """
            UPDATE conversations_archive
            SET
                turn1_input_tokens = COALESCE((
                    SELECT s.total_input_tokens
                    FROM steps_archive s
                    WHERE s.convo_id = conversations_archive.convo_id
                      AND s.step_type = 15
                      AND s.total_input_tokens > 0
                    ORDER BY s.step_idx ASC
                    LIMIT 1
                ), 0),
                turn1_cached_tokens = COALESCE((
                    SELECT s.cached_tokens
                    FROM steps_archive s
                    WHERE s.convo_id = conversations_archive.convo_id
                      AND s.step_type = 15
                      AND s.total_input_tokens > 0
                    ORDER BY s.step_idx ASC
                    LIMIT 1
                ), 0)
            WHERE COALESCE(turn1_input_tokens, 0) = 0 AND turn_count > 0;
            """
        )
    except sqlite3.OperationalError:
        pass

    # Idempotent sanitization: Purge corrupt rows in skills_archive failing slug regex (Milestone B)
    cur.execute(
        """
        DELETE FROM skills_archive
        WHERE skill_name IS NULL
           OR skill_name NOT GLOB '[a-zA-Z0-9]*'
           OR skill_name GLOB '*[^a-zA-Z0-9_-]*'
           OR skill_name LIKE '%' || char(10) || '%'
           OR length(skill_name) < 2
           OR length(skill_name) > 64;
        """
    )

    # 12. Idempotent one-time backfill of wire latency metrics gated via vault_sync_state PK (Milestone 94)
    try:
        cur.execute("SELECT value FROM vault_sync_state WHERE key = 'm94_ttft_backfill_done'")
        row = cur.fetchone()
        if not row or row[0] != "1":
            from src.vault import backfill_step_latency_metrics
            backfill_step_latency_metrics(conn=conn)
            cur.execute(
                "INSERT OR REPLACE INTO vault_sync_state (key, value, updated_at) VALUES ('m94_ttft_backfill_done', '1', datetime('now'))"
            )
    except Exception:
        pass

    cur.execute(
        "INSERT OR REPLACE INTO vault_sync_state (key, value, updated_at) VALUES ('schema_version', 'm94_v2', datetime('now'))"
    )
    conn.commit()
    return conn


def get_vault_connection(
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    busy_timeout: int = 5000,
) -> sqlite3.Connection:
    """
    Open connection to vault SQLite database with 5.0s timeout and busy_timeout PRAGMA.
    Initializes database and tables if not already present.
    """
    vault_file = Path(vault_path).resolve()
    return init_vault(vault_file, busy_timeout=busy_timeout)


__all__ = [
    "DEFAULT_VAULT_PATH",
    "init_vault",
    "get_vault_connection",
]
