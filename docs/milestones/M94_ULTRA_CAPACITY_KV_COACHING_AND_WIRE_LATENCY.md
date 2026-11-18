# Milestone 94: Ultra Capacity Calibration, Intra-Family KV Coaching, Wire Protobuf TTFT & Now-Tab Active Swarms

**Date:** 2026-10-14  
**Branch:** `feat/m93-quota-snapshot-observer-and-fast-monitor`  
**Status:** Closed  
**Related ADRs:** ADR-038, ADR-095, ADR-096, GADR-018

---

## 1. Context & Problem Statement

Following the empirical 6-model deep-context calibration (`130k`–`202k` tokens across Gemini 4 Argon `1417`–`1419` and Gemini 3.8 Flash `1318`–`1320` in conversation `454735fb-536a-49fe-9e29-1c801bb5349e`), four concrete gaps remained between our forensic findings and the live dashboard/popover telemetry stack:

1. **Outdated `ultra_5x` Quota Capacities (`4x` Inflated):** `config/pricing.json`, `src/temporal.py`, `dashboard/js/plan-manager.js`, and `dashboard/js/simulator.js` still used nominal `$100.00` (5h) / `$645.00` (weekly) limits instead of the empirical `$25.00` (`2,500` credits) / `$100.00` (`10,000` credits at the `4.0000x` weekly-to-5h Connect-RPC ratio).
2. **Blindness to Intra-Family KV Cache Evictions:** `compute_cache_coaching_metrics()` (`src/aggregator_coaching.py`) only flagged cross-provider flips (`gemini` $\leftrightarrow$ `claude_gpt`), missing 31 historical `0.0%` KV cache wipes across the Pro and Ultra eras caused by intra-family effort tier changes (`1417` $\leftrightarrow$ `1418` $\leftrightarrow$ `1419`, `1318` $\leftrightarrow$ `1319` $\leftrightarrow$ `1320`) and intra-track switches past `40k` context.
3. **Unplumbed Wire Protobuf TTFT & Latency:** `raw_metadata_blob` contained sub-millisecond request, first-token, completion, and streaming chunk timestamps across `99.9995%` of Vault rows (`steps_archive`), but `ttft_ms` and `latency_ms` were neither extracted into SQLite columns nor surfaced in the web turns table or macOS menu bar popover.
4. **Popover vs. Dashboard `Now` Tab Swarm Asymmetry:** The macOS Menu Bar popover rendered active multi-agent swarms and weakest-link context risk on its main HUD, whereas the web dashboard's `Now` tab only showed a single flat session footer.

---

## 2. Architecture & Implementation Summary

### Workstream 1: Pricing & Era Capacity Calibration
* Updated `config/pricing.json` (`subscription.quota_limits` and `subscription_history[1]` for `ultra_5x`) to `gemini_5h_capacity_usd: 25.00` and `gemini_weekly_capacity_usd: 100.00`.
* Preserved `subscription_history[0]` (`pro`, pre-`2026-09-13`) at `$20.00` / `$129.00` to keep historical September 2026 credit exhaustion ledger reconciliations exact.
* Synchronized preset constants across `src/temporal.py`, `scripts/configure_plan.py`, `dashboard/js/plan-manager.js`, and `dashboard/js/simulator.js`.

### Workstream 2: Intra-Family & Intra-Track KV Cache Coaching (GADR-018)
* Extended `src/aggregator_coaching.py` with `normalize_model_id()` and `get_model_family()` to classify mid-session model switches at $\ge 40\text{k}$ context into `cross_provider`, `intra_family`, and `intra_track` flips when cache hit ratio drops (`<20%`).
* Updated `dashboard/js/sessions.js` to render subtype breakdown pills, model transition badges (`from_model ➔ to_model`), and GADR-018 coaching guidance (lock effort tiers at Turn 1; route discovery/research subagents to `Model: "flash"`).

### Workstream 3: Wire Protobuf TTFT & Latency Pipeline
* Implemented `extract_wire_latency_ms(raw_blob)` in `antigravity_telemetry/reader.py` (re-exported via `src/telemetry_reader.py`), decoding wire protobuf timestamps (`Field 1`, `Field 6`, `Field 7`, `Field 8`, `Field 26`).
* Added `ttft_ms REAL` and `latency_ms REAL` to `steps_archive` and `v_turns` in `src/vault_schema.py`, and executed `backfill_step_latency_metrics()` across `data/antigravity_vault.db`, backfilling **104,107 historical turns** across both Pro and Ultra eras.
* Added `TTFT / Latency` and `⚡ KV Evicted (0% Hit)` badges to `dashboard/js/sessions-turns.js` and `LiveTokenTickerCard` in `macos/AntigravityBar/Sources/AntigravityBar/PopoverContentView.swift`.

