"""
Unit tests for What-If Workload Simulator (Milestone 21).

Tests token breakdown, turn cost calculations, Gemini burst and credit spillover,
Claude/GPT hard 429 lockout dynamics (ADR-019 & ADR-030), multi-tier comparisons,
archetype presets, and boundary edge cases.
"""

import unittest

from src.simulator import (
    DEFAULT_CREDIT_COST_GBP,
    DEFAULT_CREDIT_COST_USD,
    calculate_turn_cost,
    calculate_turn_tokens,
    compare_plan_tiers,
    get_archetype_presets,
    get_model_rates,
    get_provider_quota_track,
    simulate_archetype,
    simulate_turn_sequence,
    simulate_workload,
)


class TestTurnTokens(unittest.TestCase):
    def test_calculate_turn_tokens_fraction(self):
        """Test calculation when cache hit ratio is provided as a fraction [0.0, 1.0]."""
        res = calculate_turn_tokens(
            prompt_tokens=50000,
            cache_hit_ratio=0.80,
            thinking_tokens=2000,
            answer_tokens=1000,
        )
        self.assertEqual(res["cached_tokens"], 40000)
        self.assertEqual(res["prompt_tokens_uncached"], 10000)
        self.assertEqual(res["thinking_tokens"], 2000)
        self.assertEqual(res["answer_tokens"], 1000)
        self.assertEqual(res["total_input_tokens"], 50000)
        self.assertEqual(res["total_output_tokens"], 3000)
        self.assertEqual(res["total_processed_tokens"], 53000)
        self.assertEqual(res["cache_hit_ratio_pct"], 80.0)

    def test_calculate_turn_tokens_percentage(self):
        """Test calculation when cache hit ratio is provided as a percentage [0.0, 100.0]."""
        res = calculate_turn_tokens(
            prompt_tokens=100000,
            cache_hit_ratio=85.0,
            thinking_tokens=5000,
            answer_tokens=2500,
        )
        self.assertEqual(res["cached_tokens"], 85000)
        self.assertEqual(res["prompt_tokens_uncached"], 15000)
        self.assertEqual(res["total_input_tokens"], 100000)
        self.assertEqual(res["total_output_tokens"], 7500)
        self.assertEqual(res["total_processed_tokens"], 107500)
        self.assertEqual(res["cache_hit_ratio_pct"], 85.0)

    def test_calculate_turn_tokens_edge_cases(self):
        """Test 0% cache hit, 100% cache hit, zero tokens, and out-of-bound ratios."""
        # 0% cache hit
        res_zero = calculate_turn_tokens(50000, 0.0, 1000, 500)
        self.assertEqual(res_zero["cached_tokens"], 0)
        self.assertEqual(res_zero["prompt_tokens_uncached"], 50000)
        self.assertEqual(res_zero["cache_hit_ratio_pct"], 0.0)

        # 100% cache hit
        res_full = calculate_turn_tokens(50000, 1.0, 1000, 500)
        self.assertEqual(res_full["cached_tokens"], 50000)
        self.assertEqual(res_full["prompt_tokens_uncached"], 0)
        self.assertEqual(res_full["cache_hit_ratio_pct"], 100.0)

        # 100% via percentage
        res_full_pct = calculate_turn_tokens(50000, 100.0, 1000, 500)
        self.assertEqual(res_full_pct["cached_tokens"], 50000)
        self.assertEqual(res_full_pct["prompt_tokens_uncached"], 0)
        self.assertEqual(res_full_pct["cache_hit_ratio_pct"], 100.0)

        # Zero tokens
        res_empty = calculate_turn_tokens(0, 0.5, 0, 0)
        self.assertEqual(res_empty["total_input_tokens"], 0)
        self.assertEqual(res_empty["total_output_tokens"], 0)
        self.assertEqual(res_empty["total_processed_tokens"], 0)
        self.assertEqual(res_empty["cache_hit_ratio_pct"], 0.0)

        # Clamping negative and > 100
        res_neg = calculate_turn_tokens(1000, -0.5, 0, 0)
        self.assertEqual(res_neg["cached_tokens"], 0)
        res_over = calculate_turn_tokens(1000, 150.0, 0, 0)
        self.assertEqual(res_over["cached_tokens"], 1000)


