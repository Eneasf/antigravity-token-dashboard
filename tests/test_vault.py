"""Unit tests for src/vault.py (Milestone M08 / ADR-018)."""

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import urllib.parse

from src.vault import (
    DEFAULT_VAULT_PATH,
    get_vault_connection,
    init_vault,
    parse_agyhub_summaries,
    sync_conversations_to_vault,
    sync_log_events_to_vault,
)


class TestVault(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.vault_path = self.temp_path / "test_vault.db"
        self.antigravity_dir = self.temp_path / "antigravity"
        self.conv_dir = self.antigravity_dir / "conversations"
        self.conv_dir.mkdir(parents=True)
        self.log_path = self.temp_path / "language_server.log"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_vault_schema_and_idempotence(self):
        conn = init_vault(self.vault_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        required = {
            "conversations_archive",
            "steps_archive",
            "tool_calls_archive",
            "skills_archive",
            "log_events_archive",
            "vault_sync_state",
        }
        self.assertTrue(required.issubset(tables))

        # Idempotence: Calling init_vault again must succeed cleanly
        conn2 = init_vault(self.vault_path)
        cur2 = conn2.cursor()
        cur2.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        self.assertGreater(cur2.fetchone()[0], 0)
        conn.close()
        conn2.close()

    def test_hybrid_storage_types_and_no_pickle(self):
        conn = init_vault(self.vault_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(steps_archive)")
        cols = {r[1]: r[2] for r in cur.fetchall()}
        self.assertEqual(cols.get("payload_text"), "TEXT")
        self.assertEqual(cols.get("tool_calls_json"), "TEXT")
        self.assertEqual(cols.get("error_text"), "TEXT")
        self.assertEqual(cols.get("raw_metadata_blob"), "BLOB")
        self.assertEqual(cols.get("raw_step_payload_blob"), "BLOB")
        self.assertEqual(cols.get("raw_error_details_blob"), "BLOB")
        conn.close()

    def test_get_vault_connection_pragmas(self):
        conn = get_vault_connection(self.vault_path)
        cur = conn.cursor()
        cur.execute("PRAGMA busy_timeout")
        row = cur.fetchone()
        self.assertEqual(row[0], 5000)
        conn.close()

    def _create_mock_convo_db(self, convo_id: str, steps: list) -> Path:
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
                INSERT INTO steps (idx, step_type, status, has_subtrajectory, metadata, error_details, permissions, task_details, render_info, step_payload, step_format)
                VALUES (?, ?, ?, 0, ?, ?, NULL, NULL, NULL, ?, 0)
                """,
                row,
            )
        conn.commit()
        conn.close()
        return db_path

    def test_high_watermark_incremental_sync(self):
        # 1. Create upstream conversation with 2 steps
        convo_id = "11111111-2222-3333-4444-555555555555"
        self._create_mock_convo_db(
            convo_id,
            [
                (0, 14, 1, None, None, b"\x9a\x01\x04test"),
                (1, 15, 1, None, None, b"\x9a\x01\x04resp"),
            ],
        )

        # Initial sync
        stats1 = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )
        self.assertEqual(stats1["conversations_synced"], 1)
        self.assertEqual(stats1["steps_synced"], 2)
        self.assertEqual(stats1["discovered_databases"], 1)
        self.assertEqual(stats1["scanned_databases"], 1)

        # 2. Second sync with no changes should sync 0 new steps
        stats2 = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )
        self.assertEqual(stats2["conversations_synced"], 0)
        self.assertEqual(stats2["steps_synced"], 0)

        # 3. Append 1 new step upstream
        db_path = self.conv_dir / f"{convo_id}.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO steps (idx, step_type, status, has_subtrajectory, metadata, error_details, permissions, task_details, render_info, step_payload, step_format) VALUES (2, 15, 1, 0, NULL, NULL, NULL, NULL, NULL, ?, 0)",
            (b"\x9a\x01\x04more",),
        )
        conn.commit()
        conn.close()

        # Incremental sync should only sync step 2
        stats3 = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )
        self.assertEqual(stats3["conversations_synced"], 1)
        self.assertEqual(stats3["steps_synced"], 1)

    def test_subagent_lineage_resolution(self):
        parent_id = "b596cf7f-af76-4966-8a8b-f90a0d1c6229"
        child_id = "68481b2d-f75d-47b3-b4ca-5d3a8f5de035"

        # Parent conversation contains invoke_subagent tool call mentioning child_id
        # Step payload simulating tool invoke
        tool_payload = b"\n" + f'invoke_subagent subagent_id="{child_id}"'.encode("utf-8")
        self._create_mock_convo_db(
            parent_id,
            [(0, 15, 1, None, None, tool_payload)],
        )

        # Child conversation contains incoming sender reference to parent_id
        child_payload = f"[Message] sender={parent_id} content=Hello child".encode("utf-8")
        self._create_mock_convo_db(
            child_id,
            [(0, 14, 1, None, None, child_payload)],
        )

        sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )

        conn = get_vault_connection(self.vault_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT parent_convo_id FROM conversations_archive WHERE convo_id = ?",
            (child_id,),
        )
        res = cur.fetchone()
        self.assertIsNotNone(res)
        self.assertEqual(res[0], parent_id)
        conn.close()

    def test_workspace_attribution_unquoting(self):
        convo_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        self._create_mock_convo_db(convo_id, [(0, 14, 1, None, None, b"prompt")])

        # Create mock agyhub_summaries_proto.pb
        raw_uri = "file:///Users/test/Documents/Token%20consumption%20per%20model"
        pb_content = convo_id.encode("utf-8") + b" dummy " + raw_uri.encode("utf-8") + b"\x00"
        (self.antigravity_dir / "agyhub_summaries_proto.pb").write_bytes(pb_content)

        sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )

        conn = get_vault_connection(self.vault_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT workspace_name, workspace_path FROM conversations_archive WHERE convo_id = ?",
            (convo_id,),
        )
        res = cur.fetchone()
        self.assertIsNotNone(res)
        self.assertIn("Token consumption", res[0])
        self.assertEqual(res[1], "/Users/test/Documents/Token consumption per model")
        conn.close()

    def test_log_truncation_detection(self):
        # 1. Write initial log lines including 429 exhaustion and lifecycle
        line1 = "I0906 10:00:00.123456 1234 server.go:10] Server started listening on port 8080\n"
        line2 = "E0906 10:00:01.654321 1234 client.go:42] RESOURCE_EXHAUSTED: code 429 capacity exceeded\n"
        line3 = "I0906 10:00:02.111222 1234 server.go:50] Processing completed\n"
        self.log_path.write_text(line1 + line2 + line3, encoding="utf-8")

        # First sync
        res1 = sync_log_events_to_vault(log_path=self.log_path, vault_path=self.vault_path)
        self.assertFalse(res1["truncated"])
        self.assertEqual(res1["events_synced"], 3)
        self.assertGreater(res1["offset"], 0)

        # Verify items in archive
        conn = get_vault_connection(self.vault_path)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM log_events_archive")
        self.assertEqual(cur.fetchone()[0], 3)
        cur.execute("SELECT event_type, code FROM log_events_archive WHERE code = 429")
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "RESOURCE_EXHAUSTED")
        self.assertEqual(row[1], 429)
        conn.close()

        # 2. Simulate file truncation on IDE restart (file becomes shorter)
        truncated_line = "I0906 11:00:00.000001 5678 server.go:10] Server restarting after clean shutdown\n"
        self.log_path.write_text(truncated_line, encoding="utf-8")

        # Second sync detects truncation
        res2 = sync_log_events_to_vault(log_path=self.log_path, vault_path=self.vault_path)
        self.assertTrue(res2["truncated"])
        self.assertEqual(res2["events_synced"], 1)

        # Total events should now be 4 (3 original + 1 new), with 0 duplicates
        conn = get_vault_connection(self.vault_path)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM log_events_archive")
        self.assertEqual(cur.fetchone()[0], 4)
        conn.close()


if __name__ == "__main__":
    unittest.main()
