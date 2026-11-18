# Milestone 93: Live Quota Snapshot Archival, Burn Interval Analytics & Fast Monitor Convergence

**Date**: 2026-10-14  
**Branch**: `feat/m93-quota-snapshot-observer-and-fast-monitor`  
**ADRs**: ADR-094

---

## 1. Context & Problem Statement

On `2026-10-13`, the first weekly Gemini quota exhaustion occurred on **Google AI Ultra (5x)** (`ultra_5x`) while using **Gemini 4 Argon (High)** (`1417`). Two critical requirements emerged from the incident forensics:

1. **Empirical Observation of the `4.0000x` Weekly-to-5h Pool Ratio & Argon Burn Rate**:
   - Forensic correlation between Connect-RPC server remaining fractions and token telemetry revealed that `1 full 5h burst = 25.00% of the Weekly Gemini pool` (`4.0000x` weekly-to-5h ratio across all Gemini models), and that Gemini 4 Argon (`1417`) burns quota `~4.2x` faster overall (`~8.2x` higher relative weight on cached tokens) than currently configured in `config/pricing.json`.
   - Before modifying `config/pricing.json` (tracked as open backlog item **M94**), we need continuous, deduplicated time-series archival of Connect-RPC `remainingFraction` snapshots in `data/antigravity_vault.db` and automated interval burn analysis (`v_quota_burn_intervals` + `scripts/quota_regression.py`).

2. **Eliminating the macOS Menu Bar Monitor (`AntigravityBar`) Update Delay**:
   - During the `2026-10-13` exhaustion event, the macOS menu bar indicator took several minutes to turn red (`EXHAUSTED`) after the `429 RESOURCE_EXHAUSTED` response.
   - Root cause forensics identified four compounding delays:
     1. **BST/Timezone Offset in `parse_glog_timestamp()`**: `language_server_macos_arm.log` emits local wall-clock timestamps (`15:52:47` BST = `UTC+1`), which `src/log_reader.py` tagged as `+00:00` UTC, making fresh `429` events appear `-3599s` in the future or misaligning window comparisons.
     2. **Fast Tier Bypassing Quota & 429 Checks**: `export_fast_tier()` only updated active conversation token counts while copying stale `five_hour` / `weekly` status from `~/.antigravity_quota_status.json` without checking the log tail for `429` events or polling Connect-RPC.
     3. **Late Status Hook Write in Heavy Export**: `_export_telemetry_impl()` wrote `~/.antigravity_quota_status.json` only after `sync_conversations_to_vault()` and `sync_log_events_to_vault()` completed.
     4. **53.73 MB `vault_cache` JSON Deserialization Bloat & Redundant `transcript_full.jsonl` Scans**: `load_vault_analytics_cached()` serialized every historical tool call's full `arguments_json` into `dashboard/.export_cache.db` (`53.73 MB`), and `sync_conversations_to_vault()` re-read multi-megabyte `transcript_full.jsonl` files once per subagent step instead of once per conversation.

---

## 2. Architecture Decision Record

### ADR-094: Live Quota Snapshot Archival & Fast Monitor Convergence
- **Status**: Adopted
- **Context**: Continuous empirical observation of server-side quota depletion requires persisting Connect-RPC `remainingFraction` readings over time, while native menu bar alerting requires sub-second reaction to `429 RESOURCE_EXHAUSTED` log events and fast-tier Connect-RPC sync without blocking on heavy Vault synchronization.
- **Decision**:
  1. Add `quota_snapshots_archive` and analytical view `v_quota_burn_intervals` to `src/vault_schema.py`, syncing deduplicated Connect-RPC quota readings via `sync_quota_snapshot_to_vault()` in `src/vault.py`.
  2. Extend `scripts/quota_regression.py` (`analyze_vault_burn_intervals()`) to report empirical $\Delta\text{5h}\%$, $\Delta\text{Weekly}\%$, and $\Delta\text{5h}/\Delta\text{Weekly}$ ratios across consecutive Vault snapshots.
  3. Convert local wall-clock glog timestamps to UTC in `parse_glog_timestamp()` when `local_tz=True` (defaulting to `True` on `DEFAULT_LOG_PATH`), and add `<0.5ms` tail-scanned `get_latest_exhaustion_event_utc()` to `src/log_reader.py`.
  4. Upgrade `export_fast_tier()` in `scripts/export_dashboard.py` (triggered by both `.db-wal` and `.log` changes in `scripts/watch_telemetry.py`) to immediately clamp `~/.antigravity_quota_status.json` to `EXHAUSTED` (`0%`) upon a recent `429` event and poll Connect-RPC live quota (throttled to once per 15s).
  5. Write `~/.antigravity_quota_status.json` immediately after `aggregate_global_telemetry()` before Vault sync, deduplicate `transcript_full.jsonl` reads per `caller_id`, and compact `tool_calls_by_convo` in `load_vault_analytics_cached()` to shrink `dashboard/.export_cache.db` from `53.73 MB` to `5.64 MB`.

