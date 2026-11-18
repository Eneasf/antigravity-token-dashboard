"""Unit tests for vault sync mtime gating (Milestone M67 / Finding C1 & Owner Decision 1).

Adheres strictly to Host Isolation & Safety Invariants (Rule AC-4):
- Uses temporary scratch directories for antigravity_dir and vault_path.
- Never touches ~/.gemini/antigravity/ or data/antigravity_vault.db.
- Cleans up temporary resources in tearDown.
"""

import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import List, Optional, Tuple
import unittest

from src.vault import sync_conversations_to_vault


class TestVaultMtimeGating(unittest.TestCase):
    """Test suite for mtime-gated incremental conversation sync in src/vault.py."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.vault_path = self.temp_path / "test_vault.db"
        self.antigravity_dir = self.temp_path / "antigravity"
        self.conv_dir = self.antigravity_dir / "conversations"
        self.conv_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_mock_convo_db(
        self,
        convo_id: str,
        steps: Optional[List[Tuple]] = None,
        mtime: Optional[float] = None,
    ) -> Path:
        """Helper to create a valid minimal mock upstream conversation SQLite DB."""
        if steps is None:
            steps = [
                (0, 14, 1, None, None, b"\x9a\x01\x04test"),
                (1, 15, 1, None, None, b"\x9a\x01\x04resp"),
            ]
        db_path = self.conv_dir / f"{convo_id}.db"
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE steps (
                idx INTEGER PRIMARY KEY,
                step_type INTEGER,
                status INTEGER,
                has_subtrajectory INTEGER,
                metadata BLOB,
                error_details BLOB,
                permissions BLOB,
                task_details BLOB,
                render_info BLOB,
                step_payload BLOB,
                step_format INTEGER
            )
            """
        )
        for row in steps:
            cur.execute(
                """
                INSERT INTO steps (
                    idx, step_type, status, has_subtrajectory,
                    metadata, error_details, permissions,
                    task_details, render_info, step_payload, step_format
                ) VALUES (?, ?, ?, 0, ?, ?, NULL, NULL, NULL, ?, 0)
                """,
                row,
            )
        conn.commit()
        conn.close()

        if mtime is not None:
            os.utime(str(db_path), (mtime, mtime))

        return db_path

    def test_sync_records_last_sync_mtime(self):
        """Verify sync_conversations_to_vault records conversations_last_sync_mtime in vault_sync_state."""
        convo_id = "11111111-aaaa-bbbb-cccc-000000000001"
        self._create_mock_convo_db(convo_id)

        stats = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )
        self.assertGreaterEqual(stats.get("discovered_databases", 0), 1)

        # Inspect vault_sync_state in isolated test vault
        conn = sqlite3.connect(f"file:{self.vault_path}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("SELECT value FROM vault_sync_state WHERE key = 'conversations_last_sync_mtime'")
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row, "conversations_last_sync_mtime key not found in vault_sync_state table")
        try:
            mtime_val = float(row[0])
        except (ValueError, TypeError) as exc:
            self.fail(f"conversations_last_sync_mtime is not a valid float: {row[0]!r}, error: {exc}")

        self.assertGreater(mtime_val, 0.0)

    def test_mtime_gating_skips_unchanged_dbs(self):
        """Verify repeated sync without modifying DBs skips all databases (scanned_databases == 0)."""
        convo_id = "22222222-aaaa-bbbb-cccc-000000000002"
        self._create_mock_convo_db(convo_id)

        # 1. Initial sync scans the DB
        stats1 = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )
        self.assertEqual(stats1.get("discovered_databases"), 1)
        self.assertEqual(stats1.get("scanned_databases"), 1)
        self.assertEqual(stats1.get("conversations_synced"), 1)

        # 2. Second sync without changing DB mtime should skip inspection
        t0 = time.time()
        stats2 = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )
        duration = time.time() - t0

        self.assertEqual(stats2.get("discovered_databases"), 1)
        self.assertEqual(
            stats2.get("scanned_databases"),
            0,
            f"Expected 0 scanned databases on unchanged DB, got {stats2.get('scanned_databases')}",
        )
        self.assertEqual(stats2.get("conversations_synced"), 0)
        self.assertLess(duration, 2.0, f"Second sync should execute rapidly, took {duration:.3f}s")

    def test_mtime_gating_picks_up_modified_db(self):
        """Verify mtime gating detects and scans only databases with updated mtime."""
        db1_path = self._create_mock_convo_db("33333333-aaaa-bbbb-cccc-000000000003")
        db2_path = self._create_mock_convo_db("44444444-aaaa-bbbb-cccc-000000000004")

        # Initial sync: both are new, both scanned
        stats1 = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )
        self.assertEqual(stats1.get("discovered_databases"), 2)
        self.assertEqual(stats1.get("scanned_databases"), 2)

        # Bump mtime of db1 into the future to simulate an upstream conversation turn update
        future_ts = time.time() + 300.0
        os.utime(str(db1_path), (future_ts, future_ts))

        # Re-run sync: only db1 should be scanned, db2 must be skipped
        stats2 = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )
        self.assertEqual(stats2.get("discovered_databases"), 2)
        self.assertEqual(
            stats2.get("scanned_databases"),
            1,
            f"Expected exactly 1 scanned database for updated db1, got {stats2.get('scanned_databases')}",
        )

    def test_force_full_scan_flag(self):
        """Verify force=True bypasses mtime gating and unconditionally scans all discovered databases."""
        self._create_mock_convo_db("55555555-aaaa-bbbb-cccc-000000000005")
        self._create_mock_convo_db("66666666-aaaa-bbbb-cccc-000000000006")

        # Initial sync
        stats1 = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )
        self.assertEqual(stats1.get("discovered_databases"), 2)
        self.assertEqual(stats1.get("scanned_databases"), 2)

        # Gated sync: 0 scanned
        stats2 = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
            force=False,
        )
        self.assertEqual(stats2.get("scanned_databases"), 0)

        # Forced sync: scans all discovered databases regardless of mtime
        stats3 = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
            force=True,
        )
        self.assertEqual(
            stats3.get("scanned_databases"),
            stats3.get("discovered_databases"),
            "force=True must scan all discovered databases",
        )
        self.assertEqual(stats3.get("scanned_databases"), 2)

    def test_export_dashboard_build_parser_has_force_full_scan(self):
        """Verify build_parser in scripts.export_dashboard defines --force-full-scan."""
        from scripts.export_dashboard import build_parser

        parser = build_parser()
        actions = parser._actions
        action_dests = [a.dest for a in actions]
        self.assertIn(
            "force_full_scan",
            action_dests,
            "Action dest 'force_full_scan' missing from scripts.export_dashboard.build_parser()",
        )

        option_strings = [opt for a in actions for opt in getattr(a, "option_strings", [])]
        self.assertIn(
            "--force-full-scan",
            option_strings,
            "CLI option string '--force-full-scan' missing from scripts.export_dashboard.build_parser()",
        )

    def test_sync_stats_keys(self):
        """Verify returned stats dict always contains discovered_databases and scanned_databases integer keys."""
        self._create_mock_convo_db("77777777-aaaa-bbbb-cccc-000000000007")

        stats = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )
        self.assertIn("discovered_databases", stats)
        self.assertIn("scanned_databases", stats)
        self.assertIsInstance(stats["discovered_databases"], int)
        self.assertIsInstance(stats["scanned_databases"], int)
        self.assertGreaterEqual(stats["discovered_databases"], 1)
        self.assertGreaterEqual(stats["scanned_databases"], 1)

    def test_boundary_empty_conversations_directory(self):
        """Boundary test: 0 conversations present yields 0 discovered and 0 scanned without errors."""
        stats = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )
        self.assertEqual(stats.get("discovered_databases"), 0)
        self.assertEqual(stats.get("scanned_databases"), 0)
        self.assertEqual(stats.get("conversations_synced"), 0)
        self.assertEqual(stats.get("steps_synced"), 0)


if __name__ == "__main__":
    unittest.main()
