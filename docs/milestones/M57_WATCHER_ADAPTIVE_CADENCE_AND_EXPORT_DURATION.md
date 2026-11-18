# M57 · Watcher Adaptive Cadence & Export Duration · 2026-09-20 · v2.15.0

## Why
When Antigravity telemetry export operations run during active coding, exports can take several seconds to synchronize vault telemetry and parse large conversation histories. A fixed 2s settle window causes telemetry watcher thrashing and near-continuous export re-runs. Per Audit 2026-09-19 Row 11 (C7) and ADR-071, the watcher debounce settle window is made adaptive (`max(2s, last_export_duration)`), export duration is logged in watcher stdout, and `export_seconds` is exposed in `meta.json` and `meta.js`.

## What changed
- `scripts/watch_telemetry.py`: Implemented `DebounceController.update_settle_window(duration)` and added export cycle duration measurement and logging (`export took {duration:.2f}s`).
- `scripts/export_dashboard.py`: Measured export execution duration, populated `"export_seconds"` into `meta_payload` (with `0.0` pinned under `--reference-time` for byte determinism per ADR-004), and included `export_seconds` in return dictionary.
- `tests/test_watch_telemetry.py`: Added unit tests for adaptive settle window expansion and clamping, and integration tests verifying `"export took"` stdout logging.
- `tests/test_export_dashboard.py`: Added assertions verifying `"export_seconds"` presence and non-negative numeric value in `meta.json`.
- `tests/test_docs_integrity.py`: Registered pre-tag version `"2.15.0"` in documentation version test allowlist.
- `docs/SYSTEM_DESIGN.md`: Documented adaptive settle window algorithm, dynamic starvation scaling, and export latency telemetry under §3.1.
- `docs/TELEMETRY_SPEC.md`: Documented `export_seconds` in `meta.json` / `meta.js` payload specification.
- `CHANGELOG.md`: Added release notes for Milestone 57 (v2.15.0).
- `package.json` & `pyproject.toml`: Bumped version to `2.15.0`.

## Decisions taken
| ADR | Title | Status | Summary | Doc |
|---|---|---|---|---|
| ADR-071 | Watcher Adaptive Cadence | Adopted | Adaptive debounce max(2s, dur), export_seconds. | [doc](milestones/M57_WATCHER_ADAPTIVE_CADENCE_AND_EXPORT_DURATION.md) |

## Gates & proofs
- **B1 (Adaptive debounce logic)**: `python3 -m unittest tests.test_watch_telemetry.TestWatchTelemetry.test_adaptive_settle_window` passed (Ran 1 test in 0.003s, exit 0).
- **B2 (Export took log presence)**: `grep -c "export took" scripts/watch_telemetry.py` returned `4` (exit 0).
- **B3 (Export seconds in meta)**: `dashboard/meta.json` contains `export_seconds: 12.44` (exit 0).
- **B4 (Watch telemetry unit suite)**: `python3 -m unittest tests.test_watch_telemetry` passed (Ran 12 tests in 1.160s, exit 0).
- **B5 (Export tests suite)**: `python3 -m unittest discover -s tests -p 'test_export_*.py'` passed (Ran 10 tests in 1.960s, exit 0).

## Ops check
```
[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 40052) | verified: 2026-09-20T16:46:32+01:00
```

## Screenshots
N/A (performance and telemetry cadence milestone; no UI interaction changes introduced).

