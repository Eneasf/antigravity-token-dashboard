# Milestone M24: Subagent Swarm Lineage, Tool Analytics & Reverse Engineering Whitepaper

**Date**: 12 September 2026  
**Branch**: `feat/subagent-swarm-and-findings`  
**ADR References**: ADR-007, ADR-018, ADR-020, ADR-037

---

## 1. Background & Objectives

As modern software engineering workflows in Google Antigravity shifted from single-threaded conversational turns to autonomous multi-agent swarms, the developer was left blind to the structural execution topologies, subagent routing tiers, and tool security dynamics underpinning each workspace task. Furthermore, despite extensive telemetry collection across 147 local conversation databases, no authoritative reference whitepaper synthesized the runtime SQLite schemas, Connect-RPC quota contracts, Google One credit accounting, context cache mechanics, and KV cache eviction boundaries.

Milestone M24 delivers four core architectural achievements:
1. **Subagent Swarm Lineage Engine (`src/swarm.py`)**:
   - Reconstructs parent-child conversational DAGs by fusing `invoke_subagent` calls from `tool_calls_archive` and session records in `data/antigravity_vault.db` and SQLite telemetry.
   - Computes multi-agent swarm economics: aggregate swarm tokens (prompt, cached, output, thinking), total wall-clock duration, avoided API value, AI credits debited, and 3-tier subagent distribution (`flash_lite` mechanical vs. `flash` engineering vs. `pro` architecture).
2. **Runtime Tool & Skill Execution Analytics (`src/tool_analytics.py`)**:
   - Analyzes tool invocation frequencies, error rates, and security sandbox bypass ratios across 10,197 tool executions and 23 native IDE tools.
   - Detects the empirical 47.8% sandbox bypass ratio on `run_command` and tracks skill activation frequencies across 102+ installed skills.
3. **Authoritative Reverse-Engineering Whitepaper (`docs/FINDINGS.md`)**:
   - A 378-line technical reference paper documenting the internal mechanics of Google Antigravity: runtime SQLite storage, dual-track quota silos, Connect-RPC protocols, Google One credit billing (£23.99 / 2,500 credits), 94% context cache efficiency, cross-provider KV cache eviction, subagent routing taxonomy, and three empirical production case studies.
4. **Interactive Swarm Visualizer & Tool UI (`dashboard/`)**:
   - Implements a dedicated **Swarms & Tools** tab in `dashboard/index.html` featuring a master/detail swarm explorer, pure responsive SVG DAG visualizer with smooth cubic Bézier curves, interactive node inspector, tool performance matrix with visual error/bypass progress bars, and an active skills showcase.
   - Retains 100% offline `file:///` execution without external CDN or build dependencies.

---

## 2. Architecture & Deliverables

### A. Subagent Swarm Lineage Engine (`src/swarm.py`)

- **Tier Classification**: Maps model IDs to architectural tiers:
  - Tier 1 (Mechanical Execution): Model `1050` (`Gemini Flash Lite Subagent`), $0.25/$1.50 per MTok, 0.35x quota weight.
  - Tier 2 (Standard Engineering): Model `1322` (`Gemini Fast Agent Assistant`), $0.75/$3.75 per MTok, 1.00x quota weight.
  - Tier 3 (Complex Architecture): Model `1036` (`Gemini 3.1 Pro Low Reasoning`), $2.00/$12.00 per MTok, 2.80x quota weight.
- **DAG Construction**: Identifies swarm root conversations, traverses child subagent calls, associates conversation metadata, and builds adjacency lists with cycle-breaking safeguards.

### B. Tool Execution & Skill Performance Analytics (`src/tool_analytics.py`)

- **Security Sandbox Bypass**: Detects `BypassSandbox: true` flags on `run_command` invocations (profiling 2,593 bypasses out of 5,423 calls = 47.8% bypass ratio).
- **Error Heuristics**: Parses exit codes, exception traces, and command failure snippets from tool execution outputs.
- **Categorization**: Groups tools into `terminal`, `filesystem`, `search`, `subagent`, `browser`, `vision`, and `mcp`.

