# Milestone 99: Gemini 4 Carbon Frontier Model Census & GPT-OSS Sunset Notice

**Date**: 2026-11-10
**Scope**: Model Census Expansion (Gemini 4 Carbon High/Medium/Low `1427`, `1437`, `1438`), Two-Era Rate History, Compaction/KV-Coaching Calibration, and Scheduled Sunset Notice for `GPT-OSS 120B (Medium)` (`342` on `2026-11-18`) (ADR-097)
**Branch**: `feat/m99-gemini-4-carbon-model-census`
**Verdict**: **PASS**

---

## 1. Overview & Context

This milestone integrates **Gemini 4 Carbon** across all three reasoning effort levels (`High`, `Medium`, `Low`) into the Antigravity Telemetry engine, canonical model census, temporal pricing engine, KV-cache coaching analyzer, quota regime detector, and web dashboard.

Key architectural and calibration decisions (ADR-097):
- **32-Model Canonical Census**: Expands `antigravity_telemetry/models.json` and `config/pricing.json` from 29 to 32 calibrated models.
- **Wire Telemetry Calibration (`GetUserStatus` Connect-RPC & Live SQLite Step Metadata)**:
  - `1427` (`MODEL_PLACEHOLDER_M427`, `gemini-4-carbon-high`): **Gemini 4 Carbon (High)**
  - `1437` (`MODEL_PLACEHOLDER_M437`, `gemini-4-carbon-medium`): **Gemini 4 Carbon (Medium)**
  - `1438` (`MODEL_PLACEHOLDER_M438`, `gemini-4-carbon-low`): **Gemini 4 Carbon (Low)** *(verified in live conversation DB `dd80500a`)*
  - Unlike Argon (`1417`–`1419`), Carbon uses a non-contiguous wire ID triplet (`1427` High, `1437` Medium, `1438` Low).
- **New Model Family (`gemini-carbon`)**: Assigned to `"family": "gemini-carbon"` (`"provider": "google"`), routing to the `"gemini"` provider quota track and `"architecture"` (`pro`) subagent tier, while keeping distinct family identity from `gemini-argon` so cross-family switches (`Argon` $\leftrightarrow$ `Carbon`) past `40k` context are accurately flagged as `intra_track` KV-cache evictions.
- **Two-Era Temporal Pricing Schedule**:
  - **Introductory Era (`2026-11-10T00:00:00Z` to `2026-11-30T23:59:59Z`)**: `$2.00` / 1M uncached input, `$0.10` / 1M cached input (95% discount), `$10.00` / 1M output (`15.0` credits/turn base).
  - **Standard Era (`2026-12-01T00:00:00Z` onwards)**: `$4.00` / 1M uncached input, `$0.20` / 1M cached input, `$20.00` / 1M output.
- **Context Window & Compaction Threshold**:
  - `context_truncation_tokens`: `1,000,000` (1M context window).
  - `compaction_threshold_tokens`: `250,000` (matching Gemini 4 Argon and Gemini 3.8 Flash).
- **Scheduled Sunset Notice on `GPT-OSS 120B (Medium)` (`342`)**:
  - Recorded `"sunset_date": "2026-11-18"` in `antigravity_telemetry/models.json`, `"status": "deprecated"`, `"sunset_at": "2026-11-18T00:00:00Z"` in `config/pricing.json` `availability`, and `(Sunset 2026-11-18)` in `#sim-model-select` per Connect-RPC `GetUserStatus` upstream notice.

---

## 2. Changes Implemented

- **`antigravity_telemetry/models.json` & `antigravity_telemetry/__init__.py`**:
  - Added models `1427`, `1437`, and `1438` under `"family": "gemini-carbon"` (`available_from: "2026-11-10"`), `1,000,000` truncation, and `250,000` compaction thresholds.
  - Added `"sunset_date": "2026-11-18"` to `342` and updated `get_model_compaction_threshold` family fallback to include `"carbon"`.
- **`config/pricing.json` & `config/pricing.sample.json`**:
  - Registered `1427`, `1437`, `1438` under `models`, two-era `rate_history`, and `availability` (`preview_from: "2026-10-28T00:00:00Z"`, `ga_from: "2026-11-10T00:00:00Z"`), plus `342` `availability` sunset (`2026-11-18T00:00:00Z`).
- **`src/aggregator_coaching.py`, `src/swarm.py`, `src/horizon_analytics.py`, `src/quota_regime.py`**:
  - Mapped `MODEL_PLACEHOLDER_M427`/`M437`/`M438` to `1427`/`1437`/`1438` and `gemini-carbon` in `aggregator_coaching.py`.
  - Registered Carbon in `swarm.py` (`TIER_ARCHITECTURE`), `horizon_analytics.py` (`gemini_carbon` family bucket & diurnal model profiles), and `quota_regime.py` (`CALIBRATED_QUOTA_WEIGHTS_POST_OCT17`, `PUBLIC_API_RATES`, `MODEL_LABELS`, and 6-turn sequential `read_file` staircase calibration prompts for `1427`, `1437`, `1438`).
- **`dashboard/js/*`, `dashboard/index.html`, `dashboard/styles.css`**:
  - Registered `1427`, `1437`, `1438` in `MODEL_TAXONOMY` (sort ranks `1`–`3`), `sessions-filters.js`, `now-burst.js` (`.model-carbon` badge), `now.js` (progression & diurnal series), `simulator.js`, and `index.html`.

