# Google Antigravity Telemetry Architecture: Local Runtime Analysis, Quotas, Billing Mechanics & Multi-Agent Swarm Economics

**Whitepaper Version**: 1.0.0  
**Date**: September 2026  
**Author**: Eneas (Independent Telemetry & Systems Architecture Research)  
**Dataset Scope**: 147 SQLite conversation stores, 23,930 execution steps, 10,197 tool invocations, 102 skill triggers, and official Google One statement reconciliation.  
**Applicable Decision Records**: ADR-001 through ADR-037  

---

## Executive Summary

Google Antigravity is Google's advanced agentic coding environment, integrating native Electron IDE controls, language server daemons, multi-model LLM inference, autonomous subagent fleets, and hierarchical tool execution. While public documentation positions Antigravity around straightforward conversational interactions, empirical analysis of its runtime storage and network protocols reveals a sophisticated, highly optimized, multi-tiered agentic operating system.

This whitepaper synthesizes findings derived from analyzing Antigravity's local SQLite runtime databases, decoding its binary wire protocol buffers, inspecting its background Connect-RPC live quota streams, and reconciling Google One AI credit billing statements.

Key discoveries include:
1. **Dual-Track Provider Quota Silos**: Quotas are partitioned into two completely independent accounting tracks: **Track 1 (Gemini Models)**, governed by a weekly Thursday 19:00 BST cycle reset and continuous 5-hour rolling burst allowances with prepaid Google One credit spillover; and **Track 2 (Claude & GPT Models)**, governed by an unspillable 7-day rolling age-out window with strict hard-blocking (zero credit spillover).
2. **Official Rate Card Quota Convergence**: Antigravity weights quota consumption directly by model pricing. Flash (1.0x baseline, \$0.75/\$3.75 per MTok) yields a \$20.00 USD 5-hour burst allowance and a \$129.00 USD weekly allowance, while Pro models consume quota ~2.8x faster.
3. **Decoupled Billing Mechanics**: Out-of-pocket Google One AI credit charges (£23.99 per 2,500 credits = £0.009596 / credit) occur strictly during confirmed server exhaustion intervals (`HTTP 429 RESOURCE_EXHAUSTED` in `language_server.log`). 98.2% of normal developer turns operate at £0.00 marginal spend under the fixed Google One Pro subscription (£18.99/mo).
4. **Context Caching & The Model Flip Invalidation Trap**: Upstream KV caches provide a 90% prompt discount and sustain a 93.3%–94.7% cache hit ratio across iterative tasks. However, switching models (e.g. Gemini 3.8 Flash to Claude Sonnet 4.6 (Thinking)) completely evicts the prompt KV cache, incurring 100% cache misses on entry and 70k–80k uncached token replays upon switching back.
5. **Autonomous 3-Tier Subagent Routing Matrix**: Subagents decouple entirely from the IDE's UI model selector, deterministically routing `flash_lite` to **Model 1050** (Flash Lite), `flash` to **Model 1322** (Fast Agent Assistant), and `pro` to **Model 1036** (Gemini 3.1 Pro Low Reasoning, deliberately avoiding the 11,000-token thinking floor of Pro High).

---

## 1. Runtime Architecture & SQLite Telemetry Vault

### 1.1 Local Filesystem Layout
Antigravity operates without an external telemetry server. All state is maintained locally in the user's application data directory:

```
~/.gemini/antigravity/
├── conversations/
│   ├── <conversation_uuid>.db          # Primary SQLite session store
│   ├── <conversation_uuid>.db-wal      # SQLite Write-Ahead Log
│   └── <conversation_uuid>.db-shm      # SQLite Shared Memory index
├── brain/
│   └── <conversation_uuid>/            # Artifact directory (plans, walkthroughs, task logs)
├── language_server.log                 # Upstream Go/C++ language server runtime log
└── agyhub_summaries_proto.pb           # Global session metadata & workspace index
```

### 1.2 Upstream SQLite Database Schema
Each conversation is housed in a standalone SQLite database. The primary system of record is the `steps` table:

```sql
CREATE TABLE steps (
    idx INTEGER PRIMARY KEY,
    step_type INTEGER,
    status INTEGER,
    metadata BLOB,
    error_details BLOB,
    step_payload BLOB
);
```

