# Engineering, UI & Ceremony Audit — 22 Sep 2026

**Scope**: Repository at commit `ce97d44` on `feat/agent-persona-telemetry` with 23 modified and 2 untracked files (301/301 unit tests passing in 68.1 s).  
**Method**: Evaluated `AGENTS.md`, `CLAUDE.md`, `README.md`, `VDONE.md`, `docs/HANDOVER.md`, the 19 Sep audit, `src/`, `scripts/`, `antigravity_telemetry/`, `macos/`, and `dashboard/`. Executed all side-effect-free acceptance gates via `tests/test_vdone_gates.py`. Started a local HTTP server (`python3 -m http.server 8089 -d dashboard`) and executed the §4.0 Playwright runner across desktop (1440×900) and mobile (375×812) viewports in both light and dark themes across all six tabs. Executed automated axe-core WCAG 2.1 AA accessibility scans and scripted the three primary interactions. Analyzed live daemon processes, launchd configurations, and log streams. Discarded contradicted hypotheses via an adversarial Challenger. No project code outside the audit document was modified (Zero Mutation).  
**Audience**: The maintaining agent and the repository owner. Every finding provides an exact reproduction command, a concrete fix, an executable gate, effort estimate, target branch, and priority.

---

## 0. Executive Summary

The engineering foundation and telemetry parser extensions are solid: pure-Python protobuf decoding for agent personas (M64) passed 10/10 unit tests, and upstream SQLite read-only invariants (`?mode=ro`) remain strictly respected.

However, the repository currently suffers from a catastrophic frontend crash and a silent background daemon deadlock, directly causing the symptom reported by the owner ("the dashboard is not loading all the info"):

| Area | Verdict | Headline |
|---|---|---|
| **Correctness** | **CRITICAL: Frontend Rendering Deadlock** | `dashboard/js/now.js:600` throws `ReferenceError: cid is not defined`. Uncaught exception immediately terminates `renderNowView()`, aborting subsequent initialization of Claude Weekly quotas, model allowance cards, swarms, trends, and session tables. |
| **Daemon & Ops** | **CRITICAL: Watcher Settle Window Freeze** | `DebounceController.update_settle_window` in `scripts/watch_telemetry.py:180` lacks an upper clamp. An export recorded while the system was suspended set `settle_window` to **26,693.34 s (7.41 hours)**, freezing the live daemon (PID 64248) from exporting for **>8.3 hours**. Dashboard data on disk is 8+ hours stale. |
| **UI & A11y** | **Regressed / Multiple Critical Violations** | Axe-core detects 6 critical `button-name` violations on desktop dock navigation buttons (SVG icons have `aria-hidden="true"` with CSS-hidden labels), 2 critical `select-name` violations, and color contrast failures peaking at **238 nodes** on the Swarms tab in dark mode. |
| **Ceremony** | **Premature Milestone Closure & Missing Gates** | `docs/HANDOVER.md` prematurely marks M64 as "Closed This Quarter" despite 23 uncommitted modified files and 2 untracked files on branch `feat/agent-persona-telemetry`. `VDONE.md` defined 0 frontend rendering gates for M64, permitting broken UI code to pass all checks. |
| **Code Structure** | **Line Budget Violations** | Three files violate the 800-line architecture rule: `dashboard/js/core.js` (921 lines), `dashboard/js/now.js` (864 lines), and `dashboard/js/sessions.js` (860 lines). |

**Top five actions, in order**:
1. **C1 (P0)**: Restore missing variables (`cid`, `turns`, `tok`, `model`) in `dashboard/js/now.js` line 583 to eliminate the uncaught `ReferenceError`.
2. **C2 (P0)**: Clamp `DebounceController.update_settle_window` to a strict upper bound (`min(10.0, ...)` seconds) in `scripts/watch_telemetry.py:182` and restart the daemon.
3. **D1 (P0)**: Reopen M64 in `docs/HANDOVER.md` and add an automated Playwright headless console error gate to `VDONE.md` §B before committing.
4. **U1 (P1)**: Add `aria-label` attributes to desktop dock navigation buttons (`#dock-tab-*`) and form selects to clear critical axe failures.
5. **D2 (P2)**: Modularize `core.js`, `now.js`, and `sessions.js` to bring all scripts strictly below the 800-line budget.

