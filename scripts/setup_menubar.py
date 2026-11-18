#!/usr/bin/env python3
"""
macOS Menu Bar Application Lifecycle Management CLI.

Manages start, stop, status, and LaunchAgent auto-start integration for AntigravityBar.
"""

import argparse
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_APP = REPO_ROOT / "dist" / "AntigravityBar.app"
BIN_PATH = DIST_APP / "Contents" / "MacOS" / "AntigravityBar"
SERVICE_LABEL = "com.antigravity.menubar"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{SERVICE_LABEL}.plist"


def get_running_pids() -> list[int]:
    """Return list of PIDs matching AntigravityBar binary."""
    try:
        res = subprocess.run(
            ["pgrep", "-f", "AntigravityBar.app/Contents/MacOS/AntigravityBar"],
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        if res.returncode == 0 and res.stdout.strip():
            return [int(pid) for pid in res.stdout.strip().splitlines()]
    except subprocess.TimeoutExpired:
        pass
    except (subprocess.SubprocessError, OSError, ValueError):
        pass
    return []


def cmd_status() -> int:
    """Check and display application and process status."""
    print("=== AntigravityBar Status ===")
    app_exists = DIST_APP.exists()
    bin_exists = BIN_PATH.exists()
    print(f"[*] Bundle: {DIST_APP} (Installed: {app_exists})")
    print(f"[*] Binary: {BIN_PATH} (Executable: {bin_exists})")

    pids = get_running_pids()
    if pids:
        print(f"[✓] Process: RUNNING (PID: {', '.join(map(str, pids))})")
    else:
        print("[!] Process: STOPPED")

    service_installed = PLIST_PATH.exists()
    print(f"[*] LaunchAgent: {PLIST_PATH} (Configured: {service_installed})")
    return 0


def is_service_registered() -> bool:
    """Return True if LaunchAgent service is registered in launchctl."""
    if not PLIST_PATH.exists():
        return False
    try:
        res = subprocess.run(["launchctl", "list", SERVICE_LABEL], capture_output=True, text=True, timeout=10.0)
        return res.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def cmd_start() -> int:
    """Launch the menu bar application."""
    if not BIN_PATH.exists():
        print(f"Error: Application binary not found at {BIN_PATH}.", file=sys.stderr)
        print("Run `python3 scripts/build_menubar.py` first to compile and package.", file=sys.stderr)
        return 1

    pids = get_running_pids()
    if pids:
        print(f"[*] AntigravityBar is already running (PID: {pids[0]}).")
        return 0

    if is_service_registered():
        uid = os.getuid()
        service_target = f"gui/{uid}/{SERVICE_LABEL}"
        print(f"[*] Starting AntigravityBar via LaunchAgent kickstart ({service_target})...")
        try:
            res = subprocess.run(
                ["launchctl", "kickstart", "-k", service_target],
                capture_output=True,
                text=True,
                timeout=15.0,
            )
            if res.returncode == 0:
                time.sleep(0.5)
                new_pids = get_running_pids()
                if new_pids:
                    print(f"[✓] AntigravityBar started successfully (PID: {new_pids[0]}).")
                    return 0
            print(f"[*] Kickstart failed ({res.stderr.strip()}). Falling back to direct app launch...")
        except subprocess.TimeoutExpired:
            print("[*] Kickstart timed out. Falling back to direct app launch...")

    print(f"[*] Launching AntigravityBar from {DIST_APP}...")
    try:
        subprocess.run(["open", "-a", str(DIST_APP)], timeout=15.0, check=True)
        time.sleep(0.5)
        new_pids = get_running_pids()
        if new_pids:
            print(f"[✓] AntigravityBar started successfully (PID: {new_pids[0]}).")
            return 0
        else:
            print("[✓] Launch signal sent.")
            return 0
    except subprocess.TimeoutExpired:
        print("Error: App launch timed out.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error launching app: {e}", file=sys.stderr)
        return 1


def cmd_stop() -> int:
    """Stop any running AntigravityBar processes."""
    pids = get_running_pids()
    if not pids:
        print("[*] AntigravityBar is not currently running.")
        return 0

    print(f"[*] Stopping AntigravityBar (PID: {', '.join(map(str, pids))})...")
    try:
        subprocess.run(["pkill", "-f", "AntigravityBar.app/Contents/MacOS/AntigravityBar"], check=True, timeout=10.0)
        time.sleep(0.3)
        print("[✓] AntigravityBar stopped cleanly.")
        return 0
    except subprocess.TimeoutExpired:
        print("Error: pkill timed out after 10s.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error stopping app: {e}", file=sys.stderr)
        return 1


def cmd_restart() -> int:
    """Restart the menu bar application."""
    if is_service_registered():
        uid = os.getuid()
        service_target = f"gui/{uid}/{SERVICE_LABEL}"
        print(f"[*] Restarting LaunchAgent {SERVICE_LABEL} via kickstart ({service_target})...")
        try:
            res = subprocess.run(
                ["launchctl", "kickstart", "-k", service_target],
                capture_output=True,
                text=True,
                timeout=15.0,
            )
            if res.returncode == 0:
                time.sleep(0.5)
                pids = get_running_pids()
                pid_str = f" (PID: {pids[0]})" if pids else ""
                print(f"[✓] Successfully kickstarted and restarted {SERVICE_LABEL}{pid_str}.")
                return 0
            print(f"[*] Kickstart failed ({res.stderr.strip()}). Falling back to process restart...")
        except subprocess.TimeoutExpired:
            print("[*] Kickstart timed out. Falling back to process restart...")

    cmd_stop()
    time.sleep(0.5)
    return cmd_start()


def cmd_install_service() -> int:
    """Install and enable LaunchAgent for auto-start at login."""
    if not BIN_PATH.exists():
        print(f"Error: Binary not found at {BIN_PATH}. Build first.", file=sys.stderr)
        return 1

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    plist_data = {
        "Label": SERVICE_LABEL,
        "ProgramArguments": [str(BIN_PATH)],
        "RunAtLoad": True,
        "KeepAlive": True,
        "LimitLoadToSessionType": "Aqua",
        "ProcessType": "Interactive",
    }

    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(plist_data, f)
    print(f"[*] Wrote LaunchAgent plist to {PLIST_PATH}")

    uid = os.getuid()
    # Try bootstrapping via modern launchctl or fallback to load
    try:
        subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(PLIST_PATH)], capture_output=True, timeout=15.0)
    except subprocess.TimeoutExpired:
        print(f"[!] Warning: launchctl bootstrap timed out after 15s.", file=sys.stderr)
    except subprocess.SubprocessError as e:
        print(f"[!] Warning: launchctl bootstrap error: {e}", file=sys.stderr)
    print(f"[✓] LaunchAgent {SERVICE_LABEL} installed and registered.")
    return 0


