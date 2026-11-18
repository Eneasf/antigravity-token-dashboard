"""
Unit tests for atomic file writes and temporary staging cleanup.

Validates that:
1. src.log_reader.atomic_write_json uses unique temporary files and os.replace,
   cleaning up staging files upon failure.
2. scripts.build_demo_showcase.atomic_write_text and write_demo_files use
   atomic staging and os.replace, cleaning up staging files upon failure.
3. scripts.export_dashboard.atomic_write_text properly stages and cleans up.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.build_demo_showcase import (
    atomic_write_text as demo_atomic_write_text,
    write_demo_files,
)
from scripts.export_dashboard import atomic_write_text as export_atomic_write_text
from src.log_reader import (
    atomic_write_json,
    load_persistent_ledger,
)


class TestAtomicWrites(unittest.TestCase):
    """Test suite ensuring atomic writes and error cleanup across ledger and demo showcase."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_log_reader_atomic_write_json_success(self):
        """Verify atomic_write_json successfully writes JSON data with directory creation."""
        target_path = self.test_dir / "subdir" / "ledger.json"
        data = {"version": 1, "incidents": [{"id": "test_1", "duration": 120}]}

        atomic_write_json(target_path, data)

        self.assertTrue(target_path.exists())
        loaded = json.loads(target_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded, data)

        # Ensure no dangling temporary files remain
        temp_files = list(target_path.parent.glob(f".{target_path.name}.*.tmp"))
        self.assertEqual(temp_files, [])

    def test_log_reader_atomic_write_json_cleanup_on_replace_failure(self):
        """Verify atomic_write_json removes temporary staging file if os.replace fails."""
        target_path = self.test_dir / "ledger_fail.json"
        data = {"version": 1, "incidents": []}

        with patch("os.replace", side_effect=OSError("Disk full / replace failed")):
            with self.assertRaises(OSError):
                atomic_write_json(target_path, data)

        self.assertFalse(target_path.exists())
        temp_files = list(self.test_dir.glob(f".{target_path.name}.*.tmp"))
        self.assertEqual(temp_files, [], f"Dangling temp file(s) found: {temp_files}")

    def test_demo_showcase_atomic_write_text_success(self):
        """Verify build_demo_showcase.atomic_write_text stages and replaces cleanly."""
        target_path = self.test_dir / "sub" / "data.demo.js"
        content = "window.__DEMO__ = { ok: true };\n"

        demo_atomic_write_text(target_path, content)

        self.assertTrue(target_path.exists())
        self.assertEqual(target_path.read_text(encoding="utf-8"), content)

        temp_files = list(target_path.parent.glob(f".{target_path.name}.*.tmp"))
        self.assertEqual(temp_files, [])

    def test_demo_showcase_atomic_write_text_cleanup_on_failure(self):
        """Verify build_demo_showcase.atomic_write_text unlinks temp file on failure."""
        target_path = self.test_dir / "data_fail.js"
        content = "window.__TEST__ = 1;\n"

        with patch("os.replace", side_effect=OSError("Permission denied")):
            with self.assertRaises(OSError):
                demo_atomic_write_text(target_path, content)

        self.assertFalse(target_path.exists())
        temp_files = list(self.test_dir.glob(f".{target_path.name}.*.tmp"))
        self.assertEqual(temp_files, [], f"Dangling temp file(s) found: {temp_files}")

    def test_write_demo_files_atomic_and_cleanup_on_failure(self):
        """Verify write_demo_files writes turns, data, and meta atomically and cleans up on error."""
        out_data = self.test_dir / "showcase" / "data.demo.js"
        out_meta = self.test_dir / "showcase" / "meta.demo.js"
        out_turns = self.test_dir / "showcase" / "turns.demo.js"

        # Suppress stdout from write_demo_files
        with contextlib.redirect_stdout(io.StringIO()):
            write_demo_files(out_data, out_meta, out_turns)

        self.assertTrue(out_data.exists())
        self.assertTrue(out_meta.exists())
        self.assertTrue(out_turns.exists())

        # No dangling tmp files
        temp_files = list(out_data.parent.glob(".*.tmp"))
        self.assertEqual(temp_files, [])

        # Test error cleanup during write_demo_files
        fail_data = self.test_dir / "fail_showcase" / "data.demo.js"
        with patch("os.replace", side_effect=OSError("Replace simulated failure")):
            with self.assertRaises(OSError):
                with contextlib.redirect_stdout(io.StringIO()):
                    write_demo_files(fail_data)

        # Ensure no orphaned temp files
        fail_temp_files = list(fail_data.parent.glob(".*.tmp"))
        self.assertEqual(fail_temp_files, [], f"Dangling temp files found: {fail_temp_files}")

    def test_export_dashboard_atomic_write_text_cleanup(self):
        """Verify export_dashboard.atomic_write_text cleans up temp files on error."""
        target_path = self.test_dir / "digest.md"
        content = "# Markdown Digest\n"

        with patch("os.replace", side_effect=OSError("Write failure")):
            with self.assertRaises(OSError):
                export_atomic_write_text(target_path, content)

        self.assertFalse(target_path.exists())
        temp_files = list(self.test_dir.glob(f".{target_path.name}.*.tmp"))
        self.assertEqual(temp_files, [])

    def test_load_persistent_ledger_self_healing_atomic(self):
        """Verify load_persistent_ledger self-heals via atomic write when vault contains incidents."""
        # Setup fake vault path
        vault_path = self.test_dir / "antigravity_vault.db"
        vault_path.touch()

        fake_ledger = {
            "version": 1,
            "incidents": [
                {
                    "source": "reconstructed_from_vault",
                    "status": "rate_limited",
                    "start_time": "2026-09-01T10:00:00Z",
                }
            ],
        }

        with patch("src.log_reader.DEFAULT_LEDGER_PATH", self.test_dir / "exhaustion_ledger.json"), \
             patch("src.log_reader.reconstruct_ledger_from_vault", return_value=fake_ledger), \
             patch("os.replace", wraps=os.replace) as mock_replace:
            result = load_persistent_ledger()
            self.assertEqual(result, fake_ledger)
            mock_replace.assert_called_once()
            target_ledger = self.test_dir / "exhaustion_ledger.json"
            self.assertTrue(target_ledger.exists())
            loaded = json.loads(target_ledger.read_text(encoding="utf-8"))
            self.assertEqual(loaded, fake_ledger)


if __name__ == "__main__":
    unittest.main()
