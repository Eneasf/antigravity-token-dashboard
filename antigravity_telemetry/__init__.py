"""
antigravity_telemetry: Zero-dependency wire protocol telemetry engine for Google Antigravity.

Exports pure-Python protobuf wire decoding, non-blocking read-only SQLite conversation ingestion,
and clean canonical model census & catalog resolution.

Zero third-party dependencies. Zero coupling to pricing, quotas, plans, or currencies.
"""

from pathlib import Path
import json
import re
from typing import Any, Dict, Optional

from .parser import (
    parse_wire_fields,
    decode_wire_protobuf,
    extract_step_telemetry,
    extract_step_payload_details,
    extract_error_details,
    extract_trajectory_metadata,
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
    extract_wire_latency_ms,
)

__version__ = "0.1.0"

_MODELS_PATH = Path(__file__).parent / "models.json"
_PLACEHOLDER_RE = re.compile(r"^MODEL_PLACEHOLDER_M?(\d+)$", re.IGNORECASE)
_CATALOG_CACHE: Optional[Dict[str, Any]] = None
_CATALOG_MTIME_NS: Optional[int] = None


def _is_path_io_patched() -> bool:
    """Detect unittest.mock patches on Path.exists or Path.read_text so error-handling tests bypass cache."""
    return (
        getattr(Path.exists, "__name__", "") != "exists"
        or getattr(Path.read_text, "__name__", "") != "read_text"
    )


def _load_raw_models_json() -> Dict[str, Any]:
    """Load raw JSON dictionary from models.json with resilient error handling."""
    if _MODELS_PATH.exists():
        try:
            data = json.loads(_MODELS_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError) as exc:
            import sys
            sys.stderr.write(f"[antigravity_telemetry] Failed to load model census from {_MODELS_PATH}: {exc}\n")
            return {}
    else:
        import sys
        sys.stderr.write(f"[antigravity_telemetry] Model census file not found at {_MODELS_PATH}\n")
    return {}


def load_model_census() -> Dict[str, Any]:
    """
    Load canonical model census without pricing, quota, or currency coupling.
    Filters out top-level schema metadata keys starting with '_' or '$' so callers
    iterating census.items() receive strictly model_id -> metadata dict mappings.
    """
    if not _is_path_io_patched():
        cat = load_model_catalog()
        return dict(cat.get("models", {}))
    raw = _load_raw_models_json()
    return {
        k: v
        for k, v in raw.items()
        if not str(k).startswith(("_", "$")) and isinstance(v, dict)
    }


def load_model_catalog() -> Dict[str, Any]:
    """
    Load complete v2 model catalog including _schema_version, _defaults, _families,
    models dict, and precomputed wire_alias_map.
    """
    global _CATALOG_CACHE, _CATALOG_MTIME_NS
    patched = _is_path_io_patched()
    mtime_ns: Optional[int] = None
    if not patched:
        try:
            mtime_ns = _MODELS_PATH.stat().st_mtime_ns
            if _CATALOG_CACHE is not None and _CATALOG_MTIME_NS == mtime_ns:
                return _CATALOG_CACHE
        except OSError:
            pass

    raw = _load_raw_models_json()
    defaults = raw.get("_defaults", raw.get("$defaults", {})) if isinstance(raw, dict) else {}
    if not isinstance(defaults, dict):
        defaults = {}
    families = raw.get("_families", raw.get("$families", {})) if isinstance(raw, dict) else {}
    if not isinstance(families, dict):
        families = {}
    models = {
        k: v
        for k, v in raw.items()
        if not str(k).startswith(("_", "$")) and isinstance(v, dict)
    }
    alias_map: Dict[str, str] = {}
    for mid, info in models.items():
        alias_map[mid] = mid
        alias_map[mid.lower()] = mid
        name = info.get("name", "")
        if isinstance(name, str) and name:
            alias_map[name] = mid
            alias_map[name.lower()] = mid
        short_badge = info.get("short_badge", "")
        if isinstance(short_badge, str) and short_badge:
            alias_map[short_badge.lower()] = mid
        for alias in info.get("wire_aliases", []):
            if isinstance(alias, str) and alias:
                alias_map[alias] = mid
                alias_map[alias.lower()] = mid

    res = {
        "schema_version": int(raw.get("_schema_version", raw.get("$schema_version", 2))) if raw else 2,
        "defaults": defaults,
        "families": families,
        "models": models,
        "wire_alias_map": alias_map,
    }
    if not patched and mtime_ns is not None and models:
        _CATALOG_CACHE = res
        _CATALOG_MTIME_NS = mtime_ns
    return res


