"""Unit tests for src/aggregator.py."""

import datetime
import unittest
from src.aggregator import (
    compute_turn_cost,
    compute_rolling_window_telemetry,
    compute_window_recovery_schedule,
    compute_historical_peaks,
    aggregate_conversation_telemetry,
    aggregate_global_telemetry,
    calculate_credit_burn,
    get_provider_quota_track,
    classify_turn_type,
    compute_subagent_metrics,
    compute_exhaustion_alarm_state,
    compute_daily_velocity,
    SUBAGENT_MODEL_IDS,
    load_pricing,
)


class TestAggregator(unittest.TestCase):

    def setUp(self):
        self.pricing_models = {
            "1318": {
                "name": "Gemini 3.8 Flash (High)",
                "family": "gemini-flash",
                "rates_per_million": {
                    "prompt_uncached": 0.10,
                    "prompt_cached": 0.025,
                    "candidate_output": 0.40,
                },
            },
            "1319": {
                "name": "Gemini 3.1 Pro",
                "family": "gemini-pro",
                "rates_per_million": {
                    "prompt_uncached": 1.25,
                    "prompt_cached": 0.3125,
                    "candidate_output": 5.00,
                },
            },
            "1050": {
                "name": "Gemini Flash Lite (Subagent)",
                "family": "gemini-flash-lite",
                "rates_per_million": {
                    "prompt_uncached": 0.075,
                    "prompt_cached": 0.01875,
                    "candidate_output": 0.30,
                },
            },
            "1035": {
                "name": "Claude Sonnet 4.6 (Thinking)",
                "family": "claude-sonnet",
                "rates_per_million": {
                    "prompt_uncached": 3.00,
                    "prompt_cached": 0.30,
                    "candidate_output": 15.00,
                },
            },
            "1026": {
                "name": "Claude Opus 4.6 (Thinking)",
                "family": "claude-opus",
                "rates_per_million": {
                    "prompt_uncached": 15.00,
                    "prompt_cached": 1.50,
                    "candidate_output": 75.00,
                },
            },
            "342": {
                "name": "GPT-OSS 120B (Medium)",
                "family": "gpt-oss",
                "rates_per_million": {
                    "prompt_uncached": 0.15,
                    "prompt_cached": 0.00,
                    "candidate_output": 0.60,
                },
            },
            "default": {
                "name": "Default Model",
                "family": "gemini-flash",
                "rates_per_million": {
                    "prompt_uncached": 0.10,
                    "prompt_cached": 0.025,
                    "candidate_output": 0.40,
                },
            },
        }

    def test_compute_turn_cost(self):
        turn = {
            "prompt_tokens_uncached": 10000,
            "cached_tokens": 100000,
            "output_tokens_total": 5000,
        }
        rates = self.pricing_models["1318"]["rates_per_million"]
        cost = compute_turn_cost(turn, rates)
        self.assertAlmostEqual(cost, 0.0055, places=5)

    def test_rolling_window_filtering_and_model_partition(self):
        ref_time = datetime.datetime(2026, 9, 5, 12, 0, 0, tzinfo=datetime.timezone.utc)
        turns = [
            # T - 6h (outside 5h window)
            {
                "timestamp": (ref_time - datetime.timedelta(hours=6)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 5000,
                "output_tokens_total": 200,
                "thinking_tokens": 100,
                "answer_tokens": 100,
            },
            # T - 3h (inside 5h window, model 1318)
            {
                "timestamp": (ref_time - datetime.timedelta(hours=3)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 4000,
                "cached_tokens": 16000,
                "output_tokens_total": 500,
                "thinking_tokens": 300,
                "answer_tokens": 200,
            },
            # T - 1h (inside 5h window, model 1319 Pro)
            {
                "timestamp": (ref_time - datetime.timedelta(hours=1)).isoformat(),
                "model_id": "1319",
                "prompt_tokens_uncached": 2000,
                "cached_tokens": 8000,
                "output_tokens_total": 300,
                "thinking_tokens": 150,
                "answer_tokens": 150,
            },
        ]

        res = compute_rolling_window_telemetry(turns, window_hours=5.0, reference_time=ref_time, pricing_models=self.pricing_models)
        self.assertEqual(res["turn_count"], 2)
        # 4000 + 2000 = 6000 uncached
        self.assertEqual(res["prompt_tokens_uncached"], 6000)
        # 16000 + 8000 = 24000 cached
        self.assertEqual(res["cached_tokens"], 24000)
        self.assertEqual(res["total_input_tokens"], 30000)
        self.assertEqual(res["total_output_tokens"], 800)
        self.assertEqual(res["cache_hit_ratio_pct"], 80.0)

        # Verify model breakdown
        by_model = {m["model_id"]: m for m in res["by_model"]}
        self.assertIn("1318", by_model)
        self.assertIn("1319", by_model)
        self.assertEqual(by_model["1318"]["turn_count"], 1)
        self.assertEqual(by_model["1319"]["turn_count"], 1)
        self.assertEqual(by_model["1318"]["cached_tokens"], 16000)
        self.assertEqual(by_model["1319"]["cached_tokens"], 8000)

    def test_window_recovery_schedule(self):
        ref_time = datetime.datetime(2026, 9, 5, 12, 0, 0, tzinfo=datetime.timezone.utc)
        turns = [
            # T - 4h (ages out in 1h = 60m)
            {
                "step_idx": 10,
                "timestamp": (ref_time - datetime.timedelta(hours=4)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 5000,
                "cached_tokens": 20000,
                "output_tokens_total": 1000,
            },
            # T - 2h (ages out in 3h = 180m)
            {
                "step_idx": 25,
                "timestamp": (ref_time - datetime.timedelta(hours=2)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 2000,
                "cached_tokens": 10000,
                "output_tokens_total": 500,
            },
        ]

        schedule = compute_window_recovery_schedule(turns, window_hours=5.0, reference_time=ref_time, pricing_models=self.pricing_models)
        self.assertEqual(len(schedule), 2)
        # First turn to age out should be step 10
        self.assertEqual(schedule[0]["step_idx"], 10)
        self.assertAlmostEqual(schedule[0]["minutes_remaining"], 60, delta=2)
        self.assertEqual(schedule[0]["tokens_to_recover"], 26000)
        self.assertEqual(schedule[0]["cumulative_tokens_recovered"], 26000)

        # Second turn to age out
        self.assertEqual(schedule[1]["step_idx"], 25)
        self.assertAlmostEqual(schedule[1]["minutes_remaining"], 180, delta=2)
        self.assertEqual(schedule[1]["tokens_to_recover"], 12500)
        self.assertEqual(schedule[1]["cumulative_tokens_recovered"], 38500)

    def test_compute_historical_peaks(self):
        base_time = datetime.datetime(2026, 9, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
        turns = [
            {"timestamp": (base_time + datetime.timedelta(hours=1)).isoformat(), "prompt_tokens_uncached": 10000, "cached_tokens": 90000, "output_tokens_total": 5000},
            {"timestamp": (base_time + datetime.timedelta(hours=2)).isoformat(), "prompt_tokens_uncached": 20000, "cached_tokens": 180000, "output_tokens_total": 10000},
            {"timestamp": (base_time + datetime.timedelta(hours=10)).isoformat(), "prompt_tokens_uncached": 5000, "cached_tokens": 10000, "output_tokens_total": 1000},
        ]
        peaks = compute_historical_peaks(turns, pricing_models=self.pricing_models)
        # In a 5h window, turns 1 & 2 overlap: 105,000 + 210,000 = 315,000
        self.assertEqual(peaks["peak_5h_tokens"], 315000)
        # In 7 days, all 3 turns overlap: 315,000 + 16,000 = 331,000
        self.assertEqual(peaks["peak_1w_tokens"], 331000)

    def test_aggregate_global_telemetry_with_quotas(self):
        ref_time = datetime.datetime(2026, 9, 5, 12, 0, 0, tzinfo=datetime.timezone.utc)
        meta = {"convo_id": "c1", "title": "Convo 1", "workspace": "repo-x"}
        turns = [
            {
                "step_idx": 1,
                "timestamp": (ref_time - datetime.timedelta(hours=1)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 5000,
                "cached_tokens": 15000,
                "total_input_tokens": 20000,
                "output_tokens_total": 1000,
                "thinking_tokens": 600,
                "answer_tokens": 400,
                "cache_hit_ratio_pct": 75.0,
            }
        ]
        conv_summary = aggregate_conversation_telemetry(meta, turns, self.pricing_models)
        res = aggregate_global_telemetry([conv_summary], self.pricing_models, reference_time=ref_time, exhaustion_intervals=[])

        self.assertIn("quotas", res)
        self.assertIn("rolling_5h", res["quotas"])
        self.assertIn("rolling_1w", res["quotas"])
        self.assertIn("recovery_schedule", res["quotas"]["rolling_5h"])
        self.assertEqual(res["summary"]["subscription_status"], "SAFE_IN_QUOTA")
        self.assertEqual(res["summary"]["total_credit_burn_usd"], 0.0)

    def test_calculate_credit_burn_model_calibration(self):
        # Model 1318 Flash High 299 turns = 748 credits ($7.48 / £7.18)
        burn = calculate_credit_burn("1318", turns_count=299)
        self.assertEqual(round(burn["credits"]), 748)
        self.assertEqual(round(burn["credit_burn_usd"], 2), 7.48)
        self.assertEqual(round(burn["credit_burn_gbp"], 2), 7.18)

        # Pro model 1016 10 turns = 150 credits ($1.50 / £1.44)
        burn_pro = calculate_credit_burn("1016", turns_count=10)
        self.assertEqual(round(burn_pro["credits"]), 150)
        self.assertEqual(round(burn_pro["credit_burn_usd"], 2), 1.50)
        self.assertEqual(round(burn_pro["credit_burn_gbp"], 2), 1.44)

    def test_aggregate_global_with_exhaustion_intervals(self):
        ref_time = datetime.datetime(2026, 9, 5, 14, 0, 0, tzinfo=datetime.timezone.utc)
        meta = {"convo_id": "c1", "title": "Overage Session", "workspace": "repo-x"}
        # Turn occurs inside exhaustion interval [13:30, 14:30]
        turn_overage = {
            "step_idx": 1,
            "timestamp": datetime.datetime(2026, 9, 5, 13, 35, 0, tzinfo=datetime.timezone.utc).isoformat(),
            "model_id": "1318",
            "prompt_tokens_uncached": 5000,
            "cached_tokens": 15000,
            "total_input_tokens": 20000,
            "output_tokens_total": 1000,
        }
        conv_summary = aggregate_conversation_telemetry(meta, [turn_overage], self.pricing_models)
        intervals = [{
            "start": datetime.datetime(2026, 9, 5, 13, 30, 0, tzinfo=datetime.timezone.utc),
            "end": datetime.datetime(2026, 9, 5, 14, 30, 0, tzinfo=datetime.timezone.utc),
            "code": 429,
            "reason": "RESOURCE_EXHAUSTED",
        }]

        res = aggregate_global_telemetry(
            [conv_summary],
            self.pricing_models,
            reference_time=ref_time,
            exhaustion_intervals=intervals,
        )

        self.assertGreater(res["summary"]["total_ai_credits_burned"], 0)
        self.assertGreater(res["summary"]["total_credit_burn_usd"], 0.0)
        self.assertGreater(res["summary"]["total_credit_burn_gbp"], 0.0)
        self.assertEqual(res["summary"]["subscription_status"], "BURNING_AI_CREDITS")
        self.assertIn("hourly_credit_activity", res)
        self.assertEqual(len(res["hourly_credit_activity"]), 1)
        self.assertEqual(res["hourly_credit_activity"][0]["turns_count"], 1)
        self.assertIn("credit_burn_gbp", res["hourly_credit_activity"][0])

    def test_overage_strictly_anchored_to_429_log_signal(self):
        # Even with massive 200M token burst, without 429 log signal, credit burn is 0
        ref_time = datetime.datetime(2026, 8, 28, 16, 0, 0, tzinfo=datetime.timezone.utc)
        meta = {"convo_id": "c_heavy", "title": "Heavy Pro Session", "workspace": "repo-pro"}
        huge_turn = {
            "step_idx": 1,
            "timestamp": datetime.datetime(2026, 8, 28, 15, 30, 0, tzinfo=datetime.timezone.utc).isoformat(),
            "model_id": "1298",
            "prompt_tokens_uncached": 50_000_000,
            "cached_tokens": 150_000_000,
            "total_input_tokens": 200_000_000,
            "output_tokens_total": 500_000,
        }
        conv_summary = aggregate_conversation_telemetry(meta, [huge_turn], self.pricing_models)

        res = aggregate_global_telemetry(
            [conv_summary],
            self.pricing_models,
            reference_time=ref_time,
            exhaustion_intervals=[],  # No 429 logged!
        )

        self.assertEqual(res["summary"]["total_ai_credits_burned"], 0)
        self.assertEqual(res["summary"]["total_credit_burn_usd"], 0.0)
        self.assertEqual(res["summary"]["total_credit_burn_gbp"], 0.0)
        self.assertEqual(res["summary"]["subscription_status"], "SAFE_IN_QUOTA")
        self.assertEqual(res["hourly_credit_activity"], [])

    def test_thursday_weekly_cycle_bounds(self):
        from src.aggregator import get_weekly_cycle_bounds
        # Saturday Sep 5, 2026 at 16:18 UTC (17:18 BST)
        now = datetime.datetime(2026, 9, 5, 16, 18, 0, tzinfo=datetime.timezone.utc)
        bounds = get_weekly_cycle_bounds(now)
        self.assertEqual(bounds["reset_day_name"], "Thursday")
        self.assertEqual(bounds["cycle_start_utc"], "2026-09-03T18:00:00+00:00")
        self.assertEqual(bounds["cycle_end_utc"], "2026-09-10T18:00:00+00:00")
        self.assertEqual(bounds["days_remaining"], 5)
        self.assertIn("10 Sep 2026", bounds["reset_display"])

    def test_monthly_billing_bounds(self):
        from src.aggregator import get_monthly_billing_bounds
        # Saturday Sep 5, 2026 at 16:18 UTC
        now = datetime.datetime(2026, 9, 5, 16, 18, 0, tzinfo=datetime.timezone.utc)
        bounds = get_monthly_billing_bounds(now, billing_day=24)
        self.assertEqual(bounds["billing_day"], 24)
        self.assertEqual(bounds["cycle_start_utc"], "2026-08-24T18:00:00+00:00")
        self.assertEqual(bounds["renewal_date"], "2026-09-24T18:00:00+00:00")
        self.assertEqual(bounds["days_remaining"], 19)
        self.assertEqual(bounds["monthly_credit_allowance"], 2500)
        self.assertEqual(bounds["monthly_plan_price_gbp"], 18.99)

    def test_decoupled_monthly_subscription_and_credit_bank(self):
        ref_time = datetime.datetime(2026, 9, 5, 16, 0, 0, tzinfo=datetime.timezone.utc)
        meta = {"convo_id": "c_sub", "title": "Subscription Test", "workspace": "repo-test"}
        turn = {
            "step_idx": 1,
            "timestamp": datetime.datetime(2026, 9, 5, 15, 0, 0, tzinfo=datetime.timezone.utc).isoformat(),
            "model_id": "1318",
            "prompt_tokens_uncached": 10000,
            "cached_tokens": 40000,
            "total_input_tokens": 50000,
            "output_tokens_total": 500,
        }
        conv_summary = aggregate_conversation_telemetry(meta, [turn], self.pricing_models)
        intervals = [{
            "incident_id": "exc-test",
            "hour_timestamp": "2026-09-05T13:00:00Z",
            "hour_display": "05 Sep 2026, 13:00:00 UTC",
            "start": datetime.datetime(2026, 9, 5, 13, 0, 0, tzinfo=datetime.timezone.utc),
            "end": datetime.datetime(2026, 9, 5, 14, 0, 0, tzinfo=datetime.timezone.utc),
            "credits_burned": 748,
            "credit_burn_usd": 7.48,
            "credit_burn_gbp": 7.18,
            "turns_count": 299,
            "from_ledger": True,
        }]
        res = aggregate_global_telemetry(
            [conv_summary],
            self.pricing_models,
            reference_time=ref_time,
            exhaustion_intervals=intervals,
        )
        s = res["summary"]
        self.assertEqual(s["monthly_subscription_price_gbp"], 18.99)
        self.assertEqual(s["credit_bank_total"], 2500)
        self.assertEqual(s["total_ai_credits_burned"], 748)
        self.assertEqual(s["credits_remaining"], 2500 - 748)
        self.assertEqual(s["total_credit_burn_gbp"], 7.18)
        self.assertEqual(s["total_credit_burn_usd"], 7.48)
        self.assertIn("19 days", s["monthly_renewal_human"])
        self.assertNotIn("1 hours", s["monthly_renewal_human"])

    def test_get_provider_quota_track(self):
        # Desktop Gemini models
        self.assertEqual(get_provider_quota_track("1318", self.pricing_models), "gemini")
        self.assertEqual(get_provider_quota_track("1319", self.pricing_models), "gemini")
        # Subagent Gemini models
        self.assertEqual(get_provider_quota_track("1050", self.pricing_models), "gemini")
        # Claude & GPT models
        self.assertEqual(get_provider_quota_track("1035", self.pricing_models), "claude_gpt")
        self.assertEqual(get_provider_quota_track("1026", self.pricing_models), "claude_gpt")
        self.assertEqual(get_provider_quota_track("342", self.pricing_models), "claude_gpt")

        # Census testing against load_pricing config
        self.assertEqual(get_provider_quota_track("1016"), "gemini")
        self.assertEqual(get_provider_quota_track("1322"), "gemini")
        self.assertEqual(get_provider_quota_track("1036"), "gemini")
        self.assertEqual(get_provider_quota_track("1071"), "gemini")
        self.assertEqual(get_provider_quota_track("1072"), "gemini")
        self.assertEqual(get_provider_quota_track("1073"), "gemini")
        self.assertEqual(get_provider_quota_track("1298"), "gemini")
        self.assertEqual(get_provider_quota_track("1299"), "gemini")
        self.assertEqual(get_provider_quota_track("1300"), "gemini")
        self.assertEqual(get_provider_quota_track("1320"), "gemini")
        self.assertEqual(get_provider_quota_track("1301"), "gemini")
        self.assertEqual(get_provider_quota_track("1132"), "gemini")
        self.assertEqual(get_provider_quota_track("1020"), "gemini")

        # Dynamic string fallback
        self.assertEqual(get_provider_quota_track("claude-3-7-sonnet"), "claude_gpt")
        self.assertEqual(get_provider_quota_track("gpt-4o"), "claude_gpt")
        self.assertEqual(get_provider_quota_track("gemini-2.5-flash"), "gemini")

    def test_zero_cross_track_contamination(self):
        """Verify adding Claude turns does not affect Gemini tokens or recovery schedules, and vice versa."""
        ref_time = datetime.datetime(2026, 9, 5, 16, 0, 0, tzinfo=datetime.timezone.utc)
        meta_gemini = {"convo_id": "c_gemini", "title": "Gemini Session", "workspace": "repo"}
        gemini_turns = [
            {
                "step_idx": 1,
                "timestamp": (ref_time - datetime.timedelta(hours=2)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 5000,
                "cached_tokens": 20000,
                "output_tokens_total": 500,
                "thinking_tokens": 200,
                "answer_tokens": 300,
            }
        ]
        conv_g = aggregate_conversation_telemetry(meta_gemini, gemini_turns, self.pricing_models)

        # Baseline: run with only Gemini turns
        baseline_res = aggregate_global_telemetry(
            [conv_g],
            self.pricing_models,
            reference_time=ref_time,
            exhaustion_intervals=[],
        )
        g_base_5h = baseline_res["quotas"]["providers"]["gemini"]["five_hour"]
        g_base_wk = baseline_res["quotas"]["providers"]["gemini"]["weekly"]

        # Now create an additional Claude session
        meta_claude = {"convo_id": "c_claude", "title": "Claude Session", "workspace": "repo"}
        claude_turns = [
            {
                "step_idx": 1,
                "timestamp": (ref_time - datetime.timedelta(hours=1)).isoformat(),
                "model_id": "1035",  # Claude Sonnet Thinking
                "prompt_tokens_uncached": 50000,
                "cached_tokens": 100000,
                "output_tokens_total": 4000,
                "thinking_tokens": 2000,
                "answer_tokens": 2000,
            }
        ]
        conv_c = aggregate_conversation_telemetry(meta_claude, claude_turns, self.pricing_models)

        # Combined telemetry
        combined_res = aggregate_global_telemetry(
            [conv_g, conv_c],
            self.pricing_models,
            reference_time=ref_time,
            exhaustion_intervals=[],
        )

        g_comb_5h = combined_res["quotas"]["providers"]["gemini"]["five_hour"]
        g_comb_wk = combined_res["quotas"]["providers"]["gemini"]["weekly"]
        c_comb_5h = combined_res["quotas"]["providers"]["claude_gpt"]["five_hour"]
        c_comb_wk = combined_res["quotas"]["providers"]["claude_gpt"]["weekly"]

        # Invariant 1: Gemini metrics in combined_res must be 100% identical to baseline
        self.assertEqual(g_comb_5h["total_processed_tokens"], g_base_5h["total_processed_tokens"])
        self.assertEqual(g_comb_5h["turn_count"], g_base_5h["turn_count"])
        self.assertEqual(g_comb_5h["prompt_tokens_uncached"], g_base_5h["prompt_tokens_uncached"])
        self.assertEqual(g_comb_5h["cached_tokens"], g_base_5h["cached_tokens"])
        self.assertEqual(g_comb_5h["total_output_tokens"], g_base_5h["total_output_tokens"])
        self.assertEqual(g_comb_wk["total_processed_tokens"], g_base_wk["total_processed_tokens"])
        self.assertEqual(g_comb_wk["turn_count"], g_base_wk["turn_count"])
        self.assertEqual(len(g_comb_5h["recovery_schedule"]), len(g_base_5h["recovery_schedule"]))
        self.assertEqual(
            g_comb_5h["recovery_schedule"][0]["tokens_to_recover"],
            g_base_5h["recovery_schedule"][0]["tokens_to_recover"],
        )

        # Invariant 2: Claude metrics are strictly populated from Claude turns
        self.assertEqual(c_comb_5h["turn_count"], 1)
        self.assertEqual(c_comb_5h["total_processed_tokens"], 50000 + 100000 + 4000)
        self.assertEqual(c_comb_wk["turn_count"], 1)

        # Invariant 3: Step-level routing in heterogeneous multi-agent swarms
        # A single conversation where Turn 1 is Claude parent and Turn 2 is Gemini subagent
        meta_hetero = {"convo_id": "c_hetero", "title": "Hetero Swarm", "workspace": "repo"}
        swarm_turns = [
            {
                "step_idx": 1,
                "timestamp": (ref_time - datetime.timedelta(minutes=30)).isoformat(),
                "model_id": "1035",  # Claude parent
                "prompt_tokens_uncached": 12000,
                "cached_tokens": 40000,
                "output_tokens_total": 1000,
            },
            {
                "step_idx": 2,
                "timestamp": (ref_time - datetime.timedelta(minutes=20)).isoformat(),
                "model_id": "1050",  # Gemini Flash Lite subagent
                "prompt_tokens_uncached": 3000,
                "cached_tokens": 15000,
                "output_tokens_total": 400,
            },
        ]
        conv_hetero = aggregate_conversation_telemetry(meta_hetero, swarm_turns, self.pricing_models)
        swarm_res = aggregate_global_telemetry(
            [conv_hetero],
            self.pricing_models,
            reference_time=ref_time,
            exhaustion_intervals=[],
        )
        g_swarm_5h = swarm_res["quotas"]["providers"]["gemini"]["five_hour"]
        c_swarm_5h = swarm_res["quotas"]["providers"]["claude_gpt"]["five_hour"]

        # Step 2 routed to Gemini silo
        self.assertEqual(g_swarm_5h["turn_count"], 1)
        self.assertEqual(g_swarm_5h["total_processed_tokens"], 3000 + 15000 + 400)

        # Step 1 routed to Claude/GPT silo
        self.assertEqual(c_swarm_5h["turn_count"], 1)
        self.assertEqual(c_swarm_5h["total_processed_tokens"], 12000 + 40000 + 1000)

    def test_dual_track_quota_payload(self):
        ref_time = datetime.datetime(2026, 9, 5, 16, 0, 0, tzinfo=datetime.timezone.utc)
        meta = {"convo_id": "c_payload", "title": "Payload Test", "workspace": "repo"}
        turns = [
            {
                "step_idx": 1,
                "timestamp": (ref_time - datetime.timedelta(hours=2)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 5000,
                "output_tokens_total": 200,
            },
            {
                "step_idx": 2,
                "timestamp": (ref_time - datetime.timedelta(hours=1)).isoformat(),
                "model_id": "1035",
                "prompt_tokens_uncached": 2000,
                "cached_tokens": 8000,
                "output_tokens_total": 300,
            },
        ]
        conv = aggregate_conversation_telemetry(meta, turns, self.pricing_models)
        res = aggregate_global_telemetry([conv], self.pricing_models, reference_time=ref_time, exhaustion_intervals=[])

        q = res["quotas"]
        self.assertIn("providers", q)
        self.assertIn("gemini", q["providers"])
        self.assertIn("claude_gpt", q["providers"])

        g = q["providers"]["gemini"]
        cg = q["providers"]["claude_gpt"]

        # Invariants & Schema
        self.assertTrue(g["credit_spillover"])
        self.assertFalse(cg["credit_spillover"])
        self.assertEqual(g["track"], "gemini")
        self.assertEqual(cg["track"], "claude_gpt")

        self.assertIn("five_hour", g)
        self.assertIn("weekly", g)
        self.assertIn("five_hour", cg)
        self.assertIn("weekly", cg)

        self.assertIn("Thursday", g["weekly"]["reset_display"])
        self.assertTrue("refresh" in g["weekly"]["message"].lower() or "fully" in g["weekly"]["message"].lower())
        self.assertTrue("refresh" in cg["weekly"]["message"].lower() or "fully" in cg["weekly"]["message"].lower())

    def test_read_conversation_metadata(self):
        import sqlite3
        import tempfile
        from pathlib import Path
        from src.telemetry_reader import (
            read_conversation_metadata,
            read_single_conversation_metadata,
            clean_workspace_path,
        )
        # Test clean_workspace_path URL decoding
        p, n = clean_workspace_path("file:///Users/alice/Projects/My%20App")
        self.assertEqual(p, "/Users/alice/Projects/My App")
        self.assertEqual(n, "My App")

        # Test deterministic extraction using synthetic database
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "test_convo.db"
            conn = sqlite3.connect(str(db))
            conn.execute("CREATE TABLE trajectory_metadata_blob (id TEXT PRIMARY KEY, data BLOB)")
            uri = b"file:///Users/alice/Projects/My%20App"
            br = b"feat/login"
            sub_payload = bytes([0x0a, len(uri)]) + uri + bytes([0x22, len(br)]) + br
            outer_payload = bytes([0x0a, len(sub_payload)]) + sub_payload
            conn.execute("INSERT INTO trajectory_metadata_blob VALUES (?, ?)", ("main", outer_payload))
            conn.commit()
            conn.close()

            single = read_single_conversation_metadata(db)
            self.assertEqual(single["workspace_path"], "/Users/alice/Projects/My App")
            self.assertEqual(single["workspace_name"], "My App")
            self.assertEqual(single["git_branch"], "feat/login")

            all_meta = read_conversation_metadata(td)
            self.assertEqual(len(all_meta), 1)
            self.assertIn("test_convo", all_meta)

        # Optional live extraction verification if live conversations are available
        meta = read_conversation_metadata()
        if meta:
            sample = next(iter(meta.values()))
            self.assertIn("workspace_path", sample)
            self.assertIn("git_branch", sample)


    def test_project_and_branch_aggregation(self):
        c1 = {
            "convo_id": "c1",
            "title": "C1",
            "workspace_path": "/Users/test/ProjectA",
            "workspace_name": "ProjectA",
            "git_branch": "main",
            "turn_count": 5,
            "total_input_tokens": 10000,
            "prompt_tokens_uncached": 2000,
            "cached_tokens": 8000,
            "total_output_tokens": 1000,
            "estimated_cost_usd": 0.05,
        }
        c2 = {
            "convo_id": "c2",
            "title": "C2",
            "workspace_path": "/Users/test/ProjectA",
            "workspace_name": "ProjectA",
            "git_branch": "feat/login",
            "turn_count": 3,
            "total_input_tokens": 6000,
            "prompt_tokens_uncached": 1000,
            "cached_tokens": 5000,
            "total_output_tokens": 500,
            "estimated_cost_usd": 0.03,
        }
        c3 = {
            "convo_id": "c3",
            "title": "C3",
            "workspace_path": "/Users/test/ProjectB",
            "workspace_name": "ProjectB",
            "git_branch": "main",
            "turn_count": 2,
            "total_input_tokens": 3000,
            "prompt_tokens_uncached": 1000,
            "cached_tokens": 2000,
            "total_output_tokens": 300,
            "estimated_cost_usd": 0.015,
        }
        res = aggregate_global_telemetry([c1, c2, c3], self.pricing_models, exhaustion_intervals=[])
        self.assertIn("projects", res)
        projects = res["projects"]
        self.assertEqual(len(projects), 2)
        # ProjectA should be first since 16000 + 1500 > 3000 + 300
        pA = projects[0]
        self.assertEqual(pA["project_name"], "ProjectA")
        self.assertEqual(pA["conversation_count"], 2)
        self.assertEqual(pA["turn_count"], 8)
        self.assertEqual(pA["total_input_tokens"], 16000)
        self.assertEqual(len(pA["branches"]), 2)

    def test_branch_level_token_costing(self):
        c1 = {
            "convo_id": "c1",
            "title": "C1",
            "workspace_path": "/Users/test/ProjectA",
            "workspace_name": "ProjectA",
            "git_branch": "main",
            "turn_count": 10,
            "total_input_tokens": 50000,
            "prompt_tokens_uncached": 10000,
            "cached_tokens": 40000,
            "total_output_tokens": 5000,
            "estimated_cost_usd": 0.25,
        }
        c2 = {
            "convo_id": "c2",
            "title": "C2",
            "workspace_path": "/Users/test/ProjectA",
            "workspace_name": "ProjectA",
            "git_branch": "feat/api",
            "turn_count": 6,
            "total_input_tokens": 30000,
            "prompt_tokens_uncached": 5000,
            "cached_tokens": 25000,
            "total_output_tokens": 3000,
            "estimated_cost_usd": 0.15,
        }
        c3 = {
            "convo_id": "c3",
            "title": "C3",
            "workspace_path": "/Users/test/ProjectA",
            "workspace_name": "ProjectA",
            "git_branch": "fix/bug",
            "turn_count": 2,
            "total_input_tokens": 10000,
            "prompt_tokens_uncached": 2000,
            "cached_tokens": 8000,
            "total_output_tokens": 1000,
            "estimated_cost_usd": 0.05,
        }
        res = aggregate_global_telemetry([c1, c2, c3], self.pricing_models, exhaustion_intervals=[])
        self.assertIn("projects", res)
        self.assertGreater(len(res["projects"]), 0)
        p = res["projects"][0]
        branches = p["branches"]
        self.assertEqual(len(branches), 3)

        # Zero leakage assertions
        self.assertEqual(p["total_input_tokens"], sum(b["total_input_tokens"] for b in branches))
        self.assertEqual(p["prompt_tokens_uncached"], sum(b["prompt_tokens_uncached"] for b in branches))
        self.assertEqual(p["cached_tokens"], sum(b["cached_tokens"] for b in branches))
        self.assertEqual(p["total_output_tokens"], sum(b["total_output_tokens"] for b in branches))
        self.assertEqual(p["turn_count"], sum(b["turn_count"] for b in branches))
        self.assertEqual(p["conversation_count"], sum(b["conversation_count"] for b in branches))
        self.assertAlmostEqual(p["estimated_cost_usd"], sum(b["estimated_cost_usd"] for b in branches), places=4)
        self.assertAlmostEqual(p["estimated_cost_gbp"], sum(b["estimated_cost_gbp"] for b in branches), places=4)

    def test_turn_overage_correlation(self):
        meta = {
            "convo_id": "c_overage_test",
            "title": "Turn Overage Correlation Test",
            "workspace_path": "/Users/test/workspace",
            "workspace_name": "workspace",
            "git_branch": "main",
        }
        ref_dt = datetime.datetime(2026, 9, 5, 14, 0, 0, tzinfo=datetime.timezone.utc)
        turns = [
            {
                "step_idx": 1,
                "timestamp": (ref_dt - datetime.timedelta(minutes=30)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 5000,
                "output_tokens_total": 200,
            },
            {
                "step_idx": 2,
                "timestamp": (ref_dt + datetime.timedelta(minutes=15)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 2000,
                "cached_tokens": 6000,
                "output_tokens_total": 300,
            },
            {
                "step_idx": 3,
                "timestamp": (ref_dt + datetime.timedelta(hours=2)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 1500,
                "cached_tokens": 4000,
                "output_tokens_total": 250,
            },
        ]
        intervals = [
            {
                "incident_id": "exc-test-1",
                "start": ref_dt,
                "end": ref_dt + datetime.timedelta(hours=1),
                "credits_burned": 250,
                "credit_burn_gbp": 2.40,
                "credit_burn_usd": 2.50,
                "from_ledger": True,
            }
        ]
        res = aggregate_conversation_telemetry(meta, turns, self.pricing_models, exhaustion_intervals=intervals)

        res_turns = res["turns"]
        self.assertEqual(len(res_turns), 3)
        self.assertFalse(res_turns[0]["is_overage"])
        self.assertTrue(res_turns[1]["is_overage"])
        self.assertFalse(res_turns[2]["is_overage"])

        self.assertEqual(res["turn_count"], 3)
        self.assertEqual(res["subscription_covered_turns"], 2)
        self.assertEqual(res["overage_turns"], 1)
        self.assertEqual(res["subscription_covered_pct"], 66.7)
        self.assertGreater(res["avoided_cost_usd"], 0)
        self.assertGreater(res["avoided_cost_gbp"], 0)

    def test_project_overage_vs_covered_attribution(self):
        ref_dt = datetime.datetime(2026, 9, 5, 14, 0, 0, tzinfo=datetime.timezone.utc)
        ledger_interval = {
            "incident_id": "exc-alpha-ledger",
            "start": ref_dt,
            "end": ref_dt + datetime.timedelta(hours=1),
            "credits_burned": 1179,
            "credit_burn_gbp": 11.31,
            "credit_burn_usd": 11.79,
            "from_ledger": True,
        }

        c_alpha_main = {
            "convo_id": "c_alpha_1",
            "title": "Alpha Main",
            "workspace_path": "/Users/test/ProjectAlpha",
            "workspace_name": "ProjectAlpha",
            "git_branch": "main",
            "turn_count": 2,
            "total_input_tokens": 20000,
            "prompt_tokens_uncached": 5000,
            "cached_tokens": 15000,
            "total_output_tokens": 1000,
            "estimated_cost_usd": 0.10,
            "turns": [
                {
                    "step_idx": 1,
                    "timestamp": (ref_dt + datetime.timedelta(minutes=10)).isoformat(),
                    "model_id": "1318",
                },
                {
                    "step_idx": 2,
                    "timestamp": (ref_dt + datetime.timedelta(minutes=20)).isoformat(),
                    "model_id": "1318",
                },
            ],
        }

        c_alpha_feat = {
            "convo_id": "c_alpha_2",
            "title": "Alpha Feat",
            "workspace_path": "/Users/test/ProjectAlpha",
            "workspace_name": "ProjectAlpha",
            "git_branch": "feat/cool",
            "turn_count": 2,
            "total_input_tokens": 10000,
            "prompt_tokens_uncached": 2000,
            "cached_tokens": 8000,
            "total_output_tokens": 500,
            "estimated_cost_usd": 0.05,
            "turns": [
                {
                    "step_idx": 1,
                    "timestamp": (ref_dt - datetime.timedelta(hours=2)).isoformat(),
                    "model_id": "1318",
                },
                {
                    "step_idx": 2,
                    "timestamp": (ref_dt - datetime.timedelta(hours=1)).isoformat(),
                    "model_id": "1318",
                },
            ],
        }

        c_beta_main = {
            "convo_id": "c_beta_1",
            "title": "Beta Main",
            "workspace_path": "/Users/test/ProjectBeta",
            "workspace_name": "ProjectBeta",
            "git_branch": "main",
            "turn_count": 2,
            "total_input_tokens": 15000,
            "prompt_tokens_uncached": 3000,
            "cached_tokens": 12000,
            "total_output_tokens": 800,
            "estimated_cost_usd": 0.08,
            "turns": [
                {
                    "step_idx": 1,
                    "timestamp": (ref_dt + datetime.timedelta(hours=3)).isoformat(),
                    "model_id": "1318",
                },
                {
                    "step_idx": 2,
                    "timestamp": (ref_dt + datetime.timedelta(hours=4)).isoformat(),
                    "model_id": "1318",
                },
            ],
        }

        res = aggregate_global_telemetry(
            [c_alpha_main, c_alpha_feat, c_beta_main],
            self.pricing_models,
            exhaustion_intervals=[ledger_interval],
        )

        projects = res["projects"]
        self.assertEqual(len(projects), 2)
        p_alpha = next(p for p in projects if p["project_name"] == "ProjectAlpha")
        p_beta = next(p for p in projects if p["project_name"] == "ProjectBeta")

        total_project_overage_credits = sum(p["actual_overage_credits"] for p in projects)
        self.assertEqual(total_project_overage_credits, 1179)
        self.assertEqual(p_alpha["actual_overage_credits"], 1179)
        self.assertEqual(p_alpha["actual_overage_gbp"], 11.31)
        self.assertEqual(p_beta["actual_overage_credits"], 0)
        self.assertEqual(p_beta["actual_overage_gbp"], 0.0)
        self.assertEqual(p_beta["subscription_covered_pct"], 100.0)

        b_main = next(b for b in p_alpha["branches"] if b["branch_name"] == "main")
        b_feat = next(b for b in p_alpha["branches"] if b["branch_name"] == "feat/cool")
        self.assertEqual(b_main["actual_overage_credits"], 1179)
        self.assertEqual(b_main["overage_turns"], 2)
        self.assertEqual(b_feat["actual_overage_credits"], 0)
        self.assertEqual(b_feat["subscription_covered_pct"], 100.0)

        total_avoided_usd = sum(p["avoided_cost_usd"] for p in projects)
        expected_total_usd = round(c_alpha_main["estimated_cost_usd"] + c_alpha_feat["estimated_cost_usd"] + c_beta_main["estimated_cost_usd"], 4)
        self.assertAlmostEqual(total_avoided_usd, expected_total_usd, places=3)

        # Conversation-level dual-track assertions
        self.assertEqual(c_alpha_main["actual_overage_credits"], 1179)
        self.assertEqual(c_alpha_main["overage_turns"], 2)
        self.assertEqual(c_alpha_main["subscription_covered_pct"], 0.0)
        self.assertEqual(c_alpha_feat["actual_overage_credits"], 0)
        self.assertEqual(c_alpha_feat["overage_turns"], 0)
        self.assertEqual(c_alpha_feat["subscription_covered_pct"], 100.0)
        self.assertEqual(c_beta_main["actual_overage_credits"], 0)
        self.assertEqual(c_beta_main["subscription_covered_pct"], 100.0)

    def test_conversation_avoided_cost_and_turn_enrichment(self):
        convo_meta = {
            "convo_id": "test_convo_avoided",
            "title": "Avoided Cost Test",
            "workspace_name": "TestWorkspace",
            "workspace_path": "/Users/test/ws",
            "git_branch": "feat/accounting",
        }
        ref_dt = datetime.datetime(2026, 9, 6, 12, 0, 0, tzinfo=datetime.timezone.utc)
        test_turns = [
            {
                "step_idx": 1,
                "timestamp": ref_dt.isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 4000,
                "output_tokens_total": 500,
                "thinking_tokens": 100,
                "answer_tokens": 400,
            }
        ]
        convo = aggregate_conversation_telemetry(convo_meta, test_turns, self.pricing_models)
        self.assertIn("avoided_cost_usd", convo)
        self.assertIn("avoided_cost_gbp", convo)
        self.assertEqual(convo["avoided_cost_usd"], convo["estimated_cost_usd"])
        self.assertEqual(convo["subscription_covered_pct"], 100.0)
        self.assertEqual(len(convo["turns"]), 1)
        turn = convo["turns"][0]
        self.assertIn("avoided_cost_usd", turn)
        self.assertIn("avoided_cost_gbp", turn)
        self.assertEqual(turn["is_overage"], False)

    def test_dead_trajectory_keys_pruned(self):
        """Verify that dead recovery_trajectory arrays are pruned from rolling_5h quotas."""
        ref_dt = datetime.datetime(2026, 9, 7, 20, 0, 0, tzinfo=datetime.timezone.utc)
        turns = [
            {
                "step_idx": 1,
                "convo_id": "c1",
                "timestamp": (ref_dt - datetime.timedelta(hours=2)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 40000,
                "cached_tokens": 10000,
                "output_tokens_total": 5000,
            }
        ]
        meta = {"convo_id": "c1", "workspace": "proj", "workspace_path": "/proj", "git_branch": "main"}
        summary = aggregate_conversation_telemetry(meta, turns, self.pricing_models)
        payload = aggregate_global_telemetry(
            [summary],
            self.pricing_models,
            all_raw_turns=turns,
            reference_time=ref_dt,
        )
        r5h = payload["quotas"]["rolling_5h"]
        self.assertNotIn("recovery_trajectory", r5h)
        # Recovery schedule must remain intact
        self.assertIn("recovery_schedule", r5h)

    def test_cost_weighted_overage_attribution(self):
        """Verify that 429 overage attribution allocates credits by rate-card cost rather than turn count."""
        ref_dt = datetime.datetime(2026, 9, 7, 20, 0, 0, tzinfo=datetime.timezone.utc)
        # Turn 1: 1 turn of Claude Opus (very expensive, model 1026)
        # Turn 2: 9 turns of Gemini Flash (very cheap, model 1318)
        # All occurring within an overage interval
        t_opus = {
            "step_idx": 1,
            "convo_id": "opus_convo",
            "timestamp": (ref_dt - datetime.timedelta(minutes=30)).isoformat(),
            "model_id": "1026",
            "prompt_tokens_uncached": 100000,
            "cached_tokens": 0,
            "output_tokens_total": 10000,
        }
        meta_opus = {"convo_id": "opus_convo", "workspace": "proj", "workspace_path": "/proj", "git_branch": "main"}
        s_opus = aggregate_conversation_telemetry(meta_opus, [t_opus], self.pricing_models)

        flash_turns = []
        for i in range(1, 10):
            flash_turns.append({
                "step_idx": i,
                "convo_id": "flash_convo",
                "timestamp": (ref_dt - datetime.timedelta(minutes=25 - i)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 0,
                "output_tokens_total": 100,
            })
        meta_flash = {"convo_id": "flash_convo", "workspace": "proj", "workspace_path": "/proj", "git_branch": "main"}
        s_flash = aggregate_conversation_telemetry(meta_flash, flash_turns, self.pricing_models)

        all_raw = [t_opus] + flash_turns
        interval = {
            "incident_id": "test-incident-opus-flash",
            "start": (ref_dt - datetime.timedelta(hours=1)).isoformat(),
            "end": ref_dt.isoformat(),
            "credits_burned": 100,
            "credit_burn_usd": 1.0,
            "credit_burn_gbp": 0.79,
            "from_ledger": True,
        }

        payload = aggregate_global_telemetry(
            [s_opus, s_flash],
            self.pricing_models,
            all_raw_turns=all_raw,
            reference_time=ref_dt,
            exhaustion_intervals=[interval],
        )

        convos = {c["convo_id"]: c for c in payload["conversations"]}
        # Turn count: Opus has 1 turn, Flash has 9 turns (10 total)
        # Cost: Opus cost is 100k * $15/M + 10k * $75/M = $1.50 + $0.75 = $2.25
        # Flash cost is 9 * (1k * $0.10/M + 100 * $0.40/M) = 9 * ($0.0001 + $0.00004) = $0.00126
        # Opus represents >99.9% of the cost.
        # Under cost weighting, Opus conversation should take almost all 100 credits, NOT 10 credits (1/10th).
        self.assertGreaterEqual(convos["opus_convo"]["actual_overage_credits"], 99)
        self.assertLessEqual(convos["flash_convo"]["actual_overage_credits"], 1)

    def test_discovered_and_scanned_databases_in_summary(self):
        """Verify summary preserves discovered_databases and scanned_databases counts."""
        payload = aggregate_global_telemetry(
            [],
            self.pricing_models,
            discovered_databases=146,
            scanned_databases=50,
        )
        self.assertEqual(payload["summary"]["discovered_databases"], 146)
        self.assertEqual(payload["summary"]["scanned_databases"], 50)

    def test_subagent_turn_partitioning(self):
        """Verify interactive vs subagent classification based on model ID."""
        from src.aggregator import classify_turn_type, compute_subagent_metrics, SUBAGENT_MODEL_IDS
        # Interactive models
        self.assertEqual(classify_turn_type({'model_id': '1318'}), 'interactive')  # Flash High
        self.assertEqual(classify_turn_type({'model_id': '1016'}), 'interactive')  # Pro High
        self.assertEqual(classify_turn_type({'model_id': '1035'}), 'interactive')  # Claude Sonnet
        # Subagent models
        self.assertEqual(classify_turn_type({'model_id': '1050'}), 'subagent')  # Flash Lite
        self.assertEqual(classify_turn_type({'model_id': '1322'}), 'subagent')  # Fast Agent
        self.assertEqual(classify_turn_type({'model_id': '1132'}), 'subagent')  # Legacy Agent
        self.assertEqual(classify_turn_type({'model_id': '1301'}), 'subagent')  # Experimental Agent

        # Metric computation
        ref_time = datetime.datetime(2026, 9, 8, 18, 0, 0, tzinfo=datetime.timezone.utc)
        turns = [
            {'model_id': '1318', 'prompt_tokens_uncached': 100000, 'cached_tokens': 500000, 'output_tokens_total': 20000},
            {'model_id': '1050', 'prompt_tokens_uncached': 5000, 'cached_tokens': 20000, 'output_tokens_total': 2000},
            {'model_id': '1322', 'prompt_tokens_uncached': 3000, 'cached_tokens': 15000, 'output_tokens_total': 1000},
        ]
        metrics = compute_subagent_metrics(turns, self.pricing_models)
        self.assertEqual(metrics['interactive']['turn_count'], 1)
        self.assertEqual(metrics['subagent']['turn_count'], 2)
        self.assertEqual(metrics['interactive']['total_tokens'], 620000)
        self.assertEqual(metrics['subagent']['total_tokens'], 46000)
        self.assertGreater(metrics['interactive']['quota_share_pct'], 80.0)

    def test_weekly_exhaustion_detection(self):
        """Verify weekly exhaustion flags and Claude fallback readiness."""
        from src.aggregator import compute_exhaustion_alarm_state
        bounds = {
            'cycle_end_utc': '2026-09-10T18:00:00+00:00',
            'human_remaining': '1 day, 20 hours',
        }
        # Exhausted Gemini + Claude available
        alarm = compute_exhaustion_alarm_state(
            gemini_weekly_used_pct=100.0,
            gemini_weekly_remaining_pct=0.0,
            gemini_5h_used_pct=85.0,
            cg_weekly_remaining_pct=94.7,
            weekly_cycle_bounds=bounds,
        )
        self.assertTrue(alarm['gemini_weekly_exhausted'])
        self.assertTrue(alarm['gemini_5h_disabled'])
        self.assertTrue(alarm['claude_fallback_ready'])
        self.assertEqual(alarm['reset_countdown_utc'], '2026-09-10T18:00:00+00:00')

        # Healthy Gemini
        alarm_healthy = compute_exhaustion_alarm_state(
            gemini_weekly_used_pct=45.0,
            gemini_weekly_remaining_pct=55.0,
            gemini_5h_used_pct=30.0,
            cg_weekly_remaining_pct=90.0,
            weekly_cycle_bounds=bounds,
        )
        self.assertFalse(alarm_healthy['gemini_weekly_exhausted'])
        self.assertFalse(alarm_healthy['gemini_5h_disabled'])
        self.assertFalse(alarm_healthy['claude_fallback_ready'])

        # Exhausted Gemini but Claude also low
        alarm_both_low = compute_exhaustion_alarm_state(
            gemini_weekly_used_pct=100.0,
            gemini_weekly_remaining_pct=0.0,
            gemini_5h_used_pct=100.0,
            cg_weekly_remaining_pct=30.0,
            weekly_cycle_bounds=bounds,
        )
        self.assertTrue(alarm_both_low['gemini_weekly_exhausted'])
        self.assertFalse(alarm_both_low['claude_fallback_ready'])  # Claude too low (<50%)

    def test_daily_velocity_bucketing(self):
        """Verify daily velocity computation and anomaly detection."""
        from src.aggregator import compute_daily_velocity
        ref_time = datetime.datetime(2026, 9, 8, 18, 0, 0, tzinfo=datetime.timezone.utc)
        cycle_start = datetime.datetime(2026, 9, 4, 18, 0, 0, tzinfo=datetime.timezone.utc)

        turns = [
            # Saturday Sep 6 — heavy day
            {'timestamp': '2026-09-06T10:00:00+00:00', 'model_id': '1318', 'prompt_tokens_uncached': 200000, 'cached_tokens': 800000, 'output_tokens_total': 50000},
            {'timestamp': '2026-09-06T14:00:00+00:00', 'model_id': '1318', 'prompt_tokens_uncached': 150000, 'cached_tokens': 600000, 'output_tokens_total': 40000},
            # Sunday Sep 7 — lighter day
            {'timestamp': '2026-09-07T12:00:00+00:00', 'model_id': '1318', 'prompt_tokens_uncached': 50000, 'cached_tokens': 200000, 'output_tokens_total': 10000},
            # Turn outside cycle (should be excluded)
            {'timestamp': '2026-09-03T10:00:00+00:00', 'model_id': '1318', 'prompt_tokens_uncached': 999999, 'cached_tokens': 999999, 'output_tokens_total': 999999},
        ]

        days = compute_daily_velocity(turns, cycle_start, ref_time, self.pricing_models, weekly_capacity_usd=129.00)
        self.assertEqual(len(days), 2)  # Only Sep 6 and Sep 7
        self.assertEqual(days[0]['date'], '2026-09-06')
        self.assertEqual(days[0]['turn_count'], 2)
        self.assertEqual(days[1]['date'], '2026-09-07')
        self.assertEqual(days[1]['turn_count'], 1)
        # Heavy day should be flagged as anomaly if it exceeds 25% of weekly budget
        self.assertGreater(days[0]['budget_pct'], 0.0)
        self.assertIn('is_anomaly', days[0])

    def test_quota_runway_bvi_calculation(self):
        from src.aggregator import compute_quota_runway

        # Cycle: Thursday 2026-09-03 18:00 UTC to Thursday 2026-09-10 18:00 UTC (7 days = 168h)
        bounds = {
            "cycle_start_utc": "2026-09-03T18:00:00+00:00",
            "cycle_end_utc": "2026-09-10T18:00:00+00:00",
            "human_remaining": "2d 14h",
            "reset_display": "Thursday 19:00 BST",
        }

        # Scenario 1: Nominal / Sustainable Pace (Mid-cycle Day 4.06)
        # Elapsed: 4.0625 days / 7 days = 58.0% (Sunday 2026-09-07 19:30 UTC)
        ref_time = datetime.datetime(2026, 9, 7, 19, 30, 0, tzinfo=datetime.timezone.utc)
        gemini_weekly = {"remaining_pct": 46.0, "used_pct": 54.0}
        gemini_5h = {"remaining_pct": 79.0, "used_pct": 21.0, "recovery_schedule": [{"seconds_until": 0}]}

        runway = compute_quota_runway(gemini_weekly, bounds, gemini_5h, ref_time)
        self.assertAlmostEqual(runway["calendar_time_elapsed_pct"], 58.0, delta=0.5)
        self.assertAlmostEqual(runway["quota_consumed_pct"], 54.0, delta=0.1)
        self.assertEqual(runway["burn_velocity_index"], 0.94)
        self.assertEqual(runway["bvi_display"], "0.94x")
        self.assertEqual(runway["status_key"], "green")
        self.assertIn("On Track", runway["status_text"])
        self.assertEqual(runway["day_index"], 5)
        self.assertEqual(runway["daily_ceiling_pct"], 71.5)
        self.assertEqual(runway["banked_buffer_pct"], 17.5)
        self.assertEqual(runway["status_sub"], "Day 5: +17.5% buffer (54.0% vs 71.5%)")
        self.assertAlmostEqual(runway["target_daily_budget_pct"], 15.7, delta=0.5)
        self.assertEqual(runway["exhaustion_eta"], "None")
        self.assertFalse(runway["burst_cooldown_active"])

        # Scenario 2: Elevated Burn Pace (BVI ~ 1.19x, over Day 5 budget)
        gemini_weekly_amber = {"remaining_pct": 28.0, "used_pct": 72.0}
        runway_amber = compute_quota_runway(gemini_weekly_amber, bounds, gemini_5h, ref_time)
        self.assertEqual(runway_amber["burn_velocity_index"], 1.19)
        self.assertEqual(runway_amber["status_key"], "amber")
        self.assertIn("Elevated", runway_amber["status_text"])
        self.assertEqual(runway_amber["status_sub"], "Day 5: -0.5% deficit (72.0% vs 71.5%)")
        self.assertNotEqual(runway_amber["exhaustion_eta"], "None")
        self.assertIn("Tight buffer", runway_amber["exhaustion_caption"])

        # Scenario 3: Critical Overburn (BVI ~ 1.41x)
        gemini_weekly_red = {"remaining_pct": 12.0, "used_pct": 88.0}
        runway_red = compute_quota_runway(gemini_weekly_red, bounds, gemini_5h, ref_time)
        self.assertEqual(runway_red["burn_velocity_index"], 1.41)
        self.assertEqual(runway_red["status_key"], "red")
        self.assertIn("Overburn", runway_red["status_text"])
        self.assertEqual(runway_red["status_sub"], "Day 5: -16.5% deficit (88.0% vs 71.5%)")
        self.assertIn("early", runway_red["exhaustion_caption"].lower())

        # Scenario 4: Cycle Start Normal Session (Day 0.1, Q=6.1% — Safe under Day 1 ceiling of 14.3%)
        start_work_time = datetime.datetime(2026, 9, 3, 20, 30, 0, tzinfo=datetime.timezone.utc)
        gemini_start_normal = {"remaining_pct": 93.9, "used_pct": 6.1}
        runway_start_normal = compute_quota_runway(gemini_start_normal, bounds, gemini_5h, start_work_time)
        self.assertEqual(runway_start_normal["burn_velocity_index"], 1.29)
        self.assertEqual(runway_start_normal["status_key"], "green")
        self.assertIn("On Track", runway_start_normal["status_text"])
        self.assertEqual(runway_start_normal["banked_buffer_pct"], 8.2)
        self.assertEqual(runway_start_normal["status_sub"], "Day 1: +8.2% buffer (6.1% vs 14.3%)")
        self.assertEqual(runway_start_normal["exhaustion_caption"], "Safe buffer (Day 1)")

        # Scenario 5: Cycle Start Catastrophic Runaway (Day 0.1, Q=50% — Breaches Day 1 ceiling)
        gemini_start_runaway = {"remaining_pct": 50.0, "used_pct": 50.0}
        runway_start_runaway = compute_quota_runway(gemini_start_runaway, bounds, gemini_5h, start_work_time)
        self.assertEqual(runway_start_runaway["burn_velocity_index"], 4.08)
        self.assertEqual(runway_start_runaway["status_key"], "red")
        self.assertIn("Overburn", runway_start_runaway["status_text"])
        self.assertEqual(runway_start_runaway["status_sub"], "Day 1: -35.7% deficit (50.0% vs 14.3%)")
        self.assertIn("early", runway_start_runaway["exhaustion_caption"].lower())

        # Scenario 6: Cycle Start Zero Boundary (Elapsed ~ 0%, Q=0%)
        zero_time = datetime.datetime(2026, 9, 3, 18, 5, 0, tzinfo=datetime.timezone.utc)
        runway_zero = compute_quota_runway({"remaining_pct": 100.0, "used_pct": 0.0}, bounds, gemini_5h, zero_time)
        self.assertEqual(runway_zero["burn_velocity_index"], 0.0)
        self.assertEqual(runway_zero["status_key"], "green")
        self.assertEqual(runway_zero["status_text"], "✓ Sustainable (0.00x)")

        # Scenario 7: Burst Cooldown Active
        gemini_5h_burst = {"remaining_pct": 0.0, "used_pct": 100.0, "recovery_schedule": [{"seconds_until": 1722}]}
        runway_burst = compute_quota_runway(gemini_weekly, bounds, gemini_5h_burst, ref_time)
        self.assertTrue(runway_burst["burst_cooldown_active"])
        self.assertEqual(runway_burst["burst_seconds_remaining"], 1722)

    def test_temporal_turn_costing_and_plan_provenance(self):
        """Verify timestamp-aware historical turn costing and temporal plan provenance (M20 / ADR-034)."""
        from src.temporal import get_temporal_resolver

        # 1. Turn-level rate resolution across rate history boundary
        t_early = {
            "model_id": "1318",
            "timestamp": "2026-04-15T12:00:00Z",
            "prompt_tokens_uncached": 1_000_000,
            "cached_tokens": 0,
            "output_tokens_total": 100_000,
        }
        # In H1 2026, 1318 had $0.80 uncached and $4.00 output -> 1.0 * 0.80 + 0.1 * 4.00 = 1.20
        cost_early = compute_turn_cost(t_early)
        self.assertAlmostEqual(cost_early, 1.20, places=4)

        t_late = {
            "model_id": "1318",
            "timestamp": "2026-08-01T12:00:00Z",
            "prompt_tokens_uncached": 1_000_000,
            "cached_tokens": 0,
            "output_tokens_total": 100_000,
        }
        # In H2 2026, 1318 had $0.75 uncached and $3.75 output -> 1.0 * 0.75 + 0.1 * 3.75 = 1.125
        cost_late = compute_turn_cost(t_late)
        self.assertAlmostEqual(cost_late, 1.125, places=4)

        # 2. Conversation aggregation with temporal turns
        meta = {
            "convo_id": "temp-convo-01",
            "title": "Temporal Turn Convo",
            "db_path": "/tmp/test.db",
        }
        pricing = load_pricing()
        convo_summary = aggregate_conversation_telemetry(meta, [t_early, t_late], pricing)
        self.assertEqual(convo_summary["turn_count"], 2)
        self.assertAlmostEqual(convo_summary["estimated_cost_usd"], 1.20 + 1.125, places=3)

        # 3. Global telemetry payload provenance and promotional capacity multipliers
        # Testing during promo period (2026-08-05 has 2x Gemini promo in config/pricing.json)
        promo_ref_time = datetime.datetime(2026, 8, 5, 12, 0, 0, tzinfo=datetime.timezone.utc)
        payload_promo = aggregate_global_telemetry(
            [convo_summary],
            pricing,
            all_raw_turns=[t_early, t_late],
            reference_time=promo_ref_time,
        )

        self.assertIn("temporal", payload_promo)
        temporal_info = payload_promo["temporal"]
        self.assertIn("active_plan", temporal_info)
        self.assertIn("capacity_multipliers", temporal_info)
        self.assertEqual(temporal_info["capacity_multipliers"]["gemini"], 2.0)
        self.assertEqual(temporal_info["capacity_multipliers"]["claude_gpt"], 1.0)
        self.assertIn("active_promotions", payload_promo["summary"])
        self.assertEqual(payload_promo["summary"]["gemini_capacity_multiplier"], 2.0)

        # Gemini 5h capacity ($20.00) * 2.0 = $40.00
        gemini_5h_cap = payload_promo["quotas"]["providers"]["gemini"]["five_hour"]["capacity_usd"]
        self.assertEqual(gemini_5h_cap, 40.00)

        # 4. Global telemetry outside promo period
        non_promo_ref = datetime.datetime(2026, 9, 10, 12, 0, 0, tzinfo=datetime.timezone.utc)
        payload_normal = aggregate_global_telemetry(
            [convo_summary],
            pricing,
            all_raw_turns=[t_early, t_late],
            reference_time=non_promo_ref,
        )
        self.assertEqual(payload_normal["temporal"]["capacity_multipliers"]["gemini"], 1.0)
        gemini_5h_normal = payload_normal["quotas"]["providers"]["gemini"]["five_hour"]["capacity_usd"]
        self.assertEqual(gemini_5h_normal, 20.00)

    def test_workload_simulation_integration(self):
        """Verify global aggregator integrates What-If simulation presets (M21 / ADR-035)."""
        pricing = load_pricing()
        ref_time = datetime.datetime(2026, 9, 12, 12, 0, 0, tzinfo=datetime.timezone.utc)

        # Sample turn to populate telemetry
        turn = {
            "timestamp": "2026-09-12T11:00:00Z",
            "model_id": "1318",
            "prompt_tokens_uncached": 5000,
            "cached_tokens": 15000,
            "output_tokens_total": 1200,
            "thinking_tokens": 800,
            "answer_tokens": 400,
        }
        convo_meta = {"conversation_id": "sim-test-01", "project_path": "/tmp/sim", "git_branch": "main"}
        convo_summary = aggregate_conversation_telemetry(convo_meta, [turn], pricing)

        payload = aggregate_global_telemetry(
            [convo_summary],
            pricing,
            all_raw_turns=[turn],
            reference_time=ref_time,
        )

        # 1. Assert presence in payload
        self.assertIn("simulator_presets", payload)
        self.assertIn("simulations", payload)
        sim_presets = payload["simulator_presets"]

        # 2. Check structure
        self.assertIn("active_plan_tier", sim_presets)
        self.assertIn("archetypes", sim_presets)
        self.assertIn("results", sim_presets)

        expected_archetypes = {
            "deep_refactor_swarm",
            "codebase_audit",
            "rapid_prototyping_burst",
            "claude_opus_deep_dive",
            "subagent_fleet",
        }
        self.assertTrue(expected_archetypes.issubset(set(sim_presets["results"].keys())))

        # 3. Validate deep refactor swarm output
        refactor = sim_presets["results"]["deep_refactor_swarm"]
        self.assertEqual(refactor["model_id"], "1016")
        self.assertEqual(refactor["provider_track"], "gemini")
        self.assertEqual(refactor["turn_count"], 40)
        self.assertGreater(refactor["imputed_value_usd"], 0.0)
        self.assertGreater(refactor["total_processed_tokens"], 0)
        self.assertIn(refactor["status_key"], ["safe", "caution", "cooldown", "lockout"])
        self.assertIn("plan_comparison", refactor)
        self.assertEqual(len(refactor["plan_comparison"]), 3)

        # 4. Validate Claude Opus stress test (ADR-030 429 dynamics)
        claude_sim = sim_presets["results"]["claude_opus_deep_dive"]
        self.assertEqual(claude_sim["model_id"], "1026")
        self.assertEqual(claude_sim["provider_track"], "claude_gpt")
        self.assertFalse(claude_sim["credit_spillover_applicable"])
        self.assertEqual(claude_sim["credits_debited"], 0)

        # 5. Direct call to compute_simulation_presets with custom quota state
        from src.aggregator import compute_simulation_presets
        custom_state = {
            "gemini": {"rolling_5h_used_usd": 15.0, "weekly_used_usd": 50.0, "credits_remaining": 1000},
            "claude_gpt": {"rolling_5h_used_usd": 8.0, "weekly_used_usd": 20.0},
        }
        res = compute_simulation_presets(initial_quota_state=custom_state, pricing_models=pricing)
        self.assertIn("results", res)
        self.assertGreater(res["results"]["deep_refactor_swarm"]["starting_5h_used_usd"], 0.0)

    def test_turn_level_git_branch_attribution(self):
        """Verify that turns within a single conversation spanning multiple Git checkout windows correctly partition into separate branch records (M33 / ADR-046)."""
        import tempfile
        from pathlib import Path
        from src.git_timeline import clear_reflog_cache


        with tempfile.TemporaryDirectory() as td:
            # Create synthetic git repo with reflog
            git_logs = Path(td) / ".git" / "logs"
            git_logs.mkdir(parents=True)
            reflog_file = git_logs / "HEAD"

            reflog_content = (
                "0000000 1111111 User <u@example.com> 1780000000 +0000\tcommit (initial): root\n"
                "1111111 2222222 User <u@example.com> 1780000100 +0000\tcheckout: moving from main to feat/subagent\n"
                "2222222 3333333 User <u@example.com> 1780000200 +0000\tcheckout: moving from feat/subagent to main\n"
            )
            reflog_file.write_text(reflog_content, encoding="utf-8")
            clear_reflog_cache()

            t1_iso = datetime.datetime.fromtimestamp(1780000050, tz=datetime.timezone.utc).isoformat()
            t2_iso = datetime.datetime.fromtimestamp(1780000150, tz=datetime.timezone.utc).isoformat()
            t3_iso = datetime.datetime.fromtimestamp(1780000250, tz=datetime.timezone.utc).isoformat()

            convo = {
                "convo_id": "single_convo_multi_branch",
                "title": "Single Convo Multi Branch",
                "workspace_path": td,
                "workspace_name": "MultiBranchProject",
                "git_branch": "main",  # static DB recorded main
                "turn_count": 3,
                "total_input_tokens": 15000,
                "prompt_tokens_uncached": 3000,
                "cached_tokens": 12000,
                "total_output_tokens": 1500,
                "estimated_cost_usd": 0.09,
                "turns": [
                    {
                        "step_idx": 1,
                        "timestamp": t1_iso,
                        "model_id": "1318",
                        "prompt_tokens_uncached": 1000,
                        "cached_tokens": 4000,
                        "total_input_tokens": 5000,
                        "total_output_tokens": 500,
                        "estimated_cost_usd": 0.03,
                    },
                    {
                        "step_idx": 2,
                        "timestamp": t2_iso,
                        "model_id": "1318",
                        "prompt_tokens_uncached": 1000,
                        "cached_tokens": 4000,
                        "total_input_tokens": 5000,
                        "total_output_tokens": 500,
                        "estimated_cost_usd": 0.03,
                    },
                    {
                        "step_idx": 3,
                        "timestamp": t3_iso,
                        "model_id": "1318",
                        "prompt_tokens_uncached": 1000,
                        "cached_tokens": 4000,
                        "total_input_tokens": 5000,
                        "total_output_tokens": 500,
                        "estimated_cost_usd": 0.03,
                    },
                ],
            }

            res = aggregate_global_telemetry([convo], self.pricing_models, exhaustion_intervals=[])
            projects = res["projects"]
            self.assertEqual(len(projects), 1)
            p = projects[0]
            self.assertEqual(p["project_name"], "MultiBranchProject")
            self.assertEqual(p["turn_count"], 3)
            self.assertEqual(p["total_input_tokens"], 15000)
            self.assertEqual(p["total_output_tokens"], 1500)

            branches = {b["branch_name"]: b for b in p["branches"]}
            self.assertIn("main", branches)
            self.assertIn("feat/subagent", branches)

            b_main = branches["main"]
            b_feat = branches["feat/subagent"]

            self.assertEqual(b_main["turn_count"], 2)
            self.assertEqual(b_main["total_input_tokens"], 10000)
            self.assertEqual(b_main["total_output_tokens"], 1000)
            self.assertAlmostEqual(b_main["estimated_cost_usd"], 0.06, places=3)

            self.assertEqual(b_feat["turn_count"], 1)
            self.assertEqual(b_feat["total_input_tokens"], 5000)
            self.assertEqual(b_feat["total_output_tokens"], 500)
            self.assertAlmostEqual(b_feat["estimated_cost_usd"], 0.03, places=3)

            self.assertEqual(p["total_input_tokens"], b_main["total_input_tokens"] + b_feat["total_input_tokens"])
            self.assertEqual(p["total_output_tokens"], b_main["total_output_tokens"] + b_feat["total_output_tokens"])
            self.assertEqual(p["turn_count"], b_main["turn_count"] + b_feat["turn_count"])
            self.assertAlmostEqual(p["estimated_cost_usd"], b_main["estimated_cost_usd"] + b_feat["estimated_cost_usd"], places=3)
            clear_reflog_cache()


if __name__ == "__main__":
    unittest.main()



