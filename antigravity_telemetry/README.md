# antigravity_telemetry

> **Zero-dependency, pure-Python wire protocol telemetry engine for Google Antigravity.**

Extract conversation turns, token consumption, context cache hits, thinking tokens, and tool invocations directly from your local Antigravity runtime—with zero compiled protobuf stubs and zero third-party dependencies.

---

## Key Features

- **Zero Third-Party Dependencies**: Pure standard library (`sqlite3`, `pathlib`, `json`, `datetime`, `re`, `typing`).
- **Safe Read-Only SQLite Connector**: Strictly enforces URI `?mode=ro` (ADR-001) with exponential-backoff retry loops resilient to active Language Server WAL checkpoints.
- **Pure-Python Wire Decoder**: Decodes raw protobuf byte streams (`steps.metadata`, `steps.step_payload`, `steps.error_details`) into structured token, tool, and sub-millisecond TTFT/turn latency metrics.
- **Canonical Model Census (Schema v2)**: Standardized catalog (`models.json`) covering Gemini 4 Hydrogen (`XHigh`–`Low`), Carbon, Argon, Orchestrator Planners & Executor, Gemini 3.8 Flash, Claude Opus/Sonnet 5.5, and historical models with zero pricing or quota coupling.

---

## Installation & Vendoring

Install via pip or vendor the directory directly into any agent project:

```bash
# Editable install from repo root
pip install -e .

# Or copy antigravity_telemetry/ into your project tree
cp -r antigravity_telemetry /path/to/your/project/
```

---

## Python API Usage

```python
import antigravity_telemetry as agy

# 1. Read all model generation turns across all local Antigravity conversations
turns = agy.read_all_turns()
print(f"Total turns: {len(turns):,}")

for turn in turns[:3]:
    print(f"[{turn['timestamp']}] Model {turn['model_id']}: "
          f"In={turn['total_input_tokens']:,} (Cached: {turn['cache_hit_ratio_pct']}%), "
          f"Out={turn['output_tokens_total']:,} (Thinking: {turn['thinking_tokens']:,})")

# 2. Discover conversations and extract authoritative workspace metadata
conversations = agy.discover_all_conversations()
for c in conversations[:3]:
    print(f"Session {c['convo_id'][:8]} | Workspace: {c['workspace_name']} ({c['git_branch']})")

# 3. Decode arbitrary protobuf wire bytes without stubs
fields = agy.decode_wire_protobuf(raw_bytes)
```

---

## Standalone CLI Usage

```bash
# Dump all parsed turns as formatted JSON
python -m antigravity_telemetry dump --json

# List discovered conversations
python -m antigravity_telemetry conversations --json

# Inspect canonical schema v2 model census
python -m antigravity_telemetry models --json
```

---

## Canonical Model Families (`models.json`, Schema v2)

| Family | Representative Wire IDs | Canonical Names | Provider | Reasoning Effort |
|:---|:---|:---|:---|:---|
| `gemini-carbon` | `1427`, `1437`, `1438` | Gemini 4 Carbon (High / Medium / Low) | Google | High / Medium / Low |
| `gemini-argon` | `1417`, `1418`, `1419` | Gemini 4 Argon (High / Medium / Low) | Google | High / Medium / Low |
| `gemini-hydrogen` | `1528`, `1525`, `1526`, `1527` | Gemini 4 Hydrogen (XHigh / High / Medium / Low) | Google | XHigh / High / Medium / Low |
| `gemini-orchestrator` | `1667`, `1681`, `1669` | Orchestrator (Carbon / Argon) & Executor (Hydrogen) | Google | High / Adaptive |
| `gemini-flash` | `1318`, `1319`, `1320`, `1198`, `1322` | Gemini 3.8 Flash & Flash Lite / Fast Agent | Google | High / Medium / Low |
| `claude-opus` | `1402`, `1401`, `1400` | Claude Opus 5.5 (High / Medium / Low) | Anthropic | High / Medium / Low |
| `claude-sonnet` | `1405`, `1404`, `1403` | Claude Sonnet 5.5 (High / Medium / Low) | Anthropic | High / Medium / Low |
| Historical / Sunset | `1016`, `1036`, `1026`, `1035`, `342`, etc. | Gemini 3.1 Pro, Claude 4.6, Gemini 3.6/3.7 Flash, GPT-OSS 120B | Multi | Preserved for historical replay |

---

## Safety & Invariants

1. **Strict Read-Only Access (`?mode=ro`)**: Connections open with SQLite URI read-only flag. Telemetry extraction never modifies Antigravity databases.
2. **Zero Network Calls**: Purely offline, deterministic local processing.
3. **Event Sourcing Invariant**: Antigravity SQLite databases remain the sole systems of record; parsed turns are disposable read projections.

---

## Technical Specifications & Research

- **Wire Format & Field Schemas**: See [`docs/TELEMETRY_SPEC.md`](../docs/TELEMETRY_SPEC.md) for full protobuf field IDs, wire types, and turn taxonomy.
- **Architecture & Telemetry Whitepaper**: See [`docs/FINDINGS.md`](../docs/FINDINGS.md) for runtime analysis of Antigravity quotas, Google One credit reconciliation, and context caching mechanics.

---

## License

MIT License. See repository `LICENSE`.

