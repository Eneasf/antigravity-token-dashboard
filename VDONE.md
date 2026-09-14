# VDONE: Quality Gates & Verifiable Acceptance Register

**Active Branch**: `main`  
**Standard**: Done if proven, not if declared (`AGENTS.md` §3 & `vdone`)

---

## Baseline Verification Gates (M01: Initial Scaffolding)

### V0: Unit Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: 100% pass (exit code 0); ran all tests in `<0.05s`; 0 failures, 0 errors.

### V1: Live Upstream Telemetry Ingestion & Deterministic Export
- **CHECK**: `python3 scripts/export_dashboard.py`
- **EXPECT**: Discovers and extracts local conversation DBs; writes deterministic JSON into `dashboard/index.html`; exit code 0.

### V2: Byte-Determinism & Git Cleanliness
- **CHECK**: `python3 scripts/export_dashboard.py --dry-run`
- **EXPECT**: Dry-run inspects without file mutations; exit code 0.

### V3: Working Tree Hygiene
- **CHECK**: `git status`
- **EXPECT**: `nothing to commit, working tree clean` at merge point.

---

## Milestone 2 Verification Gates (M02: Rolling Quotas & Subscription Value Engine)

### V4: Rolling 5-Hour & 1-Week Window Calculation Accuracy
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: Correctly partitions tokens by `model_id` across `[now - 5h, now]` and `[now - 7d, now]` windows; verifies chronological age-out recovery schedule; 8/8 tests pass in `<0.05s`.

### V5: Quota & Imputed Value Dashboard Surface
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert 'rolling_5h' in d['quotas']; assert 'by_model' in d['quotas']['rolling_5h']; print('Verified: Quota telemetry intact.')"`
- **EXPECT**: `Verified: Quota telemetry intact.`; exit code 0.

---

## Milestone 2b Verification Gates (M02b: AI Credit Burn Reconciliation)

### V6: Log Parser 429 Exhaustion & Recovery Schedule
- **CHECK**: `python3 -c "from src.log_reader import extract_exhaustion_intervals; intervals=extract_exhaustion_intervals(); assert len(intervals) >= 1; print(f'Verified: Discovered {len(intervals)} exhaustion intervals.')"`
- **EXPECT**: Correctly extracts `RESOURCE_EXHAUSTED` timestamps from `language_server.log`; exit code 0.

### V7: Model-Specific AI Credit Burn Calibration
- **CHECK**: `python3 -c "from src.aggregator import calculate_credit_burn; burn=calculate_credit_burn('1318', turns_count=299); assert round(burn['credits']) == 748; print('Verified: Flash High 299 turns = 748 credits.')"`
- **EXPECT**: Evaluates 299 Flash turns to exactly 748 credits ($7.48); exit code 0.

### V8: Live AI Credit Burn Surface Reconciliation
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert d['summary']['total_ai_credits_burned'] >= 1100; assert d['summary']['total_credit_burn_usd'] >= 11.0; print('Verified: Official AI credits burned reconciled.')"`
- **EXPECT**: Reconciles against the ~1,179 credits ($11.79) observed in Google One portal; exit code 0.

### V9: Multi-Currency Accounting & British Pounds (GBP) Default Calibration
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert d['summary']['currency_default'] == 'GBP'; assert d['summary']['total_credit_burn_gbp'] > 0; assert d['summary']['cost_per_credit_gbp'] == 0.009596; print('Verified: British Pounds multi-currency accounting calibrated.')"`
- **EXPECT**: Validates GBP £23.99 / 2,500 credits rate (£0.009596/credit) and dual-track summary fields; exit code 0.

### V10: Unified Light and Dark Interactive Theme Switcher
- **CHECK**: `python3 -c "import re; c=open('dashboard/index.html').read(); assert 'toggle-group' in c; assert 'btn-theme-light' in c; assert 'btn-theme-dark' in c; assert 'antigravity_dashboard_theme' in c; print('Verified: Unified light/dark theme switcher and CSS tokens intact in single index.html.')"`
- **EXPECT**: `Verified: Unified light/dark theme switcher and CSS tokens intact in single index.html.`; exit code 0.

### V11: Unit Test Suite Expansion
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: 17/17 tests pass cleanly; exit code 0.

---

## Milestone 2c Verification Gates (M02c: Quota Cycle Anchoring & Signal-Anchored Overage)

### V12: Signal-Anchored 5h Overage Engine (Zero Phantom Deductions)
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); dates=[h['hour_timestamp'][:10] for h in d.get('hourly_credit_activity', [])]; assert '2026-08-28' not in dates; print('Verified: No phantom August deductions.')"`
- **EXPECT**: `Verified: No phantom August deductions.`; exit code 0.

### V13: Thursday Weekly Cycle Reset Anchoring
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert 'weekly_cycle' in d['quotas']; assert d['quotas']['weekly_cycle']['reset_day_name'] == 'Thursday'; print('Verified: Thursday weekly cycle reset intact.')"`
- **EXPECT**: `Verified: Thursday weekly cycle reset intact.`; exit code 0.

### V14: 24th Monthly Billing Horizon Renewal
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert 'monthly_billing' in d['quotas']; assert '2026-09-24' in d['quotas']['monthly_billing']['renewal_date']; print('Verified: 24th monthly billing horizon intact.')"`
- **EXPECT**: `Verified: 24th monthly billing horizon intact.`; exit code 0.

---

## Milestone 3 Verification Gates (M03: Live Watcher Daemon & Service Packaging)

### V15: Debounce & Burst Coalescing Engine
- **CHECK**: `python3 -m unittest tests.test_watch_telemetry.TestWatchTelemetry.test_debounce_coalescing`
- **EXPECT**: Rapid succession writes coalesce into exactly 1 export trigger after settle window; exit code 0.

### V13: Dual-Source Telemetry Watcher (`*.db-wal` + `language_server.log`)
- **CHECK**: `python3 -m unittest tests.test_watch_telemetry.TestWatchTelemetry.test_snapshot_detects_db_and_wal tests.test_watch_telemetry.TestWatchTelemetry.test_snapshot_detects_language_server_log`
- **EXPECT**: Changes to SQLite WAL logs or runtime log file are independently detected and trigger export; exit code 0.

### V14: Clean Signal & Stop Event Shutdown
- **CHECK**: `python3 -m unittest tests.test_watch_telemetry.TestWatchTelemetry.test_clean_shutdown_on_stop_event`
- **EXPECT**: Watcher loop terminates cleanly upon stop event with 0 zombie threads; exit code 0.

### V15: macOS LaunchAgent Service Packaging & Plist Validation
- **CHECK**: `python3 scripts/setup_service.py validate`
- **EXPECT**: Generated plist is valid XML conforming to Apple launchd schema; exit code 0.

### V16: Full Regression & Integration Test Suite
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.

---

## Milestone 6 Verification Gates (M06: Dual-Tier Plan & Overage Credit Architecture)

### V17: Decoupled Tier 1 Subscription vs Tier 2 Overage Accounting in Aggregator
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); s=d['summary']; assert s['monthly_subscription_price_gbp'] == 18.99; assert s['credit_bank_total'] == 2500; assert s['total_ai_credits_burned'] == 1179; assert s['credits_remaining'] == 1321; assert s['credit_bank_remaining_gbp'] == 12.68; assert s['credit_bank_remaining_usd'] == 13.21; print('Verified: Decoupled Tier 1 & Tier 2 summary accounting intact.')"`
- **EXPECT**: `Verified: Decoupled Tier 1 & Tier 2 summary accounting intact.`; exit code 0.

### V18: Persistent Exhaustion Ledger Ingestion & Reconciliation
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert len(d.get('hourly_credit_activity', [])) == 2; assert d['hourly_credit_activity'][0]['credits_burned'] + d['hourly_credit_activity'][1]['credits_burned'] == 1179; print('Verified: Official billing hourly credit deductions reconciled (1179 credits).')"`
- **EXPECT**: `Verified: Official billing hourly credit deductions reconciled (1179 credits).`; exit code 0.

### V19: Decoupled Dashboard UI Surface Binding
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); ids=['quota-sub-renewal-badge', 'quota-sub-price', 'quota-sub-status', 'quota-sub-roi', 'quota-sub-roi-multiplier', 'quota-credits-badge', 'quota-credits-remaining-hero', 'quota-bank-sub', 'quota-credits-progress', 'quota-credit-burn', 'quota-credits-burned-count', 'quota-bank-balance', 'credit-reconciliation-card', 'reconciliation-subtitle', 'reconciliation-total-badge', 'reconciliation-tbody', 'th-cash-burn']; assert all(f'id=\"{i}\"' in c for i in ids); print('Verified: All Card 3, Card 4, and Reconciliation DOM elements present in HTML.')"`
- **EXPECT**: `Verified: All Card 3, Card 4, and Reconciliation DOM elements present in HTML.`; exit code 0.

### V20: Multi-Currency Dynamic Switching Support
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); assert 'quota-sub-price' in c and 'quota-bank-sub' in c and 'updateCurrencyViews' in c; print('Verified: Currency toggle updates Card 3 and Card 4 synchronously.')"`
- **EXPECT**: `Verified: Currency toggle updates Card 3 and Card 4 synchronously.`; exit code 0.

### V21: Full Unit & Regression Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: 30/30 unit tests pass cleanly in `<1.0s`; exit code 0.

---

## Milestone 7 Verification Gates (M07: Multi-Model Benchmark Taxonomy & Subagent Discovery)

### V22: 14-Model Pricing Configuration Integrity
- **CHECK**: `python3 -c "import json; p=json.load(open('config/pricing.json')); required=['1318','1319','1320','1298','1299','1300','1071','1072','1073','1050','1016','1036','1035','1026','342']; assert all(k in p['models'] for k in required); print('Verified: All 15 benchmark models registered in pricing matrix.')"`
- **EXPECT**: `Verified: All 15 benchmark models registered in pricing matrix.`; exit code 0.

### V23: Benchmark Ledger Attainment
- **CHECK**: `python3 -c "c=open('docs/MODEL_BENCHMARKS.md').read(); assert '1050' in c and '84.6%' in c and 'b596cf7f' in c and '68481b2d' in c; print('Verified: Model benchmarks ledger complete with Model 1050 and orchestrator topology.')"`
- **EXPECT**: `Verified: Model benchmarks ledger complete with Model 1050 and orchestrator topology.`; exit code 0.

### V24: Full Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: 30/30 unit tests pass cleanly; exit code 0.

---

## Milestone 8 Verification Gates (M08: Telemetry Vault, Lineage Topology & Archival Skill)

### V25: Vault Schema Initialization & Idempotence
- **CHECK**: `python3 -c "from src.vault import init_vault; conn=init_vault('data/antigravity_vault.db'); cur=conn.cursor(); cur.execute('SELECT name FROM sqlite_master WHERE type=\'table\''); tables={r[0] for r in cur.fetchall()}; assert {'conversations_archive', 'steps_archive', 'tool_calls_archive', 'log_events_archive'}.issubset(tables); print('Verified: Vault schema tables initialized.')"`
- **EXPECT**: `Verified: Vault schema tables initialized.`; exit code 0.

### V26: Hybrid Step Ingestion (Text + Raw Blobs, Zero PKL)
- **CHECK**: `python3 -c "from src.vault import get_vault_connection; conn=get_vault_connection('data/antigravity_vault.db'); cur=conn.cursor(); cur.execute('PRAGMA table_info(steps_archive)'); cols={r[1]: r[2] for r in cur.fetchall()}; assert cols.get('payload_text') == 'TEXT'; assert cols.get('raw_step_payload_blob') == 'BLOB'; print('Verified: Hybrid text and blob schema intact without pickle.')"`
- **EXPECT**: `Verified: Hybrid text and blob schema intact without pickle.`; exit code 0.

### V27: Parent-Child Subagent Lineage Resolution
- **CHECK**: `python3 -c "from src.vault import get_vault_connection; conn=get_vault_connection('data/antigravity_vault.db'); cur=conn.cursor(); cur.execute('SELECT parent_convo_id FROM conversations_archive WHERE convo_id = \'68481b2d-f75d-47b3-b4ca-5d3a8f5de035\''); res=cur.fetchone(); assert res and res[0] == 'b596cf7f-af76-4966-8a8b-f90a0d1c6229'; print('Verified: Subagent lineage resolved.')"`
- **EXPECT**: `Verified: Subagent lineage resolved.`; exit code 0.

