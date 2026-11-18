#!/usr/bin/env python3
"""
Near real-time telemetry watcher daemon.

Monitors Antigravity SQLite Write-Ahead Logs (*.db-wal), conversation databases,
and runtime logs (language_server.log), automatically refreshing dashboard/index.html
with debounced export triggers when generation turns occur.
"""

import argparse
import datetime
import gc
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from typing import Callable, Dict, Optional, Tuple, Union
import uuid

# Ensure repository root is on Python module search path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)


from antigravity_telemetry import read_single_conversation_metadata
from scripts.export_dashboard import (
    export_telemetry,
    export_fast_tier,
    build_or_patch_status_tracks,
    status_file_lock,
    DEFAULT_STATUS_PATH,
    is_subagent_conversation,
    resolve_authoritative_session_db,
)
from src.log_reader import DEFAULT_LOG_PATH
from src.telemetry_reader import DEFAULT_ANTIGRAVITY_DIR

DEFAULT_REFRESH_SIGNAL_PATH = Path.home() / ".antigravity_refresh_requested"


def update_watcher_heartbeat(
    status_path: Optional[Path] = None,
    pid: Optional[int] = None,
    heartbeat_utc: Optional[str] = None,
) -> bool:
    """Atomically update the watcher heartbeat {pid, heartbeat_utc} in ~/.antigravity_quota_status.json."""
    target = Path(status_path) if status_path is not None else DEFAULT_STATUS_PATH
    tmp_path = None
    try:
        with status_file_lock(target):
            data = {}
            if target.exists():
                try:
                    with open(target, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict):
                            data = loaded
                except Exception:
                    data = {}

            current_pid = pid if pid is not None else os.getpid()
            current_time = (
                heartbeat_utc
                if heartbeat_utc is not None
                else datetime.datetime.now(datetime.timezone.utc).isoformat()
            )
            data["watcher"] = {
                "pid": current_pid,
                "heartbeat_utc": current_time,
            }
            if data.get("schema_version") != 2 or not isinstance(data.get("tracks"), list):
                build_or_patch_status_tracks(data)

            nonce = uuid.uuid4().hex[:8]
            tmp_path = target.parent / f".{target.name}.tmp.{os.getpid()}_{threading.get_ident()}_{nonce}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
            os.replace(tmp_path, target)
            return True
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        return False


