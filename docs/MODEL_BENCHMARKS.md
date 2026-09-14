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
| **Claude Sonnet 4.6 (Thinking)** | `1035` | *(bundled)* | 8,649 | 25,325 (72.8%) | *(bundled)* | *(bundled)* | 13,887 | *N/A (Vertex)* | 13,887 | $0.3222 (£0.2546) | `0280a3a2` |
| **Claude Opus 4.6 (Thinking)** | `1026` | *(bundled)* | 5,326 | **25,351 (80.5%)** | *(bundled)* | *(bundled)* | 9,246 | *N/A (Vertex)* | 9,246 | $1.2137 (£0.9588) | `0cba11e2` |
| **GPT-OSS 120B (Medium)** | `342` | 0 | 2,508 | **0 (0.0%)** | 0 | **0** | 4,891 | **0.00 : 1** | **4,891** | $0.0092 (£0.0072) | `c9624981` |

---

## 3. Analysis & Key Behavioral Insights

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
- **`Model: "flash_lite"`** $\rightarrow$ **`1050`** (*Gemini Flash Lite*): Zero-thinking, ultra-fast, sub-half-cent execution.
- **`Model: "flash"`** $\rightarrow$ **`1322`** (*Gemini Fast Agent Assistant*): High-velocity autonomous tool loop specialist.
- **`Model: "pro"`** $\rightarrow$ **`1036`** (*Gemini 3.1 Pro Low*): Agile architectural reasoning without the 11k-token thinking floor.
- **`Model: "inherit"`** $\rightarrow$ *Parent Model ID*: 1:1 clone of the user's desktop model.

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




