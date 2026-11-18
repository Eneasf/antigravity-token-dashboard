# Backend Architecture, Scripts & Data Pipelines Audit — 26 Sep 2026

**Scope**: Backend infrastructure, pipelines, daemons, and scripts (`scripts/`, `src/`, `antigravity_telemetry/`) at commit `526d71e` on `main`.  
**Method**: Evaluated all 16 scripts, 19 library modules, and telemetry package modules. Executed the 318-test unit suite, 10 active VDONE acceptance gates, and quality gate commands. Analyzed dependency topology, SQLite connection semantics, file write atomicity, exception patterns, and subprocess calls via AST scans. Benchmarked cycle latencies and profiled individual export phases against the live 2.81 GB local vault and 545 upstream conversation databases. Evaluated headless browser runtime smoke and axe-core accessibility across 1440×900 and 375×812 viewports. Adversarially stress-tested all claims with the read-only Challenger subagent. No application code modified (Zero Mutation).  
**Audience**: Repository owner and maintaining implementer agent.

---

## 0. Executive Summary

The offline core mechanics (pure-Python protobuf decoding, read-only upstream SQLite connections, and unit test pass rates) remain robust: all 318 tests pass in 74.9s, and all 10 VDONE acceptance gates pass.

However, the backend pipelines suffer from severe scaling degradation, concurrency race conditions, and host isolation violations:

| Area | Verdict | Headline |
| :--- | :--- | :--- |
| **Pipeline Latency** | **CRITICAL: 101.5s Export Duration Bottleneck** | `sync_conversations_to_vault` takes **88.9s** per cycle, opening 1,090 unindexed SQLite connections across 545 DBs, scanning 119k text rows with `LIKE`, and running 544 individual SQL queries in a loop. |
| **Host Isolation** | **CRITICAL: `--dry-run` Mutates Live Vault Database** | Running `scripts/export_dashboard.py --dry-run` executes `sync_*_to_vault` before line 639, mutating `data/antigravity_vault.db` and updating sync high-watermarks during dry runs. |
| **Concurrency & Locks** | **HIGH: In-Process Thread Race on Status File** | `update_watcher_heartbeat` writes to hardcoded `.{target}.tmp.{pid}` without a mutex; concurrent execution between daemon heartbeat thread and main watcher thread races on the same temp file. |
| **Subprocess Hygiene** | **HIGH: 100% Subprocess Calls Lack Timeouts (0/28)** | All 28 `subprocess.run` and `Popen` calls omit `timeout=`, risking permanent daemon or check hanging if commands like `lsof`, `ps`, or `export_dashboard.py` block. |
| **Code Structure & Error Handling** | **MEDIUM: 48 Silent `except Exception: pass` & Circular Module Cycle** | 48 general exception blocks silently swallow failures without logging; `src/vault.py` and `src/weekly_trends.py` form a circular dependency requiring deferred inline imports. |

**Top five actions, in order**:
1. **C1 (P0)**: Filter `db_paths` by `st_mtime` and batch distinct conversation queries in `sync_conversations_to_vault` to cut sync latency from 88.9s to <1.0s.
2. **C2 (P0)**: Guard vault synchronization calls in `scripts/export_dashboard.py:530` with `if not is_custom_dir and not dry_run:` to ensure dry-runs are 100% read-only.
3. **C3 (P1)**: Add a `threading.Lock` and random/thread-safe tempfile prefix in `scripts/watch_telemetry.py:40-82` to eliminate status file race conditions.
4. **C4 (P1)**: Add explicit `timeout=` parameters and `subprocess.TimeoutExpired` handling across all 28 subprocess invocations.
5. **C5 (P1)**: Replace in-place writes in `src/log_reader.py:201` (`exhaustion_ledger.json`) and `build_demo_showcase.py` with atomic write staging (`os.replace`).

**Blunt version for the owner**: The telemetry exporter is bogged down, taking over a minute and a half (101 seconds) every time it updates because it opens over a thousand database connections and re-scans 120,000 archived messages even if nothing changed. Running the exporter in "dry run" mode secretly writes to your permanent vault database. In addition, the background watcher thread and menu bar updater can collide when updating your status file because they write to the exact same temporary file name at the same time. Fixing this requires adding an mtime check so old files are skipped, preventing dry-runs from saving data, and putting a thread lock on status updates.

---

## 1. Measured Facts

### 1.1 Detected Parameters (§0.2)
```text
AUDIT_TIER        DEEP (Backend & Scripts Focus)                           (sure: explicit request)
GOVERNANCE_DOCS   AGENTS.md CLAUDE.md CONTRIBUTING.md VDONE.md README.md docs/HANDOVER.md (sure: 6 found)
PREVIOUS_AUDIT    docs/AUDIT_2026-09-24_STATUS_SELF_HEAL.md                (sure: head -1)
TEST_CMD          python3 -m unittest discover -s tests                    (sure: AGENTS.md §1)
LINTER_CMD        git diff --check && python3 -m unittest tests/test_docs_integrity.py (sure: AGENTS.md §1)
GATE_FILE         VDONE.md                                                 (sure: 10 active gates)
SAFETY_RULES      AGENTS.md §1: upstream *.db opened ?mode=ro; host path protection (sure)
DECISION_LOG      docs/HANDOVER.md                                         (sure: §4)
CYCLE_CMD         python3 scripts/export_dashboard.py --dry-run --no-live-quota (sure: README:25)
OWNER_PROFILE     developer, blunt architecture findings                   (sure: confirmed)
OUTPUT            docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md           (sure)
```

