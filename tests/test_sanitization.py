"""
Automated Telemetry & PII Sanitization Regression Test Suite (ADR-049 / Milestone 35).

Enforces that:
1. Zero local user paths or machine usernames exist in any tracked file.
2. Zero real conversation IDs exist in docs or config.
3. Zero enterprise/work keywords exist in docs or config.
4. Zero unowned domain emails (@antigravity.community) exist in project metadata.
5. Zero overclaiming research group personas exist.
"""

from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories to audit
AUDIT_DIRS = [
    REPO_ROOT / "docs",
    REPO_ROOT / "config",
    REPO_ROOT / "data",
    REPO_ROOT / ".github",
    REPO_ROOT / "src",
    REPO_ROOT / "antigravity_telemetry",
    REPO_ROOT / "tests" / "fixtures",
    REPO_ROOT / "macos",
]

# Individual root files to audit
AUDIT_FILES = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "CHANGELOG.md",
    REPO_ROOT / "pyproject.toml",
    REPO_ROOT / "package.json",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "CONTRIBUTING.md",
]


class TestTelemetrySanitization(unittest.TestCase):
    """Regression gate ensuring zero PII, enterprise terms, or unscrubbed telemetry leaks."""

    def _collect_files(self):
        files = []
        for d in AUDIT_DIRS:
            if d.exists():
                for p in d.rglob("*"):
                    if p.is_file() and not p.name.endswith((".png", ".jpg", ".jpeg", ".ico", ".woff2", ".db", ".db-wal", ".db-shm", ".pyc", ".pyo")):
                        if "__pycache__" in p.parts or ".build" in p.parts:
                            continue
                        # Skip git-ignored personal exhaustion ledger if present locally
                        if p.name == "exhaustion_ledger.json":
                            continue
                        files.append(p)
        for f in AUDIT_FILES:
            if f.exists() and f.is_file():
                files.append(f)
        return files

    def test_zero_local_user_home_paths(self):
        """No tracked document or code file should contain local machine usernames or home paths."""
        forbidden = [
            "Users" + "/eneasf",
            "home" + "/eneasf",
        ]
        violations = []
        for file_path in self._collect_files():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for needle in forbidden:
                if needle.lower() in content.lower():
                    violations.append(f"{file_path.relative_to(REPO_ROOT)}: contains '{needle}'")

        self.assertEqual(
            violations,
            [],
            f"Found forbidden local user home path(s) in repository:\n" + "\n".join(violations),
        )

    def test_zero_leaked_real_conversation_uuids(self):
        """No documentation or config file should contain leaked conversation UUIDs."""
        forbidden_uuids = [
            "df35" + "048e",
        ]
        violations = []
        for file_path in self._collect_files():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for needle in forbidden_uuids:
                if needle.lower() in content.lower():
                    violations.append(f"{file_path.relative_to(REPO_ROOT)}: contains '{needle}'")

        self.assertEqual(
            violations,
            [],
            f"Found leaked conversation UUID(s) in repository:\n" + "\n".join(violations),
        )

    def test_zero_enterprise_or_client_keywords(self):
        """No documentation or report should reference enterprise work systems."""
        violations = []
        pattern = re.compile(r"\b(" + "AT" + "LAS|" + "S" + "AP" + r")\b", re.IGNORECASE)
        for file_path in self._collect_files():
            # Only check docs/ and config/
            if "docs" not in file_path.parts and "config" not in file_path.parts:
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            matches = pattern.findall(content)
            if matches:
                violations.append(f"{file_path.relative_to(REPO_ROOT)}: matched {set(matches)}")

        self.assertEqual(
            violations,
            [],
            f"Found enterprise/client keywords in docs/config:\n" + "\n".join(violations),
        )

    def test_zero_unowned_email_domains(self):
        """No metadata or code should use unowned domain emails (e.g. @antigravity.community)."""
        violations = []
        forbidden_domain = "antigravity.community"
        for file_path in self._collect_files():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if forbidden_domain in content:
                violations.append(f"{file_path.relative_to(REPO_ROOT)}: contains '{forbidden_domain}'")

        self.assertEqual(
            violations,
            [],
            f"Found unowned email domain '{forbidden_domain}' in:\n" + "\n".join(violations),
        )

    def test_zero_overclaiming_group_personas(self):
        """Whitepaper and docs must be attributed authentically, not to an invented research group."""
        forbidden_phrase = "Deterministic Antigravity Telemetry Research Group"
        violations = []
        for file_path in self._collect_files():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if forbidden_phrase in content:
                violations.append(f"{file_path.relative_to(REPO_ROOT)}: contains '{forbidden_phrase}'")

        self.assertEqual(
            violations,
            [],
            f"Found overclaiming persona in:\n" + "\n".join(violations),
        )

    def test_zero_geminu_or_private_workspace_needles(self):
        """No tracked document or code file should contain 'Geminu' or 'token consumption dashboard.'."""
        forbidden = [
            "Gem" + "inu",
            "token consumption " + "dashboard.",
        ]
        violations = []
        for file_path in self._collect_files():
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for needle in forbidden:
                if needle.lower() in content.lower():
                    violations.append(f"{file_path.relative_to(REPO_ROOT)}: contains '{needle}'")

        self.assertEqual(
            violations,
            [],
            f"Found forbidden private workspace needle(s) in repository:\n" + "\n".join(violations),
        )

    def test_detection_triggers_failure_on_forbidden_needle(self):
        """Verify that forbidden needle detection catches simulated needles."""
        forbidden = ["Gem" + "inu", "token consumption " + "dashboard."]
        sample_with_typo = "This is a reference to Gem" + "inu token consumption in a workspace."
        violations = [n for n in forbidden if n.lower() in sample_with_typo.lower()]
        self.assertIn("Gem" + "inu", violations)

        sample_with_dashboard = "Workspace path: /path/to/token consumption " + "dashboard."
        violations2 = [n for n in forbidden if n.lower() in sample_with_dashboard.lower()]
        self.assertIn("token consumption " + "dashboard.", violations2)


if __name__ == "__main__":
    unittest.main()
