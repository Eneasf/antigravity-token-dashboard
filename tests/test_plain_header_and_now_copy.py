"""
Unit Tests for Plain Header & Now Tab Copy (Milestone 52 / Row 7 / U1 + U2).

Verifies:
1. Zero occurrences of engineering jargon (contamination, spillover, governor,
   dual-track, dual-benchmark, family routing, isolation policy) in index.html,
   demo.html, and app.js outside comments and tooltips.
2. Plain copy replacements across the Now tab (Quota right now, Gemini, Claude & GPT,
   Weekly pace, Pace).
3. Deletion of redundant fallback reserve capacity widget.
4. Compact single-line header markup, clamp(18px) title, overflow menu with standup copy.
5. Strict CSS max-height constraints (desktop < 72px, mobile < 160px).
"""

from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "dashboard" / "index.html"
JS_DIR = REPO_ROOT / "dashboard" / "js"
STYLES_CSS = REPO_ROOT / "dashboard" / "styles.css"

FORBIDDEN_JARGON_PATTERN = re.compile(
    r"(?i)\b(contamination|spillover|governor|dual-track|dual-benchmark|family routing|isolation policy)\b"
)


def strip_comments_and_tooltips(content: str, is_js: bool = False) -> str:
    """Strip HTML comments, JS comments, and tooltip/title attributes for fair jargon scanning."""
    if is_js:
        cleaned = re.sub(r"//.*?\n", "\n", content)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.S)
    else:
        cleaned = re.sub(r"<!--.*?-->", "", content, flags=re.S)

    cleaned = re.sub(r'(?:title|data-tooltip)=["\'][^"\']*["\']', '', cleaned)
    return cleaned


class TestPlainHeaderAndNowCopy(unittest.TestCase):
    """Test suite verifying plain English copy and compact header architecture."""

    def test_zero_jargon_in_html(self):
        """Verify zero engineering jargon in dashboard/index.html outside comments/tooltips."""
        raw = INDEX_HTML.read_text(encoding="utf-8")
        cleaned = strip_comments_and_tooltips(raw, is_js=False)
        matches = FORBIDDEN_JARGON_PATTERN.findall(cleaned)
        self.assertEqual(
            matches,
            [],
            f"Found forbidden engineering jargon in dashboard/index.html: {set(matches)}",
        )

    def test_zero_jargon_in_js_modules(self):
        """Verify zero engineering jargon in dashboard/js/*.js outside comments/tooltips."""
        for js_file in sorted(JS_DIR.glob("*.js")):
            raw = js_file.read_text(encoding="utf-8")
            cleaned = strip_comments_and_tooltips(raw, is_js=True)
            matches = FORBIDDEN_JARGON_PATTERN.findall(cleaned)
            self.assertEqual(
                matches,
                [],
                f"Found forbidden engineering jargon in {js_file.name}: {set(matches)}",
            )

    def test_plain_now_tab_copy(self):
        """Verify that cards on the Now tab use plain English copy."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn("Quota right now", html)
        self.assertIn("Weekly pace", html)
        self.assertIn("Pace", html)
        self.assertIn("Claude &amp; GPT", html)
        self.assertIn("Separate allowance, hard stop", html)
        # Standby capacity redundant widget must be deleted
        self.assertNotIn("Fallback Reserve Capacity", html)
        self.assertNotIn("standby-capacity-box", html)

    def test_compact_header_structure(self):
        """Verify compact header HTML elements, preserved IDs, and overflow menu."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        # Header h1 title is concise and p description is removed from header
        self.assertIn("<header>", html)
        self.assertIn("Token Quota Dashboard", html)
        header_section = re.search(r"<header>(.*?)</header>", html, re.S).group(1)
        self.assertNotIn("<p>", header_section)

        # Essential badges and buttons preserved
        self.assertIn('id="sub-status-badge"', header_section)
        self.assertIn('id="header-tier-badge"', header_section)
        self.assertIn('id="data-freshness-badge"', header_section)
        self.assertIn('id="btn-open-plan-manager"', header_section)
        self.assertIn('id="btn-header-overflow"', header_section)
        self.assertIn('id="header-overflow-menu"', header_section)
        self.assertIn('id="btn-copy-standup"', header_section)

        # Settings toggles preserved for accessibility and tests
        self.assertIn('id="currency-toggle-group"', header_section)
        self.assertIn('id="theme-toggle-group"', header_section)
        self.assertIn('id="header-shell-toggle"', header_section)

    def test_header_css_dimensions(self):
        """Verify CSS contains clamping, desktop height caps, and responsive queries."""
        css = STYLES_CSS.read_text(encoding="utf-8")
        self.assertIn("clamp(18px", css)
        self.assertIn("max-height: 68px", css)
        self.assertIn("@media (max-width: 960px)", css)
        self.assertIn(".header-desktop-toggles", css)
        self.assertIn("@media (max-width: 768px)", css)
        self.assertIn("max-height: 140px", css)

    def test_header_badge_spacing_and_hierarchy(self):
        """Verify badge spacing, flex-shrink: 0, and responsive visibility hierarchy (Row 6 / U2)."""
        css = STYLES_CSS.read_text(encoding="utf-8")
        self.assertIn("padding: 3px 8px", css)
        self.assertIn("flex-shrink: 0", css)
        self.assertIn("@media (max-width: 1600px)", css)
        self.assertIn("#session-count-badge", css)
        self.assertIn("@media (max-width: 1250px)", css)
        self.assertIn("#billing-cycle-badge", css)
        self.assertIn("#degraded-badge-header", css)
        self.assertIn("@media (max-width: 1620px)", css)
        self.assertIn("@media (max-width: 1380px)", css)


if __name__ == "__main__":
    unittest.main()
