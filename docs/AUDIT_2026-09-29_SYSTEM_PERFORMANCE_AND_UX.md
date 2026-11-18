# System Performance, DOM Architecture & UX Audit — 29 Sep 2026

**Scope**: Entire repository (`src/`, `scripts/`, `dashboard/`, `tests/`, `antigravity_telemetry/`, `macos/`) at commit `1256195` on `main`.  
**Method**: Evaluated all 16 scripts, 22 library modules, 12 dashboard frontend JavaScript modules, and package modules. Executed 365 unit tests, 10 active VDONE acceptance gates, and quality gate commands. Analyzed dependency topology, SQLite connection semantics, file write atomicity, exception patterns via AST scans, and design tokens across 37 repository files. Benchmarked cycle latencies, test suite subprocess discovery recursion, and profiled export phases against the live 2.82 GB vault and 543 upstream conversation databases. Evaluated headless browser runtime smoke and axe-core accessibility across Desktop (1440×900) and Mobile (375×812) viewports in Light and Dark themes. Verified Swift 6 companion app compilation. Adversarially stress-tested all claims with the read-only Challenger subagent. No application code modified (Zero Mutation).  
**Audience**: Repository owner and maintaining implementer agent.

---

## 0. Executive Summary

The offline core mechanics (protobuf decoding, read-only upstream SQLite connections, and isolated unit test pass rates) remain robust: all 365 tests pass, and all active VDONE acceptance gates pass. The Swift menu bar companion (`macos/AntigravityBar`) builds cleanly with zero errors or warnings in 22.02s.

However, the repository suffers from test discovery recursion overhead, unclosed SQLite connection leaks, extreme initial DOM bloat, responsive header badge truncation, and intentional accessibility test masking:

| Area | Verdict | Headline |
| :--- | :--- | :--- |
| **Backend & Test Suite** | **HIGH: Recursive Test Discovery Blowout** | The 365-test unit suite runs in **40.5s** standalone, but inflates to **82.6s–149.3s** under discovery because `tests/test_vdone_gates.py:270-302` re-executes `unittest discover` for Gate A1, running the suite twice. Unclosed connection leak (`ResourceWarning`) in `export_dashboard.py:574`. |
| **DOM & UI Performance** | **HIGH: 8,180 Initial DOM Elements from Eager Multi-Tab Rendering** | The dashboard renders all 6 tab views eagerly on initial load. `#view-projects` generates **3,409 DOM nodes** and `#view-swarms` generates **1,828 nodes** before any user interaction, causing initial DOM node count to breach the 1,500 target by 5.4×. |
| **UX & Responsive Layout** | **MEDIUM: All 5 Desktop Header Badges Truncated with Ellipsis at 1440×900** | Due to `flex-wrap: nowrap` and `flex-shrink: 1` in `dashboard/styles.css:320-335`, all 5 header badges suffer text clipping (Billing badge requires 268px, clipped to 196px; Freshness requires 206px, clipped to 153px). |
| **Accessibility & Gates** | **MEDIUM: Intentional Axe Rule Suppression in E2E Suite** | `e2e/a11y.spec.js:58-60` explicitly disables `color-contrast` and `scrollable-region-focusable`. Re-enabling them exposes 5 serious WCAG AA contrast failures in Light Mode and keyboard traps in mobile table views. |
| **Exception Hygiene** | **MEDIUM: 33 Silent `except Exception: pass` Blocks & Active Bug** | AST scan reveals 33 generic exception-swallowing handlers. `antigravity_telemetry/__init__.py:47` returns `None` on failure, causing `TypeError: argument of type 'NoneType' is not iterable` in downstream truncation threshold queries. |

**Top five actions, in order**:
1. **Row 1 (C1 / P0)**: Skip recursive discovery inside `tests/test_vdone_gates.py` when already running under `unittest`, restoring test duration to ~40s (< 90s ceiling).
2. **Row 2 (C2 / P1)**: Fix unclosed SQLite connection leak in `scripts/export_dashboard.py:574` via `try...finally: vconn.close()`.
3. **Row 5 (U1 / P1)**: Implement lazy tab rendering in `dashboard/js/core.js` to defer `#view-projects` and `#view-swarms` until tab activation, cutting initial DOM elements from 8,180 to ~500.
4. **Row 6 (U2 / P1)**: Calibrate header badge layout in `dashboard/styles.css` with wrapping or responsive priority hiding to eliminate text truncation on 1440×900 desktop screens.
5. **Row 7 (U3 / P1)**: Calibrate Light Mode text contrast and re-enable `color-contrast` in `e2e/a11y.spec.js`.

**Blunt version for the owner**: The test suite takes twice as long as it needs to (nearly 2.5 minutes under load) because one of the acceptance tests runs the entire test suite inside itself. The dashboard page is sluggish on initial boot because it builds thousands of hidden HTML rows for tabs you haven't clicked yet (Projects and Swarms alone inject over 5,200 elements). On a standard desktop monitor, every single badge in your top header has its text cut off with an ellipsis. Finally, the automated accessibility tests were secretly turned off for color contrast and mobile scrolling to make the test suite pass.

