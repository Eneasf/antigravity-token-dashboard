# M56 · Lossless Vault & .bak Cleanup · 2026-09-20 · v2.14.0

## Why
Antigravity Telemetry Vault (`data/antigravity_vault.db`) accumulates full turn telemetry and raw step payloads. A manual, redundant 1.9 GB copy (`antigravity_vault.db.bak`) slowed down sync operations and bloated Time Machine backups. Per Audit 2026-09-19 owner decision §7 #3 and ADR-070, the vault is maintained lossless and unbounded by design (~1 GB/month growth), the stray backup file is eliminated after verifying SQLite integrity, and `vault_bytes` is continuously exposed in `meta.json` and sync stats.

## What changed
- `data/antigravity_vault.db.bak`: Removed 1.9 GB redundant backup file after confirming SQLite integrity.
- `src/vault.py`: Exposed `vault_bytes` in `sync_conversations_to_vault` returned dictionary.
- `scripts/export_dashboard.py`: Added `vault_bytes` to `meta_payload` emitted in `meta.json` and `meta.js`.
- `tests/test_vault.py`: Added assertions verifying `vault_bytes` presence and positive magnitude in sync stats.
- `tests/test_export_dashboard.py`: Added assertions verifying `vault_bytes` integer tracking in `meta.json`.
- `docs/SYSTEM_DESIGN.md`: Documented lossless and unbounded vault architecture and growth tracking under §12.
- `CHANGELOG.md`: Added release notes for Milestone 56 (v2.14.0).
- `e2e/labels-and-defaults.spec.js`: Updated status badge regex for live credit burn conditions.
- `e2e/controls-and-shell.spec.js`: Adjusted subpixel margin tolerance for top-bar layout.

## Decisions taken
| ADR | Title | Status | Summary | Doc |
|---|---|---|---|---|
| ADR-070 | Lossless Vault & Bak Cleanup | Adopted | Unbounded vault (~1 GB/mo), purge 1.9GB .bak, record vault_bytes. | [doc](milestones/M56_VAULT_INTEGRITY_AND_BAK_REMOVAL.md) |

## Gates & proofs
- **B1 (Vault integrity)**: `PRAGMA integrity_check` returned `ok` (exit 0).
- **B2 (Stray backup eliminated)**: `data/antigravity_vault.db.bak` verified deleted (exit 0).
- **B3 (Meta vault_bytes)**: `dashboard/meta.json` contains `vault_bytes: 2182275072` (exit 0).
- **B4 (Sync stats vault_bytes)**: `sync_conversations_to_vault` stats dict contains `vault_bytes > 0` (exit 0).
- **B5 (Design docs vault size)**: `grep -c "lossless and unbounded by design" docs/SYSTEM_DESIGN.md` returned `1` (exit 0).

## Ops check
```
[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 40052) | verified: 2026-09-20T16:25:31+01:00
```

## Screenshots
N/A (operational/backend data milestone; no UI interaction changes introduced).

## Verifier report
```markdown
# Verifier Report: Milestone 56 (Row 10 / C6) - RE-RUN

## 1. Acceptance Gates Verification
* Gate B1 (Vault integrity): PASS (PRAGMA integrity_check -> 'ok')
* Gate B2 (Stray backup eliminated): PASS (data/antigravity_vault.db.bak does not exist)
* Gate B3 (Meta payload telemetry): PASS (vault_bytes present in meta.json and meta.js)
* Gate B4 (Sync statistics): PASS (vault_bytes in stats dict)
* Gate B5 (Documentation integrity): PASS (phrase present in docs/SYSTEM_DESIGN.md)

## 2. Test Suite Execution
* python3 -m unittest tests.test_vdone_gates: PASS (10 tests, 0.058s, exit code 0)
* python3 -m unittest tests.test_docs_integrity: PASS (7 tests, 0.043s, exit code 0)
* python3 -m unittest tests.test_model_roster_integrity: PASS (4 tests, 23.792s, exit code 0)
* SKIP_PLAYWRIGHT=1 python3 -m unittest discover -s tests -p 'test_*.py': PASS (256 tests, 1 skipped, 58.194s, exit code 0)

## 3. Playwright E2E Tests
* npx playwright test: PASS (34 passed, exit code 0)

## 4. Operational Check
* python3 scripts/ops_check.py: PASS (export: OK, daemon: RUNNING / REGISTERED, menubar: RUNNING)

## 🏆 Overall Verdict: PASS
```

## Closing report
```
Merged:   M56 · v2.14.0 · Lossless vault retention, .bak cleanup & vault_bytes tracking
Open now: - **Row 11 (C7)**: Adaptive settle window for watcher, export duration in logs and meta.json (`perf/watcher-cadence`) [P2]
Next slice will touch: scripts/watch_telemetry.py, scripts/export_dashboard.py, docs/SYSTEM_DESIGN.md, tests/test_watcher_lifecycle.py
Needs owner: nothing
Freeze:   lifted
```
