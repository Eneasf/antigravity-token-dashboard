# M61 · Mobile Viewport Polish, Ticker Clipping Fix & Table Scroll Wrappers · 2026-09-21 · v2.19.0

## Why
Under Audit 2026-09-19 Row 16 (U8), mobile viewports (<=768px and 375px) exhibited two critical usability and layout defects:
1. The live token ticker HUD (`.token-ticker-hud` inside `.workspace-command-strip`) was aligned via flexbox in a way that caused overflow chips on narrow screens to clip off-screen to the left where users could not see or scroll to them (`left < 0`).
2. The 11 data tables across the dashboard could overflow horizontally without consistent, accessible container boundaries or visual cues indicating that additional table columns extended off-screen.

Per ADR-075, this milestone eliminates ticker left-clipping on viewports <=768px by aligning to `flex-start` and wrapping items responsively, wraps all 11 data tables in dedicated `.table-scroll-container` and `.table-scroll-wrapper` elements with native smooth scrolling (`overflow-x: auto; -webkit-overflow-scrolling: touch;`), adds right-edge gradient fade indicator masks (`.table-scroll-fade`) that reveal horizontal scrollability and automatically fade out when scrolled to the end, and establishes delegated passive scroll event listening to toggle `.is-scrolled-end` states with zero layout thrash.

## What changed
- `dashboard/styles.css`: Added responsive media query (<=768px) switching `.workspace-command-strip` to `justify-content: flex-start !important; overflow-x: auto; -webkit-overflow-scrolling: touch;`; created `.table-scroll-container` and `.table-scroll-wrapper` with relative positioning, horizontal overflow, smooth momentum scrolling; created `.table-scroll-fade` gradient masks indicating scrollable overflow with CSS transition on `.is-scrolled-end`.
- `dashboard/index.html`: Wrapped all 11 data tables in `.table-scroll-container` and `.table-scroll-wrapper` containers accompanied by `.table-scroll-fade` elements across Sessions, Projects, Swarms, Billing, Tools, and Plan tabs.
- `dashboard/js/core.js`: Added delegated capture-phase scroll event listener attached to document to dynamically toggle `.is-scrolled-end` class when scrolled to the maximum horizontal offset; implemented `initScrollFades()` called on boot, tab switch, render, and window resize.
- `tests/test_mobile_pass_and_scroll_wrappers.py`: Authored comprehensive unit and styling test suite verifying ticker alignment, table wrapper markup, fade indicator presence, and delegated scroll interaction logic.
- `e2e/mobile-pass.spec.js`: Authored Playwright E2E browser test verifying mobile viewports (375x812), horizontal table scrollability, absence of ticker left-clipping (`left >= 0`), and fade mask behavior.
- `tests/test_docs_integrity.py`: Added `2.19.0` to version whitelist.
- `docs/REPO_MAP.md`: Documented new test modules `tests/test_mobile_pass_and_scroll_wrappers.py` and `e2e/mobile-pass.spec.js`.
- `package.json` & `pyproject.toml`: Bumped version to `2.19.0`.
- `CHANGELOG.md`: Added release notes for v2.19.0 (Milestone 61).
- `docs/HANDOVER.md`: Documented ADR-075, indexed M61, removed Row 16 from Open Work, and moved Row 16 to Closed This Quarter.

## Decisions taken
| ADR | Title | Status | Summary | Doc |
|---|---|---|---|---|
| ADR-075 | Mobile Viewport Polish, Ticker Clipping Fix & Table Scroll Wrappers | Adopted | Eliminate ticker left clipping via flex-start at <=768px; add overflow-x wrappers with right-edge fade across all tables. | [doc](milestones/M61_MOBILE_PASS_AND_SCROLL_WRAPPERS.md) |

