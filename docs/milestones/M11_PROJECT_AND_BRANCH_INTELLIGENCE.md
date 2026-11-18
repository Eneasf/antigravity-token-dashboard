# Milestone Slice M11: Multi-Project & Git Branch Telemetry Intelligence (Dedicated Dashboard Tab & Branch Costing)

- **Status**: Completed
- **Date**: 2026-09-06
- **Branch**: `feat/project-branch-intelligence`
- **ADR Reference**: ADR-022
- **Empirical Ground Truth**: `trajectory_metadata_blob` (`id = 'main'`) across 115+ Antigravity conversation SQLite databases.

---

## 1. Architectural Objectives & Invariants

1. **Authoritative Extraction from `trajectory_metadata_blob` (ADR-022)**:
   - Antigravity conversation SQLite databases (`~/.gemini/antigravity/conversations/*.db`) store structured protobuf metadata in `trajectory_metadata_blob`:
     - **Workspace Path**: `Field 7` / `Field 1:sf1` (`file:///Users/developer/Documents/...`).
     - **Active Git Branch**: `Field 1:sf4` (e.g. `feat/qnap-service-scaffolding`, `main`).
     - **Conversation UUID**: `Field 6`.
   - This eliminates dependency on brittle regex scraping of central summaries and resolves 100% of previous `"Unknown Workspace"` or trailing byte artifact cases (`...B&`).
2. **Project & Git Branch Hierarchical Aggregation**:
   - `src/aggregator.py` groups sessions and turns by project (clean directory basename) and nested Git branch.
   - Aggregated metrics per project and per branch:
     - `conversation_count`, `turn_count`
     - `total_input_tokens`, `prompt_tokens_uncached`, `cached_tokens`, `total_output_tokens`
     - `cache_hit_ratio_pct`
     - `estimated_cost_usd`, `estimated_cost_gbp`
     - `branches`: Array of branch breakdowns with token and cost attribution.
3. **Dedicated Tabbed Dashboard Navigation**:
   - Persistent top-level tab switcher in `dashboard/index.html` positioned directly beneath the Quota Command Banner:
     - `[ 📊 Quotas & Telemetry ]` (Primary operational view: Quota gauges, model allowance matrix, turn inspector).
     - `[ 📁 Projects & Git Branches ]` (New dedicated portfolio view: Project cards, branch cost breakdown, path inspect).
     - `[ 💳 Credit Bank & Reconciliation ]` (Dedicated billing view: 429 exhaustion intervals, ledger audit, hourly activity).
   - Preserves 100% offline single-file execution (ADR-003) and byte-deterministic JSON export (ADR-004).
4. **Interactive Cross-Linking**:
   - Clicking a project or specific branch instantly filters the Conversations Explorer and Turn-by-Turn Telemetry inspector.

---

## 2. Verified Acceptance Gates (VDONE.md)

1. **Gate V42**: Authoritative extraction from `trajectory_metadata_blob`: `read_conversation_metadata` resolves clean workspace path, project name, and active Git branch directly from DB. (PASS)
2. **Gate V43**: Project & branch aggregation payload: `payload['projects']` correctly computed with nested `branches` arrays in `src/aggregator.py`. (PASS)
3. **Gate V44**: Branch-level token costing: sum of branch tokens and costs strictly equals project totals with zero leaked tokens (`test_branch_level_token_costing`). (PASS)
4. **Gate V45**: Tabbed navigation DOM elements: `dashboard/index.html` contains persistent tab switcher (`tab-quotas`, `tab-projects`, `tab-credits`, `view-quotas`, `view-projects`, `view-credits`) with client-side switching logic. (PASS)
5. **Gate V46**: Projects & branches table DOM elements: `projects-portfolio-kpis`, `projects-table-tbody`, and branch expansion elements present and bound. (PASS)
6. **Gate V47**: Full regression test suite integrity (`python3 -m unittest discover -s tests`: 67/67 tests passing). (PASS)
