# Milestone 89: Claude 5.5 Model Census Expansion & Reasoning Taxonomy

**Date**: 2026-10-03
**Scope**: Model Census Expansion (Claude Opus 5.5 & Sonnet 5.5), Backward-Compatible Sunsetting of Claude 4.6 (ADR-086)
**Branch**: `feat/m89-claude-55-model-census-expansion`
**Verdict**: **PASS**

---

## 1. Overview & Context

This milestone formally integrates the newly released **Claude Opus 5.5** and **Claude Sonnet 5.5** models with **three reasoning effort levels (Low, Medium, High)** into the Antigravity Telemetry engine, model census, and dashboard.

Following strict backward-compatibility and telemetry preservation principles:
- **Zero Loss of Historical Data**: Existing Claude Opus 4.6 (`1026`) and Claude Sonnet 4.6 (`1035`) records, vault entries, and rate calculations are 100% preserved.
- **Availability Sunsetting**: Models `1026` and `1035` are documented and marked as `sunset` / `deprecated` with `sunset_date: "2026-10-03"` and `superseded_by` links pointing to the new 5.5 tiers.
- **26-Model Canonical Census**: Expands the canonical ground-truth census from 20 to 26 models in `antigravity_telemetry/models.json` and `config/pricing.json`.
- **Wire Telemetry Calibration**:
  - `1400`: **Claude Opus 5.5 (Low)**
  - `1401`: **Claude Opus 5.5 (Medium)**
  - `1402`: **Claude Opus 5.5 (High)**
  - `1403`: **Claude Sonnet 5.5 (Low)**
  - `1404`: **Claude Sonnet 5.5 (Medium)**
  - `1405`: **Claude Sonnet 5.5 (High)**
- **Dynamic Quota Silo Routing**: Models `1400`–`1405` are automatically recognized by `get_provider_quota_track` and routed into the separate `claude_gpt` quota track.
- **Threshold Invariants**: Configured with 200,000 context truncation limit and 80,000 empirical compaction threshold.

---

## 2. Changes Implemented

- **`antigravity_telemetry/models.json`**:
  - Preserved `1026` and `1035` with `"status": "deprecated"`, `"sunset_date": "2026-10-03"`, and `"superseded_by"`.
  - Added models `1400`–`1405` with canonical names, reasoning levels (`low`, `medium`, `high`), `"status": "active"`, `"available_from": "2026-10-03"`, and `"supersedes"` references.
- **`config/pricing.json` & `config/pricing.sample.json`**:
  - Registered official rate cards for `1400`–`1405` under `models`.
  - Updated `availability` registry marking `1026` and `1035` as sunset as of `2026-10-03T00:00:00Z` and activating `1400`–`1405` as GA.
- **`dashboard/js/plan-rates.js`**:
  - Added `1400`–`1405` to `MODEL_TAXONOMY` and `explicitRanks`.
- **`dashboard/js/sessions-filters.js`**:
  - Added `1400`–`1405` to `claudeModels` and `proClaudeModels`.
- **`dashboard/js/simulator.js`**:
  - Added `1400`–`1405` to `SIM_MODEL_RATES`.
- **`dashboard/index.html`**:
  - Updated `#sim-model-select` dropdown with options for `1400`–`1405` while retaining `1026` and `1035` with `(Sunset 2026-10-03)` labels.
- **`tests/test_model_roster_integrity.py`**:
  - Updated Gate V136 to assert the 26-model census count and exact taxonomy for Claude 5.5 and deprecated 4.6 models.
- **`tests/test_antigravity_telemetry_pkg.py`**:
  - Updated package census test and CLI `models --json` test to assert 26 models.
- **`tests/test_truncation_thresholds.py`**:
  - Updated census count to 26 and verified 200k truncation / 80k compaction thresholds across all 6 new Claude 5.5 models.
- **`README.md`**:
  - Updated architecture catalog count from 20 to 26 models.