### Workstream 4: Dashboard `Now` Tab Active Swarms & Weakest-Link Parity
* Added `renderNowActiveSwarms(data)` in `dashboard/js/now-burst.js` and styled `.now-active-swarms-container` in `dashboard/styles.css`, bringing full multi-agent swarm hierarchy, model badges, and weakest-link context risk parity to the `Now` tab without modifying protected `dashboard/index.html`.

### Workstream 5: `QUOTA_RESET_BONUS` Ledger Reconciliation & Oct 17 Post-Reset 6-Model Calibration
* Recorded unscheduled server-side quota flush `exc-20261017-01` (`2026-10-17T01:46:18Z`, `event_type: "QUOTA_RESET_BONUS"`, `+75.4%` Gemini weekly / `7,540` credits / `$75.40` / `£59.57` forgiven across `4,631` turns) in `data/exhaustion_ledger.json` and `log_events_archive` without deducting prepaid Google One AI Credits (`614 / 5,000` remaining) or triggering `BURNING_AI_CREDITS`.
* Updated `src/log_reader.py`, `src/aggregator_quotas.py`, `src/aggregator_windows.py`, `src/aggregator_attribution.py`, `scripts/quota_history.py`, and `dashboard/js/billing.js` (`renderHourlyCreditActivity`) to surface bonus reset events with green forgiveness badges (`+75.4% Bonus` / `+7,540 forgiven`).
* Verified post-reset burn rates across `698` turns and `25` Connect-RPC snapshots (`#208` $\rightarrow$ `#232`) spanning `1417` (`Argon High`), `1418` (`Argon Medium`), `1419` (`Argon Low`), `1318` (`3.8 Flash High`), `1319` (`3.8 Flash Medium`), and `1322` (`Fast Assistant`), documenting in `docs/reports/COST_UTILITY_ANALYSIS_ULTRA.md` §8 that:
  1. `5h : Weekly` coupling remains `4.0000x` (`1` burst = `25.00%` of weekly).
  2. All three Argon effort tiers (`1417`, `1418`, `1419`) share identical per-token weights, with the `2026-10-17T01:46:18Z` backend update reducing KV-cached input weight by `~75%` (`~$0.10/1M` $\rightarrow$ `~$0.025–$0.035/1M`, converging all three tiers within `< 1%` at `~$25.00–$30.50` per 5h window) while `1417` High burns more per turn only when generating thinking tokens.
  3. `Gemini 3.8 Flash` (`1318`–`1322`) deducts quota at `1/6x` (`0.167x`) of its API benchmark rate (`$150.00` 5h / `$600.00` weekly API-equivalent compute).

---

## 3. Verification & Acceptance Gate Proof

* **Unit Suite:** `510 / 510` tests passing (`0` failures, including `tests/test_quota_reset_bonus.py` and `tests/test_docs_integrity.py`).
* **Playwright E2E:** `5 / 5` tests passing (`e2e/dashboard-boot.spec.js`, `e2e/tree-and-swarms.spec.js`, `0` console/page errors).
* **Live Runtime Convergence:** Rebuilt `dist/AntigravityBar.app` and restarted `com.antigravity.telemetry.watcher` and `com.antigravity.menubar`; verified via `scripts/ops_check.py`.
* **Milestone 98 (ADR-096) Subprocess Exporter Crash Remediation (2026-11-09):** Eliminated no-op `vault_sync_state` writes in `sync_conversations_to_vault()`, keyed `vault_cache` on `_get_vault_logical_fingerprint()`, persisted `horizon_analytics` in `dashboard/.export_cache.db`, scoped `sync_weekly_trends_to_vault()` to active-cycle delta rows, replaced $O(N_{\text{snaps}} \times N_{\text{turns}})$ linear scans in `evaluate_vault_quota_regime()` with `bisect_right`, and enforced `busy_timeout=60000` + retry helpers in `sync_regime_events_to_vault_and_ledger()`.
