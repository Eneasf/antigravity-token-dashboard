# Telemetry Specification: Antigravity Protobuf & SQLite Stores

## 1. Upstream Storage Locations

Antigravity stores session data and execution telemetry under `~/.gemini/antigravity/`:

| Path | Format | Role |
|---|---|---|
| `conversations/<uuid>.db` | SQLite 3 (WAL mode) | Primary conversation event store. Table `steps` contains step-by-step turns. |
| `conversations/<uuid>.db-wal` | SQLite WAL file | Active write-ahead log buffer during ongoing conversation turns. |
| `annotations/<uuid>.pbtxt` | Text Protobuf (`pbtxt`) | Contains human-readable conversation title and view timestamps. |
| `agyhub_summaries_proto.pb` | Binary Protobuf (`pb`) | Maps conversation UUIDs to workspace directory URIs, git repos, and branches. |
| `~/Library/Logs/Antigravity/language_server.log` | Text Log | Real-time Language Server HTTP stream log containing API Response IDs and endpoints. |

---

## 2. SQLite Database Schema (`steps` table)

Each conversation database contains a `steps` table with the following schema:

```sql
CREATE TABLE steps (
    idx INTEGER PRIMARY KEY,
    step_type INTEGER NOT NULL,
    metadata BLOB,
    step_payload BLOB
);
```

### Step Types
- `14`: **`USER_INPUT`** — User turn containing the user prompt and uploaded context.
- `15`: **`PLANNER_RESPONSE`** — Model generation turn containing `usageMetadata` with prompt, cached, thinking, and candidate token counts.
- Other integers represent tool executions, environment notifications, or subagent message relays.

---

## 3. Protobuf Wire Schema for `steps.metadata`

The `metadata` column in `steps` contains a serialized Google Protobuf message. The relevant fields for telemetry are:

### Top-Level Message
- **Field 1 (Submessage, Wire Type 2)**: Turn Creation Timestamp
  - **Field 1.1 (Varint, Wire Type 0)**: `seconds` (Unix epoch seconds)
  - **Field 1.2 (Varint, Wire Type 0)**: `nanos` (Nanoseconds fraction)
- **Field 9 (Submessage, Wire Type 2)**: `UsageMetadata`
  - **Field 9.1 (Varint, Wire Type 0)**: `model_id` (Internal model enum/ID, e.g. `1318`)
  - **Field 9.2 (Varint, Wire Type 0)**: `prompt_token_count` — Uncached input tokens for this turn
  - **Field 9.3 (Varint, Wire Type 0)**: `candidates_token_count` — Total generated output tokens (`Field 9.9 + Field 9.10`)
  - **Field 9.5 (Varint, Wire Type 0)**: `cached_content_token_count` — Context cache input tokens
  - **Field 9.6 (Varint, Wire Type 0)**: Flags / status code
  - **Field 9.7 (String, Wire Type 2)**: Bot / Agent instance ID (e.g., `bot-68ca7b9b-...`)
  - **Field 9.8 (String, Wire Type 2)**: Session ID string
  - **Field 9.9 (Varint, Wire Type 0)**: `thoughts_token_count` — Reasoning / Thinking tokens generated
  - **Field 9.10 (Varint, Wire Type 0)**: Visible response answer tokens
  - **Field 9.11 (String, Wire Type 2)**: Gemini API unique `ResponseID` (e.g., `cxacat7FNcfmxN8PuNaviAI`)

---

## 4. Conversation Annotations (`annotations/<uuid>.pbtxt`)

Contains human-readable metadata in text protobuf format:
```protobuf
title: "Workspace Usage Telemetry Analysis"
last_user_view_time: {
  seconds: 1788614748
  nanos: 237000000
}
```
Extracted using regex to display friendly conversation names on the dashboard.

---

## 5. Model Mappings

| Model ID | Human-Readable Name | Default Family |
|---|---|---|
| `1318` | Gemini 3.8 Flash (High) | `gemini-flash` |
| `MODEL_PLACEHOLDER_M318` | Gemini 3.8 Flash (High) | `gemini-flash` |
| `1319` | Gemini 3.1 Pro | `gemini-pro` |
| `1317` | Gemini Flash Lite | `gemini-flash-lite` |
| `*` (Fallback) | Gemini Model (Unmapped) | `gemini-flash` |

