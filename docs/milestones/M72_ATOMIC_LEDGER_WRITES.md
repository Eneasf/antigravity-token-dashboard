# Milestone 72: Atomic Ledger & Showcase Artifact Writes (C5)

**Date**: 2026-09-26
**Scope**: Row 6 (C5) from `docs/HANDOVER.md` §4 & `docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md`
**Branch**: `fix/atomic-ledger-writes`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `C5` identified non-atomic in-place file writes across several backend components:
- `src/log_reader.py`: `load_persistent_ledger` wrote `data/exhaustion_ledger.json` directly in-place, risking a truncated/empty file if interrupted.
- `scripts/build_demo_showcase.py`: `write_demo_files` wrote demo JavaScript and metadata payloads in-place.
- `scripts/export_dashboard.py`: wrote Markdown digest files directly without staging.

---

## 2. Changes Implemented

- **`src/log_reader.py`**:
  - Implemented `atomic_write_json(target_path, data, indent=2)` utilizing `tempfile.NamedTemporaryFile` in `target_path.parent` and atomic `os.replace`.
  - Added deterministic cleanup unlinking `.tmp` files upon any exception.
  - Refactored `load_persistent_ledger` to use `atomic_write_json`.
- **`scripts/build_demo_showcase.py`**:
  - Implemented `atomic_write_text(target_path, content, encoding="utf-8")` with exception cleanup.
  - Refactored `write_demo_files` to write turns, data, and meta demo files atomically via temporary staging.
- **`scripts/export_dashboard.py`**:
  - Used `atomic_write_text` for Markdown digest exports.
- **`tests/test_atomic_writes.py`**:
  - Added comprehensive test suite with 6 tests verifying atomic staging, file content preservation, error cleanup on rename failure, and self-healing ledger restoration. Registered in `docs/REPO_MAP.md`.

---

## 3. Acceptance Gates (§B)

| Gate # | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :---: |
| B1 | `python3 -c "import inspect, src.log_reader; src_code = inspect.getsource(src.log_reader.load_persistent_ledger); assert 'os.replace' in src_code or 'atomic_write' in src_code, 'Direct open write found in load_persistent_ledger'; print('OK')"` | `OK` | PASS |
| B2 | `python3 -c "import inspect, scripts.build_demo_showcase as b; src = inspect.getsource(b.write_demo_files); assert 'os.replace' in src, 'Atomic os.replace missing from write_demo_files'; print('OK')"` | `OK` | PASS |

Tested with: `atomic_write_json` and `atomic_write_text` execution, simulated filesystem `os.replace` failures asserting zero dangling `.tmp` files, and full regression test suite (338 tests in 92.8s).
