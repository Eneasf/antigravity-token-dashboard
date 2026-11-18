# M51 · Dashboard Boot & Pure Render Split · 2026-09-19 · v2.9.0

## Why
Split `initDashboard()` into one-time DOM wiring (`bootOnce()`) and idempotent DOM projection (`render(data)`), replaced 61 inline `onclick=` handlers with declarative `data-action` delegation, defaulted `#plan-tier-select` to `summary.tier`, and eliminated UI refresh duplication leaks (audit row 6 / C3, ADR-064).

## What changed
- `dashboard/app.js`: Added `let isBooted = false;` and `bootOnce()`; refactored `render(data)` as pure DOM update; replaced inline `onclick` with delegated click listener on `document`; updated `checkAndReloadTelemetry()` to call `render()`; defaulted `#plan-tier-select` to `summary.tier`.
- `dashboard/index.html` & `dashboard/demo.html`: Replaced all 48 inline `onclick=` handlers with `data-action` attributes and removed hardcoded `selected` from plan tier `<option value="pro">`.
- `tests/test_dashboard_boot.py`: Authored 8 unit tests covering boot/render separation, reload behavior, zero inline onclicks, event delegation coverage, plan tier preset defaults, and idempotence.
- `e2e/dashboard-boot.spec.js`: Playwright E2E test verifying delegated interactions, currency switching, archetype selection, plan tier defaults, reload idempotence, and mobile viewports.
- `docs/REPO_MAP.md`: Registered `test_dashboard_boot.py`.
- `CHANGELOG.md`: Added release notes for v2.9.0 / Milestone 51.
- `docs/HANDOVER.md`: Logged ADR-064, updated Milestone Index, and transitioned Row 6 to Closed.
- `package.json` & `pyproject.toml`: Bumped version to `2.9.0`.

## Decisions taken
- ADR-064: Dashboard Boot & Pure Render Lifecycle Split adopted.

## Gates & proofs
- B1 Boot/render split: `python3 -c "import re; s=open('dashboard/app.js').read(); assert 'function bootOnce' in s and 'function render(data)' in s and 'let isBooted = false;' in s; print('OK')"` -> OK
- B2 Reload calls render: `python3 -c "import re; s=open('dashboard/app.js').read(); fn=re.search(r'function checkAndReloadTelemetry.*?\{(.*?)\n\}', s, re.S).group(1); assert 'render(' in fn and 'initDashboard(' not in fn; print('OK')"` -> OK
- B3 Zero inline onclicks: `python3 -c "import re; assert not re.search(r'onclick\s*=', open('dashboard/index.html').read(), re.I); assert not re.search(r'onclick\s*=', open('dashboard/demo.html').read(), re.I); assert not re.search(r'onclick\s*=', open('dashboard/app.js').read(), re.I); print('OK')"` -> OK
- B4 Plan tier default: `python3 -c "s=open('dashboard/index.html').read(); assert '<option value=\"pro\" selected>' not in s; print('OK')"` -> OK
- B5 Unit tests: `python3 -m unittest tests.test_dashboard_boot` -> Ran 8 tests in 0.010s, OK
- B6 Playwright e2e test: `npx playwright test e2e/dashboard-boot.spec.js` -> 1 passed (10.8s), OK
- B7 VDONE size budget: `wc -l VDONE.md` -> <= 150 lines, OK
- B8 Gate runner proof: `python3 -m unittest tests.test_vdone_gates` -> Ran 4 tests in 12.248s, OK

## Ops check
`[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 57220) | verified: 2026-09-19T20:14:51+01:00`

## Screenshots
- Desktop Now (1440x900): `dashboard/test-artifacts/m51_screenshots/before-1440-now.png` -> `dashboard/test-artifacts/m51_screenshots/after-1440-now.png`
- Desktop Plan (1440x900): `dashboard/test-artifacts/m51_screenshots/before-1440-plan.png` -> `dashboard/test-artifacts/m51_screenshots/after-1440-plan.png`
- Mobile Now (375x812): `dashboard/test-artifacts/m51_screenshots/before-375-now.png` -> `dashboard/test-artifacts/m51_screenshots/after-375-now.png`
- Mobile Plan (375x812): `dashboard/test-artifacts/m51_screenshots/before-375-plan.png` -> `dashboard/test-artifacts/m51_screenshots/after-375-plan.png`

## Closing report
Merged:   M51 · v2.9.0 · Dashboard boot refactor, delegated listeners & plan tier default (audit row 6)
Open now: Row 7 (U1/U2): Plain-language Now tab copy, compact 1-line header, mobile header (<160px) (`ui/plain-header`) [P1]
Next slice will touch: dashboard/index.html, dashboard/app.js, dashboard/styles.css
Needs owner: nothing
Freeze:   lifted (rows 4 and 5 merged)
