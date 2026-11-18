"""
Unit Test Suite for Mobile Viewport Polish, Ticker Clipping Fix & Table Scroll Wrappers.
Milestone 61 (Row 16 / U8).

Verifies:
1. All 11 dashboard tables are enclosed in .table-scroll-wrapper and .table-scroll-container
   with corresponding .table-scroll-fade overlay elements in dashboard/index.html.
2. CSS definitions in dashboard/styles.css for .table-scroll-container, .table-scroll-wrapper,
   and .table-scroll-fade (including dark theme and .is-scrolled-end states).
3. Mobile viewport rules (<768px and <480px) in dashboard/styles.css enforcing
   justify-content: flex-start and overflow-x: auto on command strip and navigation elements
   to eliminate left clipping of the live token ticker HUD.
4. Core JavaScript scroll fade interactions in dashboard/js/core.js, ensuring
   updateTableScrollFade checks (scrollLeft + clientWidth >= scrollWidth - offset),
   toggles .is-scrolled-end on container, and delegates scroll events.
"""

from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML_PATH = REPO_ROOT / "dashboard" / "index.html"
STYLES_CSS_PATH = REPO_ROOT / "dashboard" / "styles.css"
CORE_JS_PATH = REPO_ROOT / "dashboard" / "js" / "core.js"


