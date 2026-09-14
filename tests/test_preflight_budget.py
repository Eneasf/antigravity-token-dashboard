"""
Unit tests for Pre-Flight Workload Budget Checker CLI and engine (Milestone 28).

Validates:
- Archetype preset resolution and simulation against live quota headroom.
- Deterministic process exit codes (0 for SAFE/PROCEED, 1 for BLOCKED/429 RISK).
- Provider track isolation: Track 2 (Claude/GPT) hard 429 lockout on burst exhaustion.
- Track 1 (Gemini) burst exhaustion spillover gating (--allow-spillover).
- Canonical 19-model roster validation.
- Clean JSON output serialization.
"""

import json
from pathlib import Path
import subprocess
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.agy_quota import run_preflight_budget_check


class TestPreflightBudgetChecker(unittest.TestCase):
    """Test suite for agy_quota.py --can-i-run workload budget checker."""

    def setUp(self):
        self.clean_quota_state = {
            "gemini": {
                "starting_5h_used_usd": 0.0,
                "starting_weekly_used_usd": 0.0,
                "credits_remaining": 1360,
            },
            "claude_gpt": {
                "starting_5h_used_usd": 0.0,
                "starting_weekly_used_usd": 0.0,
                "credits_remaining": 1360,
            },
            "credits_remaining": 1360,
        }

    def test_safe_archetype_proceeds_cleanly(self):
        """Standard deep_refactor_swarm under Ultra 5x should proceed with exit code 0."""
        res = run_preflight_budget_check(
            workload_type="deep_refactor_swarm",
            quota_state_override=self.clean_quota_state,
            plan_tier="ultra_5x",
        )
        self.assertEqual(res["exit_code"], 0)
        self.assertTrue(res["safe_to_run"])
        self.assertIn("SAFE", res["verdict"])
        self.assertFalse(res["projected_state"]["burst_exhausted"])
        self.assertFalse(res["projected_state"]["hard_429_block_risk"])
        self.assertGreater(res["projected_state"]["final_5h_remaining_pct"], 50.0)

    def test_claude_excess_burst_triggers_429_block(self):
        """Massive Claude Opus run must trigger hard 429 lockout with exit code 1."""
        res = run_preflight_budget_check(
            workload_type="claude_opus_deep_dive",
            turns=300,
            quota_state_override=self.clean_quota_state,
            plan_tier="pro",
        )
        self.assertEqual(res["exit_code"], 1)
        self.assertFalse(res["safe_to_run"])
        self.assertEqual(res["verdict"], "BLOCKED")
        self.assertTrue(res["projected_state"]["burst_exhausted"])
        self.assertTrue(res["projected_state"]["hard_429_block_risk"])

    def test_gemini_burst_exhaustion_requires_spillover_flag(self):
        """Gemini run exceeding burst allowance blocks without --allow-spillover, proceeds with it."""
        tight_quota = {
            "gemini": {
                "starting_5h_used_usd": 19.50,
                "starting_weekly_used_usd": 10.0,
                "credits_remaining": 1360,
            },
            "claude_gpt": {
                "starting_5h_used_usd": 0.0,
                "starting_weekly_used_usd": 0.0,
                "credits_remaining": 1360,
            },
            "credits_remaining": 1360,
        }

        # 1. Without allow_spillover -> BLOCKED (exit 1)
        res_blocked = run_preflight_budget_check(
            workload_type="deep_refactor_swarm",
            quota_state_override=tight_quota,
            allow_spillover=False,
            plan_tier="pro",
        )
        self.assertEqual(res_blocked["exit_code"], 1)
        self.assertEqual(res_blocked["verdict"], "BLOCKED")
        self.assertTrue(res_blocked["projected_state"]["burst_exhausted"])

        # 2. With allow_spillover -> PROCEED_WITH_SPILLOVER (exit 0)
        res_allowed = run_preflight_budget_check(
            workload_type="deep_refactor_swarm",
            quota_state_override=tight_quota,
            allow_spillover=True,
            plan_tier="pro",
        )
        self.assertEqual(res_allowed["exit_code"], 0)
        self.assertEqual(res_allowed["verdict"], "PROCEED_WITH_SPILLOVER")
        self.assertTrue(res_allowed["safe_to_run"])
        self.assertGreater(res_allowed["projected_state"]["credits_debited"], 0)

    def test_custom_workload_parameters(self):
        """Custom workload accepts turn count, model ID, and token breakdown."""
        res = run_preflight_budget_check(
            workload_type="custom",
            turns=15,
            model_id="1318",
            prompt_tokens=40000,
            thinking_tokens=1500,
            answer_tokens=800,
            cache_hit_ratio_pct=85.0,
            quota_state_override=self.clean_quota_state,
            plan_tier="ultra_5x",
        )
        self.assertEqual(res["exit_code"], 0)
        self.assertEqual(res["workload"]["turn_count"], 15)
        self.assertEqual(res["workload"]["model_id"], "1318")
        self.assertEqual(res["workload"]["provider_track"], "gemini")

    def test_invalid_archetype_raises_error(self):
        """Unknown archetype string must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            run_preflight_budget_check(workload_type="quantum_teleportation_swarm")
        self.assertIn("Unknown archetype ID", str(ctx.exception))

    def test_invalid_model_id_raises_error(self):
        """Unknown model ID not in canonical 19-model roster must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            run_preflight_budget_check(
                workload_type="custom",
                model_id="gpt-5-turbo-uncalibrated",
            )
        self.assertIn("Unknown model ID", str(ctx.exception))

    def test_cli_json_execution(self):
        """Running scripts/agy_quota.py --can-i-run via subprocess outputs valid JSON."""
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "agy_quota.py"),
            "--can-i-run",
            "subagent_fleet",
            "--json",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self.assertIn(proc.returncode, (0, 1))
        data = json.loads(proc.stdout)
        self.assertIn("verdict", data)
        self.assertIn("exit_code", data)
        self.assertIn("workload", data)
        self.assertIn("live_headroom", data)
        self.assertIn("projected_state", data)
        self.assertEqual(data["workload"]["archetype_id"], "subagent_fleet")


if __name__ == "__main__":
    unittest.main()
