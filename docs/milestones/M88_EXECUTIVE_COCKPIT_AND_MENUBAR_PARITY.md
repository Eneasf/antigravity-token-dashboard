# Milestone 88: Dashboard Executive Cockpit & Mac Menu Bar Parity

**Date**: 2026-10-02
**Scope**: Dashboard Executive Cockpit, False-Alarm Truncation Elimination & Menu Bar Parity (ADR-085)
**Branch**: `feat/m88-dashboard-executive-cockpit`
**Verdict**: **PASS**

---

## 1. Overview & Context

This milestone establishes complete visual and functional parity between the web analytics dashboard (`dashboard/index.html`) and the native macOS menu bar app (`AntigravityBar`), while eliminating distracting false-alarm context truncation alerts on active sessions:
- **False-Alarm Session Truncation Elimination**:
  - Previously, `checkDegradedSessions` in `dashboard/js/sessions.js` evaluated `convos[0]` to display the red top warning banner on the Now tab. When the most recently modified conversation in the IDE was a completed historical session that reached context compaction, the Now tab displayed a false-alarm warning even if the current active session was healthy.
  - Refactored `checkDegradedSessions(convos, liveCurrentSession)` to evaluate strictly the live active session from `data.current_session`. Completed historical sessions with degraded context are quarantined strictly to the Sessions tab audit drawer (`window.__lastDegradedSessions`).
- **High-Contrast Executive Hero Card**:
  - Implemented the Executive Hero Card in `dashboard/index.html`, `dashboard/js/now-burst.js`, and `dashboard/styles.css` mirroring the macOS `AntigravityBar` popover visual hierarchy:
    - **Header**: Plan Name (`exec-plan-name`, e.g. "Google AI Ultra") and Dynamic Status Badge (`exec-status-badge`, `SAFE`, `CAUTION`, `CRITICAL`).
    - **Weekly Runway**: Large percentage, progress bar (`exec-weekly-bar`), reset deadline countdown (`exec-weekly-countdown`), and pacing buffer verdict (`exec-weekly-verdict`).
    - **5-Hour Limit**: Progress bar (`exec-5h-bar`), used tokens (`exec-5h-tokens`), and plain-English recovery time forecast (`exec-5h-forecast`).
    - **Live Turn & Velocity**: Burn rate pill (`exec-burn-rate`), delta pill (`exec-delta-val`), active model & cache % (`exec-active-model`, `exec-active-cache`), and 5h burst headroom (`exec-burst-headroom`).
    - **Secondary Track & Credit Bank Footer**: Claude/GPT status (`exec-claude-status`), Credit Bank balance (`exec-credit-balance`), and active workspace & branch context (`exec-active-context`).
- **Demoted Dense Telemetry Drawer**:
  - Wrapped the Sacred Dual Benchmark Bar (`#runway-dual-bar`), Bayesian BVI shrinkage formulas, and dense KPI grid below the Executive Hero Card into a collapsible `<details class="dense-telemetry-drawer" id="dense-telemetry-drawer">` sub-drawer labeled "Detailed Pace & Diagnostics".
  - Preserved 100% of existing DOM elements, IDs, and controller hooks for complete backward compatibility.
- **Byte-Deterministic Export Parity**:
  - Extracted `compute_current_session(payload, census)` in `scripts/export_dashboard.py` to ensure consistent 2D compaction and drift schema across `data.json`, `data.js`, and `~/.antigravity_quota_status.json`.
  - Updated synthetic showcase demo generation in `scripts/build_demo_showcase.py` and hermetic test baseline fixtures in `tests/fixtures/aggregator_baseline_data.json`.
- **Engineering & Accessibility Invariants**:
  - Zero inline `onclick=` handlers (ADR-064 event delegation).
  - Strict compliance with script line budgets (<800 lines per ADR-066; `now-burst.js` is 376 lines, `now.js` is 736 lines).
  - Zero Axe-core accessibility violations with light theme contrast calibrated to >7:1 and zero sub-11px font sizes.
  - Zero engineering jargon ("contamination", "spillover", "benchmark", "governor") in primary dashboard copy.

---

## 2. Changes Implemented

- **`scripts/export_dashboard.py`**:
  - Extracted `compute_current_session(payload, census)` returning canonical schema (`id`, `workspace_path`, `branch`, `model_name`, `tokens`, `threshold`, `ratio`, `severity`, `turns_count`, `active_window_turns`, `evicted_turns_count`, `last_turn_time`).
  - Attached `payload["current_session"]` to both `payload` and `payload_without_turns` before writing `data.json` and `data.js`.
  - Updated `write_quota_status_file` to use `compute_current_session`.
