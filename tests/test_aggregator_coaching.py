"""
Unit tests for aggregator coaching metrics:
  - Intra-family reasoning effort tier flips (Argon High/Med/Low, Flash High/Med/Low)
  - Intra-track model switches (Argon <-> Flash)
  - Cross-provider model flips (Gemini <-> Claude/GPT)
  - GADR-018 coaching tips and KV cache eviction accounting (M94 / Gate B2)
"""

import unittest
from typing import Any, Dict, List

from src.aggregator_coaching import (
    compute_cache_coaching_metrics,
    get_model_family,
    normalize_model_id,
)


class TestAggregatorCoaching(unittest.TestCase):
    def setUp(self):
        self.pricing_models = {
            "1427": {
                "name": "Gemini 4 Carbon (High)",
                "family": "gemini-carbon",
                "rates_per_million": {
                    "prompt_uncached": 2.00,
                    "prompt_cached": 0.10,
                    "candidate_output": 10.00,
                },
            },
            "1437": {
                "name": "Gemini 4 Carbon (Medium)",
                "family": "gemini-carbon",
                "rates_per_million": {
                    "prompt_uncached": 2.00,
                    "prompt_cached": 0.10,
                    "candidate_output": 10.00,
                },
            },
            "1438": {
                "name": "Gemini 4 Carbon (Low)",
                "family": "gemini-carbon",
                "rates_per_million": {
                    "prompt_uncached": 2.00,
                    "prompt_cached": 0.10,
                    "candidate_output": 10.00,
                },
            },
            "1417": {
                "name": "Gemini 4 Argon (High)",
                "family": "gemini-argon",
                "rates_per_million": {
                    "prompt_uncached": 2.00,
                    "prompt_cached": 0.10,
                    "candidate_output": 10.00,
                },
            },
            "1418": {
                "name": "Gemini 4 Argon (Medium)",
                "family": "gemini-argon",
                "rates_per_million": {
                    "prompt_uncached": 2.00,
                    "prompt_cached": 0.10,
                    "candidate_output": 10.00,
                },
            },
            "1419": {
                "name": "Gemini 4 Argon (Low)",
                "family": "gemini-argon",
                "rates_per_million": {
                    "prompt_uncached": 2.00,
                    "prompt_cached": 0.10,
                    "candidate_output": 10.00,
                },
            },
            "1318": {
                "name": "Gemini 3.8 Flash (High)",
                "family": "gemini-flash",
                "rates_per_million": {
                    "prompt_uncached": 0.75,
                    "prompt_cached": 0.075,
                    "candidate_output": 3.75,
                },
            },
            "1319": {
                "name": "Gemini 3.8 Flash (Medium)",
                "family": "gemini-flash",
                "rates_per_million": {
                    "prompt_uncached": 0.75,
                    "prompt_cached": 0.075,
                    "candidate_output": 3.75,
                },
            },
            "1035": {
                "name": "Claude Sonnet 4.6",
                "family": "claude-sonnet",
                "rates_per_million": {
                    "prompt_uncached": 3.00,
                    "prompt_cached": 0.30,
                    "candidate_output": 15.00,
                },
            },
        }

    def test_gate_b2_intra_family_argon_tier_flip(self):
        """Verify Gate B2 specification: Argon High to Medium flip triggers intra-family eviction."""
        convs = [
            {
                "id": "c1",
                "title": "Argon Tier Flip",
                "turns": [
                    {
                        "turn": 1,
                        "model": "MODEL_PLACEHOLDER_M1417",
                        "quota_track": "gemini",
                        "input": 140000,
                        "cached": 137000,
                        "cache_Creation": 0,
                        "cost": 0.02,
                        "uncached_cost": 0.28,
                    },
                    {
                        "turn": 2,
                        "model": "MODEL_PLACEHOLDER_M1418",
                        "quota_track": "gemini",
                        "input": 142000,
                        "cached": 0,
                        "cache_Creation": 0,
                        "cost": 0.284,
                        "uncached_cost": 0.284,
                    },
                ],
            }
        ]
        res = compute_cache_coaching_metrics(convs)
        self.assertGreaterEqual(res["cross_model_flips"], 1)
        self.assertEqual(res["intra_family_flips"], 1)
        self.assertEqual(res["intra_track_flips"], 0)
        self.assertEqual(res["cross_provider_flips"], 0)
        self.assertGreaterEqual(res["estimated_flip_waste_tokens"], 130000)
        self.assertGreater(res["estimated_flip_waste_usd"], 0.0)

        # Verify GADR-018 in coaching tip
        self.assertIn("GADR-018", res["coaching_tip"])
        self.assertIn("Argon High/Med/Low", res["coaching_tip"])

        # Verify incident metadata
        self.assertEqual(len(res["flip_incidents"]), 1)
        inc = res["flip_incidents"][0]
        self.assertEqual(inc["flip_type"], "intra_family")
        self.assertEqual(inc["from_model"], "Gemini 4 Argon (High)")
        self.assertEqual(inc["to_model"], "Gemini 4 Argon (Medium)")
        self.assertEqual(inc["wasted_tokens"], 137000)

    def test_intra_family_flash_effort_tier_flip(self):
        """Verify effort tier flip within Gemini Flash family (1318 -> 1319)."""
        convs = [
            {
                "convo_id": "flash-session",
                "title": "Flash Deep Refactor",
                "turns": [
                    {
                        "step_idx": 1,
                        "model_id": "1318",
                        "prompt_tokens_uncached": 5000,
                        "cached_tokens": 75000,
                    },
                    {
                        "step_idx": 2,
                        "model_id": "1319",
                        "prompt_tokens_uncached": 82000,
                        "cached_tokens": 0,
                    },
                ],
            }
        ]
        res = compute_cache_coaching_metrics(convs, self.pricing_models)
        self.assertEqual(res["cross_model_flips"], 1)
        self.assertEqual(res["intra_family_flips"], 1)
        self.assertEqual(res["intra_track_flips"], 0)
        self.assertEqual(res["cross_provider_flips"], 0)
        self.assertGreaterEqual(res["estimated_flip_waste_tokens"], 70000)
        self.assertIn("GADR-018", res["coaching_tip"])

    def test_intra_track_model_switch_argon_to_flash(self):
        """Verify intra-track switch between different families in same quota silo (Argon -> Flash)."""
        convs = [
            {
                "convo_id": "intra-track-session",
                "title": "Argon to Flash Sweep",
                "turns": [
                    {
                        "step_idx": 1,
                        "model_id": "1419",  # Argon Low
                        "prompt_tokens_uncached": 5000,
                        "cached_tokens": 60000,
                    },
                    {
                        "step_idx": 2,
                        "model_id": "1318",  # Flash High
                        "prompt_tokens_uncached": 65000,
                        "cached_tokens": 0,
                    },
                ],
            }
        ]
        res = compute_cache_coaching_metrics(convs, self.pricing_models)
        self.assertEqual(res["cross_model_flips"], 1)
        self.assertEqual(res["intra_track_flips"], 1)
        self.assertEqual(res["intra_family_flips"], 0)
        self.assertEqual(res["cross_provider_flips"], 0)
        inc = res["flip_incidents"][0]
        self.assertEqual(inc["flip_type"], "intra_track")
        self.assertEqual(inc["from_family"], "gemini-argon")
        self.assertEqual(inc["to_family"], "gemini-flash")

    def test_cross_provider_model_flip(self):
        """Verify cross-provider flip between Claude Sonnet and Gemini Flash."""
        convs = [
            {
                "convo_id": "cross-provider-session",
                "title": "Cross Provider Refactor",
                "turns": [
                    {
                        "step_idx": 1,
                        "model_id": "1035",  # Claude Sonnet
                        "prompt_tokens_uncached": 10000,
                        "cached_tokens": 80000,
                    },
                    {
                        "step_idx": 2,
                        "model_id": "1318",  # Gemini Flash
                        "prompt_tokens_uncached": 90000,
                        "cached_tokens": 0,
                    },
                ],
            }
        ]
        res = compute_cache_coaching_metrics(convs, self.pricing_models)
        self.assertEqual(res["cross_model_flips"], 1)
        self.assertEqual(res["cross_provider_flips"], 1)
        self.assertEqual(res["intra_family_flips"], 0)
        self.assertEqual(res["intra_track_flips"], 0)
        self.assertIn("Cross-provider model flips", res["coaching_tip"])

    def test_mixed_flips_breakdown_accumulation(self):
        """Verify sessions with multiple types of flips sum correctly to cross_model_flips."""
        convs = [
            {
                "convo_id": "multi-flip-session",
                "title": "Multi-Phase Architecture",
                "turns": [
                    # Turn 1: Claude Sonnet
                    {"step_idx": 1, "model_id": "1035", "prompt_tokens_uncached": 10000, "cached_tokens": 60000},
                    # Turn 2: Cross-provider flip to Argon High
                    {"step_idx": 2, "model_id": "1417", "prompt_tokens_uncached": 75000, "cached_tokens": 0},
                    # Turn 3: Warm cache on Argon High
                    {"step_idx": 3, "model_id": "1417", "prompt_tokens_uncached": 3000, "cached_tokens": 76000},
                    # Turn 4: Intra-family tier flip to Argon Medium
                    {"step_idx": 4, "model_id": "1418", "prompt_tokens_uncached": 80000, "cached_tokens": 0},
                    # Turn 5: Warm cache on Argon Medium
                    {"step_idx": 5, "model_id": "1418", "prompt_tokens_uncached": 4000, "cached_tokens": 82000},
                    # Turn 6: Intra-track flip to Flash High
                    {"step_idx": 6, "model_id": "1318", "prompt_tokens_uncached": 88000, "cached_tokens": 0},
                ],
            }
        ]
        res = compute_cache_coaching_metrics(convs, self.pricing_models)
        self.assertEqual(res["cross_provider_flips"], 1)
        self.assertEqual(res["intra_family_flips"], 1)
        self.assertEqual(res["intra_track_flips"], 1)
        self.assertEqual(res["cross_model_flips"], 3)
        self.assertEqual(res["model_flips_detected"], 3)
        self.assertEqual(len(res["flip_incidents"]), 3)
        self.assertIn("GADR-018", res["coaching_tip"])
        self.assertIn("Cross-provider model flips", res["coaching_tip"])

    def test_zero_flips_when_consistent(self):
        """Verify that keeping the same model produces zero penalty and optimal message."""
        convs = [
            {
                "convo_id": "consistent-session",
                "turns": [
                    {"step_idx": 1, "model_id": "1417", "prompt_tokens_uncached": 5000, "cached_tokens": 70000},
                    {"step_idx": 2, "model_id": "1417", "prompt_tokens_uncached": 2000, "cached_tokens": 74000},
                ],
            }
        ]
        res = compute_cache_coaching_metrics(convs, self.pricing_models)
        self.assertEqual(res["cross_model_flips"], 0)
        self.assertEqual(res["estimated_flip_waste_tokens"], 0)
        self.assertEqual(res["estimated_flip_waste_usd"], 0.0)
        self.assertEqual(res["severity"], "none")
        self.assertIn("Zero model flips detected", res["coaching_tip"])

    def test_ignore_small_input_below_threshold(self):
        """Verify that tier flip on small input (< 40k tokens) is not flagged as KV cache eviction."""
        convs = [
            {
                "convo_id": "small-session",
                "turns": [
                    {"step_idx": 1, "model_id": "1417", "prompt_tokens_uncached": 1000, "cached_tokens": 5000},
                    {"step_idx": 2, "model_id": "1418", "prompt_tokens_uncached": 12000, "cached_tokens": 0},
                ],
            }
        ]
        res = compute_cache_coaching_metrics(convs, self.pricing_models)
        self.assertEqual(res["cross_model_flips"], 0)
        self.assertEqual(res["intra_family_flips"], 0)

    def test_carbon_intra_family_and_argon_to_carbon_intra_track_switches(self):
        """Verify Carbon intra-family switch (1427 -> 1438) and Argon-to-Carbon intra-track switch (1417 -> 1438)."""
        # 1. Intra-family tier switch: 1427 -> 1438 at >40k prompt depth with <20% cache hit
        convs_intra_family = [
            {
                "convo_id": "carbon-tier-flip",
                "title": "Carbon High to Low Flip",
                "turns": [
                    {
                        "step_idx": 1,
                        "model_id": "1427",
                        "prompt_tokens_uncached": 5000,
                        "cached_tokens": 55000,
                    },
                    {
                        "step_idx": 2,
                        "model_id": "1438",
                        "prompt_tokens_uncached": 62000,
                        "cached_tokens": 0,
                    },
                ],
            }
        ]
        res_fam = compute_cache_coaching_metrics(convs_intra_family, self.pricing_models)
        self.assertEqual(res_fam["intra_family_flips"], 1)
        self.assertEqual(res_fam["intra_track_flips"], 0)
        self.assertEqual(res_fam["flip_incidents"][0]["flip_type"], "intra_family")
        self.assertEqual(res_fam["flip_incidents"][0]["from_family"], "gemini-carbon")
        self.assertEqual(res_fam["flip_incidents"][0]["to_family"], "gemini-carbon")

        # 2. Cross-family intra-track switch: 1417 Argon -> 1438 Carbon at >40k depth with <20% cache hit
        convs_intra_track = [
            {
                "convo_id": "argon-to-carbon-flip",
                "title": "Argon High to Carbon Low Switch",
                "turns": [
                    {
                        "step_idx": 1,
                        "model_id": "1417",
                        "prompt_tokens_uncached": 5000,
                        "cached_tokens": 55000,
                    },
                    {
                        "step_idx": 2,
                        "model_id": "1438",
                        "prompt_tokens_uncached": 62000,
                        "cached_tokens": 0,
                    },
                ],
            }
        ]
        res_trk = compute_cache_coaching_metrics(convs_intra_track, self.pricing_models)
        self.assertEqual(res_trk["intra_track_flips"], 1)
        self.assertEqual(res_trk["intra_family_flips"], 0)
        self.assertEqual(res_trk["flip_incidents"][0]["flip_type"], "intra_track")
        self.assertEqual(res_trk["flip_incidents"][0]["from_family"], "gemini-argon")
        self.assertEqual(res_trk["flip_incidents"][0]["to_family"], "gemini-carbon")

    def test_normalize_model_id_and_family(self):
        """Verify normalization of placeholders and family resolution."""
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M427"), "1427")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M437"), "1437")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M438"), "1438")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M1417"), "1417")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M417"), "1417")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M1418"), "1418")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M418"), "1418")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M1419"), "1419")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M419"), "1419")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M525"), "1525")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M528"), "1528")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M667"), "1667")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M681"), "1681")
        self.assertEqual(normalize_model_id("MODEL_PLACEHOLDER_M669"), "1669")
        self.assertEqual(normalize_model_id("1318"), "1318")

        self.assertEqual(get_model_family("1427"), "gemini-carbon")
        self.assertEqual(get_model_family("1437"), "gemini-carbon")
        self.assertEqual(get_model_family("1438"), "gemini-carbon")
        self.assertEqual(get_model_family("1667"), "gemini-orchestrator")
        self.assertEqual(get_model_family("1681"), "gemini-orchestrator")
        self.assertEqual(get_model_family("1669"), "gemini-orchestrator")
        self.assertEqual(get_model_family("Orchestrator (Carbon)"), "gemini-orchestrator")
        self.assertEqual(get_model_family("Orchestrator Executor (Hydrogen)"), "gemini-orchestrator")
        self.assertEqual(get_model_family("1528"), "gemini-hydrogen")
        self.assertEqual(get_model_family("1525"), "gemini-hydrogen")
        self.assertEqual(get_model_family("1417"), "gemini-argon")
        self.assertEqual(get_model_family("1318"), "gemini-flash")
        self.assertEqual(get_model_family("1016"), "gemini-pro")
        self.assertEqual(get_model_family("1400"), "claude-opus")
        self.assertEqual(get_model_family("1403"), "claude-sonnet")
        self.assertEqual(get_model_family("1018"), "gemini-flash")
        self.assertEqual(get_model_family("1027"), "claude-opus")


if __name__ == "__main__":
    unittest.main()
