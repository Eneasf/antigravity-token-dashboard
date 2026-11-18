# Antigravity Documentation Hub & Map of Content (MoC)

Welcome to the central documentation registry for the **Google Antigravity Token Consumption Dashboard & Telemetry Engine**. This Map of Content organizes all living architecture specifications, empirical research, diagnostic post-mortems, architectural decision records (ADRs), and compliance reports into a navigable index.

---

## 1. Living System Specifications

These documents define the canonical operational state, schemas, and runtime contracts of the telemetry engine and analytics dashboard.

| Document | Purpose & Scope | Status |
| :--- | :--- | :---: |
| [**SYSTEM_DESIGN.md**](SYSTEM_DESIGN.md) | High-level system architecture, Electron IPC, SQLite WAL ingestion pipelines, and decoupled two-tier telemetry architecture. | ![Status: Living](https://img.shields.io/badge/Status-Living-brightgreen) |
| [**TELEMETRY_SPEC.md**](TELEMETRY_SPEC.md) | Wire protocol specifications, protobuf field schemas (Fields 1–30), turn taxonomy, and canonical model mappings. | ![Status: Living](https://img.shields.io/badge/Status-Living-brightgreen) |
| [**DATA_DICTIONARY.md**](DATA_DICTIONARY.md) | Comprehensive SQLite vault catalog, table grains, analytical views (`v_active_sessions`, `v_turns`), and reference tables (ADR-089/ADR-090). | ![Status: Living](https://img.shields.io/badge/Status-Living-brightgreen) |
| [**REPO_MAP.md**](REPO_MAP.md) | Ground-truth structural inventory of all files, modules, scripts, and test suites across the repository. | ![Status: Living](https://img.shields.io/badge/Status-Living-brightgreen) |

---

## 2. Authoritative Research & Empirical Studies

Ground-truth empirical whitepapers and benchmark ledgers documenting real-world tokenomics, quota ceilings, reasoning token profiles, and context compaction mechanics.

| Document | Key Discoveries & Topics | Status |
| :--- | :--- | :---: |
| [**FINDINGS.md**](FINDINGS.md) | Authoritative whitepaper on runtime telemetry, Dual-Track silos (Track 1 Gemini vs Track 2 Claude/GPT), Ultra 5x tier capacities, billing mechanics, and swarm economics. | ![Status: Living](https://img.shields.io/badge/Status-Living-brightgreen) |
| [**MODEL_BENCHMARKS.md**](MODEL_BENCHMARKS.md) | Multi-model benchmark ledger across 32 models, measuring reasoning effort ratios, thinking tokens, verbosity, and context cache hit rates. | ![Status: Living](https://img.shields.io/badge/Status-Living-brightgreen) |
| [**STUDY_SUMMARY_PRESERVATION_VS_CONTEXT.md**](STUDY_SUMMARY_PRESERVATION_VS_CONTEXT.md) | Empirical analysis across 268 compactions proving the 10-request FIFO prompt queue, fixed ~7,000 char budget, and Protobuf Field 30 compaction dynamics. | ![Status: Completed](https://img.shields.io/badge/Status-Completed-blue) |
| [**STUDY_PROPOSAL_CONTEXT_TRUNCATION.md**](STUDY_PROPOSAL_CONTEXT_TRUNCATION.md) | Initial exploratory research proposal for Gemini truncation triggers; superseded by the full compaction study. | ![Status: Superseded](https://img.shields.io/badge/Status-Superseded-orange) |

---

## 3. Investigation Reports & Economic Analyses (`docs/reports/`)

Diagnostic post-mortems, historical quota exhaustion audits, and financial utility evaluations.

| Document | Domain & Context | Status |
| :--- | :--- | :---: |
| [**reports/COST_UTILITY_ANALYSIS_ULTRA.md**](reports/COST_UTILITY_ANALYSIS_ULTRA.md) | Mathematical break-even analysis driving the upgrade from Pro (£18.99/mo) to Google AI Ultra 5x (£79.99/mo), evaluating AI credit reload avoidance. | ![Status: Adopted](https://img.shields.io/badge/Status-Adopted-success) |
| [**reports/WEEKLY_QUOTA_EXHAUSTION_REPORT.md**](reports/WEEKLY_QUOTA_EXHAUSTION_REPORT.md) | Historical empirical study documenting the first recorded 5h micro-burst ($20.00) and weekly ($129.00) exhaustion cycle under Google One AI Premium (Pro). | ![Status: Historical](https://img.shields.io/badge/Status-Historical%20(Pro)-lightgrey) |
| [**reports/SESSION_CONTEXT_DEGRADATION_AND_FRONTEND_POSTMORTEM.md**](reports/SESSION_CONTEXT_DEGRADATION_AND_FRONTEND_POSTMORTEM.md) | Post-mortem analyzing DOM flexbox collapse under extreme context depth, cognitive attention decay, and diagnostic remediation protocols. | ![Status: Resolved](https://img.shields.io/badge/Status-Resolved-blue) |
| [**reports/CONVERSATION_TELEMETRY_ANALYSIS.md**](reports/CONVERSATION_TELEMETRY_ANALYSIS.md) | Telemetry profile of turn distributions, tool call frequencies, and agent sub-task decomposition. | ![Status: Archived](https://img.shields.io/badge/Status-Archived-lightgrey) |

---

## 4. Architectural Decisions & Governance

Governance frameworks, compliance declarations, and the master architectural decision log.

| Document | Scope | Status |
| :--- | :--- | :---: |
| [**DECISIONS.md**](DECISIONS.md) | Master architectural decision registry (complete ADR catalog) paired with delete-on-close [`BACKLOG.md`](BACKLOG.md). | ![Status: Living](https://img.shields.io/badge/Status-Living-brightgreen) |
| [**ADR-082-discrete-5h-quota-reset.md**](ADR-082-discrete-5h-quota-reset.md) | Decision ratifying discrete 5-hour quota reset epochs from Connect-RPC `resetTime`, superseding the legacy rolling burst window model. | ![Status: Adopted](https://img.shields.io/badge/Status-Adopted-success) |
| [**COMPLIANCE_REPORT.md**](COMPLIANCE_REPORT.md) | Strict legal and policy evaluation covering Google Terms of Service, Generative AI Prohibited Uses, and Fair Use reverse engineering criteria. | ![Status: Compliant](https://img.shields.io/badge/Status-Compliant-brightgreen) |
| [**REVIEW_PLAYBOOK.md**](REVIEW_PLAYBOOK.md) | Operational audit guidelines (v2.1) enforcing multi-agent invariants, headless verification gates, and code review ceremonies. | ![Status: Living](https://img.shields.io/badge/Status-Living-brightgreen) |
| [**milestones/**](milestones/) | Historical records of all completed repository milestones from M01 through M90. | ![Status: Archive](https://img.shields.io/badge/Status-Archive-lightgrey) |

---

## 5. Architectural & Quality Audit Archive

Periodic adversarial fact-checks, repository audits, and ceremony logs conducted per `REVIEW_PLAYBOOK.md`.

| Document | Date | Scope | Status |
| :--- | :---: | :--- | :---: |
| [**AUDIT_2026-09-12_CODE_AND_UX.md**](AUDIT_2026-09-12_CODE_AND_UX.md) | 2026-09-12 | Comprehensive code quality, test coverage, and UX verification pass. | ![Status: Archived](https://img.shields.io/badge/Status-Archived-lightgrey) |
| [**AUDIT_2026-09-19_UI_CODE_AND_CEREMONY.md**](AUDIT_2026-09-19_UI_CODE_AND_CEREMONY.md) | 2026-09-19 | Frontend rendering, design system invariants, and multi-agent ceremony audit. | ![Status: Archived](https://img.shields.io/badge/Status-Archived-lightgrey) |
| [**AUDIT_2026-09-22_SYSTEM_DATA_AND_UX.md**](AUDIT_2026-09-22_SYSTEM_DATA_AND_UX.md) | 2026-09-22 | Telemetry data layer, protobuf parsing, and UI usability review. | ![Status: Archived](https://img.shields.io/badge/Status-Archived-lightgrey) |
| [**AUDIT_2026-09-24_TEST_ISOLATION.md**](AUDIT_2026-09-24_TEST_ISOLATION.md) | 2026-09-24 | Test suite filesystem isolation and hermetic fixture verification. | ![Status: Archived](https://img.shields.io/badge/Status-Archived-lightgrey) |
| [**AUDIT_2026-09-24_STATUS_SELF_HEAL.md**](AUDIT_2026-09-24_STATUS_SELF_HEAL.md) | 2026-09-24 | macOS status hook, daemon self-healing, and IPC reliability audit. | ![Status: Archived](https://img.shields.io/badge/Status-Archived-lightgrey) |
| [**AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md**](AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md) | 2026-09-26 | Backend aggregator decomposition, exporter pipelines, and lock resilience. | ![Status: Archived](https://img.shields.io/badge/Status-Archived-lightgrey) |
| [**AUDIT_2026-09-29_SYSTEM_PERFORMANCE_AND_UX.md**](AUDIT_2026-09-29_SYSTEM_PERFORMANCE_AND_UX.md) | 2026-09-29 | Menu bar popover performance, SQLite indexing, and UX contrast verification. | ![Status: Archived](https://img.shields.io/badge/Status-Archived-lightgrey) |