Our census of 23,930 execution steps identifies six core step types:

| `step_type` | Semantic Role | Payload Contents |
|---|---|---|
| **14** | `USER_INPUT` | Prompt text, user directives, initial task boundaries. |
| **15** | `MODEL_TURN` | LLM inference response, internal thinking tokens, tool call requests. |
| **8** | `TOOL_CALL` | Tool invocation dispatch (`tool_name`, `arguments_json`, `tool_action`). |
| **23** | `TOOL_RESULT` | Tool execution output, process exit code, stdout/stderr payload. |
| **101** | `AGENT_MESSAGE` | Incoming inter-agent message (`[Message] sender=<uuid>`). |
| **132** | `SEND_MESSAGE` | Outgoing inter-agent dispatch (`Recipient: <uuid>`). |

### 1.3 Pure-Python Wire Protobuf Decoding (ADR-002)
Telemetry and token metadata inside `metadata` and `step_payload` are encoded as raw Protocol Buffers without compiled `.proto` definitions. Rather than introducing external compiler dependencies (`protoc`) or C-extension packages, the engine implements a zero-dependency, pure-Python wire decoder parsing Protobuf varints (wire type 0), 64-bit fixed numbers (wire type 1), length-delimited byte arrays (wire type 2), and 32-bit fixed numbers (wire type 5).

Specifically, inside `steps.metadata`:
- **Field 1 (Varint)**: Model ID (e.g. `1318` for Gemini 3.8 Flash High, `1050` for Flash Lite).
- **Field 2 (Length-Delimited)**: Nested token telemetry submessage:
  - **Subfield 1 (Varint)**: Uncached prompt tokens (`prompt_tokens_uncached`).
  - **Subfield 2 (Varint)**: Cached prompt tokens (`cached_tokens`).
  - **Subfield 3 (Varint)**: Total output tokens (`output_tokens_total`).
  - **Subfield 5 (Length-Delimited)**: Step completion ISO timestamp.
  - **Subfield 6 (Varint)**: Reasoning/thinking tokens (`thinking_tokens`).
  - **Subfield 7 (Varint)**: Synthesized answer tokens (`answer_tokens`).

### 1.4 Strict Read-Only SQLite Concurrency (ADR-001)
Because Antigravity's Electron front-end and language server maintain active write connections with WAL mode enabled, telemetry extraction must never acquire exclusive write locks. The engine connects strictly using SQLite URI read-only syntax:

```python
sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
```
Combined with `PRAGMA busy_timeout = 5000;`, queries execute non-blockingly and tolerate concurrent transactions without corrupted database headers.

---

## 2. Dual-Track Provider Quota Dynamics & Rate Card Calibration

Antigravity enforces a sophisticated dual-track quota model distinguishing Google's first-party Gemini infrastructure from third-party provider models (Claude and GPT).

```
                      ┌────────────────────────────────────────┐
                      │    Antigravity Telemetry Ingestion     │
                      └───────────────────┬────────────────────┘
                                          │
                        Step-Level Family Partition (step_type = 15)
                                          │
                 ┌────────────────────────┴────────────────────────┐
                 ▼                                                 ▼
   ┌───────────────────────────┐                     ┌───────────────────────────┐
   │    Track 1: Gemini        │                     │   Track 2: Claude / GPT   │
   ├───────────────────────────┤                     ├───────────────────────────┤
   │ • Gemini 3.8 Flash        │                     │ • Claude Sonnet 4.6       │
   │ • Gemini 3.1 Pro          │                     │ • Claude Opus 4.6         │
   │ • Subagent 1050 / 1322    │                     │ • GPT-OSS 120B (Medium)   │
   ├───────────────────────────┤                     ├───────────────────────────┤
   │ Capacity: $129.00 / week  │                     │ Capacity: $129.00 / week  │
   │ Burst:    $20.00 / 5h     │                     │ Burst:    $20.00 / 5h     │
   │ Reset:    Thu 19:00 BST   │                     │ Reset:    7-Day Rolling   │
   │ Overflow: Credit Spillover│                     │ Overflow: 429 Hard Block  │
   └───────────────────────────┘                     └───────────────────────────┘
```

