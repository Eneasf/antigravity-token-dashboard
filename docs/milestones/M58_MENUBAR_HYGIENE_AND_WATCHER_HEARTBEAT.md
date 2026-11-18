# M58 · Menu Bar Hygiene & Watcher Heartbeat · 2026-09-20 · v2.16.0

## Why
The macOS Menu Bar companion (`AntigravityBar`) previously spawned `/usr/bin/pgrep` every 5 seconds and on every filesystem event to monitor watcher process health, violating the 0.0% idle CPU invariant. Furthermore, a hardcoded personal repository path literal was compiled into the Swift app fallback. Per Audit 2026-09-19 Row 13 (C9/C10) and ADR-072, `pgrep` is replaced by an event-driven 10s watcher heartbeat timestamp (`watcher: {pid, heartbeat_utc}`) in the status hook, and repo path resolution reads `dashboard_path`, `ANTIGRAVITY_DASHBOARD_REPO`, or falls back cleanly to the user home.

## What changed
- `macos/AntigravityBar/Sources/AntigravityBar/StatusModel.swift`: Added `WatcherInfo` struct `{pid, heartbeat_utc}` and added `watcher` property to `StatusModel`.
- `macos/AntigravityBar/Sources/AntigravityBar/StatusStore.swift`: Completely removed `/usr/bin/pgrep` process execution; replaced with ISO 8601 heartbeat evaluation (alive if <= 30s); dropped hardcoded private path fallback.
- `scripts/watch_telemetry.py`: Added `update_watcher_heartbeat` to atomically write `{pid, heartbeat_utc}` on startup, every 10s in the watch loop, and post-export.
- `scripts/export_dashboard.py`: Preserved and serialized `watcher` dictionary in `write_quota_status_file`.
- `scripts/publish_to_public.py`: Added private repository folder needles to forbidden needles check.
- `tests/test_sanitization.py`: Added `macos/` to audited directories and added regression gates for private workspace needles.
- `tests/test_quota_status_enrichment.py`: Added unit tests verifying preservation and serialization of `watcher` dictionary.
- `tests/test_watch_telemetry.py`: Added unit tests for atomic `update_watcher_heartbeat`.
- `tests/test_docs_integrity.py`: Added `2.16.0` to pre-tag version allowlist.
- `e2e/labels-and-defaults.spec.js`: Updated status badge regex to tolerate live `"Recovered (Cooldown)"` state.
- `docs/SYSTEM_DESIGN.md`: Documented watcher heartbeat cadence, zero-CPU monitoring, and `ANTIGRAVITY_DASHBOARD_REPO` contract.
- `docs/TELEMETRY_SPEC.md`: Documented §14 Executive Quota Status Hook Schema and §14.2 Watcher Heartbeat Schema.
- `docs/FINDINGS.md`, `docs/WEEKLY_QUOTA_EXHAUSTION_REPORT.md`, `docs/milestones/*`: Scrubbed occurrences of private folder typos.
- `package.json` & `pyproject.toml`: Bumped version to `2.16.0`.

## Decisions taken
| ADR | Title | Status | Summary | Doc |
|---|---|---|---|---|
| ADR-072 | Menubar Path Sanitization & Watcher Heartbeat | Adopted | Sanitize Swift path literal via status hook/env; replace pgrep with 10s watcher heartbeat. | [doc](milestones/M58_MENUBAR_HYGIENE_AND_WATCHER_HEARTBEAT.md) |

## Gates & proofs
- **B1 (StatusStore pgrep removal)**: `grep -c "pgrep" macos/AntigravityBar/Sources/AntigravityBar/StatusStore.swift` returned `0` (exit 0).
- **B2 (StatusStore path literal drop)**: Status store verified free of hardcoded repository path literal (`grep` returned 0, exit 0).
- **B3 (Sanitization test suite)**: `python3 -m unittest tests.test_sanitization` passed (Ran 7 tests in 0.963s, OK).
- **B4 (Watcher heartbeat hook schema)**: `~/.antigravity_quota_status.json` carries `watcher.heartbeat_utc` and `watcher.pid` (exit 0).
- **B5 (Watch telemetry test suite)**: `python3 -m unittest tests.test_watch_telemetry` passed (Ran 14 tests in 1.144s, OK).
- **B6 (Quota status enrichment suite)**: `python3 -m unittest tests.test_quota_status_enrichment` passed (Ran 5 tests in 0.012s, OK).
- **B7 (Menu bar packaging test suite)**: `python3 -m unittest tests.test_menubar_packaging` passed (Ran 3 tests in 0.344s, OK).
- **C9 Independent Gate**: Sanitization check returned 0 matches across repository (exit 1).

## Ops check
```
[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 40052) | verified: 2026-09-20T17:23:38+01:00
```

## Screenshots
N/A (backend daemon & native companion menu bar hygiene milestone; no web UI layout changes).