class TestTurnCost(unittest.TestCase):
    def test_calculate_turn_cost(self):
        """Test USD and GBP cost computations based on rate card."""
        tokens = {
            "prompt_tokens_uncached": 10000,
            "cached_tokens": 40000,
            "total_output_tokens": 3000,
        }
        rates = {
            "prompt_uncached": 0.75,
            "prompt_cached": 0.075,
            "candidate_output": 3.75,
        }
        # 10000/1e6*0.75 = 0.0075
        # 40000/1e6*0.075 = 0.003
        # 3000/1e6*3.75 = 0.01125
        # total_usd = 0.02175
        # gbp = 0.02175 * 0.79 = 0.0171825
        cost = calculate_turn_cost(tokens, rates, fx_rate=0.79)
        self.assertAlmostEqual(cost["cost_usd"], 0.02175, places=5)
        self.assertAlmostEqual(cost["cost_gbp"], 0.017183, places=5)

    def test_calculate_turn_cost_zero(self):
        """Zero tokens must yield zero cost."""
        tokens = {
            "prompt_tokens_uncached": 0,
            "cached_tokens": 0,
            "total_output_tokens": 0,
        }
        rates = {"prompt_uncached": 0.75, "prompt_cached": 0.075, "candidate_output": 3.75}
        cost = calculate_turn_cost(tokens, rates, fx_rate=0.79)
        self.assertEqual(cost["cost_usd"], 0.0)
        self.assertEqual(cost["cost_gbp"], 0.0)


class TestProviderRouting(unittest.TestCase):
    def test_get_provider_quota_track(self):
        """Verify dynamic classification into Gemini vs Claude/GPT silos (ADR-019)."""
        self.assertEqual(get_provider_quota_track("1318"), "gemini")  # Flash High
        self.assertEqual(get_provider_quota_track("1016"), "gemini")  # Pro High
        self.assertEqual(get_provider_quota_track("1050"), "gemini")  # Flash Lite
        self.assertEqual(get_provider_quota_track("1026"), "claude_gpt")  # Claude Opus
        self.assertEqual(get_provider_quota_track("1035"), "claude_gpt")  # Claude Sonnet
        self.assertEqual(get_provider_quota_track("342"), "claude_gpt")  # GPT OSS
        self.assertEqual(get_provider_quota_track("claude-3-7-sonnet"), "claude_gpt")
        self.assertEqual(get_provider_quota_track("gpt-4o"), "claude_gpt")
        self.assertEqual(get_provider_quota_track("gemini-2.5-pro"), "gemini")


class TestSimulateWorkloadGemini(unittest.TestCase):
    def test_gemini_safe_workload(self):
        """Simulate a modest Gemini Flash workload well within Pro 5h burst limit."""
        sim = simulate_workload(
            model_id="1318",
            turn_count=25,
            prompt_tokens=50000,
            cache_hit_ratio_pct=80.0,
            thinking_tokens=2000,
            answer_tokens=1000,
            duration_minutes_per_turn=2.0,
            plan_tier="pro",
        )
        self.assertEqual(sim["turn_count"], 25)
        self.assertEqual(sim["provider_track"], "gemini")
        self.assertFalse(sim["burst_exhausted"])
        self.assertIsNone(sim["turns_to_exhaustion"])
        self.assertIsNone(sim["time_to_exhaustion_minutes"])
        self.assertEqual(sim["over_burst_usd"], 0.0)
        self.assertEqual(sim["over_burst_turns"], 0)
        self.assertEqual(sim["status_key"], "safe")
        self.assertEqual(sim["status_label"], "Safe Zone")
        self.assertEqual(sim["risk_level"], "SAFE")
        self.assertTrue(sim["credit_spillover_applicable"])
        self.assertEqual(sim["credits_debited"], 0)
        self.assertEqual(sim["credit_cost_gbp"], 0.0)
        self.assertEqual(sim["credit_cost_usd"], 0.0)
        self.assertFalse(sim["hard_429_block_risk"])
        self.assertEqual(len(sim["turns_trajectory"]), 25)
        self.assertIn("Safe to proceed", sim["recommendation"])

    def test_gemini_exceeding_burst_spillover(self):
        """
        Simulate an intense Gemini Pro workload (1016) exceeding the $20 Pro 5h burst capacity.
        Verifies detection of turns_to_exhaustion, Google One credit bank spillover, and cooldown status.
        """
        # 1016 rates: prompt_uncached=2.00, cached=0.20, output=12.00. credits_per_turn=15.0
        # 120k prompt (88% cache hit -> 14.4k uncached, 105.6k cached), 9.5k output
        # ~ $0.16392 / turn. 200 turns = ~ $32.78 spend. Burst capacity = $20.00.
        sim = simulate_workload(
            model_id="1016",
            turn_count=200,
            prompt_tokens=120000,
            cache_hit_ratio_pct=88.0,
            thinking_tokens=8000,
            answer_tokens=1500,
            duration_minutes_per_turn=2.5,
            plan_tier="pro",
            initial_quota_state={"credits_remaining": 500},
        )
        self.assertTrue(sim["burst_exhausted"])
        self.assertIsNotNone(sim["turns_to_exhaustion"])
        self.assertGreater(sim["turns_to_exhaustion"], 100)
        self.assertLess(sim["turns_to_exhaustion"], 150)
        self.assertIsNotNone(sim["time_to_exhaustion_minutes"])
        self.assertGreater(sim["over_burst_usd"], 10.0)
        self.assertGreater(sim["over_burst_turns"], 50)
        self.assertEqual(sim["status_key"], "cooldown")
        self.assertEqual(sim["status_label"], "Burst Cooldown")
        self.assertEqual(sim["risk_level"], "HIGH_EXHAUSTION")
        self.assertTrue(sim["credit_spillover_applicable"])
        self.assertGreater(sim["credits_debited"], 0)
        self.assertGreater(sim["credit_cost_gbp"], 0.0)
        self.assertGreater(sim["credit_cost_usd"], 0.0)
        # Because credits_remaining was 500 and > 1000 credits were debited:
        self.assertTrue(sim["credit_bank_exhaustion_risk"])
        # Gemini does not trigger hard 429 on burst because of credit spillover
        self.assertFalse(sim["hard_429_block_risk"])
        self.assertIn("Enterprise", sim["recommendation"])


