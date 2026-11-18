"""Unit tests for status file self-healing and watcher status writes (TI-2 / ADR-072 / Milestone 66).

Validates Gate B1:
- Case 1: Watcher-triggered export calls export_telemetry with status_path equal to
  the watcher's status path (TI-2a regression test). Running
  watch_loop(..., once=True, status_path=temp_status_file) results in temp_status_file
  being written and containing valid status JSON.
- Case 2: A foreign dashboard_path (pointing to a non-existent file or a different
  dashboard file) triggers exactly one export (with export_telemetry mocked).
- Case 3: A missing status file triggers exactly one export (with export_telemetry mocked).
- Case 4: A matching status file triggers none (0 exports triggered by the health check).
- Case 5: A second mismatch within 60 s triggers none (rate limiting prevents repeat export).

Also validates check_status_health helper unit behavior.
Strict isolation invariant: NEVER writes to ~/.antigravity_quota_status.json or DEFAULT_STATUS_PATH.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.watch_telemetry import check_status_health, watch_loop


class TestStatusSelfHeal(unittest.TestCase):
    """Test suite for watcher status file self-repair and export routing."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.antigravity_dir = self.temp_path / "antigravity"
        self.conv_dir = self.antigravity_dir / "conversations"
        self.conv_dir.mkdir(parents=True)

        self.dashboard_dir = self.temp_path / "dashboard"
        self.dashboard_dir.mkdir(parents=True)
        self.dashboard_path = self.dashboard_dir / "index.html"
        self.dashboard_path.write_text(
            '<html><head><script id="injected-dashboard-data" type="application/json">{}</script></head><body></body></html>',
            encoding="utf-8",
        )

        self.log_path = self.temp_path / "language_server.log"
        self.log_path.write_text("", encoding="utf-8")

        self.status_file = self.temp_path / "quota_status.json"

        # Trap any accidental unpatched DEFAULT_STATUS_PATH or DEFAULT_REFRESH_SIGNAL_PATH calls into temp isolation
        self.fake_default_status = self.temp_path / "fake_home" / ".antigravity_quota_status.json"
        self.fake_default_status.parent.mkdir(parents=True, exist_ok=True)
        self.fake_refresh_signal = self.temp_path / "fake_home" / ".antigravity_refresh_requested"

        self.patch_export_default = patch("scripts.export_dashboard.DEFAULT_STATUS_PATH", self.fake_default_status)
        self.patch_watch_default = patch("scripts.watch_telemetry.DEFAULT_STATUS_PATH", self.fake_default_status)
        self.patch_watch_signal = patch("scripts.watch_telemetry.DEFAULT_REFRESH_SIGNAL_PATH", self.fake_refresh_signal)

        self.patch_export_default.start()
        self.patch_watch_default.start()
        self.patch_watch_signal.start()

    def tearDown(self):
        self.patch_export_default.stop()
        self.patch_watch_default.stop()
        self.patch_watch_signal.stop()
        try:
            self.temp_dir.cleanup()
        except OSError:
            pass

    # -------------------------------------------------------------------------
    # Unit tests for check_status_health helper
    # -------------------------------------------------------------------------

    def test_check_status_health_missing_file(self):
        """Missing status file returns healthy=False with descriptive reason."""
        nonexistent = self.temp_path / "missing_status.json"
        is_healthy, reason = check_status_health(nonexistent, self.dashboard_path)
        self.assertFalse(is_healthy)
        self.assertIn("does not exist", reason)

    def test_check_status_health_corrupt_json(self):
        """Corrupt JSON in status file returns healthy=False."""
        self.status_file.write_text("{not-valid-json", encoding="utf-8")
        is_healthy, reason = check_status_health(self.status_file, self.dashboard_path)
        self.assertFalse(is_healthy)
        self.assertIn("invalid JSON", reason)

    def test_check_status_health_non_dict_json(self):
        """Valid JSON that is not a dictionary returns healthy=False."""
        self.status_file.write_text("[\"item1\", \"item2\"]", encoding="utf-8")
        is_healthy, reason = check_status_health(self.status_file, self.dashboard_path)
        self.assertFalse(is_healthy)
        self.assertIn("invalid JSON", reason)

    def test_check_status_health_missing_dashboard_path_key(self):
        """Status file without dashboard_path key returns healthy=False."""
        self.status_file.write_text(json.dumps({"updated_at": "2026-09-24T20:00:00Z"}), encoding="utf-8")
        is_healthy, reason = check_status_health(self.status_file, self.dashboard_path)
        self.assertFalse(is_healthy)
        self.assertIn("dashboard_path missing", reason)

    def test_check_status_health_target_file_does_not_exist(self):
        """dashboard_path pointing to a non-existent file on disk returns healthy=False."""
        dead_path = self.temp_path / "does_not_exist" / "index.html"
        self.status_file.write_text(json.dumps({"dashboard_path": str(dead_path)}), encoding="utf-8")
        is_healthy, reason = check_status_health(self.status_file, self.dashboard_path)
        self.assertFalse(is_healthy)
        self.assertIn("target does not exist", reason)

    def test_check_status_health_different_dashboard_file(self):
        """dashboard_path pointing to a different existing dashboard file returns healthy=False."""
        other_dir = self.temp_path / "other_dashboard"
        other_dir.mkdir(parents=True)
        other_dash = other_dir / "index.html"
        other_dash.write_text("<html></html>", encoding="utf-8")

        self.status_file.write_text(json.dumps({"dashboard_path": str(other_dash)}), encoding="utf-8")
        is_healthy, reason = check_status_health(self.status_file, self.dashboard_path)
        self.assertFalse(is_healthy)
        self.assertIn("dashboard_path mismatch", reason)

    def test_check_status_health_matching_dashboard_path(self):
        """dashboard_path matching expected path returns healthy=True."""
        self.status_file.write_text(
            json.dumps({"dashboard_path": str(self.dashboard_path.resolve())}),
            encoding="utf-8",
        )
        is_healthy, reason = check_status_health(self.status_file, self.dashboard_path)
        self.assertTrue(is_healthy)
        self.assertEqual(reason, "healthy")

    # -------------------------------------------------------------------------
    # Gate B1: The 5 required acceptance test cases
    # -------------------------------------------------------------------------

    def test_case_1_watcher_triggered_export_writes_status_path(self):
        """Case 1 (TI-2a regression test): Watcher-triggered export calls export_telemetry

        with status_path equal to the watcher's status path.
        Running watch_loop(..., once=True, status_path=temp_status_file) results in
        temp_status_file being written and containing valid status JSON.
        """
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            count = watch_loop(
                antigravity_dir=self.antigravity_dir,
                dashboard_path=self.dashboard_path,
                log_path=self.log_path,
                status_path=self.status_file,
                refresh_signal_path=self.fake_refresh_signal,
                once=True,
            )

        self.assertGreaterEqual(count, 1)
        self.assertTrue(self.status_file.exists(), "Watcher export must write to designated status_path")
        self.assertFalse(
            self.fake_default_status.exists(),
            "Watcher must not touch DEFAULT_STATUS_PATH when explicit status_path is passed",
        )

        data = json.loads(self.status_file.read_text(encoding="utf-8"))
        self.assertIsInstance(data, dict)
        self.assertIn("dashboard_path", data)
        self.assertIn("updated_at", data)
        self.assertIn("watcher", data)
        self.assertEqual(data["watcher"]["pid"], os.getpid())
        self.assertIn("status", data)

    def test_case_2_foreign_dashboard_path_triggers_one_export(self):
        """Case 2: A foreign dashboard_path (e.g. pointing to a non-existent file or a

        different dashboard file) triggers exactly one export (with export_telemetry mocked).
        """
        foreign_dashboard = self.temp_path / "foreign" / "index.html"
        self.status_file.write_text(
            json.dumps({
                "dashboard_path": str(foreign_dashboard),
                "updated_at": "2026-09-24T20:00:00Z",
            }),
            encoding="utf-8",
        )

        mock_export = MagicMock(return_value={"status": "ok"})
        stop_event = threading.Event()
        captured_stdout = io.StringIO()

        with patch("scripts.watch_telemetry.export_telemetry", mock_export):
            with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(io.StringIO()):
                t = threading.Thread(
                    target=watch_loop,
                    kwargs={
                        "antigravity_dir": self.antigravity_dir,
                        "dashboard_path": self.dashboard_path,
                        "log_path": self.log_path,
                        "status_path": self.status_file,
                        "refresh_signal_path": self.fake_refresh_signal,
                        "interval_seconds": 0.01,
                        "heartbeat_interval": 0.03,
                        "repair_rate_limit": 60.0,
                        "stop_event": stop_event,
                    },
                    daemon=True,
                )
                t.start()
                # Initial export occurs at start (call 1).
                # After 0.03s, heartbeat detects foreign dashboard_path -> triggers repair export (call 2).
                # Sleep spans multiple heartbeat ticks to verify no additional export occurs within 60s.
                time.sleep(0.12)
                stop_event.set()
                t.join(timeout=2.0)

        self.assertEqual(mock_export.call_count, 2, "Expected initial export + exactly 1 self-heal repair export")
        self.assertEqual(mock_export.call_args_list[1].kwargs["status_path"], self.status_file)
        self.assertIn("Foreign status file detected", captured_stdout.getvalue())

    def test_case_3_missing_status_file_triggers_one_export(self):
        """Case 3: A missing status file triggers exactly one export (with export_telemetry mocked)."""
        if self.status_file.exists():
            self.status_file.unlink()

        mock_export = MagicMock(return_value={"status": "ok"})
        stop_event = threading.Event()
        captured_stdout = io.StringIO()

        with patch("scripts.watch_telemetry.export_telemetry", mock_export):
            with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(io.StringIO()):
                t = threading.Thread(
                    target=watch_loop,
                    kwargs={
                        "antigravity_dir": self.antigravity_dir,
                        "dashboard_path": self.dashboard_path,
                        "log_path": self.log_path,
                        "status_path": self.status_file,
                        "refresh_signal_path": self.fake_refresh_signal,
                        "interval_seconds": 0.01,
                        "heartbeat_interval": 0.03,
                        "repair_rate_limit": 60.0,
                        "stop_event": stop_event,
                    },
                    daemon=True,
                )
                t.start()
                time.sleep(0.12)
                stop_event.set()
                t.join(timeout=2.0)

        self.assertEqual(mock_export.call_count, 2, "Expected initial export + exactly 1 repair export for missing status")
        self.assertIn("Foreign status file detected", captured_stdout.getvalue())

    def test_case_4_matching_status_file_triggers_zero_exports(self):
        """Case 4: A matching status file triggers none (0 exports triggered by the health check)."""
        # Pre-seed a valid status file pointing to the expected dashboard path
        self.status_file.write_text(
            json.dumps({
                "dashboard_path": str(self.dashboard_path.resolve()),
                "updated_at": "2026-09-24T20:00:00Z",
            }),
            encoding="utf-8",
        )

        mock_export = MagicMock(return_value={"status": "ok"})
        stop_event = threading.Event()
        captured_stdout = io.StringIO()

        with patch("scripts.watch_telemetry.export_telemetry", mock_export):
            with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(io.StringIO()):
                t = threading.Thread(
                    target=watch_loop,
                    kwargs={
                        "antigravity_dir": self.antigravity_dir,
                        "dashboard_path": self.dashboard_path,
                        "log_path": self.log_path,
                        "status_path": self.status_file,
                        "refresh_signal_path": self.fake_refresh_signal,
                        "interval_seconds": 0.01,
                        "heartbeat_interval": 0.03,
                        "repair_rate_limit": 60.0,
                        "stop_event": stop_event,
                    },
                    daemon=True,
                )
                t.start()
                # Run through multiple heartbeat ticks
                time.sleep(0.12)
                stop_event.set()
                t.join(timeout=2.0)

        # Only initial export occurs on start; 0 exports triggered by the health check
        self.assertEqual(mock_export.call_count, 1, "Matching status file must trigger 0 health-check exports")
        self.assertNotIn("Foreign status file detected", captured_stdout.getvalue())

    def test_case_5_second_mismatch_within_60s_triggers_none(self):
        """Case 5: A second mismatch within 60 s triggers none (rate limiting prevents repeat export)."""
        foreign_dashboard = self.temp_path / "foreign" / "index.html"
        self.status_file.write_text(
            json.dumps({
                "dashboard_path": str(foreign_dashboard),
                "updated_at": "2026-09-24T20:00:00Z",
            }),
            encoding="utf-8",
        )

        mock_export = MagicMock(return_value={"status": "ok"})
        stop_event = threading.Event()
        captured_stdout = io.StringIO()

        with patch("scripts.watch_telemetry.export_telemetry", mock_export):
            with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(io.StringIO()):
                t = threading.Thread(
                    target=watch_loop,
                    kwargs={
                        "antigravity_dir": self.antigravity_dir,
                        "dashboard_path": self.dashboard_path,
                        "log_path": self.log_path,
                        "status_path": self.status_file,
                        "refresh_signal_path": self.fake_refresh_signal,
                        "interval_seconds": 0.01,
                        "heartbeat_interval": 0.02,
                        "repair_rate_limit": 60.0,
                        "stop_event": stop_event,
                    },
                    daemon=True,
                )
                t.start()
                # Run through ~6 heartbeat ticks
                time.sleep(0.15)
                stop_event.set()
                t.join(timeout=2.0)

        # 1 initial export + 1 self-heal repair export. Subsequent ticks suppressed by 60s rate limit.
        self.assertEqual(mock_export.call_count, 2, "Second mismatch within 60s must NOT trigger another export")
        self.assertEqual(
            captured_stdout.getvalue().count("Refreshing dashboard..."),
            1,
            "Dashboard refresh must only trigger once within rate limit window",
        )


    def test_case_5b_rate_limit_allows_export_after_window_elapses(self):
        """Verify that when the rate limit window elapses, another repair export can be triggered."""
        foreign_dashboard = self.temp_path / "foreign" / "index.html"
        self.status_file.write_text(
            json.dumps({
                "dashboard_path": str(foreign_dashboard),
                "updated_at": "2026-09-24T20:00:00Z",
            }),
            encoding="utf-8",
        )

        mock_export = MagicMock(return_value={"status": "ok"})
        stop_event = threading.Event()

        with patch("scripts.watch_telemetry.export_telemetry", mock_export):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                t = threading.Thread(
                    target=watch_loop,
                    kwargs={
                        "antigravity_dir": self.antigravity_dir,
                        "dashboard_path": self.dashboard_path,
                        "log_path": self.log_path,
                        "status_path": self.status_file,
                        "refresh_signal_path": self.fake_refresh_signal,
                        "interval_seconds": 0.01,
                        "heartbeat_interval": 0.02,
                        "repair_rate_limit": 0.05,  # Short rate-limit to test expiration
                        "stop_event": stop_event,
                    },
                    daemon=True,
                )
                t.start()
                time.sleep(0.15)
                stop_event.set()
                t.join(timeout=2.0)

        # Should have 1 initial export + at least 2 repairs after rate limit expired
        self.assertGreaterEqual(mock_export.call_count, 3)


if __name__ == "__main__":
    unittest.main()
