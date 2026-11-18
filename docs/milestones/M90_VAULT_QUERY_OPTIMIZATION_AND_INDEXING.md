# Milestone 90: Telemetry Vault Query Optimization, Structured Extraction & Reference Dictionaries

**Date**: 2026-10-06  
**Scope**: Database Architecture, Compound & Partial Indexing, Structured Error Extraction, Self-Documenting Reference Tables, Analytical Views & Benchmark KPI Harness  
**Branch**: `feat/m90-menubar-top-refactor-and-popover-bento`  
**Verdict**: **PASS**  

---

## 1. Overview & Architectural Motivation

During investigation into quota exhaustion and credit spillover events (specifically locating the -517 credit burn on 20 September 2026), interactive queries against `data/antigravity_vault.db` (3.78 GB, 192,832 rows in `steps_archive`) suffered severe latency degradation:
1. **Unindexed Timestamp Range Lookups**: Filtering model generation turns (`step_type = 15 AND timestamp >= '2026-09-13'`) forced SQLite to fetch and inspect all ~75,000 model turns sequentially from disk.
2. **Gigabyte-Scale Free-Text Scans**: Queries searching for error codes or exhaustion strings (`LIKE '%RESOURCE_EXHAUSTED%'` or `LIKE '%429%'`) scanned gigabytes of decoded text/protobuf payloads sequentially across all 192k rows, taking 10–15 seconds and causing CLI timeouts.
3. **Unindexed Telemetry Codes**: `log_events_archive` had duplicate indexes on `timestamp_iso` but zero index on `code` (e.g. `code = 429`).
4. **Undocumented Magic Numbers**: `steps_archive` stores `step_type` (14, 15, 23, 101, 132) and `status` (1, 2, 3, 4, 7) as raw integers without any in-database lookup dictionary, requiring manual cross-referencing against source code and markdown specs.

This milestone establishes a comprehensive performance and schema optimization package governed by empirical KPI benchmarks.

---

## 2. Architecture Decisions Adopted

### ADR-087: Telemetry Vault Compound & Partial Indexing
- **Decision**: Add compound and partial indexes to `src/vault_schema.py`:
  1. `idx_steps_step_type_ts ON steps_archive(step_type, timestamp, model_name)`: transforms time-window turn filtering from sequential disk reads into sub-millisecond B-tree range seeks.
  2. `idx_steps_convo_id_ts ON steps_archive(convo_id, timestamp)`: enables instant session step timeline filtering.
  3. `idx_steps_error_text ON steps_archive(timestamp) WHERE error_text IS NOT NULL AND error_text != ''`: partial index covering only the ~840 failure turns out of 192k total rows.
  4. `idx_steps_rate_limit ON steps_archive(timestamp) WHERE rate_limit_flag = 1`: partial index covering exhaustion steps.
  5. `idx_log_events_code_type_ts ON log_events_archive(code, event_type, timestamp_iso)`: compound index covering HTTP/RPC error codes, event types, and timestamps.

### ADR-088: Structured Rate-Limit & Error Flag Extraction vs. FTS5 Rejection
- **Decision**: Formally reject SQLite `FTS5` virtual table indexing over `payload_text`.
  - *Rationale*: An inverted FTS5 index over massive JSON/protobuf text blobs would inflate the 3.78 GB database by +2 to 3 GB and severely increase WAL checkpoint lock contention during concurrent multi-agent swarm execution.
  - *Alternative*: Extract two structured columns into `steps_archive` at ingestion:
    - `rate_limit_flag INTEGER DEFAULT 0`: set to 1 when a turn encounters 429 or `RESOURCE_EXHAUSTED`.
    - `error_code TEXT`: structured error code (e.g. `RESOURCE_EXHAUSTED`, `PERMISSION_DENIED`).
  - Backed by partial index `idx_steps_rate_limit ON steps_archive(timestamp) WHERE rate_limit_flag = 1`.

### ADR-089: Self-Documenting Telemetry Reference Dictionaries (`ref_step_types`, `ref_status_codes`)
- **Decision**: Populate authoritative lookup tables in SQLite during `init_vault()`:
  1. `ref_step_types(step_type INTEGER PRIMARY KEY, code_name TEXT, category TEXT, description TEXT)`: documents all step types (14=USER_INPUT, 15=PLANNER_RESPONSE, 23=CHECKPOINT, 101=BACKGROUND_MESSAGE, 132=TOOL_EXECUTION, etc.).
  2. `ref_status_codes(code INTEGER PRIMARY KEY, standard_name TEXT, domain TEXT, description TEXT, is_error INTEGER, is_rate_limit INTEGER)`: documents step execution statuses (1..9) and standard HTTP/RPC codes (200, 400, 403, 429, 500, 503).