class TestSimulateWorkloadClaudeGPT(unittest.TestCase):
    def test_claude_exceeding_burst_hard_429(self):
        """
        Simulate Claude Opus workload exceeding Claude 5h burst limit ($10.00 for Pro).
        CRITICAL INVARIANT (ADR-019 & ADR-030): Claude has ZERO credit spillover.
        Must flag hard_429_block_risk=True, credits_debited=0, risk_level='CRITICAL_429'.
        """
        # 1026 rates: uncached=15.00, cached=1.50, output=75.00.
        # ~ $0.785 / turn. 35 turns = ~ $27.48. Burst capacity = $10.00.
        sim = simulate_workload(
            model_id="1026",
            turn_count=35,
            prompt_tokens=95000,
            cache_hit_ratio_pct=92.0,
            thinking_tokens=6000,
            answer_tokens=1200,
            duration_minutes_per_turn=2.0,
            plan_tier="pro",
        )
        self.assertEqual(sim["provider_track"], "claude_gpt")
        self.assertTrue(sim["burst_exhausted"])
        self.assertEqual(sim["burst_capacity_usd"], 10.0)
        self.assertIsNotNone(sim["turns_to_exhaustion"])
        self.assertLessEqual(sim["turns_to_exhaustion"], 15)
        self.assertFalse(sim["credit_spillover_applicable"])
        self.assertEqual(sim["credits_debited"], 0)
        self.assertEqual(sim["credit_cost_gbp"], 0.0)
        self.assertEqual(sim["credit_cost_usd"], 0.0)
        self.assertTrue(sim["hard_429_block_risk"])
        self.assertEqual(sim["status_key"], "lockout")
        self.assertEqual(sim["status_label"], "HTTP 429 Lockout")
        self.assertEqual(sim["risk_level"], "CRITICAL_429")
        self.assertIn("HTTP 429", sim["recommendation"])


class TestArchetypePresets(unittest.TestCase):
    def test_get_archetype_presets_structure(self):
        """Verify all 5 standard archetype presets exist and have complete configurations."""
        presets = get_archetype_presets()
        expected_keys = [
            "deep_refactor_swarm",
            "codebase_audit",
            "rapid_prototyping_burst",
            "claude_opus_deep_dive",
            "subagent_fleet",
        ]
        for k in expected_keys:
            self.assertIn(k, presets)
            arch = presets[k]
            self.assertEqual(arch["id"], k)
            self.assertIn("name", arch)
            self.assertIn("model_id", arch)
            self.assertGreater(arch["turn_count"], 0)
            self.assertGreater(arch["prompt_tokens"], 0)
            self.assertGreaterEqual(arch["cache_hit_ratio_pct"], 0.0)
            self.assertGreaterEqual(arch["thinking_tokens"], 0)
            self.assertGreater(arch["answer_tokens"], 0)
            self.assertGreater(arch["duration_minutes_per_turn"], 0.0)
            self.assertIn("description", arch)

    def test_simulate_all_archetypes(self):
        """Verify each archetype preset simulates cleanly without exceptions."""
        presets = get_archetype_presets()
        for arch_id in presets:
            res = simulate_archetype(arch_id, plan_tier="pro")
            self.assertEqual(res["archetype_id"], arch_id)
            self.assertEqual(res["turn_count"], presets[arch_id]["turn_count"])
            self.assertIn(res["status_key"], ["safe", "caution", "cooldown", "lockout"])
            self.assertIn(res["risk_level"], ["SAFE", "MODERATE", "HIGH_EXHAUSTION", "CRITICAL_429"])
            self.assertGreater(res["imputed_value_usd"], 0.0)
            self.assertGreater(res["imputed_value_gbp"], 0.0)

    def test_simulate_archetype_invalid_id(self):
        """Invalid archetype ID must raise ValueError."""
        with self.assertRaises(ValueError):
            simulate_archetype("non_existent_swarm")


