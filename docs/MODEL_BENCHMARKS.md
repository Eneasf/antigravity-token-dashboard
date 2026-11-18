# Gemini Model Token & Reasoning Benchmark Ledger

Standardized benchmark suite measuring token consumption, reasoning intensity (thinking tokens), answer verbosity, and context cache hit efficiency across Gemini model tiers in Google Antigravity.

---

## 1. Benchmark Methodology

- **Target Task**: Production-grade Asynchronous Sliding Window Log Rate Limiter in Python.
- **Constraints**: 100% zero tools / zero file mutations (`[CRITICAL CONSTRAINT: Do NOT use tools or create files. Answer directly in chat.]`).
- **Turn 1 (The Design Turn)**: Evaluates architectural analysis, initial reasoning chain-of-thought depth, and code generation volume.
- **Turn 2 (The Cache & Decorator Turn)**: Evaluates follow-up reasoning, decorator extension, and context caching hit ratio on the Turn 1 prompt history.

---

## 2. Multi-Model Telemetry Ledger

| Model & Reasoning Level | Internal ID | T1 Thinking | T1 Answer | T2 Cached (%) | T2 Thinking | Total Thinking | Total Answer | Think/Answer Ratio | Total Output | Total Cost (USD / GBP) | Session ID |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Gemini 3.8 Flash (High)** | `1318` | 5,910 | 5,099 | 21,478 (59.7%) | 4,681 | **10,591** | 7,391 | **1.43 : 1** | 17,982 | $0.0115 (£0.0091) | `b6151ce3` |
| **Gemini 3.8 Flash (Medium)** | `1319` | 0 | 3,458 | 0 (0.0%) | 0 | **0** | 6,561 | **0.00 : 1** | 6,561 | $0.0076 (£0.0060) | `2c1b79c5` |
| **Gemini 3.8 Flash (Low)** | `1320` | 0 | 3,356 | 20,381 (**76.9%**) | 0 | **0** | 5,365 | **0.00 : 1** | 5,365 | **$0.0056 (£0.0044)** | `2b45de8d` |
| **Gemini 3.7 Flash (High)** | `1298` | 1,922 | 3,720 | 20,748 (70.8%) | 1,787 | 3,709 | 5,754 | **0.64 : 1** | 9,463 | $0.0075 (£0.0059) | `1b30647a` |
| **Gemini 3.7 Flash (Medium)** | `1299` | 1,219 | 3,669 | 20,552 (72.7%) | 857 | **2,076** | 5,508 | **0.38 : 1** | 7,584 | **$0.0066 (£0.0052)** | `e0f6f217` |
| **Gemini 3.7 Flash (Low)** | `1300` | 0 | 3,001 | 20,380 (**78.0%**) | 0 | **0** | 4,847 | **0.00 : 1** | 4,847 | **$0.0053 (£0.0042)** | `efa4d18c` |
| **Gemini 3.6 Flash (High)** | `1071` | 2,537 | 2,323 | 20,818 (70.0%) | 2,003 | 4,540 | 5,029 | **0.90 : 1** | 9,569 | **$0.0070 (£0.0055)** | `9b91d477` |
| **Gemini 3.6 Flash (Medium)** | `1072` | 1,274 | 2,309 | 20,502 (73.2%) | 627 | **1,901** | 3,959 | **0.48 : 1** | 5,860 | **$0.0054 (£0.0043)** | `ef1827bb` |
| **Gemini 3.6 Flash (Low)** | `1073` | 0 | 2,438 | 20,382 (**76.3%**) | 0 | **0** | 5,087 | **0.00 : 1** | 5,087 | **$0.0050 (£0.0039)** | `7f6e0cdc` |
| **Gemini Flash Lite (Subagent)** | `1050` | 0 | 943 | **20,376 (84.6%)** | 0 | **0** | **1,637** | **0.00 : 1** | **1,637** | **$0.0029 (£0.0023)** | `68481b2d` |
| **Gemini 3.1 Pro (High)** | `1016` | 6,965 | 2,180 | 21,888 (62.5%) | 4,042 | 11,007 | 3,589 | **3.07 : 1** | 14,596 | $0.1177 (£0.0930) | `6373aceb` |
| **Gemini 3.1 Pro (Low)** | `1036` | 1,954 | 2,241 | 20,843 (73.6%) | 3,224 | **5,178** | 3,691 | **1.40 : 1** | 8,869 | **$0.0817 (£0.0645)** | `2c224f34` |
| **Gemini 3.1 Pro Low (Subagent)** | `1036` | 2,091 | 1,476 | **21,366 (75.0%)** | 1,017 | **3,108** | 2,563 | **1.21 : 1** | **5,671** | **$0.0656 (£0.0518)** | `b9b5125e` |
| **Claude Sonnet 4.6 (Thinking)** *(Deprecated 2026-10-03)* | `1035` | *(bundled)* | 8,649 | 25,325 (72.8%) | *(bundled)* | *(bundled)* | 13,887 | *N/A (Vertex)* | 13,887 | $0.3222 (£0.2546) | `0280a3a2` |
| **Claude Opus 4.6 (Thinking)** *(Deprecated 2026-10-03)* | `1026` | *(bundled)* | 5,326 | **25,351 (80.5%)** | *(bundled)* | *(bundled)* | 9,246 | *N/A (Vertex)* | 9,246 | $1.2137 (£0.9588) | `0cba11e2` |
| **GPT-OSS 120B (Medium)** | `342` | 0 | 2,508 | **0 (0.0%)** | 0 | **0** | 4,891 | **0.00 : 1** | **4,891** | $0.0092 (£0.0072) | `c9624981` |
| *Gemini Flash Lite Gen 2 (Adaptive)* | `1198` | *(queued)* | *(queued)* | *(queued)* | *(queued)* | *(queued)* | *(queued)* | *TBD* | *(queued)* | *Placeholder (ADR-082)* | `pending` |
| *Claude 5.5 Opus (Low / Med / High)* | `1400-1402` | *(queued)* | *(queued)* | *(queued)* | *(queued)* | *(queued)* | *(queued)* | *TBD* | *(queued)* | *Placeholder (ADR-086)* | `pending` |
| *Claude 5.5 Sonnet (Low / Med / High)* | `1403-1405` | *(queued)* | *(queued)* | *(queued)* | *(queued)* | *(queued)* | *(queued)* | *TBD* | *(queued)* | *Placeholder (ADR-086)* | `pending` |
| **Gemini 4 Carbon (High)** | `1427` | **32,616** | 11,306 | **0 (0.0%)** *(>5m TTL)* | **18,387** | **51,003** | **25,572** | **1.99 : 1** | **76,575** | $0.9493 (£0.7500) | `24c69678` |
| **Gemini 4 Carbon (Medium)** | `1437` | 22,130 | 9,205 | **30,488 (91.5%)** | 9,530 | **31,660** | 22,078 | **1.43 : 1** | 53,738 | $0.6095 (£0.4815) | `2d5e1f60` |
| **Gemini 4 Carbon (Low)** | `1438` | 0 | 6,708 | **23,649 (77.4%)** | 0 | **0** | 17,911 | **0.00 : 1** | 17,911 | **$0.2426 (£0.1917)** | `32563590` |
| *Gemini 4 Argon (High / Med / Low)* | `1417-1419` | *(16,116 prod turns — §3.1)* | *(see §3.1)* | **92.2%–93.1%** | *(see §3.1)* | *(see §3.1)* | *(see §3.1)* | **0.44 / 0.34 / 0.05 : 1** | *(see §3.1)* | *Calibrated (ADR-093/096)* | `5feed114` |
| *Gemini 4 Hydrogen (Low / Med / High / XHigh)* | `1525-1528` | *(Phase 2 — §6)* | *(see §6)* | **79.6%–95.6%** | *(see §6)* | *(see §6)* | *(see §6)* | **0.23 – 5.82 : 1** | *(see §6)* | *Verified 1/6x (`1525`–`1528`)* | `563cc06e` |
| *Orchestrator (Carbon / Argon / Exec)* | `1667` / `1681` / `1669` | *(Phase 2 — §6)* | *(see §6)* | **68.3%–88.5%** | *(see §6)* | *(see §6)* | *(see §6)* | **1.00 / 1.94 : 1** | *(see §6)* | *0.50x planner (`1667`/`1681`) + 1/6x exec (`1669`)* | `82e45f58` |