## Verifier report
```markdown
# Independent Verification Report: Milestone 57 (Row 11 / C7)
**Target**: Watcher Adaptive Cadence & Export Duration  
**Active Branch**: `perf/watcher-cadence`  
**Mode**: Strictly READ-ONLY Verification

---

## 1. Independent Gate Re-Derivation

### 1.1 `DebounceController` Adaptive Settle Window Behavior
- **Method**: Isolated Python harness instantiating `DebounceController(settle_window=2.0, max_delay=10.0)`, testing expansion via `update_settle_window(4.5)` and `update_settle_window(8.0)` (scaling `max_delay` to 16.0s), and clamping lower-bound to `base_settle_window` upon `update_settle_window(0.5)`.
- **Command**:
  ```python
  from scripts.watch_telemetry import DebounceController
  dc = DebounceController(settle_window=2.0, max_delay=10.0)
  dc.update_settle_window(4.5)
  assert dc.settle_window == 4.5
  dc.update_settle_window(8.0)
  assert dc.settle_window == 8.0 and dc.max_delay == 16.0
  dc.update_settle_window(0.5)
  assert dc.settle_window == 2.0 and dc.max_delay == 16.0
  ```
- **Result**: **PASS** (Correctly adapts up to measured export duration, dynamically doubles `max_delay` if needed, and never drops below `base_settle_window`).

### 1.2 Presence of `"export took"` Logging in `scripts/watch_telemetry.py`
- **Method**: Grep for exact pattern `"export took"` in `scripts/watch_telemetry.py`.
- **Occurrences**:
  - Line 234: `print(f"[*] Initial export complete: export took {duration:.2f}s (adaptive settle window: {debounce.settle_window:.2f}s)")`
  - Line 236: `print(f"[*] Initial export skipped: export took {duration:.2f}s")`
  - Line 297: `print(f"[*] Export complete: export took {duration:.2f}s (adaptive settle window: {debounce.settle_window:.2f}s)")`
  - Line 299: `print(f"[*] Export skipped: export took {duration:.2f}s")`
- **Result**: **PASS** (4 occurrences covering all initial and subsequent export outcomes).

### 1.3 `export_seconds` Presence in `meta.json` & Determinism Clamp
- **Method**: Isolated executions of `scripts/export_dashboard.py` in fresh temp directories:
  - **Case A (Live / Wall-clock)**: No reference time passed.
    - Verified `'export_seconds' in meta` and `isinstance(meta['export_seconds'], (int, float))` and `meta['export_seconds'] >= 0.0`.
    - Measured: `12.44`s.
  - **Case B (Deterministic / Reference Time)**: Passed `--reference-time 2026-09-05T14:30:00Z`.
    - Verified `meta['export_seconds'] == 0.0`.
- **Result**: **PASS**

### 1.4 ADR-004 Fixture Determinism
- **Method**: Executed `scripts/export_dashboard.py --antigravity-dir tests/fixtures/antigravity --no-live-quota --reference-time 2026-09-05T14:30:00Z` twice into independent temporary directories and compared binary outputs.
- **Files Verified**:
  - `data.json`: 265,171 bytes (100% byte-identical)
  - `data.js`: 159,753 bytes (100% byte-identical)
  - `meta.json`: 879 bytes (100% byte-identical)
- **Result**: **PASS**

---

## 2. Test Suite Execution

| Test Suite | Command | Result | Details |
|---|---|---|---|
| **VDONE Gates** | `python3 -m unittest tests.test_vdone_gates` | **PASS** | Ran 4 tests in 52.240s (`OK`) |
| **Docs Integrity** | `python3 -m unittest tests.test_docs_integrity` | **PASS** | Ran 10 tests in 0.058s (`OK`) |
| **Model Roster Integrity** | `python3 -m unittest tests.test_model_roster_integrity` | **PASS** | Ran 7 tests in 0.042s (`OK`) |
| **Full Python Suite** | `SKIP_PLAYWRIGHT=1 python3 -m unittest discover -s tests -p 'test_*.py'` | **PASS** | Ran 259 tests in 69.199s (`OK (skipped=1)`) |

---

## 3. Playwright E2E Suite Execution

- **Command**: `npx playwright test`
- **Result**: **PASS**
- **Summary**: `34 passed (1.7m)` across all views, theme variations, pagination tests, truncation accordions, and visual proof suites.

---

## 4. Operational Health Check

- **Command**: `python3 scripts/ops_check.py`
- **Output**:
  ```text
  [OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 40052) | verified: 2026-09-20T16:46:32+01:00
  ```
- **Result**: **PASS** (Export operational, watcher LaunchAgent daemon running/registered, menubar running).

---

## 5. Working Tree Cleanliness

- **Command**: `git status --short`
- **Untracked / Scratch Files**: None (`0` untracked files). All modified files are strictly within Milestone 57 scope.

---

## 🏆 Overall Verdict: PASS
```

## Closing report
```
Merged:   M57 · v2.15.0 · Watcher adaptive cadence, export took logging & export_seconds in meta
Open now: - **Row 13 (C9/C10)**: Sanitize Swift repo path literal, replace pgrep with watcher heartbeat (`fix/menubar-hygiene`) [P2]
Next slice will touch: menubar/AntigravityTokenMonitor/StatusItemController.swift, scripts/watch_telemetry.py
Needs owner: nothing
Freeze:   lifted
```
