"""Unit and integration tests for scripts/watch_telemetry.py and service packaging."""

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

    def test_debounce_coalescing(self):
        """Integration test: rapid successive file modifications result in exactly 1 debounced export."""
        export_count = 0
        def count_export():
            nonlocal export_count
            export_count += 1

        stop_event = threading.Event()
        wal_file = self.conv_dir / "active.db-wal"
        wal_file.write_bytes(b"initial wal")

        t = threading.Thread(
            target=watch_loop,
            kwargs={
                "antigravity_dir": self.temp_path,
                "dashboard_path": self.dashboard_path,
                "log_path": self.log_path,
                "interval_seconds": 0.05,
                "debounce_seconds": 0.35,
                "max_debounce_seconds": 2.0,
                "stop_event": stop_event,
                "on_export": count_export,
            },
            daemon=True,
        )
        t.start()

        # Wait for initial export on start
        for _ in range(30):
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
        for _ in range(40):
            if export_count >= 2:
                break
            time.sleep(0.05)
        self.assertEqual(export_count, 2, "Burst of 5 writes should have coalesced into exactly 1 additional export")

        stop_event.set()
        t.join(timeout=1.0)
        self.assertFalse(t.is_alive())

    def test_clean_shutdown_on_stop_event(self):
        """Verify watcher loop responds immediately to stop_event and shuts down."""
        stop_event = threading.Event()
        t = threading.Thread(
            target=watch_loop,
            kwargs={
                "antigravity_dir": self.temp_path,
                "dashboard_path": self.dashboard_path,
                "log_path": self.log_path,
                "interval_seconds": 1.0,
                "stop_event": stop_event,
            },
            daemon=True,
        )
        t.start()
        time.sleep(0.1)
        self.assertTrue(t.is_alive())

        stop_event.set()
        t.join(timeout=1.0)
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
        cmd_restart(args)

        commands_invoked = [call_args[0][0][1] for call_args in mock_run.call_args_list if len(call_args[0][0]) > 1]
        self.assertIn("kickstart", commands_invoked)
        self.assertIn("unload", commands_invoked)
        self.assertIn("load", commands_invoked)


if __name__ == "__main__":
    unittest.main()
