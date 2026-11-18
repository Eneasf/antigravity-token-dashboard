# Milestone 75: Decouple Vault and Weekly Trends Circular Import (C7)

**Date**: 2026-09-28
**Scope**: Row 8 (C7) from `docs/HANDOVER.md` §4 & `docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md`
**Branch**: `refactor/vault-weekly-trends-decouple`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `C7` (listed as `C1` in the finding catalog and Row 8 in `HANDOVER.md`) identified a circular import dependency between `src/vault.py` and `src/weekly_trends.py`:
- `src/vault.py:1330, 1352` imported `sync_weekly_trends_to_vault` and `get_weekly_trends` inside function bodies to defer evaluation.
- `src/weekly_trends.py:263` imported `init_vault` inside `sync_weekly_trends_to_vault` to avoid a circular `ImportError` on module load.

This architectural coupling required deferred function-level imports and obscured module ownership of the SQLite vault schema.

---

## 2. Changes Implemented

- **`src/vault_schema.py`** (New Module):
  - Extracted authoritative SQLite vault schema definition and initialization logic into dedicated `src/vault_schema.py`.
  - Defines `DEFAULT_VAULT_PATH`, `init_vault()`, and `get_vault_connection()` with WAL pragma, busy timeout, table creation (all 8 tables), agent persona migrations, and performance indexes.
- **`src/vault.py`**:
  - Re-exported `DEFAULT_VAULT_PATH`, `init_vault`, and `get_vault_connection` from `src.vault_schema` for 100% backward compatibility.
  - Replaced inline deferred imports of `weekly_trends` with clean top-level imports `_sync_weekly_trends_to_vault_impl` and `_get_weekly_trends_impl`.
- **`src/weekly_trends.py`**:
  - Imported `DEFAULT_VAULT_PATH` and `init_vault` directly from `src.vault_schema` at module level.
  - Eliminated inline `from src.vault import init_vault` from `sync_weekly_trends_to_vault()`.
- **`tests/test_vault_schema.py`** (New Test Suite):
  - Added comprehensive unit tests validating schema creation, idempotence, agent column migrations, connection pragmas, symbol re-export identity, and strict process isolation (verifying importing `src.vault_schema` never loads `src.vault` or `src.weekly_trends`).
- **`docs/REPO_MAP.md`**:
  - Registered `src/vault_schema.py` and `tests/test_vault_schema.py`.

---

## 3. Acceptance Gates (§B)

| Gate # | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :--- |
| B1 | `python3 -c "import src.vault_schema as vs; assert hasattr(vs, 'init_vault') and hasattr(vs, 'DEFAULT_VAULT_PATH'); conn = vs.init_vault(':memory:'); cur = conn.cursor(); cur.execute('SELECT count(*) FROM sqlite_master WHERE type=\'table\''); assert cur.fetchone()[0] >= 8; print('OK')"` | `OK` | PASS |
| B2 | `python3 -c "import ast; tree = ast.parse(open('src/vault.py').read()); deferred = [f'{n.name}:{c.lineno}' for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for c in ast.walk(n) if isinstance(c, (ast.Import, ast.ImportFrom)) and 'weekly_trends' in (getattr(c, 'module', '') or '')]; assert not deferred, f'Deferred imports remain in vault.py: {deferred}'; print('OK')"` | `OK` | PASS |
| B3 | `python3 -c "import ast; tree = ast.parse(open('src/weekly_trends.py').read()); deferred = [f'{n.name}:{c.lineno}' for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for c in ast.walk(n) if isinstance(c, (ast.Import, ast.ImportFrom)) and 'vault' in (getattr(c, 'module', '') or '')]; assert not deferred, f'Deferred imports remain in weekly_trends.py: {deferred}'; print('OK')"` | `OK` | PASS |
| B4 | `python3 -c "import src.vault as v, src.weekly_trends as wt, tempfile, pathlib; d = tempfile.mkdtemp(); p = pathlib.Path(d)/'test_vault.db'; conn = wt.init_vault(p); cur = conn.cursor(); cur.execute('SELECT count(*) FROM sqlite_master WHERE type=\'table\''); assert cur.fetchone()[0] >= 8; assert v.init_vault is wt.init_vault; print('OK')"` | `OK` | PASS |

Tested with: AST parse over `src/vault.py` and `src/weekly_trends.py` for deferred imports; clean memory schema verification; top-level cross-import and symbol identity assertion; 345 unit tests; Playwright headless browser boot spec.
