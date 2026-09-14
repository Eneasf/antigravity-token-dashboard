"""
Unit tests for Cost-Weighted Overage Credit Allocation (Milestone 28 / Audit §2.1 A5).

Validates:
- Confirmed ledger incident credits are distributed across branches and conversations
  proportionally to each turn's rate-card spend (estimated_cost_usd), rather than flat turn counts.
- Heterogeneous incident with 5 Claude Opus turns ($1.00) vs 50 Flash-Lite turns ($0.10)
  correctly allocates ~90.9% of incident credits to the Opus conversation and ~9.1% to Flash-Lite.
"""

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.aggregator import aggregate_global_telemetry, load_pricing


class TestOverageWeighting(unittest.TestCase):
    """Test suite verifying cost-weighted overage distribution across conversations and branches."""

    def setUp(self):
        self.pricing = load_pricing()

    def test_cost_weighted_attribution_vs_turn_count(self):
        """High-cost model (Opus) gets proportional share of incident credits over low-cost model (Flash-Lite)."""
        incident_start = "2026-09-08T14:00:00Z"
        incident_end = "2026-09-08T15:00:00Z"

        # Convo A: 5 Opus turns @ $0.20/turn = $1.00 total spend
        turns_a = [
            {
                "timestamp": "2026-09-08T14:10:00Z",
                "model_id": "1026",
                "prompt_tokens": 80000,
                "cached_tokens": 70000,
                "total_input_tokens": 80000,
                "thinking_tokens": 2000,
                "answer_tokens": 1000,
                "output_tokens_total": 3000,
                "total_processed_tokens": 83000,
                "estimated_cost_usd": 0.20,
            }
            for _ in range(5)
        ]

        convo_a = {
            "convo_id": "convo-opus-01",
            "title": "Opus Architecture Refactor",
            "workspace_path": "/Users/test/workspace/repo",
            "git_branch": "main",
            "turns": turns_a,
            "turn_count": 5,
            "total_input_tokens": 400000,
            "cached_tokens": 350000,
            "total_output_tokens": 15000,
            "total_processed_tokens": 415000,
            "estimated_cost_usd": 1.00,
            "actual_overage_credits": 0.0,
            "actual_overage_usd": 0.0,
            "actual_overage_gbp": 0.0,
            "overage_turns": 0,
            "subscription_covered_turns": 0,
        }

        # Convo B: 50 Flash-Lite turns @ $0.002/turn = $0.10 total spend
        turns_b = [
            {
                "timestamp": "2026-09-08T14:20:00Z",
                "model_id": "1050",
                "prompt_tokens": 5000,
                "cached_tokens": 4000,
                "total_input_tokens": 5000,
                "thinking_tokens": 100,
                "answer_tokens": 200,
                "output_tokens_total": 300,
                "total_processed_tokens": 5300,
                "estimated_cost_usd": 0.002,
            }
            for _ in range(50)
        ]

        convo_b = {
            "convo_id": "convo-lite-02",
            "title": "Flash Lite Batch Formatting",
            "workspace_path": "/Users/test/workspace/repo",
            "git_branch": "feat/formatting",
            "turns": turns_b,
            "turn_count": 50,
            "total_input_tokens": 250000,
            "cached_tokens": 200000,
            "total_output_tokens": 15000,
            "total_processed_tokens": 265000,
            "estimated_cost_usd": 0.10,
            "actual_overage_credits": 0.0,
            "actual_overage_usd": 0.0,
            "actual_overage_gbp": 0.0,
            "overage_turns": 0,
            "subscription_covered_turns": 0,
        }

        # Confirmed ledger incident: 550 credits debited during the window
        intervals = [
            {
                "incident_id": "inc-test-01",
                "start": incident_start,
                "end": incident_end,
                "credits_burned": 550,
                "credit_burn_usd": 5.50,
                "credit_burn_gbp": 5.28,
                "from_ledger": True,
            }
        ]

        all_turns = turns_a + turns_b
        payload = aggregate_global_telemetry(
            conversation_summaries=[convo_a, convo_b],
            pricing_models=self.pricing,
            all_raw_turns=all_turns,
            exhaustion_intervals=intervals,
        )

        # Under flat turn count: Convo A would get 5/55 = 50 credits; Convo B would get 50/55 = 500 credits.
        # Under cost-weighting (A5): Convo A ($1.00 / $1.10 = 90.91%) gets 500 credits; Convo B ($0.10 / $1.10 = 9.09%) gets 50 credits!
        self.assertEqual(convo_a["actual_overage_credits"], 500)
        self.assertEqual(convo_b["actual_overage_credits"], 50)
        self.assertGreater(convo_a["actual_overage_credits"], convo_b["actual_overage_credits"])
        self.assertEqual(convo_a["actual_overage_credits"] + convo_b["actual_overage_credits"], 550)

        # Verify branch-level overage allocation
        projects = payload.get("projects", [])
        self.assertEqual(len(projects), 1)
        branches = projects[0]["branches"]
        b_map = {b["branch_name"]: b for b in branches}
        self.assertEqual(b_map["main"]["actual_overage_credits"], 500)
        self.assertEqual(b_map["feat/formatting"]["actual_overage_credits"], 50)


if __name__ == "__main__":
    unittest.main()
