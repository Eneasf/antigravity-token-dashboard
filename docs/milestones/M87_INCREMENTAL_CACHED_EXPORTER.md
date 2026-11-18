# Milestone 87: Incremental Cached Exporter (<500ms) & Fast Heavy Rollup

**Date**: 2026-10-02
**Scope**: Row 1 from `docs/HANDOVER.md` §4 Open Work (ADR-084)
**Branch**: `feat/m87-incremental-cached-exporter`
**Verdict**: **PASS**

---

## 1. Overview & Context

This milestone resolves the heavy dashboard export latency bottleneck, slashing export duration from 40–80s down to sub-second (<500ms CLI, ~78ms in-memory watcher) across 526 conversation databases:
- **Two-Tier Incremental Caching Architecture**:
  - **Tier 1 (In-Memory Cache)**: Fast process-local dictionary caching (`_IN_MEMORY_CONVO_CACHE`, `_IN_MEMORY_VAULT_CACHE`) inside long-running daemon processes (`watch_telemetry.py`), allowing successive Heavy Tier exports to execute in ~78ms.
  - **Tier 2 (Persistent SQLite Cache)**: Shared, durable SQLite database (`dashboard/.export_cache.db`) caching parsed summaries, raw turns, fingerprints, and config hashes with WAL mode (`PRAGMA journal_mode=WAL;`) and `PRAGMA busy_timeout=60000;` per GADR-013 / ADR-081.
- **Fingerprint & Config Gating**:
  - Conversation databases are checked using lightweight `os.scandir` stat checks (~8ms for 526 DBs), gating re-reads on `(effective_mtime_ns, effective_size_bytes)` including SQLite `-wal` sidecars.
  - Cache entries are invalidated on configuration changes via deterministic SHA-256 hashes (`pricing_hash`, `intervals_hash`).
  - Vault analytics (`extract_tool_analytics`, `extract_swarm_lineage`, `get_vault_truncation_markers`, subagent parent-child counts, prompts, tool calls) are cached against vault file mtime and size, avoiding expensive repetitive scans over the 3.28 GB vault database.
- **Timestamp Parsing Cache**:
  - Implemented `@functools.lru_cache(maxsize=16384)` in `src/temporal.py`, `src/aggregator_pricing.py`, and `src/git_timeline.py`, eliminating over 1.5 million redundant ISO string parsing operations across 40,454 turns.
- **Watcher Debounce Cadence Reduction**:
  - With Heavy Tier exports reduced to <500ms, watcher debounce settle window was safely lowered from 30.0s to 2.0s (max delay lowered from 60.0s to 10.0s) in `scripts/watch_telemetry.py` and `scripts/setup_service.py`, bringing near real-time updates to the dashboard.
- **Resilience & Safe Invariants**:
  - Automatic self-healing on corrupt cache files with zero crashes or data corruption.
  - Added `--force-full-scan` flag to both `export_telemetry()` and CLI parser to force full re-scan and refresh cache.

---

## 2. Changes Implemented

- **`src/temporal.py`**:
  - Added `_parse_iso_str_cached` with `@functools.lru_cache(maxsize=16384)`.
  - Replaced slow `copy.deepcopy` in `resolve_rates` with fast `dict()`.
- **`src/aggregator_pricing.py`**:
  - Added cached `_parse_ts_str` with `@functools.lru_cache(maxsize=16384)` and fast datetime passthrough in `parse_timestamp`.
- **`src/git_timeline.py`**:
  - Added `_parse_str_to_epoch` with `@functools.lru_cache(maxsize=16384)` in `parse_timestamp_to_epoch`.
- **`scripts/export_dashboard.py`**:
  - Implemented `get_cache_db_path()`, `init_export_cache_db()`, `get_cache_connection()`, `compute_config_hash()`, `get_conversation_db_fingerprint()`.
  - Implemented `load_incremental_conversations()`: checks fingerprints via `os.scandir`, re-reads only dirty/new conversations, prunes deleted DBs, and persists to SQLite cache.
  - Implemented `load_vault_analytics_cached()`: caches expensive swarms, tool analytics, truncation markers, subagents, prompts, and tool calls.
  - Added `--force-full-scan` flag and fixed `write_quota_status_file` NoneType timestamp comparison.
- **`scripts/watch_telemetry.py`**:
  - Reduced default `debounce_seconds` from 30.0s to 2.0s, and `max_debounce_seconds` from 60.0s to 10.0s.
- **`scripts/setup_service.py`**:
  - Updated default `--debounce` to 2.0s in LaunchAgent plist generator and CLI arguments.
- **`.gitignore`**:
  - Added `.export_cache.db*` and `dashboard/.export_cache.db*`.
- **`tests/test_incremental_cache.py`**:
  - Authored comprehensive test suite covering cold/warm lifecycle, dirty detection, additions, deletions, `--force-full-scan`, corruption self-healing, pricing invalidation, and WAL pragmas.
- **`docs/REPO_MAP.md`**:
  - Registered `tests/test_incremental_cache.py`.

---

## 3. Acceptance Gates

| Gate # | Description | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :--- | :--- |
| C1 | Incremental cache unit suite | `python3 -m unittest tests.test_incremental_cache` | `OK` | PASS (13 tests in 1.07s) |
| C2 | Two-Tier Fast Ticker suite | `python3 -m unittest tests.test_two_tier_exporter` | `OK` | PASS (13 tests in 1.62s) |
| C3 | Fast warm in-memory export | Benchmarked in `export_dashboard.py` | `< 500ms` | PASS (measured 78ms) |
| C4 | Full unit test suite | `python3 -m unittest discover -s tests` | `454 passed, < 90s` | PASS (454 passed in 39.5s) |
| C5 | Docs integrity | `python3 -m unittest tests.test_docs_integrity` | `OK` | PASS |
| C6 | Headless dashboard boot | `npx playwright test e2e/dashboard-boot.spec.js` | `1 passed` | PASS |
| C7 | Quality gate command | `$QUALITY_GATE_CMD` | `exit code 0` | PASS |