## Verifier report
```markdown
# Independent Verification Report: Milestone 58 (Second Pass)
**Role**: Read-Only Independent Verifier  
**Branch**: `fix/menubar-hygiene`  
**Working Tree Status**: Clean (0 untracked files, no secret leaks, strictly read-only execution)  
**Overall Verdict**: **PASS**

---

### Section 1: VDONE Acceptance Gates Verification

| Gate | Description | Command | Measured Output | Verdict |
|---|---|---|---|---|
| **A1** | Full Unit Suite | `SKIP_PLAYWRIGHT=1 python3 -m unittest discover -s tests -p 'test_*.py'` | `Ran 265 tests in 41.808s; OK (skipped=1)` (< 45s) | **PASS** |
| **A2** | Docs Integrity | `python3 -m unittest tests.test_docs_integrity` | `Ran 10 tests in 0.060s; OK` | **PASS** |
| **A3** | Model Roster Integrity | `python3 -m unittest tests.test_model_roster_integrity` | `Ran 7 tests in 0.044s; OK` | **PASS** |
| **A4** | No Stale Numbers | `python3 -m unittest tests.test_docs_integrity -k test_stale_numbers` | `Ran 1 test in 0.017s; OK` | **PASS** |
| **A5** | Fixture Determinism | `python3 -c "import tempfile, subprocess, pathlib, shutil; ... assert f1.read_bytes() == f2.read_bytes() and len(f1.read_bytes()) > 0; ..."` | Byte-identical output verified (exit code 0) | **PASS** |
| **B1** | StatusStore pgrep removal | `grep -c "pgrep" macos/AntigravityBar/Sources/AntigravityBar/StatusStore.swift` | `0` (Expected: 0) | **PASS** |
| **B2** | StatusStore path literal drop | `grep -c "Gemi""nu" macos/AntigravityBar/Sources/AntigravityBar/StatusStore.swift` | `0` (Expected: 0) | **PASS** |
| **B3** | Sanitization Test Suite | `python3 -m unittest tests.test_sanitization` | `Ran 7 tests in 0.963s; OK` | **PASS** |
| **B4** | Watcher Heartbeat Hook Schema | `python3 -c "... assert 'watcher' in d and 'heartbeat_utc' in d['watcher'] and 'pid' in d['watcher']"` | Validated `watcher`, `heartbeat_utc`, and `pid` in `~/.antigravity_quota_status.json` (exit code 0) | **PASS** |
| **B5** | Watch Telemetry Test Suite | `python3 -m unittest tests.test_watch_telemetry` | `Ran 14 tests in 1.144s; OK` | **PASS** |
| **B6** | Quota Status Enrichment Suite | `python3 -m unittest tests.test_quota_status_enrichment` | `Ran 5 tests in 0.012s; OK` | **PASS** |
| **B7** | Menu Bar Packaging Test Suite | `python3 -m unittest tests.test_menubar_packaging` | `Ran 3 tests in 0.344s; OK` | **PASS** |
| **VDONE Meta** | VDONE Gates Orchestration | `python3 -m unittest tests.test_vdone_gates` | `Ran 4 tests in 23.226s; OK` | **PASS** |

---

### Section 2: Gate C9 Independent Verification

- **Command**: `git grep -i 'Gemi''nu' -- ':!scripts/publish_to_public.py' ':!tests/test_sanitization.py' ':!docs/AUDIT_*'`
- **Result**: Exit code 1 (0 matches found across entire repository outside permitted exemptions).
- **Verdict**: **PASS**

---

### Section 3: Swift Compilation Verification

- **Command**: `swift build --package-path macos/AntigravityBar`
- **Result**: `Build complete! (0.26s)` (Exit code 0, 0 compiler warnings/errors).
- **Verdict**: **PASS**

---

### Section 4: Playwright End-to-End Suite

- **Command**: `npx playwright test`
- **Result**: `34 passed (1.7m)` (Exit code 0).
- **Verdict**: **PASS**

---

### Section 5: Hygiene, Secrets & Working Tree Cleanliness

- **Untracked files check** (`git status --porcelain`): 0 untracked files (`??` count is 0).
- **Secret leak check** (`git diff | grep -iE 'api_key|apikey|secret|password|bearer|authorization'`): No leaked secrets or tokens found.
- **Repository integrity**: Zero modifications made by this verification subagent; strictly read-only execution maintained.
- **Verdict**: **PASS**

---

### Overall Milestone 58 Verification Summary

Every acceptance gate (A1-A5, B1-B7, VDONE Meta, C9 Gate, Swift compilation, and Playwright E2E) has been independently re-derived, executed, and verified.

**FINAL VERDICT: PASS**
```

## Closing report
```
Merged:   M58 · v2.16.0 · Sanitize Swift repo path literal & watcher heartbeat (Row 13: C9/C10)
Open now: - **Row 14 (U5/U6)**: Accessibility baseline (roles, SVG titles, captions), 2-decimal money, single formatter (`ui/a11y-baseline`) [P2]
Next slice will touch: dashboard/index.html, dashboard/styles.css, dashboard/js/*.js, tests/
Needs owner: nothing
Freeze:   lifted
```
