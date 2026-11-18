# Milestone 71: Version Manifest Synchronization (D1)

**Date**: 2026-09-26
**Scope**: Row 5 (D1) from `docs/HANDOVER.md` §4 & `docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md`
**Branch**: `chore/version-manifest-sync`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `D1` identified potential version desynchronization across Git tags, `pyproject.toml`, and `package.json`, which had historically allowed divergent version strings and bypassed strict equality checking via whitelist allowances in `tests/test_docs_integrity.py`.

---

## 2. Changes Implemented

- **`tests/test_docs_integrity.py`**:
  - Renamed test class to `DocsIntegrityTest`.
  - Added unit test `test_version_manifest_sync` to enforce strict equality across `pyproject.toml` version, `package.json` version, and the latest git tag from `git tag --sort=-v:refname` without bypass whitelists.
- **`tests/test_vdone_gates.py`**:
  - Permitted read-only Git query commands (`describe`, `tag`, `rev-parse`, `log`, `show`) in VDONE Python test gate validation.

---

## 3. Acceptance Gates (§B)

| Gate # | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :---: |
| B1 | `python3 -m unittest tests.test_docs_integrity.DocsIntegrityTest.test_version_manifest_sync` | `OK` | PASS |
| B2 | `python3 -c "import json, tomllib, pathlib, subprocess; tag=subprocess.check_output(['git','describe','--tags','--abbrev=0']).decode().strip().lstrip('v'); py_ver=tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['version']; js_ver=json.loads(pathlib.Path('package.json').read_text())['version']; assert tag==py_ver==js_ver, f'Desync: tag={tag}, py={py_ver}, js={js_ver}'; print('OK')"` | `OK` | PASS |

Tested with: Exact version string equality comparison across `pyproject.toml` (2.24.0), `package.json` (2.24.0), and git tag (`v2.24.0`); `DocsIntegrityTest.test_version_manifest_sync`; `is_command_permitted` safety evaluation; and full offline regression suite (331 tests in 95.6s).