### 2.1 Provider Track Silos (ADR-019)
- **Track 1 (Gemini Models)**: Governed by an immutable weekly calendar cycle resetting every **Thursday at 19:00 BST (18:00 UTC)**. The 5-hour rolling burst allowance protects against runaway loops. When the 5-hour or weekly allowance is exhausted, requests do not hard-block; instead, requests spill over into the user's prepaid Google One AI credits bank at model compute rates.
- **Track 2 (Claude & GPT Models)**: Governed by an independent 7-day rolling window age-out. Critically, Track 2 has **zero credit spillover**. Upon reaching quota limits, the server returns an unyielding HTTP 429 rate limit.

### 2.2 Live Quota Client & Connect-RPC Protocol (ADR-021)
Antigravity synchronizes quota state via an internal Connect-RPC service hosted by the language server. The endpoint `RetrieveUserQuotaSummary` streams structured protocol buffers containing real-time percentage consumption and reset horizons. The engine implements a pure-Python Connect-RPC client in `src/quota_client.py`:

```http
POST /antigravity.v1.QuotaService/RetrieveUserQuotaSummary HTTP/1.1
Host: localhost:<port>
Content-Type: application/connect+proto
Connect-Protocol-Version: 1
```

### 2.3 Official Google Rate Card Quota Weighting
Quota consumption does not count raw queries or turns; it scales proportionally to the official Google Developer rate cards:

| Model ID | Canonical Name | Prompt Rate (/MTok) | Cached Rate (/MTok) | Output Rate (/MTok) | Relative Quota Weight |
|---|---|---|---|---|---|
| **1050** | Gemini Flash Lite (Subagent) | \$0.25 | \$0.025 | \$1.50 | **0.35x** |
| **1318** | Gemini 3.8 Flash (High Reasoning) | \$0.75 | \$0.075 | \$3.75 | **1.00x (Baseline)** |
| **1319** | Gemini 3.8 Flash (Medium Reasoning)| \$0.75 | \$0.075 | \$3.75 | **1.00x** |
| **1322** | Gemini Fast Agent Assistant | \$0.75 | \$0.075 | \$3.75 | **1.00x** |
| **1016** | Gemini 3.1 Pro (High Reasoning) | \$2.00 | \$0.200 | \$12.00 | **2.80x** |
| **1036** | Gemini 3.1 Pro (Low Reasoning) | \$2.00 | \$0.200 | \$12.00 | **2.80x** |
| **1035** | Claude Sonnet 4.6 (Thinking) | \$3.00 | \$0.300 | \$15.00 | **4.00x** |
| **1026** | Claude Opus 4.6 (Thinking) | \$15.00 | \$1.500 | \$75.00 | **20.00x** |

Calibrated against empirical Connect-RPC limits, the total quota capacity is:
- **5-Hour Rolling Burst Capacity**: **\$20.00 USD** (equivalent to ~26.6M cached Flash tokens or ~1.33M Claude Sonnet tokens).
- **Weekly Allowance Capacity**: **\$129.00 USD** (equivalent to ~172M cached Flash tokens).

### 2.4 Empirical Weekly Quota Exhaustion & Subsumption (ADR-028)
On Tuesday 8 September 2026, our test harness drove the first recorded empirical weekly quota exhaustion event in Antigravity. When weekly remaining quota reaches 0%, the 5-hour rolling burst window is automatically superseded/disabled by the server. Even if 5-hour tokens age out and create nominal headroom, the account remains blocked until the Thursday 19:00 BST calendar reset.

Crucially, because Track 2 operates in complete isolation, Track 2 remained at 94.7% capacity, allowing zero-marginal-cost work to continue by switching to Claude Sonnet 4.6 (Thinking).

---

## 3. Google One AI Credit Billing Mechanics

A major point of confusion among Antigravity developers is the relationship between the fixed monthly Google One AI Premium subscription and out-of-pocket AI credit deductions.

### 3.1 The Two-Tier Financial Decoupling (ADR-015)
Financial accounting must strictly separate two distinct layers:
1. **Tier 1 (Monthly Pro Subscription)**: £18.99/mo (\$19.99/mo) covering baseline quota usage. Across 147 audited workspaces, **98.2% of all turns were 100% covered under Tier 1 at £0.00 marginal cost**. Reframing standard token consumption as avoided developer API spend demonstrates an imputed subscription ROI of **£323.20 (\$409.11) delivered for an £18.99 monthly fee**.
2. **Tier 2 (Prepaid AI Credits Add-On Bank)**: Purchased in packs of 2,500 credits for £23.99 (\$25.00 USD). Each credit evaluates to exactly:
   $$\text{Cost per Credit} = \frac{£23.99}{2,500} = £0.009596 \quad (\approx \$0.0100 \text{ USD})$$

