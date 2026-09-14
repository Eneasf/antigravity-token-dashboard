"""
antigravity_telemetry: Zero-dependency wire protocol telemetry engine for Google Antigravity.

Exports pure-Python protobuf wire decoding, non-blocking read-only SQLite conversation ingestion,
and clean canonical model census.

Zero third-party dependencies. Zero coupling to pricing, quotas, plans, or currencies.
"""

from pathlib import Path
import json
from typing import Any, Dict

from .parser import (
    parse_wire_fields,
    decode_wire_protobuf,
    extract_step_telemetry,
    extract_step_payload_details,
    extract_error_details,
)
from .reader import (
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

__version__ = "0.1.0"

_MODELS_PATH = Path(__file__).parent / "models.json"


def load_model_census() -> Dict[str, Any]:
    """
    Load canonical 19-model census without pricing, quota, or currency coupling.
    Returns mapping of model_id -> metadata dict (name, family, provider, reasoning_effort).
    """
    if _MODELS_PATH.exists():
        try:
            return json.loads(_MODELS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


__all__ = [
    "__version__",
    "parse_wire_fields",
    "decode_wire_protobuf",
    "extract_step_telemetry",
    "extract_step_payload_details",
    "extract_error_details",
    "DEFAULT_ANTIGRAVITY_DIR",
    "get_conversation_title",
    "get_workspace_mapping",
    "clean_workspace_path",
    "read_conversation_turns",
    "read_single_conversation_metadata",
    "read_conversation_metadata",
    "discover_all_conversations",
    "read_all_turns",
    "load_model_census",
]
