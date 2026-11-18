"""
Test Suite: Per-Model Context Truncation Thresholds & Severity Evaluation (Gate B1 / ADR-068)

Tests:
1. All 20 models in `antigravity_telemetry/models.json` have `context_truncation_tokens` defined as positive int.
2. `get_model_truncation_threshold(model_id)`:
   - Gemini models ("1318", "1016", "1050", etc.) return 1,000,000.
   - Claude models ("1035", "1026") return 200,000.
   - GPT-OSS ("342") return 200,000.
   - Unknown model ID ("unknown-999", "", None) returns 200,000 fallback.
3. 244k tokens scenario:
   - A session with 244,000 peak tokens on a model with 200,000 threshold (Claude) evaluates to `critical`.
   - A session with 244,000 peak tokens on a model with 1,000,000 threshold (Gemini 3.1 Pro / Flash) evaluates to `safe`.
4. 80% boundary:
   - 160,000 tokens on 200,000 threshold evaluates to `warning`.
   - 800,000 tokens on 1,000,000 threshold evaluates to `warning`.
"""

import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any, Dict, Optional
import unittest
from unittest.mock import patch

from src.vault import scan_conversation_truncation

REPO_ROOT = Path(__file__).resolve().parent.parent

# Import canonical census loader and threshold resolver from antigravity_telemetry
try:
    from antigravity_telemetry import (
        get_model_truncation_threshold,
        get_model_compaction_threshold,
        load_model_census,
    )
except ImportError:
    # Fallback loader if circular or during bootstrap
    def load_model_census() -> Dict[str, Any]:
        models_path = REPO_ROOT / "antigravity_telemetry" / "models.json"
        if models_path.exists():
            return json.loads(models_path.read_text(encoding="utf-8"))
        return {}

    def get_model_truncation_threshold(model_id: str, census: Optional[Dict[str, Any]] = None) -> int:
        if census is None:
            census = load_model_census()
        mid = str(model_id) if model_id is not None else ""
        if mid in census:
            return int(census[mid].get("context_truncation_tokens", 200000))
        return 200000

    def get_model_compaction_threshold(model_id: str, census: Optional[Dict[str, Any]] = None) -> int:
        if census is None:
            census = load_model_census()
        mid = str(model_id) if model_id is not None else ""
        if mid in census:
            return int(census[mid].get("compaction_threshold_tokens", 200000))
        return 200000

# Severity evaluation helper
try:
    from antigravity_telemetry import evaluate_truncation_severity
except ImportError:
    try:
        from scripts.export_dashboard import evaluate_truncation_severity
    except (ImportError, AttributeError):
        def evaluate_truncation_severity(peak_tokens: int, threshold_or_model: Any) -> str:
            """Evaluate session severity given peak tokens and a threshold or model ID."""
            if isinstance(threshold_or_model, (int, float)):
                threshold = int(threshold_or_model)
            else:
                threshold = get_model_truncation_threshold(str(threshold_or_model))
            if threshold <= 0:
                return "safe"
            ratio = peak_tokens / threshold
            if ratio >= 1.0:
                return "critical"
            if ratio >= 0.8:
                return "warning"
            return "safe"


