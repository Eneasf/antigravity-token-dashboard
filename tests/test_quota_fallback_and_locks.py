"""Regression tests for Vault quota fallback, shared status locking, and cold-start watcher fast-tier pass."""

import contextlib
import datetime
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.export_dashboard import (
    export_fast_tier,
    export_telemetry,
    write_quota_status_file,
)
import scripts.watch_telemetry as watch_mod
from src.vault import sync_quota_snapshot_to_vault
from src.vault_schema import init_vault


class TestQuotaFallbackAndLocks(unittest.TestCase):
    """Verify outage resilience for quota fallback, status.json locking, and startup latency."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.ag_dir = self.temp_path / "antigravity"
        self.conv_dir = self.ag_dir / "conversations"
        self.conv_dir.mkdir(parents=True)

        self.dash_dir = self.temp_path / "dashboard"
        self.dash_dir.mkdir(parents=True)
        self.index_html = self.dash_dir / "index.html"
        self.index_html.write_text(
            '<!DOCTYPE html><html><head></head><body><script id="injected-dashboard-data" type="application/json">{}</script></body></html>',
            encoding="utf-8",
        )
        self.empty_log = self.temp_path / "language_server.log"
        self.empty_log.write_text("", encoding="utf-8")

        self.status_file = self.temp_path / "quota_status.json"
        self.fake_default_status = self.temp_path / "fake_home" / ".antigravity_quota_status.json"
        self.fake_default_status.parent.mkdir(parents=True, exist_ok=True)
        self.fake_refresh_signal = self.temp_path / "fake_home" / ".antigravity_refresh_requested"

        self.patchers = [
            patch("scripts.export_dashboard.DEFAULT_STATUS_PATH", self.fake_default_status),
            patch("scripts.watch_telemetry.DEFAULT_STATUS_PATH", self.fake_default_status),
            patch("scripts.watch_telemetry.DEFAULT_REFRESH_SIGNAL_PATH", self.fake_refresh_signal),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in self.patchers:
            p.stop()
        self.temp_dir.cleanup()

    def _copy_fixture_db(self, name: str = "11111111-1111-1111-1111-111111111111.db") -> Path:
        src = REPO_ROOT / "tests" / "fixtures" / "antigravity" / "conversations" / name
        dst = self.conv_dir / name
        shutil.copy2(src, dst)
        return dst

    def test_vault_fallback_when_live_quota_unavailable(self):
        """When live RPC is unavailable (no_live_quota=False), active Vault weekly snapshot anchors cycle bounds."""
        self._copy_fixture_db()
        vault_file = self.ag_dir / "antigravity_vault.db"
        init_vault(vault_file).close()

        sync_quota_snapshot_to_vault(
            {
                "available": True,
                "gemini_weekly": {
                    "remaining_pct": 85.1,
                    "used_pct": 14.9,
                    "reset_time": "2026-11-14T09:00:28Z",
                },
                "gemini_5h": {
                    "remaining_pct": 40.0,
                    "used_pct": 60.0,
                    "reset_time": "2026-11-12T16:30:00Z",
                },
            },
            vault_path=vault_file,
            timestamp_utc="2026-11-12T11:50:00+00:00",
        )

        # Nov 13 12:35Z: weekly window (Nov 14 09:00:28Z) is still active, while 5h window (Nov 12 16:30Z) expired.
        ref_dt = datetime.datetime(2026, 11, 13, 12, 35, 0, tzinfo=datetime.timezone.utc)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            payload = export_telemetry(
                antigravity_dir=self.ag_dir,
                dashboard_path=self.index_html,
                log_path=self.empty_log,
                status_path=self.status_file,
                reference_time=ref_dt,
                no_live_quota=False,
            )

        gem = payload["quotas"]["providers"]["gemini"]
        self.assertEqual(gem["weekly"]["used_pct"], 14.9)
        self.assertEqual(gem["weekly"]["remaining_pct"], 85.1)
        self.assertEqual(gem["weekly"]["reset_time"], "2026-11-14T09:00:28Z")
        self.assertEqual(gem["weekly"]["weekly_reset_utc"], "2026-11-14T09:00:28+00:00")
        self.assertFalse(gem["five_hour"].get("live_desktop_sync", False))

        status_data = json.loads(self.status_file.read_text(encoding="utf-8"))
        self.assertEqual(status_data["gemini_weekly_pct"], 14.9)
        self.assertEqual(status_data["gemini_weekly_remaining_pct"], 85.1)
        self.assertEqual(status_data["weekly_reset_utc"], "2026-11-14T09:00:28+00:00")

        # Expired snapshot must NOT anchor future cycle after reset
        after_reset_dt = datetime.datetime(2026, 11, 14, 10, 0, 0, tzinfo=datetime.timezone.utc)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            expired_payload = export_telemetry(
                antigravity_dir=self.ag_dir,
                dashboard_path=self.index_html,
                log_path=self.empty_log,
                status_path=self.status_file,
                reference_time=after_reset_dt,
                no_live_quota=False,
            )
        self.assertFalse(expired_payload["quotas"]["providers"]["gemini"]["weekly"].get("live_desktop_sync", False))

    def test_concurrent_heartbeat_and_status_write_preserve_fields(self):
        """Concurrent update_watcher_heartbeat and write_quota_status_file must serialize without lost updates."""
        self.status_file.write_text(
            json.dumps({
                "status": "SAFE_IN_QUOTA",
                "gemini_weekly_remaining_pct": 56.5,
                "watcher": {"pid": 111, "heartbeat_utc": "2026-11-13T10:00:00+00:00"},
            }),
            encoding="utf-8",
        )

        payload = {
            "summary": {"subscription_status": "SAFE_IN_QUOTA"},
            "quotas": {
                "providers": {
                    "gemini": {
                        "five_hour": {"used_pct": 5.0},
                        "weekly": {"used_pct": 14.9},
                        "runway": {"burst_cooldown_active": False},
                    },
                    "claude_gpt": {"five_hour": {"used_pct": 0.0}, "weekly": {"used_pct": 0.0}},
                }
            },
            "conversations": [],
            "temporal": {"evaluation_time_utc": "2026-11-13T10:05:00+00:00"},
        }

        t1_read_done = threading.Event()
        t2_done = threading.Event()
        orig_patch_tracks = watch_mod.build_or_patch_status_tracks

        def slow_patch_tracks(status_dict):
            orig_patch_tracks(status_dict)
            t1_read_done.set()
            t2_done.wait(timeout=0.25)

        t1_result = []

        def run_heartbeat():
            t1_result.append(
                watch_mod.update_watcher_heartbeat(
                    status_path=self.status_file,
                    pid=222,
                    heartbeat_utc="2026-11-13T10:05:00+00:00",
                )
            )

        with patch("scripts.watch_telemetry.build_or_patch_status_tracks", side_effect=slow_patch_tracks):
            t1 = threading.Thread(target=run_heartbeat)
            t1.start()
            self.assertTrue(t1_read_done.wait(timeout=2.0), "Heartbeat thread did not reach read-modify section")

            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                write_quota_status_file(payload, status_path=self.status_file)
            t2_done.set()
            t1.join(timeout=2.0)

        self.assertEqual(t1_result, [True])
        final = json.loads(self.status_file.read_text(encoding="utf-8"))
        self.assertEqual(final.get("gemini_weekly_remaining_pct"), 85.1)
        self.assertEqual((final.get("watcher") or {}).get("pid"), 222)

    def test_cold_start_runs_fast_tier_before_heavy_export(self):
        """watch_loop must run fast-tier status before blocking on initial export, and log early status errors."""
        self._copy_fixture_db()
        call_order = []

        def fake_fast(**kwargs):
            call_order.append("fast")
            return {"status": "success", "tier": "fast", "duration_ms": 2.0, "epoch": 1}

        def fake_heavy(**kwargs):
            call_order.append("heavy")
            return {"status": "ok"}

        with (
            patch("scripts.watch_telemetry.export_fast_tier", side_effect=fake_fast),
            patch("scripts.watch_telemetry.export_telemetry", side_effect=fake_heavy),
        ):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                watch_mod.watch_loop(
                    antigravity_dir=self.ag_dir,
                    dashboard_path=self.index_html,
                    log_path=self.empty_log,
                    status_path=self.status_file,
                    refresh_signal_path=self.fake_refresh_signal,
                    once=True,
                    enable_fast_tier=True,
                )

        self.assertGreaterEqual(len(call_order), 2)
        self.assertEqual(call_order[0], "fast")
        self.assertEqual(call_order[1], "heavy")

        # Early write_quota_status_file failures must log warning instead of silent swallow
        with patch("scripts.export_dashboard.write_quota_status_file", side_effect=[OSError("disk busy"), self.status_file]):
            with self.assertLogs("scripts.export_dashboard", level="WARNING") as log_ctx:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    export_telemetry(
                        antigravity_dir=self.ag_dir,
                        dashboard_path=self.index_html,
                        log_path=self.empty_log,
                        status_path=self.status_file,
                        no_live_quota=True,
                    )
        self.assertTrue(
            any("Early status hook write failed" in msg for msg in log_ctx.output),
            f"Expected warning log for early status hook failure, got: {log_ctx.output}",
        )

    def test_cross_process_flock_blocks_concurrent_writer(self):
        """Verify subprocess acquiring status_file_lock blocks conflicting in-process fast-tier write until released."""
        db_path = self._copy_fixture_db()
        self.status_file.write_text(json.dumps({"status": "SAFE_IN_QUOTA"}), encoding="utf-8")

        lock_script = (
            "import sys, time\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
            "from scripts.export_dashboard import status_file_lock\n"
            f"target = Path({str(self.status_file)!r})\n"
            "with status_file_lock(target):\n"
            "    print('LOCKED', flush=True)\n"
            "    time.sleep(0.25)\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", lock_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            ready = proc.stdout.readline().strip()
            self.assertEqual(ready, "LOCKED")
            t0 = time.monotonic()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                res = export_fast_tier(
                    antigravity_dir=self.ag_dir,
                    dashboard_path=self.index_html,
                    status_path=self.status_file,
                    active_db=db_path,
                    log_path=self.empty_log,
                )
            elapsed = time.monotonic() - t0
            self.assertEqual(res.get("status"), "success")
            self.assertGreaterEqual(elapsed, 0.15)
        finally:
            proc.wait(timeout=5)
            proc.stdout.close()
            proc.stderr.close()


if __name__ == "__main__":
    unittest.main()