**Blunt version for the owner**: The dashboard is empty because a variable was deleted during the subagent telemetry update while still being used in the HTML template. When the page opens, it crashes immediately, before it can draw the rest of the cards and tables. At the same time, the background watcher daemon froze 8 hours ago because it recorded a laptop sleep period as an "export duration" and decided to wait 7.4 hours before updating again. Fixing this requires 2 lines of code in the frontend, 1 line of clamping in the watcher script, and adding a browser test so broken JavaScript can never slip through again.

---

## 1. Measured Facts (reproduce before disputing)

### 1.1 Detected Parameters (§0.2)
```text
AUDIT_TIER        DEEP                                                     (sure: request specified in-depth review)
GOVERNANCE_DOCS   AGENTS.md CLAUDE.md CONTRIBUTING.md VDONE.md README.md docs/HANDOVER.md  (sure)
PREVIOUS_AUDIT    docs/AUDIT_2026-09-19_UI_CODE_AND_CEREMONY.md            (sure)
TEST_CMD          python3 -m unittest discover -s tests                    (sure: .github/workflows/ci.yml:37)
LINTER_CMD        none                                                     (sure: nothing in CI or manifests)
GATE_FILE         VDONE.md                                                 (sure)
UI_ENTRY          dashboard/index.html via python3 -m http.server 8089 -d dashboard   (sure: playwright.config.js:46)
UI_VIEWPORTS      1440x900, 375x812   UI_THEMES light,dark                 (sure)
SAFETY_RULES      AGENTS.md §2: upstream *.db opened with ?mode=ro only    (sure)
DECISION_LOG      docs/HANDOVER.md    MILESTONE_DIR docs/milestones/        (sure)
DAEMON_LOG        ~/Library/Logs/Antigravity/telemetry_watcher.*.log       (sure: scripts/setup_service.py:46)
CYCLE_CMD         python3 scripts/export_dashboard.py --dry-run --no-live-quota   (sure: README:25)
OWNER_PROFILE     non-developer, blunt findings                            (sure: confirmed by owner)
OUTPUT            docs/AUDIT_2026-09-22_SYSTEM_DATA_AND_UX.md              (sure)
```

### 1.2 Quantitative Measurements

| Fact | Measured Value | Exact Command / Reproduction Method |
|---|---|---|
| Active git branch | `feat/agent-persona-telemetry` (dirty: 23 modified, 2 untracked) | `git status --short` |
| Tracked files | 259 files | `git ls-files \| wc -l` |
| Repository `.git` size | 34 MB | `du -sh .git` |
| Unit test suite | 301 pass, 0 fail (68.14 s) | `time python3 -m unittest discover -s tests` |
| Test suite warnings | 1 `ResourceWarning: unclosed database` at `src/git_timeline.py:169` | `python3 -W error::ResourceWarning -m unittest discover -s tests` |
| Automated gates in `VDONE.md` | 4 test cases (covering 10 assertions) pass in 28.36 s | `python3 -m unittest tests/test_vdone_gates.py` |
| Upstream db connection safety | 100% compliant: all upstream SQLite DBs opened via `file:...?mode=ro` with `uri=True` | `grep -rnE 'sqlite3\.connect\(' src scripts antigravity_telemetry \| grep -v 'mode=ro'` |
| Exporter concurrency locks | `fcntl.flock(fcntl.LOCK_EX \| fcntl.LOCK_NB)` on `dashboard/.export.lock` | `grep -rnE 'fcntl\.flock' scripts/export_dashboard.py` |
| Offline dry-run cycle duration | 54.33 s wall (333 DBs scanned, 332 sessions extracted) | `time python3 scripts/export_dashboard.py --dry-run --no-live-quota` |
| Live daemon PID & status | PID 64248 running, heartbeat active every 10 s | `ps aux \| grep watch_telemetry`; `cat ~/.antigravity_quota_status.json` |
| Daemon export freeze duration | Stalled for **29,481 s (~8.19 hours)** without export | `stat -f "%Sm" dashboard/data.js` vs `date` |
| Daemon debounce inflation | `settle_window = 26693.34s` (7.41 h), `max_delay = 53386.68s` (14.8 h) | `tail -n 20 ~/Library/Logs/Antigravity/telemetry_watcher.stdout.log` |
| Frontend uncaught exceptions | `pageErrors: ["cid is not defined", "cid is not defined"]` on all tabs | Playwright runner `scratch/audit_ui.mjs` console/pageerror listener |
| Desktop header height (1440×900) | 52 px (compliant, < 160 px) | `document.querySelector('header').getBoundingClientRect().height` |
| Mobile header height (375×812) | 70 px (compliant, < 160 px) | `document.querySelector('header').getBoundingClientRect().height` |
| Horizontal overflow (`overflowX`) | 0 px on 1440×900, 0 px on 375×812 | `document.documentElement.scrollWidth - innerWidth` |
| Axe critical a11y violations | 6 `button-name` (desktop dock), 1–2 `select-name` (swarms/plan) | AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze() |
| Axe serious contrast violations | 15–110 nodes (light theme), 21–238 nodes (dark theme, peak: Swarms) | AxeBuilder `color-contrast` violation nodes count |
| Small touch targets (< 44 px) | 18–37 on desktop; 5–24 on mobile | DOM element bounding rect evaluation |
| Telemetry vault size on disk | 2.3 GB (`data/antigravity_vault.db`), 0 `.bak` files | `ls -lh data/` |
| JavaScript line count violations | `core.js`: 921 lines; `now.js`: 864 lines; `sessions.js`: 860 lines | `wc -l dashboard/js/*.js` |