class TestTruncationThresholds(unittest.TestCase):
    """Verifies per-model context truncation boundaries, thresholds, and severity evaluations."""

    def setUp(self):
        self.models_json_path = REPO_ROOT / "antigravity_telemetry" / "models.json"
        self.census = load_model_census()

    def test_all_32_models_have_positive_context_truncation_tokens(self):
        """All models in antigravity_telemetry/models.json have positive context_truncation_tokens and compaction_threshold_tokens."""
        self.assertGreaterEqual(len(self.census), 33, f"Expected >= 33 models in census, got {len(self.census)}")
        for model_id, info in self.census.items():
            self.assertIn(
                "context_truncation_tokens",
                info,
                f"Model {model_id} ({info.get('name')}) is missing 'context_truncation_tokens'",
            )
            tokens = info["context_truncation_tokens"]
            self.assertIsInstance(
                tokens,
                int,
                f"Model {model_id} 'context_truncation_tokens' must be an int, got {type(tokens).__name__}",
            )
            self.assertGreater(
                tokens,
                0,
                f"Model {model_id} 'context_truncation_tokens' must be positive, got {tokens}",
            )
            self.assertIn(
                "compaction_threshold_tokens",
                info,
                f"Model {model_id} ({info.get('name')}) is missing 'compaction_threshold_tokens'",
            )
            comp_tokens = info["compaction_threshold_tokens"]
            self.assertIsInstance(comp_tokens, int)
            self.assertGreater(comp_tokens, 0)

    def test_get_model_truncation_threshold_gemini_models(self):
        """Gemini models return 1,000,000 token truncation threshold."""
        gemini_ids = [mid for mid, info in self.census.items() if info.get("provider") == "google"]
        self.assertGreaterEqual(len(gemini_ids), 24)
        for m_id in gemini_ids:
            with self.subTest(model_id=m_id):
                threshold = get_model_truncation_threshold(m_id)
                self.assertEqual(
                    threshold,
                    1_000_000,
                    f"Gemini model {m_id} expected threshold 1,000,000, got {threshold}",
                )

    def test_get_model_truncation_threshold_claude_models(self):
        """Claude models return 200,000 token truncation threshold."""
        claude_ids = [mid for mid, info in self.census.items() if info.get("provider") == "anthropic"]
        self.assertGreaterEqual(len(claude_ids), 8)
        for m_id in claude_ids:
            with self.subTest(model_id=m_id):
                threshold = get_model_truncation_threshold(m_id)
                self.assertEqual(
                    threshold,
                    200_000,
                    f"Claude model {m_id} expected threshold 200,000, got {threshold}",
                )

    def test_get_model_truncation_threshold_gpt_oss_model(self):
        """OpenAI/GPT-OSS models return 200,000 token truncation threshold."""
        openai_ids = [mid for mid, info in self.census.items() if info.get("provider") == "openai"]
        self.assertGreaterEqual(len(openai_ids), 1)
        for m_id in openai_ids:
            threshold = get_model_truncation_threshold(m_id)
            self.assertEqual(
                threshold,
                200_000,
                f"OpenAI model {m_id} expected threshold 200,000, got {threshold}",
            )

    def test_get_model_truncation_threshold_unknown_fallback(self):
        """Unknown or missing model IDs return 200,000 fallback threshold."""
        self.assertEqual(get_model_truncation_threshold("unknown-999"), 200_000)
        self.assertEqual(get_model_truncation_threshold("non-existent"), 200_000)
        self.assertEqual(get_model_truncation_threshold(""), 200_000)
        self.assertEqual(get_model_truncation_threshold(None), 200_000)

    def test_get_model_compaction_threshold(self):
        """Verify calibrated empirical compaction limits: 250k Carbon/Argon/Flash 3.8, 165k 3.7, 80k Pro/Claude/GPT."""
        # Gemini 4 Carbon (250k)
        for mid in ("1427", "1437", "1438"):
            self.assertEqual(get_model_compaction_threshold(mid), 250_000)
        # Gemini 4 Orchestrator (planners + Hydrogen executor) & Hydrogen (250k compaction, 1M truncation)
        for mid in ("1667", "1681", "1669", "1525", "1526", "1527", "1528"):
            self.assertEqual(get_model_compaction_threshold(mid), 250_000)
            self.assertEqual(get_model_truncation_threshold(mid), 1_000_000)
        # Gemini 4 Argon (250k)
        for mid in ("1417", "1418", "1419"):
            self.assertEqual(get_model_compaction_threshold(mid), 250_000)
        # Gemini 3.8 Flash (250k)
        self.assertEqual(get_model_compaction_threshold("1318"), 250_000)
        self.assertEqual(get_model_compaction_threshold("1319"), 250_000)
        # Gemini 3.7 Flash (165k)
        self.assertEqual(get_model_compaction_threshold("1298"), 165_000)
        # Gemini 3.1 Pro (80k)
        self.assertEqual(get_model_compaction_threshold("1016"), 80_000)
        self.assertEqual(get_model_compaction_threshold("1036"), 80_000)
        # Claude (80k)
        self.assertEqual(get_model_compaction_threshold("1035"), 80_000)
        self.assertEqual(get_model_compaction_threshold("1026"), 80_000)
        for mid in ("1400", "1401", "1402", "1403", "1404", "1405"):
            self.assertEqual(get_model_compaction_threshold(mid), 80_000)
        # GPT-OSS (80k)
        self.assertEqual(get_model_compaction_threshold("342"), 80_000)
        # Fallback
        self.assertEqual(get_model_compaction_threshold("unknown"), 200_000)

    def test_244k_tokens_scenario(self):
        """
        244k tokens scenario:
        - 244,000 peak tokens on 200,000 threshold (Claude) evaluates to critical.
        - 244,000 peak tokens on 1,000,000 threshold (Gemini 3.1 Pro / Flash) evaluates to safe (normal).
        """
        # Claude (200,000 threshold): 244,000 >= 200,000 -> critical
        self.assertEqual(evaluate_truncation_severity(244_000, 200_000), "critical")
        self.assertEqual(evaluate_truncation_severity(244_000, "1035"), "critical")
        self.assertEqual(evaluate_truncation_severity(244_000, "1026"), "critical")

        # Gemini (1,000,000 threshold): 244,000 < 800,000 (80%) -> safe
        self.assertEqual(evaluate_truncation_severity(244_000, 1_000_000), "safe")
        self.assertEqual(evaluate_truncation_severity(244_000, "1016"), "safe")
        self.assertEqual(evaluate_truncation_severity(244_000, "1318"), "safe")
        self.assertEqual(evaluate_truncation_severity(244_000, "1417"), "safe")

    def test_80_percent_boundary(self):
        """
        80% boundary:
        - 160,000 tokens on 200,000 threshold evaluates to warning.
        - 800,000 tokens on 1,000,000 threshold evaluates to warning.
        """
        # 200,000 threshold
        # Exactly 80% (160,000) -> warning
        self.assertEqual(evaluate_truncation_severity(160_000, 200_000), "warning")
        self.assertEqual(evaluate_truncation_severity(160_000, "1035"), "warning")
        self.assertEqual(evaluate_truncation_severity(160_000, "1026"), "warning")

        # Just below 80% (159,999) -> safe
        self.assertEqual(evaluate_truncation_severity(159_999, 200_000), "safe")
        self.assertEqual(evaluate_truncation_severity(159_999, "1035"), "safe")

        # At or above 100% (200,000) -> critical
        self.assertEqual(evaluate_truncation_severity(200_000, 200_000), "critical")
        self.assertEqual(evaluate_truncation_severity(250_000, "1035"), "critical")

        # 1,000,000 threshold
        # Exactly 80% (800,000) -> warning
        self.assertEqual(evaluate_truncation_severity(800_000, 1_000_000), "warning")
        self.assertEqual(evaluate_truncation_severity(800_000, "1016"), "warning")
        self.assertEqual(evaluate_truncation_severity(800_000, "1318"), "warning")

        # Just below 80% (799,999) -> safe
        self.assertEqual(evaluate_truncation_severity(799_999, 1_000_000), "safe")
        self.assertEqual(evaluate_truncation_severity(799_999, "1016"), "safe")

        # At or above 100% (1,000,000) -> critical
        self.assertEqual(evaluate_truncation_severity(1_000_000, 1_000_000), "critical")
        self.assertEqual(evaluate_truncation_severity(1_200_000, "1016"), "critical")