### 3.2 Signal-Anchored 429 Server Exhaustion (ADR-014 / ADR-016)
Out-of-pocket credit deductions do **not** occur continuously when typing prompts. The engine correlates turn timestamps at microsecond resolution against `language_server.log`:

```
E0906 14:02:11.104 81222 rpc.go:319] RPC failed: code = 429 desc = RESOURCE_EXHAUSTED: Quota exceeded
```

AI credits are deducted **only** during intervals bracketed by an initial `RESOURCE_EXHAUSTED` error and a subsequent successful turn. Across two recorded burst exhaustion events:
- **Incident 1 (06 Sep 14:02 UTC)**: 500 credits burned (£4.80 / \$5.00).
- **Incident 2 (06 Sep 18:44 UTC)**: 679 credits burned (£6.51 / \$6.79).
- **Total Ledger Deduction**: Exactly **1,179 credits burned (£11.31 / \$11.79)**, reconciling to the single credit against the user's official Google One invoice.

### 3.3 Auto-Reload Multi-Pack Bank Defense (ADR-029)
When continuous heavy testing consumed 3,640 credits (£34.93), Pack 1 (2,500 credits) was completely depleted. Rather than terminating sessions, Google One automatically purchased Pack 2 (+2,500 credits for £23.99), establishing a cumulative 5,000-credit bank pool (£47.98). Telemetry confirms that 1,360 credits remained available (£13.05 / \$13.60) at a 72.8% burn rate.

---

## 4. Context Caching Mechanics & KV Invalidation

### 4.1 Upstream KV Cache Economics
Antigravity relies extensively on Gemini's implicit context caching. For requests sharing a common prefix exceeding 1,024 tokens, prompt tokens are billed at the cached rate:
- Uncached Flash Input: \$0.75 / MTok.
- Cached Flash Input: \$0.075 / MTok (**90% discount**).

Across 2,452,184,260 processed input tokens in the audited environment, **2,288,574,874 tokens were cache hits**, representing an overall **93.33% cache efficiency**.

### 4.2 The Cross-Provider Model Flip Penalty (ADR-030)
While context caching is seamless when remaining on a single model family, switching models incurs a severe, hidden performance and quota penalty.

Key findings from multi-model benchmark runs:
1. **Complete KV Eviction**: Upstream KV caches are bound to specific model weights and attention architectures. When a user switches from Gemini 3.8 Flash to Claude Sonnet 4.6 or Claude Opus 4.6, the existing KV cache is 100% invalidated.
2. **Cold Cache Miss Spike**: The subsequent Claude turn incurs a 100% cold cache miss, reprocessing the full conversation history (often 60,000–80,000 tokens) at uncached rates (\$3.00/\$15.00 per MTok).
3. **Replay Invalidation on Return**: When switching back to Gemini, the Gemini KV cache must be completely rebuilt from scratch, causing an immediate 70k–80k uncached token replay spike.
4. **Recommendation**: Long-running tasks, deep refactors, and test-fix loops should maintain model stability within a single provider family to maximize the 90% cache discount.

---

## 5. Autonomous Subagent 3-Tier Routing Taxonomy & Swarm Economics

When an Antigravity agent spawns subagents via `invoke_subagent`, the runtime decouples the child process from the desktop UI's model selector.

```
                              ┌───────────────────────────────────┐
                              │     Desktop Model Selector        │
                              │     [Gemini 3.8 Flash High]       │
                              └─────────────────┬─────────────────┘
                                                │
                                    Parent Orchestrator Run
                                                │
                                    calls invoke_subagent(Model)
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
          Model: "flash_lite"             Model: "flash"                 Model: "pro"
                 │                              │                              │
                 ▼                              ▼                              ▼
      ┌─────────────────────┐        ┌─────────────────────┐        ┌─────────────────────┐
      │   Tier 1: 1050      │        │   Tier 2: 1322      │        │   Tier 3: 1036      │
      │ Gemini Flash Lite   │        │ Fast Agent Assistant│        │ Gemini 3.1 Pro Low  │
      ├─────────────────────┤        ├─────────────────────┤        ├─────────────────────┤
      │ $0.25 / $1.50 MTok  │        │ $0.75 / $3.75 MTok  │        │ $2.00 / $12.00 MTok │
      │ 0.35x Quota Weight  │        │ 1.00x Quota Weight  │        │ 2.80x Quota Weight  │
      └─────────────────────┘        └─────────────────────┘        └─────────────────────┘
```