---

## 6. AI Credit & Overage Telemetry Architecture

### 6.1 Live In-Memory Streaming vs. SQLite Persistence
- **In-Memory Streaming (`streamAgentStateUpdates`)**:
  When generating steps in overage, upstream `GenerateContentResponse` messages contain `consumed_credits`:
  ```protobuf
  consumed_credits {
    credit_type: GOOGLE_ONE_AI
    credit_amount: 1
    last_step_index: 479
  }
  ```
  The Language Server packages this into `CreditUsageSummary` and pushes it via live gRPC streaming to the Electron renderer, driving the chat UI pill (*"AI Credits Used to Generate Response ⓘ"*).
- **SQLite Persistence Invariant**:
  When the Language Server writes step records into `steps.metadata`, **`consumed_credits` is intentionally omitted**. SQLite stores only `UsageMetadata` (tokens, timings, model ID, response ID). The database does **not** persist an `is_overage` or `credit_burn` flag.

### 6.2 Log-Anchored Telemetry (`language_server.log`)
Because SQLite lacks billing flags, the engine correlates turn timestamps with `~/Library/Logs/Antigravity/language_server.log`:
- **429 Quota Depletion**:
  ```text
  Run: attempt 1 failed (RESOURCE_EXHAUSTED (code 429): You have exhausted your capacity on this model. Your quota will reset after 0s.), retrying in 1s
  ```
- **Attempt 1 Clean Success**:
  Subsequent generation logs showing direct `streamGenerateContent Trace: ... ResponseID: ...` without a preceding 429 error indicate that the 5-hour rolling token sum has dropped below capacity and the session has returned to quota.

### 6.3 Unified State Sync (`state.vscdb`)
Located at `~/Library/Application Support/Antigravity IDE/User/globalStorage/state.vscdb`:
- `antigravityUnifiedStateSync.modelCredits`:
  - `useAICreditsSentinelKey`: `b'\x08\x01'` (True)
  - `availableCreditsSentinelKey`: `b'\x10\x00'` (0 credits available / actively burning)
  - `minimumCreditAmountForUsageKey`: `b'\x102'` (50 credits threshold)
- `antigravityUnifiedStateSync.userStatus`:
  - Plan definition: `tier: "g1-pro-tier"` (`Google AI Pro`).

### 6.4 Multi-Currency Accounting & Google One AI Credit Calibration
- **Credit Pack Calibration**:
  - GBP Cost: **£23.99 for 2,500 credits** = **£0.009596 / credit** (~0.96p per credit).
  - USD Baseline: **$25.00 for 2,500 credits** = **$0.0100 / credit** (1.0¢ per credit).
- **Imputed Subscription Value Conversion**:
  - USD Baseline rates applied per 1M tokens.
  - GBP Conversion: USD × 0.79 FX rate.
- **Dual-Track Persistence & Seamless UI Toggle**:
  - All summary metrics and hourly billing block objects persist dual values:
    `total_credit_burn_usd`, `total_credit_burn_gbp`, `total_imputed_value_usd`, `total_imputed_value_gbp`.
  - The offline HTML dashboard defaults to British Pounds (`activeCurrency = "GBP"`) and provides an instant `[ GBP (£) | USD ($) ]` interactive toggle across all KPI cards, model yield matrices, and reconciliation tables.

### 6.5 Decoupled Dual-Tier Financial Architecture (ADR-015)
- **Tier 1: Google One AI Premium (Antigravity Pro Subscription)**:
  - Monthly subscription: **£18.99 / mo** (**$19.99 / mo**).
  - Renews on the 24th of each month (e.g. 24 Sep).
  - Provides unlimited in-quota standard usage at £0 marginal cost.
  - Imputed API value quantifies developer savings and computes live subscription ROI (`imputed_value / subscription_price`).
