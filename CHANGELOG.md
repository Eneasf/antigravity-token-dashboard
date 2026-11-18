# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [v2.27.0] - 2026-11-18 (Public Sibling Synchronization, Sanitization Hardening & Milestone 100 Release)
- **Public Staging Sanitizer & Audit-Doc PII Gate (`scripts/publish_to_public.py`, `tests/test_sanitization.py`, `tests/test_public_release_hygiene.py`)**: Added `sanitize_public_staging_tree()` to scrub personal Vault snapshot event intervals from staged `data/quota_regime_ledger.json` while preserving calibrated model weights, added `data/quota_regime_ledger.sample.json`, removed `docs/AUDIT_*.md` exemptions from PII needle checks, and anchored public tag pushes cleanly without mutating local branch tags.
- **Isolated Light Mode Showcase Pipeline & Schema v2 Docs (`scripts/capture_showcase_screenshots.py`, `README.md`, `antigravity_telemetry/README.md`)**: Isolated headless Chrome screenshot rendering inside a temporary staging directory backed by `build_demo_showcase.py` (`data.js`, `meta.js`, `turns.js`) so live `window.__TELEMETRY_META__` never bleeds into showcase assets, and updated documentation to reflect the schema v2 model catalog, Executive Cockpit UI, wire TTFT, and KV-cache coaching.
- **40-Model Canonical Census & Phase 2 Connect-RPC Calibration (`antigravity_telemetry/models.json`, `config/pricing.json`, `src/quota_regime.py`, ADR-098 / Milestone 100)**: Registered **Gemini 4 Hydrogen** (`1528` XHigh, `1525` High, `1526` Medium, `1527` Low; `gemini-hydrogen` family, `1M` truncation, `250k` compaction, `$0.25/$0.0125/$1.25` `1/6x` quota weights vs `$1.50/$0.075/$7.50` API), both **Orchestrator Planners** (`1667` Carbon, `1681` Argon; `gemini-orchestrator` family, `0.50x` weights), and **Orchestrator Executor (Hydrogen)** (`1669`; `1/6x` execution model invoked on `exit_plan_mode`), locking Phase 2 Connect-RPC intervals (`#3623 -> #3638`, `<= 0.02%` residual across all four Hydrogen tiers `1525`–`1528` and Orchestrators `1667`/`1681`/`1669`) in [`docs/MODEL_BENCHMARKS.md`](docs/MODEL_BENCHMARKS.md) and [`M100_HYDROGEN_AND_ORCHESTRATOR_CARDS.md`](docs/milestones/M100_HYDROGEN_AND_ORCHESTRATOR_CARDS.md).
- **Analytics, Coaching, Swarm Tiering & Accessible UI Badges (`src/*`, `dashboard/*`)**: Added `gemini_orchestrator` / `gemini_hydrogen` Horizon & diurnal series, ordered Orchestrator keyword matching before Carbon/Argon in coaching/horizon/badge resolvers, `XHigh Reasoning` parsing in `plan-rates.js`, `hydrogen_xhigh_sprint` simulator archetype, semantic CSS token `.model-hydrogen` / `.model-orchestrator` badges, and hermetically regenerated `tests/fixtures/aggregator_baseline_data.json`.

## [2026-11-10] (Milestone 99: Gemini 4 Carbon Frontier Model Census, Two-Era Pricing & GPT-OSS Sunset Notice)
- **32-Model Canonical Census & Wire Calibration (`antigravity_telemetry/models.json`, `antigravity_telemetry/__init__.py`, `config/pricing.json`, ADR-097)**: Registered **Gemini 4 Carbon** across non-contiguous wire IDs `1427` (`High`, `MODEL_PLACEHOLDER_M427`), `1437` (`Medium`, `MODEL_PLACEHOLDER_M437`), and `1438` (`Low`, `MODEL_PLACEHOLDER_M438`) under `family: "gemini-carbon"` (`1M` truncation, `250k` compaction threshold) with two-era temporal pricing (`$2.00/$0.10/$10.00` introductory until `2026-11-30`, `$4.00/$0.20/$20.00` standard from `2026-12-01`), and recorded the upstream `2026-11-18` removal schedule on `GPT-OSS 120B (Medium)` (`342`) ([`M99_GEMINI_4_CARBON_MODEL_CENSUS.md`](docs/milestones/M99_GEMINI_4_CARBON_MODEL_CENSUS.md)).
- **KV-Cache Coaching, Horizon Analytics, Regime Detector & Dashboard Taxonomy (`src/aggregator_coaching.py`, `src/horizon_analytics.py`, `src/quota_regime.py`, `src/swarm.py`, `dashboard/js/*`, `dashboard/index.html`, `dashboard/styles.css`)**: Added `gemini-carbon` placeholder normalization and intra-family/intra-track KV eviction detection (`Carbon` $\leftrightarrow$ `Argon`), `gemini_carbon` horizon/diurnal latency series, 6-turn sequential `read_file` staircase calibration prompts for `1427`/`1437`/`1438`, and `.model-carbon` UI badges + simulator options.

## [2026-11-09] (Milestone 98 / M94 Series: Subprocess Exporter Crash Remediation, Logical Vault Cache Fingerprinting & Bisect Regime Slicing)
- **Logical `vault_cache` Fingerprinting & No-Op Sync Guard (`scripts/export_dashboard.py`, `src/vault.py`, ADR-096)**: Eliminated unconditional `conversations_last_sync_mtime` writes on `0`-DB no-op syncs in `sync_conversations_to_vault()`, and keyed `load_vault_analytics_cached()` on `_get_vault_logical_fingerprint()` (`MAX(rowid)` / `MAX(id)` / `MAX(synced_at)`) so `quota_snapshots_archive` and `weekly_cycles_archive` updates do not invalidate `vault_cache` in subprocess mode.
- **Persistent SQLite `horizon_analytics` Cache (`scripts/export_dashboard.py`)**: Persisted `horizon_analytics` in `dashboard/.export_cache.db` (`vault_cache`), avoiding redundant 123k-turn `load_merged_vault_and_live_turns()` + `compute_horizon_analytics()` recomputation across isolated watcher subprocess invocations.
- **Active-Cycle Delta Sync for Weekly Trends & Lineage Updates (`src/weekly_trends.py`, `src/vault.py`)**: Scoped `sync_weekly_trends_to_vault()` to recompute only the active weekly cycle when historical turn counts match archived cycles, and skipped redundant `parent_convo_id` `UPDATE` statements and full-table `COUNT(DISTINCT convo_id)` scans in `sync_conversations_to_vault()`.
- **$O(\log N)$ `bisect_right` Quota Regime Slicing & ADR-081 Lock Resilience (`src/quota_regime.py`)**: Replaced $O(N_{\text{snaps}} \times N_{\text{turns}})$ list comprehension scans and generator `sum()` frames in `evaluate_vault_quota_regime()` with `bisect_right` slicing (`4.10s` $\rightarrow$ `<0.04s`), and hardened `sync_regime_events_to_vault_and_ledger()` with `busy_timeout=60000`, exponential retry helpers, and hash-based no-op write skipping.

## [2026-10-14] (Milestone 94: Ultra Capacity Calibration, Intra-Family KV Coaching, Wire Protobuf TTFT & Now-Tab Active Swarms)
- **Ultra 5x Quota Capacity Calibration (`config/pricing.json`, `src/temporal.py`, `dashboard/js/plan-manager.js`, `dashboard/js/simulator.js`)**: Calibrated active and Ultra-era (`subscription_history[1]`) Gemini capacities to `$25.00` (`2,500 credits`) 5h burst and `$100.00` (`10,000 credits`, exact `4.0000x` ratio) weekly quota while preserving Pro-era (`subscription_history[0]`) `$20.00` / `$129.00` limits for historical September 2026 ledger reconciliations ([`M94_ULTRA_CAPACITY_KV_COACHING_AND_WIRE_LATENCY.md`](docs/milestones/M94_ULTRA_CAPACITY_KV_COACHING_AND_WIRE_LATENCY.md)).
- **Intra-Family & Intra-Track KV Cache Eviction Coaching (`src/aggregator_coaching.py`, `dashboard/js/sessions.js`, GADR-018)**: Extended `compute_cache_coaching_metrics()` to detect intra-family effort tier switches (`1417` $\leftrightarrow$ `1418` $\leftrightarrow$ `1419`, `1318` $\leftrightarrow$ `1319` $\leftrightarrow$ `1320`) and intra-track model changes past `40k` prompt depth where cache hit drops (`<20%`), surfacing subtype breakdown badges and GADR-018 subagent routing guidance.
- **Wire Protobuf TTFT & Turn Latency Pipeline (`antigravity_telemetry/reader.py`, `src/vault_schema.py`, `src/vault.py`, `dashboard/js/sessions-turns.js`, `PopoverContentView.swift`)**: Implemented `extract_wire_latency_ms()` to decode sub-millisecond wire protobuf timestamps (`Fields 1, 6, 7, 8, 26`), added `ttft_ms` and `latency_ms` to `steps_archive` and `v_turns`, backfilled `104,107` historical turns across Pro and Ultra eras in `data/antigravity_vault.db`, and added TTFT/latency and `KV Cache Evicted (0% Hit)` badges to the web turns table and macOS Menu Bar popover.
- **Dashboard `Now` Tab Active Swarms & Weakest-Link Parity (`dashboard/js/now-burst.js`, `dashboard/styles.css`)**: Added `renderNowActiveSwarms()` to the `Now` tab Executive Cockpit, rendering multi-agent swarm hierarchies, model badges, and weakest-link context utilization risk directly on the main dashboard view.