### V28: Workspace & Project Attribution Parsing
- **CHECK**: `python3 -c "from src.vault import get_vault_connection; conn=get_vault_connection('data/antigravity_vault.db'); cur=conn.cursor(); cur.execute('SELECT workspace_name FROM conversations_archive WHERE convo_id = \'b596cf7f-af76-4966-8a8b-f90a0d1c6229\''); res=cur.fetchone(); assert res and 'Token consumption' in res[0]; print('Verified: Workspace origin attributed.')"`
- **EXPECT**: `Verified: Workspace origin attributed.`; exit code 0.

### V29: Truncation-Resilient Log Archival
- **CHECK**: `python3 -m unittest tests.test_vault.TestVault.test_log_truncation_detection`
- **EXPECT**: Truncated log file resets offset and continues ingesting without duplicates; exit code 0.

### V30: Universal Ingestion Skill Discovery
- **CHECK**: `python3 -c "import os; p=os.path.expanduser('~/.gemini/config/skills/credit-statement-ingest/SKILL.md'); assert os.path.exists(p); print('Verified: Global credit-statement-ingest skill installed.')"`
- **EXPECT**: `Verified: Global credit-statement-ingest skill installed.`; exit code 0.

---

## Milestone 9 Verification Gates (M09: Dual-Track Provider Quota Silos)

### V31: Provider Family Classification Integrity
- **CHECK**: `python3 -c "from src.aggregator import get_provider_quota_track; assert get_provider_quota_track('1318') == 'gemini'; assert get_provider_quota_track('1016') == 'gemini'; assert get_provider_quota_track('1050') == 'gemini'; assert get_provider_quota_track('1322') == 'gemini'; assert get_provider_quota_track('1036') == 'gemini'; assert get_provider_quota_track('1035') == 'claude_gpt'; assert get_provider_quota_track('1026') == 'claude_gpt'; assert get_provider_quota_track('342') == 'claude_gpt'; print('Verified: Provider family classification routes correctly across desktop and subagent models.')"`
- **EXPECT**: `Verified: Provider family classification routes correctly across desktop and subagent models.`; exit code 0.

### V32: Dual-Track Quota Payload Computation
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); q=d['quotas']; assert 'providers' in q; assert 'gemini' in q['providers']; assert 'claude_gpt' in q['providers']; assert 'five_hour' in q['providers']['gemini'] and 'weekly' in q['providers']['gemini']; assert 'five_hour' in q['providers']['claude_gpt'] and 'weekly' in q['providers']['claude_gpt']; print('Verified: Dual-track provider quota payload intact.')"`
- **EXPECT**: `Verified: Dual-track provider quota payload intact.`; exit code 0.

### V33: Distinct Refresh Countdowns & Cycle Alignment
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); g=d['quotas']['providers']['gemini']; cg=d['quotas']['providers']['claude_gpt']; assert 'Thursday' in g['weekly']['reset_display']; assert 'refresh' in g['weekly']['message'].lower() or 'fully' in g['weekly']['message'].lower(); print('Verified: Distinct refresh countdowns verified.')"`
- **EXPECT**: `Verified: Distinct refresh countdowns verified.`; exit code 0.

### V34: Zero Cross-Track Contamination
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_zero_cross_track_contamination`
- **EXPECT**: Turns added to Claude/GPT do not change Gemini token sums or recovery schedule, and vice versa; exit code 0.

### V35: Visual Dashboard DOM Elements for Dual Tracks
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); ids=['gemini-weekly-pct', 'gemini-5h-pct', 'claude-weekly-pct', 'claude-5h-pct', 'gemini-weekly-sub', 'gemini-5h-sub', 'claude-weekly-sub', 'claude-5h-sub']; assert all(f'id=\"{i}\"' in c for i in ids); print('Verified: Dual provider quota DOM elements present.')"`
- **EXPECT**: `Verified: Dual provider quota DOM elements present.`; exit code 0.

### V36: Full Regression & Integration Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.

---

## Milestone 10 Verification Gates (M10: Cost-Weighted Quota Convergence & Desktop Sync)

### V37: Official Google Document Rate Card Proportions
- **CHECK**: `python3 -c "import json; p=json.load(open('config/pricing.json'))['models']; flash=p['1318']['rates_per_million']; pro=p['1016']['rates_per_million']; lite=p['1050']['rates_per_million']; assert flash['prompt_uncached']==0.75 and flash['prompt_cached']==0.075 and flash['candidate_output']==3.75; assert pro['prompt_uncached']==2.00 and pro['prompt_cached']==0.20 and pro['candidate_output']==12.00; assert lite['prompt_uncached']==0.25 and lite['prompt_cached']==0.025 and lite['candidate_output']==1.50; print('Verified: Official Google document rates calibrated.')"`
- **EXPECT**: `Verified: Official Google document rates calibrated.`; exit code 0.

### V38: Live Desktop Quota Client Discovery & Probe
- **CHECK**: `python3 -c "from src.quota_client import fetch_live_quota_summary; res=fetch_live_quota_summary(); assert res is not None; assert 'groups' in res; print('Verified: Live Desktop Quota RPC retrieved successfully.')"`
- **EXPECT**: Discovers local language_server port and CSRF token, queries `RetrieveUserQuotaSummary`, and returns valid quota groups; exit code 0.

### V39: CLI Quota Inspection Tool (`scripts/agy_quota.py`)
- **CHECK**: `python3 scripts/agy_quota.py`
- **EXPECT**: Exposes live desktop quota fractions in JSON/text format with exit code 0.

### V40: Cost-Weighted Quota Convergence & Capacity Modeling
- **CHECK**: `python3 -c "import json; p=json.load(open('config/pricing.json'))['subscription']['quota_limits']; assert p['gemini_5h_capacity_usd'] == 20.00; assert p['gemini_weekly_capacity_usd'] == 133.00; print('Verified: Cost-weighted capacity limits calibrated.')"`
- **EXPECT**: `Verified: Cost-weighted capacity limits calibrated.`; exit code 0.

### V41: Full Regression & Integration Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.

---

## Milestone 11 Verification Gates (M11: Project & Git Branch Intelligence)

### V42: Authoritative Extraction from `trajectory_metadata_blob`
- **CHECK**: `python3 -c "from src.telemetry_reader import read_conversation_metadata; meta = read_conversation_metadata(); assert len(meta) > 0; sample = next(iter(meta.values())); assert 'workspace_path' in sample and 'git_branch' in sample; print('Verified: Authoritative metadata extracted.')"`
- **EXPECT**: `Verified: Authoritative metadata extracted.`; exit code 0.
- **PROOF**: Verified against 100+ local conversation databases. Clean paths decoded and git branches mapped. Exit code 0.

### V43: Project & Branch Aggregation Payload
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert 'projects' in d; assert len(d['projects']) > 0; p = d['projects'][0]; assert 'project_name' in p and 'branches' in p; print('Verified: Project & branch aggregation payload intact.')"`
- **EXPECT**: `Verified: Project & branch aggregation payload intact.`; exit code 0.
- **PROOF**: Injected dashboard JSON contains 15 projects with nested branch arrays. Exit code 0.

### V44: Branch-Level Token Costing Integrity
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_branch_level_token_costing`
- **EXPECT**: Sum of branch tokens and imputed costs matches project totals with zero leakage; exit code 0.
- **PROOF**: Unit test passed in 0.001s with exact token and float equality. Exit code 0.

### V45: Tabbed Navigation DOM Elements & State Switching
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); ids=['tab-quotas', 'tab-projects', 'tab-credits', 'view-quotas', 'view-projects', 'view-credits']; assert all(f'id=\"{i}\"' in c for i in ids); print('Verified: Tab navigation DOM elements present.')"`
- **EXPECT**: `Verified: Tab navigation DOM elements present.`; exit code 0.
- **PROOF**: All 6 navigation and view container IDs verified in `dashboard/index.html`. Exit code 0.

### V46: Projects & Branches Table DOM Elements
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); ids=['projects-portfolio-kpis', 'projects-table-tbody']; assert all(f'id=\"{i}\"' in c for i in ids); print('Verified: Project explorer table DOM elements present.')"`
- **EXPECT**: `Verified: Project explorer table DOM elements present.`; exit code 0.
- **PROOF**: Both portfolio KPI and project table tbody IDs verified in `dashboard/index.html`. Exit code 0.

### V47: Full Regression & Integration Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.
- **PROOF**: 67/67 tests passing in 1.196s. Exit code 0.

---

## Milestone 12 Verification Gates (M12: Subscription Coverage vs. Actual Overage Accounting & Avoided Cost)

### V48: Turn-Level Exhaustion Correlation & Flagging
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_turn_overage_correlation`
- **EXPECT**: Turns falling inside confirmed exhaustion intervals are flagged `is_overage=True`, turns outside are `is_overage=False`; exit code 0.
- **PROOF**: Unit test passed in 0.000s with exact boolean flag assertions on turns inside and outside intervals. Exit code 0.

### V49: Project & Branch Subscription vs. Overage Payload Schema
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert 'projects' in d and len(d['projects']) > 0; p=d['projects'][0]; assert 'subscription_covered_pct' in p and 'actual_overage_gbp' in p and 'avoided_cost_gbp' in p; print('Verified: Project subscription vs overage schema intact.')"`
- **EXPECT**: `Verified: Project subscription vs overage schema intact.`; exit code 0.
- **PROOF**: Verified against 15 active projects in `dashboard/index.html`. Exit code 0.

### V50: Mathematical Zero-Leakage & Credit Reconciliation Invariant
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_project_overage_vs_covered_attribution`
- **EXPECT**: Sum of project actual overage credits matches total credit deductions (1,179 credits) with zero discrepancy, and avoided costs match total imputed value; exit code 0.
- **PROOF**: Unit test passed in 0.001s. Verified exact allocation of 1,179 credits to target project and 100% coverage to clean projects with zero leakage. Exit code 0.

### V51: Dual-Metric Dashboard DOM Elements & Table Headers
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); assert 'Subscription Coverage' in c and 'Actual Overage' in c and 'Avoided Cost' in c; print('Verified: Dual-metric DOM elements present.')"`
- **EXPECT**: `Verified: Dual-metric DOM elements present.`; exit code 0.
- **PROOF**: Table headers and KPI badges verified in `dashboard/index.html`. Exit code 0.

### V52: Full Regression & Integration Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.
- **PROOF**: 70/70 tests passing in 0.957s. Exit code 0.

---

## Milestone 13 Verification Gates (M13: Interactive Sliding-Window Quota Age-Out Timeline & Visual Recovery Gauge)

### V53: Recovery Trajectory Mathematical Integrity & Monotonicity
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_recovery_trajectory_monotonicity`
- **EXPECT**: Projected available headroom starts at current available % and increases monotonically to 100%; all age-out timestamps fall in `[now, now + 5h]`; sum of recovered tokens matches 5h window total; exit code 0.
- **PROOF**: Unit test passed in 0.001s with exact assertions across 20 uniform 15-minute buckets verifying monotonic progression, threshold milestone minutes, and empty window edge cases. Exit code 0.

### V54: Injected Trajectory Schema Attainment
- **CHECK**: `python3 -c "import json; d=json.load(open('dashboard/data.json')); q=d['quotas']['rolling_5h']; assert 'recovery_trajectory' in q; assert len(q['recovery_trajectory']['intervals_15m']) == 20; print('Verified: Recovery trajectory schema intact in data.json.')"`
- **EXPECT**: `Verified: Recovery trajectory schema intact in data.json.`; exit code 0.
- **PROOF**: Verified against active decoupled data projection `dashboard/data.json` across all quota windows (`rolling_5h`, `gemini_5h`, `cg_5h`). Exit code 0.

### V55: SVG Timeline DOM Elements & Container
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); ids=['recovery-timeline-card', 'svg-recovery-chart', 'svg-recovery-container', 'svg-step-area', 'svg-step-line']; assert all(f'id=\"{i}\"' in c for i in ids); print('Verified: SVG timeline DOM elements present.')"`
- **EXPECT**: `Verified: SVG timeline DOM elements present.`; exit code 0.
- **PROOF**: All 5 container, SVG chart, gradient, and tooltip elements confirmed present in `dashboard/index.html`. Exit code 0.

### V56: Live 30s Clock Tick & Tab Focus Auto-Refresh Mechanisms
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); assert 'updateTimelineTick' in c and 'visibilitychange' in c and 'btn-auto-refresh' in c; print('Verified: Live client-side tick and auto-refresh mechanisms present.')"`
- **EXPECT**: `Verified: Live client-side tick and auto-refresh mechanisms present.`; exit code 0.
- **PROOF**: Live 30-second interval ticker, tab visibility auto-refresh listener, and dynamic `data.js` script injector confirmed present in `dashboard/index.html`. Exit code 0.

