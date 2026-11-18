# Principal Architecture, UX & Runtime-Alignment Review (Nov 2026)

> **Scope:** Backend (`src/`, `antigravity_telemetry/`, `scripts/`, `config/`), Web Dashboard (`dashboard/`), and Native macOS Menu Bar Popover (`macos/AntigravityBar/`).
> **Methodology:** Cold-eyes 4-pillar `/swarm` investigation (`schema-and-flexibility`, `agy-findings-backend`, `web-frontend-ux`, `macos-popover`) followed by an adversarial `challenger` pass (`EVIDENCED` / `GUESSED` / `CONTRADICTED`) enforcing the Cut Proof.

---

## 1. Executive Verdict & Top-Tier Highest-Leverage Moves

The protobuf decoding engine and SQLite vault foundation are solid, capabilities-wise, yet four systemic fractures have accumulated across rapid iterative additions:

1. **Five-Way Model & Rate Split-Brain:** Model IDs, display names, provider tracks, plan capacities, and simulator rates are duplicated across five desynchronized stores (`antigravity_telemetry/models.json`, `config/pricing.json`, `dashboard/js/plan-rates.js`, `config/pricing.sample.json`, and `dashboard/js/simulator.js`). While `models.json` registers Claude 5.5 (`1400`–`1405`), `pricing.json` omits `credits_per_turn` on those entries (silently charging fallback credits), and UI copy, simulator presets, and swarm classifiers remain pinned to sunset Claude 4.6 (`1026`/`1035`) and Gemini 3.1 Pro (`1016`/`1036`).
2. **Pre-Nov-2026 Antigravity Runtime Blindness:** Subagent classification relies on a static `SUBAGENT_MODEL_IDS` set (`src/aggregator_pricing.py`), misclassifying all `Model: "inherit"` (`Carbon`/`Argon`) subagents and all Native `/swarm` workers (`1318`/`1320`/`1418`) as interactive user turns. Modern tools (`read_file`, `write_file`, `edit_file`, `swarm`, `post_message`, `read_board`, `swarm_wait`) fall into `"other"` in `src/tool_analytics.py` and bypass file-churn detection.
3. **Silent Vault Log Corruption & Daemon Tree-Dirtying:** `src/log_archiver.py` inserts `timestamp_iso` without `timestamp`, leaving 96.5% of rows in `log_events_archive` with `timestamp IS NULL`. Meanwhile, background exports rewrite `turns_analyzed` on already-`CONFIRMED` rows in tracked `data/quota_regime_ledger.json`.
4. **Above-the-Fold Redundancy & Swift Prose-Scraping Debt:** On desktop (`1440x900`), `Now` stacks 2,821 px (3.5 viewports; 6,401 px on mobile) of quota cards repeating the 5h limit six times and surfacing conflicting status badges before the first chart. In `macos/AntigravityBar/`, `PopoverContentView.swift` mutates English sentences with 22 `.replacingOccurrences` and regex rules, lacks a `ScrollView` (~862 pt worst-case height), and wires `⌘R` to `store.loadStatus()` instead of `store.refreshNow()`.

### Ranked Execution Moves