---

## 1. Measured Facts

### 1.1 Detected Parameters (§0.2)
```text
AUDIT_TIER        DEEP (Full Repository & UX Audit)                        (sure: explicit request)
GOVERNANCE_DOCS   AGENTS.md CLAUDE.md CONTRIBUTING.md VDONE.md README.md docs/HANDOVER.md (sure: 6 found)
PREVIOUS_AUDIT    docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md           (sure: head -1)
TEST_CMD          python3 -m unittest discover -s tests                    (sure: AGENTS.md §1)
LINTER_CMD        git diff --check && python3 -m unittest tests/test_docs_integrity.py (sure: AGENTS.md §1)
GATE_FILE         VDONE.md                                                 (sure: 10 active gates)
SAFETY_RULES      AGENTS.md §1: upstream *.db opened ?mode=ro; host path protection (sure)
DECISION_LOG      docs/HANDOVER.md                                         (sure: §4)
CYCLE_CMD         python3 scripts/export_dashboard.py --dry-run --no-live-quota (sure: README:25)
OWNER_PROFILE     developer, blunt architecture findings                   (sure: confirmed)
OUTPUT            docs/AUDIT_2026-09-29_SYSTEM_PERFORMANCE_AND_UX.md       (sure)
```

### 1.2 Quantitative Measurements

| Fact | Measured Value | Exact Command / Reproduction Method |
| :--- | :--- | :--- |
| Active Git branch & cleanliness | `main` @ `1256195` (clean) | `git rev-parse --abbrev-ref HEAD; git status --short` |
| Tracked file count | 277 files | `git ls-files \| wc -l` |
| Repository `.git` size | 37.8 MB | `du -sh .git` |
| Test suite pass & direct duration | 365 passed in 40.52s | `_IN_VDONE_GATE_RUNNER=1 python3 -m unittest discover -s tests` |
| Test suite duration under normal discovery | 365 passed in 82.66s–149.29s | `python3 -m unittest discover -s tests` |
| Quality gate pass & duration | 12 passed in 0.65s | `python3 -m unittest tests/test_docs_integrity.py` |
| VDONE acceptance gates | 10 ran, 10 passed, 0 failed | Execution of VDONE gates A1–A5 and B1–B5 |
| Vault DB on-disk size | 2,822.4 MB (2.82 GB) | `du -m data/antigravity_vault.db` |
| Upstream DBs on host | 543 DBs, 542 WALs | `find ~/.gemini/antigravity/conversations -name '*.db' \| wc -l` |
| Steps archive row count | 120,448 rows | `sqlite3 data/antigravity_vault.db "SELECT count(*) FROM steps_archive"` |
| Initial DOM node count | 8,180 elements | `document.querySelectorAll('*').length` via Playwright at load |
| `#view-projects` DOM nodes | 3,409 elements | Playwright node count inside `#view-projects` |
| `#view-swarms` DOM nodes | 1,828 elements | Playwright node count inside `#view-swarms` |
| `#view-sessions` DOM nodes | 1,240 elements | Playwright node count inside `#view-sessions` (paged to 25 rows) |
| Clipped header badges at 1440×900 | 5 of 5 badges clipped | Playwright measurement `scrollWidth > clientWidth` |
| Axe accessibility violations (masked) | 0 violations reported | `npx playwright test e2e/a11y.spec.js` |
| Axe accessibility violations (unmasked) | 7 serious violations (5 contrast, 2 mobile) | `run_axe.mjs` with rules re-enabled |
| Bare `except Exception: pass` count | 33 instances | AST scan for `ast.ExceptHandler` with `body=[ast.Pass]` |
| Design token violations | 174 violations (9 html, 121 css, 44 js) | `scratch/audit_design_tokens.py` |
| Swift companion app compilation | Clean build in 22.02s (0 warnings) | `swift build --package-path macos/AntigravityBar` |
| Version tags vs manifest | Git `v2.24.0`, pyproject `2.24.0`, package `2.24.0` | `git describe --tags; grep version pyproject.toml package.json` |

---

## 2. Scorecard Against Previous Audits

Evaluated against `AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md` (Rows 1–11):

