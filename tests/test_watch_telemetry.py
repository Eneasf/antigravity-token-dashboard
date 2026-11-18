"""Unit and integration tests for scripts/watch_telemetry.py and service packaging."""

import contextlib
import io
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, MagicMock

from scripts.setup_service import render_plist_template, validate_plist_content, cmd_restart
from scripts.watch_telemetry import (
    DebounceController,
    get_snapshot,
    snapshots_differ,
    start_heartbeat_thread,
    update_watcher_heartbeat,
    watch_loop,
)


class TestWatchTelemetry(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.conv_dir = self.temp_path / "conversations"
        self.conv_dir.mkdir(parents=True)
        self.log_path = self.temp_path / "language_server.log"
        self.log_path.write_text("initial log content\n", encoding="utf-8")
        self.dashboard_path = self.temp_path / "dashboard" / "index.html"
        self.dashboard_path.parent.mkdir(parents=True)
        self.dashboard_path.write_text(
            '<html><body><script id="injected-dashboard-data" type="application/json">{}</script></body></html>',
            encoding="utf-8",
        )
        self.status_file = self.temp_path / "quota_status.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_snapshot_detects_db_and_wal(self):
        db1 = self.conv_dir / "test1.db"
        wal1 = self.conv_dir / "test1.db-wal"
        shm1 = self.conv_dir / "test1.db-shm"
        ignore_file = self.conv_dir / "ignored.txt"

        db1.write_bytes(b"dummy db data")
        wal1.write_bytes(b"dummy wal data")
        shm1.write_bytes(b"dummy shm data")
        ignore_file.write_bytes(b"ignored")

        snap = get_snapshot(self.conv_dir)
        self.assertIn(str(db1), snap)
        self.assertIn(str(wal1), snap)
        self.assertIn(str(shm1), snap)
        self.assertNotIn(str(ignore_file), snap)

    def test_snapshot_detects_language_server_log(self):
        snap1 = get_snapshot(self.conv_dir, log_path=self.log_path)
        self.assertIn(str(self.log_path.resolve()), snap1)

        time.sleep(0.01)
        self.log_path.write_text("updated log line\n", encoding="utf-8")
        snap2 = get_snapshot(self.conv_dir, log_path=self.log_path)

        self.assertTrue(snapshots_differ(snap1, snap2))

    def test_snapshots_differ_logic(self):
        s1 = {"/path/a": (100, 50)}
        s2 = {"/path/a": (100, 50)}
        s3 = {"/path/a": (200, 50)}
        s4 = {"/path/a": (100, 50), "/path/b": (100, 20)}

        self.assertFalse(snapshots_differ(s1, s2))
        self.assertTrue(snapshots_differ(s1, s3))
        self.assertTrue(snapshots_differ(s1, s4))

    def test_debounce_controller_logic(self):
        ctrl = DebounceController(settle_window=2.0, max_delay=10.0)
        self.assertFalse(ctrl.should_trigger(now=100.0))

        # Initial change at t=100.0
        ctrl.notify_change(now=100.0)
        self.assertTrue(ctrl.pending)
        self.assertFalse(ctrl.should_trigger(now=101.5))  # Settle window (2.0) not reached

        # Burst write at t=101.8
        ctrl.notify_change(now=101.8)
        self.assertFalse(ctrl.should_trigger(now=102.5))  # Only 0.7s since last change
        self.assertFalse(ctrl.should_trigger(now=103.7))  # 1.9s since last change

        # Settle achieved at t=103.9 (2.1s > 2.0s since last change at 101.8)
        self.assertTrue(ctrl.should_trigger(now=103.9))

        # Reset after trigger
        ctrl.reset()
        self.assertFalse(ctrl.pending)
        self.assertFalse(ctrl.should_trigger(now=104.0))

    def test_debounce_starvation_guard(self):
        # Even if changes arrive continuously, max_delay triggers export
        ctrl = DebounceController(settle_window=2.0, max_delay=5.0)
        start = 100.0
        ctrl.notify_change(now=start)

        # Changes keep coming every 1 second
        for step in range(1, 6):
            t = start + step
            ctrl.notify_change(now=t)
            if step < 5:
                self.assertFalse(ctrl.should_trigger(now=t))

        # At t=105.1 (total elapsed 5.1s >= max_delay 5.0s)
        self.assertTrue(ctrl.should_trigger(now=start + 5.1))

    def test_adaptive_settle_window(self):
        """Verify DebounceController adapts settle window dynamically to export duration."""
        ctrl = DebounceController(settle_window=2.0)
        self.assertEqual(ctrl.settle_window, 2.0)
        self.assertEqual(ctrl.base_settle_window, 2.0)

        # Expanding window updates max_delay below upper bound
        ctrl.update_settle_window(6.0)
        self.assertEqual(ctrl.settle_window, 6.0)
        self.assertEqual(ctrl.max_delay, 12.0)

        # Clamping to 10.0s upper bound (Finding C2 / Row 2)
        ctrl.update_settle_window(15.5)
        self.assertEqual(ctrl.settle_window, 10.0)
        self.assertEqual(ctrl.max_delay, 20.0)

        ctrl.update_settle_window(3600.0)
        self.assertEqual(ctrl.settle_window, 10.0)
        self.assertEqual(ctrl.max_delay, 20.0)

        # Clamping down respects base_settle_window floor
        ctrl.update_settle_window(1.0)
        self.assertEqual(ctrl.settle_window, 2.0)

    def test_watcher_logs_export_took(self):
        """Integration test: verify watcher logs 'export took' during export cycles."""
        wal_file = self.conv_dir / "cycle.db-wal"
        wal_file.write_bytes(b"initial wal")
        stop_event = threading.Event()

        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            t = threading.Thread(
                target=watch_loop,
                kwargs={
                    "antigravity_dir": self.temp_path,
                    "dashboard_path": self.dashboard_path,
                    "log_path": self.log_path,
                    "interval_seconds": 0.05,
                    "debounce_seconds": 0.1,
                    "max_debounce_seconds": 1.0,
                    "stop_event": stop_event,
                    "status_path": self.status_file,
                },
                daemon=True,
            )
            t.start()

            # Wait for initial export log
            for _ in range(80):
                if "export took" in mock_stdout.getvalue():
                    break
                time.sleep(0.05)

            # Trigger a new file modification cycle
            wal_file.write_bytes(b"next turn")

            # Wait for subsequent debounced export
            for _ in range(80):
                if mock_stdout.getvalue().count("export took") >= 2:
                    break
                time.sleep(0.05)

            stop_event.set()
            t.join(timeout=3.0)

            output = mock_stdout.getvalue()
            self.assertIn("export took", output)
            self.assertIn("Initial export complete: export took", output)
            self.assertIn("Export complete: export took", output)

    def test_debounce_coalescing(self):
        """Integration test: rapid successive file modifications result in exactly 1 debounced export."""
        export_count = 0
        def count_export():
            nonlocal export_count
            export_count += 1

        stop_event = threading.Event()
        wal_file = self.conv_dir / "active.db-wal"
        wal_file.write_bytes(b"initial wal")

        def run_watcher():
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                watch_loop(
                    antigravity_dir=self.temp_path,
                    dashboard_path=self.dashboard_path,
                    log_path=self.log_path,
                    interval_seconds=0.05,
                    debounce_seconds=0.35,
                    max_debounce_seconds=2.0,
                    stop_event=stop_event,
                    on_export=count_export,
                    status_path=self.status_file,
                )

        t = threading.Thread(target=run_watcher, daemon=True)
        t.start()

        # Wait for initial export on start
        for _ in range(60):
            if export_count >= 1:
                break
            time.sleep(0.05)
        initial_exports = export_count
        self.assertEqual(initial_exports, 1)

        # Rapid burst of 5 file modifications within ~50ms (< 350ms settle window)
        for i in range(5):
            wal_file.write_bytes(f"burst chunk {i}".encode("utf-8"))
            time.sleep(0.01)

        # Before settle window expires (elapsed ~100ms < 350ms), export_count should still be 1
        time.sleep(0.05)
        self.assertEqual(export_count, 1)

        # Wait for quiet settle window (350ms debounce)
        for _ in range(60):
            if export_count >= 2:
                break
            time.sleep(0.05)
        self.assertEqual(export_count, 2, "Burst of 5 writes should have coalesced into exactly 1 additional export")

        stop_event.set()
        t.join(timeout=3.0)
        self.assertFalse(t.is_alive())

    def test_clean_shutdown_on_stop_event(self):
        """Verify watcher loop responds immediately to stop_event and shuts down."""
        stop_event = threading.Event()

        def run_clean_watcher():
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                watch_loop(
                    antigravity_dir=self.temp_path,
                    dashboard_path=self.dashboard_path,
                    log_path=self.log_path,
                    interval_seconds=0.2,
                    stop_event=stop_event,
                    status_path=self.status_file,
                )

        t = threading.Thread(target=run_clean_watcher, daemon=True)
        t.start()
        time.sleep(0.2)
        self.assertTrue(t.is_alive())

        stop_event.set()
        t.join(timeout=3.0)
        self.assertFalse(t.is_alive(), "Watcher thread failed to stop promptly on stop_event")

    def test_launchagent_plist_generation_and_validation(self):
        """Verify service packaging renders valid LaunchAgent plist conforming to Apple XML."""
        rendered = render_plist_template(
            label="com.test.watcher",
            interval=1.5,
            debounce=3.0,
        )
        self.assertIn("<key>Label</key>", rendered)
        self.assertIn("<string>com.test.watcher</string>", rendered)
        self.assertIn("--interval", rendered)
        self.assertIn("1.5", rendered)
        self.assertIn("--debounce", rendered)
        self.assertIn("3.0", rendered)

        self.assertIn("<key>KeepAlive</key>", rendered)
        self.assertIn("<true/>", rendered)
        self.assertIn("<key>ThrottleInterval</key>", rendered)
        self.assertIn("<integer>2</integer>", rendered)

        # Validate with plistlib and plutil
        self.assertTrue(validate_plist_content(rendered))

    @patch("subprocess.run")
    def test_cmd_restart_kickstart(self, mock_run):
        import argparse
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_run.return_value = mock_res

        dest = self.temp_path / "com.test.plist"
        dest.write_text("dummy", encoding="utf-8")

        args = argparse.Namespace(dest=str(dest), interval=1.0, debounce=2.0)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cmd_restart(args)

        self.assertTrue(any("kickstart" in call_args[0][0] for call_args in mock_run.call_args_list))

    @patch("subprocess.run")
    def test_cmd_restart_fallback_reload(self, mock_run):
        import argparse
        # Simulate kickstart failure (returncode 1) then successful reload
        mock_res_fail = MagicMock()
        mock_res_fail.returncode = 1
        mock_res_fail.stderr = b"kickstart failed"

        mock_res_ok = MagicMock()
        mock_res_ok.returncode = 0
        mock_res_ok.stderr = b""

        mock_run.side_effect = [mock_res_fail, mock_res_ok, mock_res_ok]

        dest = self.temp_path / "com.test.plist"
        dest.write_text("dummy", encoding="utf-8")

        args = argparse.Namespace(dest=str(dest), interval=1.0, debounce=2.0)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cmd_restart(args)

        commands_invoked = [call_args[0][0][1] for call_args in mock_run.call_args_list if len(call_args[0][0]) > 1]
        self.assertIn("kickstart", commands_invoked)
        self.assertIn("unload", commands_invoked)
        self.assertIn("load", commands_invoked)

    def test_update_watcher_heartbeat_non_existent_file(self):
        """Test writing heartbeat to a non-existent file creates valid JSON with 'watcher' dict."""
        import json
        status_path = self.temp_path / "new_status.json"
        self.assertFalse(status_path.exists())

        res = update_watcher_heartbeat(status_path=status_path, pid=12345, heartbeat_utc="2026-09-20T17:00:00+00:00")
        self.assertTrue(status_path.exists())

        data = json.loads(status_path.read_text(encoding="utf-8"))
        self.assertIn("watcher", data)
        self.assertEqual(data["watcher"]["pid"], 12345)
        self.assertEqual(data["watcher"]["heartbeat_utc"], "2026-09-20T17:00:00+00:00")

    def test_update_watcher_heartbeat_existing_file_preserves_fields(self):
        """Test writing heartbeat to an existing status file preserves existing status fields while updating 'watcher'."""
        import json
        status_path = self.temp_path / "existing_status.json"
        initial_data = {
            "status": "SAFE_IN_QUOTA",
            "gemini_5h_pct": 15.0,
            "plan_name": "Google AI Ultra (5x)",
            "watcher": {
                "pid": 11111,
                "heartbeat_utc": "2026-09-20T16:00:00+00:00",
            },
        }
        status_path.write_text(json.dumps(initial_data, indent=2), encoding="utf-8")

        res = update_watcher_heartbeat(status_path=status_path, pid=22222, heartbeat_utc="2026-09-20T17:05:00+00:00")

        updated_data = json.loads(status_path.read_text(encoding="utf-8"))
        self.assertEqual(updated_data["status"], "SAFE_IN_QUOTA")
        self.assertEqual(updated_data["gemini_5h_pct"], 15.0)
        self.assertEqual(updated_data["plan_name"], "Google AI Ultra (5x)")
        self.assertEqual(updated_data["watcher"]["pid"], 22222)
        self.assertEqual(updated_data["watcher"]["heartbeat_utc"], "2026-09-20T17:05:00+00:00")

    def test_start_heartbeat_thread_continuous_updates(self):
        """Verify start_heartbeat_thread runs background thread writing periodic heartbeats."""
        import json
        import os

        status_path = self.temp_path / "thread_status.json"
        stop_event = threading.Event()

        t = start_heartbeat_thread(status_path, stop_event, interval=0.1)
        try:
            time.sleep(0.25)
            self.assertTrue(status_path.exists())
            data = json.loads(status_path.read_text(encoding="utf-8"))
            self.assertIn("watcher", data)
            self.assertEqual(data["watcher"]["pid"], os.getpid())
            self.assertIn("heartbeat_utc", data["watcher"])
        finally:
            stop_event.set()
            t.join(timeout=1.0)
        self.assertFalse(t.is_alive())

    def test_update_watcher_heartbeat_concurrent_writes(self):
        """Verify concurrent update_watcher_heartbeat calls do not corrupt status file or collide on temp files."""
        import concurrent.futures
        import json

        status_path = self.temp_path / "concurrent_status.json"
        status_path.write_text(json.dumps({"status": "SAFE_IN_QUOTA"}), encoding="utf-8")

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(update_watcher_heartbeat, status_path=status_path, pid=1000 + i)
                for i in range(50)
            ]
            results = [f.result() for f in futures]

        self.assertTrue(all(results), "All concurrent heartbeat updates should succeed")
        data = json.loads(status_path.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "SAFE_IN_QUOTA")
        self.assertIn("watcher", data)
        self.assertIn("pid", data["watcher"])
        self.assertIn("heartbeat_utc", data["watcher"])
        self.assertGreaterEqual(data["watcher"]["pid"], 1000)
        self.assertLess(data["watcher"]["pid"], 1050)

        # Ensure no dangling temp files remain in target directory
        temp_files = list(self.temp_path.glob(f".{status_path.name}.tmp.*"))
        self.assertEqual(temp_files, [], f"Found dangling temp files: {temp_files}")

    def test_update_watcher_heartbeat_replace_error_cleanup(self):
        """Verify update_watcher_heartbeat cleans up temp file if os.replace fails."""
        status_path = self.temp_path / "replace_fail_status.json"
        with patch("os.replace", side_effect=OSError("Permission denied")):
            res = update_watcher_heartbeat(status_path=status_path)
            self.assertFalse(res)
        temp_files = list(self.temp_path.glob(f".{status_path.name}.tmp.*"))
        self.assertEqual(temp_files, [], f"Temp file was not cleaned up on error: {temp_files}")

    def test_watcher_loop_has_no_direct_vault_sync_calls(self):
        """Verify watch_loop does not contain direct calls to sync_conversations_to_vault or sync_vault_telemetry (Finding C5 / Row 8)."""
        import ast
        import inspect

        src = inspect.getsource(watch_loop)
        tree = ast.parse(src)
        called_functions = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    called_functions.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    called_functions.add(node.func.attr)

        self.assertNotIn(
            "sync_conversations_to_vault",
            called_functions,
            "watch_loop must not call sync_conversations_to_vault directly",
        )
        self.assertNotIn(
            "sync_vault_telemetry",
            called_functions,
            "watch_loop must not call sync_vault_telemetry directly",
        )

        non_comment_lines = [line.strip() for line in src.splitlines() if not line.strip().startswith("#")]
        executable_text = "\n".join(non_comment_lines)
        self.assertNotIn(
            "sync_conversations_to_vault",
            executable_text,
            "watch_loop source contains un-commented reference to sync_conversations_to_vault",
        )
        self.assertNotIn(
            "sync_vault_telemetry",
            executable_text,
            "watch_loop source contains un-commented reference to sync_vault_telemetry",
        )

    def test_sync_vault_telemetry_archives_logs_only(self):
        """Verify sync_vault_telemetry delegates to archive_logs and does not call sync_conversations_to_vault."""
        from scripts.watch_telemetry import sync_vault_telemetry

        with patch("src.log_archiver.archive_logs") as mock_archive, \
             patch("src.vault.sync_conversations_to_vault", create=True) as mock_conv_sync:
            sync_vault_telemetry(antigravity_dir=self.temp_path, log_path=self.log_path)
            self.assertEqual(mock_archive.call_count, 1)
            self.assertEqual(mock_conv_sync.call_count, 0)

    @patch("scripts.watch_telemetry.export_telemetry")
    @patch("src.vault.sync_conversations_to_vault")
    def test_watcher_export_cycle_delegates_to_export_telemetry_without_pre_sync(
        self, mock_vault_sync, mock_export
    ):
        """Verify watcher single-cycle export executes export_telemetry without preceding conversation vault sync (Finding C5 / Row 8)."""
        mock_export.return_value = {"status": "ok"}
        stop_event = threading.Event()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            res = watch_loop(
                antigravity_dir=self.temp_path,
                dashboard_path=self.dashboard_path,
                log_path=self.log_path,
                once=True,
                sync_vault=True,
                stop_event=stop_event,
                status_path=self.status_file,
            )

        self.assertEqual(
            mock_vault_sync.call_count,
            0,
            "Watcher loop must not invoke sync_conversations_to_vault prior to export_telemetry",
        )
        self.assertEqual(
            mock_export.call_count,
            1,
            "Watcher loop must invoke export_telemetry exactly once",
        )
        self.assertEqual(res, 1, "watch_loop should return 1 export completed")

    @patch("scripts.watch_telemetry.export_telemetry")
    @patch("src.vault.sync_conversations_to_vault")
    def test_watcher_debounced_cycle_delegates_without_vault_sync(
        self, mock_vault_sync, mock_export
    ):
        """Verify debounced multi-event watcher cycle does not call sync_conversations_to_vault across settled exports."""
        mock_export.return_value = {"status": "ok"}
        stop_event = threading.Event()
        wal_file = self.conv_dir / "cycle_test.db-wal"
        wal_file.write_bytes(b"initial wal")

        def run_watcher():
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                watch_loop(
                    antigravity_dir=self.temp_path,
                    dashboard_path=self.dashboard_path,
                    log_path=self.log_path,
                    interval_seconds=0.05,
                    debounce_seconds=0.1,
                    max_debounce_seconds=1.0,
                    stop_event=stop_event,
                    sync_vault=True,
                    status_path=self.status_file,
                )

        t = threading.Thread(target=run_watcher, daemon=True)
        t.start()

        for _ in range(40):
            if mock_export.call_count >= 1:
                break
            time.sleep(0.05)

        wal_file.write_bytes(b"turn 2 wal")

        for _ in range(40):
            if mock_export.call_count >= 2:
                break
            time.sleep(0.05)

        stop_event.set()
        t.join(timeout=3.0)

        self.assertEqual(
            mock_vault_sync.call_count,
            0,
            "Debounced export cycle must not invoke sync_conversations_to_vault",
        )
        self.assertGreaterEqual(
            mock_export.call_count,
            2,
            "Watcher should have completed initial export and debounced export",
        )

    @patch("scripts.watch_telemetry.run_isolated_export_subprocess")
    def test_watcher_isolated_export_subprocess_delegation(self, mock_isolated):
        """Verify watch_loop with isolate_export_subprocess=True delegates to run_isolated_export_subprocess."""
        mock_isolated.return_value = {"status": "ok"}
        stop_event = threading.Event()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            res = watch_loop(
                antigravity_dir=self.temp_path,
                dashboard_path=self.dashboard_path,
                log_path=self.log_path,
                once=True,
                stop_event=stop_event,
                status_path=self.status_file,
                isolate_export_subprocess=True,
            )
        self.assertEqual(res, 1)
        self.assertEqual(mock_isolated.call_count, 1)


if __name__ == "__main__":
    unittest.main()
