"""Unit tests for src/quota_client.py and live desktop quota synchronization."""

import datetime
import json
import unittest
from unittest.mock import patch, MagicMock

from src.quota_client import fetch_live_quota_summary, discover_language_server_credentials
from src.aggregator import aggregate_global_telemetry, aggregate_conversation_telemetry


class TestQuotaClient(unittest.TestCase):

    def setUp(self):
        self.mock_quota_response = {
            "response": {
                "groups": [
                    {
                        "displayName": "Gemini Models",
                        "description": "Models within this group: Gemini Flash, Gemini Pro",
                        "buckets": [
                            {
                                "bucketId": "gemini-weekly",
                                "displayName": "Weekly Limit Remaining",
                                "description": "You have used some of your weekly limit, it will fully refresh in 4 days, 6 hours.",
                                "window": "weekly",
                                "remainingFraction": 0.3240786,
                                "resetTime": "2026-09-10T18:26:24Z",
                            },
                            {
                                "bucketId": "gemini-5h",
                                "displayName": "Five Hour Limit Remaining",
                                "description": "You have used some of your 5-hour limit, it will fully refresh in 2 hours, 31 minutes.",
                                "window": "5h",
                                "remainingFraction": 0.2723328,
                                "resetTime": "2026-09-06T14:13:55Z",
                            },
                        ],
                    },
                    {
                        "displayName": "Claude and GPT models",
                        "description": "Models within this group: Claude Opus, Claude Sonnet, GPT-OSS",
                        "buckets": [
                            {
                                "bucketId": "3p-weekly",
                                "displayName": "Weekly Limit Remaining",
                                "description": "You have used some of your weekly limit, it will fully refresh in 6 days, 1 hour.",
                                "window": "weekly",
                                "remainingFraction": 0.9468391,
                                "resetTime": "2026-09-12T13:20:50Z",
                            },
                            {
                                "bucketId": "3p-5h",
                                "displayName": "Five Hour Limit Remaining",
                                "window": "5h",
                                "remainingFraction": 1.0,
                                "resetTime": "2026-09-06T16:42:46Z",
                            },
                        ],
                    },
                ],
                "description": "Within each group, models share a weekly limit and a 5-hour limit. Quota is consumed proportionally to the cost of the tokens.",
            }
        }

        self.pricing_models = {
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
        }

    @patch("urllib.request.urlopen")
    def test_fetch_live_quota_summary_parses_buckets(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(self.mock_quota_response).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        creds = {"pid": 1234, "csrf_token": "dummy-token", "port": 58000}
        res = fetch_live_quota_summary(credentials=creds)

        self.assertIsNotNone(res)
        self.assertTrue(res["available"])
        self.assertIn("gemini_weekly", res)
        self.assertIn("gemini_5h", res)
        self.assertIn("claude_weekly", res)
        self.assertIn("claude_5h", res)

        gw = res["gemini_weekly"]
        self.assertEqual(gw["remaining_pct"], 32.4)
        self.assertEqual(gw["used_pct"], 67.6)
        self.assertEqual(gw["reset_time"], "2026-09-10T18:26:24Z")

        g5 = res["gemini_5h"]
        self.assertEqual(g5["remaining_pct"], 27.2)
        self.assertEqual(g5["used_pct"], 72.8)

        cw = res["claude_weekly"]
        self.assertEqual(cw["remaining_pct"], 94.7)

        c5 = res["claude_5h"]
        self.assertEqual(c5["remaining_pct"], 100.0)

    @patch("subprocess.run")
    def test_discover_credentials_handles_offline(self, mock_run):
        mock_run.return_value.stdout = "pid command\n100 /usr/bin/bash\n"
        creds = discover_language_server_credentials()
        self.assertIsNone(creds)

    def test_aggregator_live_desktop_sync_integration(self):
        ref_time = datetime.datetime(2026, 9, 6, 11, 43, 0, tzinfo=datetime.timezone.utc)
        meta = {"convo_id": "c1", "title": "Test Convo", "workspace": "repo-test"}
        turns = [
            {
                "step_idx": 1,
                "timestamp": (ref_time - datetime.timedelta(hours=1)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 1000000,
                "cached_tokens": 10000000,
                "total_input_tokens": 11000000,
                "output_tokens_total": 50000,
                "thinking_tokens": 40000,
                "answer_tokens": 10000,
            }
        ]
        conv_summary = aggregate_conversation_telemetry(meta, turns, self.pricing_models)

        # Mock parsed live quota
        parsed_live_quota = {
            "available": True,
            "description": "Within each group, models share a weekly limit.",
            "gemini_weekly": {
                "remaining_pct": 32.4,
                "used_pct": 67.6,
                "reset_time": "2026-09-10T18:26:24Z",
                "description": "It will fully refresh in 4 days, 6 hours",
            },
            "gemini_5h": {
                "remaining_pct": 27.2,
                "used_pct": 72.8,
                "reset_time": "2026-09-06T14:13:55Z",
                "description": "It will fully refresh in 2 hours, 31 minutes",
            },
        }

        res = aggregate_global_telemetry(
            [conv_summary],
            self.pricing_models,
            reference_time=ref_time,
            live_quota=parsed_live_quota,
        )

        q = res["quotas"]["providers"]
        self.assertTrue(q["desktop_sync"]["active"])
        self.assertEqual(q["gemini"]["weekly"]["remaining_pct"], 32.4)
        self.assertEqual(q["gemini"]["weekly"]["used_pct"], 67.6)
        self.assertTrue(q["gemini"]["weekly"].get("live_desktop_sync"))
        self.assertEqual(q["gemini"]["five_hour"]["remaining_pct"], 27.2)
        self.assertEqual(q["gemini"]["five_hour"]["used_pct"], 72.8)
        self.assertTrue(q["gemini"]["five_hour"].get("live_desktop_sync"))

    def test_aggregator_cost_weighted_offline_fallback(self):
        ref_time = datetime.datetime(2026, 9, 6, 11, 43, 0, tzinfo=datetime.timezone.utc)
        meta = {"convo_id": "c1", "title": "Test Convo", "workspace": "repo-test"}
        # 1M uncached ($0.75) + 10M cached ($0.75) + 100k out ($0.375) = $1.875 total cost
        turns = [
            {
                "step_idx": 1,
                "timestamp": (ref_time - datetime.timedelta(hours=1)).isoformat(),
                "model_id": "1318",
                "prompt_tokens_uncached": 1000000,
                "cached_tokens": 10000000,
                "total_input_tokens": 11000000,
                "output_tokens_total": 100000,
                "thinking_tokens": 80000,
                "answer_tokens": 20000,
            }
        ]
        conv_summary = aggregate_conversation_telemetry(meta, turns, self.pricing_models)

        res = aggregate_global_telemetry(
            [conv_summary],
            self.pricing_models,
            reference_time=ref_time,
            live_quota=None,
        )

        q = res["quotas"]["providers"]
        self.assertFalse(q["desktop_sync"]["active"])
        self.assertEqual(q["gemini"]["five_hour"]["capacity_usd"], 20.00)
        self.assertEqual(q["gemini"]["weekly"]["capacity_usd"], 129.00)
        # Cost is $1.875 -> 5h used_pct = (1.875 / 20.00) * 100 = 9.4%
        self.assertEqual(q["gemini"]["five_hour"]["used_pct"], 9.4)
        self.assertEqual(q["gemini"]["five_hour"]["remaining_pct"], 90.6)
        # Weekly used_pct = (1.875 / 129.00) * 100 = 1.5%
        self.assertEqual(q["gemini"]["weekly"]["used_pct"], 1.5)
        self.assertEqual(q["gemini"]["weekly"]["remaining_pct"], 98.5)


if __name__ == "__main__":
    unittest.main()
