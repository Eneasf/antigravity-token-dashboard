# Milestone 31: CI Offline Fixtures, Deterministic Offline Export & Public Showcase Release

**Status**: Completed  
**Branch**: `feat/ci-offline-fixtures-and-showcase`  
**Tag**: `v1.31.0`  
**ADR Citation**: [ADR-044](../../docs/HANDOVER.md#adr-table)  
**Acceptance Gates**: V159–V164 in [`VDONE.md`](../../VDONE.md)  

---

## 1. Executive Summary

Milestone 31 executes the one-pass strategy delivering a fully offline, reproducible CI pipeline alongside the public showcase release (`v1.31.0`), while formally settling repository governance:

1. **Governance Formalization (ADR-044)**:
   - Formally discarded and indefinitely deferred Item 1 from the Senior Engineering Audit (`src/aggregator.py` modularization / C1).
   - Rationale: `src/aggregator.py` is battle-tested, stable, and 100% covered by 170+ unit tests; splitting it introduces significant regression risk and churn with zero capability or user benefit.
2. **Deterministic Offline Exporter Flag**:
   - Added `--no-live-quota` flag to `scripts/export_dashboard.py` bypassing localhost Connect-RPC calls in offline/CI environments.
   - Added optional `--reference-time` CLI parameter to enable fixed evaluation timestamp testing.
3. **Anonymized Offline Fixtures & CI Pipeline**:
   - Built a lightweight, realistic, zero-PII test environment in `tests/fixtures/antigravity/` containing sanitized SQLite databases across Gemini 3.8 Flash High (`1318`), Gemini Flash Lite Subagent (`1050`), and Claude Opus 4.6 Thinking (`1026`), with titles in `annotations/` and workspace mapping in `agyhub_summaries_proto.pb`.
   - Hardened `.github/workflows/ci.yml` to export telemetry against the offline fixtures and assert 100% byte-identical export across successive runs.
   - Authored `tests/test_ci_fixtures.py` (5/5 passing unit tests) asserting discovery, token extraction, zero PII, and byte-determinism.
4. **Public Showcase Synchronization**:
   - Released `v1.31.0` to the public repository (`Eneasf/antigravity-token-dashboard`) via `scripts/publish_to_public.py`.

---

## 2. Changes Implemented

### Engine & Exporter Hardening
- **`scripts/export_dashboard.py`**:
  - Added `--no-live-quota` and `--reference-time` arguments.
  - Passed `no_live_quota` and `reference_time` down to `export_telemetry`, `aggregate_global_telemetry`, and `get_weekly_trends`.
  - Resolved `updated_at` and `gen_at` via `temporal.resolved_at_utc` for byte-determinism.
- **`src/weekly_trends.py`**:
  - Hardened `load_ledger_incidents` to gracefully handle `ledger_path=None`.

### Test Fixtures & Automated CI
- **`scripts/build_ci_fixtures.py`**:
  - Reproducible generator script for sanitized test databases and protobuf blobs.
- **`tests/fixtures/antigravity/`**:
  - `conversations/11111111-1111-1111-1111-111111111111.db` (Gemini 1318 & 1050).
  - `conversations/22222222-2222-2222-2222-222222222222.db` (Claude 1026).
  - `annotations/*.pbtxt` (Titles).
  - `agyhub_summaries_proto.pb` (Workspace URIs).
- **`tests/test_ci_fixtures.py`**:
  - 5 comprehensive tests verifying discovery, token census, zero PII, and byte-determinism.
- **`.github/workflows/ci.yml`**:
  - Updated CI to execute export against offline fixtures and diff data files for byte-determinism.

### Documentation & Governance
- **`docs/HANDOVER.md`**: Logged ADR-044, updated Milestone Index (§3), and recorded Item 1 in Open Work Register (§4) as discarded/deferred.
- **`VDONE.md`**: Added Phase 11 acceptance gates (V159–V164).
- **`README.md`**: Updated with v1.31.0 release notes, CLI flags, test suite listings, and ADR-044 citation.

---

## 3. Verification & Acceptance Gates

All Phase 11 verification gates (V159–V164) passed cleanly:
- `V159`: `--no-live-quota` flag verified bypassing localhost Connect-RPC execution.
- `V160`: Offline fixtures in `tests/fixtures/antigravity/` verified with 2 conversations and 3 turns across Gemini and Claude.
- `V161`: `tests/test_ci_fixtures.py` (5/5 tests) verified passing with zero PII and byte-determinism.
- `V162`: `.github/workflows/ci.yml` verified executing export against fixtures with diff assertions.
- `V163`: ADR-044 and Item 1 deferral verified logged in `docs/HANDOVER.md`.
- `V164`: Full regression test suite + documentation integrity + model roster integrity verified passing with 0 errors.
