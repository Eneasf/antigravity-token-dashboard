"""
Compatibility shim for src/telemetry_reader.py.

All SQLite reading and workspace metadata extraction functionality has been
extracted to the standalone importable package `antigravity_telemetry` (ADR-040).
This module re-exports all symbols to preserve 100% backward compatibility.
"""

from antigravity_telemetry.reader import (
    DEFAULT_ANTIGRAVITY_DIR,
    get_conversation_title,
    get_workspace_mapping,
    clean_workspace_path,
    read_conversation_turns,
    read_single_conversation_metadata,
    read_conversation_metadata,
    discover_all_conversations,
    read_all_turns,
)

__all__ = [
    "DEFAULT_ANTIGRAVITY_DIR",
    "get_conversation_title",
    "get_workspace_mapping",
    "clean_workspace_path",
    "read_conversation_turns",
    "read_single_conversation_metadata",
    "read_conversation_metadata",
    "discover_all_conversations",
    "read_all_turns",
]