### C. Reverse-Engineering Whitepaper (`docs/FINDINGS.md`)

| Section | Topic | Key Insight |
|---|---|---|
| §1 | Runtime SQLite Architecture | `conversations/*.db` layout, WAL mechanics, protobuf `steps.metadata` wire fields. |
| §2 | Dual-Track Quota Silos | Gemini (Thursday 18:00 UTC cycle reset + 5h burst) vs. Claude/GPT (rolling 7d + hard 429 lockout). |
| §3 | Connect-RPC Quota Synchronization | Port 42124 local language server RPC and protocol buffers. |
| §4 | Google One Credit Billing Reconciliation | £23.99 / 2,500 credits add-on packs, 429 exhaustion window reconciliation. |
| §5 | Context Caching & KV Cache Eviction | 94% cache efficiency; 100% KV cache eviction on cross-provider model flips. |
| §6 | Subagent Routing Taxonomy | 3-tier routing matrix (1050, 1322, 1036) and reasoning intensity sliders. |
| §7 | Tool Execution & Security Boundaries | Sandbox bypass ratio analysis and tool safety. |
| §8 | Empirical Case Studies | Weekly quota cliff, Claude unthrottled burst, multi-agent refactor swarm. |
| §9 | Implementation Reference | Architecture mapping to project modules. |

### D. Interactive Offline Frontend Components

- **`#view-swarms`** in `dashboard/index.html`: KPI banner, master list with duration & token badges, detail view with SVG DAG container (`#swarm-dag-container`), node inspector drawer (`#swarm-node-detail`), tool analytics table, and active skills showcase.
- **`dashboard/styles.css`**: Styling for `.swarm-card`, `.swarm-dag-svg`, `.swarm-node`, `.swarm-edge`, `.tier-pill` (`tier-mechanical`, `tier-engineering`, `tier-architecture`), and tool progress bars.
- **`dashboard/app.js`**: `renderSwarmsView()`, `selectSwarm()`, `renderSwarmDag()` (responsive SVG Bézier curves, tier-coded nodes, interactive click selection), `inspectSwarmNode()`, and `renderToolAnalytics()`.

---

## 3. Verification & Quality Gates

All 6 acceptance gates for Milestone 24 verified cleanly:

| Gate | Check | Expectation | Measured Proof |
|---|---|---|---|
| **V113** | `python3 -c "from src.swarm import extract_swarm_lineage; swarms=extract_swarm_lineage(); assert len(swarms) >= 5; s=swarms[0]; assert 'swarm_id' in s and 'total_swarm_tokens' in s and 'tier_breakdown' in s; print(f'Verified: Discovered {len(swarms)} swarms with economics.')"` | `Verified: Discovered ... swarms with economics.` | Passed: Discovered 12 swarms with multi-agent economics. Exit code 0. |
| **V114** | `python3 -c "from src.tool_analytics import extract_tool_analytics; t=extract_tool_analytics(); assert t['total_tool_calls'] >= 10000; assert len(t['tools']) >= 15; assert 'run_command' in t['tools']; assert 'sandbox_bypass_pct' in t['tools']['run_command']; print(f'Verified: Tool analytics extracted {t[\"total_tool_calls\"]} calls across {len(t[\"tools\"])} tools.')"` | `Verified: Tool analytics extracted ... calls across ... tools.` | Passed: Extracted 10,197 calls across 23 tools (47.8% sandbox bypass on `run_command`). Exit code 0. |
| **V115** | `python3 scripts/export_dashboard.py && python3 -c "import json; d=json.load(open('dashboard/data.json')); assert 'swarms' in d; assert 'tool_analytics' in d; assert len(d['swarms']['swarms']) >= 5; assert d['tool_analytics']['total_tool_calls'] >= 10000; print('Verified: Swarm and tool analytics injected into export payload.')"` | `Verified: Swarm and tool analytics injected into export payload.` | Passed: Injected 12 swarms and 10,197 tool calls into export payload (`data.js` and `data.json`). Exit code 0. |
| **V116** | `test -f dashboard/app.js && node -c dashboard/app.js && python3 -c "h=open('dashboard/index.html').read(); j=open('dashboard/app.js').read(); c=open('dashboard/styles.css').read(); assert 'tab-swarms' in h; assert 'view-swarms' in h; assert 'swarm-dag-container' in h; assert 'renderSwarmsView' in j; assert 'renderSwarmDag' in j; assert 'renderToolAnalytics' in j; assert '.swarm-node' in c; print('Verified: Swarms and tools UI DOM elements, JS renderers, and CSS tokens verified cleanly.')"` | `Verified: Swarms and tools UI DOM elements, JS renderers, and CSS tokens verified cleanly.` | Passed: DOM elements, SVG DAG renderer, JS handlers, and CSS tokens verified; `node -c dashboard/app.js` reports 0 errors. Exit code 0. |
| **V117** | `python3 -c "c=open('docs/FINDINGS.md').read(); assert len(c.splitlines()) >= 300; assert '1050' in c and '1322' in c and '1036' in c; assert 'Connect-RPC' in c; assert '23.99' in c; assert 'RESOURCE_EXHAUSTED' in c; assert 'KV cache' in c or 'KV Cache' in c; print('Verified: FINDINGS.md whitepaper complete and comprehensive.')"` | `Verified: FINDINGS.md whitepaper complete and comprehensive.` | Passed: 378 lines whitepaper verifying all required runtime terms. Exit code 0. |
| **V118** | `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py` | 100% tests pass (0 failures, 0 errors) | Passed: 129 unit tests + 6 integrity tests pass cleanly. Exit code 0. |

---

## 4. Swarm Token Economics, Cache Efficiency & Project Intelligence (Post-Review Addendum)

Following empirical review of live multi-agent execution telemetry, four critical enhancements were implemented:

1. **True-Roots DAG Deduplication**:
   - Intermediate subagents that invoke further child workers (e.g. `Synthesizing Python Learning Material` invoking intermediate managers that subsequently spawn leaf specialists) no longer generate duplicate root swarm entries.
   - Filtered roots strictly via authoritative set complement: `true_roots = [p for p in all_parents if p not in child_to_parent]`.
   - Result: Exactly **10 authoritative autonomous swarms** across 6 distinct projects (24 total subagents), eliminating the redundant 50.6M token duplicate.

2. **Cost Framing & Avoided API Value Segregation**:
   - Reframed swarm economics: standard Google Antigravity Pro subscription usage has £0.00 marginal spend.
   - Distinctly separated **Imputed API Value / Avoided Cost** (developer rate card equivalent, £30.67 portfolio value) from **Actual Overage Spend** (0 AI credit debits, £0.00 actual overage).
   - Added clear UI badges (`✓ 100% Pro covered • £0.00 actual overage`) preventing false perception of out-of-pocket charges.

3. **Token Velocity & Prompt Cache Metrics**:
   - Elevated token volume, cache hit ratio (`% cached`), and token generation velocity (`toks/turn` and `toks/min`) above monetary figures.
   - Swarms demonstrate an exceptional **92.3% aggregate prompt cache hit ratio** (210.7M cached tokens out of 228.4M input tokens).
   - Quantified reasoning intensity: **672,504 thinking tokens** generated across 10 swarms, averaging **107,010 tokens/turn** operational velocity.

4. **Multi-Criteria Sorting & Project Filtering**:
   - Default sorting orders swarms chronologically by most recent activity timestamp descending (`last_activity`).
   - Added interactive project dropdown (`#swarm-project-filter`) and multi-criteria sort selector (`#swarm-sort-select`: Recent, Tokens, Cache %, Subagents, Value).
   - Added cross-tab project navigation links (`jumpToProject()`) connecting swarms directly to the Projects tab.