### 1.2 Quantitative Measurements

| Fact | Measured Value | Exact Command / Reproduction Method |
| :--- | :--- | :--- |
| Active Git branch & cleanliness | `main` @ `526d71e` (clean) | `git rev-parse --abbrev-ref HEAD; git status --short` |
| Tracked file count | 272 files | `git ls-files \| wc -l` |
| Repository `.git` size | 37 MB | `du -sh .git` |
| Test suite pass & duration | 318 passed in 74.9s | `python3 -m unittest discover -s tests` |
| Quality gate pass & duration | 11 passed in 3.96s | `git diff --check && python3 -m unittest tests/test_docs_integrity.py` |
| VDONE acceptance gates | 10 ran, 10 passed, 0 failed | Execution of VDONE gates A1–A5 and B1–B5 |
| Vault DB on-disk size | 2,812.7 MB (2.81 GB) | `du -m data/antigravity_vault.db` |
| Upstream DBs on host | 545 DBs, 544 WALs (2.63 GB) | `find ~/.gemini/antigravity/conversations -name '*.db' \| wc -l` |
| Steps archive row count | 119,941 rows | `sqlite3 data/antigravity_vault.db "SELECT count(*) FROM steps_archive"` |
| Total export cycle duration | 101.49 s | `python3 scripts/export_dashboard.py --output-dir <temp> --no-live-quota` |
| `sync_conversations_to_vault` latency | 88.87 s | Empirical timer in `profile_vault_sync.py` |
| Distinct convo loop query latency | 80.47 s | Empirical timer running `src/vault.py:787-820` queries |
| Subprocess calls without timeout | 28 of 28 calls (100%) | AST call inspection on `subprocess.run` and `Popen` |
| Bare `except Exception: pass` count | 48 instances | AST scan for `ast.ExceptHandler` with `body=[ast.Pass]` |
| Headless page errors (1440×900 & 375×812) | 0 errors across light & dark | Headless Playwright runner `audit_ui.mjs` |
| Axe-core critical accessibility violations | 0 critical violations | Axe-core scan via `run_axe.mjs` |
| Version tags vs manifest | Git `v2.23.0`, pyproject `2.22.0`, package `2.21.0` | `git tag; grep version pyproject.toml package.json` |

---

## 2. Scorecard Against Previous Audits

Evaluated against `AUDIT_2026-09-24_STATUS_SELF_HEAL.md` (TI-2), `AUDIT_2026-09-24_TEST_ISOLATION.md` (TI-1), and `AUDIT_2026-09-22_SYSTEM_DATA_AND_UX.md`:

| Previous Finding / Recommendation | Status | Evidence |
| :--- | :--- | :--- |
| **TI-2a**: Pass `effective_status_path` in watcher exports | **Done** | `scripts/watch_telemetry.py:336, 404` passes `status_path=effective_status_path`; tested by Gate B1. |
| **TI-2b**: Watcher self-heals foreign/corrupt status file | **Done** | `check_status_health` and repair loop in `watch_telemetry.py:84, 381`; tested by `tests/test_status_self_heal.py`. |
| **TI-1**: Unit tests must not overwrite live status file | **Done** | `test_status_isolation.py` passes; Gate B2 asserts `$HOME/.antigravity_quota_status.json` untouched. |
| **C1 (22 Sep)**: Restore missing variables in `now.js:583` | **Done** | `ReferenceError` eliminated; Playwright headless smoke reports 0 page errors. |
| **C2 (22 Sep)**: Clamp debounce settle window to 10.0s | **Done** | `DebounceController.update_settle_window` enforces `min(10.0, ...)` (ADR-079). |
| **C3 (22 Sep)**: Resolve unclosed SQLite connection in `git_timeline.py` | **Done** | Explicit `conn.close()` inside `finally:` blocks in `src/git_timeline.py`. |
| **U1 (22 Sep)**: Add `aria-label` to dock navigation buttons | **Done** | Axe-core critical `button-name` violations resolved from 6 to 0. |
| **U2 (22 Sep)**: Calibrate dark theme contrast ratios | **Done** | 1440×900 dark theme yields 0 axe violations. |
| **D1 (22 Sep)**: Automated Playwright headless console gate | **Done** | Documented in ADR-080; verified clean in Playwright runner. |

---

## 3. Code & Correctness Findings

### Finding C1: Scaling Bottleneck in `sync_conversations_to_vault` (88.9s Sync Latency)
- **What happens**: `sync_conversations_to_vault` (`src/vault.py:551-820`) executes an unconditional full-history scan across all 545 upstream SQLite databases on every sync cycle. It opens and closes 1,090 SQLite connections (2 per database: `_read_convo_db_trajectory_blob` and `_read_convo_db_steps`), performs 2 unindexed full-table text scans over 119,941 rows (`WHERE payload_text LIKE '%invoke_subagent%subagent_id=%'` and `LIKE '%sender=%'`), and executes 544 individual `SELECT` queries in a Python loop (`:787-800`) to compute aggregate counts for every conversation in vault history.
- **Evidence**: Measured runtime of `sync_conversations_to_vault` is **88.87 seconds**. The 544-conversation Python loop alone takes **80.47 seconds** of pure database query time (`profile_vault_sync.py`), causing total export latency to reach **101.49 seconds**.
- **Why it matters**: Because the watcher and export pipelines run on every file event or refresh request, a 101s cycle consumes 100% of a CPU core continuously, delays dashboard updates by nearly 2 minutes, and degrades background daemon responsiveness.
- **Intended behavior**: 
  1. Filter `db_paths` by `p.stat().st_mtime > last_sync_timestamp` so only modified DBs are opened.
  2. Query `conversations_archive` aggregates via a single `GROUP BY convo_id` query across recently changed `convo_id`s rather than 544 individual round trips.
  3. Scope subagent lineage discovery to new steps rather than full-table scans.
