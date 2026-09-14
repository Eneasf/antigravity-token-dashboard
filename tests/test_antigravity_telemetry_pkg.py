"""
Unit test suite for standalone importable package `antigravity_telemetry`.

Validates:
- Public API surface & version exports
- Zero third-party dependencies invariant
- Pure-Python wire protobuf decoding & alias parity
- Safe read-only SQLite connector & ?mode=ro invariant (ADR-001)
- Canonical 19-model census without pricing/quota coupling
- Standalone CLI subcommands (dump --json, models --json, conversations --json)
- Backward compatibility shims in src/proto_parser.py and src/telemetry_reader.py
"""

from io import StringIO
from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

import antigravity_telemetry as agy
from antigravity_telemetry import (
    DEFAULT_ANTIGRAVITY_DIR,
    __version__,
    clean_workspace_path,
    decode_wire_protobuf,
    discover_all_conversations,
    extract_error_details,
    extract_step_payload_details,
    extract_step_telemetry,
    get_conversation_title,
    get_workspace_mapping,
    load_model_census,
    parse_wire_fields,
    read_all_turns,
    read_conversation_metadata,
    read_conversation_turns,
    read_single_conversation_metadata,
)
from antigravity_telemetry.__main__ import main as cli_main


class TestAntigravityTelemetryPackage(unittest.TestCase):
    """Test suite for the independent antigravity_telemetry package."""

    def test_public_api_surface(self):
        """All documented public functions and symbols must be accessible and callable."""
        self.assertEqual(__version__, "0.1.0")
        callables = [
            decode_wire_protobuf,
            parse_wire_fields,
            extract_step_telemetry,
            extract_step_payload_details,
            extract_error_details,
            read_conversation_turns,
            read_single_conversation_metadata,
            read_conversation_metadata,
            discover_all_conversations,
            read_all_turns,
            get_conversation_title,
            get_workspace_mapping,
            clean_workspace_path,
            load_model_census,
        ]
        for fn in callables:
            self.assertTrue(callable(fn), f"Expected {fn} to be callable")

        self.assertTrue(isinstance(DEFAULT_ANTIGRAVITY_DIR, Path))
        for symbol in agy.__all__:
            self.assertTrue(hasattr(agy, symbol), f"Exported symbol '{symbol}' not found in package")

    def test_zero_dependencies_hygiene(self):
        """Package must strictly use Python standard library without 3rd party deps."""
        # Non-standard libraries that must NOT be loaded by antigravity_telemetry
        forbidden = ["requests", "numpy", "pandas", "google", "protobuf", "pydantic", "flask", "fastapi"]
        for mod in forbidden:
            self.assertNotIn(mod, sys.modules, f"Forbidden third-party package '{mod}' detected in sys.modules")

    def test_canonical_19_model_census(self):
        """Model census must contain exactly 19 canonical models without pricing/quota coupling."""
        census = load_model_census()
        self.assertEqual(len(census), 19, f"Expected 19 models in census, got {len(census)}")

        expected_ids = {
            "1318", "1298", "1016", "1322", "1132", "1301", "1035", "1072",
            "1026", "1071", "1319", "1020", "1036", "342", "1299", "1050",
            "1073", "1300", "1320"
        }
        self.assertEqual(set(census.keys()), expected_ids)

        for mid, data in census.items():
            self.assertIn("name", data, f"Model {mid} missing 'name'")
            self.assertIn("family", data, f"Model {mid} missing 'family'")
            self.assertIn("provider", data, f"Model {mid} missing 'provider'")
            self.assertIn("reasoning_effort", data, f"Model {mid} missing 'reasoning_effort'")
            # Enforce zero pricing coupling
            self.assertNotIn("rates_per_million", data, f"Model {mid} coupled to rates_per_million")
            self.assertNotIn("credits_per_turn", data, f"Model {mid} coupled to credits_per_turn")
            self.assertNotIn("price_usd", data, f"Model {mid} coupled to price_usd")
            self.assertNotIn("price_gbp", data, f"Model {mid} coupled to price_gbp")

    def test_decode_wire_protobuf_alias_parity(self):
        """decode_wire_protobuf must produce byte-identical results to parse_wire_fields."""
        # Construct wire bytes: field 1 varint 42, field 2 string "antigravity"
        raw_wire = bytes([
            (1 << 3) | 0, 42,
            (2 << 3) | 2, 11, *b"antigravity",
        ])
        fields1 = parse_wire_fields(raw_wire)
        fields2 = decode_wire_protobuf(raw_wire)
        self.assertEqual(fields1, fields2)
        self.assertEqual(len(fields1), 2)
        self.assertEqual(fields1[0], (1, "varint", 42))
        self.assertEqual(fields1[1], (2, "bytes", b"antigravity"))

    def test_extract_step_telemetry_synthetic(self):
        """extract_step_telemetry decodes timestamp and usage tokens from nested metadata."""
        # Build field 9 usage submessage:
        # 1=1318 (model), 2=100 (uncached), 3=50 (output), 5=500 (cached), 9=20 (thinking), 10=30 (answer)
        sub_9 = bytes([
            (1 << 3) | 0, 166, 10,  # 1318 in varint: 1318 = 0x526 -> 0xA6 (166) 0x0A (10)
            (2 << 3) | 0, 100,
            (3 << 3) | 0, 50,
            (5 << 3) | 0, 244, 3,   # 500 = 0x1F4 -> 0xF4 0x03
            (9 << 3) | 0, 20,
            (10 << 3) | 0, 30,
        ])
        # Top message: field 9 length-delimited
        top_msg = bytes([(9 << 3) | 2, len(sub_9)]) + sub_9

        res = extract_step_telemetry(top_msg)
        self.assertIsNotNone(res)
        self.assertEqual(res["model_id"], "1318")
        self.assertEqual(res["prompt_tokens_uncached"], 100)
        self.assertEqual(res["cached_tokens"], 500)
        self.assertEqual(res["total_input_tokens"], 600)
        self.assertEqual(res["output_tokens_total"], 50)
        self.assertEqual(res["thinking_tokens"], 20)
        self.assertEqual(res["answer_tokens"], 30)
        self.assertAlmostEqual(res["cache_hit_ratio_pct"], 83.33, places=2)

    def test_reader_readonly_and_read_all_turns(self):
        """Verify read-only SQLite connector, ?mode=ro enforcement, and read_all_turns aggregation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            conv_dir = base_dir / "conversations"
            conv_dir.mkdir(parents=True)

            db_path = conv_dir / "00000000-0000-0000-0000-000000000001.db"
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("CREATE TABLE steps (idx INTEGER, step_type INTEGER, metadata BLOB, step_payload BLOB);")

            # Create synthetic turn
            # uncached: 100, output: 40, cached: 400 (144, 3) -> total input: 500
            sub_9 = bytes([
                (1 << 3) | 0, 166, 10,
                (2 << 3) | 0, 100,
                (3 << 3) | 0, 40,
                (5 << 3) | 0, 144, 3,
            ])
            top_msg = bytes([(9 << 3) | 2, len(sub_9)]) + sub_9

            cur.execute("INSERT INTO steps VALUES (?, ?, ?, ?)", (1, 15, top_msg, b""))
            # Non-model turn (should be ignored)
            cur.execute("INSERT INTO steps VALUES (?, ?, ?, ?)", (2, 2, b"", b""))
            conn.commit()
            conn.close()

            # Test read_conversation_turns
            turns = read_conversation_turns(db_path)
            self.assertEqual(len(turns), 1)
            self.assertEqual(turns[0]["model_id"], "1318")
            self.assertEqual(turns[0]["step_idx"], 1)
            self.assertEqual(turns[0]["total_input_tokens"], 500)

            # Test discover_all_conversations
            convos = discover_all_conversations(base_dir)
            self.assertEqual(len(convos), 1)
            self.assertEqual(convos[0]["convo_id"], "00000000-0000-0000-0000-000000000001")

            # Test read_all_turns
            all_turns = read_all_turns(base_dir)
            self.assertEqual(len(all_turns), 1)
            self.assertEqual(all_turns[0]["convo_id"], "00000000-0000-0000-0000-000000000001")

    def test_cli_subcommands(self):
        """Test standalone CLI execution: dump --json, models --json, conversations --json."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            conv_dir = base_dir / "conversations"
            conv_dir.mkdir(parents=True)

            # 1. Test models --json
            buf = StringIO()
            with patch("sys.stdout", buf):
                ret = cli_main(["models", "--json"])
            self.assertEqual(ret, 0)
            data = json.loads(buf.getvalue())
            self.assertEqual(len(data), 19)

            # 2. Test dump --json with empty runtime
            buf = StringIO()
            with patch("sys.stdout", buf):
                ret = cli_main(["dump", "--json", "--antigravity-dir", str(base_dir)])
            self.assertEqual(ret, 0)
            turns = json.loads(buf.getvalue())
            self.assertEqual(turns, [])

            # 3. Test conversations --json
            buf = StringIO()
            with patch("sys.stdout", buf):
                ret = cli_main(["conversations", "--json", "--antigravity-dir", str(base_dir)])
            self.assertEqual(ret, 0)
            convos = json.loads(buf.getvalue())
            self.assertEqual(convos, [])

    def test_backward_compatibility_shims(self):
        """src/proto_parser.py and src/telemetry_reader.py must match antigravity_telemetry exports."""
        from src.proto_parser import (
            decode_wire_protobuf as shim_decode,
            extract_step_telemetry as shim_extract_telemetry,
            parse_wire_fields as shim_parse_wire,
        )
        from src.telemetry_reader import (
            DEFAULT_ANTIGRAVITY_DIR as SHIM_DIR,
            discover_all_conversations as shim_discover,
            read_all_turns as shim_read_all,
            read_conversation_turns as shim_read_turns,
        )

        self.assertIs(shim_decode, decode_wire_protobuf)
        self.assertIs(shim_parse_wire, parse_wire_fields)
        self.assertIs(shim_extract_telemetry, extract_step_telemetry)
        self.assertIs(SHIM_DIR, DEFAULT_ANTIGRAVITY_DIR)
        self.assertIs(shim_discover, discover_all_conversations)
        self.assertIs(shim_read_turns, read_conversation_turns)
        self.assertIs(shim_read_all, read_all_turns)


if __name__ == "__main__":
    unittest.main()
