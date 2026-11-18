"""
Unit tests for Antigravity log reader and 429 exhaustion parser.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
import warnings
from unittest import mock

from src.log_reader import (
    extract_exhaustion_intervals,
    extract_raw_exhaustion_events,
    get_latest_exhaustion_event_utc,
    parse_glog_timestamp,
    reconstruct_ledger_from_vault,
)


class TestLogReader(unittest.TestCase):
    def test_parse_glog_timestamp_success(self):
        line = "ERROR: logging before google.Init: I0905 13:35:13.877653    8813 run.go:371] Run: attempt 1 failed"
        dt = parse_glog_timestamp(line, year=2026)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 9)
        self.assertEqual(dt.day, 5)
        self.assertEqual(dt.hour, 13)
        self.assertEqual(dt.minute, 35)
        self.assertEqual(dt.second, 13)
        self.assertEqual(dt.microsecond, 877653)
        self.assertEqual(dt.tzinfo, timezone.utc)

    def test_parse_glog_timestamp_local_tz_conversion(self):
        """Verify parse_glog_timestamp converts local wall-clock glog time (e.g. BST +01:00) to UTC."""
        line = "E1013 22:05:46.392701 38451 interceptor.go:74] RESOURCE_EXHAUSTED (code 429)"
        bst = timezone(timedelta(hours=1))
        dt_utc = parse_glog_timestamp(line, year=2026, local_tz=bst)
        self.assertIsNotNone(dt_utc)
        self.assertEqual(dt_utc.hour, 21)
        self.assertEqual(dt_utc.minute, 5)
        self.assertEqual(dt_utc.second, 46)
        self.assertEqual(dt_utc.tzinfo, timezone.utc)

    def test_get_latest_exhaustion_event_utc_tail_scan(self):
        """Verify get_latest_exhaustion_event_utc tail-scans log file and extracts latest 429 timestamp."""
        sample_log = (
            "I1013 20:00:00.000000 100 run.go:1] RESOURCE_EXHAUSTED (code 429)\n"
            "I1013 21:05:46.392701 101 run.go:1] RESOURCE_EXHAUSTED (code 429)\n"
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(sample_log)
            temp_path = Path(f.name)
        try:
            ts = get_latest_exhaustion_event_utc(temp_path, local_tz=timezone.utc)
            self.assertIsNotNone(ts)
            self.assertEqual(ts.hour, 21)
            self.assertEqual(ts.minute, 5)
            self.assertEqual(ts.second, 46)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_parse_glog_timestamp_invalid(self):
        self.assertIsNone(parse_glog_timestamp("Some random unformatted line", year=2026))
        self.assertIsNone(parse_glog_timestamp("", year=2026))

    def test_extract_from_mock_log(self):
        sample_log = """
