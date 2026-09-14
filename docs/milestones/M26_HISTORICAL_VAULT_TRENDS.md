# Milestone 26: Historical Vault Trends & 8–12 Week SVG Trendline Chart (M4 / ADR-039)

## 1. Executive Summary

Milestone 26 delivers the core historical intelligence layer outlined in the Code & UX Audit (`docs/AUDIT_2026-09-12_CODE_AND_UX.md` §1.2 & §5 #16):
1. **Historical Weekly Cycles Persistence (`weekly_cycles_archive`)**:
   - Aggregates long-term turn history from the Vault (`steps_archive` in `data/antigravity_vault.db`) into weekly cycle snapshots.
   - Anchors cycles strictly to Google Antigravity's **Thursday 18:00 UTC** quota reset boundary (`get_weekly_cycle_bounds`).
   - Implements fast-path cache validation via `vault_sync_state` (`weekly_trends:last_turn_count` and `weekly_trends:last_cycle_key`), executing repeated checks in `<0.5ms`.
2. **Deterministic Overage Reconciliation & Peak Burn Velocity Index (BVI)**:
   - Seamlessly correlates weekly cycles with `data/exhaustion_ledger.json`, capturing 3,640 official Google One AI credits burned across 03–10 Sep 2026 (£34.93 / .40 overage).
   - Implements Bayesian M-estimate shrinkage on daily burn rates to compute the peak Burn Velocity Index (1.65x peak velocity during exhaustion week).
3. **Interactive 8–12 Week SVG Trendline Chart & Billing Tab Surface**:
   - Renders a responsive SVG trendline chart inside `#weekly-trends-card` on the `Billing` tab (`view-billing`).
   - Features 3 metric views with instant toggle buttons:
     - **Processed Tokens**: Area and line chart showing prompt, cached, and output token trajectories.
     - **Cost & Overage**: Avoided commercial API costs alongside reconciled Google One credit overages.
     - **Peak Burn Velocity (BVI)**: Moving burn intensity relative to weekly quota threshold (1.0x reference).
   - Provides interactive hover crosshairs, data scrubbers, tooltips with cycle details, a 4-metric executive KPI ribbon, and a historical cycles breakdown table.

---

## 2. Architecture & Data Contracts (ADR-039)

### SQLite Schema (`weekly_cycles_archive`)
```sql
CREATE TABLE IF NOT EXISTS weekly_cycles_archive (
    cycle_key TEXT PRIMARY KEY,
    cycle_start_utc TEXT NOT NULL,
    cycle_end_utc TEXT NOT NULL,
    label TEXT NOT NULL,
    total_turns INTEGER DEFAULT 0,
    total_input_tokens INTEGER DEFAULT 0,
    cached_tokens INTEGER DEFAULT 0,
    prompt_tokens_uncached INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_processed_tokens INTEGER DEFAULT 0,
    cache_hit_ratio_pct REAL DEFAULT 0.0,
    estimated_cost_usd REAL DEFAULT 0.0,
    estimated_cost_gbp REAL DEFAULT 0.0,
    actual_overage_credits INTEGER DEFAULT 0,
    actual_overage_usd REAL DEFAULT 0.0,
    actual_overage_gbp REAL DEFAULT 0.0,
    peak_bvi REAL DEFAULT 0.0,
    is_current_cycle INTEGER DEFAULT 0,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_weekly_cycles_start ON weekly_cycles_archive(cycle_start_utc);
```

### Telemetry Payload Schema (`payload["weekly_trends"]`)
```json
{
  "cycles": [
    {
      "cycle_key": "2026-09-03_18:00",
      "cycle_start_utc": "2026-09-03T18:00:00+00:00",
      "cycle_end_utc": "2026-09-10T18:00:00+00:00",
      "label": "03 Sep – 10 Sep 2026",
      "total_turns": 4350,
      "total_processed_tokens": 1051755054,
      "total_input_tokens": 1047120000,
      "cached_tokens": 892000000,
      "prompt_tokens_uncached": 155120000,
      "total_output_tokens": 4635054,
      "cache_hit_ratio_pct": 85.19,
      "estimated_cost_usd": 1284.50,
      "estimated_cost_gbp": 1014.75,
      "actual_overage_credits": 3640,
      "actual_overage_usd": 36.40,
      "actual_overage_gbp": 34.93,
      "peak_bvi": 1.65,
      "is_current_cycle": 0
    }
  ],
  "total_cycles_recorded": 13,
  "summary": {
    "cycles_analyzed": 12,
    "average_tokens_per_week": 210817371,
    "average_cost_per_week_usd": 245.80,
    "average_cost_per_week_gbp": 194.18,
    "peak_week_tokens": 1051755054,
    "peak_week_label": "03 Sep – 10 Sep 2026",
    "peak_week_cost_usd": 1284.50,
    "token_growth_rate_pct": 14.2,
    "overage_cycles_count": 1,
    "total_overage_credits": 3640
  }
}
```

---

## 3. Verifiable Quality Gates & Proofs

| Gate | Check Command | Status | Proof |
|---|---|---|---|
| **V125** | Schema & Vault Archival Verification (`weekly_cycles_archive`) | **PASSED** | `weekly_cycles_archive` active with 13 historical weekly cycles (Exit code 0) |
| **V126** | Thursday 18:00 UTC Cycle Anchoring & Overage Ledger Reconciliation | **PASSED** | 03-10 Sep cycle reconciled 3,640 credits (1,051,755,054 tokens) (Exit code 0) |
| **V127** | Peak BVI & Multi-Week Moving Averages | **PASSED** | Peak week tokens 1,051,755,054, peak BVI 1.65x (Exit code 0) |
| **V128** | Exporter Integration & Telemetry Payload Structure | **PASSED** | `[DRY-RUN] Historical Trends: 12 weekly cycles archived (last 12 weeks avg: 210,817,371 tokens/wk)` (Exit code 0) |
| **V129** | Responsive SVG Trendline Chart DOM, JS Renderer & Styling Integrity | **PASSED** | Trendline chart HTML, JS renderers, and CSS styles verified (Exit code 0) |
| **V130** | Full Regression Test Suite & Documentation Integrity | **PASSED** | 139 unit tests + 6 documentation integrity tests passing cleanly across full suite in 4.95s (0 failures, 0 errors) (Exit code 0) |
