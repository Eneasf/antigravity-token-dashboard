#!/usr/bin/env python3
"""
publish_to_public.py

Safeguarded release publisher for the public repository (Eneasf/antigravity-token-dashboard).
Ensures zero leaks, runs full test verification, verifies clean state,
and requires explicit interactive confirmation before pushing anything to the public remote.

Usage:
    python3 scripts/publish_to_public.py v1.1.0 "feat: summarize new features"
"""

import argparse
from pathlib import Path
import re
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_REMOTE = "public"
PUBLIC_REPO_URL = "https://github.com/Eneasf/antigravity-token-dashboard.git"


def run_cmd(cmd: list[str], check: bool = True, capture: bool = True) -> tuple[int, str, str]:
    """Run a shell command within the repository root."""
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=capture,
        text=True,
        check=False,
    )
    stdout = proc.stdout.strip() if proc.stdout else ""
    stderr = proc.stderr.strip() if proc.stderr else ""
    if check and proc.returncode != 0:
        err = stderr if stderr else stdout
        print(f"[!] Command failed: {' '.join(cmd)}\n{err}", file=sys.stderr)
        sys.exit(proc.returncode)
    return proc.returncode, stdout, stderr


def verify_prerequisites(version: str = ""):
    """Run pre-flight security and quality checks before publishing."""
    print("[1/5] Checking git status and working tree...")
    code, stdout, _ = run_cmd(["git", "status", "--porcelain"])
    if stdout:
        print("[!] Error: Working tree has uncommitted changes. Please commit or stash before publishing.", file=sys.stderr)
        sys.exit(1)

    print("[2/5] Running unit test suite (including documentation integrity gates)...")
    code, stdout, stderr = run_cmd(["python3", "-m", "unittest", "discover", "-s", "tests"])
    print("  ✓ All unit tests passed (code logic & documentation drift gates).")

    if version:
        readme_text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        clean_v = version.lstrip("v")
        if f"v{clean_v}" not in readme_text and clean_v not in readme_text:
            print(f"[!] Error: Version '{version}' is not referenced in README.md! Please update README.md before publishing.", file=sys.stderr)
            sys.exit(1)
        print(f"  ✓ Version {version} verified in README.md.")

    print("[3/5] Verifying comprehensive telemetry, PII and path sanitization...")
    # 1. Run automated sanitization regression test suite
    code, stdout, stderr = run_cmd(["python3", "-m", "unittest", "tests/test_sanitization.py"])
    if code != 0:
        print(f"[!] Security Error: tests/test_sanitization.py failed!\n{stderr}\n{stdout}", file=sys.stderr)
        sys.exit(1)

    # 2. Grep for forbidden needles
    forbidden_needles = [
        "Users" + "/eneasf",
        "home" + "/eneasf",
        "df35" + "048e",
        "antigravity" + ".community",
        "Deterministic" + " Antigravity Telemetry Research Group",
    ]
    for needle in forbidden_needles:
        code, stdout, _ = run_cmd(["git", "grep", "-i", needle, "--", ":!scripts/publish_to_public.py", ":!tests/test_sanitization.py"], check=False)
        if stdout:
            print(f"[!] Security Error: Found unscrubbed string '{needle}':\n{stdout}", file=sys.stderr)
            sys.exit(1)

    # 3. Check that personal ledger is NOT tracked
    code, stdout, _ = run_cmd(["git", "ls-files", "data/exhaustion_ledger.json"])
    if stdout:
        print("[!] Security Error: data/exhaustion_ledger.json is tracked by git!", file=sys.stderr)
        sys.exit(1)
    print("  ✓ Sanitization verified (zero local paths, leaked UUIDs, unowned domains, or private ledgers tracked).")


def ensure_public_remote():
    """Verify that the public remote exists and points to the correct URL."""
    _, stdout, _ = run_cmd(["git", "remote", "-v"])
    if PUBLIC_REMOTE not in stdout:
        print(f"[*] Adding '{PUBLIC_REMOTE}' remote ({PUBLIC_REPO_URL})...")
        run_cmd(["git", "remote", "add", PUBLIC_REMOTE, PUBLIC_REPO_URL])
    print(f"[4/5] Public remote confirmed: {PUBLIC_REPO_URL}")


