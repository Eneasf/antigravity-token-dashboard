# Milestone M20: Temporal Plan Profiles, Promotional Multipliers & Historical Provenance Engine

**Date**: 12 September 2026  
**Branch**: `feat/temporal-plan-profiles`  
**ADR**: ADR-034 — Temporal Plan Profiles, Promotional Multipliers & Historical Provenance Engine

---

## 1. Background & Problem

Prior to Milestone 20, the analytics engine operated with static configuration assumptions:
- **Static Plan Tier**: The subscription configuration was a single dictionary (`tier: "pro"`, £18.99/mo, \$20.00 5h burst, \$129.00 weekly quota). Transitioning between plans (e.g., Pro 2 TB to Enterprise 5x £49.99/mo or Ultra 10x) caused retroactive distortion of historical Avoided Cost (Plan Value ROI) and quota adherence.
- **No Promotional Multiplier Support**: Temporary capacity overlays (e.g. Google's 2-week 2x capacity promotion during developer conferences) could not be modeled without permanently altering base quota limits.
- **Static Rate Cards**: Historical turns were re-evaluated against the latest model pricing rate cards, misrepresenting historical inference costs when Google issued price cuts or rate adjustments.
- **Absence of Model Lifecycle Telemetry**: No explicit tracking of model lifecycle stages (preview, GA, sunset) to correlate performance and pricing shifts over time.

Milestone 20 delivers **ADR-034**, introducing the Unified Temporal Interval Schema, deterministic pure-Python temporal resolution engine (`src/temporal.py`), timestamp-aware turn costing and quota aggregation (`src/aggregator.py`), and an interactive Plan Profile & Promotion Manager in `dashboard/index.html`.

---

## 2. Architecture & Design Specification (ADR-034)

### A. Unified Temporal Interval Schema (`config/pricing.json`)
Maintains 100% backward compatibility with legacy consumers expecting top-level `subscription` and `models` dictionaries, while augmenting the configuration with four temporal registries:

```json
{
  "subscription": { ... },
  "subscription_history": [
    {
      "tier": "pro",
      "name": "Google One AI Premium (Pro 2 TB)",
      "monthly_fee_gbp": 18.99,
      "monthly_fee_usd": 19.99,
      "quota_limits": {
        "gemini_5h_capacity_usd": 20.00,
        "gemini_weekly_capacity_usd": 129.00,
        "claude_gpt_5h_capacity_usd": 20.00,
        "claude_gpt_weekly_capacity_usd": 100.00
      },
      "valid_from": "2026-08-01T00:00:00Z",
      "valid_to": null
    }
  ],
  "promotions": [
    {
      "id": "promo-2026-sep-boost",
      "name": "September 2026 Developer Boost (2x 5h Burst)",
      "multiplier": 2.0,
      "target_window": "5h",
      "valid_from": "2026-09-01T00:00:00Z",
      "valid_to": "2026-09-07T23:59:59Z",
      "description": "Double 5h burst allowance during Gemini 3.8 preview launch."
    }
  ],
  "rate_history": {
    "1016": [
      {
        "input_cost_per_mtok": 2.00,
        "prompt_cache_read_per_mtok": 0.20,
        "candidate_cost_per_mtok": 12.00,
        "valid_from": "2026-08-01T00:00:00Z",
        "valid_to": null,
        "reason": "Official Gemini 3.1 Pro High GA Rate Card"
      }
    ]
  },
  "availability": {
    "1318": {
      "status": "ga",
      "preview_date": "2026-07-15T00:00:00Z",
      "ga_date": "2026-08-20T00:00:00Z",
      "sunset_date": null
    }
  }
}
```

### B. Pure-Python Temporal Resolver (`src/temporal.py`)
Encapsulates all ISO 8601 interval containment logic, boundary resolution, model rate versioning, and plan presets:
- `resolve_plan(timestamp)`: Deterministically matches timestamp $t$ against `[valid_from, valid_to)` intervals. Falls back cleanly to current active plan if no interval matches.
- `get_promotions(timestamp)`: Retrieves all active promotions matching timestamp $t$.
- `get_effective_quota_limits(timestamp)`: Returns base quota limits with promotional capacity multipliers applied (e.g. 2x on 5h window yields \$40.00 capacity).
- `get_model_rates(model_id, timestamp)`: Resolves rate card revisions matching timestamp $t$, falling back to static rate table.
- `get_model_availability(model_id, timestamp)`: Resolves model lifecycle status (`preview`, `ga`, `sunset`).
- `get_plan_preset(tier)`: Generates complete plan specifications for standard tiers (`pro`, `enterprise_5x`, `ultra_10x`, `custom`).

### C. Timestamp-Aware Historical Turn Costing & Aggregator Integration (`src/aggregator.py`)
- `compute_turn_cost(turn, timestamp=ts)`: Resolves timestamp-aware model rates per turn, embedding `plan_tier` and `rates_revision` provenance directly into turn metadata.
- `compute_subagent_metrics`: Timestamp-aware costing for subagent delegated turns.
- `compute_rolling_window_telemetry` & `compute_window_recovery_trajectory`: Dynamically incorporate active promotional capacity multipliers and effective plan limits.
- `aggregate_global_telemetry`: Emits a top-level `temporal` payload containing active plan details, active promotions list, full subscription history, and available plan presets.

### D. Interactive Plan Profile & Promotion Manager (`dashboard/index.html`)
- Sited next to the hero deck quota controls with a dedicated "⚙️ Plan & Promotions" button (`#btn-open-plan-manager`).
- Accessible modal overlay (`#plan-manager-modal`) with four responsive tabs:
  1. **Plan Switcher**: Interactive tier selector (`Pro 2 TB`, `Enterprise 5x`, `Ultra 10x`, `Custom`), effective date scheduler (`valid_from`), dynamic quota inputs, and direct configuration save.
  2. **Promotions Manager**: List of active and upcoming capacity multipliers, with an interactive "Add Promotion" dialog.
  3. **Rate History & Availability**: Searchable table displaying model lifecycle status (GA, Preview, Sunset) and historical price cuts.
  4. **Config JSON Sync**: Instant copy-to-clipboard and download interface for updated `config/pricing.json`.

---

## 3. Deliverables Summary

| Component | File | Description |
|---|---|---|
| **Configuration Schema** | `config/pricing.json` | Augmented with `subscription_history`, `promotions`, `rate_history`, and `availability`. |
| **Temporal Engine** | `src/temporal.py` | Standalone deterministic temporal resolver module with interval containment and plan presets. |
| **Unit Test Suite** | `tests/test_temporal.py` | 8 dedicated unit tests verifying interval resolution, multipliers, rate revisions, and fallbacks. |
| **Aggregator Integration** | `src/aggregator.py` | Timestamp-aware turn costing, provenance metadata, dynamic rolling window capacities, and payload export. |
| **Integration Test** | `tests/test_aggregator.py` | Added `test_temporal_turn_costing_and_plan_provenance` verifying end-to-end historical evaluation. |
| **UI Surface & Controller** | `dashboard/index.html` | Plan Profile & Promotion Manager modal, 4-tab interface, dynamic DOM bindings, and JSON synchronization. |
| **Acceptance Gates** | `VDONE.md` | Defined and verified acceptance gates V82 through V87 with measured PROOF records. |

---

## 4. Verification Commands & Results

```bash
# V82: Unified Temporal Interval Schema & Backward Compatibility
python3 -c "import json; p=json.load(open('config/pricing.json')); assert 'subscription_history' in p and len(p['subscription_history']) >= 1; assert 'promotions' in p; assert 'rate_history' in p; assert 'availability' in p; assert p['subscription']['tier'] == 'pro'; print('Verified: Unified temporal interval schema and backward compatibility intact.')"
# Verified: Unified temporal interval schema and backward compatibility intact.

# V83: Temporal Pricing & Plan Resolver Unit Tests (tests/test_temporal.py)
python3 -m unittest tests.test_temporal
# Ran 8 tests in 0.003s — OK

# V84: Timestamp-Aware Turn Cost & Plan Provenance Aggregation
python3 -m unittest tests.test_aggregator.TestAggregator.test_temporal_turn_costing_and_plan_provenance
# Ran 1 test in 0.007s — OK

# V85: Plan Profile & Promotion Manager Modal DOM & Dynamic Controller
python3 -c "c=open('dashboard/index.html').read(); ids=['plan-manager-modal', 'btn-open-plan-manager', 'plan-tier-select', 'plan-effective-date', 'btn-save-plan', 'promotions-list', 'btn-add-promo', 'rate-history-table']; assert all(i in c for i in ids); print('Verified: Plan Profile and Promotion Manager modal DOM elements present.')"
# Verified: Plan Profile and Promotion Manager modal DOM elements present.

# V86: Full Regression & Integration Test Suite Integrity
python3 -m unittest discover -s tests
# Ran 88 tests in 1.061s — OK

# V87: Live Decoupled Telemetry Export with Temporal Provenance (data.js)
python3 -c "import json, re; c=open('dashboard/data.js').read(); d=json.loads(re.search(r'window\.__TELEMETRY_DATA__\s*=\s*(.*);', c, re.DOTALL).group(1)); assert 'temporal' in d or 'subscription_history' in d['summary']; print('Verified: Decoupled telemetry payload includes temporal plan profiles and provenance.')"
# Verified: Decoupled telemetry payload includes temporal plan profiles and provenance.
```
