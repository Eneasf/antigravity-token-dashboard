"""
Unit test suite for Subagent Swarm Lineage & Economics Engine.
"""

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.aggregator import (
    classify_session_mode,
    detect_file_churn,
    is_session_file_churn,
)
from src.swarm import (
    build_swarms_summary,
    classify_subagent_tier,
    compute_recursive_session_rollups,
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
        self.assertEqual(classify_subagent_tier("1669"), TIER_ENGINEERING)
        self.assertEqual(classify_subagent_tier("flash"), TIER_ENGINEERING)

        self.assertEqual(classify_subagent_tier("1036"), TIER_ARCHITECTURE)
        self.assertEqual(classify_subagent_tier("1667"), TIER_ARCHITECTURE)
        self.assertEqual(classify_subagent_tier("1681"), TIER_ARCHITECTURE)
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

    def test_extract_swarm_lineage_single_invoke_and_root_priority(self):
        """Verify single-subagent invoke_subagent and root priority when legacy poisoned cycle exists."""
        import src.swarm as swarm_mod

        with tempfile.TemporaryDirectory() as tmpdir:
            v_path = Path(tmpdir) / "test_vault.db"
            conn = init_vault(v_path)
            cur = conn.cursor()

            root_id = "6e8b5b79-fce9-48f0-9ede-cc0a17dfda18"
            child_id = "a26a5649-d88d-49f4-9df6-749bcaad484d"

            cur.execute(
                """
                INSERT INTO conversations_archive (
                    convo_id, parent_convo_id, title, is_subagent, agent_name, subagent_role,
                    turn_count, total_input_tokens, total_output_tokens
                ) VALUES
                (?, ?, 'Full-Stack Codebase Size Audit', 0, 'default', '', 12, 50000, 2000),
                (?, ?, 'Conversation a26a5649', 1, 'DeepInvestigator', 'Backend and Frontend File Size & Modularity Investigator', 6, 30000, 1000)
                """,
                (root_id, child_id, child_id, root_id),
            )

            cur.execute(
                """
                INSERT INTO tool_calls_archive (
                    convo_id, step_idx, tool_name, arguments_json, result_summary
                ) VALUES (?, 1, 'invoke_subagent', ?, ?)
                """,
                (
                    root_id,
                    json.dumps({
                        "TypeName": "DeepInvestigator",
                        "Role": "Backend and Frontend File Size & Modularity Investigator",
                        "Model": "inherit",
                    }),
                    f'{{"conversationId": "{child_id}"}}',
                ),
            )
            conn.commit()
            conn.close()

            swarms = extract_swarm_lineage(vault_path=v_path)
            self.assertEqual(len(swarms), 1)
            self.assertEqual(
                swarms[0].get("root_id") or swarms[0].get("root_convo_id") or swarms[0].get("swarm_id"),
                root_id,
            )
            self.assertEqual(swarms[0]["root_title"], "Full-Stack Codebase Size Audit")
            self.assertEqual(
                swarms[0].get("subagent_count", swarms[0].get("subagents_count")),
                1,
            )

            rollup_fn = getattr(swarm_mod, "rollup_subagent_trees", compute_recursive_session_rollups)
            convs = [
                {
                    "convo_id": root_id,
                    "title": "Full-Stack Codebase Size Audit",
                    "is_subagent": False,
                    "parent_convo_id": "",
                },
                {
                    "convo_id": child_id,
                    "title": "Conversation a26a5649",
                    "is_subagent": True,
                    "parent_convo_id": root_id,
                },
            ]
            rollup_fn(convs, lineage_data=swarms)
            root_conv = [c for c in convs if c["convo_id"] == root_id][0]
            self.assertFalse(root_conv["is_subagent"])
            self.assertEqual(root_conv["parent_convo_id"], "")


class TestSessionTreeRollup(unittest.TestCase):
    """Test suite for recursive session tree rollups."""

    def test_leaf_node_rollup(self):
        """Verify leaf node rollups equal own metrics and direct children is empty."""
        convos = [
            {
                "convo_id": "session-standalone",
                "total_input_tokens": 1000,
                "total_output_tokens": 500,
                "thinking_tokens": 100,
                "estimated_cost_usd": 0.05,
            }
        ]
        result = compute_recursive_session_rollups(convos)
        c = result[0]
        self.assertEqual(c["tree_total_input_tokens"], 1000)
        self.assertEqual(c["tree_total_output_tokens"], 500)
        self.assertEqual(c["tree_total_thinking_tokens"], 100)
        self.assertEqual(c["tree_total_cost_usd"], 0.05)
        self.assertEqual(c["tree_children_count"], 0)
        self.assertFalse(c["has_children"])
        self.assertEqual(c["child_ids"], [])

    def test_multilevel_tree_rollup(self):
        """Verify multi-level tree rollup across root -> child1 -> grandchild, root -> child2."""
        convos = [
            {
                "convo_id": "root",
                "total_input_tokens": 100,
                "total_output_tokens": 50,
                "thinking_tokens": 10,
                "estimated_cost_usd": 0.10,
            },
            {
                "convo_id": "child1",
                "parent_convo_id": "root",
                "total_input_tokens": 200,
                "total_output_tokens": 80,
                "thinking_tokens": 20,
                "estimated_cost_usd": 0.20,
            },
            {
                "convo_id": "child2",
                "parent_convo_id": "root",
                "total_input_tokens": 300,
                "total_output_tokens": 90,
                "thinking_tokens": 30,
                "estimated_cost_usd": 0.30,
            },
            {
                "convo_id": "grandchild1",
                "parent_convo_id": "child1",
                "total_input_tokens": 400,
                "total_output_tokens": 100,
                "thinking_tokens": 40,
                "estimated_cost_usd": 0.40,
            },
        ]
        compute_recursive_session_rollups(convos)
        cmap = {c["convo_id"]: c for c in convos}

        # Check grandchild (leaf)
        gc = cmap["grandchild1"]
        self.assertEqual(gc["tree_children_count"], 0)
        self.assertFalse(gc["has_children"])
        self.assertEqual(gc["child_ids"], [])
        self.assertEqual(gc["tree_total_input_tokens"], 400)
        self.assertEqual(gc["tree_total_output_tokens"], 100)
        self.assertEqual(gc["tree_total_thinking_tokens"], 40)
        self.assertEqual(gc["tree_total_cost_usd"], 0.40)

        # Check child1 (intermediate node with 1 descendant)
        c1 = cmap["child1"]
        self.assertEqual(c1["tree_children_count"], 1)
        self.assertTrue(c1["has_children"])
        self.assertEqual(c1["child_ids"], ["grandchild1"])
        self.assertEqual(c1["tree_total_input_tokens"], 200 + 400)
        self.assertEqual(c1["tree_total_output_tokens"], 80 + 100)
        self.assertEqual(c1["tree_total_thinking_tokens"], 20 + 40)
        self.assertEqual(c1["tree_total_cost_usd"], 0.60)

        # Check child2 (leaf)
        c2 = cmap["child2"]
        self.assertEqual(c2["tree_children_count"], 0)
        self.assertFalse(c2["has_children"])
        self.assertEqual(c2["child_ids"], [])

        # Check root (top orchestrator with 3 descendants: child1, child2, grandchild1)
        r = cmap["root"]
        self.assertEqual(r["tree_children_count"], 3)
        self.assertTrue(r["has_children"])
        self.assertEqual(sorted(r["child_ids"]), ["child1", "child2"])
        self.assertEqual(r["tree_total_input_tokens"], 100 + 200 + 300 + 400)
        self.assertEqual(r["tree_total_output_tokens"], 50 + 80 + 90 + 100)
        self.assertEqual(r["tree_total_thinking_tokens"], 10 + 20 + 30 + 40)
        self.assertEqual(r["tree_total_cost_usd"], 1.00)

    def test_cycle_prevention(self):
        """Verify cycle in parent-child relationships does not cause infinite loop."""
        convos = [
            {
                "convo_id": "nodeA",
                "parent_convo_id": "nodeB",
                "total_input_tokens": 100,
                "total_output_tokens": 10,
                "thinking_tokens": 0,
                "estimated_cost_usd": 0.01,
            },
            {
                "convo_id": "nodeB",
                "parent_convo_id": "nodeA",
                "total_input_tokens": 200,
                "total_output_tokens": 20,
                "thinking_tokens": 0,
                "estimated_cost_usd": 0.02,
            },
            {
                "convo_id": "nodeSelf",
                "parent_convo_id": "nodeSelf",
                "total_input_tokens": 50,
                "total_output_tokens": 5,
                "thinking_tokens": 0,
                "estimated_cost_usd": 0.005,
            },
        ]
        # Must terminate safely without recursion or hang
        compute_recursive_session_rollups(convos)
        cmap = {c["convo_id"]: c for c in convos}
        self.assertIn("nodeA", cmap)
        self.assertIn("nodeB", cmap)
        self.assertIn("nodeSelf", cmap)
        self.assertEqual(cmap["nodeSelf"]["tree_children_count"], 0)
        self.assertEqual(cmap["nodeSelf"]["child_ids"], [])

    def test_dict_input(self):
        """Verify compute_recursive_session_rollups accepts dictionary mapping ID -> convo."""
        convos_dict = {
            "p1": {"convo_id": "p1", "total_input_tokens": 50, "total_output_tokens": 10, "thinking_tokens": 0, "estimated_cost_usd": 0.01},
            "c1": {"convo_id": "c1", "parent_convo_id": "p1", "total_input_tokens": 50, "total_output_tokens": 10, "thinking_tokens": 0, "estimated_cost_usd": 0.01},
        }
        res = compute_recursive_session_rollups(convos_dict)
        self.assertIsInstance(res, dict)
        self.assertEqual(res["p1"]["tree_children_count"], 1)
        self.assertEqual(res["p1"]["tree_total_input_tokens"], 100)

    def test_lineage_data_swarms(self):
        """Verify rollups when parent-child relationships are supplied via lineage_data edges."""
        convos = [
            {"convo_id": "orch", "total_input_tokens": 100, "total_output_tokens": 20, "thinking_tokens": 5, "estimated_cost_usd": 0.02},
            {"convo_id": "worker", "total_input_tokens": 100, "total_output_tokens": 20, "thinking_tokens": 5, "estimated_cost_usd": 0.02},
        ]
        lineage = [
            {
                "root_convo_id": "orch",
                "edges": [{"source": "orch", "target": "worker"}],
            }
        ]
        compute_recursive_session_rollups(convos, lineage_data=lineage)
        cmap = {c["convo_id"]: c for c in convos}
        self.assertEqual(cmap["orch"]["tree_children_count"], 1)
        self.assertEqual(cmap["orch"]["child_ids"], ["worker"])
        self.assertEqual(cmap["orch"]["tree_total_input_tokens"], 200)

    def test_lineage_data_swarms_summary_dict(self):
        """Verify swarms summary dictionary ({'swarms': [...]}) works properly as lineage_data."""
        convos = [
            {"convo_id": "r1", "total_input_tokens": 100},
            {"convo_id": "c1", "total_input_tokens": 50},
        ]
        swarms_summary = {
            "total_swarms": 1,
            "swarms": [
                {
                    "root_convo_id": "r1",
                    "edges": [{"source": "r1", "target": "c1"}],
                }
            ],
        }
        compute_recursive_session_rollups(convos, lineage_data=swarms_summary)
        cmap = {c["convo_id"]: c for c in convos}
        self.assertEqual(cmap["r1"]["tree_children_count"], 1)
        self.assertEqual(cmap["r1"]["child_ids"], ["c1"])
        self.assertEqual(cmap["r1"]["tree_total_input_tokens"], 150)

    def test_diamond_dag_convergence(self):
        """Verify DAG diamond convergence (A -> B -> D, A -> C -> D) counts shared descendant once."""
        convos = [
            {"convo_id": "nodeA", "total_input_tokens": 100, "estimated_cost_usd": 0.10},
            {"convo_id": "nodeB", "parent_convo_id": "nodeA", "total_input_tokens": 50, "estimated_cost_usd": 0.05},
            {"convo_id": "nodeC", "parent_convo_id": "nodeA", "total_input_tokens": 50, "estimated_cost_usd": 0.05},
            {"convo_id": "nodeD", "total_input_tokens": 25, "estimated_cost_usd": 0.025},
        ]
        lineage = [
            {"source": "nodeB", "target": "nodeD"},
            {"source": "nodeC", "target": "nodeD"},
        ]
        compute_recursive_session_rollups(convos, lineage_data=lineage)
        cmap = {c["convo_id"]: c for c in convos}
        nA = cmap["nodeA"]
        self.assertEqual(sorted(nA["child_ids"]), ["nodeB", "nodeC"])
        self.assertEqual(nA["tree_children_count"], 3)  # nodeB, nodeC, nodeD (counted once)
        self.assertEqual(nA["tree_total_input_tokens"], 100 + 50 + 50 + 25)
        self.assertEqual(nA["tree_total_cost_usd"], 0.225)

    def test_robustness_none_and_invalid_values(self):
        """Verify compute_recursive_session_rollups handles None items and invalid token literals gracefully."""
        convos = [
            None,
            {
                "convo_id": "c1",
                "total_input_tokens": "invalid",
                "total_output_tokens": None,
                "thinking_tokens": None,
                "estimated_cost_usd": "not-a-number",
            },
        ]
        res = compute_recursive_session_rollups(convos)
        c1 = [c for c in res if c and c.get("convo_id") == "c1"][0]
        self.assertEqual(c1["tree_total_input_tokens"], 0)
        self.assertEqual(c1["tree_total_output_tokens"], 0)
        self.assertEqual(c1["tree_total_thinking_tokens"], 0)
        self.assertEqual(c1["tree_total_cost_usd"], 0.0)

    def test_lineage_nodes_with_none_tokens(self):
        """Verify lineage node with None tokens/cost does not raise TypeError."""
        convs = [{"convo_id": "root", "total_input_tokens": 100}]
        lineage = [{"nodes": [{"id": "sub1", "parent_id": "root", "thinking_tokens": None, "cost_usd": None}]}]
        compute_recursive_session_rollups(convs, lineage_data=lineage)
        self.assertEqual(convs[0]["tree_children_count"], 1)
        self.assertEqual(convs[0]["tree_total_thinking_tokens"], 0)

    def test_empty_conversations(self):
        """Verify empty conversations list and dict return empty."""
        self.assertEqual(compute_recursive_session_rollups([]), [])
        self.assertEqual(compute_recursive_session_rollups({}), {})
        self.assertEqual(compute_recursive_session_rollups(None), [])


class TestSessionModeClassifier(unittest.TestCase):
    """Test suite for session mode classification."""

    def test_explicit_boost_slash_command(self):
        """Verify /boost or \\boost in user prompt classifies as boost mode."""
        self.assertEqual(classify_session_mode({}, steps_archive_records=["/boost optimize database"]), "boost")
        self.assertEqual(classify_session_mode({}, steps_archive_records=[r"\boost refactor UI"]), "boost")
        self.assertEqual(classify_session_mode({"title": "/boost performance test"}), "boost")
        self.assertEqual(classify_session_mode({"prompt": "please run with /boost"}), "boost")
        self.assertEqual(classify_session_mode({}, steps_archive_records=[{"step_type": 14, "payload_text": "/boost mode"}]), "boost")

    def test_explicit_teamwork_slash_command(self):
        """Verify /teamwork or \\teamwork in prompt classifies as teamwork mode."""
        self.assertEqual(classify_session_mode({}, steps_archive_records=["/teamwork audit security"]), "teamwork")
        self.assertEqual(classify_session_mode({}, steps_archive_records=[r"\teamwork deploy fleet"]), "teamwork")
        self.assertEqual(classify_session_mode({}, steps_archive_records=["/teamwork-preview test"]), "teamwork")
        self.assertEqual(classify_session_mode({"title": "/teamwork swarm"}), "teamwork")

    def test_explicit_goal_slash_command(self):
        """Verify /goal or \\goal in prompt classifies as goal mode."""
        self.assertEqual(classify_session_mode({}, steps_archive_records=["/goal fix all linter bugs"]), "goal")
        self.assertEqual(classify_session_mode({}, steps_archive_records=[r"\goal pass integration"]), "goal")
        self.assertEqual(classify_session_mode({"title": "/goal marathon milestone"}), "goal")

    def test_url_paths_do_not_trigger_slash_commands(self):
        """Verify URLs containing /boost or /goal do not trigger mode classification."""
        self.assertEqual(classify_session_mode({"prompt": "See https://github.com/project/boost for details"}), "standard")
        self.assertEqual(classify_session_mode({"prompt": "POST to https://api.com/v1/goal"}), "standard")
        self.assertEqual(classify_session_mode({"prompt": "Visit https://app.slack.com/teamwork"}), "standard")

    def test_heuristic_teamwork_subagents(self):
        """Verify swarm lineage with >= 2 subagents classifies as teamwork mode when prompt text is unavailable."""
        self.assertEqual(classify_session_mode({"subagents_count": 2, "turn_count": 10}), "teamwork")
        self.assertEqual(classify_session_mode({"tree_children_count": 5, "turn_count": 10}), "teamwork")
        self.assertEqual(classify_session_mode({"child_ids": ["c1", "c2"], "turn_count": 10}), "teamwork")

    def test_subagents_heuristic_prefers_max(self):
        """Verify subagents heuristic takes maximum across subagents_count, tree_children_count, child_ids."""
        # 1 direct child, but 2 total tree children: should classify as teamwork
        self.assertEqual(classify_session_mode({"subagents_count": 1, "tree_children_count": 2}), "teamwork")

    def test_heuristic_goal_marathon(self):
        """Verify marathon session with >= 300 turns classifies as goal mode."""
        self.assertEqual(classify_session_mode({"turn_count": 300, "subagents_count": 0}), "goal")
        self.assertEqual(classify_session_mode({"turn_count": 500, "subagents_count": 0}), "goal")

    def test_heuristic_boost_high_thinking(self):
        """Verify high thinking-to-output ratio (>= 0.30) classifies as boost mode."""
        convo = {
            "turn_count": 20,
            "subagents_count": 0,
            "thinking_tokens": 6000,
            "total_output_tokens": 12000,  # 50% thinking ratio
        }
        self.assertEqual(classify_session_mode(convo), "boost")

    def test_none_values_resilience(self):
        """Verify classify_session_mode does not crash on None fields."""
        self.assertEqual(classify_session_mode({"child_ids": None}), "standard")
        self.assertEqual(classify_session_mode({"thinking_tokens": None, "total_output_tokens": None}), "standard")
        self.assertEqual(
            classify_session_mode({"total_output_tokens": 0}, steps_archive_records=[{"thinking_tokens": None}]),
            "standard",
        )

    def test_standard_fallback(self):
        """Verify normal sessions fall back gracefully to standard mode."""
        convo = {
            "turn_count": 25,
            "subagents_count": 0,
            "thinking_tokens": 500,
            "total_output_tokens": 10000,  # 5% thinking ratio (< 0.30)
        }
        self.assertEqual(classify_session_mode(convo), "standard")
        self.assertEqual(classify_session_mode({}), "standard")
        self.assertEqual(classify_session_mode(None), "standard")


class TestFileChurnDetection(unittest.TestCase):
    """Test suite for file churn and thrashing detection."""

    def test_churn_flagged_at_threshold(self):
        """Verify session is flagged when single file has >= 5 modifications."""
        tools = [
            {"tool_name": "replace_file_content", "arguments": {"TargetFile": "src/app.py"}},
            {"tool_name": "replace_file_content", "arguments": {"TargetFile": "src/app.py"}},
            {"tool_name": "write_to_file", "arguments": {"TargetFile": "src/app.py"}},
            {"tool_name": "replace_file_content", "arguments": {"TargetFile": "src/app.py"}},
            {"tool_name": "replace_file_content", "arguments": {"TargetFile": "src/app.py"}},
            {"tool_name": "replace_file_content", "arguments": {"TargetFile": "src/other.py"}},
        ]
        res = detect_file_churn(tools)
        self.assertTrue(res["has_churn"])
        self.assertEqual(res["max_modifications"], 5)
        self.assertIn("src/app.py", res["churn_files"])
        self.assertEqual(res["churn_files"]["src/app.py"], 5)
        self.assertTrue(is_session_file_churn(tools))

    def test_churn_below_threshold(self):
        """Verify session is not flagged when modifications are < 5."""
        tools = [
            {"tool_name": "replace_file_content", "arguments": {"TargetFile": "src/app.py"}},
            {"tool_name": "replace_file_content", "arguments": {"TargetFile": "src/app.py"}},
            {"tool_name": "write_to_file", "arguments": {"TargetFile": "src/app.py"}},
            {"tool_name": "replace_file_content", "arguments": {"TargetFile": "src/app.py"}},
        ]
        res = detect_file_churn(tools)
        self.assertFalse(res["has_churn"])
        self.assertEqual(res["max_modifications"], 4)
        self.assertEqual(res["churn_files"], {})
        self.assertFalse(is_session_file_churn(tools))

    def test_non_modification_tools_ignored(self):
        """Verify read-only tools (view_file, grep_search) do not count as file modifications."""
        tools = [
            {"tool_name": "view_file", "arguments": {"AbsolutePath": "src/app.py"}},
            {"tool_name": "view_file", "arguments": {"AbsolutePath": "src/app.py"}},
            {"tool_name": "grep_search", "arguments": {"SearchPath": "src/app.py"}},
            {"tool_name": "replace_file_content", "arguments": {"TargetFile": "src/app.py"}},
        ]
        res = detect_file_churn(tools)
        self.assertFalse(res["has_churn"])
        self.assertEqual(res["max_modifications"], 1)

    def test_empty_tool_name_ignored(self):
        """Verify tools with empty or non-matching tool names do not count."""
        tools = [
            {"tool_name": "", "arguments": {"TargetFile": "src/app.py"}},
            {"arguments": {"TargetFile": "src/app.py"}},
        ]
        res = detect_file_churn(tools)
        self.assertEqual(res["max_modifications"], 0)
        self.assertEqual(res["total_modifications"], 0)

    def test_tuple_and_top_level_arguments(self):
        """Verify tuple with dict argument and top-level TargetFile in tool call dict."""
        tools = [
            ("replace_file_content", {"TargetFile": "src/app.py"}),
            {"tool_name": "replace_file_content", "TargetFile": "src/app.py"},
        ]
        res = detect_file_churn(tools)
        self.assertEqual(res["file_counts"].get("src/app.py"), 2)

    def test_vault_query_churn(self):
        """Verify querying vault tool_calls_archive detects file churn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            v_path = Path(tmpdir) / "test_vault.db"
            conn = init_vault(v_path)
            cur = conn.cursor()

            cid = "convo-churn-test"
            for i in range(6):
                cur.execute(
                    """
                    INSERT INTO tool_calls_archive (convo_id, step_idx, tool_name, arguments_json)
                    VALUES (?, ?, 'replace_file_content', ?)
                    """,
                    (cid, i, json.dumps({"TargetFile": "/path/to/HomeScreen.kt"})),
                )
            conn.commit()
            conn.close()

            res = detect_file_churn(cid, vault_path=v_path)
            self.assertTrue(res["has_churn"])
            self.assertEqual(res["max_modifications"], 6)
            self.assertIn("/path/to/HomeScreen.kt", res["churn_files"])


if __name__ == "__main__":
    unittest.main()