> [!NOTE]
> **Model Roster Evolution (October–November 2026)**:
> - **Gemini 4 Hydrogen & Dual Orchestrator + Executor Calibration (2026-11-12 to 2026-11-14, ADR-098)**: Registered **Gemini 4 Hydrogen** (`1528` XHigh, `1525` High, `1526` Medium, `1527` Low; `gemini-hydrogen`, 1M context, `250k` compaction, verified `1/6x` quota burn weight `$0.25 / $0.0125 / $1.25` vs `$1.50 / $0.075 / $7.50` API across all four tiers `1525`–`1528`), **Orchestrator Planners** (`1667` Carbon, `1681` Argon; `0.50x` `$1.00 / $0.050 / $5.00`), and **Orchestrator Executor (Hydrogen)** (`1669`; `1/6x` `$0.25 / $0.0125 / $1.25`, activated automatically on `exit_plan_mode`). Phase 1 and Phase 2 telemetry are detailed in §6.
> - **Gemini 4 Carbon Launch & GPT-OSS Scheduled Sunset (2026-11-10, ADR-097)**: Gemini 4 Carbon (`1427` High, `1437` Medium, `1438` Low; `gemini-carbon` family, 1M context window, 250k compaction threshold) launched with two-era pricing (`$2.00 / $0.10 / $10.00` introductory until 2026-11-30; `$4.00 / $0.20 / $20.00` standard from 2026-12-01), while `GPT-OSS 120B (Medium)` (`342`) recorded an upstream removal notice scheduled for `2026-11-18`.
> - **Gemini 4 Argon Launch & 3.1 Pro Deprecation (2026-10-13, ADR-093)**: Gemini 4 Argon (`1417` High, `1418` Medium, `1419` Low; `gemini-argon` family, 1M context window, 250k compaction threshold) launched with two-era pricing (`$2.00 / $0.10 / $10.00` introductory until 2026-11-30; `$4.00 / $0.20 / $20.00` standard from 2026-12-01), while Gemini 3.1 Pro (`1016` High, `1036` Low) was marked deprecated/sunset as of 2026-10-13.
> - **Claude 4.6 Deprecation**: Claude Sonnet 4.6 (`1035`) and Claude Opus 4.6 (`1026`) were deprecated on 2026-10-03 following upstream retirement and succeeded by the calibrated Claude 5.5 series (`1400`–`1405`, ADR-086).
> - **Flash Lite Gen 2 Expansion**: Gemini Flash Lite Gen 2 with Adaptive Thinking (`1198`) supersedes Flash Lite Gen 1 (`1050`) for subagent workloads.
> - Benchmarks for `1198` and `1400`–`1405` remain queued; **Gemini 4 Carbon (`1427`, `1437`, `1438`)** and **Gemini 4 Argon (`1417`–`1419`)** empirical comparisons are documented in §3.1 below.

---

## 3. Analysis & Key Behavioral Insights

### 3.1 Gemini 4 Carbon (`1427` / `1437` / `1438`) vs. Gemini 4 Argon (`1417`–`1419`) — The Reasoning Ladder Shift & `>300s` TTL Paradox

#### A. Tier-by-Tier Production Telemetry (`16,116` Argon Turns vs. Live Carbon Trajectories)
Comparing all `16,116` archived `v_turns` of Gemini 4 Argon (`1417` High, `1418` Medium, `1419` Low) against live Gemini 4 Carbon trajectories (`1427` High, `1437` Medium, `1438` Low; `Carbon Medium` production row excludes the 3 zero-tool Card 1 turns for apples-to-apples multi-turn coding parity):

| Effort Tier | Model (`Wire ID`) | Sample Turns | Avg Warm Cache (`Hit %`) | `%` of Turns That Think | Avg Thinking / Turn | Peak Thinking (`max`) | Avg Answer / Turn | Think : Answer Ratio | Avg Wire TTFT |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | :---: | ---: |
| **Low** | **Gemini 4 Argon (Low)** (`1419`) | `971` | `109.8k` (`93.1%`) | `7.7%` | `25` tok | `1,896` tok | `482` tok | `0.05 : 1` | `1.30s` |
| **Low** | **Gemini 4 Carbon (Low)** (`1438`) | `154` | `111.7k` (`93.6%`) | **`3.2%`** | **`3` tok** | **`286` tok** | `672` tok | **`0.01 : 1`** | `2.63s` |
| **Medium** | **Gemini 4 Argon (Medium)** (`1418`) | `10,472` | `115.1k` (`92.2%`) | `74.9%` *(adaptive)* | `197` tok | `14,933` tok | `571` tok | `0.34 : 1` | `3.41s` |
| **Medium** | **Gemini 4 Carbon (Medium)** (`1437`) | `94` | `114.5k` (`94.2%`) | **`100.0%` *(mandatory)*** | **`508` tok** (`2.6x` Argon Med) | **`21,916` tok** | `648` tok | **`0.78 : 1`** (`1.8x` Argon High) | `6.45s` |
| **High** | **Gemini 4 Argon (High)** (`1417`) | `4,673` | `122.2k` (`92.5%`) | `100.0%` *(mandatory)* | `302` tok | `10,959` tok | `695` tok | `0.44 : 1` | `4.11s` |
| **High** | **Gemini 4 Carbon (High)** (`1427`) | `2` *(Card 1)* | `0.0%` *(>5m TTL)* | **`100.0%` *(ultra-deep)*** | **`25,502` tok** | **`32,616` tok** (`3.0x` Argon High max) | `12,786` tok | **`1.99 : 1`** | `419.6s` |

1. **Carbon Shifts the Reasoning Ladder Up by One Full Rung**:
   - `Argon Medium` (`1418`) was adaptive (`25.1%` of turns generated `0` thinking tokens). **`Carbon Medium` (`1437`) enforces a `100.0%` mandatory thinking floor**, averaging `508` thinking tokens/turn (`0.78 : 1` ratio)—`2.6x` `Argon Medium` and `1.68x` higher than `Argon High` (`302` tok, `0.44 : 1`).
   - **`Carbon High` (`1427`) operates as an ultra-deep research / verification tier**: on Turn 1 of the zero-tool Rate Limiter benchmark (`24c69678`), `1427` generated **`32,616` thinking tokens** (`493.0s` TTFT)—nearly **`3.0x` the largest single-turn thinking burst ever recorded across `4,673` historical turns of `Argon High` (`10,959` max)**.
   - **`Carbon Low` (`1438`) is cleaner than `Argon Low` (`1419`)**, dropping thinking incidence from `7.7%` to `3.2%` (`0.01 : 1` ratio) and `0` thinking tokens across both Rate Limiter benchmark turns (`32563590`).

2. **The High-Thinking Implicit Cache TTL Paradox (`> 300s` Self-Eviction) & Lower Prefix Floor**:
   - On `Carbon High` (`24c69678`), Turn 1 generated `32,616` thinking + `11,306` answer = `43,922` output tokens over **`511` seconds (`8m 31s`)**. Because upstream Gemini's implicit prefix KV cache carries a **5-minute (`300s`) idle TTL**, Turn 1's prompt prefix expired *while Turn 1 was still streaming*, causing Turn 2 (`67,981` input tokens) to record `0` cached tokens (`0.0%`).
   - Conversely, `Carbon Low` (`56s` Turn 1) and `Carbon Medium` (`264s` Turn 1) completed inside the `300s` TTL window and achieved **`77.4%` (`23,649` cached)** and **`91.5%` (`30,488` cached)** hits. Furthermore, short `Carbon` trajectories (`23e59892`, `8cda936a`) activate prefix KV caching as low as **`6,181`–`8,192` tokens** (down from the legacy `~20k–28k` threshold).

#### B. Unified 7-Decimal Connect-RPC Quota Calibration (`$1.00 / $0.050 / $5.00` = `0.5000x` Intro API Across Both Carbon & Argon)
Inside the `$25.00` 5h / `$100.00` Weekly `ultra_5x` reference frame (`4.0000x` `5h : Weekly` coupling), **all six Gemini 4 registrations**—both **Carbon (`1427`, `1437`, `1438`)** and **post-Oct-17 Argon (`1417`, `1418`, `1419`)**—deduct at **exact `0.5000000x` (`1/2`) of the `$2.00 / $0.10 / $10.00` Introductory API rate**:
- **`prompt_uncached = $1.00 / 1M`**, **`prompt_cached = $0.050 / 1M`**, **`candidate_output = $5.00 / 1M`** (thinking + answer).
- **Effective Burst Capacity**: `1` full `ultra_5x` 5h burst = **`$50.00` Introductory API-equivalent Gemini 4 compute (`$200.00 / week`)**.
- **Oct 17 Boundary-Bleed Correction (`1417`–`1419`)**: The initial M94 Argon fit (`$1.65 / $0.025 / $8.25`) was skewed because `e7761176` (`1418`) and `3697da31` (`1417`) ran `2m 48s` apart without a `>= 6m` Connect-RPC flush gap while `02fdeea7` (`1419`, `6.96M` cached) streamed concurrently (`#230 -> #232`). Auditing all `3,239` post-Oct-17 snapshots uncovers **`45` pure settled Argon intervals** matching `$1.00 / $0.050 / $5.00` to `6–7` decimal places and brings 24-day cumulative `Obs/Pred` across `14,044` turns from `0.8045x` to **`1.0332x`**. Consequently, any per-turn quota delta between `Carbon Medium` (`1437`) and `Argon Medium` (`1418`) derives strictly from `Carbon Medium` generating `2.6x` more thinking tokens (`+311` tok/turn $\approx$ `+0.006%` of a 5h bar per warm turn), not a per-token rate difference.

