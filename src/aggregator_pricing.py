"""
Pricing models, credit calculations, subagent classification, and timestamp parsing.
"""

from collections import Counter, defaultdict
import datetime
import functools
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from antigravity_telemetry import (
    load_model_catalog,
    load_model_census,
    resolve_wire_model_id,
)
from src.temporal import (
    DEFAULT_PRICING_FILE,
    TemporalPricingResolver,
    get_temporal_resolver,
    load_pricing,
    load_raw_pricing,
    parse_temporal_timestamp,
)

DEFAULT_SUBSCRIPTION_FILE = DEFAULT_PRICING_FILE


def _derive_subagent_model_ids() -> Set[str]:
    base: Set[str] = {'1050', '1322', '1132', '1301', '1198'}
    try:
        catalog = load_model_catalog()
        for mid, meta in catalog.get("models", {}).items():
            if isinstance(meta, dict) and meta.get("is_subagent"):
                base.add(str(mid))
    except Exception:
        pass
    return base


# Autonomous subagent model IDs (routed independently from desktop selector)
SUBAGENT_MODEL_IDS: Set[str] = _derive_subagent_model_ids()


def load_subscription_config(
    pricing_path: Path = DEFAULT_PRICING_FILE,
    timestamp: Optional[Any] = None,
) -> Dict[str, Any]:
    """Load subscription settings from config, resolving temporal intervals if timestamp is provided."""
    try:
        resolver = get_temporal_resolver(config_or_path=pricing_path)
        if timestamp is not None:
            return resolver.resolve_subscription(timestamp)
    except (KeyError, ValueError, OSError):
        pass

    if not pricing_path.exists():
        return {"tier": "pro", "use_ai_credits": True, "windows": {"burst_hours": 5, "weekly_hours": 168}}

    try:
        data = json.loads(pricing_path.read_text(encoding="utf-8"))
        return data.get("subscription", {
            "tier": "pro",
            "use_ai_credits": True,
            "windows": {"burst_hours": 5, "weekly_hours": 168},
        })
    except (OSError, json.JSONDecodeError):
        return {"tier": "pro", "use_ai_credits": True, "windows": {"burst_hours": 5, "weekly_hours": 168}}


def load_currency_config(pricing_path: Path = DEFAULT_PRICING_FILE) -> Dict[str, Any]:
    """Load currency rates and credit pack configuration."""
    default_cfg = {
        "default": "GBP",
        "supported": ["GBP", "USD"],
        "usd_to_gbp_fx_rate": 0.79,
        "credit_pack": {
            "credits": 2500,
            "price_gbp": 23.99,
            "price_usd": 25.00,
            "pence_per_credit": 0.9596,
            "cents_per_credit": 1.0,
            "cost_per_credit_gbp": 0.009596,
            "cost_per_credit_usd": 0.010000,
        },
    }
    if not pricing_path.exists():
        return default_cfg

    try:
        data = json.loads(pricing_path.read_text(encoding="utf-8"))
        return data.get("currency", default_cfg)
    except (OSError, json.JSONDecodeError):
        return default_cfg


def get_model_rates(
    model_id: Any,
    pricing_models: Optional[Dict[str, Any]] = None,
    timestamp: Optional[Any] = None,
) -> Dict[str, float]:
    """Resolve rate table for a model ID with fallback, supporting temporal rate history."""
    raw_mid = str(model_id) if model_id is not None else "default"
    mid = resolve_wire_model_id(raw_mid) if raw_mid != "default" else "default"
    if timestamp is not None:
        try:
            resolver = get_temporal_resolver()
            return resolver.resolve_rates(mid, timestamp=timestamp)
        except (KeyError, ValueError, OSError):
            pass

    if pricing_models is None:
        pricing_models = load_pricing()

    for candidate in (mid, raw_mid):
        if pricing_models and candidate in pricing_models:
            rates = pricing_models[candidate].get("rates_per_million", {})
            if rates:
                return rates

    default_cfg = pricing_models.get("default", {}) if pricing_models else {}
    return default_cfg.get("rates_per_million", {
        "prompt_uncached": 0.10,
        "prompt_cached": 0.025,
        "candidate_output": 0.40,
    })


