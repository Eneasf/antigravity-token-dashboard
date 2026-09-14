"""
Test Suite: Model Roster Integrity & Reasoning Taxonomy (Gate V136)

Enforces the canonical 19-model census defined in `antigravity_telemetry/models.json`
as the Single Source of Truth across:
- `config/pricing.json` and `config/pricing.sample.json`
- `dashboard/app.js` and `dashboard/index.html`
- `src/simulator.py`
- Prevents drift or hallucination of forbidden/legacy model strings.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestModelRosterIntegrity(unittest.TestCase):
    """Verifies that all model taxonomy references adhere strictly to the canonical roster."""

    def setUp(self):
        self.models_json_path = REPO_ROOT / "antigravity_telemetry" / "models.json"
        self.pricing_json_path = REPO_ROOT / "config" / "pricing.json"
        self.pricing_sample_path = REPO_ROOT / "config" / "pricing.sample.json"
        self.app_js_path = REPO_ROOT / "dashboard" / "app.js"
        self.index_html_path = REPO_ROOT / "dashboard" / "index.html"
        self.simulator_py_path = REPO_ROOT / "src" / "simulator.py"

        with open(self.models_json_path, "r", encoding="utf-8") as f:
            self.canonical_models = json.load(f)

    def test_canonical_models_census_count_and_keys(self):
        """Verify models.json defines exactly the 19 calibrated internal Antigravity models."""
        self.assertEqual(len(self.canonical_models), 19)
        required_keys = {"1318", "1319", "1320", "1298", "1299", "1300",
                         "1071", "1072", "1073", "1016", "1036", "1050",
                         "1322", "1132", "1301", "1035", "1026", "1020", "342"}
        self.assertEqual(set(self.canonical_models.keys()), required_keys)

    def test_authoritative_ground_truth_models(self):
        """Verify exact canonical naming and reasoning effort for critical models."""
        # 1035: Claude Sonnet 4.6 (Thinking)
        m1035 = self.canonical_models.get("1035")
        self.assertIsNotNone(m1035)
        self.assertEqual(m1035["name"], "Claude Sonnet 4.6 (Thinking)")
        self.assertEqual(m1035["family"], "claude-sonnet")
        self.assertEqual(m1035["provider"], "anthropic")
        self.assertEqual(m1035["reasoning_effort"], "thinking")

        # 1026: Claude Opus 4.6 (Thinking)
        m1026 = self.canonical_models.get("1026")
        self.assertIsNotNone(m1026)
        self.assertEqual(m1026["name"], "Claude Opus 4.6 (Thinking)")
        self.assertEqual(m1026["family"], "claude-opus")
        self.assertEqual(m1026["provider"], "anthropic")
        self.assertEqual(m1026["reasoning_effort"], "thinking")

        # 342: GPT-OSS 120B (Medium)
        m342 = self.canonical_models.get("342")
        self.assertIsNotNone(m342)
        self.assertEqual(m342["name"], "GPT-OSS 120B (Medium)")
        self.assertEqual(m342["family"], "gpt-oss")
        self.assertEqual(m342["provider"], "openai")
        self.assertEqual(m342["reasoning_effort"], "medium")

    def test_pricing_json_alignment(self):
        """Verify config/pricing.json aligns 100% with the canonical model roster."""
        with open(self.pricing_json_path, "r", encoding="utf-8") as f:
            pricing = json.load(f)

        pricing_models = pricing.get("models", {})
        for model_id, canonical_info in self.canonical_models.items():
            self.assertIn(model_id, pricing_models, f"Model {model_id} missing in pricing.json")
            self.assertEqual(
                pricing_models[model_id]["name"],
                canonical_info["name"],
                f"Model name mismatch for {model_id} in pricing.json"
            )
            self.assertEqual(
                pricing_models[model_id]["family"],
                canonical_info["family"],
                f"Model family mismatch for {model_id} in pricing.json"
            )

    def test_pricing_sample_json_alignment(self):
        """Verify config/pricing.sample.json aligns with canonical names for critical models."""
        with open(self.pricing_sample_path, "r", encoding="utf-8") as f:
            sample = json.load(f)

        sample_models = sample.get("models", {})
        for model_id in ("1035", "1026", "342"):
            self.assertIn(model_id, sample_models)
            self.assertEqual(
                sample_models[model_id]["name"],
                self.canonical_models[model_id]["name"]
            )

    def test_dashboard_frontend_alignment(self):
        """Verify dashboard/app.js and dashboard/index.html contain canonical model entries."""
        app_js = self.app_js_path.read_text(encoding="utf-8")
        index_html = self.index_html_path.read_text(encoding="utf-8")

        # Check app.js MODEL_TAXONOMY
        self.assertIn('"1035": { name: "Claude Sonnet 4.6", reasoning: "Thinking Enabled"', app_js)
        self.assertIn('"1026": { name: "Claude Opus 4.6", reasoning: "Thinking Enabled"', app_js)
        self.assertIn('"342": { name: "GPT-OSS 120B", reasoning: "Medium Reasoning"', app_js)

        # Check app.js Simulator archetypes and rates
        self.assertIn("Claude Opus 4.6 Stress Test", app_js)
        self.assertIn('"1035": { name: "Claude Sonnet 4.6 Thinking"', app_js)
        self.assertIn('"1026": { name: "Claude Opus 4.6 Thinking"', app_js)
        self.assertIn('"342": { name: "GPT-OSS 120B (Medium)"', app_js)

        # Check index.html dropdown options, fallback callout, and simulator presets
        self.assertIn("Claude Opus 4.6 (Thinking) - [1026]", index_html)
        self.assertIn("Claude Sonnet 4.6 (Thinking) - [1035]", index_html)
        self.assertIn("GPT-OSS 120B (Medium) - [342]", index_html)
        self.assertIn("Claude Opus 4.6 Stress Test", index_html)
        self.assertIn("Claude Sonnet 4.6 or GPT-OSS 120B", index_html)

    def test_simulator_archetype_alignment(self):
        """Verify src/simulator.py archetype naming matches canonical roster."""
        sim_py = self.simulator_py_path.read_text(encoding="utf-8")
        self.assertIn("Claude Opus 4.6 Stress Test", sim_py)

    def test_zero_forbidden_legacy_strings_in_active_code(self):
        """Verify that forbidden drifted model strings do not exist in active config and UI files."""
        forbidden_patterns = [
            r"\bClaude 3\.7 Sonnet\b",
            r"\bClaude 3\.5 Sonnet\b",
            r"\bClaude 3\.1 Opus\b",
            r"\bClaude 3 Opus\b",
            r"\"name\": \"Claude Sonnet \(Thinking\)\"",
            r"\"name\": \"Claude Opus \(Thinking\)\"",
            r"\"name\": \"GPT OSS \(Medium\)\"",
        ]

        files_to_check = [
            self.models_json_path,
            self.pricing_json_path,
            self.pricing_sample_path,
            self.app_js_path,
            self.index_html_path,
            self.simulator_py_path,
        ]

        for file_path in files_to_check:
            content = file_path.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                match = re.search(pattern, content)
                self.assertIsNone(
                    match,
                    f"Forbidden legacy model string matching pattern '{pattern}' found in {file_path.name}: '{match.group(0) if match else ''}'"
                )


if __name__ == "__main__":
    unittest.main()