## Gates & proofs
- **B1 (Unit suite M61)**: `python3 -m unittest discover -s tests -p 'test_mobile_pass_and_scroll_wrappers.py'` -> Ran 3 tests in 0.002s (PASS).
- **B2 (Table scroll wrappers)**: `python3 -c "h=open('dashboard/index.html').read(); assert h.count('table-scroll-wrapper') >= 10 and h.count('table-scroll-fade') >= 10; print('OK')"` -> 11 wrappers & 11 fades detected (PASS).
- **B3 (Mobile CSS styling)**: `python3 -c "s=open('dashboard/styles.css').read(); assert 'table-scroll-wrapper' in s and 'table-scroll-fade' in s and '@media (max-width: 768px)' in s and 'justify-content: flex-start' in s; print('OK')"` -> Exit code 0 (PASS).
- **B4 (Table scroll interaction)**: `python3 -m unittest tests.test_mobile_pass_and_scroll_wrappers -k test_scroll_interaction` -> Ran 1 test in 0.001s (PASS).
- **B5 (Zero mobile left clipping)**: `python3 -c "s=open('dashboard/styles.css').read(); assert '@media (max-width: 768px)' in s and 'overflow-x: auto' in s; print('OK')"` -> Exit code 0 (PASS).

## Ops check
```
[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 614) | verified: 2026-09-21T10:42:17+01:00
```

## Screenshots
- Desktop (1440x900): `docs/milestones/screenshots/m61-desktop-after-1440x900.png`
- Mobile (375x812): `docs/milestones/screenshots/m61-mobile-after-375x812.png`