| Previous Finding / Recommendation | Status | Evidence |
| :--- | :--- | :--- |
| **Row 1 (C1)**: Filter DBs by mtime & batch queries in `sync_conversations_to_vault` | **Done** | `src/vault.py:590-620` implements `st_mtime` filtering and `--force-full-scan` support (M67). |
| **Row 2 (C2)**: Gate vault sync with `not dry_run` in `scripts/export_dashboard.py` | **Done** | `scripts/export_dashboard.py:530` gates sync calls with `if not is_custom_dir and not dry_run:` (M68). |
| **Row 3 (C3)**: Thread lock & unique tempfile prefix in `update_watcher_heartbeat` | **Done** | `scripts/watch_telemetry.py:40-85` uses module `threading.Lock` and random nonce (M69). |
| **Row 4 (C4)**: Add explicit `timeout=` across 28 subprocess calls | **Done** | All subprocess calls across `src/` and `scripts/` specify explicit `timeout=` (M70). |
| **Row 5 (D1)**: Align version across Git tag, `pyproject.toml`, and `package.json` | **Done (M71)** | All three were aligned to `2.24.0` (M71), though subsequent milestones M72–M76 drifted. |
| **Row 6 (C5)**: Atomic file writes for `exhaustion_ledger.json` & demo showcase | **Done** | Staging via `.tmp` and `os.replace` implemented across log reader and demo builder (M72). |
| **Row 7 (C6)**: Replace silent `except Exception: pass` with targeted logging | **Partly Done** | M74 addressed several modules, but 33 instances remain in active pipelines. |
| **Row 8 (C7)**: Decouple circular import between `src/vault.py` and `src/weekly_trends.py` | **Done** | Decoupled via `src/vault_schema.py` in Milestone 75. |
| **Row 9 (C8)**: Import `get_model_rates` directly in `src/simulator.py` from pricing | **Done** | Redundant fallback functions deleted; simulator imports from `src.aggregator_pricing` (M73). |
| **Row 10 (C9)**: Add test harnesses for `quota_regression.py` and GitHub guardrails | **Done** | Unit tests added in `tests/test_quota_regression.py` and `tests/test_setup_github_guardrails.py` (M76). |
| **Row 11 (U1)**: Calibrate light mode badge color contrast in `dashboard/styles.css` | **Partly Done** | Primary badges calibrated, but `.highlight-camel`, `#a78bfa`, and mobile scrollable wrappers remain non-compliant. |

---

## 3. Code & Correctness Findings

### Finding C1: Circular Subprocess Discovery in `test_vdone_gates.py` & Test Suite Inflation
- **What happens**: `VDONE.md:5` contains:
  ```text
  A1 Unit suite CHECK python3 -m unittest discover -s tests -p 'test_*.py' EXPECT OK, < 90 s
  ```
  When the top-level test runner executes `python3 -m unittest discover -s tests`, it runs `tests/test_vdone_gates.py`. In `test_vdone_gates_execution()`, line 250 checks `_IN_VDONE_GATE_RUNNER`. Because it is unset in the outer process, Gate A1 executes `subprocess.run(["python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])`. The entire 365-test suite executes twice sequentially.
- **Evidence**:
  - Direct execution without recursion (`_IN_VDONE_GATE_RUNNER=1`): **40.520s**.
  - Normal discovery execution: **82.664s** on idle machine, **149.29s** under I/O pressure.
  - Subprocess overhead alone: **42.144s**.
- **Why it matters**: Inflates test duration by over 100%, causing false alarms and breaching the strict GADR-002 `< 90s` ceiling under normal multitasking.
- **Intended behavior**: Unit test discovery should run each test exactly once. Gate A1 should not spawn recursive discovery when already executing inside `unittest`.
- **Concrete fix**: In `tests/test_vdone_gates.py:270-302`, check `if "unittest" in sys.argv[0] or "discover" in sys.argv:` and skip Gate A1 subprocess execution with `self.skipTest("Skipping Gate A1 recursive discovery within unittest runner")`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import time, subprocess; t0=time.time(); res=subprocess.run(['python3', '-m', 'unittest', 'tests/test_vdone_gates.py'], capture_output=True, text=True); dt=time.time()-t0; assert res.returncode==0 and dt < 25, f'Too slow: {dt}s'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 1 hour.
- **Branch**: `fix/test-vdone-gates-recursion`
- **Priority**: P0.

---

### Finding C2: Unclosed SQLite Database Connection Leak in `scripts/export_dashboard.py:574`
- **What happens**: `scripts/export_dashboard.py:574` opens the vault database using Python's context manager syntax:
  ```python
  with sqlite3.connect(f"file:{vault_file}?mode=ro", uri=True) as vconn:
  ```
  In Python's `sqlite3` module, the `Connection` context manager manages *transactions* (`commit`/`rollback`), not connection lifetime; it does **not** close the database upon exiting the `with` block.
- **Evidence**: Running `python3 -W error::ResourceWarning -m unittest tests/test_export_dashboard.py` emits:
  ```text
  Exception ignored while finalizing database connection <sqlite3.Connection object at ...>:
  ResourceWarning: unclosed database in <sqlite3.Connection object at ...>
  ```
