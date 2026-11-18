# Milestone 81: Lazy Tab Rendering to Eliminate Initial DOM Bloat (U1)

**Date**: 2026-09-29
**Scope**: Row 5 (U1) from `docs/HANDOVER.md` §Open Work & `docs/AUDIT_2026-09-29_SYSTEM_PERFORMANCE_AND_UX.md`
**Branch**: `perf/lazy-tab-rendering`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `U1` in `docs/AUDIT_2026-09-29_SYSTEM_PERFORMANCE_AND_UX.md` identified:
- On initial dashboard boot, all tab views (`#view-now`, `#view-sessions`, `#view-projects`, `#view-swarms`, `#view-billing`, `#view-plan`) were eagerly rendered into the DOM, resulting in 8,392 DOM elements on load.
- Projects (3,409 nodes) and Swarms (1,828 nodes) accounted for the majority of initial DOM bloat, exceeding the Lighthouse DOM budget by 5.4×.
- Intended behavior: Defer rendering deferred tab views (`#view-sessions`, `#view-projects`, `#view-swarms`, `#view-billing`, `#view-plan`) until their tab navigation button is clicked by the user.

---

## 2. Changes Implemented

- **`dashboard/js/core.js`**:
  - Implemented lazy tab activation tracking via `renderedTabs` set (`renderedTabs.has(viewId)`).
  - On initial boot, only `#view-now` and common shell components (context safety strip, active session strip) are rendered.
  - When clicking navigation dock items (`#dock-tab-*`), `showView(viewId)` checks whether the target tab has been rendered; if not, it triggers the corresponding renderer (`renderSessionsView()`, `renderProjectsView()`, `renderSwarmsView()`, `renderBillingView()`, `renderPlanManager()`) and marks it rendered.
  - Subsequent data updates (`render(data)`) refresh only currently active and previously rendered tabs, maintaining responsiveness and preventing memory leaks.
- **`dashboard/js/now.js`**:
  - Guarded against re-rendering inactive deferred views during live ticker and meta micro-polling.
- **`dashboard/js/sessions-turns.js` & `dashboard/js/sessions-filters.js`**:
  - Guarded lazy drawer rendering and filter state to initialize cleanly upon first view activation.

---

## 3. Acceptance Gates (§B)

| Gate # | Description | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :--- | :--- |
| B1 | Initial DOM node count under 1500 on load | `node -e "const { chromium } = require('./node_modules/@playwright/test'); const path = require('path'); (async () => { const b = await chromium.launch({ headless: true }); const p = await b.newPage({ viewport: { width: 1440, height: 900 } }); await p.goto('file://' + path.resolve('dashboard/index.html')); await p.waitForSelector('#sub-status-badge'); const count = await p.evaluate(() => document.querySelectorAll('*').length); await b.close(); if (count > 1500) { console.error('DOM_TOO_LARGE:', count); process.exit(1); } console.log(count); })();"` | `< 1500` | PASS (shows change: 8392 -> 1353) |
| B2 | Headless console error-free load and tab traversal | `node -e "const { chromium } = require('./node_modules/@playwright/test'); const path = require('path'); (async () => { const b = await chromium.launch({ headless: true }); const p = await b.newPage({ viewport: { width: 1440, height: 900 } }); const errs = []; p.on('pageerror', e => errs.push(e.message)); await p.goto('file://' + path.resolve('dashboard/index.html')); await p.waitForSelector('#sub-status-badge'); for (const id of ['dock-tab-sessions', 'dock-tab-projects', 'dock-tab-swarms', 'dock-tab-billing', 'dock-tab-plan', 'dock-tab-now']) { await p.click('#' + id); await p.waitForTimeout(100); } await b.close(); if (errs.length) { console.error('PAGE_ERRORS:', errs); process.exit(1); } console.log('OK'); })();"` | `OK` | PASS |
| B3 | Lazy tab activation and DOM population on click | `node -e "const { chromium } = require('./node_modules/@playwright/test'); const path = require('path'); (async () => { const b = await chromium.launch({ headless: true }); const p = await b.newPage({ viewport: { width: 1440, height: 900 } }); await p.goto('file://' + path.resolve('dashboard/index.html')); await p.waitForSelector('#sub-status-badge'); const preEmpty = await p.evaluate(() => document.querySelectorAll('#projects-table-tbody .empty-state').length); await p.click('#dock-tab-projects'); await p.waitForTimeout(200); const postProj = await p.evaluate(() => document.querySelectorAll('#projects-table tbody tr').length); const postEmpty = await p.evaluate(() => document.querySelectorAll('#projects-table-tbody .empty-state').length); await b.close(); if (preEmpty !== 1 || postProj <= 1 || postEmpty !== 0) { console.error('PROJECTS_LAZY_FAIL:', { preEmpty, postProj, postEmpty }); process.exit(1); } console.log('OK'); })();"` | `OK` | PASS (shows change) |
| B4 | JS line budget compliance core.js < 800 lines | `python3 -c "import pathlib; lines = len(pathlib.Path('dashboard/js/core.js').read_text().splitlines()); assert lines < 800, f'core.js lines: {lines}'; print('OK')"` | `OK` | PASS |
| B5 | E2E tab navigation and boot suites pass | `python3 -c "import subprocess; res = subprocess.run(['npx', 'playwright', 'test', 'e2e/navigation-and-tabs.spec.js', 'e2e/dashboard-boot.spec.js'], capture_output=True, text=True); assert res.returncode == 0, res.stderr + res.stdout; print('OK')"` | `OK` | PASS |
