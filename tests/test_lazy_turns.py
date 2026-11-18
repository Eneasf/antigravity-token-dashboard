"""Unit tests for lazy turns decoupled architecture and context truncation markers (Milestone 55 / Row 9)."""

import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestLazyTurns(unittest.TestCase):
    """Verifies data.js minification, turns.js decoupling, and context truncation markers."""

    def setUp(self):
        self.dashboard_dir = REPO_ROOT / "dashboard"
        self.data_js_path = self.dashboard_dir / "data.js"
        self.data_json_path = self.dashboard_dir / "data.json"
        self.turns_js_path = self.dashboard_dir / "turns.js"
        self.vault_path = REPO_ROOT / "data" / "antigravity_vault.db"
        self.fixture_dir = REPO_ROOT / "tests" / "fixtures" / "antigravity"

    def test_a_data_js_size_under_3mb(self):
        """Gate B1: data.js must be minified and decoupled so its size is under 3MB."""
        if not self.data_js_path.exists():
            self.skipTest("Uncommitted dashboard artifacts not present in clean checkout")
        size_bytes = self.data_js_path.stat().st_size
        self.assertLess(
            size_bytes,
            3 * 1024 * 1024,
            f"data.js size {size_bytes:,} bytes is >= 3MB",
        )

    def test_b_turns_js_exists_and_header(self):
        """Gate B4: turns.js exists and starts with window.__TELEMETRY_TURNS__ = ."""
        if not self.turns_js_path.exists():
            self.skipTest("Uncommitted dashboard artifacts not present in clean checkout")
        content = self.turns_js_path.read_text(encoding="utf-8")
        self.assertTrue(
            content.startswith("window.__TELEMETRY_TURNS__ = "),
            "turns.js must start with 'window.__TELEMETRY_TURNS__ = '",
        )

    def test_c_turns_js_structure_and_mapping(self):
        """Gate B4: turns.js contains a non-empty dictionary mapping convo_id to turn lists."""
        if not self.turns_js_path.exists():
            self.skipTest("Uncommitted dashboard artifacts not present in clean checkout")
        content = self.turns_js_path.read_text(encoding="utf-8")
        prefix = "window.__TELEMETRY_TURNS__ = "
        self.assertTrue(content.startswith(prefix))
        raw_json = content[len(prefix):].strip()
        if raw_json.endswith(";"):
            raw_json = raw_json[:-1].strip()

        turns_map = json.loads(raw_json)
        self.assertIsInstance(turns_map, dict, "turns.js payload must be a JSON object / dict")
        self.assertGreater(len(turns_map), 0, "turns.js must contain mapped conversations")
        for convo_id, turns in turns_map.items():
            self.assertIsInstance(convo_id, str)
            self.assertIsInstance(turns, list, f"Turns for {convo_id} must be a list")

    def test_d_truncation_marker_parity(self):
        """Gate B2: Truncation marker parity between steps_archive in vault and data.json."""
        if not self.vault_path.exists() or not self.data_json_path.exists():
            self.skipTest("Uncommitted dashboard artifacts not present in clean checkout")
        self.assertTrue(self.vault_path.exists(), f"Missing {self.vault_path}")
        self.assertTrue(self.data_json_path.exists(), f"Missing {self.data_json_path}")

        # Query vault strictly in read-only mode (ADR-001) with busy timeout and retry tolerance
        # against concurrent background export_dashboard.py runs
        uri = f"file:{self.vault_path}?mode=ro"
        expected_convo_ids = set()
        data_convo_ids = set()
        for parity_attempt in range(3):
            vault_markers = {}
            for attempt in range(5):
                try:
                    conn = sqlite3.connect(uri, uri=True, timeout=15.0)
                    try:
                        from src.vault import get_vault_truncation_markers
                        vault_markers = get_vault_truncation_markers(self.vault_path)
                        break
                    finally:
                        conn.close()
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < 4:
                        time.sleep(2)
                        continue
                    raise

            data_payload = json.loads(self.data_json_path.read_text(encoding="utf-8"))
            convo_map = {c["convo_id"]: c for c in data_payload.get("conversations", [])}
            data_all_ids = set(convo_map.keys())
            data_convo_ids = set(
                cid for cid, c in convo_map.items() if c.get("has_truncated")
            )
            # Exclude live sessions whose first compaction step occurred after the data.json snapshot
            vault_convo_ids = set()
            for cid, marker in vault_markers.items():
                if cid not in convo_map:
                    continue
                c_obj = convo_map[cid]
                turns = c_obj.get("turns") or []
                max_exported_step = max((t.get("step_index", 0) for t in turns), default=None)
                first_mark = marker[0] if isinstance(marker, (tuple, list)) else getattr(marker, "first_mark", 0)
                if max_exported_step is not None and first_mark > max_exported_step and not c_obj.get("has_truncated"):
                    continue
                vault_convo_ids.add(cid)
            expected_convo_ids = vault_convo_ids & data_all_ids
            if expected_convo_ids == data_convo_ids:
                break
            if parity_attempt < 2:
                time.sleep(2)

        # Truncation markers in vault for conversations exported to data.json must match
        self.assertEqual(
            expected_convo_ids,
            data_convo_ids,
            f"Mismatch between vault CONTEXT_SUMMARY and data.json has_truncated: {expected_convo_ids ^ data_convo_ids}",
        )

    def test_e_truncation_fields_integrity(self):
        """Gate B3: Truncated conversations have valid first_truncation_step and depth_at_truncation."""
        if not self.data_json_path.exists():
            self.skipTest("Uncommitted dashboard artifacts not present in clean checkout")
        data_payload = json.loads(self.data_json_path.read_text(encoding="utf-8"))
        convos = data_payload.get("conversations", [])

        truncs = [c for c in convos if c.get("has_truncated")]
        self.assertGreaterEqual(
            len(truncs), 7, f"Expected at least 7 truncated conversations, got {len(truncs)}"
        )

        for c in truncs:
            cid = c.get("convo_id")
            first_step = c.get("first_truncation_step")
            depth = c.get("depth_at_truncation")

            self.assertIsInstance(
                first_step,
                int,
                f"Conversation {cid} first_truncation_step must be an int, got {type(first_step)}",
            )
            self.assertGreaterEqual(
                first_step,
                0,
                f"Conversation {cid} first_truncation_step must be >= 0, got {first_step}",
            )
            self.assertIsInstance(
                depth,
                int,
                f"Conversation {cid} depth_at_truncation must be an int, got {type(depth)}",
            )
            self.assertGreater(
                depth,
                0,
                f"Conversation {cid} depth_at_truncation must be > 0, got {depth}",
            )

        non_truncs = [c for c in convos if not c.get("has_truncated")]
        for c in non_truncs:
            cid = c.get("convo_id")
            self.assertFalse(c.get("has_truncated", False))
            self.assertIsNone(
                c.get("first_truncation_step"),
                f"Non-truncated convo {cid} must have first_truncation_step None",
            )
            self.assertIsNone(
                c.get("depth_at_truncation"),
                f"Non-truncated convo {cid} must have depth_at_truncation None",
            )

    def test_f_fixture_determinism(self):
        """Gate B7 / A5: Two export runs against test fixtures produce byte-identical data.js, turns.js, and data.json."""
        exporter_script = REPO_ROOT / "scripts" / "export_dashboard.py"
        self.assertTrue(exporter_script.exists())
        self.assertTrue(self.fixture_dir.exists())

        d1 = tempfile.mkdtemp(prefix="lazy_turns_det_1_")
        d2 = tempfile.mkdtemp(prefix="lazy_turns_det_2_")
        try:
            for out_d in (d1, d2):
                cmd = [
                    sys.executable,
                    str(exporter_script),
                    "--antigravity-dir",
                    str(self.fixture_dir),
                    "--no-live-quota",
                    "--reference-time",
                    "2026-09-05T14:30:00Z",
                    "--output-dir",
                    out_d,
                ]
                res = subprocess.run(cmd, check=True, capture_output=True, text=True)
                self.assertEqual(res.returncode, 0)

            p1 = Path(d1)
            p2 = Path(d2)

            f1_js = (p1 / "data.js").read_bytes()
            f2_js = (p2 / "data.js").read_bytes()
            self.assertGreater(len(f1_js), 0)
            self.assertEqual(f1_js, f2_js, "data.js must be byte-identical across runs")

            f1_turns = (p1 / "turns.js").read_bytes()
            f2_turns = (p2 / "turns.js").read_bytes()
            self.assertGreater(len(f1_turns), 0)
            self.assertEqual(f1_turns, f2_turns, "turns.js must be byte-identical across runs")

            f1_json = (p1 / "data.json").read_bytes()
            f2_json = (p2 / "data.json").read_bytes()
            self.assertGreater(len(f1_json), 0)
            self.assertEqual(f1_json, f2_json, "data.json must be byte-identical across runs")

            # Verify turns are decoupled: in data.js, conversations have turns: []
            js_text = (p1 / "data.js").read_text(encoding="utf-8")
            prefix = "window.__TELEMETRY_DATA__ = "
            self.assertTrue(js_text.startswith(prefix))
            raw_js_json = js_text[len(prefix):].strip().rstrip(";")
            data_js_payload = json.loads(raw_js_json)
            for c in data_js_payload.get("conversations", []):
                self.assertEqual(
                    c.get("turns", []),
                    [],
                    f"Conversation {c.get('convo_id')} in data.js must have empty turns",
                )

            # Verify turns.js has the fixture turns
            turns_text = (p1 / "turns.js").read_text(encoding="utf-8")
            turns_prefix = "window.__TELEMETRY_TURNS__ = "
            self.assertTrue(turns_text.startswith(turns_prefix))
            raw_turns_json = turns_text[len(turns_prefix):].strip().rstrip(";")
            turns_payload = json.loads(raw_turns_json)
            self.assertIsInstance(turns_payload, dict)
            self.assertEqual(len(turns_payload), len(data_js_payload.get("conversations", [])))
        finally:
            shutil.rmtree(d1, ignore_errors=True)
            shutil.rmtree(d2, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