- **Why it matters**: Leaks SQLite file descriptors and locks, triggering resource warnings in strict test environments.
- **Intended behavior**: Connections must be explicitly closed in a `finally` block or wrapped in `contextlib.closing`.
- **Concrete fix**: Wrap connection lifetime in `try...finally: vconn.close()`.
- **Executable gate**:
  - `CHECK`: `python3 -W error::ResourceWarning -m unittest tests/test_export_dashboard.py`
  - `EXPECT`: `OK` (zero ResourceWarning)
- **Effort**: 30 minutes.
- **Branch**: `fix/export-connection-leak`
- **Priority**: P1.

---

### Finding C3: Missing Connection Cleanup & Concurrency Settings in `src/vault.py` and `src/log_reader.py`
- **What happens**:
  - In `src/vault.py:1248-1284` (`get_vault_truncation_markers`) and `1302-1350` (`scan_conversation_truncation`), `conn.close()` is located at the tail of the `try:` block without a `finally:` block. If cursor operations raise an exception or hit early returns (`:1315`, `:1321`), `conn.close()` is bypassed.
  - In `src/log_reader.py:98-113` (`reconstruct_ledger_from_vault`), `conn = sqlite3.connect(...)` lacks `try...finally: conn.close()` and omits GADR-013 concurrency parameters (`timeout=60.0` and `PRAGMA busy_timeout = 60000;`).
- **Evidence**: Code inspection of lines cited above.
- **Why it matters**: Violates GADR-013 / ADR-081 SQLite Concurrency Resilience and leaks open database connections on unexpected exceptions.
- **Intended behavior**: All SQLite connection lifetimes must be protected with `try...finally: conn.close()`, and configure `timeout=60.0`.
- **Concrete fix**: Refactor connection blocks in `src/vault.py` and `src/log_reader.py` to use `try...finally: if conn: conn.close()`, and add GADR-013 timeouts.
- **Executable gate**:
  - `CHECK`: `python3 -W error::ResourceWarning -m unittest tests/test_vault.py`
  - `EXPECT`: `OK`
- **Effort**: 45 minutes.
- **Branch**: `fix/vault-connection-closure-hardening`
- **Priority**: P1.

---

### Finding C4: 33 Silent `except Exception: pass` Blocks & Active Bug in Model Census
- **What happens**:
  - An AST scan identifies 33 `except Exception: pass` blocks across production code.
  - In `antigravity_telemetry/__init__.py:47`, `load_model_census()` catches all exceptions and silently returns `None`:
    ```python
    except Exception:
        return None
    ```
    Callers such as `get_model_truncation_threshold()` assume a dictionary is returned and attempt iteration, crashing with `TypeError: argument of type 'NoneType' is not iterable` when `models.json` cannot be parsed.
- **Evidence**: AST audit script output and direct execution trace.
- **Why it matters**: Silently swallows file corruption or schema errors and causes hard-to-trace downstream crashes.
- **Intended behavior**: Catch specific exceptions (`(OSError, json.JSONDecodeError)`), log to `sys.stderr`, and return an empty fallback dictionary `{}` rather than `None`.
- **Concrete fix**: Fix fallback in `antigravity_telemetry/__init__.py:47` and replace remaining `except Exception: pass` instances in `antigravity_telemetry/` and `src/` with explicit types and targeted logging.
- **Executable gate**:
  - `CHECK`: `python3 -c "import antigravity_telemetry; res=antigravity_telemetry.get_model_truncation_threshold('non_existent_model'); assert res == 1000000; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 1 hour.
- **Branch**: `fix/model-census-exception-handling`
- **Priority**: P1.

---

### Finding C5: Redundant Dual Vault Synchronization in Watcher Daemon
- **What happens**: In `scripts/watch_telemetry.py:422-430`, triggering an export calls `sync_vault_telemetry()` (which invokes `sync_conversations_to_vault()`), immediately followed by `export_telemetry()`, which internally calls `sync_conversations_to_vault()` again at `scripts/export_dashboard.py:538`.
- **Evidence**: Execution trace of `watch_telemetry.py:422-430` and `export_dashboard.py:538`.
- **Why it matters**: Performs two consecutive full vault synchronization scans of all 543 SQLite conversation databases on every single file change event, doubling I/O and processor load.
- **Intended behavior**: Vault synchronization should run exactly once per export cycle.
- **Concrete fix**: Remove the redundant `sync_vault_telemetry()` call from `watch_telemetry.py:423`, delegating vault sync entirely to `export_telemetry()`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import inspect, scripts.watch_telemetry; src=inspect.getsource(scripts.watch_telemetry.watch_loop); assert src.count('sync_conversations_to_vault') == 0, 'Direct sync_conversations_to_vault call in watcher loop should be removed'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 45 minutes.
- **Branch**: `perf/deduplicate-watcher-vault-sync`
- **Priority**: P2.

---

## 4. UI and UX Findings

### Finding U1: Extreme Initial DOM Node Bloat (8,180 Nodes vs. 1,500 Target)
- **What happens**: On initial dashboard load, the DOM contains **8,180 elements** (exceeding Google Lighthouse and web performance budgets by 5.4×). All six tab views (`#view-now`, `#view-sessions`, `#view-projects`, `#view-swarms`, `#view-billing`, `#view-plan`) are rendered eagerly into the DOM on initial boot, even though the user only views `#view-now`.
- **Evidence**: Playwright node distribution:
  - `#view-projects`: **3,409 nodes** (67 project/branch rows with ~50 nested nodes each)
  - `#view-swarms`: **1,828 nodes**
  - `#view-sessions`: **1,240 nodes** (paged to 25 rows)
  - Shell & remaining views: **1,703 nodes**
