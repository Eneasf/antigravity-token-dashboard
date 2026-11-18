"""
Unit Tests for Multi-Project & Cascading Multi-Agent Context Degradation Telemetry (M91 / ADR-092).

Verifies:
1. Dual-state session metrics: Evaluating current capacity from latest turn prompt depth
   while tracking compaction epoch / memory drift independently.
2. Weakest-link subagent election: Bubbling up critical subagents to primary alert
   with explicit role badges and parent conversation links.
3. Multi-project active swarms hierarchy: Grouping active sessions by workspace
   with parent orchestrator and child subagent trees.
4. Velocity spike detection: Single-turn payload swelling triggering early warning.
5. Executive status file payload: Correct serialization of active_swarms and weakest link.
"""

import datetime
import json
from pathlib import Path
import tempfile
import unittest

from scripts.export_dashboard import (
    compute_current_session,
    extract_active_swarms_hierarchy,
    write_quota_status_file,
)
from antigravity_telemetry import load_model_census


class TestMultiAgentDegradation(unittest.TestCase):
    """Test suite for multi-project and multi-agent context degradation telemetry."""

    def setUp(self):
        self.census = load_model_census()
        self.ref_time = datetime.datetime(2026, 10, 7, 21, 0, 0, tzinfo=datetime.timezone.utc)

    def test_dual_state_reset_recovery(self):
        """
        Prove that when a conversation had a historic peak of 240,000 tokens and then
        compacted/restarted down to 35,000 tokens, current active load evaluates to 35,000
        and safe capacity headroom, rather than remaining stuck on 240k critical.
        """
        conv = {
            "convo_id": "conv-restarted",
            "title": "Main Implementation Task",
            "workspace_name": "Project Alpha",
            "git_branch": "feat/engine",
            "turns": [
                {"total_input_tokens": 240000, "model_id": "1318"},
                {"total_input_tokens": 35000, "model_id": "1318"},
            ],
            "compaction_count": 1,
            "models_used": ["gemini-3.8-flash"],
            "last_turn_ts": "2026-10-07T20:55:00Z",
        }

        payload = {"conversations": [conv]}
        res = compute_current_session(payload, self.census, reference_time=self.ref_time)

        self.assertIsNotNone(res)
        self.assertEqual(res["tokens"], 35000)
        self.assertEqual(res["compaction_epoch"], 2)
        self.assertEqual(res["severity"], "warning")
        self.assertGreater(res["headroom_to_warning"], 100000)
        self.assertEqual(res["drift_risk"], "caution")
        self.assertIn("Epoch 2", res["drift_message"])

    def test_subagent_weakest_link_election(self):
        """
        Prove that when an orchestrator is safe (50k tokens) and a child subagent is critical
        (230k tokens / 250k = 92%), the subagent is elected as the primary alert with
        subagent role and parent context links.
        """
        orch = {
            "convo_id": "orch-1",
            "title": "Orchestrator Session",
            "workspace_name": "Project Alpha",
            "git_branch": "main",
            "is_subagent": False,
            "turns": [{"total_input_tokens": 50000, "model_id": "1318"}],
            "models_used": ["gemini-3.8-flash"],
            "last_turn_ts": "2026-10-07T20:50:00Z",
        }
        sub = {
            "convo_id": "sub-1",
            "title": "Subagent: Codebase Researcher",
            "parent_convo_id": "orch-1",
            "workspace_name": "Project Alpha",
            "git_branch": "main",
            "is_subagent": True,
            "subagent_role": "research",
            "turns": [{"total_input_tokens": 230000, "model_id": "1318"}],
            "models_used": ["gemini-3.8-flash"],
            "last_turn_ts": "2026-10-07T20:55:00Z",
        }

        payload = {"conversations": [orch, sub]}
        res = compute_current_session(payload, self.census, reference_time=self.ref_time)

        self.assertIsNotNone(res)
        self.assertTrue(res["is_subagent"])
        self.assertEqual(res["subagent_role"], "research")
        self.assertEqual(res["parent_convo_id"], "orch-1")
        self.assertEqual(res["tokens"], 230000)
        self.assertEqual(res["severity"], "critical")
        self.assertIn("Compaction Imminent", res["drift_message"])

    def test_multi_project_active_swarms_hierarchy(self):
        """
        Prove that conversations across multiple projects are grouped into active swarms
        preserving orchestrators and child subagents within the 30-minute window.
        """
        orch_a = {
            "convo_id": "orch-a",
            "title": "Project A Orchestrator",
            "workspace_name": "Project Alpha",
            "git_branch": "feat/engine",
            "is_subagent": False,
            "turns": [{"total_input_tokens": 60000}],
            "models_used": ["gemini-3.8-flash"],
            "last_turn_ts": "2026-10-07T20:52:00Z",
        }
        sub_a1 = {
            "convo_id": "sub-a1",
            "title": "Subagent Researcher",
            "parent_convo_id": "orch-a",
            "workspace_name": "Project Alpha",
            "git_branch": "feat/engine",
            "is_subagent": True,
            "subagent_role": "research",
            "turns": [{"total_input_tokens": 235000}],
            "models_used": ["gemini-3.8-flash"],
            "last_turn_ts": "2026-10-07T20:54:00Z",
        }
        orch_b = {
            "convo_id": "orch-b",
            "title": "Project B Standalone",
            "workspace_name": "Project Beta",
            "git_branch": "main",
            "is_subagent": False,
            "turns": [{"total_input_tokens": 40000}],
            "models_used": ["gemini-3.8-flash"],
            "last_turn_ts": "2026-10-07T20:48:00Z",
        }

        convos = [orch_a, sub_a1, orch_b]
        swarms, weakest = extract_active_swarms_hierarchy(
            convos, self.census, reference_time=self.ref_time, recency_minutes=30
        )

        self.assertEqual(len(swarms), 2)
        # Verify Project Alpha
        alpha_group = next((g for g in swarms if g["workspace"] == "Project Alpha"), None)
        self.assertIsNotNone(alpha_group)
        self.assertEqual(alpha_group["worst_severity"], "critical")
        self.assertEqual(alpha_group["orchestrator"]["convo_id"], "orch-a")
        self.assertEqual(len(alpha_group["subagents"]), 1)
        self.assertEqual(alpha_group["subagents"][0]["convo_id"], "sub-a1")
        self.assertTrue(alpha_group["subagents"][0]["is_weakest_link"])

        # Verify Project Beta
        beta_group = next((g for g in swarms if g["workspace"] == "Project Beta"), None)
        self.assertIsNotNone(beta_group)
        self.assertEqual(beta_group["worst_severity"], "safe")
        self.assertEqual(beta_group["orchestrator"]["convo_id"], "orch-b")
        self.assertEqual(len(beta_group["subagents"]), 0)

        # Verify Weakest Link overall
        self.assertIsNotNone(weakest)
        self.assertEqual(weakest["convo_id"], "sub-a1")
        self.assertEqual(weakest["severity"], "critical")

    def test_velocity_spike_detection(self):
        """
        Prove that a single-turn token velocity spike (>40k tok/turn) pushing capacity past
        65% triggers a warning state with velocity spike diagnosis.
        """
        conv = {
            "convo_id": "conv-spike",
            "title": "Spike Session",
            "workspace_name": "Project Spiky",
            "git_branch": "main",
            "turns": [
                {"total_input_tokens": 50000},
                {"total_input_tokens": 175000},  # +125k tokens spike, 175k/250k = 70%
            ],
            "models_used": ["gemini-3.8-flash"],
            "last_turn_ts": "2026-10-07T20:58:00Z",
        }

        payload = {"conversations": [conv]}
        res = compute_current_session(payload, self.census, reference_time=self.ref_time)

        self.assertIsNotNone(res)
        self.assertEqual(res["tokens"], 175000)
        self.assertEqual(res["severity"], "warning")
        self.assertEqual(res["drift_risk"], "warning")
        self.assertIn("Velocity Spike", res["drift_message"])
        self.assertEqual(res["turn_velocity"], 125000)

    def test_status_file_serialization_with_swarms(self):
        """
        Prove that write_quota_status_file writes active_swarms and weakest link
        into the quota status JSON file.
        """
        orch = {
            "convo_id": "orch-root",
            "title": "Master Task",
            "workspace_name": "Core WS",
            "git_branch": "main",
            "turns": [{"total_input_tokens": 45000}],
            "models_used": ["gemini-3.8-flash"],
            "last_turn_ts": "2026-10-07T20:55:00Z",
        }
        sub = {
            "convo_id": "sub-worker",
            "title": "Implementer Worker",
            "parent_convo_id": "orch-root",
            "workspace_name": "Core WS",
            "git_branch": "main",
            "is_subagent": True,
            "subagent_role": "implementer",
            "turns": [{"total_input_tokens": 235000}],
            "models_used": ["gemini-3.8-flash"],
            "last_turn_ts": "2026-10-07T20:56:00Z",
        }

        payload = {
            "conversations": [orch, sub],
            "quotas": {"providers": {}},
            "summary": {"subscription_status": "SAFE_IN_QUOTA"},
            "temporal": {"resolved_at_utc": "2026-10-07T21:00:00Z"},
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            status_path = Path(tmpdir) / "quota_status.json"
            write_quota_status_file(payload, status_path=status_path)

            self.assertTrue(status_path.exists())
            data = json.loads(status_path.read_text(encoding="utf-8"))

            self.assertIn("active_swarms", data)
            self.assertEqual(len(data["active_swarms"]), 1)
            self.assertIn("current_session", data)
            self.assertEqual(data["current_session"]["convo_id"], "sub-worker")
            self.assertEqual(data["current_session"]["severity"], "critical")
            self.assertTrue(data["current_session"]["is_subagent"])
            self.assertEqual(data["current_session"]["subagent_role"], "implementer")

    def test_idle_workspace_returns_zero_active_swarms(self):
        """
        Prove that when all conversations are older than recency_minutes,
        extract_active_swarms_hierarchy returns 0 active swarms instead of
        dumping all historical conversations into a single fallback swarm.
        """
        old_convos = [
            {
                "convo_id": f"old-{i}",
                "title": f"Historical Session {i}",
                "workspace_name": "Project Alpha",
                "is_subagent": i > 0,
                "turns": [{"total_input_tokens": 60000}],
                "last_turn_ts": "2026-10-07T15:00:00Z",
            }
            for i in range(25)
        ]

        swarms, weakest = extract_active_swarms_hierarchy(
            old_convos, self.census, reference_time=self.ref_time, recency_minutes=30
        )
        self.assertEqual(swarms, [])
        self.assertIsNotNone(weakest)
        self.assertEqual(weakest["convo_id"], "old-0")
        self.assertFalse(weakest["is_subagent"])

    def test_subagent_strict_parent_lineage_binding(self):
        """
        Prove that active subagents with a different parent_convo_id or non-subagent
        peer orchestrators are not falsely attached as child subagents of the latest orchestrator.
        """
        convos = [
            {
                "convo_id": "orch-current",
                "title": "Current Orchestrator",
                "workspace_name": "Project Alpha",
                "is_subagent": False,
                "turns": [{"total_input_tokens": 40000}],
                "last_turn_ts": "2026-10-07T20:58:00Z",
            },
            {
                "convo_id": "sub-matching",
                "title": "Matching Subagent",
                "parent_convo_id": "orch-current",
                "workspace_name": "Project Alpha",
                "is_subagent": True,
                "subagent_role": "research",
                "turns": [{"total_input_tokens": 55000}],
                "last_turn_ts": "2026-10-07T20:59:00Z",
            },
            {
                "convo_id": "sub-unrelated",
                "title": "Unrelated Subagent",
                "parent_convo_id": "orch-older",
                "workspace_name": "Project Alpha",
                "is_subagent": True,
                "subagent_role": "challenger",
                "turns": [{"total_input_tokens": 90000}],
                "last_turn_ts": "2026-10-07T20:45:00Z",
            },
            {
                "convo_id": "orch-peer",
                "title": "Peer Orchestrator",
                "workspace_name": "Project Alpha",
                "is_subagent": False,
                "turns": [{"total_input_tokens": 70000}],
                "last_turn_ts": "2026-10-07T20:40:00Z",
            },
        ]

        swarms, _ = extract_active_swarms_hierarchy(
            convos, self.census, reference_time=self.ref_time, recency_minutes=30
        )
        self.assertEqual(len(swarms), 1)
        sub_ids = [s["convo_id"] for s in swarms[0]["subagents"]]
        self.assertEqual(sub_ids, ["sub-matching"])

    def test_active_orchestrator_preserves_older_child_subagents(self):
        """
        Prove that when an orchestrator is active within recency_minutes, all of its
        child and grandchild subagents are preserved in the swarm tree even if those
        subagents finished their turns >30 minutes ago.
        """
        convos = [
            {
                "convo_id": "orch-active",
                "title": "Active Orchestrator",
                "workspace_name": "Project Alpha",
                "is_subagent": False,
                "turns": [{"total_input_tokens": 80000}],
                "last_turn_ts": "2026-10-07T20:55:00Z",  # 5m ago
            },
            {
                "convo_id": "sub-older",
                "title": "Completed Subagent",
                "parent_convo_id": "orch-active",
                "workspace_name": "Project Alpha",
                "is_subagent": True,
                "subagent_role": "implementer",
                "turns": [{"total_input_tokens": 110000}],
                "last_turn_ts": "2026-10-07T19:15:00Z",  # 1h45m ago (>30m)
            },
            {
                "convo_id": "sub-grandchild",
                "title": "Nested Challenger",
                "parent_convo_id": "sub-older",
                "workspace_name": "Project Alpha",
                "is_subagent": True,
                "subagent_role": "challenger",
                "turns": [{"total_input_tokens": 45000}],
                "last_turn_ts": "2026-10-07T19:10:00Z",  # 1h50m ago (>30m)
            },
        ]

        swarms, _ = extract_active_swarms_hierarchy(
            convos, self.census, reference_time=self.ref_time, recency_minutes=30
        )
        self.assertEqual(len(swarms), 1)
        self.assertEqual(swarms[0]["orchestrator"]["convo_id"], "orch-active")
        sub_ids = [s["convo_id"] for s in swarms[0]["subagents"]]
        self.assertEqual(sub_ids, ["sub-older", "sub-grandchild"])

    def test_swarm_recency_window_and_newer_standalone_chat(self):
        """
        Prove that multi-agent swarms active within swarm_recency_minutes (24h) are
        included and are not hidden when a newer 0-subagent standalone chat is opened
        in the same workspace.
        """
        convos = [
            {
                "convo_id": "standalone-now",
                "title": "Quick Question",
                "workspace_name": "Project Alpha",
                "is_subagent": False,
                "turns": [{"total_input_tokens": 15000}],
                "last_turn_ts": "2026-10-07T20:58:00Z",  # 2m ago, 0 subagents
            },
            {
                "convo_id": "orch-swarm-recent",
                "title": "Architecture Refactor Swarm",
                "workspace_name": "Project Alpha",
                "is_subagent": False,
                "turns": [{"total_input_tokens": 95000}],
                "last_turn_ts": "2026-10-07T17:30:00Z",  # 3.5h ago, has subagent
            },
            {
                "convo_id": "sub-swarm-worker",
                "title": "Conversation 698aa0d7",
                "parent_convo_id": "orch-swarm-recent",
                "workspace_name": "Project Alpha",
                "is_subagent": True,
                "subagent_role": "Backend Horizon Analytics Engineer",
                "turns": [{"total_input_tokens": 120000}],
                "last_turn_ts": "2026-10-07T17:20:00Z",
            },
        ]

        swarms, weakest = extract_active_swarms_hierarchy(
            convos,
            self.census,
            reference_time=self.ref_time,
            recency_minutes=30,
            swarm_recency_minutes=1440,
        )
        self.assertIsNotNone(weakest)
        self.assertEqual(weakest["convo_id"], "standalone-now")
        self.assertEqual(len(swarms), 1)
        self.assertEqual(swarms[0]["orchestrator"]["convo_id"], "orch-swarm-recent")
        self.assertEqual(len(swarms[0]["subagents"]), 1)
        self.assertEqual(swarms[0]["subagents"][0]["convo_id"], "sub-swarm-worker")

    def test_single_safe_session_not_weakest_link(self):
        """
        Prove that a single healthy (severity == 'safe') session does not set
        is_weakest_link = True, and that warning drift messages use headroom_to_compaction.
        """
        safe_conv = {
            "convo_id": "safe-single",
            "title": "Healthy Single Session",
            "workspace_name": "Project Solo",
            "is_subagent": False,
            "turns": [{"total_input_tokens": 50000, "model_id": "1318"}],
            "models_used": ["1318"],
            "last_turn_ts": "2026-10-07T20:58:00Z",
        }
        swarms, weakest = extract_active_swarms_hierarchy(
            [safe_conv], self.census, reference_time=self.ref_time, recency_minutes=30
        )
        self.assertIsNotNone(weakest)
        self.assertEqual(weakest["severity"], "safe")
        self.assertFalse(weakest.get("is_weakest_link", False))
        # 0.75 * 250,000 - 50,000 = 137,500
        self.assertEqual(weakest["headroom_to_warning"], 137500)

    def test_active_subagent_with_older_parent_marks_weakest_link(self):
        """
        Prove that when a child subagent is active within recency_minutes (5m ago, critical)
        while its parent orchestrator's last turn was >30m ago (waiting on subagent),
        is_weakest_link is still True because the session belongs to a multi-agent swarm tree.
        """
        orch = {
            "convo_id": "orch-waiting",
            "title": "Waiting Orchestrator",
            "workspace_name": "Project Alpha",
            "is_subagent": False,
            "turns": [{"total_input_tokens": 50000, "model_id": "1318"}],
            "models_used": ["1318"],
            "last_turn_ts": "2026-10-07T19:45:00Z",  # 1h15m ago (>30m)
        }
        sub = {
            "convo_id": "sub-long-running",
            "title": "Long Running Subagent",
            "parent_convo_id": "orch-waiting",
            "workspace_name": "Project Alpha",
            "is_subagent": True,
            "subagent_role": "implementer",
            "turns": [{"total_input_tokens": 235000, "model_id": "1318"}],
            "models_used": ["1318"],
            "last_turn_ts": "2026-10-07T20:58:00Z",  # 2m ago
        }
        swarms, weakest = extract_active_swarms_hierarchy(
            [orch, sub], self.census, reference_time=self.ref_time, recency_minutes=30
        )
        self.assertIsNotNone(weakest)
        self.assertEqual(weakest["convo_id"], "sub-long-running")
        self.assertEqual(weakest["severity"], "critical")
        self.assertTrue(weakest["is_weakest_link"])
        self.assertEqual(len(swarms), 1)
        self.assertTrue(swarms[0]["subagents"][0]["is_weakest_link"])


if __name__ == "__main__":
    unittest.main()