| Rank | Priority | Architectural / UX Move | Net Structural Effect |
| :---: | :---: | :--- | :--- |
| **1** | **P0** | **Schema-Driven Catalog & Dynamic `quota_tracks[]` SSOT** (`models.json` v2 + `pricing.json` v2 -> `window.__TELEMETRY_DATA__.catalog` & status hook v2 `tracks[]`) | Zero-code model/track/sunset updates; deletes 7 duplicated lookup tables across Python, JS, HTML, and Swift |
| **2** | **P0** | **`Now` View Bento Consolidation (`2,821 px -> ~338 px` to Chart #1)** | Deletes `#dual-provider-quotas-section` and `#exec-velocity-strip`; extracts `#now-active-swarms` into a compact Bento pulse tile |
| **3** | **P0** | **First-Class Native `/swarm` + `Model: "inherit"` Attribution & Turn-1 Ambient Tax** | Ingests `.system_generated/swarm/members.json` + `tool_name="swarm"`; separates `monitor`/`narrator` overhead; surfaces Turn-1 ambient prompt weight (`GADR-028`/`031`) |
| **4** | **P0** | **Vault `LogArchiver` Schema Fix + Idempotent SQL Self-Heal + Frozen `CONFIRMED` Regime Ledger** | Restores `NULL`-timestamp 429 log rows in `log_events_archive`; stops live daemon exports from dirtying `git status` |
| **5** | **P1** | **`AntigravityBar` v2 Contract + `⌘R`/Spinner Fix + `ScrollView` + Watcher Re-Arm** | Deletes all 22 Swift string-scraping replacements; syncs `tracks[]` in both heavy and 1s `export_fast_tier()`; fixes `⌘R`, adds spinner & `ScrollView(maxHeight: 680)` |
| **6** | **P1** | **Calibrated Quota Burn Weights + Discrete 5h/Weekly Epoch Alignment + Live `GetUserStatus`** | Decouples quota burn from retail API Dec 1 rate doubling (`ADR-095`/`097`); aligns 5h/weekly windows to live RPC `resetTime`; fetches live tier & AI credit balance |
| **7** | **P1** | **Exporter Incremental Horizon Cache** | Caches completed pre-`active_week` buckets in `vault_sync_state` instead of scanning the entire historical `v_turns` archive in Python on every export |
| **8** | **P1** | **Commercial Telemetry Visual & Chart Polish** | Semantic CSS tokens (`--surface-*`, `--accent-*`, `--status-*`), emoji/SSR placeholder purge, `ResizeObserver` SVG viewBox, proportional epoch X-axis, right-aligned `tabular-nums` tables |
| **9** | **P2** | **Frontend Runtime Hygiene, Referential Test Gates & `?demo=1` Guard** | Preserves DOM state on 3s micro-polls, adds drawer focus trap & `file://` reload safety, skips loading live `data.js` in `?demo=1`, upgrades roster tests to referential integrity |

---

## 2. Reconciled v2 Schemas (`models.json`, `pricing.json`, `catalog`, `status_hook`)

1. **`antigravity_telemetry/models.json` (`_schema_version: 2`):**
   - Retains strict zero-pricing package isolation while adding `_defaults`, `_families` (`display_name`, `short_name`, `horizon_key`, `track_id`, `chart_color`, `sort_order`), and complete per-model metadata (`name`, `short_badge`, `taxonomy_name`, `reasoning_label`, `family`, `provider`, `track_id`, `reasoning_effort`, `wire_aliases`, `context_truncation_tokens`, `compaction_threshold_tokens`, `is_subagent`, `subagent_tier`, `swarm_tier`, `generation`, `sort_rank`, `status`, `available_from`, `sunset_date`).
   - `load_model_census()` ignores `_`/`$` keys for full backward compatibility; `load_model_catalog()` returns `{models, families, defaults}`.
2. **`config/pricing.json` & `config/pricing.sample.json` (`schema_version: 2`):**
   - Defines `quota_tracks[]` (`id`, `name`, `short_name`, `icon`, `is_primary`, `credit_spillover`, `badge_text`, `rpc_bucket_patterns`, `windows`, `capacity_keys`), `plan_tiers`, `simulator_archetypes[]` (upgraded to `1427`, `1402`, `1198`), `rates_per_million`, `quota_weights_per_million`, and `credits_per_turn` across every canonical model.
3. **`data.js` (`window.__TELEMETRY_DATA__.catalog`):**
   - Exported by `scripts/export_dashboard.py` and accessed via `getCatalog()` in `dashboard/js/core-utils.js`, allowing deletion of `MODEL_TAXONOMY`, `explicitRanks`, `presets`, `ARCHETYPE_PRESETS`, `SIM_MODEL_RATES`, and `SIM_PLAN_CAPACITIES`.
4. **`~/.antigravity_quota_status.json` (`schema_version: 2`):**
   - Emits `generated_at_epoch`, `plan: { tier_id, name, badge, credit_pool, credits_remaining, credit_balance_gbp }`, and `tracks: [{ id, name, short_name, icon, is_primary, credit_spillover, windows: [{ window_id, label, icon, used_pct, remaining_pct, used_tokens, reset_utc, reset_epoch, is_cooldown, severity, bvi, bvi_status, bvi_pacing_pct, bvi_label }] }]` in **both** `write_quota_status_file()` and `export_fast_tier()`, while retaining all v1 flat keys.

---

## 3. AGY Runtime & Backend Alignment Summary

- **Native `/swarm` Lineage & Overhead (`antigravity_telemetry/parser.py`, `src/vault.py`, `src/swarm.py`):** Extract `tool_name == "swarm"` (`add`, `model`, `kill`, `fork`, `workspace`), read `.system_generated/swarm/members.json` + protobuf `trajectory_metadata_blob` (`Field 5 parent_convo_id`) before `sender=` fallback regexes, tag `topology_mode` (`"native_swarm"` vs `"star_subagent"`), and separate `monitor`/`narrator` infrastructure overhead from productive slice workers.
- **Turn-1 Ambient Prompt Weight (`src/vault_schema.py`, `src/swarm.py`, `src/aggregator_coaching.py`):** Track `turn1_input_tokens` and `turn1_cached_tokens` from the first `step_type = 15` turn per session (`GADR-028`/`031`).
- **Subagent & Tool Classification (`src/aggregator_pricing.py`, `src/tool_analytics.py`, `src/aggregator.py`):** Classify subagent turns using `turn.get("is_subagent")` and conversation metadata alongside `is_subagent` catalog flags; register `read_file`, `write_file`, `edit_file`, `swarm`, `post_message`, `read_board`, `swarm_wait`, `schedule`, and `manage_task`.
- **Quota Epoch, Weight & `GetUserStatus` Precision (`src/quota_client.py`, `src/aggregator_quotas.py`, `src/aggregator_cycles.py`):** Bound 5h token counts by discrete reset epochs (`ADR-082`), fix `burst_seconds_remaining` (`reset_dt - now`), derive per-track weekly cycle bounds with updated `days_elapsed`/`remaining_seconds`, decouple quota burn from Dec 1 retail API rate doubling via `quota_weights_per_million`, add `<0.5 ms` empirical bootstrap `[P10, P50, P90]` runway over `v_quota_burn_intervals`, and query Connect-RPC `GetUserStatus` for live tier & credit balances.
- **Vault Self-Heal & Exporter Speed (`src/log_archiver.py`, `src/vault_schema.py`, `src/quota_regime.py`, `src/horizon_analytics.py`):** Fix `LogArchiver` column mapping + local timezone parsing, backfill `timestamp = timestamp_iso` where `NULL`, freeze `CONFIRMED` regime ledger rows, and cache completed pre-`active_week` horizon buckets.

---

## 4. Web Dashboard & macOS `AntigravityBar` Redesign Summary

- **Web Dashboard (`dashboard/`):** Replace the 4-layer top stack on `Now` with a dynamic `quota_tracks[]` Executive Bento + compact Swarm & Runway Pulse tile (`y ~ 338 px` to first chart); replace `--camel-500`/`--espresso-900` with semantic `--surface-*`/`--accent-*`/`--status-*` tokens (keeping a compact legacy alias block); remove consumer emojis and stale SSR text; fix `#sim-trajectory-svg` `preserveAspectRatio="none"` text stretching, proportional epoch X-axes, zero-burn series clutter, and right-aligned `tabular-nums` numeric columns; preserve DOM state across 3s micro-polls, add `#desktop-inspector-drawer` focus trap + `Escape` menu close + `#tab-*` hash routing, skip live `data.js` download in `?demo=1`, and strip `?t=` on `file://` reloads while keeping all `dashboard/js/*.js` files under the 800-line ceiling (`ADR-066`).
- **macOS Popover (`macos/AntigravityBar/`):** Decode v2 `tracks[]` and `plan` with v1 fallback, delete all 22 English string-scraping replacements in `PopoverContentView.swift`, move AI Credits off the hard-stop `claude_gpt` track, wire `⌘R` and a new header spinner button to `store.refreshNow()`, wrap body in `ScrollView(maxHeight: 680)` with `.ultraThinMaterial` and a `10pt`/`11pt` typography floor, re-arm file watching cleanly across `ENOENT`/atomic renames, and format `#tab-*` deep-links safely via URL string concatenation.

---

## 5. Three-Wave Zero-Collision Execution Topology

1. **Wave 1 (`catalog-foundation`):** `antigravity_telemetry/{models.json, __init__.py, parser.py}`, `config/{pricing.json, pricing.sample.json}`.
2. **Wave 2 (4 Disjoint Parallel Scopes):**
   - `2A (src/* + docs/{FINDINGS,DATA_DICTIONARY}.md + data/quota_regime_ledger.json)`
   - `2B (scripts/*)`
   - `2C (dashboard/*)`
   - `2D (macos/AntigravityBar/*)`
3. **Wave 3 (`gates-and-merge`):** `tests/test_*.py`, `e2e/*.spec.js`, `docs/REPO_MAP.md`, `VDONE.md` verification (`fail_first.py --verdict`, `swift test`, Playwright suite).