- **Why it matters**: Severe initial DOM bloat degrades first-load paint performance, increases memory footprint, and slows down style recalculations on mobile devices.
- **Intended behavior**: Tabs should render lazily when activated by the user. Initial DOM should remain under 1,500 elements.
- **Concrete fix**: In `dashboard/js/core.js`, defer `renderProjectsView()`, `renderSwarmsView()`, and `renderBillingView()` until their respective tab navigation button is clicked.
- **Executable gate**:
  - `CHECK`: `node -e "const { chromium } = require('playwright'); (async () => { const browser = await chromium.launch(); const page = await browser.newPage(); await page.goto('http://localhost:8091/index.html'); const count = await page.evaluate(() => document.querySelectorAll('*').length); await browser.close(); if (count > 2000) throw new Error('DOM count too high: ' + count); console.log('OK, DOM count: ' + count); })();"`
  - `EXPECT`: `OK, DOM count: <= 1500`
- **Effort**: 1.5 hours.
- **Branch**: `perf/lazy-tab-rendering`
- **Priority**: P1.

---

### Finding U2: Desktop Header Badge Text Truncation at 1440×900 Viewport
- **What happens**: At the standard desktop viewport (`1440x900`), all 5 header status badges clip text with ellipsis.
- **Evidence**: Playwright measurement of badge dimensions:
  - `#billing-cycle-badge`: clientWidth 196px vs scrollWidth 268px (**clipped -72px**)
  - `#data-freshness-badge`: clientWidth 153px vs scrollWidth 206px (**clipped -53px**)
  - `#sub-status-badge`: clientWidth 106px vs scrollWidth 141px (**clipped -35px**)
  - `#btn-open-plan-manager`: clientWidth 99px vs scrollWidth 130px (**clipped -31px**)
  - `#session-count-badge`: clientWidth 74px vs scrollWidth 96px (**clipped -22px**)
- **Why it matters**: Key quota, billing, and freshness information is unreadable on standard desktop laptops and monitors.
- **Intended behavior**: Badges must remain fully legible without text clipping on standard desktop viewports.
- **Concrete fix**: In `dashboard/styles.css:320-335`, allow `flex-wrap: wrap` or set priority visibility to hide secondary badges (`#session-count-badge`) on widths below 1600px, and set `flex-shrink: 0` on critical status badges.
- **Executable gate**:
  - `CHECK`: `node -e "const { chromium } = require('playwright'); (async () => { const browser = await chromium.launch(); const page = await browser.newPage({ viewport: { width: 1440, height: 900 } }); await page.goto('http://localhost:8091/index.html'); const clipped = await page.evaluate(() => { const badges = Array.from(document.querySelectorAll('header .badge, header #btn-open-plan-manager')); return badges.filter(b => b.scrollWidth > b.clientWidth).map(b => b.id || b.className); }); await browser.close(); if (clipped.length > 0) throw new Error('Clipped badges: ' + clipped.join(', ')); console.log('OK'); })();"`
  - `EXPECT`: `OK`
- **Effort**: 1 hour.
- **Branch**: `ui/header-badge-clipping-fix`
- **Priority**: P1.

---

### Finding U3: Axe-Core Light Mode Color Contrast Violations & Test Masking
- **What happens**: `e2e/a11y.spec.js:58-60` intentionally suppresses:
  ```javascript
  const results = await new AxeBuilder({ page })
    .disableRules(['color-contrast', 'scrollable-region-focusable'])
    .analyze();
  ```
  When unmasked, Axe reports 5 serious WCAG AA contrast failures in Light Theme:
  - `tr > .highlight-camel` (contrast ratio **2.6:1** against `#F8F6F2`, required: 4.5:1)
  - `#models-tbody td:nth-child(7) > span` (`#a78bfa` contrast ratio **3.1:1**)
  - `#kpi-uncached-tokens` and `.badge-subagent-pill.badge-agent`
- **Evidence**: Execution of `run_axe.mjs` with rules re-enabled.
- **Why it matters**: Fails WCAG 2.1 AA accessibility compliance and masks defects from the automated test suite.
- **Intended behavior**: All text elements in Light Theme must maintain $\ge 4.5:1$ contrast ratio, and the automated test suite must run without rule suppression.
- **Concrete fix**: Darken light-theme accent variables (e.g. `--camel-600: #855227`) and remove `.disableRules(['color-contrast', ...])` from `e2e/a11y.spec.js`.
- **Executable gate**:
  - `CHECK`: `npx playwright test e2e/a11y.spec.js`
  - `EXPECT`: `passed`
