#!/usr/bin/env python3
"""
Near real-time telemetry watcher daemon.

Monitors Antigravity SQLite Write-Ahead Logs (*.db-wal), conversation databases,
and runtime logs (language_server.log), automatically refreshing dashboard/index.html
with debounced export triggers when generation turns occur.
"""

import argparse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
from pathlib import Path
import signal
import sys
import threading
import time
from typing import Callable, Dict, Optional, Tuple

# Ensure repository root is on Python module search path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True)


from scripts.export_dashboard import export_telemetry
from src.log_reader import DEFAULT_LOG_PATH
from src.telemetry_reader import DEFAULT_ANTIGRAVITY_DIR


def sync_vault_telemetry(antigravity_dir: Path, log_path: Optional[Path] = None) -> None:
    """Safely synchronize conversation telemetry and runtime logs to the local Vault."""
    try:
        from src.vault import sync_conversations_to_vault
        sync_conversations_to_vault(antigravity_dir=antigravity_dir)
    except Exception as e:
        pass
    try:
        from src.log_archiver import archive_logs
        archive_logs(log_path=log_path)
    except Exception as e:
        pass


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

    def __init__(self, settle_window: float = 2.0, max_delay: float = 10.0):
        self.settle_window = max(0.1, float(settle_window))
        self.max_delay = max(self.settle_window, float(max_delay))
        self.pending = False
        self.first_change_time: Optional[float] = None
        self.last_change_time: Optional[float] = None

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
            except Exception:
                pass


def watch_loop(
    antigravity_dir: Path,
    dashboard_path: Path,
    log_path: Optional[Path] = None,
    interval_seconds: float = 1.0,
    debounce_seconds: float = 2.0,
    max_debounce_seconds: float = 10.0,
    stop_event: Optional[threading.Event] = None,
    on_export: Optional[Callable[[], None]] = None,
    once: bool = False,
    sync_vault: bool = False,
) -> int:
    """
    Continuously poll conversation directory and language_server.log with debounced exports.
    Returns total count of exports performed.
    """
    if stop_event is None:
        stop_event = threading.Event()

    conv_dir = antigravity_dir / "conversations"
    active_log = log_path or DEFAULT_LOG_PATH
    debounce = DebounceController(
        settle_window=debounce_seconds,
        max_delay=max_debounce_seconds,
    )

    print(f"[*] Starting Antigravity telemetry watcher daemon...")
    print(f"[*] Monitoring conversation DBs/WALs: {conv_dir}")
    print(f"[*] Monitoring runtime log: {active_log}")
    print(f"[*] Polling interval: {interval_seconds}s | Settle window: {debounce_seconds}s (max: {max_debounce_seconds}s)")

    export_count = 0

    # Initial export on start
    if sync_vault:
        sync_vault_telemetry(antigravity_dir=antigravity_dir, log_path=active_log)
    try:
        export_telemetry(
            antigravity_dir=antigravity_dir,
            dashboard_path=dashboard_path,
            log_path=active_log,
        )
        export_count += 1
        if on_export:
            on_export()
    except Exception as e:
        print(f"[!] Initial export warning: {e}", file=sys.stderr)

    if once:
        print("[*] Single-cycle export complete (--once).")
        return export_count

    last_snapshot = get_snapshot(conv_dir, active_log)

    while not stop_event.is_set():
        # Sleep responsive to stop_event
        if stop_event.wait(timeout=interval_seconds):
            break

        now = time.time()
        current_snapshot = get_snapshot(conv_dir, active_log)

        if snapshots_differ(current_snapshot, last_snapshot):
            debounce.notify_change(now)
            last_snapshot = current_snapshot

        if debounce.should_trigger(now):
            print(f"[!] Activity settled in telemetry storage at {time.strftime('%X')}. Refreshing dashboard...")
            if sync_vault:
                sync_vault_telemetry(antigravity_dir=antigravity_dir, log_path=active_log)
            try:
                export_telemetry(
                    antigravity_dir=antigravity_dir,
                    dashboard_path=dashboard_path,
                    log_path=active_log,
                )
                export_count += 1
                if on_export:
                    on_export()
            except Exception as e:
                print(f"[!] Error updating dashboard: {e}", file=sys.stderr)

            debounce.reset()
            # Capture snapshot post-export to register any writes during export
            last_snapshot = get_snapshot(conv_dir, active_log)

    print("[*] Watcher daemon stopped cleanly.")
    return export_count


def setup_signal_handlers(stop_event: threading.Event) -> None:
    """Register SIGINT and SIGTERM handlers for graceful shutdown."""
    def handle_signal(signum, frame):
        sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else str(signum)
        print(f"\n[*] Received signal {sig_name}. Initiating graceful shutdown...")
        stop_event.set()

    try:
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
    except (ValueError, AttributeError):
        # In non-main thread or certain testing harnesses
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
        help="Debounce quiet settle window in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--max-debounce",
        type=float,
        default=10.0,
        help="Maximum debounce delay before forced export in seconds (default: 10.0)",
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

    args = parser.parse_args()

    stop_event = threading.Event()
    setup_signal_handlers(stop_event)

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
        )
    finally:
        if server:
            server.stop()


if __name__ == "__main__":
    main()

