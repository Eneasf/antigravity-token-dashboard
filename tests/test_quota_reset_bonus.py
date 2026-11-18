"""
Unit tests for unscheduled quota reset bonus ledger reconciliation (Gate B15).
Verifies that QUOTA_RESET_BONUS events in exhaustion_ledger.json:
1. Are preserved by extract_exhaustion_intervals with full bonus metadata.
2. Surface in hourly_credit_activity without altering total_ai_credits_burned or bank_credits_rem.
3. Do not falsely trigger BURNING_AI_CREDITS or mark turns as overage.
4. Are cleanly summarized by scripts/quota_history.py.
"""

import datetime
import json
from pathlib import Path
import tempfile
import unittest

from scripts.quota_history import build_audit_report
from src.aggregator_attribution import extract_project_branch_attribution
from src.aggregator_quotas import reconcile_credit_burn_and_overage
from src.aggregator_windows import aggregate_conversation_telemetry
from src.log_reader import extract_exhaustion_intervals
from src.temporal import load_raw_pricing


class TestQuotaResetBonus(unittest.TestCase):
    def setUp(self) -> None:
        self.pricing = load_raw_pricing()

    def test_live_exhaustion_ledger_contains_oct17_bonus_reset(self) -> None:
        """Verify data/exhaustion_ledger.json records exc-20261017-01 without altering cumulative credit burn."""
        ledger_path = Path("data/exhaustion_ledger.json")
        if not ledger_path.exists():
            self.skipTest("data/exhaustion_ledger.json not present in sandbox")

        data = json.loads(ledger_path.read_text(encoding="utf-8"))
        incidents = data.get("incidents", [])
        bonus_events = [
            inc for inc in incidents
            if inc.get("incident_id") == "exc-20261017-01"
        ]
        self.assertEqual(len(bonus_events), 1)
        bonus = bonus_events[0]
        self.assertEqual(bonus.get("event_type"), "QUOTA_RESET_BONUS")
        self.assertEqual(bonus.get("reason"), "QUOTA_RESET_BONUS")
        self.assertEqual(bonus.get("credits_burned"), 0)
        self.assertEqual(bonus.get("credit_burn_usd"), 0.0)
        self.assertEqual(bonus.get("credit_burn_gbp"), 0.0)
        self.assertEqual(bonus.get("bonus_pct_forgiven"), 75.4)
        self.assertEqual(bonus.get("bonus_credits_forgiven"), 7540)
        self.assertEqual(bonus.get("bonus_value_usd"), 75.4)
        self.assertEqual(bonus.get("bonus_value_gbp"), 59.57)

        # Total debited credits across all incidents must equal 5,150 (2,350 remaining of 7,500)
        total_burned = sum(inc.get("credits_burned", 0) for inc in incidents)
        self.assertEqual(total_burned, 5150)

    def test_reconcile_credit_burn_preserves_bonus_without_debiting_balance(self) -> None:
        """Verify reconcile_credit_burn_and_overage surfaces QUOTA_RESET_BONUS with 0 credit burn."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_file = Path(tmpdir) / "exhaustion_ledger.json"
            sample_ledger = {
                "version": 1,
                "prepaid_pack": {
                    "pack_size": 2500,
                    "packs_purchased": 2,
                    "total_credits": 5000,
                    "auto_reload": True,
                },
                "incidents": [
                    {
                        "incident_id": "exc-20261014-11",
                        "hour_timestamp": "2026-10-14T11:00:00Z",
                        "hour_display": "14 Oct 2026, 11:00:00 BST",
                        "start_utc": "2026-10-14T10:00:00+00:00",
                        "end_utc": "2026-10-14T11:00:00+00:00",
                        "turns_count": 30,
                        "credits_burned": 120,
                        "credit_burn_usd": 1.20,
                        "credit_burn_gbp": 1.15,
                        "code": 429,
                        "reason": "RESOURCE_EXHAUSTED",
                        "models": {"Gemini 4 Argon (High)": 30},
                    },
                    {
                        "incident_id": "exc-20261017-01",
                        "hour_timestamp": "2026-10-17T01:00:00Z",
                        "hour_display": "17 Oct 2026, 01:46:18 UTC",
                        "start_utc": "2026-10-17T01:46:18+00:00",
                        "end_utc": "2026-10-17T01:46:18+00:00",
                        "turns_count": 4631,
                        "credits_burned": 0,
                        "credit_burn_usd": 0.0,
                        "credit_burn_gbp": 0.0,
                        "bonus_pct_forgiven": 75.4,
                        "bonus_credits_forgiven": 7540,
                        "bonus_value_usd": 75.40,
                        "bonus_value_gbp": 59.57,
                        "code": 200,
                        "event_type": "QUOTA_RESET_BONUS",
                        "reason": "QUOTA_RESET_BONUS",
                        "description": "Unscheduled Google backend weekly quota reset",
                        "models": {"Gemini Fast Agent Assistant": 2448},
                    },
                ],
            }
            ledger_file.write_text(json.dumps(sample_ledger), encoding="utf-8")

            empty_log = Path(tmpdir) / "empty.log"
            empty_log.write_text("", encoding="utf-8")

            intervals = extract_exhaustion_intervals(log_path=empty_log, ledger_path=ledger_file)
            self.assertEqual(len(intervals), 2)

            # Reference time right at the bonus timestamp should NOT trigger BURNING_AI_CREDITS
            ref_dt = datetime.datetime(2026, 10, 17, 1, 46, 18, tzinfo=datetime.timezone.utc)
            recon = reconcile_credit_burn_and_overage(
                flat_turns=[],
                exhaustion_intervals=intervals,
                pricing_models=self.pricing,
                sub_cfg=self.pricing.get("subscription", {}),
                ref_dt=ref_dt,
                rolling_5h={"total_processed_tokens": 0},
                burst_limit=840000000,
            )

            self.assertEqual(recon["bank_credits_burned"], 120)
            self.assertEqual(recon["bank_credits_rem"], 4880)
            self.assertEqual(recon["subscription_status"], "SAFE_IN_QUOTA")

            activity = recon["hourly_credit_activity"]
            self.assertEqual(len(activity), 2)
            bonus_row = activity[0]
            self.assertEqual(bonus_row["event_type"], "QUOTA_RESET_BONUS")
            self.assertEqual(bonus_row["reason"], "QUOTA_RESET_BONUS")
            self.assertEqual(bonus_row["credits_burned"], 0)
            self.assertEqual(bonus_row["bonus_pct_forgiven"], 75.4)
            self.assertEqual(bonus_row["bonus_credits_forgiven"], 7540)
            self.assertEqual(bonus_row["bonus_value_usd"], 75.40)
            self.assertEqual(bonus_row["bonus_value_gbp"], 59.57)

            # Verify turns at 01:46:18 UTC are not marked as overage
            sample_turns = [
                {
                    "step_idx": 1,
                    "timestamp": "2026-10-17T01:46:18+00:00",
                    "model_id": "1322",
                    "prompt_tokens_uncached": 1000,
                    "cached_tokens": 5000,
                    "output_tokens_total": 200,
                }
            ]
            conv_summary = aggregate_conversation_telemetry(
                {"convo_id": "test-1", "title": "Test", "workspace": "test"},
                sample_turns,
                self.pricing,
                exhaustion_intervals=intervals,
            )
            self.assertEqual(conv_summary["overage_turns"], 0)
            self.assertEqual(conv_summary["subscription_covered_turns"], 1)

            projects = extract_project_branch_attribution(
                [conv_summary], self.pricing, exhaustion_intervals=intervals
            )
            self.assertEqual(projects[0]["overage_turns"], 0)

            # Verify quota_history audit report separates deductions from bonus resets
            report = build_audit_report(Path(tmpdir) / "nonexistent.db", ledger_file)
            self.assertEqual(report["summary"]["macro_incidents_count"], 1)
            self.assertEqual(report["summary"]["bonus_resets_count"], 1)
            self.assertEqual(report["summary"]["total_credits_burned"], 120)
            self.assertEqual(report["summary"]["total_bonus_credits_forgiven"], 7540)


if __name__ == "__main__":
    unittest.main()