## Verifier report
```markdown
# Milestone 61 Independent Verification Report: Mobile Viewport Polish, Ticker Clipping Fix & Table Scroll Wrappers

**Milestone**: M61 (Row 16 / U8)  
**Target Release**: v2.19.0  
**Active Branch**: `main`  
**Execution Timestamp**: 2026-09-21T10:41:04+01:00  
**Verifier Role**: Independent Verification Agent (Strict Read-Only)  
**Overall Verdict**: **PASS (100% Verified, Zero Defects)**

---

## 1. Executive Summary

Milestone 61 (Row 16 / U8) addresses critical mobile viewport defects identified in the 2026-09-19 Audit:
1. **Live Token Ticker Clipping**: On mobile screens (<=768px, specifically 375x812), the live ticker was centered with `justify-content: center`, causing overflow chips to clip off the left edge (`left < 0`).
2. **Table Horizontal Containment**: 11 data tables lacked uniform horizontal scroll containers and gradient fade cues indicating overflow.

All planned changes in `dashboard/styles.css`, `dashboard/index.html`, and `dashboard/js/core.js` have been thoroughly inspected, executed, and independently verified against:
- All 5 Always-on acceptance gates (§A1–A5)
- All 5 Milestone-specific acceptance gates (§B1–B5)
- Automated gate runner (`tests.test_vdone_gates`)
- Playwright E2E test suite (`e2e/mobile-pass.spec.js`) across mobile (375x812) and desktop (1440x900)
- Browser interaction and layout audits across all 6 application views
- Production environment daemon operations check (`scripts/ops_check.py`)

Every gate passed cleanly on the first invocation with zero regressions.

---

## 2. Gate-by-Gate Verification Matrix

| Gate ID | Description | Executed CHECK Command | Expected Output | Measured Output | Status |
|---|---|---|---|---|---|
| **A1** | Full Unit Suite | `python3 -m unittest discover -s tests -p 'test_*.py'` | `OK, < 60 s` | Ran 284 tests in 38.058s (`OK`) | **PASS** |
| **A2** | Documentation Integrity | `python3 -m unittest tests.test_docs_integrity` | `OK` | Ran 11 tests in 0.566s (`OK`) | **PASS** |
| **A3** | Model Roster Integrity | `python3 -m unittest tests.test_model_roster_integrity` | `OK` | Ran 7 tests in 0.039s (`OK`) | **PASS** |
| **A4** | Zero Stale Numbers | `python3 -m unittest tests.test_docs_integrity -k test_stale_numbers` | `OK` | Ran 1 test in 0.022s (`OK`) | **PASS** |
| **A5** | Fixture Determinism | Run fixture export twice to temp dirs, verify byte-identical `data.json` | `OK` | Returncode 0, `OK` (Byte-identical output) | **PASS** |
| **B1** | M61 Unit Suite | `python3 -m unittest discover -s tests -p 'test_mobile_pass_and_scroll_wrappers.py'` | `OK` | Ran 3 tests in 0.002s (`OK`) | **PASS** |
| **B2** | Table Scroll Wrappers Markup | `python3 -c "h=open('dashboard/index.html').read(); assert h.count('table-scroll-wrapper') >= 10 and h.count('table-scroll-fade') >= 10; print('OK')"` | `OK` | `OK` (11 wrappers, 11 fades detected) | **PASS** |
| **B3** | Mobile CSS Styling | `python3 -c "s=open('dashboard/styles.css').read(); assert 'table-scroll-wrapper' in s and 'table-scroll-fade' in s and '@media (max-width: 768px)' in s and 'justify-content: flex-start' in s; print('OK')"` | `OK` | `OK` | **PASS** |
| **B4** | Table Scroll Interaction | `python3 -m unittest tests.test_mobile_pass_and_scroll_wrappers -k test_scroll_interaction` | `OK` | Ran 1 test in 0.001s (`OK`) | **PASS** |
| **B5** | Zero Mobile Left Clipping | `python3 -c "s=open('dashboard/styles.css').read(); assert '@media (max-width: 768px)' in s and 'overflow-x: auto' in s; print('OK')"` | `OK` | `OK` | **PASS** |
| **Runner** | VDONE Gate Runner | `python3 -m unittest tests.test_vdone_gates` | `OK` | Ran 4 tests in 18.885s (`OK`) | **PASS** |

---

## 3. Playwright E2E Test Suite Results

**Command**: `npx playwright test e2e/mobile-pass.spec.js`  
**Execution Metrics**: 8 tests passed in 17.3s (0 failed, 0 skipped, 0 retried)

### Individual Test Breakdown:
1. `at 375x812 viewport: #token-ticker-hud is visible with bounding box left >= 0` — **PASS** (1.8s)
2. `at 375x812 viewport on tab 'Now': all visible elements have left >= -0.5` — **PASS** (2.1s)
3. `at 375x812 viewport on tab 'Sessions': all visible elements have left >= -0.5` — **PASS** (2.0s)
4. `at 375x812 viewport on tab 'Projects': all visible elements have left >= -0.5` — **PASS** (1.9s)
5. `at 375x812 viewport on tab 'Swarms': all visible elements have left >= -0.5` — **PASS** (2.1s)
6. `at 375x812 viewport on tab 'Billing': all visible elements have left >= -0.5` — **PASS** (1.9s)
7. `at 375x812 viewport on tab 'Plan': all visible elements have left >= -0.5` — **PASS** (1.8s)
8. `table scroll wrapper horizontal scroll updates is-scrolled-end class on container` — **PASS** (1.7s)

---

## 4. UI Interaction & Layout Hand-Testing Audit

### A. Mobile Viewport (375x812)

1. **Token Ticker HUD Alignment & Left Boundary**:
   - `boundingBox`: `{ x: 24, y: 108.39, width: 327, height: 34 }`
   - `left` coordinate: `24px` (satisfies `left >= 0`; zero left clipping, model names unclipped).
   - Parent `.workspace-command-strip` styling:
     - `display`: `flex`
     - `justify-content`: `flex-start`
     - `overflow-x`: `auto`

