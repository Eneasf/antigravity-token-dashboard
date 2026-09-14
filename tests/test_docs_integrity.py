"""
Automated Documentation Integrity & Drift Prevention Test Suite.

Enforces that any newly authored or renamed source modules, scripts, test files,
milestones, and ADR decisions are faithfully documented in README.md and system specifications.
Fails CI if code changes drift from documentation.
"""

from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDocumentationIntegrity(unittest.TestCase):
    """Test suite ensuring README.md and architecture documentation stay synchronized with code."""

    @classmethod
    def setUpClass(cls):
        cls.readme_path = REPO_ROOT / "README.md"
        cls.assertTrue(cls.readme_path.exists(), "README.md must exist in repo root")
        cls.readme_text = cls.readme_path.read_text(encoding="utf-8")

        cls.handover_path = REPO_ROOT / "docs" / "HANDOVER.md"
        cls.assertTrue(cls.handover_path.exists(), "docs/HANDOVER.md must exist")
        cls.handover_text = cls.handover_path.read_text(encoding="utf-8")

    def test_readme_documents_all_src_modules(self):
        """Every Python module in src/ must be documented in README.md's Repository Structure."""
        src_dir = REPO_ROOT / "src"
        src_files = [f.name for f in src_dir.glob("*.py") if f.name != "__init__.py"]
        self.assertGreater(len(src_files), 0, "src/ directory must contain Python modules")

        missing_modules = []
        for filename in src_files:
            if filename not in self.readme_text:
                missing_modules.append(filename)

        self.assertEqual(
            missing_modules,
            [],
            f"README.md is missing documentation for source module(s): {missing_modules}. "
            f"Update README.md ## Repository Structure to describe these modules.",
        )

    def test_readme_documents_package_modules(self):
        """Every Python module in antigravity_telemetry/ must be documented in README.md's Repository Structure."""
        pkg_dir = REPO_ROOT / "antigravity_telemetry"
        pkg_files = [f.name for f in pkg_dir.glob("*.py") if f.name != "__init__.py"]
        self.assertGreater(len(pkg_files), 0, "antigravity_telemetry/ directory must contain Python modules")

        missing_modules = []
        for filename in pkg_files:
            if filename not in self.readme_text:
                missing_modules.append(filename)

        self.assertEqual(
            missing_modules,
            [],
            f"README.md is missing documentation for package module(s): {missing_modules}. "
            f"Update README.md ## Repository Structure to describe these package modules.",
        )

    def test_readme_documents_all_scripts(self):
        """Every script in scripts/ must be documented in README.md."""
        scripts_dir = REPO_ROOT / "scripts"
        script_files = [f.name for f in scripts_dir.glob("*.py") if f.name != "__init__.py"]
        self.assertGreater(len(script_files), 0, "scripts/ directory must contain Python scripts")

        missing_scripts = []
        for filename in script_files:
            if filename not in self.readme_text:
                missing_scripts.append(filename)

        self.assertEqual(
            missing_scripts,
            [],
            f"README.md is missing documentation for script(s): {missing_scripts}. "
            f"Update README.md ## Repository Structure to describe these scripts.",
        )

    def test_readme_documents_all_test_modules(self):
        """Every test module in tests/ must be documented in README.md's Repository Structure."""
        tests_dir = REPO_ROOT / "tests"
        test_files = [f.name for f in tests_dir.glob("test_*.py")]
        self.assertGreater(len(test_files), 0, "tests/ directory must contain test modules")

        missing_tests = []
        for filename in test_files:
            if filename not in self.readme_text:
                missing_tests.append(filename)

        self.assertEqual(
            missing_tests,
            [],
            f"README.md is missing documentation for test module(s): {missing_tests}. "
            f"Update README.md ## Repository Structure to describe these test modules.",
        )

    def test_readme_documents_latest_milestone(self):
        """README.md must reference the latest completed milestone slice in docs/milestones/."""
        milestones_dir = REPO_ROOT / "docs" / "milestones"
        milestone_files = list(milestones_dir.glob("M*.md"))
        self.assertGreater(len(milestone_files), 0, "docs/milestones/ must contain milestone files")

        milestone_nums = []
        for mf in milestone_files:
            m = re.match(r"M(\d+)", mf.name)
            if m:
                milestone_nums.append(int(m.group(1)))

        self.assertGreater(len(milestone_nums), 0, "Could not parse milestone numbers")
        latest_m_num = max(milestone_nums)
        expected_ref = f"M{latest_m_num}"

        self.assertTrue(
            expected_ref in self.readme_text or f"Milestone {latest_m_num}" in self.readme_text,
            f"README.md does not reference the latest milestone M{latest_m_num}. "
            f"Update README.md to include Milestone {latest_m_num} in highlights and repository structure.",
        )

    def test_readme_documents_latest_adr(self):
        """README.md must reference the latest Architecture Decision Record from docs/HANDOVER.md."""
        adr_matches = re.findall(r"ADR-(\d{3})", self.handover_text)
        self.assertGreater(len(adr_matches), 0, "docs/HANDOVER.md must contain ADR records")

        latest_adr_num = max(int(num) for num in adr_matches)
        latest_adr = f"ADR-{latest_adr_num:03d}"

        self.assertIn(
            latest_adr,
            self.readme_text,
            f"README.md does not reference the latest ADR ({latest_adr}). "
            f"Update README.md Key Highlights to cite {latest_adr}.",
        )

    def test_system_design_sync(self):
        """docs/SYSTEM_DESIGN.md must exist and document primary architecture components."""
        sys_design_path = REPO_ROOT / "docs" / "SYSTEM_DESIGN.md"
        self.assertTrue(sys_design_path.exists(), "docs/SYSTEM_DESIGN.md must exist")
        sys_design_text = sys_design_path.read_text(encoding="utf-8")

        for core_kw in ["telemetry_reader", "proto_parser", "aggregator"]:
            self.assertIn(
                core_kw,
                sys_design_text,
                f"docs/SYSTEM_DESIGN.md missing core component reference: {core_kw}",
            )


if __name__ == "__main__":
    unittest.main()
