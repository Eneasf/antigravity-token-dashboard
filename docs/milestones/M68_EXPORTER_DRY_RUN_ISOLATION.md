# Milestone 68: Exporter Dry-Run Vault Isolation (C2)

**Date**: 2026-09-26
**Scope**: Row 2 (C2) from `docs/HANDOVER.md` §4 & `docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md`
**Branch**: `fix/exporter-dry-run-isolation`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `C2` identified that running `scripts/export_dashboard.py --dry-run` was invoking `sync_subscription_to_vault()`, `sync_conversations_to_vault()`, and `sync_weekly_trends_to_vault()` whenever `is_custom_dir` was false, modifying `data/antigravity_vault.db` and violating Host Isolation (Principle 11 & AGENTS.md Rule AC-4).

---

## 2. Changes Implemented

- **`scripts/export_dashboard.py`**:
  - Guarded vault synchronization calls with `if not is_custom_dir and not dry_run:`.
  - In dry-run mode, historical weekly trends are computed strictly read-only against the existing vault file via `get_weekly_trends` with `?mode=ro`, without modifying the vault database.

- **`tests/test_export_dashboard.py`**:
  - Added unit test `test_export_dry_run_does_not_invoke_vault_sync` verifying that `export_telemetry` with `dry_run=True` executes zero vault write operations, while `dry_run=False` properly invokes them.

---

## 3. Acceptance Gates (§B)

| Gate # | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :---: |
| B1 | `python3 -c "import os, subprocess, pathlib; v=pathlib.Path('data/antigravity_vault.db'); m0=v.stat().st_mtime; subprocess.run(['python3', 'scripts/export_dashboard.py', '--dry-run', '--no-live-quota'], check=True, capture_output=True); m1=v.stat().st_mtime; assert m0 == m1, 'Vault DB modified during dry run'; print('OK')"` | `OK` | PASS |

Tested with: `python3 scripts/export_dashboard.py --dry-run --no-live-quota against data/antigravity_vault.db mtime isolation, unittest mock assertion of sync_subscription_to_vault, sync_conversations_to_vault, sync_weekly_trends_to_vault under dry_run={True, False}`