---

## 3. Verification Gates (VDONE)

- **B1**: Full unit test suite (`python3 -m unittest discover -s tests -p 'test_*.py'`) passes with zero errors.
- **B2**: `parse_glog_timestamp` local timezone conversion and `get_latest_exhaustion_event_utc` tail scan verified.
- **B3**: `quota_snapshots_archive` and `v_quota_burn_intervals` accurately compute `delta_5h_pct = 20.0`, `delta_weekly_pct = 5.0`, and `ratio_5h_to_weekly = 4.0`.
- **B4**: `tests.test_export_dashboard`, `tests.test_quota_regression`, and `tests.test_log_reader` pass.
- **B5**: `docs/HANDOVER.md` records `M94` as an explicit `Open` backlog item to calibrate `config/pricing.json` after the M93 observation period.

---

## 4. Empirical Post-Upgrade Reconciliation (14 Oct 2026)

Following deployment of `quota_snapshots_archive` and `v_quota_burn_intervals`, a full 5-hour Gemini burst exhaustion (`100.0% -> 0.0%` from `07:51:10Z` to `09:26:23Z`), weekly quota reset (`0% -> 100%`), and Google One AI Credit overage transition (`exc-20261014-10`: `-6` credits; `exc-20261014-11`: `-120` credits) were captured and reconciled in `docs/reports/COST_UTILITY_ANALYSIS_ULTRA.md` §6:

1. **Silent 5-Hour Overage Transition (`BURNING_AI_CREDITS`)**:
   - When `gemini_5h.remainingFraction` reaches `0.0` while prepaid Google One AI Credits are available, Antigravity transitions directly to billing AI Credits without emitting a `429 RESOURCE_EXHAUSTED` log entry. `src/aggregator_quotas.py` and `src/vault.py` now detect active post-cutoff turns while `gemini_5h == 0%` and report `BURNING_AI_CREDITS`.
   - While burning AI Credits during a 5h cooldown, `gemini_weekly.remainingFraction` remains **frozen** (`98.18%` from `09:26:23Z` to `12:51:10Z`)—paid overage credits never double-deduct from the weekly pool.
2. **1:1 Equivalence Between Overage Credits and Public API Rate Card (`1 credit = $0.01 USD`)**:
   - **Gemini 3.8 Flash (`1318`) (`exc-20260920-15`)**: `203 turns` = **$5.2043** API rate card vs. **517 credits ($5.17)** debited (`99.3%` 1:1 match).
   - **Gemini 4 Argon (High) (`1417`) (`exc-20261014-11`)**: `30 turns` = **$1.0531** Intro API rate card (`$2.00/$0.10/$10.00`, or **$1.20** at `~$0.135/1M` cached) vs. **120 credits ($1.20)** debited (`~1:1` match).
3. **True Retail Compute Size of `ultra_5x` Quota Pools (`4.33 : 1` Subscription Subsidy)**:
   - **1 Full 5-Hour Gemini Burst (`100% -> 0%`)**: Consumed `474` Argon High turns + `76` Fast turns = **$22.59–$25.00** retail API spend (**2,500 AI credits** = 1 full `£23.99 / $25` credit pack), proving `config/pricing.json`'s nominal `$100.00` 5h cap was `4.0x` too high.
   - **1 Full Weekly Gemini Pool (`4 × 5h bursts`, `ratio_5h_to_weekly = 4.0000x`)**: **$100.00 / week** (**10,000 AI credits** / `£95.96`) on pure Argon (or up to **$148.50 / week** on mixed Flash/Argon), recovering **100% of the $99.99 (£79.99) monthly subscription in a single week** (`$433–$643/month` included Gemini compute = **4.33 : 1 to 6.43 : 1 subsidy**).