| Snapshot Interval (`UTC`) | Workload / Session | Uncached In | Cached In | Output (Thk+Ans) | Observed `Δ5h %` | Predicted `Δ5h %` | Residual (`IEEE-754 f32`) |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| **`#3443` $\rightarrow$ `#3444`** (`11-10 17:55Z`) | Pure `1438` (`Carbon Low` 7-turn staircase `5fd93ea4`) | `99,610` | `321,926` | `3,659` | `0.5360000%` | **`0.5360052%`** | **`-0.0000052%`** |
| **`#3444` $\rightarrow$ `#3445`** (`11-10 18:01Z`) | Pure `1437` (`Carbon Med` 1-turn `1e318cb4`) | `25,175` | `0` | `176` | `0.1042200%` | **`0.1042200%`** | **`0.0000000%`** |
| **`#3433` $\rightarrow$ `#3434`** (`11-10 16:51Z`) | Pure `1437` (`Carbon Med` 14 warm turns) | `30,613` | `1,545,418` | `4,998` | `1.1391300%` | **`1.1391340%`** | **`-0.0000040%`** |
| **`#3434` $\rightarrow$ `#3435`** (`11-10 16:57Z`) | `1427` (`Carbon High` T1 `24c69678`) + `1`×`1437` | `27,277` | `241,542` | `45,174` | `1.0609000%` | **`1.0608964%`** | **`+0.0000036%`** |
| **`#316` $\rightarrow$ `#317`** (`10-18 22:04Z`) | Pure `1418` (`Argon Med` 2 turns) | `185,657` | `179,611` | `5,999` | `0.8985300%` | **`0.8985302%`** | **`-0.0000002%`** |
| **`#2272` $\rightarrow$ `#2273`** (`11-01 21:58Z`) | Pure `1418` (`Argon Med` 2 uncached turns) | `452,299` | `0` | `1,542` | `1.8400300%` | **`1.8400360%`** | **`-0.0000060%`** |
| **`#2916` $\rightarrow$ `#2917`** (`11-05 20:04Z`) | Pure `1417` (`Argon High` 11 warm turns) | `38,018` | `1,102,494` | `8,975` | `0.5520700%` | **`0.5520708%`** | **`-0.0000008%`** |
| **`#3055` $\rightarrow$ `#3056`** (`11-07 09:33Z`) | Pure `1417` (`Argon High` 22 turns) | `454,344` | `4,172,548` | `18,159` | `3.0150600%` | **`3.0150656%`** | **`-0.0000056%`** |

#### C. Subagent Routing Matrix (`invoke_subagent` vs. Custom Markdown Agents)
Built-in `research` subagents dispatched from Carbon (`dd80500a`) match Argon (`M92` `5feed114`) identically: `Model="inherit"` $\rightarrow$ parent's active Carbon tier (`1438`, `8cda936a`), `Model="pro"` $\rightarrow$ `1322` (`d98959b9`), `Model="flash"` $\rightarrow$ `1322` (`31007b7d`), and `Model="flash_lite"` $\rightarrow$ `1198` (`6b8c7395`). Custom markdown agents (`~/.gemini/config/agents/*.md`) always bind to the parent session's active model (`1438` in `eca65232` / `9f196d03`) regardless of the `Model` argument, though their ambient-stripped system prompt starts at just `3,830` tokens vs `17,547` on `research`.

#### D. Intra-Family & Intra-Track KV-Cache Eviction Probe (`f2608107`)
Executed in `3m 15s` (`19s`–`65s` inter-step gaps, eliminating any `300s` TTL confound) across `~68k` input context (`f2608107-2150-4c4a-82be-46c680c54b25`):

| Step | Gap | Transition | Wire ID | Total Input | Uncached In | Cached In (`Hit %`) | Thinking | Wire TTFT | Eviction Verdict (`aggregator_coaching.py`) |
| :---: | ---: | :--- | :---: | ---: | ---: | ---: | ---: | ---: | :--- |
| `1` | — | Turn 1 Seed (`Low`) | `1438` | `25,022` | `25,022` | `0` (`0.0%`) | `0` | `785ms` | Cold start |
| `5` | `+29s` | Context Inflation (`Low`) | `1438` | `67,884` | `42,861` | `25,023` (`36.9%`) | `0` | `495ms` | Prefix warm-up |
| `7` | `+19s` | **Same-Model Control (`Low` $\rightarrow$ `Low`)** | `1438` | `67,975` | `2,140` | **`65,835` (`96.8%`)** | `0` | **`25.9ms`** | **KV Cache Warm** |
| `9` | `+36s` | **Intra-Family (`Low` $\rightarrow$ `Medium`)** | `1437` | `68,143` | **`68,143`** | **`0` (`0.0%`)** | `0` | `1.14s` | **`intra_family` wipe** (`65,835` wasted / `$0.1251`) |
| `11` | `+65s` | **Intra-Family (`Medium` $\rightarrow$ `High`)** | `1427` | `68,319` | **`68,319`** | **`0` (`0.0%`)** | `47` | `18.0ms` | **`intra_family` wipe** (`61,487` wasted / `$0.1168`) |
| `13` | `+46s` | **Intra-Track (`Carbon High` $\rightarrow$ `Argon Med`)** | `1418` | `68,535` | **`68,535`** | **`0` (`0.0%`)** | `23` | `991ms` | **`intra_track` wipe** (`61,681` wasted / `$0.1172`) |

*(Also replicated at `202,829` tokens in session `dd80500a` step `385`, where switching `1438` $\rightarrow$ `1437` evicted `199,709` cached tokens to `0%`.)*

#### E. Empirical Antigravity Implicit KV-Cache TTL Survival Curve (`91,032` Vault Turns)
Auditing all `91,032` consecutive same-model Google Gemini turns (`>= 40,000` input tokens) in `antigravity_vault.db` proves that Antigravity relies on **opportunistic implicit prefix KV caching** with a **`5.0`-minute guaranteed TTL floor** followed by gradual cluster LRU eviction and a **hard `60`-minute purge**:

| Inter-Turn Wall Gap | Sample Turns | Warm Cache Hit Rate (`cached > 0`) | Regime Interpretation |
| :--- | ---: | ---: | :--- |
| **`0 – 1 min`** | `87,025` | **`94.3%`** (`82,103`) | Active autonomous tool loop |
| **`1 – 3 min`** | `2,252` | **`91.6%`** (`2,063`) | Interactive reading / prompt drafting |
| **`3 – 4 min`** | `361` | **`75.6%`** (`273`) | Pre-TTL tail (long-streaming turns skewing start-to-start gap) |
| **`4 – 5 min`** | `231` | **`62.3%`** (`144`) | Approaching `300s` implicit TTL boundary |
| **`5 – 6 min`** | `145` | **`45.5%`** (`66`) | **`5.0`-minute guaranteed TTL half-life cliff** |
| **`6 – 8 min`** | `206` | **`28.2%`** (`58`) | Opportunistic GPU/TPU HBM retention under low cluster load |
| **`8 – 15 min`** | `287` | **`18.8%`** (`54`) | Residual un-evicted prefix blocks |
| **`15 – 30 min`** | `167` | **`8.4%`** (`14`) | Rare un-evicted prefix blocks |
| **`30 – 60 min`** | `112` | **`5.4%`** (`6`) | Near-complete LRU eviction |
| **`60+ min`** | `246` | **`0.0%`** (`0`) | **Hard `60`-minute server-side cache purge** |

