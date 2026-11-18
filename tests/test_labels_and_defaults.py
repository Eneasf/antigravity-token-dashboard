"""
Unit & Regression Tests for Dynamic Labels, Simulator Defaults & Light Theme (Milestone 50 / Row 5).

Verifies:
  - Elimination of hardcoded labels ('Renews 24 Sep', 'Safe in Pro Quota', '100% Pro plan', 'SQLite WAL Hook')
  - Elimination of LaTeX mathematical notation in simulator slider labels
  - Simulator plan tier options renamed to clean capacity names ('Pro (1×)', 'Ultra (5×)', 'Ultra (20×)')
  - Simulator defaults tier selector from summary.tier
  - Simulator callout states 'hard stop at limit' when use_ai_credits is false
  - Canonical light theme standard across CSS :root, app.js activeTheme, and HTML bootstrap
"""

from pathlib import Path
import json
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestLabelsAndDefaults(unittest.TestCase):
    """Verifies label dynamicism, simulator defaults, and theme defaults."""

    def setUp(self):
        self.index_html_path = REPO_ROOT / "dashboard" / "index.html"
        self.js_dir = REPO_ROOT / "dashboard" / "js"
        self.styles_css_path = REPO_ROOT / "dashboard" / "styles.css"

        self.index_html = self.index_html_path.read_text(encoding="utf-8")
        self.all_js = "\n".join(f.read_text(encoding="utf-8") for f in sorted(self.js_dir.glob("*.js")))
        self.app_js = self.all_js
        self.styles_css = self.styles_css_path.read_text(encoding="utf-8")

    def test_no_hardcoded_stale_labels(self):
        """Zero occurrences of stale hardcoded strings in HTML and JS."""
        forbidden_patterns = [
            r"Renews 24 Sep",
            r"Safe in Pro Quota",
            r"100% Pro plan",
            r"SQLite WAL Hook",
        ]
        files = {
            "index.html": self.index_html,
            "all_js": self.all_js,
        }

        for fname, content in files.items():
            for pat in forbidden_patterns:
                matches = re.findall(pat, content)
                self.assertEqual(
                    matches,
                    [],
                    f"Found forbidden hardcoded string '{pat}' in {fname}",
                )

    def test_zero_latex_in_html(self):
        """Zero LaTeX mathematical notation in index.html."""
        latex_pattern = re.compile(r"\$[A-Za-z\\{]")
        matches = latex_pattern.findall(self.index_html)
        self.assertEqual(
            matches,
            [],
            f"Found LaTeX mathematical token in index.html: {matches}",
        )

    def test_simulator_slider_labels_plain_english(self):
        """Simulator slider labels must use plain English titles."""
        expected_labels = [
            "Average prompt size (tokens)",
            "Cache hit ratio (%)",
            "Thinking tokens per turn",
            "Candidate answer output (tokens)",
            "Minutes between turns",
        ]
        for label in expected_labels:
            self.assertIn(label, self.index_html, f"Missing label '{label}' in index.html")

    def test_simulator_tier_names(self):
        """Simulator tier dropdown options must use clean capacity names."""
        expected_options = [
            '<option value="pro">Pro (1×)</option>',
            '<option value="ultra_5x">Ultra (5×)</option>',
            '<option value="ultra_20x">Ultra (20×)</option>',
        ]
        for opt in expected_options:
            self.assertIn(opt, self.index_html, f"Missing tier option '{opt}' in index.html")

    def test_light_theme_is_canonical_default(self):
        """CSS :root and JS bootstrap must default to Light Theme (ADR-048)."""
        self.assertIn(
            ':root, [data-theme="light"]',
            self.styles_css,
            "styles.css must bind light theme variables to :root",
        )
        self.assertNotIn(
            ':root, [data-theme="dark"]',
            self.styles_css,
            "styles.css must not bind dark theme variables to :root",
        )
        self.assertIn(
            'activeTheme = "light";',
            self.app_js,
            "JS must initialize activeTheme to 'light'",
        )
        self.assertIn(
            '(savedTheme === "dark") ? "dark" : "light"',
            self.index_html,
            "index.html pre-render bootstrap must default to 'light'",
        )

    def test_data_freshness_badge_exists(self):
        """Data freshness badge replaces SQLite WAL Hook in header."""
        self.assertIn('id="data-freshness-badge"', self.index_html)
        self.assertIn('document.getElementById("data-freshness-badge")', self.app_js)

    def test_simulator_hard_stop_logic_in_app_js(self):
        """app.js must state hard stop at limit when use_ai_credits is false."""
        self.assertIn("use_ai_credits !== false", self.app_js)
        self.assertIn("Credit overages disabled: hard stop at limit until window resets", self.app_js)

    def test_simulator_defaults_to_summary_tier(self):
        """initSimulator must set sim-plan-select to globalDashboardData.summary.tier."""
        self.assertIn('globalDashboardData.summary.tier', self.app_js)
        self.assertIn('planSelect.value = summaryTier', self.app_js)


if __name__ == "__main__":
    unittest.main()
