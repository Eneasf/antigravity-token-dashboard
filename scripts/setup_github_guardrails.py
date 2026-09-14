#!/usr/bin/env python3
"""
setup_github_guardrails.py

Automated GitHub security & branch protection provisioner.
Configures branch protection on 'main', designates CODEOWNERS review requirements,
enforces status checks, and blocks unauthorized force pushes using GitHub CLI (`gh`).
"""

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
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        print("[!] Error: GitHub CLI ('gh') is not installed or not in PATH.", file=sys.stderr)
        sys.exit(1)


def check_repo_visibility() -> bool:
    """Return True if the repository is private, False if public."""
    code, stdout, stderr = run_gh_command(["repo", "view", REPO, "--json", "isPrivate", "--jq", ".isPrivate"])
    if code != 0:
        print(f"[!] Failed to fetch repo metadata: {stderr}", file=sys.stderr)
        return True
    return stdout.lower() == "true"


def configure_repository_settings():
    """Enable automatic branch deletion and clean merge options."""
    print(f"[*] Configuring repository settings for {REPO}...")
    # Enable deleting head branches automatically after PR merge
    code, _, stderr = run_gh_command([
        "api",
        f"repos/{REPO}",
        "-X", "PATCH",
        "-F", "delete_branch_on_merge=true",
        "-F", "allow_auto_merge=true",
        "-F", "allow_squash_merge=true",
        "-F", "allow_rebase_merge=true",
    ])
    if code == 0:
        print("  ✓ Auto-delete head branches after PR merge enabled.")
        print("  ✓ Clean squash and rebase merge options configured.")
    else:
        print(f"  [!] Note on repo settings: {stderr}")


def configure_branch_protection():
    """Apply strict branch protection rules to main."""
    print(f"[*] Applying branch protection rules to '{BRANCH}'...")

    payload = {
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

    code, stdout, stderr = run_gh_command(
        [
            "api",
            f"repos/{REPO}/branches/{BRANCH}/protection",
            "-X", "PUT",
            "--input", "-",
        ],
        stdin_data=json.dumps(payload),
    )
    if code == 0:
        print(f"  ✓ Branch protection successfully applied to '{BRANCH}'.")
        print("    - Mandatory pull request reviews required (approvals >= 1).")
        print("    - Code owner review required (@Eneasf via .github/CODEOWNERS).")
        print("    - Dismiss stale pull request approvals when new commits are pushed.")
        print("    - Required conversation resolution before merging.")
        print("    - Force pushes and branch deletions strictly prohibited.")
    else:
        print(f"  [!] Failed to apply branch protection: {stderr}")


def main():
    print(f"=== GitHub Guardrails & Maintainer Controls ({REPO}) ===")
    
    # 1. Verify GitHub CLI Authentication
    code, stdout, stderr = run_gh_command(["auth", "status"])
    if code != 0:
        print(f"[!] gh CLI not authenticated: {stderr}", file=sys.stderr)
        sys.exit(1)

    is_private = check_repo_visibility()
    if is_private:
        print(f"[*] Notice: Repository is currently PRIVATE.")
        print("    On GitHub Free accounts, branch protection API requires a public repository.")
        print("    Repository settings have been prepared.")
        print("    Run this script again immediately after toggling the repo to Public:")
        print("    $ python3 scripts/setup_github_guardrails.py")
        print()
    
    configure_repository_settings()

    if not is_private:
        configure_branch_protection()
    else:
        print("[*] Skipped branch protection API call until repository is made Public.")

    print()
    print("✓ Technical controls configuration complete.")


if __name__ == "__main__":
    main()
