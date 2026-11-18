"""Unit test suite for executive quota status hook isolation (ADR-050 / Milestone 50).

Validates:
- Test A (Library isolation): Calling export_telemetry(...) directly without
  status_path and without output_dir does NOT write to DEFAULT_STATUS_PATH.
- Test B (CLI default): Invoking main() without --output-dir and without
  --status-path DOES write to DEFAULT_STATUS_PATH.
- Test C (CLI with output-dir): Invoking main() with --output-dir writes to
  <output_dir>/.antigravity_quota_status.json and does NOT write to DEFAULT_STATUS_PATH.
- Test D (Library with status_path): Calling export_telemetry(..., status_path=explicit_path)
  writes to explicit_path.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.export_dashboard import export_telemetry, main


class TestStatusIsolation(unittest.TestCase):
    """Verify library and CLI status file isolation semantics."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

        self.antigravity_dir = self.temp_path / "antigravity"
        self.conv_dir = self.antigravity_dir / "conversations"
        self.conv_dir.mkdir(parents=True)

        self.dashboard_dir = self.temp_path / "dashboard"
        self.dashboard_dir.mkdir(parents=True)
        self.index_html = self.dashboard_dir / "index.html"
        self.index_html.write_text(
            '<html><head><script id="injected-dashboard-data" type="application/json">{}</script></head><body></body></html>',
            encoding="utf-8",
        )

        self.empty_log = self.temp_path / "language_server.log"
        self.empty_log.write_text("", encoding="utf-8")

        self.fake_default_status_path = self.temp_path / "fake_home" / ".antigravity_quota_status.json"
        self.fake_default_status_path.parent.mkdir(parents=True, exist_ok=True)

        # Patch DEFAULT_STATUS_PATH to a safe temporary location
        self.patcher = patch("scripts.export_dashboard.DEFAULT_STATUS_PATH", self.fake_default_status_path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_a_library_isolation(self):
        """Test A (Library isolation): Calling export_telemetry(...) directly without

        status_path and without output_dir does NOT write to DEFAULT_STATUS_PATH.
        """
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload = export_telemetry(
                antigravity_dir=self.antigravity_dir,
                dashboard_path=self.index_html,
                log_path=self.empty_log,
                no_live_quota=True,
            )

        self.assertIn("summary", payload)
        self.assertFalse(
            self.fake_default_status_path.exists(),
            "Library call without status_path and without output_dir must NOT write to DEFAULT_STATUS_PATH",
        )
        self.assertFalse(
            (self.dashboard_dir / ".antigravity_quota_status.json").exists(),
            "Library call without output_dir must NOT write to dashboard_dir status file",
        )

    def test_b_cli_default(self):
        """Test B (CLI default): Invoking main() without --output-dir and without

        --status-path DOES write to DEFAULT_STATUS_PATH.
        """
        cli_args = [
            "export_dashboard.py",
            "--antigravity-dir",
            str(self.antigravity_dir),
            "--dashboard-path",
            str(self.index_html),
            "--log-path",
            str(self.empty_log),
            "--no-live-quota",
        ]

        with patch("sys.argv", cli_args), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            main()

        self.assertTrue(
            self.fake_default_status_path.exists(),
            "CLI invocation without --output-dir and without --status-path must write to DEFAULT_STATUS_PATH",
        )
        status_data = json.loads(self.fake_default_status_path.read_text(encoding="utf-8"))
        self.assertIn("status", status_data)
        self.assertIn("gemini_5h_pct", status_data)

    def test_c_cli_with_output_dir(self):
        """Test C (CLI with output-dir): Invoking main() with --output-dir writes to

        <output_dir>/.antigravity_quota_status.json and does NOT write to DEFAULT_STATUS_PATH.
        """
        custom_output = self.temp_path / "custom_output"
        custom_output.mkdir(parents=True, exist_ok=True)

        cli_args = [
            "export_dashboard.py",
            "--antigravity-dir",
            str(self.antigravity_dir),
            "--output-dir",
            str(custom_output),
            "--log-path",
            str(self.empty_log),
            "--no-live-quota",
        ]

        with patch("sys.argv", cli_args), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            main()

        expected_status_file = custom_output / ".antigravity_quota_status.json"
        self.assertTrue(
            expected_status_file.exists(),
            "CLI invocation with --output-dir must write to <output_dir>/.antigravity_quota_status.json",
        )
        self.assertFalse(
            self.fake_default_status_path.exists(),
            "CLI invocation with --output-dir must NOT write to DEFAULT_STATUS_PATH",
        )

        status_data = json.loads(expected_status_file.read_text(encoding="utf-8"))
        self.assertIn("status", status_data)

    def test_d_library_with_status_path(self):
        """Test D (Library with status_path): Calling export_telemetry(..., status_path=explicit_path)

        writes to explicit_path and does NOT write to DEFAULT_STATUS_PATH.
        """
        explicit_status_path = self.temp_path / "explicit_status.json"

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload = export_telemetry(
                antigravity_dir=self.antigravity_dir,
                dashboard_path=self.index_html,
                log_path=self.empty_log,
                no_live_quota=True,
                status_path=explicit_status_path,
            )

        self.assertIn("summary", payload)
        self.assertTrue(
            explicit_status_path.exists(),
            "Calling export_telemetry with explicit status_path must write to that path",
        )
        self.assertFalse(
            self.fake_default_status_path.exists(),
            "Calling export_telemetry with explicit status_path must NOT write to DEFAULT_STATUS_PATH",
        )

        status_data = json.loads(explicit_status_path.read_text(encoding="utf-8"))
        self.assertIn("status", status_data)


if __name__ == "__main__":
    unittest.main()