---

## 2. Scorecard Against Previous Audit (19 Sep 2026)

| # | Item | Status | Verification & Evidence |
|---|---|---|---|
| **1** | D1 — `VDONE.md` to §A/§B + `test_vdone_gates.py` | **DONE** | `VDONE.md` reduced to 18 lines; `tests/test_vdone_gates.py` runs active gates automatically in 28.36 s. |
| **2** | D2 — README front door, `CHANGELOG.md`, `REPO_MAP.md` | **DONE** | README is 100 lines; `CHANGELOG.md` created; `docs/REPO_MAP.md` created. |
| **3** | D3 — HANDOVER ADR rows ≤ 160 chars, semantic `v2.x.y` | **DONE** | ADR table reformatted; tags follow `v2.20.1`. |
| **4** | C1 — Export advisory lock and unique temp files | **DONE** | `fcntl.flock` implemented on `dashboard/.export.lock` in `scripts/export_dashboard.py:795`. |
| **5** | C2+U4+U7 — Dynamic labels, simulator default plan, light theme | **DONE** | Header labels dynamically formatted from metadata; light theme supported. |
| **6** | C3 — `bootOnce()` / `render()` split | **DONE** | Split implemented in `dashboard/js/core.js:900-903`. |
| **7** | U1+U2 — Compact header, mobile header < 160 px | **DONE** | Desktop header is 52 px; mobile header is 70 px. |
| **8** | C4+U3 — Per-model truncation thresholds, paged sessions | **DONE** | Implemented in `src/aggregator_windows.py` and `dashboard/js/sessions.js`. |
| **9** | C5 — Compact `data.js` and lazy-loaded `turns.js` | **DONE** | Decoupled in M55; `turns.js` (19.7 MB) loaded on demand. |
| **10** | C6 — Integrity check, `.bak` removal, vault size in meta | **DONE** | `.bak` deleted; `vault_bytes` recorded in `meta.json`. |
| **11** | C7 — Adaptive settle window for watcher | **REGRESSED** | Implemented in M57, but lacking upper clamp; caused daemon deadlock (Finding C2). |
| **12** | C8 — Delete `demo.html`, unified `?demo=1` | **DONE** | `dashboard/demo.html` deleted; demo query param supported. |
| **13** | C9+C10 — Swift path literal sanitization, watcher heartbeat | **DONE** | Swift uses sanitized path; heartbeat written to `~/.antigravity_quota_status.json`. |
| **14** | U5+U6 — A11y baseline, 2-decimal money, single formatter | **PARTLY** | Currency unified; however, critical button-name and dark-theme contrast issues remain. |
| **15** | 5.6 — Playwright bridge isolated to `tests/e2e_bridge/` | **DONE** | Isolated and verified; test suite outputs clean without stdout spam. |
| **16** | U8 — Mobile viewport polish, ticker clipping fix | **DONE** | Mobile horizontal scroll eliminated (`overflowX = 0`). |
| **17** | C11 — Aggregator modularization into 6 submodules | **DONE** | Modularized into `src/aggregator_*.py` in M62 (< 800 lines each). |
| **18** | C12 — Hermetic fixture export & isolated HOME | **DONE** | Verified hermetic in M63 fixture determinism gate. |

---

## 3. Code and Correctness Findings

