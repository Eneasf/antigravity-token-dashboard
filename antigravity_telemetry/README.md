# antigravity_telemetry

> **Zero-dependency, pure-Python wire protocol telemetry engine for Google Antigravity.**

Extract conversation turns, token consumption, context cache hits, thinking tokens, and tool invocations directly from your local Antigravity runtime—with zero compiled protobuf stubs and zero third-party dependencies.

---

## Key Features

- **Zero Third-Party Dependencies**: Pure standard library (`sqlite3`, `pathlib`, `json`, `datetime`, `re`, `typing`).
- **Safe Read-Only SQLite Connector**: Strictly enforces URI `?mode=ro` (ADR-001) with exponential-backoff retry loops resilient to active Language Server WAL checkpoints.
- **Pure-Python Wire Decoder**: Decodes raw protobuf byte streams (`steps.metadata`, `steps.step_payload`, `steps.error_details`) into structured metrics.
- **Canonical Model Census**: Standardized catalog of 19 internal model IDs (`1318` Flash High, `1016` Pro High, `1050` Flash Lite, `1035` Claude Sonnet 4.6, `1026` Claude Opus 4.6, `342` GPT-OSS 120B) with zero pricing or quota coupling.

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

# Inspect canonical 19-model census
python -m antigravity_telemetry models --json
```

---

## Canonical Model Census (19 Models)

| Model ID | Canonical Name | Provider | Reasoning Effort |
|:---|:---|:---|:---|
| `1318` | Gemini 3.8 Flash (High) | Google | High |
| `1319` | Gemini 3.8 Flash (Medium) | Google | Medium |
| `1320` | Gemini 3.8 Flash (Low) | Google | Low |
| `1298` | Gemini 3.7 Flash (High) | Google | High |
| `1299` | Gemini 3.7 Flash (Medium) | Google | Medium |
| `1300` | Gemini 3.7 Flash (Low) | Google | Low |
| `1071` | Gemini 3.6 Flash (High) | Google | High |
| `1072` | Gemini 3.6 Flash (Medium) | Google | Medium |
| `1073` | Gemini 3.6 Flash (Low) | Google | Low |
| `1016` | Gemini 3.1 Pro (High) | Google | High |
| `1036` | Gemini 3.1 Pro (Low) | Google | Low |
| `1050` | Gemini Flash Lite (Subagent) | Google | None |
| `1322` | Gemini Fast Agent Assistant | Google | None |
| `1132` | Gemini Fast Agent (Legacy) | Google | None |
| `1301` | Gemini Experimental Agent | Google | None |
| `1035` | Claude Sonnet 4.6 (Thinking) | Anthropic | Thinking |
| `1026` | Claude Opus 4.6 (Thinking) | Anthropic | Thinking |
| `1020` | Gemini Search Agent | Google | None |
| `342` | GPT-OSS 120B (Medium) | OpenAI | Medium |

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

