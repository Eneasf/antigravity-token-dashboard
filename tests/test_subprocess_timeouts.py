"""
Test Suite: Subprocess Timeout Hardening & Bounded Execution (Finding C4)

Ensures all subprocess invocations across `src/` and `scripts/` specify explicit,
bounded `timeout=` keyword arguments to prevent infinite blocking or hung daemons.
"""

import ast
import glob
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestSubprocessTimeouts(unittest.TestCase):
    """Verifies that all subprocess calls in production and maintenance code enforce timeouts."""

    def test_all_subprocess_calls_have_explicit_timeout(self):
        """AST scan over src/ and scripts/ must find 0 subprocess.run or Popen calls lacking timeout=."""
        py_files = sorted(
            glob.glob(str(REPO_ROOT / "src" / "**" / "*.py"), recursive=True)
            + glob.glob(str(REPO_ROOT / "scripts" / "**" / "*.py"), recursive=True)
        )
        self.assertGreater(len(py_files), 0, "No python files found in src/ or scripts/")

        missing_timeouts = []
        timeout_calls_count = 0

        for file_path in py_files:
            rel_path = Path(file_path).relative_to(REPO_ROOT).as_posix()
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=rel_path)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func_attr = getattr(node.func, "attr", "")
                    if func_attr in ("run", "Popen"):
                        has_timeout = any(kw.arg == "timeout" for kw in node.keywords)
                        if not has_timeout:
                            missing_timeouts.append(f"{rel_path}:{node.lineno} ({func_attr})")
                        else:
                            timeout_calls_count += 1

        self.assertEqual(
            len(missing_timeouts),
            0,
            f"Found {len(missing_timeouts)} subprocess call(s) lacking timeout=:\n"
            + "\n".join(missing_timeouts),
        )
        self.assertGreaterEqual(timeout_calls_count, 28, "Expected at least 28 hardened subprocess calls")

    def test_timeout_scanner_detects_missing_timeout(self):
        """Negative assertion: verify that the AST scanner correctly flags calls without timeout."""
        code = (
            "import subprocess\n"
            "subprocess.run(['ls', '-la'])\n"
            "subprocess.Popen(['sleep', '1'])\n"
            "subprocess.run(['ps'], timeout=10.0)\n"
        )
        tree = ast.parse(code)
        flagged = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") in ("run", "Popen"):
                if not any(kw.arg == "timeout" for kw in node.keywords):
                    flagged.append(node.lineno)

        self.assertEqual(flagged, [2, 3])


if __name__ == "__main__":
    unittest.main()