def check_status_health(
    status_path: Union[Path, str],
    expected_dashboard_path: Union[Path, str],
) -> tuple[bool, str]:
    """Validate status JSON file health and ensure dashboard_path matches expected target."""
    status_path = Path(status_path)
    if not status_path.exists():
        return (False, "status file does not exist")
    try:
        with open(status_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return (False, "invalid JSON")
    except Exception:
        return (False, "invalid JSON")

    if "dashboard_path" not in data or not isinstance(data["dashboard_path"], str):
        return (False, "dashboard_path missing")

    file_dash = Path(data["dashboard_path"])
    if not file_dash.exists():
        return (False, f"dashboard_path target does not exist ({file_dash})")

    if file_dash.resolve() != Path(expected_dashboard_path).resolve():
        return (False, f"dashboard_path mismatch ({file_dash} != {Path(expected_dashboard_path).resolve()})")

    return (True, "healthy")


def start_heartbeat_thread(
    status_path: Optional[Path] = None,
    stop_event: Optional[threading.Event] = None,
    interval: float = 10.0,
) -> threading.Thread:
    """
    Spawn a background daemon thread that periodically calls update_watcher_heartbeat()
    every interval seconds, preventing heartbeat starvation during lengthy exports.
    """
    effective_path = status_path if status_path is not None else DEFAULT_STATUS_PATH
    event = stop_event if stop_event is not None else threading.Event()

    def _worker():
        while not event.is_set():
            update_watcher_heartbeat(effective_path)
            event.wait(timeout=interval)

    t = threading.Thread(target=_worker, daemon=True, name="telemetry-heartbeat")
    t.start()
    return t


def sync_vault_telemetry(antigravity_dir: Path, log_path: Optional[Path] = None) -> None:
    """Safely synchronize runtime logs to the local Vault (conversation sync handled exclusively by export_telemetry)."""
    try:
        from src.log_archiver import archive_logs
        archive_logs(log_path=log_path)
    except (sqlite3.Error, OSError) as e:
        sys.stderr.write(f"[!] Warning: watcher log archive failed: {e}\n")
    except Exception as e:
        sys.stderr.write(f"[!] Unexpected error in watcher log archive: {e}\n")


def get_snapshot(
    conv_dir: Path,
    log_path: Optional[Path] = None,
) -> Dict[str, Tuple[int, int]]:
    """
    Return dict of {filepath: (mtime_ns, size)} for conversation DBs/WALs and runtime log.
    Tolerates live file rotation, deletions, and transient permissions errors.
    """
    snapshot: Dict[str, Tuple[int, int]] = {}

    if conv_dir.exists():
        try:
            for entry in os.scandir(conv_dir):
                name = entry.name
                if name.endswith(".db") or name.endswith(".db-wal") or name.endswith(".db-shm"):
                    try:
                        st = entry.stat()
                        snapshot[entry.path] = (st.st_mtime_ns, st.st_size)
                    except OSError:
                        continue
        except OSError:
            pass

    if log_path and log_path.exists():
        try:
            st = log_path.stat()
            snapshot[str(log_path.resolve())] = (st.st_mtime_ns, st.st_size)
        except OSError:
            pass

    return snapshot


def snapshots_differ(
    snap_a: Dict[str, Tuple[int, int]],
    snap_b: Dict[str, Tuple[int, int]],
) -> bool:
    """Return True if two filesystem snapshots differ in keys or (mtime, size) tuples."""
    if len(snap_a) != len(snap_b):
        return True
    for k, v in snap_a.items():
        if snap_b.get(k) != v:
            return True
    return False


class DebounceController:
    """
    Coalesces rapid successive modification events into a single settled export.
    Prevents exporter thrashing during rapid multi-turn generation streams.
    """

    def __init__(self, settle_window: float = 2.0, max_delay: float = 10.0, max_settle_window: Optional[float] = None):
        self.base_settle_window = max(0.1, float(settle_window))
        self.settle_window = self.base_settle_window
        self.max_delay = max(self.settle_window, float(max_delay))
        self.max_settle_window = float(max_settle_window) if max_settle_window is not None else max(10.0, self.base_settle_window)
        self.pending = False
        self.first_change_time: Optional[float] = None
        self.last_change_time: Optional[float] = None

    MAX_SETTLE_WINDOW: float = 10.0

    def update_settle_window(self, last_duration: float) -> None:
        """Adapt settle window to measured export duration so rapid exports don't thrash."""
        upper = getattr(self, "max_settle_window", self.MAX_SETTLE_WINDOW)
        self.settle_window = min(upper, max(self.base_settle_window, float(last_duration)))
        self.max_delay = max(self.settle_window * 2.0, self.max_delay)

    def notify_change(self, now: Optional[float] = None) -> None:
        """Mark an activity event."""
        current = time.time() if now is None else now
        if not self.pending:
            self.pending = True
            self.first_change_time = current
        self.last_change_time = current

    def should_trigger(self, now: Optional[float] = None) -> bool:
        """Return True if debounce window has settled or max delay has elapsed."""
        if not self.pending:
            return False
        current = time.time() if now is None else now

        # Settled: No new changes for >= settle_window
        if self.last_change_time is not None and (current - self.last_change_time) >= self.settle_window:
            return True

        # Starvation guard: Continuous changes exceeding max_delay
        if self.first_change_time is not None and (current - self.first_change_time) >= self.max_delay:
            return True

        return False

    def reset(self) -> None:
        """Reset state after export trigger."""
        self.pending = False
        self.first_change_time = None
        self.last_change_time = None


class DualModeServer:
    """Lightweight HTTP server serving dashboard/ locally with clean shutdown."""

    def __init__(self, port: int = 8088, web_dir: Optional[Path] = None):
        self.port = port
        self.web_dir = web_dir or (REPO_ROOT / "dashboard")
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        web_dir_path = self.web_dir

        class DashboardHandler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(web_dir_path), **kwargs)

            def log_message(self, format, *args):
                # Silence standard HTTP request logging to avoid cluttering telemetry logs
                pass

        self.server = HTTPServer(("127.0.0.1", self.port), DashboardHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"[*] Local HTTP server listening at http://127.0.0.1:{self.port}/")

    def stop(self) -> None:
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except OSError as e:
                sys.stderr.write(f"[!] Warning: error shutting down HTTP server: {e}\n")
            except Exception as e:
                sys.stderr.write(f"[!] Unexpected error during HTTP server shutdown: {e}\n")