class TestComparePlanTiers(unittest.TestCase):
    def test_compare_plan_tiers_pro_burst_vs_enterprise_safe(self):
        """
        Verify tier comparison for an intense workload that exhausts Pro ($20)
        while Enterprise ($100) and Ultra ($200) remain safe.
        """
        workload = {
            "model_id": "1016",
            "turn_count": 200,
            "prompt_tokens": 120000,
            "cache_hit_ratio_pct": 88.0,
            "thinking_tokens": 8000,
            "answer_tokens": 1500,
            "duration_minutes_per_turn": 2.5,
        }
        summaries = compare_plan_tiers(workload)
        self.assertEqual(len(summaries), 3)

        pro = next(s for s in summaries if s["tier"] == "pro")
        ent = next(s for s in summaries if s["tier"] == "enterprise_5x")
        ultra = next(s for s in summaries if s["tier"] == "ultra_10x")

        # Pro exhausts burst
        self.assertTrue(pro["burst_exhausted"])
        self.assertEqual(pro["burst_capacity_usd"], 20.0)
        self.assertEqual(pro["risk_level"], "HIGH_EXHAUSTION")
        self.assertGreater(pro["credits_debited"], 0)

        # Enterprise 5x remains comfortably safe
        self.assertFalse(ent["burst_exhausted"])
        self.assertEqual(ent["burst_capacity_usd"], 100.0)
        self.assertEqual(ent["risk_level"], "SAFE")
        self.assertEqual(ent["credits_debited"], 0)

        # Ultra 10x remains comfortably safe
        self.assertFalse(ultra["burst_exhausted"])
        self.assertEqual(ultra["burst_capacity_usd"], 200.0)
        self.assertEqual(ultra["risk_level"], "SAFE")
        self.assertEqual(ultra["credits_debited"], 0)


class TestEdgeCases(unittest.TestCase):
    def test_zero_turn_count(self):
        """Simulating 0 turns must produce clean zeroed metrics without division by zero."""
        sim = simulate_workload(turn_count=0)
        self.assertEqual(sim["turn_count"], 0)
        self.assertEqual(sim["total_prompt_tokens"], 0)
        self.assertEqual(sim["total_processed_tokens"], 0)
        self.assertEqual(sim["cache_hit_ratio_pct"], 0.0)
        self.assertEqual(sim["imputed_value_usd"], 0.0)
        self.assertEqual(sim["imputed_value_gbp"], 0.0)
        self.assertFalse(sim["burst_exhausted"])
        self.assertIsNone(sim["turns_to_exhaustion"])
        self.assertEqual(sim["over_burst_usd"], 0.0)
        self.assertEqual(sim["over_burst_turns"], 0)
        self.assertEqual(sim["credits_debited"], 0)
        self.assertEqual(len(sim["turns_trajectory"]), 0)
        self.assertEqual(sim["status_key"], "safe")

    def test_weekly_quota_exhaustion_triggers_hierarchical_lockout(self):
        """
        Weekly quota exhaustion overrides burst window and triggers hierarchical HTTP 429 lockout.
        """
        sim = simulate_workload(
            model_id="1318",
            turn_count=10,
            prompt_tokens=50000,
            cache_hit_ratio_pct=80.0,
            initial_quota_state={
                "starting_5h_used_usd": 0.0,
                "starting_weekly_used_usd": 128.95,  # Within 5 cents of $129 Pro weekly limit
            },
            plan_tier="pro",
        )
        self.assertTrue(sim["hard_429_block_risk"])
        self.assertEqual(sim["status_key"], "lockout")
        self.assertEqual(sim["status_label"], "HTTP 429 Lockout")
        self.assertEqual(sim["risk_level"], "CRITICAL_429")
        self.assertIn("Weekly quota limit", sim["recommendation"])

    def test_trajectory_snapshot_fields(self):
        """Verify each turn snapshot in trajectory contains all required fields."""
        sim = simulate_workload(turn_count=3, prompt_tokens=10000)
        self.assertEqual(len(sim["turns_trajectory"]), 3)
        for snap in sim["turns_trajectory"]:
            self.assertIn("turn", snap)
            self.assertIn("model_id", snap)
            self.assertIn("cost_usd", snap)
            self.assertIn("cumulative_5h_usd", snap)
            self.assertIn("used_5h_pct", snap)
            self.assertIn("remaining_5h_pct", snap)
            self.assertIn("exhausted", snap)


if __name__ == "__main__":
    unittest.main()
