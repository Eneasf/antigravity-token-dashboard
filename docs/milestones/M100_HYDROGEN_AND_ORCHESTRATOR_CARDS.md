# Milestone 100: Gemini 4 Hydrogen & Dual Orchestrator Model Cards

**Date**: 2026-11-14
**Scope**: Model Census Expansion (`1525`–`1528` Gemini 4 Hydrogen High/Med/Low/XHigh, `1667` Orchestrator Carbon, `1681` Orchestrator Argon, `1669` Orchestrator Executor Hydrogen), Family Taxonomy (`gemini-hydrogen`, `gemini-orchestrator`), Phase 1 & Phase 2 Connect-RPC Quota Calibration (`1/6x` Hydrogen & `1669` Executor, `0.50x` Orchestrator Planners), Dashboard XHigh & Orch Exec UI Support (ADR-098)
**Branch**: `feat/hydrogen-and-orchestrator-cards`
**Verdict**: **PASS**

---

## 1. Overview & Architecture Decisions (ADR-098)

This milestone expands the canonical census from 33 to 40 internal Antigravity model registrations by onboarding **Gemini 4 Hydrogen** (`Low`, `Medium`, `High`, `XHigh`), both **Orchestrator** planners (`Carbon` and `Argon`), and the **`1669` Orchestrator Executor (Hydrogen)** discovered via Phase 2 live probes, plus semantic design-token badges, `XHigh` reasoning resolution, and documented Phase 1/2 Connect-RPC benchmarks.

Key decisions ratified in **ADR-098**:
- **Distinct Model Families for KV-Cache Isolation**:
  - `gemini-hydrogen` (`1528` XHigh, `1525` High, `1526` Medium, `1527` Low): `1,000,000` context truncation, `250,000` compaction threshold (`step_type = 23` verified across `bb66a4a6`, `ad6e818a`, and `3542221f`), `swarm_tier = "engineering"`, `subagent_tier = "inherit"`.
  - `gemini-orchestrator` (`1667` Orchestrator (Carbon), `1681` Orchestrator (Argon), `1669` Orchestrator Executor (Hydrogen)): `is_subagent = false`, `1,000,000` context truncation, `250,000` compaction threshold, `swarm_tier = "architecture"` on `1667`/`1681` planners vs `"engineering"` on `1669` executor, `subagent_tier = "inherit"`.
  - Both checks check `"orchestrator"` before `"carbon"` / `"argon"` / `"hydrogen"` in `src/horizon_analytics.py` (`classify_model_family`), `src/aggregator_coaching.py` (`get_model_family`), `dashboard/js/plan-rates.js` (`getModelSortRank`), and `dashboard/js/now-burst.js` (`resolveModelBadge`) so Orchestrator planner and executor IDs never misclassify as base Carbon, Argon, or Hydrogen.
- **Quota Weight & API Benchmark Rates (Phase 1 + Phase 2 Connect-RPC Verified `<= 0.02%`)**:
  - **Hydrogen (`1525`–`1528`) & `1669` Orchestrator Executor**: `$0.25 / $0.0125 / $1.25` per 1M tokens (`1/6x` of `$1.50 / $0.075 / $7.50` API rate; `5.0` credits/turn base). Reconciles `#3607` $\rightarrow$ `#3611` (`1525` + `1322`), `#3623` $\rightarrow$ `#3624` (`1528`: `$0.02993` pred vs `$0.02993` obs, `0.00%`), `#3627` $\rightarrow$ `#3628` (`1525`: `$0.02432` vs `$0.02431`), `#3629` $\rightarrow$ `#3630` (`1527`: `$0.02196` vs `$0.02196`), `#3637` $\rightarrow$ `#3638` (`1526`: `$0.02341` pred vs `$0.02341` obs `Δ5h` / `$0.02342` `Δwk`, `0.00%`), `#3624` $\rightarrow$ `#3625` (`1667`+`1669`: `$0.09555` vs `$0.09555`), and `#3625` $\rightarrow$ `#3626` (`1681`+`1669`: `$0.04850` vs `$0.04849`). All 4 Hydrogen tiers (`1525`–`1528`) verified.
  - **Orchestrator Planners (`1667` / `1681`)**: `$1.00 / $0.050 / $5.00` per 1M tokens (`0.5000x` of `$2.00 / $0.10 / $10.00` Carbon/Argon Intro API baseline; `15.0` credits/turn base); `exit_plan_mode` delegates execution to `1669` (`1/6x`), `enter_plan_mode` returns to planner reusing warm KV prefix (`27,686` tok), and `invoke_subagent(Model="inherit")` inherits planner `1667` (`$0.10199`) rather than `1669` (`092ea829`, `$0.24202` vs `$0.24202` obs).

---

## 2. Changes Implemented

- **`antigravity_telemetry/models.json` & `config/pricing.json` / `config/pricing.sample.json`**:
  - Added `_families` entries `"gemini-orchestrator"` (`horizon_key: "gemini_orchestrator"`, `sort_order: 2`) and `"gemini-hydrogen"` (`horizon_key: "gemini_hydrogen"`, `sort_order: 4`).
  - Registered `1667`, `1681`, `1669`, `1528`, `1525`, `1526`, `1527` (`sort_rank` `7`–`13`, shifting downstream models `+7`), updated `quota_tracks[0].silo_subtitle`, added `hydrogen_xhigh_sprint` simulator archetype, and added GA availability records.
- **Backend Analytics (`src/`)**:
  - `src/horizon_analytics.py`: Registered `"gemini_orchestrator"` and `"gemini_hydrogen"` in `CANONICAL_FAMILIES`, `classify_model_family()`, and diurnal `by_family` / `latency_by_model`.
  - `src/aggregator_coaching.py`, `src/swarm.py`, `src/temporal.py`, `src/simulator.py`: Mapped placeholders (`M525`–`M528`, `M667`, `M681`), family fallback strings, `TIER_ENGINEERING` / `TIER_ARCHITECTURE`, temporal tier resolution, and `hydrogen_xhigh_sprint` fallback preset.
  - `src/quota_regime.py`: Added `1525`–`1528` (`1/6x` weights) and `1667`/`1681` (provisional `0.50x` weights) across all regime/rate tables plus Phase 2 probe prompts in `generate_calibration_probe_prompts()`.
- **Dashboard UI & Styling (`dashboard/`)**:
  - `dashboard/js/plan-rates.js`: Added `(XHigh)` reasoning parsing and regex stripping (`Gemini 4 Hydrogen` + `XHigh Reasoning`) plus `orchestrator`/`hydrogen` fallback sort ranks.
  - `dashboard/js/sessions-filters.js`, `dashboard/js/now-burst.js`, `dashboard/js/now.js`, `dashboard/js/simulator.js`: Registered `1M` truncation / `250k` compaction IDs, `.model-hydrogen` / `.model-orchestrator` badges with safe `meta = {}` defaults, progression & diurnal chart series, and `hydrogen_xhigh_sprint`.
  - `dashboard/styles.css` & `dashboard/index.html`: Added `--chart-orchestrator`, `--chart-hydrogen`, accessible `color-mix(in oklab, ...)` badge classes in light/dark themes, `#sim-archetype-select` + card, and `#sim-model-select` `<option>` entries.
- **Documentation & Verification (`docs/`, `tests/`)**:
  - Added §6 benchmark analysis to `docs/MODEL_BENCHMARKS.md`, expanded roster/threshold/coaching/horizon/regime unit tests, and hermetically regenerated `tests/fixtures/aggregator_baseline_data.json`.
