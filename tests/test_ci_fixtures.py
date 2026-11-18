"""
Unit tests for anonymized offline Antigravity CI fixtures and offline export (Milestone 31).

Validates:
- Fixture environment in tests/fixtures/antigravity/ discovers valid conversations.
- Authoritative workspace names, titles, and Git branches are extracted accurately.
- Multi-model turn extraction covers Gemini (1318/1050) and Claude (1026) telemetry.
- --no-live-quota prevents Connect-RPC network calls and side channels.
- Byte-determinism invariant (ADR-004) holds across multiple exports.
- Zero PII or local user home paths exist in the fixture files.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "antigravity"

from antigravity_telemetry.reader import (
    discover_all_conversations,
    read_conversation_turns,
)
from scripts.export_dashboard import export_telemetry


class TestCIFixtures(unittest.TestCase):
    """Test suite verifying anonymized offline Antigravity fixtures and deterministic exports."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(FIXTURE_DIR.exists(), f"Fixture directory {FIXTURE_DIR} must exist")
        cls.assertTrue((FIXTURE_DIR / "conversations").exists(), "conversations/ must exist in fixtures")
        cls.assertTrue((FIXTURE_DIR / "annotations").exists(), "annotations/ must exist in fixtures")
        cls.assertTrue((FIXTURE_DIR / "agyhub_summaries_proto.pb").exists(), "agyhub_summaries_proto.pb must exist")

    def test_fixture_discovery_and_metadata(self):
        """Discovers both fixture conversations with clean titles, workspaces, and Git branches."""
        convos = discover_all_conversations(FIXTURE_DIR)
        self.assertEqual(len(convos), 2, "Expected exactly 2 fixture conversations")

        by_id = {c["convo_id"]: c for c in convos}
        self.assertIn("11111111-1111-1111-1111-111111111111", by_id)
        self.assertIn("22222222-2222-2222-2222-222222222222", by_id)

        c1 = by_id["11111111-1111-1111-1111-111111111111"]
        self.assertEqual(c1["title"], "Project Alpha Architecture")
        self.assertEqual(c1["workspace_name"], "project-alpha")
        self.assertEqual(c1["git_branch"], "main")

        c2 = by_id["22222222-2222-2222-2222-222222222222"]
        self.assertEqual(c2["title"], "Claude Performance Benchmarks")
        self.assertEqual(c2["workspace_name"], "project-beta")
        self.assertEqual(c2["git_branch"], "feat/claude-audit")

    def test_turn_extraction_and_model_census(self):
        """Extracts turn telemetry across Gemini (1318/1050) and Claude (1026)."""
        convos = discover_all_conversations(FIXTURE_DIR)
        by_id = {c["convo_id"]: c for c in convos}

        # Convo 1 turns (Gemini Flash High 1318 + Flash Lite 1050)
        t1 = read_conversation_turns(by_id["11111111-1111-1111-1111-111111111111"]["db_path"])
        self.assertEqual(len(t1), 2)
        self.assertEqual(t1[0]["model_id"], "1318")
        self.assertEqual(t1[0]["prompt_tokens_uncached"], 4000)
        self.assertEqual(t1[0]["cached_tokens"], 16000)
        self.assertEqual(t1[0]["total_input_tokens"], 20000)
        self.assertEqual(t1[0]["output_tokens_total"], 500)
        self.assertEqual(t1[0]["thinking_tokens"], 350)
        self.assertEqual(t1[0]["answer_tokens"], 150)
        self.assertEqual(t1[0]["cache_hit_ratio_pct"], 80.0)

        self.assertEqual(t1[1]["model_id"], "1050")
        self.assertEqual(t1[1]["prompt_tokens_uncached"], 1200)
        self.assertEqual(t1[1]["cached_tokens"], 4800)
        self.assertEqual(t1[1]["total_input_tokens"], 6000)
        self.assertEqual(t1[1]["output_tokens_total"], 200)

        # Convo 2 turns (Claude Opus 1026)
        t2 = read_conversation_turns(by_id["22222222-2222-2222-2222-222222222222"]["db_path"])
        self.assertEqual(len(t2), 1)
        self.assertEqual(t2[0]["model_id"], "1026")
        self.assertEqual(t2[0]["prompt_tokens_uncached"], 6000)
        self.assertEqual(t2[0]["cached_tokens"], 45000)
        self.assertEqual(t2[0]["total_input_tokens"], 51000)
        self.assertEqual(t2[0]["output_tokens_total"], 800)
        self.assertEqual(t2[0]["thinking_tokens"], 600)
        self.assertEqual(t2[0]["answer_tokens"], 200)
        self.assertEqual(t2[0]["cache_hit_ratio_pct"], 88.24)

    def test_no_live_quota_flag_bypasses_rpc(self):
        """Passing no_live_quota=True guarantees fetch_live_quota_summary is never called."""
        with tempfile.TemporaryDirectory() as td:
            temp_path = Path(td)
            d_dir = temp_path / "dashboard"
            d_dir.mkdir()
            html_p = d_dir / "index.html"
            html_p.write_text(
                '<!DOCTYPE html><html><head></head><body><script id="injected-dashboard-data" type="application/json">{}</script></body></html>',
                encoding="utf-8",
            )

            with patch("src.quota_client.fetch_live_quota_summary") as mock_rpc:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    export_telemetry(
                        antigravity_dir=FIXTURE_DIR,
                        dashboard_path=html_p,
                        no_live_quota=True,
                    )
                mock_rpc.assert_not_called()

    def test_byte_determinism_across_runs(self):
        """Repeated export executions with fixed reference time produce byte-identical data files (ADR-004)."""
        ref_iso = "2026-09-05T14:30:00+00:00"
        import datetime
        ref_dt = datetime.datetime.fromisoformat(ref_iso)

        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            d1 = Path(td1) / "dashboard"
            d1.mkdir()
            h1 = d1 / "index.html"
            h1.write_text(
                '<!DOCTYPE html><html><head></head><body><script id="injected-dashboard-data" type="application/json">{}</script></body></html>',
                encoding="utf-8",
            )

            d2 = Path(td2) / "dashboard"
            d2.mkdir()
            h2 = d2 / "index.html"
            h2.write_text(
                '<!DOCTYPE html><html><head></head><body><script id="injected-dashboard-data" type="application/json">{}</script></body></html>',
                encoding="utf-8",
            )

            # First export
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                p1 = export_telemetry(
                    antigravity_dir=FIXTURE_DIR,
                    dashboard_path=h1,
                    no_live_quota=True,
                    reference_time=ref_dt,
                )

            # Second export
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                p2 = export_telemetry(
                    antigravity_dir=FIXTURE_DIR,
                    dashboard_path=h2,
                    no_live_quota=True,
                    reference_time=ref_dt,
                )

            # Payloads match
            self.assertEqual(p1["summary"]["total_input_tokens"], p2["summary"]["total_input_tokens"])
            self.assertEqual(p1["summary"]["total_input_tokens"], 77000)

            # Decoupled files byte-identical
            data_json_1 = (d1 / "data.json").read_bytes()
            data_json_2 = (d2 / "data.json").read_bytes()
            self.assertEqual(data_json_1, data_json_2)

            data_js_1 = (d1 / "data.js").read_bytes()
            data_js_2 = (d2 / "data.js").read_bytes()
            self.assertEqual(data_js_1, data_js_2)

            meta_json_1 = (d1 / "meta.json").read_bytes()
            meta_json_2 = (d2 / "meta.json").read_bytes()
            self.assertEqual(meta_json_1, meta_json_2)

            meta_js_1 = (d1 / "meta.js").read_bytes()
            meta_js_2 = (d2 / "meta.js").read_bytes()
            self.assertEqual(meta_js_1, meta_js_2)

    def test_zero_pii_and_local_paths_in_fixtures(self):
        """Fixture databases and files contain zero local user paths or personal usernames."""
        forbidden = [b"/Users/", b"eneasf", b"Eneasf", b"/home/"]
        for p in FIXTURE_DIR.rglob("*"):
            if p.is_file():
                raw = p.read_bytes()
                for needle in forbidden:
                    self.assertNotIn(
                        needle,
                        raw,
                        f"Security violation: Found forbidden '{needle.decode()}' in fixture file {p.relative_to(REPO_ROOT)}",
                    )

    def test_hermetic_export_with_isolated_home(self):
        """Exporting fixtures with an isolated/empty HOME produces byte-identical output to baseline."""
        baseline_path = REPO_ROOT / "tests" / "fixtures" / "aggregator_baseline_data.json"
        self.assertTrue(baseline_path.exists(), "aggregator_baseline_data.json must exist")

        with tempfile.TemporaryDirectory() as empty_home, tempfile.TemporaryDirectory() as out_dir:
            env = dict(os.environ, HOME=empty_home)
            cmd = [
                "python3",
                str(REPO_ROOT / "scripts" / "export_dashboard.py"),
                "--antigravity-dir",
                str(FIXTURE_DIR),
                "--no-live-quota",
                "--reference-time",
                "2026-09-05T14:30:00Z",
                "--output-dir",
                out_dir,
            ]
            res = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
            )
            self.assertEqual(res.returncode, 0, f"Export failed with stderr: {res.stderr}")

            out_data_json = Path(out_dir) / "data.json"
            self.assertTrue(out_data_json.exists(), "data.json must be generated in output-dir")

            generated_bytes = out_data_json.read_bytes()
            baseline_bytes = baseline_path.read_bytes()
            self.assertEqual(
                generated_bytes,
                baseline_bytes,
                "Hermetic export with isolated HOME must match aggregator_baseline_data.json byte-for-byte",
            )

    def test_baseline_contains_only_synthetic_fixtures(self):
        """Baseline aggregator_baseline_data.json must never contain owner personal total (3640)
        and must only contain fixture synthetic events."""
        baseline_path = REPO_ROOT / "tests" / "fixtures" / "aggregator_baseline_data.json"
        self.assertTrue(baseline_path.exists(), "aggregator_baseline_data.json must exist")
        raw_text = baseline_path.read_text(encoding="utf-8")

        # 1. Personal total 3640 must not appear anywhere in baseline
        self.assertNotIn(
            "3640",
            raw_text,
            "Security violation: Personal total 3640 found in aggregator_baseline_data.json",
        )

        # 2. Baseline must only contain the fixture's synthetic exhaustion events
        data = json.loads(raw_text)
        intervals = data.get("exhaustion_intervals", [])
        self.assertEqual(
            len(intervals),
            2,
            f"Expected exactly 2 synthetic exhaustion intervals in baseline, got {len(intervals)}",
        )
        for interval in intervals:
            self.assertEqual(interval.get("code"), 429)
            self.assertEqual(interval.get("reason"), "RESOURCE_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()