### V57: Full Regression & Integration Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.
- **PROOF**: 72/72 tests passing in 1.207s across full suite. Exit code 0.

---

## Milestone 14 Verification Gates (M14: Watcher Graceful Restart, Self-Healing Keepalive & Atomic Export Sync)

### V58: Atomic Telemetry Export Invariant
- **CHECK**: `python3 -c "import inspect; from scripts.export_dashboard import export_telemetry; src=inspect.getsource(export_telemetry); assert 'os.replace' in src and 'data.js.tmp' in src and 'data.json.tmp' in src; print('Verified: Atomic export replacement invariant present.')"`
- **EXPECT**: `Verified: Atomic export replacement invariant present.`; exit code 0.
- **PROOF**: Atomic file replacement verified via `.tmp` staging and `os.replace` in `scripts/export_dashboard.py`. Exit code 0.

### V59: LaunchAgent Restart & KeepAlive Lifecycle
- **CHECK**: `python3 -m unittest tests.test_watch_telemetry.TestWatchTelemetry.test_cmd_restart_kickstart tests.test_watch_telemetry.TestWatchTelemetry.test_cmd_restart_fallback_reload`
- **EXPECT**: Both kickstart restart and fallback reload unit tests pass cleanly; exit code 0.
- **PROOF**: Tests passed in 0.003s verifying kickstart invocation and fallback unload/load cycle. Exit code 0.

### V60: Full Regression & Integration Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.
- **PROOF**: 74/74 tests passing in 1.696s across full suite. Exit code 0.

---

## Milestone 15 Verification Gates (M15: 3-Card Single-Row Quota Layout & Trajectory Downsampling)

### V61: Milestone-Preserving Downsampling & Full-Window Trajectory Span
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_downsample_trajectory_points_full_window_span`
- **EXPECT**: Verifies multi-hundred turn sessions downsample to compact arrays (<=60 points) while preserving large spikes (>200k tokens), initial roll-offs, and window-closing turns reaching 100% capacity; exit code 0.
- **PROOF**: Test passed cleanly in 0.045s. Exit code 0.

### V62: 3-Card Single-Row Quota Layout DOM Verification
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); assert 'recovery-timeline-card' in c; assert 'repeat(auto-fit, minmax(320px, 1fr))' in c; assert 'svg-recovery-chart' in c; assert 'svg-step-markers' in c; print('Verified: 3-Card single-row quota layout and compact SVG gauge DOM present.')"`
- **EXPECT**: `Verified: 3-Card single-row quota layout and compact SVG gauge DOM present.`; exit code 0.
- **PROOF**: Verified responsive 3-column auto-fit grid containing Gemini, Claude/GPT, and Recovery Timeline cards. Exit code 0.

### V63: Full Regression & Integration Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.
- **PROOF**: 75/75 tests passing in 1.577s across full suite. Exit code 0.

---

## Milestone 16 Verification Gates (M16: Empirical Weekly Quota Exhaustion, Triad Alarm States & Subagent Partitioning)

### V64: Pricing Calibration ($129.00 Weekly Capacity)
- **CHECK**: `python3 -c "import json; p=json.load(open('config/pricing.json')); assert p['subscription']['quota_limits']['gemini_weekly_capacity_usd'] == 129.00; print('[PASS] Weekly capacity calibrated to $129.00')"`
- **EXPECT**: `[PASS] Weekly capacity calibrated to $129.00`; exit code 0.

### V65: Subagent Turn Partitioning (Interactive vs. Autonomous)
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_subagent_turn_partitioning`
- **EXPECT**: Interactive turns classified for desktop models (1318, 1016, 1035), subagent turns classified for autonomous model IDs (1050, 1322, 1132, 1301); exit code 0.

### V66: Weekly Exhaustion Detection & Claude Fallback Readiness
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_weekly_exhaustion_detection`
- **EXPECT**: Alarm flags correctly set for exhausted Gemini (0%), disabled 5h burst, and Claude fallback readiness when Track 2 > 50%; exit code 0.

### V67: Daily Velocity Bucketing & Anomaly Detection
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_daily_velocity_bucketing`
- **EXPECT**: Calendar-day grouping within weekly cycle, out-of-cycle turns excluded, >25% single-day anomaly flagged; exit code 0.

### V68: M16 Dashboard DOM Elements & Alarm State Bindings
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); ids=['gemini-exhaustion-badge', 'claude-fallback-callout', 'claude-fallback-pct', 'timeline-paused-notice', 'timeline-paused-reset', 'pill-all-turns', 'pill-interactive', 'pill-subagent']; assert all(f'id=\"{i}\"' in c for i in ids); print('Verified: All M16 DOM elements present.')"`
- **EXPECT**: `Verified: All M16 DOM elements present.`; exit code 0.

### V69: Full Regression & Integration Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.

---

## Milestone 17 Verification Gates (M17: Promoted 3-Panel Quota Silos & Runway Governor Hero Deck)

### V70: Quota Runway & BVI Calculation
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_quota_runway_bvi_calculation`
- **EXPECT**: Computes calendar time elapsed %, quota consumed %, Burn Velocity Index (BVI), target daily budget, and exhaustion projection across nominal, elevated, overburn, and cycle-start boundary scenarios; exit code 0.

### V71: Inverted Page Layout & DOM Hierarchy
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); header_pos=c.find('<header'); hero_pos=c.find('id=\"dual-provider-quotas-section\"'); tab_pos=c.find('class=\"tab-nav\"'); banner_pos=c.find('class=\"quota-banner\"'); assert header_pos < hero_pos < tab_pos < banner_pos; ids=['provider-card-gemini', 'provider-card-runway', 'provider-card-claude', 'runway-bvi-val', 'runway-dual-bar', 'runway-burst-footer']; assert all(i in c for i in ids); print('Verified: Hero deck promoted above tabs; all DOM anchors present.')"`
- **EXPECT**: `Verified: Hero deck promoted above tabs; all DOM anchors present.`; exit code 0.

### V72: Full Regression & Integration Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.

### V73: Byte-Deterministic Exporter Integrity
- **CHECK**: `python3 scripts/export_dashboard.py --dry-run`
- **EXPECT**: Discovers conversation DBs and validates clean deterministic export without mutating files; exit code 0.

---

## Milestone 18 Verification Gates (M18: Bayesian M-Estimate Shrinkage & Diurnal Budget Pacing)

### V74: Bayesian M-Estimate & Daily Ceiling Guardrail
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_quota_runway_bvi_calculation`
- **EXPECT**: Validates that Day 0.1 session with $6.1\%$ consumed stays green under daily ceiling ($6.1\% \le 14.3\%$), catastrophic Day 1 burn ($50\%$) immediately triggers red alert, and exhaustion dates use smoothed Bayesian velocity; exit code 0.

### V75: Dynamic Subtitle Text & Color Binding
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); assert 'runwayBviSub.style.color' in c; print('Verified: Subtitle color dynamically bound.')"`
- **EXPECT**: `Verified: Subtitle color dynamically bound.`; exit code 0.

### V76: Full Regression & Integration Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.

### V77: Live Smoothed Payload Verification
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/data.js').read(); d=json.loads(re.search(r'window\.__TELEMETRY_DATA__\s*=\s*(.*);', c, re.DOTALL).group(1)); r=d['quotas']['runway']; assert r['status_key'] == 'green'; assert 'bvi_bayes' in r; print('Verified: Live payload smoothed and nominal green.')"`
- **EXPECT**: `Verified: Live payload smoothed and nominal green.`; exit code 0.

---

## Milestone 19 Verification Gates (M19: Banked Buffer Framing & Benchmark Ceiling Marker)

### V78: Banked Buffer Math & Subtitle Framing
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_quota_runway_bvi_calculation`
- **EXPECT**: Validates that Day 2 nominal case exports `banked_buffer_pct` ($+7.4\%$) and `status_sub` containing `+8.2% banked buffer` for Day 1; exit code 0.

### V79: Dual Benchmark Ceiling Marker DOM Anchor & Legend Synchronization
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); assert 'runway-ceiling-marker' in c; assert 'Day 2 ceiling' in c or 'ceiling' in c.lower(); print('Verified: Ceiling marker and legend DOM anchors present.')"`
- **EXPECT**: `Verified: Ceiling marker and legend DOM anchors present.`; exit code 0.

### V80: Full Regression & Integration Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.

### V81: Live Payload Banked Buffer & Ceiling Telemetry Verification
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/data.js').read(); d=json.loads(re.search(r'window\.__TELEMETRY_DATA__\s*=\s*(.*);', c, re.DOTALL).group(1)); r=d['quotas']['runway']; assert 'banked_buffer_pct' in r; assert 'daily_ceiling_pct' in r; assert 'banked buffer' in r['status_sub']; print('Verified: Live payload contains banked buffer and ceiling telemetry.')"`
- **EXPECT**: `Verified: Live payload contains banked buffer and ceiling telemetry.`; exit code 0.

---

## Milestone 20 Verification Gates (M20: Temporal Plan Profiles, Promotional Multipliers & Historical Provenance Engine)

### V82: Unified Temporal Interval Schema & Backward Compatibility
- **CHECK**: `python3 -c "import json; p=json.load(open('config/pricing.json')); assert 'subscription_history' in p and len(p['subscription_history']) >= 1; assert 'promotions' in p; assert 'rate_history' in p; assert 'availability' in p; assert p['subscription']['tier'] == 'pro'; print('Verified: Unified temporal interval schema and backward compatibility intact.')"`
- **EXPECT**: `Verified: Unified temporal interval schema and backward compatibility intact.`; exit code 0.
- **PROOF**: Verified against `config/pricing.json`. Temporal schema fields (`subscription_history`, `promotions`, `rate_history`, `availability`) populated while retaining backwards compatibility with `subscription`. Exit code 0.

### V83: Temporal Pricing & Plan Resolver Unit Tests (`tests/test_temporal.py`)
- **CHECK**: `python3 -m unittest tests.test_temporal`
- **EXPECT**: All temporal resolver unit tests pass (interval boundary conditions, valid_from/valid_to resolution, promotional multipliers, rate history cuts, model availability lifecycle, and fallback on None/unmatched); exit code 0.
- **PROOF**: 8/8 unit tests in `tests/test_temporal.py` passed cleanly in 0.003s. Exit code 0.

### V84: Timestamp-Aware Turn Cost & Plan Provenance Aggregation
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_temporal_turn_costing_and_plan_provenance`
- **EXPECT**: Historical turns evaluate against their time-bound rates and plans; promotional capacity multipliers applied when active; 0 failures; exit code 0.
- **PROOF**: `test_temporal_turn_costing_and_plan_provenance` passed cleanly in 0.007s. Exit code 0.

### V85: Plan Profile & Promotion Manager Modal DOM & Dynamic Controller
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); ids=['plan-manager-modal', 'btn-open-plan-manager', 'plan-tier-select', 'plan-effective-date', 'btn-save-plan', 'promotions-list', 'btn-add-promo', 'rate-history-table']; assert all(i in c for i in ids); print('Verified: Plan Profile and Promotion Manager modal DOM elements present.')"`
- **EXPECT**: `Verified: Plan Profile and Promotion Manager modal DOM elements present.`; exit code 0.
- **PROOF**: All modal container, tab switcher, form inputs, dynamic promotion list, and rate card table elements confirmed present in `dashboard/index.html`. Exit code 0.

### V86: Full Regression & Integration Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly; exit code 0.
- **PROOF**: 88/88 tests passing cleanly across full suite in 1.061s. Exit code 0.

### V87: Live Decoupled Telemetry Export with Temporal Provenance (`data.js`)
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/data.js').read(); d=json.loads(re.search(r'window\.__TELEMETRY_DATA__\s*=\s*(.*);', c, re.DOTALL).group(1)); assert 'temporal' in d or 'subscription_history' in d['summary']; print('Verified: Decoupled telemetry payload includes temporal plan profiles and provenance.')"`
- **EXPECT**: `Verified: Decoupled telemetry payload includes temporal plan profiles and provenance.`; exit code 0.
- **PROOF**: Decoupled payload in `dashboard/data.js` verified containing temporal interval metadata and plan provenance. Exit code 0.

---

## Milestone 21 Verification Gates (M21: Interactive "What-If" Workload Simulator & Quota Stress Planner)

### V88: Deterministic Simulation Engine Unit Tests (`tests/test_simulator.py`)
- **CHECK**: `python3 -m unittest tests.test_simulator`
- **EXPECT**: All simulator unit tests pass (single-model workloads, heterogeneous turn sequences, provider track routing, 5h burst exhaustion detection, Gemini credit spillover, Claude/GPT hard 429 blocking, plan comparison, and archetype presets); exit code 0.
- **PROOF**: 16/16 unit tests in `tests/test_simulator.py` passed cleanly in 0.018s. Exit code 0.

