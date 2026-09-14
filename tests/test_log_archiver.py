"""
Unit tests for src/log_archiver.py (Milestone M08 / ADR-018).
"""

from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.log_archiver import (
    DEFAULT_LOG_PATH,
    DEFAULT_VAULT_PATH,
    EVENT_ERROR,
    EVENT_LIFECYCLE,
    EVENT_RESOURCE_EXHAUSTED,
    LogArchiver,
    archive_logs,
    classify_event,
    compute_event_fingerprint,
    parse_timestamp,
)


class TestLogArchiver(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.log_path = Path(self.temp_dir.name) / "test_language_server.log"
        self.vault_path = Path(self.temp_dir.name) / "test_vault.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_paths(self):
        archiver = LogArchiver()
        self.assertEqual(archiver.log_path, DEFAULT_LOG_PATH)
        self.assertEqual(archiver.vault_path, DEFAULT_VAULT_PATH)
        self.assertEqual(archiver.file_offset, 0)
        self.assertEqual(archiver.last_size, 0)
        self.assertIsNone(archiver.last_inode)

    def test_classify_event_types(self):
        # 429 RESOURCE_EXHAUSTED
        line_429 = "ERROR: logging before google.Init: I0905 13:35:13.877653    8813 run.go:371] Run: attempt 1 failed (RESOURCE_EXHAUSTED (code 429): You have exhausted your capacity on this model. Your quota will reset after 0s.), retrying in 1s"
        self.assertEqual(classify_event(line_429), EVENT_RESOURCE_EXHAUSTED)

        # Lifecycle events
        line_startup = "ERROR: logging before google.Init: I0905 13:31:27.557147       1 server.go:1487] Starting language server process"
        self.assertEqual(classify_event(line_startup), EVENT_LIFECYCLE)

        line_shutdown = "2026-09-06T10:00:00Z Shutting down language server"
        self.assertEqual(classify_event(line_shutdown), EVENT_LIFECYCLE)

        # Error events
        line_err = "ERROR: logging before google.Init: E0905 14:18:17.687126   56476 worker.go:100] Something failed badly"
        self.assertEqual(classify_event(line_err), EVENT_ERROR)

        line_exc = "Exception in thread 'worker': Out of memory"
        self.assertEqual(classify_event(line_exc), EVENT_ERROR)

        # Normal logs (should be None)
        line_info = "ERROR: logging before google.Init: I0905 16:00:00.123456   12345 http_helpers.go:246] Normal request"
        self.assertIsNone(classify_event(line_info))

    def test_deterministic_fingerprint(self):
        ts_iso = "2026-09-05T13:35:13.877653+00:00"
        line = "ERROR: logging before google.Init: I0905 13:35:13.877653    8813 run.go:371] RESOURCE_EXHAUSTED (code 429)"
        expected = hashlib.sha256(f"{ts_iso}:{line.strip()}".encode("utf-8")).hexdigest()
        self.assertEqual(compute_event_fingerprint(ts_iso, line), expected)

    def test_poll_non_existent_file(self):
        archiver = LogArchiver(log_path=self.log_path, vault_path=self.vault_path)
        self.assertEqual(archiver.poll(), 0)

    def test_poll_and_archive_events(self):
        sample_log = (
            "ERROR: logging before google.Init: I0905 13:31:27.557147       1 server.go:1487] Starting language server process\n"
            "ERROR: logging before google.Init: I0905 13:35:10.000000   10375 http_helpers.go:246] URL: https://daily-cloudcode-pa.googleapis.com\n"
            "ERROR: logging before google.Init: I0905 13:35:13.877653    8813 run.go:371] Run: attempt 1 failed (RESOURCE_EXHAUSTED (code 429): You have exhausted your capacity on this model. Your quota will reset after 0s.), retrying in 1s\n"
            "ERROR: logging before google.Init: E0905 14:18:17.687126   56476 worker.go:100] Failed to sync session\n"
            "ERROR: logging before google.Init: I0905 16:00:00.123456   12345 http_helpers.go:246] Normal request\n"
        )
        self.log_path.write_text(sample_log, encoding="utf-8")

        archiver = LogArchiver(log_path=self.log_path, vault_path=self.vault_path, default_year=2026)
        inserted = archiver.poll()
        # 3 events: 1 lifecycle, 1 429 exhaustion, 1 error (2 normal info lines ignored)
        self.assertEqual(inserted, 3)
        self.assertGreater(archiver.file_offset, 0)

        # Polling again with no file changes should return 0
        self.assertEqual(archiver.poll(), 0)

        # Verify vaulted records
        events = archiver.get_archived_events()
        self.assertEqual(len(events), 3)
        types = [e["event_type"] for e in events]
        self.assertIn(EVENT_LIFECYCLE, types)
        self.assertIn(EVENT_RESOURCE_EXHAUSTED, types)
        self.assertIn(EVENT_ERROR, types)

    def test_incremental_appending(self):
        initial_log = "ERROR: logging before google.Init: I0905 13:31:27.557147       1 server.go:1487] Starting language server process\n"
        self.log_path.write_text(initial_log, encoding="utf-8")

        archiver = LogArchiver(log_path=self.log_path, vault_path=self.vault_path, default_year=2026)
        self.assertEqual(archiver.poll(), 1)
        offset_after_1 = archiver.file_offset

        # Append new event
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write("ERROR: logging before google.Init: I0905 13:35:13.877653    8813 run.go:371] RESOURCE_EXHAUSTED (code 429)\n")

        self.assertEqual(archiver.poll(), 1)
        self.assertGreater(archiver.file_offset, offset_after_1)

        # Total in vault is 2
        events = archiver.get_archived_events()
        self.assertEqual(len(events), 2)

    def test_truncation_detection_and_deduplication(self):
        # Write large log file
        long_log = (
            "ERROR: logging before google.Init: I0905 10:00:00.000000       1 server.go:100] Starting language server process\n"
            "ERROR: logging before google.Init: I0905 10:05:00.000000    1000 run.go:371] RESOURCE_EXHAUSTED (code 429)\n"
            "ERROR: logging before google.Init: I0905 10:10:00.000000    1000 run.go:371] Long text padding line filler AAAAA\n"
            "ERROR: logging before google.Init: I0905 10:15:00.000000    1000 run.go:371] Long text padding line filler BBBBB\n"
        )
        self.log_path.write_text(long_log, encoding="utf-8")

        archiver = LogArchiver(log_path=self.log_path, vault_path=self.vault_path, default_year=2026)
        self.assertEqual(archiver.poll(), 2)
        old_offset = archiver.file_offset

        # Truncate file (simulate log rotation or IDE restart writing shorter file)
        # Note: contains the same starting event plus 1 brand new event
        truncated_log = (
            "ERROR: logging before google.Init: I0905 10:00:00.000000       1 server.go:100] Starting language server process\n"
            "ERROR: logging before google.Init: I0905 11:00:00.000000    2000 run.go:371] RESOURCE_EXHAUSTED (code 429): Brand new event\n"
        )
        self.assertTrue(len(truncated_log.encode("utf-8")) < old_offset)
        self.log_path.write_text(truncated_log, encoding="utf-8")

        # poll should detect truncation, reset file_offset to 0, ignore the existing event, and insert only the new event
        inserted = archiver.poll()
        self.assertEqual(inserted, 1)

        # Total events in vault should be 3: initial 2 plus the 1 new event (0 duplicates)
        events = archiver.get_archived_events()
        self.assertEqual(len(events), 3)

    def test_inode_change_detection(self):
        # First file
        log1 = "ERROR: logging before google.Init: I0905 10:00:00.000000       1 server.go:100] Starting language server process\n"
        self.log_path.write_text(log1, encoding="utf-8")

        archiver = LogArchiver(log_path=self.log_path, vault_path=self.vault_path, default_year=2026)
        self.assertEqual(archiver.poll(), 1)

        # Unlink and recreate file with new inode
        self.log_path.unlink()
        log2 = (
            "ERROR: logging before google.Init: I0905 10:00:00.000000       1 server.go:100] Starting language server process\n"
            "ERROR: logging before google.Init: E0905 12:00:00.000000    3000 server.go:200] Fatal crash\n"
        )
        self.log_path.write_text(log2, encoding="utf-8")

        # poll should detect inode change, reset offset, and archive only the new event
        inserted = archiver.poll()
        self.assertEqual(inserted, 1)

        events = archiver.get_archived_events()
        self.assertEqual(len(events), 2)

    def test_archive_logs_helper(self):
        sample_log = "ERROR: logging before google.Init: I0905 13:35:13.877653    8813 run.go:371] RESOURCE_EXHAUSTED (code 429)\n"
        self.log_path.write_text(sample_log, encoding="utf-8")

        count = archive_logs(log_path=self.log_path, vault_path=self.vault_path)
        self.assertEqual(count, 1)

        # Second call does not duplicate
        count2 = archive_logs(log_path=self.log_path, vault_path=self.vault_path)
        self.assertEqual(count2, 0)


if __name__ == "__main__":
    unittest.main()