- **Concrete fix**: In `src/vault.py`, record `last_sync_mtime` in `vault_sync_state`. Skip DB inspection when `st_mtime <= last_sync_mtime`. Replace the 544-iteration query loop with `INSERT OR REPLACE INTO conversations_archive SELECT ... FROM steps_archive WHERE convo_id IN (synced_convo_ids) GROUP BY convo_id`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import time, sys; sys.path.insert(0, '.'); from src.vault import sync_conversations_to_vault; from antigravity_telemetry import DEFAULT_ANTIGRAVITY_DIR; t0=time.time(); r=sync_conversations_to_vault(DEFAULT_ANTIGRAVITY_DIR); dur=time.time()-t0; assert dur < 5.0, f'Vault sync took {dur:.2f}s'; print(f'OK: {dur:.2f}s')"`
  - `EXPECT`: `OK: < 5.00s`
- **Effort**: 3 hours.
- **Branch**: `perf/vault-sync-mtime-gating`
- **Priority**: P0 (Blocks responsive updates).

### Finding C2: `--dry-run` in Exporter Mutates Live Vault Database
- **What happens**: `scripts/export_dashboard.py:530-540` invokes `sync_subscription_to_vault()`, `sync_conversations_to_vault()`, and `sync_weekly_trends_to_vault()` whenever `not is_custom_dir` is true. The `--dry-run` check occurs at line 639, well after vault synchronization has executed.
- **Evidence**: Running `python3 scripts/export_dashboard.py --dry-run` against standard paths writes new steps and updates `vault_sync_state` inside `data/antigravity_vault.db`.
- **Why it matters**: Violates Host Isolation (Principle 11 and AGENTS.md Rule AC-4). A dry-run must be strictly read-only and side-effect-free. An analytical inspection command mutating persistent storage risks corrupting test environments or altering historical provenance.
- **Intended behavior**: When `--dry-run` is passed, all vault write routines (`sync_*_to_vault`) must be skipped, and existing vault data queried strictly in read-only mode (`?mode=ro`).
- **Concrete fix**: At line 530 of `scripts/export_dashboard.py`, change condition to: `if not is_custom_dir and not dry_run:`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import os, subprocess, pathlib; v=pathlib.Path('data/antigravity_vault.db'); m0=v.stat().st_mtime; subprocess.run(['python3', 'scripts/export_dashboard.py', '--dry-run', '--no-live-quota'], check=True, capture_output=True); m1=v.stat().st_mtime; assert m0 == m1, 'Vault DB modified during dry run'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 20 minutes.
- **Branch**: `fix/exporter-dry-run-isolation`
- **Priority**: P0 (Safety invariant).

