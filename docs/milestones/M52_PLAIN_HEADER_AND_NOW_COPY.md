# M52 · Plain Header & Now Copy · 2026-09-20 · v2.10.0

## Why
Replaced internal engineering jargon across Now tab cards with plain English ("Quota right now", "Gemini", "Weekly pace", "Pace", "Claude & GPT"), deleted redundant fallback reserve widget, compacted desktop header into a single line (<72px), reduced mobile header (<160px), and added an overflow dropdown menu (audit row 7 / U1 + U2, ADR-065).

## What changed
- `dashboard/index.html` & `dashboard/demo.html`: Plain English card titles/subtitles, single-line header layout with overflow dropdown, removed redundant reserve widget, eliminated engineering jargon.
- `dashboard/styles.css`: Clamped title `clamp(18px, 2.2vw, 26px)`, header `max-height: 68px`, media queries for <=960px and <=768px (`max-height: 140px`).
- `dashboard/app.js`: Replaced visible jargon in quota indicators, burst governor slots, track badges, and simulator recommendations; added `toggle-header-overflow` and outside-click handling in `bootOnce()`.
- `tests/test_plain_header_and_now_copy.py`: 6 unit tests asserting zero jargon in HTML/JS, plain copy, compact structure, and CSS height bounds.
- `e2e/plain-header.spec.js`: 4 Playwright tests verifying desktop header height (55.8px < 72px), mobile header height (140px < 160px), zero overflow, overflow menu, and plain copy.
- `docs/REPO_MAP.md`: Registered `test_plain_header_and_now_copy.py`.
- `CHANGELOG.md`: Added release notes for v2.10.0 / Milestone 52.
- `docs/HANDOVER.md`: Logged ADR-065, added M52 to Milestone Index, transitioned Row 7 to Closed.
- `package.json` & `pyproject.toml`: Bumped version to `2.10.0`.

## Decisions taken
- ADR-065: Plain-Language Now Copy & Compact Single-Line Header adopted.

## Gates & proofs
- B1 Plain Now copy: `python3 -c "import re; f=lambda s: re.sub(r'(title|data-tooltip)=[\'\"][^\'\"]*[\'\"]', '', s); h = f(re.sub(r'<!--.*?-->', '', open('dashboard/index.html').read(), flags=re.S)); j = f(re.sub(r'//.*?\n|/\*.*?\*/', '', open('dashboard/app.js').read(), flags=re.S)); m = re.findall(r'(?i)\b(contamination|spillover|governor|dual-track|dual-benchmark|family routing|isolation policy)\b', h + j); assert not m, f'Found jargon: {set(m)}'; print('OK')"` -> OK
- B2 Header clamp CSS: `python3 -c "s=open('dashboard/styles.css').read(); assert 'clamp(18px' in s and 'header {' in s and 'max-height: 68px' in s; print('OK')"` -> OK
- B3 Mobile header CSS: `python3 -c "s=open('dashboard/styles.css').read(); assert '@media (max-width: 960px)' in s and '@media (max-width: 768px)' in s and 'max-height: 140px' in s; print('OK')"` -> OK
- B4 Header overflow DOM: `python3 -c "h=open('dashboard/index.html').read(); assert 'btn-header-overflow' in h and 'header-overflow-menu' in h and 'btn-copy-standup' in h; print('OK')"` -> OK
- B5 Unit suite M52: `python3 -m unittest tests.test_plain_header_and_now_copy` -> Ran 6 tests in 0.034s, OK
- B6 VDONE size budget: `wc -l VDONE.md` -> 19 lines (< 150 lines), OK
- B7 Gate runner proof: `python3 -m unittest tests.test_vdone_gates` -> Ran 4 tests in 13.156s, OK

## Ops check
`[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 57220) | verified: 2026-09-20T11:09:09+01:00`

## Screenshots
- Desktop Now (1440x900): `dashboard/test-artifacts/m52_screenshots/before-1440-now.png` -> `dashboard/test-artifacts/m52_screenshots/after-1440-now.png`
- Desktop Plan (1440x900): `dashboard/test-artifacts/m52_screenshots/before-1440-plan.png` -> `dashboard/test-artifacts/m52_screenshots/after-1440-plan.png`
- Mobile Now (375x812): `dashboard/test-artifacts/m52_screenshots/before-375-now.png` -> `dashboard/test-artifacts/m52_screenshots/after-375-now.png`
- Mobile Plan (375x812): `dashboard/test-artifacts/m52_screenshots/before-375-plan.png` -> `dashboard/test-artifacts/m52_screenshots/after-375-plan.png`

## Closing report
Merged:   M52 · v2.10.0 · Plain header & Now copy (audit row 7)
Open now: - **Row 8 (C4/U3)**: Per-model truncation thresholds in models.json, demote warning badge, paged Sessions (`feat/truncation-per-model`) [P1]
Next slice will touch: models.json, src/aggregator.py, dashboard/index.html, dashboard/app.js
Needs owner: nothing
Freeze:   lifted
