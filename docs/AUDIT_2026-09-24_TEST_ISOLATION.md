# Audit 2026-09-24 — Unit Tests Overwrite the Live Menu-Bar Status File

> **Auditor:** Claude (external second opinion; read-only; no code changed)
> **Scope:** one finding, `TI-1`, observed during the Study A eligibility run (`Agentic work`, 2026-09-24)
> **Tree at audit time:** `main` @ `669049b`, plus the owner's pending `AGENTS.md` / `CLAUDE.md` edits from 2026-09-23

## Finding TI-1 — every test-suite run can break the live token monitor `[EVIDENCED]`

**What happens:**
- `tests/test_export_dashboard.py` calls `export_telemetry(...)` at lines 47, 98, 119, 140, 152, 203, 226 and 246. Each call passes `dashboard_path=<temp dir>`, but neither `output_dir` nor `status_path`.
- In that case `scripts/export_dashboard.py:759–760` resolves `effective_status_path = None`, and `write_quota_status_file` falls back to `DEFAULT_STATUS_PATH` (`:86`), which is the **real** `~/.antigravity_quota_status.json`.
- The file is overwritten with fixture figures and a `dashboard_path` pointing at the test's temporary folder, which is deleted when the test ends.
- AntigravityBar reads that file, so the menu-bar monitor shows wrong data or stops working. It recovers only when the live watcher next runs a full export.

**Evidence:**
- On 2026-09-24 the owner reported "My antigravity token monitor stopped working" while the study coordinator was running the suite repeatedly in throwaway clones.
- The same bug affected an overnight pilot on 2026-09-23 that ran the suite in a scratch clone.
- Every candidate and replay commit examined for Study A carries between 5 and 8 such calls. This means **any** agent running `$TEST_CMD` during normal work (implementer, verifier, CI-style gates) can trigger it.

**Why it matters:** tests must never write outside their own temporary directories. It is the same principle as read-only DB access (ADR-001): the live environment is not a test fixture.

**Intended behaviour after the fix:**
- Only an explicit caller writes `~/.antigravity_quota_status.json`: the CLI run without `--output-dir` (what the watcher uses), and the watcher's heartbeat.
- A direct library call to `export_telemetry(...)`, which is what tests make, never writes the home status file unless it is given an explicit `status_path`.
- Existing CLI flags keep their meaning.

## Row

- **Row 1 (TI-1)**: Stop unit tests overwriting the live menu-bar status file (`fix/test-status-isolation`)
  - **Touches:** `scripts/export_dashboard.py` (status-path resolution and CLI default), the tests that call `export_telemetry`, and a new regression test `tests/test_status_isolation.py`.
  - **Delegation:** disjoint scopes. One worker owns the exporter/CLI change, one owns the tests. An independent verifier goes last.
  - **Live pipeline op:** the exporter changes, so ADR-047 applies: run the live export, restart the LaunchAgent, then `scripts/ops_check.py`.

**Gates** (for `VDONE.md` §B):

```text
B1 Status isolation: CHECK python3 -c "import os,subprocess,tempfile,pathlib; h=tempfile.mkdtemp(); subprocess.run(['python3','-m','unittest','tests.test_export_dashboard','tests.test_export_lock','tests.test_quota_status_enrichment','tests.test_watch_telemetry','tests.test_status_isolation'], env={**os.environ,'HOME':h}, capture_output=True); assert not (pathlib.Path(h)/'.antigravity_quota_status.json').exists(), 'a test wrote the home status file'; print('OK')" EXPECT OK
B2 Regression test: CHECK python3 -m unittest tests.test_status_isolation EXPECT OK
B3 Unit suite: CHECK python3 -m unittest discover -s tests EXPECT OK, < 90 s
B4 Live monitor intact: CHECK python3 -c "import json,pathlib; d=json.loads((pathlib.Path.home()/'.antigravity_quota_status.json').read_text()); p=d.get('dashboard_path',''); assert p.endswith('antigravity-token-dashboard/dashboard/index.html'), p; print('OK')" EXPECT OK
```

About the gates:
- **B1** runs the modules that touch the exporter or the status file with `HOME` pointed at an empty temporary folder. It passes only if no test created a status file there, whatever the individual test results are. (`test_lazy_turns` needs the real home, so it is deliberately left out.)
- **B2** must cover both halves of the intended behaviour, with `DEFAULT_STATUS_PATH` patched to a temporary file:
  - a library call without `status_path` writes nothing to the default path;
  - the CLI path without `--output-dir` still writes it.
- **B4** runs after the ADR-047 live pipeline op. It checks that the live status file points at the real dashboard.
