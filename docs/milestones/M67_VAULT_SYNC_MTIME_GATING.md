# Milestone 67: Vault Sync Mtime Gating & Batch Query Optimization (C1)

**Date**: 2026-09-26
**Scope**: Row 1 (C1) from `docs/HANDOVER.md` §4 & `docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md`
**Branch**: `perf/vault-sync-mtime-gating`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `C1` (`docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md`) identified a critical scaling bottleneck in `sync_conversations_to_vault` (`src/vault.py`):
1. **Unconditional Full-History Scans**: `sync_conversations_to_vault` opened and closed over 1,090 SQLite connections across 545 upstream conversation DBs on every sync cycle, taking ~89s per cycle and causing export latencies over 101s.
2. **Aggregated Count Query Loop**: Executed 544 individual queries in a Python loop to calculate aggregates for every conversation in vault history.
3. **Owner Decision 1**: Gating on `st_mtime > last_sync_time` to inspect only modified databases, adding `--force-full-scan` CLI option and `force: bool = False` argument to allow bypassing the cache on demand.

---

## 2. Changes Implemented

### src/vault.py
- **`sync_conversations_to_vault`**:
  - Added `force: bool = False` argument.
  - Recorded and read `conversations_last_sync_mtime` in `vault_sync_state`.
  - Filtered `db_paths` by `p.stat().st_mtime > last_sync_mtime` when `not force`.
  - Added Fast Path: if no candidate DBs are newer than `last_sync_mtime` and `conversations_archive` already contains rows, bypasses aggregation and lineage queries completely (reducing latency to ~0.11s).
  - Scoped aggregate re-computation to `conversations_synced_set` instead of entire vault history.
  - Added `_execute_sql_with_retry` and `_commit_with_retry` for concurrency resilience against `sqlite3.OperationalError` (database locked).
  - Released read lock immediately after querying high watermarks to prevent filesystem scan lock contention.
  - Returned `discovered_databases` and `scanned_databases` in sync stats dictionary.

### scripts/export_dashboard.py
- Refactored argument parser into reusable `build_parser() -> argparse.ArgumentParser`.
- Added `--force-full-scan` CLI flag.
- Threaded `force_full_scan` through `export_telemetry` to `sync_conversations_to_vault(..., force=force_full_scan)`.

### tests/test_vault_mtime_gating.py (New)
- Added comprehensive unit tests covering:
  - Last sync mtime persistence in `vault_sync_state`.
  - Gating skip behavior for unmodified DBs.
  - Modification detection via updated file mtimes.
  - `force=True` bypass of mtime cache.
  - `--force-full-scan` argument presence in `build_parser()`.
  - Stats dictionary key assertions.

### docs/REPO_MAP.md & VDONE.md
- Registered `test_vault_mtime_gating.py` in test tree.
- Configured VDONE Section B gates for M67.

---

## 3. ADR-047 Live Pipeline Operation

1. **LaunchAgent Restart**: `python3 scripts/setup_service.py restart` reloaded `com.antigravity.telemetry.watcher`.
2. **Sync Latency Benchmark**:
   - Idle sync duration: **0.13s** (down from **88.87s**, a 680x speedup).
3. **Ops Health Probe**: Verified live watcher running and refreshing.

---

## 4. Acceptance Gates Archive (from VDONE.md §B)

| Gate # | Name | Executable Check Command | Expected Output | Actual Output | Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **B1** | Mtime gating unit tests | `python3 -m unittest tests.test_vault_mtime_gating` | `OK` | `Ran 7 tests in 1.803s, OK` | **PASS** |
| **B2** | Vault sync latency gate (< 5.0s) | `python3 -c "import time, sys; sys.path.insert(0, '.'); from src.vault import sync_conversations_to_vault; from antigravity_telemetry import DEFAULT_ANTIGRAVITY_DIR; t0=time.time(); r=sync_conversations_to_vault(DEFAULT_ANTIGRAVITY_DIR); dur=time.time()-t0; assert dur < 5.0, f'Vault sync took {dur:.2f}s'; print(f'OK: {dur:.2f}s')"` | `OK` | `OK: 0.13s` | **PASS** |
| **B3** | Force full scan support | `python3 -c "import inspect; from src.vault import sync_conversations_to_vault; sig=inspect.signature(sync_conversations_to_vault); assert 'force' in sig.parameters and sig.parameters['force'].default is False; import scripts.export_dashboard as ed; p=ed.build_parser(); act=[a.dest for a in p._actions]; assert 'force_full_scan' in act; print('OK') # --dry-run"` | `OK` | `OK` | **PASS** |
| **B4** | Incremental sync state persistence | `python3 -c "import sqlite3; conn=sqlite3.connect('file:data/antigravity_vault.db?mode=ro', uri=True); c=conn.cursor(); c.execute('SELECT COUNT(*) FROM conversations_archive'); count=c.fetchone()[0]; assert count > 0; c.execute(\"SELECT value FROM vault_sync_state WHERE key = 'conversations_last_sync_mtime'\"); v=c.fetchone(); assert v and float(v[0]) > 0; conn.close(); print('OK')"` | `OK` | `OK` | **PASS** |
| **B5** | Full test suite under 90s | `python3 -m unittest discover -s tests` | `OK, < 90 s` | `Ran 325 tests in 63.557s, OK` | **PASS** |

---

## 5. Independent Verifier Verdict

The read-only Verifier subagent confirmed full compliance under strict GADR-005 tree purity:
- **Pre & Post Tree Purity**: Clean (0 porcelain lines).
- **Unit Suite ($TEST_CMD)**: PASS (325 tests in 63.56s < 90s).
- **Quality Gate ($QUALITY_GATE_CMD)**: PASS (`git diff --check` clean, 11 docs integrity tests OK).
- **Fail-First Analysis**: 2 gates showed the change (B1, B3).
- **Overall Verdict**: **PASS**