- **`scripts/build_demo_showcase.py`**:
  - Added synthetic `current_session` object with `severity: "safe"` matching canonical schema to `generate_synthetic_payload()`.
- **`tests/fixtures/aggregator_baseline_data.json`**:
  - Updated fixture with hermetic `current_session` schema to maintain Gate A5 fixture determinism.
- **`dashboard/js/sessions.js`**:
  - Updated `checkDegradedSessions(convos, liveCurrentSession)` to evaluate strictly `liveCurrentSession` / `data.current_session` for Now tab active session severity, quarantining historical sessions to `window.__lastDegradedSessions`.
  - Fixed `is_current` reference to check against `currentSession.id`.
- **`dashboard/js/core.js`**:
  - Passed `globalDashboardData && globalDashboardData.current_session` to `checkDegradedSessions`.
- **`dashboard/index.html`**:
  - Added `.executive-hero-card` section above `#dual-provider-quotas-section`.
  - Wrapped `#runway-dual-bar` and KPI grid into `<details class="dense-telemetry-drawer" id="dense-telemetry-drawer">` with `<summary class="dense-telemetry-summary">Detailed Pace & Diagnostics</summary>`.
- **`dashboard/styles.css`**:
  - Added styling for `.executive-hero-card`, `.exec-hero-header`, `.exec-weekly-metric`, `.exec-5h-metric`, `.exec-velocity-bar`, `.exec-footer-row`, and `.dense-telemetry-drawer`.
  - Calibrated light mode `.exec-delta-pill` and `.exec-status-badge` to `#064e3b` (>7:1 contrast) and ensured font sizes are `>= 0.75rem` (12px).
- **`dashboard/js/now-burst.js`**:
  - Implemented `renderExecutiveHero(data)` and `updateExecutiveHeroTicker(ticker)`, exporting them to `window`.
- **`dashboard/js/now.js`**:
  - Hooked `renderExecutiveHero(data)` inside `renderNowView(data)` and `updateExecutiveHeroTicker(ticker)` inside `updateTokenTicker(ticker)`.
- **`tests/test_dashboard_executive_cockpit.py`**:
  - Authored comprehensive test suite verifying schema parity, false-alarm isolation via Node mock DOM, DOM anchors, JS renderers, line budgets, and zero inline onclick.
- **`VDONE.md`**:
  - Registered gates B1–B5.

---

## 3. Acceptance Gates

| Gate # | Description | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :--- | :--- |
| B1 | Executive cockpit suite | `python3 -m unittest tests.test_dashboard_executive_cockpit` | `OK` | PASS (11 tests in 0.52s) |
| B2 | Degraded session isolation | `python3 -m unittest tests.test_dashboard_executive_cockpit.TestDegradedSessionFalseAlarmIsolation` | `OK` | PASS (2 tests in 0.12s) |
| B3 | Executive DOM & renderers | `python3 -m unittest tests.test_dashboard_executive_cockpit.TestExecutiveHeroCardDomAndRenderers` | `OK` | PASS (4 tests in 0.10s) |
| B4 | Status schema parity | `python3 -m unittest tests.test_dashboard_executive_cockpit.TestExecutiveSessionParity.test_schema_keys_parity` | `OK` | PASS |
| B5 | JS line budget compliance | `python3 -m unittest tests.test_dashboard_executive_cockpit.TestJsBudgetsAndIntegrity.test_script_line_budgets` | `OK` | PASS |
| A1 | Full unit test suite | `python3 -m unittest discover -s tests -p 'test_*.py'` | `468 passed, < 90s` | PASS (468 passed in 38.8s) |
| A2 | Docs integrity | `python3 -m unittest tests.test_docs_integrity` | `OK` | PASS |
| A5 | Fixture determinism | Gate A5 check | `OK` | PASS |
| Q1 | Headless dashboard boot | `npx playwright test e2e/dashboard-boot.spec.js` | `1 passed` | PASS |
| Q2 | Accessibility audit | `npx playwright test e2e/a11y.spec.js` | `0 violations` | PASS |
| Q3 | Plain header copy | `npx playwright test e2e/plain-header.spec.js` | `5 passed` | PASS |
| Q4 | Quality gate command | `$QUALITY_GATE_CMD` | `exit code 0` | PASS |
