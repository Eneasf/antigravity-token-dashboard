"""
Unit tests for src/temporal.py (Milestone 20: ADR-034).
"""

import datetime
import unittest

from src.temporal import (
    PLAN_PRESETS,
    TemporalPricingResolver,
    get_temporal_resolver,
    in_temporal_interval,
    parse_temporal_timestamp,
)


class TestTemporalResolver(unittest.TestCase):
    def setUp(self):
        self.sample_config = {
            "subscription": {
                "tier": "pro",
                "name": "Google One AI Premium (Antigravity Pro)",
                "monthly_price_gbp": 18.99,
                "monthly_price_usd": 19.99,
                "quota_limits": {
                    "gemini_5h_capacity_usd": 20.0,
                    "gemini_weekly_capacity_usd": 129.0,
                    "claude_5h_capacity_usd": 10.0,
                    "claude_weekly_capacity_usd": 35.0,
                },
            },
            "subscription_history": [
                {
                    "valid_from": "2025-01-01T00:00:00Z",
                    "valid_to": "2026-05-31T23:59:59Z",
                    "tier": "pro",
                    "name": "Google One AI Premium (Old Rate)",
                    "monthly_price_gbp": 15.99,
                    "monthly_price_usd": 16.99,
                    "quota_limits": {
                        "gemini_5h_capacity_usd": 15.0,
                        "gemini_weekly_capacity_usd": 100.0,
                    },
                },
                {
                    "valid_from": "2026-06-01T00:00:00Z",
                    "valid_to": None,
                    "tier": "enterprise_5x",
                    "name": "Antigravity Enterprise (5x)",
                    "monthly_price_gbp": 49.99,
                    "monthly_price_usd": 59.99,
                    "quota_limits": {
                        "gemini_5h_capacity_usd": 100.0,
                        "gemini_weekly_capacity_usd": 645.0,
                    },
                },
            ],
            "promotions": [
                {
                    "id": "promo_gemini_boost",
                    "name": "Gemini 2x Overlay",
                    "valid_from": "2026-08-01T00:00:00Z",
                    "valid_to": "2026-08-15T23:59:59Z",
                    "target_provider": "gemini",
                    "multiplier": 2.0,
                },
                {
                    "id": "promo_all_flash",
                    "name": "All Providers 1.5x Flash Boost",
                    "valid_from": "2026-08-10T00:00:00Z",
                    "valid_to": "2026-08-20T23:59:59Z",
                    "target_provider": "all",
                    "multiplier": 1.5,
                },
            ],
            "rate_history": {
                "1318": [
                    {
                        "valid_from": "2026-01-01T00:00:00Z",
                        "valid_to": "2026-06-30T23:59:59Z",
                        "rates_per_million": {
                            "prompt_uncached": 0.80,
                            "prompt_cached": 0.08,
                            "candidate_output": 4.00,
                        },
                    },
                    {
                        "valid_from": "2026-07-01T00:00:00Z",
                        "valid_to": None,
                        "rates_per_million": {
                            "prompt_uncached": 0.75,
                            "prompt_cached": 0.075,
                            "candidate_output": 3.75,
                        },
                    },
                ]
            },
            "models": {
                "1318": {
                    "name": "Gemini 3.8 Flash (High)",
                    "rates_per_million": {
                        "prompt_uncached": 0.75,
                        "prompt_cached": 0.075,
                        "candidate_output": 3.75,
                    },
                },
                "default": {
                    "rates_per_million": {
                        "prompt_uncached": 0.10,
                        "prompt_cached": 0.025,
                        "candidate_output": 0.40,
                    }
                },
            },
            "availability": {
                "1318": {
                    "preview_from": "2026-02-01T00:00:00Z",
                    "ga_from": "2026-05-01T00:00:00Z",
                    "sunset_at": None,
                    "status": "ga",
                },
                "old_model": {
                    "preview_from": "2025-01-01T00:00:00Z",
                    "ga_from": "2025-03-01T00:00:00Z",
                    "sunset_at": "2026-04-01T00:00:00Z",
                    "status": "sunset",
                },
            },
        }
        self.resolver = TemporalPricingResolver(self.sample_config)

    def test_parse_temporal_timestamp(self):
        self.assertIsNone(parse_temporal_timestamp(None))
        self.assertIsNone(parse_temporal_timestamp(""))
        self.assertIsNone(parse_temporal_timestamp("   "))

        dt = datetime.datetime(2026, 8, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(parse_temporal_timestamp(dt), dt)

        # Naive datetime
        naive = datetime.datetime(2026, 8, 1, 12, 0, 0)
        parsed_naive = parse_temporal_timestamp(naive)
        self.assertEqual(parsed_naive.tzinfo, datetime.timezone.utc)
        self.assertEqual(parsed_naive.hour, 12)

        # ISO string with Z
        iso_z = "2026-08-01T12:00:00Z"
        parsed_z = parse_temporal_timestamp(iso_z)
        self.assertEqual(parsed_z.year, 2026)
        self.assertEqual(parsed_z.tzinfo, datetime.timezone.utc)

        # Epoch seconds
        epoch = 1754049600.0  # around Aug 2025
        parsed_epoch = parse_temporal_timestamp(epoch)
        self.assertIsNotNone(parsed_epoch)
        self.assertEqual(parsed_epoch.tzinfo, datetime.timezone.utc)

        # Epoch milliseconds
        epoch_ms = 1754049600000.0
        parsed_ms = parse_temporal_timestamp(epoch_ms)
        self.assertEqual(parsed_ms, parsed_epoch)

    def test_in_temporal_interval(self):
        t = datetime.datetime(2026, 6, 15, 12, 0, 0, tzinfo=datetime.timezone.utc)

        # Both open
        self.assertTrue(in_temporal_interval(t, None, None))
        # Left bounded, open right
        self.assertTrue(in_temporal_interval(t, "2026-01-01T00:00:00Z", None))
        self.assertFalse(in_temporal_interval(t, "2026-07-01T00:00:00Z", None))
        # Right bounded, open left
        self.assertTrue(in_temporal_interval(t, None, "2026-12-31T23:59:59Z"))
        self.assertFalse(in_temporal_interval(t, None, "2026-05-01T00:00:00Z"))
        # Closed interval
        self.assertTrue(in_temporal_interval(t, "2026-06-01T00:00:00Z", "2026-06-30T23:59:59Z"))
        self.assertFalse(in_temporal_interval(t, "2026-07-01T00:00:00Z", "2026-07-31T23:59:59Z"))

    def test_resolve_rates(self):
        # 1. Historical turn in H1 2026 (before rate cut)
        rates_h1 = self.resolver.resolve_rates("1318", "2026-04-15T12:00:00Z")
        self.assertEqual(rates_h1["prompt_uncached"], 0.80)
        self.assertEqual(rates_h1["candidate_output"], 4.00)

        # 2. Modern turn in H2 2026 (after rate cut)
        rates_h2 = self.resolver.resolve_rates("1318", "2026-08-01T12:00:00Z")
        self.assertEqual(rates_h2["prompt_uncached"], 0.75)
        self.assertEqual(rates_h2["candidate_output"], 3.75)

        # 3. None timestamp falls back to current model rates
        rates_none = self.resolver.resolve_rates("1318", None)
        self.assertEqual(rates_none["prompt_uncached"], 0.75)

        # 4. Unknown model falls back to default rates
        rates_unk = self.resolver.resolve_rates("9999", "2026-04-15T12:00:00Z")
        self.assertEqual(rates_unk["prompt_uncached"], 0.10)

    def test_resolve_subscription(self):
        # Past interval (Pro old rate)
        sub_past = self.resolver.resolve_subscription("2025-05-01T00:00:00Z")
        self.assertEqual(sub_past["tier"], "pro")
        self.assertEqual(sub_past["monthly_price_gbp"], 15.99)
        self.assertEqual(sub_past["quota_limits"]["gemini_5h_capacity_usd"], 15.0)

        # Current interval (Enterprise 5x)
        sub_curr = self.resolver.resolve_subscription("2026-07-15T00:00:00Z")
        self.assertEqual(sub_curr["tier"], "enterprise_5x")
        self.assertEqual(sub_curr["monthly_price_gbp"], 49.99)
        self.assertEqual(sub_curr["quota_limits"]["gemini_5h_capacity_usd"], 100.0)

        # None timestamp falls back to top-level subscription config
        sub_none = self.resolver.resolve_subscription(None)
        self.assertEqual(sub_none["tier"], "pro")
        self.assertEqual(sub_none["monthly_price_gbp"], 18.99)

    def test_resolve_promotions_and_multipliers(self):
        # Outside promotion window
        promos_early = self.resolver.resolve_promotions("2026-07-01T00:00:00Z", provider="gemini")
        self.assertEqual(len(promos_early), 0)
        self.assertEqual(self.resolver.get_capacity_multiplier("2026-07-01T00:00:00Z", "gemini"), 1.0)

        # Inside gemini boost window only (2026-08-05)
        promos_mid = self.resolver.resolve_promotions("2026-08-05T12:00:00Z", provider="gemini")
        self.assertEqual(len(promos_mid), 1)
        self.assertEqual(promos_mid[0]["id"], "promo_gemini_boost")
        self.assertEqual(self.resolver.get_capacity_multiplier("2026-08-05T12:00:00Z", "gemini"), 2.0)
        # Claude during this same time has 1.0 (gemini boost only targets gemini)
        self.assertEqual(self.resolver.get_capacity_multiplier("2026-08-05T12:00:00Z", "claude_gpt"), 1.0)

        # Inside overlapping promotions window (2026-08-12): gemini gets 2.0 * 1.5 = 3.0x
        promos_overlap = self.resolver.resolve_promotions("2026-08-12T12:00:00Z", provider="gemini")
        self.assertEqual(len(promos_overlap), 2)
        self.assertEqual(self.resolver.get_capacity_multiplier("2026-08-12T12:00:00Z", "gemini"), 3.0)

        # Claude gets only the "all" promo (1.5x)
        self.assertEqual(self.resolver.get_capacity_multiplier("2026-08-12T12:00:00Z", "claude_gpt"), 1.5)

    def test_resolve_model_status(self):
        # Model 1318
        # Before preview: 2026-01-01
        st_pre = self.resolver.resolve_model_status("1318", "2026-01-01T00:00:00Z")
        self.assertEqual(st_pre["status"], "ga")  # base status when before preview

        # Preview: 2026-03-01
        st_prev = self.resolver.resolve_model_status("1318", "2026-03-01T00:00:00Z")
        self.assertEqual(st_prev["status"], "preview")

        # GA: 2026-06-01
        st_ga = self.resolver.resolve_model_status("1318", "2026-06-01T00:00:00Z")
        self.assertEqual(st_ga["status"], "ga")

        # Model old_model sunset after 2026-04-01
        st_sunset = self.resolver.resolve_model_status("old_model", "2026-05-01T00:00:00Z")
        self.assertEqual(st_sunset["status"], "sunset")

    def test_plan_presets_and_provenance(self):
        presets = self.resolver.get_plan_presets()
        self.assertGreaterEqual(len(presets), 4)
        tiers = [p["tier"] for p in presets]
        self.assertIn("pro", tiers)
        self.assertIn("enterprise_5x", tiers)
        self.assertIn("ultra_10x", tiers)
        self.assertIn("custom", tiers)

        prov = self.resolver.get_provenance_summary("2026-08-05T12:00:00Z")
        self.assertIn("resolved_at_utc", prov)
        self.assertIn("active_plan", prov)
        self.assertIn("active_promotions", prov)
        self.assertIn("capacity_multipliers", prov)
        self.assertIn("plan_presets", prov)

    def test_factory_and_default_resolver(self):
        res1 = get_temporal_resolver()
        res2 = get_temporal_resolver()
        self.assertIs(res1, res2)


if __name__ == "__main__":
    unittest.main()