### Finding C1: Frontend crash `ReferenceError: cid is not defined` breaks page rendering
- **What**: In `dashboard/js/now.js` lines 583–615, the recent M64 refactor for agent persona badges deleted the variable declarations for `tok`, `turns`, `cid`, and `model`, but left template interpolation references `${cid}`, `${turns}`, `${model}`, and `${tok}` at lines 600, 605, 607, 611, and 612.
- **Why it matters**: During `renderNowView()`, calling `renderActiveBurstSessions()` throws an unhandled `ReferenceError: cid is not defined`. This abruptly halts JavaScript execution, causing subsequent view modules (Claude Weekly quotas, Model matrix, Swarms view, Tool analytics, Weekly trends, and conversation tables) to never render. The dashboard appears blank or frozen.
- **Fix**: Re-declare `cid`, `turns`, `model`, and `tok` from session properties in `dashboard/js/now.js`:
  ```javascript
  const cid = escapeHtml(s.convo_id || "");
  const turns = s.turn_count || 0;
  const tok = formatNumber(s.total_processed_tokens || 0);
  const model = escapeHtml(s.primary_model_name || "Flash");
  ```
- **Gate**:
  - `CHECK`: `node -e 'const { chromium } = require("./node_modules/@playwright/test"); (async () => { const b = await chromium.launch(); const p = await b.newPage(); const errs = []; p.on("pageerror", e => errs.push(e.message)); await p.goto("http://127.0.0.1:8089"); await p.waitForTimeout(1000); await b.close(); if (errs.length > 0) { console.error("PAGE_ERRORS:", errs); process.exit(1); } console.log("OK"); })()'`
  - `EXPECT`: `OK`
- **Effort**: 15 minutes.
- **Branch**: `fix/now-burst-session-scope`
- **Priority**: P0 (Urgent / Blocker)

---

### Finding C2: Watcher settle window runaway freezes background exports
- **What**: In `scripts/watch_telemetry.py:180-184`, `DebounceController.update_settle_window(last_duration)` calculates:
  ```python
  self.settle_window = max(self.base_settle_window, float(last_duration))
  self.max_delay = max(self.settle_window * 2.0, self.max_delay)
  ```
  It has no upper clamp. When an export ran during machine sleep or system suspension, `last_duration` was measured as 26,693.34 s (7.41 hours). Consequently, `self.settle_window` was locked to 7.41 hours and `max_delay` to 14.8 hours. The daemon PID 64248 remained active, emitting heartbeats, but refused to export for over 8.19 hours.
- **Why it matters**: The dashboard data (`data.js`, `meta.js`) ceased updating entirely, remaining frozen at yesterday's state despite hundreds of active turns in the Antigravity IDE.
- **Fix**: Clamp `settle_window` to an upper bound of 10.0 seconds (or `max_delay` ceiling):
  ```python
  MAX_SETTLE_WINDOW = 10.0
  self.settle_window = min(MAX_SETTLE_WINDOW, max(self.base_settle_window, float(last_duration)))
  self.max_delay = max(self.settle_window * 2.0, float(max_delay))
  ```
- **Gate**:
  - `CHECK`: `python3 -c "from scripts.watch_telemetry import DebounceController; d = DebounceController(); d.update_settle_window(3600.0); assert d.settle_window <= 10.0, f'Settle window unconstrained: {d.settle_window}'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 20 minutes.
- **Branch**: `fix/watcher-settle-clamp`
- **Priority**: P0 (Urgent / Blocker)

---

### Finding C3: Leaked SQLite connection warning in test suite
- **What**: Running `python3 -m unittest discover -s tests` emits a `ResourceWarning: unclosed database in <sqlite3.Connection object>` pointing to `src/git_timeline.py:169`.
- **Why it matters**: Indicates an unclosed SQLite connection being garbage-collected during timeline test discovery, creating flakes and file lock warnings on Windows/macOS.
- **Fix**: Ensure connection context manager `with sqlite3.connect(...) as conn:` or explicit `conn.close()` is used across timeline and vault tests.
- **Gate**:
  - `CHECK`: `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_git_timeline.py'`
  - `EXPECT`: `OK`
- **Effort**: 30 minutes.
- **Branch**: `fix/git-timeline-connection-leak`
- **Priority**: P2

---

## 4. UI and UX Findings

