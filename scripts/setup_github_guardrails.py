#!/usr/bin/env python3
"""
setup_github_guardrails.py

Automated GitHub security & branch protection provisioner.
Configures branch protection on 'main', designates CODEOWNERS review requirements,
enforces status checks, and blocks unauthorized force pushes using GitHub CLI (`gh`).
"""

import argparse
import json
import subprocess
import sys


REPO = "Eneasf/antigravity-token-dashboard"
BRANCH = "main"


def run_gh_command(args: list[str], stdin_data: str | None = None) -> tuple[int, str, str]:
    """Execute a gh CLI command and return exit code, stdout, and stderr."""
    try:
        proc = subprocess.run(
            ["gh"] + args,
            input=stdin_data,
            capture_output=True,
            text=True,
            check=False,
            timeout=30.0,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        print(f"[!] Error: GitHub CLI ('gh') command timed out after 30s: gh {' '.join(args)}", file=sys.stderr)
        return 1, "", "Command timed out after 30s"
    except FileNotFoundError:
        print("[!] Error: GitHub CLI ('gh') is not installed or not in PATH.", file=sys.stderr)
        return 1, "", "GitHub CLI ('gh') is not installed"


def build_repo_settings_args(repo: str = REPO) -> list[str]:
    """Build the gh api arguments for configuring repository settings."""
    return [
        "api",
        f"repos/{repo}",
        "-X", "PATCH",
        "-F", "delete_branch_on_merge=true",
        "-F", "allow_auto_merge=true",
        "-F", "allow_squash_merge=true",
        "-F", "allow_rebase_merge=true",
    ]


def build_branch_protection_payload() -> dict:
    """Build the branch protection configuration payload dict."""
    return {
        "required_status_checks": {
            "strict": True,
            "contexts": [
                "Test (macos-latest - Python 3.12)",
                "Test (ubuntu-latest - Python 3.12)",
            ],
        },
        "enforce_admins": False,
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "require_code_owner_reviews": True,
            "required_approving_review_count": 1,
            "require_last_push_approval": True,
        },
        "restrictions": None,
        "allow_force_pushes": False,
        "allow_deletions": False,
        "required_conversation_resolution": True,
    }


def check_repo_visibility(repo: str = REPO) -> bool:
    """Return True if the repository is private, False if public."""
    code, stdout, stderr = run_gh_command(["repo", "view", repo, "--json", "isPrivate", "--jq", ".isPrivate"])
    if code != 0:
        print(f"[!] Failed to fetch repo metadata: {stderr}", file=sys.stderr)
        return True
    return stdout.lower() == "true"


def configure_repository_settings(repo: str = REPO, dry_run: bool = False) -> int:
    """Enable automatic branch deletion and clean merge options."""
    print(f"[*] Configuring repository settings for {repo}...")
    if dry_run:
        print("  ✓ [DRY RUN] Would enable auto-delete head branches after PR merge.")
        print("  ✓ [DRY RUN] Would configure clean squash and rebase merge options.")
        return 0

    code, _, stderr = run_gh_command(build_repo_settings_args(repo))
    if code == 0:
        print("  ✓ Auto-delete head branches after PR merge enabled.")
        print("  ✓ Clean squash and rebase merge options configured.")
    else:
        print(f"  [!] Note on repo settings: {stderr}")
    return code


def configure_branch_protection(repo: str = REPO, branch: str = BRANCH, dry_run: bool = False) -> int:
    """Apply strict branch protection rules to target branch."""
    print(f"[*] Applying branch protection rules to '{branch}'...")
    payload = build_branch_protection_payload()

    if dry_run:
        print(f"  ✓ [DRY RUN] Would apply branch protection rules to '{branch}':")
        print("    - Mandatory pull request reviews required (approvals >= 1).")
        print("    - Code owner review required (@Eneasf via .github/CODEOWNERS).")
        print("    - Dismiss stale pull request approvals when new commits are pushed.")
        print("    - Required conversation resolution before merging.")
        print("    - Force pushes and branch deletions strictly prohibited.")
        print("    - Required status checks: Test (macos-latest - Python 3.12), Test (ubuntu-latest - Python 3.12)")
        return 0

    code, stdout, stderr = run_gh_command(
        [
            "api",
            f"repos/{repo}/branches/{branch}/protection",
            "-X", "PUT",
            "--input", "-",
        ],
        stdin_data=json.dumps(payload),
    )
    if code == 0:
        print(f"  ✓ Branch protection successfully applied to '{branch}'.")
        print("    - Mandatory pull request reviews required (approvals >= 1).")
        print("    - Code owner review required (@Eneasf via .github/CODEOWNERS).")
        print("    - Dismiss stale pull request approvals when new commits are pushed.")
        print("    - Required conversation resolution before merging.")
        print("    - Force pushes and branch deletions strictly prohibited.")
    else:
        print(f"  [!] Failed to apply branch protection: {stderr}")
    return code


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Automated GitHub security & branch protection provisioner."
    )
    parser.add_argument(
        "--repo",
        default=REPO,
        help="Target GitHub repository (default: %(default)s)",
    )
    parser.add_argument(
        "--branch",
        default=BRANCH,
        help="Target protected branch (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate configurations and print API payloads without executing mutations",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    print(f"=== GitHub Guardrails & Maintainer Controls ({args.repo}) ===")

    if args.dry_run:
        print("[*] DRY RUN MODE: Simulating configuration without invoking GitHub API.")
        configure_repository_settings(repo=args.repo, dry_run=True)
        configure_branch_protection(repo=args.repo, branch=args.branch, dry_run=True)
        print()
        print("✓ Technical controls configuration simulated successfully.")
        return 0

    # 1. Verify GitHub CLI Authentication
    code, stdout, stderr = run_gh_command(["auth", "status"])
    if code != 0:
        print(f"[!] gh CLI not authenticated: {stderr}", file=sys.stderr)
        return 1

    is_private = check_repo_visibility(repo=args.repo)
    if is_private:
        print(f"[*] Notice: Repository is currently PRIVATE.")
        print("    On GitHub Free accounts, branch protection API requires a public repository.")
        print("    Repository settings have been prepared.")
        print("    Run this script again immediately after toggling the repo to Public:")
        print(f"    $ python3 scripts/setup_github_guardrails.py --repo {args.repo} --branch {args.branch}")
        print()

    configure_repository_settings(repo=args.repo)

    if not is_private:
        configure_branch_protection(repo=args.repo, branch=args.branch)
    else:
        print("[*] Skipped branch protection API call until repository is made Public.")

    print()
    print("✓ Technical controls configuration complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
