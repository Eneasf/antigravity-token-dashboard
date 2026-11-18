"""Unit tests for src/vault.py (Milestone M08 / ADR-018)."""

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import urllib.parse
import warnings
from unittest import mock

from src.vault import (
    DEFAULT_VAULT_PATH,
    backfill_step_latency_metrics,
    get_vault_connection,
    get_vault_truncation_markers,
    init_vault,
    parse_agyhub_summaries,
    scan_conversation_truncation,
    sync_conversations_to_vault,
    sync_log_events_to_vault,
)
from tests.test_telemetry_reader import (
    encode_field,
    encode_length_delimited,
    encode_timestamp,
    encode_varint,
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
        self.assertIn("vault_bytes", stats1)
        self.assertIsInstance(stats1["vault_bytes"], int)
        self.assertGreater(stats1["vault_bytes"], 0)

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

    def test_sync_conversations_to_vault(self):
        convo_id = "22222222-3333-4444-5555-666666666666"
        self._create_mock_convo_db(
            convo_id,
            [(0, 14, 1, None, None, b"payload_content")],
        )
        stats = sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )
        self.assertIn("vault_bytes", stats)
        self.assertIsInstance(stats["vault_bytes"], int)
        self.assertGreater(stats["vault_bytes"], 0)

    def test_schema_has_ttft_and_latency_columns_and_view(self):
        conn = init_vault(self.vault_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(steps_archive)")
        cols = {r[1]: r[2] for r in cur.fetchall()}
        self.assertIn("ttft_ms", cols)
        self.assertIn("latency_ms", cols)
        self.assertEqual(cols["ttft_ms"], "REAL")
        self.assertEqual(cols["latency_ms"], "REAL")

        # Test view v_turns includes ttft_ms and latency_ms
        cur.execute("PRAGMA table_info(v_turns)")
        view_cols = {r[1] for r in cur.fetchall()}
        self.assertIn("ttft_ms", view_cols)
        self.assertIn("latency_ms", view_cols)
        conn.close()

    def test_backfill_step_latency_metrics(self):
        conn = init_vault(self.vault_path)
        cur = conn.cursor()

        # Insert a row without latency metrics but with wire metadata
        ts_req = encode_timestamp(1000, 0)
        ts_first = encode_timestamp(1000, 95000000)
        ts_done = encode_timestamp(1001, 500000000)
        meta_blob = (
            encode_length_delimited(6, ts_req)
            + encode_length_delimited(7, ts_first)
            + encode_length_delimited(8, ts_done)
        )
        cur.execute(
            """
            INSERT INTO steps_archive (convo_id, step_idx, step_type, raw_metadata_blob, ttft_ms, latency_ms)
            VALUES (?, ?, ?, ?, NULL, NULL)
            """,
            ("convo-backfill-1", 1, 15, meta_blob),
        )
        # Also insert a row with invalid blob to test -1.0 sentinel
        cur.execute(
            """
            INSERT INTO steps_archive (convo_id, step_idx, step_type, raw_metadata_blob, ttft_ms, latency_ms)
            VALUES (?, ?, ?, ?, NULL, NULL)
            """,
            ("convo-backfill-2", 2, 15, b"corrupted"),
        )
        conn.commit()

        # Run backfill
        updated = backfill_step_latency_metrics(self.vault_path, conn=conn)
        self.assertEqual(updated, 2)

        cur.execute("SELECT convo_id, ttft_ms, latency_ms FROM steps_archive ORDER BY convo_id")
        rows = cur.fetchall()
        self.assertEqual(rows[0][0], "convo-backfill-1")
        self.assertEqual(rows[0][1], 95.0)
        self.assertEqual(rows[0][2], 1500.0)

        self.assertEqual(rows[1][0], "convo-backfill-2")
        self.assertEqual(rows[1][1], -1.0)
        self.assertEqual(rows[1][2], -1.0)
        conn.close()

    def test_sync_conversations_to_vault_populates_latency(self):
        convo_id = "33333333-4444-5555-6666-777777777777"
        ts_req = encode_timestamp(2000, 0)
        ts_first = encode_timestamp(2000, 120000000)
        ts_done = encode_timestamp(2001, 800000000)
        meta_blob = (
            encode_length_delimited(6, ts_req)
            + encode_length_delimited(7, ts_first)
            + encode_length_delimited(8, ts_done)
        )
        self._create_mock_convo_db(
            convo_id,
            [(0, 15, 1, meta_blob, None, b"response_payload")],
        )
        sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
        )

        conn = get_vault_connection(self.vault_path)
        cur = conn.cursor()
        cur.execute("SELECT ttft_ms, latency_ms FROM steps_archive WHERE convo_id = ?", (convo_id,))
        row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 120.0)
        self.assertEqual(row[1], 1800.0)
        conn.close()

    def test_root_orchestrator_not_parented_to_child_sender(self):
        root_id = "6e8b5b79-fce9-48f0-9ede-cc0a17dfda18"
        child_id = "a26a5649-d88d-49f4-9df6-749bcaad484d"

        # Root step containing a system message from the child (field 114 containing inner field 1 bytes)
        msg_bytes = f"[Message] sender={child_id} Task completed".encode("utf-8")
        root_step_payload = encode_length_delimited(114, encode_length_delimited(1, msg_bytes))
        root_db_path = self._create_mock_convo_db(
            root_id,
            [(0, 14, 1, None, None, root_step_payload)],
        )
        root_traj_blob = encode_length_delimited(6, root_id.encode("utf-8"))
        conn_r = sqlite3.connect(str(root_db_path))
        conn_r.execute("CREATE TABLE trajectory_metadata_blob (id TEXT PRIMARY KEY, data BLOB)")
        conn_r.execute("INSERT INTO trajectory_metadata_blob (id, data) VALUES ('main', ?)", (root_traj_blob,))
        conn_r.commit()
        conn_r.close()

        # Child DB with parent_convo_id = root_id (field 5), convo_id = child_id (field 6), is_subagent = 1 (field 17)
        child_step_payload = encode_length_delimited(114, encode_length_delimited(1, b"Child task input"))
        child_db_path = self._create_mock_convo_db(
            child_id,
            [(0, 14, 1, None, None, child_step_payload)],
        )
        child_traj_blob = (
            encode_length_delimited(5, root_id.encode("utf-8"))
            + encode_length_delimited(6, child_id.encode("utf-8"))
            + encode_field(17, 0, encode_varint(1))
        )
        conn_c = sqlite3.connect(str(child_db_path))
        conn_c.execute("CREATE TABLE trajectory_metadata_blob (id TEXT PRIMARY KEY, data BLOB)")
        conn_c.execute("INSERT INTO trajectory_metadata_blob (id, data) VALUES ('main', ?)", (child_traj_blob,))
        conn_c.commit()
        conn_c.close()

        sync_conversations_to_vault(
            antigravity_dir=self.antigravity_dir,
            vault_path=self.vault_path,
            force=True,
        )

        conn = get_vault_connection(self.vault_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT parent_convo_id, is_subagent FROM conversations_archive WHERE convo_id = ?",
            (root_id,),
        )
        root_row = cur.fetchone()
        self.assertIsNotNone(root_row)
        self.assertIn(root_row[0], (None, ""))
        self.assertEqual(int(root_row[1] or 0), 0)

        cur.execute(
            "SELECT parent_convo_id, is_subagent FROM conversations_archive WHERE convo_id = ?",
            (child_id,),
        )
        child_row = cur.fetchone()
        self.assertIsNotNone(child_row)
        self.assertEqual(child_row[0], root_id)
        self.assertEqual(int(child_row[1] or 0), 1)
        conn.close()



