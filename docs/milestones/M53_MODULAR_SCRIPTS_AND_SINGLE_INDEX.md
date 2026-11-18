# M53 · Modular Plain Scripts & Single-Index Demo · 2026-09-20 · v2.11.0

## Why
Decomposed monolith `dashboard/app.js` into seven focused plain script files (<800 lines each) loaded in sequence via `<script>` tags, eliminated duplicate function declarations, collapsed disparate compact formatters into one canonical `formatCompactNumber`, unified interactive demo showcase mode into `dashboard/index.html?demo=1`, and deleted `dashboard/demo.html` (audit row 7.5 and row 12 / C8, ADR-066).

## What changed
- `dashboard/app.js`: Deleted monolith script and replaced with seven modular plain scripts under `dashboard/js/`.
- `dashboard/demo.html`: Deleted; demo showcase mode unified directly into `index.html?demo=1`.
- `dashboard/index.html`: Loaded the 7 plain scripts in strict dependency order; added conditional dynamic demo data injection when `?demo=1` is present.
- `dashboard/js/core.js`: Core state, formatters (`formatNumber`, `formatCompactNumber`, `formatCurrency`), theme, shell, tab routing, and boot/render lifecycle.
- `dashboard/js/now.js`: Telemetry cockpit, live token ticker, active model matrix, and real-time quota gauges.
- `dashboard/js/sessions.js`: Session table, token breakdown, turn inspector drawer, and unified context safety strip.
- `dashboard/js/projects.js`: Project workspace cards, branch trees, and per-project usage metrics.
- `dashboard/js/swarms.js`: Multi-agent swarm timeline, DAG visualizer, and agent economics.
- `dashboard/js/billing.js`: Weekly cycle ledger, billing KPI cards, and credit reconciliation.
- `dashboard/js/plan.js`: Plan profile manager, what-if workload simulator, and model rate cards.
- `e2e/app-js-split.spec.js`: Playwright E2E test verifying byte-for-byte tab equality across all 6 tabs (`now`, `sessions`, `projects`, `swarms`, `billing`, `plan`) against pre-split baseline captures, plus validating demo showcase banner activation via `?demo=1`.
- `tests/fixtures/baseline_tabs/`: Pre-split baseline HTML captures across all 6 tabs on deterministic fixture data.
- `scripts/build_demo_showcase.py`: Updated demo showcase builder to validate `index.html?demo=1` instead of `demo.html`.
- `tests/test_model_roster_integrity.py`, `tests/test_dashboard_boot.py`, `tests/test_plain_header_and_now_copy.py`, `tests/test_labels_and_defaults.py`: Updated to inspect `dashboard/js/*.js` instead of deleted `app.js` and `demo.html`.
- `docs/REPO_MAP.md`: Registered `dashboard/js/` plain scripts and removed references to `app.js` and `demo.html`.
- `CHANGELOG.md`: Added release notes for v2.11.0 / Milestone 53.
- `docs/HANDOVER.md`: Logged ADR-066, added M53 to Milestone Index, and closed Row 7.5 and Row 12 in Section 4.
- `package.json` & `pyproject.toml`: Bumped version to `2.11.0`.

## Decisions taken
- ADR-066: Modular Plain Script Architecture & Single-Index Demo Unification.

## Gates & proofs
- B1 File size budget: `python3 -c "from pathlib import Path; files = list(Path('dashboard/js').glob('*.js')); assert len(files) == 7, f'Expected 7 files, got {len(files)}'; over = [f'{f.name} ({len(f.read_text().splitlines())} lines)' for f in files if len(f.read_text().splitlines()) > 800]; assert not over, f'Over 800: {over}'; print('OK')"` -> OK
- B2 Zero duplicate fns: `python3 -c "import re, glob; from collections import Counter; fns = [m.group(1) for p in glob.glob('dashboard/js/*.js') for m in re.finditer(r'^(?:async\s+)?function\s+([a-zA-Z0-9_]+)', open(p).read(), re.M)]; dups = [k for k, v in Counter(fns).items() if v > 1]; assert not dups, f'Duplicates: {dups}'; print('OK')"` -> OK
- B3 Single compact fmt: `python3 -c "import re, glob; fns = [m.group(1) for p in glob.glob('dashboard/js/*.js') for m in re.finditer(r'^(?:async\s+)?function\s+(format(?:Compact|Tokens)[a-zA-Z0-9_]*)', open(p).read(), re.M)]; assert set(fns) == {'formatCompactNumber'}, f'Expected only formatCompactNumber, got: {set(fns)}'; print('OK')"` -> OK
- B4 Demo HTML deleted: `python3 -c "from pathlib import Path; assert not Path('dashboard/demo.html').exists(), 'demo.html must be deleted'; print('OK')"` -> OK
- B5 Playwright tabs byte equality: `python3 -c "import subprocess; res = subprocess.run(['npx', 'playwright', 'test', 'e2e/app-js-split.spec.js'], capture_output=True, text=True); assert res.returncode == 0, res.stderr + res.stdout; print('OK')"` -> OK
- Gate runner proof: `python3 -m unittest tests.test_vdone_gates` -> Ran 4 tests in 22.278s, OK

## Ops check
`[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 57220) | verified: 2026-09-20T12:21:43+01:00`

## Closing report
Merged:   M53 · v2.11.0 · Split app.js into 7 plain scripts and unify demo mode (Row 7.5 & Row 12)
Open now: - **Row 8 (C4/U3)**: Per-model truncation thresholds in models.json, demote warning badge, paged Sessions (`feat/truncation-per-model`) [P1]
Next slice will touch: antigravity_telemetry/models.json, src/aggregator.py, dashboard/index.html, dashboard/js/sessions.js
Needs owner: nothing
Freeze:   lifted
