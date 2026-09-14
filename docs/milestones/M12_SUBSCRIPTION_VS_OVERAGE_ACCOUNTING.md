# Milestone Slice M12: Subscription Coverage vs. Actual Overage Accounting & Avoided Cost

- **Status**: Completed
- **Date**: 2026-09-07
- **Branch**: `feat/subscription-avoided-cost-accounting`
- **ADR Reference**: ADR-023
- **Empirical Ground Truth**: 11,743 audited conversation turns across 15 active workspaces, reconciled with persistent exhaustion ledger (`data/exhaustion_ledger.json`).

---

## 1. Architectural Objectives & Invariants

1. **Decoupled Subscription vs. Overage Dual-Metric Model (ADR-023)**:
   - Previously, project and branch tables presented theoretical developer API rate-card costs under "Total Spend", creating the misleading impression that all turns were billed as out-of-pocket overages or API usage.
   - The reality:
     - The vast majority of turns (11,532 / 11,743 = 98.2%) were executed within standard Google One AI Premium / Antigravity Pro quota allowance (£18.99/mo) at **£0.00 marginal spend**.
     - Exactly 211 turns occurred during confirmed 429 server exhaustion intervals (`exc-20260905-13` and `exc-20260905-14`), debiting exactly 1,179 AI credits (£11.31 / $11.79) from the user's prepaid add-on credit bank.
     - 100% of these 211 overage turns belonged exclusively to workspace `Geminu token consumption dashboard.` on branch `main`.
     - All other 14 projects operated at **100% subscription coverage** with **£0.00 actual overage**.
2. **Turn-Level Exhaustion Correlation Engine (`src/aggregator.py`)**:
   - `aggregate_conversation_telemetry` evaluates each turn timestamp against confirmed exhaustion intervals (`start` to `end`), flagging turns with `is_overage: true | false`.
   - Conversation summaries compute:
     - `subscription_covered_turns`
     - `overage_turns`
     - `subscription_covered_pct`
     - `avoided_cost_usd` & `avoided_cost_gbp` (imputed developer API value)
3. **Mathematical Zero-Leakage & Credit Reconciliation Invariant**:
   - `aggregate_global_telemetry` attributes confirmed ledger incidents across projects and branches in exact proportion to turns falling inside each incident window.
   - Invariant: Sum of project `actual_overage_credits` strictly equals total confirmed credit deductions (1,179 credits).
   - Invariant: Sum of project `avoided_cost_gbp` strictly equals global imputed plan value (£203.07), demonstrating a 10.7x ROI on the £18.99/mo subscription.
4. **Visual Dashboard Redesign (`dashboard/index.html`)**:
   - Portfolio KPIs:
     - Monitored Projects (15)
     - Active Git Branches
     - Subscription Coverage (`98.2%` with `£0 marginal cost`)
     - Avoided API Cost (`£203.07` plan value vs. `£11.31` actual overages)
   - Projects table columns: `Project & Filesystem Path`, `Branches`, `Turns`, `Total Input`, `Cache %`, `Subscription Coverage`, `Actual Overage`, `Avoided Cost`, `Actions`.
   - High-contrast visual badges:
     - `✓ 100% Covered` (green) for projects with zero overage.
     - `⚠️ 92.7% Covered` (amber) for projects with credit spillover.
   - Expandable branch drawer showing branch-specific coverage, overage credits, and avoided costs.

---

## 2. Verified Acceptance Gates (VDONE.md)

1. **Gate V48**: Turn-Level Exhaustion Correlation & Flagging (`python3 -m unittest tests.test_aggregator.TestAggregator.test_turn_overage_correlation`). (PASS)
2. **Gate V49**: Project & Branch Subscription vs. Overage Payload Schema verified against 15 active projects in `dashboard/index.html`. (PASS)
3. **Gate V50**: Mathematical Zero-Leakage & Credit Reconciliation Invariant (`python3 -m unittest tests.test_aggregator.TestAggregator.test_project_overage_vs_covered_attribution`). (PASS)
4. **Gate V51**: Dual-Metric Dashboard DOM Elements & Table Headers verified in `dashboard/index.html`. (PASS)
5. **Gate V52**: Full Regression & Integration Test Suite Integrity (`python3 -m unittest discover -s tests`: 69/69 tests passing). (PASS)