## [2026-10-14] (Milestone 93: Live Quota Snapshot Archival, Burn Interval Analytics & Fast Monitor Convergence)
- **Live Quota Snapshot Archival & Interval Burn View (ADR-094)**: Added `quota_snapshots_archive` table and `v_quota_burn_intervals` SQL view in `src/vault_schema.py`, along with deduplicated Connect-RPC snapshot persistence via `sync_quota_snapshot_to_vault()` in `src/vault.py`.
- **Empirical Burn Interval Regression (`scripts/quota_regression.py`)**: Added Section 5 (`analyze_vault_burn_intervals()`) and `--vault-path` CLI flag to compare $\Delta\text{5h}\%$, $\Delta\text{Weekly}\%$, and the $\Delta\text{5h}/\Delta\text{Weekly}$ pool ratio across consecutive Vault quota snapshots.
- **Local-to-UTC glog Timestamp Conversion & `<0.5ms` 429 Tail Scan (`src/log_reader.py`)**: Fixed `parse_glog_timestamp()` to convert local wall-clock glog timestamps (e.g., BST `UTC+1`) to UTC when `local_tz=True`, and added fingerprint-cached `get_latest_exhaustion_event_utc()` for sub-millisecond tail detection of `429 RESOURCE_EXHAUSTED` events.
- **Fast-Tier 429 Clamping & 15s Connect-RPC Refresh (`scripts/export_dashboard.py`, `scripts/watch_telemetry.py`)**: Triggered `export_fast_tier()` on both `.db-wal` and `.log` modifications, immediately clamping `~/.antigravity_quota_status.json` to `EXHAUSTED` (`0%`) upon a recent `429` event and polling live Connect-RPC quota with a 15-second throttle.
- **Pre-Vault Status Hook Write & `vault_cache` De-Bloat (`scripts/export_dashboard.py`, `src/vault.py`)**: Moved `write_quota_status_file()` ahead of Vault synchronization, deduplicated `transcript_full.jsonl` reads per conversation in `sync_conversations_to_vault()`, and compacted `tool_calls_by_convo` in `load_vault_analytics_cached()` to shrink `dashboard/.export_cache.db` from `53.73 MB` to `5.64 MB`.

## [2026-10-13] (Milestone 92: Gemini 4 Argon Frontier Model Census & Two-Era Pricing)
- **Gemini 4 Argon Frontier Model Census (ADR-093)**: Registered `1417` (`Gemini 4 Argon (High)`), `1418` (`Gemini 4 Argon (Medium)`), and `1419` (`Gemini 4 Argon (Low)`) under `"family": "gemini-argon"` in `antigravity_telemetry/models.json` and `config/pricing.json`, expanding the canonical census from 26 to 29 models.
- **Two-Era Temporal Rate History**: Configured `rate_history` in `config/pricing.json` for `1417`–`1419` with introductory pricing (`$2.00` uncached input / `$0.10` cached input / `$10.00` output per 1M tokens) from `2026-10-13T00:00:00Z` through `2026-11-30T23:59:59Z` and standard pricing (`$4.00` / `$0.20` / `$20.00`) from `2026-12-01T00:00:00Z` onwards.
- **Context Window & Compaction Threshold Calibration**: Configured `context_truncation_tokens: 1000000` (1M context window) and `compaction_threshold_tokens: 250000` (matching Gemini 3.8 Flash and empirically confirmed on live `1417` sessions).
- **Backward-Compatible Sunsetting of Gemini 3.1 Pro**: Marked `1016` (`Gemini 3.1 Pro (High)`) and `1036` (`Gemini 3.1 Pro (Low)`) as `"status": "deprecated"`, `"sunset_date": "2026-10-13"` in `models.json` and `"sunset"` in `config/pricing.json` without `superseded_by` coupling, preserving 100% of historical telemetry.
- **Dashboard & Subagent Routing Integration**: Added `1417`–`1419` to `MODEL_TAXONOMY` and `SCHEDULED` badge support in `dashboard/js/plan-rates.js`, truncation/compaction helpers in `dashboard/js/sessions-filters.js`, `SIM_MODEL_RATES` in `dashboard/js/simulator.js`, `#sim-model-select` in `dashboard/index.html`, and `"pro"` subagent tier routing in `src/swarm.py`.

## [2026-10-07] (Milestone 91: Multi-Agent Swarms, Weakest-Link Risk Scoring & Native Popover Cascade Trees)
- **Multi-Project Active Swarms Hierarchy (ADR-092)**: Grouped active sessions by project workspace with hierarchical orchestrator parent nodes and child subagents within a 30-minute recency window (with fixture fallback).
- **Weakest-Link Risk Scoring & Preemption**: Implemented base priority scoring (`critical` 300+, `warning` 200+, `safe` orchestrator 150+, `safe` subagent 100+) ensuring degraded subagents immediately preempt safe orchestrators as the primary alert.
- **Dual-State Context Metrics Decoupling**: Decoupled active capacity load (measured strictly from latest turn $t_n$ prompt depth) from compaction drift (measured by Compaction Epoch $E1..E3+$), completely eliminating post-compaction/restart false alarms.
- **Subagent Telemetry & Lineage**: Removed exclusion of subagents in active session evaluation, surfacing subagent persona role badges (`arrow.triangle.branch`) and parent session context links (`↳ child of <parent>`).
- **Velocity Spike Early Warning**: Added detection for rapid single-turn token growth ($\ge 40{,}000$ tokens/turn) to flag runaway context accumulation before context boundaries are breached.
- **macOS Menu Bar Native Progressive Disclosure**: Enhanced `AntigravityBar` popover with subagent role badges on the pinned active session card and a collapsible `Active Swarms & Projects` section showing all active projects and nested subagent micro-meters.
- **Web Dashboard Header & Session Card Parity**: Updated Now tab header alert badge and pinned active session card to display subagent roles, parent links, and epoch badges.

## [2026-10-06] (Milestone 90: Telemetry Vault Query Optimization, Structured Extraction & Reference Dictionaries)
- **Compound & Partial Indexing (ADR-087)**: Added `idx_steps_step_type_ts(step_type, timestamp, model_name)`, `idx_steps_convo_id_ts(convo_id, timestamp)`, `idx_log_events_code_type_ts(code, event_type, timestamp_iso)`, and partial index `idx_steps_error_text` on non-empty errors in `src/vault_schema.py`.
- **Structured Error Extraction & FTS5 Rejection (ADR-088)**: Formally rejected SQLite FTS5 index bloat (+2–3GB); implemented ingestion-time structured extraction of `rate_limit_flag` and `error_code` into `steps_archive` with partial index acceleration.
- **Self-Documenting Reference Tables (ADR-089)**: Created `ref_step_types` and `ref_status_codes` lookup dictionaries in SQLite schema to eradicate magic numbers from queries and analytical reports.
- **Canonical Analytical Views (ADR-090)**: Created `v_turns`, `v_hourly_token_velocity`, `v_active_sessions`, and `v_rate_limit_events` for instant, join-free session duration seeks and rate-limit incident correlation.
- **Empirical Benchmarking & KPI Governance (ADR-091)**: Created `scripts/bench_vault_performance.py` tracking query latency (ms), row scan reduction, index disk footprint, and batch insertion throughput.

## [2026-10-03] (Milestone 89: Claude 5.5 Model Census Expansion & Reasoning Taxonomy)
- **Claude 5.5 Model Census Expansion**: Registered 6 newly calibrated models in `antigravity_telemetry/models.json` and `config/pricing.json`: Claude Opus 5.5 (`1400` Low, `1401` Medium, `1402` High) and Claude Sonnet 5.5 (`1403` Low, `1404` Medium, `1405` High), expanding canonical census from 20 to 26 models.
- **Backward-Compatible Sunsetting**: Preserved all legacy metrics, vault history, and rate cards for Claude Opus 4.6 (`1026`) and Claude Sonnet 4.6 (`1035`), marking them as `sunset` / `deprecated` with `sunset_date: "2026-10-03"` and `superseded_by` pointers.
- **Provider Quota Silo Routing**: Automated classification in `src/aggregator_pricing.py` routing models `1400`–`1405` dynamically into the dedicated `claude_gpt` quota track.
- **Dashboard & Simulator Integration**: Added new models to `#sim-model-select` dropdown in `dashboard/index.html`, `MODEL_TAXONOMY` in `dashboard/js/plan-rates.js`, `claudeModels` in `dashboard/js/sessions-filters.js`, and `SIM_MODEL_RATES` in `dashboard/js/simulator.js`.
- **Roster & Threshold Integrity**: Updated Gate V136 in `tests/test_model_roster_integrity.py`, package census tests in `tests/test_antigravity_telemetry_pkg.py`, and compaction/truncation threshold verification in `tests/test_truncation_thresholds.py`.

---