ERROR: logging before google.Init: I0905 13:31:27.557147       1 server.go:1487] Starting language server process
ERROR: logging before google.Init: I0905 13:35:10.000000   10375 http_helpers.go:246] URL: https://daily-cloudcode-pa.googleapis.com
ERROR: logging before google.Init: I0905 13:35:13.877653    8813 run.go:371] Run: attempt 1 failed (RESOURCE_EXHAUSTED (code 429): You have exhausted your capacity on this model. Your quota will reset after 0s.), retrying in 1s
ERROR: logging before google.Init: I0905 14:18:17.687126   56476 run.go:371] Run: attempt 1 failed (RESOURCE_EXHAUSTED (code 429): You have exhausted your capacity on this model. Your quota will reset after 0s.), retrying in 1s
ERROR: logging before google.Init: I0905 16:00:00.123456   12345 http_helpers.go:246] Normal request
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(sample_log)
            temp_path = Path(f.name)

        try:
            events = extract_raw_exhaustion_events(temp_path)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["line_no"], 4)
            self.assertEqual(events[1]["line_no"], 5)

            intervals = extract_exhaustion_intervals(temp_path, ledger_path=False, cluster_gap_minutes=60.0)
            self.assertEqual(len(intervals), 1)
            self.assertEqual(intervals[0]["events_count"], 2)
            self.assertEqual(intervals[0]["code"], 429)
            self.assertEqual(intervals[0]["reason"], "RESOURCE_EXHAUSTED")
            self.assertTrue("13:35:13" in intervals[0]["first_exhaustion_ts"])
            self.assertTrue("14:18:17" in intervals[0]["last_exhaustion_ts"])
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_extract_discrete_clusters(self):
        sample_log = """
ERROR: logging before google.Init: I0905 10:00:00.000000    1000 run.go:371] RESOURCE_EXHAUSTED (code 429)
ERROR: logging before google.Init: I0905 10:15:00.000000    1001 run.go:371] RESOURCE_EXHAUSTED (code 429)
ERROR: logging before google.Init: I0905 14:00:00.000000    2000 run.go:371] RESOURCE_EXHAUSTED (code 429)
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write(sample_log)
            temp_path = Path(f.name)

        try:
            intervals = extract_exhaustion_intervals(temp_path, ledger_path=False, cluster_gap_minutes=30.0)
            self.assertEqual(len(intervals), 2)
            self.assertEqual(intervals[0]["events_count"], 2)
            self.assertEqual(intervals[1]["events_count"], 1)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_missing_or_empty_file(self):
        non_existent = Path("/tmp/non_existent_antigravity_log_file_12345.log")
        self.assertEqual(extract_raw_exhaustion_events(non_existent), [])
        self.assertEqual(extract_exhaustion_intervals(non_existent, ledger_path=False), [])

    def test_extract_with_persistent_ledger(self):
        # When log file is missing or empty, ledger incidents from ledger_path are still returned
        non_existent = Path("/tmp/non_existent_antigravity_log_file_12345.log")
        sample_ledger = Path(__file__).resolve().parent.parent / "data" / "exhaustion_ledger.sample.json"
        intervals = extract_exhaustion_intervals(non_existent, ledger_path=sample_ledger)
        self.assertGreaterEqual(len(intervals), 1)
        self.assertTrue(intervals[0]["from_ledger"])
        self.assertEqual(intervals[0]["code"], 429)


class TestReconstructLedgerFromVaultConnectionHardening(unittest.TestCase):
    """Regression test suite for reconstruct_ledger_from_vault connection hardening (C3)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.vault_path = self.temp_path / "antigravity_vault.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_reconstruct_ledger_closes_connection_on_exception(self):
        conn = sqlite3.connect(self.vault_path)
        conn.execute("CREATE TABLE log_events_archive (idx INTEGER)")
        conn.commit()
        conn.close()

        closed = []
        orig_connect = sqlite3.connect

        class CW:
            def __init__(self, c):
                self._c = c
            def __getattr__(self, name):
                return getattr(self._c, name)
            def execute(self, sql, *args):
                return self._c.execute(sql, *args)
            def close(self):
                closed.append(True)
                return self._c.close()

        with mock.patch("sqlite3.connect", side_effect=lambda *a, **k: CW(orig_connect(*a, **k))):
            res = reconstruct_ledger_from_vault(self.vault_path)
            self.assertEqual(res, {"version": 1, "incidents": []})
            self.assertEqual(len(closed), 1)

    def test_reconstruct_ledger_early_return_and_concurrency(self):
        conn = sqlite3.connect(self.vault_path)
        conn.execute("CREATE TABLE other_table (idx INTEGER)")
        conn.commit()
        conn.close()

        closed = []
        timeouts = []
        pragmas = []
        orig_connect = sqlite3.connect

        class CW:
            def __init__(self, c):
                self._c = c
            def __getattr__(self, name):
                return getattr(self._c, name)
            def execute(self, sql, *args):
                pragmas.append(sql)
                return self._c.execute(sql, *args)
            def close(self):
                closed.append(True)
                return self._c.close()

        def spy(*a, **k):
            timeouts.append(k.get("timeout"))
            return CW(orig_connect(*a, **k))

        with mock.patch("sqlite3.connect", side_effect=spy):
            res = reconstruct_ledger_from_vault(self.vault_path)
            self.assertEqual(res, {"version": 1, "incidents": []})
            self.assertEqual(len(closed), 1)
            self.assertEqual(timeouts, [60.0])
            self.assertTrue(any("busy_timeout = 60000" in p for p in pragmas))

    def test_reconstruct_ledger_resource_warning_hygiene(self):
        conn = sqlite3.connect(self.vault_path)
        conn.execute(
            """
            CREATE TABLE log_events_archive (
                event_fingerprint TEXT,
                timestamp TEXT,
                raw_line TEXT,
                code INTEGER,
                reason TEXT,
                event_type TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO log_events_archive VALUES (
                'fp1', '2026-09-29T10:00:00Z', '-500 credits (29 Sep 2026, 10:00 UTC)', 429, 'RESOURCE_EXHAUSTED', 'STATEMENT_RECONCILIATION'
            )
            """
        )
        conn.commit()
        conn.close()

        with warnings.catch_warnings():
            warnings.simplefilter("error", ResourceWarning)
            res = reconstruct_ledger_from_vault(self.vault_path)
            self.assertEqual(len(res["incidents"]), 1)


if __name__ == "__main__":
    unittest.main()
