# Antigravity Telemetry Vault: Data Dictionary & Semantic Layer

**Database File**: `data/antigravity_vault.db`
**Storage Engine**: SQLite 3 (WAL Mode, `PRAGMA busy_timeout = 60000;`)
**Access Rule**: Strict URI Read-Only Mode (`file:data/antigravity_vault.db?mode=ro`, ADR-001)
**Schema Definition**: `src/vault_schema.py` (ADR-018, ADR-087 – ADR-091)
**CLI Inspector**: `scripts/quota_history.py` (Deterministic quota audit)

---

## 1. Overview & Semantic Architecture

The **Antigravity Telemetry Vault** is the permanent local archive of all agentic coding sessions, model generation turns, tool calls, skill triggers, and quota/billing events across Google Antigravity workspaces.

To prevent expensive full-table disk scans, eliminate undocumented magic numbers, and resolve field naming asymmetries, the database exposes a **two-tier architecture**:
1. **Physical Storage Layer (`*_archive`)**: 10 tables preserving strict **Upstream Fidelity** with Google's Antigravity runtime SQLite database and Protobuf wire definitions (`steps`, `trajectory_meta`, `step_type`, `status`, `idx` $\rightarrow$ `step_idx`).
2. **Semantic Presentation Layer (`v_*`)**: 4 canonical SQL views and 2 reference dictionaries providing human-readable, pre-aggregated analytics and **Symmetric Aliases** (`turn_count AS total_turns`, `model_name AS model`, `step_idx AS turn_idx`) without altering physical storage or breaking live pipelines.

> [!WARNING]
> **Binary Asset Protection (Never Grep Large Databases)**:
> `data/antigravity_vault.db` is ~3.88 GB. Never execute recursive text search tools (`grep -rn`) across the project root or `data/` without passing `--exclude="*.db*"`. Use targeted search paths (`docs/`, `src/`, `scripts/`) or query SQLite directly via URI read-only mode to prevent system I/O hangs.

---

## 2. Canonical Semantic Views Catalog

Whenever querying the vault, **always prefer these views over raw tables**:

### 2.1 `v_turns` (Model Generation Turns)
Pre-filters `step_type = 15` (`PLANNER_RESPONSE`). Excludes system checkpoints, tool calls, and user prompts.