#### F. Context Compaction Routine (`250,000` Threshold, `step_type = 23` `CHECKPOINT` & Quota Billing)
Empirical telemetry across **4 live Gemini 4 Carbon compactions** (`dd80500a` and `d4b2b26d`) vs. **26 Gemini 4 Argon compactions** confirms identical `250,000`-token user-boundary compaction mechanics:
- **Trigger Boundary**: Steps below `250,000` input tokens (`249,720` at `step=421`; `248,880` at `step=575`) never compact; crossing `250,000` fires `step_type = 23` (`CHECKPOINT`) at the next user-turn boundary, shedding **`87.3%–89.3%`** (`~224k` tokens) down to `27.4k–32.2k`.
- **Same-Model Summarizer & Prefix KV-Cache Continuity**: Unlike legacy Pro sessions where `1050` (`Flash Lite`) executed `CHECKPOINT`, Antigravity runs `step_type = 23` on the session's active model (`1438` or `1437`, matching Argon `1417`/`1418`). The summarizer call reads **`97.4%–99.1%`** of its `~258k` input from the warm KV cache (`$0.05/M` quota weight), and the static `~22.6k–24.8k` system/tool/rules prefix typically stays warm (`72.7%–82.6%` cached) on the very first post-compaction turn. Consistent with `1437`'s reasoning floor, `Carbon Medium` thinks (`114–3,132` tok) during summarization while `Carbon Low` (`1438`) emits `0` thinking tokens.
- **Connect-RPC Quota Billing (`#3444` $\rightarrow$ `#3446`)**: Summing `step_type = 15` (`4.031534%`) plus `step=430` (`step_type = 23` on `1437`: **`+0.250417%`** 5h = `$0.0626` quota / `$0.1252` Intro API) yields **`4.281951%`** vs observed Connect-RPC `Δ5h = 4.281940%` (residual **`-0.000011%`**). `src/quota_regime.py` includes `step_type IN (15, 23)` in interval drift reconciliation while `v_turns` remains restricted to `step_type = 15` so post-compaction active context depth (`t_n`) stays clean.

| Session & Checkpoint | Active Model | Pre-Compact (`step_type=15`) | Summarizer Call (`step_type=23`) | Post-Compact Turn 1 (`step_type=15`) | Tokens Shed |
| :--- | :---: | ---: | :--- | ---: | ---: |
| `dd80500a` `step=200` | `1438` (`Low`) | `255,397` | `in=257,120` (`99.1%` cac), `out=5,800` (`thk=0`) | `31,125` (`72.7%` cac) | **`-224,272` (`-87.8%`)** |
| `d4b2b26d` `step=187` | `1437` (`Med`) | `254,812` | `in=257,646` (`98.9%` cac), `out=4,090` (`thk=114`) | `27,368` (`82.6%` cac) | **`-227,444` (`-89.3%`)** |
| `dd80500a` `step=430` | `1437` (`Med`) | `253,824` | `in=260,613` (`97.4%` cac), `out=8,625` (`thk=3,132`) | `32,238` (`77.0%` cac) | **`-221,586` (`-87.3%`)** |
| `dd80500a` `step=583` | `1437` (`Med`) | `256,228` | `in=258,485` (`99.1%` cac), `out=4,634` (`thk=127`) | `31,247` (`91.3%` cac by `step=586`) | **`-224,981` (`-87.8%`)** |

### GPT-OSS 120B (Medium) (`342`) — Zero Caching & Ultra-Compact Output
- **Zero Context Caching**: Turn 2 context cache hit ratio was **0.0% (0 tokens cached)**. Unlike Gemini (~60–71%) and Claude (~73–80%), this open-source endpoint does not activate prompt prefix caching, re-evaluating the full 21.8k prompt from scratch.
- **Direct Output Without Chain-of-Thought**: 0 thinking tokens generated. Emitted direct, no-nonsense code and explanations (only 4,891 total output tokens across both turns — the most concise of all models).
- **Model ID Discovery**: Confirmed internal ID `342` as **GPT-OSS 120B (Medium)**.

### Gemini 3.8 Flash: High vs. Medium Reasoning Effort & The Caching Paradox

#### 1. Internal Model ID Routing
Switching the reasoning effort slider in Antigravity does not merely pass a runtime parameter (`thinking_budget`). It routes requests to distinct server-side model registrations:
- **`1318`**: Gemini 3.8 Flash (**High** Reasoning)
- **`1319`**: Gemini 3.8 Flash (**Medium** Reasoning)

#### 2. Adaptive Thinking vs. Forced Chain-of-Thought
- **High Mode (`1318`)**: Operates with a mandatory high thinking budget floor. Even on canonical, well-understood tasks (such as an asynchronous sliding window rate limiter), it is compelled to produce deep internal deliberations, consuming **5,910 thinking tokens on Turn 1** and **4,681 on Turn 2** (10,591 total thinking tokens).
- **Medium Mode (`1319`)**: Operates with **adaptive / dynamic reasoning**. When given a clear coding prompt with a strict `"do not use tools / answer in chat"` constraint, the model determines that no deep multi-step deduction is required and bypasses thinking entirely (**0 thinking tokens**), streaming the code response immediately.
- **Historical Telemetry Proof**: Multi-turn analysis across other workspace sessions proves that `1319` is **not** "thinking-disabled." In exploratory turns requiring complex data parsing, regression analysis, or error diagnostics, `1319` dynamically allocated between **14 and 1,133 thinking tokens** per turn. It thinks only when genuine ambiguity warrants it.

#### 3. The Caching Threshold Paradox (Why High Cached 59.7% but Medium Cached 0.0%)
Gemini prompt caching requires crossing a cluster activation threshold (typically ~28k–32k tokens) before prefix KV caching is engaged:
- **High Mode (`1318`)**: Generated 5,910 thinking + 5,099 answer = **11,009 output tokens** on Turn 1. Consequently, Turn 2 input jumped to **35,952 tokens**, crossing the activation threshold and triggering **21,478 cached tokens (59.7% hit ratio)**.
- **Medium Mode (`1319`)**: Generated 0 thinking + 3,458 answer = **3,458 output tokens** on Turn 1. On Turn 2, total input was only **26,599 tokens**—falling just short of the ~28k–32k threshold, resulting in **0 cached tokens (0.0% hit ratio)**.
- **The Paradox**: In multi-turn sessions, spending heavy thinking tokens on Turn 1 can paradoxically pay for itself on Turn 2 by inflating the conversation history over the cache threshold, unlocking a ~60% discount on the subsequent turn.

#### 4. High vs. Medium Comparative Summary

| Dimension | Gemini 3.8 Flash (High) | Gemini 3.8 Flash (Medium) |
|---|---|---|
| **Internal Model ID** | `1318` | `1319` |
| **Thinking Budget Behavior** | Rigid / High minimum floor | Dynamic / Adaptive down to zero |
| **T1 Thinking (Rate Limiter)** | 5,910 tokens | 0 tokens |
| **T2 Thinking (Decorator)** | 4,681 tokens | 0 tokens |
| **Total Thinking Tokens** | 10,591 tokens | 0 tokens |
| **Time-to-First-Token (TTFT)** | Pauses 5–15s to think | Instant stream generation |
| **Total Output Generation** | 17,982 tokens | 6,561 tokens (**63.5% reduction**) |
| **Total Cost (USD / GBP)** | $0.0115 (£0.0091) | $0.0076 (£0.0060) (**34% cheaper**) |
| **T2 Cache Hit Ratio** | **59.7% (21,478 tokens)** | **0.0% (0 tokens - under threshold)** |

### Gemini 3.7 Flash: High (`1298`) vs. Medium (`1299`) — The New Budget Champion ($0.0066 / ~0.52p)
- **Model ID Confirmation**: Confirms internal ID **`1299`** as **Gemini 3.7 Flash (Medium)**, demonstrating a consistent pairing convention across Gemini Flash generations (`1298`/`1299` for 3.7; `1318`/`1319` for 3.8).
- **The #1 Cost-Efficiency Leader**: Clocking in at **$0.0066 (£0.0052)** across both turns, 3.7 Flash Medium dethrones 3.6 Flash High ($0.0070) as the **single cheapest model configuration tested across the entire benchmark suite**.
- **Measured Reasoning (0.38 : 1 Ratio)**: Unlike 3.8 Flash Medium which dropped thinking tokens completely to 0, 3.7 Flash Medium allocated a calibrated thinking budget of **1,219 tokens on Turn 1** and **857 tokens on Turn 2** (2,076 total thinking tokens), delivering high-quality implementation while keeping overhead minimal.
- **Cache Activation Boundary Proven**: On Turn 2, total input reached **28,286 tokens**, successfully crossing Gemini's ~28,000-token cluster threshold and triggering a **72.7% context cache hit (20,552 cached tokens)**. This empirical datapoint pinpoints the cache activation threshold between **26.6k tokens** (where 3.8 Medium missed) and **28.3k tokens** (where 3.7 Medium hit).

### Gemini 3.6 Flash: The Complete Triplet (`1071` / `1072` / `1073`) — The Sub-Half-Cent Record
- **The Universal Sequential Triplet Architecture**: Confirms internal ID **`1073`** as **Gemini 3.6 Flash (Low)**. This permanently proves Antigravity's model routing rule across all Gemini Flash versions:
  - **3.6 Flash**: `1071` (High) $\rightarrow$ `1072` (Medium) $\rightarrow$ `1073` (Low)
  - **3.7 Flash**: `1298` (High) $\rightarrow$ `1299` (Medium) $\rightarrow$ `1300` (Low)
  - **3.8 Flash**: `1318` (High) $\rightarrow$ `1319` (Medium) $\rightarrow$ `1320` (Low)
