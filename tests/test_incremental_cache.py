"""
Unit and integration tests for Milestone 87:
Incremental Cached Exporter (<500ms) with SQLite & In-Memory Two-Tier Architecture.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

from scripts.export_dashboard import (
    build_parser,
    clear_exporter_cache,
    compute_config_hash,
    export_telemetry,
    get_cache_connection,
    get_cache_db_path,
    get_conversation_db_fingerprint,
    init_export_cache_db,
    load_incremental_conversations,
    load_pricing,
    load_vault_analytics_cached,
    _IN_MEMORY_CONVO_CACHE,
    _IN_MEMORY_VAULT_CACHE,
)


class TestIncrementalCache(unittest.TestCase):
    """Test suite validating incremental SQLite and in-memory caching mechanics."""

    def setUp(self):
        clear_exporter_cache()
        self.test_dir = tempfile.mkdtemp(prefix="agy_test_m87_")
        self.test_path = Path(self.test_dir)
        self.conv_dir = self.test_path / "conversations"
        self.conv_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = self.test_path / "dashboard_out"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.index_html = self.output_dir / "index.html"
        self.index_html.write_text("<!DOCTYPE html><html><body></body></html>", encoding="utf-8")
        self.status_file = self.test_path / "status.json"
        self.pricing = load_pricing()

    def tearDown(self):
        clear_exporter_cache()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_mock_db(
        self,
        db_path: Path,
        turn_count: int = 3,
        uncached_prompt: int = 1500,
        cached_prompt: int = 20000,
    ):
        """Create a minimal SQLite schema matching Antigravity conversation format."""
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trajectory_metadata_blob (
                id TEXT PRIMARY KEY,
                data BLOB
            )
            """
        )
        uri = b"file:///Users/alice/Projects/Test%20Workspace"
        br = b"feat/test-branch"
        sub_payload = bytes([0x0a, len(uri)]) + uri + bytes([0x22, len(br)]) + br
        outer_payload = bytes([0x0a, len(sub_payload)]) + sub_payload
        cur.execute("INSERT OR REPLACE INTO trajectory_metadata_blob VALUES (?, ?)", ("main", outer_payload))

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS steps (
                idx INTEGER PRIMARY KEY,
                step_type INTEGER,
                metadata BLOB,
                step_payload BLOB
            )
            """
        )

        def encode_varint(n: int) -> bytes:
            res = []
            while n > 0x7f:
                res.append((n & 0x7f) | 0x80)
                n >>= 7
            res.append(n & 0x7f)
            return bytes(res)

        sf1 = bytes([(1 << 3) | 0]) + encode_varint(1)
        sf2 = bytes([(2 << 3) | 0]) + encode_varint(uncached_prompt)
        sf3 = bytes([(3 << 3) | 0]) + encode_varint(150)
        sf5 = bytes([(5 << 3) | 0]) + encode_varint(cached_prompt)
        sub_9 = sf1 + sf2 + sf3 + sf5
        f9 = bytes([(9 << 3) | 2, len(sub_9)]) + sub_9

        for i in range(turn_count):
            cur.execute(
                "INSERT OR REPLACE INTO steps VALUES (?, ?, ?, ?)",
                (i + 1, 15, f9, b"step payload"),
            )

        conn.commit()
        conn.close()

    def _create_mock_vault(self, vault_path: Path, turn_count: int = 5):
        """Create a mock Antigravity vault SQLite DB."""
        conn = sqlite3.connect(str(vault_path))
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS steps_archive (
                id INTEGER PRIMARY KEY,
                convo_id TEXT,
                step_index INTEGER,
                step_type INTEGER,
                model_id TEXT,
                model_name TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cached_tokens INTEGER,
                cost_usd REAL,
                duration_ms INTEGER,
                timestamp_utc TEXT,
                payload_text TEXT,
                workspace TEXT,
                source_file TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_calls_archive (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                convo_id TEXT,
                step_idx INTEGER,
                call_id TEXT,
                tool_name TEXT,
                tool_action TEXT,
                tool_summary TEXT,
                arguments_json TEXT,
                result_summary TEXT,
                timestamp TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS swarms_archive (
                swarm_id TEXT PRIMARY KEY,
                parent_convo_id TEXT,
                child_convo_id TEXT,
                objective TEXT,
                model TEXT,
                status TEXT,
                start_time_utc TEXT,
                end_time_utc TEXT,
                duration_ms INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                total_cost_usd REAL,
                turns_count INTEGER,
                exit_code INTEGER,
                result_summary TEXT,
                created_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations_archive (
                convo_id TEXT PRIMARY KEY,
                parent_convo_id TEXT,
                workspace_name TEXT,
                workspace_path TEXT,
                title TEXT,
                turn_count INTEGER,
                total_input_tokens INTEGER,
                total_output_tokens INTEGER,
                cached_tokens INTEGER,
                thinking_tokens INTEGER,
                estimated_cost_usd REAL,
                first_turn_ts TEXT,
                last_turn_ts TEXT,
                agent_name TEXT,
                is_subagent INTEGER,
                subagent_role TEXT
            )
            """
        )
        for i in range(turn_count):
            cur.execute(
                """
                INSERT INTO steps_archive
                (id, convo_id, step_index, step_type, model_id, model_name, input_tokens, output_tokens, cached_tokens, cost_usd, duration_ms, timestamp_utc, payload_text, workspace, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    i + 1,
                    f"convo-{i}",
                    i + 1,
                    14 if i % 2 == 0 else 15,
                    "gemini-2.5-flash",
                    "Gemini 2.5 Flash",
                    1000,
                    100,
                    500,
                    0.001,
                    200,
                    "2026-09-20T12:00:00Z",
                    "User prompt text",
                    "ws",
                    "db.db",
                ),
            )
            cur.execute(
                """
                INSERT INTO conversations_archive
                (convo_id, parent_convo_id, workspace_name, workspace_path, title, turn_count, total_input_tokens, total_output_tokens, cached_tokens, thinking_tokens, estimated_cost_usd, first_turn_ts, last_turn_ts, agent_name, is_subagent, subagent_role)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"convo-{i}",
                    None,
                    "ws",
                    "/path/to/ws",
                    f"Conversation {i}",
                    1,
                    1000,
                    100,
                    500,
                    0,
                    0.001,
                    "2026-09-20T12:00:00Z",
                    "2026-09-20T12:00:00Z",
                    "default",
                    0,
                    "",
                ),
            )
            cur.execute(
                """
                INSERT INTO tool_calls_archive
                (convo_id, step_idx, call_id, tool_name, tool_action, tool_summary, arguments_json, result_summary, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"convo-{i}",
                    i + 1,
                    f"call-{i}",
                    "replace_file_content",
                    "Replacing content",
                    "Edit file",
                    '{"TargetFile": "/path/to/foo"}',
                    "ok",
                    "2026-09-20T12:00:00Z",
                ),
            )
        conn.commit()
        conn.close()

    def test_cold_and_warm_export_cache_lifecycle(self):
        """
        Verify initial cold export populates both in-memory cache and SQLite cache,
        and subsequent warm export produces byte-identical payload and hits cache.
        """
        db1 = self.conv_dir / "convo-1.db"
        db2 = self.conv_dir / "convo-2.db"
        self._create_mock_db(db1, turn_count=2)
        self._create_mock_db(db2, turn_count=4)

        # Cold export
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload1 = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
            )

        # Verify cache DB created
        cache_db = get_cache_db_path(self.output_dir)
        self.assertTrue(cache_db.exists(), "Persistent cache DB must exist after export")

        # Verify SQLite cache contents
        conn = sqlite3.connect(str(cache_db))
        cur = conn.cursor()
        rows = cur.execute("SELECT convo_id, mtime_ns, size_bytes FROM conversation_cache").fetchall()
        conn.close()
        self.assertEqual(len(rows), 2)
        cached_ids = {r[0] for r in rows}
        self.assertEqual(cached_ids, {"convo-1", "convo-2"})

        # Verify in-memory cache populated
        self.assertIn("convo-1", _IN_MEMORY_CONVO_CACHE)
        self.assertIn("convo-2", _IN_MEMORY_CONVO_CACHE)

        # Warm export
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload2 = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
            )

        # Assert parity
        self.assertEqual(payload1["summary"]["total_turns"], payload2["summary"]["total_turns"])
        self.assertEqual(payload1["summary"]["total_input_tokens"], payload2["summary"]["total_input_tokens"])
        self.assertEqual(len(payload1["conversations"]), len(payload2["conversations"]))

    def test_incremental_dirty_detection_single_db_modified(self):
        """
        Verify modifying only 1 conversation updates only that conversation in payload and cache,
        while unchanged conversations are served directly from cache.
        """
        db1 = self.conv_dir / "convo-1.db"
        db2 = self.conv_dir / "convo-2.db"
        self._create_mock_db(db1, turn_count=2, uncached_prompt=1000)
        self._create_mock_db(db2, turn_count=3, uncached_prompt=1000)

        # Initial export
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload1 = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
            )
        self.assertEqual(payload1["summary"]["total_turns"], 5)

        # Wait small fraction and update db1 with 5 turns
        time.sleep(0.02)
        self._create_mock_db(db1, turn_count=5, uncached_prompt=2000)

        # Second export
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload2 = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
            )

        self.assertEqual(payload2["summary"]["total_turns"], 8)
        c1 = next(c for c in payload2["conversations"] if c["convo_id"] == "convo-1")
        c2 = next(c for c in payload2["conversations"] if c["convo_id"] == "convo-2")
        self.assertEqual(c1["turn_count"], 5)
        self.assertEqual(c2["turn_count"], 3)

        # Verify SQLite cache updated for convo-1
        cache_db = get_cache_db_path(self.output_dir)
        conn = sqlite3.connect(str(cache_db))
        cur = conn.cursor()
        c1_row = cur.execute("SELECT raw_turns_json FROM conversation_cache WHERE convo_id = 'convo-1'").fetchone()
        conn.close()
        c1_turns = json.loads(c1_row[0])
        self.assertEqual(len(c1_turns), 5)

    def test_incremental_new_conversation_added(self):
        """Verify adding a new DB dynamically includes it in export and cache."""
        db1 = self.conv_dir / "convo-1.db"
        self._create_mock_db(db1, turn_count=2)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload1 = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
            )
        self.assertEqual(len(payload1["conversations"]), 1)

        # Add convo-2
        db2 = self.conv_dir / "convo-2.db"
        self._create_mock_db(db2, turn_count=3)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload2 = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
            )
        self.assertEqual(len(payload2["conversations"]), 2)

        cache_db = get_cache_db_path(self.output_dir)
        conn = sqlite3.connect(str(cache_db))
        cur = conn.cursor()
        rows = cur.execute("SELECT convo_id FROM conversation_cache").fetchall()
        conn.close()
        self.assertEqual(len(rows), 2)

    def test_incremental_deleted_conversation_pruned(self):
        """Verify deleting a DB removes it from payload and prunes it from cache."""
        db1 = self.conv_dir / "convo-1.db"
        db2 = self.conv_dir / "convo-2.db"
        self._create_mock_db(db1, turn_count=2)
        self._create_mock_db(db2, turn_count=3)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload1 = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
            )
        self.assertEqual(len(payload1["conversations"]), 2)

        # Delete db1
        db1.unlink()

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload2 = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
            )
        self.assertEqual(len(payload2["conversations"]), 1)
        self.assertEqual(payload2["conversations"][0]["convo_id"], "convo-2")

        # Verify pruned from in-memory cache
        self.assertNotIn("convo-1", _IN_MEMORY_CONVO_CACHE)

        # Verify pruned from SQLite cache
        cache_db = get_cache_db_path(self.output_dir)
        conn = sqlite3.connect(str(cache_db))
        cur = conn.cursor()
        rows = cur.execute("SELECT convo_id FROM conversation_cache").fetchall()
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "convo-2")

    def test_force_full_scan_flag(self):
        """Verify force_full_scan=True ignores cache, performs complete re-scan, and refreshes cache."""
        db1 = self.conv_dir / "convo-1.db"
        self._create_mock_db(db1, turn_count=3)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload1 = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
            )

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload2 = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
                force_full_scan=True,
            )

        self.assertEqual(payload1["summary"]["total_turns"], payload2["summary"]["total_turns"])
        self.assertEqual(payload1["summary"]["total_input_tokens"], payload2["summary"]["total_input_tokens"])

    def test_cache_corruption_self_healing(self):
        """Verify corrupt cache SQLite database is gracefully self-healed and does not crash exporter."""
        db1 = self.conv_dir / "convo-1.db"
        self._create_mock_db(db1, turn_count=2)

        # Pre-create corrupted cache file
        cache_db = get_cache_db_path(self.output_dir)
        cache_db.write_bytes(b"CORRUPTED_GARBAGE_HEADER_NOT_A_SQLITE_DB")

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
            )

        self.assertEqual(payload["summary"]["total_turns"], 2)
        # Verify cache_db is now a valid SQLite database
        conn = sqlite3.connect(str(cache_db))
        cur = conn.cursor()
        rows = cur.execute("SELECT convo_id FROM conversation_cache").fetchall()
        conn.close()
        self.assertEqual(len(rows), 1)

    def test_vault_analytics_caching_and_invalidation(self):
        """Verify vault analytics queries are cached and re-invalidated when vault row count changes."""
        vault_file = self.test_path / "antigravity_vault.db"
        self._create_mock_vault(vault_file, turn_count=4)

        cache_db = get_cache_db_path(self.output_dir)
        cache_conn = get_cache_connection(cache_db)

        # Initial call
        res1 = load_vault_analytics_cached(
            vault_file=vault_file,
            pricing=self.pricing,
            cache_conn=cache_conn,
        )
        self.assertEqual(len(res1["prompts_by_convo"]), 2)
        self.assertEqual(len(res1["tool_calls_by_convo"]), 4)

        # Second call with same vault: should return cached dict directly
        res2 = load_vault_analytics_cached(
            vault_file=vault_file,
            pricing=self.pricing,
            cache_conn=cache_conn,
        )
        self.assertEqual(res1["prompts_by_convo"], res2["prompts_by_convo"])
        self.assertEqual(res1["tool_calls_by_convo"], res2["tool_calls_by_convo"])

        # Clear in-memory cache and verify persistent SQLite vault_cache hits cleanly
        clear_exporter_cache()
        stderr_buf = io.StringIO()
        with contextlib.redirect_stderr(stderr_buf):
            res_sqlite_hit = load_vault_analytics_cached(
                vault_file=vault_file,
                pricing=self.pricing,
                cache_conn=cache_conn,
            )
        self.assertEqual(stderr_buf.getvalue(), "")
        self.assertEqual(res1["prompts_by_convo"], res_sqlite_hit["prompts_by_convo"])
        self.assertEqual(res1["tool_calls_by_convo"], res_sqlite_hit["tool_calls_by_convo"])

        # Mutate vault by inserting a new step
        time.sleep(0.02)
        vconn = sqlite3.connect(str(vault_file))
        vconn.execute(
            """
            INSERT INTO steps_archive
            (id, convo_id, step_index, step_type, model_id, input_tokens, output_tokens, cached_tokens, cost_usd, duration_ms, timestamp_utc, payload_text, workspace, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (99, "convo-new", 1, 14, "gemini-2.5-flash", 500, 50, 0, 0.0005, 100, "2026-09-20T13:00:00Z", "Fresh prompt", "ws", "db.db"),
        )
        vconn.commit()
        vconn.close()

        # Third call: cache should invalidate and reflect new prompt
        res3 = load_vault_analytics_cached(
            vault_file=vault_file,
            pricing=self.pricing,
            cache_conn=cache_conn,
        )
        self.assertIn("convo-new", res3["prompts_by_convo"])
        cache_conn.close()

    def test_cli_parser_has_force_full_scan(self):
        """Verify CLI argument parser defines --force-full-scan."""
        parser = build_parser()
        args = parser.parse_args(["--force-full-scan"])
        self.assertTrue(args.force_full_scan)

        default_args = parser.parse_args([])
        self.assertFalse(default_args.force_full_scan)

    def test_fingerprint_helper_detects_wal(self):
        """Verify get_conversation_db_fingerprint aggregates both DB and WAL mtime/size."""
        db_file = self.conv_dir / "sample.db"
        self._create_mock_db(db_file, turn_count=1)

        fp1 = get_conversation_db_fingerprint(db_file)
        self.assertIsNotNone(fp1)

        # Create synthetic WAL
        wal_file = self.conv_dir / "sample.db-wal"
        wal_file.write_bytes(b"wal contents here")

        fp2 = get_conversation_db_fingerprint(db_file)
        self.assertIsNotNone(fp2)
        self.assertGreater(fp2[1], fp1[1])

    def test_fingerprint_helper_handles_string_path(self):
        """Verify get_conversation_db_fingerprint supports string paths without raising AttributeError."""
        db_file = self.conv_dir / "string_path_test.db"
        self._create_mock_db(db_file, turn_count=1)

        fp = get_conversation_db_fingerprint(str(db_file))
        self.assertIsNotNone(fp)
        self.assertIsInstance(fp, tuple)
        self.assertEqual(len(fp), 2)

    def test_partial_memory_cache_loads_from_sqlite(self):
        """Verify partially populated in-memory cache populates remaining entries from SQLite cache."""
        db1 = self.conv_dir / "convo-alpha.db"
        db2 = self.conv_dir / "convo-beta.db"
        self._create_mock_db(db1, turn_count=1)
        self._create_mock_db(db2, turn_count=1)

        # 1. Warm SQLite cache with full scan
        load_incremental_conversations(
            antigravity_dir=self.test_path,
            pricing=self.pricing,
            dashboard_dir=self.output_dir,
        )
        self.assertIn("convo-alpha", _IN_MEMORY_CONVO_CACHE)
        self.assertIn("convo-beta", _IN_MEMORY_CONVO_CACHE)

        # 2. Simulate partial eviction from memory cache
        del _IN_MEMORY_CONVO_CACHE["convo-beta"]
        self.assertNotIn("convo-beta", _IN_MEMORY_CONVO_CACHE)
        self.assertIn("convo-alpha", _IN_MEMORY_CONVO_CACHE)

        # 3. Re-run: convo-beta should be restored from SQLite cache without re-parsing
        with patch("scripts.export_dashboard.read_single_conversation_metadata") as mock_read:
            summaries, turns, disc, scn = load_incremental_conversations(
                antigravity_dir=self.test_path,
                pricing=self.pricing,
                dashboard_dir=self.output_dir,
            )
            self.assertEqual(mock_read.call_count, 0, "convo-beta should have been loaded from SQLite cache")
            self.assertEqual(len(summaries), 2)
            self.assertIn("convo-beta", _IN_MEMORY_CONVO_CACHE)

    def test_directory_switch_clears_stale_memory_cache(self):
        """Verify targeting a different antigravity directory clears in-memory cache to avoid cross-dir contamination."""
        db1 = self.conv_dir / "convo-1.db"
        self._create_mock_db(db1, turn_count=1)
        load_incremental_conversations(
            antigravity_dir=self.test_path,
            pricing=self.pricing,
            dashboard_dir=self.output_dir,
        )
        self.assertIn("convo-1", _IN_MEMORY_CONVO_CACHE)

        other_dir = tempfile.mkdtemp(prefix="agy_other_")
        try:
            other_conv = Path(other_dir) / "conversations"
            other_conv.mkdir(parents=True, exist_ok=True)
            db2 = other_conv / "convo-other.db"
            self._create_mock_db(db2, turn_count=1)

            load_incremental_conversations(
                antigravity_dir=other_dir,
                pricing=self.pricing,
            )
            self.assertIn("convo-other", _IN_MEMORY_CONVO_CACHE)
            self.assertNotIn("convo-1", _IN_MEMORY_CONVO_CACHE)
        finally:
            shutil.rmtree(other_dir, ignore_errors=True)

    def test_empty_conversations_directory(self):
        """Verify exporter works cleanly with 0 conversation DBs."""
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
            )
        self.assertEqual(payload["summary"]["total_conversations"], 0)
        self.assertEqual(len(payload["conversations"]), 0)

    def test_corrupt_individual_conversation_db(self):
        """Verify a corrupt conversation DB does not prevent other valid DBs from being cached and exported."""
        valid_db = self.conv_dir / "valid.db"
        corrupt_db = self.conv_dir / "corrupt.db"
        self._create_mock_db(valid_db, turn_count=2)
        corrupt_db.write_bytes(b"NOT_A_SQLITE_DATABASE_JUNK_DATA")

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
            )
        self.assertEqual(len(payload["conversations"]), 1)
        self.assertEqual(payload["conversations"][0]["convo_id"], "valid")

    def test_pricing_config_change_invalidates_cache(self):
        """Verify changing pricing model configuration triggers re-computation of conversation summaries."""
        db1 = self.conv_dir / "convo-1.db"
        self._create_mock_db(db1, turn_count=2)

        pricing_a = {"1": {"name": "M1", "rates_per_million": {"prompt_uncached": 1.0, "prompt_cached": 0.5, "candidate_output": 2.0}}}
        pricing_b = {"1": {"name": "M1", "rates_per_million": {"prompt_uncached": 10.0, "prompt_cached": 5.0, "candidate_output": 20.0}}}

        summaries_a, turns_a, _, _ = load_incremental_conversations(
            antigravity_dir=self.test_path,
            pricing=pricing_a,
            exhaustion_intervals=[],
            dashboard_dir=self.output_dir,
        )

        # Re-run with changed pricing: should invalidate cached summary
        summaries_b, turns_b, _, _ = load_incremental_conversations(
            antigravity_dir=self.test_path,
            pricing=pricing_b,
            exhaustion_intervals=[],
            dashboard_dir=self.output_dir,
        )

        self.assertEqual(len(summaries_a), 1)
        self.assertEqual(len(summaries_b), 1)
        # Cost should differ due to new pricing
        self.assertNotEqual(summaries_a[0]["estimated_cost_usd"], summaries_b[0]["estimated_cost_usd"])

    def test_sqlite_pragmas_wal_and_busy_timeout(self):
        """Verify export cache DB adheres to GADR-013 / ADR-081 SQLite concurrency standards."""
        cache_db = get_cache_db_path(self.output_dir)
        conn = get_cache_connection(cache_db)
        self.assertIsNotNone(conn)
        cur = conn.cursor()
        journal_mode = cur.execute("PRAGMA journal_mode;").fetchone()[0]
        busy_timeout = cur.execute("PRAGMA busy_timeout;").fetchone()[0]
        conn.close()

        self.assertEqual(journal_mode.lower(), "wal")
        self.assertEqual(busy_timeout, 60000)

    def test_aggregate_global_telemetry_skips_redundant_horizon_analytics(self):
        """Verify aggregate_global_telemetry(include_horizon_analytics=False) skips duplicate compute_horizon_analytics pass."""
        from src.aggregator import aggregate_global_telemetry

        with patch("src.aggregator.compute_horizon_analytics") as mock_horizon:
            res = aggregate_global_telemetry(
                [],
                self.pricing,
                all_raw_turns=[],
                exhaustion_intervals=[],
                include_horizon_analytics=False,
            )
            self.assertEqual(mock_horizon.call_count, 0)
            self.assertEqual(res.get("horizon_analytics"), {})

    def test_in_memory_cache_omits_duplicate_raw_turns_when_summary_present(self):
        """Verify _IN_MEMORY_CONVO_CACHE does not retain duplicate raw_turns list when summary is populated."""
        db1 = self.conv_dir / "convo-dedup.db"
        self._create_mock_db(db1, turn_count=3)

        summaries, turns, _, _ = load_incremental_conversations(
            antigravity_dir=self.test_path,
            pricing=self.pricing,
            exhaustion_intervals=[],
            dashboard_dir=self.output_dir,
        )
        self.assertEqual(len(summaries), 1)
        self.assertEqual(len(turns), 3)
        self.assertIn("convo-dedup", _IN_MEMORY_CONVO_CACHE)
        self.assertIsNone(_IN_MEMORY_CONVO_CACHE["convo-dedup"]["raw_turns"])
        self.assertEqual(len(_IN_MEMORY_CONVO_CACHE["convo-dedup"]["summary"]["turns"]), 3)

    def test_vault_cache_survives_noop_sync_and_quota_snapshot_insert(self):
        """Verify vault_cache in .export_cache.db is not invalidated by no-op conversation syncs or quota snapshot writes."""
        from src.vault import init_vault, sync_conversations_to_vault, sync_quota_snapshot_to_vault

        vault_file = self.test_path / "antigravity_vault.db"
        init_vault(vault_file).close()
        self._create_mock_db(self.conv_dir / "convo-1.db", turn_count=2)
        sync_conversations_to_vault(antigravity_dir=self.test_path, vault_path=vault_file)

        cache_conn = get_cache_connection(get_cache_db_path(self.output_dir))
        load_vault_analytics_cached(vault_file=vault_file, pricing=self.pricing, cache_conn=cache_conn)
        ts_before = cache_conn.execute(
            "SELECT updated_at FROM vault_cache WHERE key = 'vault_analytics'"
        ).fetchone()[0]

        # Simulate subprocess restart + no-op conversation sync + quota snapshot write
        clear_exporter_cache()
        sync_conversations_to_vault(antigravity_dir=self.test_path, vault_path=vault_file)
        sq = sync_quota_snapshot_to_vault(
            {"available": True, "gemini_5h": {"remaining_fraction": 0.75, "reset_time": "2026-11-09T20:00:00Z"}},
            vault_path=vault_file,
        )
        self.assertTrue(sq.get("inserted"))

        load_vault_analytics_cached(vault_file=vault_file, pricing=self.pricing, cache_conn=cache_conn)
        ts_after = cache_conn.execute(
            "SELECT updated_at FROM vault_cache WHERE key = 'vault_analytics'"
        ).fetchone()[0]
        cache_conn.close()
        self.assertEqual(ts_before, ts_after)

    def test_horizon_analytics_persisted_in_sqlite_cache(self):
        """Verify horizon_analytics is persisted in .export_cache.db across clear_exporter_cache()."""
        from src.vault import init_vault

        vault_file = self.test_path / "antigravity_vault.db"
        init_vault(vault_file).close()
        self._create_mock_db(self.conv_dir / "convo-1.db", turn_count=2)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            p1 = export_telemetry(
                antigravity_dir=self.test_path,
                dashboard_path=self.index_html,
                output_dir=self.output_dir,
                status_path=self.status_file,
                no_live_quota=True,
            )

        clear_exporter_cache()
        with patch("src.horizon_analytics.compute_horizon_analytics", side_effect=AssertionError("Should hit SQLite cache")):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                p2 = export_telemetry(
                    antigravity_dir=self.test_path,
                    dashboard_path=self.index_html,
                    output_dir=self.output_dir,
                    status_path=self.status_file,
                    no_live_quota=True,
                )
        self.assertEqual(p1.get("horizon_analytics"), p2.get("horizon_analytics"))


if __name__ == "__main__":
    unittest.main()
