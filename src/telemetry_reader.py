"""
src/telemetry_reader.py: Backward-compatibility shim for antigravity_telemetry.reader.

Adheres to:
- ADR-001: Safe Read-Only SQLite Access (?mode=ro, uri=True).
- ADR-002: Pure-Python Wire Protobuf Decoding (zero protoc/compiler dependencies).
"""

from antigravity_telemetry.reader import (
    DEFAULT_ANTIGRAVITY_DIR,
    get_conversation_title,
    get_workspace_mapping,
    clean_workspace_path,
    read_single_conversation_metadata,
    read_conversation_metadata,
    discover_all_conversations,
    read_conversation_turns,
    read_all_turns,
    extract_wire_latency_ms,
)

__all__ = [
    "DEFAULT_ANTIGRAVITY_DIR",
    "get_conversation_title",
    "get_workspace_mapping",
    "clean_workspace_path",
    "read_single_conversation_metadata",
    "read_conversation_metadata",
    "discover_all_conversations",
    "read_conversation_turns",
    "read_all_turns",
    "extract_wire_latency_ms",
]