def run_isolated_export_subprocess(
    antigravity_dir: Path,
    dashboard_path: Path,
    log_path: Optional[Path] = None,
    status_path: Optional[Path] = None,
    timeout_seconds: float = 300.0,
) -> Dict[str, str]:
    """
    Execute Heavy Tier export_dashboard.py in a short-lived child subprocess so the OS kernel
    reclaims 100% of transient SQLite, JSON, and turn-aggregation memory on exit.
    """
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "export_dashboard.py"),
        "--antigravity-dir",
        str(antigravity_dir),
        "--dashboard-path",
        str(dashboard_path),
    ]
    if log_path is not None:
        cmd.extend(["--log-path", str(log_path)])
    if status_path is not None:
        cmd.extend(["--status-path", str(status_path)])

    proc = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if proc.stdout:
        sys.stdout.write(proc.stdout)
        sys.stdout.flush()
    if proc.stderr:
        sys.stderr.write(proc.stderr)
        sys.stderr.flush()
    if proc.returncode != 0:
        raise RuntimeError(f"export_dashboard subprocess exited with code {proc.returncode}")
    if "[skip] export already running" in (proc.stdout or ""):
        return {"status": "skipped", "reason": "lock_held"}
    return {"status": "ok"}


def watch_loop(
    antigravity_dir: Path,
    dashboard_path: Path,
    log_path: Optional[Path] = None,
    interval_seconds: float = 1.0,
    debounce_seconds: float = 2.0,
    max_debounce_seconds: float = 10.0,
    stop_event: Optional[threading.Event] = None,
    on_export: Optional[Callable[[], None]] = None,
    on_fast_export: Optional[Callable[[], None]] = None,
    once: bool = False,
    sync_vault: bool = False,
    refresh_signal_path: Optional[Path] = None,
    refresh_event: Optional[threading.Event] = None,
    status_path: Optional[Path] = None,
    heartbeat_interval: float = 10.0,
    repair_rate_limit: float = 60.0,
    enable_fast_tier: bool = True,
    isolate_export_subprocess: bool = False,
) -> int:
    """
    Continuously poll conversation directory and language_server.log with debounced exports.
    Returns total count of exports performed.
    """
    if stop_event is None:
        stop_event = threading.Event()

    effective_status_path = status_path if status_path is not None else DEFAULT_STATUS_PATH
    update_watcher_heartbeat(effective_status_path)
    heartbeat_thread = start_heartbeat_thread(effective_status_path, stop_event, interval=heartbeat_interval)

    conv_dir = antigravity_dir / "conversations"
    active_log = log_path or DEFAULT_LOG_PATH
    debounce = DebounceController(
        settle_window=debounce_seconds,
        max_delay=max_debounce_seconds,
        max_settle_window=max(10.0, max_debounce_seconds),
    )
    sig_path = refresh_signal_path if refresh_signal_path is not None else DEFAULT_REFRESH_SIGNAL_PATH

    print(f"[*] Starting Antigravity telemetry watcher daemon...")
    print(f"[*] Monitoring conversation DBs/WALs: {conv_dir}")
    print(f"[*] Monitoring runtime log: {active_log}")
    print(f"[*] Polling interval: {interval_seconds}s | Settle window: {debounce_seconds}s (max: {max_debounce_seconds}s)")
    if sig_path:
        print(f"[*] Monitoring manual refresh signal: {sig_path}")

    export_count = 0

    if enable_fast_tier:
        try:
            fast_t0 = time.time()
            fast_init_res = export_fast_tier(
                antigravity_dir=antigravity_dir,
                dashboard_path=dashboard_path,
                status_path=effective_status_path,
                log_path=active_log,
            )
            fast_ms = (time.time() - fast_t0) * 1000
            if isinstance(fast_init_res, dict) and fast_init_res.get("status") == "success":
                epoch_label = f"E{fast_init_res.get('epoch', 1)}"
                print(f"[*] Initial Fast Tier export complete in {fast_ms:.2f}ms (Epoch: {epoch_label})")
        except Exception as e:
            sys.stderr.write(f"[!] Initial Fast Tier export warning: {e}\n")

    # Initial export on start
    t0 = time.time()
    try:
        if isolate_export_subprocess and not hasattr(export_telemetry, "mock_calls"):
            res = run_isolated_export_subprocess(
                antigravity_dir=antigravity_dir,
                dashboard_path=dashboard_path,
                log_path=active_log,
                status_path=effective_status_path,
            )
        else:
            res = export_telemetry(
                antigravity_dir=antigravity_dir,
                dashboard_path=dashboard_path,
                log_path=active_log,
                status_path=effective_status_path,
            )
        duration = time.time() - t0
        last_snapshot = get_snapshot(conv_dir, active_log)
        update_watcher_heartbeat(effective_status_path)
        if not (isinstance(res, dict) and res.get("status") == "skipped"):
            export_count += 1
            debounce.update_settle_window(duration)
            print(f"[*] Initial export complete: export took {duration:.2f}s (adaptive settle window: {debounce.settle_window:.2f}s)")
        else:
            print(f"[*] Initial export skipped: export took {duration:.2f}s")
    except Exception as e:
        print(f"[!] Initial export warning: {e}", file=sys.stderr)
        update_watcher_heartbeat(effective_status_path)
        last_snapshot = get_snapshot(conv_dir, active_log)
    if on_export:
        on_export()

    if once:
        print("[*] Single-cycle export complete (--once).")
        stop_event.set()
        if heartbeat_thread and heartbeat_thread.is_alive():
            heartbeat_thread.join(timeout=1.0)
        return export_count

    last_heartbeat_time = time.time()
    last_repair_time = 0.0

    while not stop_event.is_set():
        # Sleep responsive to stop_event
        if stop_event.wait(timeout=interval_seconds):
            break

        now = time.time()
        trigger_export = False
        trigger_reason = ""

        if (now - last_heartbeat_time) >= heartbeat_interval:
            is_healthy, reason = check_status_health(effective_status_path, dashboard_path)
            if not is_healthy:
                if (now - last_repair_time) >= repair_rate_limit:
                    trigger_export = True
                    trigger_reason = f"Foreign status file detected: {reason}"
                    last_repair_time = now
                    print(f"[!] Foreign status file detected: {reason}")
            update_watcher_heartbeat(effective_status_path)
            last_heartbeat_time = now

        current_snapshot = get_snapshot(conv_dir, active_log)

        # Check for manual refresh file signal (e.g. from macOS menu bar or CLI)
        if sig_path and sig_path.exists():
            try:
                sig_path.unlink(missing_ok=True)
            except OSError:
                pass
            trigger_export = True
            trigger_reason = f"Manual refresh signal ({sig_path.name}) detected"

        # Check for manual refresh event (e.g. SIGUSR1)
        if refresh_event and refresh_event.is_set():
            refresh_event.clear()
            trigger_export = True
            trigger_reason = "Manual refresh signal (SIGUSR1) detected"

        if snapshots_differ(current_snapshot, last_snapshot):
            if enable_fast_tier:
                changed_files = [
                    f for f, snap in current_snapshot.items()
                    if last_snapshot.get(f) != snap
                ]
                wal_changed = any(f.endswith(".db-wal") or f.endswith(".db") for f in changed_files)
                log_changed = any(f.endswith(".log") for f in changed_files)
                if wal_changed or log_changed:
                    wal_dbs = []
                    for f in changed_files:
                        p = Path(f)
                        if p.name.endswith(".db-wal"):
                            db_cand = p.parent / p.name[:-4]
                            if db_cand.exists():
                                wal_dbs.append(db_cand)
                        elif p.name.endswith(".db"):
                            wal_dbs.append(p)
                    active_db = max(wal_dbs, key=lambda p: p.stat().st_mtime if p.exists() else 0) if wal_dbs else None
                    if active_db and active_db.exists():
                        curr_p = active_db
                        visited = set()
                        valid_lineage = False
                        while curr_p and curr_p.exists() and len(visited) < 5:
                            if curr_p in visited:
                                break
                            visited.add(curr_p)
                            meta = read_single_conversation_metadata(curr_p) or {}
                            if not is_subagent_conversation(meta):
                                valid_lineage = True
                                break
                            pid = meta.get("parent_convo_id")
                            if not pid:
                                break
                            parent_cand = conv_dir / f"{pid}.db" if conv_dir.exists() else curr_p.parent / f"{pid}.db"
                            if not parent_cand.exists():
                                parent_cand = curr_p.parent / f"{pid}.db"
                            if not parent_cand.exists():
                                break
                            curr_p = parent_cand
                        if not valid_lineage:
                            active_db = resolve_authoritative_session_db(active_db, conv_dir)
                    try:
                        fast_t0 = time.time()
                        fast_res = export_fast_tier(
                            antigravity_dir=antigravity_dir,
                            dashboard_path=dashboard_path,
                            status_path=effective_status_path,
                            active_db=active_db,
                            log_path=active_log,
                        )
                        fast_ms = (time.time() - fast_t0) * 1000
                        if fast_res and fast_res.get("status") == "success":
                            epoch_label = f"E{fast_res.get('epoch', 1)}"
                            print(f"[*] Fast Tier export complete in {fast_ms:.2f}ms (Epoch: {epoch_label})")
                            if on_fast_export:
                                on_fast_export()
                    except Exception as e:
                        sys.stderr.write(f"[!] Fast Tier export warning: {e}\n")

            debounce.notify_change(now)
            last_snapshot = current_snapshot

        if not trigger_export and debounce.should_trigger(now):
            trigger_export = True
            trigger_reason = f"Activity settled in telemetry storage at {time.strftime('%X')}"

        if trigger_export:
            print(f"[!] {trigger_reason}. Refreshing dashboard...")
            t0 = time.time()
            try:
                if isolate_export_subprocess and not hasattr(export_telemetry, "mock_calls"):
                    res = run_isolated_export_subprocess(
                        antigravity_dir=antigravity_dir,
                        dashboard_path=dashboard_path,
                        log_path=active_log,
                        status_path=effective_status_path,
                    )
                else:
                    res = export_telemetry(
                        antigravity_dir=antigravity_dir,
                        dashboard_path=dashboard_path,
                        log_path=active_log,
                        status_path=effective_status_path,
                    )
                duration = time.time() - t0
                debounce.reset()
                # Capture snapshot post-export before logging completion so concurrent writers are detected
                last_snapshot = get_snapshot(conv_dir, active_log)
                update_watcher_heartbeat(effective_status_path)
                last_heartbeat_time = time.time()
                if not (isinstance(res, dict) and res.get("status") == "skipped"):
                    export_count += 1
                    debounce.update_settle_window(duration)
                    print(f"[*] Export complete: export took {duration:.2f}s (adaptive settle window: {debounce.settle_window:.2f}s)")
                else:
                    print(f"[*] Export skipped: export took {duration:.2f}s")
                if on_export:
                    on_export()
            except Exception as e:
                print(f"[!] Error updating dashboard: {e}", file=sys.stderr)
                debounce.reset()
                last_snapshot = get_snapshot(conv_dir, active_log)
                update_watcher_heartbeat(effective_status_path)
                last_heartbeat_time = time.time()

    print("[*] Watcher daemon stopped cleanly.")
    if heartbeat_thread and heartbeat_thread.is_alive():
        heartbeat_thread.join(timeout=1.0)
    return export_count


