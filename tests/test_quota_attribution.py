"""
tests/test_quota_attribution.py

Unit tests for Milestone 25:
- 5-Hour rolling window session attribution (M3 / ADR-038)
- Cache-efficiency coaching & cross-provider model-flip diagnostics (M5 / ADR-030 / ADR-038)
- Plan configuration CLI calibrator (M7 / ADR-038)
"""

import datetime
import json
from pathlib import Path
import tempfile
import unittest

from src.aggregator import (
    aggregate_global_telemetry,
    compute_cache_coaching_metrics,
    compute_rolling_window_telemetry,
)
from scripts.configure_plan import (
    apply_tier_preset,
    load_config,
    save_config_atomic,
    show_plan,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestQuotaAttribution(unittest.TestCase):
    """Test suite verifying per-session quota attribution, cache coaching, and plan configuration."""

    def setUp(self):
        self.pricing_models = {
            "subscription": {
                "tier": "pro",
                "name": "Google One AI Premium (Antigravity Pro)",
                "monthly_price_gbp": 18.99,
                "monthly_price_usd": 19.99,
                "renewal_day": 24,
                "quota_limits": {
                    "burst_5h_tokens": 168000000,
                    "gemini_5h_capacity_usd": 20.00,
                    "gemini_weekly_capacity_usd": 129.00,
                    "claude_5h_capacity_usd": 10.00,
                    "claude_weekly_capacity_usd": 35.00,
                },
            },
            "currency": {
                "default": "GBP",
                "usd_to_gbp_fx_rate": 0.79,
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
            "default": {
                "name": "Default Model",
                "rates_per_million": {
                    "prompt_uncached": 0.75,
                    "prompt_cached": 0.075,
                    "candidate_output": 3.75,
                },
            },
        }

    def test_5h_window_session_attribution(self):
        """Verify that turns in a 5h rolling window are partitioned by convo_id with correct totals."""
        ref_time = datetime.datetime(2026, 9, 13, 12, 0, 0, tzinfo=datetime.timezone.utc)
        t_recent_1 = (ref_time - datetime.timedelta(hours=1)).isoformat()
        t_recent_2 = (ref_time - datetime.timedelta(hours=2)).isoformat()
        t_old = (ref_time - datetime.timedelta(hours=6)).isoformat()

        turns = [
            # Convo A: 2 turns inside 5h
            {
                "convo_id": "convo-alpha",
                "timestamp": t_recent_1,
                "model_id": "1318",
                "prompt_tokens_uncached": 1000,
                "cached_tokens": 9000,
                "output_tokens_total": 500,
            },
            {
                "convo_id": "convo-alpha",
                "timestamp": t_recent_2,
                "model_id": "1318",
                "prompt_tokens_uncached": 2000,
                "cached_tokens": 8000,
                "output_tokens_total": 1000,
            },
            # Convo B: 1 turn inside 5h, 1 turn outside 5h
            {
                "convo_id": "convo-beta",
                "timestamp": t_recent_1,
                "model_id": "1035",
                "prompt_tokens_uncached": 5000,
                "cached_tokens": 15000,
                "output_tokens_total": 2000,
            },
            {
                "convo_id": "convo-beta",
                "timestamp": t_old,
                "model_id": "1035",
                "prompt_tokens_uncached": 50000,
                "cached_tokens": 100000,
                "output_tokens_total": 5000,
            },
        ]

        result = compute_rolling_window_telemetry(
            turns, window_hours=5.0, reference_time=ref_time, pricing_models=self.pricing_models
        )

        self.assertIn("active_sessions_5h", result)
        sessions = result["active_sessions_5h"]
        self.assertEqual(len(sessions), 2)

        # Sorted by total processed tokens descending
        # Convo B in window: 5000 + 15000 + 2000 = 22,000 tokens
        # Convo A in window: 1000 + 9000 + 500 + 2000 + 8000 + 1000 = 21,500 tokens
        self.assertEqual(sessions[0]["convo_id"], "convo-beta")
        self.assertEqual(sessions[0]["total_processed_tokens"], 22000)
        self.assertEqual(sessions[0]["turn_count"], 1)
        self.assertEqual(sessions[0]["primary_model_name"], "Claude Sonnet 4.6 (Thinking)")

        self.assertEqual(sessions[1]["convo_id"], "convo-alpha")
        self.assertEqual(sessions[1]["total_processed_tokens"], 21500)
        self.assertEqual(sessions[1]["turn_count"], 2)
        self.assertEqual(sessions[1]["primary_model_name"], "Gemini 3.8 Flash (High)")

    def test_cache_coaching_model_flip_detection(self):
        """Verify cross-provider model flips (Gemini <-> Claude) evicting KV cache are quantified."""
        t1 = "2026-09-09T10:00:00Z"
        t2 = "2026-09-09T10:05:00Z"
        t3 = "2026-09-09T10:10:00Z"

        convo_summaries = [
            {
                "convo_id": "convo-flip-1",
                "title": "Complex Architecture Refactor",
                "workspace_name": "Workspace A",
                "turns": [
                    # Turn 0: Deep Claude turn (80k tokens total)
                    {
                        "step_idx": 1,
                        "timestamp": t1,
                        "model_id": "1035",  # Claude (claude_gpt track)
                        "prompt_tokens_uncached": 10000,
                        "cached_tokens": 70000,
                        "output_tokens_total": 2000,
                    },
                    # Turn 1: Flip to Gemini Flash, cache evicted (85k tokens uncached, 0 cached)
                    {
                        "step_idx": 2,
                        "timestamp": t2,
                        "model_id": "1318",  # Gemini (gemini track)
                        "prompt_tokens_uncached": 85000,
                        "cached_tokens": 0,
                        "output_tokens_total": 1500,
                    },
                    # Turn 2: Stays on Gemini Flash, cache warms up (cache hit > 80%)
                    {
                        "step_idx": 3,
                        "timestamp": t3,
                        "model_id": "1318",  # Gemini
                        "prompt_tokens_uncached": 5000,
                        "cached_tokens": 82000,
                        "output_tokens_total": 1000,
                    },
                ],
            }
        ]

        coaching = compute_cache_coaching_metrics(
            convo_summaries, self.pricing_models, usd_to_gbp_fx=0.79
        )

        self.assertEqual(coaching["model_flips_detected"], 1)
        self.assertGreater(coaching["wasted_uncached_tokens"], 70000)
        self.assertGreater(coaching["wasted_avoided_cost_usd"], 0.0)
        self.assertEqual(len(coaching["top_incidents"]), 1)

        inc = coaching["top_incidents"][0]
        self.assertEqual(inc["convo_id"], "convo-flip-1")
        self.assertEqual(inc["from_track"], "claude_gpt")
        self.assertEqual(inc["to_track"], "gemini")
        self.assertIn("Cross-provider model flips", coaching["coaching_tip"])

    def test_cache_coaching_zero_penalty_when_consistent(self):
        """Verify that staying on the same provider model incurs zero model-flip penalties."""
        convo_summaries = [
            {
                "convo_id": "convo-consistent",
                "title": "Consistent Deep Session",
                "workspace_name": "Workspace B",
                "turns": [
                    {
                        "step_idx": 1,
                        "timestamp": "2026-09-09T10:00:00Z",
                        "model_id": "1318",
                        "prompt_tokens_uncached": 5000,
                        "cached_tokens": 50000,
                        "output_tokens_total": 1000,
                    },
                    {
                        "step_idx": 2,
                        "timestamp": "2026-09-09T10:05:00Z",
                        "model_id": "1318",
                        "prompt_tokens_uncached": 4000,
                        "cached_tokens": 52000,
                        "output_tokens_total": 1000,
                    },
                ],
            }
        ]

        coaching = compute_cache_coaching_metrics(
            convo_summaries, self.pricing_models, usd_to_gbp_fx=0.79
        )
        self.assertEqual(coaching["model_flips_detected"], 0)
        self.assertEqual(coaching["wasted_uncached_tokens"], 0)
        self.assertEqual(coaching["wasted_avoided_cost_usd"], 0.0)
        self.assertEqual(len(coaching["top_incidents"]), 0)

    def test_configure_plan_presets_and_atomic_save(self):
        """Verify configure_plan tier presets and atomic write operations."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cfg_path = Path(tmp_dir) / "pricing.json"
            save_config_atomic(self.pricing_models, cfg_path)
            self.assertTrue(cfg_path.exists())

            loaded = load_config(cfg_path)
            self.assertEqual(loaded["subscription"]["tier"], "pro")

            # Apply enterprise_5x tier
            apply_tier_preset(loaded, "enterprise_5x")
            self.assertEqual(loaded["subscription"]["tier"], "enterprise_5x")
            self.assertEqual(loaded["subscription"]["quota_limits"]["gemini_weekly_capacity_usd"], 645.00)

            # Atomic save and re-load
            save_config_atomic(loaded, cfg_path)
            reloaded = load_config(cfg_path)
            self.assertEqual(reloaded["subscription"]["tier"], "enterprise_5x")
            self.assertEqual(reloaded["subscription"]["quota_limits"]["burst_5h_tokens"], 840000000)

    def test_temporal_weekly_bounds_pro_vs_ultra(self):
        """Verify get_weekly_cycle_bounds dynamically resolves Thursday for Pro and Sunday for Ultra."""
        from src.aggregator import get_weekly_cycle_bounds

        # 1. Pre-upgrade (Pro era): Saturday 5 Sep 2026 -> Thursday 18:00 UTC reset
        pro_ref = datetime.datetime(2026, 9, 5, 16, 18, 0, tzinfo=datetime.timezone.utc)
        pro_bounds = get_weekly_cycle_bounds(pro_ref)
        self.assertEqual(pro_bounds["reset_day_name"], "Thursday")
        self.assertEqual(pro_bounds["cycle_start_utc"], "2026-09-03T18:00:00+00:00")
        self.assertEqual(pro_bounds["cycle_end_utc"], "2026-09-10T18:00:00+00:00")
        self.assertIn("10 Sep 2026", pro_bounds["reset_display"])

        # 2. Post-upgrade (Ultra era): Sunday 13 Sep 2026 18:15 UTC -> Sunday 17:58:04 UTC reset
        ultra_ref = datetime.datetime(2026, 9, 13, 18, 15, 57, tzinfo=datetime.timezone.utc)
        ultra_bounds = get_weekly_cycle_bounds(ultra_ref)
        self.assertEqual(ultra_bounds["reset_day_name"], "Sunday")
        self.assertEqual(ultra_bounds["cycle_start_utc"], "2026-09-13T17:58:04+00:00")
        self.assertEqual(ultra_bounds["cycle_end_utc"], "2026-09-20T17:58:04+00:00")
        self.assertEqual(ultra_bounds["days_remaining"], 6)
        self.assertEqual(ultra_bounds["hours_remaining"], 23)
        self.assertEqual(ultra_bounds["human_remaining"], "6 days, 23 hours")
        self.assertIn("20 Sep 2026", ultra_bounds["reset_display"])

    def test_explicit_reset_dt_override(self):
        """Verify explicit_reset_dt directly forces weekly bounds matching live desktop indicator."""
        from src.aggregator import get_weekly_cycle_bounds

        ref = datetime.datetime(2026, 9, 13, 18, 15, 57, tzinfo=datetime.timezone.utc)
        explicit = datetime.datetime(2026, 9, 20, 17, 58, 4, tzinfo=datetime.timezone.utc)
        bounds = get_weekly_cycle_bounds(ref, explicit_reset_dt=explicit)
        self.assertEqual(bounds["cycle_start_utc"], "2026-09-13T17:58:04+00:00")
        self.assertEqual(bounds["cycle_end_utc"], "2026-09-20T17:58:04+00:00")
        self.assertEqual(bounds["human_remaining"], "6 days, 23 hours")

    def test_monthly_billing_bounds_day_13(self):
        """Verify get_monthly_billing_bounds anchors to Day 13 monthly renewal."""
        from src.aggregator import get_monthly_billing_bounds

        ref = datetime.datetime(2026, 9, 13, 18, 15, 57, tzinfo=datetime.timezone.utc)
        bounds = get_monthly_billing_bounds(ref, billing_day=13, plan_price_gbp=79.99, plan_price_usd=99.99)
        self.assertEqual(bounds["billing_day"], 13)
        self.assertEqual(bounds["cycle_start_utc"], "2026-09-13T18:00:00+00:00")
        self.assertEqual(bounds["renewal_date"], "2026-10-13T18:00:00+00:00")
        self.assertIn("13 Oct 2026", bounds["renewal_display"])
        self.assertEqual(bounds["monthly_plan_price_gbp"], 79.99)

    def test_vault_subscription_sync_prunes_stale_records(self):
        """Verify sync_subscription_to_vault synchronizes history and prunes stale valid_from records."""
        import sqlite3
        from src.vault import init_vault, sync_subscription_to_vault

        with tempfile.TemporaryDirectory() as tmp_dir:
            v_path = Path(tmp_dir) / "test_vault.db"
            init_vault(v_path)

            # Insert a stale entry
            conn = sqlite3.connect(v_path)
            conn.execute(
                "INSERT INTO subscription_history_archive (tier, name, valid_from, renewal_day) VALUES ('old', 'Old Tier', '2020-01-01T00:00:00Z', 1)"
            )
            conn.commit()
            conn.close()

            # Sync from pricing.json
            sync_subscription_to_vault(vault_path=v_path)

            conn = sqlite3.connect(f"file:{v_path}?mode=ro", uri=True)
            rows = conn.execute("SELECT tier, valid_from, renewal_day FROM subscription_history_archive ORDER BY valid_from ASC").fetchall()
            conn.close()

            # Verify stale entry was pruned and current entries are present
            tiers = [r[0] for r in rows]
            self.assertNotIn("old", tiers)
            self.assertIn("pro", tiers)
            self.assertIn("ultra_5x", tiers)
            ultra_row = [r for r in rows if r[0] == "ultra_5x"][0]
            self.assertEqual(ultra_row[1], "2026-09-13T17:58:04Z")
            self.assertEqual(ultra_row[2], 13)


if __name__ == "__main__":
    unittest.main()