def get_model_quota_weights(
    model_id: Any,
    pricing_models: Optional[Dict[str, Any]] = None,
    timestamp: Optional[Any] = None,
) -> Dict[str, float]:
    """
    Resolve calibrated quota burn weights (quota_weights_per_million) for a model ID,
    falling back to retail rates (rates_per_million) when unset (ADR-095).
    """
    raw_mid = str(model_id) if model_id is not None else "default"
    mid = resolve_wire_model_id(raw_mid) if raw_mid != "default" else "default"
    if timestamp is not None:
        try:
            resolver = get_temporal_resolver()
            if pricing_models is None:
                return resolver.resolve_quota_weights(mid, timestamp=timestamp)
        except (KeyError, ValueError, OSError):
            pass

    if pricing_models is None:
        pricing_models = load_pricing()

    for candidate in (mid, raw_mid):
        if pricing_models and candidate in pricing_models:
            weights = pricing_models[candidate].get("quota_weights_per_million")
            if weights:
                return weights
            rates = pricing_models[candidate].get("rates_per_million", {})
            if rates:
                return rates

    return get_model_rates(mid, pricing_models=pricing_models, timestamp=timestamp)


def get_model_display_name(model_id: str, pricing_models: Dict[str, Any]) -> str:
    """Get human-readable model name, falling back to canonical model census."""
    resolved = resolve_wire_model_id(model_id)
    for candidate in (model_id, resolved):
        if pricing_models and candidate in pricing_models:
            return pricing_models[candidate].get("name", f"Model {candidate}")
    census = load_model_census()
    for candidate in (model_id, resolved):
        if candidate in census:
            return census[candidate].get("name", f"Model {candidate}")
    return f"Model {model_id}"