### Finding U1: Critical axe violations on desktop navigation dock buttons
- **What**: In `dashboard/index.html` lines 70–110, the desktop sidebar dock buttons (`#dock-tab-now`, `#dock-tab-sessions`, `#dock-tab-projects`, `#dock-tab-swarms`, `#dock-tab-billing`, `#dock-tab-plan`) contain SVG icons marked `aria-hidden="true"` while their label text is hidden via CSS `.sidebar-dock .dock-nav-label { display: none; }`. As a result, the buttons have no accessible name. Furthermore, select dropdowns on swarms and plan tabs lack explicit labels.
- **Why it matters**: Screen readers cannot announce the tab destinations, causing 6 Critical `button-name` and 3 Critical `select-name` WCAG 2.1 AA violations.
- **Fix**: Add `aria-label="Real-Time Quotas"` (and respective names) to each `#dock-tab-*` `<button>` and add `aria-label` to `#swarm-project-filter`, `#swarm-sort-select`, and `#sim-baseline-select`.
- **Gate**:
  - `CHECK`: `node -e 'const { chromium } = require("./node_modules/@playwright/test"); const AxeBuilder = require("./node_modules/@axe-core/playwright").default; (async () => { const b = await chromium.launch(); const c = await b.newContext({ viewport: { width: 1440, height: 900 } }); const p = await c.newPage(); await p.goto("http://127.0.0.1:8089"); const res = await new AxeBuilder({ page: p }).withRules(["button-name", "select-name"]).analyze(); await b.close(); assert(res.violations.length === 0, JSON.stringify(res.violations)); console.log("OK"); })()'`
  - `EXPECT`: `OK`
- **Effort**: 45 minutes.
- **Branch**: `fix/dock-a11y-labels`
- **Priority**: P1

---

### Finding U2: Color contrast failures across tabs peaking on dark Swarms view
- **What**: Automated axe-core scan reveals 15–110 failing nodes in light mode and 21–238 failing nodes in dark mode. The worst failure occurs on `tab-swarms` in dark theme with 238 nodes failing WCAG AA 4.5:1 ratio (subagent pills, muted timestamps, and DAG edge labels).
- **Why it matters**: Low readability in dark theme renders lineage metadata and model cost badges illegible.
- **Fix**: Increase luminance of `--text-muted` in dark mode from `#6b7280` (2.8:1) to `#9ca3af` (4.8:1), and calibrate `.badge-agent-auditor`, `.badge-agent-implementer`, and `.badge-subagent-pill` dark background/border tints.
- **Gate**:
  - `CHECK`: `node -e 'const { chromium } = require("./node_modules/@playwright/test"); const AxeBuilder = require("./node_modules/@axe-core/playwright").default; (async () => { const b = await chromium.launch(); const c = await b.newContext({ viewport: { width: 1440, height: 900 } }); const p = await c.newPage(); await p.goto("http://127.0.0.1:8089"); await p.evaluate(() => document.documentElement.setAttribute("data-theme", "dark")); await p.evaluate(() => window.switchTab("tab-swarms")); const res = await new AxeBuilder({ page: p }).withRules(["color-contrast"]).analyze(); await b.close(); const count = res.violations[0]?.nodes.length || 0; assert(count < 50, "Contrast violations: " + count); console.log("OK (" + count + " nodes)"); })()'`
  - `EXPECT`: `OK`
- **Effort**: 1.5 hours.
- **Branch**: `ui/dark-contrast-calibration`
- **Priority**: P2

---

### Finding U3: Touch target sizing under 44 px on mobile and desktop
- **What**: DOM evaluation identifies 5–24 buttons/inputs on mobile (375×812) and 18–37 on desktop that have bounding dimensions below 44×44 px (filter dropdowns, pagination buttons, compact currency pills).
- **Why it matters**: Fails WCAG 2.5.5 / 2.5.8 Target Size guidelines, causing misclicks on touchscreens.
- **Fix**: Apply CSS `min-height: 44px; min-width: 44px;` or touch hit target expansion via pseudo-elements (`::after` hit padding) on mobile pagination buttons and select controls.
- **Gate**:
  - `CHECK`: `python3 -c "import pathlib; css = pathlib.Path('dashboard/styles.css').read_text(); assert '.btn-pill' in css and 'min-height' in css; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 1 hour.
- **Branch**: `ui/tap-target-expansion`
- **Priority**: P3

---

## 5. Ceremony and Documentation Findings

### Finding D1: Premature milestone closure in `docs/HANDOVER.md`
- **What**: Line 198 of `docs/HANDOVER.md` records:
  `- **M64**: Agent persona telemetry & workflow attribution (feat/agent-persona-telemetry) — 2026-09-21` in the "Closed This Quarter" list. However, `git status --short` reveals 23 modified files and 2 untracked files on branch `feat/agent-persona-telemetry` that are neither committed nor verified.
- **Why it matters**: Violates ceremony rules (Principle 5 & AGENTS.md §5). Claiming a milestone is closed before its code is committed and verified leads to ghost releases and untracked defects.
- **Fix**: Move M64 back into `docs/HANDOVER.md` §4 "Open Work" until the C1 fix and B-gates pass verification and are merged.
- **Gate**:
  - `CHECK`: `python3 -c "t = open('docs/HANDOVER.md').read(); assert 'M64' in t.split('### Open Work')[1].split('### Closed This Quarter')[0]; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 10 minutes.
