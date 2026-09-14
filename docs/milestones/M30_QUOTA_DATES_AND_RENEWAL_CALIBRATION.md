# Milestone 30: Quota Reset Dates & Monthly Renewal Day Calibration

**Status**: Completed  
**Branch**: `feat/quota-dates-and-renewal-update`  
**Tag**: `v1.30.0`  
**ADR Citation**: [ADR-042](../../docs/HANDOVER.md#adr-table)  
**Acceptance Gates**: V152–V158 in [`VDONE.md`](../../VDONE.md)  

---

## 1. Executive Summary

Upon user upgrade to **Google AI Ultra (5x Capacity)**, live Antigravity desktop Connect-RPC telemetry (`RetrieveUserQuotaSummary`) and UI screenshot confirmation revealed two fundamental calendar transitions:
1. **Weekly Quota Reset Anchor**: Instead of the historical fixed Thursday 18:00 UTC cycle reset, Google Antigravity immediately reset the weekly quota timer at the exact second of upgrade (`2026-09-13T17:58:04Z`), establishing a recurring **Sunday 17:58:04 UTC (18:58:04 BST)** weekly cycle (`2026-09-20T17:58:04Z`, matching *"6 days, 23 hours remaining"*).
2. **Monthly Billing Renewal Day**: Calibrated from Day 24 (historical Pro tier) to **Day 13** of each month, aligning with Google One's immediate upgrade billing anniversary.
3. **Temporal Invariant**: Historical turns prior to `2026-09-13T17:58:04Z` preserve Thursday 18:00 UTC cycle boundaries and Pro rates, preventing retroactive calculation contamination.

---

## 2. Changes Implemented

### Configuration & Temporal Engine
- **`config/pricing.json`**:
  - Updated `subscription.renewal_day` to `13`.
  - Added `subscription.weekly_reset_day = "Sunday"` and `subscription.weekly_reset_time_utc = "17:58:04"`.
  - In `subscription_history`: Closed `pro` at `"valid_to": "2026-09-13T17:58:04Z"` and started `ultra_5x` at `"valid_from": "2026-09-13T17:58:04Z"` with `renewal_day: 13`.
- **`src/temporal.py`**:
  - Updated `PLAN_PRESETS` for `ultra_5x` and `enterprise_5x` with `renewal_day: 13` and Sunday reset parameters.

### Quota Aggregation Engine
- **`src/aggregator.py`**:
  - Enhanced `get_weekly_cycle_bounds()` to dynamically resolve reset weekday and time via `get_temporal_resolver().resolve_subscription(ref_dt)`. Supports `explicit_reset_dt` override from live desktop indicator.
  - In `aggregate_global_telemetry()`: Synced `weekly_cycle_bounds` with live desktop indicator `reset_time` (`2026-09-20T17:58:04Z`). Passed `renewal_day = 13` to `get_monthly_billing_bounds`.

### Historical Weekly Trends & Vault Archival
- **`src/weekly_trends.py`**:
  - Updated `compute_weekly_cycles_from_turns()` and `sync_weekly_trends_to_vault()` to format `cycle_key` as `s_dt.strftime("%Y-%m-%d_%H:%M")`, smoothly grouping post-upgrade turns into `2026-09-13_17:58`.
- **`src/vault.py`**:
  - Updated `sync_subscription_to_vault()` to prune stale records from `subscription_history_archive`, ensuring exact 1:1 projection of `subscription_history`.

---

## 3. Verification & Acceptance Gates

All Phase 10 verification gates (V152–V158) passed cleanly:
- `V152`: `config/pricing.json` verified with Day 13 and Sunday 17:58:04 reset.
- `V153`: Historical Pro era (e.g. 5 Sep 2026) verified returning Thursday 18:00 UTC bounds.
- `V154`: Post-upgrade era verified returning Sunday 17:58:04 UTC bounds and 6 days, 23 hours countdown.
- `V155`: Monthly billing horizon verified anchoring to 13 Oct 2026.
- `V156`: SQLite Vault `subscription_history_archive` verified synchronized and pruned.
- `V157`: Executive status hook (`~/.antigravity_quota_status.json`) verified with Sunday reset.
- `V158`: 170 unit tests + documentation integrity tests passed with 0 errors.
