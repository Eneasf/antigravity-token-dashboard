"""
test_demo_showcase.py

Unit and regression test suite for scripts/build_demo_showcase.py (ADR-050 / Milestone 36).
Validates schema completeness, byte-determinism, and zero-PII guarantees.
"""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_demo_showcase import generate_synthetic_payload, write_demo_files

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDemoShowcase(unittest.TestCase):
    """Test suite ensuring the synthetic demo generator produces complete, safe showcase data."""

    def test_generate_synthetic_payload_schema(self):
        """Verify all required top-level telemetry sections are present."""
        payload = generate_synthetic_payload()
        required_sections = [
            "summary",
            "projects",
            "conversations",
            "swarms",
            "tool_analytics",
            "quotas",
            "weekly_trends",
        ]
        for sec in required_sections:
            self.assertIn(sec, payload, f"Missing required telemetry section: {sec}")

    def test_is_demo_flag_present(self):
        """Verify the payload explicitly flags itself as a demo."""
        payload = generate_synthetic_payload()
        self.assertTrue(payload.get("summary", {}).get("is_demo"))
        self.assertIn("Demo", payload.get("summary", {}).get("demo_title", ""))

    def test_projects_and_branches_completeness(self):
        """Verify projects contain diverse workspaces and active Git branches."""
        payload = generate_synthetic_payload()
        projects = payload.get("projects", [])
        self.assertGreaterEqual(len(projects), 4, "Showcase must feature at least 4 projects")

        for p in projects:
            self.assertTrue(p.get("project_name"))
            self.assertTrue(p.get("workspace_root"))
            self.assertGreater(p.get("total_turns", 0), 0)
            self.assertGreater(p.get("total_input_tokens", 0), 0)
            self.assertGreaterEqual(p.get("cache_hit_ratio_pct", 0.0), 80.0)
            self.assertGreater(len(p.get("branches", [])), 0)

    def test_turn_inspector_fields(self):
        """Verify conversation turns feature full step-level metrics including thinking tokens."""
        payload = generate_synthetic_payload()
        convos = payload.get("conversations", [])
        self.assertGreaterEqual(len(convos), 8, "Showcase must feature at least 8 conversations")

        total_turns = 0
        thinking_turn_found = False
        for c in convos:
            turns = c.get("turns", [])
            self.assertGreater(len(turns), 0)
            total_turns += len(turns)
            for t in turns:
                self.assertIn("convo_id", t)
                self.assertIn("step_idx", t)
                self.assertIn("model_name", t)
                self.assertIn("prompt_tokens_uncached", t)
                self.assertIn("cached_tokens", t)
                self.assertIn("thinking_tokens", t)
                self.assertIn("answer_tokens", t)
                self.assertIn("response_id", t)
                if t["thinking_tokens"] > 0:
                    thinking_turn_found = True

        self.assertGreaterEqual(total_turns, 50, "Showcase must include at least 50 individual turns")
        self.assertTrue(thinking_turn_found, "Showcase turns must include thinking/reasoning token telemetry")

    def test_swarms_hierarchy_dag(self):
        """Verify multi-agent swarm lineages feature 3-tier routing, rich telemetry, and complete DAGs."""
        payload = generate_synthetic_payload()
        swarms = payload.get("swarms", {})
        self.assertGreaterEqual(swarms.get("total_swarms", 0), 4)
        self.assertGreaterEqual(swarms.get("total_subagents", 0), 10)
        self.assertGreaterEqual(swarms.get("total_swarm_tokens", 0), 20000000)
        self.assertGreaterEqual(swarms.get("global_cache_hit_pct", 0.0), 90.0)
        self.assertGreaterEqual(swarms.get("avg_tokens_per_turn", 0), 100000)
        self.assertGreaterEqual(swarms.get("total_thinking_tokens", 0), 200000)
        self.assertGreaterEqual(len(swarms.get("unique_projects", [])), 4)

        tier_routing = swarms.get("tier_routing", {})
        self.assertIn("mechanical_execution", tier_routing)
        self.assertIn("standard_engineering", tier_routing)
        self.assertIn("complex_architecture", tier_routing)

        for s in swarms.get("swarms", []):
            self.assertTrue(s.get("root_agent"))
            self.assertGreater(s.get("total_swarm_tokens", 0), 1000000)
            self.assertGreaterEqual(s.get("cache_hit_pct", 0.0), 90.0)
            self.assertGreater(s.get("tokens_per_turn", 0), 50000)

            # Validate DAG nodes and edges
            nodes = s.get("nodes", [])
            edges = s.get("edges", [])
            self.assertGreaterEqual(len(nodes), 3, "Each swarm DAG must have at least 3 nodes")
            self.assertGreaterEqual(len(edges), 2, "Each swarm DAG must have at least 2 edges")

            root_nodes = [n for n in nodes if n.get("is_root")]
            self.assertEqual(len(root_nodes), 1, "Each swarm DAG must have exactly one root node")
            root_id = root_nodes[0]["id"]

            for n in nodes:
                self.assertIn("id", n)
                self.assertIn("role", n)
                self.assertIn("tier", n)
                self.assertIn("model_name", n)
                self.assertGreater(n.get("tokens_total", 0), 0)
                self.assertGreater(n.get("cost_gbp", 0.0), 0.0)
                if not n.get("is_root"):
                    self.assertEqual(n.get("parent_id"), root_id)

            for e in edges:
                self.assertIn("source", e)
                self.assertIn("target", e)
                self.assertEqual(e["source"], root_id)

            for sub in s.get("subagents", []):
                self.assertTrue(sub.get("parent_id"), "Subagents in DAG must specify parent_id")

    def test_tool_analytics_data(self):
        """Verify tool execution analytics feature invocation counts and bypass metrics."""
        payload = generate_synthetic_payload()
        tools_data = payload.get("tool_analytics", {})
        self.assertGreaterEqual(tools_data.get("unique_tools_count", 0), 10)
        self.assertGreater(tools_data.get("total_tool_calls", 0), 1000)
        self.assertGreater(tools_data.get("total_sandbox_bypasses", 0), 50)
        self.assertIn("tools", tools_data)

    def test_weekly_trends_and_billing(self):
        """Verify historical weekly cycles and Google One billing reconciliation have complete data."""
        payload = generate_synthetic_payload()
        trends = payload.get("weekly_trends", {})
        self.assertIn("cycles", trends)
        self.assertIn("summary", trends)

        cycles = trends["cycles"]
        self.assertEqual(len(cycles), 12, "Must contain exactly 12 weekly cycles")

        summary = trends["summary"]
        self.assertEqual(summary.get("cycles_analyzed"), 12)
        self.assertGreaterEqual(summary.get("average_tokens_per_week", 0), 30000000)
        self.assertGreater(summary.get("average_cost_per_week_gbp", 0.0), 50.0)
        self.assertGreater(summary.get("average_cost_per_week_usd", 0.0), 50.0)
        self.assertGreaterEqual(summary.get("peak_week_tokens", 0), 40000000)
        self.assertTrue(summary.get("peak_week_label"))
        self.assertGreater(summary.get("token_growth_rate_pct", 0.0), 0.0)

        # Check cycle properties
        overage_found = False
        current_found = False
        for c in cycles:
            self.assertTrue(c.get("cycle_start_utc"))
            self.assertTrue(c.get("label"))
            self.assertGreater(c.get("total_processed_tokens", 0), 20000000)
            self.assertGreaterEqual(c.get("cache_hit_ratio_pct", 0.0), 90.0)
            self.assertGreater(c.get("estimated_cost_gbp", 0.0), 50.0)
            self.assertGreater(c.get("peak_bvi", 0.0), 0.5)
            if c.get("actual_overage_credits", 0) > 0:
                overage_found = True
            if c.get("is_current_cycle"):
                current_found = True

        self.assertTrue(overage_found, "Must feature at least one overage cycle with credit debits")
        self.assertTrue(current_found, "Must mark the current active cycle")

        # Check hourly credit activity
        activity = payload.get("hourly_credit_activity", [])
        self.assertGreaterEqual(len(activity), 1, "Must contain reconciled hourly credit activity")
        total_act_credits = sum(a.get("credits_burned", 0) for a in activity)
        self.assertEqual(total_act_credits, payload.get("summary", {}).get("total_ai_credits_burned"))

    def test_quota_silos_and_model_matrix(self):
        """Verify dual-track quota silos, runway governor, and model allowance matrix are populated."""
        payload = generate_synthetic_payload()
        quotas = payload.get("quotas", {})
        providers = quotas.get("providers", {})
        self.assertIn("gemini", providers)
        self.assertIn("claude_gpt", providers)

        # Gemini Silo
        gemini = providers["gemini"]
        self.assertLess(gemini["weekly"]["remaining_pct"], 100.0)
        self.assertGreater(gemini["weekly"]["remaining_pct"], 50.0)
        self.assertLess(gemini["five_hour"]["remaining_pct"], 100.0)
        self.assertGreater(gemini["five_hour"]["total_processed_tokens"], 1000000)
        self.assertGreaterEqual(len(gemini["five_hour"].get("active_sessions_5h", [])), 3)

        # Runway Governor
        runway = gemini.get("runway", {})
        self.assertGreater(runway.get("quota_consumed_pct", 0), 0)
        self.assertIn("0.", runway.get("bvi_display", ""))
        self.assertEqual(runway.get("status_key"), "green")

        # Claude Silo
        claude = providers["claude_gpt"]
        self.assertLess(claude["weekly"]["remaining_pct"], 100.0)
        self.assertLess(claude["five_hour"]["remaining_pct"], 100.0)
        self.assertGreater(claude["five_hour"]["total_processed_tokens"], 300000)

        # Subagent Metrics
        sub_metrics = payload.get("summary", {}).get("subagent_metrics", {})
        self.assertIn("interactive", sub_metrics)
        self.assertIn("subagent", sub_metrics)
        self.assertGreater(sub_metrics["interactive"]["total_tokens"], 5000000)
        self.assertGreater(sub_metrics["subagent"]["total_tokens"], 10000000)

        # Model Allowance Matrix (5h and 1w)
        r5h_models = quotas.get("rolling_5h", {}).get("by_model", [])
        r1w_models = quotas.get("rolling_1w", {}).get("by_model", [])
        self.assertGreaterEqual(len(r5h_models), 5)
        self.assertGreaterEqual(len(r1w_models), 7)

        for m in r1w_models:
            self.assertTrue(m.get("model_id"))
            self.assertTrue(m.get("model_name"))
            self.assertGreater(m.get("turn_count", 0), 0)
            self.assertGreater(m.get("total_processed_tokens", 0), 0)
            self.assertGreater(m.get("cache_hit_ratio_pct", 0.0), 85.0)

    def test_byte_deterministic_file_writing(self):
        """Verify write_demo_files produces identical byte output given identical inputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = Path(tmpdir) / "demo1.js"
            f2 = Path(tmpdir) / "demo2.js"
            m1 = Path(tmpdir) / "meta1.js"
            m2 = Path(tmpdir) / "meta2.js"

            write_demo_files(f1, m1)
            write_demo_files(f2, m2)

            self.assertEqual(f1.read_bytes(), f2.read_bytes(), "Generated data.js must be byte-deterministic")
            self.assertEqual(m1.read_bytes(), m2.read_bytes(), "Generated meta.js must be byte-deterministic")

    def test_zero_pii_in_generated_payload(self):
        """Verify generated payload has zero local paths, real UUIDs, or enterprise keywords."""
        payload = generate_synthetic_payload()
        json_str = json.dumps(payload)

        # Check local user paths
        self.assertNotIn("Users" + "/eneasf", json_str)
        self.assertNotIn("home" + "/eneasf", json_str)

        # Check leaked conversation UUID
        self.assertNotIn("df35" + "048e", json_str)

        # Check enterprise keywords
        self.assertNotIn("AT" + "LAS", json_str)
        self.assertNotIn("S" + "AP ", json_str)
        self.assertNotIn("antigravity" + ".community", json_str)


if __name__ == "__main__":
    unittest.main()
