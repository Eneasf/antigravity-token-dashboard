"""
Unit and integration test harness for scripts/quota_regression.py (Row 10 / Finding C9).

Verifies:
1. Turn cost calculation math across uncached, cached, and output token rates.
2. Official rate cards presence, proportions, and benchmark weights in config/pricing.json.
3. CLI argument parsing, flags, and hermetic dry-run execution.
4. Hermetic regression execution using offline fixtures (tests/fixtures/antigravity).
5. Offline fallback and zero-division resilience for quota indicator convergence.
"""

import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent

from scripts.quota_regression import (
    build_parser,
    calc_turn_cost,
    main,
    run_regression_analysis,
)


class TestQuotaRegression(unittest.TestCase):
    """Test suite ensuring scripts/quota_regression.py operates deterministically and safely."""

    @classmethod
    def setUpClass(cls):
        cls.pricing_path = REPO_ROOT / "config" / "pricing.json"
        with open(cls.pricing_path, "r", encoding="utf-8") as f:
            cls.pricing_cfg = json.load(f)
        cls.models_cfg = cls.pricing_cfg.get("models", {})

    def test_calc_turn_cost_standard(self):
        """Verify cost calculation for standard Gemini Flash rates."""
        flash_rates = {
            "prompt_uncached": 0.75,
            "prompt_cached": 0.075,
            "candidate_output": 3.75,
        }
        models_cfg = {"1318": {"rates_per_million": flash_rates}}

        turn = {
            "model_id": "1318",
            "prompt_tokens_uncached": 1_000_000,
            "cached_tokens": 1_000_000,
            "output_tokens_total": 1_000_000,
        }
        # 1M uncached ($0.75) + 1M cached ($0.075) + 1M output ($3.75) = $4.575
        cost = calc_turn_cost(turn, models_cfg)
        self.assertAlmostEqual(cost, 4.575, places=4)

    def test_calc_turn_cost_defaults_and_fallbacks(self):
        """Verify cost calculation defaults missing token fields and uses fallback rates."""
        fallback = {
            "prompt_uncached": 1.0,
            "prompt_cached": 0.1,
            "candidate_output": 2.0,
        }
        turn = {"model_id": "unknown_model"}
        cost = calc_turn_cost(turn, {}, fallback_rates=fallback)
        self.assertEqual(cost, 0.0)

        turn_with_uncached = {
            "model_id": "unknown_model",
            "prompt_tokens_uncached": 500_000,
        }
        cost_uncached = calc_turn_cost(turn_with_uncached, {}, fallback_rates=fallback)
        self.assertAlmostEqual(cost_uncached, 0.5, places=4)

    def test_rate_cards_presence_and_proportions(self):
        """Verify presence of baseline models and their relative pricing proportions."""
        self.assertIn("1318", self.models_cfg, "Model 1318 (Flash) must exist in pricing.json")
        self.assertIn("1016", self.models_cfg, "Model 1016 (Pro) must exist in pricing.json")
        self.assertIn("1050", self.models_cfg, "Model 1050 (Flash-Lite) must exist in pricing.json")

        flash_in = self.models_cfg["1318"]["rates_per_million"]["prompt_uncached"]
        pro_in = self.models_cfg["1016"]["rates_per_million"]["prompt_uncached"]
        lite_in = self.models_cfg["1050"]["rates_per_million"]["prompt_uncached"]

        self.assertGreater(pro_in, flash_in, "Pro uncached rate must exceed Flash uncached rate")
        self.assertLess(lite_in, flash_in, "Flash-Lite uncached rate must be below Flash uncached rate")

    def test_build_parser_options(self):
        """Verify that CLI parser contains required arguments."""
        parser = build_parser()
        args = parser.parse_args([
            "--antigravity-dir", "/tmp/antigravity",
            "--pricing-config", "/tmp/pricing.json",
            "--no-live-quota",
            "--dry-run",
        ])
        self.assertEqual(str(args.antigravity_dir), "/tmp/antigravity")
        self.assertEqual(str(args.pricing_config), "/tmp/pricing.json")
        self.assertTrue(args.no_live_quota)
        self.assertTrue(args.dry_run)

    def test_run_regression_analysis_dry_run(self):
        """Verify run_regression_analysis runs hermetically in dry-run mode."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = run_regression_analysis(dry_run=True)

        self.assertTrue(result.get("dry_run"))
        self.assertIn("flash_rates", result)
        self.assertIn("pro_rates", result)
        self.assertIn("lite_rates", result)
        output = buf.getvalue()
        self.assertIn("OFFICIAL GOOGLE RATE CARDS", output)
        self.assertIn("[OK] REGRESSION & CONVERGENCE VERIFICATION COMPLETE (DRY RUN)", output)

    def test_main_cli_dry_run(self):
        """Verify main() CLI executes cleanly with --dry-run and returns exit code 0."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["--dry-run"])
        self.assertEqual(code, 0)
        self.assertIn("DRY RUN", buf.getvalue())

    def test_run_regression_analysis_fixtures(self):
        """Verify run_regression_analysis runs hermetically against offline fixtures."""
        fixtures_dir = REPO_ROOT / "tests" / "fixtures" / "antigravity"
        if not fixtures_dir.exists():
            self.skipTest("tests/fixtures/antigravity directory not present")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = run_regression_analysis(
                antigravity_dir=fixtures_dir,
                no_live_quota=True,
            )

        self.assertFalse(result.get("dry_run"))
        self.assertGreaterEqual(result.get("total_turns", 0), 0)
        output = buf.getvalue()
        self.assertIn("INGESTING ACTIVE TELEMETRY FROM LOCAL SYSTEM", output)
        self.assertIn("[OK] REGRESSION & CONVERGENCE VERIFICATION COMPLETE", output)

    @patch("scripts.quota_regression.fetch_live_quota_summary")
    def test_live_quota_convergence_reporting(self, mock_live_quota):
        """Verify convergence math when live quota indicator reports valid percentages."""
        mock_live_quota.return_value = {
            "available": True,
            "gemini_weekly": {"remaining_pct": 50.0, "used_pct": 50.0},
            "gemini_5h": {"remaining_pct": 80.0, "used_pct": 20.0},
        }

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = run_regression_analysis(
                antigravity_dir=REPO_ROOT / "tests" / "fixtures" / "antigravity",
                no_live_quota=False,
            )

        output = buf.getvalue()
        self.assertIn("Weekly Indicator Ground Truth", output)
        self.assertIn("5-Hour Indicator Ground Truth", output)

    @patch("scripts.quota_regression.fetch_live_quota_summary")
    def test_zero_division_guard(self, mock_live_quota):
        """Verify solved capacity falls back safely when used percentage is zero."""
        mock_live_quota.return_value = {
            "available": True,
            "gemini_weekly": {"remaining_pct": 100.0, "used_pct": 0.0},
            "gemini_5h": {"remaining_pct": 100.0, "used_pct": 0.0},
        }

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = run_regression_analysis(
                antigravity_dir=REPO_ROOT / "tests" / "fixtures" / "antigravity",
                no_live_quota=False,
            )

        output = buf.getvalue()
        self.assertIn("Solved Weekly Capacity:   $133.00 USD", output)
        self.assertIn("Solved 5-Hour Capacity:   $20.00 USD", output)

    def test_vault_quota_snapshot_sync_and_burn_intervals(self):
        """Verify sync_quota_snapshot_to_vault deduplicates consecutive snapshots and v_quota_burn_intervals computes the 4.0x pool ratio."""
        import datetime
        import tempfile
        from scripts.quota_regression import analyze_vault_burn_intervals
        from src.vault import sync_quota_snapshot_to_vault

        with tempfile.TemporaryDirectory() as tmp:
            vp = Path(tmp) / "vault.db"
            s1 = {
                "gemini": {
                    "five_hour": {"remaining_fraction": 1.0, "reset_time": "2026-10-14T14:00:00Z"},
                    "weekly": {"remaining_fraction": 1.0, "reset_time": "2026-10-21T09:02:46Z"},
                },
                "claude_gpt": {
                    "five_hour": {"remaining_fraction": 1.0, "reset_time": "2026-10-14T14:00:00Z"},
                    "weekly": {"remaining_fraction": 1.0, "reset_time": "2026-10-21T09:02:46Z"},
                },
            }
            s2 = {
                "gemini": {
                    "five_hour": {"remaining_fraction": 0.80, "reset_time": "2026-10-14T14:00:00Z"},
                    "weekly": {"remaining_fraction": 0.95, "reset_time": "2026-10-21T09:02:46Z"},
                },
                "claude_gpt": {
                    "five_hour": {"remaining_fraction": 1.0, "reset_time": "2026-10-14T14:00:00Z"},
                    "weekly": {"remaining_fraction": 1.0, "reset_time": "2026-10-21T09:02:46Z"},
                },
            }

            r1 = sync_quota_snapshot_to_vault(s1, vault_path=vp, timestamp_utc="2026-10-14T10:00:00+00:00")
            r1_dup = sync_quota_snapshot_to_vault(s1, vault_path=vp, timestamp_utc="2026-10-14T10:05:00+00:00")
            r2 = sync_quota_snapshot_to_vault(s2, vault_path=vp, timestamp_utc="2026-10-14T10:15:00+00:00")

            self.assertTrue(r1.get("inserted"))
            self.assertFalse(r1_dup.get("inserted"), "Consecutive identical quota snapshot must be deduplicated")
            self.assertTrue(r2.get("inserted"))

            turns = [
                {
                    "model_id": "1417",
                    "prompt_tokens_uncached": 100_000,
                    "cached_tokens": 900_000,
                    "output_tokens_total": 10_000,
                    "dt": datetime.datetime(2026, 10, 14, 10, 10, tzinfo=datetime.timezone.utc),
                }
            ]
            report = analyze_vault_burn_intervals(vp, turns, self.models_cfg, self.models_cfg["1318"]["rates_per_million"])
            self.assertEqual(report["snapshots_count"], 2)
            self.assertEqual(len(report["intervals"]), 1)
            self.assertAlmostEqual(report["pool_ratio_mean"], 4.0, places=2)
            self.assertEqual(report["intervals"][0]["turns_count"], 1)
            self.assertEqual(report["intervals"][0]["primary_model_id"], "1417")


if __name__ == "__main__":
    unittest.main()