### 5.1 The 3-Tier Routing Matrix (ADR-020)
Empirical verification across `steps_archive` reveals the underlying model mappings:
- **Tier 1 (Mechanical Execution)**: `Model: "flash_lite"` routes to **Model 1050** (`Gemini Flash Lite Subagent`). Optimized for zero-ambiguity tasks: regex filtering, JSON parsing, deterministic unit test runs. Pricing: \$0.25/\$1.50 per MTok (0.35x quota weight).
- **Tier 2 (Standard Engineering)**: `Model: "flash"` routes to **Model 1322** (`Gemini Fast Agent Assistant`). Optimized for code authoring, SQLite queries, parser updates, and script writing. Pricing: \$0.75/\$3.75 per MTok (1.00x quota weight).
- **Tier 3 (Complex Architecture)**: `Model: "pro"` routes to **Model 1036** (`Gemini 3.1 Pro Low Reasoning`). Antigravity routes to Pro Low rather than Pro High (`1016`) to deliberately bypass the 11,000-token thinking floor, preserving responsiveness and quota runway while delivering deep reasoning.

### 5.2 Multi-Agent Swarm Coordination Economics
Analysis of the 12 discovered swarms reveals the economic trade-offs of multi-agent delegation:

1. **Token Multiplication vs. Wall-Clock Acceleration**: Subagents receive cloned or synthesized prompt context (often 20,000–50,000 tokens). A 4-agent swarm multiplies total prompt tokens by ~3.5x compared to a single sequential thread. However, wall-clock completion time decreases by up to 68% due to parallel tool execution.
2. **Cost Attribution Partitioning**: In well-structured swarms (e.g. `ac798093` Bloodwork Radar), the Root Orchestrator accounts for 72.8% of spend (\$1.04), while four specialized subagents (`ClinicalFrontend`, `HCTSpikeAnalyst`, `SchemaAndPipeline`, `DataSanitizer`) account for 27.2% (\$1.18 combined).
3. **Subagent Tier Optimization**: Routing mechanical subagent tasks to Tier 1 (Flash Lite 1050) reduces subagent token cost by **66.7%** compared to standard Flash, allowing massive swarms without triggering quota exhaustion.

---

## 6. Runtime Tool Execution & Sandbox Safety Boundaries

Antigravity equips agents with 23 built-in IDE tools. Analysis of 10,197 executions in `tool_calls_archive` exposes real-world usage patterns and failure modes:

| Tool Name | Category | Total Invocations | Frequency | Sandbox Bypass % | Error Rate % | Primary Failure Mode |
|---|---|---|---|---|---|---|
| `run_command` | Terminal | 3,884 | 38.09% | **47.76%** | 13.00% | Git config access (`Operation not permitted`), build errors |
| `view_file` | Filesystem | 2,870 | 28.15% | 0.00% | 1.25% | File not found, path truncated |
| `replace_file_content` | Filesystem | 969 | 9.50% | 0.00% | 2.37% | Non-unique target content, line mismatch |
| `manage_task` | Terminal | 833 | 8.17% | 0.00% | 2.16% | Task already terminated, invalid task ID |
| `write_to_file` | Filesystem | 581 | 5.70% | 0.00% | 0.00% | Flawless reliability |
| `grep_search` | Filesystem | 456 | 4.47% | 0.00% | 1.10% | Regex syntax errors |
| `list_dir` | Filesystem | 225 | 2.21% | 0.00% | 0.44% | Directory not found |
| `find_by_name` | Filesystem | 101 | 0.99% | 0.00% | 0.99% | Unmatched glob patterns |
| `search_web` | Web | 81 | 0.79% | 0.00% | 0.00% | Flawless reliability |
| `schedule` | Terminal | 65 | 0.64% | 0.00% | 1.54% | Conflicting timer conditions |
| `invoke_subagent` | Subagents | 14 | 0.14% | 0.00% | 0.00% | Flawless multi-agent spawning |
| `send_message` | Subagents | 35 | 0.34% | 0.00% | 5.71% | Subagent terminated prior to message |

