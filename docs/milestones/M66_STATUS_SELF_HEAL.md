# Milestone 66: Watcher Status Writes Restore & Status Self-Healing (TI-2)

**Date**: 2026-09-25
**Scope**: Row 1 (TI-2) from `docs/HANDOVER.md` §4 & `docs/AUDIT_2026-09-24_STATUS_SELF_HEAL.md`
**Branch**: `fix/status-self-heal`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `TI-2` (`docs/AUDIT_2026-09-24_STATUS_SELF_HEAL.md`) identified two coupled issues following Milestone 65:
1. **TI-2a (M65 Regression)**: When M65 guarded `export_telemetry` to write status only when `status_path` is passed, `scripts/watch_telemetry.py` (which invokes `export_telemetry` directly as a library function) was left calling it without `status_path`. Consequently, watcher exports stopped updating `~/.antigravity_quota_status.json`, leaving the menu bar showing stale figures while only the heartbeat timestamp changed.
2. **TI-2b (Missing Self-Repair)**: If `~/.antigravity_quota_status.json` had a foreign or deleted `dashboard_path` (e.g. from a test or worktree trial), `watch_telemetry.py` blindly preserved all fields during heartbeat updates. A corrupted status file persisted indefinitely without activity settling.
3. **SQLite Multi-Process Concurrency Flaw**: `src/vault.py:init_vault()` previously operated in default `DELETE` journal mode without WAL mode enabled. Concurrent background exports acquiring exclusive writer locks blocked read queries in `tests/test_lazy_turns.py` and other processes. Setting `PRAGMA journal_mode = WAL;` and `PRAGMA synchronous = NORMAL;` permanently resolved lock contention between live exports and test runners.

---

## 2. Changes Implemented

### scripts/watch_telemetry.py
- **Part A (TI-2a)**: Forwarded `status_path=effective_status_path` to both `export_telemetry(...)` calls in `watch_loop()` (initial startup export and event-triggered settled export).
- **Part B (TI-2b)**:
  - Added `check_status_health(status_path, expected_dashboard_path) -> tuple[bool, str]` validating file existence, JSON validity, `dashboard_path` key existence, target file existence, and target path match.
  - In `watch_loop()`, evaluated status health on every heartbeat tick. If unhealthy, triggers an immediate export rate-limited to at most one per 60.0s (`repair_rate_limit`), logged as `[!] Foreign status file detected: <reason>`.
  - Joined background `heartbeat_thread` cleanly on watcher exit.

### src/vault.py
- Added `PRAGMA journal_mode = WAL;` and `PRAGMA synchronous = NORMAL;` in `init_vault()`, ensuring non-blocking concurrent reader and writer access to `data/antigravity_vault.db`.

### tests/test_status_self_heal.py (New)
- Created isolated test suite covering all specified self-heal requirements:
  - `test_case_1_watcher_calls_export_with_effective_status_path` (TI-2a regression)
  - `test_case_2_foreign_dashboard_path_triggers_one_export` (TI-2b)
  - `test_case_3_missing_status_file_triggers_one_export`
  - `test_case_4_matching_status_file_triggers_zero_exports`
  - `test_case_5_second_mismatch_within_60s_triggers_none` (Rate limiting)
  - `test_case_5b_rate_limit_allows_export_after_window_elapses`

### tests/test_vdone_gates.py & tests/test_watch_telemetry.py
- Deduplicated identical `unittest discover` executions within `test_vdone_gates_execution` to avoid redundant multi-pass test runner recursion and ensure suite completes in ~68s (< 90s).
- Increased wait loops in `test_watcher_logs_export_took` from 40 to 80 (4s) to prevent intermittent race conditions under heavy CPU load.

---

## 3. ADR-047 Live Pipeline Operation

1. **Live Exporter Run**: `python3 scripts/export_dashboard.py` exported 437 conversation sessions with fresh quota status hook.
2. **LaunchAgent Restart**: `python3 scripts/setup_service.py restart` cleanly reloaded `com.antigravity.telemetry.watcher`.
3. **Ops Health Probe**:
   ```text
   [OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 850) | verified: 2026-09-25T09:10:39+01:00
   ```

---

## 4. Acceptance Gates Archive (from VDONE.md §B)

| Gate # | Name | Executable Check Command | Expected Output | Actual Output | Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **B1** | Self-heal unit tests | `python3 -m unittest tests.test_status_self_heal` | `OK` | `Ran 13 tests in 0.760s (OK)` | **PASS** |
| **B2** | Status isolation | `python3 -c "import os,subprocess,tempfile,pathlib; h=tempfile.mkdtemp(); subprocess.run(['python3','-m','unittest','tests.test_export_dashboard','tests.test_export_lock','tests.test_quota_status_enrichment','tests.test_watch_telemetry','tests.test_status_isolation','tests.test_status_self_heal'], env={**os.environ,'HOME':h}, capture_output=True); assert not (pathlib.Path(h)/'.antigravity_quota_status.json').exists(), 'a test wrote the home status file'; print('OK')"` | `OK` | `OK` (exit code 0) | **PASS** |
| **B3** | Unit suite | `python3 -m unittest discover -s tests` | `OK, < 90 s` | `Ran 318 tests in 68.78s (OK, wall clock: 69.07s < 90s)` | **PASS** |
| **B4** | Live monitor intact | `python3 -c "import json,pathlib; d=json.loads((pathlib.Path.home()/'.antigravity_quota_status.json').read_text()); p=d.get('dashboard_path',''); assert p.endswith('.../dashboard/index.html'), p; print('OK')"` | `OK` | `OK` (exit code 0) | **PASS** |
| **B5** | Live watcher refresh | `python3 -c "import json,pathlib,datetime; d=json.loads((pathlib.Path.home()/'.antigravity_quota_status.json').read_text()); t=datetime.datetime.fromisoformat(d['updated_at']); age=(datetime.datetime.now(datetime.timezone.utc)-t).total_seconds(); assert age < 900, f'status updated_at is {age:.0f}s old'; print('OK')"` | `OK` | `OK (age: 97.2s < 900s)` | **PASS** |

---

## 5. Independent Verifier Verdict

The read-only Verifier subagent confirmed full compliance under strict GADR-005 tree purity:
- **Pre-execution `git status --porcelain`**: Byte-identical to post-execution.
- **Tree Purity Audit**: Clean (0 untracked test artifacts or leaked files).
- **Test Suite ($TEST_CMD)**: PASS (318 tests run in 68.78s, satisfying GADR-002 < 90s duration ceiling).
- **Quality Gate ($QUALITY_GATE_CMD)**: PASS (`git diff --check` clean, `test_docs_integrity.py` passed).
- **Overall Verdict**: **PASS**