class TestModelCensusResilience(unittest.TestCase):
    """Verifies resilience of model census loading, exception handling, and caller immunity to TypeErrors."""

    def test_load_model_census_success(self):
        """Normal load returns dict of >= 33 models."""
        census = load_model_census()
        self.assertIsInstance(census, dict)
        self.assertGreaterEqual(len(census), 33)
        self.assertIn("1317", census)
        self.assertIn("1318", census)
        self.assertIn("1417", census)
        self.assertIn("1427", census)

    def test_load_model_census_missing_file_fallback(self):
        """Missing models.json returns empty dict and logs to sys.stderr rather than returning None."""
        stderr_capture = io.StringIO()
        with patch.object(Path, "exists", return_value=False), patch("sys.stderr", stderr_capture):
            census = load_model_census()
        self.assertIsInstance(census, dict)
        self.assertEqual(census, {})
        self.assertIn("Model census file not found", stderr_capture.getvalue())

    def test_load_model_census_corrupted_json_fallback(self):
        """Corrupted JSON in models.json returns empty dict and logs error rather than returning None."""
        stderr_capture = io.StringIO()
        with patch.object(Path, "read_text", return_value="{corrupted json!"), patch("sys.stderr", stderr_capture):
            census = load_model_census()
        self.assertIsInstance(census, dict)
        self.assertEqual(census, {})
        self.assertIn("Failed to load model census", stderr_capture.getvalue())

    def test_load_model_census_os_error_fallback(self):
        """OSError during reading models.json returns empty dict and logs error."""
        stderr_capture = io.StringIO()
        with patch.object(Path, "read_text", side_effect=PermissionError("Permission denied")), patch("sys.stderr", stderr_capture):
            census = load_model_census()
        self.assertIsInstance(census, dict)
        self.assertEqual(census, {})
        self.assertIn("Failed to load model census", stderr_capture.getvalue())

    def test_get_model_truncation_threshold_resilient_to_missing_file(self):
        """get_model_truncation_threshold does not raise TypeError when models.json is missing."""
        with patch.object(Path, "exists", return_value=False):
            # Must return default 200,000 without crashing with TypeError
            threshold = get_model_truncation_threshold("1318")
            self.assertEqual(threshold, 200_000)

    def test_get_model_truncation_threshold_resilient_to_corrupted_json(self):
        """get_model_truncation_threshold does not raise TypeError when models.json has syntax errors."""
        with patch.object(Path, "read_text", return_value="INVALID JSON"):
            threshold = get_model_truncation_threshold("1318")
            self.assertEqual(threshold, 200_000)

    def test_get_model_truncation_threshold_resilient_to_none_or_non_dict_census(self):
        """get_model_truncation_threshold handles None or invalid census objects defensively."""
        # Explicitly passing census=None triggers internal fallback load
        threshold = get_model_truncation_threshold("1318", census=None)
        self.assertEqual(threshold, 1_000_000)

        # Defensively handles non-dict census types passed by callers
        self.assertEqual(get_model_truncation_threshold("1318", census="not_a_dict"), 200_000)
        self.assertEqual(get_model_truncation_threshold("1318", census=12345), 200_000)

    def test_evaluate_truncation_severity_resilient_to_census_failure(self):
        """evaluate_truncation_severity safely degrades when census cannot be read."""
        with patch.object(Path, "exists", return_value=False):
            # With fallback 200,000 threshold:
            # 250,000 tokens >= 200,000 -> critical
            severity = evaluate_truncation_severity(250_000, "1318")
            self.assertEqual(severity, "critical")

            # 100,000 tokens < 160,000 (80%) -> safe
            severity = evaluate_truncation_severity(100_000, "1318")
            self.assertEqual(severity, "safe")