## [2026-10-02] (Milestone 88: Dashboard Executive Cockpit & Mac Menu Bar Parity)
- **False-Alarm Session Truncation Elimination**: Refactored `checkDegradedSessions` in `dashboard/js/sessions.js` to evaluate strictly the live active session from `data.current_session`, completely eliminating false-alarm red context truncation warnings on the Now tab caused by completed historical sessions at `convos[0]`. Historical sessions remain strictly quarantined to the Sessions tab audit drawer.
- **Executive Hero Card (Mac Menu Bar Parity)**: Implemented high-contrast Executive Hero Card in `dashboard/index.html`, `dashboard/js/now-burst.js`, and `dashboard/styles.css` mirroring the macOS `AntigravityBar` popover hierarchy across five modules: Plan Name & Status Badge (`exec-status-badge`), Weekly Runway (large percentage, progress bar `exec-weekly-bar`, reset countdown `exec-weekly-countdown`, pacing verdict `exec-weekly-verdict`), 5-Hour Limit (`exec-5h-bar`, `exec-5h-tokens`, plain-English recovery time forecast `exec-5h-forecast`), Live Turn & Velocity (`exec-burn-rate`, `exec-delta-val`, active model & cache %, 5h burst headroom `exec-burst-headroom`), and Secondary Track & Credit Bank Footer (`exec-claude-status`, `exec-credit-balance`, active workspace & branch context `exec-active-context`).
- **Demoted Dense Telemetry Drawer**: Demoted Sacred Dual Benchmark Bar (`#runway-dual-bar`), Bayesian BVI shrinkage formulas, and dense KPI grid below the Executive Card into a collapsible `<details class="dense-telemetry-drawer" id="dense-telemetry-drawer">` sub-drawer labeled "Detailed Pace & Diagnostics", preserving 100% of DOM IDs and backward-compatible controller selectors.
- **Byte-Deterministic Export Parity**: Extracted `compute_current_session` in `scripts/export_dashboard.py`, ensuring consistent schema parity across `data.json`, `data.js`, and `~/.antigravity_quota_status.json`, with updated synthetic showcase generation in `scripts/build_demo_showcase.py` and hermetic test baseline fixtures.
- **Accessibility & Design Token Compliance**: Verified zero Axe-core accessibility and WCAG AA contrast violations in both Light (>7:1 contrast on badges) and Dark modes, zero sub-11px font sizes, zero inline `onclick=` handlers, and strict adherence to ADR-066 line budgets (<800 lines per script).

---

## [2026-10-02] (Milestone 87: Incremental Cached Exporter & Fast Heavy Rollup)
- **Incremental Cached Exporter (<500ms)**: Implemented two-tier caching architecture in `scripts/export_dashboard.py` via process-local memory cache (`_IN_MEMORY_CONVO_CACHE`, `_IN_MEMORY_VAULT_CACHE`) and persistent SQLite cache (`dashboard/.export_cache.db`), cutting full export time from 40–80s down to <500ms CLI and ~78ms for daemon exports.
- **Lightweight Fingerprint Gating**: Leveraged `os.scandir` stat checks (~8ms for 526 DBs) with `(mtime_ns, size_bytes)` fingerprinting including `-wal` sidecars, re-parsing only dirty/new conversations and pruning deleted ones.
- **Cached Vault Analytics**: Cached expensive queries over the 3.28 GB vault DB (`extract_tool_analytics`, `extract_swarm_lineage`, `get_vault_truncation_markers`, subagent parent-child counts, prompts, tool calls).
- **ISO Timestamp Parsing Optimization**: Added `@functools.lru_cache(maxsize=16384)` in `src/temporal.py`, `src/aggregator_pricing.py`, and `src/git_timeline.py` to eliminate millions of redundant date parsing calls.
- **Watcher Debounce Cadence Reduction**: Lowered watcher quiet settle window from 30.0s to 2.0s (max delay lowered from 60.0s to 10.0s) in `scripts/watch_telemetry.py` and `scripts/setup_service.py`.
- **Resilience & Safe Invariants**: Added `--force-full-scan` flag, automatic self-healing on corrupt cache files, and SQLite WAL/busy timeout configuration per GADR-013 / ADR-081.

---

## [v2.26.0] - 2026-09-30 (Milestone 86: Menu Bar Epoch Number Indicator & Two-Tier Fast Ticker Exporter)
- **Menu Bar Dynamic Epoch Badge**: Replaced blunt 🔴/⚠️ warning dots in `macos/AntigravityBar` with dynamic Epoch number badge (E1..E5) with color grading (`#34D399` for E1..E2, `#FBBF24` for E3, `#EF4444` for E4+).
- **Two-Tier Fast Ticker Exporter (<20ms)**: Implemented `export_fast_tier` in `scripts/export_dashboard.py` running in <7ms on active session WAL changes, writing strictly `dashboard/meta.js`, `dashboard/meta.json`, and `~/.antigravity_quota_status.json` without updating 32.5MB `dashboard/data.js`.
- **Decoupled Telemetry Watcher**: Updated `scripts/watch_telemetry.py` to trigger Fast Tier immediately on active session `.db-wal` modifications while debouncing Heavy Tier full rollups to 30–60s settle window.
- **CLI Invariant Extensions**: Added `--fast-tier` / `--fast` flags to `export_dashboard.py` and `--no-fast-tier` to `watch_telemetry.py`.

---

## [v2.25.0] - 2026-09-29 (Milestone 82: Backlog Burndown, Token Compliance & Manifest Sync)
- **Watcher Vault Sync Deduplication (Audit Row 8 / C5)**: Removed duplicate `sync_vault_telemetry` scan prior to `export_telemetry` in `scripts/watch_telemetry.py:423`, ensuring conversation vault synchronization runs strictly 1x per export cycle.
- **Accessible Horizontal Scroll Regions (Audit Row 9 / U4)**: Equipped 16 horizontal overflow table containers with `role="region"`, `tabindex="0"`, focus indicators, and descriptive `aria-label`s; unmasked `scrollable-region-focusable` in `e2e/a11y.spec.js`.
- **Anti-Generic Design Token Compliance (Audit Row 10 / D1)**: Replaced all 6 instances of banned `border-radius: 9999px` with canonical design tokens (`var(--radius-card, 6px)` and `--radius-pill`).
- **JavaScript Design Token Migration (Audit Row 11 / D2)**: Migrated 68 raw hex color codes across 8 frontend modules in `dashboard/js/*.js` to semantic CSS custom properties (`--accent-green`, `--accent-purple`, `--camel-500`, `--status-alert`, etc.).
- **Manifest & Git Tag Synchronization (Audit Row 12 / D3)**: Synchronized version declarations across `package.json`, `pyproject.toml`, and Git tags to `2.25.0`.
- **Frontend Modular Decomposition (Audit Row 13 / D4)**: Extracted rate history table and model taxonomy logic to `dashboard/js/plan-rates.js` (205 lines), dropping `plan-manager.js` to 622 lines; delegated shell mode logic to `dashboard/js/core-utils.js`, dropping `core.js` to 732 lines. All dashboard JS files strictly comply with ADR-066 (`<= 750` lines).

---

## [v2.24.0] - 2026-09-29 (Milestone 81 / Audit Row 5: U1 Lazy Tab Rendering to Eliminate Initial DOM Bloat)
- Implemented lazy tab activation tracking in `dashboard/js/core.js` to defer rendering `#view-sessions`, `#view-projects`, `#view-swarms`, `#view-billing`, and `#view-plan` until their navigation dock item is clicked.
- Slashed initial dashboard DOM element count from 8,392 nodes on boot to 1,353 nodes (an 83.9% reduction), remaining safely below the 1,500-element budget.
- Guarded ticker updates and sessions filter initializations to only touch active and previously rendered tab views.
- Preserved strict module size budgets with all JS scripts under the 800-line ceiling.

---

## [v2.24.0] - 2026-09-29 (Milestone 80 / Audit Row 4: C4 Model Census Exception Handling & Resilience)
- Fixed `load_model_census()` in `antigravity_telemetry/__init__.py` to catch `(OSError, json.JSONDecodeError)`, log warnings to `sys.stderr`, and return an empty dictionary `{}` instead of `None`, resolving downstream `TypeError` crashes in `get_model_truncation_threshold()`.
- Replaced silent `except Exception: pass` blocks across `antigravity_telemetry/`, `src/`, and `scripts/` with explicit exception types and targeted diagnostic logging.
- Added comprehensive unit test suite `TestModelCensusResilience` in `tests/test_truncation_thresholds.py` verifying fallback behavior with missing, corrupted, unreadable, and invalid census models.
- Added Python 3.14 cursor wrapper compatibility in `tests/test_vault.py`.

---

## [v2.24.0] - 2026-09-29 (Milestone 79 / Audit Row 3: C3 SQLite Connection Closure Hardening)
- Wrapped SQLite connection lifetimes in `src/vault.py` (`get_vault_truncation_markers`, `scan_conversation_truncation`) and `src/log_reader.py` (`reconstruct_ledger_from_vault`) with `conn = None` and `try...finally: if conn is not None: conn.close()`.
- Configured `timeout=60.0` and `PRAGMA busy_timeout = 60000;` on all connections per GADR-013 / ADR-081 SQLite Concurrency Resilience.
- Removed early return connection leaks and unhandled cursor exception bypasses.
- Added comprehensive unit test suites `TestVaultConnectionHardening` in `tests/test_vault.py` and `TestReconstructLedgerFromVaultConnectionHardening` in `tests/test_log_reader.py` with strict `ResourceWarning` hygiene.

---

## [v2.24.0] - 2026-09-29 (Milestone 78 / Audit Row 2: C2 Exporter SQLite Database Connection Leak Fix)
- Wrapped vault SQLite database connection in `scripts/export_dashboard.py:574` with `try...finally: vconn.close()`, resolving connection leak and eliminating `ResourceWarning: unclosed database`.
- Added `timeout=60.0` and `PRAGMA busy_timeout = 60000;` on vault read connection adhering to GADR-013 / ADR-081 SQLite Concurrency Resilience.
- Added regression unit test in `tests/test_export_dashboard.py` asserting clean connection closure during telemetry export.

