"""
Test Suite Hygiene and Output Leak Prevention (ADR-074 / Milestone 60 / Row 15).

Asserts that running the unit test suites of export, watcher, packaging, and showcase modules
produces zero leaked output to sys.stdout or sys.stderr.
"""

import contextlib
import io
import unittest


class TestSuiteHygiene(unittest.TestCase):
    """Test suite ensuring critical modules execute with zero stdout/stderr leakage."""

    def _assert_module_zero_leak(self, module_name: str):
        suite = unittest.defaultTestLoader.loadTestsFromName(module_name)
        runner_stream = io.StringIO()
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        runner = unittest.TextTestRunner(stream=runner_stream, verbosity=0)
        with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
            result = runner.run(suite)

        self.assertTrue(
            result.wasSuccessful(),
            f"Test suite {module_name} failed:\n{runner_stream.getvalue()}\nErrors: {result.errors}\nFailures: {result.failures}",
        )
        self.assertEqual(
            captured_stdout.getvalue(),
            "",
            f"Test suite {module_name} leaked stdout:\n{captured_stdout.getvalue()}",
        )
        self.assertEqual(
            captured_stderr.getvalue(),
            "",
            f"Test suite {module_name} leaked stderr:\n{captured_stderr.getvalue()}",
        )

    def test_ci_fixtures_zero_leak(self):
        self._assert_module_zero_leak("tests.test_ci_fixtures")

    def test_demo_showcase_zero_leak(self):
        self._assert_module_zero_leak("tests.test_demo_showcase")

    def test_export_dashboard_zero_leak(self):
        self._assert_module_zero_leak("tests.test_export_dashboard")

    def test_export_lock_zero_leak(self):
        self._assert_module_zero_leak("tests.test_export_lock")

    def test_ingest_statement_zero_leak(self):
        self._assert_module_zero_leak("tests.test_ingest_statement")

    def test_menubar_packaging_zero_leak(self):
        self._assert_module_zero_leak("tests.test_menubar_packaging")

    def test_watch_telemetry_zero_leak(self):
        self._assert_module_zero_leak("tests.test_watch_telemetry")


if __name__ == "__main__":
    unittest.main()