- **Branch**: `docs/handover-m64-reopen`
- **Priority**: P0

---

### Finding D2: Three JS files exceed 800-line budget
- **What**: Current file sizes in `dashboard/js/`:
  - `core.js`: 921 lines (121 lines over budget)
  - `now.js`: 864 lines (64 lines over budget)
  - `sessions.js`: 860 lines (60 lines over budget)
- **Why it matters**: Breaches the project's 800-line modularity rule (M53 / AGENTS.md §2). Monolithic frontend files encourage variable scoping accidents (exactly like Finding C1).
- **Fix**: Extract burst sessions and Now-tab tickers into `js/now-burst.js` (~150 lines), and filter handlers into `js/sessions-filters.js` (~150 lines).
- **Gate**:
  - `CHECK`: `python3 -c "import glob; bad = [f for f in glob.glob('dashboard/js/*.js') if len(open(f).readlines()) > 800]; assert not bad, f'Files over 800 lines: {bad}'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 2 hours.
- **Branch**: `refactor/js-budget-compliance`
- **Priority**: P2

---

### Finding D3: Missing frontend rendering gate in `VDONE.md`
- **What**: Active gates for M64 in `VDONE.md` (B1–B5) test only Python wire decoding, SQLite migration, and backend attribution classes. Not a single gate executes Playwright or verifies that `dashboard/index.html` loads without console errors.
- **Why it matters**: A major UI refactor shipped with a fatal `ReferenceError` while reporting "100% acceptance gates passed".
- **Fix**: Add gate B6 to `VDONE.md`:
  `B6 Frontend error-free render: CHECK node -e 'const { chromium } = require("./node_modules/@playwright/test"); (async () => { const b = await chromium.launch(); const p = await b.newPage(); const errs = []; p.on("pageerror", e => errs.push(e.message)); await p.goto("http://127.0.0.1:8089"); await p.waitForTimeout(800); await b.close(); if(errs.length) process.exit(1); })()' EXPECT OK`
- **Gate**:
  - `CHECK`: `grep -E 'Frontend error-free render' VDONE.md`
  - `EXPECT`: `Frontend error-free render`
- **Effort**: 15 minutes.
- **Branch**: `docs/vdone-frontend-gate`
- **Priority**: P1

---

## 6. Prioritised Backlog

| # | Item | Type | Pri | Effort | Branch | Blocking Decision |
|---|---|---|---|---|---|---|
| 1 | **C1** — Fix undeclared variable references in `dashboard/js/now.js:600` | fix | P0 | 15 min | `fix/now-burst-session-scope` | — |
| 2 | **C2** — Add 10.0 s upper clamp to watcher settle window | fix | P0 | 20 min | `fix/watcher-settle-clamp` | decided (Q1) |
| 3 | **D1 + D3** — Reopen M64 in `HANDOVER.md` & add frontend Playwright gate to `VDONE.md` | docs+gate | P0 | 25 min | `docs/m64-reopen-and-gate` | — |
| 4 | **U1** — Add accessible `aria-label` to dock navigation buttons & select elements | ui/a11y | P1 | 45 min | `fix/dock-a11y-labels` | — |
| 5 | **D2** — Split `core.js`, `now.js`, and `sessions.js` to bring under 800 lines | refactor | P2 | 2 h | `refactor/js-budget-compliance` | decided (Q2) |
| 6 | **C3** — Resolve unclosed SQLite connection in `src/git_timeline.py` | fix | P2 | 30 min | `fix/git-timeline-connection-leak` | — |
| 7 | **U2** — Calibrate dark theme Swarms & pill contrast ratios | ui | P2 | 1.5 h | `ui/dark-contrast-calibration` | — |
| 8 | **U3** — Expand mobile touch target hit areas to >= 44 px | ui | P3 | 1 h | `ui/tap-target-expansion` | — |

### 6.1 Instructions for the Maintaining Agent
1. Branch from `feat/agent-persona-telemetry` (or apply fixes directly before committing M64).
2. Execute Row 1 (C1) and Row 2 (C2) immediately to restore live dashboard rendering and unfreeze the background daemon.
3. Restart the LaunchAgent daemon (`python3 scripts/setup_service.py restart`) and confirm `RUNNING / REGISTERED` with a fresh settle window.
4. Execute `python3 -m unittest discover -s tests` and verify that the Playwright headless check passes with 0 page errors.
5. Only move M64 to "Closed This Quarter" in `HANDOVER.md` after the working tree is committed clean and tagged.

---

## 7. Owner Decisions (Taken 22 Sep 2026)

| # | Question | Decision Taken | Consequence Applied |
|---|---|---|---|
| **1** | **Watcher Settle Window Upper Limit**: Clamp `scripts/watch_telemetry.py` debounce settle window to 10.0 s maximum? | **Taken**: Yes, strictly clamp `settle_window` to `10.0` seconds. | Enforced in Finding C2 and Backlog Row 2 (`fix/watcher-settle-clamp`). |
| **2** | **JavaScript File Budget Split**: Split `core.js`, `now.js`, and `sessions.js` into submodules under 800 lines? | **Taken**: Yes, extract domain submodules (`now-burst.js`, `sessions-filters.js`). | Enforced in Finding D2 and Backlog Row 5 (`refactor/js-budget-compliance`). |
| **3** | **Enforce Automated Playwright Gate for UI Milestones**: Mandate automated headless Playwright console error check in `VDONE.md` §B for all UI changes? | **Taken**: Yes, mandate headless Playwright gate. | Enforced in Finding D3 and Backlog Row 3 (`docs/m64-reopen-and-gate`). |

---

## 8. Appendix

### 8.1 Verification Scripts Executed
- **UI & Accessibility Runner**: Written to isolated scratch directory `<scratch-dir>/audit_ui.mjs` and executed via Node against `http://127.0.0.1:8089`. Captured screenshots across 6 tabs at `1440x900` and `375x812` in light and dark themes.
- **Interactive Verification**: Tested currency toggle persistence, filter selection reactivity, and turn inspector drawer rendering via `test_interactions.mjs`.

