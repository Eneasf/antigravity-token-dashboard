"""
Concurrency and Export Advisory Lock Verification Test Suite (ADR-047 / Milestone 49 / C1).

Validates:
1. Two concurrent threads attempting export against the same output directory:
   exactly one produces output, the other returns the skip code.
2. The output data.js is byte-identical to a single un-contended export run.
3. Subprocess CLI execution while lock is held exits 0 with '[skip] export already running'.
4. Lock is released cleanly upon completion or failure.
5. Manual refresh signal (.antigravity_refresh_requested) is consumed and triggers export.
"""

import contextlib
from datetime import datetime
import fcntl
import io
import os
from pathlib import Path
import shutil
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

from scripts.export_dashboard import export_telemetry
import scripts.export_dashboard as export_mod
from scripts.watch_telemetry import watch_loop

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "antigravity"
REF_TIME = datetime.fromisoformat("2026-09-05T14:30:00+00:00")


class TestExportLock(unittest.TestCase):
    """Test suite for exclusive export lock, atomic temporary files, and refresh signaling."""

    def setUp(self):
        self.temp_dirs = []
        self.temp_path = self._make_temp_dir()

    def tearDown(self):
        for d in self.temp_dirs:
            if Path(d).exists():
                shutil.rmtree(d, ignore_errors=True)

    def _make_temp_dir(self) -> Path:
        d = Path(tempfile.mkdtemp(prefix="agy_lock_test_"))
        self.temp_dirs.append(d)
        return d

    def test_concurrent_threads_export_lock(self):
        """
        Starting two export_telemetry() calls in threads against the same dir:
        exactly one produces output, the other returns the skip code.
        data.js must be byte-identical to a single un-contended run.
        """
        output_dir = self._make_temp_dir()

        thread1_holding = threading.Event()
        thread2_completed = threading.Event()
        results = [None, None]

        orig_load_pricing = export_mod.load_pricing

        def slow_load_pricing():
            pricing = orig_load_pricing()
            thread1_holding.set()
            thread2_completed.wait(timeout=5.0)
            return pricing

        def run_thread1():
            try:
                export_mod.load_pricing = slow_load_pricing
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    results[0] = export_telemetry(
                        antigravity_dir=FIXTURE_DIR,
                        output_dir=output_dir,
                        no_live_quota=True,
                        reference_time=REF_TIME,
                    )
            finally:
                export_mod.load_pricing = orig_load_pricing

        def run_thread2():
            # Wait until thread 1 has acquired the lock and entered slow_load_pricing
            thread1_holding.wait(timeout=5.0)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                results[1] = export_telemetry(
                    antigravity_dir=FIXTURE_DIR,
                    output_dir=output_dir,
                    no_live_quota=True,
                    reference_time=REF_TIME,
                )
            thread2_completed.set()

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            t1 = threading.Thread(target=run_thread1)
            t2 = threading.Thread(target=run_thread2)

            t1.start()
            t2.start()

            t1.join(timeout=10.0)
            t2.join(timeout=10.0)

        # Verify exactly one produced output, and the other returned skip code
        r1, r2 = results[0], results[1]
        self.assertIsNotNone(r1, "Thread 1 should return a result dictionary")
        self.assertIsNotNone(r2, "Thread 2 should return a result dictionary")

        self.assertIn("summary", r1, "Thread 1 must produce full telemetry output")
        self.assertEqual(r2.get("status"), "skipped", "Thread 2 must return skip status")
        self.assertEqual(r2.get("reason"), "lock_held", "Thread 2 must skip due to lock_held")

        # Run single un-contended export in clean directory
        single_dir = self._make_temp_dir()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            export_telemetry(
                antigravity_dir=FIXTURE_DIR,
                output_dir=single_dir,
                no_live_quota=True,
                reference_time=REF_TIME,
            )

        # data.js must be byte-identical to single run
        t1_data_js = (output_dir / "data.js").read_bytes()
        single_data_js = (single_dir / "data.js").read_bytes()
        self.assertEqual(t1_data_js, single_data_js, "data.js must be byte-identical to single run")
        self.assertGreater(len(t1_data_js), 0)

    def test_cli_skip_when_lock_held(self):
        """CLI exporter must exit 0 with '[skip] export already running' when lock is held."""
        output_dir = self._make_temp_dir()
        lock_file_path = output_dir / ".export.lock"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Hold the lock exclusively in this process
        with open(lock_file_path, "a+") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            f.seek(0)
            f.truncate(0)
            f.write(f"{os.getpid()}\n")
            f.flush()

            # Execute CLI in subprocess
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts" / "export_dashboard.py"),
                "--antigravity-dir",
                str(FIXTURE_DIR),
                "--no-live-quota",
                "--output-dir",
                str(output_dir),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
            self.assertEqual(proc.returncode, 0, f"Expected exit 0, got {proc.returncode}: {proc.stderr}")
            self.assertIn("[skip] export already running", proc.stdout)

    def test_lock_released_after_export(self):
        """After export completes, subsequent exports against same dir must succeed."""
        output_dir = self._make_temp_dir()

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            res1 = export_telemetry(
                antigravity_dir=FIXTURE_DIR,
                output_dir=output_dir,
                no_live_quota=True,
                reference_time=REF_TIME,
            )
        self.assertIn("summary", res1)

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            res2 = export_telemetry(
                antigravity_dir=FIXTURE_DIR,
                output_dir=output_dir,
                no_live_quota=True,
                reference_time=REF_TIME,
            )
        self.assertIn("summary", res2)

    def test_zero_static_tmp_files_left(self):
        """No static data.js.tmp or .tmp leftovers should exist in output dir."""
        output_dir = self._make_temp_dir()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            export_telemetry(
                antigravity_dir=FIXTURE_DIR,
                output_dir=output_dir,
                no_live_quota=True,
                reference_time=REF_TIME,
            )
        self.assertFalse((output_dir / "data.js.tmp").exists())
        self.assertFalse((output_dir / "data.json.tmp").exists())
        self.assertFalse((output_dir / "meta.js.tmp").exists())
        self.assertFalse((output_dir / "meta.json.tmp").exists())

    def test_watcher_manual_refresh_signal(self):
        """Watcher loop must detect ~/.antigravity_refresh_requested, delete it, and export."""
        output_dir = self._make_temp_dir()
        signal_file = output_dir / ".test_refresh_signal"
        dashboard_html = output_dir / "index.html"
        dashboard_html.write_text(
            '<html><head><script id="injected-dashboard-data" type="application/json">{}</script></head><body></body></html>',
            encoding="utf-8",
        )
        empty_log = output_dir / "empty.log"
        empty_log.write_text("", encoding="utf-8")

        stop_event = threading.Event()
        exports_done = []

        # Touch signal before or during loop
        signal_file.write_text("refresh", encoding="utf-8")
        self.assertTrue(signal_file.exists())

        def on_export():
            exports_done.append(time.time())
            if len(exports_done) >= 2:
                stop_event.set()

        def run_watcher():
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with patch("src.quota_client.fetch_live_quota_summary", return_value=None):
                    watch_loop(
                        antigravity_dir=FIXTURE_DIR,
                        dashboard_path=dashboard_html,
                        log_path=empty_log,
                        interval_seconds=0.05,
                        debounce_seconds=0.2,
                        stop_event=stop_event,
                        on_export=on_export,
                        refresh_signal_path=signal_file,
                        status_path=self.temp_path / "status.json",
                    )

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            t = threading.Thread(target=run_watcher)
            t.start()

            # Wait for thread to finish
            t.join(timeout=10.0)
            stop_event.set()

        # Signal file must have been unlinked
        self.assertFalse(signal_file.exists(), "Signal file must be unlinked upon detection")
        self.assertGreaterEqual(len(exports_done), 2, "Should perform initial export + manual refresh export")


if __name__ == "__main__":
    unittest.main()