class TestVaultConnectionHardening(unittest.TestCase):
    """Regression test suite for SQLite connection hardening and concurrency (C3)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.vault_path = self.temp_path / "antigravity_vault.db"
        self.convo_path = self.temp_path / "conversation.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_vault_truncation_markers_closes_connection_on_exception(self):
        conn = sqlite3.connect(self.vault_path)
        conn.execute("CREATE TABLE steps_archive (convo_id TEXT, step_idx INTEGER, payload_text TEXT, prompt_tokens_uncached INTEGER, cached_tokens INTEGER)")
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
            def cursor(self):
                cr = self._c.cursor()
                orig_exec = cr.execute
                class CursorWrapper:
                    def __init__(self, cursor_obj):
                        self._cr = cursor_obj
                    def __getattr__(self, name):
                        return getattr(self._cr, name)
                    def execute(self, sql, *a):
                        if "SELECT" in sql and "WITH marks" in sql:
                            raise sqlite3.OperationalError("Simulated query failure")
                        return orig_exec(sql, *a)
                return CursorWrapper(cr)
            def close(self):
                closed.append(True)
                return self._c.close()

        with mock.patch("sqlite3.connect", side_effect=lambda *a, **k: CW(orig_connect(*a, **k))):
            res = get_vault_truncation_markers(self.vault_path)
            self.assertEqual(res, {})
            self.assertTrue(len(closed) >= 1)

    def test_get_vault_truncation_markers_early_return_and_concurrency(self):
        conn = sqlite3.connect(self.vault_path)
        conn.execute("CREATE TABLE other_table (id INTEGER)")
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
            res = get_vault_truncation_markers(self.vault_path)
            self.assertEqual(res, {})
            self.assertEqual(len(closed), 1)
            self.assertEqual(timeouts, [60.0])
            self.assertTrue(any("busy_timeout = 60000" in p for p in pragmas))

    def test_scan_conversation_truncation_closes_connection_on_exception(self):
        conn = sqlite3.connect(self.convo_path)
        conn.execute("CREATE TABLE steps (idx INTEGER, step_type INTEGER, metadata BLOB, step_payload BLOB)")
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
            def cursor(self):
                cr = self._c.cursor()
                class CursorWrapper:
                    def __init__(self, cursor_obj):
                        self._cr = cursor_obj
                    def __getattr__(self, name):
                        return getattr(self._cr, name)
                    def execute(self, sql, *a):
                        raise sqlite3.OperationalError("Simulated query failure")
                return CursorWrapper(cr)
            def close(self):
                closed.append(True)
                return self._c.close()

        with mock.patch("sqlite3.connect", side_effect=lambda *a, **k: CW(orig_connect(*a, **k))):
            res = scan_conversation_truncation(self.convo_path)
            self.assertEqual(res, (False, None, None))
            self.assertTrue(len(closed) >= 1)

    def test_scan_conversation_truncation_early_returns_and_concurrency(self):
        conn = sqlite3.connect(self.convo_path)
        conn.execute("CREATE TABLE steps (idx INTEGER, step_type INTEGER)")
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
            res = scan_conversation_truncation(self.convo_path)
            self.assertEqual(res, (False, None, None))
            self.assertEqual(len(closed), 1)
            self.assertEqual(timeouts, [60.0])
            self.assertTrue(any("busy_timeout = 60000" in p for p in pragmas))

    def test_vault_resource_warning_hygiene(self):
        conn = sqlite3.connect(self.convo_path)
        conn.execute("CREATE TABLE steps (idx INTEGER, step_payload BLOB, metadata BLOB, step_type INTEGER)")
        conn.commit()
        conn.close()

        conn = sqlite3.connect(self.vault_path)
        conn.execute("CREATE TABLE steps_archive (convo_id TEXT, step_idx INTEGER, payload_text TEXT, prompt_tokens_uncached INTEGER, cached_tokens INTEGER)")
        conn.commit()
        conn.close()

        with warnings.catch_warnings():
            warnings.simplefilter("error", ResourceWarning)
            scan_conversation_truncation(self.convo_path)
            get_vault_truncation_markers(self.vault_path)


if __name__ == "__main__":
    unittest.main()