def get_provider_quota_track(
    model_id: Any,
    pricing_models: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Classify model ID into its independent provider quota silo (ADR-019).
    Dynamic routing:
      - Catalog track_id if present in antigravity_telemetry/models.json
      - 'claude*' or 'gpt*' (including 'gpt-oss') -> 'claude_gpt'
      - All other models (gemini-flash, gemini-pro, gemini-flash-lite, default) -> 'gemini'
    """
    mid = str(model_id) if model_id is not None else ""
    resolved = resolve_wire_model_id(mid) if mid else ""
    try:
        catalog_models = load_model_catalog().get("models", {})
        for candidate in (mid, resolved):
            if candidate in catalog_models and isinstance(catalog_models[candidate], dict):
                track_id = catalog_models[candidate].get("track_id")
                if track_id:
                    return str(track_id)
    except Exception:
        pass

    if pricing_models is None:
        pricing_models = load_pricing()

    family = ""
    for candidate in (mid, resolved):
        if pricing_models and candidate in pricing_models:
            family = str(pricing_models[candidate].get("family", "")).lower()
            if family:
                break

    # Dynamic family routing
    if family.startswith("claude") or family.startswith("gpt"):
        return "claude_gpt"

    # Fallback to model_id inspection if unmapped in pricing_models
    mid_lower = mid.lower()
    if mid_lower.startswith("claude") or mid_lower.startswith("gpt"):
        return "claude_gpt"

    return "gemini"


def compute_turn_cost(
    turn: Dict[str, Any],
    rates: Optional[Dict[str, float]] = None,
    timestamp: Optional[Any] = None,
    pricing_models: Optional[Dict[str, Any]] = None,
) -> float:
    """Calculate estimated cost (imputed value) for a single turn in USD, with temporal rate card support."""
    if rates is None:
        ts = timestamp or turn.get("timestamp")
        mid = str(turn.get("model_id", "default"))
        rates = get_model_rates(mid, pricing_models or {}, timestamp=ts)

    p_uncached = rates.get("prompt_uncached", 0.10)
    p_cached = rates.get("prompt_cached", 0.025)
    p_output = rates.get("candidate_output", 0.40)

    cost = (
        (turn.get("prompt_tokens_uncached", 0) / 1e6 * p_uncached)
        + (turn.get("cached_tokens", 0) / 1e6 * p_cached)
        + (turn.get("output_tokens_total", 0) / 1e6 * p_output)
    )
    return round(cost, 6)


def calculate_credit_burn(
    model_id: str,
    turns_count: int = 1,
    pricing_models: Optional[Dict[str, Any]] = None,
    cents_per_credit: float = 1.0,
    cost_per_credit_gbp: float = 0.009596,
) -> Dict[str, Any]:
    """
    Calculate AI credit burn, USD equivalent, and GBP equivalent for a given model and turn count.
    Uses model-specific credits_per_turn rate from pricing configuration.
    """
    if pricing_models is None:
        pricing_models = load_pricing()

    rate = 2.5
    mid = str(model_id)
    if mid in pricing_models:
        rate = pricing_models[mid].get("credits_per_turn", 2.5)
    elif "default" in pricing_models:
        rate = pricing_models["default"].get("credits_per_turn", 2.5)

    credits = rate * turns_count
    usd = (credits * cents_per_credit) / 100.0
    gbp = credits * cost_per_credit_gbp
    return {
        "model_id": mid,
        "turns_count": turns_count,
        "credits_per_turn": rate,
        "credits": round(credits, 4),
        "credit_burn_usd": round(usd, 4),
        "credit_burn_gbp": round(gbp, 4),
    }


def classify_turn_type(
    turn: Dict[str, Any],
    pricing_models: Optional[Dict[str, Any]] = None,
    convo_subagent_map: Optional[Dict[str, bool]] = None,
) -> str:
    """
    Classify a turn as 'interactive' or 'subagent' based on:
    1. Explicit turn['is_subagent'] flag (populated from conversations_archive / v_turns),
    2. Optional convo_subagent_map[convo_id] lookup (supports inherit/Carbon/Argon subagents & /swarm workers),
    3. Autonomous subagent model IDs in antigravity_telemetry/models.json (SUBAGENT_MODEL_IDS).
    """
    if bool(turn.get('is_subagent')):
        return 'subagent'
    cid = str(turn.get('convo_id') or '')
    if cid:
        if convo_subagent_map and bool(convo_subagent_map.get(cid)):
            return 'subagent'
        if isinstance(pricing_models, dict) and cid in pricing_models and isinstance(pricing_models[cid], bool):
            if pricing_models[cid]:
                return 'subagent'
    mid = resolve_wire_model_id(turn.get('model_id', 'unknown'))
    if mid in SUBAGENT_MODEL_IDS:
        return 'subagent'
    return 'interactive'


def compute_subagent_metrics(
    flat_turns: List[Dict[str, Any]],
    pricing_models: Optional[Dict[str, Any]] = None,
    convo_subagent_map: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """Compute aggregate metrics partitioned into interactive vs subagent turns."""
    if pricing_models is None:
        pricing_models = {}
    interactive = []
    subagent = []
    for t in flat_turns:
        if classify_turn_type(t, pricing_models, convo_subagent_map=convo_subagent_map) == 'subagent':
            subagent.append(t)
        else:
            interactive.append(t)

    def _agg(turns_list):
        total_tokens = sum(
            t.get('prompt_tokens_uncached', 0) + t.get('cached_tokens', 0) + t.get('output_tokens_total', 0)
            for t in turns_list
        )
        total_cost = 0.0
        for t in turns_list:
            mid = str(t.get('model_id', 'unknown'))
            rates = get_model_rates(mid, pricing_models, timestamp=t.get('timestamp'))
            total_cost += compute_turn_cost(t, rates)
        return {
            'turn_count': len(turns_list),
            'total_tokens': total_tokens,
            'imputed_cost_usd': round(total_cost, 4),
        }

    i_m = _agg(interactive)
    s_m = _agg(subagent)
    total_cost = i_m['imputed_cost_usd'] + s_m['imputed_cost_usd']
    s_m['quota_share_pct'] = round((s_m['imputed_cost_usd'] / total_cost * 100.0) if total_cost > 0 else 0.0, 1)
    i_m['quota_share_pct'] = round(100.0 - s_m['quota_share_pct'], 1)

    return {'interactive': i_m, 'subagent': s_m}


@functools.lru_cache(maxsize=262144)
def _parse_ts_str(cleaned: str) -> Optional[datetime.datetime]:
    try:
        dt = datetime.datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt
    except Exception:
        return None


def parse_timestamp(ts_val: Any) -> Optional[datetime.datetime]:
    """Parse ISO timestamp string or epoch number into datetime in UTC."""
    if not ts_val:
        return None
    if isinstance(ts_val, datetime.datetime):
        if ts_val.tzinfo is datetime.timezone.utc:
            return ts_val
        if ts_val.tzinfo is None:
            return ts_val.replace(tzinfo=datetime.timezone.utc)
        return ts_val.astimezone(datetime.timezone.utc)
    if isinstance(ts_val, str):
        cleaned = ts_val.replace("Z", "+00:00") if ts_val.endswith("Z") else ts_val
        return _parse_ts_str(cleaned)
    if isinstance(ts_val, (int, float)):
        return datetime.datetime.fromtimestamp(ts_val, tz=datetime.timezone.utc)
    return None