- **Tier 2: Prepaid Overage Credit Bank (AI Credit Activity)**:
  - Add-on credit pack: **2,500 credits** for **£23.99** (**$25.00**).
  - Effective rate: **£0.009596 / credit** (~0.96p) and **$0.0100 / credit** (1.0¢).
  - Debited strictly when exceeding 5-hour rolling limits (168M tokens) or out-of-quota execution.
  - Separate state tracking for remaining balance (1,321 credits = £12.68 / $13.21) and cumulative burn (1,179 credits = £11.31 / $11.79).

### 6.6 Persistent Exhaustion Ledger Defense (ADR-016)
- Located at [`data/exhaustion_ledger.json`](../data/exhaustion_ledger.json).
- Preserves verified 429 exhaustion incidents and official Google One billing activity statements across IDE log truncations:
  - `exc-20260905-13`: 13:00 UTC, 299 turns on Gemini 3.8 Flash (High) -> -748 credits (£7.18 / $7.48).
  - `exc-20260905-14`: 14:00 UTC, 172 turns on Gemini 3.8 Flash (High) -> -431 credits (£4.13 / $4.31).
  - Cumulative: -1,179 credits (£11.31 / $11.79), reconciled with ground truth Google One statements.

---

## 7. Model ID Taxonomy & Autonomous Subagent Routing Matrix (ADR-020)

### 7.1 Desktop Selector vs. Autonomous Subagent Routing
Antigravity operates with a dual-layer model dispatch architecture:
1. **Interactive Desktop UI**: Users select explicit model generations and reasoning effort sliders:
   - Gemini 3.8 Flash: High (`1318`), Medium (`1319`), Low (`1320`)
   - Gemini 3.7 Flash: High (`1298`), Medium (`1299`), Low (`1300`)
   - Gemini 3.6 Flash: High (`1071`), Medium (`1072`), Low (`1073`)
   - Gemini 3.1 Pro: High (`1016`), Low (`1036`)
   - Claude Sonnet 4.6 (Thinking) (`1035`), Claude Opus 4.6 (Thinking) (`1026`), GPT-OSS 120B (Medium) (`342`)
2. **Autonomous Subagent Matrix (`invoke_subagent`)**:
   - `Model: "flash_lite"` $\longrightarrow$ **`1050`** (*Gemini Flash Lite*): Zero thinking tokens, 0.55s TTFT, ultra-lean execution (~1,600 total tokens).
   - `Model: "flash"` $\longrightarrow$ **`1322`** (*Gemini Fast Agent Assistant*): Fine-tuned specifically for high-frequency tool loops.
   - `Model: "pro"` $\longrightarrow$ **`1036`** (*Gemini 3.1 Pro Low*): Pro-grade architectural reasoning without the rigid 11k-token thinking floor of `1016`.
   - `Model: "inherit"` $\longrightarrow$ *Parent Model ID*: 1:1 clone of the calling session's desktop model.

### 7.2 The 19-Model Telemetry Census
Across 115 SQLite databases and 11,200+ historical generation turns in `~/.gemini/antigravity/conversations/`, exactly 19 unique model IDs have been recorded. All 19 are 100% calibrated in [`config/pricing.json`](../config/pricing.json) with zero unmapped fallbacks:

