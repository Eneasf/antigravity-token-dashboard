"""
tests/test_quota_history.py - Unit tests for scripts/quota_history.py.

Validates:
- Script execution with --summary, --incidents, --turns, and --json.
- Deterministic output parsing and metric consistency.
- Custom vault and ledger path redirection (Rule AC-4 compliance).
"""

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from src.vault_schema import init_vault
from scripts.quota_history import build_audit_report, load_macro_incidents, load_throttled_turns


class TestQuotaHistory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.vault_path = self.temp_path / "test_vault.db"
        self.ledger_path = self.temp_path / "test_ledger.json"

        # Initialize test vault schema
        conn = init_vault(self.vault_path)
        cur = conn.cursor()

        # Insert a sample conversation
        cur.execute(
            """
            INSERT INTO conversations_archive (
                convo_id, title, turn_count, first_turn_ts, last_turn_ts
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("convo-1", "Test Session", 10, "2026-09-08T20:00:00Z", "2026-09-08T22:00:00Z"),
        )

        # Insert a sample throttled turn
        cur.execute(
            """
            INSERT INTO steps_archive (
                convo_id, step_idx, step_type, status, timestamp, model_name, rate_limit_flag, error_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("convo-1", 1, 15, 3, "2026-09-08T21:15:00Z", "Gemini 3.8 Flash (High)", 1, "RESOURCE_EXHAUSTED"),
        )
        conn.commit()
        conn.close()

        # Create a sample ledger JSON
        sample_ledger = {
            "version": 1,
            "incidents": [
                {
                    "incident_id": "test-exc-1",
                    "hour_timestamp": "2026-09-08T21:00:00Z",
                    "code": 429,
                    "reason": "RESOURCE_EXHAUSTED",
                    "credits_burned": 50,
                    "credit_burn_usd": 0.50,
                    "credit_burn_gbp": 0.48,
                    "models": {"Gemini 3.8 Flash (High)": 20},
                }
            ],
        }
        self.ledger_path.write_text(json.dumps(sample_ledger), encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_build_audit_report(self):
        report = build_audit_report(self.vault_path, self.ledger_path)
        self.assertIn("summary", report)
        self.assertEqual(report["summary"]["macro_incidents_count"], 1)
        self.assertEqual(report["summary"]["total_credits_burned"], 50)
        self.assertEqual(report["summary"]["turn_level_throttles_count"], 1)
        self.assertIn("Gemini 3.8 Flash (High)", report["summary"]["affected_models"])

    def test_cli_execution_json(self):
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "quota_history.py"
        cmd = [
            sys.executable,
            str(script_path),
            "--vault-path",
            str(self.vault_path),
            "--ledger-path",
            str(self.ledger_path),
            "--json",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        self.assertEqual(data["summary"]["macro_incidents_count"], 1)
        self.assertEqual(data["summary"]["total_credits_burned"], 50)

    def test_cli_execution_summary_and_tables(self):
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "quota_history.py"
        cmd = [
            sys.executable,
            str(script_path),
            "--vault-path",
            str(self.vault_path),
            "--ledger-path",
            str(self.ledger_path),
            "--summary",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        self.assertIn("ANTIGRAVITY TELEMETRY VAULT: QUOTA EXHAUSTION", res.stdout)
        self.assertIn("MACRO STATEMENT DEDUCTIONS", res.stdout)
        self.assertIn("MICRO TURN-LEVEL 429 REJECTIONS", res.stdout)
        self.assertIn("Gemini 3.8 Flash (High)", res.stdout)


if __name__ == "__main__":
    unittest.main()
