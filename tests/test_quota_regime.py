"""
Unit tests for Quota Regime & Burn-Rate Drift Detector (Milestone 97 / Gate B16).
"""

import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts.quota_regression import main as regression_main
from src.quota_regime import (
    CALIBRATED_QUOTA_WEIGHTS_POST_OCT17,
    PUBLIC_API_RATES,
    check_early_weekly_reset_bonus,
    compute_turn_quota_usd,
    evaluate_vault_quota_regime,
    generate_calibration_probe_prompts,
    update_regime_event_review_status,
)
from src.vault import sync_quota_snapshot_to_vault
from src.vault_schema import init_vault


class TestQuotaRegimeDetector(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)
        self.vault_path = self.root / "test_vault.db"
        self.ledger_path = self.root / "quota_regime_ledger.json"
        conn = init_vault(self.vault_path)
        conn.close()

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_check_early_weekly_reset_bonus_triggers_when_early(self) -> None:
        prev = {
            "id": 310,
            "timestamp_utc": "2026-10-16T22:57:50Z",
            "gemini_5h_remaining": 0.82,
            "gemini_weekly_remaining": 0.2459965,
            "gemini_weekly_reset_utc": "2026-10-20T15:36:14Z",
            "turns_analyzed": 128,
        }
        curr = {
            "id": 311,
            "timestamp_utc": "2026-10-17T01:46:18Z",
            "gemini_5h_remaining": 0.50,
            "gemini_weekly_remaining": 1.0,
            "gemini_weekly_reset_utc": "2026-10-24T01:46:18Z",
        }
        bonus = check_early_weekly_reset_bonus(prev, curr)
        self.assertIsNotNone(bonus)
        assert bonus is not None
        self.assertEqual(bonus["id"], "exc-20261017-01")
        self.assertEqual(bonus["event_id"], "reg-20261017-bonus")
        self.assertEqual(bonus["reason"], "QUOTA_RESET_BONUS")
        self.assertEqual(bonus["credits_burned"], 0)
        self.assertAlmostEqual(bonus["bonus_pct_forgiven"], 75.4, places=1)
        self.assertEqual(bonus["bonus_credits_forgiven"], 7540)
        self.assertAlmostEqual(bonus["bonus_value_usd"], 75.40, places=2)
        self.assertAlmostEqual(bonus["bonus_value_gbp"], 59.57, places=2)
        self.assertEqual(bonus["snapshot_range"], "#310 -> #311")
        self.assertEqual(bonus["turns_analyzed"], 128)
        self.assertAlmostEqual(bonus["pre_reset_5h_rem_pct"], 82.0, places=2)
        self.assertAlmostEqual(bonus["post_reset_5h_rem_pct"], 50.0, places=2)
        self.assertAlmostEqual(bonus["delta_5h_pct"], -32.0, places=2)

    def test_check_early_weekly_reset_bonus_ignores_scheduled_reset(self) -> None:
        # Reset occurring within 1 hour of scheduled weekly_reset_utc is normal, not an unscheduled bonus
        prev = {
            "timestamp_utc": "2026-10-20T15:10:00Z",
            "gemini_weekly_remaining": 0.20,
            "gemini_weekly_reset_utc": "2026-10-20T15:36:14Z",
        }
        curr = {
            "timestamp_utc": "2026-10-20T15:36:20Z",
            "gemini_weekly_remaining": 1.0,
            "gemini_weekly_reset_utc": "2026-10-27T15:36:14Z",
        }
        self.assertIsNone(check_early_weekly_reset_bonus(prev, curr))

    def test_sync_quota_snapshot_to_vault_records_early_reset_in_vault(self) -> None:
        q1 = {
            "gemini": {
                "five_hour": {"remaining_fraction": 0.6862, "reset_time": "2026-10-17T03:00:00Z"},
                "weekly": {"remaining_fraction": 0.246, "reset_time": "2026-10-20T15:36:14Z"},
            }
        }
        q2 = {
            "gemini": {
                "five_hour": {"remaining_fraction": 1.0, "reset_time": "2026-10-17T06:46:18Z"},
                "weekly": {"remaining_fraction": 1.0, "reset_time": "2026-10-24T01:46:18Z"},
            }
        }
        r1 = sync_quota_snapshot_to_vault(q1, vault_path=self.vault_path, timestamp_utc="2026-10-16T22:57:50Z")
        self.assertTrue(r1["inserted"])
        r2 = sync_quota_snapshot_to_vault(q2, vault_path=self.vault_path, timestamp_utc="2026-10-17T01:46:18Z")
        self.assertTrue(r2["inserted"])
        self.assertIn("early_reset_bonus", r2)
        self.assertEqual(r2["early_reset_bonus"]["bonus_credits_forgiven"], 7540)

        conn = sqlite3.connect(str(self.vault_path))
        row = conn.execute(
            "SELECT event_type, code FROM log_events_archive WHERE event_fingerprint = 'bonus-exc-20261017-01'"
        ).fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "QUOTA_RESET_BONUS")
        self.assertEqual(row[1], 200)

    def test_evaluate_vault_quota_regime_and_review_workflow(self) -> None:
        conn = sqlite3.connect(str(self.vault_path))
        cur = conn.cursor()
        # Insert pre-reset and post-reset snapshots
        snaps = [
            (1, "fp1", "2026-10-16T12:00:00Z", 1.0, 0.0, "2026-10-16T17:00:00Z", 0.30, 70.0, "2026-10-20T15:36:14Z"),
            (2, "fp2", "2026-10-16T13:00:00Z", 0.96, 4.0, "2026-10-16T17:00:00Z", 0.29, 71.0, "2026-10-20T15:36:14Z"),
            (3, "fp3", "2026-10-17T01:46:18Z", 1.0, 0.0, "2026-10-17T06:46:18Z", 1.0, 0.0, "2026-10-24T01:46:18Z"),
            (4, "fp4", "2026-10-17T13:18:00Z", 0.992, 0.8, "2026-10-17T18:18:00Z", 0.998, 0.2, "2026-10-24T01:46:18Z"),
        ]
        for sid, fp, ts, g5, g5u, g5r, gw, gwu, gwr in snaps:
            cur.execute(
                """
                INSERT INTO quota_snapshots_archive (
                    id, snapshot_fingerprint, timestamp_utc,
                    gemini_5h_remaining, gemini_5h_used_pct, gemini_5h_reset_utc,
                    gemini_weekly_remaining, gemini_weekly_used_pct, gemini_weekly_reset_utc,
                    active_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'SAFE_IN_QUOTA')
                """,
                (sid, fp, ts, g5, g5u, g5r, gw, gwu, gwr),
            )

        # Insert 6 turns in pre-reset and 7 turns in post-reset for model 1417
        for idx in range(1, 7):
            cur.execute(
                """
                INSERT INTO steps_archive (
                    convo_id, step_idx, step_type, timestamp, model_id, model_name, status,
                    prompt_tokens_uncached, cached_tokens, total_input_tokens, output_tokens_total, thinking_tokens
                ) VALUES (?, ?, 15, ?, '1419', 'Gemini 4 Argon (Low)', 3, 20000, 100000, 120000, 2000, 500)
                """,
                ("convo-pre", idx, f"2026-10-16T12:1{idx}:00Z"),
            )
        for idx in range(1, 8):
            cur.execute(
                """
                INSERT INTO steps_archive (
                    convo_id, step_idx, step_type, timestamp, model_id, model_name, status,
                    prompt_tokens_uncached, cached_tokens, total_input_tokens, output_tokens_total, thinking_tokens
                ) VALUES (?, ?, 15, ?, '1417', 'Gemini 4 Argon (High)', 3, 10000, 120000, 130000, 1000, 400)
                """,
                ("convo-post", idx, f"2026-10-17T13:1{idx}:00Z"),
            )
        conn.commit()
        conn.close()

        res = evaluate_vault_quota_regime(
            vault_path=self.vault_path,
            ledger_path=self.ledger_path,
            persist=True,
        )
        self.assertEqual(res["coupling_ratio_5h_to_weekly"], 4.0)
        self.assertTrue(res["model_coverage"]["1417"]["verified"])
        self.assertEqual(res["model_coverage"]["1417"]["turns"], 7)
        for carbon_id in ("1427", "1437", "1438"):
            self.assertIn(carbon_id, res["model_coverage"])

        event_ids = [e["event_id"] for e in res["events"]]
        self.assertIn("reg-20261013-argon-launch", event_ids)
        self.assertIn("reg-20261017-bonus", event_ids)
        self.assertIn("reg-20261017-kv-discount", event_ids)

        # Test transition to PENDING_REVIEW then CLI --confirm and --dismiss
        updated_pending = update_regime_event_review_status(
            "reg-20261017-kv-discount",
            "PENDING_REVIEW",
            vault_path=self.vault_path,
            ledger_path=self.ledger_path,
        )
        self.assertIsNotNone(updated_pending)
        assert updated_pending is not None
        self.assertEqual(updated_pending["review_status"], "PENDING_REVIEW")

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = regression_main([
                "--confirm",
                "reg-20261017-kv-discount",
                "--vault-path",
                str(self.vault_path),
                "--regime-ledger",
                str(self.ledger_path),
            ])
        self.assertEqual(rc, 0)
        self.assertIn("transitioned to CONFIRMED", buf.getvalue())

        with open(self.ledger_path, "r", encoding="utf-8") as f:
            saved_ledger = json.load(f)
        by_id = {e["event_id"]: e for e in saved_ledger["events"]}
        self.assertEqual(by_id["reg-20261017-kv-discount"]["review_status"], "CONFIRMED")

    def test_cli_review_and_probe_prompts(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            rc = regression_main(["--probe-prompts"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("1427 (Gemini 4 Carbon High)", out)
        self.assertIn("1437 (Gemini 4 Carbon Medium)", out)
        self.assertIn("1438 (Gemini 4 Carbon Low)", out)
        self.assertIn("1418 (Gemini 4 Argon Medium)", out)
        self.assertIn("1417 (Gemini 4 Argon High)", out)

        prompts = generate_calibration_probe_prompts()
        self.assertEqual(len(prompts), 8)
        self.assertIn("1427 (Gemini 4 Carbon High)", prompts)
        self.assertIn("1437 (Gemini 4 Carbon Medium)", prompts)
        self.assertIn("1438 (Gemini 4 Carbon Low)", prompts)
        self.assertIn("1528 (Gemini 4 Hydrogen XHigh Isolated Phase 2)", prompts)
        self.assertIn("1526 (Gemini 4 Hydrogen Medium Phase 2)", prompts)
        self.assertIn("1667 / 1681 (Orchestrator Carbon vs Argon Phase 2 Real Multi-Step)", prompts)

        # Verify Gemini 4 Hydrogen (1525-1528) & Orchestrator Executor (1669) exact 1/6x quota weights,
        # plus Orchestrator Planners (1667/1681) 0.50x weights
        for hid in ("1525", "1526", "1527", "1528", "1669"):
            self.assertEqual(
                CALIBRATED_QUOTA_WEIGHTS_POST_OCT17[hid],
                {"prompt_uncached": 0.25, "prompt_cached": 0.0125, "candidate_output": 1.25},
            )
            self.assertEqual(
                PUBLIC_API_RATES[hid],
                {"prompt_uncached": 1.50, "prompt_cached": 0.075, "candidate_output": 7.50},
            )
        for oid in ("1667", "1681"):
            self.assertEqual(
                CALIBRATED_QUOTA_WEIGHTS_POST_OCT17[oid],
                {"prompt_uncached": 1.00, "prompt_cached": 0.05, "candidate_output": 5.00},
            )

        # Verify Phase 2 Connect-RPC intervals (#3623 -> #3638)
        # 563cc06e (1528 XHigh): $0.02993 vs $0.02993 obs
        self.assertAlmostEqual(
            compute_turn_quota_usd("1528", 69_001, 269_014, 7_452, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17),
            0.02993,
            places=5,
        )
        # 6db26ee8 (1525 High): $0.02432 pred vs $0.02431 obs 5h / $0.02432 wk (#3627 -> #3628)
        self.assertAlmostEqual(
            compute_turn_quota_usd("1525", 68_866, 268_387, 2_996, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17),
            0.02432,
            places=5,
        )
        # 09dcae19 (1526 Medium): $0.02341 pred vs $0.02341 obs 5h / $0.02342 wk (#3637 -> #3638)
        self.assertAlmostEqual(
            compute_turn_quota_usd("1526", 68_929, 268_632, 2_258, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17),
            0.02341,
            places=5,
        )
        # b16b2008 (1527 Low): $0.02196 pred vs $0.02196 obs (#3629 -> #3630)
        self.assertAlmostEqual(
            compute_turn_quota_usd("1527", 68_597, 267_231, 1_178, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17),
            0.02196,
            places=5,
        )
        # 82e45f58 (1667 n=2 + 1669 n=7): $0.07691 + $0.01864 = $0.09555 vs $0.09555 obs
        orch_c_usd = compute_turn_quota_usd("1667", 40_525, 27_686, 7_000, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17)
        orch_exec_c_usd = compute_turn_quota_usd("1669", 48_136, 188_808, 3_400, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17)
        self.assertAlmostEqual(orch_c_usd + orch_exec_c_usd, 0.09555, places=5)
        # 61cfa298 (1681 n=1 + 1669 n=6): $0.04850 vs $0.04849 obs
        orch_a_usd = compute_turn_quota_usd("1681", 27_674, 0, 1_101, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17)
        orch_exec_a_usd = compute_turn_quota_usd("1669", 42_672, 144_703, 2_272, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17)
        self.assertAlmostEqual(orch_a_usd + orch_exec_a_usd, 0.04850, places=5)

        # Verify unified Gemini 4 (Argon 1417-1419 & Carbon 1427/1437/1438) 7-decimal Connect-RPC calibration
        # ($1.00 / $0.050 / $5.00 = exact 0.5000x Intro API = $50.00 5h / $200.00 weekly)
        cost_1m_cached = compute_turn_quota_usd("1417", 0, 1_000_000, 0, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17)
        self.assertAlmostEqual(cost_1m_cached, 0.05, places=4)

        for gid in ("1417", "1418", "1419", "1427", "1437", "1438"):
            self.assertEqual(
                CALIBRATED_QUOTA_WEIGHTS_POST_OCT17[gid],
                {"prompt_uncached": 1.00, "prompt_cached": 0.05, "candidate_output": 5.00},
            )
        # Argon Med (#316->#317, 1418): 185,657 unc, 179,611 cac, 5,999 out -> 0.8985302% of $25 5h (obs 0.8985300%)
        argon_med_usd = compute_turn_quota_usd("1418", 185_657, 179_611, 5_999, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17)
        self.assertAlmostEqual((argon_med_usd / 25.0) * 100.0, 0.8985302, places=7)
        # Argon High (#2916->#2917, 1417): 38,018 unc, 1,102,494 cac, 8,975 out -> 0.5520708% of $25 5h (obs 0.5520700%)
        argon_high_usd = compute_turn_quota_usd("1417", 38_018, 1_102_494, 8_975, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17)
        self.assertAlmostEqual((argon_high_usd / 25.0) * 100.0, 0.5520708, places=7)
        # Carbon Low (#3443->#3444, 1438 7-turn staircase 5fd93ea4): 99,610 unc, 321,926 cac, 3,659 out -> 0.5360052% of $25 5h
        low_usd = compute_turn_quota_usd("1438", 99_610, 321_926, 3_659, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17)
        self.assertAlmostEqual((low_usd / 25.0) * 100.0, 0.5360052, places=6)
        # Carbon Med (#3444->#3445, 1437 1-turn 1e318cb4): 25,175 unc, 0 cac, 176 out -> 0.1042200% of $25 5h
        med_usd = compute_turn_quota_usd("1437", 25_175, 0, 176, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17)
        self.assertAlmostEqual((med_usd / 25.0) * 100.0, 0.1042200, places=7)

    def test_checkpoint_step_type_23_included_in_regime_drift(self) -> None:
        """Verify step_type = 23 (CHECKPOINT) quota burn is included in evaluate_vault_quota_regime while v_turns stays pure."""
        conn = sqlite3.connect(str(self.vault_path))
        cur = conn.cursor()
        snaps = [
            (1, "fp1", "2026-11-10T17:55:01Z", 1.0, 0.0, "2026-11-10T22:55:01Z", 1.0, 0.0, "2026-11-17T01:46:18Z"),
            (2, "fp2", "2026-11-10T18:08:55Z", 0.9571806, 4.28194, "2026-11-10T22:55:01Z", 0.98929515, 1.070485, "2026-11-17T01:46:18Z"),
        ]
        for sid, fp, ts, g5, g5u, g5r, gw, gwu, gwr in snaps:
            cur.execute(
                """
                INSERT INTO quota_snapshots_archive (
                    id, snapshot_fingerprint, timestamp_utc,
                    gemini_5h_remaining, gemini_5h_used_pct, gemini_5h_reset_utc,
                    gemini_weekly_remaining, gemini_weekly_used_pct, gemini_weekly_reset_utc,
                    active_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'SAFE_IN_QUOTA')
                """,
                (sid, fp, ts, g5, g5u, g5r, gw, gwu, gwr),
            )

        # Normal step_type=15 turn accounting for 4.0315344% of $25 5h ($1.0078836 quota USD: 900,000 unc, 157,672 cac, 20,000 out)
        cur.execute(
            """
            INSERT INTO steps_archive (
                convo_id, step_idx, step_type, timestamp, model_id, model_name, status,
                prompt_tokens_uncached, cached_tokens, total_input_tokens, output_tokens_total, thinking_tokens
            ) VALUES ('dd80500a', 426, 15, '2026-11-10T18:05:00Z', '1437', 'Gemini 4 Carbon (Medium)', 3, 900000, 157672, 1057672, 20000, 1500)
            """
        )
        # Compaction CHECKPOINT step_type=23 (dd80500a step=430): 6,788 unc, 253,825 cac, 8,625 out -> +0.2504170% 5h ($0.06260425 quota USD)
        cur.execute(
            """
            INSERT INTO steps_archive (
                convo_id, step_idx, step_type, timestamp, model_id, model_name, status,
                prompt_tokens_uncached, cached_tokens, total_input_tokens, output_tokens_total, thinking_tokens
            ) VALUES ('dd80500a', 430, 23, '2026-11-10T18:06:28Z', '1437', 'Gemini 4 Carbon (Medium)', 3, 6788, 253825, 260613, 8625, 3132)
            """
        )
        v_turns_count = cur.execute("SELECT COUNT(*) FROM v_turns WHERE convo_id = 'dd80500a'").fetchone()[0]
        conn.commit()
        conn.close()

        self.assertEqual(v_turns_count, 1)

        res = evaluate_vault_quota_regime(
            vault_path=self.vault_path,
            ledger_path=self.ledger_path,
            persist=False,
        )
        mc_1437 = res["model_coverage"]["1437"]
        self.assertEqual(mc_1437["turns"], 2)
        self.assertAlmostEqual(mc_1437["expected_5h_pct"], 4.282, places=3)
        self.assertAlmostEqual(res["drift_ratio"], 1.0, places=3)

    def test_multiple_early_reset_bonuses_preserve_oct17_regime_and_ledger_history(self) -> None:
        # Seed persisted drift event in ledger to verify historical CONFIRMED/PENDING_REVIEW merge
        seeded_ledger = {
            "active_regime_id": "regime-20261017-post-reset",
            "active_regime_since_utc": "2026-10-17T01:46:18Z",
            "events": [
                {
                    "event_id": "reg-20261113-drift",
                    "detected_at_utc": "2026-11-13T18:00:00Z",
                    "event_type": "BURN_RATE_SHIFT (DISCOUNT_PROMO)",
                    "review_status": "PENDING_REVIEW",
                    "confirmed_at_utc": None,
                    "snapshot_range": "#5 -> #6",
                    "turns_analyzed": 10,
                    "delta_5h_pct": 5.0,
                    "delta_weekly_pct": 1.25,
                    "drift_ratio": 0.65,
                    "coupling_ratio": 4.0,
                    "solved_5h_api_usd": 70.0,
                    "solved_weekly_api_usd": 280.0,
                    "summary": "Seeded historical drift event",
                    "prev_baseline": {},
                    "observed_metrics": {},
                    "model_breakdown": {},
                }
            ],
        }
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            json.dump(seeded_ledger, f, indent=2)

        conn = sqlite3.connect(str(self.vault_path))
        cur = conn.cursor()
        snaps = [
            (1, "fp1", "2026-10-16T12:00:00Z", 1.0, 0.0, "2026-10-16T17:00:00Z", 0.30, 70.0, "2026-10-20T15:36:14Z"),
            (2, "fp2", "2026-10-16T13:00:00Z", 0.96, 4.0, "2026-10-16T17:00:00Z", 0.29, 71.0, "2026-10-20T15:36:14Z"),
            (3, "fp3", "2026-10-17T01:46:18Z", 1.0, 0.0, "2026-10-17T06:46:18Z", 1.0, 0.0, "2026-10-24T01:46:18Z"),
            (4, "fp4", "2026-10-17T13:18:00Z", 0.992, 0.8, "2026-10-17T18:18:00Z", 0.998, 0.2, "2026-10-24T01:46:18Z"),
            (5, "fp5", "2026-11-13T21:12:30Z", 0.798, 20.2, "2026-11-14T02:12:30Z", 0.072, 92.8, "2026-11-14T09:00:28Z"),
            (6, "fp6", "2026-11-14T02:10:20Z", 1.0, 0.0, "2026-11-14T07:10:20Z", 1.0, 0.0, "2026-11-21T01:17:32Z"),
            (7, "fp7", "2026-11-14T04:00:00Z", 0.98, 2.0, "2026-11-14T09:00:00Z", 0.995, 0.5, "2026-11-21T01:17:32Z"),
        ]
        for sid, fp, ts, g5, g5u, g5r, gw, gwu, gwr in snaps:
            cur.execute(
                """
                INSERT INTO quota_snapshots_archive (
                    id, snapshot_fingerprint, timestamp_utc,
                    gemini_5h_remaining, gemini_5h_used_pct, gemini_5h_reset_utc,
                    gemini_weekly_remaining, gemini_weekly_used_pct, gemini_weekly_reset_utc,
                    active_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'SAFE_IN_QUOTA')
                """,
                (sid, fp, ts, g5, g5u, g5r, gw, gwu, gwr),
            )

        # Pre-Oct-17 turns
        cur.execute(
            """
            INSERT INTO steps_archive (
                convo_id, step_idx, step_type, timestamp, model_id, model_name, status,
                prompt_tokens_uncached, cached_tokens, total_input_tokens, output_tokens_total, thinking_tokens
            ) VALUES ('c-pre', 1, 15, '2026-10-16T12:15:00Z', '1419', 'Gemini 4 Argon (Low)', 3, 20000, 100000, 120000, 2000, 500)
            """
        )
        # Oct-17 interval turns
        for idx in range(1, 8):
            cur.execute(
                """
                INSERT INTO steps_archive (
                    convo_id, step_idx, step_type, timestamp, model_id, model_name, status,
                    prompt_tokens_uncached, cached_tokens, total_input_tokens, output_tokens_total, thinking_tokens
                ) VALUES (?, ?, 15, ?, '1417', 'Gemini 4 Argon (High)', 3, 10000, 120000, 130000, 1000, 400)
                """,
                ("c-post-oct", idx, f"2026-10-17T13:1{idx}:00Z"),
            )
        # Nov 7-Nov 14 cycle turns (strictly inside Nov 7 09:00:28Z .. Nov 14 02:10:20Z)
        for idx in (1, 2):
            cur.execute(
                """
                INSERT INTO steps_archive (
                    convo_id, step_idx, step_type, timestamp, model_id, model_name, status,
                    prompt_tokens_uncached, cached_tokens, total_input_tokens, output_tokens_total, thinking_tokens
                ) VALUES (?, ?, 15, ?, '1427', 'Gemini 4 Carbon (High)', 3, 15000, 100000, 115000, 1500, 300)
                """,
                ("c-nov-cycle", idx, f"2026-11-10T10:0{idx}:00Z"),
            )
        conn.commit()
        conn.close()

        res = evaluate_vault_quota_regime(
            vault_path=self.vault_path,
            ledger_path=self.ledger_path,
            persist=True,
        )
        # Oct 17 partition anchor must stay anchored on the initial KV-discount regime boundary
        self.assertEqual(res["active_regime_since_utc"], "2026-10-17T01:46:18Z")
        self.assertEqual(res["latest_reset_bonus_utc"], "2026-11-14T02:10:20Z")
        self.assertTrue(res["model_coverage"]["1417"]["verified"])
        self.assertGreaterEqual(res["model_coverage"]["1417"]["turns"], 7)

        events_by_id = {e["event_id"]: e for e in res["events"]}
        self.assertIn("reg-20261013-argon-launch", events_by_id)
        self.assertIn("reg-20261017-bonus", events_by_id)
        self.assertIn("reg-20261017-kv-discount", events_by_id)
        self.assertIn("reg-20261114-bonus", events_by_id)
        self.assertIn("reg-20261113-drift", events_by_id)

        # Nov 14 bonus turns_analyzed must be scoped strictly to the Nov 7-Nov 14 cycle (2 turns)
        self.assertEqual(events_by_id["reg-20261114-bonus"]["turns_analyzed"], 2)
        self.assertEqual(events_by_id["reg-20261113-drift"]["review_status"], "PENDING_REVIEW")


if __name__ == "__main__":
    unittest.main()
