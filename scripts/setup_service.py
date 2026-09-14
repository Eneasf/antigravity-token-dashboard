#!/usr/bin/env python3
"""
macOS LaunchAgent Service Packaging & Management Script.

Manages background daemon installation, plist templating, syntax validation,
and launchctl lifecycle for com.antigravity.telemetry.watcher.
"""

import argparse
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
from typing import Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO_ROOT / "config" / "com.antigravity.telemetry.watcher.plist.template"
DEFAULT_SERVICE_LABEL = "com.antigravity.telemetry.watcher"
DEFAULT_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{DEFAULT_SERVICE_LABEL}.plist"
DEFAULT_LOG_DIR = Path.home() / "Library" / "Logs" / "Antigravity"


def render_plist_template(
    template_path: Path = TEMPLATE_PATH,
    label: str = DEFAULT_SERVICE_LABEL,
    python_executable: Optional[str] = None,
    watcher_script: Optional[Path] = None,
    repo_dir: Optional[Path] = None,
    log_dir: Optional[Path] = None,
    interval: float = 1.0,
    debounce: float = 2.0,
) -> str:
    """Render LaunchAgent plist template with active environment paths."""
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found at {template_path}")

    template_content = template_path.read_text(encoding="utf-8")

    python_bin = python_executable or sys.executable
    script_path = str((watcher_script or (REPO_ROOT / "scripts" / "watch_telemetry.py")).resolve())
    working_dir = str((repo_dir or REPO_ROOT).resolve())
    logs = log_dir or DEFAULT_LOG_DIR

    stdout_log = str((logs / "telemetry_watcher.stdout.log").resolve())
    stderr_log = str((logs / "telemetry_watcher.stderr.log").resolve())

    replacements: Dict[str, str] = {
        "{{LABEL}}": label,
        "{{PYTHON_EXECUTABLE}}": python_bin,
        "{{WATCHER_SCRIPT}}": script_path,
        "{{REPO_DIR}}": working_dir,
        "{{INTERVAL}}": str(interval),
        "{{DEBOUNCE}}": str(debounce),
        "{{STDOUT_PATH}}": stdout_log,
        "{{STDERR_PATH}}": stderr_log,
    }

    rendered = template_content
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)

    return rendered


