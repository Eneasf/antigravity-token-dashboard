# M49 · Export Advisory Lock & Concurrency Control · 2026-09-19 · v2.7.0

## Why
Eliminated file write races and SQLite vault collision crashes during concurrent export triggers by implementing an exclusive advisory lock on `.export.lock`, atomic unique temporary output files, and daemon refresh signaling (audit row 4, ADR-062).

## What changed
- `scripts/export_dashboard.py`: Implemented advisory `fcntl.flock` on `.export.lock` and replaced fixed temporary filenames with `atomic_write_text` using `tempfile.NamedTemporaryFile`.
- `scripts/watch_telemetry.py`: Added polling for `~/.antigravity_refresh_requested` and `SIGUSR1` signal handling to trigger immediate dashboard exports.
- `macos/AntigravityBar/Sources/AntigravityBar/StatusStore.swift`: Updated `refreshNow()` to touch `~/.antigravity_refresh_requested` when watcher is running instead of launching concurrent exporter.
- `.gitignore`: Added `.export.lock` and `*.lock` rules.
- `tests/test_export_lock.py`: Authored comprehensive test suite verifying thread concurrency, byte-identical outputs, CLI skip on lock contention, and signal unlinking.
- `docs/REPO_MAP.md`: Documented `test_export_lock.py`.
- `CHANGELOG.md`: Added release notes for v2.7.0 / Milestone 49.
- `docs/HANDOVER.md`: Logged ADR-062, updated Milestone Index, and transitioned Row 4 from Open to Closed.
- `package.json` & `pyproject.toml`: Bumped version to `2.7.0`.

## Decisions taken
- ADR-062: Exporter Advisory Lock & Concurrency Control adopted.

## Gates & proofs
- B1 Export lock test: `python3 -m unittest tests.test_export_lock` -> Ran 5 tests in 0.928s, OK
- B2 No static tmp file: `grep -c 'data.js.tmp' scripts/export_dashboard.py` -> 0 (EXPECT 0)
- B3 Advisory lock in export: `grep -c 'fcntl.flock' scripts/export_dashboard.py` -> 2 (EXPECT > 0)
- B4 Refresh signal watcher: `grep -c 'antigravity_refresh_requested' scripts/watch_telemetry.py` -> 3 (EXPECT > 0)
- B5 Refresh signal menubar: `grep -c 'antigravity_refresh_requested' macos/AntigravityBar/Sources/AntigravityBar/StatusStore.swift` -> 2 (EXPECT > 0)
- B6 Lock file gitignored: `grep -c '\.export\.lock' .gitignore` -> 2 (EXPECT > 0)
- B7 VDONE size budget: `wc -l VDONE.md` -> 20 lines (EXPECT < 150 lines)
- B8 Gate runner proof: `python3 -m unittest tests.test_vdone_gates` -> Ran 4 tests in 13.128s, OK

## Ops check
`[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 57220) | verified: 2026-09-19T19:25:37+01:00`

## Closing report
Merged:   M49 · v2.7.0 · Export advisory lock, unique temp file, refresh signaling (audit row 4)
Open now: Row 5 (C2/U4/U7): Dynamic labels, simulator default tier, plain English labels, light theme default (`fix/labels-and-simulator-defaults`) [P0]
Next slice will touch: dashboard/index.html, dashboard/app.js, dashboard/styles.css, tests/test_labels_and_defaults.py
Needs owner: nothing
Freeze:   in effect until rows 4–5 merge
