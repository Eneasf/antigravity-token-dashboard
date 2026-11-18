# Audit 2026-09-24 — Watcher Stopped Writing the Status File (M65 Regression) and Never Repairs a Corrupted One

> **Auditor:** Claude (external second opinion; read-only; no code changed)
> **Scope:** finding `TI-2` in two parts (TI-2a, a regression from M65; TI-2b, no self-repair), observed at the end of Study A (`Agentic work`, 2026-09-24)
> **Tree at audit time:** `main` @ `c847fa3`, clean

## Finding TI-2a (urgent) — since M65, watcher exports no longer write the status file at all `[EVIDENCED]`

**What happens:**
- M65 (TI-1) changed `scripts/export_dashboard.py:759–761` so that `export_telemetry()` writes the status file only when a caller passes `status_path` or `output_dir`.
- The CLI still passes `DEFAULT_STATUS_PATH` explicitly (`:1025`).
- But the watcher does **not** use the CLI. It calls `export_telemetry(antigravity_dir=…, dashboard_path=…, log_path=…)` directly, at `scripts/watch_telemetry.py:301` and `:371`, without `status_path`.
- So since M65 was deployed (≈13:30 BST, 2026-09-24), every watcher export leaves `~/.antigravity_quota_status.json` untouched. Only the heartbeat's `watcher` field changes, and the menu bar shows frozen figures.

**Evidence:**
- The watcher log (`~/Library/Logs/Antigravity/telemetry_watcher.stdout.log`) records full exports at 21:36, 21:48 and 21:51 (after a manual refresh), each "Export complete".
- Yet the status file kept `updated_at = 19:00:28Z` and a stale `dashboard_path` throughout.
- One CLI run (`python3 scripts/export_dashboard.py`, 21:54) repaired the file immediately. It will go stale again until this row lands.

**Correction to `AUDIT_2026-09-24_TEST_ISOLATION.md`:** its "intended behaviour" said the CLI without `--output-dir` is "what the watcher uses". That was wrong: the watcher calls the library function directly. M65 implemented the note as written, and no gate checked that watcher exports still update the file. The error is the auditor's, not the implementer's.

## Finding TI-2b — a foreign `dashboard_path` survives until the next full export `[EVIDENCED]`

**What happens:**
- `scripts/watch_telemetry.py:40–82` (`update_watcher_heartbeat`) reads `~/.antigravity_quota_status.json`, updates only `data["watcher"] = {pid, heartbeat_utc}`, and writes the file back. **Every other field is preserved as found, including a wrong `dashboard_path`.**
- `watch_loop` (`:327–392`) runs a full export, which rewrites the whole file, only in three cases:
  - the manual refresh file `~/.antigravity_refresh_requested` exists;
  - `SIGUSR1` is received;
  - activity has settled in the telemetry storage.

  Without Antigravity activity, a corrupted status file therefore stays corrupted indefinitely, while the heartbeat keeps making it look fresh.

**Evidence:**
- The Study A trial copies ran pre-TI-1 test suites, as accepted in Protocol Amendment 1, §13 A1.4.
- The last copy (`~/wt/r-b2fc`, a replay trial) left `dashboard_path = ~/wt/r-b2fc/dashboard/index.html` in the live file.
- The copy was deleted at the end of the study. At 21:50 BST the live file still pointed at it, with a heartbeat only seconds old, so the menu-bar monitor stayed broken.
- The study's process checker failed gate G5 on exactly this point (`docs/milestones/2026-09-24_VERIFIER_SENSITIVITY.md` in `Agentic work`).

**Why it matters:** TI-1 removed one way the file gets corrupted (our own tests). It did not make the monitor robust to the others:
- an old checkout;
- a manual export into another folder;
- a future bug.

A heartbeat that refreshes the timestamp of a broken file hides the fault.

