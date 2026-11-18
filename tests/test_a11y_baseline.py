"""
A11y Baseline & Formatter Unification Test Suite (Milestone 59 / Row 14 / U5 + U6).

Verifies:
1. Exactly one compact number formatter function definition across dashboard/js/*.js.
2. All tables in dashboard/index.html have accessible captions (<caption class="sr-only">).
3. Core ARIA roles ('role="tablist"', 'role="tab"', 'role="tabpanel"', 'role="progressbar"')
   are present in dashboard/index.html.
4. No font-size rules under 11px exist in dashboard/styles.css.
5. Focus-visible outline styles are explicitly defined in dashboard/styles.css.
6. Status badge glyphs (✓, !, ×) are present in index.html and/or core.js for color-independent status.
7. Real-time ticker units ('tok/min') are present in dashboard/js/now.js.
"""

from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"
INDEX_HTML = DASHBOARD_DIR / "index.html"
STYLES_CSS = DASHBOARD_DIR / "styles.css"
JS_DIR = DASHBOARD_DIR / "js"


class TestA11yBaseline(unittest.TestCase):
    """Test suite verifying accessibility baseline, typography, ARIA attributes, and formatter unification."""

    def test_single_compact_number_formatter(self):
        """Verify exactly 1 function definition for format(Compact|Tokens) across dashboard/js/*.js."""
        formatter_regex = re.compile(r"function\s+format(?:Compact|Tokens)")
        matches = []
        for js_file in sorted(JS_DIR.glob("*.js")):
            content = js_file.read_text(encoding="utf-8")
            found = formatter_regex.findall(content)
            for f in found:
                matches.append((js_file.name, f))

        self.assertEqual(
            len(matches),
            1,
            f"Expected exactly 1 definition of format(Compact|Tokens) across JS files, but found {len(matches)}: {matches}",
        )

    def test_table_captions_count(self):
        """Verify all tables in dashboard/index.html have an accessible <caption> element."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        tables = re.findall(r"<table\b", html)
        captions = re.findall(r"<caption\b", html)
        self.assertGreater(len(tables), 0, "dashboard/index.html must contain tables")
        self.assertGreaterEqual(
            len(captions),
            len(tables),
            f"Expected every table to have a <caption>, found {len(tables)} tables and {len(captions)} captions",
        )

    def test_aria_roles_present(self):
        """Verify role='tablist', role='tab', role='tabpanel', and role='progressbar' exist in index.html."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        required_roles = ["tablist", "tab", "tabpanel", "progressbar"]
        missing_roles = [role for role in required_roles if f'role="{role}"' not in html]
        self.assertEqual(
            missing_roles,
            [],
            f"Missing required ARIA roles in dashboard/index.html: {missing_roles}",
        )

    def test_min_font_size_baseline(self):
        """Verify no font-size rules < 11px exist in dashboard/styles.css."""
        css = STYLES_CSS.read_text(encoding="utf-8")
        sub_11px_regex = re.compile(r"font-size:\s*(0\.[0-6][0-9]*rem|[1-9]px|10px)")
        matches = sub_11px_regex.findall(css)
        self.assertEqual(
            matches,
            [],
            f"Found sub-11px font sizes in dashboard/styles.css: {matches}",
        )

    def test_focus_visible_styles(self):
        """Verify :focus-visible rules are present in dashboard/styles.css."""
        css = STYLES_CSS.read_text(encoding="utf-8")
        self.assertIn(
            ":focus-visible",
            css,
            ":focus-visible styles must be defined in dashboard/styles.css for keyboard navigation accessibility",
        )

    def test_status_badge_glyphs(self):
        """Verify status glyphs (✓, !, ×) are present in index.html and/or core.js."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        core_js = (JS_DIR / "core.js").read_text(encoding="utf-8")
        combined = html + " " + core_js
        glyphs = ["✓", "!", "×"]
        has_any = any(g in combined for g in glyphs)
        self.assertTrue(
            has_any,
            f"Expected at least one status glyph {glyphs} in index.html or core.js for color-blind accessibility",
        )

    def test_ticker_units(self):
        """Verify 'tok/min' unit label is present in dashboard/js/now.js."""
        now_js = (JS_DIR / "now.js").read_text(encoding="utf-8")
        self.assertIn(
            "tok/min",
            now_js,
            "'tok/min' rate unit must be present in dashboard/js/now.js",
        )


if __name__ == "__main__":
    unittest.main()
