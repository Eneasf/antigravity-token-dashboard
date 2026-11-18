#!/usr/bin/env python3
"""
Unit tests for executive quota status hook schema enrichment.
"""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.export_dashboard import build_or_patch_status_tracks, write_quota_status_file
from scripts.agy_status import get_status_data, format_status_summary, format_status_short, format_status_verbose


class TestQuotaStatusEnrichment(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.status_file = Path(self.temp_dir.name) / "test_status.json"

        # Realistic mock payload
        self.mock_payload = {
            "summary": {
                "subscription_status": "SAFE_IN_QUOTA",
                "tier": "ultra_5x",
                "subscription_tier_name": "Google AI Ultra (5x)",
                "total_ai_credits_burned": 3640,
                "monthly_plan_credits": 5000,
                "monthly_credits_remaining": 1360,
                "credit_bank_remaining_gbp": 13.05,
            },
            "quotas": {
                "providers": {
                    "gemini": {
                        "five_hour": {
                            "used_pct": 8.5,
                            "recovery_schedule": [
                                {"minutes_remaining": 15, "tokens_to_recover": 50000},
                                {"minutes_remaining": 75, "tokens_to_recover": 120000},
                            ],
                        },
                        "weekly": {
                            "used_pct": 14.2,
                            "weekly_reset_utc": "2026-09-20T17:58:04+00:00",
                            "human_remaining": "4 days, 19 hours",
                            "reset_day_name": "Sunday",
                            "reset_time_utc": "17:58:04 UTC",
                        },
                        "runway": {
                            "bvi_bayes": 0.65,
                            "status_sub": "Day 3: +28.7% buffer (14.2% vs 42.9%)",
                            "burst_cooldown_active": False,
                        },
                    },
                    "claude_gpt": {
                        "five_hour": {"used_pct": 0.0},
                        "weekly": {"used_pct": 0.0},
                    },
                },
            },
            "conversations": [
                {
                    "workspace_name": "Test Project Alpha",
                    "git_branch": "feat/test-branch",
                }
            ],
            "temporal": {
                "evaluation_time_utc": "2026-09-15T22:00:00+00:00",
            },
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_enriched_schema_completeness(self):
        written = write_quota_status_file(self.mock_payload, status_path=self.status_file)
        self.assertIsNotNone(written)
        self.assertTrue(self.status_file.exists())

        data = json.loads(self.status_file.read_text(encoding="utf-8"))

        # Preserved backward-compatible fields
        self.assertEqual(data["status"], "SAFE_IN_QUOTA")
        self.assertEqual(data["gemini_5h_pct"], 8.5)
        self.assertEqual(data["gemini_weekly_pct"], 14.2)
        self.assertEqual(data["claude_5h_pct"], 0.0)
        self.assertEqual(data["claude_weekly_pct"], 0.0)
        self.assertFalse(data["cooldown_active"])
        self.assertEqual(data["weekly_reset_utc"], "2026-09-20T17:58:04+00:00")

        # Enriched headroom percentages
        self.assertEqual(data["gemini_5h_remaining_pct"], 91.5)
        self.assertEqual(data["gemini_weekly_remaining_pct"], 85.8)
        self.assertEqual(data["claude_5h_remaining_pct"], 100.0)
        self.assertEqual(data["claude_weekly_remaining_pct"], 100.0)

        # Enriched metadata strings
        self.assertIn("Next roll-off in 15m", data["gemini_5h_recovery_desc"])
        self.assertIn("Sunday 17:58:04 UTC", data["weekly_reset_desc"])
        self.assertEqual(data["bvi"], 0.65)
        self.assertIn("+28.7% buffer", data["bvi_verdict"])
        self.assertEqual(data["plan_name"], "Google AI Ultra (5x)")
        self.assertEqual(data["active_project"], "Test Project Alpha")
        self.assertEqual(data["active_branch"], "feat/test-branch")
        self.assertIn("1,360 / 5,000 credits", data["credit_balance"])
        self.assertTrue(data["dashboard_path"].endswith("dashboard/index.html"))

    def test_agy_status_integration(self):
        write_quota_status_file(self.mock_payload, status_path=self.status_file)
        data = get_status_data(self.status_file)

        summary = format_status_summary(data)
        self.assertIn("Gemini 5h: 91.5% rem", summary)
        self.assertIn("1w: 85.8% rem", summary)

        short = format_status_short(data)
        self.assertIn("G:92%/86%", short)

        verbose = format_status_verbose(data)
        self.assertIn("Google AI Ultra (5x)", verbose)
        self.assertIn("91.5% headroom", verbose)
        self.assertIn("Test Project Alpha", verbose)

    def test_current_session_and_branch_attribution(self):
        # Payload with degraded and current conversations
        import datetime
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        payload = dict(self.mock_payload)
        payload["conversations"] = [
            {
                "convo_id": "current-convo-001",
                "title": "Current Active Work",
                "workspace_name": "Workspace Main",
                "git_branch": "feat/active-branch",
                "last_turn_ts": now_dt.isoformat(),
                "turns": [{"total_input_tokens": 71000}],
            },
            {
                "convo_id": "degraded-convo-002",
                "title": "Old Heavy Run",
                "workspace_name": "Workspace Other",
                "git_branch": "feat/old-branch",
                "last_turn_ts": (now_dt - datetime.timedelta(hours=2)).isoformat(),
                "turns": [{"total_input_tokens": 215000}],
            },
            {
                "convo_id": "warning-convo-003",
                "title": "Warning Run",
                "workspace_name": "Workspace Main",
                "git_branch": "feat/warning-branch",
                "last_turn_ts": (now_dt - datetime.timedelta(hours=4)).isoformat(),
                "turns": [{"total_input_tokens": 175000}],
            },
        ]
        write_quota_status_file(payload, status_path=self.status_file)
        data = json.loads(self.status_file.read_text(encoding="utf-8"))

        self.assertIn("current_session", data)
        curr = data["current_session"]
        self.assertEqual(curr["title"], "Current Active Work")
        self.assertEqual(curr["branch"], "feat/active-branch")
        self.assertEqual(curr["workspace"], "Workspace Main")
        self.assertEqual(curr["tokens"], 71000)
        self.assertEqual(curr["severity"], "safe")
        self.assertEqual(curr["headroom_to_warning"], 79000)
        self.assertTrue(curr["is_current"])

        # Check degraded sessions
        degraded = data.get("degraded_sessions", [])
        self.assertEqual(len(degraded), 2)
        # First should be the 215k critical
        self.assertEqual(degraded[0]["tokens"], 215000)
        self.assertEqual(degraded[0]["severity"], "critical")
        self.assertEqual(degraded[0]["branch"], "feat/old-branch")
        self.assertEqual(degraded[0]["workspace"], "Workspace Other")
        self.assertFalse(degraded[0]["is_current"])

        # Second should be the 175k warning
        self.assertEqual(degraded[1]["tokens"], 175000)
        self.assertEqual(degraded[1]["severity"], "warning")
        self.assertEqual(degraded[1]["branch"], "feat/warning-branch")
        self.assertEqual(degraded[1]["workspace"], "Workspace Main")
        self.assertFalse(degraded[1]["is_current"])

    def test_write_quota_status_preserves_existing_watcher_dict(self):
        """Verify write_quota_status_file preserves existing 'watcher' dictionary in target file."""
        initial_watcher = {
            "pid": 4567,
            "heartbeat_utc": "2026-09-20T16:45:00+00:00",
        }
        initial_status = {
            "status": "OLD_STATUS",
            "watcher": initial_watcher,
        }
        self.status_file.write_text(json.dumps(initial_status, indent=2), encoding="utf-8")

        written = write_quota_status_file(self.mock_payload, status_path=self.status_file)
        self.assertIsNotNone(written)
        self.assertTrue(self.status_file.exists())

        data = json.loads(self.status_file.read_text(encoding="utf-8"))
        self.assertIn("watcher", data)
        self.assertEqual(data["watcher"], initial_watcher)
        self.assertEqual(data["status"], "SAFE_IN_QUOTA")
        self.assertEqual(data["gemini_5h_pct"], 8.5)

    def test_write_quota_status_accepts_and_serializes_watcher_info(self):
        """Verify write_quota_status_file accepts and serializes watcher_info when provided."""
        watcher_info = {
            "pid": 7890,
            "heartbeat_utc": "2026-09-20T17:00:00+00:00",
        }
        written = write_quota_status_file(
            self.mock_payload,
            status_path=self.status_file,
            watcher_info=watcher_info,
        )
        self.assertIsNotNone(written)
        self.assertTrue(self.status_file.exists())

        data = json.loads(self.status_file.read_text(encoding="utf-8"))
        self.assertIn("watcher", data)
        self.assertEqual(data["watcher"], watcher_info)

    def test_day1_buffer_bvi_above_one_stays_sustainable_across_full_and_fast_tier(self):
        """Day-1 buffer clamp keeps bvi_status='sustainable' when bvi=1.01, across full and fast-tier updates."""
        import copy

        payload = copy.deepcopy(self.mock_payload)
        gem = payload["quotas"]["providers"]["gemini"]
        gem["weekly"]["used_pct"] = 0.2
        gem["runway"] = {
            "bvi_bayes": 1.01,
            "status_key": "green",
            "status_sub": "Day 1: +14.1% buffer (0.2% vs 14.3%)",
            "calendar_time_elapsed_pct": 0.1,
            "burst_cooldown_active": False,
        }

        write_quota_status_file(payload, status_path=self.status_file)
        data = json.loads(self.status_file.read_text(encoding="utf-8"))
        gem_track = next(t for t in data["tracks"] if t["id"] == "gemini")
        wk_win = next(w for w in gem_track["windows"] if w["window_id"] == "weekly")
        self.assertEqual(wk_win["bvi_status"], "sustainable")

        # Fast-tier patch (payload=None) must preserve sustainable status instead of reverting to 'deficit'
        build_or_patch_status_tracks(data)
        gem_track_fast = next(t for t in data["tracks"] if t["id"] == "gemini")
        wk_win_fast = next(w for w in gem_track_fast["windows"] if w["window_id"] == "weekly")
        self.assertEqual(wk_win_fast["bvi_status"], "sustainable")

    def test_real_midcycle_deficit_and_overburn_preserved(self):
        """Real amber/red runway verdicts still emit 'deficit' and 'overburn' bvi_status."""
        import copy

        amber_payload = copy.deepcopy(self.mock_payload)
        amber_payload["quotas"]["providers"]["gemini"]["weekly"]["used_pct"] = 72.0
        amber_payload["quotas"]["providers"]["gemini"]["runway"] = {
            "bvi_bayes": 1.19,
            "status_key": "amber",
            "status_sub": "Day 5: -0.5% deficit (72.0% vs 71.5%)",
            "burst_cooldown_active": False,
        }
        write_quota_status_file(amber_payload, status_path=self.status_file)
        amber_data = json.loads(self.status_file.read_text(encoding="utf-8"))
        amber_wk = next(
            w
            for t in amber_data["tracks"]
            if t["id"] == "gemini"
            for w in t["windows"]
            if w["window_id"] == "weekly"
        )
        self.assertEqual(amber_wk["bvi_status"], "deficit")

        red_payload = copy.deepcopy(self.mock_payload)
        red_payload["quotas"]["providers"]["gemini"]["weekly"]["used_pct"] = 88.0
        red_payload["quotas"]["providers"]["gemini"]["runway"] = {
            "bvi_bayes": 1.41,
            "status_key": "red",
            "status_sub": "Day 5: -16.5% deficit (88.0% vs 71.5%)",
            "burst_cooldown_active": False,
        }
        write_quota_status_file(red_payload, status_path=self.status_file)
        red_data = json.loads(self.status_file.read_text(encoding="utf-8"))
        red_wk = next(
            w
            for t in red_data["tracks"]
            if t["id"] == "gemini"
            for w in t["windows"]
            if w["window_id"] == "weekly"
        )
        self.assertEqual(red_wk["bvi_status"], "overburn")


if __name__ == "__main__":
    unittest.main()
