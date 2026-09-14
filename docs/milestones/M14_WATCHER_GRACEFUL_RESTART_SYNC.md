# Milestone Slice M14: Watcher Graceful Restart, Self-Healing Keepalive & Atomic Export Sync

- **Status**: Completed
- **Date**: 2026-09-08
- **Branch**: `feat/watcher-graceful-restart-sync`
- **ADR Reference**: ADR-026
- **Architecture Invariant**: Atomic Telemetry Export (`os.replace`) & Daemon Self-Healing (`KeepAlive: true`, `launchctl kickstart -k`).

---

## 1. Architectural Objectives & Invariants

1. **Atomic Exporter Writes (`scripts/export_dashboard.py`)**:
   - In near real-time watcher setups, concurrent browser tab reads of `dashboard/data.js` and `dashboard/data.json` could occasionally collide with active file writes, leading to JSON parse errors or blank charts.
   - Implemented POSIX atomic file replacement:
     - Output payloads are written to temporary staging files (`data.js.tmp`, `data.json.tmp`, `index.html.tmp`).
     - Once completely flushed to disk, `os.replace()` atomically swaps the staging file over the active target.
     - Guarantees zero partial-write artifacts and collision-free reading under concurrent loads.

2. **Self-Healing LaunchAgent Daemon (`scripts/setup_service.py` & `.plist.template`)**:
   - Added daemon resilience keys to `config/com.antigravity.telemetry.watcher.plist.template`:
     - `<key>KeepAlive</key><true/>`: macOS `launchd` automatically revives the watcher process if terminated or crash-killed.
     - `<key>ThrottleInterval</key><integer>2</integer>`: Prevents CPU churn during rapid restart cycles.
   - Added CLI lifecycle command:
     ```bash
     python3 scripts/setup_service.py restart
     ```
   - Uses native macOS `launchctl kickstart -k gui/<uid>/com.antigravity.telemetry.watcher` for seamless signal-level process recycling without unregistering the service, with automatic fallback to `unload` + `load -w`.

3. **Line-Buffered Daemon Output (`scripts/watch_telemetry.py`)**:
   - Configured `sys.stdout.reconfigure(line_buffering=True)` and `sys.stderr.reconfigure(line_buffering=True)`.
   - Eliminates standard Python 4KB buffer latency so telemetry events flush immediately to system log files and active `tail -f` streams.

4. **Telemetry Freshness & Spillover Badges in UI (`dashboard/index.html`)**:
   - Added dynamic data freshness indicator (`#badge-last-extracted`):
     - Calculates elapsed time from telemetry `reference_timestamp`:
       - `< 90s`: `● Synced: Just now` (green badge)
       - `< 10m`: `● Synced: Xm ago` (green badge)
       - `> 10m`: `⚠️ Stale (Xh Xm ago)` (amber warning badge)
   - Added dynamic Google One Credit Spillover status pill (`#gemini-spillover-badge`):
     - Reflects `Credit Spillover ON` vs `Credit Overages OFF` based on `summary.use_ai_credits`.

---

## 2. Verified Acceptance Gates (VDONE.md)

1. **Gate V58**: Atomic File Replacement Invariant verified in `scripts/export_dashboard.py` (`data.js.tmp` -> `data.js`). (PASS)
2. **Gate V59**: LaunchAgent Restart & KeepAlive Lifecycle (`python3 -m unittest tests.test_watch_telemetry.TestWatchTelemetry.test_cmd_restart_kickstart tests.test_watch_telemetry.TestWatchTelemetry.test_cmd_restart_fallback_reload`). (PASS)
3. **Gate V60**: Full Test Suite Regression Integrity (`python3 -m unittest discover -s tests`: 74/74 tests passing in 1.696s). (PASS)
