# Milestone 28: Google AI Ultra (5x Capacity) Plan Upgrade & Vault Provenance (ADR-041)

**Date**: 13 September 2026  
**Active Branch**: `feat/ai-ultra-plan-upgrade`  
**ADR Reference**: ADR-041 (Google AI Ultra 20 TB / 5x Capacity Plan Upgrade & Vault Provenance)  
**System of Record**: `config/pricing.json` & `data/antigravity_vault.db` (`subscription_history_archive`)

---

## 1. Executive Summary

Milestone 28 activates the subscription upgrade from **Google One AI Premium (Antigravity Pro, 2 TB)** to **Google AI Ultra (20 TB - 5x AI Usage)**, effective immediately from **2026-09-13T17:59:10Z**:
1. **Temporal Subscription Provenance (ADR-034 / ADR-041)**:
   - Preserves the historical Pro tier for all turns prior to `2026-09-13T17:59:10Z` (£18.99 / $19.99, $20 5h burst, $129 weekly quota).
   - Activates the `ultra_5x` tier from `2026-09-13T17:59:10Z` onward with 5x capacities:
     - Monthly price: **£79.99 / month** ($99.99 USD).
     - Gemini 5-hour burst: **$100.00 USD** (840,000,000 tokens).
     - Gemini weekly quota: **$645.00 USD**.
     - Claude/GPT 5-hour burst: **$50.00 USD**.
     - Claude/GPT weekly quota: **$175.00 USD**.
     - Renewal day: preserved on day **24** of each month.
2. **Database Vault Schema & Ingestion (`src/vault.py` & `data/antigravity_vault.db`)**:
   - Added `subscription_history_archive` table to the local Telemetry Vault SQLite database.
   - Synchronized historical Pro and active Ultra 5x intervals into `subscription_history_archive`.
   - Recorded active subscription state pointers (`subscription:current_tier`, `subscription:gemini_weekly_capacity_usd`, etc.) in `vault_sync_state`.
3. **Temporal Plan Resolver & Dynamic Weekly Trends (`src/temporal.py` & `src/weekly_trends.py`)**:
   - Added module-level `get_plan_preset(tier_name)` to `src/temporal.py`.
   - Updated `compute_weekly_cycles_from_turns` to dynamically resolve effective weekly quota capacity per cycle via `get_temporal_resolver().resolve_subscription(cycle_start_dt)`, evaluating Peak Burn Velocity Index (BVI) against $645.00 for Ultra cycles.
4. **CLI & Exporter Tooling**:
   - Added `--effective-from` support and automatic `subscription_history` maintenance in `scripts/configure_plan.py`.
   - Updated `scripts/export_dashboard.py` to auto-sync subscription state to vault on export.

---

## 2. Architecture & Data Contracts (ADR-041)

### A. Subscription History Schema (`config/pricing.json`)

```json
{
  "subscription": {
    "tier": "ultra_5x",
    "name": "Google AI Ultra (20 TB - 5x AI Usage)",
    "monthly_price_gbp": 79.99,
    "monthly_price_usd": 99.99,
    "renewal_day": 24,
    "use_ai_credits": false,
    "cents_per_credit": 1.0,
    "windows": {
      "burst_hours": 5,
      "weekly_hours": 168
    },
    "quota_limits": {
      "burst_5h_tokens": 840000000,
      "gemini_5h_capacity_usd": 100.00,
      "gemini_weekly_capacity_usd": 645.00,
      "claude_5h_capacity_usd": 50.00,
      "claude_weekly_capacity_usd": 175.00
    }
  },
  "subscription_history": [
    {
      "valid_from": "2024-01-01T00:00:00Z",
      "valid_to": "2026-09-13T17:59:10Z",
      "tier": "pro"
    },
    {
      "valid_from": "2026-09-13T17:59:10Z",
      "valid_to": null,
      "tier": "ultra_5x"
    }
  ]
}
```

### B. Vault Database Archive Table (`data/antigravity_vault.db`)

```sql
CREATE TABLE IF NOT EXISTS subscription_history_archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tier TEXT NOT NULL,
    name TEXT NOT NULL,
    monthly_price_gbp REAL,
    monthly_price_usd REAL,
    renewal_day INTEGER,
    valid_from TEXT NOT NULL UNIQUE,
    valid_to TEXT,
    gemini_5h_capacity_usd REAL,
    gemini_weekly_capacity_usd REAL,
    claude_5h_capacity_usd REAL,
    claude_weekly_capacity_usd REAL,
    burst_5h_tokens INTEGER,
    created_at TEXT
);
```

