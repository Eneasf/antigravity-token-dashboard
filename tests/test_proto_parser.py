"""Unit tests for src/proto_parser.py."""

import unittest
from src.proto_parser import parse_wire_fields, extract_step_telemetry


def encode_varint(val: int) -> bytes:
    """Helper to encode an unsigned integer into protobuf varint bytes."""
    res = bytearray()
    while True:
        towrite = val & 0x7F
        val >>= 7
        if val:
            res.append(towrite | 0x80)
        else:
            res.append(towrite)
            break
    return bytes(res)


def make_field(field_num: int, wire_type: int, payload: bytes) -> bytes:
    """Helper to create a protobuf tag + payload."""
    key = (field_num << 3) | wire_type
    return encode_varint(key) + payload


class TestProtoParser(unittest.TestCase):

    def test_varint_parsing(self):
        # Field 1 = 150 (varint)
        data = make_field(1, 0, encode_varint(150))
        fields = parse_wire_fields(data)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0], (1, "varint", 150))

    def test_length_delimited_string(self):
        # Field 2 = "hello world"
        payload = b"hello world"
        data = make_field(2, 2, encode_varint(len(payload)) + payload)
        fields = parse_wire_fields(data)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0], (2, "bytes", payload))

    def test_extract_step_telemetry_full(self):
        # Construct submessage 1: timestamp
        ts_bytes = (
            make_field(1, 0, encode_varint(1788614000)) +
            make_field(2, 0, encode_varint(500000000))
        )
        field_1 = make_field(1, 2, encode_varint(len(ts_bytes)) + ts_bytes)

        # Construct submessage 9: usageMetadata
        resp_id = b"resp-test-xyz"
        usage_bytes = (
            make_field(1, 0, encode_varint(1318)) +             # model_id
            make_field(2, 0, encode_varint(4000)) +             # uncached prompt
            make_field(3, 0, encode_varint(500)) +              # total candidates
            make_field(5, 0, encode_varint(16000)) +            # cached prompt
            make_field(9, 0, encode_varint(350)) +              # thoughts/thinking
            make_field(10, 0, encode_varint(150)) +             # answer tokens
            make_field(11, 2, encode_varint(len(resp_id)) + resp_id) # response_id
        )
        field_9 = make_field(9, 2, encode_varint(len(usage_bytes)) + usage_bytes)

        full_metadata = field_1 + field_9

        res = extract_step_telemetry(full_metadata)
        self.assertIsNotNone(res)
        self.assertEqual(res["model_id"], "1318")
        self.assertEqual(res["prompt_tokens_uncached"], 4000)
        self.assertEqual(res["cached_tokens"], 16000)
        self.assertEqual(res["total_input_tokens"], 20000)
        self.assertEqual(res["output_tokens_total"], 500)
        self.assertEqual(res["thinking_tokens"], 350)
        self.assertEqual(res["answer_tokens"], 150)
        self.assertEqual(res["cache_hit_ratio_pct"], 80.0)
        self.assertEqual(res["response_id"], "resp-test-xyz")
        self.assertTrue(res["timestamp"].startswith("2026-"))

    def test_extract_step_telemetry_nested_session_id(self):
        """Field 8 contains nested protobuf submessage with field 2 containing session_id."""
        sess_bytes = b"session-uuid-12345"
        nested_field_8 = make_field(2, 2, encode_varint(len(sess_bytes)) + sess_bytes)

        usage_bytes = (
            make_field(1, 0, encode_varint(1318)) +
            make_field(8, 2, encode_varint(len(nested_field_8)) + nested_field_8)
        )
        metadata = make_field(9, 2, encode_varint(len(usage_bytes)) + usage_bytes)
        res = extract_step_telemetry(metadata)
        self.assertIsNotNone(res)
        self.assertEqual(res["session_id"], "session-uuid-12345")

    def test_extract_step_telemetry_fallback_session_id(self):
        """Field 8 with control characters and 'sessionID' prefix is sanitized."""
        dirty_bytes = b"\n\tsessionID\x12\x14clean-id-9999"
        usage_bytes = (
            make_field(1, 0, encode_varint(1318)) +
            make_field(8, 2, encode_varint(len(dirty_bytes)) + dirty_bytes)
        )
        metadata = make_field(9, 2, encode_varint(len(usage_bytes)) + usage_bytes)
        res = extract_step_telemetry(metadata)
        self.assertIsNotNone(res)
        self.assertNotIn("\x00", res["session_id"])
        self.assertNotIn("\n", res["session_id"])
        self.assertNotIn("\t", res["session_id"])
        self.assertNotIn("sessionID", res["session_id"])
        self.assertIn("clean-id-9999", res["session_id"])


if __name__ == "__main__":
    unittest.main()
