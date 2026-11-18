# M59 · Accessibility Baseline & Formatter Unification · 2026-09-20 · v2.17.0

## Why
Under Audit 2026-09-19 Row 14 (U5/U6), the dashboard lacked accessibility fundamentals: screen readers could not interpret navigation tabs or data tables, interactive elements lacked keyboard `:focus-visible` styling, typography contained sub-11px font sizes, SVG icons lacked descriptive `<title>` attributes, currency figures used inconsistent decimal precisions, and token rate units were ambiguous. Per ADR-073, this milestone establishes a WCAG 2.1 AA accessibility baseline, unifies compact number formatting under a single canonical function, and standardizes currency display to 2 decimals outside the raw turns inspector.

## What changed
- `dashboard/index.html`: Added WAI-ARIA tab semantics (`role="tablist"`, `role="tab"`, `role="tabpanel"`), `role="progressbar"`, `<title>` tags to interactive SVG icons, and `<caption class="sr-only">` to all data tables.
- `dashboard/styles.css`: Standardized `:focus-visible` rings with `--focus-ring` token; raised base font floor to minimum 11px (`--font-xs: 0.6875rem`); added `.sr-only` utility class.
- `dashboard/js/core.js`: Unified compact number formatting under canonical `formatCompactNumber`; standardized 2-decimal currency formatting outside turns inspector; added accessible status glyphs.
- `dashboard/js/now.js`: Clarified live ticker rate unit to `tok/min` and applied canonical formatters.
- `e2e/a11y.spec.js`: Added Playwright + `@axe-core/playwright` accessibility automated test suite.
- `tests/test_a11y_baseline.py`: Added unit test suite for ARIA roles, table captions, focus styles, and currency formatting.
- `docs/HANDOVER.md`: Documented ADR-073, indexed M59, and moved Row 14 to Closed This Quarter.
- `CHANGELOG.md`: Added release notes for v2.17.0 (M59).

## Decisions taken
| ADR | Title | Status | Summary | Doc |
|---|---|---|---|---|
| ADR-073 | Accessibility Baseline, WCAG Contrast & Formatter Unification | Adopted | WAI-ARIA roles, SVG titles, sr-only table captions, :focus-visible outlines, single formatCompactNumber, and 2-decimal money. | [doc](milestones/M59_A11Y_BASELINE_AND_UNITS.md) |

## Gates & proofs
- **B1 (Single number formatter)**: `grep -cE 'function format(Compact|Tokens)' dashboard/js/*.js` returned `1`.
- **B2 (Ticker rate units)**: `grep -cE 'tok/min' dashboard/js/now.js` returned `> 0`.
- **B3 (Min font size baseline)**: Sub-11px font size regex check in `dashboard/styles.css` returned 0 matches.
- **B4 (Table captions presence)**: Every `<table>` in `dashboard/index.html` has a corresponding `<caption class="sr-only">`.
- **B5 (ARIA roles and attributes)**: `role="tablist"`, `role="tab"`, `role="tabpanel"`, and `role="progressbar"` verified in HTML.
- **B6 (Focus visible styles)**: `:focus-visible` ring rules confirmed in `dashboard/styles.css`.
- **B7 (Status badge glyph presence)**: Accessible indicator glyphs (`✓`, `!`, `×`) confirmed in UI markup/scripts.
- **B8 (A11y unit test suite)**: `python3 -m unittest tests.test_a11y_baseline` passed.

## Ops check
```
[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 72976) | verified: 2026-09-20T19:25:16+01:00
```

## Screenshots
- `docs/milestones/screenshots/m59-desktop-before-1440x900.png`
- `docs/milestones/screenshots/m59-desktop-after-1440x900.png`
- `docs/milestones/screenshots/m59-mobile-before-375x812.png`
- `docs/milestones/screenshots/m59-mobile-after-375x812.png`

