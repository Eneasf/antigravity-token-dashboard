"""
Unit tests for modular aggregator architecture and interaction gate B5.

Verifies:
  1. Submodule imports and exports across all 6 decomposed aggregator modules.
  2. Re-export integrity and identity matching in src/aggregator.py (__all__).
  3. Backward compatibility of public APIs accessed directly from src.aggregator.
  4. Interactive dynamic stream processing (Gate B5), validating dual-track partitioning,
     dynamic cache hit ratio progression, reflog branch attribution, 429 exhaustion overage,
     and responsive runway/velocity updates.
"""

from collections import defaultdict
import datetime
import importlib
import unittest
from unittest.mock import patch

import src.aggregator as agg
from src.aggregator import (
    DEFAULT_PRICING_FILE,
    DEFAULT_SUBSCRIPTION_FILE,
    SUBAGENT_MODEL_IDS,
    WEEKDAY_MAP,
    aggregate_conversation_telemetry,
    aggregate_global_telemetry,
    calculate_credit_burn,
    classify_turn_type,
    compute_cache_coaching_metrics,
    compute_daily_velocity,
    compute_exhaustion_alarm_state,
    compute_historical_peaks,
    compute_live_ticker,
    compute_project_branch_attribution,
    compute_provider_quota_silos,
    compute_quota_runway,
    compute_rolling_window_telemetry,
    compute_simulation_presets,
    compute_subagent_metrics,
    compute_turn_cost,
    compute_window_recovery_schedule,
    compute_workspace_metrics,
    decorate_active_sessions,
    extract_project_branch_attribution,
    get_model_display_name,
    get_model_rates,
    get_monthly_billing_bounds,
    get_provider_quota_track,
    get_weekly_cycle_bounds,
    load_currency_config,
    load_subscription_config,
    normalize_exhaustion_intervals,
    parse_timestamp,
    reconcile_credit_burn_and_overage,
)


