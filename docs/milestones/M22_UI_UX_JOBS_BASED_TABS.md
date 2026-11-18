# Milestone M22: UI/UX Ergonomics & Jobs-Based Tabs Architecture

**Date**: 12 September 2026  
**Branch**: `feat/jobs-based-tabs` (Merged into `main`)  
**Commit**: `83db388`  
**ADR References**: ADR-003, ADR-004, ADR-024, ADR-031, ADR-035

---

## 1. Background & Objectives

Following the Senior Engineering and UI/UX Audit across Antigravity workspaces, the dashboard UI required an ergonomic overhaul to align with developer mental models and eliminate layout shift, telemetry download bloat, and cognitive clutter:
1. **Jobs-Based Mental Model (Decision 7)**:
   - Previously, telemetry metrics, quotas, conversation tables, and billing information were crowded into an unsegmented view with duplicate 5-hour and weekly allowance cards.
   - Developers needed 5 clean, distinct jobs-based views:
     - **Now**: Live 5h burst gauge, 1w quota card, provider split (Gemini vs Claude), quota runway with dual benchmark needle, and quick recent active sessions.
     - **Sessions**: Dedicated deep dive for all historical conversations and turn-by-turn inspection, enhanced with real-time text search and multi-column sorting.
     - **Projects**: Authoritative multi-workspace and Git branch rollups with context caching efficiency and dual-track cost attribution.
     - **Billing**: Monthly Pro subscription (£18.99/mo) plan value, prepaid AI credit bank status, and deterministic Google One activity reconciliation history.
     - **Plan**: Forward-looking What-If Workload Simulator and directly embedded Plan Profile, Promotions & Rate Cards management.
2. **Decoupled Fast Hash-Gating Ticker (Decision 5)**:
   - Previously, client-side live auto-refresh reloaded `data.js` (~12.0 MB) every 30 seconds unconditionally, forcing heavy repeated network downloads and JSON parsing.
   - The exporter now generates a decoupled, lightweight metadata file (`dashboard/meta.js`, 207 bytes) containing the SHA-1 hash of the telemetry payload. The ticker reloads `meta.js` and only fetches `data.js` when the payload hash actually changes.
3. **UI Polish, Clean Labels & Icon Discipline (Decisions 9 & User Directive)**:
   - Eliminated raw LaTeX syntax (`Turn Count ($N$)` -> `Turn Count`) in simulator sliders.
   - Stripped commit-level and internal ADR badges (`ADR-035`, `ADR-034`, `ADR-019`, `ADR-022`) from visible end-user UI.
   - Replaced informal emojis (`💼`, `💳`) with clean, executive typography and professional navigation markers.
   - Standardized summary money formatting to 2 decimal places (`<span id="kpi-imputed-val">`).
   - Fixed archetype carousel padding and layout clipping.

---

## 2. Architecture & Deliverables

### A. 5 Jobs-Based Tab Layout (`dashboard/index.html`)

| Tab ID | View ID | Primary Job & Components |
|---|---|---|
| `tab-now` | `view-now` | **Live Monitoring**: 3-panel Provider Quota Silos (Gemini 5h burst & weekly, Center Runway with Dual Benchmark Needle, Claude/GPT models), Model Allowance Matrix (5h vs 1w with subagent partition pills), Lifetime KPI grid, and Recent Active Sessions quick table. |
| `tab-sessions` | `view-sessions` | **Session Forensics**: Real-time search filter (`#convo-search-input`), workspace filter, conversation dropdown, sortable table headers (`title`, `workspace`, `turns`, `input`, `cache`, `overage`, `cost`), and turn-by-turn inspection drawer (`#turns-card`). |
| `tab-projects` | `view-projects` | **Workspace Intelligence**: Dynamic Portfolio KPI Cards (`#projects-portfolio-kpis`) and Projects & Git Branch Costing hierarchy (`#projects-table`). |
| `tab-billing` | `view-billing` | **Financial Accounting**: Monthly Pro Subscription card, Prepaid AI Credit Bank card (2,500 credits add-on), and Google One AI Credit Activity Reconciliation table. |
| `tab-plan` | `view-plan` | **Capacity Planning**: Interactive What-If Workload Simulator, multi-agent archetypes, safety gauge, plan tier sensitivity table, and embedded Plan Profiles, Overlays & Rate Cards manager (`#plan-manager-card`). |

### B. Fast Telemetry Hash-Gating Engine (`scripts/export_dashboard.py`)

- Computes deterministic SHA-1 hash of `data.json` content:
  `payload_sha1 = hashlib.sha1(json_str.encode("utf-8")).hexdigest()`
- Writes `dashboard/meta.js` and `dashboard/meta.json` atomically via `.tmp` staging:
  `window.__TELEMETRY_META__ = { "conversations_count": ..., "generated_at": ..., "payload_bytes": ..., "payload_sha1": ... };`
- Client ticker fetches `meta.js?t=${Date.now()}` (~200 B) every 30s. If `payload_sha1` matches `currentTelemetrySha1`, the 12 MB `data.js` download is bypassed completely.

---

## 3. Verification & Quality Gates

All 6 acceptance gates for Phase 2 verified cleanly:

| Gate | Check | Expectation | Measured Proof |
|---|---|---|---|
| **V101** | `python3 scripts/export_dashboard.py && test -f dashboard/meta.js && ...` | `Verified: meta.js contains SHA-1 payload hash.` | **PASS** (exit code 0; 207 bytes payload SHA-1 generated atomically). |
| **V102** | `python3 -c "tabs=['tab-now', 'tab-sessions', 'tab-projects', 'tab-billing', 'tab-plan']; ..."` | `Verified: 5 Jobs-Based tabs present in dashboard HTML.` | **PASS** (exit code 0; all 5 views and tabs structured and responsive). |
| **V103** | `python3 -c 'assert "ADR-035" not in c; assert "($N$)" not in c; ...'` | `Verified: Clean UI labels without ADR badges or raw LaTeX syntax.` | **PASS** (exit code 0; clean 'Turn Count' slider label, zero ADR-035 references). |
| **V104** | `python3 -c "assert '💼' not in c; assert '💳' not in c; ..."` | `Verified: Clean professional navigation icons.` | **PASS** (exit code 0; zero informal emojis in navigation or billing tabs). |
| **V105** | `python3 -c "assert 'kpi-imputed-val' in c; ..."` | `Verified: 2-decimal summary currency display.` | **PASS** (exit code 0; `kpi-imputed-val` formatted to 2 decimals). |
| **V106** | `python3 -m unittest discover -s tests` | 100% tests pass, exit code 0 | **PASS** (114/114 tests passing cleanly across full suite in 1.521s, 0 failures, 0 errors, 0 ResourceWarnings). |