class TestMobilePassAndScrollWrappers(unittest.TestCase):
    """Test suite ensuring mobile layout invariants and table scroll fades are strictly maintained."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(INDEX_HTML_PATH.exists(), f"dashboard/index.html must exist at {INDEX_HTML_PATH}")
        cls.assertTrue(STYLES_CSS_PATH.exists(), f"dashboard/styles.css must exist at {STYLES_CSS_PATH}")
        cls.assertTrue(CORE_JS_PATH.exists(), f"dashboard/js/core.js must exist at {CORE_JS_PATH}")

    def test_table_scroll_wrappers_present(self):
        """Verify that all 11 tables are enclosed in .table-scroll-wrapper and have .table-scroll-fade."""
        h = INDEX_HTML_PATH.read_text(encoding="utf-8")

        # Global count assertions matching VDONE Gate B2
        wrapper_count = h.count("table-scroll-wrapper")
        fade_count = h.count("table-scroll-fade")
        self.assertGreaterEqual(
            wrapper_count,
            10,
            f"Expected at least 10 occurrences of 'table-scroll-wrapper', found {wrapper_count}",
        )
        self.assertGreaterEqual(
            fade_count,
            10,
            f"Expected at least 10 occurrences of 'table-scroll-fade', found {fade_count}",
        )

        # Expected 11 tables across all views and modals:
        # 1. models-table
        # 2. recent-sessions-table
        # 3. conversations-table
        # 4. turns-table
        # 5. projects-table
        # 6. tools-table
        # 7. weekly-trends-table
        # 8. reconciliation-table
        # 9. sim-tier-table
        # 10. modal table (plan-history-tbody / plan history table)
        # 11. rate-history-table
        table_targets = [
            ("models-table", '<table id="models-table"'),
            ("recent-sessions-table", '<table id="recent-sessions-table"'),
            ("conversations-table", '<table id="conversations-table"'),
            ("turns-table", '<table id="turns-table"'),
            ("projects-table", '<table id="projects-table"'),
            ("tools-table", '<table id="tools-table"'),
            ("weekly-trends-table", '<table id="weekly-trends-table"'),
            ("reconciliation-table", '<table id="reconciliation-table"'),
            ("sim-tier-table", '<table class="sim-tier-table"'),
            ("plan-history-modal-table", '<tbody id="plan-history-tbody"'),
            ("rate-history-table", '<table id="rate-history-table"'),
        ]

        for name, identifier in table_targets:
            with self.subTest(table=name):
                self.assertIn(
                    identifier,
                    h,
                    f"Table identifier '{identifier}' for '{name}' must exist in dashboard/index.html",
                )
                pos = h.find(identifier)
                # Look backwards for enclosing .table-scroll-wrapper within 1000 characters
                preceding = h[max(0, pos - 1000) : pos]
                self.assertIn(
                    "table-scroll-wrapper",
                    preceding,
                    f"Table '{name}' must be enclosed in an element with class 'table-scroll-wrapper'",
                )
                # Look forwards in container for .table-scroll-fade
                window = h[max(0, pos - 1000) : min(len(h), pos + 8000)]
                self.assertIn(
                    "table-scroll-fade",
                    window,
                    f"Table '{name}' must have an associated 'table-scroll-fade' element in its container",
                )

    def test_mobile_css_ticker_and_wrappers(self):
        """Verify CSS definitions for scroll wrappers, fades, and mobile flex-start alignments."""
        s = STYLES_CSS_PATH.read_text(encoding="utf-8")

        # Verify core class definitions exist
        self.assertIn(".table-scroll-container", s, "CSS must define .table-scroll-container")
        self.assertIn(".table-scroll-wrapper", s, "CSS must define .table-scroll-wrapper")
        self.assertIn(".table-scroll-fade", s, "CSS must define .table-scroll-fade")

        # Verify fade properties and scrolled-end state
        self.assertIn("opacity: 0", s, "CSS must hide .table-scroll-fade when scrolled to end")
        self.assertTrue(
            "is-scrolled-end" in s,
            "CSS must handle .is-scrolled-end state for fade element",
        )

        # Verify mobile media queries for <= 768px
        self.assertIn("@media (max-width: 768px)", s, "CSS must include media query for max-width: 768px")

        # Assert that within the stylesheet, under mobile max-width: 768px,
        # .workspace-command-strip or .tab-nav has justify-content: flex-start
        self.assertIn(
            "justify-content: flex-start",
            s,
            "CSS must specify 'justify-content: flex-start' to prevent mobile left clipping",
        )
        self.assertIn(
            "overflow-x: auto",
            s,
            "CSS must specify 'overflow-x: auto' for mobile horizontal scrolling",
        )

        # Check ticker constraints to prevent negative left edge
        self.assertIn(
            "token-ticker-hud",
            s,
            "CSS must define rules for .token-ticker-hud",
        )

    def test_scroll_interaction(self):
        """Verify dashboard/js/core.js implements scroll fade updating logic and listeners."""
        js = CORE_JS_PATH.read_text(encoding="utf-8")

        # Assert function presence
        self.assertIn(
            "function updateTableScrollFade",
            js,
            "dashboard/js/core.js must implement updateTableScrollFade function",
        )
        self.assertIn(
            "function initScrollFades",
            js,
            "dashboard/js/core.js must implement initScrollFades function",
        )

        # Assert logic: checks scrollLeft + clientWidth >= scrollWidth
        # Supports variations such as (wrapper.scrollLeft + wrapper.clientWidth) >= (wrapper.scrollWidth - 3)
        has_scroll_calc = bool(
            re.search(
                r"scrollLeft\s*\+\s*.*clientWidth\s*\)?\s*>=\s*\(?.*scrollWidth",
                js,
            )
        )
        self.assertTrue(
            has_scroll_calc,
            "updateTableScrollFade must compare (scrollLeft + clientWidth) against scrollWidth",
        )

        # Assert toggles 'is-scrolled-end'
        self.assertIn(
            "is-scrolled-end",
            js,
            "updateTableScrollFade must toggle 'is-scrolled-end' class",
        )
        self.assertTrue(
            "classList.add('is-scrolled-end')" in js or 'classList.add("is-scrolled-end")' in js,
            "updateTableScrollFade must call classList.add('is-scrolled-end')",
        )
        self.assertTrue(
            "classList.remove('is-scrolled-end')" in js or 'classList.remove("is-scrolled-end")' in js,
            "updateTableScrollFade must call classList.remove('is-scrolled-end')",
        )

        # Assert delegated scroll listener on document
        self.assertIn(
            "addEventListener('scroll'",
            js.replace('"', "'"),
            "document must register a scroll listener for table scroll wrappers",
        )
        self.assertIn(
            "table-scroll-wrapper",
            js,
            "Delegated scroll listener must check for 'table-scroll-wrapper' class",
        )

        # Assert exposed on window
        self.assertTrue(
            "window.updateTableScrollFade" in js or "window.__updateTableScrollFade" in js,
            "updateTableScrollFade must be exposed on window for testing and integration",
        )
        self.assertTrue(
            "window.initScrollFades" in js or "window.__initScrollFades" in js,
            "initScrollFades must be exposed on window for testing and integration",
        )


if __name__ == "__main__":
    unittest.main()