def cmd_uninstall_service() -> int:
    """Unload and remove LaunchAgent auto-start service."""
    if PLIST_PATH.exists():
        uid = os.getuid()
        try:
            subprocess.run(["launchctl", "bootout", f"gui/{uid}/{SERVICE_LABEL}"], capture_output=True, timeout=15.0)
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            pass
        try:
            subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True, timeout=15.0)
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            pass
        PLIST_PATH.unlink()
        print(f"[✓] LaunchAgent {SERVICE_LABEL} uninstalled.")
    else:
        print(f"[*] LaunchAgent plist {PLIST_PATH} not found.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="AntigravityBar macOS Menu Bar CLI.")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("status", help="Check status of menu bar app and process")
    subparsers.add_parser("start", help="Start menu bar app")
    subparsers.add_parser("stop", help="Stop menu bar app")
    subparsers.add_parser("restart", help="Restart menu bar app")
    subparsers.add_parser("install-service", help="Install LaunchAgent for auto-start at login")
    subparsers.add_parser("uninstall-service", help="Uninstall LaunchAgent auto-start service")

    args = parser.parse_args()

    if args.command == "status" or not args.command:
        sys.exit(cmd_status())
    elif args.command == "start":
        sys.exit(cmd_start())
    elif args.command == "stop":
        sys.exit(cmd_stop())
    elif args.command == "restart":
        sys.exit(cmd_restart())
    elif args.command == "install-service":
        sys.exit(cmd_install_service())
    elif args.command == "uninstall-service":
        sys.exit(cmd_uninstall_service())


if __name__ == "__main__":
    main()
