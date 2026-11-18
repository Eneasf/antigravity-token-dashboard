# Milestone 86: Menu Bar Epoch Number Indicator & Two-Tier Fast Ticker Exporter

**Date**: 2026-09-30
**Scope**: Row 1 from `docs/HANDOVER.md` §4 Open Work
**Branch**: `feat/m86-menubar-epoch-and-two-tier-exporter`
**Verdict**: **PASS**

---

## 1. Overview & Context

This milestone delivers the Two-Tier Fast Ticker Exporter and the dynamic macOS Menu Bar Epoch Number indicator:
- **macOS Menu Bar Topper (`macos/AntigravityBar/`)**:
  - Replaced legacy blunt warning markers (`🔴` / `⚠️`) with a dynamic Epoch number badge (`E1`..`E5`).
  - Implemented color grading:
    - Epoch 1 & 2: Green (`#34D399` / `sRGB(52/255, 211/255, 153/255)`)
    - Epoch 3: Amber/Orange (`#FBBF24` / `sRGB(251/255, 191/255, 36/255)`)
    - Epoch 4+: Red (`#EF4444` / `sRGB(239/255, 68/255, 68/255)`)
  - Updated `StatusModel.swift` to decode `compaction_epoch` from `~/.antigravity_quota_status.json`.
  - Re-packaged release binary (`dist/AntigravityBar.app`) via `python3 scripts/build_menubar.py` and restarted via `python3 scripts/setup_menubar.py restart`.
- **Two-Tier Exporter (`scripts/export_dashboard.py` & `scripts/watch_telemetry.py`)**:
  - Engineered Fast Tier exporter (`export_fast_tier`): executes in <20ms (<7ms measured) on active session WAL changes, writing strictly `dashboard/meta.js`, `dashboard/meta.json`, and `~/.antigravity_quota_status.json` without touching `dashboard/data.js`.
  - Decoupled Heavy Tier rollup in `scripts/watch_telemetry.py`: debounced to 30–60s settle window for complete 519-session aggregation and writing `dashboard/data.js` (32.5 MB).
  - Added CLI flags `--fast-tier` / `--fast` to `export_dashboard.py` and `--no-fast-tier` to `watch_telemetry.py`.

---

## 2. Changes Implemented

- **`macos/AntigravityBar/Sources/AntigravityBar/StatusModel.swift`**:
  - Added `compaction_epoch: Int?` field to `QuotaStatusPayload`.
- **`macos/AntigravityBar/Sources/AntigravityBar/StatusBarController.swift`**:
  - Replaced legacy `🔴` / `⚠️` badges with dynamic `E\(epoch)  ` badge in `updateTitle()`.
  - Applied color grading using NSAttributedString with `#34D399` (E1/E2), `#FBBF24` (E3), and `#EF4444` (E4+).
- **`scripts/export_dashboard.py`**:
  - Implemented `export_fast_tier()` function that reads single active session metadata, turns, and compaction epoch in <7ms, updates ticker metrics, and writes `meta.js`/`status.json`.
  - Updated `write_quota_status_file` to record `compaction_epoch`.
  - Added `--fast-tier` and `--fast` flags to CLI argument parser.
- **`scripts/watch_telemetry.py`**:
  - Decoupled Fast Tier invocation (<20ms) inside snapshot change loop on `.db-wal` modifications.
  - Extended Heavy Tier debounce window to 30s settle and 60s max delay.
  - Added `--no-fast-tier` CLI argument.
- **`tests/test_two_tier_exporter.py`**:
  - Created 6 unit and integration tests covering latency (<20ms), filesystem isolation (omitting `data.js`), epoch detection (E1 vs E2), CLI flags, watcher decoupling, and Swift source badge invariants.
- **`docs/REPO_MAP.md`**:
  - Registered `tests/test_two_tier_exporter.py`.

---

## 3. Acceptance Gates

| Gate # | Description | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :--- | :--- |
| B1 | Menubar epoch badge & color grading | `python3 -c "import pathlib; src = pathlib.Path('macos/AntigravityBar/Sources/AntigravityBar/StatusBarController.swift').read_text(); title_src = src.split('func updateTitle()')[1].split('func handleStatusBarClick')[0]; assert '🔴' not in title_src and '⚠️' not in title_src and r'E\(epoch)' in title_src; print('OK')"` | `OK` | PASS |
| B2 | Fast Tier export under 20ms | `python3 -m unittest tests.test_two_tier_exporter.TestTwoTierExporter.test_fast_tier_export_under_20ms` | `OK` | PASS (measured 6.3ms) |
| B3 | Two-Tier watcher decoupling | `python3 -m unittest tests.test_two_tier_exporter.TestTwoTierExporter.test_watcher_two_tier_decoupling` | `OK` | PASS |
| B4 | Menubar binary compiled & valid | `python3 -c "import pathlib; p = pathlib.Path('dist/AntigravityBar.app/Contents/MacOS/AntigravityBar'); assert p.exists() and p.stat().st_size > 0; print('OK')"` | `OK` | PASS |
| B5 | Two-Tier exporter test suite | `python3 -m unittest tests.test_two_tier_exporter` | `OK` | PASS (6 tests in 0.23s) |
| A1 | Full unit test suite | `python3 -m unittest discover -s tests` | `428 passed, < 90s` | PASS (428 passed in 53.7s) |
| A2 | Docs integrity | `python3 -m unittest tests.test_docs_integrity` | `OK` | PASS |
| QG | Full quality gate | `git diff --check && python3 -m unittest tests/test_docs_integrity.py && python3 scripts/build_demo_showcase.py && npx playwright test e2e/dashboard-boot.spec.js` | `OK` | PASS |