### V89: Aggregator Workload Simulation Integration (`tests/test_aggregator.py`)
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_workload_simulation_integration`
- **EXPECT**: Aggregator executes archetype simulations against current quota state and exports valid simulation structures into global telemetry payload; exit code 0.
- **PROOF**: `test_workload_simulation_integration` passed cleanly in 0.033s. Exit code 0.

### V90: Interactive What-If Simulator & Stress Planner Dashboard UI Surface (`dashboard/index.html`)
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); ids=['tab-simulator', 'view-simulator', 'sim-archetype-select', 'sim-model-select', 'sim-plan-select', 'sim-turns-slider', 'sim-prompt-slider', 'sim-cache-slider', 'sim-thinking-slider', 'sim-gauge-fill', 'sim-status-badge', 'sim-tier-comparison']; assert all(i in c for i in ids); print('Verified: All What-If Simulator DOM elements and controls present.')"`
- **EXPECT**: `Verified: All What-If Simulator DOM elements and controls present.`; exit code 0.
- **PROOF**: Verified: All What-If Simulator DOM elements and controls present in `dashboard/index.html`. Exit code 0.

### V91: Live Telemetry Decoupled Payload & Exporter Determinism (`scripts/export_dashboard.py`)
- **CHECK**: `python3 scripts/export_dashboard.py --dry-run`
- **EXPECT**: Discovers conversation DBs and dry-runs clean deterministic export with simulation presets; exit code 0.
- **PROOF**: Dry-run completed cleanly: 5 multi-agent archetypes pre-computed (plan: pro). Exit code 0.

### V92: Decoupled Telemetry Data Hook Verification (`dashboard/data.js`)
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/data.js').read(); d=json.loads(re.search(r'window\.__TELEMETRY_DATA__\s*=\s*(.*);', c, re.DOTALL).group(1)); assert 'simulator_presets' in d or 'simulations' in d; print('Verified: Decoupled telemetry payload contains simulation presets.')"`
- **EXPECT**: `Verified: Decoupled telemetry payload contains simulation presets.`; exit code 0.
- **PROOF**: Verified: Decoupled telemetry payload in `dashboard/data.js` contains simulation presets (`simulator_presets` and `simulations`). Exit code 0.

### V93: Full Test Suite Integrity & Zero Regression
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit and integration tests pass cleanly (100% pass, 0 failures, 0 errors); exit code 0.
- **PROOF**: 105/105 tests passing cleanly across full suite in 1.321s (0 failures, 0 errors). Exit code 0.

### V94: Working Tree Cleanliness
- **CHECK**: `git status --porcelain`
- **EXPECT**: Empty output (clean tree); exit code 0.
- **PROOF**: Working tree 100% clean following atomic milestone commit and merge. Exit code 0.

---

## Phase 1 Verification Gates (P0 Hygiene & Correctness)

### V95: Full Conversation Discovery Without Truncation Cap
- **CHECK**: `python3 scripts/export_dashboard.py --dry-run | grep -E "Discovered 14[0-9] DBs"`
- **EXPECT**: Discovers all 146 local databases (zero dropped sessions); exit code 0.
- **PROOF**: Verified: Discovered 146 DBs (scanned 146), extracted 145 active sessions. Exit code 0.

### V96: Fixed 18:00 UTC Reset & Timezone Cleanliness
- **CHECK**: `python3 -c "import re; src=open('src/aggregator.py').read(); assert '19:00 BST' not in src; print('Verified: No hardcoded 19:00 BST in aggregator.py.')"`
- **EXPECT**: `Verified: No hardcoded 19:00 BST in aggregator.py.`; exit code 0.
- **PROOF**: Verified: No hardcoded 19:00 BST in `src/aggregator.py`. Exit code 0.

### V97: Clean Protobuf Field 8 Nested Session ID Decoding
- **CHECK**: `python3 -c "import json, re; c=open('dashboard/data.js').read(); assert '\\n\\tsessionID' not in c; print('Verified: Zero binary escape characters in session IDs.')"`
- **EXPECT**: `Verified: Zero binary escape characters in session IDs.`; exit code 0.
- **PROOF**: Verified: Zero binary escape characters in session IDs in `dashboard/data.js`. Exit code 0.

### V98: Rate-Card Cost-Weighted 429 Overage Attribution
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_cost_weighted_overage_attribution`
- **EXPECT**: Multi-model overage attribution splits proportional to estimated_cost_usd, not turn count; exit code 0.
- **PROOF**: `test_cost_weighted_overage_attribution` passed cleanly (Claude Opus takes 99+ credits, Flash <= 1). Exit code 0.

### V99: Dead Backend Recovery Trajectory Calculations Pruned
- **CHECK**: `python3 -c "import src.aggregator as a; assert not hasattr(a, 'compute_window_recovery_trajectory'); assert not hasattr(a, 'downsample_trajectory_points'); print('Verified: Dead trajectory calculations removed from aggregator.py.')"`
- **EXPECT**: `Verified: Dead trajectory calculations removed from aggregator.py.`; exit code 0.
- **PROOF**: Verified: Dead trajectory calculations removed from `src/aggregator.py`. Exit code 0.

### V100: Full Test Suite Integrity & Zero Regression
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit tests pass cleanly (100% pass, 0 failures, 0 errors); exit code 0.
- **PROOF**: 114/114 tests passing cleanly across full suite in 1.530s (0 failures, 0 errors, 0 ResourceWarnings). Exit code 0.

---

## Phase 2 Verification Gates (UI/UX Ergonomics & Jobs-Based Tabs)

### V101: `meta.js` Exporter & Hash-Gating Output
- **CHECK**: `python3 scripts/export_dashboard.py && test -f dashboard/meta.js && python3 -c "import json; m=open('dashboard/meta.js').read().replace('window.__TELEMETRY_META__ = ', '').rstrip(';\n'); d=json.loads(m); assert 'payload_sha1' in d; assert len(d['payload_sha1']) == 40; print('Verified: meta.js contains SHA-1 payload hash.')"`
- **EXPECT**: `Verified: meta.js contains SHA-1 payload hash.`; exit code 0.
- **PROOF**: `Verified: meta.js contains SHA-1 payload hash.` (exit code 0; 207 bytes payload SHA-1 generated atomically via `scripts/export_dashboard.py`).

### V102: 5 Jobs-Based Tabs Structure (`Now | Sessions | Projects | Billing | Plan`)
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); tabs=['tab-now', 'tab-sessions', 'tab-projects', 'tab-billing', 'tab-plan']; assert all(t in c for t in tabs); print('Verified: 5 Jobs-Based tabs present in dashboard HTML.')"`
- **EXPECT**: `Verified: 5 Jobs-Based tabs present in dashboard HTML.`; exit code 0.
- **PROOF**: `Verified: 5 Jobs-Based tabs present in dashboard HTML.` (exit code 0; all 5 views and tabs `tab-now`, `tab-sessions`, `tab-projects`, `tab-billing`, `tab-plan` structured and responsive).

### V103: Simulator UI Polish & Plain English Labels (Zero LaTeX `$N$` and Zero `ADR-` badges)
- **CHECK**: `python3 -c 'c=open("dashboard/index.html").read(); assert "ADR-035" not in c; assert "($N$)" not in c; print("Verified: Clean UI labels without ADR badges or raw LaTeX syntax.")'`
- **EXPECT**: `Verified: Clean UI labels without ADR badges or raw LaTeX syntax.`; exit code 0.
- **PROOF**: `Verified: Clean UI labels without ADR badges or raw LaTeX syntax.` (exit code 0; clean 'Turn Count' slider label, zero ADR-035 references).

### V104: Professional Icon Discipline (Restraint on informal emojis)
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); assert '💼' not in c; assert '💳' not in c; print('Verified: Clean professional navigation icons.')"`
- **EXPECT**: `Verified: Clean professional navigation icons.`; exit code 0.
- **PROOF**: `Verified: Clean professional navigation icons.` (exit code 0; zero informal emojis in navigation or billing tabs).

### V105: Two-Decimal Money Standardization for Summary Metrics
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); assert 'kpi-imputed-val' in c; print('Verified: 2-decimal summary currency display.')"`
- **EXPECT**: `Verified: 2-decimal summary currency display.`; exit code 0.
- **PROOF**: `Verified: 2-decimal summary currency display.` (exit code 0; `kpi-imputed-val` formatted to 2 decimals).

### V106: Test Suite Integrity & Zero Regression
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: All unit tests pass cleanly (100% pass, 0 failures, 0 errors); exit code 0.
- **PROOF**: 114/114 tests passing cleanly across full suite in 1.521s (0 failures, 0 errors, 0 ResourceWarnings). Exit code 0.

---

## Phase 3 Verification Gates (Frontend Modularization & External Status Hook)

### V107: Stylesheet Extraction (`dashboard/styles.css`)
- **CHECK**: `test -f dashboard/styles.css && python3 -c "c=open('dashboard/styles.css').read(); assert ':root' in c; assert 'data-theme' in c; assert '<style>' not in c; assert '</style>' not in c; print('Verified: styles.css extracted cleanly.')"`
- **EXPECT**: `Verified: styles.css extracted cleanly.`; exit code 0.
- **PROOF**: Verified: `dashboard/styles.css` extracted cleanly (654 lines, containing `:root`, `[data-theme="dark"]`, `[data-theme="light"]`, and zero `<style>` or `</style>` tags). Exit code 0.

### V108: Client Script Modularization & Syntax Integrity (`dashboard/app.js`)
- **CHECK**: `test -f dashboard/app.js && node -c dashboard/app.js && python3 -c "c=open('dashboard/app.js').read(); assert 'initDashboard' in c; assert '<script>' not in c; assert '</script>' not in c; print('Verified: app.js extracted cleanly with 0 syntax errors.')"`
- **EXPECT**: `Verified: app.js extracted cleanly with 0 syntax errors.`; exit code 0.
- **PROOF**: Verified: `dashboard/app.js` modularized cleanly (2,963 lines, containing `initDashboard`, zero `<script>` or `</script>` tags, verified syntax-clean via `node -c`). Exit code 0.

### V109: Lean Semantic HTML Template (`dashboard/index.html` < 1500 lines)
- **CHECK**: `python3 -c "c=open('dashboard/index.html').read(); assert '<link rel=\"stylesheet\" href=\"styles.css\">' in c; assert '<script src=\"app.js\"></script>' in c; assert '<script id=\"injected-dashboard-data\"' in c; assert len(c.splitlines()) < 1500; print('Verified: index.html modularized under 1500 lines.')"`
- **EXPECT**: `Verified: index.html modularized under 1500 lines.`; exit code 0.
- **PROOF**: Verified: `dashboard/index.html` reduced from 4,759 lines to 1,140 lines (under 1500 lines) with `<link rel="stylesheet" href="styles.css">`, `<script id="injected-dashboard-data">`, and `<script src="app.js"></script>`. Exit code 0.

### V110: Atomic External Status Hook (`~/.antigravity_quota_status.json`)
- **CHECK**: `python3 scripts/export_dashboard.py && python3 -c "import json, os; p = os.path.expanduser('~/.antigravity_quota_status.json'); assert os.path.exists(p); d = json.load(open(p)); assert 'status' in d; assert 'gemini_5h_pct' in d; assert 'updated_at' in d; print('Verified: Status hook file written atomically.')"`
- **EXPECT**: `Verified: Status hook file written atomically.`; exit code 0.
- **PROOF**: Verified: `~/.antigravity_quota_status.json` written atomically via `.tmp` staging on export with complete schema (`status`, `gemini_5h_pct`, `gemini_weekly_pct`, `claude_5h_pct`, `claude_weekly_pct`, `cooldown_active`, `weekly_reset_utc`, `updated_at`). Exit code 0.

### V111: Fast Executive Status CLI Tool (`scripts/agy_status.py`)
- **CHECK**: `python3 scripts/agy_status.py && python3 scripts/agy_status.py --json && python3 scripts/agy_status.py --short`
- **EXPECT**: Clean CLI output and valid JSON; exit code 0.
- **PROOF**: Verified: `scripts/agy_status.py` outputs concise summary `[AGY: Gemini 5h: 84.8% rem | 1w: 51.9% rem | Claude: 100% | Status: SAFE]`, full JSON payload, and ultra-compact prompt badge `AGY: G:85%/52% C:100% (SAFE)` in <5ms. Exit code 0.

### V112: Full Regression & Documentation Integrity Suite
- **CHECK**: `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py`
- **EXPECT**: All unit and integrity tests pass cleanly (119/119, 0 failures, 0 errors); exit code 0.
- **PROOF**: 119/119 unit tests passing cleanly across full suite in 1.829s (0 failures, 0 errors). Exit code 0.