- **The All-Time Benchmark Price Champion ($0.0050 / ~0.39p)**: Clocking in at **$0.0050 (£0.0039)** across both turns, Gemini 3.6 Flash Low breaks the sub-half-cent barrier to become the **single cheapest model run across the entire benchmark suite**.
- **Dual-Turn Caching Powerhouse**: Achieved **33.8% cache on Turn 1 (8,152 tokens)** and **76.3% cache on Turn 2 (20,382 tokens)**.
- **Zero Thinking Overhead**: Just like 3.7 Low and 3.8 Low, 3.6 Low allocated **0 thinking tokens**, streaming direct code immediately.

### The Flash Evolution: 3.6 vs 3.7 vs 3.8
- **3.6 Flash Low (`1073`) — The Undisputed All-Time Benchmark Champion**: 0 thinking tokens, 5,087 answer tokens, dual-turn caching (33.8% T1, 76.3% T2) $\rightarrow$ **lowest total cost of the entire benchmark at $0.0050 (~0.39p)**.
- **3.7 Flash Low (`1300`) — The Modern Ultra-Budget Runner-Up**: 0 thinking tokens, 4,847 answer tokens, 78.0% T2 cache $\rightarrow$ **$0.0053 (~0.42p)**.
- **3.6 Flash Medium (`1072`) — The Dual-Turn Cache Specialist**: 1,901 thinking tokens (0.48 : 1 ratio). Dual-turn caching (33.8% T1, 73.2% T2) $\rightarrow$ **$0.0054 (~0.43p)**.
- **3.8 Flash Low (`1320`) — The Zero-Thinking Speedster**: 0 thinking tokens, 5,365 answer tokens, 76.9% T2 cache $\rightarrow$ **$0.0056 (~0.44p)**.
- **3.7 Flash Medium (`1299`) — The Modern Efficiency Leader**: 2,076 thinking tokens (0.38 : 1 ratio), 5,508 answer tokens, 72.7% T2 cache $\rightarrow$ **$0.0066 (~0.52p)**.
- **3.6 Flash High (`1071`) — The Balanced Budget Veteran**: 4,540 thinking tokens (0.90 : 1 ratio), 5,029 answer tokens, 70.0% T2 cache $\rightarrow$ **$0.0070 (~0.55p)**.
- **3.7 Flash High (`1298`) — The Generative Speedster**: 3,709 thinking tokens (0.64 : 1 ratio), 5,754 answer tokens, 70.8% T2 cache $\rightarrow$ **$0.0075 (~0.59p)**.
- **3.8 Flash Medium (`1319`) — The Instant Code Synthesizer**: 0 thinking tokens, 6,561 answer tokens, 0.0% T2 cache $\rightarrow$ **$0.0076 (~0.60p)**.
- **3.8 Flash High (`1318`) — The Heavyweight Reasoning Engine**: 10,591 thinking tokens (1.43 : 1 ratio), 7,391 answer tokens, 59.7% T2 cache $\rightarrow$ **$0.0115 (~0.91p)**.

### Gemini 3.1 Pro: High (`1016`) vs. Low (`1036`) — 31% Cost Reduction
- **Model ID Discovery**: Confirms internal ID **`1036`** as **Gemini 3.1 Pro (Low)**.
- **53% Drop in Reasoning Overhead**: Pro High spent **11,007 thinking tokens** (3.07 : 1 ratio); Pro Low dropped to **5,178 thinking tokens** (1.40 : 1 ratio), cutting out 5,829 hidden chain-of-thought tokens.
- **Output Depth Preserved**: Answer code generation remained virtually identical (3,691 tokens on Low vs. 3,589 tokens on High), delivering identical unit test coverage and structural completeness.
- **High Cache Efficiency**: Achieved **34.9% cache on Turn 1 (8,124 tokens)** and **73.6% cache on Turn 2 (20,843 tokens)**.
- **Financial Profile**: Reduced 2-turn task cost from $0.1177 down to **$0.0817 (£0.0645)**—saving ~31% on Pro compute without compromising code quality.

### Claude Sonnet (Thinking) via Vertex AI — Generative Leader
- **Output Balance**: Generated 8,649 tokens on Turn 1 and 5,238 on Turn 2 (13,887 total output). On Vertex AI (`req_vrtx_...`), Anthropic returns thinking tokens bundled directly within the output token payload.
- **Cache Hit**: 72.8% (25,325 tokens cached) on Turn 2.
- **Cost Profile**: $0.3222 (£0.2546) under Anthropic Vertex tier rates ($3.00/M in, $15.00/M out).

### Claude Opus (Thinking) via Vertex AI — All-Time Cache Record & Heavyweight Compute
- **Output Balance**: Delivered a dense, highly structured implementation generating 5,326 tokens on Turn 1 and 3,920 on Turn 2 (9,246 total output).
- **All-Time Cache Hit Record**: Achieved an astounding **80.5% context cache hit ratio (25,351 cached tokens)** on Turn 2, the highest in the entire benchmark.
- **Cost Profile**: $1.2137 (£0.9588) reflecting flagship tier pricing ($15.00/M in, $75.00/M out) — ~105x the cost of Flash High.

### Gemini Flash Lite (Subagent) (`1050`) — The All-Time Cost & Cache Champion ($0.0029 / ~0.23p)
- **Runtime Discovery of Model `1050`**: While Antigravity hides `flash-lite` from the primary interactive dropdown picker, subagent invocations specifying `Model: "flash_lite"` route deterministically to internal ID **`1050`** (`Gemini Flash Lite`).
- **The Orchestrator Topology**:
  - **Master Session (`b596cf7f`)**: Ran **Gemini 3.8 Flash (High)** (`1318`) acting as high-level planner and coordinator. Decomposed user intent across 2 turns, making structured tool calls to `invoke_subagent` and `send_message`.
  - **Subagent Session (`68481b2d`)**: Ran pure **Gemini Flash Lite** (`1050`). Executed the canonical Python rate limiter and decorator implementation with **0 thinking overhead**, zero tool distractions, and immaculate code structure.
- **The New All-Time Lowest Cost Record ($0.0029 / ~0.23p)**:
  - At dedicated Flash Lite rates ($0.075 / $0.01875 / $0.30), 2 full turns total **$0.0029 (£0.0023 / 0.23p)**.
  - Even under standard Flash rates ($0.10 / $0.025 / $0.40), the run totaled **$0.0038 (£0.0030 / 0.30p)**—surpassing 3.6 Flash Low ($0.0050) by **24% to 42%** to establish the absolute lowest operational cost across the entire benchmark suite.
- **The All-Time Highest Cache Hit Record (84.6%)**:
  - On Turn 2, Flash Lite cached **20,376 tokens out of 24,076 total input tokens (84.6% cache hit ratio)**, shattering Claude Opus's previous benchmark record of 80.5%.
- **Maximum Generative Concision**:
  - Flash Lite generated just **943 output tokens on Turn 1** and **694 output tokens on Turn 2** (**1,637 total output tokens**). This is 66% fewer tokens than GPT OSS (4,891 tokens) and 68% fewer than 3.6 Flash Low (5,087 tokens) while fulfilling 100% of the functional requirements.
- **Speed & Latency**:
  - **TTFT**: **0.557s** on Turn 1 (near-instantaneous interactive response).
  - **Throughput**: **401.1 tok/s** on Turn 1 and **327.2 tok/s** on Turn 2.

### Gemini 3.1 Pro Low (Subagent) (`1036`) — Automated Architectural Execution
- **Subagent Routing Confirmation**: When an agent invokes a subagent with `Model: "pro"`, Antigravity deterministically routes the session to **Internal Model ID `1036`** (`Gemini 3.1 Pro Low Reasoning`), avoiding the latency-heavy, rigid thinking floor of Pro High (`1016`).
- **The Orchestrator Topology**:
  - **Master Session (`1cf2586e`)**: Ran **Gemini 3.8 Flash High** (`1318`) acting as coordinator, delegating Turn 1 and Turn 2 via `invoke_subagent` and `send_message`.
  - **Subagent Session (`b9b5125e`)**: Ran pure **Gemini 3.1 Pro Low** (`1036`).
- **20% Cost Reduction vs Desktop Pro Low**:
  - Generated **5,671 total output tokens** (3,108 thinking, 2,563 answer), compared to 8,869 tokens in the desktop chat session.
  - Reduced total 2-turn task cost from $0.0817 down to **$0.0656 (£0.0518)**, delivering production-grade code with tighter, more focused reasoning.
- **Context Cache Parity**:
  - Turn 2 input reached 28,503 tokens, triggering an immediate **74.96% context cache hit (21,366 tokens cached)**, matching the 73.6% desktop cache performance.
- **Latency Profile**:
  - **TTFT**: 5.85s on Turn 1 and 5.04s on Turn 2, reflecting deep reasoning graph initialization before streaming code.
  - **Throughput**: 151.2 tok/s on Turn 1 and 167.9 tok/s on Turn 2.

