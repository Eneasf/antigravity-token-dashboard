"""
Unit and integration test harness for scripts/setup_github_guardrails.py (Row 10 / Finding C9).

Verifies:
1. Branch protection payload schema and required technical controls.
2. Repository settings API argument construction.
3. CLI argument parsing, flags, and hermetic dry-run simulation.
4. Repo visibility parsing (private vs public GitHub accounts).
5. gh command execution handling, timeouts, and missing binary resilience.
6. End-to-end main() lifecycle under authenticated, unauthenticated, and dry-run paths.
"""

import contextlib
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent

from scripts.setup_github_guardrails import (
    build_branch_protection_payload,
    build_parser,
    build_repo_settings_args,
    check_repo_visibility,
    configure_branch_protection,
    configure_repository_settings,
    main,
    run_gh_command,
)


class TestSetupGitHubGuardrails(unittest.TestCase):
    """Test suite ensuring scripts/setup_github_guardrails.py operates safely with full coverage."""

    def test_branch_protection_payload_structure(self):
        """Verify the exact technical controls in the branch protection payload."""
        payload = build_branch_protection_payload()

        status_checks = payload.get("required_status_checks", {})
        self.assertTrue(status_checks.get("strict"), "Status checks must require branches to be up to date")
        contexts = status_checks.get("contexts", [])
        self.assertIn("Test (macos-latest - Python 3.12)", contexts)
        self.assertIn("Test (ubuntu-latest - Python 3.12)", contexts)

        reviews = payload.get("required_pull_request_reviews", {})
        self.assertTrue(reviews.get("dismiss_stale_reviews"), "Must dismiss stale reviews")
        self.assertTrue(reviews.get("require_code_owner_reviews"), "Must require CODEOWNERS reviews")
        self.assertEqual(reviews.get("required_approving_review_count"), 1)
        self.assertTrue(reviews.get("require_last_push_approval"), "Must require last push approval")

        self.assertFalse(payload.get("allow_force_pushes"), "Force pushes must be prohibited")
        self.assertFalse(payload.get("allow_deletions"), "Branch deletions must be prohibited")
        self.assertTrue(payload.get("required_conversation_resolution"), "Must require conversation resolution")

    def test_repo_settings_args(self):
        """Verify gh api argument construction for repository settings."""
        args = build_repo_settings_args("CustomOrg/CustomRepo")
        self.assertIn("repos/CustomOrg/CustomRepo", args[1])
        self.assertIn("delete_branch_on_merge=true", args)
        self.assertIn("allow_auto_merge=true", args)
        self.assertIn("allow_squash_merge=true", args)
        self.assertIn("allow_rebase_merge=true", args)

    def test_build_parser_options(self):
        """Verify CLI argument parser configuration."""
        parser = build_parser()
        args = parser.parse_args([
            "--repo", "TestOwner/TestRepo",
            "--branch", "release",
            "--dry-run",
        ])
        self.assertEqual(args.repo, "TestOwner/TestRepo")
        self.assertEqual(args.branch, "release")
        self.assertTrue(args.dry_run)

    def test_main_dry_run_mode(self):
        """Verify that --dry-run operates purely offline without invoking gh."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), patch("scripts.setup_github_guardrails.run_gh_command") as mock_gh:
            exit_code = main(["--dry-run"])

        self.assertEqual(exit_code, 0)
        mock_gh.assert_not_called()
        output = buf.getvalue()
        self.assertIn("DRY RUN MODE", output)
        self.assertIn("Would apply branch protection rules", output)
        self.assertIn("Technical controls configuration simulated successfully", output)

    @patch("scripts.setup_github_guardrails.run_gh_command")
    def test_check_repo_visibility(self, mock_gh):
        """Verify repo visibility parsing for private, public, and error cases."""
        mock_gh.return_value = (0, "true", "")
        self.assertTrue(check_repo_visibility("Test/Repo"))

        mock_gh.return_value = (0, "false", "")
        self.assertFalse(check_repo_visibility("Test/Repo"))

        # On API failure, safe default is True (treat as private to avoid failing free tier)
        mock_gh.return_value = (1, "", "Not Found")
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            self.assertTrue(check_repo_visibility("Test/Repo"))

    @patch("scripts.setup_github_guardrails.run_gh_command")
    def test_configure_repository_settings(self, mock_gh):
        """Verify configure_repository_settings handles success and failure."""
        mock_gh.return_value = (0, "", "")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = configure_repository_settings("Test/Repo", dry_run=False)
        self.assertEqual(code, 0)
        self.assertIn("Auto-delete head branches after PR merge enabled", buf.getvalue())

        mock_gh.return_value = (1, "", "API rate limit exceeded")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = configure_repository_settings("Test/Repo", dry_run=False)
        self.assertEqual(code, 1)
        self.assertIn("Note on repo settings", buf.getvalue())

        # Dry run bypasses gh command
        mock_gh.reset_mock()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = configure_repository_settings("Test/Repo", dry_run=True)
        self.assertEqual(code, 0)
        mock_gh.assert_not_called()

    @patch("scripts.setup_github_guardrails.run_gh_command")
    def test_configure_branch_protection(self, mock_gh):
        """Verify configure_branch_protection handles success and failure."""
        mock_gh.return_value = (0, "", "")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = configure_branch_protection("Test/Repo", "main", dry_run=False)
        self.assertEqual(code, 0)
        self.assertIn("Branch protection successfully applied", buf.getvalue())

        mock_gh.return_value = (1, "", "Upgrade to GitHub Team")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = configure_branch_protection("Test/Repo", "main", dry_run=False)
        self.assertEqual(code, 1)
        self.assertIn("Failed to apply branch protection", buf.getvalue())

        # Dry run bypasses gh command
        mock_gh.reset_mock()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = configure_branch_protection("Test/Repo", "main", dry_run=True)
        self.assertEqual(code, 0)
        mock_gh.assert_not_called()

    @patch("scripts.setup_github_guardrails.subprocess.run")
    def test_run_gh_command_timeout(self, mock_run):
        """Verify run_gh_command handles subprocess.TimeoutExpired gracefully."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["gh", "api"], timeout=30.0)
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code, stdout, stderr = run_gh_command(["api", "test"])
        self.assertEqual(code, 1)
        self.assertIn("timed out after 30s", stderr)

    @patch("scripts.setup_github_guardrails.subprocess.run")
    def test_run_gh_command_missing_binary(self, mock_run):
        """Verify run_gh_command handles missing gh executable gracefully."""
        mock_run.side_effect = FileNotFoundError()
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code, stdout, stderr = run_gh_command(["auth", "status"])
        self.assertEqual(code, 1)
        self.assertIn("not installed", stderr)

    @patch("scripts.setup_github_guardrails.run_gh_command")
    def test_main_auth_failure(self, mock_gh):
        """Verify main() exits 1 when gh auth status reports not authenticated."""
        mock_gh.return_value = (1, "", "You are not logged into any GitHub hosts.")
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        with contextlib.redirect_stdout(buf_out), contextlib.redirect_stderr(buf_err):
            exit_code = main([])
        self.assertEqual(exit_code, 1)
        self.assertIn("gh CLI not authenticated", buf_err.getvalue())

    @patch("scripts.setup_github_guardrails.run_gh_command")
    def test_main_public_repo_success(self, mock_gh):
        """Verify main() runs full workflow on public repo when authenticated."""
        def gh_side_effect(args, stdin_data=None):
            if args == ["auth", "status"]:
                return (0, "Logged in to github.com account", "")
            elif "view" in args:
                return (0, "false", "")  # isPrivate = false
            elif "api" in args:
                return (0, "{}", "")
            return (0, "", "")

        mock_gh.side_effect = gh_side_effect
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = main([])
        self.assertEqual(exit_code, 0)
        output = buf.getvalue()
        self.assertIn("Branch protection successfully applied", output)
        self.assertIn("Technical controls configuration complete", output)


if __name__ == "__main__":
    unittest.main()