### Finding C3: In-Process Thread Race Condition on Status Temp File
- **What happens**: `update_watcher_heartbeat` (`scripts/watch_telemetry.py:40-82`) writes status updates using a hardcoded temporary file pattern: `tmp_path = target.parent / f".{target.name}.tmp.{os.getpid()}"` (`:70`). The daemon thread spawned by `start_heartbeat_thread` (`:113-132`) invokes this function every 10 seconds. Meanwhile, the main watcher thread in `watch_loop` (`:349, :379, :434`) invokes `update_watcher_heartbeat` whenever file events settle or repairs trigger.
- **Evidence**: Both threads share identical `os.getpid()`. Zero thread locks (`threading.Lock`) exist in `scripts/watch_telemetry.py`. When an event-triggered write and a 10s heartbeat coincide, both threads open and truncate the same `.tmp.<pid>` file concurrently, causing race conditions, truncated JSON, or `FileNotFoundError` during `os.replace`.
- **Why it matters**: Menu bar companion (`AntigravityBar`) reads `~/.antigravity_quota_status.json`. Interleaved writes produce corrupted JSON, triggering popover render failures.
- **Intended behavior**: All status updates within the process must be serialized by an in-memory lock, and temporary files must use unique thread IDs or random nonces.
- **Concrete fix**: Add a module-level `_status_lock = threading.Lock()` in `scripts/watch_telemetry.py`. Acquire `_status_lock` in `update_watcher_heartbeat`. Use `tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.tmp.{os.getpid()}_{threading.get_ident()}.", delete=False)` for staging.
- **Executable gate**:
  - `CHECK`: `python3 -c "import concurrent.futures, pathlib, json; from scripts.watch_telemetry import update_watcher_heartbeat; p=pathlib.Path('/tmp/test_race_status.json'); with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex: [ex.submit(update_watcher_heartbeat, p) for _ in range(50)]; d=json.loads(p.read_text()); assert 'watcher' in d; p.unlink(); print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 45 minutes.
- **Branch**: `fix/watcher-thread-lock-temp-safety`
- **Priority**: P1.

### Finding C4: Zero Subprocess Timeouts Across Entire Codebase (0/28 Calls)
- **What happens**: 28 calls to `subprocess.run` and `subprocess.Popen` exist across `src/` and `scripts/`. Exactly 0 enforce a `timeout=` argument.
- **Evidence**: AST scan across all `ast.Call` nodes invoking `subprocess.*` found 0 instances with keyword `timeout`. Critical un-timeouted calls include:
  - `src/quota_client.py:74`: `subprocess.run(['lsof', '-nP', f'-p{pid}', '-iTCP', '-sTCP:LISTEN'], ...)`
  - `src/quota_client.py:32`: `subprocess.run(['ps', '-ww', '-E', '-e', '-o', 'pid,command'], ...)`
  - `scripts/ops_check.py:24, 34, 48, 67`: `subprocess.run([sys.executable, str(export_script)], ...)`
  - `scripts/setup_menubar.py:27`: `subprocess.run(['pgrep', ...])`
- **Why it matters**: `lsof` is notorious on macOS for blocking indefinitely if network file shares or stuck sockets exist. `ops_check.py` or `quota_client.py` will hang silently, blocking automated monitoring and status checks.
- **Intended behavior**: All subprocess invocations must specify an explicit, bounded timeout (e.g., `timeout=5.0` for local system utilities, `timeout=30.0` for compilation/builds) and handle `subprocess.TimeoutExpired`.
- **Concrete fix**: Add `timeout=10.0` to `src/quota_client.py` and `scripts/ops_check.py`. Wrap in `try...except subprocess.TimeoutExpired`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import ast, glob; errs=[]; [errs.append(f'{p}:{n.lineno}') for p in glob.glob('src/**/*.py')+glob.glob('scripts/**/*.py') for n in ast.walk(ast.parse(open(p).read())) if isinstance(n, ast.Call) and getattr(n.func, 'attr', '') in ('run', 'Popen') and not any(k.arg=='timeout' for k in n.keywords)]; assert not errs, f'Missing timeout in: {errs}'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 1.5 hours.
- **Branch**: `fix/subprocess-timeout-hardening`
- **Priority**: P1.

### Finding C5: Non-Atomic In-Place File Writes to Consumed State
- **What happens**: Multiple scripts perform direct in-place writes to state files rather than staging via temporary files and `os.replace`:
  1. `src/log_reader.py:201`: `with open(path, "w", encoding="utf-8") as f: json.dump(reconstructed, f)` writes `data/exhaustion_ledger.json` directly in-place.
  2. `scripts/build_demo_showcase.py:1486, 1494, 1507`: directly writes `out_turns_path.write_text()`, `out_data_path.write_text()`, `out_meta_path.write_text()` in-place.
  3. `scripts/export_dashboard.py:1019`: `args.markdown_file.write_text(digest)` in-place.
- **Evidence**: Verified via `audit_writes.py` and manual code inspection.
- **Why it matters**: If `src/log_reader.py` crashes or is killed during `json.dump`, `data/exhaustion_ledger.json` is left with 0 bytes or half-written JSON, breaking all future quota overage calculations.
- **Intended behavior**: All file writes to state and dashboard artifacts must use atomic write staging (`tempfile` + `os.replace` on the same directory mount).
- **Concrete fix**: In `src/log_reader.py`, replace direct `open(path, 'w')` with `tmp_path = path.parent / f'.{path.name}.tmp'; tmp_path.write_text(...); os.replace(tmp_path, path)`. Apply atomic writing in `build_demo_showcase.py`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import inspect, src.log_reader; src_code = inspect.getsource(src.log_reader.load_exhaustion_ledger); assert 'os.replace' in src_code or 'atomic_write' in src_code, 'Direct open write found in load_exhaustion_ledger'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 1 hour.
- **Branch**: `fix/atomic-ledger-writes`
- **Priority**: P1.

### Finding C6: 48 Instances of Silent `except Exception: pass` Swallowing Failures
- **What happens**: 48 exception handlers across `src/`, `scripts/`, and `antigravity_telemetry/` catch general `Exception` and execute `pass` with zero logging or metrics emission.
- **Evidence**: Confirmed by AST scan and Challenger verification. Key locations:
  - `scripts/export_dashboard.py:535, 539`: Swallows vault and weekly trends synchronization failures.
  - `scripts/export_dashboard.py:572`: Swallows parent subagent correlation failures.
  - `scripts/watch_telemetry.py:140, 145`: Swallows vault and log archive failures.
  - `src/log_reader.py:205`: Swallows ledger write failures.
- **Why it matters**: When vault operations or ledger dumps fail due to permissions, disk space, or schema mismatches, no errors appear in stdout/stderr or logs, masking catastrophic data corruption.
- **Intended behavior**: Catch specific expected exceptions (e.g. `sqlite3.OperationalError`, `FileNotFoundError`), and log unexpected `Exception` occurrences to `sys.stderr` or logger.
- **Concrete fix**: Replace generic `except Exception:` on persistence boundaries with `except (sqlite3.OperationalError, OSError) as e: sys.stderr.write(f'[!] Warning: {e}\n')`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import ast, glob; targets=['scripts/export_dashboard.py', 'scripts/watch_telemetry.py', 'src/log_reader.py']; bare=[f'{f}:{h.lineno}' for f in targets for h in ast.walk(ast.parse(open(f).read())) if isinstance(h, ast.ExceptHandler) and getattr(h.type, 'id', '')=='Exception' and len(h.body)==1 and isinstance(h.body[0], ast.Pass)]; assert not bare, f'Found silent exceptions: {bare}'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 2 hours.
- **Branch**: `fix/explicit-exception-handling`
- **Priority**: P2.

### Finding C7: Circular Module Dependency Between `src/vault.py` and `src/weekly_trends.py`
- **What happens**: `src/vault.py` and `src/weekly_trends.py` depend on each other at runtime, necessitating deferred inline imports within function bodies (`src/vault.py:1155, 1177` and `src/weekly_trends.py:263`).
- **Evidence**: `src/vault.py` imports `sync_weekly_trends_to_vault` and `get_weekly_trends` inside functions; `src/weekly_trends.py` imports `init_vault` inside `sync_weekly_trends_to_vault`.
- **Why it matters**: Violates clean architectural layering. Prevents top-level type checking, obscures the dependency graph, and creates subtle import-order bugs when new modules import both.
- **Intended behavior**: Pure unidirectional dependencies. Shared vault initialization and connection helpers should reside in a foundational module (`src/vault_base.py` or `src/vault_schema.py`).
- **Concrete fix**: Move `init_vault` and schema definitions into `src/vault_schema.py`. Both `src/vault.py` and `src/weekly_trends.py` import `src.vault_schema` at top-level.
- **Executable gate**:
  - `CHECK`: `python3 -c "import ast; tree = ast.parse(open('src/weekly_trends.py').read()); inline_imps = [n.lineno for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for child in ast.walk(n) if isinstance(child, (ast.Import, ast.ImportFrom)) and 'vault' in getattr(child, 'module', '')]; assert not inline_imps, f'Inline vault imports found at {inline_imps}'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 1.5 hours.