### ADR-090: Canonical Telemetry Analytical Views
- **Decision**: Define 4 canonical SQL views in `src/vault_schema.py`:
  1. `v_active_sessions`: Direct session timeline view with `session_start`, `session_end`, duration in seconds, turn count, total tokens, cost USD, subagent status, and agent role.
  2. `v_turns`: Pre-filters `step_type = 15` model generation turns with computed `total_tokens`.
  3. `v_hourly_token_velocity`: Hourly roll-up of turns, input, cached, and output tokens by model.
  4. `v_rate_limit_events`: Pre-joins 429 log events with active conversation intervals.

### ADR-091: Empirical Database Benchmarking & KPI Governance Harness
- **Decision**: Author `scripts/bench_vault_performance.py` measuring 4 core database KPIs:
  1. **Query Latency (ms)**: Mean and Min across time-window turns, error audits, and rate-limit seeks.
  2. **Rows & Pages Inspected**: Full table scans vs index B-tree seeks.
  3. **Index Storage Footprint**: Total index bytes added (< 30 MB / < 1% of DB size).
  4. **Ingestion Write Overhead**: Impact on batch insert throughput (< 2 µs / step).

---

## 3. Empirical Benchmark Scorecard (BEFORE vs. AFTER)

Measured directly against live production database `data/antigravity_vault.db` (192,832 rows in `steps_archive`):

| Benchmark Query Pattern | Baseline `BEFORE` | Optimized `AFTER` | Speedup Factor | Query Plan Evolution |
| :--- | :---: | :---: | :---: | :--- |
| **Failure steps lookup**<br>`WHERE error_text IS NOT NULL` | **280.10 ms** | **5.91 ms** | **47.4x faster** | `SCAN steps_archive` (192k rows) $\rightarrow$ `SCAN USING INDEX idx_steps_error_text` (840 entries) |
| **Exhaustion / 429 seek**<br>Free-text vs Structured Flag | **1,119.09 ms** | **0.35 ms** | **3,197x faster** | `SCAN steps_archive` (JSON text scan) $\rightarrow$ `SCAN USING INDEX idx_steps_rate_limit` (221 entries) |
| **Log event code lookup**<br>`WHERE code = 429` | 0.07 ms | **0.03 ms** | **2.3x faster** | `SCAN log_events_archive` $\rightarrow$ `SEARCH USING INDEX idx_log_events_code_type_ts (code=?)` |
| **Session step timeline seek**<br>`WHERE convo_id = ? AND ts >= ?` | 0.22 ms | **0.20 ms** | Range Seek | `SEARCH USING INDEX idx_steps_convo_id` $\rightarrow$ `SEARCH USING INDEX idx_steps_convo_id_ts` |
| **Active Session Analysis**<br>`SELECT * FROM v_active_sessions` | *N/A (no view)* | **3.49 ms** | **Instant timeline** | Joins start/end timestamps, calculates duration & token sums across 913 sessions in 3.49 ms |

### Storage Footprint Added (KPI 3)
- **Database Size Before**: 3,612.18 MB (20 indexes, 0 views)
- **Database Size After**: 3,631.72 MB (25 indexes, 4 views)
- **Net Delta**: **+19.54 MB** (**+0.54%** disk overhead, strictly within `< 1.5%` budget).

---

## 4. Verification Gate Proofs

- **Gate 1 (Zero Unit Test Regression)**: `python3 -m unittest discover -s tests` $\rightarrow$ **Ran 472 tests in 51.9s, OK**.
- **Gate 2 (Documentation Integrity)**: `python3 -m unittest tests/test_docs_integrity.py` $\rightarrow$ **Ran 12 tests in 0.79s, OK**.
- **Gate 3 (Schema Migration & Idempotence)**: `python3 -m unittest tests/test_vault_schema.py` $\rightarrow$ **Ran 9 tests in 0.15s, OK**.
- **Gate 4 (Playwright Dashboard Boot)**: `npx playwright test e2e/dashboard-boot.spec.js` $\rightarrow$ **1 passed in 9.1s, OK**.
- **Gate 5 (Git Whitespace Check)**: `git diff --check` $\rightarrow$ **Clean (0 errors)**.
