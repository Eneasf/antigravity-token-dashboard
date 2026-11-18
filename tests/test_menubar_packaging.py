#!/usr/bin/env python3
"""
Unit tests for macOS Menu Bar application packaging and lifecycle management.
"""

import contextlib
import io
from pathlib import Path
import plistlib
import tempfile
import unittest

from scripts.build_menubar import check_swift_compiler, assemble_app_bundle
from scripts.setup_menubar import get_running_pids, cmd_status


class TestMenuBarPackaging(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_bin = Path(self.temp_dir.name) / "AntigravityBar"
        self.mock_bin.write_text("#!/bin/sh\necho mock\n", encoding="utf-8")
        self.mock_bin.chmod(0o755)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_swift_compiler_detection(self):
        ver = check_swift_compiler()
        self.assertTrue(len(ver) > 0)
        self.assertIn("Swift", ver)

    def test_assemble_app_bundle(self):
        out_app = Path(self.temp_dir.name) / "TestBar.app"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result_app = assemble_app_bundle(self.mock_bin, output_app=out_app)

        self.assertEqual(result_app, out_app)
        self.assertTrue(out_app.exists())

        bin_in_app = out_app / "Contents" / "MacOS" / "AntigravityBar"
        self.assertTrue(bin_in_app.exists())
        self.assertTrue(bin_in_app.stat().st_mode & 0o111)

        plist_path = out_app / "Contents" / "Info.plist"
        self.assertTrue(plist_path.exists())

        with open(plist_path, "rb") as f:
            plist = plistlib.load(f)

        self.assertEqual(plist["CFBundleExecutable"], "AntigravityBar")
        self.assertEqual(plist["CFBundleIdentifier"], "com.antigravity.menubar")
        self.assertEqual(plist["CFBundlePackageType"], "APPL")
        self.assertTrue(plist["LSUIElement"])
        self.assertTrue(plist["NSHighResolutionCapable"])

    def test_setup_menubar_status_and_pids(self):
        pids = get_running_pids()
        self.assertIsInstance(pids, list)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            exit_code = cmd_status()
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
