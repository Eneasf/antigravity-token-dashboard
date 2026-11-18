"""
Unit tests for src/horizon_analytics.py (Milestone M96).
"""

import datetime
import json
import unittest
from typing import Any, Dict, List

from src.horizon_analytics import (
    CANONICAL_FAMILIES,
    DEFAULT_ERA_CUTOVER_UTC,
    HORIZON_KEYS,
    classify_model_family,
    compute_horizon_analytics,
    load_merged_vault_and_live_turns,
    resolve_era_cutover,
)


class TestHorizonAnalytics(unittest.TestCase):

    def setUp(self):
        self.pricing_models = {
            "1417": {
                "name": "Gemini 4 Argon (High)",
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
            "1016": {
                "name": "Gemini 3.1 Pro (High)",
                "family": "gemini-pro",
                "rates_per_million": {
                    "prompt_uncached": 2.00,
                    "prompt_cached": 0.20,
                    "candidate_output": 12.00,
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
                    "prompt_uncached": 0.75,
                    "prompt_cached": 0.075,
                    "candidate_output": 3.75,
                },
            },
        }
        self.pricing_data = {
            "models": self.pricing_models,
            "currency": {
                "default": "GBP",
                "usd_to_gbp_fx_rate": 0.79,
            },
            "subscription_history": [
                {
                    "valid_from": "2024-01-01T00:00:00Z",
                    "valid_to": "2026-09-13T17:58:04Z",
                    "tier": "pro",
                    "monthly_price_gbp": 18.99,
                },
                {
                    "valid_from": "2026-09-13T17:58:04Z",
                    "valid_to": None,
                    "tier": "ultra_5x",
                    "monthly_price_gbp": 79.99,
                },
            ],
        }

    def test_cutover_partitioning(self):
        """Test strict Pro (< 2026-09-13T17:58:04Z) vs Ultra (>= 2026-09-13T17:58:04Z) partitioning."""
        turns = [
            # Exactly 1 second before cutover -> Pro era
            {
                "timestamp": "2026-09-13T17:58:03Z",
                "model_id": "1318",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 5000,
                "output_tokens_total": 200,
            },
            # 5 days before cutover -> Pro era
            {
                "timestamp": "2026-09-08T12:00:00Z",
                "model_id": "1016",
                "prompt_tokens_uncached": 2000,
                "cached_tokens": 8000,
                "output_tokens_total": 400,
            },
            # Exactly on cutover -> Ultra era
            {
                "timestamp": "2026-09-13T17:58:04Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 3000,
                "cached_tokens": 12000,
                "output_tokens_total": 600,
            },
            # 5 days after cutover -> Ultra era
            {
                "timestamp": "2026-09-18T15:30:00Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 4000,
                "cached_tokens": 16000,
                "output_tokens_total": 800,
            },
        ]

        ref_dt = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = compute_horizon_analytics(
            turns=turns,
            pricing_data=self.pricing_data,
            reference_time=ref_dt,
        )

        horizons = result["horizons"]
        self.assertEqual(horizons["pro_era"]["total_turns"], 2)
        self.assertEqual(horizons["ultra_era"]["total_turns"], 2)
        self.assertEqual(horizons["lifetime"]["total_turns"], 4)

        # Verify Pro era turns
        self.assertEqual(horizons["pro_era"]["prompt_tokens_uncached"], 3000)
        self.assertEqual(horizons["pro_era"]["cached_tokens"], 13000)

        # Verify Ultra era turns
        self.assertEqual(horizons["ultra_era"]["prompt_tokens_uncached"], 7000)
        self.assertEqual(horizons["ultra_era"]["cached_tokens"], 28000)

        # Test custom cutover resolution
        custom_pricing = {
            "models": self.pricing_models,
            "subscription_history": [
                {
                    "valid_from": "2026-10-01T00:00:00Z",
                    "valid_to": None,
                    "tier": "ultra_5x",
                }
            ],
        }
        res_custom = compute_horizon_analytics(
            turns=turns,
            pricing_data=custom_pricing,
            reference_time=ref_dt,
        )
        self.assertEqual(res_custom["era_cutover_utc"], "2026-10-01T00:00:00Z")
        # With cutover at 2026-10-01, all 4 turns are < 2026-10-01 -> all in Pro era
        self.assertEqual(res_custom["horizons"]["pro_era"]["total_turns"], 4)
        self.assertEqual(res_custom["horizons"]["ultra_era"]["total_turns"], 0)

    def test_era_comparison_and_normalized_velocity(self):
        """Test normalized daily velocity multipliers and deltas in era_comparison."""
        turns = [
            # Pro era: Day 1 (2026-09-01) - 10k tokens, 1 turn, rate limit 0
            {
                "timestamp": "2026-09-01T10:00:00Z",
                "model_id": "1318",
                "prompt_tokens_uncached": 2000,
                "cached_tokens": 7000,
                "output_tokens_total": 1000,
                "thinking_tokens": 200,
                "answer_tokens": 800,
                "latency_ms": 1000.0,
                "is_subagent": False,
            },
            # Pro era: Day 2 (2026-09-02) - 10k tokens, 1 turn, 1 rate limit
            {
                "timestamp": "2026-09-02T10:00:00Z",
                "model_id": "1318",
                "prompt_tokens_uncached": 2000,
                "cached_tokens": 7000,
                "output_tokens_total": 1000,
                "thinking_tokens": 200,
                "answer_tokens": 800,
                "latency_ms": 1000.0,
                "rate_limit_flag": 1,
                "is_subagent": False,
            },
            # Ultra era: Day 1 (2026-09-15) - 30k tokens, 2 turns, rate limit 0
            {
                "timestamp": "2026-09-15T10:00:00Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 5000,
                "cached_tokens": 20000,
                "output_tokens_total": 5000,
                "thinking_tokens": 2000,
                "answer_tokens": 3000,
                "latency_ms": 2000.0,
                "is_subagent": True,
            },
            # Ultra era: Day 2 (2026-09-16) - 30k tokens, 2 turns, rate limit 0
            {
                "timestamp": "2026-09-16T10:00:00Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 5000,
                "cached_tokens": 20000,
                "output_tokens_total": 5000,
                "thinking_tokens": 2000,
                "answer_tokens": 3000,
                "latency_ms": 2000.0,
                "is_subagent": True,
            },
        ]

        ref_dt = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = compute_horizon_analytics(
            turns=turns,
            pricing_data=self.pricing_data,
            reference_time=ref_dt,
        )

        cmp = result["era_comparison"]
        pro_h = result["horizons"]["pro_era"]
        ultra_h = result["horizons"]["ultra_era"]

        # Pro: 20k tokens over 2 active days = 10,000 / day
        # Ultra: 60k tokens over 2 active days = 30,000 / day
        self.assertEqual(pro_h["daily_avg_tokens"], 10000.0)
        self.assertEqual(ultra_h["daily_avg_tokens"], 30000.0)
        self.assertEqual(cmp["daily_tokens_multiplier"], 3.0)

        # Pro: 2 turns over 2 active days = 1 turn / day
        # Ultra: 2 turns over 2 active days = 1 turn / day
        self.assertEqual(cmp["daily_turns_multiplier"], 1.0)

        # Multiplier of daily value
        self.assertGreater(cmp["daily_value_multiplier"], 1.0)

        # Deltas
        # Cache hit delta: Ultra cache hit ratio - Pro cache hit ratio
        self.assertEqual(cmp["cache_hit_delta_pct"], round(ultra_h["cache_hit_ratio_pct"] - pro_h["cache_hit_ratio_pct"], 2))
        # Thinking share delta
        self.assertEqual(cmp["thinking_share_delta_pct"], round(ultra_h["thinking_share_pct"] - pro_h["thinking_share_pct"], 2))
        # Subagent share delta: Pro had 0%, Ultra had 100% -> +100.0%
        self.assertEqual(cmp["subagent_share_delta_pct"], 100.0)

        # Latency delta: 2000ms vs 1000ms -> +100.0%
        self.assertEqual(cmp["latency_mean_delta_pct"], 100.0)

        # ROI checks
        self.assertEqual(cmp["roi_pro_x"], pro_h["roi_multiplier"])
        self.assertEqual(cmp["roi_ultra_x"], ultra_h["roi_multiplier"])

    def test_progression_series(self):
        """Test daily, weekly, monthly progression series sorting, by_family sums, and ROI."""
        turns = [
            # Week 36 (02 Sep 2026 - Wednesday) - Pro era
            {
                "timestamp": "2026-09-02T12:00:00Z",
                "model_id": "1318",
                "prompt_tokens_uncached": 5000,
                "cached_tokens": 15000,
                "output_tokens_total": 2000,
                "thinking_tokens": 500,
                "answer_tokens": 1500,
                "is_subagent": False,
            },
            # Week 37 (09 Sep 2026 - Wednesday) - Pro era
            {
                "timestamp": "2026-09-09T14:00:00Z",
                "model_id": "1016",
                "prompt_tokens_uncached": 8000,
                "cached_tokens": 20000,
                "output_tokens_total": 3000,
                "thinking_tokens": 1000,
                "answer_tokens": 2000,
                "is_subagent": True,
            },
            # Week 38 (16 Sep 2026 - Wednesday) - Ultra era
            {
                "timestamp": "2026-09-16T16:00:00Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 10000,
                "cached_tokens": 40000,
                "output_tokens_total": 5000,
                "thinking_tokens": 2500,
                "answer_tokens": 2500,
                "is_subagent": True,
            },
        ]

        incidents = [
            {
                "timestamp": "2026-09-02T13:00:00Z",
                "credit_burn_gbp": 5.00,
            }
        ]

        ref_dt = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = compute_horizon_analytics(
            turns=turns,
            pricing_data=self.pricing_data,
            ledger_incidents=incidents,
            reference_time=ref_dt,
        )

        series = result["progression_series"]
        self.assertIn("daily", series)
        self.assertIn("weekly", series)
        self.assertIn("monthly", series)

        # 1. Chronological sorting
        for s_key in ("daily", "weekly", "monthly"):
            buckets = series[s_key]
            keys = [b["bucket_key"] for b in buckets]
            self.assertEqual(keys, sorted(keys), f"{s_key} buckets must be sorted chronologically")

        # 2. Daily progression invariant assertions
        for b in series["daily"]:
            self.assertIn("by_family", b)
            # by_family sums == total_tokens
            family_sum = sum(b["by_family"].values())
            self.assertEqual(family_sum, b["total_tokens"], "Family token sum must equal total_tokens")
            # subagent_tokens + interactive_tokens == total_tokens
            self.assertEqual(b["subagent_tokens"] + b["interactive_tokens"], b["total_tokens"])
            # All 5 families present
            for fam in CANONICAL_FAMILIES:
                self.assertIn(fam, b["by_family"])
            # ROI multiplier check
            expected_spend = round(b["subscription_cost_gbp"] + b["overage_gbp"], 2)
            if expected_spend > 0:
                expected_roi = round(b["imputed_cost_gbp"] / expected_spend, 2)
                self.assertEqual(b["roi_multiplier"], expected_roi)

        # Check overage incorporation on 2026-09-02
        day_0902 = [b for b in series["daily"] if b["bucket_key"] == "2026-09-02"][0]
        self.assertEqual(day_0902["overage_gbp"], 5.00)

        # Check era tags
        day_0902 = [b for b in series["daily"] if b["bucket_key"] == "2026-09-02"][0]
        self.assertEqual(day_0902["era"], "pro")
        day_0916 = [b for b in series["daily"] if b["bucket_key"] == "2026-09-16"][0]
        self.assertEqual(day_0916["era"], "ultra_5x")

        # 3. Weekly progression invariants
        for b in series["weekly"]:
            self.assertEqual(sum(b["by_family"].values()), b["total_tokens"])
            self.assertEqual(b["subagent_tokens"] + b["interactive_tokens"], b["total_tokens"])

        # 4. Monthly progression invariants
        for b in series["monthly"]:
            self.assertEqual(sum(b["by_family"].values()), b["total_tokens"])
            self.assertEqual(b["subagent_tokens"] + b["interactive_tokens"], b["total_tokens"])

    def test_diurnal_profiles(self):
        """Test 24-hour diurnal profile completeness (0..23) and family latency stratification."""
        turns = [
            # Hour 03: Flash turn
            {
                "timestamp": "2026-09-15T03:15:00Z",
                "model_id": "1318",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 4000,
                "output_tokens_total": 200,
                "latency_ms": 500.0,
            },
            # Hour 14: Argon turn (latency 1200ms)
            {
                "timestamp": "2026-09-15T14:10:00Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 2000,
                "cached_tokens": 8000,
                "output_tokens_total": 500,
                "latency_ms": 1200.0,
            },
            # Hour 14: Claude turn (latency 3500ms)
            {
                "timestamp": "2026-09-15T14:40:00Z",
                "model_id": "1035",
                "prompt_tokens_uncached": 3000,
                "cached_tokens": 10000,
                "output_tokens_total": 1000,
                "latency_ms": 3500.0,
            },
        ]

        ref_dt = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = compute_horizon_analytics(
            turns=turns,
            pricing_data=self.pricing_data,
            reference_time=ref_dt,
        )

        diurnal = result["diurnal_profiles"]

        # Check all 5 horizon keys present
        for h_key in HORIZON_KEYS:
            self.assertIn(h_key, diurnal)
            profile = diurnal[h_key]
            self.assertEqual(len(profile), 24, f"Diurnal profile for {h_key} must have exactly 24 hours")
            for h in range(24):
                entry = profile[h]
                self.assertEqual(entry["hour_utc"], h)
                self.assertEqual(entry["label"], f"{h:02d}:00")
                self.assertIn("by_family_tokens", entry)
                self.assertIn("by_family_latency_ms", entry)
                self.assertIn("Gemini 4 Carbon", entry["by_family"])
                self.assertIn("Gemini 4 Carbon", entry["latency_by_model"])
                for fam in CANONICAL_FAMILIES:
                    self.assertIn(fam, entry["by_family_tokens"])
                    self.assertIn(fam, entry["by_family_latency_ms"])

        # Check Hour 14 stratification in Ultra era profile
        ultra_h14 = diurnal["ultra_era"][14]
        self.assertEqual(ultra_h14["turns"], 2)
        # Argon tokens and latency
        self.assertEqual(ultra_h14["by_family_tokens"]["gemini_argon"], 10500)
        self.assertEqual(ultra_h14["by_family_latency_ms"]["gemini_argon"], 1200.0)
        # Claude tokens and latency
        self.assertEqual(ultra_h14["by_family_tokens"]["claude"], 14000)
        self.assertEqual(ultra_h14["by_family_latency_ms"]["claude"], 3500.0)
        # Overall hour mean latency: (1200 + 3500) / 2 = 2350.0 ms
        self.assertEqual(ultra_h14["latency_mean_ms"], 2350.0)

    def test_subagent_classification(self):
        """Test subagent determination via turn.is_subagent, conversations map, and model ID fallback."""
        conversations = [
            {"id": "conv-agent-1", "is_subagent": True},
            {"id": "conv-user-1", "is_subagent": False},
        ]
        turns = [
            # 1. Explicit turn.is_subagent = True
            {
                "timestamp": "2026-09-15T10:00:00Z",
                "model_id": "1417",
                "convo_id": "conv-user-1",  # turn flag takes precedence
                "is_subagent": True,
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 1000,
                "output_tokens_total": 100,
            },
            # 2. Convo map lookup
            {
                "timestamp": "2026-09-15T11:00:00Z",
                "model_id": "1417",
                "convo_id": "conv-agent-1",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 1000,
                "output_tokens_total": 100,
            },
            # 3. Model ID fallback (1050 is in SUBAGENT_MODEL_IDS)
            {
                "timestamp": "2026-09-15T12:00:00Z",
                "model_id": "1050",
                "convo_id": "conv-unknown",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 1000,
                "output_tokens_total": 100,
            },
            # 4. Interactive user turn
            {
                "timestamp": "2026-09-15T13:00:00Z",
                "model_id": "1417",
                "convo_id": "conv-user-1",
                "is_subagent": False,
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 1000,
                "output_tokens_total": 100,
            },
        ]

        ref_dt = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = compute_horizon_analytics(
            turns=turns,
            conversations=conversations,
            pricing_data=self.pricing_data,
            reference_time=ref_dt,
        )

        ultra_h = result["horizons"]["ultra_era"]
        self.assertEqual(ultra_h["subagent_turns"], 3)
        self.assertEqual(ultra_h["total_turns"], 4)
        self.assertEqual(ultra_h["subagent_tokens"], 3 * 2100)
        self.assertEqual(ultra_h["interactive_tokens"], 1 * 2100)
        self.assertEqual(ultra_h["subagent_share_pct"], 75.0)

    def test_model_family_classification(self):
        """Test canonical model family classification rules."""
        self.assertEqual(classify_model_family("1427"), "gemini_carbon")
        self.assertEqual(classify_model_family("1437"), "gemini_carbon")
        self.assertEqual(classify_model_family("1438"), "gemini_carbon")
        self.assertEqual(classify_model_family("", "Gemini 4 Carbon (Low)"), "gemini_carbon")
        self.assertEqual(classify_model_family("Gemini 4 Carbon (Low)"), "gemini_carbon")
        self.assertEqual(classify_model_family("1417", "Gemini 4 Argon (High)"), "gemini_argon")
        self.assertEqual(classify_model_family("gemini-4-argon"), "gemini_argon")
        self.assertEqual(classify_model_family("1528", "Gemini 4 Hydrogen (XHigh)"), "gemini_hydrogen")
        self.assertEqual(classify_model_family("1525"), "gemini_hydrogen")
        self.assertEqual(classify_model_family("gemini-4-hydrogen-medium"), "gemini_hydrogen")
        self.assertEqual(classify_model_family("1667", "Orchestrator (Carbon)"), "gemini_orchestrator")
        self.assertEqual(classify_model_family("1681", "Orchestrator (Argon)"), "gemini_orchestrator")
        self.assertEqual(classify_model_family("1669", "Orchestrator Executor (Hydrogen)"), "gemini_orchestrator")
        self.assertEqual(classify_model_family("1318", "Gemini 3.8 Flash (High)"), "gemini_flash")
        self.assertEqual(classify_model_family("1322", "Gemini Fast Agent Assistant"), "gemini_flash")
        self.assertEqual(classify_model_family("1016", "Gemini 3.1 Pro (High)"), "gemini_pro")
        self.assertEqual(classify_model_family("1035", "Claude Sonnet 4.6 (Thinking)"), "claude")
        self.assertEqual(classify_model_family("1026", "Claude Opus 4.6 (Thinking)"), "claude")
        self.assertEqual(classify_model_family("claude-3-7-sonnet"), "claude")
        self.assertEqual(classify_model_family("342", "GPT-OSS 120B (Medium)"), "other")
        self.assertEqual(classify_model_family("custom-model"), "other")

    def test_determinism(self):
        """Test byte-identical JSON determinism given identical inputs."""
        turns = [
            {
                "timestamp": "2026-09-10T09:00:00Z",
                "model_id": "1318",
                "prompt_tokens_uncached": 5000,
                "cached_tokens": 15000,
                "output_tokens_total": 1000,
                "latency_ms": 800.0,
            },
            {
                "timestamp": "2026-09-15T14:00:00Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 8000,
                "cached_tokens": 32000,
                "output_tokens_total": 2000,
                "latency_ms": 1500.0,
            },
        ]
        ref_dt = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)

        run1 = compute_horizon_analytics(
            turns=turns,
            pricing_data=self.pricing_data,
            reference_time=ref_dt,
        )
        run2 = compute_horizon_analytics(
            turns=turns,
            pricing_data=self.pricing_data,
            reference_time=ref_dt,
        )

        json1 = json.dumps(run1, sort_keys=True, indent=2)
        json2 = json.dumps(run2, sort_keys=True, indent=2)
        self.assertEqual(json1, json2)

    def test_empty_turns_input(self):
        """Test that empty turns input returns safe, complete horizon structures."""
        ref_dt = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)
        result = compute_horizon_analytics(
            turns=[],
            pricing_data=self.pricing_data,
            reference_time=ref_dt,
        )

        self.assertIn("horizons", result)
        self.assertIn("era_comparison", result)
        self.assertIn("progression_series", result)
        self.assertIn("diurnal_profiles", result)

        for h_key in HORIZON_KEYS:
            h = result["horizons"][h_key]
            self.assertEqual(h["total_turns"], 0)
            self.assertEqual(h["active_days"], 1)
            self.assertEqual(h["roi_multiplier"], 0.0)
            self.assertEqual(sum(h["by_family"].values()), 0)

    def test_latency_strictly_positive_filter(self):
        """Test that latency calculation strictly filters latency_ms > 0, excluding 0.0 unrecorded values."""
        ref_dt = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)
        turns = [
            # Turn with 0.0 latency (unrecorded wire latency)
            {
                "timestamp": "2026-09-18T10:00:00Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 4000,
                "output_tokens_total": 500,
                "latency_ms": 0.0,
            },
            # Turn with valid recorded latency 100.0
            {
                "timestamp": "2026-09-18T10:05:00Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 4000,
                "output_tokens_total": 500,
                "latency_ms": 100.0,
            },
            # Turn with valid recorded latency 200.0
            {
                "timestamp": "2026-09-18T10:10:00Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 4000,
                "output_tokens_total": 500,
                "latency_ms": 200.0,
            },
        ]
        res = compute_horizon_analytics(turns=turns, pricing_data=self.pricing_data, reference_time=ref_dt)
        active_week = res["horizons"]["active_week"]

        # If 0.0 was included, p50 would be 100.0 and mean would be 100.0 ((0+100+200)/3).
        # With strictly > 0 filtering: latencies are [100.0, 200.0], so p50 is 150.0 and mean is 150.0.
        self.assertEqual(active_week["latency_p50_ms"], 150.0)
        self.assertEqual(active_week["latency_mean_ms"], 150.0)

        # Diurnal profile for hour 10:
        diurnal_h10 = [dp for dp in res["diurnal_profiles"]["active_week"] if dp["hour"] == 10][0]
        self.assertEqual(diurnal_h10["latency_p50_ms"], 150.0)
        self.assertEqual(diurnal_h10["by_family_latency_ms"]["gemini_argon"], 150.0)

    def test_load_merged_vault_and_live_turns(self):
        """Test merging vault turns with live turns and deduplication by (convo_id, step_idx)."""
        import tempfile
        import sqlite3
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            v_db = Path(tmpdir) / "test_vault.db"
            conn = sqlite3.connect(str(v_db))
            cur = conn.cursor()

            # Create mock schema
            cur.execute("""
                CREATE TABLE conversations_archive (
                    convo_id TEXT PRIMARY KEY,
                    is_subagent INTEGER
                )
            """)
            cur.execute("""
                CREATE TABLE v_turns (
                    convo_id TEXT,
                    step_idx INTEGER,
                    timestamp TEXT,
                    model_id TEXT,
                    model_name TEXT,
                    prompt_tokens_uncached INTEGER,
                    cached_tokens INTEGER,
                    total_input_tokens INTEGER,
                    output_tokens_total INTEGER,
                    thinking_tokens INTEGER,
                    total_tokens INTEGER,
                    rate_limit_flag INTEGER,
                    error_code TEXT,
                    ttft_ms REAL,
                    latency_ms REAL
                )
            """)

            # Insert archived conversation & turns (Pro era)
            cur.execute("INSERT INTO conversations_archive VALUES ('c-sub-1', 1)")
            cur.execute("INSERT INTO conversations_archive VALUES ('c-main-1', 0)")

            cur.execute("""
                INSERT INTO v_turns VALUES (
                    'c-sub-1', 1, '2026-06-01T10:00:00Z', '1050', 'Gemini Flash Lite',
                    2000, 8000, 10000, 400, 0, 10400, 0, NULL, 50.0, 120.0
                )
            """)
            cur.execute("""
                INSERT INTO v_turns VALUES (
                    'c-main-1', 1, '2026-06-01T11:00:00Z', '1016', 'Gemini 3.1 Pro',
                    5000, 20000, 25000, 1000, 400, 26000, 0, NULL, 150.0, 400.0
                )
            """)
            conn.commit()
            conn.close()

            # Live turns: one duplicate of c-main-1 step 1, plus one brand-new step 2
            live_turns = [
                {
                    "convo_id": "c-main-1",
                    "step_idx": 1,  # Duplicate of vault
                    "timestamp": "2026-06-01T11:00:00Z",
                    "model_id": "1016",
                    "prompt_tokens_uncached": 5000,
                    "cached_tokens": 20000,
                    "output_tokens_total": 1000,
                },
                {
                    "convo_id": "c-main-1",
                    "step_idx": 2,  # Brand-new turn
                    "timestamp": "2026-06-01T11:05:00Z",
                    "model_id": "1016",
                    "prompt_tokens_uncached": 3000,
                    "cached_tokens": 22000,
                    "output_tokens_total": 800,
                },
            ]
            live_convos = [
                {"convo_id": "c-main-1", "title": "Main Session"}
            ]

            merged_turns, merged_convos = load_merged_vault_and_live_turns(
                v_db,
                live_turns=live_turns,
                live_conversations=live_convos,
            )

            # Total turns must be 3 (c-sub-1 s1, c-main-1 s1, c-main-1 s2)
            self.assertEqual(len(merged_turns), 3)

            # Check subagent turn preserved
            sub_turns = [t for t in merged_turns if t["convo_id"] == "c-sub-1"]
            self.assertEqual(len(sub_turns), 1)
            self.assertTrue(sub_turns[0]["is_subagent"])

            # Check conversation archive metadata merged
            convo_ids = {c["convo_id"] for c in merged_convos}
            self.assertIn("c-sub-1", convo_ids)
            self.assertIn("c-main-1", convo_ids)

    def test_diurnal_family_latency_uses_p50_median(self):
        """Verify hourly model family latency uses median (p50) rather than mean to resist single-turn outliers."""
        ref_dt = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)
        turns = [
            {
                "timestamp": "2026-09-18T23:05:00Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 4000,
                "output_tokens_total": 500,
                "latency_ms": 120.0,
            },
            {
                "timestamp": "2026-09-18T23:15:00Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 4000,
                "output_tokens_total": 500,
                "latency_ms": 180.0,
            },
            {
                "timestamp": "2026-09-18T23:45:00Z",
                "model_id": "1417",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 4000,
                "output_tokens_total": 500,
                "latency_ms": 28488.0,
            },
        ]
        res = compute_horizon_analytics(turns=turns, pricing_data=self.pricing_data, reference_time=ref_dt)
        h23 = res["diurnal_profiles"]["lifetime"][23]
        self.assertEqual(h23["by_family_latency_ms"]["gemini_argon"], 180.0)


if __name__ == "__main__":
    unittest.main()