- **Branch**: `refactor/vault-weekly-trends-decouple`
- **Priority**: P2.

### Finding C8: Calculation Divergence Between `simulator.py` and `aggregator_pricing.py`
- **What happens**: `src/simulator.py:29-84` defines its own copy of `get_provider_quota_track` and `get_model_rates` instead of importing from `src/aggregator_pricing.py`. The two implementations have silently diverged: `simulator.py:get_model_rates` uses fallback rates of `$0.10` / `$0.025` / `$0.40` (legacy defaults), lacks timestamp support, and does not evaluate temporal rate cards, whereas `aggregator_pricing.py:get_model_rates` integrates `src.temporal` and uses `$0.75` / `$0.075` / `$3.75` Flash baselines.
- **Evidence**: Comparison of function signatures and bodies in `src/simulator.py:58-84` vs `src/aggregator_pricing.py:60-98`.
- **Why it matters**: Workload simulations on the "Plan" tab produce pricing projections based on obsolete hardcoded rates rather than authoritative rates from `config/pricing.json`.
- **Intended behavior**: `src/simulator.py` imports `get_model_rates` and `get_provider_quota_track` directly from `src/aggregator_pricing.py`.
- **Concrete fix**: In `src/simulator.py`, delete the redundant function definitions and add `from src.aggregator_pricing import get_model_rates, get_provider_quota_track`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import src.simulator, src.aggregator_pricing; assert src.simulator.get_model_rates is src.aggregator_pricing.get_model_rates; assert src.simulator.get_provider_quota_track is src.aggregator_pricing.get_provider_quota_track; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 30 minutes.
- **Branch**: `fix/simulator-pricing-alignment`
- **Priority**: P2.

### Finding C9: Orphaned Scripts Without Tests or Governance Integration
- **What happens**: `scripts/setup_github_guardrails.py` (139 lines) and `scripts/quota_regression.py` (167 lines) have 0 test coverage, are not referenced in `README.md`, `CLAUDE.md`, or `VDONE.md`, and are not executed in CI. `scripts/quota_regression.py` imports `src.telemetry_reader` (an old compatibility shim).
- **Evidence**: `check_script_citations.py` scan across all markdown and test files.
- **Why it matters**: Dead and un-tested code incurs maintenance drag, rots silently, and confuses maintainers.
- **Intended behavior**: Formally document script entry points and bind them to test gates or deprecate them.
- **Concrete fix**: Add automated test harness for `quota_regression.py` and `setup_github_guardrails.py` in `tests/`, or archive to `scripts/archive/`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import subprocess; p=subprocess.run(['python3', 'scripts/quota_regression.py'], capture_output=True, text=True); assert p.returncode==0, p.stderr; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 1 hour.
- **Branch**: `chore/scripts-governance-cleanup`
- **Priority**: P3.

---

## 4. UI & UX Findings

*Note: In accordance with Audit Tier (DEEP Backend & Scripts Focus), browser rendering was executed as a smoke verification per AGENTS.md §3.*

### Finding U1: Minor Color-Contrast Violations in Light Theme
- **What happens**: Headless Playwright scan with axe-core across 1440×900 and 375×812 detected 0 critical violations and 0 console errors. Dark mode passed with 0 violations. Light mode reported 24–27 nodes with `color-contrast` notices in secondary metadata badges (`#dock-tab-*` and muted helper spans).
- **Evidence**: Automated Axe scan results (`run_axe.mjs`): `1440x900-light` (24 serious, 0 critical), `1440x900-dark` (0 violations), `375x812-light` (27 serious, 0 critical), `375x812-dark` (2 serious `scrollable-region-focusable`, 0 critical).
- **Why it matters**: Muted text on light backgrounds must satisfy WCAG 2.1 AA 4.5:1 ratio for low-vision accessibility.
- **Intended behavior**: Increase color contrast of `--text-muted` and `--surface-pill` in `dashboard/styles.css` from `#888` to `#595959`.
- **Executable gate**:
  - `CHECK`: `node <scratch-dir>/run_axe.mjs | grep -q '"critical": 0' && echo OK`
  - `EXPECT`: `OK`