---

## [v2.24.0] - 2026-09-29 (Milestone 77 / Audit Row 1: C1 VDONE Gates Subprocess Recursion Fix)
- Fixed circular `unittest discover` subprocess invocation in `tests/test_vdone_gates.py`.
- Skipped recursive full test suite discovery under `unittest` runner, preventing nested duplication and slashing test execution time.
- Hardened `tests/test_docs_integrity.py` to skip git tag assertions in tagless throwaway archive checkouts.

---

## [v2.24.0] - 2026-09-28 (Milestone 76 / Audit Row 10: C9 Scripts Governance Test Harnesses)
- Added comprehensive unit test suites `tests/test_quota_regression.py` and `tests/test_setup_github_guardrails.py`.
- Modernized `scripts/quota_regression.py` to import from `antigravity_telemetry` and added CLI parser with `--dry-run`.
- Modernized `scripts/setup_github_guardrails.py` with payload builder helpers, CLI parser, and safe offline `--dry-run` simulation.
- Documented governance and rate card scripts in `README.md` and registered new tests in `docs/REPO_MAP.md`.

---

## [v2.24.0] - 2026-09-28 (Milestone 75 / Audit Row 8: C7 Vault and Weekly Trends Circular Import Decoupling)
- Extracted canonical SQLite vault schema definition and initialization into standalone module `src/vault_schema.py`.
- Decoupled `src/vault.py` and `src/weekly_trends.py`, eliminating deferred inline imports inside function bodies in favor of clean top-level imports.
- Re-exported schema initialization and constants from `src/vault.py` for 100% backward compatibility.
- Added comprehensive unit test suite `tests/test_vault_schema.py` validating schema creation, migrations, isolation, and symbol identity.

---

## [v2.24.0] - 2026-09-28 (Milestone 74 / Audit Row 7: C6 Explicit Exception Handling & Targeted Logging)
- Replaced 15 silent `except Exception: pass` handlers in `scripts/export_dashboard.py`, `scripts/watch_telemetry.py`, and `src/log_reader.py` with explicit exception types and targeted `sys.stderr.write` warnings.
- Hardened status hook parsing, vault synchronization error paths, parent subagent correlation, and persistent ledger JSON loads against silent failures.

---

## [v2.24.0] - 2026-09-28 (Milestone 73 / Audit Row 9: C8 Simulator Pricing Alignment)
- Imported `get_model_rates` and `get_provider_quota_track` directly in `src/simulator.py` from `src.aggregator_pricing`, removing redundant and obsolete rate definitions.
- Enhanced `get_model_rates` in `src/aggregator_pricing.py` to support default pricing lookup, string model ID coercion, and temporal rate evaluation with timestamps.
- Added tie-breaker sort in `antigravity_telemetry/reader.py` and `src/vault.py` for deterministic SQLite sorting in clean checkouts.

---

## [v2.24.0] - 2026-09-26 (Milestone 72 / Audit Row 6: C5 Atomic Ledger & Demo Showcase Writes)
- Swapped direct file writes for `data/exhaustion_ledger.json` and demo showcases to atomic tempfile-and-rename pattern.
- Added comprehensive test suite `tests/test_atomic_writes.py`.

---

## [v2.24.0] - 2026-09-26 (Milestone 71 / Audit Row 5: D1 Version Manifest Synchronization)
- Enforced strict version parity across git tags, `pyproject.toml`, and `package.json` without bypass whitelists.
- Added `DocsIntegrityTest.test_version_manifest_sync` to ensure version manifest alignment in test suites.

---

## [v2.24.0] - 2026-09-26 (Milestone 70 / Audit Row 4: C4 Subprocess Timeout Hardening)
- Added explicit `timeout=` and `TimeoutExpired` exception handling across 28 `subprocess.run` and `subprocess.Popen` invocations in `src/` and `scripts/`.
- Authored AST test suite `tests/test_subprocess_timeouts.py` enforcing timeout parameters on all subprocess calls.

---

## [v2.24.2] - 2026-09-26 (Milestone 69 / Audit Row 3: C3 Watcher Thread Lock & Tempfile Safety)
- Added process-level `_status_lock = threading.Lock()` in `scripts/watch_telemetry.py` to serialize status updates between heartbeat thread and event triggers.
- Replaced fixed temporary file naming in `update_watcher_heartbeat` with unique tempfile names containing PID, thread ID, and UUID nonce.
- Added comprehensive multi-threaded concurrency unit test `test_update_watcher_heartbeat_concurrent_writes` and error cleanup tests.

---

## [v2.24.1] - 2026-09-26 (Milestone 68 / Audit Row 2: C2 Exporter Dry-Run Vault Isolation)
- Guarded `sync_subscription_to_vault()`, `sync_conversations_to_vault()`, and `sync_weekly_trends_to_vault()` in `scripts/export_dashboard.py` with `if not is_custom_dir and not dry_run:`.
- Enforced read-only weekly trend computation during `--dry-run` to protect `data/antigravity_vault.db` from side effects.
- Added regression test `test_export_dry_run_does_not_invoke_vault_sync` in `tests/test_export_dashboard.py`.

---

## [v2.24.0] - 2026-09-26 (Milestone 67 / Audit Row 1: C1 Vault Sync Mtime Gating & Batch Optimization)
- Implemented `st_mtime > last_sync_time` gating in `src/vault.py:sync_conversations_to_vault`, eliminating unconditional full-history SQLite scans and reducing sync latency from 88.9s to 0.13s (a 680x speedup).
- Added Fast Path bypass in `sync_conversations_to_vault` when no databases have changed and archive is populated, skipping full distinct conversation aggregation and lineage discovery.
- Scoped aggregate re-computation and subagent lineage queries to modified conversations rather than querying all historical records.
- Added `force: bool = False` argument to `sync_conversations_to_vault` and CLI `--force-full-scan` flag to `scripts/export_dashboard.py` (Owner Decision 1).
- Added SQLite retry logic with exponential backoff on `sqlite3.OperationalError` (database locked) and configured 60s busy timeouts for multi-process safety.
- Added comprehensive unit test suite `tests/test_vault_mtime_gating.py` and registered entry in `docs/REPO_MAP.md`.

---

## [v2.23.0] - 2026-09-25 (Milestone 66 / Audit Row 1: TI-2 Watcher Status Writes Restore & Self-Healing)
- Restored `status_path=effective_status_path` in `scripts/watch_telemetry.py` for both startup and settled exports, resolving the M65 regression where watcher exports stopped updating `~/.antigravity_quota_status.json`.
- Implemented status self-healing in `scripts/watch_telemetry.py` (`check_status_health`), detecting foreign or missing status files on heartbeat ticks and triggering rate-limited (60s) repair exports.
- Enabled SQLite WAL journal mode and normal synchronous mode in `src/vault.py:init_vault()`, permanently resolving database lock contention between background exports and concurrent test suites.
- Added comprehensive unit test suite `tests/test_status_self_heal.py` covering all self-heal and rate-limiting scenarios.
- Deduplicated `unittest discover` executions in `tests/test_vdone_gates.py`, ensuring full test suite completes in ~68s (<90s ceiling).

---

## [v2.22.0] - 2026-09-24 (Milestone 65 / Audit Row 1: TI-1 Unit Test Status File Isolation)
- Guarded `write_quota_status_file` in `scripts/export_dashboard.py` so direct library calls to `export_telemetry(...)` without `status_path` and without `output_dir` omit writing any status file, preventing test suite runs from mutating `~/.antigravity_quota_status.json`.
- Maintained CLI defaults in `scripts/export_dashboard.py:main()` so explicit executions without `--output-dir` default `status_path` to `DEFAULT_STATUS_PATH` (`~/.antigravity_quota_status.json`).
- Updated `tests/test_export_lock.py` and `tests/test_watch_telemetry.py` to isolate background watcher loops to temporary file paths.
- Added comprehensive regression test suite `tests/test_status_isolation.py` validating library isolation, CLI default behavior, `--output-dir` isolation, and explicit target handling.
- Passed acceptance gates B1–B4 and verified ADR-047 live pipeline operations.

---

## [v2.21.1] - 2026-09-22 (Showcase UI/UX Elevation & Repository Presentation)
- Overhauled public GitHub presentation with professional Shields.io badges, responsive visual feature showcase, and architecture flow diagram.
- Re-architected screenshot capture automation pipeline (`scripts/capture_showcase_screenshots.py`) with unblocked selectors and synchronous turns inspection.
- Generated high-definition Light Mode showcase assets for Quota Silos, Autonomous Swarms DAG tree, Thinking Token Inspector, and Git Branch Attribution.
- Hardened `dashboard/js/swarms.js` against undefined tool execution and bypass metrics.

---

