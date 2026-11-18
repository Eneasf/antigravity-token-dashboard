"""
Unit tests for src/vault_schema.py (Milestone M75 / Row 8 (C7)).

Validates:
- Schema initialization and table creation across all 8 vault tables.
- Schema idempotence and safe column addition migrations.
- Connection PRAGMAs (WAL mode, busy_timeout).
- get_vault_connection helper factory.
- Strict isolation: importing vault_schema does not import vault or weekly_trends.
- Backward compatibility: re-exported symbols match across vault and weekly_trends.
"""

from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from src.vault_schema import (
    DEFAULT_VAULT_PATH,
    get_vault_connection,
    init_vault,
)
import src.vault as vault_mod
import src.weekly_trends as weekly_trends_mod


class TestVaultSchema(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.vault_path = self.temp_path / "test_vault.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_init_vault_creates_all_tables_and_indexes(self):
        conn = init_vault(self.vault_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        required_tables = {
            "conversations_archive",
            "steps_archive",
            "tool_calls_archive",
            "skills_archive",
            "log_events_archive",
            "vault_sync_state",
            "weekly_cycles_archive",
            "subscription_history_archive",
            "ref_step_types",
            "ref_status_codes",
        }
        self.assertTrue(required_tables.issubset(tables), f"Missing tables: {required_tables - tables}")

        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {r[0] for r in cur.fetchall()}
        required_indexes = {
            "idx_conversations_parent",
            "idx_conversations_workspace",
            "idx_steps_convo_id",
            "idx_steps_step_type",
            "idx_steps_model_id",
            "idx_tool_calls_convo_step",
            "idx_tool_calls_name",
            "idx_skills_convo_step",
            "idx_skills_name",
            "idx_log_events_iso",
            "idx_weekly_cycles_start",
            "idx_sub_history_from",
            "idx_steps_convo_id_ts",
            "idx_steps_step_type_ts",
            "idx_steps_error_text",
            "idx_steps_rate_limit",
            "idx_log_events_code_type_ts",
        }
        self.assertTrue(required_indexes.issubset(indexes), f"Missing indexes: {required_indexes - indexes}")

        cur.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = {r[0] for r in cur.fetchall()}
        required_views = {
            "v_turns",
            "v_hourly_token_velocity",
            "v_active_sessions",
            "v_rate_limit_events",
        }
        self.assertTrue(required_views.issubset(views), f"Missing views: {required_views - views}")
        conn.close()

    def test_view_column_aliases_and_ergonomics(self):
        conn = init_vault(self.vault_path)
        cur = conn.cursor()

        # Check v_turns columns and aliases
        cur.execute("PRAGMA table_info(v_turns)")
        turns_cols = {r[1] for r in cur.fetchall()}
        expected_turns_cols = {
            "convo_id",
            "step_idx",
            "turn_idx",
            "model_id",
            "model_name",
            "model",
            "output_tokens_total",
            "total_output_tokens",
            "error_text",
            "error_code",
            "rate_limit_flag",
        }
        self.assertTrue(expected_turns_cols.issubset(turns_cols), f"Missing v_turns cols: {expected_turns_cols - turns_cols}")

        # Check v_active_sessions columns and aliases
        cur.execute("PRAGMA table_info(v_active_sessions)")
        sessions_cols = {r[1] for r in cur.fetchall()}
        expected_sessions_cols = {
            "convo_id",
            "turn_count",
            "total_turns",
            "cached_tokens",
            "thinking_tokens",
            "estimated_cost_usd",
            "duration_seconds",
            "subagent_role",
        }
        self.assertTrue(
            expected_sessions_cols.issubset(sessions_cols),
            f"Missing v_active_sessions cols: {expected_sessions_cols - sessions_cols}",
        )

        # Check v_hourly_token_velocity columns and aliases
        cur.execute("PRAGMA table_info(v_hourly_token_velocity)")
        velocity_cols = {r[1] for r in cur.fetchall()}
        expected_velocity_cols = {"hour_utc", "model_name", "model", "turn_count", "total_turns", "total_input", "total_cached", "total_output"}
        self.assertTrue(
            expected_velocity_cols.issubset(velocity_cols),
            f"Missing v_hourly_token_velocity cols: {expected_velocity_cols - velocity_cols}",
        )

        # Check v_rate_limit_events columns
        cur.execute("PRAGMA table_info(v_rate_limit_events)")
        rate_cols = {r[1] for r in cur.fetchall()}
        expected_rate_cols = {"event_time", "code", "reason", "convo_id", "title", "agent_name", "subagent_role"}
        self.assertTrue(
            expected_rate_cols.issubset(rate_cols),
            f"Missing v_rate_limit_events cols: {expected_rate_cols - rate_cols}",
        )
        conn.close()

    def test_init_vault_idempotence(self):
        conn1 = init_vault(self.vault_path)
        conn1.close()

        # Second call on existing database must succeed cleanly
        conn2 = init_vault(self.vault_path)
        cur = conn2.cursor()
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        self.assertGreaterEqual(cur.fetchone()[0], 10)
        conn2.close()

    def test_reference_tables_pre_populated(self):
        conn = init_vault(self.vault_path)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM ref_step_types")
        self.assertGreaterEqual(cur.fetchone()[0], 10)
        cur.execute("SELECT count(*) FROM ref_status_codes")
        self.assertGreaterEqual(cur.fetchone()[0], 10)

        # Verify specific codes
        cur.execute("SELECT code_name FROM ref_step_types WHERE step_type = 15")
        self.assertEqual(cur.fetchone()[0], "PLANNER_RESPONSE")
        cur.execute("SELECT standard_name FROM ref_status_codes WHERE code = 429")
        self.assertEqual(cur.fetchone()[0], "RESOURCE_EXHAUSTED")
        conn.close()

    def test_steps_archive_rate_limit_columns_migration(self):
        # Create legacy table without rate_limit_flag or error_code
        conn = sqlite3.connect(str(self.vault_path))
        conn.execute(
            """
            CREATE TABLE steps_archive (
                convo_id TEXT,
                step_idx INTEGER,
                step_type INTEGER,
                status INTEGER,
                timestamp TEXT,
                model_id TEXT,
                model_name TEXT,
                payload_text TEXT,
                error_text TEXT,
                PRIMARY KEY (convo_id, step_idx)
            );
            """
        )
        conn.commit()
        conn.close()

        conn_migrated = init_vault(self.vault_path)
        cur = conn_migrated.cursor()
        cur.execute("PRAGMA table_info(steps_archive)")
        cols = {r[1] for r in cur.fetchall()}
        self.assertIn("rate_limit_flag", cols)
        self.assertIn("error_code", cols)
        conn_migrated.close()

    def test_conversations_archive_agent_columns_migration(self):
        # Create legacy table without agent columns
        conn = sqlite3.connect(str(self.vault_path))
        conn.execute(
            """
            CREATE TABLE conversations_archive (
                convo_id TEXT PRIMARY KEY,
                parent_convo_id TEXT,
                workspace_name TEXT,
                workspace_path TEXT,
                title TEXT
            );
            """
        )
        conn.commit()
        conn.close()

        # Running init_vault should automatically ALTER TABLE to add missing agent columns
        conn_migrated = init_vault(self.vault_path)
        cur = conn_migrated.cursor()
        cur.execute("PRAGMA table_info(conversations_archive)")
        cols = {r[1] for r in cur.fetchall()}
        self.assertIn("agent_name", cols)
        self.assertIn("agent_description", cols)
        self.assertIn("is_subagent", cols)
        self.assertIn("subagent_role", cols)
        conn_migrated.close()

    def test_pragmas_configured(self):
        conn = init_vault(self.vault_path, busy_timeout=45000)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode")
        mode = cur.fetchone()[0]
        self.assertEqual(mode.lower(), "wal")

        cur.execute("PRAGMA busy_timeout")
        timeout = cur.fetchone()[0]
        self.assertEqual(timeout, 45000)
        conn.close()

    def test_get_vault_connection(self):
        conn = get_vault_connection(self.vault_path, busy_timeout=5000)
        self.assertIsInstance(conn, sqlite3.Connection)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        self.assertGreaterEqual(cur.fetchone()[0], 8)
        conn.close()

    def test_strict_isolation_imports(self):
        """Importing src.vault_schema in an isolated process must not import src.vault or src.weekly_trends."""
        code = (
            "import sys\n"
            "import src.vault_schema\n"
            "assert 'src.vault' not in sys.modules, 'src.vault was loaded unexpectedly'\n"
            "assert 'src.weekly_trends' not in sys.modules, 'src.weekly_trends was loaded unexpectedly'\n"
            "print('ISOLATION_OK')\n"
        )
        res = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0, f"Isolation failed:\n{res.stderr}\n{res.stdout}")
        self.assertIn("ISOLATION_OK", res.stdout)

    def test_symbol_re_export_identity(self):
        """Verify re-exported symbols in vault and weekly_trends match vault_schema exactly."""
        self.assertIs(vault_mod.init_vault, init_vault)
        self.assertIs(vault_mod.DEFAULT_VAULT_PATH, DEFAULT_VAULT_PATH)
        self.assertIs(vault_mod.get_vault_connection, get_vault_connection)
        self.assertIs(weekly_mod_init := getattr(weekly_trends_mod, "init_vault"), init_vault)
        self.assertIs(getattr(weekly_trends_mod, "DEFAULT_VAULT_PATH"), DEFAULT_VAULT_PATH)


if __name__ == "__main__":
    unittest.main()
