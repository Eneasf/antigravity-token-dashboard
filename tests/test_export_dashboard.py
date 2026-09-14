"""Unit tests for scripts/export_dashboard.py."""

import json
from pathlib import Path
import tempfile
import unittest

from scripts.export_dashboard import export_telemetry


class TestExportDashboard(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.dashboard_dir = self.temp_path / "dashboard"
        self.dashboard_dir.mkdir(parents=True)
        self.index_html = self.dashboard_dir / "index.html"

        sample_html = (
            '<!DOCTYPE html>\n'
            '<html lang="en">\n'
            '<head><title>Test</title></head>\n'
            '<body>\n'
            '<script id="injected-dashboard-data" type="application/json">{}</script>\n'
            '<script>\n'
            'let activeTheme = "dark";\n'
            '</script>\n'
            '</body>\n'
            '</html>'
        )
        self.index_html.write_text(sample_html, encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_writes_decoupled_data_js(self):
        empty_antigravity = self.temp_path / "antigravity"
        empty_antigravity.mkdir()

        payload = export_telemetry(
            antigravity_dir=empty_antigravity,
            dashboard_path=self.index_html,
        )

        self.assertIn("summary", payload)
        self.assertTrue(self.index_html.exists())

        # Verify decoupled data.js and data.json
        data_js = self.dashboard_dir / "data.js"
        data_json = self.dashboard_dir / "data.json"
        self.assertTrue(data_js.exists())
        self.assertTrue(data_json.exists())

        js_content = data_js.read_text(encoding="utf-8")
        self.assertTrue(js_content.startswith("window.__TELEMETRY_DATA__ = "))
        self.assertIn('"summary": {', js_content)
        self.assertIn('"subscription_status": "SAFE_IN_QUOTA"', js_content)

        # Verify decoupled meta.js and meta.json (Decision 5 fast hash-gating)
        meta_js = self.dashboard_dir / "meta.js"
        meta_json = self.dashboard_dir / "meta.json"
        self.assertTrue(meta_js.exists())
        self.assertTrue(meta_json.exists())

        meta_js_content = meta_js.read_text(encoding="utf-8")
        self.assertTrue(meta_js_content.startswith("window.__TELEMETRY_META__ = "))
        meta_dict = json.loads(meta_json.read_text(encoding="utf-8"))
        self.assertIn("payload_sha1", meta_dict)
        self.assertEqual(len(meta_dict["payload_sha1"]), 40)
        self.assertIn("payload_bytes", meta_dict)
        self.assertIn("conversations_count", meta_dict)

        # Verify index.html references meta.js and data.js
        index_content = self.index_html.read_text(encoding="utf-8")
        self.assertIn('<script src="meta.js"></script>', index_content)
        self.assertIn('<script src="data.js"></script>', index_content)
        self.assertLess(index_content.find('<script src="meta.js"></script>'), index_content.find('<script src="data.js"></script>'))

    def test_export_embed_mode(self):
        empty_antigravity = self.temp_path / "antigravity"
        empty_antigravity.mkdir()

        payload = export_telemetry(
            antigravity_dir=empty_antigravity,
            dashboard_path=self.index_html,
            embed=True,
        )

        self.assertIn("summary", payload)
        index_content = self.index_html.read_text(encoding="utf-8")
        self.assertIn('<script id="injected-dashboard-data" type="application/json">', index_content)
        self.assertIn('"summary": {', index_content)
        self.assertIn('"subscription_status": "SAFE_IN_QUOTA"', index_content)

    def test_export_missing_hook_raises(self):
        empty_antigravity = self.temp_path / "antigravity"
        empty_antigravity.mkdir()
        bad_html = self.dashboard_dir / "bad.html"
        bad_html.write_text("<html><body>No hook here</body></html>", encoding="utf-8")

        with self.assertRaises(SystemExit):
            export_telemetry(
                antigravity_dir=empty_antigravity,
                dashboard_path=bad_html,
            )


if __name__ == "__main__":
    unittest.main()
