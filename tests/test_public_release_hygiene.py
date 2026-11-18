"""
Unit tests for public release staging sanitization and audit-file PII coverage.

Verifies:
1. `sanitize_public_staging_tree()` scrubs personal Vault snapshot events from
   `data/quota_regime_ledger.json` while preserving calibrated model weights and
   bucket capacities.
2. `TestTelemetrySanitization._collect_files()` includes `docs/AUDIT_*.md`,
   `data/quota_regime_ledger.sample.json`, and `.github/` workflows without
   exempting `AUDIT_*` files.
3. `scripts/publish_to_public.py` does not exempt `docs/AUDIT_*.md` from its
   forbidden-needle grep check.
"""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.publish_to_public import sanitize_public_staging_tree
from tests.test_sanitization import TestTelemetrySanitization


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestPublicReleaseHygiene(unittest.TestCase):
    """Verify public release staging filter and un-exempted sanitization coverage."""

    def test_sanitize_public_staging_tree_scrubs_events_preserves_weights(self):
        """Personal regime events are cleared while calibrated weights and bucket limits stay intact."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            data_dir.mkdir(parents=True)
            ledger_path = data_dir / "quota_regime_ledger.json"
            sample_path = data_dir / "quota_regime_ledger.sample.json"

            source_payload = {
                "active_regime_id": "regime-20261017-post-reset",
                "active_regime_since_utc": "2026-10-17T01:46:18Z",
                "bucket_5h_usd": 25.0,
                "bucket_weekly_usd": 100.0,
                "expected_coupling_ratio": 4.0,
                "calibrated_weights_per_1m": {
                    "1427": {"prompt_uncached": 1.0, "prompt_cached": 0.05, "candidate_output": 5.0},
                    "1528": {"prompt_uncached": 0.25, "prompt_cached": 0.0125, "candidate_output": 1.25},
                },
                "events": [
                    {"event_id": "reg-personal-1", "snapshot_range": "#1 -> #205", "turns_analyzed": 4511},
                    {"event_id": "reg-personal-2", "snapshot_range": "#3899 -> #3905", "turns_analyzed": 145},
                ],
            }
            sample_payload = {"events": [{"event_id": "reg-sample-baseline"}]}
            ledger_path.write_text(json.dumps(source_payload, indent=2), encoding="utf-8")
            sample_path.write_text(json.dumps(sample_payload, indent=2), encoding="utf-8")

            result = sanitize_public_staging_tree(root)
            self.assertEqual(result["regime_events_scrubbed"], 2)

            scrubbed = json.loads(ledger_path.read_text(encoding="utf-8"))
            self.assertEqual(scrubbed["events"], [])
            self.assertEqual(scrubbed["bucket_5h_usd"], 25.0)
            self.assertEqual(scrubbed["bucket_weekly_usd"], 100.0)
            self.assertEqual(scrubbed["calibrated_weights_per_1m"], source_payload["calibrated_weights_per_1m"])

            # Sample template must remain untouched
            untouched_sample = json.loads(sample_path.read_text(encoding="utf-8"))
            self.assertEqual(len(untouched_sample["events"]), 1)

    def test_sanitization_collector_includes_audit_files_and_sample_ledgers(self):
        """Ensure TestTelemetrySanitization no longer skips docs/AUDIT_*.md files."""
        checker = TestTelemetrySanitization()
        collected = {p.relative_to(REPO_ROOT).as_posix() for p in checker._collect_files()}

        audit_files = [p for p in collected if p.startswith("docs/AUDIT_")]
        self.assertGreaterEqual(len(audit_files), 6, "Expected all docs/AUDIT_*.md files to be audited for PII")
        self.assertIn("data/quota_regime_ledger.sample.json", collected)
        self.assertIn(".github/workflows/deploy_pages.yml", collected)

    def test_publisher_does_not_exempt_audit_docs(self):
        """Ensure publish_to_public.py does not exclude docs/AUDIT_*.md from needle scans."""
        pub_src = (REPO_ROOT / "scripts" / "publish_to_public.py").read_text(encoding="utf-8")
        self.assertNotIn(":!docs/AUDIT_", pub_src)
        self.assertIn("sanitize_public_staging_tree", pub_src)


if __name__ == "__main__":
    unittest.main()
