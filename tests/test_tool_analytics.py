"""
Unit test suite for Tool Execution & Skill Performance Analytics Engine.
"""

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.tool_analytics import (
    classify_tool_category,
    extract_tool_analytics,
    is_error_result,
    is_sandbox_bypass,
)
from src.vault import init_vault


class TestToolAnalytics(unittest.TestCase):
    """Test suite for tool analytics aggregation and heuristics."""

    def test_classify_tool_category(self):
        """Test tool categorization."""
        self.assertEqual(classify_tool_category("run_command"), "terminal")
        self.assertEqual(classify_tool_category("manage_task"), "terminal")
        self.assertEqual(classify_tool_category("view_file"), "filesystem")
        self.assertEqual(classify_tool_category("write_to_file"), "filesystem")
        self.assertEqual(classify_tool_category("invoke_subagent"), "subagents")
        self.assertEqual(classify_tool_category("send_message"), "subagents")
        self.assertEqual(classify_tool_category("search_web"), "web")
        self.assertEqual(classify_tool_category("ask_question"), "interactive")
        self.assertEqual(classify_tool_category("mcp_custom_tool"), "mcp")
        self.assertEqual(classify_tool_category("custom_unknown"), "other")

    def test_is_sandbox_bypass(self):
        """Test sandbox bypass detection."""
        self.assertTrue(is_sandbox_bypass('{"CommandLine":"ls","BypassSandbox": true}'))
        self.assertTrue(is_sandbox_bypass('{"CommandLine":"ls","BypassSandbox":true}'))
        self.assertFalse(is_sandbox_bypass('{"CommandLine":"ls","BypassSandbox": false}'))
        self.assertFalse(is_sandbox_bypass('{"CommandLine":"ls"}'))
        self.assertFalse(is_sandbox_bypass(None))

    def test_is_error_result(self):
        """Test error detection heuristic in tool results."""
        self.assertFalse(is_error_result("The command exited with code 0.\nOutput:\nHello world"))
        self.assertTrue(is_error_result("The command exited with code 1.\nOutput:\nError: file not found"))
        self.assertTrue(is_error_result("fatal: unable to access '/Users/...': Operation not permitted"))
        self.assertTrue(is_error_result("Traceback (most recent call last):\n  File 'test.py', line 1"))
        self.assertFalse(is_error_result("Created the following subagents:\n{\"conversationId\":\"abc\"}"))
        self.assertFalse(is_error_result(None))

    def test_extract_tool_analytics_with_mock_vault(self):
        """Test aggregation with a mock vault SQLite database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            v_path = Path(tmpdir) / "test_vault.db"
            conn = init_vault(v_path)
            cur = conn.cursor()

            # Insert tool calls
            cur.execute(
                """
                INSERT INTO tool_calls_archive (convo_id, step_idx, tool_name, arguments_json, result_summary, timestamp)
                VALUES
                ('c1', 1, 'run_command', '{"CommandLine": "ls", "BypassSandbox": true}', 'The command exited with code 0.', '2026-09-12T10:00:00Z'),
                ('c1', 2, 'run_command', '{"CommandLine": "git status"}', 'The command exited with code 128.\nfatal: not a git repo', '2026-09-12T10:01:00Z'),
                ('c1', 3, 'view_file', '{"AbsolutePath": "/foo/bar.py"}', 'File contents: print("hello")', '2026-09-12T10:02:00Z'),
                ('c1', 4, 'invoke_subagent', '{"Subagents": []}', 'Created the following subagents', '2026-09-12T10:03:00Z')
                """
            )

            # Insert skills
            cur.execute(
                """
                INSERT INTO skills_archive (convo_id, step_idx, skill_name, skill_path, activation_type, timestamp)
                VALUES
                ('c1', 1, 'credit-statement-ingest', 'skills/credit-statement-ingest/SKILL.md', 'referenced', '2026-09-12T10:00:00Z'),
                ('c1', 2, 'credit-statement-ingest', 'skills/credit-statement-ingest/SKILL.md', 'referenced', '2026-09-12T10:01:00Z'),
                ('c1', 3, 'vdone', 'skills/vdone/SKILL.md', 'referenced', '2026-09-12T10:02:00Z')
                """
            )
            conn.commit()
            conn.close()

            res = extract_tool_analytics(vault_path=v_path)
            self.assertEqual(res["total_tool_calls"], 4)
            self.assertEqual(res["unique_tools_count"], 3)

            rc = res["tools"]["run_command"]
            self.assertEqual(rc["call_count"], 2)
            self.assertEqual(rc["frequency_pct"], 50.0)
            self.assertEqual(rc["sandbox_bypass_count"], 1)
            self.assertEqual(rc["sandbox_bypass_pct"], 50.0)
            self.assertEqual(rc["error_count"], 1)
            self.assertEqual(rc["error_rate_pct"], 50.0)

            vf = res["tools"]["view_file"]
            self.assertEqual(vf["call_count"], 1)
            self.assertEqual(vf["error_count"], 0)
            self.assertEqual(vf["error_rate_pct"], 0.0)

            # Categories
            self.assertIn("terminal", res["categories"])
            self.assertEqual(res["categories"]["terminal"]["call_count"], 2)
            self.assertIn("filesystem", res["categories"])

            # Skills
            self.assertEqual(res["total_skill_activations"], 3)
            self.assertEqual(len(res["skills"]), 2)
            self.assertEqual(res["skills"][0]["skill_name"], "credit-statement-ingest")
            self.assertEqual(res["skills"][0]["activation_count"], 2)

    def test_missing_vault_graceful(self):
        """Test missing vault gracefully returns default structure."""
        res = extract_tool_analytics(vault_path="/non/existent/vault.db")
        self.assertEqual(res["total_tool_calls"], 0)
        self.assertEqual(res["tools"], {})


if __name__ == "__main__":
    unittest.main()