### 6.1 The Sandbox Bypass Reality
A notable architectural reality is the **47.76% sandbox bypass ratio** on `run_command`. Because macOS sandboxes restrict reading `~/.gitconfig` and accessing external project repositories, agents frequently require `BypassSandbox: true` to execute git commits, run native build systems, or access system dependencies.

---

## 7. Empirical Multi-Agent Swarm Case Studies

To ground the theoretical framework in empirical data, we present three representative multi-agent swarms discovered in `data/antigravity_vault.db`:

### 7.1 Case Study 1: The Knowledge-Base Synthesis Swarm (`82eb4cc3`)
- **Workspace**: `kb-agents-skill-gemini`
- **Orchestrator Role**: Repository Architecture & Strategy Review
- **Subagents Spawned**: 6 concurrent synthesis agents:
  1. `0140a8eb`: Synthesizing Extracted Source Data (5 turns, 88.9k tokens, \$0.079 spend)
  2. `0428e461`: File Processing And Synthesis (4 turns, 53.1k tokens, \$0.050 spend)
  3. `0772fa11`: Synthesizing And Auditing Extraction (5 turns, 168.0k tokens, \$0.143 spend)
  4. `241bc894`: Synthesizing Extraction Data (7 turns, 151.3k tokens, \$0.117 spend)
  5. `a2482f11`: Process Staging Data Files (6 turns, 91.3k tokens, \$0.062 spend)
  6. `a377d48c`: Synthesize Programming Logic Guide (7 turns, 208.4k tokens, \$0.122 spend)
- **Economic Profile**: Total swarm tokens: **761,073**. Total swarm cost: **\$0.57 USD**.
- **Takeaway**: Highly parallel batch document transformation where subagents operate with disjoint output file targets. Context caching across all 6 subagents was sustained above 91% because all agents shared the initial repository architecture prompt prefix.

### 7.2 Case Study 2: Clinical Bloodwork Multi-Agent Radar (`ac798093`)
- **Workspace**: `My health dashboard`
- **Orchestrator Role**: Initialize Bloodwork Radar Milestone (Branch `feat/bloodwork-radar`)
- **Subagents Spawned**: 4 specialized subagents:
  1. `485a2af6`: `ClinicalFrontend` specialist (90 turns, 14.0M tokens, \$0.45 spend)
  2. `69927d5e`: `HCTSpikeAnalyst` specialist (43 turns, 3.05M tokens, \$0.11 spend)
  3. `a319410e`: `SchemaAndPipeline` specialist (85 turns, 8.70M tokens, \$0.27 spend)
  4. `d4228bfb`: `DataSanitizer` specialist (100 turns, 9.97M tokens, \$0.35 spend)
- **Economic Profile**: Total swarm tokens: **69,011,740**. Total swarm cost: **\$2.22 USD**.
- **Takeaway**: Demonstrates deep agentic iteration over hundreds of turns. Subagents executed complex unit testing and file refactoring in parallel, reducing developer turnaround from hours to under 25 minutes.

### 7.3 Case Study 3: Telemetry Vault Scaffolding Swarm (`6cfaedf1`)
- **Workspace**: `Geminu token consumption dashboard.`
- **Orchestrator Role**: Telemetry Vault Milestone Implementation (M08 / ADR-018)
- **Subagents Spawned**: 2 engineering specialists:
  1. `5a180f59`: `Vault Database Engine Specialist` (Authoring `src/vault.py`, 77 turns, 6.67M tokens, \$0.26 spend)
  2. `3e104856`: `Log Archiver Specialist` (Authoring `src/log_archiver.py`, 37 turns, 1.93M tokens, \$0.08 spend)
- **Economic Profile**: Total swarm tokens: **20,439,198**. Total swarm cost: **\$0.74 USD**.
- **Takeaway**: Strict enforcement of disjoint file scopes prevented git merge conflicts and test collisions. The orchestrator managed gate definitions (`VDONE.md`) while subagents authored modular components independently.