- **Effort**: 1 hour.
- **Branch**: `ui/light-theme-contrast-calibration`
- **Priority**: P1.

---

### Finding U4: Mobile Scrollable Region Focusability Violations
- **What happens**: On mobile viewports (`375x812`), `.tab-nav` and `.table-scroll-wrapper` overflow horizontally to enable touch scrolling, but lack `tabindex="0"`. Keyboard and screen-reader users cannot focus or scroll the tables.
- **Evidence**: Axe-core reports serious `scrollable-region-focusable` violation when unmasked.
- **Why it matters**: Violates WCAG 2.1 Success Criterion 2.1.1 (Keyboard Accessible) on mobile and responsive views.
- **Intended behavior**: Scrollable table containers must be focusable with keyboard navigation.
- **Concrete fix**: Add `tabindex="0"` and `aria-label="Scrollable table view"` to scroll wrappers in `dashboard/styles.css` and `dashboard/index.html`. Remove rule suppression from `e2e/a11y.spec.js`.
- **Executable gate**:
  - `CHECK`: `npx playwright test e2e/a11y.spec.js`
  - `EXPECT`: `passed`
- **Effort**: 30 minutes.
- **Branch**: `a11y/mobile-scrollable-regions`
- **Priority**: P2.

---

## 5. Ceremony and Documentation Findings

### Finding D1: Banned `border-radius: 9999px` in HTML and CSS
- **What happens**: `border-radius: 9999px` is hardcoded in `dashboard/index.html:367-368` (runway progress bar) and `dashboard/styles.css:397, 459, 720, 729` (`.badge`, `.badge-agent`), violating the strict anti-generic border radius directive of the Eneas Design Standard.
- **Evidence**: `scratch/audit_design_tokens.py` scan.
- **Why it matters**: Violates repository design standards requiring deliberate `--radius-card` (6px) or `--radius-pill` (4px).
- **Intended behavior**: All border radii must use tokens from the canonical design system.
- **Concrete fix**: Replace `9999px` with `var(--radius-card, 6px)` across `dashboard/index.html` and `dashboard/styles.css`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import pathlib; text = pathlib.Path('dashboard/styles.css').read_text() + pathlib.Path('dashboard/index.html').read_text(); assert '9999px' not in text, 'Found banned 9999px radius'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 30 minutes.
- **Branch**: `ui/anti-generic-radius-compliance`
- **Priority**: P2.

---

