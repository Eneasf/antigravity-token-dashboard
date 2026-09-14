"""
Unit test suite for Subagent Swarm Lineage & Economics Engine.
"""

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.swarm import (
    build_swarms_summary,
    classify_subagent_tier,
    extract_swarm_lineage,
    format_duration,
    TIER_ARCHITECTURE,
    TIER_ENGINEERING,
    TIER_MECHANICAL,
    TIER_OTHER,
)
from src.vault import init_vault


class TestSwarmLineage(unittest.TestCase):
    """Test suite for swarm lineage extraction and economics."""

    def test_classify_subagent_tier(self):
        """Test tier classification across model IDs and alias strings."""
        self.assertEqual(classify_subagent_tier("1050"), TIER_MECHANICAL)
        self.assertEqual(classify_subagent_tier("flash_lite"), TIER_MECHANICAL)
        self.assertEqual(classify_subagent_tier("gemini-flash-lite"), TIER_MECHANICAL)

        self.assertEqual(classify_subagent_tier("1322"), TIER_ENGINEERING)
        self.assertEqual(classify_subagent_tier("flash"), TIER_ENGINEERING)

        self.assertEqual(classify_subagent_tier("1036"), TIER_ARCHITECTURE)
        self.assertEqual(classify_subagent_tier("1016"), TIER_ARCHITECTURE)
        self.assertEqual(classify_subagent_tier("pro"), TIER_ARCHITECTURE)

        self.assertEqual(classify_subagent_tier("inherit"), TIER_OTHER)
        self.assertEqual(classify_subagent_tier(None), TIER_OTHER)
        self.assertEqual(classify_subagent_tier("unknown-model"), TIER_OTHER)

    def test_format_duration(self):
        """Test human-readable duration formatting."""
        self.assertEqual(format_duration(45), "45s")
        self.assertEqual(format_duration(120), "2m")
        self.assertEqual(format_duration(125), "2m 5s")
        self.assertEqual(format_duration(3660), "1h 1m")
        self.assertEqual(format_duration(-10), "0s")

    def test_extract_swarm_with_mock_vault(self):
        """Test swarm extraction and economics calculation against a controlled mock vault."""
        with tempfile.TemporaryDirectory() as tmpdir:
            v_path = Path(tmpdir) / "test_vault.db"
            conn = init_vault(v_path)
            cur = conn.cursor()

            root_id = "11111111-2222-3333-4444-555555555555"
            child1_id = "66666666-7777-8888-9999-000000000001"
            child2_id = "66666666-7777-8888-9999-000000000002"

            # 1. Insert conversations_archive
            cur.execute(
                """
                INSERT INTO conversations_archive (
                    convo_id, parent_convo_id, workspace_name, title,
                    turn_count, total_input_tokens, total_output_tokens,
                    estimated_cost_usd, first_turn_ts, last_turn_ts
                ) VALUES
                (?, NULL, 'Test Workspace', 'Lead Architect Task', 10, 50000, 5000, 0.25, '2026-09-12T10:00:00Z', '2026-09-12T10:30:00Z'),
                (?, ?, 'Test Workspace', 'Mechanical Task Worker', 5, 20000, 2000, 0.05, '2026-09-12T10:05:00Z', '2026-09-12T10:15:00Z'),
                (?, ?, 'Test Workspace', 'Engineering Feature Worker', 8, 40000, 4000, 0.15, '2026-09-12T10:10:00Z', '2026-09-12T10:25:00Z')
                """,
                (root_id, child1_id, root_id, child2_id, root_id),
            )

            # 2. Insert invoke_subagent tool call in root
            invoke_args = {
                "Subagents": [
                    {"Model": "flash_lite", "Role": "Mechanical Worker", "TypeName": "self"},
                    {"Model": "flash", "Role": "Engineering Specialist", "TypeName": "self"},
                ]
            }
            invoke_res = f"Created subagents:\n{{\"conversationId\": \"{child1_id}\"}}\n{{\"conversationId\": \"{child2_id}\"}}"
            cur.execute(
                """
                INSERT INTO tool_calls_archive (
                    convo_id, step_idx, tool_name, arguments_json, result_summary, timestamp
                ) VALUES (?, 1, 'invoke_subagent', ?, ?, '2026-09-12T10:02:00Z')
                """,
                (root_id, json.dumps(invoke_args), invoke_res),
            )

            # 3. Insert dominant models in steps_archive
            cur.execute(
                """
                INSERT INTO steps_archive (convo_id, step_idx, model_id, model_name) VALUES
                (?, 1, '1318', 'Gemini 3.8 Flash (High)'),
                (?, 1, '1050', 'Gemini Flash Lite (Subagent)'),
                (?, 1, '1322', 'Gemini Fast Agent Assistant')
                """,
                (root_id, child1_id, child2_id),
            )

            conn.commit()
            conn.close()

            swarms = extract_swarm_lineage(vault_path=v_path)
            self.assertEqual(len(swarms), 1)

            s = swarms[0]
            self.assertEqual(s["swarm_id"], root_id)
            self.assertEqual(s["subagents_count"], 2)
            self.assertEqual(s["total_turns"], 23)  # 10 + 5 + 8
            self.assertEqual(s["total_swarm_tokens"], 121000)  # (50+5)k + (20+2)k + (40+4)k = 55k+22k+44k = 121k
            self.assertAlmostEqual(s["total_swarm_cost_usd"], 0.45, places=2)  # 0.25 + 0.05 + 0.15 = 0.45
            self.assertEqual(s["duration_seconds"], 1800.0)  # 10:00 to 10:30 = 30m = 1800s

            # Verify token and cost segregation metrics
            self.assertEqual(s["total_input_tokens"], 110000)
            self.assertEqual(s["total_output_tokens"], 11000)
            self.assertEqual(s["tokens_per_turn"], round(121000 / 23))
            self.assertEqual(s["avoided_cost_usd"], s["total_swarm_cost_usd"])
            self.assertEqual(s["actual_overage_credits"], 0)
            self.assertEqual(s["is_overage"], False)

            # Verify tier breakdown
            tb = s["tier_breakdown"]
            self.assertEqual(tb[TIER_MECHANICAL]["count"], 1)
            self.assertEqual(tb[TIER_MECHANICAL]["tokens"], 22000)
            self.assertEqual(tb[TIER_ENGINEERING]["count"], 1)
            self.assertEqual(tb[TIER_ENGINEERING]["tokens"], 44000)
            self.assertEqual(tb[TIER_ARCHITECTURE]["count"], 0)

            # Verify nodes and edges
            self.assertEqual(len(s["nodes"]), 3)
            self.assertEqual(len(s["edges"]), 2)
            self.assertEqual(s["nodes"][0]["role"], "Root Orchestrator")
            self.assertEqual(s["nodes"][1]["role"], "Mechanical Worker")
            self.assertEqual(s["nodes"][2]["role"], "Engineering Specialist")

            # Verify portfolio summary
            summary = build_swarms_summary(swarms)
            self.assertEqual(summary["total_swarms"], 1)
            self.assertEqual(summary["total_subagents"], 2)
            self.assertEqual(summary["total_swarm_tokens"], 121000)
            self.assertEqual(summary["total_avoided_cost_usd"], s["avoided_cost_usd"])
            self.assertEqual(summary["total_overage_credits"], 0)
            self.assertEqual(summary["unique_projects"], ["Test Workspace"])

    def test_true_roots_deduplication(self):
        """Verify that intermediate subagents spawning subsequent children do not produce duplicate swarms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            v_path = Path(tmpdir) / "test_vault.db"
            conn = init_vault(v_path)
            cur = conn.cursor()

            root_id = "00000000-0000-0000-0000-000000000001"
            sub_id = "00000000-0000-0000-0000-000000000002"
            leaf1_id = "00000000-0000-0000-0000-000000000003"
            leaf2_id = "00000000-0000-0000-0000-000000000004"

            cur.execute(
                """
                INSERT INTO conversations_archive (convo_id, parent_convo_id, workspace_name, title, turn_count, total_input_tokens, total_output_tokens, estimated_cost_usd)
                VALUES
                (?, NULL, 'Workspace A', 'Top Orchestrator', 5, 10000, 1000, 0.10),
                (?, ?, 'Workspace A', 'Intermediate Manager', 5, 20000, 2000, 0.20),
                (?, ?, 'Workspace A', 'Leaf Worker 1', 3, 5000, 500, 0.05),
                (?, ?, 'Workspace A', 'Leaf Worker 2', 3, 5000, 500, 0.05)
                """,
                (root_id, sub_id, root_id, leaf1_id, sub_id, leaf2_id, sub_id),
            )

            # Root calls sub
            cur.execute(
                """
                INSERT INTO tool_calls_archive (convo_id, step_idx, tool_name, arguments_json, result_summary)
                VALUES (?, 1, 'invoke_subagent', ?, ?)
                """,
                (root_id, json.dumps({"Subagents": [{"Model": "pro", "Role": "Manager"}]}), f'{{"conversationId": "{sub_id}"}}')
            )
            # Sub calls 2 leaves
            cur.execute(
                """
                INSERT INTO tool_calls_archive (convo_id, step_idx, tool_name, arguments_json, result_summary)
                VALUES (?, 1, 'invoke_subagent', ?, ?)
                """,
                (sub_id, json.dumps({"Subagents": [{"Model": "flash_lite", "Role": "W1"}, {"Model": "flash_lite", "Role": "W2"}]}), f'{{"conversationId": "{leaf1_id}"}}\n{{"conversationId": "{leaf2_id}"}}')
            )
            conn.commit()
            conn.close()

            swarms = extract_swarm_lineage(vault_path=v_path)
            # Must return exactly 1 deduplicated swarm rooted at top orchestrator, not 2
            self.assertEqual(len(swarms), 1)
            self.assertEqual(swarms[0]["swarm_id"], root_id)
            self.assertEqual(swarms[0]["subagents_count"], 3)  # sub, leaf1, leaf2
            self.assertEqual(len(swarms[0]["nodes"]), 4)  # root + 3 descendants

    def test_missing_vault_graceful(self):
        """Test that missing vault path gracefully returns empty list."""
        swarms = extract_swarm_lineage(vault_path="/non/existent/vault.db")
        self.assertEqual(swarms, [])


if __name__ == "__main__":
    unittest.main()
