# Milestone 74: Explicit Exception Handling & Targeted Logging (C6)

**Date**: 2026-09-28
**Scope**: Row 7 (C6) from `docs/HANDOVER.md` §4 & `docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md`
**Branch**: `fix/explicit-exception-handling`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `C6` identified silent `except Exception: pass` handlers across `scripts/export_dashboard.py`, `scripts/watch_telemetry.py`, and `src/log_reader.py`:
When operations such as vault synchronization, ledger reading/writing, or status file hooks failed, exceptions were caught silently without logging, masking potential errors and disk/permission/schema failures.

---

## 2. Changes Implemented

- **`scripts/export_dashboard.py`**:
  - Replaced silent `except Exception: pass` blocks in status hook loading, vault sync routines, subagent correlation queries, and export lock management with explicit exception types (`(json.JSONDecodeError, OSError)`, `(sqlite3.Error, OSError)`, `(OSError, UnicodeDecodeError)`) and targeted `sys.stderr.write` warnings.
- **`scripts/watch_telemetry.py`**:
  - Replaced silent `except Exception: pass` blocks in vault sync and server teardown with explicit `(sqlite3.Error, OSError)` and `OSError` handlers and targeted `sys.stderr.write` warnings.
- **`src/log_reader.py`**:
  - Replaced silent `except Exception: pass` blocks in mtime evaluation and persistent ledger JSON reading/writing with explicit `(OSError, ValueError)`, `(json.JSONDecodeError, OSError)`, and `OSError` handlers and targeted `sys.stderr.write` warnings.

---

## 3. Acceptance Gates (§B)

| Gate # | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :--- |
| B1 | `python3 -c "import ast, glob; targets = [p for p in glob.glob('scripts/*.py') + ['src/log_reader.py'] if 'export' in p or 'watch' in p or 'log_reader' in p]; bare = [f'{f}:{h.lineno}' for f in targets for h in ast.walk(ast.parse(open(f).read())) if isinstance(h, ast.ExceptHandler) and getattr(h.type, 'id', '') == 'Exception' and len(h.body) == 1 and isinstance(h.body[0], ast.Pass)]; assert not bare, f'Found silent exceptions: {bare}'; print('OK')"` | `OK` | PASS |
| B2 | `python3 -c "import io, sys, tempfile, pathlib; from src.log_reader import load_persistent_ledger; f = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False); f.write('{bad_json:'); f.close(); stderr_cap = io.StringIO(); orig_stderr = sys.stderr; sys.stderr = stderr_cap; res = load_persistent_ledger(pathlib.Path(f.name)); sys.stderr = orig_stderr; pathlib.Path(f.name).unlink(); assert '[!] Warning:' in stderr_cap.getvalue(), f'No warning logged: {stderr_cap.getvalue()}'; print('OK')"` | `OK` | PASS |
| B3 | `python3 -c "import tempfile, subprocess, shutil; d = tempfile.mkdtemp(); res = subprocess.run(['python3', 'scripts/export_dashboard.py', '--antigravity-dir', 'tests/fixtures/antigravity', '--no-live-quota', '--reference-time', '2026-09-05T14:30:00Z', '--output-dir', d, '--dry-run'], capture_output=True, text=True); shutil.rmtree(d); assert res.returncode == 0, res.stderr; print('OK')"` | `OK` | PASS |

Tested with: AST parse over `scripts/export_dashboard.py`, `scripts/watch_telemetry.py`, and `src/log_reader.py` for `ast.ExceptHandler` catching `Exception` with body `[Pass]`; malformed JSON load via `load_persistent_ledger` capturing stderr; production CLI dry-run export with test fixture directory and reference timestamp; 338 unit tests; Playwright headless browser boot spec.