## [v2.21.0] - 2026-09-21 (Milestone 64: Agent Persona Telemetry & Workflow Attribution)
- Extracted and decoded agent persona and subagent topology from upstream `trajectory_metadata_blob` wire format (Field 4 agent name/description, Field 10 config URI, Field 17 subagent flag, Field 5 parent UUID, Field 8 subagent spec) (ADR-078).
- Idempotently upgraded vault schema with `agent_name`, `agent_description`, `is_subagent`, `subagent_role`, and `raw_metadata_blob`, with high-performance 1-second backfill over 300+ historical sessions.
- Implemented recursive workflow cost attribution in `compute_agent_workflow_attribution`, rolling up child subagent consumption (`self`, `research`, `kb_writer`, `verifier`) to parent orchestrators (`implementer`, `auditor`, `default`).
- Labeled swarm lineage root nodes with persona-aware role titles (`Implementer (Orchestrator)`, `Auditor (Orchestrator)`) and added interactive `[⚡ N subagents]` pills linking directly to DAG topologies.
- Added Sessions view Hierarchy toggle (Main Sessions Only default vs. All vs. Subagents Only) and Agent Role dropdown filter.
- Added comprehensive unit test suite `tests/test_agent_telemetry.py` satisfying all acceptance gates B1-B5.

---

## [v2.20.1] - 2026-09-21 (Milestone 63 / Audit Row 18: Hermetic Fixture Export and Anonymized Baseline)
- Implemented hermetic fixture export with isolated HOME resolution and custom Antigravity directory path binding for `language_server.log` and `exhaustion_ledger.json` (ADR-077).
- Eliminated host PII and personal credit burn from golden baseline fixtures, ensuring deterministic offline test execution.
- Configured VDONE acceptance gates B1-B4 verifying hermetic fixture export and output completeness.

---

## [v2.20.0] - 2026-09-21 (Milestone 62 / Audit Row 17: C11 Aggregator Modularization Refactor)
- Modularized `src/aggregator.py` by extracting 6 cohesive submodules: `aggregator_pricing.py`, `aggregator_cycles.py`, `aggregator_windows.py`, `aggregator_coaching.py`, `aggregator_attribution.py`, and `aggregator_quotas.py`.
- Refactored `aggregate_global_telemetry` from 988 lines down to 229 lines, meeting the <250-line gate.
- Preserved 100% backward compatibility with complete `__all__` symbol re-export from `src.aggregator`.
- Byte-identical export determinism verified against golden fixture baseline.
- Added `tests/test_aggregator_modular.py` with dynamic turn stream interaction test.

---

## [v2.19.0] - 2026-09-21 (Milestone 61: Row 16 / U8 Mobile Viewport Polish, Ticker Clipping Fix & Table Scroll Wrappers)
- Fixed live token ticker left-clipping on <=768px and 375px mobile viewports by switching `.live-ticker-track` alignment to `flex-start` (ADR-075).
- Wrapped all 11 data tables in responsive `.table-scroll-wrapper` containers with persistent horizontal scrolling (`overflow-x: auto; -webkit-overflow-scrolling: touch;`).
- Added right-edge gradient fade indicator masks (`.table-scroll-fade`) that indicate scrollable overflow and dynamically hide when tables are scrolled to end.
- Added passive delegated scroll event listener in `dashboard/js/core.js` to manage `.scrolled-end` state on scroll wrappers with zero layout thrash.
- Added comprehensive unit and styling test suite (`tests/test_mobile_pass_and_scroll_wrappers.py`) and Playwright E2E mobile viewport audit (`e2e/mobile-pass.spec.js`).

---

## [v2.18.0] - 2026-09-20 (Milestone 60)
- Isolated Playwright E2E bridge out of default discover into `tests/e2e_bridge/test_playwright_e2e.py` (ADR-074).
- Added scheduled nightly browser workflow in `.github/workflows/e2e-nightly.yml`.
- Captured stdout/stderr leaks across unit tests via `contextlib.redirect_stdout`.
- Added `tests/test_suite_hygiene.py` to enforce zero output leakage.
- Added VDONE `python3 -c` automated acceptance verification to `tests/test_docs_integrity.py`.

---

## [v2.17.0] - 2026-09-20
- Added WAI-ARIA accessibility foundation (`role="tablist"`, `role="tab"`, `role="tabpanel"`, `role="progressbar"`, and `<caption class="sr-only">` on all data tables) (Milestone 59 / Row 14: U5/U6).
- Standardized visual focus rings (`:focus-visible`) and raised base typography to minimum 11px (`--font-xs: 0.6875rem`).
- Unified compact number formatting under canonical `formatCompactNumber` and standardized 2-decimal currency display outside turns inspector.

---

## [v2.16.0] - 2026-09-20
- Replaced menu bar app `/usr/bin/pgrep` polling with event-driven 10s watcher heartbeat timestamp (`watcher: {pid, heartbeat_utc}`) in `~/.antigravity_quota_status.json`, eliminating process spawning and ensuring 0.0% idle CPU (Milestone 58 / Row 13 / C10).
- Eliminated hardcoded personal workspace repository path literal in Swift companion app, establishing dynamic 3-tier path resolution (`dashboard_path`, `ANTIGRAVITY_DASHBOARD_REPO`, and home directory fallback) and added private workspace needles to publish sanitizer (Row 13 / C9).
- Added regression tests for private workspace needle sanitization and watcher heartbeat status hook schema.

---

## [v2.15.0] - 2026-09-20
- Added adaptive settle window to telemetry watcher (`max(2s, last_export_duration)`) to prevent exporter thrashing during long export cycles (Milestone 57).
- Added export duration logging (`export took {duration:.2f}s`) in watcher stdout and exposed `export_seconds` in `meta.json` / `meta.js`.
- Ensured byte-deterministic export durations under fixed reference time for offline testing and CI fixtures.

---

## Milestone 56: Lossless Unbounded Vault Codification, Backup Pruning & Vault Bytes Telemetry (v2.14.0 — 2026-09-20)
- **Lossless Unbounded Vault Codification (Row 10 / C6)**: Codified the telemetry archive in `data/antigravity_vault.db` as lossless and unbounded by design in `docs/SYSTEM_DESIGN.md` §Vault under Audit 2026-09-19 owner decision §7 #3, accepting an observed growth rate of approximately 1 GB/month under active development without destructive pruning.
- **Legacy Backup Pruning & DB Integrity**: Verified SQLite database health via `PRAGMA integrity_check` on the live vault and safely deleted redundant legacy backup file (`data/antigravity_vault.db.bak`), reclaiming storage space while maintaining zero-risk telemetry preservation.
- **Continuous Vault Telemetry Exposure in `meta.json`**: Added `vault_bytes` (integer size of `antigravity_vault.db`) to `sync_conversations_to_vault` stats, exposing the metric in `dashboard/meta.json` and `meta.js` during every sync and export cycle for continuous growth observability.

---

## Milestone 55: Minified data.js, Lazy-Loaded Turns & Truncation Marker (v2.13.0 — 2026-09-20)
- **Minified Decoupled `data.js` Projection (C5 / ADR-069)**: Dropped `data.js` footprint from 24 MB to ~660 KB (<3 MB gate) via dense serialization (`separators=(",", ":")`, `indent=None`, `sort_keys=True`) and decoupled per-conversation turn trajectories.
- **On-Demand Lazy-Loaded Turns (`turns.js`)**: Extracted all session turn trajectories into `dashboard/turns.js` (`window.__TELEMETRY_TURNS__`), loaded on-demand via dynamic script injection when opening the session inspector drawer or turns card; modularized drawer and turns table logic into `dashboard/js/sessions-turns.js` (472 lines), reducing `sessions.js` from 934 to 774 lines (<800 line invariant).
- **Ground-Truth Context Truncation Marker Fold-In**: Scanned conversation steps for `<CONTEXT_SUMMARY>` history compression markers; populated `has_truncated` (bool), `first_truncation_step` (int), and `depth_at_truncation` (int) across `data.json` and `data.js`, with 100% parity against vault `steps_archive` records.

---

## Milestone 54: Per-model truncation thresholds & paged Sessions (v2.12.0 — 2026-09-20)
- **Per-Model Context Truncation Thresholds (C4 / ADR-068)**: Added `context_truncation_tokens` to canonical 19-model census in `models.json` (1M for Gemini, 200k for Claude/GPT) with 200k fallback for unmapped model IDs.
- **Demoted Header Alarm**: Replaced permanent false red alarms with an amber-on-hover context depth badge, and gated the Now-tab warning strip to show only when the active session reaches >= 80% of its model limit.
- **Paged Sessions Explorer & Accordion Audit (U3)**: Client-side pagination (25 conversations per page) with sticky table headers and responsive pagination controls; moved the 24-hour truncation audit below the explorer table into a collapsed accordion with incident count badge.

---

## [v2.11.1] - Plan JS Restore & E2E Interaction Proofs (Milestone 53.1)
- **Plan JS & Simulator Restoration (ADR-067)**: Restored plan simulator interactivity, calculations, and event handlers following script decomposition.
- **Refactor Interaction Test Proof Standard**: Enforced mandatory interaction test validation for refactor milestones in AGENTS.md §3, avoiding load-only DOM snapshots.
- **E2E & Cleanliness Gates**: Verified all Playwright E2E interaction, layout regression, and cleanup gates.

---

## [v2.11.0] - Modular Plain Script Architecture & Single-Index Demo Unification (Milestone 53)
- **Modular Plain Script Architecture (Row 7.5, ADR-066)**: Decomposed `dashboard/app.js` into 7 specialized plain script files loaded in strict sequence from `index.html`: `js/core.js`, `js/now.js`, `js/sessions.js`, `js/projects.js`, `js/swarms.js`, `js/billing.js`, `js/plan.js`. All files adhere strictly to the <= 800 line ceiling with zero duplicate function definitions.
- **Single Compact-Number Formatter**: Collapsed legacy disparate compact formatters (`formatCompactTokens`, `formatTokensCompact`, `formatCompactNumber`) into a single canonical `formatCompactNumber` in `core.js`.
- **Showcase Demo Unification & `demo.html` Deletion (Row 12 / C8)**: Decommissioned and deleted `dashboard/demo.html`. Supported demo showcase mode natively in `dashboard/index.html?demo=1`, dynamically injecting synthetic demo payloads while retaining byte-deterministic script tags in a single entry file.
- **Byte-for-Byte HTML Regression Proof**: Asserted 100% byte-for-byte innerHTML equality across all 6 views (`now`, `sessions`, `projects`, `swarms`, `billing`, `plan`) against pre-split baseline captures via Playwright E2E (`e2e/app-js-split.spec.js`).