| Model ID | Canonical Name | Family | Historical Turns | Role / Notes |
|---|---|---|:---:|---|
| **`1298`** | Gemini 3.7 Flash (High) | `gemini-flash` | 4,977 | Primary desktop interactive model |
| **`1318`** | Gemini 3.8 Flash (High) | `gemini-flash` | 4,101 | Primary desktop interactive model |
| **`1016`** | Gemini 3.1 Pro (High) | `gemini-pro` | 1,160 | Flagship reasoning model (rigid 11k thinking floor) |
| **`1322`** | Gemini Fast Agent Assistant | `gemini-flash` | 564 | Dedicated subagent engine for `Model: "flash"` |
| **`1132`** | Gemini Fast Agent (Legacy) | `gemini-flash` | 88 | Historical subagent engine |
| **`1301`** | Gemini Experimental Agent | `gemini-flash` | 65 | Internal canary / experimental agent |
| **`1035`** | Claude Sonnet 4.6 (Thinking) | `claude-sonnet` | 59 | Anthropic on Vertex AI |
| **`1072`** | Gemini 3.6 Flash (Medium) | `gemini-flash` | 53 | Adaptive reasoning Flash |
| **`1026`** | Claude Opus 4.6 (Thinking) | `claude-opus` | 33 | Flagship Anthropic on Vertex AI (80.5% cache) |
| **`1071`** | Gemini 3.6 Flash (High) | `gemini-flash` | 32 | High reasoning Flash |
| **`1319`** | Gemini 3.8 Flash (Medium) | `gemini-flash` | 25 | Adaptive reasoning Flash |
| **`1020`** | Gemini Search Agent | `gemini-flash` | 22 | Search / retrieval specialist agent |
| **`1036`** | Gemini 3.1 Pro (Low) | `gemini-pro` | 21 | Subagent engine for `Model: "pro"` & desktop low |
| **`342`** | GPT-OSS 120B (Medium) | `gpt-oss` | 12 | Open-source endpoint |
| **`1299`** | Gemini 3.7 Flash (Medium) | `gemini-flash` | 7 | Adaptive reasoning Flash ($0.0066) |
| **`1050`** | Gemini Flash Lite (Subagent) | `gemini-flash-lite` | 2 | Subagent engine for `Model: "flash_lite"` ($0.0029) |
| **`1073`** | Gemini 3.6 Flash (Low) | `gemini-flash` | 2 | Zero-thinking Flash ($0.0050) |
| **`1300`** | Gemini 3.7 Flash (Low) | `gemini-flash` | 2 | Zero-thinking Flash ($0.0053) |
| **`1320`** | Gemini 3.8 Flash (Low) | `gemini-flash` | 2 | Zero-thinking Flash ($0.0056) |

---

## 8. Subscription Coverage vs. Actual Overage Accounting (ADR-023)

### 8.1 Dual-Metric Accounting Distinction
In Antigravity workspaces, cost telemetry distinguishes between:
1. **Subscription-Covered Turns**: Turns executed within regular quota allowances under Google One AI Premium (£18.99/mo). Marginal cost is strictly **£0.00**. Across 11,743 audited conversation turns, 11,532 (98.2%) were fully covered.
2. **Actual Overages**: Out-of-pocket charges debited from the prepaid AI credit bank (£23.99 / 2,500 credits at £0.009596/credit) exclusively during confirmed 429 server exhaustion intervals. Reconciles to exactly 1,179 credits (£11.31 / $11.79) attributed to `Geminu token consumption dashboard.` on branch `main`.
3. **Avoided API Cost (Plan Value)**: Theoretical developer API cost calculated from official Google rate cards, demonstrating financial savings and plan ROI (£203.07 total value delivered against an £18.99/mo subscription).

### 8.2 Project & Branch Metric Schema
In aggregated project payloads (`payload['projects']`):
- `turn_count`: Total executed model turns.
- `subscription_covered_turns`: Turns executed within quota.
- `overage_turns`: Turns executed during confirmed 429 exhaustion.
- `subscription_covered_pct`: Percentage of turns covered at £0 marginal cost (`covered / total * 100.0`).
- `actual_overage_credits`: Number of AI credits debited.
- `actual_overage_usd` & `actual_overage_gbp`: True out-of-pocket overage expense.
- `avoided_cost_usd` & `avoided_cost_gbp`: Theoretical developer API value avoided by the subscription.

### 8.3 Cost-Weighted Incident Attribution (ADR-041 / Audit §2.1 A5)
When distributing persistent Google One credit deductions across concurrent conversations and Git branches during a confirmed 429 server exhaustion incident:
- Rather than a flat per-turn count division ($\text{frac} = \text{cnt} / \text{total\_turns}$), credits are apportioned proportionally to each turn's rate-card dollar cost (`estimated_cost_usd`):
  $$\text{frac}_i = \frac{\sum_{t \in C_i} \text{estimated\_cost\_usd}(t)}{\sum_{t \in I} \text{estimated\_cost\_usd}(t)}$$
- This ensures that high-cost reasoning models (e.g. Claude Opus 4.6 at ~$0.20–$0.30/turn) shoulder their true proportional share of billing deductions when running concurrently with low-cost mechanical models (e.g. Flash Lite at ~$0.002/turn).

---

## 9. Sliding-Window Recovery Trajectory Schema (ADR-025)

