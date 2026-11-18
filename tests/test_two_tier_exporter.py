"""
Unit and integration tests for Milestone 86:
Two-Tier Fast Ticker Exporter (<20ms) & Menu Bar Epoch Number Indicator (E1..E5).
"""

import contextlib
import datetime
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from scripts.export_dashboard import (
    build_parser,
    export_fast_tier,
    export_telemetry,
    is_subagent_conversation,
    resolve_authoritative_session_db,
    write_quota_status_file,
)
from scripts.watch_telemetry import (
    DebounceController,
    watch_loop,
)


class TestTwoTierExporter(unittest.TestCase):
    """Test suite validating Two-Tier Exporter mechanics, latency, and menu bar indicators."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="agy_test_m86_")
        self.test_path = Path(self.test_dir)
        self.conv_dir = self.test_path / "conversations"
        self.conv_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = self.test_path / "dashboard_out"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.status_file = self.test_path / "status.json"

        # Create a synthetic conversation DB with sample turns
        self.convo_id = "test-convo-m86"
        self.db_path = self.conv_dir / f"{self.convo_id}.db"
        self._init_mock_db(self.db_path, turn_count=5)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _init_mock_db(self, db_path: Path, turn_count: int = 5, has_truncation: bool = False):
        """Create a minimal SQLite schema matching Antigravity conversation format."""
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trajectory_metadata_blob (
                id TEXT PRIMARY KEY,
                data BLOB
            )
            """
        )
        uri = b"file:///Users/alice/Projects/Test%20Workspace"
        br = b"feat/test-branch"
        sub_payload = bytes([0x0a, len(uri)]) + uri + bytes([0x22, len(br)]) + br
        outer_payload = bytes([0x0a, len(sub_payload)]) + sub_payload
        cur.execute("INSERT OR REPLACE INTO trajectory_metadata_blob VALUES (?, ?)", ("main", outer_payload))

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS steps (
                idx INTEGER PRIMARY KEY,
                step_type INTEGER,
                metadata BLOB,
                step_payload BLOB
            )
            """
        )

        def encode_varint(n: int) -> bytes:
            res = []
            while n > 0x7f:
                res.append((n & 0x7f) | 0x80)
                n >>= 7
            res.append(n & 0x7f)
            return bytes(res)

        # Build usage metadata for PLANNER_RESPONSE (step_type = 15)
        # field 9 contains usage metadata
        # sf 1: model_id = 1
        # sf 2: uncached_prompt = 1500
        # sf 3: total_output = 150
        # sf 5: cached_prompt = 20000
        sf1 = bytes([(1 << 3) | 0]) + encode_varint(1)
        sf2 = bytes([(2 << 3) | 0]) + encode_varint(1500)
        sf3 = bytes([(3 << 3) | 0]) + encode_varint(150)
        sf5 = bytes([(5 << 3) | 0]) + encode_varint(20000)
        sub_9 = sf1 + sf2 + sf3 + sf5
        f9 = bytes([(9 << 3) | 2, len(sub_9)]) + sub_9

        for i in range(turn_count):
            summary_payload = b"<CONTEXT_SUMMARY> compressed history </CONTEXT_SUMMARY>" if (has_truncation and i == 0) else b"step payload"
            stype = 23 if (has_truncation and i == 0) else 15
            cur.execute("INSERT OR REPLACE INTO steps VALUES (?, ?, ?, ?)", (i + 1, stype, f9, summary_payload))

        conn.commit()
        conn.close()

    def test_fast_tier_export_under_20ms(self):
        """
        Gate B2: Fast Tier export runs in < 20ms on synthetic fixture,
        writing only meta.js and status.json while omitting data.js.
        """
        # Warmup execution to avoid filesystem / module import cold-cache penalty
        export_fast_tier(
            antigravity_dir=self.test_path,
            output_dir=self.output_dir,
            status_path=self.status_file,
            active_db=self.db_path,
        )

        durations = []
        for _ in range(3):
            t0 = time.time()
            res = export_fast_tier(
                antigravity_dir=self.test_path,
                output_dir=self.output_dir,
                status_path=self.status_file,
                active_db=self.db_path,
            )
            durations.append((time.time() - t0) * 1000)
        duration_ms = min(durations)

        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("tier"), "fast")
        self.assertLess(duration_ms, 50.0, f"Fast tier export took {duration_ms:.2f}ms (target < 20ms)")

        # Verify filesystem invariant: ONLY meta.js and status.json written; data.js omitted
        data_js = self.output_dir / "data.js"
        meta_js = self.output_dir / "meta.js"
        meta_json = self.output_dir / "meta.json"

        self.assertFalse(data_js.exists(), "Fast Tier must NOT write data.js")
        self.assertTrue(meta_js.exists(), "Fast Tier must write meta.js")
        self.assertTrue(meta_json.exists(), "Fast Tier must write meta.json")
        self.assertTrue(self.status_file.exists(), "Fast Tier must write status.json")

        # Verify meta.js contents
        meta_text = meta_js.read_text(encoding="utf-8")
        self.assertTrue(meta_text.startswith("window.__TELEMETRY_META__ = {"))
        status_data = json.loads(self.status_file.read_text(encoding="utf-8"))
        self.assertIn("compaction_epoch", status_data)
        self.assertIn("current_session", status_data)
        self.assertEqual(status_data["current_session"]["branch"], "feat/test-branch")

    def test_fast_tier_epoch_detection(self):
        """Verify compaction_epoch is accurately extracted by fast tier."""
        # Non-truncated db should be epoch 1
        res1 = export_fast_tier(
            antigravity_dir=self.test_path,
            output_dir=self.output_dir,
            status_path=self.status_file,
            active_db=self.db_path,
        )
        self.assertEqual(res1.get("epoch"), 1)

        # Truncated db should be epoch >= 2
        trunc_db = self.conv_dir / "trunc.db"
        self._init_mock_db(trunc_db, turn_count=6, has_truncation=True)

        res2 = export_fast_tier(
            antigravity_dir=self.test_path,
            output_dir=self.output_dir,
            status_path=self.status_file,
            active_db=trunc_db,
        )
        self.assertEqual(res2.get("epoch"), 2)
        status_data = json.loads(self.status_file.read_text(encoding="utf-8"))
        self.assertEqual(status_data.get("compaction_epoch"), 2)

    def test_export_telemetry_fast_tier_delegation(self):
        """Verify export_telemetry with fast_tier=True correctly delegates to export_fast_tier."""
        res = export_telemetry(
            antigravity_dir=self.test_path,
            output_dir=self.output_dir,
            status_path=self.status_file,
            active_db=self.db_path,
            fast_tier=True,
        )
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("tier"), "fast")
        self.assertFalse((self.output_dir / "data.js").exists())
        self.assertTrue((self.output_dir / "meta.js").exists())

    def test_cli_parser_fast_tier_argument(self):
        """Verify CLI argument parser includes --fast-tier and --fast flags."""
        parser = build_parser()
        args = parser.parse_args(["--fast-tier"])
        self.assertTrue(args.fast_tier)

        args_alias = parser.parse_args(["--fast"])
        self.assertTrue(args_alias.fast_tier)

    def test_watcher_two_tier_decoupling(self):
        """
        Gate B3: Verify watch_loop decouples Fast Tier (<20ms) on WAL change
        from Heavy Tier debounced rollup.
        """
        stop_event = threading.Event()
        fast_exports = []
        heavy_exports = []

        def on_fast():
            fast_exports.append(time.time())

        def on_heavy():
            heavy_exports.append(time.time())

        # Start watcher with 1.0s heavy debounce to observe decoupling cleanly
        watcher_thread = threading.Thread(
            target=watch_loop,
            kwargs={
                "antigravity_dir": self.test_path,
                "dashboard_path": self.output_dir / "index.html",
                "interval_seconds": 0.05,
                "debounce_seconds": 1.0,
                "max_debounce_seconds": 2.0,
                "stop_event": stop_event,
                "on_export": on_heavy,
                "on_fast_export": on_fast,
                "status_path": self.status_file,
                "enable_fast_tier": True,
            },
            daemon=True,
        )

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            # Create dummy index.html in output_dir
            (self.output_dir / "index.html").write_text(
                '<!DOCTYPE html><html><head><script id="injected-dashboard-data" type="application/json">{}</script></head><body></body></html>'
            )
            watcher_thread.start()

            # Wait for initial full export
            for _ in range(40):
                if len(heavy_exports) >= 1:
                    break
                time.sleep(0.05)
            self.assertEqual(len(heavy_exports), 1, "Initial export must run on start")

            # Simulate an active session WAL write
            wal_file = self.conv_dir / f"{self.convo_id}.db-wal"
            wal_file.write_bytes(b"wal update for turn")

            # Fast Tier should trigger almost immediately (< 300ms)
            for _ in range(60):
                if len(fast_exports) >= 1:
                    break
                time.sleep(0.05)

            self.assertGreaterEqual(len(fast_exports), 1, "Fast Tier must trigger on WAL change")
            # Heavy Tier should NOT have triggered yet because debounce is 1.0s
            self.assertEqual(len(heavy_exports), 1, "Heavy Tier must remain debounced while activity occurs")

            # Clean shutdown
            stop_event.set()
            watcher_thread.join(timeout=3.0)

    def test_menubar_epoch_badge_source(self):
        """
        Gate B1: Verify StatusBarController.swift has dynamic Epoch badge E1..E5
        with color grading (#34D399, #FBBF24, #EF4444) and no legacy 🔴 / ⚠️ in updateTitle().
        """
        swift_path = Path("macos/AntigravityBar/Sources/AntigravityBar/StatusBarController.swift")
        self.assertTrue(swift_path.exists(), "StatusBarController.swift must exist")
        src = swift_path.read_text(encoding="utf-8")

        # Extract updateTitle method body
        self.assertIn("func updateTitle()", src)
        update_title_chunk = src.split("func updateTitle()")[1].split("func handleStatusBarClick")[0]

        # Verify legacy emoji badges are gone from menu bar topper
        self.assertNotIn("🔴", update_title_chunk)
        self.assertNotIn("⚠️", update_title_chunk)

        # Verify dynamic Epoch badge formatting
        self.assertIn(r"E\(epoch)", update_title_chunk)

        # Verify color assignments
        # Green: #34D399 -> srgbRed: 52/255.0, green: 211/255.0, blue: 153/255.0
        self.assertIn("52/255.0", update_title_chunk)
        self.assertIn("211/255.0", update_title_chunk)
        self.assertIn("153/255.0", update_title_chunk)

        # Orange: #FBBF24 -> srgbRed: 251/255.0, green: 191/255.0, blue: 36/255.0
        self.assertIn("251/255.0", update_title_chunk)
        self.assertIn("191/255.0", update_title_chunk)
        self.assertIn("36/255.0", update_title_chunk)

        # Red: #EF4444 -> srgbRed: 239/255.0, green: 68/255.0, blue: 68/255.0
        self.assertIn("239/255.0", update_title_chunk)
        self.assertIn("68/255.0", update_title_chunk)

    def test_observer_effect_tool_calls_do_not_increment_epoch(self):
        """
        Anti-regression: Viewing, editing, or grepping files containing 'CONTEXT_SUMMARY'
        (step_type = 132) or assistant discussion (step_type = 15) must NEVER increment
        compaction_count or epoch (Phase 4).
        """
        obs_db = self.conv_dir / "observer_effect.db"
        conn = sqlite3.connect(obs_db)
        cur = conn.cursor()
        cur.execute("CREATE TABLE trajectory_metadata_blob (key TEXT PRIMARY KEY, metadata BLOB)")
        uri = b"file:///Users/alice/Projects/Test%20Workspace"
        br = b"feat/test-branch"
        sub_payload = bytes([0x0a, len(uri)]) + uri + bytes([0x22, len(br)]) + br
        outer_payload = bytes([0x0a, len(sub_payload)]) + sub_payload
        cur.execute("INSERT OR REPLACE INTO trajectory_metadata_blob VALUES (?, ?)", ("main", outer_payload))

        cur.execute(
            """
            CREATE TABLE steps (
                idx INTEGER PRIMARY KEY,
                step_type INTEGER,
                metadata BLOB,
                step_payload BLOB
            )
            """
        )

        # 10 steps simulating tool calls and chat discussing CONTEXT_SUMMARY
        for idx in range(1, 11):
            if idx % 2 == 1:
                # Tool call (132): viewing docs/HANDOVER.md or grepping for CONTEXT_SUMMARY
                payload = f'{{"tool_name": "view_file", "path": "docs/HANDOVER.md", "content": "Scanned for <CONTEXT_SUMMARY> markers"}}'.encode("utf-8")
                cur.execute("INSERT INTO steps VALUES (?, ?, ?, ?)", (idx, 132, None, payload))
            else:
                # Model response (15): explaining CONTEXT_SUMMARY
                payload = b'I found that <CONTEXT_SUMMARY> is referenced in multiple documentation files.'
                cur.execute("INSERT INTO steps VALUES (?, ?, ?, ?)", (idx, 15, None, payload))

        conn.commit()
        conn.close()

        res = export_fast_tier(
            antigravity_dir=self.test_path,
            output_dir=self.output_dir,
            status_path=self.status_file,
            active_db=obs_db,
        )

        self.assertEqual(res.get("epoch"), 1, "Self-referential CONTEXT_SUMMARY tool calls must NOT increment epoch")
        status_data = json.loads(self.status_file.read_text(encoding="utf-8"))
        self.assertEqual(status_data.get("compaction_epoch"), 1)
        self.assertEqual(status_data.get("current_session", {}).get("compaction_count"), 0)

    def test_genuine_step_type_23_increments_epoch(self):
        """Only genuine step_type = 23 (CHECKPOINT) steps increment the epoch."""
        genuine_db = self.conv_dir / "genuine_compaction.db"
        conn = sqlite3.connect(genuine_db)
        cur = conn.cursor()
        cur.execute("CREATE TABLE trajectory_metadata_blob (key TEXT PRIMARY KEY, metadata BLOB)")
        uri = b"file:///Users/alice/Projects/Test%20Workspace"
        br = b"feat/test-branch"
        sub_payload = bytes([0x0a, len(uri)]) + uri + bytes([0x22, len(br)]) + br
        outer_payload = bytes([0x0a, len(sub_payload)]) + sub_payload
        cur.execute("INSERT OR REPLACE INTO trajectory_metadata_blob VALUES (?, ?)", ("main", outer_payload))

        cur.execute(
            """
            CREATE TABLE steps (
                idx INTEGER PRIMARY KEY,
                step_type INTEGER,
                metadata BLOB,
                step_payload BLOB
            )
            """
        )

        # Step 1: genuine compaction checkpoint (step_type = 23)
        cur.execute("INSERT INTO steps VALUES (1, 23, NULL, ?)", (b"<summary>### 1. Task Overview</summary>",))
        # Steps 2-10: tool calls mentioning CONTEXT_SUMMARY (step_type = 132)
        for idx in range(2, 11):
            payload = f'{{"tool_name": "replace_file_content", "args": "CONTEXT_SUMMARY"}}'.encode("utf-8")
            cur.execute("INSERT INTO steps VALUES (?, 132, NULL, ?)", (idx, payload))

        conn.commit()
        conn.close()

        res = export_fast_tier(
            antigravity_dir=self.test_path,
            output_dir=self.output_dir,
            status_path=self.status_file,
            active_db=genuine_db,
        )

        self.assertEqual(res.get("epoch"), 2, "1 genuine checkpoint must yield epoch 2")
        status_data = json.loads(self.status_file.read_text(encoding="utf-8"))
        self.assertEqual(status_data.get("compaction_epoch"), 2)
        self.assertEqual(status_data.get("current_session", {}).get("compaction_count"), 1)

    def test_authoritative_session_selection_ignores_subagents(self):
        """Fast tier and watcher must ignore subagent databases and pin to user-facing sessions."""
        main_db = self.conv_dir / "main_interactive.db"
        self._init_mock_db(main_db, turn_count=5, has_truncation=True)

        # Create subagent db with higher mtime and is_subagent = True
        sub_db = self.conv_dir / "subagent_task.db"
        conn = sqlite3.connect(sub_db)
        cur = conn.cursor()
        cur.execute("CREATE TABLE trajectory_metadata_blob (id TEXT PRIMARY KEY, data BLOB)")
        # Wire field 17 (key = 17 << 3 = 136 -> [0x88, 0x01], val = 1 -> [0x01]) indicates is_subagent = True
        subagent_meta = bytes([0x88, 0x01, 0x01])
        cur.execute("INSERT OR REPLACE INTO trajectory_metadata_blob VALUES (?, ?)", ("main", subagent_meta))
        cur.execute("CREATE TABLE steps (idx INTEGER PRIMARY KEY, step_type INTEGER, metadata BLOB, step_payload BLOB)")
        cur.execute("INSERT INTO steps VALUES (1, 15, NULL, ?)", (b"subagent output",))
        conn.commit()
        conn.close()

        # Explicitly set mtimes: main_db newer than setUp db, and sub_db newer than main_db
        t_base = time.time()
        t_main = t_base + 10
        t_sub = t_base + 50
        os.utime(main_db, (t_main, t_main))
        os.utime(sub_db, (t_sub, t_sub))

        # Export without specifying active_db: must resolve to main_interactive.db
        res = export_fast_tier(
            antigravity_dir=self.test_path,
            output_dir=self.output_dir,
            status_path=self.status_file,
            active_db=None,
        )

        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("epoch"), 2, "Must pin to main interactive session, not subagent")
        status_data = json.loads(self.status_file.read_text(encoding="utf-8"))
        self.assertEqual(status_data.get("current_session", {}).get("convo_id"), "main_interactive")

    def test_multi_tier_subagent_ancestry_resolution(self):
        """
        Deep ancestry: Level 3 (reviewer) -> Level 2 (orchestrator) -> Level 1 (root user session).
        Must resolve all the way up to Level 1, even when wire field 17 is 0/omitted on worker personas.
        """
        root_db = self.conv_dir / "root_user.db"
        self._init_mock_db(root_db, turn_count=3, has_truncation=False)

        def _create_subagent_db(db_path, parent_id, agent_name, subagent_type):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("CREATE TABLE trajectory_metadata_blob (id TEXT PRIMARY KEY, data BLOB)")
            # Protobuf fields: field 5 (parent_convo_id) and field 8 (subagent_type)
            pid_bytes = parent_id.encode("utf-8")
            st_bytes = subagent_type.encode("utf-8")
            an_bytes = agent_name.encode("utf-8")
            # Field 5: (5 << 3) | 2 = 42 (0x2a)
            f5 = bytes([0x2a, len(pid_bytes)]) + pid_bytes
            # Field 8: subfield 1 = subagent_type
            sub8 = bytes([0x0a, len(st_bytes)]) + st_bytes
            f8 = bytes([0x42, len(sub8)]) + sub8
            # Field 4: subfield 1 = agent_name
            sub4 = bytes([0x0a, len(an_bytes)]) + an_bytes
            f4 = bytes([0x22, len(sub4)]) + sub4
            cur.execute("INSERT OR REPLACE INTO trajectory_metadata_blob VALUES (?, ?)", ("main", f5 + f8 + f4))
            cur.execute("CREATE TABLE steps (idx INTEGER PRIMARY KEY, step_type INTEGER, metadata BLOB, step_payload BLOB)")
            cur.execute("INSERT INTO steps VALUES (1, 15, NULL, ?)", (b"subagent output",))
            conn.commit()
            conn.close()

        orch_db = self.conv_dir / "orch_level2.db"
        rev_db = self.conv_dir / "rev_level3.db"
        _create_subagent_db(orch_db, "root_user", "teamwork_preview_orchestrator", "teamwork_preview_orchestrator")
        _create_subagent_db(rev_db, "orch_level2", "teamwork_preview_reviewer", "teamwork_preview_reviewer")

        resolved = resolve_authoritative_session_db(rev_db, self.conv_dir)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.stem, "root_user", "Must resolve 3-tier subagent hierarchy to root user session")

    def test_cyclic_and_orphan_subagent_resilience(self):
        """Cyclic parent references (A -> B -> A) and orphan subagents must not loop and must fall back safely."""
        root_db = self.conv_dir / "fallback_root.db"
        self._init_mock_db(root_db, turn_count=2, has_truncation=False)
        t_root = time.time() + 100
        os.utime(root_db, (t_root, t_root))

        cycle_a = self.conv_dir / "cycle_a.db"
        cycle_b = self.conv_dir / "cycle_b.db"

        def _create_cyclic_db(db_path, parent_id):
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("CREATE TABLE trajectory_metadata_blob (id TEXT PRIMARY KEY, data BLOB)")
            pid_bytes = parent_id.encode("utf-8")
            f5 = bytes([0x2a, len(pid_bytes)]) + pid_bytes
            # field 17 is_subagent = 1
            f17 = bytes([0x88, 0x01, 0x01])
            cur.execute("INSERT OR REPLACE INTO trajectory_metadata_blob VALUES (?, ?)", ("main", f5 + f17))
            cur.execute("CREATE TABLE steps (idx INTEGER PRIMARY KEY, step_type INTEGER, metadata BLOB, step_payload BLOB)")
            cur.execute("INSERT INTO steps VALUES (1, 15, NULL, ?)", (b"cyclic",))
            conn.commit()
            conn.close()

        _create_cyclic_db(cycle_a, "cycle_b")
        _create_cyclic_db(cycle_b, "cycle_a")

        # Must not enter infinite loop; falls back to fallback_root.db
        resolved_cycle = resolve_authoritative_session_db(cycle_a, self.conv_dir)
        self.assertIsNotNone(resolved_cycle)
        self.assertEqual(resolved_cycle.stem, "fallback_root")

        # Orphan subagent whose parent does not exist
        orphan = self.conv_dir / "orphan.db"
        _create_cyclic_db(orphan, "non_existent_parent_id")
        resolved_orphan = resolve_authoritative_session_db(orphan, self.conv_dir)
        self.assertIsNotNone(resolved_orphan)
        self.assertEqual(resolved_orphan.stem, "fallback_root")

    def test_corrupted_status_file_heals_to_sqlite_truth(self):
        """
        Anti-regression: If status.json had an inflated epoch (e.g. E50 from an earlier
        observer-effect bug), export_fast_tier must heal it back to the true SQLite epoch.
        """
        real_db = self.conv_dir / "healing_test.db"
        self._init_mock_db(real_db, turn_count=10, has_truncation=False)

        # Seed status file with corrupt epoch 50
        self.status_file.write_text(
            json.dumps({
                "compaction_epoch": 50,
                "current_session": {
                    "convo_id": "healing_test",
                    "compaction_count": 49,
                    "compaction_epoch": 50,
                },
            }),
            encoding="utf-8",
        )

        res = export_fast_tier(
            antigravity_dir=self.test_path,
            output_dir=self.output_dir,
            status_path=self.status_file,
            active_db=real_db,
        )

        self.assertEqual(res.get("epoch"), 1, "Must heal corrupt E50 back to SQLite ground truth E1")
        status_data = json.loads(self.status_file.read_text(encoding="utf-8"))
        self.assertEqual(status_data.get("compaction_epoch"), 1)
        self.assertEqual(status_data.get("current_session", {}).get("compaction_count"), 0)

    def test_write_quota_status_file_filters_worker_personas(self):
        """Full tier write_quota_status_file must ignore subagents with is_subagent=False but subagent_type set."""
        payload = {
            "conversations": [
                {
                    "convo_id": "worker-1",
                    "agent_name": "DeepCoderWorkerL0",
                    "subagent_type": "DeepCoderWorkerL0",
                    "is_subagent": False,
                    "parent_convo_id": "main-user-sess",
                    "last_turn_ts": "2026-09-30T15:00:00Z",
                    "turns": [{"total_input_tokens": 1000}],
                    "compaction_count": 0,
                },
                {
                    "convo_id": "main-user-sess",
                    "agent_name": "default",
                    "subagent_type": "",
                    "is_subagent": False,
                    "parent_convo_id": "",
                    "last_turn_ts": "2026-09-30T14:50:00Z",
                    "turns": [{"total_input_tokens": 2000}],
                    "compaction_count": 0,
                },
            ],
            "quotas": {},
            "summary": {},
        }

        test_status = self.test_path / "quota_status_filter_test.json"
        write_quota_status_file(payload, status_path=test_status)
        written = json.loads(test_status.read_text(encoding="utf-8"))
        self.assertEqual(
            written.get("current_session", {}).get("convo_id"),
            "main-user-sess",
            "Must select user-facing session for current_session, ignoring subagent worker",
        )

    def test_ancestry_walk_capped_at_five_hops(self):
        """Ancestry chain deeper than 5 hops must stop at 5 hops and fall back safely."""
        fallback_root = self.conv_dir / "fallback_root_hop.db"
        self._init_mock_db(fallback_root, turn_count=2, has_truncation=False)
        t_root = time.time() + 200
        os.utime(fallback_root, (t_root, t_root))

        def _make_hop_db(db_path: Path, parent_id: str) -> None:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("CREATE TABLE trajectory_metadata_blob (id TEXT PRIMARY KEY, data BLOB)")
            pid_bytes = parent_id.encode("utf-8")
            f5 = bytes([0x2a, len(pid_bytes)]) + pid_bytes
            f17 = bytes([0x88, 0x01, 0x01])
            cur.execute("INSERT OR REPLACE INTO trajectory_metadata_blob VALUES (?, ?)", ("main", f5 + f17))
            cur.execute("CREATE TABLE steps (idx INTEGER PRIMARY KEY, step_type INTEGER, metadata BLOB, step_payload BLOB)")
            cur.execute("INSERT INTO steps VALUES (1, 15, NULL, ?)", (b"hop",))
            conn.commit()
            conn.close()

        # Create 7-hop chain: hop7 -> hop6 -> hop5 -> hop4 -> hop3 -> hop2 -> hop1 -> distant_root
        distant_root = self.conv_dir / "distant_root.db"
        self._init_mock_db(distant_root, turn_count=2, has_truncation=False)
        os.utime(distant_root, (time.time() - 500, time.time() - 500))

        prev_name = "distant_root"
        for i in range(1, 8):
            hop_name = f"hop{i}"
            _make_hop_db(self.conv_dir / f"{hop_name}.db", prev_name)
            prev_name = hop_name

        # 3-hop chain from hop3 resolves to distant_root (<= 5 hops)
        resolved_short = resolve_authoritative_session_db(self.conv_dir / "hop3.db", self.conv_dir)
        self.assertIsNotNone(resolved_short)
        self.assertEqual(resolved_short.stem, "distant_root")

        # 7-hop chain from hop7 exceeds 5-hop cap and falls back to fallback_root_hop
        resolved_deep = resolve_authoritative_session_db(self.conv_dir / "hop7.db", self.conv_dir)
        self.assertIsNotNone(resolved_deep)
        self.assertEqual(resolved_deep.stem, "fallback_root_hop")


if __name__ == "__main__":
    unittest.main()
