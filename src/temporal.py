"""
Temporal Plan Profiles, Promotional Multipliers & Historical Provenance Engine (ADR-034).

Provides timestamp-aware resolution for:
- Date-bounded subscription plan tiers (valid_from / valid_to).
- Promotional capacity multipliers (e.g. 2-week 2x capacity overlay).
- Historical model API rate card revisions.
- Model availability and lifecycle tracking (preview, GA, sunset).
- Standard plan presets for interactive tier switching.
"""

from copy import deepcopy
import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

DEFAULT_PRICING_FILE = Path(__file__).resolve().parent.parent / "config" / "pricing.json"


def load_pricing(pricing_path: Path = DEFAULT_PRICING_FILE) -> Dict[str, Any]:
    """
    Canonical loader for model pricing definitions from config/pricing.json.
    Returns the models dictionary with default fallback if missing or unreadable.
    """
    if not pricing_path.exists():
        return {
            "default": {
                "name": "Gemini Standard",
                "family": "gemini-flash",
                "credits_per_turn": 2.5,
                "rates_per_million": {
                    "prompt_uncached": 0.75,
                    "prompt_cached": 0.075,
                    "candidate_output": 3.75,
                },
            }
        }

    try:
        data = json.loads(pricing_path.read_text(encoding="utf-8"))
        return data.get("models", {})
    except Exception:
        return {}


def load_raw_pricing(pricing_path: Path = DEFAULT_PRICING_FILE) -> Dict[str, Any]:
    """
    Canonical loader for raw full pricing configuration dictionary.
    """
    if not pricing_path.exists():
        return {}
    try:
        return json.loads(pricing_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def parse_temporal_timestamp(ts_val: Any) -> Optional[datetime.datetime]:
    """
    Parse timestamp into a timezone-aware UTC datetime.
    Supports datetime objects, ISO strings, and numeric epoch timestamps.
    """
    if ts_val is None:
        return None

    if isinstance(ts_val, datetime.datetime):
        if ts_val.tzinfo is None:
            return ts_val.replace(tzinfo=datetime.timezone.utc)
        return ts_val.astimezone(datetime.timezone.utc)

    if isinstance(ts_val, (int, float)):
        # If epoch milliseconds (> 1e11), convert to seconds
        val = float(ts_val)
        if val > 1e11:
            val = val / 1000.0
        return datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)

    if isinstance(ts_val, str):
        val = ts_val.strip()
        if not val:
            return None
        # Handle 'Z' suffix
        if val.endswith("Z"):
            val = val[:-1] + "+00:00"
        try:
            dt = datetime.datetime.fromisoformat(val)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=datetime.timezone.utc)
            return dt.astimezone(datetime.timezone.utc)
        except Exception:
            pass

    return None


def in_temporal_interval(
    target_dt: Optional[datetime.datetime],
    valid_from: Optional[Any],
    valid_to: Optional[Any],
) -> bool:
    """
    Check if target_dt falls inside [valid_from, valid_to] (inclusive).
    If valid_from is None, open on the left.
    If valid_to is None, open on the right (currently active).
    """
    if target_dt is None:
        return True

    from_dt = parse_temporal_timestamp(valid_from)
    to_dt = parse_temporal_timestamp(valid_to)

    if from_dt and target_dt < from_dt:
        return False
    if to_dt and target_dt > to_dt:
        return False

    return True