2. **Table Scroll Wrapper Audit (11 Tables Enclosed)**:
   - `models-table`: Wrapper: **Yes**, Container: **Yes**, Fade: **Yes**
   - `recent-sessions-table`: Wrapper: **Yes**, Container: **Yes**, Fade: **Yes**
   - `conversations-table`: Wrapper: **Yes**, Container: **Yes**, Fade: **Yes**
   - `turns-table`: Wrapper: **Yes**, Container: **Yes**, Fade: **Yes**
   - `projects-table`: Wrapper: **Yes**, Container: **Yes**, Fade: **Yes**
   - `tools-table`: Wrapper: **Yes**, Container: **Yes**, Fade: **Yes**
   - `weekly-trends-table`: Wrapper: **Yes**, Container: **Yes**, Fade: **Yes**
   - `reconciliation-table`: Wrapper: **Yes**, Container: **Yes**, Fade: **Yes**
   - `rate-history-table`: Wrapper: **Yes**, Container: **Yes**, Fade: **Yes**
   - `.sim-tier-table`: Wrapper: **Yes**, Container: **Yes**, Fade: **Yes**
   - `plan-history-modal-table`: Wrapper: **Yes**, Container: **Yes**, Fade: **Yes**

3. **Horizontal Scroll Interaction & Dynamic Gradient Mask**:
   - Tested on `#models-table` (`scrollWidth: 725px`, `clientWidth: 277px`, `maxScroll: 448px`):
     - At `scrollLeft = 0`: Container class `['table-scroll-container']`, fade opacity: `0.85`.
     - At `scrollLeft = 448px` (scrolled to end): Container class `['table-scroll-container', 'is-scrolled-end']`, fade opacity: `0`.
     - Returned to `scrollLeft = 0`: Container class `['table-scroll-container']`, fade opacity: `0.85`.
   - Verified that `.is-scrolled-end` smoothly transitions gradient opacity to 0 when table reaches the right boundary.

4. **Negative Left Bounding Rect Audit Across All 6 Views**:
   - Tab **Now** (`view-now`): `0` violations
   - Tab **Sessions** (`view-sessions`): `0` violations
   - Tab **Projects** (`view-projects`): `0` violations
   - Tab **Swarms** (`view-swarms`): `0` violations
   - Tab **Billing** (`view-billing`): `0` violations
   - Tab **Plan** (`view-plan`): `0` violations
   - Total elements with `left < -0.5`: **0 across entire application**.

### B. Desktop Viewport (1440x900)
- Ticker HUD in top command strip: `{ x: 830.64, y: 96, width: 585.36, height: 36 }`, visible and correctly aligned.
- Dock tab navigation transitions tested across all 6 tabs (`#dock-tab-now`, `#dock-tab-sessions`, `#dock-tab-projects`, `#dock-tab-swarms`, `#dock-tab-billing`, `#dock-tab-plan`); all activate and render cleanly.
- Visual inspection confirms full responsive fidelity with no side-effects from mobile CSS rules.

### C. Screenshot Proofs Captured
- Desktop: `docs/milestones/screenshots/m61-desktop-after-1440x900.png` (895,235 bytes)
- Mobile: `docs/milestones/screenshots/m61-mobile-after-375x812.png` (344,924 bytes)

---

## 5. Live Operations Check

```bash
$ python3 scripts/ops_check.py
[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 614) | verified: 2026-09-21T10:41:04+01:00
```
- Telemetry export: Functional
- Background launchd service: `RUNNING / REGISTERED`
- Menubar applet: `RUNNING (PID: 614)`

---

## 6. Closing Assessment

Milestone 61 (Row 16 / U8) has satisfied all functional, visual, accessibility, and documentation requirements.
All 10 acceptance gates in `VDONE.md` pass with zero failures. The implementation is deterministic, side-effect free, and fully verified.

**Verdict: READY FOR MERGE & RELEASE (v2.19.0)**
```

## Closing report
```
Merged:   M61 · v2.19.0 · Mobile viewport polish, ticker clipping fix & table scroll wrappers (Row 16: U8)
Open now: - **Row 17 (C11)**: Aggregator modularization refactor (reopen ADR-044) (`refactor/aggregator-modules`) [P3]
Next slice will touch: src/aggregator.py, src/aggregator_*, tests/test_aggregator.py
Needs owner: nothing
Freeze:   lifted
```