| Column Name | Type | Provenance | Description / Aliasing |
| :--- | :---: | :--- | :--- |
| `convo_id` | TEXT | `[Google Upstream Wire]` | Session UUID matching conversation archive. |
| `step_idx` | INTEGER | `[Google Upstream Wire]` | Step sequence index in trajectory (Google's `idx`). |
| `turn_idx` | INTEGER | `[Semantic View Alias]` | Ergonomic alias for `step_idx`. |
| `timestamp` | TEXT | `[Google Upstream Wire]` | ISO-8601 UTC timestamp of model response. |
| `model_id` | TEXT | `[Telemetry Pipeline]` | Internal model ID. |
| `model_name` | TEXT | `[Telemetry Pipeline]` | Calibrated model display name (e.g. `Gemini 3.8 Flash (High)`). |
| `model` | TEXT | `[Semantic View Alias]` | Ergonomic alias for `model_name`. |
| `status` | INTEGER | `[Google Upstream Wire]` | Step execution status code (e.g. 3=COMPLETED, 7=ERROR). |
| `prompt_tokens_uncached`| INTEGER | `[Google Protobuf Wire]` | Raw uncached input prompt tokens. |
| `cached_tokens` | INTEGER | `[Google Protobuf Wire]` | Context cache tokens read at 90% discount. |
| `total_input_tokens` | INTEGER | `[Telemetry Pipeline]` | Sum of uncached prompt tokens and cached tokens. |
| `output_tokens_total` | INTEGER | `[Google Protobuf Wire]` | Total generation tokens (thinking + answer). |
| `total_output_tokens` | INTEGER | `[Semantic View Alias]` | Ergonomic alias for `output_tokens_total`. |
| `thinking_tokens` | INTEGER | `[Google Protobuf Wire]` | Extended reasoning / chain-of-thought tokens. |
| `total_tokens` | INTEGER | `[Telemetry Computed]` | Pre-calculated sum: uncached + cached + output tokens. |
| `rate_limit_flag` | INTEGER | `[Telemetry Computed]` | `1` if turn encountered HTTP 429 or `RESOURCE_EXHAUSTED`. |
| `error_code` | TEXT | `[Google Protobuf Enum]` | Structured error enum string (e.g. `RESOURCE_EXHAUSTED`). |
| `error_text` | TEXT | `[Google Protobuf Wire]` | Exact error details string passed from runtime. |
| `ttft_ms` | REAL | `[Google Protobuf Wire]` | Time-to-first-token in milliseconds extracted from wire chunks. |
| `latency_ms` | REAL | `[Google Protobuf Wire]` | Total turn completion latency in milliseconds. |

### 2.2 `v_active_sessions` (Session Timeline & Cost)
Provides 1 row per active conversation session with pre-calculated duration, token totals, and costs.

| Column Name | Type | Provenance | Description / Aliasing |
| :--- | :---: | :--- | :--- |
| `convo_id` | TEXT | `[Google Upstream Wire]` | Primary key session UUID. |
| `title` | TEXT | `[Telemetry Pipeline]` | Auto-summarized conversation title. |
| `session_start` | TEXT | `[Telemetry Computed]` | First turn timestamp (`first_turn_ts`). |
| `session_end` | TEXT | `[Telemetry Computed]` | Last turn timestamp (`last_turn_ts`). |
| `duration_seconds` | REAL | `[Telemetry Computed]` | Elapsed session duration: `(julianday(end) - julianday(start)) * 86400`. |
| `turn_count` | INTEGER | `[Telemetry Computed]` | Total turn count in session. |
| `total_turns` | INTEGER | `[Semantic View Alias]` | Ergonomic alias for `turn_count`. |
| `total_input_tokens` | INTEGER | `[Telemetry Computed]` | Total prompt tokens consumed in session. |
| `total_output_tokens`| INTEGER | `[Telemetry Computed]` | Total generation tokens consumed in session. |
| `cached_tokens` | INTEGER | `[Telemetry Computed]` | Total cached tokens reused in session. |
| `thinking_tokens` | INTEGER | `[Telemetry Computed]` | Total thinking tokens generated in session. |
| `estimated_cost_usd` | REAL | `[Telemetry Computed]` | Dollar cost calculated from canonical model pricing. |
| `is_subagent` | INTEGER | `[Telemetry Pipeline]` | `1` if session was dispatched as a Star subagent or Native `/swarm` worker. |
| `agent_name` | TEXT | `[Telemetry Pipeline]` | Agent persona or swarm roster name (`default`, `implementer`, `Swarm Worker (narrator)`, etc.). |
| `subagent_role` | TEXT | `[Telemetry Pipeline]` | Dispatched subagent role or swarm assignment brief. |
| `turn1_input_tokens` | INTEGER | `[Telemetry Computed]` | Total input tokens on the first `step_type = 15` turn of the session (measures Turn-1 ambient prompt weight per `GADR-028`). |
| `turn1_cached_tokens` | INTEGER | `[Telemetry Computed]` | Cached tokens on the first `step_type = 15` turn of the session. |

### 2.3 `v_hourly_token_velocity` (Hourly Roll-Ups)
Aggregates hourly token consumption by UTC hour and model to identify consumption spikes.

| Column Name | Type | Provenance | Description / Aliasing |
| :--- | :---: | :--- | :--- |
| `hour_utc` | TEXT | `[Telemetry Computed]` | UTC hour bucket (`YYYY-MM-DD HH:00:00`). |
| `model_name` | TEXT | `[Telemetry Pipeline]` | Calibrated model display name. |
| `model` | TEXT | `[Semantic View Alias]` | Ergonomic alias for `model_name`. |
| `turn_count` | INTEGER | `[Telemetry Computed]` | Total generation turns executed in this hour. |
| `total_turns` | INTEGER | `[Semantic View Alias]` | Ergonomic alias for `turn_count`. |
| `total_input` | INTEGER | `[Telemetry Computed]` | Total prompt tokens in hour. |
| `total_cached` | INTEGER | `[Telemetry Computed]` | Total cached tokens in hour. |
| `total_output` | INTEGER | `[Telemetry Computed]` | Total generated tokens in hour. |

### 2.4 `v_rate_limit_events` (Correlated 429 Incidents)
Pre-joins HTTP 429 exhaustion logs with active conversation intervals.

| Column Name | Type | Provenance | Description / Aliasing |
| :--- | :---: | :--- | :--- |
| `event_time` | TEXT | `[Google Upstream Log]` | ISO-8601 UTC timestamp of 429 log event. |
| `code` | INTEGER | `[Google HTTP Code]` | HTTP 429 status code. |
| `reason` | TEXT | `[Google Upstream Enum]`| `RESOURCE_EXHAUSTED`. |
| `convo_id` | TEXT | `[Correlated Session]` | Conversation active during the 429 event. |
| `title` | TEXT | `[Correlated Session]` | Conversation title. |
| `agent_name` | TEXT | `[Correlated Session]` | Agent executing when rate limit hit. |
| `subagent_role` | TEXT | `[Correlated Session]` | Subagent role executing when rate limit hit. |

### 2.5 `v_quota_burn_intervals` (Consecutive Quota Depletion Intervals)
Computes server-side quota depletion (`delta_5h_pct`, `delta_weekly_pct`) and the empirical `ratio_5h_to_weekly` across consecutive deduplicated Connect-RPC snapshots within the same reset epoch (`ADR-094`).

| Column Name | Type | Provenance | Description / Aliasing |
| :--- | :---: | :--- | :--- |
| `id` | INTEGER | `[Telemetry Vault]` | Snapshot primary key. |
| `start_utc` | TEXT | `[Telemetry Computed]` | Previous snapshot ISO-8601 UTC timestamp (`LAG(timestamp_utc)`). |
| `end_utc` | TEXT | `[Telemetry Vault]` | Current snapshot ISO-8601 UTC timestamp. |
| `start_5h_rem_pct` | REAL | `[Connect-RPC Wire]` | Starting 5h remaining percentage (`0.0`–`100.0`). |
| `end_5h_rem_pct` | REAL | `[Connect-RPC Wire]` | Ending 5h remaining percentage (`0.0`–`100.0`). |
| `delta_5h_pct` | REAL | `[Telemetry Computed]` | 5h quota percentage points burned in interval (`start - end`). |
| `start_weekly_rem_pct` | REAL | `[Connect-RPC Wire]` | Starting weekly remaining percentage (`0.0`–`100.0`). |
| `end_weekly_rem_pct` | REAL | `[Connect-RPC Wire]` | Ending weekly remaining percentage (`0.0`–`100.0`). |
| `delta_weekly_pct` | REAL | `[Telemetry Computed]` | Weekly quota percentage points burned in interval (`start - end`). |
| `ratio_5h_to_weekly` | REAL | `[Telemetry Computed]` | Ratio `delta_5h_pct / delta_weekly_pct` (empirically `~4.0000x` on Ultra 5x). |
| `gemini_5h_reset_utc` | TEXT | `[Connect-RPC Wire]` | Active 5h discrete epoch reset timestamp. |
| `gemini_weekly_reset_utc`| TEXT | `[Connect-RPC Wire]` | Active weekly discrete epoch reset timestamp. |
| `active_status` | TEXT | `[Telemetry Pipeline]` | Quota status at snapshot (`SAFE`, `WARNING`, `CRITICAL`, `EXHAUSTED`). |

---

## 3. The 3-Grain Model of Quota Exhaustion

When analyzing quota limits, never confuse the three analytical grains:

1. **Macro Statement Grain (Billing Deduction)**:
   - Source: `log_events_archive` (`event_type = 'STATEMENT_RECONCILIATION'`) and `data/exhaustion_ledger.json`.
   - Meaning: Discrete confirmed credit debits on the user's Google One statement (e.g. 9 historical incidents totaling 3,640 credits burned).
2. **Micro Turn Grain (Model Generation 429)**:
   - Source: `v_turns` (`rate_limit_flag = 1`, `step_type = 15`).
   - Meaning: Actual model planner requests rejected with HTTP 429 `RESOURCE_EXHAUSTED`.
3. **Pipeline Step Grain (Retry Cascade)**:
   - Source: `steps_archive` (`rate_limit_flag = 1`).
   - Meaning: Checkpoints (`23`), tool executions (`132`), and background messages (`101`) that inherited the error code during an agent retry loop without making an independent model call.

---

## 4. In-Database Reference Dictionaries

### 4.1 `ref_step_types` (Step Categories)
Maps integer `step_type` values in `steps_archive` to canonical names and functional domains:

| `step_type` | `code_name` | `category` | Description |
| :---: | :--- | :---: | :--- |
| `14` | `USER_INPUT` | `USER` | User prompt, uploaded attachments, or instructions |
| `15` | `PLANNER_RESPONSE` | `MODEL` | Model reasoning, thinking tokens, and candidate response |
| `132` | `TOOL_EXECUTION` | `TOOL` | Execution of agent tools (bash, read, edit, grep, web) |
| `101` | `BACKGROUND_MESSAGE` | `SUBAGENT` | Inter-agent message or task completion notification |
| `23` | `CHECKPOINT` | `SYSTEM` | Context window compaction / summary checkpoint |
| `127` | `INVOKE_SUBAGENT` | `SUBAGENT` | Delegation invocation to a subagent |
| `138` | `ASK_QUESTION` | `USER` | Interactive user prompt / modal dialog question |
| `90` | `AGENT_STATE` | `SYSTEM` | Agent internal state snapshot |
| `5` | `REPLACE_FILE_CONTENT` | `TOOL` | Direct file replacement tool execution |
| `7` | `GREP_SEARCH` | `TOOL` | Direct grep search tool execution |
| `8` | `VIEW_FILE` | `TOOL` | Direct file inspection tool execution |
| `9` | `LIST_DIR` | `TOOL` | Direct directory listing tool execution |
| `17` | `WRITE_TO_FILE` | `TOOL` | Direct file creation/write tool execution |
| `21` | `RUN_COMMAND` | `TOOL` | Direct shell command execution |
| `33` | `SEARCH_WEB` | `TOOL` | Direct web search execution |
| `38` | `CALL_MCP_TOOL` | `TOOL` | External MCP tool execution |

### 4.2 `ref_status_codes` (Execution & HTTP Statuses)
Maps step status enums (`1`..`9`) and API response codes (`200`..`504`):

| `code` | `standard_name` | `domain` | `is_error` | `is_rate_limit` | Description |
| :---: | :--- | :---: | :---: | :---: | :--- |
| `1` | `INITIALIZING` | `STEP_STATUS` | 0 | 0 | Step initiated, awaiting runtime start |
| `2` | `RUNNING` | `STEP_STATUS` | 0 | 0 | Step actively executing |
| `3` | `COMPLETED` | `STEP_STATUS` | 0 | 0 | Step completed successfully |
| `4` | `INVALID_INPUT` | `STEP_STATUS` | 1 | 0 | Step failed due to schema or argument validation |
| `5` | `AWAITING_INPUT` | `STEP_STATUS` | 0 | 0 | Step paused waiting for user input or subagent |
| `6` | `CANCELLED` | `STEP_STATUS` | 1 | 0 | Step cancelled by user or timeout |
| `7` | `EXECUTION_ERROR`| `STEP_STATUS` | 1 | 0 | Tool, model, or command failure |
| `8` | `SKIPPED` | `STEP_STATUS` | 0 | 0 | Step skipped by execution plan |
| `9` | `TERMINATED` | `STEP_STATUS` | 1 | 0 | Step terminated prematurely |
| `200` | `OK` | `HTTP` | 0 | 0 | Successful API response |
| `400` | `BAD_REQUEST` | `HTTP` | 1 | 0 | Invalid API request or arguments |
| `401` | `UNAUTHENTICATED`| `HTTP` | 1 | 0 | Missing or invalid credentials |
| `403` | `PERMISSION_DENIED`| `HTTP`| 1 | 0 | Access forbidden or quota exhausted |
| `429` | `RESOURCE_EXHAUSTED`| `HTTP`| 1 | 1 | Rate limit or burst quota capacity depleted |
| `500` | `INTERNAL_ERROR` | `HTTP` | 1 | 0 | Internal server error |
| `503` | `SERVICE_UNAVAILABLE`| `HTTP`| 1 | 0 | Provider model temporarily overloaded |
| `504` | `DEADLINE_EXCEEDED`| `HTTP` | 1 | 0 | Gateway or RPC timeout |

---

## 5. Physical Tables Catalog

| Table Name | Primary Key | Description & Provenance |
| :--- | :--- | :--- |
| **`conversations_archive`** | `convo_id` | Session metadata: workspace paths, title, turn count, token sums, cost, `first_turn_ts`, `last_turn_ts`, `agent_name`, `is_subagent`, `subagent_role`, `parent_convo_id`, `turn1_input_tokens`, `turn1_cached_tokens`. |
| **`steps_archive`** | `(convo_id, step_idx)` | Hybrid store: decoded tokens, text (`payload_text`, `error_text`), flags (`rate_limit_flag`, `error_code`), and lossless raw wire protobuf blobs. |
| **`tool_calls_archive`** | `id` (AUTOINCREMENT) | Indexed individual tool executions (`tool_name`, `tool_action`, `arguments_json`, `result_summary`, `timestamp`). |
| **`skills_archive`** | `id` (AUTOINCREMENT) | Indexed skill triggers (`skill_name`, `skill_path`, `activation_type`, `timestamp`). |
| **`log_events_archive`** | `id` (AUTOINCREMENT) | Deduplicated runtime log events (`event_fingerprint` UNIQUE, `timestamp_iso`, `code`, `reason`, `raw_line`). |
| **`quota_snapshots_archive`** | `id` (AUTOINCREMENT) | Deduplicated Connect-RPC live quota snapshots (`snapshot_fingerprint` UNIQUE, `timestamp_utc`, `gemini_5h_remaining`, `gemini_weekly_remaining`, `claude_weekly_remaining`, reset epochs, `active_status`). |
| **`quota_regime_events_archive`** | `event_id` | Historical quota regime shifts, unscheduled early weekly resets (`QUOTA_RESET_BONUS`), empirical burn-rate calibrations (`BURN_RATE_SHIFT`), and human-in-the-loop verification statuses (`PENDING_REVIEW`, `CONFIRMED`, `DISMISSED`). |
| **`vault_sync_state`** | `key` | Ingestion high-watermark pointers and current subscription tier tracking. |
| **`weekly_cycles_archive`** | `cycle_key` | Historical weekly cycle aggregates: total input/cached/output tokens, cost USD/GBP, overage credits burned. |
| **`subscription_history_archive`** | `id` (AUTOINCREMENT) | Historical plan tier boundaries (`pro`, `ultra_5x`), pricing (£18.99 vs £79.99), and validity intervals. |
| **`ref_step_types`** | `step_type` | Reference dictionary for step type enums (see §4.1). |
| **`ref_status_codes`** | `code` | Reference dictionary for execution status enums and HTTP codes (see §4.2). |

---

## 6. Performance Indexes Guide

To guarantee sub-millisecond execution, all queries should align with these compound and partial indexes:

* **Time-Window Turns Range**: `idx_steps_step_type_ts ON steps_archive(step_type, timestamp, model_name)`
* **Session Step Timeline**: `idx_steps_convo_id_ts ON steps_archive(convo_id, timestamp)`
* **Failure Step Audit**: `idx_steps_error_text ON steps_archive(timestamp) WHERE error_text IS NOT NULL AND error_text != ''`
* **Rate-Limit & Exhaustion Seek**: `idx_steps_rate_limit ON steps_archive(timestamp) WHERE rate_limit_flag = 1`
* **Log Code & Event Seek**: `idx_log_events_code_type_ts ON log_events_archive(code, event_type, timestamp_iso)`
* **Quota Snapshot Timeline**: `idx_quota_snapshots_ts ON quota_snapshots_archive(timestamp_utc)`
* **Quota Regime Events Timeline**: `idx_quota_regime_events_ts ON quota_regime_events_archive(detected_at_utc, review_status)`

---

## 7. Fast Deterministic CLI (`scripts/quota_history.py`)

Rather than having agents perform multi-turn ad-hoc SQL exploratory queries, run the dedicated CLI:

```bash
# Full executive audit (macro deductions + micro 429 throttles)
python3 scripts/quota_history.py --summary

# Machine-readable JSON output for automated ingestion
python3 scripts/quota_history.py --json

# Macro statement deductions only
python3 scripts/quota_history.py --incidents

# Micro turn-level 429 throttles only
python3 scripts/quota_history.py --turns
```
