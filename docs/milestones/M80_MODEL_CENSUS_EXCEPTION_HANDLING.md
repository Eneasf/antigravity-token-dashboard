# Milestone 80: Model Census Exception Handling & Resilience (C4)

**Date**: 2026-09-29
**Scope**: Row 4 (C4) from `docs/HANDOVER.md` §Open Work & `docs/AUDIT_2026-09-29_SYSTEM_PERFORMANCE_AND_UX.md`
**Branch**: `fix/model-census-exception-handling`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `C4` in `docs/AUDIT_2026-09-29_SYSTEM_PERFORMANCE_AND_UX.md` identified:
- `antigravity_telemetry/__init__.py:47`: `load_model_census()` caught generic `Exception` and returned `None` instead of an empty dictionary. Callers such as `get_model_truncation_threshold()` assumed a mapping returned and attempted iteration, crashing with `TypeError: argument of type 'NoneType' is not iterable` when `models.json` was missing or unparseable.
- Production code across `antigravity_telemetry/`, `src/`, and `scripts/` contained silent `except Exception: pass` blocks that masked file corruption, schema drift, and SQLite errors.

---

## 2. Changes Implemented

- **`antigravity_telemetry/__init__.py`**:
  - `load_model_census()` now catches specific `(OSError, json.JSONDecodeError)`, logs diagnostic warnings to `sys.stderr`, and returns an empty dictionary `{}` instead of `None`.
  - `get_model_truncation_threshold()` defensively inspects census type to safely handle non-dict or empty census objects.
- **`antigravity_telemetry/` (`parser.py`, `reader.py`)**:
  - Replaced silent generic exceptions with explicit types (`OSError`, `sqlite3.Error`, `UnicodeDecodeError`, `ValueError`, `KeyError`, `AttributeError`) and targeted `sys.stderr` diagnostic logging.
- **`src/` and `scripts/`**:
  - Replaced remaining silent `except Exception: pass` blocks in `swarm.py`, `log_archiver.py`, `temporal.py`, `tool_analytics.py`, `aggregator_pricing.py`, `quota_client.py`, `vault.py`, `simulator.py`, `log_reader.py`, `setup_menubar.py`, `agy_status.py`, `configure_plan.py`, `ingest_statement.py`, and `build_demo_showcase.py` with typed exception tuples and targeted logging.
- **`tests/test_truncation_thresholds.py`**:
  - Added `TestModelCensusResilience` with 8 comprehensive unit tests covering corrupted JSON, missing file, unreadable file (`PermissionError`), non-dict census fallback, and threshold evaluations.
- **`tests/test_vault.py`**:
  - Added Python 3.14 cursor wrapper compatibility for cursor-level exception simulation.

---

## 3. Acceptance Gates (§B)

| Gate # | Description | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :--- | :--- |
| B1 | Corrupt census fallback | `python3 -c "from unittest.mock import patch; import antigravity_telemetry as at, io, sys; stderr=io.StringIO(); patch.object(at.Path, 'read_text', return_value='{corrupt').start(); old_err=sys.stderr; sys.stderr=stderr; res=at.load_model_census(); sys.stderr=old_err; assert res == {}, f'Expected empty dict, got {res}'; assert 'Failed to load model census' in stderr.getvalue(); t=at.get_model_truncation_threshold('1318'); assert t == 200000, f'Expected 200000 fallback, got {t}'; print('OK')"` | `OK` | PASS (shows change) |
| B2 | Missing census fallback | `python3 -c "from unittest.mock import patch; import antigravity_telemetry as at, io, sys; stderr=io.StringIO(); patch.object(at.Path, 'exists', return_value=False).start(); old_err=sys.stderr; sys.stderr=stderr; res=at.load_model_census(); sys.stderr=old_err; assert res == {}, f'Expected empty dict, got {res}'; assert 'Model census file not found' in stderr.getvalue(); t=at.get_model_truncation_threshold('1318'); assert t == 200000; print('OK')"` | `OK` | PASS (shows change) |
| B3 | Normal census load | `python3 -c "import antigravity_telemetry as at; res=at.load_model_census(); assert len(res) == 19; assert at.get_model_truncation_threshold('1318') == 1000000; assert at.get_model_truncation_threshold('non_existent_model') == 200000; print('OK')"` | `OK` | PASS |
| B4 | Boundary severity evaluation | `python3 -c "import antigravity_telemetry as at; assert at.evaluate_truncation_severity(160000, '1035') == 'warning'; assert at.evaluate_truncation_severity(200000, '1035') == 'critical'; assert at.evaluate_truncation_severity(159999, '1035') == 'safe'; assert at.evaluate_truncation_severity(100000, None) == 'safe'; assert at.evaluate_truncation_severity(0, '1035') == 'safe'; print('OK')"` | `OK` | PASS |
| B5 | Production caller resilience | `python3 -c "import tempfile, subprocess, pathlib, shutil; d = tempfile.mkdtemp(); res = subprocess.run(['python3', 'scripts/export_dashboard.py', '--antigravity-dir', 'tests/fixtures/antigravity', '--no-live-quota', '--reference-time', '2026-09-05T14:30:00Z', '--output-dir', d], capture_output=True, text=True, timeout=30); assert res.returncode == 0, res.stderr; shutil.rmtree(d); print('OK')"` | `OK` | PASS |
| B6 | Unit test suite | `python3 -m unittest discover -s tests -p 'test_truncation_thresholds.py'` | `OK` | PASS |
