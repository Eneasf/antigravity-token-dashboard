#!/usr/bin/env python3
"""
Build and package native macOS Menu Bar application (AntigravityBar).

Compiles the Swift package in macos/AntigravityBar using `swift build -c release`
and packages the output into a standalone `dist/AntigravityBar.app` bundle with
LSUIElement=true (agent/menu bar app with no Dock icon).
"""

import argparse
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
SWIFT_DIR = REPO_ROOT / "macos" / "AntigravityBar"
DIST_DIR = REPO_ROOT / "dist"
APP_BUNDLE_NAME = "AntigravityBar.app"
APP_BUNDLE_PATH = DIST_DIR / APP_BUNDLE_NAME


def check_swift_compiler() -> str:
    """Verify that swift compiler is installed and accessible."""
    try:
        res = subprocess.run(
            ["swift", "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=15.0,
        )
        first_line = res.stdout.splitlines()[0] if res.stdout else "swift"
        return first_line
    except subprocess.TimeoutExpired:
        print("Error: Swift compiler check timed out after 15s.", file=sys.stderr)
        sys.exit(1)
    except (subprocess.SubprocessError, FileNotFoundError):
        print("Error: Swift compiler (swift) not found on PATH.", file=sys.stderr)
        sys.exit(1)


def build_swift_package(swift_dir: Path = SWIFT_DIR) -> Path:
    """Compile Swift package in release mode and return path to binary."""
    if not swift_dir.exists():
        print(f"Error: Swift package directory {swift_dir} does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Building AntigravityBar in release mode at {swift_dir}...")
    cmd = ["swift", "build", "-c", "release"]
    try:
        res = subprocess.run(cmd, cwd=str(swift_dir), timeout=120.0)
        if res.returncode != 0:
            print("Error: Swift build failed.", file=sys.stderr)
            sys.exit(res.returncode)
    except subprocess.TimeoutExpired:
        print("Error: Swift build timed out after 120s.", file=sys.stderr)
        sys.exit(1)

    bin_path = swift_dir / ".build" / "release" / "AntigravityBar"
    if not bin_path.exists():
        candidates = list(swift_dir.glob(".build/**/release/AntigravityBar"))
        if candidates:
            bin_path = candidates[0]
        else:
            print(f"Error: Compiled binary not found in {swift_dir / '.build'}", file=sys.stderr)
            sys.exit(1)

    print(f"[*] Compiled binary verified: {bin_path} ({bin_path.stat().st_size:,} bytes)")
    return bin_path


def assemble_app_bundle(binary_path: Path, output_app: Path = APP_BUNDLE_PATH) -> Path:
    """Assemble .app bundle structure with Info.plist (LSUIElement=True)."""
    contents_dir = output_app / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    dest_bin = macos_dir / "AntigravityBar"
    shutil.copy2(binary_path, dest_bin)
    os.chmod(dest_bin, 0o755)

    info_plist_data = {
        "CFBundleExecutable": "AntigravityBar",
        "CFBundleIdentifier": "com.antigravity.menubar",
        "CFBundleName": "AntigravityBar",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "13.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSHumanReadableCopyright": "Copyright 2026 Eneas. All rights reserved.",
    }

    plist_path = contents_dir / "Info.plist"
    with open(plist_path, "wb") as f:
        plistlib.dump(info_plist_data, f)

    # Perform ad-hoc code signature if codesign is present
    if shutil.which("codesign"):
        try:
            subprocess.run(
                ["codesign", "--force", "--deep", "--sign", "-", str(output_app)],
                capture_output=True,
                check=True,
                timeout=30.0,
            )
            print("[*] Ad-hoc code signature applied successfully.")
        except subprocess.TimeoutExpired:
            print("[!] Warning: codesign timed out after 30s, app may still run locally.", file=sys.stderr)
        except subprocess.SubprocessError as e:
            print(f"[!] Warning: codesign failed ({e}), app may still run locally.", file=sys.stderr)

    print(f"[✓] Successfully packaged {output_app}")
    return output_app


def main():
    parser = argparse.ArgumentParser(description="Build and package native AntigravityBar macOS menu bar app.")
    parser.add_argument("--out", type=Path, default=APP_BUNDLE_PATH, help="Destination .app path")
    args = parser.parse_args()

    swift_ver = check_swift_compiler()
    print(f"[*] Detected {swift_ver}")

    bin_path = build_swift_package(SWIFT_DIR)
    app_path = assemble_app_bundle(bin_path, args.out)

    print(f"\nBuild complete: {app_path}")
    print(f"Launch with: open '{app_path}' or python3 scripts/setup_menubar.py start")


if __name__ == "__main__":
    main()
