"""
Unit tests for src/telemetry_reader.py (Wire Protobuf TTFT & Latency Pipeline).
"""

from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.telemetry_reader import (
    DEFAULT_ANTIGRAVITY_DIR,
    extract_wire_latency_ms,
    read_conversation_turns,
    read_all_turns,
)


def encode_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        b = value & 0x7F
        value >>= 7
        if value:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def encode_field(field_num: int, wire_type: int, payload: bytes) -> bytes:
    key = (field_num << 3) | wire_type
    return encode_varint(key) + payload


def encode_length_delimited(field_num: int, payload: bytes) -> bytes:
    return encode_field(field_num, 2, encode_varint(len(payload)) + payload)


def encode_timestamp(seconds: int, nanos: int = 0) -> bytes:
    p = encode_field(1, 0, encode_varint(seconds))
    if nanos > 0:
        p += encode_field(2, 0, encode_varint(nanos))
    return p


class TestTelemetryReader(unittest.TestCase):

    def test_extract_wire_latency_ms_empty_and_corrupt(self):
        self.assertEqual(extract_wire_latency_ms(None), {"ttft_ms": None, "latency_ms": None})
        self.assertEqual(extract_wire_latency_ms(b""), {"ttft_ms": None, "latency_ms": None})
        self.assertEqual(extract_wire_latency_ms(b"\xff\xff\xff"), {"ttft_ms": None, "latency_ms": None})

    def test_extract_wire_latency_ms_standard_f6_f7_f8(self):
        ts_req = encode_timestamp(1000, 0)
        ts_first = encode_timestamp(1000, 75000000)      # +75ms
        ts_done = encode_timestamp(1001, 200000000)     # +1200ms

        blob = (
            encode_length_delimited(6, ts_req)
            + encode_length_delimited(7, ts_first)
            + encode_length_delimited(8, ts_done)
        )
        res = extract_wire_latency_ms(blob)
        self.assertEqual(res, {"ttft_ms": 75.0, "latency_ms": 1200.0})

    def test_extract_wire_latency_ms_field_1_created_at_fallback(self):
        ts_created = encode_timestamp(1000, 0)
        ts_first = encode_timestamp(1000, 150000000)     # +150ms
        ts_done = encode_timestamp(1002, 0)             # +2000ms

        blob = (
            encode_length_delimited(1, ts_created)
            + encode_length_delimited(7, ts_first)
            + encode_length_delimited(8, ts_done)
        )
        res = extract_wire_latency_ms(blob)
        self.assertEqual(res, {"ttft_ms": 150.0, "latency_ms": 2000.0})

    def test_extract_wire_latency_ms_field_26_streaming_chunk_fallback(self):
        ts_req = encode_timestamp(1000, 0)
        chunk1 = encode_length_delimited(1, encode_timestamp(1000, 80000000))
        chunk2 = encode_length_delimited(1, encode_timestamp(1001, 500000000))

        blob = (
            encode_length_delimited(6, ts_req)
            + encode_length_delimited(26, chunk1)
            + encode_length_delimited(26, chunk2)
        )
        res = extract_wire_latency_ms(blob)
        self.assertEqual(res, {"ttft_ms": 80.0, "latency_ms": 1500.0})

    def test_extract_wire_latency_ms_clamping_and_validation(self):
        ts_req = encode_timestamp(1000, 0)

        # Negative difference (clock skew) -> None
        ts_skew = encode_timestamp(999, 0)
        blob_neg = encode_length_delimited(6, ts_req) + encode_length_delimited(7, ts_skew)
        self.assertIsNone(extract_wire_latency_ms(blob_neg)["ttft_ms"])

        # TTFT exceeding 600,000ms (10 minutes) -> None
        ts_huge_ttft = encode_timestamp(1601, 0)
        blob_huge_ttft = encode_length_delimited(6, ts_req) + encode_length_delimited(7, ts_huge_ttft)
        self.assertIsNone(extract_wire_latency_ms(blob_huge_ttft)["ttft_ms"])

        # Latency exceeding 1,800,000ms (30 minutes) -> None
        ts_huge_lat = encode_timestamp(2801, 0)
        blob_huge_lat = encode_length_delimited(6, ts_req) + encode_length_delimited(8, ts_huge_lat)
        self.assertIsNone(extract_wire_latency_ms(blob_huge_lat)["latency_ms"])

    def test_read_conversation_turns_attaches_latency(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_convo.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                """
                CREATE TABLE steps (
                    idx INTEGER PRIMARY KEY,
                    step_type INTEGER,
                    status INTEGER,
                    metadata BLOB
                );
                """
            )

            # Construct valid metadata blob:
            # Field 1: created_at
            # Field 6: req
            # Field 7: first
            # Field 8: done
            # Field 9: usage (model_id=1322, uncached=100, output=50, cached=20)
            ts_created = encode_timestamp(1000, 0)
            ts_req = encode_timestamp(1000, 10000000)
            ts_first = encode_timestamp(1000, 85000000)
            ts_done = encode_timestamp(1001, 50000000)

            usage = (
                encode_field(1, 0, encode_varint(1322))
                + encode_field(2, 0, encode_varint(100))
                + encode_field(3, 0, encode_varint(50))
                + encode_field(5, 0, encode_varint(20))
            )
            meta_blob = (
                encode_length_delimited(1, ts_created)
                + encode_length_delimited(6, ts_req)
                + encode_length_delimited(7, ts_first)
                + encode_length_delimited(8, ts_done)
                + encode_length_delimited(9, usage)
            )

            conn.execute(
                "INSERT INTO steps (idx, step_type, status, metadata) VALUES (?, ?, ?, ?)",
                (1, 15, 3, sqlite3.Binary(meta_blob)),
            )
            conn.commit()
            conn.close()

            turns = read_conversation_turns(db_path)
            self.assertEqual(len(turns), 1)
            turn = turns[0]
            self.assertEqual(turn["step_idx"], 1)
            self.assertEqual(turn["convo_id"], "test_convo")
            self.assertEqual(turn["model_id"], "1322")
            self.assertAlmostEqual(turn["ttft_ms"], 75.0, places=1)
            self.assertAlmostEqual(turn["latency_ms"], 1040.0, places=1)


if __name__ == "__main__":
    unittest.main()