---

## [v2.10.0] - Plain-Language Now Tab Copy, Compact 1-Line Header & Mobile Optimization (Milestone 52)
- **Plain-Language Now Tab Copy (U1, ADR-065)**: Replaced internal engineering jargon across cards, badges, and simulator messages with plain English ("Quota right now", "Gemini", "Weekly pace", "Pace", "Claude & GPT"). Deleted redundant "Fallback Reserve Capacity" card. Zero occurrences of forbidden jargon (`contamination`, `spillover`, `governor`, `dual-track`, `dual-benchmark`, `family routing`, `isolation policy`) outside comments and tooltips.
- **Compact Single-Line Header (U2)**: Streamlined desktop header into a single line with `clamp(18px, 2.2vw, 26px)` title and height < 72px (measured at 55.8px). Added an overflow `⋯` dropdown menu for Copy Summary and secondary toggles.
- **Mobile Header Height Optimization (< 160px)**: Refactored mobile header layout with media queries hiding desktop settings toggles below 960px and compact badge wraps, reducing mobile header height from 572px to 140px (< 160px requirement).

---

## [v2.9.0] - Dashboard Boot & Pure Render Split, Delegated CSP Listeners & Plan Tier Default (Milestone 51)
- **Boot vs. Render Lifecycle Split (C3, ADR-064)**: Refactored `initDashboard()` into `bootOnce()` (wiring one-time event delegation, tooltips, modals, and simulator inputs guarded by `isBooted`) and `render(data)` (pure, idempotent DOM projection from telemetry data). Auto-reload now calls `render()` directly without listener leaks or UI flickering.
- **Strict Event Delegation & Zero Inline Handlers**: Removed all 61 inline `onclick=` handlers across `index.html`, `demo.html`, and `app.js` in favor of declarative `data-action` attributes and a centralized delegated click dispatcher, satisfying CSP and clean DOM separation.
- **Plan Tier Preset Defaulting**: Aligned `#plan-tier-select` with dynamic `summary.tier` (e.g. `ultra_5x`), eliminating hardcoded `pro` fallback across both plan profile and simulator selectors.

---

## [v2.8.0] - Dynamic UI Labels, Simulator Defaults & Canonical Light Mode (Milestone 50)
- **Dynamic Tier & Header Badges (C2)**: Eliminated hardcoded quota labels in `#sub-status-badge`, `#billing-cycle-badge`, and `#data-freshness-badge`, binding them dynamically to active subscription data and telemetry generation timestamps.
- **Simulator Dynamic Defaults & Overage Flag (U4)**: Defaulted simulator plan dropdown to payload tier (`summary.tier`), surfaced hard stop warning when `use_ai_credits: false`, and replaced LaTeX tokens with clear English labels.
- **Canonical Light Theme Default (U7, ADR-048)**: Restored light theme tokens as canonical `:root` variables, guaranteed default light mode initialization on clean storage, and verified cross-theme visual parity.

---

## [v2.7.0] - Export Advisory Lock, Unique Temp Files & Refresh Signaling (Milestone 49)
- **Exclusive Export Advisory Lock (C1)**: Acquired non-blocking `fcntl.flock` on `.export.lock` for all export operations, preventing concurrency collisions between the daemon watcher, menu bar app, and test runners.
- **Unique Atomic Temporary Files**: Replaced static `.tmp` filenames with `tempfile.NamedTemporaryFile` and atomic `os.replace` across `data.js`, `data.json`, `meta.js`, `meta.json`, `index.html`, and `status.json`.
- **Decoupled Refresh Signaling**: Configured macOS menu bar app to signal the background watcher daemon by touching `~/.antigravity_refresh_requested` or via `SIGUSR1`, eliminating concurrent duplicate exporter spawns.

---

## [v2.6.0] - Repository Consolidation, Ceremony Reduction & Automated Gate Runner (Milestone 48)
- **Active Acceptance Gate Runner**: Streamlined `VDONE.md` to lean always-on and milestone gates (<150 lines); introduced `tests/test_vdone_gates.py` executing all side-effect-free checks automatically; preserved historical V0–V260 register in `docs/milestones/VDONE_ARCHIVE_M01-M47.md`.
- **Project Front Door & Repository Map**: Condensed `README.md` into high-signal overview (<180 lines, zero milestone or ADR numbers); extracted capability history into `CHANGELOG.md` and repository tree into `docs/REPO_MAP.md`.
- **Decision Hub & Governance Hygiene**: Restructured `docs/HANDOVER.md` with concise ADR summaries (<=160 chars), line length ceiling (<=300 chars), and clear separation of active audit backlog rows 4–17 from closed items; codified documentation numbers rule and single exporter rule in `AGENTS.md`.

---

## Unified Context Safety Strip, Active Thread Disambiguation & Inline Audit Accordion (Milestone 47, ADR-061)
- **Active Health vs. Historical Audit Disentanglement**: Separated active session context health (<80k tokens = safe) from historical degraded sessions in the 24-hour audit log, eliminating misleading false-positive alarms.
- **Compact 1-Row Status Bar (~38px)**: Replaced intrusive full-width alert banners with a compact inline status bar (`.context-safety-strip`) and expandable accordion drawer (`[View Audit Log (N) ▾]`).
- **Pinned Active Branch Hero Card**: Pins the current active conversation at the top of the expanded drawer with live token count, branch badge, workspace attribution, and headroom to warning (`+45k tokens`).
- **Authoritative Branch & Workspace Attribution**: Clearly attributes historical offender sessions with Git branch badges and workspace names so offenders are immediately identifiable.
- **macOS Menu Bar (`AntigravityBar`) & Hook Sync**: Enriched `~/.antigravity_quota_status.json` with `current_session`, active branch, and headroom; updated native Swift popover view to highlight the pinned active thread and list historical offenders with branch badges.

---


## Session Context Boundary Hardening, DOM Structural Linting & Agent Session Hygiene (ADR-060)
- **Hard 25-Turn Session Ceiling (Rule of 25)**: Established mandatory proactive session handoffs before attention degradation and "Lost in the Middle" syndrome impair diagnostic accuracy on long-running tasks.
- **Mandatory Step 0 DOM Structural Tree Linting**: Mandated structural DOM tree verification before any visual CSS/JS debugging on layout issues, preventing misplaced or duplicated tags from derailing flexbox engines.
- **Subagent Quarantine for High-Volume Tools**: Mandated subagent delegation (`invoke_subagent`) for noisy test suites and large repository greps to preserve parent agent context depth (<30k tokens).
- **Hard Stop on `<CONTEXT_SUMMARY>`**: Codified the injection of `<CONTEXT_SUMMARY>` as an unambiguous signal that history has been truncated, requiring immediate session conclusion.
- **Authoritative Post-Mortem & Telemetry Audit**: Detailed analysis and empirical session telemetry (45MB DB, 143M cumulative tokens) documented in [`docs/SESSION_CONTEXT_DEGRADATION_AND_FRONTEND_POSTMORTEM.md`](docs/SESSION_CONTEXT_DEGRADATION_AND_FRONTEND_POSTMORTEM.md).


## Degraded Sessions Warnings & Context Boundary Hygiene (Milestone 46)
- **UI Warning Engine & Context Rot Protection**: Added `checkDegradedSessions` in `dashboard/app.js` using a 2-tier severity model (>80k amber warning, >200k critical red emergency truncation zone) with 24-hour recency auto-reset.
- **Visual Alert Banners & Handover Extraction**: Injected live warning badges across the top menu bar, contextual alerts in the "Now" tab, dedicated warning cards in the "Sessions" tab, and one-click `copyHandoverSummary(convoId)` for rapid continuation.


## Subagent Tracking Truncation Fix (Milestone 45)
- **Lossless Transcript Fallback**: Patched `src/vault.py`'s `sync_conversations_to_vault` to natively locate and read the un-truncated `transcript_full.jsonl` from the Antigravity system logs when available, completely bypassing upstream SQLite text truncation limits that were severing deep subagent swarms.


## Layout Fix & Playwright Upgrades (Milestone 44)
- **Geometric Viewport Assertions**: Overhauled the Playwright E2E suite to use true geometric assertions and pixel-perfect visual regression testing, and fixed a critical 50/50 flex layout collapse defect in the main inspector drawer layout.