PLAN_PRESETS: List[Dict[str, Any]] = [
    {
        "tier": "free",
        "name": "Free Tier (Personal Google Account)",
        "monthly_price_gbp": 0.0,
        "monthly_price_usd": 0.0,
        "renewal_day": 1,
        "use_ai_credits": False,
        "cents_per_credit": 1.0,
        "windows": {
            "burst_hours": 5,
            "weekly_hours": 168,
        },
        "quota_limits": {
            "burst_5h_tokens": 40000000,
            "gemini_5h_capacity_usd": 5.00,
            "gemini_weekly_capacity_usd": 25.00,
            "claude_5h_capacity_usd": 0.00,
            "claude_weekly_capacity_usd": 0.00,
        },
    },
    {
        "tier": "plus_2tb",
        "name": "Google AI Plus (2 TB)",
        "monthly_price_gbp": 7.99,
        "monthly_price_usd": 9.99,
        "renewal_day": 24,
        "use_ai_credits": False,
        "cents_per_credit": 1.0,
        "windows": {
            "burst_hours": 5,
            "weekly_hours": 168,
        },
        "quota_limits": {
            "burst_5h_tokens": 80000000,
            "gemini_5h_capacity_usd": 10.00,
            "gemini_weekly_capacity_usd": 65.00,
            "claude_5h_capacity_usd": 0.00,
            "claude_weekly_capacity_usd": 0.00,
        },
    },
    {
        "tier": "pro",
        "name": "Google AI Pro (2 TB)",
        "monthly_price_gbp": 18.99,
        "monthly_price_usd": 19.99,
        "renewal_day": 24,
        "weekly_reset_day": "Thursday",
        "weekly_reset_time_utc": "18:00:00",
        "use_ai_credits": False,
        "cents_per_credit": 1.0,
        "windows": {
            "burst_hours": 5,
            "weekly_hours": 168,
        },
        "quota_limits": {
            "burst_5h_tokens": 168000000,
            "gemini_5h_capacity_usd": 20.00,
            "gemini_weekly_capacity_usd": 129.00,
            "claude_5h_capacity_usd": 10.00,
            "claude_weekly_capacity_usd": 35.00,
        },
    },
    {
        "tier": "pro_5tb",
        "name": "Google AI Pro (5 TB)",
        "monthly_price_gbp": 29.99,
        "monthly_price_usd": 34.99,
        "renewal_day": 24,
        "use_ai_credits": False,
        "cents_per_credit": 1.0,
        "windows": {
            "burst_hours": 5,
            "weekly_hours": 168,
        },
        "quota_limits": {
            "burst_5h_tokens": 168000000,
            "gemini_5h_capacity_usd": 20.00,
            "gemini_weekly_capacity_usd": 129.00,
            "claude_5h_capacity_usd": 10.00,
            "claude_weekly_capacity_usd": 35.00,
        },
    },
    {
        "tier": "pro_10tb",
        "name": "Google AI Pro (10 TB)",
        "monthly_price_gbp": 39.99,
        "monthly_price_usd": 49.99,
        "renewal_day": 24,
        "use_ai_credits": False,
        "cents_per_credit": 1.0,
        "windows": {
            "burst_hours": 5,
            "weekly_hours": 168,
        },
        "quota_limits": {
            "burst_5h_tokens": 168000000,
            "gemini_5h_capacity_usd": 20.00,
            "gemini_weekly_capacity_usd": 129.00,
            "claude_5h_capacity_usd": 10.00,
            "claude_weekly_capacity_usd": 35.00,
        },
    },
    {
        "tier": "ultra_5x",
        "aliases": ["enterprise_5x", "ultra"],
        "name": "Google AI Ultra (20 TB - 5x AI Usage)",
        "monthly_price_gbp": 79.99,
        "monthly_price_usd": 99.99,
        "renewal_day": 13,
        "weekly_reset_day": "Sunday",
        "weekly_reset_time_utc": "17:58:04",
        "use_ai_credits": False,
        "cents_per_credit": 1.0,
        "windows": {
            "burst_hours": 5,
            "weekly_hours": 168,
        },
        "quota_limits": {
            "burst_5h_tokens": 840000000,
            "gemini_5h_capacity_usd": 100.00,
            "gemini_weekly_capacity_usd": 645.00,
            "claude_5h_capacity_usd": 50.00,
            "claude_weekly_capacity_usd": 175.00,
        },
    },
    {
        "tier": "enterprise_5x",
        "name": "Google AI Ultra / Enterprise 5x",
        "monthly_price_gbp": 79.99,
        "monthly_price_usd": 99.99,
        "renewal_day": 13,
        "weekly_reset_day": "Sunday",
        "weekly_reset_time_utc": "17:58:04",
        "use_ai_credits": False,
        "cents_per_credit": 1.0,
        "windows": {
            "burst_hours": 5,
            "weekly_hours": 168,
        },
        "quota_limits": {
            "burst_5h_tokens": 840000000,
            "gemini_5h_capacity_usd": 100.00,
            "gemini_weekly_capacity_usd": 645.00,
            "claude_5h_capacity_usd": 50.00,
            "claude_weekly_capacity_usd": 175.00,
        },
    },
    {
        "tier": "ultra_20x",
        "aliases": ["ultra_30tb", "ultra_max"],
        "name": "Google AI Ultra (30 TB - 20x AI Usage)",
        "monthly_price_gbp": 189.99,
        "monthly_price_usd": 239.99,
        "renewal_day": 24,
        "use_ai_credits": False,
        "cents_per_credit": 1.0,
        "windows": {
            "burst_hours": 5,
            "weekly_hours": 168,
        },
        "quota_limits": {
            "burst_5h_tokens": 3360000000,
            "gemini_5h_capacity_usd": 400.00,
            "gemini_weekly_capacity_usd": 2580.00,
            "claude_5h_capacity_usd": 200.00,
            "claude_weekly_capacity_usd": 700.00,
        },
    },
    {
        "tier": "ultra_10x",
        "name": "Antigravity Ultra (10x Capacity)",
        "monthly_price_gbp": 99.99,
        "monthly_price_usd": 119.99,
        "renewal_day": 24,
        "use_ai_credits": False,
        "cents_per_credit": 1.0,
        "windows": {
            "burst_hours": 5,
            "weekly_hours": 168,
        },
        "quota_limits": {
            "burst_5h_tokens": 1680000000,
            "gemini_5h_capacity_usd": 200.00,
            "gemini_weekly_capacity_usd": 1290.00,
            "claude_5h_capacity_usd": 100.00,
            "claude_weekly_capacity_usd": 350.00,
        },
    },
    {
        "tier": "custom",
        "name": "Custom Capacity Plan",
        "monthly_price_gbp": 0.0,
        "monthly_price_usd": 0.0,
        "renewal_day": 1,
        "use_ai_credits": False,
        "cents_per_credit": 1.0,
        "windows": {
            "burst_hours": 5,
            "weekly_hours": 168,
        },
        "quota_limits": {
            "burst_5h_tokens": 200000000,
            "gemini_5h_capacity_usd": 25.00,
            "gemini_weekly_capacity_usd": 150.00,
            "claude_5h_capacity_usd": 15.00,
            "claude_weekly_capacity_usd": 50.00,
        },
    },
]