- **Effort**: 45 minutes.
- **Branch**: `ui/light-contrast-touchup`
- **Priority**: P3.

---

## 5. Ceremony & Documentation Findings

### Finding D1: Version Desynchronization Across Git Tag and Package Manifests
- **What happens**: The repository version is desynchronized across three authoritative locations:
  - Git tag on HEAD: `v2.23.0` (commit `78a1501`)
  - `pyproject.toml:7`: `version = "2.22.0"`
  - `package.json:3`: `"version": "2.21.0"`
- **Evidence**: `git tag --sort=-v:refname | head -1` outputs `v2.23.0`; `pyproject.toml` line 7 has `version = "2.22.0"`; `package.json` line 3 has `"version": "2.21.0"`.
- **Why it matters**: Breaks release traceability and automated packaging. Tooling or users inspecting `pip` metadata or npm manifests observe outdated version numbers.
- **Intended behavior**: Single synchronized version across Git tags, Python packaging, and Node testing manifests.
- **Concrete fix**: Bump `pyproject.toml` and `package.json` to `"2.23.0"`. Add a version parity gate in `tests/test_docs_integrity.py`.
- **Executable gate**:
  - `CHECK`: `python3 -c "import json, tomllib, pathlib, subprocess; tag=subprocess.check_output(['git','describe','--tags','--abbrev=0']).decode().strip().lstrip('v'); py_ver=tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version']; js_ver=json.loads(pathlib.Path('package.json').read_text())['version']; assert tag==py_ver==js_ver, f'Desync: tag={tag}, py={py_ver}, js={js_ver}'; print('OK')"`
  - `EXPECT`: `OK`
- **Effort**: 20 minutes.
- **Branch**: `chore/version-manifest-sync`
- **Priority**: P1.

---

## 6. Prioritised Backlog

| # | Item | Type | Priority | Effort | Branch | Blocking Decision |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Row 1** | Filter DBs by mtime & batch queries in `sync_conversations_to_vault` (C1) | Performance | P0 | 3 h | `perf/vault-sync-mtime-gating` | Decision 1 |
| **Row 2** | Gate vault sync with `not dry_run` in `scripts/export_dashboard.py` (C2) | Bug Fix / Safety | P0 | 20 m | `fix/exporter-dry-run-isolation` | None |
| **Row 3** | Add thread lock & unique tempfile prefix to `update_watcher_heartbeat` (C3) | Bug Fix / Concurrency | P1 | 45 m | `fix/watcher-thread-lock-temp-safety` | None |
| **Row 4** | Add explicit `timeout=` and error handling across 28 subprocess calls (C4) | Robustness | P1 | 1.5 h | `fix/subprocess-timeout-hardening` | None |
| **Row 5** | Align version across Git tag, `pyproject.toml`, and `package.json` (D1) | Ceremony / Docs | P1 | 20 m | `chore/version-manifest-sync` | None |
| **Row 6** | Atomic file writes for `exhaustion_ledger.json` & demo showcase (C5) | Safety / Atomicity | P1 | 1 h | `fix/atomic-ledger-writes` | None |
| **Row 7** | Replace silent `except Exception: pass` with targeted logging (C6) | Quality | P2 | 2 h | `fix/explicit-exception-handling` | None |
| **Row 8** | Decouple `src/vault.py` and `src/weekly_trends.py` circular import (C7) | Refactor | P2 | 1.5 h | `refactor/vault-weekly-trends-decouple` | None |
| **Row 9** | Import `get_model_rates` directly in `src/simulator.py` from pricing (C8) | Correctness | P2 | 30 m | `fix/simulator-pricing-alignment` | Decision 2 |
| **Row 10** | Add test harnesses for `quota_regression.py` and GitHub guardrails (C9) | Governance | P3 | 1 h | `chore/scripts-governance-cleanup` | Decision 3 |
| **Row 11** | Calibrate light mode badge color contrast in `dashboard/styles.css` (U1) | UI / A11y | P3 | 45 m | `ui/light-contrast-touchup` | None |

### Instructions for the Maintaining Implementer Agent
- Take the lowest-numbered open row in one session.
- Run `$TEST_CMD` and `$QUALITY_GATE_CMD` before making any edit.
- Respect the strict file scope: stage only files modified for that specific row.
- Ensure the tree remains 100% clean (`git status --short`).

---

## 7. Owner Decisions

