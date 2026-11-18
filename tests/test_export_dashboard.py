"""Unit tests for scripts/export_dashboard.py."""

import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from scripts.export_dashboard import export_telemetry


class TestExportDashboard(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.dashboard_dir = self.temp_path / "dashboard"
        self.dashboard_dir.mkdir(parents=True)
        self.index_html = self.dashboard_dir / "index.html"

        sample_html = (
            '<!DOCTYPE html>\n'
            '<html lang="en">\n'
            '<head><title>Test</title></head>\n'
            '<body>\n'
            '<script id="injected-dashboard-data" type="application/json">{}</script>\n'
            '<script>\n'
            'let activeTheme = "dark";\n'
            '</script>\n'
            '</body>\n'
            '</html>'
        )
        self.index_html.write_text(sample_html, encoding="utf-8")
        self.empty_log = self.temp_path / "empty_server.log"
        self.empty_log.write_text("", encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_writes_decoupled_data_js(self):
        empty_antigravity = self.temp_path / "antigravity"
        empty_antigravity.mkdir()

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload = export_telemetry(
                antigravity_dir=empty_antigravity,
                dashboard_path=self.index_html,
                log_path=self.empty_log,
            )

        self.assertIn("summary", payload)
        self.assertTrue(self.index_html.exists())

        # Verify decoupled data.js and data.json
        data_js = self.dashboard_dir / "data.js"
        data_json = self.dashboard_dir / "data.json"
        self.assertTrue(data_js.exists())
        self.assertTrue(data_json.exists())

        js_content = data_js.read_text(encoding="utf-8")
        self.assertTrue(js_content.startswith("window.__TELEMETRY_DATA__ = "))
        self.assertIn('"summary":', js_content)
        self.assertIn('"subscription_status":"SAFE_IN_QUOTA"', js_content)

        # Verify decoupled meta.js and meta.json (Decision 5 fast hash-gating)
        meta_js = self.dashboard_dir / "meta.js"
        meta_json = self.dashboard_dir / "meta.json"
        self.assertTrue(meta_js.exists())
        self.assertTrue(meta_json.exists())

        meta_js_content = meta_js.read_text(encoding="utf-8")
        self.assertTrue(meta_js_content.startswith("window.__TELEMETRY_META__ = "))
        meta_dict = json.loads(meta_json.read_text(encoding="utf-8"))
        self.assertIn("payload_sha1", meta_dict)
        self.assertEqual(len(meta_dict["payload_sha1"]), 40)
        self.assertIn("payload_bytes", meta_dict)
        self.assertIn("conversations_count", meta_dict)
        self.assertIn("vault_bytes", meta_dict)
        self.assertTrue(isinstance(meta_dict["vault_bytes"], int))
        self.assertGreaterEqual(meta_dict["vault_bytes"], 0)
        self.assertIn("export_seconds", meta_dict)
        self.assertTrue(isinstance(meta_dict["export_seconds"], (int, float)))
        self.assertGreaterEqual(meta_dict["export_seconds"], 0.0)

        # Verify index.html references meta.js and data.js
        index_content = self.index_html.read_text(encoding="utf-8")
        self.assertIn('<script src="meta.js"></script>', index_content)
        self.assertIn('<script src="data.js"></script>', index_content)
        self.assertLess(index_content.find('<script src="meta.js"></script>'), index_content.find('<script src="data.js"></script>'))

    def test_decoupled_meta_files(self):
        empty_antigravity = self.temp_path / "antigravity"
        empty_antigravity.mkdir(exist_ok=True)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            export_telemetry(
                antigravity_dir=empty_antigravity,
                dashboard_path=self.index_html,
                log_path=self.empty_log,
            )

        meta_json = self.dashboard_dir / "meta.json"
        self.assertTrue(meta_json.exists())
        meta = json.loads(meta_json.read_text(encoding="utf-8"))
        self.assertIn("vault_bytes", meta)
        self.assertTrue(isinstance(meta["vault_bytes"], int))
        self.assertGreaterEqual(meta["vault_bytes"], 0)
        self.assertIn("export_seconds", meta)
        self.assertTrue(isinstance(meta["export_seconds"], (int, float)))
        self.assertGreaterEqual(meta["export_seconds"], 0.0)

    def test_export_embed_mode(self):
        empty_antigravity = self.temp_path / "antigravity"
        empty_antigravity.mkdir()

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload = export_telemetry(
                antigravity_dir=empty_antigravity,
                dashboard_path=self.index_html,
                log_path=self.empty_log,
                embed=True,
            )

        self.assertIn("summary", payload)
        index_content = self.index_html.read_text(encoding="utf-8")
        self.assertIn('<script id="injected-dashboard-data" type="application/json">', index_content)
        self.assertIn('"summary": {', index_content)
        self.assertIn('"subscription_status": "SAFE_IN_QUOTA"', index_content)

    def test_export_missing_hook_raises(self):
        empty_antigravity = self.temp_path / "antigravity"
        empty_antigravity.mkdir()
        bad_html = self.dashboard_dir / "bad.html"
        bad_html.write_text("<html><body>No hook here</body></html>", encoding="utf-8")

        with self.assertRaises(SystemExit):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                export_telemetry(
                    antigravity_dir=empty_antigravity,
                    dashboard_path=bad_html,
                    log_path=self.empty_log,
                )

    def test_meta_json_contains_export_seconds(self):
        """Verify that meta.json generated by export_dashboard contains export_seconds as a float/number."""
        empty_antigravity = self.temp_path / "antigravity"
        empty_antigravity.mkdir(exist_ok=True)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload = export_telemetry(
                antigravity_dir=empty_antigravity,
                dashboard_path=self.index_html,
                log_path=self.empty_log,
            )

        meta_json = self.dashboard_dir / "meta.json"
        self.assertTrue(meta_json.exists())
        meta = json.loads(meta_json.read_text(encoding="utf-8"))
        self.assertIn("export_seconds", meta)
        self.assertTrue(isinstance(meta["export_seconds"], (int, float)))
        self.assertGreaterEqual(meta["export_seconds"], 0.0)
        self.assertEqual(meta["export_seconds"], payload.get("export_seconds"))

    def test_custom_antigravity_dir_resolves_local_log_and_ledger(self):
        """Verify that when export_telemetry is called with a custom antigravity_dir,
        it resolves language_server.log and exhaustion_ledger.json from that directory
        and does not access the host's default log or ledger."""
        custom_ag = self.temp_path / "custom_antigravity"
        custom_ag.mkdir()
        (custom_ag / "conversations").mkdir()

        # Create custom synthetic log and ledger inside custom_antigravity
        custom_log = custom_ag / "language_server.log"
        custom_log.write_text(
            "ERROR: logging before google.Init: I0905 13:35:13.877653    8813 run.go:371] code 429 RESOURCE_EXHAUSTED\n",
            encoding="utf-8",
        )
        custom_ledger = custom_ag / "exhaustion_ledger.json"
        synthetic_incident = {
            "incident_id": "custom-synth-incident-429",
            "start_utc": "2026-09-05T13:00:00Z",
            "end_utc": "2026-09-05T14:00:00Z",
            "credits_burned": 99,
            "credit_burn_gbp": 0.95,
            "credit_burn_usd": 0.99,
            "turns_count": 40,
            "reason": "RESOURCE_EXHAUSTED",
            "code": 429,
        }
        custom_ledger.write_text(
            json.dumps({"version": 1, "incidents": [synthetic_incident]}),
            encoding="utf-8",
        )

        trap_log = self.temp_path / "trap_host_default.log"
        trap_ledger = self.temp_path / "trap_host_default.json"

        with patch("src.log_reader.DEFAULT_LOG_PATH", trap_log), \
             patch("src.log_reader.DEFAULT_LEDGER_PATH", trap_ledger):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                payload = export_telemetry(
                    antigravity_dir=custom_ag,
                    dashboard_path=self.index_html,
                    no_live_quota=True,
                )

        # 1. Custom ledger was loaded from custom_ag, not host default
        self.assertIn("exhaustion_intervals", payload)
        intervals = payload["exhaustion_intervals"]
        self.assertEqual(len(intervals), 1)
        self.assertEqual(intervals[0]["code"], 429)
        self.assertTrue(intervals[0]["start"].startswith("2026-09-05T13:00:00"))
        self.assertTrue(intervals[0]["end"].startswith("2026-09-05T14:00:00"))
        self.assertEqual(payload.get("summary", {}).get("total_ai_credits_burned"), 99)

        # 2. When custom_ag has neither log nor ledger, it does not fall back to host defaults
        empty_ag = self.temp_path / "empty_isolated_ag"
        empty_ag.mkdir()
        (empty_ag / "conversations").mkdir()

        with patch("src.log_reader.DEFAULT_LOG_PATH", trap_log), \
             patch("src.log_reader.DEFAULT_LEDGER_PATH", trap_ledger):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                empty_payload = export_telemetry(
                    antigravity_dir=empty_ag,
                    dashboard_path=self.index_html,
                    no_live_quota=True,
                )

        self.assertEqual(empty_payload.get("exhaustion_intervals", []), [])
        self.assertEqual(empty_payload.get("summary", {}).get("total_ai_credits_burned", 0), 0)

        # 3. Custom antigravity dir with only log file (no ledger) resolves local log
        log_only_ag = self.temp_path / "log_only_ag"
        log_only_ag.mkdir()
        (log_only_ag / "conversations").mkdir()
        (log_only_ag / "language_server.log").write_text(
            "ERROR: logging before google.Init: I0905 16:00:00.000000    8813 run.go:371] code 429 RESOURCE_EXHAUSTED\n",
            encoding="utf-8",
        )
        with patch("src.log_reader.DEFAULT_LOG_PATH", trap_log), \
             patch("src.log_reader.DEFAULT_LEDGER_PATH", trap_ledger):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                log_payload = export_telemetry(
                    antigravity_dir=log_only_ag,
                    dashboard_path=self.index_html,
                    no_live_quota=True,
                )

        self.assertEqual(len(log_payload.get("exhaustion_intervals", [])), 1)
        self.assertEqual(log_payload["exhaustion_intervals"][0]["code"], 429)
        self.assertTrue(log_payload["exhaustion_intervals"][0]["start"].startswith("2026-09-05T16:00:00"))

    def test_export_dry_run_does_not_invoke_vault_sync(self):
        """Verify that running export_telemetry with dry_run=True does not invoke vault sync (C2)."""
        empty_ag = self.temp_path / "dry_run_ag"
        empty_ag.mkdir()
        (empty_ag / "conversations").mkdir()

        with patch("scripts.export_dashboard.DEFAULT_ANTIGRAVITY_DIR", empty_ag), \
             patch("src.vault.sync_subscription_to_vault") as mock_sub, \
             patch("src.vault.sync_conversations_to_vault") as mock_conv, \
             patch("scripts.export_dashboard.sync_weekly_trends_to_vault") as mock_trends:

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                export_telemetry(
                    antigravity_dir=empty_ag,
                    dashboard_path=self.index_html,
                    dry_run=True,
                    no_live_quota=True,
                )

            self.assertFalse(mock_sub.called, "sync_subscription_to_vault was called during dry run")
            self.assertFalse(mock_conv.called, "sync_conversations_to_vault was called during dry run")
            self.assertFalse(mock_trends.called, "sync_weekly_trends_to_vault was called during dry run")

            # Verify that in a non-dry run with the default directory, sync IS invoked
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                export_telemetry(
                    antigravity_dir=empty_ag,
                    dashboard_path=self.index_html,
                    dry_run=False,
                    no_live_quota=True,
                )

            self.assertTrue(mock_sub.called, "sync_subscription_to_vault should be called when not dry run")
            self.assertTrue(mock_conv.called, "sync_conversations_to_vault should be called when not dry run")
            self.assertTrue(mock_trends.called, "sync_weekly_trends_to_vault should be called when not dry run")

    def test_export_subagent_correlation_closes_vault_connection(self):
        """Verify that export_telemetry properly closes the vault SQLite connection (C2)."""
        import gc
        import warnings
        empty_ag = self.temp_path / "conn_leak_ag"
        empty_ag.mkdir()
        (empty_ag / "conversations").mkdir()

        with patch("scripts.export_dashboard.DEFAULT_ANTIGRAVITY_DIR", empty_ag), \
             patch("src.vault.sync_subscription_to_vault"), \
             patch("src.vault.sync_conversations_to_vault"), \
             patch("scripts.export_dashboard.sync_weekly_trends_to_vault"):

            with warnings.catch_warnings(record=True) as recorded_warnings:
                warnings.simplefilter("always", ResourceWarning)
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    export_telemetry(
                        antigravity_dir=empty_ag,
                        dashboard_path=self.index_html,
                        dry_run=False,
                        no_live_quota=True,
                    )
                gc.collect()

                leak_warnings = [
                    w for w in recorded_warnings
                    if issubclass(w.category, ResourceWarning) and "unclosed database" in str(w.message)
                ]
                self.assertEqual(leak_warnings, [], f"Unclosed database connection detected: {leak_warnings}")

    def test_export_vault_sync_precedes_swarm_and_tool_analytics(self):
        """Verify that vault synchronization executes BEFORE extract_swarm_lineage and extract_tool_analytics (Feature 2 / intra-cycle freshness)."""
        empty_ag = self.temp_path / "ordering_ag"
        empty_ag.mkdir()
        (empty_ag / "conversations").mkdir()

        call_manager = MagicMock()
        with patch("scripts.export_dashboard.DEFAULT_ANTIGRAVITY_DIR", empty_ag), \
             patch("src.vault.sync_conversations_to_vault", call_manager.sync_conversations), \
             patch("src.vault.sync_subscription_to_vault", call_manager.sync_subscription), \
             patch("scripts.export_dashboard.sync_weekly_trends_to_vault", call_manager.sync_weekly_trends), \
             patch("scripts.export_dashboard.extract_swarm_lineage", call_manager.extract_swarm_lineage), \
             patch("scripts.export_dashboard.extract_tool_analytics", call_manager.extract_tool_analytics):

            call_manager.extract_swarm_lineage.return_value = []
            call_manager.extract_tool_analytics.return_value = {}

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                export_telemetry(
                    antigravity_dir=empty_ag,
                    dashboard_path=self.index_html,
                    dry_run=False,
                    no_live_quota=True,
                )

            recorded_calls = [call[0] for call in call_manager.mock_calls]
            self.assertIn("sync_conversations", recorded_calls)
            self.assertIn("extract_swarm_lineage", recorded_calls)
            self.assertIn("extract_tool_analytics", recorded_calls)

            sync_idx = recorded_calls.index("sync_conversations")
            swarm_idx = recorded_calls.index("extract_swarm_lineage")
            tool_idx = recorded_calls.index("extract_tool_analytics")

            self.assertLess(sync_idx, swarm_idx, "sync_conversations must be called BEFORE extract_swarm_lineage")
            self.assertLess(sync_idx, tool_idx, "sync_conversations must be called BEFORE extract_tool_analytics")

    def test_export_handles_conversation_vault_sync_sqlite_error_gracefully(self):
        """Verify that SQLite exceptions during conversation vault sync are caught gracefully without UnboundLocalError."""
        empty_ag = self.temp_path / "conv_sync_err_ag"
        empty_ag.mkdir()
        (empty_ag / "conversations").mkdir()
        isolated_vault = self.temp_path / "isolated_vault.db"

        with patch("scripts.export_dashboard.DEFAULT_ANTIGRAVITY_DIR", empty_ag), \
             patch("scripts.export_dashboard.DEFAULT_VAULT_PATH", isolated_vault), \
             patch("src.vault.sync_subscription_to_vault"), \
             patch("src.vault.sync_conversations_to_vault", side_effect=sqlite3.OperationalError("database is locked")), \
             patch("scripts.export_dashboard.sync_weekly_trends_to_vault"):

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as captured_err:
                payload = export_telemetry(
                    antigravity_dir=empty_ag,
                    dashboard_path=self.index_html,
                    dry_run=False,
                    no_live_quota=True,
                )

            err_msg = captured_err.getvalue()
            self.assertIn("[!] Warning: vault conversation sync failed: database is locked", err_msg)
            self.assertIsInstance(payload, dict)
            self.assertIn("summary", payload)
            self.assertTrue((self.dashboard_dir / "data.json").exists())

    def test_export_handles_weekly_trends_vault_sync_sqlite_error_gracefully(self):
        """Verify that SQLite exceptions during weekly trends vault sync are caught gracefully without UnboundLocalError."""
        empty_ag = self.temp_path / "trends_sync_err_ag"
        empty_ag.mkdir()
        (empty_ag / "conversations").mkdir()
        isolated_vault = self.temp_path / "isolated_vault.db"

        with patch("scripts.export_dashboard.DEFAULT_ANTIGRAVITY_DIR", empty_ag), \
             patch("scripts.export_dashboard.DEFAULT_VAULT_PATH", isolated_vault), \
             patch("src.vault.sync_subscription_to_vault"), \
             patch("src.vault.sync_conversations_to_vault"), \
             patch("scripts.export_dashboard.sync_weekly_trends_to_vault", side_effect=sqlite3.OperationalError("database is locked")):

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as captured_err:
                payload = export_telemetry(
                    antigravity_dir=empty_ag,
                    dashboard_path=self.index_html,
                    dry_run=False,
                    no_live_quota=True,
                )

            err_msg = captured_err.getvalue()
            self.assertIn("[!] Warning: vault weekly trends sync failed: database is locked", err_msg)
            self.assertIsInstance(payload, dict)
            self.assertIn("summary", payload)
            self.assertTrue((self.dashboard_dir / "data.json").exists())

    def test_export_handles_dual_vault_sync_sqlite_errors_gracefully(self):
        """Verify that multiple SQLite errors across both conversation and trends sync are caught and warned without aborting export."""
        empty_ag = self.temp_path / "dual_sync_err_ag"
        empty_ag.mkdir()
        (empty_ag / "conversations").mkdir()
        isolated_vault = self.temp_path / "isolated_vault.db"

        with patch("scripts.export_dashboard.DEFAULT_ANTIGRAVITY_DIR", empty_ag), \
             patch("scripts.export_dashboard.DEFAULT_VAULT_PATH", isolated_vault), \
             patch("src.vault.sync_subscription_to_vault"), \
             patch("src.vault.sync_conversations_to_vault", side_effect=sqlite3.OperationalError("convo db locked")), \
             patch("scripts.export_dashboard.sync_weekly_trends_to_vault", side_effect=sqlite3.OperationalError("trends db locked")):

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as captured_err:
                payload = export_telemetry(
                    antigravity_dir=empty_ag,
                    dashboard_path=self.index_html,
                    dry_run=False,
                    no_live_quota=True,
                )

            err_msg = captured_err.getvalue()
            self.assertIn("[!] Warning: vault conversation sync failed: convo db locked", err_msg)
            self.assertIn("[!] Warning: vault weekly trends sync failed: trends db locked", err_msg)
            self.assertIsInstance(payload, dict)
            self.assertIn("summary", payload)
            self.assertTrue((self.dashboard_dir / "data.json").exists())

    def test_no_shadowed_global_imports_in_export_dashboard(self):
        """Verify that no function in export_dashboard.py locally imports a module shadowing a global import (AST lint)."""
        import ast
        export_script = Path(__file__).resolve().parent.parent / "scripts" / "export_dashboard.py"
        with open(export_script, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(export_script))

        global_imports = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    global_imports.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    global_imports.add(alias.asname or alias.name)

        shadowed = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    name = None
                    if isinstance(child, ast.Import):
                        for alias in child.names:
                            name = alias.asname or alias.name
                    elif isinstance(child, ast.ImportFrom):
                        for alias in child.names:
                            name = alias.asname or alias.name
                    if name and name in global_imports:
                        shadowed.append((node.name, name, child.lineno))

        self.assertEqual(shadowed, [], f"Found local imports shadowing global imports in export_dashboard.py: {shadowed}")

    def test_export_enriches_session_tree_and_mode(self):
        """Verify that export_telemetry enriches conversations with tree rollups, session mode, and modes_summary."""
        empty_antigravity = self.temp_path / "antigravity"
        empty_antigravity.mkdir(exist_ok=True)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload = export_telemetry(
                antigravity_dir=empty_antigravity,
                dashboard_path=self.index_html,
                log_path=self.empty_log,
            )

        self.assertIn("modes_summary", payload)
        ms = payload["modes_summary"]
        self.assertIn("boost", ms)
        self.assertIn("teamwork", ms)
        self.assertIn("goal", ms)
        self.assertIn("standard", ms)
        self.assertIn("file_churn_sessions", ms)

        for convo in payload.get("conversations", []):
            self.assertIn("tree_total_input_tokens", convo)
            self.assertIn("tree_total_output_tokens", convo)
            self.assertIn("tree_total_thinking_tokens", convo)
            self.assertIn("tree_total_cost_usd", convo)
            self.assertIn("tree_children_count", convo)
            self.assertIn("has_children", convo)
            self.assertIn("child_ids", convo)
            self.assertIn("session_mode", convo)
            self.assertIn("has_file_churn", convo)

    def test_fast_tier_clamps_status_on_recent_429(self):
        """Verify export_fast_tier immediately transitions status to BURNING_AI_CREDITS and 0% remaining when log has recent 429."""
        import datetime
        from scripts.export_dashboard import export_fast_tier

        ag_dir = self.temp_path / "fast_429_ag"
        conv_dir = ag_dir / "conversations"
        conv_dir.mkdir(parents=True)
        db_file = conv_dir / "sess1.db"
        conn = sqlite3.connect(str(db_file))
        conn.execute("CREATE TABLE steps (idx INTEGER PRIMARY KEY, step_type INTEGER, metadata BLOB, step_payload BLOB)")
        conn.commit()
        conn.close()

        log_file = ag_dir / "language_server.log"
        log_file.write_text(
            "E1013 21:05:46.392701 38451 interceptor.go:74] RESOURCE_EXHAUSTED (code 429): You have exhausted your capacity\n",
            encoding="utf-8",
        )
        status_file = self.temp_path / "fast_status.json"
        ref_dt = datetime.datetime(2026, 10, 13, 21, 8, 0, tzinfo=datetime.timezone.utc)

        res = export_fast_tier(
            antigravity_dir=ag_dir,
            output_dir=self.dashboard_dir,
            status_path=status_file,
            active_db=db_file,
            reference_time=ref_dt,
            log_path=log_file,
        )
        self.assertEqual(res.get("status"), "success")
        status_data = json.loads(status_file.read_text(encoding="utf-8"))
        self.assertEqual(status_data.get("status"), "BURNING_AI_CREDITS")
        self.assertTrue(status_data.get("cooldown_active"))
        self.assertEqual(status_data.get("gemini_5h_remaining_pct"), 0.0)
        self.assertEqual(status_data.get("gemini_5h_pct"), 100.0)

    def test_early_status_hook_preserves_compaction_epoch(self):
        """Verify pre-Vault write_quota_status_file does not flicker compaction_epoch to 1."""
        import datetime
        import shutil
        from scripts.export_dashboard import clear_exporter_cache, write_quota_status_file
        from src.vault_schema import init_vault

        clear_exporter_cache()
        compact_ag = self.temp_path / "compact_ag"
        conv_dir = compact_ag / "conversations"
        conv_dir.mkdir(parents=True)

        fixture_db = Path(__file__).resolve().parent / "fixtures" / "antigravity" / "conversations" / "11111111-1111-1111-1111-111111111111.db"
        target_db = conv_dir / "11111111-1111-1111-1111-111111111111.db"
        shutil.copy2(fixture_db, target_db)

        conn = sqlite3.connect(str(target_db))
        conn.execute("INSERT INTO steps (idx, step_type, metadata) VALUES (3, 23, ?)", (b"Checkpoint 1",))
        conn.execute("INSERT INTO steps (idx, step_type, metadata) VALUES (4, 23, ?)", (b"Checkpoint 2",))
        conn.commit()
        conn.close()

        vault_file = compact_ag / "vault.db"
        vconn = init_vault(vault_file)
        vconn.execute(
            """
            INSERT INTO steps_archive (
                convo_id, step_idx, step_type, timestamp, model_id, model_name, status,
                prompt_tokens_uncached, cached_tokens, total_input_tokens, output_tokens_total, thinking_tokens, payload_text
            ) VALUES (?, 3, 23, '2026-09-05T13:26:00+00:00', '1437', 'Gemini 4 Carbon (Medium)', 3, 2329, 254791, 257120, 5800, 0, '<CONTEXT_SUMMARY>')
            """,
            ("11111111-1111-1111-1111-111111111111",),
        )
        vconn.execute(
            """
            INSERT INTO steps_archive (
                convo_id, step_idx, step_type, timestamp, model_id, model_name, status,
                prompt_tokens_uncached, cached_tokens, total_input_tokens, output_tokens_total, thinking_tokens, payload_text
            ) VALUES (?, 4, 23, '2026-09-05T13:28:00+00:00', '1437', 'Gemini 4 Carbon (Medium)', 3, 6788, 253825, 260613, 8625, 3132, '<CONTEXT_SUMMARY>')
            """,
            ("11111111-1111-1111-1111-111111111111",),
        )
        vconn.commit()
        vconn.close()

        status_file = self.temp_path / "early_epoch_status.json"
        ref_dt = datetime.datetime(2026, 9, 5, 14, 30, 0, tzinfo=datetime.timezone.utc)
        written_snapshots = []

        def _spy_write_status(payload_arg, status_path=None, watcher_info=None):
            out_path = write_quota_status_file(payload_arg, status_path=status_path, watcher_info=watcher_info)
            written_snapshots.append(json.loads(out_path.read_text(encoding="utf-8")))
            return out_path

        with patch("scripts.export_dashboard.write_quota_status_file", side_effect=_spy_write_status):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                export_telemetry(
                    antigravity_dir=compact_ag,
                    dashboard_path=self.index_html,
                    log_path=self.empty_log,
                    status_path=status_file,
                    reference_time=ref_dt,
                    no_live_quota=True,
                )

        self.assertEqual(len(written_snapshots), 2)
        early_snap, final_snap = written_snapshots[0], written_snapshots[1]
        self.assertEqual(early_snap.get("compaction_epoch"), 3)
        self.assertEqual(early_snap.get("current_session", {}).get("compaction_epoch"), 3)
        self.assertEqual(final_snap.get("compaction_epoch"), 3)
        self.assertEqual(final_snap.get("current_session", {}).get("compaction_epoch"), 3)


if __name__ == "__main__":
    unittest.main()