## Playwright End-to-End Automated Testing & Front-End Visual Quality Architecture (Milestone 43 / ADR-059)
- **Automated Playwright E2E Test Suite**: Integrated `@playwright/test` executing headless Google Chrome (`channel: chrome`) against local static web fixtures, validating zero horizontal scrollbar overflow, zero console errors, interactive tab switching across 6 views, dual shell switching (sidebar rail vs top bar), theme toggling, currency switching, and drawer transitions.
- **Mandatory Front-End VDONE Quality Gates**: Established mandatory browser test execution and visual artifact generation gates (V253–V256) for any milestone touching front-end markup or stylesheets (`dashboard/`).
- **Zero Off-Screen Shadow Bleeding**: Eliminated 64px dark blur bleeding on the right viewport edge by removing `box-shadow` and enforcing `visibility: hidden; pointer-events: none;` on closed `.inspector-drawer` elements.
- **Seamless Rail Collapse Button**: Restyled the sidebar collapse toggle from an isolated floating white box into an integrated, transparent rail icon button in collapsed mode and an accessible full-width action bar in expanded mode.
- **Icon Differentiation**: Replaced the duplicate compass glyph on the brand anchor with an authentic orbital atom mark and updated the "Now" tab to a live activity pulse SVG.
- **Unified Python Test Bridge**: Added `tests/test_playwright_e2e.py` to seamlessly execute Playwright browser suites via `python3 -m unittest discover -s tests`.


## Layout Defect Elimination, Interactive Button Resilience & Persistent Icon Dock Rail (Milestone 42.2 / ADR-058)
- **Zero JS TypeError Crash Fix**: Replaced invalid `svg.getElementById()` calls with `document.getElementById()` in the trendline SVG scrubber, preventing premature runtime aborts and restoring 100% interactive responsiveness to header currency (`GBP/USD`), theme (`Light/Dark`), and shell switcher (`Sidebar/Top Bar`) buttons.
- **Persistent 64px Collapsed Dock Rail (Pattern A)**: Replaced 0px sidebar disappearance with the canonical 64px icon dock rail (`--dock-collapsed-w: 64px`) with centered Phosphor icons and tooltips, smoothly expanding to 240px (`--dock-expanded-w`) on user toggle with chevron rotate animation.
- **Zero Horizontal Overflow**: Constrained `.main-viewport` width to `calc(100% - var(--dock-collapsed-w))` and added `overflow-x: hidden; max-width: 100vw;` to `html, body` and `.app-layout`, permanently preventing horizontal scrolling across standard and wide desktop displays.
- **Complete Blue Purge**: Eradicated all residual RGB blues (`rgba(37, 99, 235, ...)`, `rgba(14, 165, 233, ...)`) and `var(--accent-blue)` across the What-If workload simulator, 5h burst governor session lists, weekly runway hero card, and trends KPIs in favor of Warm Camel `#D4A373`.


## Design System Refinement & Shell Usability (Milestone 42.1 / ADR-057)
- **Complete 0px Sidebar Collapse**: Replaces fragile hover-lock sidebar expansion with a persistent complete collapse (`.sidebar-collapsed` with `width: 0`, `overflow: hidden`, and `pointer-events: none`) triggered by a top header toggle (`#btn-sidebar-toggle`), cleanly freeing 100% of viewport width for complex multi-column telemetry tables.
- **Bidirectional Header Layout Switcher**: Adds an accessible header shell switcher (`#header-shell-toggle`) synchronized bidirectionally with the sidebar switcher and `localStorage`, and strictly suppresses duplicate tab navigation links in sidebar mode (`.shell-mode-side .workspace-command-strip .tab-buttons-group { display: none !important; }`).
- **100% Blue Purge**: Fully eliminates all residual Tailwind blues (`#3b82f6`, `#2563eb`, `#1d4ed8`, `#60a5fa`, `#38bdf8`, `#0ea5e9`, `#93c5fd`, `.badge.blue`) in favor of the canonical Warm Editorial palette (Warm Camel `#D4A373`, Forest Mint `#10B981`, and neutral contrast-calibrated badges).
- **Inline Phosphor SVG Iconography**: Standardizes all icons to clean inline Phosphor SVG glyphs across navigation links, action buttons, status pills, and summary cards, permanently eradicating raw emoji soup across the entire dashboard DOM.


## Canonical Eneas Design System Rollout & UI Unification (Milestone 42 / ADR-056)
- **3-Tier CSS Custom Property Dictionary & Warm Editorial Palette**: Completely aligns the dashboard with the canonical Eneas Design System across Dark mode (Smoked Obsidian `#0A0C0E`) and Light mode (Warm Parchment `#FBFBFA`), eliminating generic AI defaults (*Tailwind/shadcn fatigue*, bubbly rounded corners, and blue/purple gradients) with tactile hairlines, 6px card radius, and mechanical 60ms active depress physics.
- **Typography Standard (`Schibsted Grotesk` + `Geist Mono`)**: Embeds Google Fonts `Schibsted Grotesk` (display & body) and `Geist Mono` (code, tables, metrics), strictly enforcing `font-feature-settings: 'tnum' 1` across all token counters, timestamps, countdown clocks, and table cells.
- **Dual App Shell Architecture**: Implements Pattern A Collapsible Sidebar Dock (`#sidebar-dock`, `64px` icon dock / `240px` expanded with inline Phosphor SVG icons) and Pattern B Top Command Strip fallback, controlled via persistent `localStorage` preference switcher (`user_shell_preference` / `antigravity_shell_mode`), paired with a mobile bottom dock (<768px with 48px touch targets) and 3-way tab/theme/currency synchronization.
- **440px Slide-Over Inspector Drawer**: Introduces `#desktop-inspector-drawer` with backdrop blur, replacing layout-jumping `#turns-card` with a smooth slide-over trajectory view triggered on conversation row clicks with keyboard `Escape` dismissal.
- **Procedural SVG Visualizations Modernization**: Upgrades trendline and simulation trajectory SVGs with smooth Catmull-Rom cubic bezier splines, 1.75px stroke, 18% max gradient fill opacity, right-margin pinned corridor labels (`text-anchor="end"`), and tactile 6px multi-agent swarm DAG cards.


## Popover High-Contrast Executive Hierarchy (Milestone 41 / ADR-055)
- **High-Contrast Numerical Typography**: Resolves low-contrast visual fatigue in the macOS menu bar popover (`AntigravityBar`) by rendering all numbers and headroom metrics in crisp, high-contrast `.primary` typography (~13:1 contrast ratio against light backgrounds), mirroring the clean readability of the Weekly Quota Runway. Saturated color shifts are strictly reserved for genuine alert thresholds (warm amber when <=35%, vivid red when <15%).
- **Deep Forest Emerald Progress Bar**: Replaces neon lime progress bars with a calibrated Deep Forest Emerald (`#059669`), eliminating background glare and eye strain in Light Mode.
- **Refined Status Badges & Ticker Card**: Restyles the safe status indicator into a subtle neutral pill, renders live burn rates in bold primary text, and standardizes turn delta badges with neutral contrast-safe backgrounds.


## State-Adaptive Token Ticker HUD & 5-Hour Burst Integration (Milestone 40 / ADR-054)
- **State-Adaptive Navigation HUD**: Replaces static text badges and peripheral second-by-second clock counters (`🕒 0s ago`) with a clean, breathing green LED beacon (`●`). Dynamically exposes burn velocity (`⚡ ... tok/min`) exclusively when code is streaming, seamlessly contracting into a quiet monitoring state when idle.
- **Permanent 5-Hour Burst Volume Anchor**: Permanently anchors cumulative 5-hour rolling burst consumption and headroom (`5h: 18.4M tok · 74% free`) alongside a unified model and cache efficiency pill (`Model · Cache%`) across both active and idle states.
- **Zero-Bandwidth Micro-Telemetry**: Extends the ~570-byte `meta.js` payload with `gemini_5h_tokens` and `last_turn_cache_pct`, delivering high-precision 3-second HUD updates without re-fetching dataset arrays.
- **Dynamic macOS Menu Bar 5-Hour Burst Indicator**: Updates native Swift `AntigravityBar` (`StatusBarController.swift`) to display remaining burst quota volume (`⚡ 74% (18.4M)`) in the top menu bar, prepending an active breathing dot `●` and live burn rate (`▲ 2.1M/m`) during active turns, paired with a streamlined 2-row native SwiftUI popover card.


## Live Token Ticker HUD & macOS Menu Bar Monitor (Milestone 39 / ADR-053)
- **Token Ticker HUD & White Space Elimination**: Restructures navigation tab bar into a balanced flex layout, eliminating dead horizontal space with a live telemetry HUD: pulsing beacon (`● LIVE STREAM` / `● MONITORING`), real-time burn velocity (`⚡ ... tok/min`), green flash-animated turn delta (`▲ +... tok`), active model pill, and elapsed time counter.
- **Zero-Bandwidth Micro-Polling**: Enriches 570-byte `meta.js` with instant `ticker` metrics, providing real-time 3-second HUD updates with zero bandwidth waste and no re-fetching of the 18.8 MB dataset.
- **Dynamic macOS Menu Bar Burn Velocity**: Extends native Swift `AntigravityBar` (`StatusBarController.swift`) to dynamically append live burn speed (`▲ 2.1M/m`) in the macOS menu bar when actively generating code, contracting back to weekly and 5h burst percentages when idle, plus a dedicated Token Ticker card in the native popover.


## High-Frequency Live Refresh & Recency Inspection (Milestone 38 / ADR-052)
- **Sub-3s Live Auto-Refresh**: Near real-time client polling cadence (3 seconds) safely decoupled from the watcher daemon's 2.0s debounce settling window using lightweight 207-byte `meta.js` SHA-1 hash gating (zero DOM churn or payload fetch when idle).
- **Reverse-Chronological Turns Drawer**: Instant visibility into the newest turns and reasoning thoughts first with a 1-click interactive sort toggle button (`Newest First` vs `Oldest First`).
- **Temporal Git Branch Ordering**: Feature branches automatically sorted by latest activity timestamp (`last_active_timestamp`) with formatted calendar pills (`🕒 18 Sep, 11:45 UTC`) in project attribution drawers.
- **Weekly Quota Reset Synchronization**: Full alignment with Google AI Ultra 5x Sunday 17:58:04 UTC reset cycles, active weekly cycle pulse indicators, and automatic vault synchronization in `scripts/export_dashboard.py`.