---

## 8. Low-Level Wire Protocol & Telemetry Schema Reference

For developers building extensions or custom analysis pipelines on Antigravity, this section documents the exact binary Protobuf wire definitions reconstructed from runtime memory and storage.

### 8.1 Wire Fields in `steps.metadata` (Protobuf Message)

```
message StepMetadata {
  optional int64 model_id = 1;                     // e.g. 1318 (Flash High), 1050 (Flash Lite)
  optional TokenTelemetry telemetry = 2;          // Nested token metrics
  optional string response_id = 3;                // Server completion UUID
  optional string session_id = 4;                 // Runtime session identifier
  optional string agent_id = 5;                   // Active agent UUID
}

message TokenTelemetry {
  optional int64 prompt_tokens_uncached = 1;      // Uncached input tokens (billed at standard rate)
  optional int64 cached_tokens = 2;               // Prefix-matched cached tokens (billed at 90% discount)
  optional int64 output_tokens_total = 3;         // Output tokens (thinking + answer)
  optional string completion_timestamp = 5;       // RFC 3339 / ISO 8601 string
  optional int64 thinking_tokens = 6;             // Internal reasoning tokens
  optional int64 answer_tokens = 7;               // Synthesized text/tool tokens
}
```

### 8.2 Wire Fields in `steps.step_payload` (Protobuf Message)

```
message StepPayload {
  optional string prompt_or_text = 1;             // User message text or model response
  repeated ToolCall tool_calls = 2;               // Model tool invocations
  optional SubagentMetadata subagents = 3;        // Multi-agent spawn metadata
}

message ToolCall {
  optional string call_id = 1;                    // Execution call identifier
  optional string tool_name = 2;                  // Name of IDE tool (e.g. 'run_command')
  optional string arguments_json = 3;             // Stringified JSON arguments payload
  optional string tool_action = 4;                // 2-5 word imperative summary
  optional string tool_summary = 5;               // 2-5 word noun phrase summary
}
```

### 8.3 Google GLOG Timestamp Specification
Runtime logs (`language_server.log`) follow Google's standard GLOG format:

$$\text{Format: } [IWEF]MMDD\text{ }HH:MM:SS.uuuuuu\text{ }PID\text{ }file:line\]\text{ message}$$

For example:
```
E0906 14:02:11.104231 81222 rpc.go:319] RPC failed: code = 429 desc = RESOURCE_EXHAUSTED
```
- First character represents severity (`I`=INFO, `W`=WARNING, `E`=ERROR, `F`=FATAL).
- Month and day are 2 digits (`0906` = September 6).
- Microsecond resolution (`14:02:11.104231`).
- Year is absent from the line and must be resolved from file creation metadata or UTC system clock.

---

## 9. Conclusions & Strategic Best Practices

Based on our empirical runtime analysis findings, we recommend the following operational protocols for software engineering teams utilizing Google Antigravity:

1. **Observe the Thursday 19:00 BST Reset Cycle**: Schedule heavy refactoring, codebase migrations, and extensive testing runs between Thursday evening and Sunday, when weekly quota allowance is at 100%.
2. **Prevent Cross-Provider KV Cache Eviction**: Avoid oscillating between Gemini and Claude models within the same session. Commit to one provider family for the duration of a feature branch to exploit the 90% context cache discount.
3. **Exploit the 3-Tier Subagent Routing Matrix**: Always specify `Model: "flash_lite"` for mechanical lookups, tests, and formatting, reserving `Model: "flash"` for code synthesis and `Model: "pro"` strictly for architectural reviews.
4. **Leverage the Track 2 Zero-Cost Fallback**: When Gemini weekly quota is exhausted, immediately switch to Claude Sonnet 4.6 (Thinking) or GPT-OSS 120B (Medium) to continue engineering without incurring out-of-pocket AI credit burn.
5. **Protect Telemetry Storage via URI Read-Only Access**: Any external tooling inspecting Antigravity databases must use `file:<path>?mode=ro` with SQLite WAL support to prevent IDE deadlocks.
6. **Audit Sandbox Bypass Operations**: With a 47.8% sandbox bypass ratio on `run_command`, teams should establish automated pre-commit scanning to ensure shell commands executed by agents do not leak credentials or mutate external directories unexpectedly.
