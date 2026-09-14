"""
Unit tests for scripts/ingest_statement.py:
Google One AI credit statement ingestion, duplicate prevention, and vault archival.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from scripts.ingest_statement import (
    build_incident_record,
    calculate_costs_and_credits,
    generate_incident_id,
    ingest_incident,
    main,
    parse_iso_datetime,
    parse_models_arg,
    record_in_vault,
    timestamps_match,
)


class TestIngestStatement(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)
        self.ledger_path = self.tmp_path / "exhaustion_ledger.json"
        self.vault_path = self.tmp_path / "antigravity_vault.db"

        # Initialize mock ledger
        self.mock_ledger = {
            "version": 1,
            "description": "Mock persistent exhaustion ledger",
            "prepaid_pack": {
                "total_credits": 2500,
                "purchase_price_gbp": 23.99,
                "purchase_price_usd": 25.0,
                "cost_per_credit_gbp": 0.009596,
                "cost_per_credit_usd": 0.01,
            },
            "incidents": [
                {
                    "code": 429,
                    "credit_burn_gbp": 7.18,
                    "credit_burn_usd": 7.48,
                    "credits_burned": 748,
                    "description": "Existing incident 1",
                    "end_utc": "2026-09-05T14:00:00.000000+00:00",
                    "hour_display": "05 Sep 2026, 13:00:00 UTC",
                    "hour_timestamp": "2026-09-05T13:00:00Z",
                    "incident_id": "exc-20260905-13",
                    "models": {
                        "Gemini 3.8 Flash (High)": 299
                    },
                    "reason": "RESOURCE_EXHAUSTED",
                    "start_utc": "2026-09-05T13:35:13.877653+00:00",
                    "turns_count": 299,
                }
            ],
        }
        with open(self.ledger_path, "w", encoding="utf-8") as f:
            json.dump(self.mock_ledger, f, indent=2)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_iso_datetime(self):
        dt = parse_iso_datetime("2026-09-06T09:00:00Z")
        self.assertEqual(dt.year, 2026)
        self.assertEqual(dt.month, 9)
        self.assertEqual(dt.day, 6)
        self.assertEqual(dt.hour, 9)
        self.assertEqual(dt.tzinfo, timezone.utc)

        dt_offset = parse_iso_datetime("2026-09-06T10:00:00+01:00")
        self.assertEqual(dt_offset.hour, 9)  # UTC normalized

        with self.assertRaises(ValueError):
            parse_iso_datetime("invalid-timestamp-format")

    def test_timestamps_match(self):
        self.assertTrue(
            timestamps_match("2026-09-06T09:00:00Z", "2026-09-06T09:00:00+00:00")
        )
        self.assertTrue(
            timestamps_match(
                "2026-09-06T09:00:00.000000+00:00", "2026-09-06T09:00:00+00:00"
            )
        )
        self.assertFalse(
            timestamps_match("2026-09-06T09:00:00Z", "2026-09-06T10:00:00Z")
        )
        self.assertFalse(timestamps_match(None, "2026-09-06T10:00:00Z"))

    def test_generate_incident_id(self):
        dt = datetime(2026, 9, 6, 9, 30, 0, tzinfo=timezone.utc)
        existing = {"exc-20260906-09"}
        new_id = generate_incident_id(dt, existing)
        self.assertTrue(new_id.startswith("exc-20260906-09"))
        self.assertNotEqual(new_id, "exc-20260906-09")

    def test_calculate_costs_and_credits(self):
        pack = {"cost_per_credit_gbp": 0.009596, "cost_per_credit_usd": 0.01}
        # Credits to cost
        c, gbp, usd = calculate_costs_and_credits(748, None, "GBP", pack)
        self.assertEqual(c, 748)
        self.assertEqual(gbp, 7.18)
        self.assertEqual(usd, 7.48)

        # Amount GBP to credits
        c2, gbp2, usd2 = calculate_costs_and_credits(None, 7.18, "GBP", pack)
        self.assertEqual(c2, 748)
        self.assertEqual(gbp2, 7.18)
        self.assertEqual(usd2, 7.48)

        # Amount USD to credits
        c3, gbp3, usd3 = calculate_costs_and_credits(None, 10.00, "USD", pack)
        self.assertEqual(c3, 1000)
        self.assertEqual(usd3, 10.00)
        self.assertEqual(gbp3, 9.60)

    def test_parse_models_arg(self):
        # Comma separated string
        m1 = parse_models_arg("Gemini 3.8 Flash (High), Gemini 3.1 Pro (High)", 100)
        self.assertEqual(m1["Gemini 3.8 Flash (High)"], 50)
        self.assertEqual(m1["Gemini 3.1 Pro (High)"], 50)

        # JSON object string
        m2 = parse_models_arg('{"Gemini 3.8 Flash (High)": 299}', 0)
        self.assertEqual(m2["Gemini 3.8 Flash (High)"], 299)

        # Direct dict
        m3 = parse_models_arg({"Gemini 3.7 Flash": 50}, 50)
        self.assertEqual(m3["Gemini 3.7 Flash"], 50)

    def test_ingest_incident_success(self):
        incident_data = {
            "incident_id": "exc-20260906-10",
            "hour_timestamp": "2026-09-06T10:00:00Z",
            "hour_display": "06 Sep 2026, 10:00:00 UTC",
            "start_utc": "2026-09-06T10:15:00+00:00",
            "end_utc": "2026-09-06T11:00:00+00:00",
            "credits_burned": 431,
            "amount": 4.13,
            "currency": "GBP",
            "models": "Gemini 3.8 Flash (High)",
            "turns_count": 172,
            "reason": "RESOURCE_EXHAUSTED",
            "description": "Second burst test deduction",
        }

        success, msg, inc = ingest_incident(
            incident_data,
            ledger_path=self.ledger_path,
            vault_path=self.vault_path,
        )
        self.assertTrue(success)
        self.assertIn("Reconciled deduction: 431 credits", msg)
        self.assertIsNotNone(inc)
        self.assertEqual(inc["incident_id"], "exc-20260906-10")

        # Verify ledger file was atomically updated
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            updated_ledger = json.load(f)

        self.assertEqual(len(updated_ledger["incidents"]), 2)
        self.assertEqual(updated_ledger["incidents"][1]["incident_id"], "exc-20260906-10")
        self.assertEqual(updated_ledger["incidents"][1]["credits_burned"], 431)
        self.assertEqual(updated_ledger["incidents"][1]["credit_burn_gbp"], 4.13)
        self.assertEqual(updated_ledger["incidents"][1]["credit_burn_usd"], 4.31)

    def test_ingest_duplicate_incident_id(self):
        # Attempting to add an incident with ID already in ledger
        incident_data = {
            "incident_id": "exc-20260905-13",
            "start_utc": "2026-09-06T15:00:00+00:00",
            "end_utc": "2026-09-06T16:00:00+00:00",
            "credits_burned": 100,
        }
        success, msg, inc = ingest_incident(
            incident_data,
            ledger_path=self.ledger_path,
            vault_path=self.vault_path,
        )
        self.assertFalse(success)
        self.assertIn("[SKIP] Incident ID already exists", msg)

        # Ledger length remains unchanged
        with open(self.ledger_path, "r", encoding="utf-8") as f:
            ledger = json.load(f)
        self.assertEqual(len(ledger["incidents"]), 1)

    def test_ingest_duplicate_timestamps(self):
        # Attempting to add an incident with matching start_utc and end_utc
        incident_data = {
            "incident_id": "exc-new-id",
            "start_utc": "2026-09-05T13:35:13.877653+00:00",
            "end_utc": "2026-09-05T14:00:00.000000+00:00",
            "credits_burned": 748,
        }
        success, msg, inc = ingest_incident(
            incident_data,
            ledger_path=self.ledger_path,
            vault_path=self.vault_path,
        )
        self.assertFalse(success)
        self.assertIn("[SKIP] Incident with exact time interval already exists", msg)

    def test_record_in_vault(self):
        # Create an empty vault database
        conn = sqlite3.connect(str(self.vault_path))
        conn.close()

        incident_data = {
            "incident_id": "exc-20260906-12",
            "hour_timestamp": "2026-09-06T12:00:00Z",
            "hour_display": "06 Sep 2026, 12:00:00 UTC",
            "start_utc": "2026-09-06T12:00:00+00:00",
            "end_utc": "2026-09-06T13:00:00+00:00",
            "credits_burned": 250,
            "amount": 2.40,
            "currency": "GBP",
            "models": "Gemini 3.8 Flash (High)",
            "turns_count": 100,
            "reason": "RESOURCE_EXHAUSTED",
            "description": "Vault recording test incident",
        }

        success, msg, inc = ingest_incident(
            incident_data,
            ledger_path=self.ledger_path,
            vault_path=self.vault_path,
        )
        self.assertTrue(success)
        self.assertIn("and recorded in Vault", msg)

        # Inspect sqlite database
        conn = sqlite3.connect(str(self.vault_path))
        cur = conn.cursor()
        cur.execute("SELECT event_id, code, reason, timestamp FROM log_events_archive WHERE event_id = ?", ("exc-20260906-12",))
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "exc-20260906-12")
        self.assertEqual(row[1], 429)
        self.assertEqual(row[2], "RESOURCE_EXHAUSTED")

    def test_json_ingest_via_main(self):
        json_file = self.tmp_path / "input.json"
        payload = {
            "incidents": [
                {
                    "incident_id": "exc-json-batch-01",
                    "start_utc": "2026-09-06T14:00:00Z",
                    "end_utc": "2026-09-06T15:00:00Z",
                    "credits_burned": 500,
                    "amount": 4.80,
                    "currency": "GBP",
                }
            ]
        }
        json_file.write_text(json.dumps(payload), encoding="utf-8")

        exit_code = main([
            "--json", str(json_file),
            "--ledger-path", str(self.ledger_path),
            "--vault-path", str(self.vault_path),
        ])
        self.assertEqual(exit_code, 0)

        with open(self.ledger_path, "r", encoding="utf-8") as f:
            updated = json.load(f)
        self.assertEqual(len(updated["incidents"]), 2)
        self.assertEqual(updated["incidents"][1]["incident_id"], "exc-json-batch-01")


    def test_record_in_vault_with_src_vault_schema(self):
        try:
            from src.vault import init_vault
        except ImportError:
            return

        # Initialize real vault schema
        conn = init_vault(self.vault_path)
        conn.close()

        incident_data = {
            "incident_id": "exc-20260906-15",
            "hour_timestamp": "2026-09-06T15:00:00Z",
            "hour_display": "06 Sep 2026, 15:00:00 UTC",
            "start_utc": "2026-09-06T15:00:00+00:00",
            "end_utc": "2026-09-06T16:00:00+00:00",
            "credits_burned": 100,
            "amount": 0.96,
            "currency": "GBP",
            "models": "Gemini 3.8 Flash (High)",
            "turns_count": 40,
            "reason": "RESOURCE_EXHAUSTED",
            "description": "Schema compatibility test",
        }

        success, msg, inc = ingest_incident(
            incident_data,
            ledger_path=self.ledger_path,
            vault_path=self.vault_path,
        )
        self.assertTrue(success)
        self.assertIn("and recorded in Vault", msg)

        conn = sqlite3.connect(str(self.vault_path))
        cur = conn.cursor()
        cur.execute(
            "SELECT event_fingerprint, code, reason, timestamp FROM log_events_archive WHERE event_fingerprint = ?",
            ("exc-20260906-15",),
        )
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "exc-20260906-15")
        self.assertEqual(row[1], 429)
        self.assertEqual(row[2], "RESOURCE_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()