def get_plan_preset(tier_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve a plan preset dictionary by tier name or alias."""
    target = tier_name.lower().strip()
    for preset in PLAN_PRESETS:
        if preset.get("tier") == target:
            return deepcopy(preset)
        if target in preset.get("aliases", []):
            return deepcopy(preset)
    return None


class TemporalPricingResolver:
    """
    Deterministic historical provenance and temporal pricing resolver.
    """

    def __init__(
        self,
        config_or_path: Optional[Union[Dict[str, Any], Path, str]] = None,
    ) -> None:
        if config_or_path is None:
            config_or_path = DEFAULT_PRICING_FILE

        if isinstance(config_or_path, (Path, str)):
            p = Path(config_or_path)
            if p.exists():
                try:
                    self.config = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    self.config = {}
            else:
                self.config = {}
        elif isinstance(config_or_path, dict):
            self.config = deepcopy(config_or_path)
        else:
            self.config = {}

        self.models: Dict[str, Any] = self.config.get("models", {})
        self.subscription: Dict[str, Any] = self.config.get("subscription", {
            "tier": "pro",
            "name": "Google One AI Premium (Antigravity Pro)",
            "monthly_price_gbp": 18.99,
            "monthly_price_usd": 19.99,
            "renewal_day": 24,
            "use_ai_credits": False,
            "cents_per_credit": 1.0,
            "windows": {"burst_hours": 5, "weekly_hours": 168},
            "quota_limits": {
                "burst_5h_tokens": 168000000,
                "gemini_5h_capacity_usd": 20.00,
                "gemini_weekly_capacity_usd": 129.00,
                "claude_5h_capacity_usd": 10.00,
                "claude_weekly_capacity_usd": 35.00,
            },
        })
        self.subscription_history: List[Dict[str, Any]] = self.config.get("subscription_history", [])
        self.promotions: List[Dict[str, Any]] = self.config.get("promotions", [])
        self.rate_history: Dict[str, List[Dict[str, Any]]] = self.config.get("rate_history", {})
        self.availability: Dict[str, Dict[str, Any]] = self.config.get("availability", {})

    def resolve_rates(
        self,
        model_id: Any,
        timestamp: Optional[Union[str, datetime.datetime, int, float]] = None,
    ) -> Dict[str, float]:
        """
        Resolve exact active rate card for a given model ID at a specific timestamp.
        Falls back to current static model rates if not matched or timestamp is None.
        """
        mid = str(model_id) if model_id is not None else "default"
        target_dt = parse_temporal_timestamp(timestamp)

        # 1. Try date-bounded rate revisions in rate_history
        if target_dt is not None and mid in self.rate_history:
            for rev in self.rate_history[mid]:
                if in_temporal_interval(target_dt, rev.get("valid_from"), rev.get("valid_to")):
                    if "rates_per_million" in rev:
                        return deepcopy(rev["rates_per_million"])

        # 2. Try static model rates
        if mid in self.models and "rates_per_million" in self.models[mid]:
            return deepcopy(self.models[mid]["rates_per_million"])

        # 3. Try default model rates
        default_cfg = self.models.get("default", {})
        return deepcopy(default_cfg.get("rates_per_million", {
            "prompt_uncached": 0.10,
            "prompt_cached": 0.025,
            "candidate_output": 0.40,
        }))

    def resolve_subscription(
        self,
        timestamp: Optional[Union[str, datetime.datetime, int, float]] = None,
    ) -> Dict[str, Any]:
        """
        Resolve active subscription tier and quota parameters at a specific timestamp.
        Falls back to current static subscription config if not matched or timestamp is None.
        """
        target_dt = parse_temporal_timestamp(timestamp)

        if target_dt is not None and self.subscription_history:
            for entry in self.subscription_history:
                if in_temporal_interval(target_dt, entry.get("valid_from"), entry.get("valid_to")):
                    return deepcopy(entry)

        return deepcopy(self.subscription)

    def resolve_promotions(
        self,
        timestamp: Optional[Union[str, datetime.datetime, int, float]] = None,
        provider: str = "all",
    ) -> List[Dict[str, Any]]:
        """
        Return all promotional capacity overlays active at a specific timestamp.
        Optionally filter by target provider ('gemini', 'claude_gpt', or 'all').
        """
        target_dt = parse_temporal_timestamp(timestamp)
        if target_dt is None:
            return []

        active = []
        for promo in self.promotions:
            if in_temporal_interval(target_dt, promo.get("valid_from"), promo.get("valid_to")):
                p_tgt = promo.get("target_provider", "all").lower()
                if provider == "all" or p_tgt == "all" or p_tgt == provider.lower():
                    active.append(deepcopy(promo))

        return active

    def get_capacity_multiplier(
        self,
        timestamp: Optional[Union[str, datetime.datetime, int, float]] = None,
        provider: str = "gemini",
    ) -> float:
        """
        Calculate combined capacity multiplier from all active promotions.
        """
        active_promos = self.resolve_promotions(timestamp=timestamp, provider=provider)
        if not active_promos:
            return 1.0

        multiplier = 1.0
        for promo in active_promos:
            m = float(promo.get("multiplier", 1.0))
            if m > 0:
                multiplier *= m

        return round(multiplier, 4)

    def resolve_model_status(
        self,
        model_id: Any,
        timestamp: Optional[Union[str, datetime.datetime, int, float]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate lifecycle availability status of a model at a timestamp:
        'preview', 'ga', 'deprecated', 'sunset', or 'unknown'.
        """
        mid = str(model_id) if model_id is not None else ""
        target_dt = parse_temporal_timestamp(timestamp)

        info = self.availability.get(mid, {})
        preview_from = info.get("preview_from")
        ga_from = info.get("ga_from")
        sunset_at = info.get("sunset_at")
        base_status = info.get("status", "ga")

        if target_dt is None:
            return {
                "model_id": mid,
                "status": base_status,
                "preview_from": preview_from,
                "ga_from": ga_from,
                "sunset_at": sunset_at,
            }

        status = base_status
        if sunset_at and target_dt >= parse_temporal_timestamp(sunset_at):
            status = "sunset"
        elif ga_from and target_dt >= parse_temporal_timestamp(ga_from):
            status = "ga"
        elif preview_from and target_dt >= parse_temporal_timestamp(preview_from):
            status = "preview"

        return {
            "model_id": mid,
            "status": status,
            "preview_from": preview_from,
            "ga_from": ga_from,
            "sunset_at": sunset_at,
        }

    def get_plan_presets(self) -> List[Dict[str, Any]]:
        """Return available plan tier presets for switching."""
        return deepcopy(PLAN_PRESETS)

    def get_provenance_summary(
        self,
        timestamp: Optional[Union[str, datetime.datetime, int, float]] = None,
    ) -> Dict[str, Any]:
        """
        Return structured provenance payload for embedding in dashboard and exports.
        """
        target_dt = parse_temporal_timestamp(timestamp) or datetime.datetime.now(datetime.timezone.utc)
        sub = self.resolve_subscription(target_dt)
        promos = self.resolve_promotions(target_dt, provider="all")
        gemini_mult = self.get_capacity_multiplier(target_dt, provider="gemini")
        claude_mult = self.get_capacity_multiplier(target_dt, provider="claude_gpt")

        return {
            "resolved_at_utc": target_dt.isoformat(),
            "active_plan": sub,
            "active_promotions": promos,
            "capacity_multipliers": {
                "gemini": gemini_mult,
                "claude_gpt": claude_mult,
            },
            "subscription_history": deepcopy(self.subscription_history),
            "promotions_catalog": deepcopy(self.promotions),
            "rate_history": deepcopy(self.rate_history),
            "availability": deepcopy(self.availability),
            "plan_presets": self.get_plan_presets(),
            "models": deepcopy(self.config.get("models", {})),
        }


_DEFAULT_RESOLVER: Optional[TemporalPricingResolver] = None


def get_temporal_resolver(
    config_or_path: Optional[Union[Dict[str, Any], Path, str]] = None,
    reload: bool = False,
) -> TemporalPricingResolver:
    """Factory to retrieve cached or new TemporalPricingResolver instance."""
    global _DEFAULT_RESOLVER
    if reload or _DEFAULT_RESOLVER is None or config_or_path is not None:
        resolver = TemporalPricingResolver(config_or_path)
        if config_or_path is None and not reload:
            _DEFAULT_RESOLVER = resolver
        return resolver
    return _DEFAULT_RESOLVER