### The Antigravity Subagent Routing Architecture
Empirical telemetry proves that Antigravity maintains a dedicated subagent execution matrix decoupled from the human desktop UI:
- **`Model: "flash_lite"`** $\rightarrow$ **`1198`** (*Gemini Flash Lite Gen 2 (Adaptive Thinking)* as of 2026-10-13; previously **`1050`** *Gemini Flash Lite*): Zero-thinking on simple prompts, ultra-fast execution.
- **`Model: "flash"`** $\rightarrow$ **`1322`** (*Gemini Fast Agent Assistant* / *Gemini 3.8 Flash (Low)*): High-velocity autonomous tool loop specialist.
- **`Model: "pro"`** $\rightarrow$ **`1322`** (*Gemini Fast Agent Assistant* as of 2026-10-13 following sunset of **`1036`** *Gemini 3.1 Pro Low*): Remapped upstream to `1322` rather than Gemini 4 Argon.
- **`Model: "inherit"`** $\rightarrow$ *Parent Model ID* (e.g. **`1417`** *Gemini 4 Argon (High)*): 1:1 clone of the user's desktop model. Required when delegating tasks that must retain frontier Gemini 4 Argon reasoning.

### Context Cache Parity Across Providers
- Gemini models cached **59.7%–84.6%**, while Claude models cached **72.8%–80.5%** on Turn 2, demonstrating that both Google DeepMind and Anthropic prompt caching engines operate seamlessly inside Antigravity.

---

## 4. Claude Models Telemetry, Context Caching & Quota Exhaustion Profile

### 4.1 Historical Claude Telemetry Across the Antigravity Workspace

Auditing all 132 conversation databases across the workspace uncovers **219 total turns** executed on Anthropic Claude foundation models (`1026` Claude Opus Thinking and `1035` Claude Sonnet Thinking via Vertex AI).

| Model | Internal ID | Convos | Total Turns | Total Input | Cached Input (%) | Uncached Input | Total Output | Total Spend (USD / GBP) | Avg Cost / Turn |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Claude Opus (Thinking)** | `1026` | 4 | 160 | 15,464,395 | 14,492,756 (**93.7%**) | 971,639 | 96,785 | $43.57 (£34.42) | **$0.2723 / turn** |
| **Claude Sonnet (Thinking)** | `1035` | 7 | 59 | 2,638,352 | 2,019,550 (**76.5%**) | 618,802 | 40,675 | $3.07 (£2.43) | **$0.0521 / turn** |
| **Grand Total (Claude)** | — | **11** | **219** | **18,102,747** | **16,512,306 (91.2%)** | **1,590,441** | **137,460** | **$46.64 (£36.85)** | **$0.2130 / turn** |

---

### 4.2 Multi-Turn Exhaustion Run Forensics & Billing Correlations

Two continuous high-intensity coding sessions were run on Claude Opus 4.6 (`1026`) until quota exhaustion / rate-limiting boundaries were encountered:

#### 1. The Heavyweight Coding Burst: Session `9bf32a2a` (08 Sep 2026)
- **Task**: Milestone M16 implementation (`feat/weekly-quota-exhaustion`).
- **Turns to Exhaustion**: **94 turns** executed within **27.3 minutes** (velocity: **3.4 turns/minute**).
- **Context Dynamics**: Context window escalated from 18.2k tokens on Turn 1 to a peak of **166,068 tokens** on Turn 199.
- **Consumption Profile**:
  - **Total Input**: **11,492,695 tokens** (10,887,453 cached [**94.7%**], 605,242 uncached).
  - **Total Output**: **47,220 tokens** (dense diff generation and tool execution).
  - **Incurred Spend**: **$28.95 (£22.87)** at an average of **$0.308 / turn**.
- **Exhaustion Trigger & Billing Correlation**:
  - The rapid context growth and $0.31/turn burn rate breached the active hourly credit rate limit, triggering the user warning at Step 134: *"No, I'm not safe in quota. I'm using overages for a while, something is wrong..."*.
  - This 94-turn run directly correlates with the largest billing deduction in the Google One statement: **-1,445 AI credits (£13.87 / $14.45)** debited across three consecutive hours on 08 Sep (21:00: -34, 22:00: -558, 23:00: -853).

#### 2. The Multimodal Cataloging Burst: Session `14d542c3` (09 Sep 2026)
- **Task**: 86 historical David Lloyd companion app screenshots ingestion.
- **Turns to Exhaustion**: **33 turns** executed within **12.0 minutes** (velocity: **2.7 turns/minute**).
- **Context Dynamics**: Began at 33.9k tokens on Step 709 (100% uncached following model flip from Gemini) and climbed to **100,325 tokens** on Step 797.
- **Consumption Profile**:
  - **Total Input**: **2,011,657 tokens** (1,871,250 cached [**93.0%**], 140,407 uncached).
  - **Total Output**: **23,271 tokens**.
  - **Incurred Spend**: **$6.66 (£5.26)** at an average of **$0.202 / turn**.
- **Exhaustion Trigger & Billing Correlation**:
  - At Step 789/793, background subagents encountered concurrency rate limits, followed immediately by complete orchestrator exhaustion on Step 797.
  - The user halted and flipped back to Gemini: *"Quota exhausted in the other model. Can we recover safely?"*.
  - This 33-turn run correlates directly with the **-312 AI credit deduction (£2.99 / $3.12)** recorded on the Google One statement for 09 Sep, 21:00 UTC.

---

### 4.3 Claude Exhaustion Boundary & Operational Thresholds

Comparing Claude Opus against Gemini 3.8 Flash yields clear empirical thresholds for when exhaustion occurs:

| Dimension | Claude Opus (Thinking) (`1026`) | Gemini 3.8 Flash (High) (`1318`) | Multiplier / Advantage |
| :--- | :---: | :---: | :---: |
| **Average Cost / Turn** | **$0.20 – $0.31** | **$0.0155** | **Opus is 13x–20x more expensive** |
| **Sustainable Velocity** | **1.0 – 1.5 turns / min** | **10.0+ turns / min** | Gemini sustains massive autonomous tool loops |
| **Turns to Exhaustion Ceiling** | **30 – 95 continuous turns** | **400 – 600+ continuous turns** | Gemini has 6x–10x higher headroom |
| **Time to Quota Depletion** | **10 – 30 minutes of continuous coding** | **Multi-hour continuous execution** | Opus exhausts credits rapidly under unthrottled loop |
| **Steady-State Caching Efficiency**| **93.0% – 94.7%** | **92.4% – 96.2%** | Parity (both providers cache long contexts well) |
| **Model Transition Penalty** | **100% cache miss on Flip 1** | **78.9k uncached replay spike on Flip 2** | Cross-provider flips incur heavy cold replay costs |

---

## 5. Case Study: Claude Opus 4.6 vs. Gemini 3.8 Flash Multimodal & Mid-Session Model Switch

### 5.1 Macro Tokenomics & Cost Disparity

Below is the verified consumption and economic breakdown derived from the wire-format protobuf payloads (`steps.metadata`) in conversation `14d542c3`:

| Metric | Claude Opus 4.6 (Thinking)<br>*(Steps 706–804)* | Gemini 3.8 Flash (High)<br>*(Steps 805–847)* | Variance / Delta |
| :--- | :---: | :---: | :---: |
| **Model Turns** | 33 turns | 22 turns | — |
| **Total Input Tokens** | 2,011,657 | 2,268,347 | +12.8% (larger accumulated context) |
| **Cached Input Tokens** | 1,871,250 (93.0%) | 2,096,982 (92.4%) | Similar steady-state cache hit |
| **Uncached Input Tokens** | 140,407 | 171,365 | +22.0% (due to model-shift replay shock) |
| **Candidate Output Tokens** | 23,271 | 14,431 | -38.0% (Gemini was significantly more concise) |
| **Thinking Tokens (Logged)** | *Embedded in output* | 6,864 | 47.6% of Gemini output was chain-of-thought |
| **Average Input / Turn** | 60,959 tokens | 103,107 tokens | Gemini operated over a context window 1.7x larger |
| **Average Output / Turn** | 705 tokens | 656 tokens | Gemini generated ~7% fewer output tokens / turn |
| **Total Incurred Cost** | **\$6.658** | **\$0.340** | **Opus was 19.6x more expensive overall** |
| **Average Cost / Turn** | **\$0.2018 / turn** | **\$0.0155 / turn** | **Opus was 13.0x more expensive per turn** |

#### Why Opus Breached Quota
At **\$0.202 per turn** under Opus rates (\$15.00/MTok uncached prompt, \$1.50/MTok cached prompt, \$75.00/MTok output), just 33 interactive turns exhausted the assigned tier allocation. By comparison, Gemini ran 22 deep inspection turns over a 100k+ token context window for merely **\$0.34 total** (\$0.015/turn).

