"""
Playwright End-to-End Test Suite Bridge.

Executes Playwright browser test specs across layout invariants, navigation tabs,
shell modes, theme and currency controls, and visual screenshot generation.
"""

from pathlib import Path
import shutil
import subprocess
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestPlaywrightE2E(unittest.TestCase):
    """Bridge test running Playwright E2E browser tests through Python unittest."""

    @classmethod
    def setUpClass(cls):
        import os
        if os.environ.get("SKIP_PLAYWRIGHT") == "1" or os.environ.get("_IN_VDONE_GATE_RUNNER") == "1":
            raise unittest.SkipTest("Playwright E2E tests disabled for standard unit suite.")

        cls.npx_bin = shutil.which("npx")
        if not cls.npx_bin:
            raise unittest.SkipTest("npx is not installed on the system; skipping Playwright E2E tests.")

        # Verify node_modules/@playwright/test exists
        playwright_pkg = REPO_ROOT / "node_modules" / "@playwright" / "test"
        if not playwright_pkg.exists():
            raise unittest.SkipTest("@playwright/test is not installed in node_modules; run npm install.")

    def test_playwright_e2e_suite(self):
        """Execute all Playwright E2E test specs (layout, navigation, controls, screenshots)."""
        cmd = [self.npx_bin, "playwright", "test"]
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        if proc.returncode != 0:
            print("\n=== Playwright STDOUT ===")
            print(proc.stdout)
            print("\n=== Playwright STDERR ===")
            print(proc.stderr)
        self.assertEqual(
            proc.returncode,
            0,
            f"Playwright E2E test suite failed with exit code {proc.returncode}.\n{proc.stdout}\n{proc.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