class TestCompactionStepTypeAndSignatureFiltering(unittest.TestCase):
    """
    Phase 4: Verify authoritative step_type = 23 (CHECKPOINT) detection
    and immunity to self-referential discussions, tool execution records,
    and file view diffs mentioning CONTEXT_SUMMARY.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_convo.db"
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            CREATE TABLE steps (
                idx INTEGER PRIMARY KEY,
                step_type INTEGER,
                metadata BLOB,
                step_payload BLOB
            )
            """
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _insert_step(self, idx: int, step_type: int, payload: bytes, metadata: Optional[bytes] = None):
        conn = sqlite3.connect(self.db_path)
        conn.execute("INSERT INTO steps VALUES (?, ?, ?, ?)", (idx, step_type, metadata, payload))
        conn.commit()
        conn.close()

    def test_viewing_or_grepping_context_summary_does_not_increment_epoch(self):
        """Tool calls (step_type = 132) viewing or searching for CONTEXT_SUMMARY must not trigger truncation."""
        # Step 1: Tool call running grep_search for CONTEXT_SUMMARY
        self._insert_step(
            1, 132,
            b'{"tool_name": "grep_search", "Query": "CONTEXT_SUMMARY", "SearchPath": "/workspace"}'
        )
        # Step 2: Tool call viewing a file containing CONTEXT_SUMMARY
        self._insert_step(
            2, 132,
            b'{"tool_name": "view_file", "path": "docs/HANDOVER.md", "content": "Scanned for <CONTEXT_SUMMARY>"}'
        )
        # Step 3: Tool call executing python script containing CONTEXT_SUMMARY
        self._insert_step(
            3, 132,
            b'{"tool_name": "run_command", "CommandLine": "python3 -c \\"print(\'<CONTEXT_SUMMARY>\')\\""}'
        )

        res = scan_conversation_truncation(self.db_path)
        self.assertFalse(res.has_truncated)
        self.assertEqual(res.compaction_count, 0)
        self.assertEqual(res.epoch, 1)

    def test_model_discussion_of_context_summary_does_not_increment_epoch(self):
        """Planner/model responses (step_type = 15) discussing CONTEXT_SUMMARY must not trigger truncation."""
        self._insert_step(
            1, 15,
            b"Yes, <CONTEXT_SUMMARY> is a marker used in historical study documents."
        )
        self._insert_step(
            2, 15,
            b"Whenever you see <CONTEXT_SUMMARY>\nThe following is a summary of the conversation history"
        )

        res = scan_conversation_truncation(self.db_path)
        self.assertFalse(res.has_truncated)
        self.assertEqual(res.compaction_count, 0)
        self.assertEqual(res.epoch, 1)

    def test_genuine_step_type_23_detected_accurately(self):
        """Genuine system compaction (step_type = 23) correctly increments compaction_count and epoch."""
        # 5 tool calls discussing CONTEXT_SUMMARY
        for i in range(1, 6):
            self._insert_step(i, 132, f'{{"tool_name": "view_file", "query": "CONTEXT_SUMMARY {i}"}}'.encode())

        # Step 6: genuine compaction checkpoint
        self._insert_step(6, 23, b"<summary>\n### 1. Task Overview\nCompacted state.</summary>")

        # 5 more tool calls discussing CONTEXT_SUMMARY
        for i in range(7, 12):
            self._insert_step(i, 132, f'{{"tool_name": "run_command", "args": "grep CONTEXT_SUMMARY {i}"}}'.encode())

        res = scan_conversation_truncation(self.db_path)
        self.assertTrue(res.has_truncated)
        self.assertEqual(res.first_mark, 6)
        self.assertEqual(res.compaction_count, 1)
        self.assertEqual(res.epoch, 2)

    def test_multi_epoch_genuine_compaction_chain(self):
        """Successive genuine compactions (step_type = 23) increment epoch monotonically without false inflation."""
        self._insert_step(10, 23, b"Checkpoint 1")
        self._insert_step(20, 132, b"Tool call mentioning <CONTEXT_SUMMARY>")
        self._insert_step(30, 23, b"Checkpoint 2")
        self._insert_step(40, 15, b"Assistant response mentioning <CONTEXT_SUMMARY>")
        self._insert_step(50, 23, b"Checkpoint 3")

        res = scan_conversation_truncation(self.db_path)
        self.assertTrue(res.has_truncated)
        self.assertEqual(res.first_mark, 10)
        self.assertEqual(res.compaction_count, 3)
        self.assertEqual(res.epoch, 4)

    def test_system_summary_with_leading_whitespace_or_newlines(self):
        """Genuine system compaction headers with leading whitespace or newlines are recognized in fallback."""
        # Non-standard system step (e.g. step_type = 200) with leading whitespace/newline
        payload = b"\n\n  <CONTEXT_SUMMARY>\nThe following is a summary of the conversation history that has been truncated to fit within the context window:"
        self._insert_step(5, 200, payload)

        res = scan_conversation_truncation(self.db_path)
        self.assertTrue(res.has_truncated)
        self.assertEqual(res.first_mark, 5)
        self.assertEqual(res.compaction_count, 1)
        self.assertEqual(res.epoch, 2)

    def test_metadata_column_fallback_for_synthetic_fixtures(self):
        """If CONTEXT_SUMMARY is placed in metadata column of a system step, it is detected while tool call metadata is rejected."""
        # Tool call with CONTEXT_SUMMARY in metadata -> rejected
        self._insert_step(1, 132, b"output", metadata=b"<CONTEXT_SUMMARY> in tool metadata")
        # System step with CONTEXT_SUMMARY in metadata -> accepted
        self._insert_step(8, 200, b"data", metadata=b"<CONTEXT_SUMMARY> compressed history")

        res = scan_conversation_truncation(self.db_path)
        self.assertTrue(res.has_truncated)
        self.assertEqual(res.first_mark, 8)
        self.assertEqual(res.compaction_count, 1)
        self.assertEqual(res.epoch, 2)


if __name__ == "__main__":
    unittest.main()