def validate_plist_content(xml_content: str) -> bool:
    """
    Validate plist XML content using Python's plistlib and system plutil.
    Returns True if completely valid; raises ValueError or returns False if invalid.
    """
    try:
        # Standard library schema and parsing check
        parsed = plistlib.loads(xml_content.encode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("Root plist element is not a dictionary.")
        if "Label" not in parsed:
            raise ValueError("Missing 'Label' key in plist.")
        if "ProgramArguments" not in parsed or not isinstance(parsed["ProgramArguments"], list):
            raise ValueError("Missing or invalid 'ProgramArguments' array in plist.")
    except Exception as e:
        raise ValueError(f"Invalid property list syntax: {e}")

    # If plutil is present on macOS, also run plutil -lint via pipe
    plutil_path = shutil.which("plutil")
    if plutil_path:
        try:
            res = subprocess.run(
                [plutil_path, "-lint", "-"],
                input=xml_content.encode("utf-8"),
                capture_output=True,
                check=False,
            )
            if res.returncode != 0:
                err = res.stderr.decode("utf-8", errors="replace").strip()
                raise ValueError(f"plutil -lint failed: {err}")
        except FileNotFoundError:
            pass

    return True


def cmd_generate(args) -> None:
    rendered = render_plist_template(
        interval=args.interval,
        debounce=args.debounce,
    )
    validate_plist_content(rendered)

    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
        print(f"[*] Generated valid LaunchAgent plist written to {out_path}")
    else:
        print(rendered)


def cmd_validate(args) -> None:
    if args.file:
        plist_path = Path(args.file)
        if not plist_path.exists():
            print(f"Error: Target plist {plist_path} does not exist.", file=sys.stderr)
            sys.exit(1)
        content = plist_path.read_text(encoding="utf-8")
    else:
        content = render_plist_template()

    try:
        validate_plist_content(content)
        target_name = args.file if args.file else "Generated template"
        print(f"[*] Verified: {target_name} is valid Apple LaunchAgent XML.")
    except ValueError as e:
        print(f"[!] Validation error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_install(args) -> None:
    dest_path = Path(args.dest) if args.dest else DEFAULT_PLIST_PATH
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)

    rendered = render_plist_template(
        interval=args.interval,
        debounce=args.debounce,
    )
    validate_plist_content(rendered)
    dest_path.write_text(rendered, encoding="utf-8")
    print(f"[*] Successfully installed LaunchAgent plist to {dest_path}")
    print(f"[*] Standard stdout log: {DEFAULT_LOG_DIR / 'telemetry_watcher.stdout.log'}")
    print(f"[*] Standard stderr log: {DEFAULT_LOG_DIR / 'telemetry_watcher.stderr.log'}")

    if args.load:
        print(f"[*] Loading LaunchAgent with launchctl...")
        subprocess.run(["launchctl", "load", "-w", str(dest_path)], check=False)
        print("[*] LaunchAgent loaded.")
    else:
        print("\nTo load and start the daemon immediately, run:")
        print(f"  launchctl load -w {dest_path}")
        print("\nTo check service status, run:")
        print(f"  launchctl list | grep {DEFAULT_SERVICE_LABEL}")
        print("\nTo unload and stop the daemon, run:")
        print(f"  launchctl unload {dest_path}")


def cmd_uninstall(args) -> None:
    target_path = Path(args.dest) if args.dest else DEFAULT_PLIST_PATH
    if not target_path.exists():
        print(f"[*] Service plist {target_path} is not installed.")
        return

    print(f"[*] Unloading LaunchAgent service...")
    subprocess.run(["launchctl", "unload", str(target_path)], capture_output=True, check=False)

    try:
        target_path.unlink()
        print(f"[*] Removed {target_path}")
    except OSError as e:
        print(f"[!] Error removing {target_path}: {e}", file=sys.stderr)


def cmd_restart(args) -> None:
    target_path = Path(args.dest) if args.dest else DEFAULT_PLIST_PATH
    if not target_path.exists():
        print(f"[*] Service plist {target_path} is not installed. Installing and loading...")
        cmd_install(argparse.Namespace(
            dest=str(target_path),
            interval=args.interval if hasattr(args, "interval") else 1.0,
            debounce=args.debounce if hasattr(args, "debounce") else 2.0,
            load=True,
        ))
        return

    uid = os.getuid()
    service_target = f"gui/{uid}/{DEFAULT_SERVICE_LABEL}"
    print(f"[*] Restarting LaunchAgent {DEFAULT_SERVICE_LABEL} via kickstart ({service_target})...")
    res = subprocess.run(
        ["launchctl", "kickstart", "-k", service_target],
        capture_output=True,
        text=True,
        check=False,
    )

    if res.returncode == 0:
        print(f"[*] Successfully kickstarted and restarted {DEFAULT_SERVICE_LABEL}.")
    else:
        # Fallback to unload and load -w
        print(f"[*] Kickstart returned non-zero ({res.stderr.strip()}). Falling back to reload...")
        subprocess.run(["launchctl", "unload", str(target_path)], capture_output=True, check=False)
        load_res = subprocess.run(
            ["launchctl", "load", "-w", str(target_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if load_res.returncode == 0:
            print(f"[*] Successfully reloaded {DEFAULT_SERVICE_LABEL}.")
        else:
            print(f"[!] Error reloading service: {load_res.stderr.strip()}", file=sys.stderr)
            sys.exit(1)


def cmd_status(args) -> None:
    target_path = Path(args.dest) if args.dest else DEFAULT_PLIST_PATH
    installed = target_path.exists()
    print(f"[*] LaunchAgent plist: {target_path} (Installed: {installed})")

    try:
        res = subprocess.run(
            ["launchctl", "list", DEFAULT_SERVICE_LABEL],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            print(f"[*] Service status: RUNNING / REGISTERED")
            print(res.stdout.strip())
        else:
            print(f"[*] Service status: NOT RUNNING in launchctl session")
    except Exception as e:
        print(f"[!] Could not query launchctl: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="macOS LaunchAgent Service Packaging & Management for Antigravity Watcher."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate
    gen_p = subparsers.add_parser("generate", help="Generate rendered LaunchAgent plist")
    gen_p.add_argument("-o", "--output", help="Output file path (prints to stdout if omitted)")
    gen_p.add_argument("--interval", type=float, default=1.0, help="Polling interval (default: 1.0)")
    gen_p.add_argument("--debounce", type=float, default=2.0, help="Debounce settle window (default: 2.0)")

    # validate
    val_p = subparsers.add_parser("validate", help="Validate plist syntax using plistlib and plutil")
    val_p.add_argument("-f", "--file", help="Path to plist file (validates rendered template if omitted)")

    # install
    ins_p = subparsers.add_parser("install", help="Install LaunchAgent into ~/Library/LaunchAgents")
    ins_p.add_argument("--dest", help=f"Destination plist path (default: {DEFAULT_PLIST_PATH})")
    ins_p.add_argument("--interval", type=float, default=1.0, help="Polling interval (default: 1.0)")
    ins_p.add_argument("--debounce", type=float, default=2.0, help="Debounce settle window (default: 2.0)")
    ins_p.add_argument("--load", action="store_true", help="Immediately run launchctl load after install")

    # restart
    res_p = subparsers.add_parser("restart", help="Gracefully restart LaunchAgent daemon")
    res_p.add_argument("--dest", help=f"Destination plist path (default: {DEFAULT_PLIST_PATH})")
    res_p.add_argument("--interval", type=float, default=1.0, help="Polling interval (default: 1.0)")
    res_p.add_argument("--debounce", type=float, default=2.0, help="Debounce settle window (default: 2.0)")

    # uninstall
    un_p = subparsers.add_parser("uninstall", help="Unload and remove LaunchAgent plist")
    un_p.add_argument("--dest", help=f"Destination plist path (default: {DEFAULT_PLIST_PATH})")

    # status
    st_p = subparsers.add_parser("status", help="Check LaunchAgent registration status")
    st_p.add_argument("--dest", help=f"Destination plist path (default: {DEFAULT_PLIST_PATH})")

    args = parser.parse_args()

    commands = {
        "generate": cmd_generate,
        "validate": cmd_validate,
        "install": cmd_install,
        "restart": cmd_restart,
        "uninstall": cmd_uninstall,
        "status": cmd_status,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
