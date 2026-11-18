# Milestone 79: Harden SQLite Connection Closures and Concurrency Settings (C3)

**Date**: 2026-09-29
**Scope**: Row 3 (C3) from `docs/HANDOVER.md` §Open Work & `docs/AUDIT_2026-09-29_SYSTEM_PERFORMANCE_AND_UX.md`
**Branch**: `fix/vault-connection-closure-hardening`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `C3` from `docs/AUDIT_2026-09-29_SYSTEM_PERFORMANCE_AND_UX.md` identified missing connection cleanup and concurrency settings:
- In `src/vault.py:1248-1284` (`get_vault_truncation_markers`) and `1302-1350` (`scan_conversation_truncation`), `conn.close()` was located at the tail of the `try:` block without a `finally:` block. If cursor operations raised an exception or hit early returns, `conn.close()` was bypassed.
- In `src/log_reader.py:98-113` (`reconstruct_ledger_from_vault`), `conn = sqlite3.connect(...)` lacked `try...finally: conn.close()` and omitted GADR-013 concurrency parameters (`timeout=60.0` and `PRAGMA busy_timeout = 60000;`).

---

## 2. Changes Implemented

- **`src/vault.py`**:
  - Wrapped SQLite connection lifetimes in `get_vault_truncation_markers` and `scan_conversation_truncation` with `conn = None` and `try...finally: if conn is not None: conn.close()`.
  - Configured `timeout=60.0` and `conn.execute("PRAGMA busy_timeout = 60000;")` per GADR-013 / ADR-081 SQLite Concurrency Resilience.
  - Eliminated early return bypasses where queries or schema inspections could leak unclosed database handles.
- **`src/log_reader.py`**:
  - Wrapped `reconstruct_ledger_from_vault` in `try...finally: if conn is not None: conn.close()`.
  - Added `timeout=60.0` to `sqlite3.connect` and executed `PRAGMA busy_timeout = 60000;`.
- **`tests/test_vault.py` & `tests/test_log_reader.py`**:
  - Added `TestVaultConnectionHardening` (5 tests) and `TestReconstructLedgerFromVaultConnectionHardening` (3 tests) validating connection closure on error, early returns, GADR-013 concurrency parameters, and strict `ResourceWarning` hygiene.

---

## 3. Acceptance Gates (§B)

| Gate # | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :--- |
| B1 | Concurrency params and timeouts spy | `OK` | PASS (shows change) |
| B2 | Connection closure on error spy | `OK` | PASS (shows change) |
| B3 | `python3 -W error::ResourceWarning -m unittest tests/test_vault.py tests/test_log_reader.py` | `OK` | PASS |
| B4 | `python3 -m unittest tests.test_vault.TestVaultConnectionHardening tests.test_log_reader.TestReconstructLedgerFromVaultConnectionHardening` | `OK` | PASS (shows change) |
| B5 | `python3 -m unittest discover -s tests` | `OK, < 150 s` | PASS |