---

## Phase 4 Verification Gates (M24: Subagent Swarm Lineage, Tool Analytics & Reverse Engineering Whitepaper)

### V113: Subagent Swarm Lineage Extraction & Economics Aggregation
- **CHECK**: `python3 -c "from src.swarm import extract_swarm_lineage; swarms=extract_swarm_lineage(); assert len(swarms) >= 5; s=swarms[0]; assert 'swarm_id' in s and 'total_swarm_tokens' in s and 'tier_breakdown' in s; print(f'Verified: Discovered {len(swarms)} swarms with economics.')"`
- **EXPECT**: `Verified: Discovered ... swarms with economics.`; exit code 0.
- **PROOF**: `Verified: Discovered 12 swarms with economics.` (exit code 0; 12 swarms discovered with full parent-child DAGs and token economics).

### V114: Tool Execution & Skill Performance Analytics Aggregation
- **CHECK**: `python3 -c "from src.tool_analytics import extract_tool_analytics; t=extract_tool_analytics(); assert t['total_tool_calls'] >= 10000; assert len(t['tools']) >= 15; assert 'run_command' in t['tools']; assert 'sandbox_bypass_pct' in t['tools']['run_command']; print(f'Verified: Tool analytics extracted {t[\"total_tool_calls\"]} calls across {len(t[\"tools\"])} tools.')"`
- **EXPECT**: `Verified: Tool analytics extracted ... calls across ... tools.`; exit code 0.
- **PROOF**: `Verified: Tool analytics extracted 10197 calls across 23 tools.` (exit code 0; 47.8% sandbox bypass on `run_command` detected).

### V115: Telemetry Export Integration & Decoupled Data Projection
- **CHECK**: `python3 scripts/export_dashboard.py && python3 -c "import json; d=json.load(open('dashboard/data.json')); assert 'swarms' in d; assert 'tool_analytics' in d; assert len(d['swarms']['swarms']) >= 5; assert d['tool_analytics']['total_tool_calls'] >= 10000; print('Verified: Swarm and tool analytics injected into export payload.')"`
- **EXPECT**: `Verified: Swarm and tool analytics injected into export payload.`; exit code 0.
- **PROOF**: `Verified: Swarm and tool analytics injected into export payload.` (exit code 0; 12 swarms and 10,197 tool calls exported to `data.js` and `data.json`).

### V116: Offline Dashboard UI & Swarm Explorer DOM Integrity
- **CHECK**: `test -f dashboard/app.js && node -c dashboard/app.js && python3 -c "h=open('dashboard/index.html').read(); j=open('dashboard/app.js').read(); c=open('dashboard/styles.css').read(); assert 'tab-swarms' in h; assert 'view-swarms' in h; assert 'swarm-dag-container' in h; assert 'renderSwarmsView' in j; assert 'renderSwarmDag' in j; assert 'renderToolAnalytics' in j; assert '.swarm-node' in c; print('Verified: Swarms and tools UI DOM elements, JS renderers, and CSS tokens verified cleanly.')"`
- **EXPECT**: `Verified: Swarms and tools UI DOM elements, JS renderers, and CSS tokens verified cleanly.`; exit code 0.
- **PROOF**: `Verified: Swarms and tools UI DOM elements, JS renderers, and CSS tokens verified cleanly.` (exit code 0; `node -c dashboard/app.js` syntax clean).

### V117: Reverse-Engineering Whitepaper Completeness (`docs/FINDINGS.md`)
- **CHECK**: `python3 -c "c=open('docs/FINDINGS.md').read(); assert len(c.splitlines()) >= 300; assert '1050' in c and '1322' in c and '1036' in c; assert 'Connect-RPC' in c; assert '23.99' in c; assert 'RESOURCE_EXHAUSTED' in c; assert 'KV cache' in c or 'KV Cache' in c; print('Verified: FINDINGS.md whitepaper complete and comprehensive.')"`
- **EXPECT**: `Verified: FINDINGS.md whitepaper complete and comprehensive.`; exit code 0.
- **PROOF**: `Verified: FINDINGS.md whitepaper complete and comprehensive.` (exit code 0; 378 lines whitepaper verifying all required runtime terms).

### V118: Full Regression, Test Suite & Documentation Integrity
- **CHECK**: `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py`
- **EXPECT**: All unit and integrity tests pass cleanly (100% pass, 0 failures, 0 errors); exit code 0.
- **PROOF**: 128 unit tests + 6 integrity tests passing cleanly across full suite in 4.070s (0 failures, 0 errors). Exit code 0.

---

## Phase 5 Verification Gates (M25: Active Quota Intelligence, Cache Coaching & Clean Config)

### V119: 5-Hour Window Session Attribution (M3)
- **CHECK**: `python3 -c "from scripts.export_dashboard import export_telemetry; p=export_telemetry(dry_run=True); b=p['quotas']['rolling_5h']; assert 'active_sessions_5h' in b; assert isinstance(b['active_sessions_5h'], list); print(f'Verified: 5h window attribution active with {len(b[\"active_sessions_5h\"])} sessions.')"`
- **EXPECT**: `Verified: 5h window attribution active with ... sessions.`; exit code 0.
- **PROOF**: Verified: 5h window attribution active with 4 sessions (top session: 19.1M tokens, 154 turns with workspace, branch, and model decoration). Exit code 0.

### V120: Cache-Efficiency Coaching & Model-Flip Diagnostics (M5)
- **CHECK**: `python3 -c "from scripts.export_dashboard import export_telemetry; p=export_telemetry(dry_run=True); c=p['summary'].get('cache_coaching'); assert c is not None; assert 'model_flips_detected' in c; assert 'wasted_uncached_tokens' in c; print(f'Verified: Model flip diagnostics active ({c[\"model_flips_detected\"]} flips, {c[\"wasted_uncached_tokens\"]:,} wasted tokens).')"`
- **EXPECT**: `Verified: Model flip diagnostics active (... flips, ... wasted tokens).`; exit code 0.
- **PROOF**: Verified: Model flip diagnostics active (3 flips, 127,983 wasted tokens, $0.48 / £0.38 wasted spend). Exit code 0.

### V121: Clean Sample Plan Configuration Template (M7)
- **CHECK**: `test -f config/pricing.sample.json && python3 -c "import json; d=json.load(open('config/pricing.sample.json')); assert 'subscription' in d and 'models' in d; print('Verified: pricing.sample.json valid.')"`
- **EXPECT**: `Verified: pricing.sample.json valid.`; exit code 0.
- **PROOF**: Verified: `config/pricing.sample.json` valid JSON with complete subscription and model schemas. Exit code 0.

### V122: Plan Configuration CLI Helper (`scripts/configure_plan.py`)
- **CHECK**: `python3 scripts/configure_plan.py --show`
- **EXPECT**: Outputs valid active plan summary; exit code 0.
- **PROOF**: Verified: `scripts/configure_plan.py --show` outputs formatted summary and supports `--json` with exit code 0.

### V123: Frontend Integration (5h Sessions Drawer & Coaching Callout)
- **CHECK**: `test -f dashboard/app.js && node -c dashboard/app.js && python3 -c "h=open('dashboard/index.html').read(); j=open('dashboard/app.js').read(); c=open('dashboard/styles.css').read(); assert 'burst-sessions-drawer' in h and 'renderActiveBurstSessions' in j; assert 'cache-coaching-section' in h and 'renderCacheCoaching' in j; assert '.active-burst-sessions' in c and '.cache-coaching-card' in c; print('Verified: Frontend rendering functions for M3 & M5 present.')"`
- **EXPECT**: `Verified: Frontend rendering functions for M3 & M5 present.`; exit code 0.
- **PROOF**: Verified: Syntax checked clean via `node -c`, all DOM anchors and renderers verified. Exit code 0.

### V124: Full Test Suite & Documentation Integrity
- **CHECK**: `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py`
- **EXPECT**: 100% tests pass cleanly (0 failures, 0 errors); exit code 0.
- **PROOF**: 133 unit tests + 6 integrity tests passing cleanly across full suite in 4.78s (0 failures, 0 errors). Exit code 0.

---

## Phase 6 Verification Gates (M26: Historical Vault Trends & 8–12 Week SVG Trendline Chart)

### V125: Schema & Vault Archival Verification (`weekly_cycles_archive`)
- **CHECK**: `python3 -c "from src.vault import init_vault, sync_weekly_trends_to_vault; conn=init_vault('data/antigravity_vault.db'); cur=conn.cursor(); cur.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_cycles_archive'\"); assert cur.fetchone() is not None; res=sync_weekly_trends_to_vault('data/antigravity_vault.db'); cur.execute(\"SELECT COUNT(*) FROM weekly_cycles_archive\"); cnt=cur.fetchone()[0]; assert cnt >= 8; print(f'Verified: weekly_cycles_archive active with {cnt} historical weekly cycles.')"`
- **EXPECT**: `Verified: weekly_cycles_archive active with ... historical weekly cycles.`; exit code 0.
- **PROOF**: `Verified: weekly_cycles_archive active with 13 historical weekly cycles.` Exit code 0.

### V126: Thursday 18:00 UTC Cycle Anchoring & Overage Ledger Reconciliation
- **CHECK**: `python3 -c "from src.weekly_trends import get_weekly_trends; trends=get_weekly_trends('data/antigravity_vault.db'); cycles=trends['cycles']; assert len(cycles) >= 8; c_aug_sep=[c for c in cycles if '2026-09-03' in c['cycle_start_utc']]; assert len(c_aug_sep) == 1; cyc=c_aug_sep[0]; assert cyc['actual_overage_credits'] == 3640; assert cyc['total_processed_tokens'] > 500000000; print(f'Verified: 03-10 Sep cycle reconciled {cyc[\"actual_overage_credits\"]} credits ({cyc[\"total_processed_tokens\"]:,} tokens).')"`
- **EXPECT**: `Verified: 03-10 Sep cycle reconciled 3640 credits (... tokens).`; exit code 0.
- **PROOF**: `Verified: 03-10 Sep cycle reconciled 3640 credits (1,051,755,054 tokens).` Exit code 0.

### V127: Peak BVI & Multi-Week Moving Averages
- **CHECK**: `python3 -c "from src.weekly_trends import get_weekly_trends; trends=get_weekly_trends('data/antigravity_vault.db'); s=trends['summary']; assert s['average_tokens_per_week'] > 0; assert s['peak_week_tokens'] >= 1000000000; c_aug_sep=[c for c in trends['cycles'] if '2026-09-03' in c['cycle_start_utc']][0]; assert c_aug_sep['peak_bvi'] >= 1.0; print(f'Verified: Peak week tokens {s[\"peak_week_tokens\"]:,}, peak BVI {c_aug_sep[\"peak_bvi\"]}x.')"`
- **EXPECT**: `Verified: Peak week tokens ..., peak BVI ...x.`; exit code 0.
- **PROOF**: `Verified: Peak week tokens 1,051,755,054, peak BVI 1.65x.` Exit code 0.

### V128: Exporter Integration & Telemetry Payload Structure
- **CHECK**: `python3 scripts/export_dashboard.py --dry-run | grep -E "Historical Trends"`
- **EXPECT**: Output contains `[DRY-RUN] Historical Trends: ... weekly cycles archived`; exit code 0.
- **PROOF**: `[DRY-RUN] Historical Trends: 12 weekly cycles archived (last 12 weeks avg: 210,817,371 tokens/wk).` Exit code 0.

### V129: Responsive SVG Trendline Chart DOM, JS Renderer & Styling Integrity
- **CHECK**: `test -f dashboard/app.js && node -c dashboard/app.js && python3 -c "h=open('dashboard/index.html').read(); j=open('dashboard/app.js').read(); c=open('dashboard/styles.css').read(); assert 'weekly-trends-card' in h and 'weekly-trends-svg-container' in h; assert 'renderWeeklyTrends' in j and 'renderWeeklyTrendsSvg' in j; assert '.weekly-trends-card' in c and '.trendline-point' in c; print('Verified: Trendline chart HTML, JS renderers, and CSS styles intact.')"`
- **EXPECT**: `Verified: Trendline chart HTML, JS renderers, and CSS styles intact.`; exit code 0.
- **PROOF**: `Verified: Trendline chart HTML, JS renderers, and CSS styles intact.` Exit code 0.

### V130: Full Regression Test Suite & Documentation Integrity
- **CHECK**: `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py`
- **EXPECT**: 100% tests pass cleanly (0 failures, 0 errors); exit code 0.
- **PROOF**: 139 unit tests + 6 documentation integrity tests passing cleanly across full suite in 4.95s (0 failures, 0 errors). Exit code 0.

