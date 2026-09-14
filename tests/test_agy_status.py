#!/usr/bin/env python3
"""
Unit tests for executive quota status hook and agy_status CLI (Phase 3).
"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.agy_status import (
    format_status_short,
    format_status_summary,
    get_status_data,
)
from scripts.export_dashboard import write_quota_status_file


class TestAgyStatus(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.status_file = Path(self.temp_dir.name) / "status.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_write_quota_status_file_atomicity_and_schema(self):
        mock_payload = {
            "summary": {
                "subscription_status": "SAFE_IN_QUOTA",
            },
            "quotas": {
                "providers": {
                    "gemini": {
                        "five_hour": {"used_pct": 30.2},
                        "weekly": {
                            "used_pct": 40.3,
                            "weekly_reset_utc": "2026-09-17T18:00:00Z",
                        },
                        "runway": {"burst_cooldown_active": False},
                    },
                    "claude_gpt": {
                        "five_hour": {"used_pct": 0.0},
                        "weekly": {"used_pct": 0.0},
                    },
                }
            },
            "temporal": {
                "evaluation_time_utc": "2026-09-12T22:30:00Z",
            },
        }

        res_path = write_quota_status_file(mock_payload, status_path=self.status_file)
        self.assertEqual(res_path, self.status_file)
        self.assertTrue(self.status_file.exists())

        data = json.loads(self.status_file.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "SAFE_IN_QUOTA")
        self.assertEqual(data["gemini_5h_pct"], 30.2)
        self.assertEqual(data["gemini_weekly_pct"], 40.3)
        self.assertEqual(data["claude_5h_pct"], 0.0)
        self.assertEqual(data["claude_weekly_pct"], 0.0)
        self.assertFalse(data["cooldown_active"])
        self.assertEqual(data["weekly_reset_utc"], "2026-09-17T18:00:00Z")
        self.assertEqual(data["updated_at"], "2026-09-12T22:30:00Z")

    def test_format_status_summary(self):
        data = {
            "status": "SAFE_IN_QUOTA",
            "gemini_5h_pct": 30.2,
            "gemini_weekly_pct": 40.3,
            "claude_5h_pct": 0.0,
            "claude_weekly_pct": 0.0,
            "cooldown_active": False,
        }
        summary = format_status_summary(data)
        self.assertIn("Gemini 5h: 69.8% rem", summary)
        self.assertIn("1w: 59.7% rem", summary)
        self.assertIn("Claude: 100%", summary)
        self.assertIn("Status: SAFE", summary)

    def test_format_status_short(self):
        data = {
            "status": "SAFE_IN_QUOTA",
            "gemini_5h_pct": 30.2,
            "gemini_weekly_pct": 40.3,
            "claude_5h_pct": 0.0,
            "claude_weekly_pct": 0.0,
            "cooldown_active": False,
        }
        short = format_status_short(data)
        self.assertEqual(short, "AGY: G:70%/60% C:100% (SAFE)")

    def test_format_cooldown_and_exhaustion(self):
        cooldown_data = {
            "status": "COOLDOWN",
            "gemini_5h_pct": 100.0,
            "gemini_weekly_pct": 80.0,
            "claude_weekly_pct": 10.0,
            "cooldown_active": True,
        }
        summary = format_status_summary(cooldown_data)
        self.assertIn("COOLDOWN", summary)
        short = format_status_short(cooldown_data)
        self.assertIn("COOL", short)

        exhausted_data = {
            "status": "EXHAUSTED",
            "gemini_5h_pct": 100.0,
            "gemini_weekly_pct": 100.0,
            "claude_weekly_pct": 0.0,
            "cooldown_active": False,
        }
        self.assertIn("EXHAUSTED", format_status_summary(exhausted_data))
        self.assertIn("EXHAUSTED", format_status_short(exhausted_data))

    def test_cli_execution(self):
        data = {
            "status": "SAFE_IN_QUOTA",
            "gemini_5h_pct": 25.0,
            "gemini_weekly_pct": 50.0,
            "claude_weekly_pct": 0.0,
            "cooldown_active": False,
            "updated_at": "2026-09-12T22:30:00Z",
        }
        self.status_file.write_text(json.dumps(data), encoding="utf-8")

        # Test default CLI output
        res = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "agy_status.py"), "--status-file", str(self.status_file)],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("Gemini 5h: 75.0% rem", res.stdout)
        self.assertIn("1w: 50.0% rem", res.stdout)

        # Test --json output
        res_json = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "agy_status.py"), "--status-file", str(self.status_file), "--json"],
            capture_output=True,
            text=True,
            check=True,
        )
        parsed = json.loads(res_json.stdout)
        self.assertEqual(parsed["gemini_5h_pct"], 25.0)

        # Test --short output
        res_short = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "agy_status.py"), "--status-file", str(self.status_file), "--short"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(res_short.stdout.strip(), "AGY: G:75%/50% C:100% (SAFE)")


if __name__ == "__main__":
    unittest.main()