| # | Question | Decision Taken | Consequence / Action Taken |
| :--- | :--- | :--- | :--- |
| **1** | Should `sync_conversations_to_vault` skip upstream SQLite databases whose file `st_mtime` has not changed since the last vault sync? | **Agreed on filter. Add an option to force full scan if needed or on demand.** | Implement `st_mtime > last_sync_time` gating, plus add `--force-full-scan` CLI flag and `force: bool = False` argument to bypass cache and force a complete scan on demand. Implemented in Row 1. |
| **2** | Should `src/simulator.py` import `get_model_rates` directly from `src/aggregator_pricing.py` to eliminate rate divergence? | **Yes — unify rate card resolution into src/aggregator_pricing.py.** | Redundant fallback functions deleted from `src/simulator.py`. Simulator dynamically calls `src/aggregator_pricing.py:get_model_rates`. Implemented in Row 9. |
| **3** | How should orphaned scripts (`quota_regression.py`, `setup_github_guardrails.py`) be handled? | **Keep both and add automated dry-run test gates to prevent silent rot.** | Add test harnesses in `tests/` verifying execution and returncode 0 without side effects. Implemented in Row 10. |

---

## 8. Appendix

### 8.1 Scripts Used During Audit
- `scratch/analyze_imports.py`: AST dependency graph and duplicate function detector.
- `scratch/check_locks.py`: Concurrency and file lock mechanism scanner.
- `scratch/audit_writes.py`: Direct write and atomicity analyzer.
- `scratch/audit_host_isolation.py`: SQLite URI read-only syntax and host mutation checker.
- `scratch/audit_subprocess.py`: Subprocess keyword and timeout inspector.
- `scratch/audit_exceptions.py`: AST exception handler analyzer.
- `scratch/audit_vault_schema.py`: Vault schema, row count, and index analyzer.
- `scratch/measure_storage.py`: Storage, database, and log volume measurement script.
- `scratch/profile_vault_sync.py`: Component-level latency breakdown for vault synchronization.
- `scratch/audit_ui.mjs` & `run_axe.mjs`: Headless Playwright runtime and axe-core accessibility scanners.

### 8.2 Challenger Verification Table (Verbatim)