## Verifier report
```markdown
# Formal Verification Report: Milestone 59 (Row 14: U5/U6 Accessibility Baseline & Formatter Unification)

**Verifier Role**: Independent Read-Only Verifier  
**Active Branch**: `ui/a11y-baseline`  
**Base Commit**: `15c35c8` (HEAD -> ui/a11y-baseline, origin/main, main)  
**Target Version**: `v2.17.0`  
**Overall Verdict**: **PASS**  

---

### Section 1: Executive Summary
Milestone 59 (Audit Row 14: U5/U6) implements a comprehensive WCAG 2.1 AA accessibility baseline, unifies number and currency formatting, and standardizes rate units without introducing any regressions or breaking existing features.
- All 5 always-on acceptance gates (A1–A5) and all 8 milestone acceptance gates (B1–B8) have been independently re-derived, measured, and verified as PASS.
- Full test suites passed cleanly: Python unit suite (273 tests in 41.67s, OK), VDONE gates (4 tests, OK), docs integrity (10 tests, OK), model roster integrity (7 tests, OK), a11y baseline (7 tests, OK), and Playwright a11y E2E suite (5 tests in 59.6s, OK).
- Headless browser verification at 1440×900 and 375×812 confirmed seamless tab switching with ARIA state toggling, accessible table captions on all 11 tables, 31 compliant progress bars, keyboard :focus-visible focus rings, 2-decimal currency display outside #turns-table, tok/min ticker units, accessible status glyphs, and an 11px font size floor.
- Operational check (scripts/ops_check.py) verified export OK, daemon RUNNING / REGISTERED, and menubar RUNNING. Zero secrets or credentials leaked.

---

### Section 2: Test Suite Execution Results
- Full Unit Suite: SKIP_PLAYWRIGHT=1 python3 -m unittest discover -s tests -p 'test_*.py' -> Ran 273 tests in 41.671s, OK (skipped=1) (PASS)
- VDONE Gates Suite: python3 -m unittest tests.test_vdone_gates -> Ran 4 tests in 22.041s, OK (PASS)
- Docs Integrity: python3 -m unittest tests.test_docs_integrity -> Ran 10 tests in 0.060s, OK (PASS)
- Model Roster Integrity: python3 -m unittest tests.test_model_roster_integrity -> Ran 7 tests in 0.046s, OK (PASS)
- A11y Baseline Unit Suite: python3 -m unittest tests.test_a11y_baseline -> Ran 7 tests in 0.004s, OK (PASS)
- Playwright A11y E2E Suite: npx playwright test e2e/a11y.spec.js -> 5 passed in 59.6s (PASS)

---

### Section 3: Independent Acceptance Gates Re-Derivation
- A1 Unit suite: Ran 273 tests in 41.671s, OK (skipped=1) -> PASS
- A2 Docs integrity: Ran 10 tests in 0.060s, OK -> PASS
- A3 Model roster: Ran 7 tests in 0.046s, OK -> PASS
- A4 No stale numbers: Ran 1 test in 0.026s, OK -> PASS
- A5 Fixture determinism: Exit 0, byte-identical data.json -> PASS
- B1 Single number formatter: 1 (formatCompactNumber in dashboard/js/core.js:7) -> PASS
- B2 Ticker rate units: 1 (${formatCompactNumber(rate)} tok/min in dashboard/js/now.js:670) -> PASS
- B3 Min font size baseline: Exit 0 (--font-xs: 0.6875rem / 11px floor; 0 matches) -> PASS
- B4 Table captions presence: Exit 0 (tables=11, captions=11) -> PASS
- B5 ARIA roles and attributes: Exit 0 (tablist: 3, tab: 18, tabpanel: 6, progressbar: 8 in HTML, 31 rendered) -> PASS
- B6 Focus visible styles: 8 (button, .dock-nav-item, .tab-btn, a, select, input, [role=button], [role=tab]) -> PASS
- B7 Status badge glyph presence: Exit 0 (✓, ×, !, ℹ present in dashboard/js/core.js) -> PASS
- B8 A11y unit test suite: Ran 7 tests in 0.004s, OK -> PASS

---

### Section 4: UI Interaction Verification Findings
- Desktop Viewport (1440×900): Tab switching toggles aria-selected dynamically across dock nav and command strip; keyboard Tab into #tab-sessions shows outlineStyle solid 2px; all 11 tables have non-empty sr-only captions; 31 progress bars rendered with progressbar role and aria-valuenow; zero 3+ decimal figures outside turns table; ticker displays tok/min; status badge displays accessible glyphs.
- Mobile Viewport (375×812): Mobile bottom nav switches views and updates aria-selected cleanly; all visible elements respect 11px minimum typography floor.

---

### Section 5: Repository Hygiene & Security
- Zero leaked credentials or secrets across git diff and new files.
- Documentation and versioning aligned to 2.17.0.
- scripts/ops_check.py verified live pipeline operational.

FINAL VERDICT: PASS
```

## Closing report
```
Merged:   M59 · v2.17.0 · Accessibility baseline, ARIA roles, table captions & currency format unification (Row 14: U5/U6)
Open now: - **Row 15 (5.6)**: Move Playwright bridge out of default discover, add nightly CI job (`ci/e2e-nightly`) [P2]
Next slice will touch: tests/test_playwright_e2e.py, .github/workflows/
Needs owner: nothing
Freeze:   lifted
```