---

### 5.2 Model Shift Mechanics & Context Replay Penalty

Switching foundation models mid-session fundamentally breaks provider-level KV caching. The telemetry reveals two distinct transition behaviors:

```text
[Gemini Session (Turns 1-705)] ──> Context: 247k tokens (98.6% cached)
             │
             ▼ [User flips to Claude Opus 4.6 at Step 706]
[Opus Turn 709] ──────────────────> Total: 33,918 tokens | Cached: 0 (100% COLD CACHE MISS)
             │                      Context compacted/truncated to fit Opus budget
             ▼ [Opus exhausts quota at Step 797-804]
[User flips back to Gemini at Step 805]
             │
             ▼ [Gemini Resume Turn 806]
[Gemini Turn 806] ────────────────> Total: 87,078 tokens | Uncached: 78,925 tokens (90.6% COLD REPLAY SHOCK)
             │                      Gemini had to ingest Opus's entire trajectory from scratch
             ▼
[Gemini Turn 808] ────────────────> Total: 89,090 tokens | Cached: 85,743 tokens (96.2% Cache Restored)
```

#### Transition 1: Gemini $\rightarrow$ Opus (Step 706)
- **Pre-switch Gemini state (Turn 705)**: 247,379 total input tokens (243,819 cached, 3,560 uncached, 98.6% cache hit).
- **Opus First Turn (Turn 709)**: Total input was **33,918 tokens**.
  - **Cached tokens**: **0** (100% cold cache miss).
  - **Uncached tokens**: **33,918 tokens**.
  - **Context Compaction**: Antigravity condensed the preceding 247k Gemini conversation history down to ~34k tokens prior to feeding Opus, protecting against an immediate context window blowup.

#### Transition 2: Opus $\rightarrow$ Gemini (Step 805 — Quota Recovery)
- **Opus Last Turn (Turn 797)**: Total input was 100,325 tokens (98,754 cached, 1,571 uncached).
- **Gemini Resume Turn (Turn 806)**: Total input was **87,078 tokens**.
  - **Cached tokens**: **8,153 tokens** (only 9.4% cache hit).
  - **Uncached tokens**: **78,925 tokens** (**90.6% cold context replay penalty**).
  - **Root Cause**: The entire 33-turn trajectory produced by Opus (tool invocations, subagent replies, scratch outputs) was foreign to Google's Gemini prompt cache. Gemini had to perform a single massive ingest of 78,925 uncached tokens to "replay and catch up".
  - **Recovery**: By Step 808 (turn 2 after resume), Gemini established its prompt cache: **85,743 cached tokens** out of 89,090 total input (**96.2% cache hit ratio**).

---

### 5.3 Image Recognition & Multimodal Categorization Behavior

Both models were tasked with inspecting the 86 screenshots staged on the NAS:

| Multimodal Dimension | Claude Opus 4.6 (Thinking) | Gemini 3.8 Flash (High) |
| :--- | :--- | :--- |
| **Direct Images Inspected** | 14 images (Scans 1, 2, 4, 12, 14, 19, 28, 45, 48, 49, 55, 61, 82, 86) | 18 images (Scans 25, 26, 27, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43) |
| **Avg Uncached Tokens / Image** | **3,140 tokens** | **4,508 tokens** (+43.5%) |
| **Avg Output Tokens / Image Turn** | **1,050 tokens** | **335 tokens** (-68.1%) |
| **Token Encoding Profile** | Compact image patch tokens, but coupled with verbose discursive outputs. | Dynamic multi-tile high-resolution image grid (~258–1000+ tokens per tile), but paired with terse, execution-focused responses. |
| **OCR & Layout Extraction** | Detected numerical values and dates on historical cards accurately. | Detected both numerical values and segmented body components with high precision. |
| **Domain Attribution Accuracy** | ⚠️ **Hallucination / Misclassification**: At Step 747, Opus falsely declared the images as *"Samsung Health / Fitness Hub yearly trend screenshots"*. | ✅ **Exact Identification**: Immediately recognized the images as **David Lloyd companion app** screenshots. |
| **Response to Correction** | Required two user interventions (Steps 749, 750, 753) to concede that data originated from eGym and InBody via David Lloyd. | Seamlessly ingested the correction during context replay and maintained 100% adherence to David Lloyd taxonomy. |
| **Final Deliverable** | Halted prematurely due to quota limits without delivering a verified catalog. | Successfully verified all 86 images (**0 corrupted**) and authored the full `implementation_plan.md` with Schema Migration v11. |

---

### 5.4 Agent Topology & Parallelism Differences

The telemetry highlights contrasting orchestration strategies:

#### Opus Orchestration Strategy (Hierarchical Subagent Delegation)
At step 710, Opus attempted to fan out image processing by spawning 4 subagents (`35195351`, `3567feab`, `ab7e9495`, `855ee473`). Notably, the subagents automatically instantiated with model `1322` (**Gemini Fast Agent Assistant**). While the subagents processed ~70 images in the background, Opus consumed excessive tokens in the parent conversation coordinating messages and re-reading samples, leading to its quota exhaustion before the aggregation completed.

#### Gemini Orchestration Strategy (Deterministic Sequential Processing)
Upon resuming at turn 805, Gemini avoided spawning additional subagents. It executed 18 rapid, sequential `view_file` calls in lockstep (turns 809–843), operating with low latency, stable cache hit rates (96%+), and immediately consolidating the findings into the final data taxonomy.

---

### 5.5 Key Operational Takeaways

1. **The Cost of Switching Models is Real (Cache Invalidation Shock)**:
   - Flipping between Claude and Gemini incurs a **100% prompt cache penalty** on turn 1, and a **70k–80k uncached token replay spike** when switching back to catch up on intervening turns.
2. **Vision Tokenomics**:
   - Gemini allocates slightly more input tokens per image due to high-resolution spatial tiling, but compensates with **13x lower per-token pricing** and **3x more concise tool-call execution**.
3. **Domain Grounding in Vision**:
   - Claude Opus was prone to UI brand over-generalization (misidentifying generic fitness card widgets as "Samsung Health"), whereas Gemini Flash adhered strictly to the subtle header metadata ("Fitness Hub", "Fitness Machine", David Lloyd branding) without prior user prompting.

---

## 6. Gemini 4 Hydrogen (`1525`–`1528`) & Orchestrator (`1667` / `1681`) Phase 1 Telemetry & Calibration (ADR-098)

### 6.1 Wire Taxonomy & Observed Phase 1 Sessions

Empirical Phase 1 runs (2026-11-13 to 2026-11-14) verified six new server-side model IDs across SQLite conversation DBs and Connect-RPC `GetUserStatus` quota snapshots:

| Family & Tier | Wire ID (`Placeholder`) | Session(s) | Turns (`Compactions`) | Uncached / Cached Input | Thinking / Total Output | Peak Context | Avg Wire TTFT |
| :--- | :---: | :--- | ---: | ---: | ---: | ---: | ---: |
| **Hydrogen (Low)** | `1527` (`M527`) | `fe81d99d` *(single-turn probe)* | `1` (`0`) | `26,780` / `0` | `103` / `518` | `26,780` | `2.08s` |
| **Hydrogen (Medium)** | `1526` (`M526`) | `ae8544f4` *(single-turn probe)* | `1` (`0`) | `26,782` / `0` | `730` / `1,166` | `26,782` | `4.56s` |
| **Hydrogen (High)** | `1525` (`M525`) | `cf9df316`, `2483b9b1`, `3542221f` | `107` (`1` @ `256k`) | `560,469` / `8,751,422` (`94.0%`) | `51,712` / `84,834` | `256,395` | `0.82s – 2.77s` |
| **Hydrogen (XHigh)** | `1528` (`M528`) | `bb66a4a6`, `ad6e818a` | `404` (`8` @ `250k`) | `3,447,070` / `56,352,753` (`94.2%`) | `404,974` / `576,689` | `255,187` | `4.06s – 4.33s` |
| **Orchestrator (Carbon)** | `1667` (`M667`) | `a71ab3cb` *(5-turn read probe)* | `5` (`0`) | `61,123` / `173,535` (`74.0%`) | `10,904` / `12,179` (`9,972` on T5) | `57,027` | `23.57s` (`115.7s` T5) |
| **Orchestrator (Argon)** | `1681` (`M681`) | `7b60899d` *(5-turn read probe)* | `5` (`0`) | `60,672` / `172,756` (`74.0%`) | `1,967` / `3,140` | `56,576` | `4.41s` |

### 6.2 Quota Weight Calibration & Compaction Boundaries