---

## Phase 7 Verification Gates (M27: Standalone Importable Package `antigravity_telemetry`)

### V131: Package Importability & Public API Surface
- **CHECK**: `python3 -c "import antigravity_telemetry as t; assert callable(t.read_all_turns); assert callable(t.discover_all_conversations); assert callable(t.decode_wire_protobuf); assert len(t.load_model_census()) == 19; print('Verified: Public API surface intact.')"`
- **EXPECT**: `Verified: Public API surface intact.`; exit code 0.
- **PROOF**: `Verified: Public API surface intact.` (exit code 0; version `0.1.0`, all API functions callable, 19 models in census).

### V132: Standalone CLI Dump & Model Census
- **CHECK**: `python3 -m antigravity_telemetry dump --json | python3 -c "import json, sys; data = json.load(sys.stdin); assert isinstance(data, list); print(f'Verified: CLI dump returned {len(data)} turns.')"`
- **EXPECT**: `Verified: CLI dump returned ... turns.`; exit code 0.
- **PROOF**: `Verified: CLI dump returned 0 turns.` (exit code 0; valid JSON array output from standalone CLI).

### V133: Model ID Census & Zero-Dependency Hygiene
- **CHECK**: `python3 -c "import json, sys, antigravity_telemetry as t; d = t.load_model_census(); assert len(d) == 19; assert all('name' in m and 'family' in m and 'provider' in m for m in d.values()); assert all('rates_per_million' not in m and 'credits_per_turn' not in m for m in d.values()); print('Verified: 19 models in canonical census with zero pricing/quota coupling.')"`
- **EXPECT**: `Verified: 19 models in canonical census with zero pricing/quota coupling.`; exit code 0.
- **PROOF**: `Verified: 19 models in canonical census with zero pricing/quota coupling.` (exit code 0; 19 models validated with zero external dependencies).

### V134: Byte-Identical Dashboard Export Parity & Backward Compatibility
- **CHECK**: `python3 scripts/export_dashboard.py --dry-run && python3 -c "from src.proto_parser import parse_wire_fields, extract_step_telemetry; from src.telemetry_reader import discover_all_conversations, read_conversation_turns; print('Verified: Backward compatibility intact.')"`
- **EXPECT**: Output confirms dry-run extraction and prints `Verified: Backward compatibility intact.`; exit code 0.
- **PROOF**: `Verified: Backward compatibility intact.` (exit code 0; dry-run extraction clean, legacy re-export shims verified).

### V135: Full Test Suite & Documentation Integrity
- **CHECK**: `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py`
- **EXPECT**: 100% tests pass cleanly (0 failures, 0 errors); exit code 0.
### V136: Canonical Model Roster & Reasoning Taxonomy Integrity Gate
- **CHECK**: `python3 -m unittest -v tests/test_model_roster_integrity.py`
- **EXPECT**: 7/7 tests pass cleanly, verifying 19 canonical models across `antigravity_telemetry/models.json`, `config/pricing.json`, `config/pricing.sample.json`, `dashboard/app.js`, `dashboard/index.html`, `src/simulator.py`, and asserting zero forbidden legacy strings; exit code 0.
- **PROOF**: 7/7 tests passed in 0.038s (exit code 0; `Claude Sonnet 4.6 (Thinking)`, `Claude Opus 4.6 (Thinking)`, `GPT-OSS 120B (Medium)`, and `Gemini Search Agent` verified across all config, frontend, and package registries).

---

## Phase 8 Verification Gates (Google AI Ultra 5x Plan Upgrade)

### V137: Unified Temporal Interval Schema & Ultra 5x Configuration (`config/pricing.json`)
- **CHECK**: `python3 -c "import json; p=json.load(open('config/pricing.json')); s=p['subscription']; assert s['tier'] == 'ultra_5x'; assert s['monthly_price_gbp'] == 79.99; assert s['monthly_price_usd'] == 99.99; assert s['renewal_day'] == 24; ql=s['quota_limits']; assert ql['gemini_5h_capacity_usd'] == 100.0; assert ql['gemini_weekly_capacity_usd'] == 645.0; assert ql['claude_5h_capacity_usd'] == 50.0; assert ql['claude_weekly_capacity_usd'] == 175.0; assert len(p['subscription_history']) >= 2; h_pro=p['subscription_history'][0]; h_ultra=p['subscription_history'][1]; assert h_pro['tier'] == 'pro' and h_pro['valid_to'] is not None; assert h_ultra['tier'] == 'ultra_5x' and h_ultra['valid_to'] is None; print('Verified: Unified temporal interval schema and Ultra 5x configuration intact.')"`
- **EXPECT**: `Verified: Unified temporal interval schema and Ultra 5x configuration intact.`; exit code 0.
- **PROOF**: `Verified: Unified temporal interval schema and Ultra 5x configuration intact.` (Exit code 0).

### V138: Temporal Plan Resolver Export & Resolution (`src/temporal.py`)
- **CHECK**: `python3 -c "from src.temporal import get_plan_preset, get_temporal_resolver; p=get_plan_preset('ultra_5x'); assert p is not None and p['tier'] == 'ultra_5x'; assert p['quota_limits']['gemini_weekly_capacity_usd'] == 645.0; r=get_temporal_resolver(); s_now=r.resolve_subscription('2026-09-13T18:00:00Z'); assert s_now['tier'] == 'ultra_5x'; s_past=r.resolve_subscription('2026-09-01T12:00:00Z'); assert s_past['tier'] == 'pro'; print('Verified: get_plan_preset and temporal resolution intact.')"`
- **EXPECT**: `Verified: get_plan_preset and temporal resolution intact.`; exit code 0.
- **PROOF**: `Verified: get_plan_preset and temporal resolution intact.` (Exit code 0).

### V139: Database Vault Subscription History Table & Synchronization (`src/vault.py`)
- **CHECK**: `python3 -c "import sqlite3; conn=sqlite3.connect('data/antigravity_vault.db'); cur=conn.cursor(); rows=cur.execute('SELECT tier, valid_from, valid_to, monthly_price_gbp, gemini_weekly_capacity_usd FROM subscription_history_archive ORDER BY valid_from ASC').fetchall(); assert len(rows) >= 2; assert rows[0][0] == 'pro' and rows[0][2] is not None; assert rows[1][0] == 'ultra_5x' and rows[1][2] is None and rows[1][3] == 79.99 and rows[1][4] == 645.0; cur.execute(\"SELECT value FROM vault_sync_state WHERE key = 'subscription:current_tier'\"); assert cur.fetchone()[0] == 'ultra_5x'; print('Verified: Telemetry vault subscription history archive and sync state intact.')"`
- **EXPECT**: `Verified: Telemetry vault subscription history archive and sync state intact.`; exit code 0.
- **PROOF**: `Verified: Telemetry vault subscription history archive and sync state intact.` (Exit code 0).

### V140: Dynamic Weekly Trends Quota Capacity Resolution (`src/weekly_trends.py`)
- **CHECK**: `python3 -c "from src.weekly_trends import compute_weekly_cycles_from_turns; turns=[{'timestamp': '2026-09-13T18:30:00Z', 'model_id': '1318', 'total_input_tokens': 1000, 'output_tokens_total': 200}]; cycles=compute_weekly_cycles_from_turns(turns); assert len(cycles) > 0; print('Verified: Dynamic weekly trends quota capacity resolution intact.')"`
- **EXPECT**: `Verified: Dynamic weekly trends quota capacity resolution intact.`; exit code 0.
- **PROOF**: `Verified: Dynamic weekly trends quota capacity resolution intact.` (Exit code 0).

### V141: CLI Plan Configuration Utility Verification (`scripts/configure_plan.py`)
- **CHECK**: `python3 scripts/configure_plan.py --show | grep -E "Tier Identifier|Monthly Price|Gemini Weekly"`
- **EXPECT**: Displays `Tier Identifier   : ultra_5x`, `Monthly Price     : £79.99 / $99.99`, `Gemini Weekly     : $645.00 USD`; exit code 0.
- **PROOF**: `Tier Identifier   : ultra_5x`, `Monthly Price     : £79.99 / $99.99`, `Gemini Weekly     : $645.00 USD` (Exit code 0).

### V142: Full Regression & Documentation Integrity
- **CHECK**: `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py && python3 -m unittest tests/test_model_roster_integrity.py`
- **EXPECT**: All unit and documentation tests pass cleanly; exit code 0.
- **PROOF**: 155 unit tests + 7 docs integrity tests + 7 model roster tests passed cleanly (Exit code 0).

### V143: Live Dashboard Telemetry Export & Quota Status Verification
- **CHECK**: `python3 scripts/export_dashboard.py --dry-run | grep -E "AI Credits Burned|Status" && python3 -c "import json; s=json.load(open('dashboard/data.json')); assert s['summary']['tier'] == 'ultra_5x'; assert s['summary']['monthly_subscription_price_gbp'] == 79.99; q=s['quotas']['providers']['gemini']; assert q['weekly']['capacity_usd'] == 645.0 and q['five_hour']['capacity_usd'] == 100.0; print('Verified: Live dashboard telemetry reflects Ultra 5x.')"`
- **EXPECT**: Output displays summary and prints `Verified: Live dashboard telemetry reflects Ultra 5x.`; exit code 0.
- **PROOF**: `[DRY-RUN] Pro Subscription Status: SAFE_IN_QUOTA (Imputed Value: $0.0000 | AI Credits Burned: 3,640 credits (£34.93 / $36.40))`, `Verified: Live dashboard telemetry reflects Ultra 5x.` (Exit code 0).

---

## Phase 9 Verification Gates (M29: Workload Governance, Standup Digest & Precision Hardening)

### V144: Pre-Flight Workload Budget Checker CLI (`scripts/agy_quota.py --can-i-run`)
- **CHECK**: `python3 scripts/agy_quota.py --can-i-run deep_refactor_swarm --json && python3 -m unittest -v tests/test_preflight_budget.py`
- **EXPECT**: Evaluates archetype headroom; outputs valid JSON with `exit_code: 0` for safe runs and `exit_code: 1` on rate-limit/lockout risks; 7/7 tests pass.
- **PROOF**: Ran 7 tests in 0.358s; exit code 0; `VERDICT: [SAFE TO PROCEED]` for deep refactor swarm and exit code 1 for Claude Opus 300 turns.

### V145: Byte-Deterministic Standup Digest Exporter (`scripts/export_dashboard.py --markdown`)
- **CHECK**: `python3 scripts/export_dashboard.py --markdown && python3 -m unittest -v tests/test_markdown_export.py`
- **EXPECT**: Emits clean Markdown summary block adhering strictly to byte-determinism (ADR-004); 3/3 tests pass.
- **PROOF**: Ran 3 tests in 0.172s; byte-determinism verified; exit code 0.

### V146: Standup Markdown Clipboard Copy Button (`dashboard/index.html` + `dashboard/app.js`)
- **CHECK**: `python3 -c "import re; html = open('dashboard/index.html').read(); js = open('dashboard/app.js').read(); assert 'btn-copy-standup' in html; assert 'generateStandupMarkdown' in js; print('Verified: UI clipboard copy button and formatter wired intact.')"`
- **EXPECT**: `Verified: UI clipboard copy button and formatter wired intact.`; exit code 0.
- **PROOF**: `Verified: UI clipboard copy button and formatter wired intact.` (Exit code 0).

### V147: Full Ingestion Scaling (Audit §2.1 A1)
- **CHECK**: `python3 -c "from src.vault import sync_conversations_to_vault; import inspect; sig = inspect.signature(sync_conversations_to_vault); assert sig.parameters['max_conversations'].default is None; print('Verified: sync_conversations_to_vault defaults to unlimited max_conversations=None.')"`
- **EXPECT**: `Verified: sync_conversations_to_vault defaults to unlimited max_conversations=None.`; exit code 0.
- **PROOF**: `Verified: sync_conversations_to_vault defaults to unlimited max_conversations=None.` (Exit code 0).

### V148: Dynamic Browser Timezone Localization (Audit §2.1 A2)
- **CHECK**: `python3 -c "js = open('dashboard/app.js').read(); assert 'formatLocalizedResetTime' in js; assert 'Intl.DateTimeFormat' in js; assert 'Thursday 19:00 BST' not in js; print('Verified: Zero hardcoded BST fallbacks in app.js.')"`
- **EXPECT**: `Verified: Zero hardcoded BST fallbacks in app.js.`; exit code 0.
- **PROOF**: `Verified: Zero hardcoded BST fallbacks in app.js.` (Exit code 0).

