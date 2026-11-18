# Milestone 27: Standalone Importable Package `antigravity_telemetry` (Audit §7.2 / ADR-040)

## 1. Executive Summary

Milestone 27 fulfills the primary package modularization objective proposed in the Code & UX Audit (`docs/AUDIT_2026-09-12_CODE_AND_UX.md` §7.2):
1. **Core Telemetry Engine Extraction (`antigravity_telemetry/`)**:
   - Extracted the pure-Python reverse-engineered protobuf decoder and read-only SQLite connector into an independent, zero-dependency Python package.
   - Strictly enforces the standard library invariant (`sqlite3`, `pathlib`, `json`, `datetime`, `re`, `typing`, `urllib.parse`) with zero external pip dependencies.
   - Enforces the `?mode=ro` read-only connection invariant (ADR-001) with exponential backoff on WAL checkpoints.
2. **Canonical Model ID Census (`models.json`)**:
   - Standardized catalog of all 19 internal model IDs observed in Antigravity (`1318`, `1298`, `1016`, `1322`, `1132`, `1301`, `1035`, `1072`, `1026`, `1071`, `1319`, `1020`, `1036`, `342`, `1299`, `1050`, `1073`, `1300`, `1320`).
   - Cleanly decoupled from pricing, quotas, plans, and currencies.
3. **Distribution & CLI**:
   - Fast CLI (`python -m antigravity_telemetry dump --json`, `conversations --json`, `models --json`).
   - Standard PEP 517 / 621 `pyproject.toml` with console script entry point `antigravity-telemetry`.
   - Single-screen concise package documentation (`antigravity_telemetry/README.md`).
4. **100% Backward Compatibility**:
   - `src/proto_parser.py` and `src/telemetry_reader.py` preserved as backward-compatible re-export shims.
   - Exporter (`scripts/export_dashboard.py`), vault archiver (`src/vault.py`), and aggregator (`src/aggregator.py`) updated to import from `antigravity_telemetry`.

---

## 2. Package Architecture & Public API (ADR-040)

```
antigravity_telemetry/
├── __init__.py      # Public API: read_all_turns(), discover_all_conversations(), decode_wire_protobuf()
├── __main__.py      # Standalone CLI: dump --json, conversations --json, models --json
├── parser.py        # Pure-Python wire protobuf decoder (parse_wire_fields, extract_step_telemetry)
├── reader.py        # Safe read-only SQLite connector (?mode=ro, discover_all_conversations)
├── models.json      # Clean canonical 19-model census without pricing coupling
└── README.md        # One-screen concise documentation and usage guides
pyproject.toml       # Standard PEP 517 / 621 packaging metadata
```

### Public API Surface (`antigravity_telemetry/__init__.py`)

```python
import antigravity_telemetry as agy

# Read all generation turns across local Antigravity runtime
turns = agy.read_all_turns()

# Discover conversations with authoritative workspace path & active Git branch
convos = agy.discover_all_conversations()

# Decode raw wire protobuf bytes without compiled proto stubs
fields = agy.decode_wire_protobuf(raw_bytes)

# Inspect canonical 19-model census
census = agy.load_model_census()
```

---

## 3. Verifiable Acceptance Gates (V131–V135)

| Gate | Description | Command | Status |
|---|---|---|---|
| **V131** | Package Importability & Public API Surface | `python3 -c "import antigravity_telemetry as t; assert callable(t.read_all_turns); assert callable(t.discover_all_conversations); assert callable(t.decode_wire_protobuf); assert len(t.load_model_census()) == 19; print('Verified: Public API surface intact.')"` | **PASS** |
| **V132** | Standalone CLI Dump & Model Census | `python3 -m antigravity_telemetry dump --json \| python3 -c "import json, sys; data = json.load(sys.stdin); assert isinstance(data, list); print(f'Verified: CLI dump returned {len(data)} turns.')"` | **PASS** |
| **V133** | Model ID Census & Zero-Dependency Hygiene | `python3 -c "import json, sys, antigravity_telemetry as t; d = t.load_model_census(); assert len(d) == 19; assert all('name' in m and 'family' in m and 'provider' in m for m in d.values()); assert all('rates_per_million' not in m and 'credits_per_turn' not in m for m in d.values()); print('Verified: 19 models in canonical census with zero pricing/quota coupling.')"` | **PASS** |
| **V134** | Byte-Identical Dashboard Export Parity & Backward Compatibility | `python3 scripts/export_dashboard.py --dry-run && python3 -c "from src.proto_parser import parse_wire_fields, extract_step_telemetry; from src.telemetry_reader import discover_all_conversations, read_conversation_turns; print('Verified: Backward compatibility intact.')"` | **PASS** |
| **V135** | Full Test Suite & Documentation Integrity | `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py` | **PASS** |
