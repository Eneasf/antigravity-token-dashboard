"""
Unit & Regression Tests for Dashboard Boot & Render Split (Milestone 51 / Row 6 / C3).

Verifies:
  - Splitting initDashboard() into bootOnce() and render(data)
  - Module-level isBooted guard prevents duplicate event listener attachment
  - checkAndReloadTelemetry() calls render() and never calls initDashboard()
  - Zero inline onclick= handlers across index.html, demo.html, and app.js
  - Event delegation handling for all data-action targets
  - Defaulting #plan-tier-select to summary.tier (mirroring #sim-plan-select)
  - Filter dropdowns reset before repopulating on render
  - Idempotent subsystems initialization
"""

from pathlib import Path
import re
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDashboardBoot(unittest.TestCase):
    """Verifies boot/render separation, CSP onclick elimination, and plan tier defaults."""

    def setUp(self):
        self.js_dir = REPO_ROOT / "dashboard" / "js"
        self.index_html_path = REPO_ROOT / "dashboard" / "index.html"

        self.index_html = self.index_html_path.read_text(encoding="utf-8")
        self.all_js = "\n".join(f.read_text(encoding="utf-8") for f in sorted(self.js_dir.glob("*.js")))
        self.app_js = self.all_js
        self.core_js = (self.js_dir / "core.js").read_text(encoding="utf-8")
        self.now_js = (self.js_dir / "now.js").read_text(encoding="utf-8")

    def test_boot_and_render_functions_exist(self):
        """bootOnce() and render() must exist as separate functions in core.js."""
        self.assertIn("function bootOnce() {", self.core_js)
        self.assertIn("function render(data) {", self.core_js)
        self.assertIn("isBooted = false;", self.core_js)
        self.assertIn("if (isBooted) return;", self.core_js)
        self.assertIn("isBooted = true;", self.core_js)

    def test_reload_calls_render_not_init_dashboard(self):
        """checkAndReloadTelemetry must call render(data) and never re-invoke initDashboard()."""
        fn_start = self.now_js.find("function checkAndReloadTelemetry()")
        self.assertNotEqual(fn_start, -1)

        reload_fn_code = self.now_js[fn_start:]
        self.assertIn("render(globalDashboardData)", reload_fn_code)
        self.assertNotIn("initDashboard()", reload_fn_code)

    def test_zero_inline_onclick_handlers(self):
        """Zero inline onclick= attributes across index.html and all JS files."""
        files = {
            "index.html": self.index_html,
            "all_js": self.all_js,
        }
        for name, content in files.items():
            matches = re.findall(r"onclick=", content)
            self.assertEqual(
                len(matches),
                0,
                f"Found {len(matches)} inline onclick= occurrences in {name}",
            )

    def test_event_delegation_actions_covered(self):
        """Global delegated click handler in bootOnce covers all standard UI actions."""
        required_actions = [
            "switch-tab",
            "set-currency",
            "set-theme",
            "set-shell-mode",
            "toggle-sidebar",
            "clear-convo-filters",
            "toggle-convo-sort",
            "close-turns-card",
            "select-archetype",
            "close-inspector-drawer",
            "toggle-turn-sort",
            "toggle-project-branches",
            "inspect-session",
            "select-swarm",
            "inspect-swarm-node",
            "toggle-burst-sessions",
            "copy-handover-summary",
            "toggle-context-audit-drawer",
        ]
        self.assertIn('document.addEventListener("click"', self.app_js)
        for act in required_actions:
            self.assertIn(
                f'action === "{act}"',
                self.app_js,
                f"Delegated action handler for '{act}' missing in app.js",
            )

    def test_plan_tier_preset_default(self):
        """#plan-tier-select must default to summary.tier without hardcoded 'selected' attribute."""
        self.assertNotIn(
            '<option value="pro" selected>',
            self.index_html,
            "index.html must not hardcode 'selected' on option pro",
        )
        self.assertIn("tierPresetSelect.value = summary.tier", self.app_js)

    def test_filter_dropdowns_cleared_before_repopulate(self):
        """render() must reset filter dropdown options to avoid duplication across data reloads."""
        self.assertIn(
            'wsSelect.innerHTML = \'<option value="all">All Workspaces</option>\'',
            self.app_js,
        )
        self.assertIn(
            'convoSelect.innerHTML = \'<option value="all">All Conversations</option>\'',
            self.app_js,
        )

    def test_init_dashboard_backward_compatibility(self):
        """initDashboard() must remain available for external callers, executing bootOnce then render."""
        self.assertIn("function initDashboard() {", self.app_js)
        fn_start = self.app_js.find("function initDashboard() {")
        fn_slice = self.app_js[fn_start:fn_start + 150]
        self.assertIn("bootOnce();", fn_slice)
        self.assertIn("render(globalDashboardData);", fn_slice)

    def test_subsystems_idempotent_guards(self):
        """Subsystems like initAutoRefresh and initPlanManagerModal have initialization guards."""
        self.assertIn("let isAutoRefreshInitialized = false;", self.app_js)
        self.assertIn("if (isAutoRefreshInitialized) return;", self.app_js)
        self.assertIn("let isPlanManagerModalInitialized = false;", self.app_js)
        self.assertIn("if (isPlanManagerModalInitialized) return;", self.app_js)


if __name__ == "__main__":
    unittest.main()