### Finding D2: 44 Raw Hex Color Values in Dashboard JavaScript Modules
- **What happens**: 44 raw hex values are embedded directly in `dashboard/js/billing.js`, `now-burst.js`, `sessions.js`, and `swarms.js` rather than referencing CSS design tokens.
- **Evidence**: Regex scan of `dashboard/js/*.js` for `#[0-9a-fA-F]{3,8}`.
- **Why it matters**: Hardcodes colors in JavaScript, breaking dynamic theme synchronization and violating tokenization standards.
- **Intended behavior**: Colors rendered by JS must derive from `getComputedStyle(document.documentElement).getPropertyValue(...)` or semantic CSS classes.
- **Concrete fix**: Refactor raw hex values in `dashboard/js/*.js` to use CSS custom properties.
- **Executable gate**:
  - `CHECK`: `python3 -c "import pathlib, re; js_files = list(pathlib.Path('dashboard/js').glob('*.js')); raw_hex = [f.name for f in js_files if re.search(r'#[0-9a-fA-F]{3,8}\b', f.read_text())]; assert len(raw_hex) == 0, f'Raw hex in {raw_hex}'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 1.5 hours.
- **Branch**: `ui/js-design-tokens-alignment`
- **Priority**: P2.

---

### Finding D3: Milestone Release & Version Manifest Parity Drift
- **What happens**: Git tag on `HEAD` is `v2.24.0` (commit `abae4c9`, Milestone 67), and `package.json:3` and `pyproject.toml:7` remain pinned at `"2.24.0"`, despite 9 subsequent milestones (M68–M76) landing on `main`.
- **Evidence**: `git describe --tags` outputs `v2.24.0-25-g1256195`.
- **Why it matters**: Violates `AGENTS.md` §1 semantic version tagging strategy and creates release traceability drift.
- **Intended behavior**: Version manifests must stay synchronized with milestone tags.
- **Concrete fix**: Bump `package.json` and `pyproject.toml` to `"2.25.0"` and tag `main` with `v2.25.0`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import json, tomllib, pathlib, subprocess; tag=subprocess.check_output(['git','describe','--tags','--abbrev=0']).decode().strip().lstrip('v'); py_ver=tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version']; js_ver=json.loads(pathlib.Path('package.json').read_text())['version']; assert tag==py_ver==js_ver=='2.25.0', f'Desync: tag={tag}, py={py_ver}, js={js_ver}'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 30 minutes.
- **Branch**: `chore/version-manifest-sync-v225`
- **Priority**: P2.

---

### Finding D4: Plan Manager & Core Script Line Limit Budget Warnings
- **What happens**:
  - `dashboard/js/plan-manager.js`: **796 lines** (4 lines from the strict 800-line budget of ADR-066).
  - `dashboard/js/core.js`: **766 lines** (34 lines from 800).
- **Evidence**: Line counts measured with `wc -l`.
- **Why it matters**: Any non-trivial feature added to plan management will breach ADR-066 and trigger CI failure.
- **Intended behavior**: Keep modules under 750 lines through proactive decomposition.
- **Concrete fix**: Split `plan-manager.js` into `plan-state.js` and `plan-ui.js`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import pathlib; max_lines = max(len(p.read_text().splitlines()) for p in pathlib.Path('dashboard/js').glob('*.js')); assert max_lines <= 750, f'Max lines {max_lines} > 750'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 1.5 hours.
- **Branch**: `refactor/plan-manager-modular-split`
- **Priority**: P3.

---

## 6. Prioritised Backlog

| # | Item | Type | Priority | Effort | Branch | Blocking Decision |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Row 1** | Fix circular `unittest discover` subprocess in `tests/test_vdone_gates.py` (C1) | Performance / Tests | P0 | 1 h | `fix/test-vdone-gates-recursion` | Decision 1 |
| **Row 2** | Fix unclosed SQLite connection leak in `scripts/export_dashboard.py:574` (C2) | Bug Fix / Exporter | P1 | 30 m | `fix/export-connection-leak` | None |
| **Row 3** | Harden SQLite connection closures in `src/vault.py` and `src/log_reader.py` (C3) | Robustness / Vault | P1 | 45 m | `fix/vault-connection-closure-hardening` | None |
| **Row 4** | Fix model census `TypeError` in `antigravity_telemetry` & typed exceptions (C4) | Quality / Package | P1 | 1 h | `fix/model-census-exception-handling` | None |
| **Row 5** | Implement lazy tab rendering to drop initial DOM from 8,180 to ~500 nodes (U1) | Performance / UI | P1 | 1.5 h | `perf/lazy-tab-rendering` | Decision 2 |
| **Row 6** | Fix desktop header badge text clipping on 1440x900 viewport (U2) | UI / Ergonomics | P1 | 1 h | `ui/header-badge-clipping-fix` | None |
| **Row 7** | Calibrate light mode color contrast and unmask `e2e/a11y.spec.js` (U3) | Accessibility / UI | P1 | 1 h | `ui/light-theme-contrast-calibration` | None |
| **Row 8** | Deduplicate redundant `sync_conversations_to_vault` in watcher daemon (C5) | Performance / Daemon| P2 | 45 m | `perf/deduplicate-watcher-vault-sync` | None |
| **Row 9** | Add `tabindex="0"` and `aria-label` to mobile scrollable tables (U4) | Accessibility / A11y| P2 | 30 m | `a11y/mobile-scrollable-regions` | None |
| **Row 10** | Replace banned `border-radius: 9999px` with `--radius-card` in HTML & CSS (D1) | Design System | P2 | 30 m | `ui/anti-generic-radius-compliance` | None |
| **Row 11** | Migrate 44 raw hex values in `dashboard/js/*.js` to CSS tokens (D2) | Design System | P2 | 1.5 h | `ui/js-design-tokens-alignment` | None |
| **Row 12** | Align version across `package.json` & `pyproject.toml` to `2.25.0` and tag (D3) | Release / Docs | P2 | 30 m | `chore/version-manifest-sync-v225` | Decision 3 |
| **Row 13** | Decompose `plan-manager.js` (796 lines) and `core.js` (766 lines) under limit (D4) | Refactor | P3 | 1.5 h | `refactor/plan-manager-modular-split` | None |

### Instructions for the Maintaining Implementer Agent
- Take the lowest-numbered open row in one session.
- Run `$TEST_CMD` and `$QUALITY_GATE_CMD` before making any edit.
- Respect the strict file scope: stage only files modified for that specific row.
- Ensure the tree remains 100% clean (`git status --short`).

---

## 7. Owner Decisions

| # | Question | Recommended Option | Consequence / Action Taken |
| :--- | :--- | :--- | :--- |
| **1** | How should Gate A1 in `tests/test_vdone_gates.py` be executed to prevent recursive discovery blowout? | **Skip Gate A1 subprocess when already running inside `unittest discover`.** | Prevents running the test suite twice in one pass, slashing test suite duration from 82.6s–149.3s to ~40.5s while preserving standalone CLI gate verification. Implemented in Row 1. |
| **2** | How should the 8,180 DOM node bloat be eliminated? | **Lazy tab activation (render views only when user clicks tab).** | Drops initial DOM node count by 93% without the complexity or scroll state bugs of virtual scrolling. Implemented in Row 5. |
| **3** | What version should be tagged for the Milestone 68–76 releases? | **Tag `v2.25.0` and bump manifests.** | Synchronizes git tags, `package.json`, and `pyproject.toml` to `2.25.0`. Implemented in Row 12. |

---

## 8. Appendix

### 8.1 Scripts Used During Audit
- `scratch/audit_design_tokens.py`: Scanned 37 repository files for un-tokenized raw hex and banned border-radii.
- `scratch/audit_exceptions.py`: AST scan identifying 33 generic exception handlers across production code.
- `scratch/profile_test_suite.py`: Benchmarked isolated vs recursive test execution latencies.
- `scratch/audit_ui.mjs` & `run_axe.mjs`: Headless Playwright runtime, DOM distribution, and axe-core accessibility scanners.

### 8.2 Challenger Verification Table (Verbatim)

| Finding ID | Stated Claim | Verification Query | Status (EVIDENCED / GUESSED / CONTRADICTED) | Action Taken / Verification Details |
| :--- | :--- | :--- | :--- | :--- |
| **C1** | `test_vdone_gates.py` re-executes `unittest discover`, running 365 tests twice in 149.3s | `python3 -m unittest discover -s tests` timing comparison | **EVIDENCED & CORRECTED** | **Keep.** Direct run is 40.52s; discover run is 82.66s–149.29s. Subprocess recursion verified at lines 270-302. |
| **C2** | `export_dashboard.py:574` leaks unclosed SQLite connection | `python3 -W error::ResourceWarning -m unittest tests/test_export_dashboard.py` | **EVIDENCED** | **Keep.** `ResourceWarning: unclosed database in <sqlite3.Connection object>` confirmed. |
| **C3** | `src/vault.py` and `src/log_reader.py` omit `try...finally: conn.close()` | AST inspection of SQLite connections in `vault.py` and `log_reader.py` | **EVIDENCED** | **Keep.** Missing cleanup and missing GADR-013 timeouts confirmed in `log_reader.py:98-113` and `vault.py:1248, 1302`. |
| **C4** | 33 silent `except Exception: pass` blocks; active `TypeError` bug in `antigravity_telemetry` | AST scan & execution test of `get_model_truncation_threshold` | **EVIDENCED** | **Keep.** AST scan confirmed 33 instances; active bug confirmed in `antigravity_telemetry/__init__.py:47`. |
| **C5** | Watcher daemon runs duplicate `sync_conversations_to_vault` scans | Code inspection of `scripts/watch_telemetry.py:423` and `export_dashboard.py:538` | **EVIDENCED** | **Keep.** Redundant double sync confirmed. |
| **U1** | DOM node bloat (8,180 nodes) caused by eager loading of Projects and Swarms tabs | Playwright element query on initial load per container ID | **EVIDENCED & CORRECTED** | **Keep with root cause correction.** Initial hypothesis of Sessions bloat disproved (Sessions is paged to 25 rows). Real cause is Projects (3,409 nodes) and Swarms (1,828 nodes) loaded eagerly. |
| **U2** | All 5 desktop header badges clipped with ellipsis at 1440×900 | Playwright measurement of clientWidth vs scrollWidth at 1440×900 | **EVIDENCED** | **Keep.** 100% reproducible; all 5 badges have `scrollWidth > clientWidth`. |
| **U3** | Axe color contrast violations masked in `e2e/a11y.spec.js:58-60` | Code inspection of `a11y.spec.js` and execution of Axe with rules unmasked | **EVIDENCED** | **Keep.** Intentional suppression of `color-contrast` and `scrollable-region-focusable` confirmed. |
| **U4** | Mobile scrollable table regions lack keyboard focusability | Axe scan on 375×812 viewport | **EVIDENCED** | **Keep.** `.tab-nav` and `.table-scroll-wrapper` lack `tabindex="0"`. |
| **D1** | Banned `border-radius: 9999px` present in `dashboard/index.html` and `styles.css` | Token scanner script on CSS/HTML | **EVIDENCED** | **Keep.** Present in `index.html:367` and `styles.css:397, 459, 720`. |
| **D2** | 44 raw hex values in `dashboard/js/*.js` | Regex search across `dashboard/js/` | **EVIDENCED** | **Keep.** Exactly 44 raw hex values across 4 JS files. |
| **D3** | Milestone release parity drift (M68–M76) on `main` | `git describe --tags` and manifest versions | **EVIDENCED** | **Keep.** Tag is `v2.24.0`, 25 commits behind `HEAD`. |
| **D4** | `plan-manager.js` at 796 lines approaching 800 ceiling | `wc -l dashboard/js/plan-manager.js` | **EVIDENCED** | **Keep.** Line count is 796 (4 lines from budget). |