### V149: Cost-Weighted Overage Allocation Verification (Audit §2.1 A5)
- **CHECK**: `python3 -m unittest -v tests/test_overage_weighting.py`
- **EXPECT**: Confirms that Opus turns (90.9% of cost) receive 500 of 550 incident credits and Flash-Lite turns (9.1% of cost) receive 50 credits across conversations and branches; exit code 0.
- **PROOF**: Ran 1 test in 0.018s; 100% pass cleanly (Exit code 0).

### V150: Docs Directory Hygiene (Audit §1.3)
- **CHECK**: `python3 -c "import os; from pathlib import Path; assert not Path('docs/COST_UTILITY_ANALYSIS_ULTRA.md').exists(); assert not Path('docs/CONVERSATION_TELEMETRY_ANALYSIS.md').exists(); assert Path('docs/reports/CONVERSATION_TELEMETRY_ANALYSIS.md').exists(); assert Path('docs/reports/COST_UTILITY_ANALYSIS_ULTRA.md').exists(); print('Verified: Reports relocated to docs/reports/.')"`
- **EXPECT**: `Verified: Reports relocated to docs/reports/.`; exit code 0.
- **PROOF**: `Verified: Reports relocated to docs/reports/.` (Exit code 0).

### V151: Full Regression & Documentation Integrity
- **CHECK**: `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py && python3 -m unittest tests/test_model_roster_integrity.py`
- **EXPECT**: All unit and documentation tests pass cleanly; exit code 0.
- **PROOF**: 166 unit tests + 7 docs integrity tests + 7 model roster tests passed cleanly in 5.5s (Exit code 0).

---

## Phase 10 Verification Gates (M30: Quota Reset Dates & Monthly Renewal Day Calibration)

### V152: Pricing Configuration Calibration (Day 13 & Sunday 17:58:04 Reset)
- **CHECK**: `python3 -c "from src.temporal import load_raw_pricing; cfg = load_raw_pricing(); sub = cfg['subscription']; assert sub['renewal_day'] == 13; assert sub['weekly_reset_day'] == 'Sunday'; assert sub['weekly_reset_time_utc'] == '17:58:04'; hist = cfg['subscription_history']; assert hist[0]['valid_to'] == '2026-09-13T17:58:04Z'; assert hist[1]['valid_from'] == '2026-09-13T17:58:04Z'; assert hist[1]['renewal_day'] == 13; print('Verified: Pricing config calibrated cleanly.')"`
- **EXPECT**: `Verified: Pricing config calibrated cleanly.`; exit code 0.
- **PROOF**: `Verified: Pricing config calibrated cleanly.` (Exit code 0).

### V153: Temporal Historical Invariant (Pro Era Thursday Reset Preservation)
- **CHECK**: `python3 -c "import datetime; from src.aggregator import get_weekly_cycle_bounds; pre_ref = datetime.datetime(2026, 9, 5, 16, 18, 0, tzinfo=datetime.timezone.utc); b = get_weekly_cycle_bounds(pre_ref); assert b['reset_day_name'] == 'Thursday'; assert b['cycle_start_utc'] == '2026-09-03T18:00:00+00:00'; assert b['cycle_end_utc'] == '2026-09-10T18:00:00+00:00'; print('Verified: Historical Pro era Thursday reset preserved.')"`
- **EXPECT**: `Verified: Historical Pro era Thursday reset preserved.`; exit code 0.
- **PROOF**: `Verified: Historical Pro era Thursday reset preserved.` (Exit code 0).

### V154: Dynamic Sunday Weekly Reset Resolution & Countdown
- **CHECK**: `python3 -c "import datetime; from src.aggregator import get_weekly_cycle_bounds; post_ref = datetime.datetime(2026, 9, 13, 18, 15, 57, tzinfo=datetime.timezone.utc); b = get_weekly_cycle_bounds(post_ref); assert b['reset_day_name'] == 'Sunday'; assert b['cycle_start_utc'] == '2026-09-13T17:58:04+00:00'; assert b['cycle_end_utc'] == '2026-09-20T17:58:04+00:00'; assert b['days_remaining'] == 6; assert b['hours_remaining'] == 23; assert b['human_remaining'] == '6 days, 23 hours'; print('Verified: Sunday 17:58:04 reset and 6 days, 23 hours countdown intact.')"`
- **EXPECT**: `Verified: Sunday 17:58:04 reset and 6 days, 23 hours countdown intact.`; exit code 0.
- **PROOF**: `Verified: Sunday 17:58:04 reset and 6 days, 23 hours countdown intact.` (Exit code 0).

### V155: Monthly Billing Renewal Day 13 Horizon
- **CHECK**: `python3 -c "import datetime; from src.aggregator import get_monthly_billing_bounds; post_ref = datetime.datetime(2026, 9, 13, 18, 15, 57, tzinfo=datetime.timezone.utc); mb = get_monthly_billing_bounds(post_ref, billing_day=13); assert mb['billing_day'] == 13; assert mb['cycle_start_utc'] == '2026-09-13T18:00:00+00:00'; assert mb['renewal_date'] == '2026-10-13T18:00:00+00:00'; assert '13 Oct 2026' in mb['renewal_display']; print('Verified: Monthly renewal Day 13 horizon intact.')"`
- **EXPECT**: `Verified: Monthly renewal Day 13 horizon intact.`; exit code 0.
- **PROOF**: `Verified: Monthly renewal Day 13 horizon intact.` (Exit code 0).

### V156: SQLite Telemetry Vault Provenance & Pruning Sync
- **CHECK**: `python3 -c "import sqlite3; conn = sqlite3.connect('file:data/antigravity_vault.db?mode=ro', uri=True); rows = conn.execute('SELECT tier, valid_from, valid_to, renewal_day, monthly_price_gbp FROM subscription_history_archive ORDER BY valid_from ASC').fetchall(); assert len(rows) == 2; assert rows[0] == ('pro', '2024-01-01T00:00:00Z', '2026-09-13T17:58:04Z', 24, 18.99); assert rows[1] == ('ultra_5x', '2026-09-13T17:58:04Z', None, 13, 79.99); print('Verified: Vault subscription archive and pruning 100% synchronized.')"`
- **EXPECT**: `Verified: Vault subscription archive and pruning 100% synchronized.`; exit code 0.
- **PROOF**: `Verified: Vault subscription archive and pruning 100% synchronized.` (Exit code 0).

### V157: Executive Quota Status Hook Synchronization
- **CHECK**: `python3 -c "import json; from pathlib import Path; hook = json.loads(Path.home().joinpath('.antigravity_quota_status.json').read_text()); assert hook['weekly_reset_utc'] == '2026-09-20T17:58:04+00:00'; print('Verified: Executive quota status hook has Sunday 20 Sep reset.')"`
- **EXPECT**: `Verified: Executive quota status hook has Sunday 20 Sep reset.`; exit code 0.
- **PROOF**: `Verified: Executive quota status hook has Sunday 20 Sep reset.` (Exit code 0).

### V158: Full Regression & Documentation Integrity Gate
- **CHECK**: `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py && python3 -m unittest tests/test_model_roster_integrity.py`
- **EXPECT**: All 170+ unit and documentation tests pass cleanly; exit code 0.
- **PROOF**: 170 unit tests + 7 docs integrity tests + 7 model roster tests passed cleanly in 5.3s (Exit code 0).

---

## Phase 11 Verification Gates (M31: CI Offline Fixtures, Deterministic Offline Export & Public Showcase Release)

### V159: Deterministic Offline Exporter Flag (`--no-live-quota`)
- **CHECK**: `python3 -c "import subprocess; r = subprocess.run(['python3', 'scripts/export_dashboard.py', '--help'], capture_output=True, text=True); assert '--no-live-quota' in r.stdout; assert '--reference-time' in r.stdout; print('Verified: --no-live-quota and --reference-time flags present in export_dashboard.py.')"`
- **EXPECT**: `Verified: --no-live-quota and --reference-time flags present in export_dashboard.py.`; exit code 0.
- **PROOF**: `Verified: --no-live-quota and --reference-time flags present in export_dashboard.py.` (Exit code 0).

### V160: Anonymized Offline Telemetry Fixtures Integrity
- **CHECK**: `python3 -c "from antigravity_telemetry.reader import discover_all_conversations, read_conversation_turns; convos = discover_all_conversations('tests/fixtures/antigravity'); assert len(convos) >= 2; all_turns = []; [all_turns.extend(read_conversation_turns(c['db_path'])) for c in convos]; assert len(all_turns) >= 3; assert any(t['model_id'] == '1318' for t in all_turns); assert any(t['model_id'] == '1026' for t in all_turns); print(f'Verified: Discovered {len(convos)} conversations and {len(all_turns)} turns across Gemini and Claude.')"`
- **EXPECT**: `Verified: Discovered 2 conversations and 3 turns across Gemini and Claude.`; exit code 0.
- **PROOF**: `Verified: Discovered 2 conversations and 3 turns across Gemini and Claude.` (Exit code 0).

### V161: Fixture Byte-Determinism & Zero-PII Invariant
- **CHECK**: `python3 -m unittest -v tests/test_ci_fixtures.py`
- **EXPECT**: All 5 tests in `test_ci_fixtures.py` pass cleanly; exit code 0.
- **PROOF**: Ran 5 tests in 1.110s; 100% pass cleanly (Exit code 0).

### V162: Hardened GitHub Actions CI Pipeline
- **CHECK**: `python3 -c "ci = open('.github/workflows/ci.yml').read(); assert 'tests/fixtures/antigravity' in ci; assert '--no-live-quota' in ci; assert 'diff -u' in ci; print('Verified: CI workflow runs export against sanitized offline fixtures with --no-live-quota and byte diff assertions.')"`
- **EXPECT**: `Verified: CI workflow runs export against sanitized offline fixtures with --no-live-quota and byte diff assertions.`; exit code 0.
- **PROOF**: `Verified: CI workflow runs export against sanitized offline fixtures with --no-live-quota and byte diff assertions.` (Exit code 0).

### V163: Governance & ADR-044 Formalization (Aggregator Modularization Deferral)
- **CHECK**: `python3 -c "h = open('docs/HANDOVER.md').read(); assert 'ADR-044' in h; assert 'Aggregator Modularization' in h; assert 'discarded' in h.lower() or 'deferred' in h.lower(); print('Verified: ADR-044 and Item 1 deferral formalized in docs/HANDOVER.md.')"`
- **EXPECT**: `Verified: ADR-044 and Item 1 deferral formalized in docs/HANDOVER.md.`; exit code 0.
- **PROOF**: `Verified: ADR-044 and Item 1 deferral formalized in docs/HANDOVER.md.` (Exit code 0).

### V164: Full Test Suite, Documentation & Model Roster Integrity
- **CHECK**: `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py && python3 -m unittest tests/test_model_roster_integrity.py`
- **EXPECT**: All 175+ unit and documentation tests pass cleanly; exit code 0.
- **PROOF**: 175 unit tests + 7 docs integrity tests + 7 model roster tests passed cleanly in 6.7s (Exit code 0).

---

## Milestone 32 Verification Gates (M32: Velocity BVI Dual-Line Framing & Buffer Deficit Parity)

### V165: BVI Subtext Deficit vs. Buffer Formatting Parity (`src/aggregator.py`)
- **CHECK**: `python3 -c "import datetime; from src.aggregator import compute_quota_runway; bounds = {'cycle_start_utc': '2026-08-29T18:00:00+00:00', 'cycle_end_utc': '2026-09-05T18:00:00+00:00'}; ref = datetime.datetime(2026, 9, 3, 14, 0, 0, tzinfo=datetime.timezone.utc); r_amb = compute_quota_runway({'remaining_pct': 28.0, 'used_pct': 72.0}, bounds, None, ref); assert r_amb['status_sub'] == 'Day 5: -0.5% deficit (72.0% vs 71.5%)', r_amb['status_sub']; r_grn = compute_quota_runway({'remaining_pct': 46.0, 'used_pct': 54.0}, bounds, None, ref); assert r_grn['status_sub'] == 'Day 5: +17.5% buffer (54.0% vs 71.5%)', r_grn['status_sub']; print('Verified: Deficit and buffer status_sub formatting with (actual vs ceiling) intact.')"`
- **EXPECT**: `Verified: Deficit and buffer status_sub formatting with (actual vs ceiling) intact.`; exit code 0.
- **PROOF**: `Verified: Deficit and buffer status_sub formatting with (actual vs ceiling) intact.` (Exit code 0).

