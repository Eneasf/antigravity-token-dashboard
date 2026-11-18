"""
Automated Documentation Integrity & Drift Prevention Test Suite.

Enforces that any newly authored or renamed source modules, scripts, test files,
milestones, and ADR decisions are faithfully documented in docs/REPO_MAP.md,
CHANGELOG.md, and docs/DECISIONS.md.
Fails CI if code changes drift from documentation.
"""

from pathlib import Path
import json
import os
import re
import subprocess
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


class DocsIntegrityTest(unittest.TestCase):
    """Test suite ensuring docs/REPO_MAP.md, CHANGELOG.md, and docs/DECISIONS.md stay synchronized with code."""

    @classmethod
    def setUpClass(cls):
        cls.readme_path = REPO_ROOT / "README.md"
        cls.assertTrue(cls.readme_path.exists(), "README.md must exist in repo root")
        cls.readme_text = cls.readme_path.read_text(encoding="utf-8")

        cls.decisions_path = REPO_ROOT / "docs" / "DECISIONS.md"
        cls.assertTrue(cls.decisions_path.exists(), "docs/DECISIONS.md must exist")
        cls.decisions_text = cls.decisions_path.read_text(encoding="utf-8")

        cls.repo_map_path = REPO_ROOT / "docs" / "REPO_MAP.md"
        cls.assertTrue(cls.repo_map_path.exists(), "docs/REPO_MAP.md must exist")
        cls.repo_map_text = cls.repo_map_path.read_text(encoding="utf-8")

        cls.changelog_path = REPO_ROOT / "CHANGELOG.md"
        cls.assertTrue(cls.changelog_path.exists(), "CHANGELOG.md must exist in repo root")
        cls.changelog_text = cls.changelog_path.read_text(encoding="utf-8")

    def test_readme_documents_all_src_modules(self):
        """Every Python module in src/ must be documented in docs/REPO_MAP.md."""
        src_dir = REPO_ROOT / "src"
        src_files = [f.name for f in src_dir.glob("*.py") if f.name != "__init__.py"]
        self.assertGreater(len(src_files), 0, "src/ directory must contain Python modules")

        missing_modules = []
        for filename in src_files:
            if filename not in self.repo_map_text:
                missing_modules.append(filename)

        self.assertEqual(
            missing_modules,
            [],
            f"docs/REPO_MAP.md is missing documentation for source module(s): {missing_modules}. "
            f"Update docs/REPO_MAP.md to describe these modules.",
        )

    def test_readme_documents_package_modules(self):
        """Every Python module in antigravity_telemetry/ must be documented in docs/REPO_MAP.md."""
        pkg_dir = REPO_ROOT / "antigravity_telemetry"
        pkg_files = [f.name for f in pkg_dir.glob("*.py") if f.name != "__init__.py"]
        self.assertGreater(len(pkg_files), 0, "antigravity_telemetry/ directory must contain Python modules")

        missing_modules = []
        for filename in pkg_files:
            if filename not in self.repo_map_text:
                missing_modules.append(filename)

        self.assertEqual(
            missing_modules,
            [],
            f"docs/REPO_MAP.md is missing documentation for package module(s): {missing_modules}. "
            f"Update docs/REPO_MAP.md to describe these package modules.",
        )

    def test_readme_documents_all_scripts(self):
        """Every script in scripts/ must be documented in docs/REPO_MAP.md."""
        scripts_dir = REPO_ROOT / "scripts"
        script_files = [f.name for f in scripts_dir.glob("*.py") if f.name != "__init__.py"]
        self.assertGreater(len(script_files), 0, "scripts/ directory must contain Python scripts")

        missing_scripts = []
        for filename in script_files:
            if filename not in self.repo_map_text:
                missing_scripts.append(filename)

        self.assertEqual(
            missing_scripts,
            [],
            f"docs/REPO_MAP.md is missing documentation for script(s): {missing_scripts}. "
            f"Update docs/REPO_MAP.md to describe these scripts.",
        )

    def test_readme_documents_all_test_modules(self):
        """Every test module in tests/ must be documented in docs/REPO_MAP.md."""
        tests_dir = REPO_ROOT / "tests"
        test_files = [f.name for f in tests_dir.glob("test_*.py")]
        self.assertGreater(len(test_files), 0, "tests/ directory must contain test modules")

        missing_tests = []
        for filename in test_files:
            if filename not in self.repo_map_text:
                missing_tests.append(filename)

        # Verify tests/e2e_bridge/test_playwright_e2e.py is documented in docs/REPO_MAP.md
        e2e_bridge_test = REPO_ROOT / "tests" / "e2e_bridge" / "test_playwright_e2e.py"
        self.assertTrue(e2e_bridge_test.exists(), f"E2E bridge test file must exist at {e2e_bridge_test}")
        if "test_playwright_e2e.py" not in self.repo_map_text:
            missing_tests.append("tests/e2e_bridge/test_playwright_e2e.py")

        self.assertEqual(
            missing_tests,
            [],
            f"docs/REPO_MAP.md is missing documentation for test module(s): {missing_tests}. "
            f"Update docs/REPO_MAP.md to describe these test modules.",
        )

    def test_readme_has_zero_milestones_and_adrs(self):
        """README.md must contain zero occurrences of 'Milestone [0-9]+' or 'ADR-[0-9]+'."""
        matches = re.findall(r"Milestone [0-9]+|ADR-[0-9]+", self.readme_text)
        self.assertEqual(
            matches,
            [],
            f"README.md contains milestone/ADR references: {matches}. "
            "All milestone details belong in CHANGELOG.md and ADRs in docs/DECISIONS.md.",
        )

    def test_changelog_documents_latest_milestone(self):
        """CHANGELOG.md must reference the latest completed milestone slice in docs/milestones/."""
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
            expected_ref in self.changelog_text or f"Milestone {latest_m_num}" in self.changelog_text,
            f"CHANGELOG.md does not reference the latest milestone M{latest_m_num}. "
            f"Update CHANGELOG.md to include Milestone {latest_m_num}.",
        )

    def test_decisions_documents_latest_adr(self):
        """docs/DECISIONS.md must reference the latest Architecture Decision Record."""
        adr_nums = []
        for path in (REPO_ROOT / "docs" / "milestones").glob("*.md"):
            content = path.read_text(encoding="utf-8", errors="ignore")
            adr_nums.extend(int(m) for m in re.findall(r"ADR-(\d{3})", content))
        if not adr_nums:
            adr_nums = [int(m) for m in re.findall(r"ADR-(\d{3})", self.decisions_text)]
        self.assertGreater(len(adr_nums), 0, "Must find ADR records")
        latest_adr = f"ADR-{max(adr_nums):03d}"

        self.assertIn(
            latest_adr,
            self.decisions_text,
            f"docs/DECISIONS.md does not reference the latest ADR ({latest_adr}).",
        )

    def test_stale_numbers(self):
        """No documentation file should contain driftable exact counts like line counts, KB sizes, or test counts."""
        patterns = [
            re.compile(r"\d+,\d{3} lines"),
            re.compile(r"\d+ KB"),
            re.compile(r"\d+ tests"),
        ]
        target_files = [REPO_ROOT / "README.md"]
        docs_dir = REPO_ROOT / "docs"
        if docs_dir.exists():
            for p in docs_dir.rglob("*.md"):
                if "milestones" in p.parts or "archive" in p.parts:
                    continue
                if p.name.startswith("AUDIT_"):
                    continue
                target_files.append(p)

        violations = []
        for file_path in target_files:
            if not file_path.exists():
                continue
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for pat in patterns:
                matches = pat.findall(content)
                if matches:
                    rel_path = file_path.relative_to(REPO_ROOT)
                    violations.append(f"{rel_path}: matches {matches} for pattern {pat.pattern}")

        self.assertEqual(
            violations,
            [],
            f"Found stale exact numbers in documentation files:\n" + "\n".join(violations),
        )

    def test_package_json_version_matches_highest_tag(self):
        """package.json version must match the highest git tag, allowing 2.5.0 or 2.6.0 during consolidation."""
        pkg_path = REPO_ROOT / "package.json"
        self.assertTrue(pkg_path.exists(), "package.json must exist")
        pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
        pkg_version = pkg_data.get("version", "")

        git_target = Path(os.environ.get("GATE_SOURCE_DIR", REPO_ROOT))
        if not (git_target / ".git").exists() and not (REPO_ROOT / ".git").exists():
            self.skipTest("Not running inside a git repository")
        target_dir = git_target if (git_target / ".git").exists() else REPO_ROOT

        proc = subprocess.run(
            ["git", "tag", "--sort=-v:refname"],
            capture_output=True,
            text=True,
            cwd=target_dir,
            timeout=10.0,
        )
        if proc.returncode != 0:
            self.skipTest(f"git tag command failed (not a git repo?): {proc.stderr}")
        tags = [t.strip() for t in proc.stdout.splitlines() if t.strip()]
        if not tags:
            self.skipTest("No git tags in repository (e.g. throwaway archive checkout)")
        highest_tag = tags[0]

        self.assertEqual(
            f"v{pkg_version}",
            highest_tag,
            f"package.json version 'v{pkg_version}' does not match highest tag '{highest_tag}'",
        )

    def test_version_manifest_sync(self):
        """pyproject.toml version, package.json version, and latest git tag must be strictly identical."""
        pyproject_path = REPO_ROOT / "pyproject.toml"
        self.assertTrue(pyproject_path.exists(), "pyproject.toml must exist in repo root")
        try:
            import tomllib
            with open(pyproject_path, "rb") as f:
                pyproject_data = tomllib.load(f)
            py_version = pyproject_data.get("project", {}).get("version", "")
        except ImportError:
            import re
            m = re.search(r'version\s*=\s*"([^"]+)"', pyproject_path.read_text(encoding="utf-8"))
            py_version = m.group(1) if m else ""

        pkg_path = REPO_ROOT / "package.json"
        self.assertTrue(pkg_path.exists(), "package.json must exist in repo root")
        pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
        js_version = pkg_data.get("version", "")

        git_target = Path(os.environ.get("GATE_SOURCE_DIR", REPO_ROOT))
        if not (git_target / ".git").exists() and not (REPO_ROOT / ".git").exists():
            self.skipTest("Not running inside a git repository")
        target_dir = git_target if (git_target / ".git").exists() else REPO_ROOT

        proc = subprocess.run(
            ["git", "tag", "--sort=-v:refname"],
            capture_output=True,
            text=True,
            cwd=target_dir,
            timeout=10.0,
        )
        if proc.returncode != 0:
            self.skipTest(f"git tag command failed (not a git repo?): {proc.stderr}")
        tags = [t.strip() for t in proc.stdout.splitlines() if t.strip()]
        if not tags:
            self.skipTest("No git tags in repository (e.g. throwaway archive checkout)")
        self.assertGreater(len(tags), 0, "Repository must have at least one git tag")
        latest_tag = tags[0].lstrip("v")

        self.assertTrue(bool(py_version), "pyproject.toml must define project.version")
        self.assertTrue(bool(js_version), "package.json must define version")
        self.assertEqual(
            py_version,
            js_version,
            f"Version desync: pyproject.toml ({py_version}) != package.json ({js_version})",
        )
        self.assertEqual(
            py_version,
            latest_tag,
            f"Version desync: manifests ({py_version}) != latest git tag ({latest_tag})",
        )

    def test_vdone_python_c_gates(self):
        """Extract all CHECK commands starting with 'python3 -c' in VDONE.md, executing each with timeout=60, asserting exit code 0."""
        vdone_path = REPO_ROOT / "VDONE.md"
        self.assertTrue(vdone_path.exists(), "VDONE.md must exist in repo root")

        content = vdone_path.read_text(encoding="utf-8")
        pattern = re.compile(r"CHECK\s+(python3\s+-c\s+.*?)(?:\s{2,}EXPECT|\s+EXPECT|$)", re.MULTILINE)
        commands = pattern.findall(content)
        self.assertGreater(len(commands), 0, "VDONE.md must contain at least one python3 -c CHECK gate")

        for cmd in commands:
            cmd = cmd.strip()
            with self.subTest(cmd=cmd):
                proc = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self.assertEqual(
                    proc.returncode,
                    0,
                    f"VDONE CHECK command failed with exit code {proc.returncode}:\nCommand: {cmd}\nStdout: {proc.stdout}\nStderr: {proc.stderr}",
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