| Finding ID | Stated Claim | Verification Query | Status (EVIDENCED / GUESSED / CONTRADICTED) | Action Taken / Verification Details |
| :--- | :--- | :--- | :--- | :--- |
| **C1** | `src/vault.py` and `src/weekly_trends.py` have a circular dependency requiring deferred inline imports. `src/vault.py:1155, 1177` import `from src.weekly_trends import sync_weekly_trends_to_vault, get_weekly_trends` inside function bodies, and `src/weekly_trends.py:263` imports `from src.vault import init_vault`. | `grep -nE "from src\.(weekly_trends\|vault) import" src/vault.py src/weekly_trends.py` | **EVIDENCED** | **Keep.** Verified exact lines: `src/vault.py:1155` (`from src.weekly_trends import sync_weekly_trends_to_vault as _sync`), `src/vault.py:1177` (`from src.weekly_trends import get_weekly_trends as _get`), and `src/weekly_trends.py:263` (`from src.vault import init_vault`). Both modules defer imports into function bodies to prevent an `ImportError` cycle at module load. |
| **C2** | `get_provider_quota_track` and `get_model_rates` are duplicate copy-pasted implementations between `src/aggregator_pricing.py:113-141` and `src/simulator.py:29-84`. In addition, `parse_timestamp` is implemented in 3 separate modules: `src/temporal.py:59`, `src/aggregator_pricing.py:246`, and `src/log_archiver.py:76`. | AST & grep symbol scans across `src/` for `get_provider_quota_track`, `get_model_rates`, and `parse_timestamp`. | **CONTRADICTED** | **Downgrade / Refine.** 1) `get_provider_quota_track` is indeed duplicated. 2) `get_model_rates` is NOT an identical copy-paste; it has divergent fallback defaults (`prompt_uncached` 0.10 vs 0.75, `cached` 0.025 vs 0.075, `candidate_output` 0.40 vs 3.75) and lacks `timestamp` temporal support in `simulator.py` (a silent calculation divergence rather than pure duplicate). 3) `src/temporal.py:59` implements `parse_temporal_timestamp` (different symbol name), and `src/log_archiver.py:76` is a log-line regex extractor (`line: str`), not a scalar timestamp parser like `aggregator_pricing.py:246`. Refine finding to focus on rate divergence and redundancy. |
| **C3** | `scripts/setup_github_guardrails.py` (139 lines) has 0 test files, 0 mentions in README/CI/VDONE, and only 1 mention in `docs/REPO_MAP.md`. `scripts/quota_regression.py` (167 lines) has 0 test files, is not run in CI or VDONE, and still imports obsolete `src.telemetry_reader`. | `wc -l scripts/{setup_github_guardrails,quota_regression}.py` & ripgrep across repository and tests. | **EVIDENCED** | **Keep.** `setup_github_guardrails.py` is exactly 139 lines, has 0 test references, 0 CI/VDONE mentions, and 1 mention in `docs/REPO_MAP.md:73`. `quota_regression.py` is 167 lines, has 0 tests, 0 CI/VDONE executions, and imports from `src.telemetry_reader` (which is a backward-compat shim re-exporting `antigravity_telemetry`). |
| **C4** | `scripts/watch_telemetry.py:70` hardcodes temporary filename as `tmp_path = target.parent / f".{target.name}.tmp.{os.getpid()}"`. Daemon thread in `start_heartbeat_thread` (`:113-132`) and main thread in `watch_loop` (`:349, :396`) both call `update_watcher_heartbeat()`. Sharing PID without a lock causes temp path collision. | Code inspection of `scripts/watch_telemetry.py:70, 113-132, 349, 379, 434` and lock search. | **EVIDENCED** | **Keep.** Verified line 70 uses `f".{target.name}.tmp.{os.getpid()}"` without thread ID or random nonce. Daemon thread calls `update_watcher_heartbeat` every 10s. Main thread calls it at lines 349, 379, and 434 (finding cited :349, :396). Zero `threading.Lock` exists in the entire module, resulting in thread collisions and file truncation races on `.status.json.tmp.<pid>`. |
| **C5** | `src/log_reader.py:201` directly writes `exhaustion_ledger.json` in-place (`with open(path, "w")... json.dump`) without `.tmp` staging or `os.replace`. `scripts/build_demo_showcase.py:1486-1507` writes demo JS files in-place using `write_text`. `scripts/export_dashboard.py:1019` writes markdown digest in-place using `write_text`. | File inspection of `src/log_reader.py:201`, `scripts/build_demo_showcase.py:1486-1507`, and `scripts/export_dashboard.py:1019`. | **EVIDENCED** | **Keep.** All three cited locations perform un-staged, non-atomic writes. `src/log_reader.py:201` opens the shared ledger in write mode directly; `build_demo_showcase.py:1486, 1494, 1507` executes direct `Path.write_text()` on turns, data, and meta JS files; `export_dashboard.py:1019` calls `args.markdown_file.write_text()`. |
| **C6** | `scripts/export_dashboard.py:530-540` calls `sync_subscription_to_vault()`, `sync_conversations_to_vault()`, and `sync_weekly_trends_to_vault()` whenever `not is_custom_dir`, without checking `if not dry_run:`. The `if dry_run:` check is at line 639. Running `export_dashboard.py --dry-run` executes vault sync writes. | AST and code inspection of `scripts/export_dashboard.py:530-540, 639`. | **EVIDENCED** | **Keep.** Lines 530-540 unconditionally execute vault sync routines before the `if dry_run:` branch at line 639 is reached. Running `--dry-run` against standard paths mutates `data/antigravity_vault.db`. |
| **C7** | Across `src/` and `scripts/`, there are 24 calls to `subprocess.run` / `Popen`. Exactly 0 / 24 specify a `timeout=`. Critical calls include `src/quota_client.py:74` (`lsof`), `src/quota_client.py:32` (`ps`), and `scripts/ops_check.py` (`subprocess.run([sys.executable, str(export_script)])`). | AST inspection of all `ast.Call` nodes invoking `subprocess.*` across `src/` and `scripts/`. | **CONTRADICTED (on count) / EVIDENCED (on defect)** | **Keep with count correction.** The audit undercounted total calls: there are actually **28** subprocess calls (2 in `src/quota_client.py`, 3 in `build_menubar.py`, 4 in `ops_check.py`, 1 in `capture_showcase_screenshots.py`, 1 in `setup_github_guardrails.py`, 1 in `publish_to_public.py`, 7 in `setup_service.py`, 9 in `setup_menubar.py`). However, **0 / 28** enforce a timeout (100% vulnerability). Update claim from 24 to 28 calls. |
| **C8** | An AST scan of `src/`, `scripts/`, and `antigravity_telemetry/` finds 48 occurrences of `except Exception: pass` silently ignoring errors without logging, including critical failure paths in `export_dashboard.py:535, 539, 572` and `src/log_reader.py:205`. | AST scan traversing `ast.ExceptHandler` with `body=[ast.Pass]` across `src/`, `scripts/`, and `antigravity_telemetry/`. | **EVIDENCED** | **Keep.** Exactly **48** instances confirmed across the target packages. Critical failure paths verified at `scripts/export_dashboard.py:535` (vault sync), `:539` (trends sync), `:572` (step extraction), and `src/log_reader.py:204-205` (ledger persistence). |
| **C9** | `data/antigravity_vault.db` is 2.81 GB (2,812 MB) with 119,941 steps. On every export cycle, `sync_conversations_to_vault` opens 1,090 SQLite connections (2 per DB across 545 DBs), executes two unindexed full-table substring scans on 119k text rows (`payload_text LIKE '%invoke_subagent%subagent_id=%'` and `LIKE '%sender=%'`), and executes 544 individual queries in a loop. Measured duration is 88.87s (export 101.49s). | Empirical execution of bottleneck queries and `steps_archive` inspect on `data/antigravity_vault.db`. | **EVIDENCED** | **Keep.** `data/antigravity_vault.db` is 2.816 GB (2,816,299,008 bytes) with 120,260 steps (119,941 at audit time). 547 upstream DBs * 2 connections = 1,094 connections opened. Unindexed substring scans verified at `src/vault.py:757, 772`. The loop over distinct `convo_id`s at line 787 executes 2 queries per convo (1,092 queries total); empirical query timing of this loop alone measured **80.47s**, corroborating the 88.87s sync latency. |
| **C10** | The latest Git tag on `HEAD` is `v2.23.0` (commit `78a1501`), but `pyproject.toml:3` has `version = "2.22.0"` and `package.json:3` has `"version": "2.21.0"`. | `git log -n 5 --decorate`, `pyproject.toml:7`, `package.json:3`. | **EVIDENCED** | **Keep (with line correction).** Tag `v2.23.0` is commit `78a1501` (`HEAD` is 1 commit ahead at `526d71e`). `package.json:3` is `"version": "2.21.0"`. In `pyproject.toml`, `version = "2.22.0"` is located at line 7 (line 3 is `build-backend`). Three-way version desynchronization is factually proven. |
