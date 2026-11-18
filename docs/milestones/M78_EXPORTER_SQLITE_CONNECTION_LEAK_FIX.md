# Milestone 78: Fix Unclosed SQLite Database Connection Leak in scripts/export_dashboard.py (C2)

**Date**: 2026-09-29
**Scope**: Row 2 (C2) from `docs/HANDOVER.md` §Open Work & `docs/AUDIT_2026-09-29_SYSTEM_PERFORMANCE_AND_UX.md`
**Branch**: `fix/export-connection-leak`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `C2` from `docs/AUDIT_2026-09-29_SYSTEM_PERFORMANCE_AND_UX.md` identified an unclosed SQLite connection leak:
- `scripts/export_dashboard.py:574` opened the vault database with `with sqlite3.connect(f"file:{vault_file}?mode=ro", uri=True) as vconn:`.
- In Python's `sqlite3` standard library, `Connection.__enter__` / `__exit__` manages transaction boundaries (`commit`/`rollback`), but does **not** close the underlying database connection.
- This leaked the connection until finalization / process exit, triggering `ResourceWarning: unclosed database in <sqlite3.Connection object>` and failing strict warning filters.

---

## 2. Changes Implemented

- **`scripts/export_dashboard.py`**:
  - Replaced context manager `with sqlite3.connect(...) as vconn:` with explicit `vconn = None` and `try...finally: if vconn is not None: vconn.close()`.
  - Configured `timeout=60.0` and `vconn.execute("PRAGMA busy_timeout = 60000;")` per GADR-013 / ADR-081 SQLite Concurrency Resilience.
- **`tests/test_export_dashboard.py`**:
  - Added unit test `test_export_subagent_correlation_closes_vault_connection` validating that `export_telemetry` with `dry_run=False` cleanly closes the vault database connection without emitting `ResourceWarning`.
- **`VDONE.md`**:
  - Formulated and verified acceptance gates B1–B3.

---

## 3. Acceptance Gates (§B)

| Gate # | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :--- |
| B1 | `python3 -c "import pathlib, subprocess, sys; from src.vault_schema import init_vault; p = pathlib.Path('data/antigravity_vault.db'); created = False; (setattr(sys, '_conn', init_vault(p)), sys._conn.close(), setattr(sys, '_c', True)) if not p.exists() else None; res = subprocess.run([sys.executable, '-W', 'error::ResourceWarning', '-m', 'unittest', 'tests/test_export_dashboard.py'], capture_output=True, text=True); p.unlink() if getattr(sys, '_c', False) and p.exists() else None; count = res.stderr.count('ResourceWarning: unclosed database'); assert count == 0, f'Found {count} unclosed database warnings'; print('OK')"` | `OK` | PASS (shows change: 2 warnings on base, 0 warnings on HEAD) |
| B2 | `python3 -m unittest discover -s tests` | `OK, < 90 s` | PASS |
| B3 | `python3 -m unittest tests/test_docs_integrity.py` | `OK` | PASS |