def main():
    parser = argparse.ArgumentParser(description="Publish a clean release to the public repository.")
    parser.add_argument("version", help="Version tag to publish (e.g. v1.1.0)")
    parser.add_argument("message", nargs="?", default="", help="Release message or summary")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip interactive confirmation prompt")
    parser.add_argument("--reset-history", action="store_true", help="Force-reset public remote to a single pristine root snapshot commit, eradicating past commit history")
    args = parser.parse_args()

    version = args.version.strip()
    if not re.match(r"^v?\d+\.\d+\.\d+", version):
        print(f"[!] Error: Version '{version}' does not match semantic format (e.g. v1.1.0).", file=sys.stderr)
        sys.exit(1)
    if not version.startswith("v"):
        version = f"v{version}"

    message = args.message.strip() or f"feat: release {version}"

    _, current_branch, _ = run_cmd(["git", "branch", "--show-current"])
    current_branch = current_branch or "main"

    print("=" * 65)
    print("   ANTIGRAVITY TOKEN DASHBOARD — PUBLIC RELEASE PUBLISHER")
    print("=" * 65)
    print(f"  Target Remote : {PUBLIC_REMOTE} ({PUBLIC_REPO_URL})")
    print(f"  Release Tag   : {version}")
    print(f"  Commit Message: {message}")
    print(f"  Source Branch : {current_branch}")
    print(f"  Reset History : {args.reset_history}")
    print("=" * 65)
    print()

    # Pre-flight safety checks
    verify_prerequisites(version=version)
    ensure_public_remote()

    print()
    print("[5/5] Awaiting explicit confirmation...")
    if args.reset_history:
        print("  ⚠️  WARNING: --reset-history is ENABLED.")
        print("  ⚠️  This will OVERWRITE and RESET public/main history to a single pristine commit.")
    else:
        print("  ⚠️  WARNING: This will push the current sanitized codebase to GitHub PUBLICLY.")
    print("  ⚠️  Anyone on the internet will be able to view this release.")
    print()

    if not args.yes:
        try:
            confirmation = input(f"Type 'yes' to publish {version} to PUBLIC: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n[!] Publish cancelled by user.")
            sys.exit(0)

        if confirmation != "yes":
            print("[!] Confirmation failed. Publish aborted. No changes made to public repo.")
            sys.exit(0)

    print("\n[*] Publishing release...")
    release_branch = f"public-release-{version}"

    try:
        if args.reset_history:
            print(f"[*] Creating orphan root snapshot branch '{release_branch}'...")
            run_cmd(["git", "checkout", "--orphan", release_branch])
            run_cmd(["git", "checkout", current_branch, "--", "."])
            run_cmd(["git", "add", "-A"])
            run_cmd(["git", "commit", "-m", f"{message} ({version})"])
            run_cmd(["git", "tag", "-f", version])
            print(f"[*] Force-pushing pristine root snapshot to {PUBLIC_REMOTE}/main...")
            run_cmd(["git", "push", "-f", PUBLIC_REMOTE, f"{release_branch}:main"], capture=False)
            print(f"[*] Synchronizing release tag {version} on {PUBLIC_REMOTE}...")
            run_cmd(["git", "push", "-f", PUBLIC_REMOTE, f"refs/tags/{version}"], capture=False)

            # Prune obsolete historical tags from public remote to eliminate orphaned commits
            _, ls_tags, _ = run_cmd(["git", "ls-remote", "--tags", PUBLIC_REMOTE])
            obsolete_tags = []
            for line in ls_tags.strip().splitlines():
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1].startswith("refs/tags/"):
                    tag_ref = parts[1]
                    if tag_ref.endswith("^{}"):
                        continue
                    tag_name = tag_ref.replace("refs/tags/", "")
                    if tag_name != version:
                        obsolete_tags.append(tag_name)
            if obsolete_tags:
                print(f"[*] Pruning {len(obsolete_tags)} obsolete historical tags from {PUBLIC_REMOTE}...")
                for old_tag in obsolete_tags:
                    run_cmd(["git", "push", PUBLIC_REMOTE, "--delete", f"refs/tags/{old_tag}"], check=False)
        else:
            # Fetch latest public remote
            print(f"[*] Fetching {PUBLIC_REMOTE} remote...")
            run_cmd(["git", "fetch", PUBLIC_REMOTE])

            # Create temporary release branch based on public/main
            run_cmd(["git", "checkout", "-B", release_branch, f"{PUBLIC_REMOTE}/main"])

            # Overlay all tracked files from current branch onto this branch
            run_cmd(["git", "checkout", current_branch, "--", "."])

            # Stage all changes (including additions, modifications, and deletions)
            run_cmd(["git", "add", "-A"])

            # Check if there are changes to commit
            code, status_out, _ = run_cmd(["git", "status", "--porcelain"])
            if status_out:
                run_cmd(["git", "commit", "-m", f"{message} ({version})"])
            else:
                print(f"[*] No code changes detected between {current_branch} and public/main.")

            # Tag release
            run_cmd(["git", "tag", "-f", version])

            # Push clean fast-forward commit and tag to public main
            print(f"[*] Pushing to {PUBLIC_REMOTE}/main...")
            run_cmd(["git", "push", PUBLIC_REMOTE, f"{release_branch}:main"], capture=False)
            run_cmd(["git", "push", "-f", PUBLIC_REMOTE, f"refs/tags/{version}"], capture=False)

        print()
        print("=" * 65)
        print(f"  ✓ SUCCESS: Release {version} is now LIVE on GitHub!")
        print(f"  URL: https://github.com/Eneasf/antigravity-token-dashboard")
        print("=" * 65)
    finally:
        # Return safely to starting branch and clean up temporary release branch
        run_cmd(["git", "checkout", current_branch], check=False)
        run_cmd(["git", "branch", "-D", release_branch], check=False)


if __name__ == "__main__":
    main()