**Intended behaviour after the fix:**
- On each heartbeat tick, the watcher checks the live status file. If `dashboard_path` is missing, differs from the watcher's own `dashboard_path`, or points to a file that does not exist, the watcher runs a full export through the same code path as a manual refresh.
- The repair is rate-limited to at most one per 60 s, so a persistent fault cannot cause an export loop.
- Each repair is logged as `Foreign status file detected`.
- A matching status file never triggers an export.

## Row

- **Row 1 (TI-2)**: Restore watcher status writes and self-heal a foreign status file (`fix/status-self-heal`)
  - **Part A (TI-2a, first):** pass the watcher's `effective_status_path` as `status_path=` in both `export_telemetry(...)` calls in `watch_loop` (`scripts/watch_telemetry.py:301`, `:371`).
  - **Part B (TI-2b):** the heartbeat-tick validation and rate-limited repair described above.
  - **Touches:** `scripts/watch_telemetry.py` and a new test module `tests/test_status_self_heal.py`.
  - **Delegation:** disjoint scopes. One worker owns the watcher change, one owns the tests. An independent verifier goes last.
  - **Live pipeline op:** the watcher changes, so ADR-047 applies: run the live export, restart the LaunchAgent, then `scripts/ops_check.py`.

**Gates** (for `VDONE.md` §B):

```text
B1 Self-heal unit tests: CHECK python3 -m unittest tests.test_status_self_heal EXPECT OK
B2 Status isolation still holds (TI-1 regression): CHECK python3 -c "import os,subprocess,tempfile,pathlib; h=tempfile.mkdtemp(); subprocess.run(['python3','-m','unittest','tests.test_export_dashboard','tests.test_export_lock','tests.test_quota_status_enrichment','tests.test_watch_telemetry','tests.test_status_isolation','tests.test_status_self_heal'], env={**os.environ,'HOME':h}, capture_output=True); assert not (pathlib.Path(h)/'.antigravity_quota_status.json').exists(), 'a test wrote the home status file'; print('OK')" EXPECT OK
B3 Unit suite: CHECK python3 -m unittest discover -s tests EXPECT OK, < 90 s
B4 Live monitor intact: CHECK python3 -c "import json,pathlib; d=json.loads((pathlib.Path.home()/'.antigravity_quota_status.json').read_text()); p=d.get('dashboard_path',''); assert p.endswith('antigravity-token-dashboard/dashboard/index.html'), p; print('OK')" EXPECT OK
B5 Live watcher refreshes the file: CHECK python3 -c "import json,pathlib,datetime; d=json.loads((pathlib.Path.home()/'.antigravity_quota_status.json').read_text()); t=datetime.datetime.fromisoformat(d['updated_at']); age=(datetime.datetime.now(datetime.timezone.utc)-t).total_seconds(); assert age < 900, f'status updated_at is {age:.0f}s old'; print('OK')" EXPECT OK
```

About the gates:
- **B1** must use temporary status files, never the real one. It must cover five cases:
  1. **a watcher-triggered export calls `export_telemetry` with `status_path` equal to the watcher's status path** (TI-2a regression test);
  2. a foreign `dashboard_path` triggers exactly one export (with `export_telemetry` mocked);
  3. a missing file triggers the same;
  4. a matching status file triggers none;
  5. a second mismatch within 60 s triggers none.
- **B5** runs after the ADR-047 restart. Request one refresh (`touch ~/.antigravity_refresh_requested`), wait for `Export complete` in `~/Library/Logs/Antigravity/telemetry_watcher.stdout.log`, then run the check. It proves that the **watcher**, not the CLI, updated the file.
- **B2** re-runs the TI-1 isolation check with the new module included.
- **B4** runs after the ADR-047 live pipeline op.

**Also observed, out of scope for this row:** watcher exports now take 135–391 s (log, 21:36–21:54 BST), up from about 12–57 s earlier in the month. During that time the single-exporter lock blocks CLI exports. This is worth a separate performance finding.
