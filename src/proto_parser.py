"""
Compatibility shim for src/proto_parser.py.

All wire protobuf parsing functionality has been extracted to the standalone
importable package `antigravity_telemetry` (ADR-040). This module re-exports
all symbols to preserve 100% backward compatibility.
"""

from antigravity_telemetry.parser import (
    parse_wire_fields,
    decode_wire_protobuf,
    extract_step_telemetry,
    extract_step_payload_details,
    extract_error_details,
)

__all__ = [
    "parse_wire_fields",
    "decode_wire_protobuf",
    "extract_step_telemetry",
    "extract_step_payload_details",
    "extract_error_details",
]