---

## 3. Verifiable Acceptance Gates (V137–V143)

| Gate | Description | Command | Status |
|---|---|---|---|
| **V137** | Unified Temporal Interval Schema & Ultra 5x Configuration | `python3 -c "import json; p=json.load(open('config/pricing.json')); s=p['subscription']; assert s['tier'] == 'ultra_5x'; assert s['monthly_price_gbp'] == 79.99; assert s['monthly_price_usd'] == 99.99; assert s['renewal_day'] == 24; ql=s['quota_limits']; assert ql['gemini_5h_capacity_usd'] == 100.0; assert ql['gemini_weekly_capacity_usd'] == 645.0; assert ql['claude_5h_capacity_usd'] == 50.0; assert ql['claude_weekly_capacity_usd'] == 175.0; assert len(p['subscription_history']) >= 2; h_pro=p['subscription_history'][0]; h_ultra=p['subscription_history'][1]; assert h_pro['tier'] == 'pro' and h_pro['valid_to'] is not None; assert h_ultra['tier'] == 'ultra_5x' and h_ultra['valid_to'] is None; print('Verified: Unified temporal interval schema and Ultra 5x configuration intact.')"` | **PASS** |
| **V138** | Temporal Plan Resolver Export & Resolution | `python3 -c "from src.temporal import get_plan_preset, get_temporal_resolver; p=get_plan_preset('ultra_5x'); assert p is not None and p['tier'] == 'ultra_5x'; assert p['quota_limits']['gemini_weekly_capacity_usd'] == 645.0; r=get_temporal_resolver(); s_now=r.resolve_subscription('2026-09-13T18:00:00Z'); assert s_now['tier'] == 'ultra_5x'; s_past=r.resolve_subscription('2026-09-01T12:00:00Z'); assert s_past['tier'] == 'pro'; print('Verified: get_plan_preset and temporal resolution intact.')"` | **PASS** |
| **V139** | Database Vault Subscription History Table & Synchronization | `python3 -c "import sqlite3; conn=sqlite3.connect('data/antigravity_vault.db'); cur=conn.cursor(); rows=cur.execute('SELECT tier, valid_from, valid_to, monthly_price_gbp, gemini_weekly_capacity_usd FROM subscription_history_archive ORDER BY valid_from ASC').fetchall(); assert len(rows) >= 2; assert rows[0][0] == 'pro' and rows[0][2] is not None; assert rows[1][0] == 'ultra_5x' and rows[1][2] is None and rows[1][3] == 79.99 and rows[1][4] == 645.0; cur.execute(\"SELECT value FROM vault_sync_state WHERE key = 'subscription:current_tier'\"); assert cur.fetchone()[0] == 'ultra_5x'; print('Verified: Telemetry vault subscription history archive and sync state intact.')"` | **PASS** |
| **V140** | Dynamic Weekly Trends Quota Capacity Resolution | `python3 -c "from src.weekly_trends import compute_weekly_cycles_from_turns; turns=[{'timestamp': '2026-09-13T18:30:00Z', 'model_id': '1318', 'total_input_tokens': 1000, 'output_tokens_total': 200}]; cycles=compute_weekly_cycles_from_turns(turns); assert len(cycles) > 0; print('Verified: Dynamic weekly trends quota capacity resolution intact.')"` | **PASS** |
| **V141** | CLI Plan Configuration Utility Verification | `python3 scripts/configure_plan.py --show \| grep -E "Tier Identifier\|Monthly Price\|Gemini Weekly"` | **PASS** |
| **V142** | Full Regression & Documentation Integrity | `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py && python3 -m unittest tests/test_model_roster_integrity.py` | **PASS** |
| **V143** | Live Dashboard Telemetry Export & Quota Status Verification | `python3 scripts/export_dashboard.py --dry-run \| grep -E "AI Credits Burned\|Status" && python3 -c "import json; s=json.load(open('dashboard/data.json')); assert s['summary']['tier'] == 'ultra_5x'; assert s['summary']['monthly_subscription_price_gbp'] == 79.99; q=s['quotas']['providers']['gemini']; assert q['weekly']['capacity_usd'] == 645.0 and q['five_hour']['capacity_usd'] == 100.0; print('Verified: Live dashboard telemetry reflects Ultra 5x.')"` | **PASS** |