---

## 3. Empirical Reasoning, Quota & Subagent Calibration (`1427` / `1437` / `1438` vs. Argon)

1. **Zero-Tool Rate-Limiter Benchmark (`docs/MODEL_BENCHMARKS.md` §2 & §3.1)**:
   - **`1427` (`Gemini 4 Carbon (High)`, session `24c69678`)**: `51,003` total thinking tokens (`32,616` T1 + `18,387` T2) vs `25,572` answer tokens (`1.99 : 1` ratio; `$0.9493` intro API equiv.). Turn 1 streamed for `511s` (`493.0s` TTFT), exceeding upstream Gemini's `300s` implicit prefix KV-cache TTL and causing a `0.0%` Turn 2 cache miss (`67,981` uncached).
   - **`1437` (`Gemini 4 Carbon (Medium)`, session `2d5e1f60`)**: `31,660` total thinking tokens vs `22,078` answer tokens (`1.43 : 1` ratio; **`91.5%`** Turn 2 cache hit at `30,488 / 33,303` tokens; `$0.6095` intro API equiv.). Across `94` production coding turns, `1437` enforces a **`100.0%` mandatory thinking floor** (`508` avg thinking tokens/turn, `0.78 : 1`), out-thinking `Argon High` (`1417`, `302` avg, `0.44 : 1`).
   - **`1438` (`Gemini 4 Carbon (Low)`, session `32563590`)**: `0` thinking tokens across both benchmark turns vs `17,911` answer tokens (`0.00 : 1` ratio; **`77.4%`** Turn 2 cache hit at `23,649 / 30,558` tokens; `$0.2426` intro API equiv.). Across `154` production turns, thinking fires on only `3.2%` of turns (`0.01 : 1`).
2. **Unified 7-Decimal Connect-RPC Quota Calibration (`#316` $\rightarrow$ `#3445`, Carbon + Argon)**:
   - Confirmed exact **`4.0000x` `5h : Weekly` coupling** and solved the exact server-side Connect-RPC quota formula across **all six Gemini 4 models (`1427`, `1437`, `1438` Carbon AND post-Oct-17 `1417`–`1419` Argon)** to 7 decimal places: **`$1.00 / 1M` uncached input, `$0.050 / 1M` cached input, `$5.00 / 1M` output/thinking** inside the `$25.00` 5h / `$100.00` Weekly `ultra_5x` reference frame (**exact `0.5000000x` of the `$2.00 / $0.10 / $10.00` Introductory API rate** = **`$50.00` 5h / `$200.00` Weekly** effective Gemini 4 capacity).
   - Recalibrated Argon (`1417`–`1419`) in `src/quota_regime.py` from its Oct 17 boundary-bleed fit (`$1.65 / $0.025 / $8.25`, caused by `e7761176` and `3697da31` overlapping `02fdeea7` without a `>= 6m` Connect-RPC flush gap) to `$1.00 / $0.050 / $5.00`, validated across `45` pure settled Argon intervals (`#316` $\rightarrow$ `#317`: `-0.0000002%` residual; `#2916` $\rightarrow$ `#2917`: `-0.0000008%` residual) and bringing 24-day cumulative `Obs/Pred` (`14,044` turns) from `0.8045x` to **`1.0332x`**.
   - Verified across pure `1438` staircase `5fd93ea4` (`#3443` $\rightarrow$ `#3444`: `0.5360000%` obs vs `0.5360052%` pred), pure `1437` single-turn `1e318cb4` (`#3444` $\rightarrow$ `#3445`: `0.1042200%` obs vs `0.1042200%` pred), pure `1437` 14-turn interval (`#3433` $\rightarrow$ `#3434`: `1.1391300%` obs vs `1.1391340%` pred), and `1427` High Turn 1 interval (`#3434` $\rightarrow$ `#3435`: `1.0609000%` obs vs `1.0608964%` pred).
3. **KV-Cache Eviction (`f2608107`) & Implicit TTL Survival Curve (`91,032` Vault Turns)**:
   - Controlled `68k`-context probe `f2608107` (`19s`–`65s` gaps) proved `100%` KV-cache eviction (`0` cached tokens) on both `intra_family` switches (`1438 Low` $\rightarrow$ `1437 Med` $\rightarrow$ `1427 High`) and `intra_track` switches (`1427 Carbon High` $\rightarrow$ `1418 Argon Med`), vs `96.8%` hit (`25.9ms` TTFT) on the `1438` $\rightarrow$ `1438` control.
   - `91,032`-turn vault survival audit confirmed a `5.0`-minute guaranteed implicit TTL floor (`94.3%` hit at `0–1m`, `45.5%` half-life cliff at `5–6m`) and a hard `60`-minute purge (`0.0%` at `60m+`).
4. **Subagent Routing Matrix (`invoke_subagent` from `dd80500a`)**:
   - Built-in `research` matches Argon (`M92`): `Model="inherit"` $\rightarrow$ `1438` (`8cda936a`), `Model="pro"` $\rightarrow$ `1322` (`d98959b9`), `Model="flash"` $\rightarrow$ `1322` (`31007b7d`), `Model="flash_lite"` $\rightarrow$ `1198` (`6b8c7395`). Custom markdown agents (`~/.gemini/config/agents/*.md`) always inherit the parent's active model (`1438` in `eca65232` / `9f196d03`) regardless of the `Model` parameter.