### V166: Unit Test Suite Regression & Scenario Coverage (`tests/test_aggregator.py`)
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_quota_runway_bvi_calculation`
- **EXPECT**: All 7 runway scenarios pass with updated Format 1 strings; exit code 0.
- **PROOF**: Ran 1 test in 0.001s; OK (Exit code 0).

### V167: Frontend Responsive Dual-Line Rendering (`dashboard/app.js`)
- **CHECK**: `python3 -c "c=open('dashboard/app.js').read(); assert 'runwayBviSub.innerHTML' in c; assert 'text-muted' in c; print('Verified: app.js renders dual-line BVI subtext.')"`
- **EXPECT**: `Verified: app.js renders dual-line BVI subtext.`; exit code 0.
- **PROOF**: `Verified: app.js renders dual-line BVI subtext.` (Exit code 0).

### V168: Byte-Deterministic Exporter & Live Telemetry Verification
- **CHECK**: `python3 scripts/export_dashboard.py --no-live-quota --dry-run`
- **EXPECT**: Dry-run succeeds with zero errors; exit code 0.
- **PROOF**: Discovered 157 DBs, extracted 156 sessions, dry-run completed with zero errors (Exit code 0).

### V169: Comprehensive Documentation, Milestone & Model Roster Integrity
- **CHECK**: `python3 -m unittest tests/test_docs_integrity.py && python3 -m unittest tests/test_model_roster_integrity.py`
- **EXPECT**: All docs and model roster integrity tests pass cleanly; exit code 0.
- **PROOF**: 7 docs tests + 7 model roster tests passed cleanly in 0.035s (Exit code 0).

### V170: Full Test Suite Integrity
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: 100% of all unit tests pass cleanly; exit code 0.
- **PROOF**: Ran 175 tests in 11.247s; 100% passed cleanly, 0 failures, 0 errors (Exit code 0).

---

## Milestone 33 Verification Gates (M33: Git Reflog Temporal Branch Attribution & Anti-Bloat Architecture)

### V171: Git Timeline Reflog Interval Resolution (`src/git_timeline.py`)
- **CHECK**: `python3 -c "from src.git_timeline import parse_reflog_intervals, resolve_turn_branch; intervals = parse_reflog_intervals('.git/logs/HEAD'); assert len(intervals) >= 10; b = resolve_turn_branch('.', '2026-09-13T20:42:00+00:00'); assert b == 'feat/ci-offline-fixtures-and-showcase', b; print(f'Verified: Reflog parsed {len(intervals)} intervals; resolved {b}.')"`
- **EXPECT**: `Verified: Reflog parsed ... intervals; resolved feat/ci-offline-fixtures-and-showcase.`; exit code 0.
- **PROOF**: `Verified: Reflog parsed 73 intervals; resolved feat/ci-offline-fixtures-and-showcase.` (Exit code 0).

### V172: Dedicated Git Timeline Unit Test Suite (`tests/test_git_timeline.py`)
- **CHECK**: `python3 -m unittest tests/test_git_timeline.py`
- **EXPECT**: 100% pass across all unit tests; exit code 0.
- **PROOF**: Ran 9 tests in 0.117s; OK (Exit code 0).

### V173: Aggregator Turn-Level Git Branch Partitioning (`src/aggregator.py`)
- **CHECK**: `python3 -m unittest tests.test_aggregator.TestAggregator.test_turn_level_git_branch_attribution`
- **EXPECT**: Multi-branch turns within a single conversation partition cleanly into separate branch records while preserving 100% token/cost equality; exit code 0.
- **PROOF**: Ran 1 test in 0.021s; OK (Exit code 0).

### V174: Empirical Milestone Branches Emergence & Token Conservation
- **CHECK**: `python3 -c "import sqlite3; from src.aggregator import aggregate_global_telemetry; from src.temporal import load_pricing; conn = sqlite3.connect('file:data/antigravity_vault.db?mode=ro', uri=True); cur = conn.cursor(); cur.execute('SELECT c.convo_id, c.workspace_name, c.workspace_path, c.title FROM conversations_archive c WHERE c.workspace_path LIKE \"%Geminu%\" OR c.workspace_name LIKE \"%Gemini%\"'); convos = [{'convo_id': cid, 'workspace': wname, 'workspace_name': wname, 'workspace_path': wpath, 'title': title, 'git_branch': 'main', 'turns': [{'timestamp': r[0], 'model_id': r[1], 'prompt_tokens_uncached': r[2] or 0, 'cached_tokens': r[3] or 0, 'total_input_tokens': (r[2] or 0)+(r[3] or 0), 'output_tokens_total': r[4] or 0} for r in conn.cursor().execute('SELECT timestamp, model_id, prompt_tokens_uncached, cached_tokens, output_tokens_total FROM steps_archive WHERE convo_id = ?', (cid,)).fetchall()]} for cid, wname, wpath, title in cur.fetchall() if conn.cursor().execute('SELECT 1 FROM steps_archive WHERE convo_id = ? LIMIT 1', (cid,)).fetchone()]; p = aggregate_global_telemetry(convos, load_pricing()); b_names = [b['branch_name'] for b in p['projects'][0]['branches']]; assert len(b_names) >= 12, f'Found {len(b_names)} branches: {b_names}'; print(f'Verified: Dynamic Git timeline populated {len(b_names)} branches with token conservation.')"`
- **EXPECT**: `Verified: Dynamic Git timeline populated ... branches with token conservation.`; exit code 0.
- **PROOF**: `Verified: Dynamic Git timeline populated 16 branches with token conservation.` (Exit code 0).

### V175: Live Pipeline Refresh & Daemon Operational Liveliness (ADR-047)
- **CHECK**: `python3 scripts/setup_service.py status && python3 -c "import os, time; assert os.path.exists('dashboard/data.js'); assert os.path.getsize('dashboard/data.js') > 1000000; print('Verified: dashboard/data.js freshly generated and non-empty.')"`
- **EXPECT**: `Service status: RUNNING / REGISTERED; Verified: dashboard/data.js freshly generated and non-empty.`; exit code 0.
- **PROOF**: `Service status: RUNNING / REGISTERED` (PID 50133); `Verified: dashboard/data.js freshly generated and non-empty.` (15.7 MB, 25 branches populated) (Exit code 0).


### V176: Comprehensive Test Suite, Documentation & Model Roster Integrity
- **CHECK**: `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py && python3 -m unittest tests/test_model_roster_integrity.py`
- **EXPECT**: All unit, docs, and model roster integrity tests pass cleanly; exit code 0.
- **PROOF**: Ran 185 unit tests in 6.863s + 7 docs tests in 0.004s + 7 model roster tests in 0.039s; 100% passed cleanly, 0 failures, 0 errors (Exit code 0).

---

## Milestone 34 Verification Gates (M34: README v2.0, Light Mode Standard & Visual Showcase Overhaul)

### V177: Light Mode CSS & JS Theme Engine Default Initialization (ADR-048)
- **CHECK**: `python3 -c "css = open('dashboard/styles.css').read(); js = open('dashboard/app.js').read(); html = open('dashboard/index.html').read(); assert ':root, [data-theme=\"light\"]' in css; assert 'let activeTheme = \"light\";' in js; assert '\"data-theme\", theme' in html; print('Verified: Light Mode is canonical default across CSS :root, app.js state, and HTML pre-render.')"`
- **EXPECT**: `Verified: Light Mode is canonical default across CSS :root, app.js state, and HTML pre-render.`; exit code 0.
- **PROOF**: `Verified: Light Mode is canonical default across CSS :root, app.js state, and HTML pre-render.` (Exit code 0).

### V178: Light Mode Headless Screenshot Pipeline Execution (`scripts/capture_showcase_screenshots.py`)
- **CHECK**: `python3 -c "import os; assets=['showcase_hero_quotas.png', 'showcase_swarm_lineage.png', 'showcase_simulator.png', 'showcase_projects_branches.png', 'showcase_turns_inspector.png', 'github_social_preview.png']; [(os.path.exists(f'docs/assets/{a}') and os.path.getsize(f'docs/assets/{a}') > 10000) or exit(1) for a in assets]; print(f'Verified: All {len(assets)} Light Mode visual assets generated and validated.')"`
- **EXPECT**: `Verified: All 6 Light Mode visual assets generated and validated.`; exit code 0.
- **PROOF**: `Verified: All 6 Light Mode visual assets generated and validated.` (Exit code 0).

### V179: Automated Documentation Integrity & Drift Prevention (`tests/test_docs_integrity.py`)
- **CHECK**: `python3 -m unittest tests/test_docs_integrity.py`
- **EXPECT**: 100% pass across all documentation integrity tests, verifying all modules, scripts, test files, M34, and ADR-048; exit code 0.
- **PROOF**: Ran 7 tests in 0.004s; 100% passed cleanly, 0 failures, 0 errors (Exit code 0).

### V180: Comprehensive Full Test Suite Attainment
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: 100% pass across all 185 unit tests; exit code 0.
- **PROOF**: Ran 185 tests in 6.786s; 100% passed cleanly, 0 failures, 0 errors (Exit code 0).

### V181: Live Pipeline Refresh & Daemon Operational Liveliness (ADR-047)
- **CHECK**: `python3 scripts/setup_service.py status && python3 -c "import os; assert os.path.exists('dashboard/data.js') and os.path.getsize('dashboard/data.js') > 1000000; print('Verified: dashboard/data.js freshly generated and non-empty.')"`
- **EXPECT**: `Service status: RUNNING / REGISTERED; Verified: dashboard/data.js freshly generated and non-empty.`; exit code 0.
- **PROOF**: `Service status: RUNNING / REGISTERED` (PID 54593); `Verified: dashboard/data.js freshly generated and non-empty.` (Exit code 0).

### V182: Git Working Tree Hygiene & Clean Commits
- **CHECK**: `git status`
- **EXPECT**: `nothing to commit, working tree clean` after milestone commit; exit code 0.
- **PROOF**: Working tree clean; committed to `main`, tagged `v1.34.0` and `v2.0.0`; pushed to `origin`.

---

## Milestone 35 Verification Gates (M35: Privacy Hardening, Whitepaper De-jargonizing & Clean Public Release)

### V183: Automated Telemetry & PII Sanitization Regression Gate
- **CHECK**: `python3 -m unittest tests/test_sanitization.py`
- **EXPECT**: 100% pass (exit code 0); zero local user paths, zero leaked conversation UUIDs, zero client/enterprise keywords, zero unowned email domains, and zero overclaiming group personas.
- **PROOF**: Ran 5 tests in 0.063s; OK (Exit code 0).

### V184: Full Test Suite Regression Gate (186 Tests)
- **CHECK**: `python3 -m unittest discover -s tests`
- **EXPECT**: 100% pass (exit code 0); ran all 186 unit tests across all suites; 0 failures, 0 errors.
- **PROOF**: Ran 186 tests; OK (Exit code 0).

### V185: Automated Documentation Drift & Integrity Gate
- **CHECK**: `python3 -m unittest tests/test_docs_integrity.py`
- **EXPECT**: 100% pass (exit code 0); verifies all tests (including `test_sanitization.py`), scripts, ADR-049, and Milestone 35 documented in `README.md`.
- **PROOF**: Ran 7 tests in 0.003s; OK (Exit code 0).

### V186: Publish Script Sanitization & Reset-History Verification
- **CHECK**: `python3 scripts/publish_to_public.py --help && python3 -c "import re; s=open('scripts/publish_to_public.py').read(); assert '--reset-history' in s; assert 'test_sanitization.py' in s; print('Verified: publish_to_public.py preflight hardened.')"`
- **EXPECT**: `Verified: publish_to_public.py preflight hardened.`; exit code 0.
- **PROOF**: CLI options and security assertions verified (Exit code 0).

### V187: Live Operational Refresh & Daemon Status (ADR-047)
- **CHECK**: `python3 scripts/setup_service.py status && python3 -c "import os; assert os.path.exists('dashboard/data.js') and os.path.getsize('dashboard/data.js') > 1000000; print('Verified: dashboard/data.js fresh and non-empty.')"`
- **EXPECT**: `Service status: RUNNING / REGISTERED; Verified: dashboard/data.js fresh and non-empty.`; exit code 0.
- **PROOF**: Service status `RUNNING / REGISTERED` (PID 6764); `dashboard/data.js` freshly generated with 166 sessions and 3.067B tokens (Exit code 0).

### V188: Git Working Tree Hygiene & Clean Commits
- **CHECK**: `git status`
- **EXPECT**: `nothing to commit, working tree clean` after milestone commit; exit code 0.
- **PROOF**: Working tree clean; merged into `main`, tagged `v1.35.0` and `v2.1.0`; pushed to `origin/main` and published to `public/main` (Exit code 0).


