1. **Gemini 4 Hydrogen (`1525`–`1528`) `1/6x` Quota Weight (`$0.25 / $0.0125 / $1.25`)**:
   - Inside the `$25.00` 5h / `$100.00` Weekly `ultra_5x` reference frame (`4.0000x` `5h : Weekly` coupling), **`1525` (`High`)** and **`1528` (`XHigh`)** align with **`1/6x` (`0.1667x`) of Hydrogen's `$1.50 / $0.075 / $7.50` API schedule**:
     - Across clean settled window **`#3607` $\rightarrow$ `#3611`** (`2026-11-14T02:23:41Z` $\rightarrow$ `04:57:06Z`, followed by idle overnight gap), Connect-RPC recorded **`1.61088%`** 5h burn (`$0.40272` on `$25` bar) and **`0.40272%`** weekly burn (`$0.40272` on `$100` bar). Reconciling vault `1525` (`99` steps: `515,959` uncached / `8,375,531` cached / `82,759` out $\rightarrow$ `$0.33713` at `1/6x`) plus `23` co-occurring `1322` subagent steps (`$0.04961` at Flash `1/6x`) accounts for `$0.38675` (`-3.97%`, no `>200k` context surcharge despite reaching `256,395` tokens in `3542221f`).
     - Across pure isolated **`1528` (`XHigh`)** window **`#3613` $\rightarrow$ `#3615`** (`15` steps, `250,434` uncached / `3,044,807` cached / `22,515` out, zero concurrent models), `1/6x` predicts `$0.12881` vs `$0.13368` observed (`-3.6%`), while pre-reset heavy multi-turn `bb66a4a6` (`#3570` $\rightarrow$ `#3585`) ran ~`+10%` above `1/6x`. An isolated 6-turn `1528` staircase probe (subsequently confirmed at `0.00%` residual via `563cc06e` in §6.3) completed the Phase 2 verification.
   - **1M Context / `250k` Compaction**: Both `1525` (`1` compaction at `256k` in `3542221f`) and `1528` (`6` `step_type = 23` compactions in `bb66a4a6`, `2` in `ad6e818a`) trigger compaction at **`250,000`** tokens inside a **`1,000,000`** context limit, matching Carbon and Argon.
2. **Orchestrator (`1667` Carbon / `1681` Argon) Provisional `0.5000x` Baseline & Phase 2 Protocol**:
   - In clean 5-turn read probes (`a71ab3cb` and `7b60899d`, identical ~`61k` uncached / ~`173k` cached input), `Orchestrator (Carbon)` (`1667`) generated **`5.5x` more thinking tokens** (`10,904` vs `1,967`, `9,972` on Turn 5 synthesis alone at `115.7s` TTFT) than `Orchestrator (Argon)` (`1681`).
   - All turns in both read probes recorded matching request (`Field 9.1`) and execution (`Field 11`) model IDs (`1667` and `1681`) with zero spawned child DBs; in mixed window `#3587` $\rightarrow$ `#3588` (`1667` x4 + `1681` x5 + `1528` x5), assigning provisional Carbon/Argon `0.5000x` weights (`$1.00 / $0.050 / $5.00`) predicts `$0.23387` vs `$0.24478` observed (`-4.5%`).
   - **Phase 2 Verified (see §6.3 below)**: Multi-step `edit -> test -> fix` trajectories (`82e45f58`, `61cfa298`) and subagent delegation (`092ea829`) revealed `exit_plan_mode` / `enter_plan_mode` dual-model switching between planner `1667`/`1681` (`0.50x`) and executor **`1669`** (`1/6x`).

### 6.3 Phase 2 Connect-RPC Verification & Orchestrator Dual-Model State Machine (`#3623` $\rightarrow$ `#3638`)

Eight isolated Connect-RPC intervals on `2026-11-14` (`ultra_5x` `$25` 5h / `$100` weekly frame) locked all four Hydrogen tiers (`1525`–`1528`) and Orchestrator `1667`/`1681`/`1669` to `<= $0.00001` (`0.00%–0.02%`) error:

| Interval (`UTC`) | Session(s) & Scope | Uncached / Cached In | Output (`Thk` / `Ans`) | Predicted USD | Observed `Δ5h` USD | Error |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| **`#3623` $\rightarrow$ `#3624`** (`15:24–15:38Z`) | `563cc06e`: `1528` XHigh (`n=7` staircase, `med_ttft=54.77ms`) | `69,001` / `269,014` | `7,452` (`6,360` / `1,092`) | `$0.02993` (`1/6x`) | `$0.02993` | **`0.00%`** |
| **`#3624` $\rightarrow$ `#3625`** (`15:38–15:46Z`) | `82e45f58`: `1667` (`n=2`, `$0.07691`) + `1669` (`n=7`, `$0.01864`) | `88,661` / `216,494` | `10,400` (`6,501` / `3,899`) | `$0.09555` | `$0.09555` | **`0.00%`** |
| **`#3625` $\rightarrow$ `#3626`** (`15:46–15:57Z`) | `61cfa298`: `1681` (`n=1`, `$0.03318`) + `1669` (`n=6`, `$0.01532`) | `70,346` / `144,703` | `3,373` (`1,085` / `2,288`) | `$0.04850` | `$0.04849` | **`+0.02%`** |
| **`#3626` $\rightarrow$ `#3627`** (`15:57–18:08Z`) | `092ea829` (`1667` `$0.12198`) + `1dbd3ff0` (`inherit -> 1667` `$0.10199`) + `060bf566` (`flash -> 1322` `$0.01805`) | `175,201` / `706,520` | `27,925` (`21,753` / `6,172`) | `$0.24202` | `$0.24202` | **`0.00%`** |
| **`#3627` $\rightarrow$ `#3628`** (`18:08–18:14Z`) | `6db26ee8`: `1525` High (`n=7` staircase, `med_ttft=86.30ms`) | `68,866` / `268,387` | `2,996` (`1,947` / `1,049`) | `$0.02432` (`1/6x`) | `$0.02431` | **`+0.00%`** *(wk `$0.02432`)* |
| **`#3628` $\rightarrow$ `#3629`** (`18:14–18:19Z`) | `786fc5d0`: `1418` Argon Med *(UI dropdown mismatch on T13)* | `68,034` / `263,567` | `1,505` (`415` / `1,090`) | `$0.08874` (`0.50x`) | `$0.08874` | **`0.00%`** |
| **`#3629` $\rightarrow$ `#3630`** (`18:19–18:30Z`) | `b16b2008`: `1527` Low (`n=7` staircase, `med_ttft=90.28ms`) | `68,597` / `267,231` | `1,178` (`222` / `956`) | `$0.02196` (`1/6x`) | `$0.02196` | **`0.00%`** |
| **`#3637` $\rightarrow$ `#3638`** (`19:50–20:26Z`) | `09dcae19`: `1526` Medium (`n=7` staircase, `med_ttft=52.20ms`) | `68,929` / `268,632` | `2,258` (`1,219` / `1,039`) | `$0.02341` (`1/6x`) | `$0.02341` | **`0.00%`** *(wk `$0.02342`)* |

Key architectural findings:
1. **Plan/Execution State Machine (`exit_plan_mode` / `enter_plan_mode`)**: Calling `exit_plan_mode` injects `"Plan mode is off: this turn runs on the execution model..."` and switches wire execution from the planner (`1667` Carbon or `1681` Argon at `0.50x`) to **`1669` (`Orchestrator Executor (Hydrogen)` at exact `1/6x` `$0.25 / $0.0125 / $1.25`)**, incurring one cold-cache handoff (`31,938` unc / `0` cac on Turn 2 of `82e45f58`, `med_ttft=818.9ms`). Calling `enter_plan_mode` returns execution to the planner inside the 300s KV cache TTL and reuses the planner's warm prefix (`27,686` cached tokens in `82e45f58` Turn 9).
2. **Orchestrator Subagent Inheritance (`092ea829`)**: `invoke_subagent(Model="inherit")` from an Orchestrator inherits the **planner** (`1667`, `0.50x`, `$0.10199` in `1dbd3ff0`), *not* the `1669` executor, whereas `Model="flash"` routes to `1322` (`$0.01805`, `5.65x` lower quota burn for read-only workers).
3. **Hydrogen (`1526` Medium) Verified & Tier Effort Gradient (`#3623` $\rightarrow$ `#3638`)**: After `786fc5d0` executed under UI `1418` (`Argon Medium`), a dedicated 6-turn staircase probe (`09dcae19`, `n=7` turns, `20:21Z`, zero co-occurring traffic) locked `1526` to exact `1/6x` (`$0.02341` predicted vs `$0.02341` observed `Δ5h` / `$0.02342` `Δwk`, `0.00%` error). Across all four matched Hydrogen 6-turn staircases, quota rate stays identically `$0.25 / $0.0125 / $1.25` while thinking output scales monotonically with effort: `222` (`1527` Low) $\rightarrow$ `1,219` (`1526` Med) $\rightarrow$ `1,947` (`1525` High) $\rightarrow$ `6,360` (`1528` XHigh).
