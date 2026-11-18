# Milestone 65: Unit Test Status File Isolation (TI-1)

**Date**: 2026-09-24  
**Scope**: Row 1 (TI-1) from `docs/HANDOVER.md` §4 & `docs/AUDIT_2026-09-24_TEST_ISOLATION.md`  
**Branch**: `fix/test-status-isolation`  
**Verdict**: **PASS**  

---

## 1. Overview & Context

During the Study A eligibility audit (`docs/AUDIT_2026-09-24_TEST_ISOLATION.md`), finding `TI-1` established that running unit tests (`$TEST_CMD`) could overwrite the live menu bar status hook (`~/.antigravity_quota_status.json`) with fixture telemetry and a pointer to an ephemeral test directory that was deleted upon test completion. This resulted in the native macOS companion app (`AntigravityBar`) failing or reporting synthetic numbers until the next live watcher export cycle.

Milestone 65 enforces strict runtime environment isolation conforming to ADR-001 (the live environment is not a test fixture):
1. **Library Calls**: Direct invocations of `export_telemetry(...)` without an explicit `status_path` and without `output_dir` omit writing any status file.
2. **CLI Executions**: Invocations of `scripts/export_dashboard.py` without `--output-dir` and without `--status-path` (e.g. interactive terminal runs and the LaunchAgent) continue to write to `DEFAULT_STATUS_PATH` (`~/.antigravity_quota_status.json`).
3. **Hermetic Test Harness**: Test invocations of `watch_loop` across `tests/test_export_lock.py` and `tests/test_watch_telemetry.py` explicitly bind status files to temporary working directories.

---

## 2. Changes Implemented

### scripts/export_dashboard.py
- In `_export_telemetry_impl()` (line 759), guarded `write_quota_status_file`:
  ```python
  effective_status_path = status_path if status_path is not None else (dashboard_dir / ".antigravity_quota_status.json" if output_dir is not None else None)
  if effective_status_path is not None:
      write_quota_status_file(payload, status_path=effective_status_path)
  ```
- In `main()` (line 1025), resolved CLI default status path:
  ```python
  cli_status_path = args.status_path if args.status_path is not None else (None if args.output_dir is not None else DEFAULT_STATUS_PATH)
  ```
  and forwarded `status_path=cli_status_path` to `export_telemetry(...)`.

### tests/test_status_isolation.py (New)
- Created comprehensive regression suite testing all 4 isolation vectors:
  - `test_a_library_isolation`: Direct library call without `status_path` leaves `DEFAULT_STATUS_PATH` untouched.
  - `test_b_cli_default`: CLI invocation without `--output-dir` writes to `DEFAULT_STATUS_PATH`.
  - `test_c_cli_with_output_dir`: CLI invocation with `--output-dir` writes strictly to `<output_dir>/.antigravity_quota_status.json`.
  - `test_d_library_with_status_path`: Direct library call with explicit `status_path` writes to the specified target.

### tests/test_export_lock.py & tests/test_watch_telemetry.py
- Updated tests calling `watch_loop` to provide explicit `status_path` pointing to temporary paths (`self.temp_path / "status.json"` and `self.temp_path / "quota_status.json"`).

### tests/test_vdone_gates.py & docs/REPO_MAP.md
- Updated `is_command_permitted` in `test_vdone_gates.py` to allow `test_export_dashboard` test runner commands while maintaining strict exclusion for unisolated `scripts/export_dashboard.py`.
- Documented `test_status_isolation.py` in `docs/REPO_MAP.md` test tree.

---

## 3. ADR-047 Live Pipeline Operation

1. **Live Exporter Run**: `python3 scripts/export_dashboard.py` executed cleanly.
2. **LaunchAgent Restart**: `python3 scripts/setup_service.py restart` kickstarted `com.antigravity.telemetry.watcher`.
3. **Ops Health Probe**:
   ```text
   [OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 850) | verified: 2026-09-24T13:14:02+01:00
   ```

---

## 4. Acceptance Gates Archive (from VDONE.md §B)

| Gate # | Name | Executable Check Command | Expected Output | Actual Output | Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **B1** | Status isolation | `python3 -c "import os,subprocess,tempfile,pathlib; h=tempfile.mkdtemp(); subprocess.run(['python3','-m','unittest','tests.test_export_dashboard','tests.test_export_lock','tests.test_quota_status_enrichment','tests.test_watch_telemetry','tests.test_status_isolation'], env={**os.environ,'HOME':h}, capture_output=True); assert not (pathlib.Path(h)/'.antigravity_quota_status.json').exists(), 'a test wrote the home status file'; print('OK')"` | `OK` | `OK` (exit code 0) | **PASS** |
| **B2** | Regression test | `python3 -m unittest tests.test_status_isolation` | `OK` | `Ran 4 tests in 0.131s\n\nOK` (exit code 0) | **PASS** |
| **B3** | Unit suite | `python3 -m unittest discover -s tests` | `OK, < 90 s` | `Ran 305 tests in 86.604s\n\nOK` (exit code 0) | **PASS** |
| **B4** | Live monitor intact | `python3 -c "import json,pathlib; d=json.loads((pathlib.Path.home()/'.antigravity_quota_status.json').read_text()); p=d.get('dashboard_path',''); assert p.endswith('.../dashboard/index.html'), p; print('OK')"` | `OK` | `OK` (exit code 0) | **PASS** |

---

## 5. Independent Verifier Verdict

The read-only Verifier subagent confirmed full compliance under strict GADR-005 tree purity:
- **Pre-execution `git status --porcelain`**: Clean (0 modified / 0 untracked files).
- **Post-execution `git status --porcelain`**: Clean (0 modified / 0 untracked files).
- **Quality Gate** (`git diff --check && python3 -m unittest tests/test_docs_integrity.py`): PASS (11 tests in 3.109s).
- **Overall Verdict**: **PASS**