## Light Mode Standard & Visual Showcase Overhaul (Milestone 34 / ADR-048 / v2.0.0)
- **Canonical Light Mode Elevation**: Reconfigures CSS design tokens (`:root`), browser pre-render bootstrapping, and headless screenshot captures to default to crisp, high-contrast Light Mode (`#f8fafc` canvas, `#ffffff` cards, `#e2e8f0` structural borders), while maintaining 100% responsive Dark Mode persistence via interactive client-side switching.
- **6-View Showcase Generation**: Automated headless Retina capture pipeline (`scripts/capture_showcase_screenshots.py`) delivering high-resolution Light Mode assets including the Subagent Swarm Lineage DAG and What-If Workload Simulator.


## Permanent Telemetry Vault & Historical Trends (Milestones 08, 26, 28 / ADR-018, ADR-039, ADR-041)
- **Lossless SQLite Vault**: Permanent store (`data/antigravity_vault.db`) archiving full decoded turn text, raw protobuf blobs (hybrid, zero `.pkl`), workspace attribution, and subagent DAG lineage across upstream IDE database purges.
- **8–12 Week SVG Trendline Chart**: Pure-Python weekly trends engine (`src/weekly_trends.py`) aggregating historical cycles with instant UI toggling between Processed Tokens, Cost & Overage, and Peak Burn Velocity.
- **Append-Only 429 Exhaustion Ledger**: Persistent ledger (`data/exhaustion_ledger.json`) preserving verified Google One credit overages (3,640 credits burned across 03–10 Sep 2026) resilient against upstream log file truncations.
- **Multi-Tier Plan Upgrades & Provenance**: Active tracking of Google AI Ultra 5x (£79.99/mo / $99.99/mo) and Pro tiers via temporal intervals in `config/pricing.json` and `subscription_history_archive`.


## Standalone Zero-Dependency Telemetry Package (`antigravity_telemetry` - Milestone 27 / ADR-040)
- **Independent Reusable Package**: Core pure-Python wire protobuf decoder and safe read-only SQLite connector extracted into an independent, zero-dependency Python package (`antigravity_telemetry/`) installable via standard `pyproject.toml`.
- **Clean Public API**: `read_all_turns()`, `discover_all_conversations()`, and `decode_wire_protobuf()`.
- **Canonical 19-Model Census**: Standardized catalog (`models.json`) covering all internal Antigravity model IDs (e.g. `1318` Gemini 3.8 Flash High, `1016` Gemini 3.1 Pro High, `1026` Claude Opus 4.6 Thinking, `342` GPT-OSS 120B) decoupled from pricing or quota logic.
- **Fast Standalone CLI**: `python -m antigravity_telemetry dump --json`, `conversations --json`, and `models --json`.


## Predictive Workload Simulation & Pre-Flight CLI Gating (Milestones 21, 29 / ADR-035, ADR-042)
- **Interactive "What-If" Workload Simulator**: Pure-Python simulation engine (`src/simulator.py`) and reactive client-side UI modeling multi-agent turn sequences (tokens, costs, 5h burst exhaustion, weekly runway, and 429 risk) before dispatching heavy swarms.
- **5 Multi-Agent Archetype Presets**: *Deep Refactor Swarm*, *Codebase Audit*, *Rapid Prototyping*, *Claude Opus Stress Test*, and *Subagent Fleet*.
- **Pre-Flight Budget Checker CLI**: `scripts/agy_quota.py --can-i-run <archetype|custom>` with deterministic exit codes (`0` SAFE/PROCEED vs `1` BLOCKED/429 RISK) for CI pipeline gating.
- **Byte-Deterministic Standup Digest**: Generates Markdown standup summaries (`scripts/export_dashboard.py --markdown`) and provides a 1-click UI clipboard button (`📋 Copy Summary`).


## Authoritative Git Reflog & Multi-Workspace Attribution (Milestones 11, 33 / ADR-022, ADR-046, ADR-047)
- **Temporal Reflog Source of Truth**: Resolves Antigravity's static conversation database snapshot limitation (where checkouts collapsed into `main`, inflating `main` to 80%+ turns) by extracting Git reflog (`.git/logs/HEAD`) transitions.
- **Microsecond Turn Attribution**: Correlates nanosecond turn timestamps against dynamic checkout intervals, resurrecting historical feature branches with zero token leakage.
- **Anti-Bloat Modular Architecture**: Reflog parsing and LRU interval caching live in standalone zero-dependency module `src/git_timeline.py` (<320 lines) connected via a minimal ~25-line hook in `src/aggregator.py`.
- **Operational Quality Gates & Live Daemon Protocol (ADR-047)**: Mandates live export (`scripts/export_dashboard.py`) to refresh `dashboard/data.js` against authentic databases, LaunchAgent daemon kickstart (`scripts/setup_service.py restart`), and status assertion across quality gates.
- **Multi-Project Workspace Attribution**: Extracts root workspace paths directly from `trajectory_metadata_blob` and `agyhub_summaries_proto.pb`.


## Dual-Track Quota Silos & Runway Governor (Milestones 09, 17, 32 / ADR-019, ADR-031, ADR-045)
- **Independent Provider Quota Silos**: Isolates **Track 1 (Google Gemini)** with Google One AI credit bank spillover from **Track 2 (Anthropic Claude & GPT on Vertex)** which enforce hard HTTP 429 blockouts with zero credit spillover.
- **Dynamic Weekly Reset Cycle Bounds**: Dynamically anchors cycle boundaries to the active subscription profile (Sunday 17:58:04 UTC for Ultra 5x, Thursday 18:00 UTC for Pro era), synchronized live with Connect-RPC desktop indicator `reset_time`.
- **Weekly Quota Runway & Burn Velocity**:
  - Smooths early-cycle burn rate to avoid false alarms in the first 48 hours of a billing cycle.
  - Clear pacing indicators showing whether your current burn rate is ahead of or behind your weekly quota budget.
- **5-Hour Rolling Burst Monitor**: Visualizes continuous sliding-window quota headroom, burst turn count, live refresh countdown clock (*"It will fully refresh in 4 hours, 12 minutes"*), and 20-bucket SVG staircase recovery gauge (Safe $\ge 50\%$, Comfortable $\ge 80\%$, Full $100\%$).


## Subagent Lineage & Tool Performance Intelligence (Milestone 24 / ADR-037)
- **Interactive Parent-Child DAG Layout**: Reconstructs true multi-agent swarm lineages from `data/antigravity_vault.db` (`invoke_subagent` tool calls), rendering clean, acyclic interactive SVG hierarchy graphs in 100% offline browser execution.
- **3-Tier Subagent Routing Economics**: Automatically partitions agent swarms into standard tiers:
  - **Mechanical Execution Tier** (Model `1050` / Gemini Flash Lite)
  - **Standard Engineering Tier** (Model `1322` / Gemini Fast Agent Assistant)
  - **Complex Architecture Tier** (Model `1036` / Gemini 3.1 Pro Low Reasoning)
- **Runtime Tool Execution Analytics**: Deep metrics across 23 tools and 10,000+ invocations (`src/tool_analytics.py`), quantifying terminal sandbox bypass ratios, tool failure rates, and skill activation distribution.


## Native macOS Menu Bar Monitor (`AntigravityBar` - Milestone 37 / ADR-051)
- **Ambient Menu Bar Presence**: Standalone native Swift 6 menu bar application (`dist/AntigravityBar.app`, 356 KB, 0.0% idle CPU, ~22 MB RAM) providing continuous peripheral quota awareness directly in the macOS top bar.
- **Glanceable Numbers with Native SF Symbols**: Displays real-time Weekly Quota Runway (`calendar` 📅) and 5-Hour Rolling Burst headroom (`bolt.fill` ⚡) in cognitive hierarchy matching the Antigravity IDE: `📅 100%  ⚡ 100%`.
- **Adaptive Health-Aware Typography**: Monochrome typography during normal work (>35% headroom), transitioning to warm amber on caution (15%–35%), and vivid red on exhaustion or 429 burst cooldown (<15%).
- **Interactive SwiftUI Popover Card**: Click to expand a rich popover showing weekly quota runway percentage, dynamic calendar reset countdown, Bayesian BVI pacing verdict, 5-hour rolling burst headroom with recovery countdown, isolated Claude/GPT secondary track, active workspace/branch, and prepaid credit bank balance.
- **Live Watcher Daemon Heartbeat**: Real-time daemon liveliness indicator (`● Watcher Live` / `⚠️ Watcher Inactive`) with 1-tap refresh.
- **Native Right-Click Context Menu**: Right-click or Control-click the status item for standard macOS controls: *Open Dashboard* (`⌘D`), *Reload Telemetry* (`⌘R`), *Watcher Daemon status*, and *Quit AntigravityBar* (`⌘Q`).
- **Enriched Executive Status Hook**: `scripts/export_dashboard.py` atomically writes pre-computed metadata to `~/.antigravity_quota_status.json`, inspected instantaneously (<5ms) via `scripts/agy_status.py -v`.


## Core Capabilities