class TestAggregatorModular(unittest.TestCase):
    """Test suite validating modular aggregator architecture and dynamic interaction streams."""

    def setUp(self):
        """Configure standard calibrated pricing models adhering to Gate V136."""
        self.pricing_models = {
            "1318": {
                "name": "Gemini 3.8 Flash (High)",
                "family": "gemini-flash",
                "rates_per_million": {
                    "prompt_uncached": 0.10,
                    "prompt_cached": 0.025,
                    "candidate_output": 0.40,
                },
                "credits_per_turn": 2.5,
            },
            "1016": {
                "name": "Gemini 3.1 Pro (High)",
                "family": "gemini-pro",
                "rates_per_million": {
                    "prompt_uncached": 1.25,
                    "prompt_cached": 0.3125,
                    "candidate_output": 5.00,
                },
                "credits_per_turn": 5.0,
            },
            "1035": {
                "name": "Claude Sonnet 4.6 (Thinking)",
                "family": "claude-sonnet",
                "rates_per_million": {
                    "prompt_uncached": 3.00,
                    "prompt_cached": 0.30,
                    "candidate_output": 15.00,
                },
                "credits_per_turn": 10.0,
            },
            "1050": {
                "name": "Gemini Flash Lite (Subagent)",
                "family": "gemini-flash-lite",
                "rates_per_million": {
                    "prompt_uncached": 0.075,
                    "prompt_cached": 0.01875,
                    "candidate_output": 0.30,
                },
                "credits_per_turn": 2.5,
            },
            "default": {
                "name": "Default Model",
                "family": "gemini-flash",
                "rates_per_million": {
                    "prompt_uncached": 0.10,
                    "prompt_cached": 0.025,
                    "candidate_output": 0.40,
                },
                "credits_per_turn": 2.5,
            },
        }
        self.ref_dt = datetime.datetime(2026, 9, 21, 12, 0, 0, tzinfo=datetime.timezone.utc)

    def test_submodule_imports_and_exports(self):
        """Verify each of the 6 decomposed submodules can be imported independently with required symbols."""
        expected_submodules = {
            "src.aggregator_pricing": [
                "DEFAULT_PRICING_FILE",
                "DEFAULT_SUBSCRIPTION_FILE",
                "SUBAGENT_MODEL_IDS",
                "calculate_credit_burn",
                "classify_turn_type",
                "compute_subagent_metrics",
                "compute_turn_cost",
                "get_model_display_name",
                "get_model_rates",
                "get_provider_quota_track",
                "load_currency_config",
                "load_subscription_config",
                "parse_timestamp",
            ],
            "src.aggregator_cycles": [
                "WEEKDAY_MAP",
                "compute_daily_velocity",
                "compute_exhaustion_alarm_state",
                "compute_quota_runway",
                "get_monthly_billing_bounds",
                "get_weekly_cycle_bounds",
            ],
            "src.aggregator_windows": [
                "aggregate_conversation_telemetry",
                "compute_historical_peaks",
                "compute_rolling_window_telemetry",
                "compute_window_recovery_schedule",
            ],
            "src.aggregator_coaching": [
                "compute_cache_coaching_metrics",
                "compute_live_ticker",
                "compute_simulation_presets",
            ],
            "src.aggregator_attribution": [
                "compute_project_branch_attribution",
                "compute_workspace_metrics",
                "extract_project_branch_attribution",
                "normalize_exhaustion_intervals",
            ],
            "src.aggregator_quotas": [
                "compute_provider_quota_silos",
                "decorate_active_sessions",
                "reconcile_credit_burn_and_overage",
            ],
        }

        for mod_name, symbols in expected_submodules.items():
            mod = importlib.import_module(mod_name)
            for sym in symbols:
                self.assertTrue(
                    hasattr(mod, sym),
                    f"Submodule {mod_name} must export symbol '{sym}'",
                )
                agg_val = getattr(agg, sym)
                mod_val = getattr(mod, sym)
                self.assertIs(
                    agg_val,
                    mod_val,
                    f"Symbol '{sym}' in src.aggregator must be identical object from {mod_name}",
                )

    def test_reexport_integrity(self):
        """Verify src.aggregator.__all__ contains all public symbols and they resolve correctly."""
        self.assertIsInstance(agg.__all__, list, "__all__ must be defined as a list in src.aggregator")
        self.assertGreater(len(agg.__all__), 30, "src.aggregator.__all__ must export all public API symbols")

        missing = []
        for symbol_name in agg.__all__:
            if not hasattr(agg, symbol_name):
                missing.append(symbol_name)

        self.assertEqual(missing, [], f"Symbols declared in __all__ missing from src.aggregator: {missing}")

    def test_backward_compatibility_functions(self):
        """Verify that direct invocation of primary aggregator functions on src.aggregator behaves identically."""
        # 1. parse_timestamp
        parsed = agg.parse_timestamp("2026-09-21T10:00:00Z")
        self.assertEqual(parsed, datetime.datetime(2026, 9, 21, 10, 0, 0, tzinfo=datetime.timezone.utc))

        # 2. get_weekly_cycle_bounds
        bounds = agg.get_weekly_cycle_bounds(self.ref_dt)
        self.assertIn("cycle_start_utc", bounds)
        self.assertIn("cycle_end_utc", bounds)
        self.assertIn("reset_display", bounds)
        self.assertIn("human_remaining", bounds)

        # 3. compute_quota_runway
        runway = agg.compute_quota_runway(
            gemini_weekly={"imputed_value_usd": 15.0, "remaining_pct": 75.0},
            weekly_cycle_bounds=bounds,
            reference_time=self.ref_dt,
        )
        self.assertIn("status_key", runway)
        self.assertIn("burn_velocity_index", runway)

        # 4. compute_rolling_window_telemetry
        window = agg.compute_rolling_window_telemetry(
            turns=[],
            window_hours=5.0,
            reference_time=self.ref_dt,
            pricing_models=self.pricing_models,
        )
        self.assertEqual(window["turn_count"], 0)
        self.assertEqual(window["total_processed_tokens"], 0)

        # 5. compute_simulation_presets
        presets = agg.compute_simulation_presets(pricing_models=self.pricing_models)
        self.assertIn("active_plan_tier", presets)
        self.assertIn("archetypes", presets)
        self.assertIn("results", presets)

        # 6. compute_cache_coaching_metrics
        coaching = agg.compute_cache_coaching_metrics([], pricing_models=self.pricing_models)
        self.assertIn("model_flips_detected", coaching)
        self.assertIn("coaching_tip", coaching)

        # 7. calculate_credit_burn
        burn = agg.calculate_credit_burn("1318", turns_count=2, pricing_models=self.pricing_models)
        self.assertEqual(burn["credits"], 5.0)
        self.assertGreater(burn["credit_burn_usd"], 0.0)

        # 8. get_provider_quota_track
        self.assertEqual(agg.get_provider_quota_track("1318", self.pricing_models), "gemini")
        self.assertEqual(agg.get_provider_quota_track("1035", self.pricing_models), "claude_gpt")

        # 9. compute_turn_cost
        sample_turn = {
            "model_id": "1318",
            "prompt_tokens_uncached": 10000,
            "cached_tokens": 50000,
            "output_tokens_total": 2000,
        }
        cost = agg.compute_turn_cost(sample_turn, pricing_models=self.pricing_models)
        self.assertGreater(cost, 0.0)

        # 10. classify_turn_type
        self.assertEqual(agg.classify_turn_type({"model_id": "1318"}), "interactive")
        self.assertEqual(agg.classify_turn_type({"model_id": "1050"}), "subagent")

        # 11. compute_subagent_metrics
        sub_metrics = agg.compute_subagent_metrics(
            [
                {"model_id": "1318", "prompt_tokens_uncached": 1000, "cached_tokens": 0, "output_tokens_total": 500},
                {"model_id": "1050", "prompt_tokens_uncached": 2000, "cached_tokens": 0, "output_tokens_total": 500},
            ],
            pricing_models=self.pricing_models,
        )
        self.assertIn("interactive", sub_metrics)
        self.assertIn("subagent", sub_metrics)
        self.assertEqual(sub_metrics["interactive"]["turn_count"], 1)
        self.assertEqual(sub_metrics["subagent"]["turn_count"], 1)

    def test_interactive_turn_stream(self):
        """
        Interaction Gate B5: Dynamic, interactive stream of turns arriving over time.

        Stream specification:
          - Turn 1: Gemini Flash turn in workspace A on branch feat/x
          - Turn 2: Claude Sonnet turn in workspace A on branch feat/y (branch checkout)
          - Turn 3: Gemini Pro turn triggering large cache hit
          - Turn 4: Gemini Flash turn falling inside a simulated 429 exhaustion interval

        Verifies pipeline interaction across:
          1. Step-level Track 1 (Gemini) vs Track 2 (Claude/GPT) quota partitioning.
          2. Dynamic cache hit ratio calculation and progression.
          3. Git reflog branch and project attribution tracking across mid-session branch switches.
          4. Overage and credit bank burn transitions on 429 exhaustion intervals.
          5. Responsive updates to quota runway and daily velocity metrics.
        """
        workspace_path = "/workspaces/project_a"
        workspace_name = "Project Alpha"
        convo_id = "stream-session-001"

        # Turn 1: Gemini Flash on branch feat/x
        turn1 = {
            "turn_id": "turn-1",
            "timestamp": "2026-09-21T10:00:00Z",
            "model_id": "1318",
            "prompt_tokens_uncached": 10000,
            "cached_tokens": 0,
            "output_tokens_total": 1000,
            "thinking_tokens": 200,
            "answer_tokens": 800,
        }

        # Turn 2: Claude Sonnet on branch feat/y
        turn2 = {
            "turn_id": "turn-2",
            "timestamp": "2026-09-21T10:15:00Z",
            "model_id": "1035",
            "prompt_tokens_uncached": 20000,
            "cached_tokens": 0,
            "output_tokens_total": 2000,
            "thinking_tokens": 500,
            "answer_tokens": 1500,
        }

        # Turn 3: Gemini Pro triggering large cache hit
        turn3 = {
            "turn_id": "turn-3",
            "timestamp": "2026-09-21T10:30:00Z",
            "model_id": "1016",
            "prompt_tokens_uncached": 5000,
            "cached_tokens": 95000,
            "output_tokens_total": 3000,
            "thinking_tokens": 1000,
            "answer_tokens": 2000,
        }

        # Turn 4: Gemini Flash in simulated 429 exhaustion interval
        turn4 = {
            "turn_id": "turn-4",
            "timestamp": "2026-09-21T10:45:00Z",
            "model_id": "1318",
            "prompt_tokens_uncached": 8000,
            "cached_tokens": 2000,
            "output_tokens_total": 1000,
            "thinking_tokens": 200,
            "answer_tokens": 800,
        }

        simulated_429_intervals = [
            {
                "start": "2026-09-21T10:40:00Z",
                "end": "2026-09-21T10:50:00Z",
                "incident_id": "inc-429-stream-001",
                "from_ledger": False,
            }
        ]

        def mock_resolve_turn_branch(ws_p, turn_ts, fallback="main"):
            dt = parse_timestamp(turn_ts)
            # Switch branch from feat/x to feat/y at 10:10:00 UTC
            if dt and dt < datetime.datetime(2026, 9, 21, 10, 10, 0, tzinfo=datetime.timezone.utc):
                return "feat/x"
            return "feat/y"

        convo_meta = {
            "convo_id": convo_id,
            "title": "Interactive Stream Session",
            "workspace_name": workspace_name,
            "workspace_path": workspace_path,
            "git_branch": "feat/x",
        }

        with patch("src.aggregator_attribution.resolve_turn_branch", side_effect=mock_resolve_turn_branch):
            accumulated_stream = []

            # =========================================================================
            # STEP 1: Turn 1 Arrives (Gemini Flash on feat/x)
            # =========================================================================
            accumulated_stream.append(turn1)
            convo_step1 = aggregate_conversation_telemetry(
                convo_meta, accumulated_stream, self.pricing_models
            )
            res1 = aggregate_global_telemetry(
                conversation_summaries=[convo_step1],
                pricing_models=self.pricing_models,
                reference_time=self.ref_dt,
                exhaustion_intervals=[],
            )

            # Assert Step 1 Pipeline State
            self.assertEqual(res1["summary"]["total_turns"], 1)
            self.assertEqual(res1["summary"]["cached_tokens"], 0)
            self.assertEqual(res1["summary"]["cache_hit_ratio_pct"], 0.0)
            self.assertEqual(res1["summary"]["total_overage_turns"], 0)
            self.assertEqual(res1["summary"]["total_ai_credits_burned"], 0)

            # Quota track partitioning
            gemini_q1 = res1["quotas"]["providers"]["gemini"]["five_hour"]
            claude_q1 = res1["quotas"]["providers"]["claude_gpt"]["five_hour"]
            self.assertEqual(gemini_q1["turn_count"], 1)
            self.assertEqual(claude_q1["turn_count"], 0)

            # Project & branch attribution
            self.assertEqual(len(res1["projects"]), 1)
            proj1 = res1["projects"][0]
            self.assertEqual(proj1["project_name"], workspace_name)
            branches1 = {b["branch_name"]: b for b in proj1["branches"]}
            self.assertIn("feat/x", branches1)
            self.assertNotIn("feat/y", branches1)
            self.assertEqual(branches1["feat/x"]["turn_count"], 1)

            # Daily velocity & runway
            self.assertEqual(len(res1["quotas"]["daily_velocity"]), 1)
            self.assertEqual(res1["quotas"]["daily_velocity"][0]["turn_count"], 1)
            self.assertGreater(res1["quotas"]["daily_velocity"][0]["imputed_cost_usd"], 0.0)
            self.assertIn("status_key", res1["quotas"]["runway"])

            # =========================================================================
            # STEP 2: Turn 2 Arrives (Claude Sonnet on feat/y - branch switch mid-session)
            # =========================================================================
            accumulated_stream.append(turn2)
            convo_step2 = aggregate_conversation_telemetry(
                convo_meta, accumulated_stream, self.pricing_models, exhaustion_intervals=[]
            )
            res2 = aggregate_global_telemetry(
                conversation_summaries=[convo_step2],
                pricing_models=self.pricing_models,
                reference_time=self.ref_dt,
                exhaustion_intervals=[],
            )

            # Assert Step 2 Pipeline State
            self.assertEqual(res2["summary"]["total_turns"], 2)
            self.assertEqual(res2["summary"]["cache_hit_ratio_pct"], 0.0)

            # Assert Dual-Track Silo Partitioning: Turn 1 to Gemini, Turn 2 to Claude
            gemini_q2 = res2["quotas"]["providers"]["gemini"]["five_hour"]
            claude_q2 = res2["quotas"]["providers"]["claude_gpt"]["five_hour"]
            self.assertEqual(gemini_q2["turn_count"], 1)
            self.assertEqual(claude_q2["turn_count"], 1)

            # Claude turn should NOT increment Gemini daily velocity
            vel2 = res2["quotas"]["daily_velocity"][0]
            self.assertEqual(vel2["turn_count"], 1)  # Gemini turns only in daily velocity

            # Dynamic Branch Attribution across switch
            proj2 = res2["projects"][0]
            branches2 = {b["branch_name"]: b for b in proj2["branches"]}
            self.assertIn("feat/x", branches2)
            self.assertIn("feat/y", branches2)
            self.assertEqual(branches2["feat/x"]["turn_count"], 1)
            self.assertEqual(branches2["feat/y"]["turn_count"], 1)

            # =========================================================================
            # STEP 3: Turn 3 Arrives (Gemini Pro triggering large cache hit)
            # =========================================================================
            accumulated_stream.append(turn3)
            convo_step3 = aggregate_conversation_telemetry(
                convo_meta, accumulated_stream, self.pricing_models, exhaustion_intervals=[]
            )
            res3 = aggregate_global_telemetry(
                conversation_summaries=[convo_step3],
                pricing_models=self.pricing_models,
                reference_time=self.ref_dt,
                exhaustion_intervals=[],
            )

            # Assert Dynamic Cache Hit Ratio Update
            # total_input = 10,000 (t1) + 20,000 (t2) + 100,000 (t3) = 130,000
            # total_cached = 95,000
            # ratio = 95,000 / 130,000 * 100 = 73.08%
            self.assertEqual(res3["summary"]["total_turns"], 3)
            self.assertEqual(res3["summary"]["cached_tokens"], 95000)
            self.assertAlmostEqual(res3["summary"]["cache_hit_ratio_pct"], 73.08, places=2)

            # Gemini quota track now has 2 turns
            gemini_q3 = res3["quotas"]["providers"]["gemini"]["five_hour"]
            claude_q3 = res3["quotas"]["providers"]["claude_gpt"]["five_hour"]
            self.assertEqual(gemini_q3["turn_count"], 2)
            self.assertEqual(claude_q3["turn_count"], 1)

            # Responsive Daily Velocity & Quota Updates
            vel3 = res2["quotas"]["daily_velocity"][0]
            vel3_new = res3["quotas"]["daily_velocity"][0]
            self.assertEqual(vel3_new["turn_count"], 2)
            self.assertGreater(vel3_new["total_tokens"], vel3["total_tokens"])
            self.assertGreater(vel3_new["imputed_cost_usd"], vel3["imputed_cost_usd"])

            # Weekly Gemini quota imputed value must have increased
            gemini_weekly3 = res3["quotas"]["providers"]["gemini"]["weekly"]
            self.assertGreater(gemini_weekly3["imputed_value_usd"], gemini_q1["imputed_value_usd"])

            # =========================================================================
            # STEP 4: Turn 4 Arrives inside Simulated 429 Exhaustion Interval
            # =========================================================================
            accumulated_stream.append(turn4)
            convo_step4 = aggregate_conversation_telemetry(
                convo_meta,
                accumulated_stream,
                self.pricing_models,
                exhaustion_intervals=simulated_429_intervals,
            )
            res4 = aggregate_global_telemetry(
                conversation_summaries=[convo_step4],
                pricing_models=self.pricing_models,
                reference_time=self.ref_dt,
                exhaustion_intervals=simulated_429_intervals,
            )

            # Assert Total Turns
            self.assertEqual(res4["summary"]["total_turns"], 4)

            # Assert Overage & Credit Burn Transition
            self.assertEqual(res4["summary"]["total_overage_turns"], 1)
            self.assertEqual(res4["summary"]["subscription_covered_turns"], 3)
            self.assertEqual(res4["summary"]["subscription_covered_pct"], 75.0)
            self.assertGreater(res4["summary"]["total_ai_credits_burned"], 0)
            self.assertGreater(res4["summary"]["total_credit_burn_usd"], 0.0)

            # Assert Branch-level Overage Attribution
            proj4 = res4["projects"][0]
            branches4 = {b["branch_name"]: b for b in proj4["branches"]}
            self.assertEqual(branches4["feat/x"]["overage_turns"], 0)
            self.assertEqual(branches4["feat/y"]["overage_turns"], 1)
            self.assertGreater(branches4["feat/y"]["actual_overage_credits"], 0)

            # Assert Final Quota Track Partitioning (3 Gemini, 1 Claude)
            gemini_q4 = res4["quotas"]["providers"]["gemini"]["five_hour"]
            claude_q4 = res4["quotas"]["providers"]["claude_gpt"]["five_hour"]
            self.assertEqual(gemini_q4["turn_count"], 3)
            self.assertEqual(claude_q4["turn_count"], 1)

            # Assert Cache Hit Ratio Dynamically Re-calculated with Turn 4
            # total_input = 130,000 + 10,000 = 140,000
            # total_cached = 95,000 + 2,000 = 97,000
            # ratio = 97,000 / 140,000 * 100 = 69.29%
            self.assertEqual(res4["summary"]["cached_tokens"], 97000)
            self.assertAlmostEqual(res4["summary"]["cache_hit_ratio_pct"], 69.29, places=2)

            # Assert Daily Velocity updated with Turn 4
            vel4 = res4["quotas"]["daily_velocity"][0]
            self.assertEqual(vel4["turn_count"], 3)
            self.assertGreater(vel4["total_tokens"], vel3_new["total_tokens"])
            self.assertGreater(vel4["imputed_cost_usd"], vel3_new["imputed_cost_usd"])


if __name__ == "__main__":
    unittest.main()
