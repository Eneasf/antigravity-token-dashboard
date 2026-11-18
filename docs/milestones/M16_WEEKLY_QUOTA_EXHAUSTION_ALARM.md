# Milestone M16: Empirical Weekly Quota Exhaustion, Triad Alarm States & Subagent Partitioning

**Date**: 8 September 2026  
**Branch**: `feat/weekly-quota-exhaustion`  
**ADR**: ADR-028 — Empirical Weekly Quota Exhaustion, 5-Hour Subsumption & Claude/GPT Fallback

---

## 1. Background & Evidence

On Tuesday 8 September 2026, the first empirical **Weekly Quota Exhaustion Event** was observed across all Gemini models. Google's upstream Connect-RPC `RetrieveUserQuotaSummary` endpoint returned `remainingFraction: 0.0` when the total accumulated Gemini API rate-card value reached **$129.07 USD** within the Thursday-to-Thursday weekly cycle.

### Key Observations
- **Capacity Calibration**: Weekly Gemini quota capacity recalibrated from $133.00 → **$129.00 USD** (99.9% convergence with upstream indicator).
- **5-Hour Subsumption**: When weekly limit exhausts, the 5-hour rolling burst window is automatically superseded/disabled by Google's server — burst headroom becomes irrelevant.
- **Track 2 Independence**: Claude and GPT models continue operating independently at 94.7% available weekly capacity with zero cross-track contamination (ADR-019).
- **Saturday Surge**: A single-day burn on Saturday consumed 39.6% of the weekly budget, identified as the primary contributor to exhaustion.

---

## 2. Deliverables

### Configuration
- **`config/pricing.json`**: `gemini_weekly_capacity_usd` updated from `133.00` to `129.00`.

### Backend Engine (`src/aggregator.py`)
1. **`SUBAGENT_MODEL_IDS`** — Constant set `{1050, 1322, 1132, 1301}` identifying autonomous subagent model IDs.
2. **`classify_turn_type(turn)`** — Classifies turns as `'interactive'` or `'subagent'`.
3. **`compute_subagent_metrics(flat_turns, pricing_models)`** — Aggregate metrics (turn count, total tokens, imputed cost, quota share %) partitioned between interactive and subagent.
4. **`compute_exhaustion_alarm_state(...)`** — Detects weekly exhaustion (`remaining_pct ≤ 0.1`), 5h burst subsumption, and Claude/GPT fallback readiness (`remaining > 50%`).
5. **`compute_daily_velocity(turns, cycle_start, ...)`** — Calendar-day bucketing within weekly cycle with >25% anomaly flagging.
6. **Integration** — `subagent_metrics` added to `summary`, `exhaustion_alarm` to `providers.gemini`, `daily_velocity` to `quotas`.

### Visual Dashboard (`dashboard/index.html`)
- **Card 1 (Gemini)**: Dynamic `⚠️ EXHAUSTED (0%)` badge in red, weekly pct color override, disabled 5h burst with `DISABLED / SUPERSEDED` text and muted progress fill.
- **Card 2 (Claude/GPT)**: `💡 ACTIVE FALLBACK` callout with available percentage, visible only when Gemini exhausted and Track 2 > 50%.
- **Card 3 (Recovery Timeline)**: `⏸ Quota Paused` badge and footer notice explaining 5h age-out continues but Gemini locked until reset.
- **Model Section**: Interactive vs. Subagent breakdown pills: `[ All | 💬 Interactive | 🤖 Subagents ]`.

### Unit Tests (`tests/test_aggregator.py`)
- `test_subagent_turn_partitioning` — Classification for 7 model IDs and metric computation.
- `test_weekly_exhaustion_detection` — 3 scenarios: exhausted+fallback, healthy, exhausted+Claude-low.
- `test_daily_velocity_bucketing` — Day grouping, cycle boundary filtering, anomaly detection.

### Supporting Test Fix (`tests/test_quota_client.py`)
- Updated `test_aggregator_cost_weighted_offline_fallback` assertions from $133.00 → $129.00 with recalculated percentages.

---

## 3. Verification Commands & Results

```bash
# V64: Pricing Calibration
python3 -c "import json; p=json.load(open('config/pricing.json')); assert p['subscription']['quota_limits']['gemini_weekly_capacity_usd'] == 129.00; print('[PASS] Weekly capacity calibrated to \$129.00')"
# [PASS] Weekly capacity calibrated to $129.00

# V65: Subagent Turn Partitioning
python3 -m unittest tests.test_aggregator.TestAggregator.test_subagent_turn_partitioning
# OK

# V66: Weekly Exhaustion Detection
python3 -m unittest tests.test_aggregator.TestAggregator.test_weekly_exhaustion_detection
# OK

# V67: Daily Velocity Bucketing
python3 -m unittest tests.test_aggregator.TestAggregator.test_daily_velocity_bucketing
# OK

# V68: Dashboard DOM Elements
python3 -c "c=open('dashboard/index.html').read(); ids=['gemini-exhaustion-badge', 'claude-fallback-callout', 'claude-fallback-pct', 'timeline-paused-notice', 'timeline-paused-reset', 'pill-all-turns', 'pill-interactive', 'pill-subagent']; assert all(f'id=\"{i}\"' in c for i in ids); print('Verified: All M16 DOM elements present.')"
# Verified: All M16 DOM elements present.

# V69: Full Regression Suite
python3 -m unittest discover -s tests
# Ran 78 tests in 1.086s — OK
```

---

## 4. Model ID Taxonomy Recap

| Classification | Model IDs | Family |
|---|---|---|
| **Interactive Desktop** | 1318, 1319, 1320, 1298, 1299, 1300, 1071, 1072, 1073, 1016, 1036, 1035, 1026, 342, 1020 | gemini-flash, gemini-pro, claude-*, gpt-* |
| **Autonomous Subagent** | 1050 (Flash Lite), 1322 (Fast Agent Assistant), 1132 (Legacy Agent), 1301 (Experimental Agent) | gemini-flash-lite, gemini-flash |
