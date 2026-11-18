"""
Test Suite: Model Roster Integrity & Reasoning Taxonomy (Gate V136)

Enforces the canonical model census (schema v2) defined in `antigravity_telemetry/models.json`
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

from antigravity_telemetry import load_model_catalog, load_model_census
from scripts.export_dashboard import build_export_catalog
from src.simulator import get_archetype_presets

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestModelRosterIntegrity(unittest.TestCase):
    """Verifies that all model taxonomy references adhere strictly to the canonical roster."""

    def setUp(self):
        self.models_json_path = REPO_ROOT / "antigravity_telemetry" / "models.json"
        self.pricing_json_path = REPO_ROOT / "config" / "pricing.json"
        self.pricing_sample_path = REPO_ROOT / "config" / "pricing.sample.json"
        self.js_dir = REPO_ROOT / "dashboard" / "js"
        self.index_html_path = REPO_ROOT / "dashboard" / "index.html"
        self.simulator_py_path = REPO_ROOT / "src" / "simulator.py"

        self.canonical_models = load_model_census()
        self.model_catalog = load_model_catalog()

    def test_canonical_models_census_count_and_keys(self):
        """Verify models.json defines the >=40 calibrated internal Antigravity models and schema_version=2."""
        self.assertEqual(self.model_catalog.get("schema_version"), 2)
        self.assertGreaterEqual(len(self.canonical_models), 40)
        required_keys = {"1427", "1437", "1438", "1667", "1681", "1669", "1417", "1418", "1419",
                         "1528", "1525", "1526", "1527",
                         "1317", "1318", "1319", "1320", "1298", "1299", "1300",
                         "1071", "1072", "1073", "1016", "1036", "1050",
                         "1198", "1322", "1132", "1301", "1035", "1026", "1020", "342",
                         "1400", "1401", "1402", "1403", "1404", "1405"}
        self.assertTrue(required_keys.issubset(set(self.canonical_models.keys())))

    def test_authoritative_ground_truth_models(self):
        """Verify exact canonical naming and reasoning effort for critical models."""
        # 1427, 1437, 1438: Gemini 4 Carbon (High, Medium, Low)
        carbon_levels = [("1427", "high"), ("1437", "medium"), ("1438", "low")]
        for mid, effort in carbon_levels:
            m = self.canonical_models.get(mid)
            self.assertIsNotNone(m, f"Model {mid} missing in canonical models")
            self.assertEqual(m["family"], "gemini-carbon")
            self.assertEqual(m["provider"], "google")
            self.assertEqual(m["reasoning_effort"], effort)
            self.assertEqual(m["status"], "active")
            self.assertEqual(m["available_from"], "2026-11-10")
            self.assertEqual(m["name"], f"Gemini 4 Carbon ({effort.capitalize()})")

        # 1417, 1418, 1419: Gemini 4 Argon (High, Medium, Low)
        argon_levels = [("1417", "high"), ("1418", "medium"), ("1419", "low")]
        for mid, effort in argon_levels:
            m = self.canonical_models.get(mid)
            self.assertIsNotNone(m, f"Model {mid} missing in canonical models")
            self.assertEqual(m["family"], "gemini-argon")
            self.assertEqual(m["provider"], "google")
            self.assertEqual(m["reasoning_effort"], effort)
            self.assertEqual(m["status"], "active")
            self.assertEqual(m["available_from"], "2026-10-13")
            self.assertEqual(m["name"], f"Gemini 4 Argon ({effort.capitalize()})")

        # 1667, 1681, 1669: Orchestrator (Carbon, Argon, Hydrogen Executor)
        for mid, expected_name in [
            ("1667", "Orchestrator (Carbon)"),
            ("1681", "Orchestrator (Argon)"),
            ("1669", "Orchestrator Executor (Hydrogen)"),
        ]:
            m = self.canonical_models.get(mid)
            self.assertIsNotNone(m, f"Model {mid} missing in canonical models")
            self.assertEqual(m["family"], "gemini-orchestrator")
            self.assertEqual(m["provider"], "google")
            self.assertFalse(m["is_subagent"])
            self.assertEqual(m["status"], "active")
            self.assertEqual(m["available_from"], "2026-11-12")
            self.assertEqual(m["name"], expected_name)
        self.assertEqual(self.canonical_models["1669"]["swarm_tier"], "engineering")

        # 1528, 1525, 1526, 1527: Gemini 4 Hydrogen (XHigh, High, Medium, Low)
        hydrogen_levels = [
            ("1528", "xhigh", "Gemini 4 Hydrogen (XHigh)"),
            ("1525", "high", "Gemini 4 Hydrogen (High)"),
            ("1526", "medium", "Gemini 4 Hydrogen (Medium)"),
            ("1527", "low", "Gemini 4 Hydrogen (Low)"),
        ]
        for mid, effort, expected_name in hydrogen_levels:
            m = self.canonical_models.get(mid)
            self.assertIsNotNone(m, f"Model {mid} missing in canonical models")
            self.assertEqual(m["family"], "gemini-hydrogen")
            self.assertEqual(m["provider"], "google")
            self.assertEqual(m["reasoning_effort"], effort)
            self.assertEqual(m["status"], "active")
            self.assertEqual(m["available_from"], "2026-11-12")
            self.assertEqual(m["name"], expected_name)

        # 1016, 1036: Gemini 3.1 Pro (High, Low - Deprecated from 2026-10-13)
        for mid, effort in [("1016", "high"), ("1036", "low")]:
            m = self.canonical_models.get(mid)
            self.assertIsNotNone(m)
            self.assertEqual(m["family"], "gemini-pro")
            self.assertEqual(m["provider"], "google")
            self.assertEqual(m["reasoning_effort"], effort)
            self.assertEqual(m["status"], "deprecated")
            self.assertEqual(m["sunset_date"], "2026-10-13")

        # 1198: Gemini Flash Lite Gen 2 (Adaptive Thinking)
        m1198 = self.canonical_models.get("1198")
        self.assertIsNotNone(m1198)
        self.assertEqual(m1198["name"], "Gemini Flash Lite Gen 2 (Adaptive Thinking)")
        self.assertEqual(m1198["family"], "gemini-flash-lite")
        self.assertEqual(m1198["provider"], "google")
        self.assertEqual(m1198["reasoning_effort"], "adaptive")
        self.assertEqual(m1198["subagent_tier"], "flash_lite")
        self.assertEqual(m1198["generation"], 2)

        # 1035: Claude Sonnet 4.6 (Thinking - Deprecated from 2026-10-03)
        m1035 = self.canonical_models.get("1035")
        self.assertIsNotNone(m1035)
        self.assertEqual(m1035["name"], "Claude Sonnet 4.6 (Thinking)")
        self.assertEqual(m1035["family"], "claude-sonnet")
        self.assertEqual(m1035["provider"], "anthropic")
        self.assertEqual(m1035["reasoning_effort"], "thinking")
        self.assertEqual(m1035["status"], "deprecated")
        self.assertEqual(m1035["sunset_date"], "2026-10-03")

        # 1026: Claude Opus 4.6 (Thinking - Deprecated from 2026-10-03)
        m1026 = self.canonical_models.get("1026")
        self.assertIsNotNone(m1026)
        self.assertEqual(m1026["name"], "Claude Opus 4.6 (Thinking)")
        self.assertEqual(m1026["family"], "claude-opus")
        self.assertEqual(m1026["provider"], "anthropic")
        self.assertEqual(m1026["reasoning_effort"], "thinking")
        self.assertEqual(m1026["status"], "deprecated")
        self.assertEqual(m1026["sunset_date"], "2026-10-03")

        # 1400, 1401, 1402: Claude Opus 5.5 (Low, Medium, High)
        opus_55_levels = [("1400", "low"), ("1401", "medium"), ("1402", "high")]
        for mid, effort in opus_55_levels:
            m = self.canonical_models.get(mid)
            self.assertIsNotNone(m, f"Model {mid} missing in canonical models")
            self.assertEqual(m["family"], "claude-opus")
            self.assertEqual(m["provider"], "anthropic")
            self.assertEqual(m["reasoning_effort"], effort)
            self.assertEqual(m["status"], "active")
            self.assertEqual(m["available_from"], "2026-10-03")
            self.assertEqual(m["name"], f"Claude Opus 5.5 ({effort.capitalize()})")

        # 1403, 1404, 1405: Claude Sonnet 5.5 (Low, Medium, High)
        sonnet_55_levels = [("1403", "low"), ("1404", "medium"), ("1405", "high")]
        for mid, effort in sonnet_55_levels:
            m = self.canonical_models.get(mid)
            self.assertIsNotNone(m, f"Model {mid} missing in canonical models")
            self.assertEqual(m["family"], "claude-sonnet")
            self.assertEqual(m["provider"], "anthropic")
            self.assertEqual(m["reasoning_effort"], effort)
            self.assertEqual(m["status"], "active")
            self.assertEqual(m["available_from"], "2026-10-03")
            self.assertEqual(m["name"], f"Claude Sonnet 5.5 ({effort.capitalize()})")

        # 342: GPT-OSS 120B (Medium)
        m342 = self.canonical_models.get("342")
        self.assertIsNotNone(m342)
        self.assertEqual(m342["name"], "GPT-OSS 120B (Medium)")
        self.assertEqual(m342["family"], "gpt-oss")
        self.assertEqual(m342["provider"], "openai")
        self.assertEqual(m342["reasoning_effort"], "medium")
        self.assertEqual(m342["sunset_date"], "2026-11-18")

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

    def test_carbon_rate_history_and_gpt_oss_availability(self):
        """Verify config/pricing.json 2-era rate_history for Carbon and sunset_at for GPT-OSS 342."""
        with open(self.pricing_json_path, "r", encoding="utf-8") as f:
            pricing = json.load(f)

        rate_history = pricing.get("rate_history", {})
        for mid in ("1427", "1437", "1438"):
            self.assertIn(mid, rate_history, f"Model {mid} missing in rate_history")
            eras = rate_history[mid]
            self.assertEqual(len(eras), 2, f"Expected 2-era rate_history for {mid}")
            self.assertEqual(eras[0]["valid_to"], "2026-11-30T23:59:59Z")
            self.assertEqual(
                eras[0]["rates_per_million"],
                {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
            )
            self.assertEqual(eras[1]["valid_from"], "2026-12-01T00:00:00Z")
            self.assertIsNone(eras[1]["valid_to"])
            self.assertEqual(
                eras[1]["rates_per_million"],
                {"prompt_uncached": 4.00, "prompt_cached": 0.20, "candidate_output": 20.00},
            )

        availability = pricing.get("availability", {})
        self.assertIn("342", availability)
        self.assertEqual(availability["342"]["sunset_at"], "2026-11-18T00:00:00Z")

    def test_pricing_sample_json_alignment(self):
        """Verify config/pricing.sample.json aligns with canonical names for critical models."""
        with open(self.pricing_sample_path, "r", encoding="utf-8") as f:
            sample = json.load(f)

        sample_models = sample.get("models", {})
        for model_id in (
            "1035", "1026", "342", "1198",
            "1400", "1401", "1402", "1403", "1404", "1405",
            "1417", "1418", "1419", "1427", "1437", "1438",
            "1667", "1681", "1669", "1528", "1525", "1526", "1527",
        ):
            self.assertIn(model_id, sample_models)
            self.assertEqual(
                sample_models[model_id]["name"],
                self.canonical_models[model_id]["name"]
            )

    def test_dashboard_frontend_alignment(self):
        """Verify dashboard/js/*.js and export catalog drive model/plan/simulator rendering without hardcoded JS tables."""
        all_js = "\n".join(f.read_text(encoding="utf-8") for f in sorted(self.js_dir.glob("*.js")))
        index_html = self.index_html_path.read_text(encoding="utf-8")

        # Verify zero hardcoded MODEL_TAXONOMY table remains in JS; catalog helpers getCatalog() & resolveModelDisplay() are used
        self.assertNotIn("const MODEL_TAXONOMY =", all_js)
        self.assertIn("function getCatalog(", all_js)
        self.assertIn("function resolveModelDisplay(", all_js)
        self.assertIn('id="executive-hero-card"', index_html)
        self.assertIn('id="exec-panel-weekly"', index_html)

        # Verify exported catalog contains all canonical models, quota_tracks, plan_tiers, and simulator_archetypes
        export_cat = build_export_catalog()
        self.assertEqual(export_cat.get("schema_version"), 2)
        cat_models = export_cat.get("models", {})
        for mid in ("1427", "1417", "1318", "1402", "1405", "1035", "1026", "342"):
            self.assertIn(mid, cat_models)
            self.assertEqual(cat_models[mid]["name"], self.canonical_models[mid]["name"])

        tracks = export_cat.get("quota_tracks", [])
        self.assertGreaterEqual(len(tracks), 2)
        track_ids = {t["id"] for t in tracks}
        self.assertIn("gemini", track_ids)
        self.assertIn("claude_gpt", track_ids)

        archetypes = export_cat.get("simulator_archetypes", [])
        self.assertGreaterEqual(len(archetypes), 3)
        for arch in archetypes:
            mid = str(arch.get("model_id", ""))
            self.assertIn(mid, self.canonical_models, f"Simulator archetype references unknown model_id {mid}")
            self.assertEqual(
                self.canonical_models[mid].get("status"),
                "active",
                f"Simulator archetype {arch.get('id')} references non-active model {mid}",
            )

    def test_simulator_archetype_alignment(self):
        """Verify src/simulator.py archetype presets resolve from catalog and reference active canonical models."""
        presets = get_archetype_presets()
        self.assertGreaterEqual(len(presets), 3)
        for arch_id, arch_cfg in presets.items():
            mid = str(arch_cfg.get("model_id", ""))
            self.assertIn(mid, self.canonical_models, f"Preset {arch_id} references unknown model {mid}")
            self.assertEqual(
                self.canonical_models[mid].get("status"),
                "active",
                f"Preset {arch_id} references deprecated model {mid}",
            )

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
            *sorted(self.js_dir.glob("*.js")),
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
