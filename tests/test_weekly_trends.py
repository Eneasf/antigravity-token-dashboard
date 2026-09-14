"""
Unit tests for Historical Vault Trends & Weekly Cycles Analytics Engine (M4 / ADR-039).
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.vault import init_vault
from src.weekly_trends import (
    compute_weekly_cycles_from_turns,
    get_weekly_trends,
    sync_weekly_trends_to_vault,
)


class TestWeeklyTrends(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temp_dir.name) / "test_vault.db"
        self.ledger_path = Path(self.temp_dir.name) / "test_ledger.json"

        # Initialize test vault schema
        self.conn = init_vault(self.vault_path)

        # Mock sample pricing
        self.mock_pricing = {
            "1318": {
                "name": "Gemini 3.8 Flash (High)",
                "input_cached_per_million": 0.075,
                "input_uncached_per_million": 0.75,
                "output_per_million": 3.75,
            },
            "1016": {
                "name": "Gemini 3.1 Pro (High)",
                "input_cached_per_million": 0.50,
                "input_uncached_per_million": 2.00,
                "output_per_million": 12.00,
            },
        }

        # Mock ledger with one confirmed incident
        sample_ledger = {
            "incidents": [
                {
                    "hour_timestamp": "2026-09-05T13:00:00Z",
                    "credits_burned": 418,
                    "credit_burn_usd": 4.18,
                    "credit_burn_gbp": 4.01,
                    "reason": "RESOURCE_EXHAUSTED",
                }
            ]
        }
        self.ledger_path.write_text(json.dumps(sample_ledger), encoding="utf-8")

    def tearDown(self):
        try:
            self.conn.close()
        except Exception:
            pass
        self.temp_dir.cleanup()

    def test_schema_initialization(self):
        """Verify weekly_cycles_archive schema exists and has required columns."""
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_cycles_archive'")
        self.assertIsNotNone(cur.fetchone())

        cur.execute("PRAGMA table_info(weekly_cycles_archive)")
        cols = {r[1]: r[2] for r in cur.fetchall()}
        self.assertIn("cycle_key", cols)
        self.assertIn("cycle_start_utc", cols)
        self.assertIn("cycle_end_utc", cols)
        self.assertIn("total_processed_tokens", cols)
        self.assertIn("cache_hit_ratio_pct", cols)
        self.assertIn("estimated_cost_usd", cols)
        self.assertIn("actual_overage_credits", cols)
        self.assertIn("peak_bvi", cols)
        self.assertIn("is_current_cycle", cols)

    def test_compute_weekly_cycles_from_turns(self):
        """Verify grouping of turns into Thursday 18:00 UTC weekly cycles."""
        turns = [
            # Cycle 1: 27 Aug 18:00 UTC to 03 Sep 18:00 UTC
            {
                "timestamp": "2026-08-28T12:00:00+00:00",
                "model_id": "1318",
                "prompt_tokens_uncached": 10000,
                "cached_tokens": 90000,
                "total_input_tokens": 100000,
                "output_tokens_total": 2000,
            },
            {
                "timestamp": "2026-08-30T15:00:00+00:00",
                "model_id": "1318",
                "prompt_tokens_uncached": 5000,
                "cached_tokens": 95000,
                "total_input_tokens": 100000,
                "output_tokens_total": 1000,
            },
            # Cycle 2: 03 Sep 18:00 UTC to 10 Sep 18:00 UTC
            {
                "timestamp": "2026-09-04T10:00:00+00:00",
                "model_id": "1016",
                "prompt_tokens_uncached": 20000,
                "cached_tokens": 80000,
                "total_input_tokens": 100000,
                "output_tokens_total": 5000,
            },
        ]

        ref_time = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
        cycles = compute_weekly_cycles_from_turns(
            turns,
            pricing_models=self.mock_pricing,
            ledger_incidents=[],
            reference_time=ref_time,
        )

        self.assertEqual(len(cycles), 2)
        c1, c2 = cycles[0], cycles[1]

        # Cycle 1 checks
        self.assertIn("2026-08-27", c1["cycle_start_utc"])
        self.assertIn("2026-09-03", c1["cycle_end_utc"])
        self.assertEqual(c1["total_turns"], 2)
        self.assertEqual(c1["total_input_tokens"], 200000)
        self.assertEqual(c1["cached_tokens"], 185000)
        self.assertEqual(c1["total_output_tokens"], 3000)
        self.assertEqual(c1["total_processed_tokens"], 203000)
        self.assertAlmostEqual(c1["cache_hit_ratio_pct"], 92.5, places=1)
        self.assertEqual(c1["is_current_cycle"], 0)

        # Cycle 2 checks
        self.assertIn("2026-09-03", c2["cycle_start_utc"])
        self.assertIn("2026-09-10", c2["cycle_end_utc"])
        self.assertEqual(c2["total_turns"], 1)
        self.assertGreater(c2["estimated_cost_usd"], 0)

    def test_overage_incident_reconciliation(self):
        """Verify credit burn from ledger correctly correlates to the matching weekly cycle."""
        turns = [
            {
                "timestamp": "2026-09-05T12:30:00+00:00",
                "model_id": "1318",
                "prompt_tokens_uncached": 10000,
                "cached_tokens": 90000,
                "total_input_tokens": 100000,
                "output_tokens_total": 1000,
            }
        ]

        ledger_incidents = [
            {
                "hour_timestamp": "2026-09-05T13:00:00Z",
                "credits_burned": 418,
                "credit_burn_usd": 4.18,
                "credit_burn_gbp": 4.01,
            },
            {
                "hour_timestamp": "2026-09-08T22:00:00Z",
                "credits_burned": 558,
                "credit_burn_usd": 5.58,
                "credit_burn_gbp": 5.35,
            },
        ]

        cycles = compute_weekly_cycles_from_turns(
            turns,
            pricing_models=self.mock_pricing,
            ledger_incidents=ledger_incidents,
        )

        self.assertEqual(len(cycles), 1)
        cyc = cycles[0]
        self.assertEqual(cyc["actual_overage_credits"], 418 + 558)
        self.assertAlmostEqual(cyc["actual_overage_usd"], 9.76, places=2)
        self.assertAlmostEqual(cyc["actual_overage_gbp"], 9.36, places=2)

    def test_sync_weekly_trends_to_vault(self):
        """Verify sync_weekly_trends_to_vault populates weekly_cycles_archive in SQLite."""
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO steps_archive (
                convo_id, step_idx, step_type, status, timestamp,
                model_id, prompt_tokens_uncached, cached_tokens,
                total_input_tokens, output_tokens_total
            ) VALUES
            ('convo-1', 1, 15, 1, '2026-08-28T10:00:00+00:00', '1318', 5000, 45000, 50000, 1000),
            ('convo-1', 2, 15, 1, '2026-09-04T12:00:00+00:00', '1318', 6000, 54000, 60000, 1500)
            """
        )
        self.conn.commit()

        res = sync_weekly_trends_to_vault(
            vault_path=self.vault_path,
            pricing_models=self.mock_pricing,
            ledger_path=self.ledger_path,
        )

        self.assertEqual(res["cycles_synced"], 2)
        self.assertEqual(res["total_turns_archived"], 2)

        cur.execute("SELECT COUNT(*) FROM weekly_cycles_archive")
        self.assertEqual(cur.fetchone()[0], 2)

    def test_get_weekly_trends_and_summary(self):
        """Verify get_weekly_trends retrieves sliced cycles and macro summary metrics."""
        cur = self.conn.cursor()
        # Seed 3 cycles into weekly_cycles_archive
        cur.execute(
            """
            INSERT INTO weekly_cycles_archive (
                cycle_key, cycle_start_utc, cycle_end_utc, label,
                total_turns, total_input_tokens, cached_tokens,
                prompt_tokens_uncached, total_output_tokens,
                total_processed_tokens, cache_hit_ratio_pct,
                estimated_cost_usd, estimated_cost_gbp,
                actual_overage_credits, actual_overage_usd,
                actual_overage_gbp, peak_bvi, is_current_cycle, updated_at
            ) VALUES
            ('2026-08-20_18:00', '2026-08-20T18:00:00+00:00', '2026-08-27T18:00:00+00:00', '20 Aug – 27 Aug', 10, 100000, 90000, 10000, 2000, 102000, 90.0, 1.5, 1.18, 0, 0, 0, 0.4, 0, '2026-09-13T12:00:00'),
            ('2026-08-27_18:00', '2026-08-27T18:00:00+00:00', '2026-09-03T18:00:00+00:00', '27 Aug – 03 Sep', 20, 200000, 180000, 20000, 4000, 204000, 90.0, 3.0, 2.37, 0, 0, 0, 0.8, 0, '2026-09-13T12:00:00'),
            ('2026-09-03_18:00', '2026-09-03T18:00:00+00:00', '2026-09-10T18:00:00+00:00', '03 Sep – 10 Sep', 50, 500000, 450000, 50000, 10000, 510000, 90.0, 8.5, 6.71, 418, 4.18, 4.01, 1.45, 0, '2026-09-13T12:00:00')
            """
        )
        self.conn.commit()

        trends = get_weekly_trends(vault_path=self.vault_path, limit_weeks=2)
        self.assertEqual(len(trends["cycles"]), 2)
        self.assertEqual(trends["total_cycles_recorded"], 3)

        summary = trends["summary"]
        self.assertEqual(summary["cycles_analyzed"], 2)
        self.assertEqual(summary["peak_week_tokens"], 510000)
        self.assertEqual(summary["peak_week_label"], "03 Sep – 10 Sep")
        self.assertEqual(summary["overage_cycles_count"], 1)
        self.assertEqual(summary["total_overage_credits"], 418)
        self.assertGreater(summary["average_tokens_per_week"], 0)

    def test_fallback_in_memory_calculation(self):
        """Verify get_weekly_trends gracefully falls back to in-memory turns when vault is absent."""
        fake_vault = Path(self.temp_dir.name) / "non_existent_vault.db"
        turns = [
            {
                "timestamp": "2026-09-04T12:00:00+00:00",
                "model_id": "1318",
                "prompt_tokens_uncached": 5000,
                "cached_tokens": 45000,
                "total_input_tokens": 50000,
                "output_tokens_total": 1000,
            }
        ]

        trends = get_weekly_trends(
            vault_path=fake_vault,
            fallback_turns=turns,
            pricing_models=self.mock_pricing,
            ledger_path=self.ledger_path,
        )

        self.assertEqual(len(trends["cycles"]), 1)
        self.assertEqual(trends["summary"]["cycles_analyzed"], 1)
        self.assertEqual(trends["cycles"][0]["total_processed_tokens"], 51000)


if __name__ == "__main__":
    unittest.main()
