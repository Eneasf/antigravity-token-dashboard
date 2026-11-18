# Milestone Slice M08: Telemetry Vault, Lineage Topology & Archival Skill

- **Status**: Completed
- **Date**: 2026-09-06
- **Branch**: `feat/telemetry-vault-archive`
- **ADR Reference**: ADR-018

---

## 1. Architectural Objectives & Invariants Attained

1. **Local Persistent SQLite Store (`data/antigravity_vault.db`)**:
   - Dedicated local database immune to Antigravity IDE restarts, file truncations, and conversation purges.
   - Preserves complete historical record across all workspaces and subagent runs.
   - Gitignored via `data/antigravity_vault.db*` to eliminate repository binary bloat while permanently retained on disk.
2. **Hybrid Storage Standard (ADR-018)**:
   - Searchable text columns: full decoded markdown/code (`payload_text`), tool call signatures (`tool_calls_json`), and error details (`error_text`).
   - Raw binary Protobuf blobs (`raw_metadata_blob`, `raw_step_payload_blob`, `raw_error_details_blob`) for 100% bit-for-bit lossless replay.
   - Zero Python Pickle (`.pkl`) to maintain universal SQL queryability and eliminate runtime fragility.
3. **Workspace / Project Attribution**:
   - Decodes `agyhub_summaries_proto.pb` with `urllib.parse.unquote` to map conversation UUIDs to project workspace directory paths and titles.
4. **Parent-Child Subagent Lineage**:
   - Captures relational trees linking master sessions to subagents via `tool_calls_archive` (`invoke_subagent` and `send_message`), resolving orchestrator session `b596cf7f` $\rightarrow$ `68481b2d`.
5. **Tool & Skill Indexing**:
   - Indexes individual tool invocations (`tool_calls_archive`) and tracks skill activations (`skills_archive`).
6. **Log Truncation Defense (`src/log_archiver.py`)**:
   - Continuous tailer for `language_server.log` with file shrink / inode rotation detection, storing deduplicated SHA-256 fingerprinted 429 and lifecycle events in `log_events_archive`.
7. **Universal Ingestion Skill (`~/.gemini/config/skills/credit-statement-ingest/`) & CLI (`scripts/ingest_statement.py`)**:
   - Autonomous multimodal skill that parses statement/receipt screenshots in any Antigravity chat and ingests them into `data/exhaustion_ledger.json` and the Vault.

---

## 2. Verification Gates & Execution Evidence (VDONE.md)

### V25: Vault Schema Initialization & Idempotence
```bash
python3 -c "from src.vault import init_vault; conn=init_vault('data/antigravity_vault.db'); cur=conn.cursor(); cur.execute('SELECT name FROM sqlite_master WHERE type=\'table\''); tables={r[0] for r in cur.fetchall()}; assert {'conversations_archive', 'steps_archive', 'tool_calls_archive', 'log_events_archive'}.issubset(tables); print('Verified: Vault schema tables initialized.')"
```
- **Output**: `Verified: Vault schema tables initialized.` (Exit code 0).

### V26: Hybrid Step Ingestion (Text + Raw Blobs, Zero PKL)
```bash
python3 -c "from src.vault import get_vault_connection; conn=get_vault_connection('data/antigravity_vault.db'); cur=conn.cursor(); cur.execute('PRAGMA table_info(steps_archive)'); cols={r[1]: r[2] for r in cur.fetchall()}; assert cols.get('payload_text') == 'TEXT'; assert cols.get('raw_step_payload_blob') == 'BLOB'; print('Verified: Hybrid text and blob schema intact without pickle.')"
```
- **Output**: `Verified: Hybrid text and blob schema intact without pickle.` (Exit code 0).

### V27: Parent-Child Subagent Lineage Resolution
```bash
python3 -c "from src.vault import get_vault_connection; conn=get_vault_connection('data/antigravity_vault.db'); cur=conn.cursor(); cur.execute('SELECT parent_convo_id FROM conversations_archive WHERE convo_id = \'68481b2d-f75d-47b3-b4ca-5d3a8f5de035\''); res=cur.fetchone(); assert res and res[0] == 'b596cf7f-af76-4966-8a8b-f90a0d1c6229'; print('Verified: Subagent lineage resolved.')"
```
- **Output**: `Verified: Subagent lineage resolved.` (Exit code 0).

### V28: Workspace & Project Attribution Parsing
```bash
python3 -c "from src.vault import get_vault_connection; conn=get_vault_connection('data/antigravity_vault.db'); cur=conn.cursor(); cur.execute('SELECT workspace_name FROM conversations_archive WHERE convo_id = \'b596cf7f-af76-4966-8a8b-f90a0d1c6229\''); res=cur.fetchone(); assert res and 'Token consumption' in res[0]; print('Verified: Workspace origin attributed.')"
```
- **Output**: `Verified: Workspace origin attributed.` (Exit code 0).

### V29: Truncation-Resilient Log Archival
```bash
python3 -m unittest tests.test_vault.TestVault.test_log_truncation_detection
```
- **Output**: `Ran 1 test in 0.028s - OK` (Exit code 0).

### V30: Universal Ingestion Skill Discovery
```bash
python3 -c "import os; p=os.path.expanduser('~/.gemini/config/skills/credit-statement-ingest/SKILL.md'); assert os.path.exists(p); print('Verified: Global credit-statement-ingest skill installed.')"
```
- **Output**: `Verified: Global credit-statement-ingest skill installed.` (Exit code 0).

### Regression Integrity Suite
```bash
python3 -m unittest discover -s tests
```
- **Output**: `Ran 57 tests in 1.052s - OK` (Exit code 0).