### 8.2 Challenger Adversarial Verification Table (Verbatim)

| Finding ID | Stated Claim | Verification Query | Status (EVIDENCED / GUESSED / CONTRADICTED) | Action Taken / Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **C1** | `dashboard/js/now.js` line 600 throws `ReferenceError: cid is not defined` because `const cid` was deleted while being referenced in template literal `${cid}`, `${turns}`, `${tok}`, `${model}`, halting dashboard execution at `renderNowView()`. | `git diff dashboard/js/now.js` lines 583-615; inspect Playwright runner console/page errors in `task-110.log`. | **EVIDENCED** | **Keep.** Diff confirms `tok`, `turns`, `cid`, and `model` declarations were deleted at line 586 while remaining in template literal at lines 600–612. Playwright execution captures `pageErrors: ["cid is not defined"]`. |
| **C2** | In `scripts/watch_telemetry.py` lines 180-184, `DebounceController.update_settle_window(last_duration)` has no upper clamp, which set `settle_window = 26693.34` seconds (7.41 hours) and `max_delay = 53386.68` seconds based on the last export log in `~/Library/Logs/Antigravity/telemetry_watcher.stdout.log`, freezing the daemon from exporting for >8 hours. | Inspect `scripts/watch_telemetry.py:180-184`; `tail -n 20 ~/Library/Logs/Antigravity/telemetry_watcher.stdout.log`; `stat -f "%Sm" dashboard/data.js` vs `date`. | **EVIDENCED** | **Keep.** `self.settle_window = max(self.base_settle_window, float(last_duration))` has no upper bound. Log line `[*] Export complete: export took 26693.34s (adaptive settle window: 26693.34s)` set `settle_window = 7.41h` and `max_delay = 14.8h`. Last mtime of `data.js` was 06:34:58 BST, freezing updates for >8.3 hours. |
| **C3 (original)** | Background LaunchAgent daemon (PID 64248) has been running since yesterday evening and is executing stale in-memory Python bytecode, unaware of working-tree changes to `antigravity_telemetry` and `src/vault.py`. | `ps -p 64248 -o pid,lstart,command`; `stat antigravity_telemetry/parser.py src/vault.py`; grep `agent_name` in `dashboard/data.js`. | **CONTRADICTED** | **Drop / Correct claim.** PID 64248 started at `22:11:54 BST` (Sep 21), whereas `parser.py` (21:59:29) and `vault.py` (22:01:30) were modified *before* start. Daemon loaded these changes and emitted 511 `agent_name` records and `agent_attribution` into `dashboard/data.js` before 06:34 BST. Daemon freeze is entirely due to C2, not stale bytecode. |
| **C4** | Running unit test suite `python3 -m unittest discover -s tests` emits a ResourceWarning for an unclosed SQLite connection at `src/git_timeline.py:169`. | `python3 -W error::ResourceWarning -m unittest discover -s tests`; inspect `src/git_timeline.py:169`. | **EVIDENCED** | **Keep, but qualify.** Test suite emits: `ResourceWarning: unclosed database in <sqlite3.Connection object ...>` with traceback pointing to `src/git_timeline.py:169` (`events.append((epoch, from_b, to_b))`). Qualify that line 169 is the GC finalization trigger point of an orphaned connection leaked by earlier tests, not an internal leak inside `git_timeline.py`. |
| **U1** | Automated axe-core scan on `dashboard/index.html` detects 6 critical `button-name` violations on desktop dock navigation buttons `#dock-tab-*` and 1-2 critical `select-name` violations. | Inspect `dashboard/index.html:70-110`; `dashboard/styles.css:1914-1917`; axe-core audit via Playwright on 1440x900. | **EVIDENCED** | **Keep.** In CSS, `.sidebar-dock .dock-nav-label` is set to `display: none;`. Buttons contain only SVG icons with `aria-hidden="true"` and no `aria-label`, triggering 6 `button-name` violations on all desktop tabs. Tab swarms has 2 `select-name` violations (`#swarm-project-filter`, `#swarm-sort-select`), and Tab plan has 1 (`#sim-baseline-select`). |
| **U2** | Axe-core reports color-contrast violations across all tabs and themes, peaking at 238 failing nodes on the Swarms tab in dark theme. | Parse axe-core color-contrast violation results across 6 tabs, 2 viewports (1440x900, 375x812), and 2 themes (light, dark). | **EVIDENCED** | **Keep.** Measured counts match exactly: failures exist across all tabs in both light (15–110 nodes) and dark (21–238 nodes), peaking at exactly 238 nodes on `tab-swarms` dark theme. |
| **U3** | Mobile tap targets under 44px range from 5 to 24 across tabs at 375x812; desktop ranges from 18 to 37. | Inspect DOM bounding rects for interactive elements `< 44px` across all tabs and viewports. | **EVIDENCED** | **Keep.** Measured ranges match exactly: mobile (375x812) spans 5 (`tab-swarms`) to 24 (`tab-projects`); desktop (1440x900) spans 18 (`tab-swarms`) to 37 (`tab-projects`). |
| **D1** | `docs/HANDOVER.md` lists M64 as "Closed This Quarter" (`- **M64**: Agent persona telemetry & workflow attribution (feat/agent-persona-telemetry) — 2026-09-21`), but `git status --short` shows 23 modified files and 2 untracked files on `feat/agent-persona-telemetry`. | `grep -n "M64" docs/HANDOVER.md`; `git branch --show-current`; `git status --short`. | **EVIDENCED** | **Keep.** `docs/HANDOVER.md` line 198 prematurely lists M64 as closed while on branch `feat/agent-persona-telemetry` with 23 uncommitted modified files and 2 untracked files in the working tree. |
| **D2** | Three JS files exceed the 800-line budget: `dashboard/js/core.js` (921 lines), `dashboard/js/now.js` (864 lines), and `dashboard/js/sessions.js` (861 lines). | `wc -l dashboard/js/core.js dashboard/js/now.js dashboard/js/sessions.js`. | **EVIDENCED** | **Keep, adjust 1 number.** Measured line counts are: `core.js` = 921, `now.js` = 864, `sessions.js` = 860. Update stated count for `sessions.js` from 861 to 860. All three violate the 800-line budget. |
| **D3** | `VDONE.md` milestone gates for M64 (B1–B5) only test Python backend imports and unit suites, with 0 browser rendering or frontend interaction gates, allowing an uncaught JavaScript error to ship past gates. | Inspect `VDONE.md` Section B lines 11–17. | **EVIDENCED** | **Keep.** Gates B1–B5 verify only Python modules via `python3 -c "import ..."` and unit test suites. Despite modifying 5 frontend files, no browser rendering or Playwright test gate was defined, directly allowing the C1 `ReferenceError` to slip past gates. |
