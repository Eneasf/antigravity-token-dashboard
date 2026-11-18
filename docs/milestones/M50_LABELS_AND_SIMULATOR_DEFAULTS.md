# M50 · Dynamic UI Labels, Simulator Defaults & Canonical Light Mode · 2026-09-19 · v2.8.0

## Why
Eliminated stale hardcoded quota tier labels, restored canonical light theme default (ADR-048 / §7 #1), defaulted simulator plan to active subscription payload tier (C2), handled overage credit disabling gracefully with hard stop callouts, and replaced confusing LaTeX math syntax with plain English descriptions (audit row 5, ADR-063).

## What changed
- `dashboard/styles.css`: Made light theme tokens canonical `:root` default; scoped dark tokens under `[data-theme="dark"], html.dark`.
- `dashboard/index.html`: Cleaned static hardcoded badges, updated theme bootstrap script to default to light, updated simulator tier options and slider labels to plain English without LaTeX.
- `dashboard/demo.html`: Synced simulator tier options and slider labels for demo consistency.
- `dashboard/app.js`: Dynamically rendered tier name in `#sub-status-badge`, renewal date in `#billing-cycle-badge`, and freshness in `#data-freshness-badge`; defaulted simulator select to `summary.tier`; added hard stop callout when `use_ai_credits === false`.
- `tests/test_labels_and_defaults.py`: Authored 8 unit tests covering label rendering, simulator defaults, zero LaTeX syntax, and light theme configuration.
- `e2e/labels-and-defaults.spec.js`: Playwright E2E test asserting light theme default, dynamic badges, simulator tier match, and overage limit messaging.
- `docs/REPO_MAP.md`: Registered `test_labels_and_defaults.py`.
- `CHANGELOG.md`: Added release notes for v2.8.0 / Milestone 50.
- `docs/HANDOVER.md`: Logged ADR-063, updated Milestone Index, and transitioned Row 5 to Closed.
- `package.json` & `pyproject.toml`: Bumped version to `2.8.0`.

## Decisions taken
- ADR-063: Dynamic UI Labels, Simulator Defaults & Canonical Light Mode adopted.

## Gates & proofs
- B1 No hardcoded labels: `grep -cE 'Renews 24 Sep|Safe in Pro Quota|100% Pro plan|SQLite WAL Hook' dashboard/index.html dashboard/app.js` -> 0
- B2 Zero LaTeX math: `grep -cE '\$[A-Za-z\\{]' dashboard/index.html` -> 0
- B3 Light theme default: `python3 -c "..."` -> OK
- B4 Simulator tier names: `python3 -c "..."` -> OK
- B5 Labels & defaults test: `python3 -m unittest tests.test_labels_and_defaults` -> Ran 8 tests in 0.017s, OK
- B6 Playwright e2e test: `npx playwright test e2e/labels-and-defaults.spec.js` -> 1 passed (8.5s), OK
- B7 VDONE size budget: `wc -l VDONE.md` -> 19 lines (< 150 lines), OK
- B8 Gate runner proof: `python3 -m unittest tests.test_vdone_gates` -> Ran 4 tests in 22.366s, OK

## Ops check
`[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 57220) | verified: 2026-09-19T19:53:12+01:00`

## Screenshots
- Desktop Now (1440x900): `dashboard/test-artifacts/m50_screenshots/before-1440-now.png` -> `dashboard/test-artifacts/m50_screenshots/after-1440-now.png`
- Desktop Plan (1440x900): `dashboard/test-artifacts/m50_screenshots/before-1440-plan.png` -> `dashboard/test-artifacts/m50_screenshots/after-1440-plan.png`
- Mobile Now (375x812): `dashboard/test-artifacts/m50_screenshots/before-375-now.png` -> `dashboard/test-artifacts/m50_screenshots/after-375-now.png`
- Mobile Plan (375x812): `dashboard/test-artifacts/m50_screenshots/before-375-plan.png` -> `dashboard/test-artifacts/m50_screenshots/after-375-plan.png`

## Closing report
Merged:   M50 · v2.8.0 · Dynamic UI labels, simulator defaults & light theme standard (audit row 5)
Open now: Row 6 (C3): Split initDashboard into bootOnce/render, delegated event listeners (`refactor/dashboard-boot`) [P1]
Next slice will touch: dashboard/app.js, dashboard/index.html, tests/test_dashboard_boot.py
Needs owner: nothing
Freeze:   lifted (rows 4 and 5 merged)
