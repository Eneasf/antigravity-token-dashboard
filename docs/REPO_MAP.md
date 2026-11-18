# Repository Map

Complete directory tree and file map for the Antigravity Token Consumption Dashboard codebase.

## Repository Structure

```
.
├── LICENSE                 # MIT License
├── CONTRIBUTING.md         # Contribution guidelines and invariants
├── SECURITY.md             # Vulnerability disclosure policy
├── CODE_OF_CONDUCT.md      # Contributor Covenant
├── AGENTS.md               # Canonical working agreement and git protocols
├── README.md               # Project documentation
├── VDONE.md                # Verifiable quality gates register
├── pyproject.toml          # Packaging metadata for antigravity-telemetry
├── .github/workflows/
│   └── e2e-nightly.yml     # Scheduled nightly Playwright suite
├── antigravity_telemetry/  # Standalone zero-dependency telemetry engine
│   ├── __init__.py         # Public API: read_all_turns(), discover_all_conversations()
│   ├── __main__.py         # CLI entrypoint (dump --json, models, conversations)
│   ├── parser.py           # Pure-Python protobuf wire-format decoder
│   ├── reader.py           # Read-only SQLite extractor with lock resilience
│   ├── models.json         # Canonical model census
│   └── README.md           # Package documentation
├── config/
│   ├── pricing.json        # Benchmark pricing matrix, plans, and promotions
│   ├── pricing.sample.json # Anonymized pricing template
│   └── com.antigravity.telemetry.watcher.plist.template # LaunchAgent template
├── data/
│   ├── exhaustion_ledger.sample.json   # Anonymized 429 exhaustion ledger template
│   └── quota_regime_ledger.sample.json # Anonymized quota regime ledger template
├── docs/
│   ├── README.md           # Documentation hub (Map of Content)
│   ├── SYSTEM_DESIGN.md    # Architecture, SQLite WAL ingestion & protobuf parsing
│   ├── TELEMETRY_SPEC.md   # Field schemas, wire types & turn taxonomy
│   ├── FINDINGS.md         # Runtime telemetry, quotas & billing whitepaper
│   ├── MODEL_BENCHMARKS.md # Reasoning & token consumption benchmark ledger
│   ├── COMPLIANCE_REPORT.md # Google ToS, GenAI policy & Fair Use audit
│   ├── DECISIONS.md        # Master Architecture Decision Record (ADR) registry
│   ├── BACKLOG.md          # Delete-on-close open work register (GADR-033)
│   ├── REVIEW_PLAYBOOK.md  # Multi-agent audit procedure
│   ├── ADR-082-discrete-5h-quota-reset.md # Discrete 5h quota reset epochs
│   ├── STUDY_SUMMARY_PRESERVATION_VS_CONTEXT.md # Summary preservation vs context decay
│   ├── STUDY_PROPOSAL_CONTEXT_TRUNCATION.md # Context truncation research proposal
│   ├── DATA_DICTIONARY.md  # Vault schema catalog, semantic views & SQL recipes
│   ├── AUDIT_*.md, REVIEW_*.md # Periodic architectural and UX audit reports
│   ├── archive/            # Archived legacy handover & milestone index
│   ├── reports/            # Post-mortems, exhaustion audits & economic analyses
│   └── milestones/         # Historical milestone slice records
├── src/
│   ├── proto_parser.py     # Protobuf wire-format decoder
│   ├── telemetry_reader.py # Read-only SQLite turn extractor
│   ├── log_reader.py       # 429 RESOURCE_EXHAUSTED log & ledger parser
│   ├── log_archiver.py     # Raw event archiver into SQLite vault
│   ├── quota_client.py     # Connect-RPC desktop quota client
│   ├── aggregator.py       # Top-level metrics, quota & credit orchestrator
│   ├── aggregator_pricing.py     # Model rate lookups, credit math & turn costs
│   ├── aggregator_cycles.py      # Weekly/monthly bounds, Bayesian velocity & runway
│   ├── aggregator_windows.py     # 5h/168h rolling telemetry & recovery timelines
│   ├── aggregator_coaching.py    # Simulator presets, KV cache coaching & ticker math
│   ├── aggregator_attribution.py # Workspace/branch mapping & 429 turn attribution
│   ├── aggregator_quotas.py      # Dual-track quota silos & credit reconciliation
│   ├── vault.py            # SQLite telemetry vault & step lineage store
│   ├── vault_schema.py     # Canonical vault schema & analytical views
│   ├── temporal.py         # Timestamp-aware rate cards & plan resolver
│   ├── simulator.py        # What-if workload simulator & stress planner
│   ├── swarm.py            # Subagent lineage DAG & multi-agent economics
│   ├── tool_analytics.py   # Tool frequency, bypass ratios & skill metrics
│   ├── weekly_trends.py    # Weekly cycle aggregation & overage trendlines
│   ├── git_timeline.py     # Git reflog checkout interval & branch resolver
│   ├── horizon_analytics.py # Multi-horizon progression & diurnal latency profiles
│   └── quota_regime.py     # Quota regime drift detector & reset bonus auditor
├── scripts/
│   ├── export_dashboard.py # Deterministic HTML/JS exporter & status hook writer
│   ├── watch_telemetry.py  # Debounced near real-time watcher daemon
│   ├── setup_service.py    # macOS LaunchAgent lifecycle manager
│   ├── build_menubar.py    # Compiles & packages dist/AntigravityBar.app
│   ├── setup_menubar.py    # AntigravityBar lifecycle manager
│   ├── agy_status.py       # Fast CLI status hook inspector
│   ├── agy_quota.py        # Live desktop Connect-RPC quota CLI
│   ├── quota_regression.py # Empirical rate-card regression harness
│   ├── ingest_statement.py # Credit statement parser & ledger reconciler
│   ├── configure_plan.py   # Plan profile calibration CLI
│   ├── capture_showcase_screenshots.py # Headless Light Mode screenshot capture
│   ├── setup_github_guardrails.py      # Branch protection & repo guardrails
│   ├── build_demo_showcase.py          # Zero-PII synthetic demo generator
│   ├── build_ci_fixtures.py            # Offline anonymized fixture builder
│   ├── bench_vault_performance.py      # Vault query KPI benchmark harness
│   ├── quota_history.py    # Macro statement & micro 429 history CLI
│   ├── ops_check.py        # Live pipeline operational health check
│   └── publish_to_public.py # Public showcase release publisher
├── dashboard/
│   ├── index.html          # Responsive analytics UI (?demo=1 showcase)
│   ├── styles.css          # CSS tokens (Light default), themes & grids
│   ├── meta.js             # Fast hash-gating & micro-polling payload
│   ├── turns.js            # Lazy-loaded turns projection payload
│   └── js/                 # Plain sequential browser scripts (no bundler)
│       ├── core-utils.js   # Formatters, tooltips & DOM helpers
│       ├── core.js         # State, theme, routing & bootOnce/render split
│       ├── now-burst.js    # Live ticker, burst trajectory & active swarms
│       ├── now.js          # Executive cockpit, model matrix & gauges
│       ├── sessions-filters.js # Session filters, search & pagination
│       ├── sessions-tree.js    # Parent-child accordion tree & rollups
│       ├── sessions.js         # Session table & context safety strip
│       ├── sessions-turns.js   # Slide-over turn inspector drawer
│       ├── projects.js     # Workspace cards & branch trees
│       ├── skills.js       # Skills inventory & tool analytics view
│       ├── swarms.js       # Swarm timeline, DAG & tier economics
│       ├── billing.js      # Cycle ledger, billing KPIs & trendlines
│       ├── plan-rates.js   # Model taxonomy & temporal rate table
│       ├── plan-manager.js # Plan profile modal & custom overrides
│       └── simulator.js    # Interactive workload simulator UI
├── e2e/
│   ├── a11y.spec.js            # Playwright axe-core WCAG AA & keyboard audit
│   ├── lazy-turns.spec.js      # Lazy turn drawer E2E spec
│   ├── mobile-pass.spec.js     # Mobile viewport & table scroll E2E spec
│   └── tree-and-swarms.spec.js # Sessions tree & Swarms subview E2E spec
└── tests/
    ├── test_proto_parser.py              # Varint & wire field decoding
    ├── test_log_reader.py                # 429 log regex & ledger parsing
    ├── test_log_archiver.py              # Log archiver & vault writes
    ├── test_aggregator.py                # Core aggregation & cost math
    ├── test_aggregator_modular.py        # Aggregator submodule & re-export parity
    ├── test_export_dashboard.py          # Deterministic export & CLI flags
    ├── test_watch_telemetry.py           # Watcher debounce & lifecycle
    ├── test_quota_client.py              # Connect-RPC client & fallbacks
    ├── test_vault.py                     # Vault storage, blobs & recovery
    ├── test_vault_schema.py              # Vault schema, views & migrations
    ├── test_temporal.py                  # Temporal rate intervals & promotions
    ├── test_simulator.py                 # Workload simulator & plan comparison
    ├── test_swarm.py                     # Swarm lineage & tier routing
    ├── test_agent_telemetry.py           # Agent persona wire decoding & backfill
    ├── test_tool_analytics.py            # Tool frequency & bypass metrics
    ├── test_quota_attribution.py         # 5h attribution & cache coaching
    ├── test_weekly_trends.py             # Weekly cycles & overage trendlines
    ├── test_ingest_statement.py          # Credit statement ingestion
    ├── test_agy_status.py                # Status hook & agy_status CLI
    ├── test_quota_status_enrichment.py   # Enriched executive status schema
    ├── test_menubar_packaging.py         # AntigravityBar build & lifecycle
    ├── test_antigravity_telemetry_pkg.py # Standalone package API & zero-dep check
    ├── test_model_roster_integrity.py    # Canonical model roster drift gate
    ├── test_preflight_budget.py          # --can-i-run budget gate CLI
    ├── test_markdown_export.py           # --markdown standup digest determinism
    ├── test_overage_weighting.py         # Spend-proportional overage attribution
    ├── test_ci_fixtures.py               # Offline fixture census & determinism
    ├── test_git_timeline.py              # Git reflog temporal branch attribution
    ├── test_sanitization.py              # PII & path sanitization gates
    ├── test_demo_showcase.py             # Synthetic showcase schema & zero-PII
    ├── e2e_bridge/
    │   └── test_playwright_e2e.py        # Isolated Playwright Python bridge
    ├── test_docs_integrity.py            # Repo map, ADR & stale-number gates
    ├── test_vdone_gates.py               # VDONE CHECK runner & purity guard
    ├── test_export_lock.py               # Advisory flock & atomic staging
    ├── test_labels_and_defaults.py       # Dynamic labels & light-mode defaults
    ├── test_dashboard_boot.py            # bootOnce/render & event delegation
    ├── test_plain_header_and_now_copy.py # Compact header & plain-English copy
    ├── test_truncation_thresholds.py     # Per-model truncation thresholds
    ├── test_lazy_turns.py                # Minified data.js & lazy turns.js
    ├── test_a11y_baseline.py             # ARIA roles, captions & formatters
    ├── test_suite_hygiene.py             # Zero stdout/stderr test leakage
    ├── test_mobile_pass_and_scroll_wrappers.py # Mobile CSS & scroll wrappers
    ├── test_status_isolation.py          # Hermetic status hook test isolation
    ├── test_status_self_heal.py          # Foreign status detection & self-heal
    ├── test_vault_mtime_gating.py        # Vault mtime gating & force scan
    ├── test_subprocess_timeouts.py       # Subprocess timeout guards
    ├── test_atomic_writes.py             # Atomic temp staging & cleanup
    ├── test_quota_regression.py          # Rate-card regression convergence
    ├── test_setup_github_guardrails.py   # GitHub guardrails dry-run
    ├── test_two_tier_exporter.py         # Fast-tier ticker & epoch badge
    ├── test_incremental_cache.py         # SQLite/memory incremental export cache
    ├── test_quota_history.py             # Quota history CLI & report
    ├── test_dashboard_executive_cockpit.py # Executive cockpit & menu bar parity
    ├── test_multiagent_degradation.py    # Multi-agent cascade degradation
    ├── test_pricing.py                   # Ultra 5x capacity & frontier pricing
    ├── test_aggregator_coaching.py       # Intra-family KV cache coaching
    ├── test_telemetry_reader.py          # Wire TTFT & turn latency decoding
    ├── test_horizon_analytics.py         # Multi-horizon & diurnal analytics
    ├── test_quota_reset_bonus.py         # Unscheduled quota reset bonus ledger
    ├── test_quota_regime.py              # Quota regime drift & CLI confirmation
    ├── test_quota_fallback_and_locks.py  # Vault quota fallback, status lock & cold-start fast tier
    └── test_public_release_hygiene.py    # Public staging filter & audit-doc PII gate
```
