# Master Handover, Decisions & Milestone Index

## 1. Executive Summary & Handover Index

Authoritative handover hub, settled architectural decisions, milestone release register, and active backlog for the Antigravity Telemetry Dashboard.

## 2. Architecture Decision Records (ADRs)

| ID | Title | Status | Summary (<= 160 chars) | Milestone |
|---|---|---|---|---|
| ADR-001 | Strict Read-Only SQLite Access | Adopted | All SQLite DB connections must use URI read-only syntax (?mode=ro) to avoid corrupting or locking live IDE sessions. | [doc](milestones/M01_REPO_INITIALIZATION.md) |
| ADR-002 | Pure-Python Wire Protobuf Decoding | Adopted | Decode varints and length-delimited wire protobufs directly in pure standard Python without protoc compilation. | [doc](milestones/M01_REPO_INITIALIZATION.md) |
| ADR-003 | Dual-Mode Dashboard Execution | Adopted | Support both single-file offline HTML dashboard (open dashboard/index.html) and near real-time live watcher daemon. | [doc](milestones/M01_REPO_INITIALIZATION.md) |
| ADR-004 | Byte-Deterministic HTML Export Hook | Superseded (by ADR-024) | Inject sorted, deterministic JSON into script tag in index.html to maintain clean git trees without timestamp drift. | [doc](milestones/M01_REPO_INITIALIZATION.md) |
| ADR-005 | Configurable Model Pricing Tier Matrix | Adopted | Pricing rates per million tokens are maintained in config/pricing.json with fallback defaults for unmapped model IDs. | [doc](milestones/M01_REPO_INITIALIZATION.md) |
| ADR-006 | Verifiable Acceptance Gates & Slices | Adopted | Non-trivial work requires explicit executable gates in VDONE.md (CHECK and EXPECT) and durable records in milestones/. | [doc](milestones/M01_REPO_INITIALIZATION.md) |
| ADR-007 | 3-Tier Subagent Allocation Standard | Adopted | Strict model tiering (flash_lite mechanical, flash engineering, inherit/pro architecture) with zero-collision scopes. | [doc](milestones/M01_REPO_INITIALIZATION.md) |
| ADR-008 | Proactive Context Boundary & Handoff | Adopted | Proactively call milestone boundaries upon completion, commit with clean tree, and instruct fresh session handoff. | [doc](milestones/M01_REPO_INITIALIZATION.md) |
| ADR-009 | Rolling Quota & Subscription Value | Adopted | Differentiate included Pro subscription quota (5h rolling burst, 1w rolling aggregate) from out-of-pocket credit burn. | [doc](milestones/M02_ROLLING_QUOTA_ALLOWANCES.md) |
| ADR-010 | Hybrid Overage Detection & Credit Burn | Adopted | Reconcile Google One AI credit overages using model compute rates fusing log-anchored exhaustion with sliding window math. | [doc](milestones/M02b_AI_CREDIT_BURN_RECONCILIATION.md) |
| ADR-011 | Multi-Currency Cost Accounting (GBP) | Adopted | Calibrated GBP (£) accounting alongside USD ($0.01/credit) with instant client-side toggling across all dashboard cards. | [doc](milestones/M02b_AI_CREDIT_BURN_RECONCILIATION.md) |
| ADR-012 | High-Contrast Light & Dark Visual Themes | Adopted | Provide interactive client-side CSS theme switching with localStorage persistence in single-file deployment. | [doc](milestones/M02b_AI_CREDIT_BURN_RECONCILIATION.md) |
| ADR-013 | Debounced Dual-Source Telemetry Watcher | Adopted | Monitor SQLite WAL and runtime logs concurrently, debouncing exporter triggers with 2s settle window as macOS LaunchAgent. | [doc](milestones/M03_LIVE_WATCHER_SERVICE.md) |
| ADR-014 | Signal-Anchored 5h Overage & Cycles | Adopted | Anchor credit deductions exclusively to confirmed 429 server exhaustion intervals; align weekly reset to Thursday UTC. | [doc](milestones/M02c_QUOTA_CYCLE_ANCHORING.md) |
| ADR-015 | Decoupled Pro Plan & Overage Credit Bank | Adopted | Decouple Tier 1 fixed subscription from Tier 2 prepaid AI credits bank debited strictly when quota bursts. | [doc](milestones/M6_DUAL_TIER_PLAN_ARCHITECTURE.md) |
| ADR-016 | Persistent 429 Exhaustion Ledger Defense | Adopted | Ingest persistent append-only records from data/exhaustion_ledger.json resilient against upstream log truncation. | [doc](milestones/M6_DUAL_TIER_PLAN_ARCHITECTURE.md) |
| ADR-017 | Reasoning Effort Model ID Multiplexing | Adopted | Antigravity routes reasoning intensity sliders to distinct model IDs (Flash High 1318 vs. Medium 1319 with adaptive thinking). | [doc](milestones/M07_MODEL_BENCHMARK_TAXONOMY.md) |
| ADR-018 | Dedicated Local Telemetry Vault DB | Adopted | Permanent SQLite database (data/antigravity_vault.db) storing full decoded text, blobs, lineage, and tool indexing. | [doc](milestones/M08_TELEMETRY_VAULT_ARCHIVE.md) |
| ADR-019 | Dual-Track Provider Quota Silos | Adopted | Partition quotas across independent tracks: Gemini (weekly reset + 5h burst) vs. Claude/GPT (7d rolling age-out, hard-blocked). | [doc](milestones/M09_DUAL_TRACK_PROVIDER_QUOTAS.md) |
| ADR-020 | Autonomous Subagent 3-Tier Routing Matrix | Adopted | Subagents decouple from desktop selector, routing flash_lite to 1050, flash to 1322, and pro to 1036. | [doc](milestones/M07_MODEL_BENCHMARK_TAXONOMY.md) |
| ADR-021 | Official Rate Card Quota Weighting | Adopted | Quota consumption scales proportionally to model token cost with prompt cache discount; calibrated against Connect-RPC. | [doc](milestones/M10_COST_WEIGHTED_QUOTA_CONVERGENCE.md) |
| ADR-022 | Multi-Project & Git Branch Attribution | Adopted | Extract authoritative workspace paths and active Git branches directly from metadata blobs inside SQLite databases. | [doc](milestones/M11_PROJECT_AND_BRANCH_INTELLIGENCE.md) |
| ADR-023 | Subscription Coverage vs. Actual Overage | Adopted | Distinguish included turns covered at zero marginal cost from actual out-of-pocket overage credit deductions. | [doc](milestones/M12_SUBSCRIPTION_VS_OVERAGE_ACCOUNTING.md) |
| ADR-024 | Decoupled Telemetry Data Hook (data.js) | Adopted | Decouple mutable telemetry JSON from index.html into git-ignored dashboard/data.js preserving 100% offline file:/// execution. | [doc](milestones/M13_SLIDING_WINDOW_RECOVERY_TIMELINE.md) |
| ADR-025 | Sliding-Window Quota Age-Out Timeline | Superseded (by ADR-082) | Continuous 5-hour quota headroom projection producing 15-minute bucket intervals and recovery milestones via responsive SVG. | [doc](milestones/M13_SLIDING_WINDOW_RECOVERY_TIMELINE.md) |
| ADR-026 | Watcher Graceful Restart & Atomic Export | Adopted | Atomic exporter writes via .tmp staging and os.replace; LaunchAgent KeepAlive and live data freshness sync badge. | [doc](milestones/M14_WATCHER_GRACEFUL_RESTART_SYNC.md) |
| ADR-027 | 3-Card Quota Triad & Marker Clustering | Adopted | Relocated 5h recovery timeline into 3-card auto-fit row alongside Gemini and Claude/GPT; downsampled trajectory points. | [doc](milestones/M15_3CARD_QUOTA_TRIAD_TIMELINE.md) |
| ADR-028 | Empirical Weekly Quota Exhaustion & Alarm | Adopted | Calibrated weekly capacity; automated 5h bar disabling on weekly exhaustion; dynamic alarm rendering with fallback callouts. | [doc](milestones/M16_WEEKLY_QUOTA_EXHAUSTION_ALARM.md) |
| ADR-029 | Credit Pack Auto-Reload Reconciliation | Adopted | Reconcile auto-reloading Google One credit packs upon exhaustion, maintaining active credit pool and cumulative burn tracking. | [doc](milestones/M16_WEEKLY_QUOTA_EXHAUSTION_ALARM.md) |
| ADR-030 | Empirical Claude Exhaustion Boundaries | Adopted | Calibrate Claude burst limits; document cross-provider model flip KV cache invalidations causing uncached token spikes. | [doc](milestones/M16_WEEKLY_QUOTA_EXHAUSTION_ALARM.md) |
| ADR-031 | Promoted 3-Panel Provider Quota Deck | Adopted | Promoted 3-panel command deck directly under header above tabs; Left Gemini, Center Runway Governor, Right Claude/GPT. | [doc](milestones/M17_QUOTA_SILOS_RUNWAY_HERO_DECK.md) |
| ADR-032 | Bayesian M-Estimate Shrinkage for BVI | Adopted | Resolved cycle-start false alarm via Bayesian M-estimate daily burn shrinkage (k=1.0) and cumulative daily ceiling floor. | [doc](milestones/M18_BAYESIAN_RUNWAY_SMOOTHING.md) |
| ADR-033 | Banked Buffer Surplus & Ceiling Marker | Adopted | Reframe ambiguous runway subtitle into Banked Buffer Surplus; added dashed ceiling marker and synchronized dual legend. | [doc](milestones/M19_BANKED_BUFFER_AND_CEILING_MARKER.md) |
| ADR-034 | Temporal Plan Profiles & Rate History | Adopted | Unified temporal interval schema in pricing.json; deterministic temporal resolver evaluating timestamp-aware model rates. | [doc](milestones/M20_TEMPORAL_PLAN_PROFILES.md) |
| ADR-035 | Interactive What-If Workload Simulator | Adopted | Deterministic simulation engine modeling multi-agent turn sequences, burst exhaustion, weekly runway, and plan tier comparisons. | [doc](milestones/M21_WHAT_IF_WORKLOAD_SIMULATOR.md) |
| ADR-036 | Frontend Asset Modularization & Status Hook | Adopted | Decomposed dashboard into styles.css, app.js, and index.html; added external status hook and fast CLI inspector. | [doc](milestones/M23_FRONTEND_MODULARIZATION_AND_STATUS_HOOK.md) |
| ADR-037 | Subagent Swarm Lineage DAG & Tool Engine | Adopted | Extracted subagent hierarchy DAG, tier economics, and tool execution analytics into dedicated modules; authored whitepaper. | [doc](milestones/M24_SUBAGENT_SWARM_AND_FINDINGS.md) |
| ADR-038 | Active Quota Attribution & Cache Coaching | Adopted | Partitioned 5h turns into per-session attribution; implemented cross-provider model-flip cache eviction diagnostics. | [doc](milestones/M25_ACTIVE_QUOTA_COACHING_AND_CONFIG.md) |
| ADR-039 | Historical Vault Trends & Trendline Chart | Adopted | Pure-Python weekly trends engine in vault DB; reconciles overage ledger; interactive SVG trendline chart on Billing tab. | [doc](milestones/M26_HISTORICAL_VAULT_TRENDS.md) |
| ADR-040 | Standalone Telemetry Package Extraction | Adopted | Extracted zero-dependency telemetry engine into importable antigravity_telemetry package with canonical 19-model roster. | [doc](milestones/M27_PACKAGE_ANTIGRAVITY_TELEMETRY.md) |
| ADR-041 | Google AI Ultra 5x Plan Upgrade | Adopted | Activated Ultra 5x tier with 5x capacity across Gemini and Claude, recording historical provenance in vault DB. | [doc](milestones/M28_GOOGLE_AI_ULTRA_PLAN_UPGRADE.md) |
| ADR-042 | Pre-Flight Budget Checker CLI & Digest | Adopted | Deterministic CLI capacity gating (--can-i-run), byte-deterministic Markdown standup digest, and unlimited vault scaling. | [doc](milestones/M29_WORKLOAD_GOVERNANCE_AND_PRECISION.md) |
| ADR-043 | Dynamic Quota Reset Anchoring & Day 13 | Adopted | Anchor weekly quota cycles dynamically to subscription transition timestamp; support live desktop reset sync. | [doc](milestones/M30_QUOTA_DATES_AND_RENEWAL_CALIBRATION.md) |
| ADR-044 | CI Offline Fixtures & Public Release | Superseded (by ADR-076) | Added anonymized fixtures and deterministic export flag; deferred aggregator refactor to prioritize stability. | [doc](milestones/M31_CI_OFFLINE_FIXTURES_AND_PUBLIC_RELEASE.md) |
| ADR-045 | Velocity BVI Dual-Line Framing | Adopted | Disambiguated BVI subtitle with two-tier format (signed verdict plus arithmetic proof operands) in muted typography. | [doc](milestones/M32_BVI_BUFFER_DEFICIT_FRAMING.md) |
| ADR-046 | Git Reflog Temporal Branch Attribution | Adopted | Resolved branch attribution by parsing Git reflog checkout intervals in standalone module src/git_timeline.py. | [doc](milestones/M33_GIT_TEMPORAL_BRANCH_ATTRIBUTION.md) |
| ADR-047 | Live Pipeline & Daemon Operational Standard | Adopted | Mandated live pipeline validation with unsandboxed exports and service verification at milestone boundaries. | [doc](milestones/M33_GIT_TEMPORAL_BRANCH_ATTRIBUTION.md) |
| ADR-048 | Light Mode Default Visual Standard | Adopted | Established high-contrast Light Mode as canonical default visual theme across CSS and assets while preserving Dark Mode. | [doc](milestones/M34_README_V2_AND_LIGHT_THEME.md) |
| ADR-049 | Comprehensive Telemetry Sanitization | Adopted | Automated sanitization gates checking zero local user paths, zero leaked UUIDs, and authentic single-developer attribution. | [doc](milestones/M35_PRIVACY_HARDENING_AND_PUBLIC_RELEASE.md) |
| ADR-050 | Deterministic Synthetic Showcase Demo | Adopted | Engineered deterministic zero-PII synthetic showcase generator and automated GitHub Pages continuous deployment. | [doc](milestones/M36_GITHUB_PAGES_LIVE_SHOWCASE.md) |
| ADR-051 | Native macOS Menu Bar Monitor (AntigravityBar) | Adopted | Native Swift 6 menu bar app consuming status hook with SF Symbols, adaptive colors, and rich SwiftUI popover card. | [doc](milestones/M37_NATIVE_MAC_MENU_BAR_MONITOR.md) |
| ADR-052 | Sub-3s Refresh & Reverse Chronological Order | Adopted | Decoupled frontend via 207-byte meta.js SHA-1 hash gating; inverted turns drawer and branch tables to reverse chronological. | [doc](milestones/M38_DASHBOARD_RECENCY_AND_CYCLES.md) |
| ADR-053 | Live Token Ticker HUD & Micro-Polling | Adopted | Token velocity engine calculating rolling burn rates with zero-bandwidth micro-polling via enriched meta.js payload. | [doc](milestones/M39_LIVE_TOKEN_TICKER_AND_WHITE_SPACE.md) |
| ADR-054 | State-Adaptive Ticker & 5h Burst Integration | Adopted | Decommissioned second counter; state-adaptive velocity active during generation; anchored cumulative 5h burst headroom. | [doc](milestones/M40_STATE_ADAPTIVE_TICKER_AND_5H_BURST.md) |
| ADR-055 | Popover High-Contrast Executive Hierarchy | Adopted | Crisp high-contrast typography in native macOS popover; Forest Emerald progress bar and semantic alert boundary colors. | [doc](milestones/M41_POPOVER_CONTRAST_AND_VISUAL_HIERARCHY.md) |
| ADR-056 | Canonical Eneas Design System Rollout | Adopted | Rollout of 3-tier CSS custom properties, Warm Editorial palette, dual app shell, and slide-over inspector drawer. | [doc](milestones/M42_DESIGN_SYSTEM_ALIGNMENT.md) |
| ADR-057 | Design System Refinements & Phosphor Icons | Adopted | Persistent sidebar collapse, bidirectional layout switcher, complete blue purge to Warm Camel, and Phosphor SVG standard. | [doc](milestones/M42.1_DESIGN_SYSTEM_REFINEMENT.md) |
| ADR-058 | Layout Defect Elimination & Persistent Dock Rail | Adopted | Restored persistent 64px vertical icon dock rail, mathematically constrained viewport width, and fixed JS runtime errors. | [doc](milestones/M42.2_LAYOUT_DEFECT_ELIMINATION.md) |
| ADR-059 | Playwright E2E Testing & Visual Quality | Adopted | Integrated Playwright browser test suite with automated visual quality specs and Python bridge test harness. | [doc](milestones/M43_PLAYWRIGHT_E2E_VERIFICATION.md) |
| ADR-060 | Session Context Boundary Hardening | Adopted | Codified 25-turn session ceiling, DOM structural tree linting, and subagent quarantine for high-volume CLI test runs. | [doc](milestones/M46_DEGRADED_SESSIONS_WARNINGS.md) |
| ADR-061 | Unified Context Safety Strip & Active Branch | Adopted | Compact context safety strip (~38px) with expandable accordion drawer, pinned active session card, and branch badges. | [doc](milestones/M47_UNIFIED_CONTEXT_SAFETY_AND_BRANCH_ATTRIBUTION.md) |
| ADR-062 | Exporter Advisory Lock & Concurrency Control | Adopted | Exclusive advisory flock on .export.lock, unique temporary files, and manual refresh signaling via status file. | [doc](milestones/M49_EXPORT_LOCK.md) |
| ADR-063 | Dynamic UI Labels, Simulator Defaults & Canonical Light Mode | Adopted | Dynamic tier and renewal labels, simulator payload defaults, plain English labels without LaTeX tokens, and light theme default. | [doc](milestones/M50_LABELS_AND_SIMULATOR_DEFAULTS.md) |
| ADR-064 | Dashboard Boot & Pure Render Lifecycle Split | Adopted | Split initDashboard into one-time bootOnce and pure render(data); replaced 61 inline onclick handlers with data-action delegation. | [doc](milestones/M51_DASHBOARD_BOOT_REFACTOR.md) |
| ADR-065 | Plain-Language Now Copy & Compact Single-Line Header | Adopted | Plain English Now tab copy, zero engineering jargon, compact 1-line desktop header (<72px), mobile header (<160px), and overflow menu. | [doc](milestones/M52_PLAIN_HEADER_AND_NOW_COPY.md) |
| ADR-066 | Modular Plain Script Architecture & Single-Index Demo Unification | Adopted | Split dashboard/app.js into 7 sequential plain scripts (<800 lines each, no bundler, offline file:// safe); unified showcase on index.html?demo=1 and decommissioned demo.html. | [doc](milestones/M53_MODULAR_SCRIPTS_AND_SINGLE_INDEX.md) |
| ADR-067 | Interaction Test Proof for Refactors | Adopted | Refactor milestones must prove behavior with interaction tests, not load-only DOM snapshots. | [doc](milestones/M53.1_PLAN_JS_RESTORE.md) |
| ADR-068 | Per-Model Truncation & Paged Sessions | Adopted | Per-model context truncation thresholds in models.json, demoted amber header badge, and paged Sessions explorer. | [doc](milestones/M54_TRUNCATION_PER_MODEL_AND_PAGING.md) |
| ADR-069 | Decoupled Lazy Turns & Context Truncation Markers | Adopted | Minify data.js (<1 MB) decoupling turns to turns.js on-demand; record <CONTEXT_SUMMARY> has_truncated markers. | [doc](milestones/M55_MINIFIED_DATA_AND_LAZY_TURNS.md) |
| ADR-070 | Lossless Vault & Bak Cleanup | Adopted | Unbounded vault (~1 GB/mo), purge 1.9GB .bak, record vault_bytes. | [doc](milestones/M56_VAULT_INTEGRITY_AND_BAK_REMOVAL.md) |
| ADR-071 | Watcher Adaptive Cadence | Adopted | Adaptive debounce max(2s, dur), export_seconds. | [doc](milestones/M57_WATCHER_ADAPTIVE_CADENCE_AND_EXPORT_DURATION.md) |
| ADR-072 | Menubar Path Sanitization & Watcher Heartbeat | Adopted | Sanitize Swift path literal via status hook/env; replace pgrep with 10s watcher heartbeat. | [doc](milestones/M58_MENUBAR_HYGIENE_AND_WATCHER_HEARTBEAT.md) |
| ADR-073 | Accessibility Baseline, WCAG Contrast & Formatter Unification | Adopted | WAI-ARIA roles, SVG titles, sr-only table captions, :focus-visible outlines, single formatCompactNumber, and 2-decimal money. | [doc](milestones/M59_A11Y_BASELINE_AND_UNITS.md) |
| ADR-074 | E2E Bridge Isolation, Nightly CI & Test Output Hygiene | Adopted | Move Playwright bridge to tests/e2e_bridge/, nightly browser CI workflow, and silence test stdout leaks. | [doc](milestones/M60_E2E_BRIDGE_AND_TEST_CEREMONY.md) |
| ADR-075 | Mobile Viewport Polish, Ticker Clipping Fix & Table Scroll Wrappers | Adopted | Eliminate ticker left clipping via flex-start at <=768px; add overflow-x wrappers with right-edge fade across all tables. | [doc](milestones/M61_MOBILE_PASS_AND_SCROLL_WRAPPERS.md) |
| ADR-076 | Aggregator Modularization Refactor | Adopted | Decomposed src/aggregator.py into 6 focused submodules (<800 lines each) and aggregate_global_telemetry into modular stages (<250 lines). | [doc](milestones/M62_AGGREGATOR_MODULARIZATION_REFACTOR.md) |
| ADR-077 | Hermetic Fixture Export & Anonymized Baseline | Adopted | When --antigravity-dir is custom, resolve language_server.log and exhaustion_ledger.json to <dir>, eliminating host PII and personal credit burn from golden fixtures. | [doc](milestones/M63_HERMETIC_FIXTURE_EXPORT.md) |
| ADR-078 | Agent Persona Telemetry & Workflow Attribution | Adopted | Wire decode Field 4/10 agent persona and Field 17/5/8 subagents; backfill vault; attribute workflow costs to orchestrators. | [doc](milestones/M64_AGENT_PERSONA_TELEMETRY.md) |
| ADR-079 | Bounded Adaptive Watcher Debounce Ceiling | Adopted | DebounceController settle window enforces a strict 10.0s upper clamp, preventing daemon export freezes across system sleep states. | [doc](milestones/M64_AGENT_PERSONA_TELEMETRY.md#7-audit--remediation-post-mortem-audit-2026-09-22--rows-18) |
| ADR-080 | Automated Headless Browser Gate for UI Slices | Adopted | Frontend milestones must include automated headless Playwright console error verification in VDONE.md before declaring done. | [doc](milestones/M64_AGENT_PERSONA_TELEMETRY.md#7-audit--remediation-post-mortem-audit-2026-09-22--rows-18) |
| ADR-081 | SQLite Concurrency Resilience & Repo Map Integrity | Adopted | Ratify GADR-013 concurrency practices in vault.py and enforce REPO_MAP registration pre-commit. | [doc](milestones/M67_EVOLUTION_RESOLUTION.md) |
| ADR-082 | Discrete 5-Hour Quota Reset Epochs & Compaction Safeguards | Adopted | Replace rolling-burst 5h model with Connect-RPC discrete resetTime epochs; document 10-request FIFO prompt compaction ceilings. | [doc](ADR-082-discrete-5h-quota-reset.md) |
| ADR-083 | Two-Tier Fast Ticker Exporter & Menu Bar Epoch Badge | Adopted | Decouple <20ms active session WAL meta.js/status ticker from 30-60s debounced data.js rollup; dynamic E1..E5 badge in AntigravityBar. | [doc](milestones/M86_MENUBAR_EPOCH_AND_TWO_TIER_EXPORTER.md) |
| ADR-084 | Incremental Cached Exporter & Sub-Second Heavy Rollup | Adopted | Two-tier in-memory and persistent SQLite cache (.export_cache.db) with fingerprint gating, cached vault queries, and 2.0s watcher settle window. | [doc](milestones/M87_INCREMENTAL_CACHED_EXPORTER.md) |
| ADR-085 | Dashboard Executive Cockpit & Menu Bar Parity | Adopted | High-contrast Executive Hero Card mirroring macOS popover, false-alarm session banner elimination, and collapsible telemetry drawer. | [doc](milestones/M88_EXECUTIVE_COCKPIT_AND_MENUBAR_PARITY.md) |
| ADR-086 | Claude 5.5 Model Census & Reasoning Taxonomy | Adopted | Register 6 Claude 5.5 models (1400–1405: Opus/Sonnet Low/Med/High), preserve legacy 1026/1035 metrics, and route to claude_gpt track. | [doc](milestones/M89_CLAUDE_55_MODEL_CENSUS_EXPANSION.md) |
| ADR-087 | Telemetry Vault Compound & Partial Indexing | Adopted | Sub-millisecond range seeks on (step_type, ts, model) and (convo_id, ts); partial indexes on error_text and code. | [doc](milestones/M90_VAULT_QUERY_OPTIMIZATION_AND_INDEXING.md) |
| ADR-088 | Structured Rate-Limit & Error Flag Extraction | Adopted | Reject FTS5 bloat (+3GB); extract rate_limit_flag and error_code into steps_archive with partial index acceleration. | [doc](milestones/M90_VAULT_QUERY_OPTIMIZATION_AND_INDEXING.md) |
| ADR-089 | Self-Documenting Telemetry Reference Dictionaries | Adopted | Add ref_step_types and ref_status_codes in SQLite schema to eliminate magic numbers from queries and reports. | [doc](milestones/M90_VAULT_QUERY_OPTIMIZATION_AND_INDEXING.md) |
| ADR-090 | Canonical Telemetry Analytical Views | Adopted | Pre-filtered SQL views (v_turns, v_hourly_token_velocity, v_active_sessions, v_rate_limit_events) for instant analytics. | [doc](milestones/M90_VAULT_QUERY_OPTIMIZATION_AND_INDEXING.md) |
| ADR-091 | Empirical DB Benchmarking & KPI Governance Harness | Adopted | Standalone harness (scripts/bench_vault_performance.py) measuring latency, rows scanned, footprint, and write overhead. | [doc](milestones/M90_VAULT_QUERY_OPTIMIZATION_AND_INDEXING.md) |
| ADR-092 | Multi-Agent Swarms & Weakest-Link Degradation Scoring | Adopted | Decouple current capacity load (latest turn $t_n$) from compaction epoch drift ($E1..E3+$); elect weakest link across orchestrators and subagents; bubble up critical subagents in macOS popover and web header; group sessions by project into active swarms. | [doc](milestones/M91_MULTI_AGENT_CASCADE_DEGRADATION.md) |
| ADR-093 | Gemini 4 Argon Frontier Model Census & Two-Era Pricing | Adopted | Register Gemini 4 Argon High/Med/Low (1417–1419) under gemini-argon family (1M context, 250k compaction), configure two-era pricing ($2/$0.10/$10 until Nov 30, $4/$0.20/$20 Dec 1+), and sunset Gemini 3.1 Pro (1016, 1036). | [doc](milestones/M92_GEMINI_4_ARGON_MODEL_CENSUS.md) |
| ADR-094 | Live Quota Snapshot Archival & Fast Monitor Convergence | Adopted | Archive deduplicated Connect-RPC quota snapshots in vault DB with v_quota_burn_intervals view; fix BST glog parsing, add <0.5ms 429 tail-scan clamping and 15s fast-tier quota sync, write status hook pre-vault, and de-bloat vault_cache (5.64 MB). | [doc](milestones/M93_QUOTA_SNAPSHOT_OBSERVER_AND_FAST_MONITOR.md) |
| ADR-095 | Ultra Capacity Calibration, Reset Bonus & Post-Reset Weights | Adopted | Calibrate Ultra 5x capacity ($25/$100, 4.0x ratio), record QUOTA_RESET_BONUS, verify Gemini 4 0.50x Intro API weight ($1.00/$0.050/$5.00) & Flash 1/6x weight, and backfill wire TTFT. | [doc](milestones/M94_ULTRA_CAPACITY_KV_COACHING_AND_WIRE_LATENCY.md) |
| ADR-096 | Logical Vault Cache Fingerprinting, Bisect Regime Slicing & Delta Sync | Adopted | Key vault_cache on logical table rowid/state, persist horizon_analytics in SQLite cache, slice regime turns via bisect_right, and scope weekly trends to active cycle. | [doc](milestones/M94_ULTRA_CAPACITY_KV_COACHING_AND_WIRE_LATENCY.md) |
| ADR-097 | Gemini 4 Carbon Frontier Model Census & GPT-OSS Sunset Notice | Adopted | Register Gemini 4 Carbon High/Med/Low (1427, 1437, 1438) under gemini-carbon family (1M context, 250k compaction), two-era pricing, 0.50x Intro API quota weights ($1.00/$0.050/$5.00 = $50 5h / $200 wk), and 342 sunset (2026-11-18). | [doc](milestones/M99_GEMINI_4_CARBON_MODEL_CENSUS.md) |

---

## 3. Milestone Index

> Note: Milestones M04 and M05 were never allocated or used in this repository.

| Milestone | Date | Scope & Deliverables | Slice Document |
|---|---|---|---|
| M01 | 2026-09-01 | Repository scaffolding & spec | [doc](milestones/M01_REPO_INITIALIZATION.md) |
| M02 | 2026-09-02 | Rolling quotas & subscription value | [doc](milestones/M02_ROLLING_QUOTA_ALLOWANCES.md) |
| M02b | 2026-09-03 | AI credit burn reconciliation & GBP multi-currency | [doc](milestones/M02b_AI_CREDIT_BURN_RECONCILIATION.md) |
| M02c | 2026-09-04 | Quota cycle anchoring & signal-anchored overage | [doc](milestones/M02c_QUOTA_CYCLE_ANCHORING.md) |
| M03 | 2026-09-04 | Live watcher daemon & service packaging | [doc](milestones/M03_LIVE_WATCHER_SERVICE.md) |
| M06 | 2026-09-06 | Dual-tier plan & overage credit architecture | [doc](milestones/M6_DUAL_TIER_PLAN_ARCHITECTURE.md) |
| M07 | 2026-09-06 | Multi-model benchmark taxonomy & subagent discovery | [doc](milestones/M07_MODEL_BENCHMARK_TAXONOMY.md) |
| M08 | 2026-09-07 | Telemetry vault, lineage topology & archival skill | [doc](milestones/M08_TELEMETRY_VAULT_ARCHIVE.md) |
| M09 | 2026-09-07 | Dual-track provider quota silos | [doc](milestones/M09_DUAL_TRACK_PROVIDER_QUOTAS.md) |
| M10 | 2026-09-08 | Cost-weighted quota convergence & desktop sync | [doc](milestones/M10_COST_WEIGHTED_QUOTA_CONVERGENCE.md) |
| M11 | 2026-09-08 | Project & Git branch intelligence | [doc](milestones/M11_PROJECT_AND_BRANCH_INTELLIGENCE.md) |
| M12 | 2026-09-09 | Subscription coverage vs. actual overage accounting | [doc](milestones/M12_SUBSCRIPTION_VS_OVERAGE_ACCOUNTING.md) |
| M13 | 2026-09-09 | Sliding-window recovery timeline & live refresh | [doc](milestones/M13_SLIDING_WINDOW_RECOVERY_TIMELINE.md) |
| M14 | 2026-09-09 | Watcher graceful restart & atomic export sync | [doc](milestones/M14_WATCHER_GRACEFUL_RESTART_SYNC.md) |
| M15 | 2026-09-10 | 3-card single-row quota triad & downsampling | [doc](milestones/M15_3CARD_QUOTA_TRIAD_TIMELINE.md) |
| M16 | 2026-09-10 | Empirical weekly quota exhaustion & alarm states | [doc](milestones/M16_WEEKLY_QUOTA_EXHAUSTION_ALARM.md) |
| M17 | 2026-09-11 | Promoted 3-panel quota silos & runway governor deck | [doc](milestones/M17_QUOTA_SILOS_RUNWAY_HERO_DECK.md) |
| M18 | 2026-09-11 | Bayesian M-estimate shrinkage & diurnal pacing | [doc](milestones/M18_BAYESIAN_RUNWAY_SMOOTHING.md) |
| M19 | 2026-09-11 | Banked buffer framing & benchmark ceiling marker | [doc](milestones/M19_BANKED_BUFFER_AND_CEILING_MARKER.md) |
| M20 | 2026-09-12 | Temporal plan profiles & historical provenance | [doc](milestones/M20_TEMPORAL_PLAN_PROFILES.md) |
| M21 | 2026-09-12 | Interactive What-If workload simulator | [doc](milestones/M21_WHAT_IF_WORKLOAD_SIMULATOR.md) |
| M22 | 2026-09-12 | UI/UX ergonomics & jobs-based tabs architecture | [doc](milestones/M22_UI_UX_JOBS_BASED_TABS.md) |
| M23 | 2026-09-12 | Frontend modularization & external status hook | [doc](milestones/M23_FRONTEND_MODULARIZATION_AND_STATUS_HOOK.md) |
| M24 | 2026-09-12 | Subagent swarm lineage, tool analytics & findings | [doc](milestones/M24_SUBAGENT_SWARM_AND_FINDINGS.md) |
| M25 | 2026-09-13 | Active quota intelligence, cache coaching & config | [doc](milestones/M25_ACTIVE_QUOTA_COACHING_AND_CONFIG.md) |
| M26 | 2026-09-13 | Historical vault trends & SVG trendline chart | [doc](milestones/M26_HISTORICAL_VAULT_TRENDS.md) |
| M27 | 2026-09-13 | Standalone importable package antigravity_telemetry | [doc](milestones/M27_PACKAGE_ANTIGRAVITY_TELEMETRY.md) |
| M28 | 2026-09-13 | Google AI Ultra (5x capacity) plan upgrade & vault | [doc](milestones/M28_GOOGLE_AI_ULTRA_PLAN_UPGRADE.md) |
| M29 | 2026-09-14 | Workload governance, standup digest & precision | [doc](milestones/M29_WORKLOAD_GOVERNANCE_AND_PRECISION.md) |
| M30 | 2026-09-14 | Quota reset dates & monthly renewal calibration | [doc](milestones/M30_QUOTA_DATES_AND_RENEWAL_CALIBRATION.md) |
| M31 | 2026-09-14 | Pre-flight quota capacity planner CLI & exit codes | [doc](milestones/M31_PREFLIGHT_CAPACITY_PLANNER.md) |
| M32 | 2026-09-14 | Executive status hook & CLI integration | [doc](milestones/M32_EXECUTIVE_STATUS_HOOK.md) |
| M33 | 2026-09-15 | Enriched status hook & agy_status enhancements | [doc](milestones/M33_ENRICHED_STATUS_HOOK.md) |
| M34 | 2026-09-15 | Native macOS menu bar companion AntigravityBar | [doc](milestones/M34_MENUBAR_STATUS_APP.md) |
| M35 | 2026-09-15 | Menu bar package assembly & lifecycle management | [doc](milestones/M35_MENUBAR_CLI_LIFECYCLE.md) |
| M36 | 2026-09-15 | Clean-room offline fixture generator & test isolation | [doc](milestones/M36_OFFLINE_FIXTURE_ISOLATION.md) |
| M37 | 2026-09-16 | Canonical 19-model benchmark taxonomy & reasoning | [doc](milestones/M37_CANONICAL_MODEL_ROSTER.md) |
| M38 | 2026-09-16 | Rate-card spend proportional overage credit math | [doc](milestones/M38_RATE_CARD_OVERAGE_PROPORTION.md) |
| M39 | 2026-09-16 | Pure-Python packaging & zero-dep telemetry reader | [doc](milestones/M39_PURE_PYTHON_PACKAGING.md) |
| M40 | 2026-09-17 | Multi-repo telemetry discovery & Git branch linking | [doc](milestones/M40_MULTI_REPO_DISCOVERY_AND_GIT_LINKING.md) |
| M41 | 2026-09-17 | Deterministic synthetic showcase generation | [doc](milestones/M41_DETERMINISTIC_SYNTHETIC_SHOWCASE.md) |
| M42 | 2026-09-17 | Public repository showcase sanitization & publishing | [doc](milestones/M42_PUBLIC_REPO_SANITIZATION.md) |
| M42.1 | 2026-09-17 | Automated CI workflow hardening & test matrix | [doc](milestones/M42.1_CI_WORKFLOW_HARDENING.md) |
| M42.2 | 2026-09-17 | Layout defect elimination & persistent dock rail | [doc](milestones/M42.2_LAYOUT_DEFECT_ELIMINATION.md) |
| M43 | 2026-09-18 | Playwright E2E testing & visual quality | [doc](milestones/M43_PLAYWRIGHT_E2E_VERIFICATION.md) |
| M44 | 2026-09-18 | Layout fix & Playwright upgrades | [doc](milestones/M44_LAYOUT_FIX_AND_PLAYWRIGHT_UPGRADES.md) |
| M45 | 2026-09-18 | Subagent tracking truncation fix | [doc](milestones/M45_SUBAGENT_TRUNCATION_FIX.md) |
| M46 | 2026-09-18 | Degraded sessions warnings & context boundary hygiene | [doc](milestones/M46_DEGRADED_SESSIONS_WARNINGS.md) |
| M47 | 2026-09-18 | Unified context safety strip & branch attribution | [doc](milestones/M47_UNIFIED_CONTEXT_SAFETY_AND_BRANCH_ATTRIBUTION.md) |
| M48 | 2026-09-19 | Repository consolidation, documentation drift & ceremony | [doc](milestones/M48_CONSOLIDATION.md) |
| M48.1 | 2026-09-19 | M48 review fixes, EXPECT evaluator & fixture determinism | [doc](milestones/M48.1_REVIEW_FIXES.md) |
| M49 | 2026-09-19 | Export advisory lock, unique temp file & refresh signaling | [doc](milestones/M49_EXPORT_LOCK.md) |
| M50 | 2026-09-19 | Dynamic UI labels, simulator defaults & light theme standard | [doc](milestones/M50_LABELS_AND_SIMULATOR_DEFAULTS.md) |
| M51 | 2026-09-19 | Dashboard boot refactor, delegated listeners & plan tier default | [doc](milestones/M51_DASHBOARD_BOOT_REFACTOR.md) |
| M52 | 2026-09-20 | Plain-language Now tab copy, compact 1-line header & mobile height | [doc](milestones/M52_PLAIN_HEADER_AND_NOW_COPY.md) |
| M53 | 2026-09-20 | Split app.js into 7 sequential plain scripts (<800 lines), unified demo on ?demo=1, deleted demo.html | [doc](milestones/M53_MODULAR_SCRIPTS_AND_SINGLE_INDEX.md) |
| M53.1 | 2026-09-20 | Plan JS restore, interaction tests & V53 gates | [doc](milestones/M53.1_PLAN_JS_RESTORE.md) |
| M54 | 2026-09-20 | Per-model truncation thresholds & paged Sessions | [doc](milestones/M54_TRUNCATION_PER_MODEL_AND_PAGING.md) |
| M55 | 2026-09-20 | Minified data.js, lazy-loaded turns.js, context truncation markers | [doc](milestones/M55_MINIFIED_DATA_AND_LAZY_TURNS.md) |
| M56 | 2026-09-20 | Lossless vault preservation, .bak cleanup & vault_bytes | [doc](milestones/M56_VAULT_INTEGRITY_AND_BAK_REMOVAL.md) |
| M57 | 2026-09-20 | Watcher adaptive settle window & export duration telemetry | [doc](milestones/M57_WATCHER_ADAPTIVE_CADENCE_AND_EXPORT_DURATION.md) |
| M58 | 2026-09-20 | Sanitize Swift repo path literal & watcher heartbeat | [doc](milestones/M58_MENUBAR_HYGIENE_AND_WATCHER_HEARTBEAT.md) |
| M59 | 2026-09-20 | Accessibility baseline, ARIA roles, table captions & currency format unification | [doc](milestones/M59_A11Y_BASELINE_AND_UNITS.md) |
| M60 | 2026-09-20 | E2E bridge isolation, nightly CI & test suite hygiene | [doc](milestones/M60_E2E_BRIDGE_AND_TEST_CEREMONY.md) |
| M61 | 2026-09-21 | Mobile viewport polish, ticker clipping fix & table scroll wrappers | [doc](milestones/M61_MOBILE_PASS_AND_SCROLL_WRAPPERS.md) |
| M62 | 2026-09-21 | Aggregator modularization refactor, submodule decomposition & interaction gate | [doc](milestones/M62_AGGREGATOR_MODULARIZATION_REFACTOR.md) |
| M63 | 2026-09-21 | Hermetic fixture export, isolated HOME & anonymized golden baseline | [doc](milestones/M63_HERMETIC_FIXTURE_EXPORT.md) |
| M64 | 2026-09-21 | Agent persona telemetry & workflow attribution | [doc](milestones/M64_AGENT_PERSONA_TELEMETRY.md) |
| M65 | 2026-09-24 | Stop unit tests overwriting live menu-bar status file (TI-1) | [doc](milestones/M65_TEST_STATUS_ISOLATION.md) |
| M66 | 2026-09-25 | Restore watcher status writes after M65 and self-heal a foreign status file (TI-2) | [doc](milestones/M66_STATUS_SELF_HEAL.md) |
| M67 | 2026-09-26 | Vault sync mtime gating & batch query optimization (C1) | [doc](milestones/M67_VAULT_SYNC_MTIME_GATING.md) |
| M68 | 2026-09-26 | Gate vault sync with not dry_run in scripts/export_dashboard.py (C2) | [doc](milestones/M68_EXPORTER_DRY_RUN_ISOLATION.md) |
| M69 | 2026-09-26 | Add thread lock & unique tempfile prefix to update_watcher_heartbeat (C3) | [doc](milestones/M69_WATCHER_THREAD_LOCK_TEMP_SAFETY.md) |
| M70 | 2026-09-26 | Add explicit timeout= and error handling across 28 subprocess calls (C4) | [doc](milestones/M70_SUBPROCESS_TIMEOUT_HARDENING.md) |
| M71 | 2026-09-26 | Align version across Git tag, pyproject.toml, and package.json (D1) | [doc](milestones/M71_VERSION_MANIFEST_SYNC.md) |
| M72 | 2026-09-26 | Atomic file writes for exhaustion_ledger.json & demo showcase (C5) | [doc](milestones/M72_ATOMIC_LEDGER_WRITES.md) |
| M73 | 2026-09-28 | Import get_model_rates directly in src/simulator.py from pricing (C8) | [doc](milestones/M73_SIMULATOR_PRICING_ALIGNMENT.md) |
| M74 | 2026-09-28 | Replace silent except Exception: pass with targeted logging & explicit exceptions (C6) | [doc](milestones/M74_EXPLICIT_EXCEPTION_HANDLING.md) |
| M75 | 2026-09-28 | Decouple circular import between src/vault.py and src/weekly_trends.py (C7) | [doc](milestones/M75_VAULT_WEEKLY_TRENDS_DECOUPLE.md) |
| M76 | 2026-09-28 | Automated test harnesses for scripts/quota_regression.py & setup_github_guardrails.py (C9) | [doc](milestones/M76_SCRIPTS_GOVERNANCE_TEST_HARNESSES.md) |
| M77 | 2026-09-29 | Fix circular unittest discover subprocess in tests/test_vdone_gates.py (C1) | [doc](milestones/M77_VDONE_GATES_RECURSION_FIX.md) |
| M78 | 2026-09-29 | Fix unclosed SQLite connection leak in scripts/export_dashboard.py:574 (C2) | [doc](milestones/M78_EXPORTER_SQLITE_CONNECTION_LEAK_FIX.md) |
| M79 | 2026-09-29 | Harden SQLite connection closures in src/vault.py and src/log_reader.py (C3) | [doc](milestones/M79_SQLITE_CONNECTION_CLOSURE_HARDENING.md) |
| M80 | 2026-09-29 | Fix model census TypeError in antigravity_telemetry and replace silent generic exceptions with typed handlers and logging (C4) | [doc](milestones/M80_MODEL_CENSUS_EXCEPTION_HANDLING.md) |
| M81 | 2026-09-29 | Lazy tab rendering to drop initial DOM from 8,180 to ~500 nodes (U1) | [doc](milestones/M81_LAZY_TAB_RENDERING.md) |
| M82 | 2026-09-29 | Watcher vault deduplication, mobile a11y, token compliance, manifest sync & script budget decomposition (Rows 8-13) | [doc](milestones/M82_BACKLOG_BURNDOWN_AND_VERSION_SYNC.md) |
| M85 | 2026-09-30 | Discrete 5h quota reset epochs, compaction drift safeguards & adaptive refresh | [ADR-082](ADR-082-discrete-5h-quota-reset.md) |
| M86 | 2026-09-30 | Menu Bar Epoch Number Indicator & Two-Tier Fast Ticker Exporter (<20ms) | [doc](milestones/M86_MENUBAR_EPOCH_AND_TWO_TIER_EXPORTER.md) |
| M87 | 2026-10-02 | Incremental Cached Exporter (<500ms) with SQLite & in-memory caching and 2.0s debounce | [doc](milestones/M87_INCREMENTAL_CACHED_EXPORTER.md) |
| M88 | 2026-10-02 | Dashboard Executive Cockpit & Mac Menu Bar Parity | [doc](milestones/M88_EXECUTIVE_COCKPIT_AND_MENUBAR_PARITY.md) |
| M89 | 2026-10-03 | Claude 5.5 model census expansion (1400–1405), 4.6 deprecation & quota routing | [doc](milestones/M89_CLAUDE_55_MODEL_CENSUS_EXPANSION.md) |
| M90 | 2026-10-06 | Telemetry vault query optimization, structured extraction, reference dictionaries & KPI harness | [doc](milestones/M90_VAULT_QUERY_OPTIMIZATION_AND_INDEXING.md) |
| M91 | 2026-10-07 | Multi-project swarms, weakest-link risk scoring & native popover cascade trees | [doc](milestones/M91_MULTI_AGENT_CASCADE_DEGRADATION.md) |
| M92 | 2026-10-13 | Gemini 4 Argon frontier model census (1417–1419), two-era pricing & 3.1 Pro sunset | [doc](milestones/M92_GEMINI_4_ARGON_MODEL_CENSUS.md) |
| M93 | 2026-10-14 | Live quota snapshot archival, v_quota_burn_intervals, fast monitor 429/quota convergence & cache de-bloat | [doc](milestones/M93_QUOTA_SNAPSHOT_OBSERVER_AND_FAST_MONITOR.md) |
| M94 | 2026-10-14 | Ultra 5x capacity calibration ($25/$100), intra-family KV cache coaching (GADR-018), wire protobuf TTFT/latency backfill & Now-tab active swarms | [doc](milestones/M94_ULTRA_CAPACITY_KV_COACHING_AND_WIRE_LATENCY.md) |
| M95 | 2026-10-17 | Idle swarm recency isolation, strict parent lineage binding, popover item caps & weekly vs 5h health grading | [doc](milestones/M94_ULTRA_CAPACITY_KV_COACHING_AND_WIRE_LATENCY.md) |
| M96 | 2026-10-20 | Multi-horizon consumption progression, Pro vs Ultra era ROI analytics & diurnal latency/speed profile | [doc](milestones/M94_ULTRA_CAPACITY_KV_COACHING_AND_WIRE_LATENCY.md) |
| M97 | 2026-10-25 | Quota regime & burn-rate drift detector, early weekly reset bonus ledger, Jules offload savings ledger & design-standards v1.3.1 | [doc](milestones/M94_ULTRA_CAPACITY_KV_COACHING_AND_WIRE_LATENCY.md) |
| M98 | 2026-11-09 | Subprocess exporter crash remediation: logical vault_cache fingerprinting, persistent horizon_analytics cache, bisect regime slicing & active-cycle weekly trends delta sync | [doc](milestones/M94_ULTRA_CAPACITY_KV_COACHING_AND_WIRE_LATENCY.md) |
| M99 | 2026-11-10 | Gemini 4 Carbon frontier model census (1427, 1437, 1438), two-era pricing, KV-coaching/regime calibration & GPT-OSS 120B (342) sunset notice | [doc](milestones/M99_GEMINI_4_CARBON_MODEL_CENSUS.md) |


---

## 4. Open Work Register & Deferred Items

### Open Work

| Milestone / Row | Scope & Description | Status |
| :--- | :--- | :--- |
| *(None — all active backlog rows closed)* | — | — |

### Closed This Quarter

- **M99**: Registered **Gemini 4 Carbon** (`1427` High, `1437` Medium, `1438` Low) under `gemini-carbon` (`1M` context, `250k` compaction) in the 32-model canonical census, configured two-era temporal pricing (`$2.00/$0.10/$10.00` introductory until `2026-11-30`, `$4.00/$0.20/$20.00` standard from `2026-12-01`), solved and calibrated 7-decimal Connect-RPC quota weights (`$1.00/$0.050/$5.00` = `0.5000x` Intro API = `$50` 5h / `$200` weekly), wired `M427`/`M437`/`M438` KV-cache eviction coaching, horizon/diurnal latency series, 6-turn staircase calibration probes, `.model-carbon` badges, and recorded the `2026-11-18` upstream sunset notice for `GPT-OSS 120B (Medium)` (`342`) (`feat/m99-gemini-4-carbon-model-census`) — 2026-11-10
- **M98**: Remediated Python 3.14.6 subprocess exporter `SIGSEGV` and SQLite lock contention by eliminating no-op `vault_sync_state` writes in `sync_conversations_to_vault()`, keying `vault_cache` on logical table fingerprints (`_get_vault_logical_fingerprint()`), persisting `horizon_analytics` in `dashboard/.export_cache.db`, scoping `sync_weekly_trends_to_vault()` to active-cycle delta rows, replacing $O(N_{\text{snaps}} \times N_{\text{turns}})$ linear scans in `evaluate_vault_quota_regime()` with `bisect_right`, and enforcing ADR-081 `60s` busy timeout + exponential retry in `sync_regime_events_to_vault_and_ledger()` (`main`) — 2026-11-09
- **M95–M97**: Added idle swarm recency isolation, strict subagent parent lineage binding, popover item caps, and decoupled weekly vs 5h health grading in `AntigravityBar` (M95); built 5-horizon consumption progression (`src/horizon_analytics.py`), Pro vs Ultra era ROI analytics, and diurnal speed/latency profiling on the `Now` and `Billing` tabs (M96); implemented the quota regime & burn-rate drift detector (`src/quota_regime.py`, `data/quota_regime_ledger.json`), Jules offload savings ledger (`data/jules_savings_ledger.json`), and design-standards v1.3.1 Glacier Sky / Carbon-Cobalt palette (M97) (`main`) — 2026-10-29
- **M94**: Calibrated `config/pricing.json` and simulator/plan presets for Google AI Ultra (`ultra_5x`) true retail quota capacities (`$25.00` 5h burst = `2,500 credits`, `$100.00` weekly = `10,000 credits` at `4.0000x` ratio) while preserving Pro era (`$20.00` 5h) ledger reconciliations; recorded and surfaced non-monetary `QUOTA_RESET_BONUS` events (`exc-20261017-01`: `+75.4%` Gemini weekly / `7,540` credits / `$75.40` / `£59.57` forgiven on `2026-10-17T01:46:18Z`) without altering prepaid credit balances (`614 / 5,000`); verified the post-reset 6-model empirical calibration across `698` turns (`1417` High, `1418` Med, and `1419` Low share identical per-token weights with KV-cached input reduced `~75%` to `~$0.025/1M`, while `1318`–`1322` Flash deducts at `1/6x` of API rate = `$150` 5h / `$600` weekly effective capacity); extended ADR-038 cache-eviction coaching (`src/aggregator_coaching.py` & `dashboard/js/sessions.js`) for GADR-018 intra-family and intra-track `model_id` flips past `40k` depth; decoded wire protobuf `ttft_ms` and `latency_ms` (`antigravity_telemetry/reader.py`), backfilling `104,107` historical turns in `data/antigravity_vault.db`; and brought active multi-agent swarm & weakest-link risk parity to the web dashboard `Now` tab (`dashboard/js/now-burst.js`) (`feat/m93-quota-snapshot-observer-and-fast-monitor`) — 2026-10-17
- **M93**: Live quota snapshot archival (`quota_snapshots_archive` & `v_quota_burn_intervals` in `data/antigravity_vault.db`), automated interval burn regression in `scripts/quota_regression.py`, BST/local glog timestamp conversion and `<0.5ms` `429` tail-scan clamping in `src/log_reader.py`, 15s-throttled Connect-RPC quota refresh in `export_fast_tier()`, pre-vault status hook writes, and `dashboard/.export_cache.db` `vault_cache` de-bloat from `53.73 MB` to `5.64 MB` (`feat/m93-quota-snapshot-observer-and-fast-monitor`) — 2026-10-14
- **M92**: Gemini 4 Argon frontier model census expansion (`1417`–`1419`: High/Medium/Low under `gemini-argon` family), two-era temporal pricing schedule (`$2.00/$0.10/$10.00` introductory until 2026-11-30, `$4.00/$0.20/$20.00` standard from 2026-12-01), 1M context truncation and 250k compaction threshold calibration, and backward-compatible deprecation of Gemini 3.1 Pro (`1016`, `1036`) (`feat/m92-gemini-4-argon-model-census`) — 2026-10-13
- **M91**: Multi-project swarms, weakest-link risk scoring, dual-state active context degradation (decoupling latest turn $t_n$ active tokens from compaction epoch $E$), subagent visibility with parent linking, and native macOS menu bar popover cascade disclosure (`feat/multi-agent-cascade-degradation`) — 2026-10-07
- **M90**: Telemetry vault query optimization, compound/partial indexes, structured error extraction, self-documenting reference dictionaries (`ref_step_types`, `ref_status_codes`), canonical analytical views (`v_turns`, `v_hourly_token_velocity`, `v_active_sessions`, `v_rate_limit_events`) and empirical KPI benchmark harness (`scripts/bench_vault_performance.py`) yielding 3,197x faster rate limit seeks and 47.4x faster error audits with only 0.54% disk overhead (ADR-087..ADR-091) (`feat/m90-menubar-top-refactor-and-popover-bento`) — 2026-10-06
- **M89**: Claude 5.5 model census expansion (1400–1405: Opus 5.5 and Sonnet 5.5 Low/Medium/High), backward-compatible deprecation of 1026/1035 starting 2026-10-03, 26-model canonical census, and dynamic Claude quota track routing (`feat/m89-claude-55-model-census-expansion`) — 2026-10-03
- **M88**: Dashboard Executive Cockpit & Mac Menu Bar Parity, false-alarm session truncation elimination on Now tab, demoted dense telemetry sub-drawer, and byte-deterministic export parity (`feat/m88-dashboard-executive-cockpit`) — 2026-10-02
- **M87**: Incremental Cached Exporter (<500ms) with two-tier in-memory and persistent SQLite cache (.export_cache.db), fingerprint gating across 526 DBs, cached vault queries, ISO parsing optimization, and 2.0s watcher settle window (`feat/m87-incremental-cached-exporter`) — 2026-10-02
- **M86**: Menu Bar Epoch number indicator badge (E1..E5) with color grading (#34D399, #FBBF24, #EF4444) and Two-Tier fast ticker exporter (<20ms) decoupled from 30–60s debounced heavy rollup (`feat/m86-menubar-epoch-and-two-tier-exporter`) — 2026-09-30
- **M85**: Discrete 5-hour quota reset epochs, empirical compaction drift safeguards, 10-turn FIFO eviction alerting, and adaptive 3s/10s/30s polling cadence (`feat/telemetry-discrete-5h-and-compaction-drift`) — 2026-09-30
- **M82 (Rows 8–13)**: Backlog burndown across watcher vault deduplication (C5), mobile scrollable table a11y (U4), anti-generic border radius (D1), JS CSS color tokens (D2), version parity to `2.25.0` (D3), and ADR-066 script line budget decomposition (D4) (`feat/backlog-burndown-v225`) — 2026-09-29
- **M81 (Row 5 / U1)**: Implement lazy tab rendering to drop initial DOM from 8,180 to ~500 nodes (`perf/lazy-tab-rendering`) — 2026-09-29
- **Row 7 (U3)**: Calibrate light mode color contrast and unmask `e2e/a11y.spec.js` (`ui/light-theme-contrast-calibration`) — 2026-09-29
- **Row 6 (U2)**: Fix desktop header badge text clipping on 1440x900 viewport (`ui/header-badge-clipping-fix`) — 2026-09-29
- **M80 (Row 4 / C4)**: Fix model census `TypeError` in `antigravity_telemetry` and replace silent generic exceptions with typed handlers and logging (`fix/model-census-exception-handling`) — 2026-09-29
- **M79 (Row 3 / C3)**: Harden SQLite connection closures in `src/vault.py` and `src/log_reader.py` (`fix/vault-connection-closure-hardening`) — 2026-09-29
- **M78 (Row 2 / C2)**: Fix unclosed SQLite connection leak in `scripts/export_dashboard.py:574` (`fix/export-connection-leak`) — 2026-09-29
- **M77 (Row 1 / C1)**: Fix circular `unittest discover` subprocess in `tests/test_vdone_gates.py` (`fix/test-vdone-gates-recursion`) — 2026-09-29
- **M76 (Row 10 / C9)**: Add test harnesses for `quota_regression.py` and GitHub guardrails (`chore/scripts-governance-cleanup`) — 2026-09-28
- **M75 (Row 8 / C7)**: Decouple circular import between `src/vault.py` and `src/weekly_trends.py` via `src/vault_schema.py` (`refactor/vault-weekly-trends-decouple`) — 2026-09-28
- **M74 (Row 7 / C6)**: Replace silent `except Exception: pass` with targeted logging (`fix/explicit-exception-handling`) — 2026-09-28
- **Row 11 (U1)**: Calibrate light mode badge color contrast in `dashboard/styles.css` (`ui/light-contrast-touchup`) — 2026-09-28
- **M73 (Row 9 / C8)**: Import `get_model_rates` directly in `src/simulator.py` from pricing (`fix/simulator-pricing-alignment`) — 2026-09-28
- **M72 (Row 6 / C5)**: Atomic file writes for `exhaustion_ledger.json` & demo showcase (`fix/atomic-ledger-writes`) — 2026-09-26
- **M71 (Row 5 / D1)**: Align version across Git tag, `pyproject.toml`, and `package.json` (`chore/version-manifest-sync`) — 2026-09-26
- **M70 (Row 4 / C4)**: Add explicit `timeout=` and error handling across 28 subprocess calls (`fix/subprocess-timeout-hardening`) — 2026-09-26
- **M69 (Row 3 / C3)**: Add thread lock & unique tempfile prefix to `update_watcher_heartbeat` (`fix/watcher-thread-lock-temp-safety`) — 2026-09-26
- **M68 (Row 2 / C2)**: Gate vault sync with `not dry_run` in `scripts/export_dashboard.py` (`fix/exporter-dry-run-isolation`) — 2026-09-26
- **M67 (Row 1 / C1)**: Filter DBs by mtime & batch queries in `sync_conversations_to_vault` (`perf/vault-sync-mtime-gating`) — 2026-09-26
- **Row 1 (TI-2)**: Restore watcher status writes after M65 and self-heal a foreign status file (`fix/status-self-heal`) — 2026-09-25
- **Row 1 (TI-1)**: Stop unit tests overwriting the live menu-bar status file (`fix/test-status-isolation`) — 2026-09-24
- **Row 8 (U3)**: Expand mobile touch target hit areas to >= 44 px (`ui/tap-target-expansion`) — 2026-09-22
- **M64**: Agent persona telemetry & workflow attribution (`feat/agent-persona-telemetry`) — 2026-09-22

- **Row 7 (U2)**: Calibrate dark theme Swarms & pill contrast ratios (`ui/dark-contrast-calibration`) — 2026-09-22
- **Row 6 (C3)**: Resolve unclosed SQLite connection in src/git_timeline.py (`fix/git-timeline-connection-leak`) — 2026-09-22
- **Row 5 (D2)**: Split core.js, now.js, and sessions.js to bring under 800 lines (`refactor/js-budget-compliance`) — 2026-09-22
- **Row 4 (U1)**: Add accessible aria-label to dock navigation buttons & select elements (`fix/dock-a11y-labels`) — 2026-09-22
- **Row 3 (D1, D3)**: Reopen M64 in HANDOVER & add frontend Playwright gate to VDONE (`docs/m64-reopen-and-gate`) — 2026-09-22
- **Row 2 (C2)**: Add 10.0 s upper clamp to watcher settle window (`fix/watcher-settle-clamp`) — 2026-09-22
- **Row 1 (C1)**: Fix undeclared variable references in now.js (`fix/now-burst-session-scope`) — 2026-09-22

- **M45**: Subagent tracking truncation fix — 2026-09-18
- **M46**: Degraded sessions warnings & context boundary hygiene — 2026-09-18
- **M47**: Unified context safety strip & branch attribution — 2026-09-18
- **M48**: Repository consolidation, documentation drift elimination & ceremony reduction (`docs/m48-consolidation`) — 2026-09-19
- **M48.1**: M48 review defect fixes & fixture determinism (`docs/m48-1-review-fixes`) — 2026-09-19
- **M49**: Export advisory lock, unique temp file & refresh signaling (`fix/export-lock`) — 2026-09-19
- **M50**: Dynamic labels, simulator default tier, plain English labels, light theme default (`fix/labels-and-simulator-defaults`) — 2026-09-19
- **M51**: Dashboard boot refactor, delegated CSP listeners & plan tier default (`refactor/dashboard-boot`) — 2026-09-19
- **M52**: Plain-language Now tab copy, compact 1-line header, mobile header (<160px) (Row 7: U1/U2) (`ui/plain-header`) — 2026-09-20
- **M53 (Row 7.5 & Row 12)**: Split app.js into 7 sequential plain scripts (<800 lines each), unified single-index demo (?demo=1), deleted demo.html (`refactor/app-js-split`) — 2026-09-20
- **M53.1**: Plan JS restore, interaction test proofs & V53 gates (`refactor/plan-js-restore`) — 2026-09-20
- **M54 (Row 8: C4/U3)**: Per-model truncation thresholds in models.json, demote warning badge, paged Sessions (`feat/truncation-per-model`) — 2026-09-20
- **M55 (Row 9: C5)**: Minified data.js, lazy-loaded turns.js per session, context truncation markers (`perf/lazy-turns`) — 2026-09-20
- **M56 (Row 10: C6)**: PRAGMA integrity check, remove stray .bak file, vault size in meta.json (`chore/vault-bak-removal`) — 2026-09-20
- **M57 (Row 11: C7)**: Adaptive settle window for watcher, export took logging, export_seconds in meta.json (`perf/watcher-cadence`) — 2026-09-20
- **M58 (Row 13: C9/C10)**: Sanitize Swift repo path literal, replace pgrep with watcher heartbeat (`fix/menubar-hygiene`) — 2026-09-20
- **M59 (Row 14: U5/U6)**: Accessibility baseline (roles, SVG titles, captions), 2-decimal money, single formatter (`ui/a11y-baseline`) — 2026-09-20
- **M60 (Row 15: 5.6)**: Move Playwright bridge to tests/e2e_bridge/, scheduled nightly CI workflow, test stdout capture (`ci/e2e-nightly`) — 2026-09-20
- **M61 (Row 16: U8)**: Mobile viewport polish, ticker clipping fix, table scroll wrappers (`ui/mobile-pass`) — 2026-09-21
- **M62 (Row 17: C11)**: Aggregator modularization refactor (reopen ADR-044), 6 submodules, <250-line aggregate_global_telemetry, interaction gate (`refactor/aggregator-modules`) — 2026-09-21
- **M63 (Row 18: C12)**: Hermetic fixture export, isolated HOME & anonymized golden baseline (`fix/hermetic-fixture-export`) — 2026-09-21