def setup_signal_handlers(stop_event: threading.Event, refresh_event: Optional[threading.Event] = None) -> None:
    """Register SIGINT, SIGTERM, and SIGUSR1 handlers for graceful shutdown and manual refresh."""
    def handle_signal(signum, frame):
        sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        print(f"\n[*] Received signal {sig_name}. Initiating graceful shutdown...")
        stop_event.set()

    def handle_usr1(signum, frame):
        print(f"\n[*] Received SIGUSR1. Triggering immediate manual export...")
        if refresh_event is not None:
            refresh_event.set()

    try:
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
    except (ValueError, AttributeError):
        pass

    try:
        if hasattr(signal, "SIGUSR1"):
            signal.signal(signal.SIGUSR1, handle_usr1)
    except (ValueError, AttributeError):
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Near real-time watcher daemon for Antigravity telemetry with debounced exports."
    )
    parser.add_argument(
        "--antigravity-dir",
        type=Path,
        default=DEFAULT_ANTIGRAVITY_DIR,
        help="Path to ~/.gemini/antigravity (default: ~/.gemini/antigravity)",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Path to language_server.log (default: ~/Library/Logs/Antigravity/language_server.log)",
    )
    parser.add_argument(
        "--dashboard-path",
        type=Path,
        default=REPO_ROOT / "dashboard" / "index.html",
        help="Path to dashboard/index.html",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Filesystem polling interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--debounce",
        type=float,
        default=2.0,
        help="Heavy Tier debounce quiet settle window in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--max-debounce",
        type=float,
        default=10.0,
        help="Maximum Heavy Tier debounce delay before forced export in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--no-fast-tier",
        action="store_true",
        help="Disable Fast Tier ticker exports (<20ms) on active session WAL changes",
    )
    parser.add_argument(
        "--refresh-signal-path",
        type=Path,
        default=DEFAULT_REFRESH_SIGNAL_PATH,
        help="Path to poll for manual refresh request signal file (default: ~/.antigravity_refresh_requested)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Also start local HTTP server on --port",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8088,
        help="Port for local HTTP server (default: 8088)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run single extraction cycle and exit immediately",
    )
    parser.add_argument(
        "--sync-vault",
        action="store_true",
        help="Synchronize telemetry and logs to permanent SQLite vault during watch loop",
    )
    parser.add_argument(
        "--status-path",
        type=Path,
        default=DEFAULT_STATUS_PATH,
        help="Path to quota status JSON file (default: ~/.antigravity_quota_status.json)",
    )
    parser.add_argument(
        "--in-process-export",
        action="store_true",
        help="Run Heavy Tier exports in-process instead of an isolated child subprocess",
    )

    args = parser.parse_args()

    stop_event = threading.Event()
    refresh_event = threading.Event()
    setup_signal_handlers(stop_event, refresh_event)

    server = None
    if args.serve and not args.once:
        server = DualModeServer(port=args.port)
        server.start()

    try:
        watch_loop(
            antigravity_dir=args.antigravity_dir,
            dashboard_path=args.dashboard_path,
            log_path=args.log_path,
            interval_seconds=args.interval,
            debounce_seconds=args.debounce,
            max_debounce_seconds=args.max_debounce,
            stop_event=stop_event,
            once=args.once,
            sync_vault=args.sync_vault,
            refresh_signal_path=args.refresh_signal_path,
            refresh_event=refresh_event,
            status_path=args.status_path,
            enable_fast_tier=not args.no_fast_tier,
            isolate_export_subprocess=not args.in_process_export,
        )
    finally:
        if server:
            server.stop()


if __name__ == "__main__":
    main()

