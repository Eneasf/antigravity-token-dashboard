# Milestone 92: Gemini 4 Argon Frontier Model Census & Two-Era Pricing

**Date**: 2026-10-13
**Scope**: Model Census Expansion (Gemini 4 Argon High/Medium/Low `1417`–`1419`), Two-Era Rate History, Compaction Threshold Calibration, and Backward-Compatible Sunsetting of Gemini 3.1 Pro (`1016`, `1036`) (ADR-093)
**Branch**: `feat/m92-gemini-4-argon-model-census`
**Verdict**: **PASS**

---

## 1. Overview & Context

This milestone integrates **Gemini 4 Argon** across all three reasoning effort levels (`High`, `Medium`, `Low`) into the Antigravity Telemetry engine, canonical model census, temporal pricing engine, and dashboard.

Key architectural and calibration decisions (ADR-093):
- **29-Model Canonical Census**: Expands `antigravity_telemetry/models.json` and `config/pricing.json` from 26 to 29 calibrated models.
- **Wire Telemetry Calibration (`GetUserStatus` Connect-RPC & Step Metadata)**:
  - `1417` (`MODEL_PLACEHOLDER_M417`, `gemini-4-argon-high`): **Gemini 4 Argon (High)**
  - `1418` (`MODEL_PLACEHOLDER_M418`, `gemini-4-argon-medium`): **Gemini 4 Argon (Medium)**
  - `1419` (`MODEL_PLACEHOLDER_M419`, `gemini-4-argon-low`): **Gemini 4 Argon (Low)**
- **New Model Family (`gemini-argon`)**: Assigned to `"family": "gemini-argon"` (`"provider": "google"`), routing to the `"gemini"` provider quota track and `"pro"` subagent architecture tier.
- **Two-Era Temporal Pricing Schedule**:
  - **Introductory Era (`2026-10-13T00:00:00Z` to `2026-11-30T23:59:59Z`)**: `$2.00` / 1M uncached input, `$0.10` / 1M cached input, `$10.00` / 1M output (`15.0` credits/turn base).
  - **Standard Era (`2026-12-01T00:00:00Z` onwards)**: `$4.00` / 1M uncached input, `$0.20` / 1M cached input, `$20.00` / 1M output.
- **Context Window & Empirical Compaction Threshold**:
  - `context_truncation_tokens`: `1,000,000` (1M context window).
  - `compaction_threshold_tokens`: `250,000` (matching Gemini 3.8 Flash; empirically verified across two live `1417` sessions: session `63482d2a` triggered its first `<CONTEXT_SUMMARY>` compaction at step `149` with `depth_at_truncation = 241,091` tokens, and session `5feed114` triggered its first compaction at step `139` with `depth_at_truncation = 255,730` tokens).
- **Backward-Compatible Sunsetting of Gemini 3.1 Pro**:
  - `1016` (`Gemini 3.1 Pro (High)`) and `1036` (`Gemini 3.1 Pro (Low)`) are marked `"status": "deprecated"`, `"sunset_date": "2026-10-13"` in `antigravity_telemetry/models.json` and `"status": "sunset"`, `"sunset_at": "2026-10-13T00:00:00Z"` in `config/pricing.json` without `superseded_by` coupling, preserving 100% of historical telemetry.

---

## 2. Changes Implemented

- **`antigravity_telemetry/models.json` & `antigravity_telemetry/__init__.py`**:
  - Added models `1417`, `1418`, and `1419` under `"family": "gemini-argon"` with `1000000` truncation and `250000` compaction thresholds.
  - Marked `1016` and `1036` as `"status": "deprecated"` with `"sunset_date": "2026-10-13"`.
  - Updated `get_model_compaction_threshold` family fallback to include `"argon"`.
- **`config/pricing.json` & `config/pricing.sample.json`**:
  - Registered `1417`–`1419` under `models`, added two-era `rate_history` entries (`2026-10-13` introductory vs `2026-12-01` standard), and updated `availability` (`1016`/`1036` sunset; `1417`–`1419` GA).
- **`src/swarm.py`**:
  - Registered `1417`, `1418`, `1419`, `gemini-argon`, and `argon` under the `"pro"` subagent architecture tier.
- **`dashboard/js/plan-rates.js`, `dashboard/js/sessions-filters.js`, `dashboard/js/simulator.js`, `dashboard/index.html`**:
  - Added `1417`–`1419` to `MODEL_TAXONOMY`, `explicitRanks`, truncation/compaction helpers, `SIM_MODEL_RATES`, and `#sim-model-select` (marking `1016`/`1036` with `(Sunset 2026-10-13)`).
  - Updated `renderRateHistoryTable` to distinguish `SCHEDULED` future pricing eras from `ACTIVE` eras.
- **Tests & Golden Baseline**:
  - Updated `tests/test_model_roster_integrity.py`, `tests/test_truncation_thresholds.py`, `tests/test_antigravity_telemetry_pkg.py`, and regenerated `tests/fixtures/aggregator_baseline_data.json`.

---

## 3. Empirical Subagent Model Routing Verification (`invoke_subagent`)

Four single-turn read-only subagent probes were dispatched from parent session `5feed114` (`1417` `Gemini 4 Argon (High)`) to verify how the Antigravity Language Server routes `invoke_subagent` `Model` tiers following the sunset of `Gemini 3.1 Pro` (`1016`, `1036`):

| Requested `Model` | Probe Session ID | Historical Wire ID (`ADR-020`) | Live Wire `model_id` (2026-10-13) | Resolved Model Name | Turn 1 Telemetry |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`"inherit"`** | `6c4e2cba` | Parent model | **`1417`** | **Gemini 4 Argon (High)** | `in=14,944`, `out=444`, `think=360` |
| **`"pro"`** | `832c88c7` | `1036` (`Gemini 3.1 Pro (Low)`) | **`1322`** | **Gemini Fast Agent Assistant** (`Gemini 3.8 Flash (Low)`) | `in=15,282`, `out=1,236`, `think=1,230` |
| **`"flash"`** | `52a0b8a2` | `1322` (`Gemini 3.8 Flash (Low)`) | **`1322`** | **Gemini Fast Agent Assistant** (`Gemini 3.8 Flash (Low)`) | `in=15,286`, `out=1,726`, `think=1,720` |
| **`"flash_lite"`** | `9f3e814b` | `1050` (`Gemini 3.1 Flash Lite`) | **`1198`** | **Gemini Flash Lite Gen 2 (Adaptive Thinking)** | `in=15,285`, `out=76`, `think=0` |

- **Key Orchestration Finding**: Following the sunset of `1036` (`Gemini 3.1 Pro (Low)`), the upstream Language Server remapped `Model="pro"` to `1322` (`Gemini 3.8 Flash (Low)`), matching `Model="flash"`. Meanwhile, `Model="flash_lite"` upgraded from `1050` to `1198` (`Gemini Flash Lite Gen 2 (Adaptive Thinking)`). To execute a subagent on **Gemini 4 Argon (`1417`–`1419`)**, orchestrators must pass **`Model="inherit"`**.
