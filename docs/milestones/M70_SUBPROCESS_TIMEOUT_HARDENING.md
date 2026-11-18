# Milestone 70: Subprocess Timeout Hardening (C4)

**Date**: 2026-09-26
**Scope**: Row 4 (C4) from `docs/HANDOVER.md` §4 & `docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md`
**Branch**: `fix/subprocess-timeout-hardening`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `C4` identified 28 invocations of `subprocess.run` and `subprocess.Popen` across `src/` and `scripts/` lacking explicit `timeout=` parameters. Local system commands such as `lsof`, `ps`, and `export_dashboard.py` carried the risk of hanging indefinitely if sockets or locks blocked, stalling monitoring pipelines and background daemons.

---

## 2. Changes Implemented

- **Subprocess Calls**:
  - `src/quota_client.py`: Added `timeout=10.0` and `TimeoutExpired` handling for `ps` and `lsof`.
  - `scripts/build_menubar.py`: Added bounded timeouts (`timeout=15.0` for swift version, `timeout=120.0` for swift build, `timeout=30.0` for codesign) with `TimeoutExpired` handling.
  - `scripts/ops_check.py`: Added `timeout=120.0` for export calls, and `timeout=15.0` for service/menubar checks with `TimeoutExpired` handling.
  - `scripts/capture_showcase_screenshots.py`: Migrated to `subprocess.run(..., timeout=30.0)` with `TimeoutExpired` handling.
  - `scripts/setup_github_guardrails.py`: Added `timeout=30.0` and `TimeoutExpired` handling to `gh` invocations.
  - `scripts/publish_to_public.py`: Added `timeout: float = 120.0` parameter and `TimeoutExpired` handling to `run_cmd`.
  - `scripts/setup_service.py`: Added `timeout=10.0` to `plutil` and `launchctl list`, and `timeout=15.0` to `launchctl load/unload/kickstart`.
  - `scripts/setup_menubar.py`: Added `timeout=10.0` to `pgrep`, `launchctl list`, `pkill`, and `timeout=15.0` to `launchctl kickstart`, `open -a`, and `launchctl bootstrap/bootout/unload`.

- **Automated Tests & Repo Map**:
  - Authored `tests/test_subprocess_timeouts.py` with AST checks asserting 0 calls without `timeout=`.
  - Registered `tests/test_subprocess_timeouts.py` in `docs/REPO_MAP.md`.

---

## 3. Acceptance Gates (§B)

| Gate # | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :---: |
| B1 | `python3 -c "import ast, glob; errs=[]; [errs.append(f'{p}:{n.lineno}') for p in glob.glob('src/**/*.py', recursive=True)+glob.glob('scripts/**/*.py', recursive=True) for n in ast.walk(ast.parse(open(p).read())) if isinstance(n, ast.Call) and getattr(n.func, 'attr', '') in ('run', 'Popen') and not any(k.arg=='timeout' for k in n.keywords)]; assert not errs, f'Missing timeout in: {errs}'; print('OK')"` | `OK` | PASS |

Tested with: AST scan over `src/**/*.py` (19 files) and `scripts/**/*.py` (16 files) finding 0 un-timeouted `run`/`Popen` calls, synthetic positive/negative AST assertions, and full test suite executions under Python 3.14.
