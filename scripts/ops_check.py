#!/usr/bin/env python3
"""
Operational Health & Telemetry Export Verification Runner (ADR-047 / Milestone 48).

Executes end-to-end operational checks outside the test sandbox:
1. Live telemetry export to dashboard/data.js (with Connect-RPC offline fallback).
2. macOS LaunchAgent daemon status (com.antigravity.telemetry.watcher).
3. macOS Menu Bar monitor status (com.antigravity.menubar).
Prints a single-line summary to stdout and exits 0.
"""

from datetime import datetime
from pathlib import Path
import re
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent


def check_export() -> str:
    """Run live export, falling back to --no-live-quota if Connect-RPC is offline."""
    export_script = REPO_ROOT / "scripts" / "export_dashboard.py"
    proc = None
    try:
        proc = subprocess.run(
            [sys.executable, str(export_script)],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=120.0,
        )
        if proc.returncode == 0:
            return "OK"
    except subprocess.TimeoutExpired:
        pass

    # Fallback if Connect-RPC endpoint is offline
    try:
        fallback_proc = subprocess.run(
            [sys.executable, str(export_script), "--no-live-quota"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=120.0,
        )
        if fallback_proc.returncode == 0:
            return "OK"
        return f"ERROR (exit {fallback_proc.returncode})"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"


def check_daemon_status() -> str:
    """Check LaunchAgent watcher daemon status."""
    service_script = REPO_ROOT / "scripts" / "setup_service.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(service_script), "status"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=15.0,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except subprocess.SubprocessError:
        return "ERROR"
    m = re.search(r"Service status:\s*([^\n\r]+)", proc.stdout)
    if m:
        return m.group(1).strip()
    if "RUNNING / REGISTERED" in proc.stdout:
        return "RUNNING / REGISTERED"
    if "NOT RUNNING" in proc.stdout:
        return "NOT RUNNING"
    return "UNKNOWN"


def check_menubar_status() -> str:
    """Check macOS menu bar app status."""
    menubar_script = REPO_ROOT / "scripts" / "setup_menubar.py"
    try:
        proc = subprocess.run(
            [sys.executable, str(menubar_script), "status"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=15.0,
        )
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except subprocess.SubprocessError:
        return "ERROR"
    m = re.search(r"Process:\s*([^\n\r]+)", proc.stdout)
    if m:
        return m.group(1).strip()
    if "RUNNING" in proc.stdout:
        return "RUNNING"
    if "STOPPED" in proc.stdout:
        return "STOPPED"
    return "UNKNOWN"


def main():
    export_st = check_export()
    daemon_st = check_daemon_status()
    menubar_st = check_menubar_status()
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")

    print(
        f"[OPS CHECK] export: {export_st} | daemon: {daemon_st} | "
        f"menubar: {menubar_st} | verified: {timestamp}"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