Attached to `payload['quotas']['rolling_5h']`, `payload['quotas']['gemini_5h']`, and `payload['quotas']['cg_5h']`:

```json
"recovery_trajectory": {
  "window_hours": 5.0,
  "start_time": "2026-09-07T20:45:00+00:00",
  "end_time": "2026-09-08T01:45:00+00:00",
  "initial_used_tokens": 156000000,
  "initial_available_pct": 7.14,
  "capacity_tokens": 168000000,
  "minutes_to_safe_zone": 42,
  "minutes_to_comfortable_zone": 115,
  "minutes_to_full_recovery": 285,
  "intervals_15m": [
    {
      "index": 0,
      "minutes_from_now": 0,
      "timestamp": "2026-09-07T20:45:00+00:00",
      "tokens_recovered_in_bucket": 0,
      "cumulative_tokens_recovered": 0,
      "projected_tokens_used": 156000000,
      "projected_available_tokens": 12000000,
      "projected_available_pct": 7.14
    },
    {
      "index": 1,
      "minutes_from_now": 15,
      "timestamp": "2026-09-07T21:00:00+00:00",
      "tokens_recovered_in_bucket": 18500000,
      "cumulative_tokens_recovered": 18500000,
      "projected_tokens_used": 137500000,
      "projected_available_tokens": 30500000,
      "projected_available_pct": 18.15
    }
  ],
  "next_roll_offs": [
    {
      "turn_timestamp": "2026-09-07T15:52:10+00:00",
      "age_out_timestamp": "2026-09-07T20:52:10+00:00",
      "minutes_remaining": 7,
      "tokens_to_recover": 2150000,
      "model_name": "Gemini 3.8 Flash (High)",
      "model_id": "1318"
    }
  ]
}
```

### 9.1 Invariant: Context Caching TTL vs. Sliding-Window Quota Age-Out
- **Context Caching (Prompt Prefix Cache)**:
  - Ephemeral server-side RAM cache in Google Gemini / Vertex AI infrastructure.
  - Short TTL (typically 1 hour default).
  - Provides a 90% input cost discount ($0.075 / 1M vs $0.75 / 1M) on consecutive turns sharing identical prompt prefixes.
  - Does **not** hold or lock account quota for 5 hours.
- **5-Hour Rolling Quota (Sliding Rate Limiter)**:
  - Account-level rate limiter evaluating usage over a strict moving 300-minute window: $\text{Used}(T) = \sum_{t > T - 5\text{h}} \text{Cost}(t)$.
  - Individual turns age out exactly at `timestamp + 5 hours`, incrementally restoring available headroom.
  - Empirical verification confirmed via local SQLite database microsecond timestamps matching Connect-RPC `RetrieveUserQuotaSummary` live responses.

### 9.2 Milestone-Preserving Trajectory Point Downsampling (ADR-025b)
To prevent massive JSON payload bloat while avoiding blind truncation of long sessions (which could truncate all points into an early burst and flatline the graph), `downsample_trajectory_points()` enforces:
1. **Full-Window Span**: Preserves initial points ($T \approx 0$) and closing points ($T \approx 300\text{m}$) so the curve completes to 100% capacity.
2. **Spike Retention**: Preserves the top 15 largest individual turns across the window by tokens recovered.
3. **Milestone Crossings**: Preserves the exact turns crossing 50% (Safe Zone) and 80% (Comfortable).
4. **Stratified Sampling**: Selects the largest turn in each 15-minute bucket across the 20 uniform intervals.

---

## 10. Standalone Telemetry Package & Canonical Model Census (ADR-040)

The core pure-Python parser and reader are packaged in `antigravity_telemetry/` with zero third-party dependencies:

### 10.1 Package Data Contract (`read_all_turns() -> List[Dict[str, Any]]`)
Each turn dictionary returned conforms to:
```json
{
  "convo_id": "00000000-0000-0000-0000-000000000001",
  "step_idx": 15,
  "timestamp": "2026-09-13T12:00:00+00:00",
  "model_id": "1318",
  "prompt_tokens_uncached": 12500,
  "cached_tokens": 85000,
  "total_input_tokens": 97500,
  "output_tokens_total": 3500,
  "thinking_tokens": 1500,
  "answer_tokens": 2000,
  "cache_hit_ratio_pct": 87.18,
  "response_id": "cxacat7FNcfmxN8PuNaviAI",
  "agent_id": "bot-68ca7b9b",
  "session_id": "session-42"
}
```

