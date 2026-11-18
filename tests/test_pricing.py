"""
Unit tests for Antigravity Pricing & Ultra-Era Capacity Calibration (Milestone 94 / ADR-038).
Validates pricing.json schema, temporal subscription eras, and capacity calibrations.
"""

import json
from pathlib import Path
import unittest

from src.temporal import (
    PLAN_PRESETS,
    get_plan_preset,
    get_subscription_for_timestamp,
    get_temporal_resolver,
)
from scripts.configure_plan import apply_tier_preset


class TestPricingAndCapacityCalibration(unittest.TestCase):
    def setUp(self):
        self.pricing_path = Path("config/pricing.json")
        self.assertTrue(self.pricing_path.exists(), "config/pricing.json must exist")
        with open(self.pricing_path, "r", encoding="utf-8") as f:
            self.pricing = json.load(f)

    def test_active_subscription_ultra_5x_capacity(self):
        """Active subscription must reflect empirical 2,500 credits ($25) burst and $100 weekly capacity."""
        sub = self.pricing.get("subscription", {})
        self.assertEqual(sub.get("tier"), "ultra_5x")
        ql = sub.get("quota_limits", {})
        self.assertEqual(ql.get("gemini_5h_capacity_usd"), 25.00)
        self.assertEqual(ql.get("gemini_weekly_capacity_usd"), 100.00)

        # Invariant: 4.0000x weekly/burst capacity ratio
        ratio = ql["gemini_weekly_capacity_usd"] / ql["gemini_5h_capacity_usd"]
        self.assertAlmostEqual(ratio, 4.0, places=4)

    def test_subscription_history_eras(self):
        """Historical Pro era (pre-Sep 13) and Ultra era (Sep 13+) must remain calibrated."""
        history = self.pricing.get("subscription_history", [])
        self.assertGreaterEqual(len(history), 2)

        # Era 0: Pro (pre-2026-09-13T17:58:04Z)
        era_pro = history[0]
        self.assertEqual(era_pro.get("tier"), "pro")
        self.assertEqual(era_pro["valid_to"], "2026-09-13T17:58:04Z")
        pro_ql = era_pro.get("quota_limits", {})
        self.assertEqual(pro_ql.get("gemini_5h_capacity_usd"), 20.00)
        self.assertEqual(pro_ql.get("gemini_weekly_capacity_usd"), 129.00)

        # Era 1: Ultra 5x (from 2026-09-13T17:58:04Z onwards)
        era_ultra = history[1]
        self.assertEqual(era_ultra.get("tier"), "ultra_5x")
        self.assertEqual(era_ultra["valid_from"], "2026-09-13T17:58:04Z")
        self.assertIsNone(era_ultra.get("valid_to"))
        ultra_ql = era_ultra.get("quota_limits", {})
        self.assertEqual(ultra_ql.get("gemini_5h_capacity_usd"), 25.00)
        self.assertEqual(ultra_ql.get("gemini_weekly_capacity_usd"), 100.00)

    def test_temporal_subscription_resolution(self):
        """get_subscription_for_timestamp correctly transitions between Pro and Ultra eras."""
        # Ultra era (October 2026)
        u_sub = get_subscription_for_timestamp("2026-10-14T12:00:00Z", self.pricing)
        self.assertEqual(u_sub.get("tier"), "ultra_5x")
        self.assertEqual(u_sub["quota_limits"]["gemini_5h_capacity_usd"], 25.00)
        self.assertEqual(u_sub["quota_limits"]["gemini_weekly_capacity_usd"], 100.00)

        # Pro era (early September 2026)
        pro_sub = get_subscription_for_timestamp("2026-09-05T12:00:00Z", self.pricing)
        self.assertEqual(pro_sub.get("tier"), "pro")
        self.assertEqual(pro_sub["quota_limits"]["gemini_5h_capacity_usd"], 20.00)
        self.assertEqual(pro_sub["quota_limits"]["gemini_weekly_capacity_usd"], 129.00)

        # Fallback without explicit timestamp or with None
        curr_sub = get_subscription_for_timestamp(None, self.pricing)
        self.assertEqual(curr_sub.get("tier"), "ultra_5x")
        self.assertEqual(curr_sub["quota_limits"]["gemini_5h_capacity_usd"], 25.00)

    def test_temporal_presets_calibration(self):
        """DEFAULT_PLAN_PRESETS in src/temporal.py must match calibrated Ultra capacity."""
        ultra_preset = get_plan_preset("ultra_5x")
        self.assertIsNotNone(ultra_preset)
        self.assertEqual(ultra_preset["quota_limits"]["gemini_5h_capacity_usd"], 25.00)
        self.assertEqual(ultra_preset["quota_limits"]["gemini_weekly_capacity_usd"], 100.00)

        ent_preset = get_plan_preset("enterprise_5x")
        self.assertIsNotNone(ent_preset)
        self.assertEqual(ent_preset["quota_limits"]["gemini_5h_capacity_usd"], 25.00)
        self.assertEqual(ent_preset["quota_limits"]["gemini_weekly_capacity_usd"], 100.00)

        pro_preset = get_plan_preset("pro")
        self.assertIsNotNone(pro_preset)
        self.assertEqual(pro_preset["quota_limits"]["gemini_5h_capacity_usd"], 20.00)
        self.assertEqual(pro_preset["quota_limits"]["gemini_weekly_capacity_usd"], 129.00)

    def test_configure_plan_tier_preset(self):
        """scripts/configure_plan apply_tier_preset applies calibrated limits."""
        cfg = {"subscription": {}}
        apply_tier_preset(cfg, "ultra_5x")
        self.assertEqual(cfg["subscription"]["quota_limits"]["gemini_5h_capacity_usd"], 25.00)
        self.assertEqual(cfg["subscription"]["quota_limits"]["gemini_weekly_capacity_usd"], 100.00)

        cfg_ent = {"subscription": {}}
        apply_tier_preset(cfg_ent, "enterprise_5x")
        self.assertEqual(cfg_ent["subscription"]["quota_limits"]["gemini_5h_capacity_usd"], 25.00)
        self.assertEqual(cfg_ent["subscription"]["quota_limits"]["gemini_weekly_capacity_usd"], 100.00)

        cfg_pro = {"subscription": {}}
        apply_tier_preset(cfg_pro, "pro")
        self.assertEqual(cfg_pro["subscription"]["quota_limits"]["gemini_5h_capacity_usd"], 20.00)
        self.assertEqual(cfg_pro["subscription"]["quota_limits"]["gemini_weekly_capacity_usd"], 129.00)


if __name__ == "__main__":
    unittest.main()