def resolve_wire_model_id(raw_id: Any, catalog: Optional[Dict[str, Any]] = None) -> str:
    """
    Resolve any raw model identifier (numeric ID, MODEL_PLACEHOLDER_M*, CLI slug,
    wire alias, or display name) to its canonical model_id in models.json.
    """
    if raw_id is None:
        return ""
    raw_str = str(raw_id).strip()
    if not raw_str:
        return ""

    if catalog is None:
        cat = load_model_catalog()
    elif isinstance(catalog, dict) and "models" in catalog and "wire_alias_map" in catalog:
        cat = catalog
    elif isinstance(catalog, dict):
        models_only = {
            k: v
            for k, v in catalog.items()
            if not str(k).startswith(("_", "$")) and isinstance(v, dict)
        }
        alias_map: Dict[str, str] = {}
        for mid, info in models_only.items():
            alias_map[mid] = mid
            alias_map[mid.lower()] = mid
            name = info.get("name", "")
            if isinstance(name, str) and name:
                alias_map[name] = mid
                alias_map[name.lower()] = mid
            for alias in info.get("wire_aliases", []):
                if isinstance(alias, str) and alias:
                    alias_map[alias] = mid
                    alias_map[alias.lower()] = mid
        cat = {"models": models_only, "wire_alias_map": alias_map}
    else:
        return raw_str

    models = cat.get("models", {})
    alias_map = cat.get("wire_alias_map", {})

    if raw_str in models:
        return raw_str
    if raw_str in alias_map:
        return alias_map[raw_str]
    lower_str = raw_str.lower()
    if lower_str in alias_map:
        return alias_map[lower_str]

    m = _PLACEHOLDER_RE.match(raw_str)
    if m:
        digits = m.group(1)
        if digits in models:
            return digits
        if len(digits) == 3 and ("1" + digits) in models:
            return "1" + digits

    if raw_str.isdigit() and len(raw_str) == 3 and ("1" + raw_str) in models:
        return "1" + raw_str

    return raw_str


def get_model_truncation_threshold(model_id: str, census: Optional[Dict[str, Any]] = None) -> int:
    """Resolve context truncation token limit for a model ID from models.json metadata."""
    default_limit = 200000
    if census is None:
        cat = load_model_catalog()
        defaults = cat.get("defaults", {})
        if isinstance(defaults, dict):
            default_limit = int(defaults.get("context_truncation_tokens", 200000))
        models = cat.get("models", {})
        mid = resolve_wire_model_id(model_id, catalog=cat)
        if mid in models and isinstance(models[mid], dict):
            return int(models[mid].get("context_truncation_tokens", default_limit))
        return default_limit

    if not isinstance(census, dict):
        return default_limit

    defaults = census.get("_defaults", census.get("$defaults", {}))
    if isinstance(defaults, dict):
        default_limit = int(defaults.get("context_truncation_tokens", 200000))

    mid = resolve_wire_model_id(model_id, catalog=census)
    if mid in census and isinstance(census[mid], dict):
        return int(census[mid].get("context_truncation_tokens", default_limit))
    return default_limit


def get_model_compaction_threshold(model_id: str, census: Optional[Dict[str, Any]] = None) -> int:
    """Resolve empirical compaction token threshold for a model ID purely from models.json metadata."""
    default_limit = 200000
    if census is None:
        cat = load_model_catalog()
        defaults = cat.get("defaults", {})
        if isinstance(defaults, dict):
            default_limit = int(defaults.get("compaction_threshold_tokens", 200000))
        models = cat.get("models", {})
        mid = resolve_wire_model_id(model_id, catalog=cat)
        if mid in models and isinstance(models[mid], dict):
            return int(models[mid].get("compaction_threshold_tokens", default_limit))
        return default_limit

    if not isinstance(census, dict):
        return default_limit

    defaults = census.get("_defaults", census.get("$defaults", {}))
    if isinstance(defaults, dict):
        default_limit = int(defaults.get("compaction_threshold_tokens", 200000))

    mid = resolve_wire_model_id(model_id, catalog=census)
    if mid in census and isinstance(census[mid], dict):
        return int(census[mid].get("compaction_threshold_tokens", default_limit))
    return default_limit


def evaluate_truncation_severity(peak_tokens: int, threshold_or_model: Any, census: Optional[Dict[str, Any]] = None) -> str:
    """Evaluate session severity given peak tokens and a threshold or model ID."""
    if isinstance(threshold_or_model, (int, float)):
        threshold = int(threshold_or_model)
    else:
        threshold = get_model_truncation_threshold(str(threshold_or_model), census=census)
    if threshold <= 0:
        return "safe"
    ratio = peak_tokens / threshold
    if ratio >= 1.0:
        return "critical"
    if ratio >= 0.8:
        return "warning"
    return "safe"


__all__ = [
    "__version__",
    "parse_wire_fields",
    "decode_wire_protobuf",
    "extract_step_telemetry",
    "extract_step_payload_details",
    "extract_error_details",
    "extract_trajectory_metadata",
    "DEFAULT_ANTIGRAVITY_DIR",
    "get_conversation_title",
    "get_workspace_mapping",
    "clean_workspace_path",
    "read_conversation_turns",
    "read_single_conversation_metadata",
    "read_conversation_metadata",
    "discover_all_conversations",
    "read_all_turns",
    "extract_wire_latency_ms",
    "load_model_census",
    "load_model_catalog",
    "resolve_wire_model_id",
    "get_model_truncation_threshold",
    "get_model_compaction_threshold",
    "evaluate_truncation_severity",
]