### 10.2 Canonical 19-Model Census (`models.json`)
The package embeds `models.json` containing all 19 internal runtime model identifiers calibrated for Antigravity:
```json
{
  "1318": { "name": "Gemini 3.8 Flash (High)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "high" },
  "1319": { "name": "Gemini 3.8 Flash (Medium)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "medium" },
  "1320": { "name": "Gemini 3.8 Flash (Low)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "low" },
  "1298": { "name": "Gemini 3.7 Flash (High)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "high" },
  "1299": { "name": "Gemini 3.7 Flash (Medium)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "medium" },
  "1300": { "name": "Gemini 3.7 Flash (Low)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "low" },
  "1071": { "name": "Gemini 3.6 Flash (High)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "high" },
  "1072": { "name": "Gemini 3.6 Flash (Medium)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "medium" },
  "1073": { "name": "Gemini 3.6 Flash (Low)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "low" },
  "1016": { "name": "Gemini 3.1 Pro (High)", "family": "gemini-pro", "provider": "google", "reasoning_effort": "high" },
  "1036": { "name": "Gemini 3.1 Pro (Low)", "family": "gemini-pro", "provider": "google", "reasoning_effort": "low" },
  "1050": { "name": "Gemini Flash Lite (Subagent)", "family": "gemini-flash-lite", "provider": "google", "reasoning_effort": "none" },
  "1322": { "name": "Gemini Fast Agent Assistant", "family": "gemini-flash", "provider": "google", "reasoning_effort": "none" },
  "1132": { "name": "Gemini Fast Agent (Legacy)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "none" },
  "1301": { "name": "Gemini Experimental Agent", "family": "gemini-flash", "provider": "google", "reasoning_effort": "none" },
  "1035": { "name": "Claude Sonnet 4.6 (Thinking)", "family": "claude-sonnet", "provider": "anthropic", "reasoning_effort": "thinking" },
  "1026": { "name": "Claude Opus 4.6 (Thinking)", "family": "claude-opus", "provider": "anthropic", "reasoning_effort": "thinking" },
  "1020": { "name": "Gemini Search Agent", "family": "gemini-flash", "provider": "google", "reasoning_effort": "none" },
  "342": { "name": "GPT-OSS 120B (Medium)", "family": "gpt-oss", "provider": "openai", "reasoning_effort": "medium" }
}
```
All entries are strictly decoupled from commercial pricing, quotas, plans, and currencies.

---

## 11. Workload Governance & Pre-Flight Capacity Budgeting (ADR-041)

### 11.1 Deterministic Pre-Flight Gate (`scripts/agy_quota.py --can-i-run`)
Automated agents and multi-agent swarms execute capacity checks prior to launching heavy workloads:
- Evaluates token, cost, and cache trajectory across 5 standard multi-agent archetypes (`deep_refactor_swarm`, `codebase_audit`, `rapid_prototyping_burst`, `claude_opus_deep_dive`, `subagent_fleet`) or custom parameter sets.
- Assesses rolling 5-hour burst capacity and weekly macro-capacity against active subscription tier (`ultra_5x`, `pro`, `enterprise_5x`).
- Process exit code contract:
  - `exit 0`: `SAFE / PROCEED` (workload fits comfortably within available quota headroom).
  - `exit 1`: `BLOCKED / 429 RISK` (workload would trigger Claude/GPT burst lockout, weekly exhaustion, or unpermitted credit spillover).
- Gated spillover control: Pass `--allow-spillover` to authorize Gemini models drawing from the Google One prepaid credit bank during 5-hour burst exhaustion.

### 11.2 Byte-Deterministic Standup Digest (`scripts/export_dashboard.py --markdown`)
Exports structured Markdown standup digests summarizing token throughput, cache efficiency, avoided API cost, AI credit debits, and provider quota headroom with zero wall-clock variance (ADR-004). Available via CLI and header clipboard button in `dashboard/index.html`.


