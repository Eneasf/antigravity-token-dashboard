"""
Analytics and aggregation engine for Antigravity token telemetry.

Computes session totals, cache efficiencies, model-by-model allowances,
rolling 5-hour/1-week windows, recovery schedules, and dual-track cost models.
"""

from collections import defaultdict, Counter
import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from src.temporal import (
    DEFAULT_PRICING_FILE,
    TemporalPricingResolver,
    get_temporal_resolver,
    load_pricing,
    load_raw_pricing,
    parse_temporal_timestamp,
)
from antigravity_telemetry import load_model_census
from src.simulator import (
    compare_plan_tiers,
    get_archetype_presets,
    simulate_archetype,
    simulate_workload,
)
from src.git_timeline import resolve_turn_branch



def load_subscription_config(
    pricing_path: Path = DEFAULT_PRICING_FILE,
    timestamp: Optional[Any] = None,
) -> Dict[str, Any]:
    """Load subscription settings from config, resolving temporal intervals if timestamp is provided."""
    try:
        resolver = get_temporal_resolver(config_or_path=pricing_path)
        if timestamp is not None:
            return resolver.resolve_subscription(timestamp)
    except Exception:
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
    except Exception:
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
    except Exception:
        return default_cfg


def get_model_rates(
    model_id: str,
    pricing_models: Dict[str, Any],
    timestamp: Optional[Any] = None,
) -> Dict[str, float]:
    """Resolve rate table for a model ID with fallback, supporting temporal rate history."""
    if timestamp is not None:
        try:
            resolver = get_temporal_resolver()
            return resolver.resolve_rates(model_id, timestamp=timestamp)
        except Exception:
            pass

    if model_id in pricing_models:
        return pricing_models[model_id].get("rates_per_million", {})

    default_cfg = pricing_models.get("default", {})
    return default_cfg.get("rates_per_million", {
        "prompt_uncached": 0.10,
        "prompt_cached": 0.025,
        "candidate_output": 0.40,
    })


def get_model_display_name(model_id: str, pricing_models: Dict[str, Any]) -> str:
    """Get human-readable model name, falling back to canonical model census."""
    if pricing_models and model_id in pricing_models:
        return pricing_models[model_id].get("name", f"Model {model_id}")
    census = load_model_census()
    if model_id in census:
        return census[model_id].get("name", f"Model {model_id}")
    return f"Model {model_id}"


def get_provider_quota_track(
    model_id: Any,
    pricing_models: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Classify model ID into its independent provider quota silo (ADR-019).
    Dynamic routing:
      - 'claude*' or 'gpt*' (including 'gpt-oss') -> 'claude_gpt'
      - All other models (gemini-flash, gemini-pro, gemini-flash-lite, default) -> 'gemini'
    """
    if pricing_models is None:
        pricing_models = load_pricing()

    mid = str(model_id) if model_id is not None else ""
    family = ""
    if mid in pricing_models:
        family = str(pricing_models[mid].get("family", "")).lower()

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


# Autonomous subagent model IDs (routed independently from desktop selector)
SUBAGENT_MODEL_IDS = {'1050', '1322', '1132', '1301'}


def classify_turn_type(turn: Dict[str, Any], pricing_models: Optional[Dict[str, Any]] = None) -> str:
    """Classify a turn as 'interactive' or 'subagent' based on model ID."""
    mid = str(turn.get('model_id', 'unknown'))
    if mid in SUBAGENT_MODEL_IDS:
        return 'subagent'
    return 'interactive'


def compute_subagent_metrics(flat_turns: List[Dict[str, Any]], pricing_models: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compute aggregate metrics partitioned into interactive vs subagent turns."""
    if pricing_models is None:
        pricing_models = {}
    interactive = []
    subagent = []
    for t in flat_turns:
        if classify_turn_type(t, pricing_models) == 'subagent':
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


def parse_timestamp(ts_val: Any) -> Optional[datetime.datetime]:
    """Parse ISO timestamp string or epoch number into datetime in UTC."""
    if not ts_val:
        return None
    if isinstance(ts_val, (int, float)):
        return datetime.datetime.fromtimestamp(ts_val, tz=datetime.timezone.utc)
    if isinstance(ts_val, str):
        try:
            cleaned = ts_val.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            return dt
        except Exception:
            return None
    return None


WEEKDAY_MAP: Dict[str, int] = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def get_weekly_cycle_bounds(
    reference_time: Optional[datetime.datetime] = None,
    reset_weekday: Optional[int] = None,
    reset_time_utc: Optional[str] = None,
    explicit_reset_dt: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    """
    Calculate weekly quota reset cycle bounds.
    Dynamically resolves reset day and time from temporal subscription profile
    (Thursday 18:00 UTC for Pro, Sunday 17:58:04 UTC for Ultra 5x), or respects
    explicit live desktop quota reset timestamp.
    """
    ref = reference_time or datetime.datetime.now(datetime.timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=datetime.timezone.utc)
    else:
        ref = ref.astimezone(datetime.timezone.utc)

    if explicit_reset_dt is not None:
        next_reset = explicit_reset_dt
        if next_reset.tzinfo is None:
            next_reset = next_reset.replace(tzinfo=datetime.timezone.utc)
        else:
            next_reset = next_reset.astimezone(datetime.timezone.utc)
        candidate_start = next_reset - datetime.timedelta(days=7)
        day_name = next_reset.strftime("%A")
        time_str = next_reset.strftime("%H:%M:%S UTC")
    else:
        target_weekday = reset_weekday
        target_time_str = reset_time_utc

        if target_weekday is None or target_time_str is None:
            try:
                from src.temporal import get_temporal_resolver
                resolver = get_temporal_resolver()
                sub_cfg = resolver.resolve_subscription(ref)
                if target_weekday is None:
                    day_str = str(sub_cfg.get("weekly_reset_day", "Thursday")).lower()
                    target_weekday = WEEKDAY_MAP.get(day_str, 3)
                if target_time_str is None:
                    target_time_str = str(sub_cfg.get("weekly_reset_time_utc", "18:00:00"))
            except Exception:
                if target_weekday is None:
                    target_weekday = 3
                if target_time_str is None:
                    target_time_str = "18:00:00"

        h, m, s = 18, 0, 0
        try:
            parts = [int(p) for p in target_time_str.split(":")[:3]]
            if len(parts) >= 1:
                h = parts[0]
            if len(parts) >= 2:
                m = parts[1]
            if len(parts) >= 3:
                s = parts[2]
        except Exception:
            h, m, s = 18, 0, 0

        days_since = (ref.weekday() - target_weekday) % 7
        candidate_start = (ref - datetime.timedelta(days=days_since)).replace(
            hour=h, minute=m, second=s, microsecond=0
        )
        if candidate_start > ref:
            candidate_start -= datetime.timedelta(days=7)

        next_reset = candidate_start + datetime.timedelta(days=7)
        inv_map = {v: k.capitalize() for k, v in WEEKDAY_MAP.items()}
        day_name = inv_map.get(target_weekday, "Thursday")
        time_str = f"{h:02d}:{m:02d}:{s:02d} UTC"

    diff = next_reset - ref
    total_sec = max(0, int(diff.total_seconds()))
    days = total_sec // 86400
    hours = (total_sec % 86400) // 3600
    minutes = (total_sec % 3600) // 60

    d_txt = f"{days} day" if days == 1 else f"{days} days"
    h_txt = f"{hours} hour" if hours == 1 else f"{hours} hours"
    m_txt = f"{minutes} min" if minutes == 1 else f"{minutes} mins"
    human_rem = f"{d_txt}, {h_txt}" if days > 0 else f"{h_txt}, {m_txt}"

    return {
        "cycle_start_utc": candidate_start.isoformat(),
        "cycle_end_utc": next_reset.isoformat(),
        "weekly_reset_utc": next_reset.isoformat(),
        "reset_day_name": day_name,
        "reset_time_utc": time_str,
        "reset_display": f"{day_name}, {next_reset.strftime('%d %b %Y, %H:%M UTC')}",
        "days_remaining": days,
        "hours_remaining": hours,
        "minutes_remaining": minutes,
        "human_remaining": human_rem,
    }


def get_monthly_billing_bounds(
    reference_time: Optional[datetime.datetime] = None,
    billing_day: int = 24,
    monthly_credits: int = 2500,
    plan_price_gbp: float = 18.99,
    plan_price_usd: float = 19.99,
) -> Dict[str, Any]:
    """
    Calculate Google One monthly billing renewal horizon (anchored to the 24th of each month).
    """
    ref = reference_time or datetime.datetime.now(datetime.timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=datetime.timezone.utc)
    else:
        ref = ref.astimezone(datetime.timezone.utc)

    y = ref.year
    m = ref.month

    # Renewal point at 18:00 UTC on billing_day
    renewal = datetime.datetime(y, m, billing_day, 18, 0, 0, tzinfo=datetime.timezone.utc)
    if ref < renewal:
        next_renewal = renewal
        prev_m = 12 if m == 1 else m - 1
        prev_y = y - 1 if m == 1 else y
        prev_renewal = datetime.datetime(prev_y, prev_m, billing_day, 18, 0, 0, tzinfo=datetime.timezone.utc)
    else:
        prev_renewal = renewal
        next_m = 1 if m == 12 else m + 1
        next_y = y + 1 if m == 1 else y
        next_renewal = datetime.datetime(next_y, next_m, billing_day, 18, 0, 0, tzinfo=datetime.timezone.utc)

    diff = next_renewal - ref
    days = diff.days
    hours = diff.seconds // 3600

    d_txt = f"{days} day" if days == 1 else f"{days} days"
    h_txt = f"{hours} hour" if hours == 1 else f"{hours} hours"
    human_rem = f"{d_txt}, {h_txt}" if days > 0 else f"{h_txt}"

    return {
        "billing_day": billing_day,
        "cycle_start_utc": prev_renewal.isoformat(),
        "renewal_date": next_renewal.isoformat(),
        "renewal_display": next_renewal.strftime("%d %b %Y, %H:%M UTC"),
        "days_remaining": days,
        "hours_remaining": hours,
        "human_remaining": human_rem,
        "monthly_credit_allowance": monthly_credits,
        "monthly_plan_price_gbp": plan_price_gbp,
        "monthly_plan_price_usd": plan_price_usd,
    }


def compute_exhaustion_alarm_state(
    gemini_weekly_used_pct: float,
    gemini_weekly_remaining_pct: float,
    gemini_5h_used_pct: float,
    cg_weekly_remaining_pct: float,
    weekly_cycle_bounds: Dict[str, Any],
    gemini_weekly_capacity_usd: float = 129.00,
) -> Dict[str, Any]:
    """Detect weekly exhaustion state and compute alarm/fallback flags (ADR-028)."""
    gemini_weekly_exhausted = gemini_weekly_remaining_pct <= 0.1  # Effectively 0%
    gemini_5h_disabled = gemini_weekly_exhausted  # 5h burst is subsumed by weekly
    claude_fallback_ready = cg_weekly_remaining_pct > 50.0 and gemini_weekly_exhausted

    # Reset countdown
    reset_utc = weekly_cycle_bounds.get('cycle_end_utc', '')
    reset_human = weekly_cycle_bounds.get('human_remaining', '')

    return {
        'gemini_weekly_exhausted': gemini_weekly_exhausted,
        'gemini_5h_disabled': gemini_5h_disabled,
        'claude_fallback_ready': claude_fallback_ready,
        'reset_countdown_utc': reset_utc,
        'reset_countdown_human': reset_human,
    }


def compute_daily_velocity(
    turns: List[Dict[str, Any]],
    weekly_cycle_start: Any,
    reference_time: Optional[datetime.datetime] = None,
    pricing_models: Optional[Dict[str, Any]] = None,
    weekly_capacity_usd: float = 129.00,
) -> List[Dict[str, Any]]:
    """Group turns by calendar day within the weekly cycle and compute burn rates."""
    if pricing_models is None:
        pricing_models = {}
    ref_dt = reference_time or datetime.datetime.now(datetime.timezone.utc)
    if ref_dt.tzinfo is None:
        ref_dt = ref_dt.replace(tzinfo=datetime.timezone.utc)

    if isinstance(weekly_cycle_start, str):
        weekly_cycle_start = parse_timestamp(weekly_cycle_start)
    elif weekly_cycle_start and weekly_cycle_start.tzinfo is None:
        weekly_cycle_start = weekly_cycle_start.replace(tzinfo=datetime.timezone.utc)

    daily_buckets = defaultdict(lambda: {
        'turn_count': 0,
        'total_tokens': 0,
        'imputed_cost_usd': 0.0,
    })

    for t in turns:
        t_dt = parse_timestamp(t.get('timestamp'))
        if not t_dt or t_dt < weekly_cycle_start or t_dt > ref_dt:
            continue
        day_key = t_dt.strftime('%Y-%m-%d')
        mid = str(t.get('model_id', 'unknown'))
        rates = get_model_rates(mid, pricing_models, timestamp=t.get('timestamp'))
        cost = compute_turn_cost(t, rates)
        tokens = t.get('prompt_tokens_uncached', 0) + t.get('cached_tokens', 0) + t.get('output_tokens_total', 0)
        daily_buckets[day_key]['turn_count'] += 1
        daily_buckets[day_key]['total_tokens'] += tokens
        daily_buckets[day_key]['imputed_cost_usd'] += cost

    days = []
    for day_key in sorted(daily_buckets.keys()):
        b = daily_buckets[day_key]
        b['date'] = day_key
        b['imputed_cost_usd'] = round(b['imputed_cost_usd'], 4)
        budget_pct = round((b['imputed_cost_usd'] / weekly_capacity_usd * 100.0) if weekly_capacity_usd > 0 else 0.0, 1)
        b['budget_pct'] = budget_pct
        b['is_anomaly'] = budget_pct > 25.0  # Single day consuming >25% of weekly budget
        days.append(b)

    return days


def compute_quota_runway(
    gemini_weekly: Dict[str, Any],
    weekly_cycle_bounds: Dict[str, Any],
    gemini_5h: Optional[Dict[str, Any]] = None,
    reference_time: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    """Compute mathematical quota runway metrics: Time needle, BVI, daily budget, and exhaustion ETA.

    Formulas (ADR-031):
      - T_elapsed_pct = (now - cycle_start) / (cycle_end - cycle_start) * 100
      - Q_consumed_pct = 100 - gemini_weekly.remaining_pct
      - BVI = Q_consumed_pct / T_elapsed_pct (clamped when T_elapsed_pct < 0.5)
      - Daily Target = remaining_pct / days_remaining
      - Exhaustion ETA = projected datetime if BVI > 1.0, else 'None'
    """
    ref_dt = reference_time or datetime.datetime.now(datetime.timezone.utc)
    if ref_dt.tzinfo is None:
        ref_dt = ref_dt.replace(tzinfo=datetime.timezone.utc)

    cycle_start = parse_timestamp(weekly_cycle_bounds.get('cycle_start_utc', ''))
    cycle_end = parse_timestamp(weekly_cycle_bounds.get('cycle_end_utc', ''))

    if not cycle_start or not cycle_end:
        return {
            'calendar_time_elapsed_pct': 0.0,
            'calendar_days_elapsed': 0.0,
            'calendar_days_remaining': 7.0,
            'day_index': 1,
            'daily_ceiling_pct': 14.3,
            'day_budget_used_pct': 0.0,
            'banked_buffer_pct': 14.3,
            'quota_consumed_pct': 0.0,
            'quota_remaining_pct': 100.0,
            'burn_velocity_index': 0.0,
            'bvi_display': '0.00x',
            'target_daily_budget_pct': 14.3,
            'exhaustion_eta': 'None',
            'exhaustion_caption': 'Survives to reset',
            'status_key': 'green',
            'status_text': '✓ Sustainable (0.00x)',
            'status_sub': 'Day 1: +14.3% buffer (0.0% vs 14.3%)',
            'burst_used_pct': 0.0,
            'burst_cooldown_active': False,
            'burst_seconds_remaining': 0,
        }

    total_seconds = max(1.0, (cycle_end - cycle_start).total_seconds())
    elapsed_seconds = max(0.0, min(total_seconds, (ref_dt - cycle_start).total_seconds()))
    remaining_seconds = max(0.0, (cycle_end - ref_dt).total_seconds())

    time_elapsed_pct = round((elapsed_seconds / total_seconds) * 100.0, 1)
    total_days = total_seconds / 86400.0
    days_elapsed = round(elapsed_seconds / 86400.0, 1)
    days_remaining = max(0.1, remaining_seconds / 86400.0)

    weekly_rem = float(gemini_weekly.get('remaining_pct', 100.0))
    quota_consumed_pct = round(max(0.0, min(100.0, 100.0 - weekly_rem)), 1)

    # Diurnal / Calendar Day Framing (ADR-032 / ADR-033 / ADR-045)
    nominal_daily_budget_pct = round(100.0 / total_days, 1) if total_days > 0 else 14.3
    import math
    day_index = max(1, min(int(math.ceil(elapsed_seconds / 86400.0)) if elapsed_seconds > 0 else 1, int(math.ceil(total_days))))
    daily_ceiling_pct = min(100.0, round(day_index * nominal_daily_budget_pct, 1))
    day_budget_used_pct = round((quota_consumed_pct / daily_ceiling_pct) * 100.0, 1) if daily_ceiling_pct > 0 else 0.0
    banked_buffer_pct = round(daily_ceiling_pct - quota_consumed_pct, 1)

    # Bayesian M-Estimate Shrinkage (ADR-032)
    # k = 1.0 pseudo-day prior weight at nominal rate (100 / 7 ≈ 14.286%/day)
    prior_daily_rate = 100.0 / total_days if total_days > 0 else 14.2857
    k_pseudo_days = 1.0
    elapsed_days_float = elapsed_seconds / 86400.0

    if quota_consumed_pct == 0:
        bvi_raw = 0.0
        bvi_bayes = 0.0
        bvi = 0.0
        bvi_display = "0.00x"
        status_key = "green"
        status_text = "✓ Sustainable (0.00x)"
        status_sub = f"Day {day_index}: +{banked_buffer_pct:.1f}% buffer ({quota_consumed_pct:.1f}% vs {daily_ceiling_pct:.1f}%)"
    else:
        bvi_raw = round(quota_consumed_pct / time_elapsed_pct, 2) if time_elapsed_pct >= 0.1 else round(quota_consumed_pct / 0.1, 2)
        effective_daily_rate = (quota_consumed_pct + (k_pseudo_days * prior_daily_rate)) / (elapsed_days_float + k_pseudo_days)
        bvi_bayes = round(effective_daily_rate / prior_daily_rate, 2)
        bvi = bvi_bayes
        bvi_display = f"{bvi:.2f}x"

        # Daily Budget Guardrail: If consumed is within today's cumulative ceiling, clamp to green
        if weekly_rem <= 0.1:
            status_key = "exhausted"
            status_text = "⚠️ Exhausted (0%)"
            status_sub = f"Quota depleted ({quota_consumed_pct:.1f}% vs {daily_ceiling_pct:.1f}%)"
        elif quota_consumed_pct <= daily_ceiling_pct:
            status_key = "green"
            status_text = f"✓ On Track ({bvi_display})"
            status_sub = f"Day {day_index}: +{banked_buffer_pct:.1f}% buffer ({quota_consumed_pct:.1f}% vs {daily_ceiling_pct:.1f}%)"
        elif bvi <= 1.0:
            status_key = "green"
            status_text = f"✓ Sustainable ({bvi_display})"
            deficit_pct = round(quota_consumed_pct - daily_ceiling_pct, 1)
            status_sub = f"Day {day_index}: -{deficit_pct:.1f}% deficit ({quota_consumed_pct:.1f}% vs {daily_ceiling_pct:.1f}%)"
        elif bvi <= 1.3:
            status_key = "amber"
            status_text = f"⚠ Elevated ({bvi_display})"
            deficit_pct = round(quota_consumed_pct - daily_ceiling_pct, 1)
            status_sub = f"Day {day_index}: -{deficit_pct:.1f}% deficit ({quota_consumed_pct:.1f}% vs {daily_ceiling_pct:.1f}%)"
        else:
            status_key = "red"
            status_text = f"⛔ Overburn ({bvi_display})"
            deficit_pct = round(quota_consumed_pct - daily_ceiling_pct, 1)
            status_sub = f"Day {day_index}: -{deficit_pct:.1f}% deficit ({quota_consumed_pct:.1f}% vs {daily_ceiling_pct:.1f}%)"

    # Target Daily Budget (remaining / remaining days)
    target_daily_budget_pct = round(weekly_rem / days_remaining, 1)

    # Exhaustion ETA using Bayesian Smoothed Daily Rate
    if weekly_rem <= 0.1:
        exhaustion_eta = "Exhausted"
        exhaustion_caption = "Quota depleted"
    elif bvi <= 1.0 or quota_consumed_pct == 0:
        exhaustion_eta = "None"
        exhaustion_caption = "Survives to reset"
    else:
        effective_rate = (quota_consumed_pct + (k_pseudo_days * prior_daily_rate)) / (elapsed_days_float + k_pseudo_days)
        days_to_exhaust = weekly_rem / effective_rate if effective_rate > 0 else 999.0
        if days_to_exhaust >= days_remaining:
            exhaustion_eta = "None"
            exhaustion_caption = "Survives to reset"
        else:
            exhaustion_dt = ref_dt + datetime.timedelta(days=days_to_exhaust)
            exhaustion_eta = exhaustion_dt.strftime("~%a %H:%M")
            early_days = round(days_remaining - days_to_exhaust, 1)
            if quota_consumed_pct <= daily_ceiling_pct:
                exhaustion_caption = f"Safe buffer (Day {day_index})"
            elif early_days >= 1.0:
                exhaustion_caption = f"Tight buffer ({early_days}d)" if bvi <= 1.3 else f"Exhausts {early_days}d early!"
            else:
                early_hours = max(1, int(round((days_remaining - days_to_exhaust) * 24.0)))
                exhaustion_caption = f"Tight buffer ({early_hours}h)" if bvi <= 1.3 else f"Exhausts {early_hours}h early!"

    # 5h Burst Governor
    burst_used_pct = float(gemini_5h.get("used_pct", 0.0)) if gemini_5h else 0.0
    burst_rem_pct = float(gemini_5h.get("remaining_pct", 100.0)) if gemini_5h else 100.0
    rec_schedule = gemini_5h.get("recovery_schedule", []) if gemini_5h else []
    seconds_to_cooldown = rec_schedule[0].get("seconds_until", 0) if rec_schedule else 0
    burst_cooldown_active = burst_rem_pct <= 0.1 or (burst_used_pct >= 99.0 and seconds_to_cooldown > 0)

    return {
        "calendar_time_elapsed_pct": time_elapsed_pct,
        "calendar_days_elapsed": days_elapsed,
        "calendar_days_remaining": round(days_remaining, 1),
        "day_index": day_index,
        "daily_ceiling_pct": daily_ceiling_pct,
        "day_budget_used_pct": day_budget_used_pct,
        "banked_buffer_pct": banked_buffer_pct,
        "quota_consumed_pct": quota_consumed_pct,
        "quota_remaining_pct": weekly_rem,
        "burn_velocity_index": bvi,
        "bvi_raw": bvi_raw if quota_consumed_pct > 0 else 0.0,
        "bvi_bayes": bvi_bayes if quota_consumed_pct > 0 else 0.0,
        "bvi_display": bvi_display,
        "target_daily_budget_pct": target_daily_budget_pct,
        "exhaustion_eta": exhaustion_eta,
        "exhaustion_caption": exhaustion_caption,
        "status_key": status_key,
        "status_text": status_text,
        "status_sub": status_sub,
        "burst_used_pct": burst_used_pct,
        "burst_cooldown_active": burst_cooldown_active,
        "burst_seconds_remaining": seconds_to_cooldown,
    }


def compute_rolling_window_telemetry(
    turns: List[Dict[str, Any]],
    window_hours: float = 5.0,
    reference_time: Optional[datetime.datetime] = None,
    pricing_models: Optional[Dict[str, Any]] = None,
    start_time: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    """
    Compute aggregate usage within a time window [window_start, reference_time].
    Partitions results by model_id and computes total tokens and imputed subscription value.
    """
    if pricing_models is None:
        pricing_models = {}

    ref_dt = reference_time or datetime.datetime.now(datetime.timezone.utc)
    if ref_dt.tzinfo is None:
        ref_dt = ref_dt.replace(tzinfo=datetime.timezone.utc)

    if start_time is not None:
        window_start = start_time
        if window_start.tzinfo is None:
            window_start = window_start.replace(tzinfo=datetime.timezone.utc)
        effective_window_hours = max(0.0, (ref_dt - window_start).total_seconds() / 3600.0)
    else:
        window_start = ref_dt - datetime.timedelta(hours=window_hours)
        effective_window_hours = window_hours

    window_turns = []
    for t in turns:
        t_dt = parse_timestamp(t.get("timestamp"))
        if t_dt and window_start <= t_dt <= ref_dt:
            window_turns.append(t)

    # Aggregation
    total_uncached = sum(t.get("prompt_tokens_uncached", 0) for t in window_turns)
    total_cached = sum(t.get("cached_tokens", 0) for t in window_turns)
    total_input = total_uncached + total_cached
    total_output = sum(t.get("output_tokens_total", 0) for t in window_turns)
    total_thinking = sum(t.get("thinking_tokens", 0) for t in window_turns)
    total_answer = sum(t.get("answer_tokens", 0) for t in window_turns)
    total_processed = total_input + total_output

    cache_hit_ratio_pct = (total_cached / total_input * 100.0) if total_input > 0 else 0.0

    # Model Breakdown
    by_model_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "model_id": "",
        "model_name": "",
        "turn_count": 0,
        "prompt_tokens_uncached": 0,
        "cached_tokens": 0,
        "total_input_tokens": 0,
        "output_tokens_total": 0,
        "thinking_tokens": 0,
        "answer_tokens": 0,
        "total_processed_tokens": 0,
        "cache_hit_ratio_pct": 0.0,
        "imputed_value_usd": 0.0,
    })

    total_imputed_value = 0.0

    for t in window_turns:
        mid = str(t.get("model_id", "unknown"))
        rates = get_model_rates(mid, pricing_models, timestamp=t.get("timestamp"))
        cost = compute_turn_cost(t, rates)
        total_imputed_value += cost

        m_entry = by_model_map[mid]
        m_entry["model_id"] = mid
        m_entry["model_name"] = get_model_display_name(mid, pricing_models)
        m_entry["turn_count"] += 1
        m_entry["prompt_tokens_uncached"] += t.get("prompt_tokens_uncached", 0)
        m_entry["cached_tokens"] += t.get("cached_tokens", 0)
        m_entry["total_input_tokens"] += (t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0))
        m_entry["output_tokens_total"] += t.get("output_tokens_total", 0)
        m_entry["thinking_tokens"] += t.get("thinking_tokens", 0)
        m_entry["answer_tokens"] += t.get("answer_tokens", 0)
        m_entry["total_processed_tokens"] += (
            t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0) + t.get("output_tokens_total", 0)
        )
        m_entry["imputed_value_usd"] += cost

    # Session attribution (M3): partition window turns by convo_id
    by_convo_map = defaultdict(lambda: {
        "convo_id": "",
        "turn_count": 0,
        "prompt_tokens_uncached": 0,
        "cached_tokens": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "thinking_tokens": 0,
        "answer_tokens": 0,
        "total_processed_tokens": 0,
        "imputed_value_usd": 0.0,
        "primary_model_id": "",
    })
    convo_model_counts = defaultdict(lambda: defaultdict(int))

    for t in window_turns:
        cid = str(t.get("convo_id", ""))
        if not cid:
            continue
        mid = str(t.get("model_id", "unknown"))
        rates = get_model_rates(mid, pricing_models, timestamp=t.get("timestamp"))
        cost = compute_turn_cost(t, rates)

        c_entry = by_convo_map[cid]
        c_entry["convo_id"] = cid
        c_entry["turn_count"] += 1
        c_entry["prompt_tokens_uncached"] += t.get("prompt_tokens_uncached", 0)
        c_entry["cached_tokens"] += t.get("cached_tokens", 0)
        c_entry["total_input_tokens"] += (t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0))
        c_entry["total_output_tokens"] += t.get("output_tokens_total", 0)
        c_entry["thinking_tokens"] += t.get("thinking_tokens", 0)
        c_entry["answer_tokens"] += t.get("answer_tokens", 0)
        c_entry["total_processed_tokens"] += (
            t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0) + t.get("output_tokens_total", 0)
        )
        c_entry["imputed_value_usd"] += cost
        convo_model_counts[cid][mid] += 1

    currency_cfg = pricing_models.get("currency", {})
    usd_to_gbp_fx = currency_cfg.get("usd_to_gbp_fx_rate", 0.79)

    # Calculate percentages for models
    model_list = []
    for m_entry in by_model_map.values():
        inp = m_entry["total_input_tokens"]
        cac = m_entry["cached_tokens"]
        m_entry["cache_hit_ratio_pct"] = round((cac / inp * 100.0) if inp > 0 else 0.0, 2)
        m_entry["imputed_value_usd"] = round(m_entry["imputed_value_usd"], 4)
        m_entry["imputed_value_gbp"] = round(m_entry["imputed_value_usd"] * usd_to_gbp_fx, 4)
        m_entry["avoided_cost_usd"] = m_entry["imputed_value_usd"]
        m_entry["avoided_cost_gbp"] = m_entry["imputed_value_gbp"]
        model_list.append(m_entry)

    # Sort models by total processed tokens descending
    model_list.sort(key=lambda m: m["total_processed_tokens"], reverse=True)

    # Format active sessions
    session_list = []
    for cid, c_entry in by_convo_map.items():
        inp = c_entry["total_input_tokens"]
        cac = c_entry["cached_tokens"]
        c_entry["cache_hit_ratio_pct"] = round((cac / inp * 100.0) if inp > 0 else 0.0, 2)
        c_entry["imputed_value_usd"] = round(c_entry["imputed_value_usd"], 4)
        c_entry["imputed_value_gbp"] = round(c_entry["imputed_value_usd"] * usd_to_gbp_fx, 4)
        c_entry["avoided_cost_usd"] = c_entry["imputed_value_usd"]
        c_entry["avoided_cost_gbp"] = c_entry["imputed_value_gbp"]
        top_mid = max(convo_model_counts[cid].items(), key=lambda x: x[1])[0] if convo_model_counts[cid] else ""
        c_entry["primary_model_id"] = top_mid
        c_entry["primary_model_name"] = get_model_display_name(top_mid, pricing_models)
        session_list.append(c_entry)

    session_list.sort(key=lambda s: s["total_processed_tokens"], reverse=True)

    return {
        "window_hours": window_hours,
        "reference_time": ref_dt.isoformat(),
        "window_start": window_start.isoformat(),
        "turn_count": len(window_turns),
        "total_input_tokens": total_input,
        "prompt_tokens_uncached": total_uncached,
        "cached_tokens": total_cached,
        "total_output_tokens": total_output,
        "thinking_tokens": total_thinking,
        "answer_tokens": total_answer,
        "total_processed_tokens": total_processed,
        "cache_hit_ratio_pct": round(cache_hit_ratio_pct, 2),
        "imputed_value_usd": round(total_imputed_value, 4),
        "imputed_value_gbp": round(total_imputed_value * usd_to_gbp_fx, 4),
        "avoided_cost_usd": round(total_imputed_value, 4),
        "avoided_cost_gbp": round(total_imputed_value * usd_to_gbp_fx, 4),
        "by_model": model_list,
        "active_sessions_5h": session_list,
    }


def compute_window_recovery_schedule(
    turns: List[Dict[str, Any]],
    window_hours: float = 5.0,
    reference_time: Optional[datetime.datetime] = None,
    limit: int = 5,
    pricing_models: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Calculate sliding-window roll-off timeline:
    Identifies the earliest upcoming turns in the window and when they will age out,
    restoring token allowance capacity to the user.
    """
    if pricing_models is None:
        pricing_models = {}

    ref_dt = reference_time or datetime.datetime.now(datetime.timezone.utc)
    if ref_dt.tzinfo is None:
        ref_dt = ref_dt.replace(tzinfo=datetime.timezone.utc)

    window_start = ref_dt - datetime.timedelta(hours=window_hours)

    active_turns = []
    for t in turns:
        t_dt = parse_timestamp(t.get("timestamp"))
        if t_dt and window_start <= t_dt <= ref_dt:
            active_turns.append((t_dt, t))

    # Sort chronologically by timestamp (oldest first)
    active_turns.sort(key=lambda item: item[0])

    schedule = []
    cumulative_recovered = 0

    for t_dt, t in active_turns[:limit]:
        age_out_dt = t_dt + datetime.timedelta(hours=window_hours)
        seconds_remaining = max(0, (age_out_dt - ref_dt).total_seconds())
        minutes_remaining = int(seconds_remaining / 60)

        mid = str(t.get("model_id", "unknown"))
        model_name = get_model_display_name(mid, pricing_models)
        inp = t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0)
        out = t.get("output_tokens_total", 0)
        turn_tokens = inp + out
        cumulative_recovered += turn_tokens

        schedule.append({
            "step_idx": t.get("step_idx"),
            "convo_id": t.get("convo_id"),
            "model_id": mid,
            "model_name": model_name,
            "turn_timestamp": t_dt.isoformat(),
            "age_out_timestamp": age_out_dt.isoformat(),
            "minutes_remaining": minutes_remaining,
            "tokens_to_recover": turn_tokens,
            "cumulative_tokens_recovered": cumulative_recovered,
        })

    return schedule


def compute_historical_peaks(
    turns: List[Dict[str, Any]],
    pricing_models: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Find maximum historical 5-hour and 7-day token bursts across all conversation turns.
    """
    if not turns:
        return {"peak_5h_tokens": 0, "peak_1w_tokens": 0}

    valid_turns = []
    for t in turns:
        t_dt = parse_timestamp(t.get("timestamp"))
        if t_dt:
            valid_turns.append((t_dt, t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0) + t.get("output_tokens_total", 0)))

    valid_turns.sort(key=lambda x: x[0])
    if not valid_turns:
        return {"peak_5h_tokens": 0, "peak_1w_tokens": 0}

    # Two-pointer sliding window for 5 hours
    max_5h = 0
    window_5h = datetime.timedelta(hours=5)
    left = 0
    current_sum = 0

    for right in range(len(valid_turns)):
        current_sum += valid_turns[right][1]
        while valid_turns[right][0] - valid_turns[left][0] > window_5h:
            current_sum -= valid_turns[left][1]
            left += 1
        if current_sum > max_5h:
            max_5h = current_sum

    # Two-pointer sliding window for 7 days (168 hours)
    max_1w = 0
    window_1w = datetime.timedelta(days=7)
    left = 0
    current_sum = 0

    for right in range(len(valid_turns)):
        current_sum += valid_turns[right][1]
        while valid_turns[right][0] - valid_turns[left][0] > window_1w:
            current_sum -= valid_turns[left][1]
            left += 1
        if current_sum > max_1w:
            max_1w = current_sum

    return {
        "peak_5h_tokens": max_5h,
        "peak_1w_tokens": max_1w,
    }


def aggregate_conversation_telemetry(
    conversation_meta: Dict[str, Any],
    turns: List[Dict[str, Any]],
    pricing_models: Dict[str, Any],
    exhaustion_intervals: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compute aggregated metrics for a single conversation, correlating turns with overage intervals."""
    total_uncached = sum(t.get("prompt_tokens_uncached", 0) for t in turns)
    total_cached = sum(t.get("cached_tokens", 0) for t in turns)
    total_input = total_uncached + total_cached
    total_output = sum(t.get("output_tokens_total", 0) for t in turns)
    total_thinking = sum(t.get("thinking_tokens", 0) for t in turns)
    total_answer = sum(t.get("answer_tokens", 0) for t in turns)

    cache_hit_ratio_pct = (total_cached / total_input * 100.0) if total_input > 0 else 0.0

    currency_cfg = pricing_models.get("currency", {})
    usd_to_gbp_fx = currency_cfg.get("usd_to_gbp_fx_rate", 0.79)

    total_cost = 0.0
    models_used = set()
    enriched_turns = []

    for t in turns:
        mid = str(t.get("model_id", "unknown"))
        models_used.add(mid)
        rates = get_model_rates(mid, pricing_models, timestamp=t.get("timestamp"))
        cost = compute_turn_cost(t, rates)
        total_cost += cost

        turn_copy = dict(t)
        turn_copy["model_name"] = get_model_display_name(mid, pricing_models)
        turn_copy["estimated_cost_usd"] = cost
        turn_copy["avoided_cost_usd"] = cost
        turn_copy["avoided_cost_gbp"] = round(cost * usd_to_gbp_fx, 4)

        # Correlate with exhaustion intervals
        turn_dt = parse_timestamp(t.get("timestamp"))
        is_overage = False
        if turn_dt and exhaustion_intervals:
            for inv in exhaustion_intervals:
                s = inv.get("start")
                e = inv.get("end")
                if isinstance(s, str):
                    s = parse_timestamp(s)
                if isinstance(e, str):
                    e = parse_timestamp(e)
                if s and e and s <= turn_dt <= e:
                    is_overage = True
                    break
        turn_copy["is_overage"] = is_overage
        enriched_turns.append(turn_copy)

    first_turn_ts = turns[0].get("timestamp") if turns else None
    last_turn_ts = turns[-1].get("timestamp") if turns else None

    covered_turns_cnt = sum(1 for t in enriched_turns if not t.get("is_overage"))
    overage_turns_cnt = len(enriched_turns) - covered_turns_cnt
    covered_pct = round(covered_turns_cnt / len(enriched_turns) * 100.0, 1) if enriched_turns else 100.0

    return {
        "convo_id": conversation_meta.get("convo_id", ""),
        "title": conversation_meta.get("title", "Untitled Conversation"),
        "workspace": conversation_meta.get("workspace_name") or conversation_meta.get("workspace", "Unknown Workspace"),
        "workspace_path": conversation_meta.get("workspace_path", ""),
        "workspace_name": conversation_meta.get("workspace_name") or conversation_meta.get("workspace", "Unknown Workspace"),
        "git_branch": conversation_meta.get("git_branch", "main"),
        "turn_count": len(turns),
        "subscription_covered_turns": covered_turns_cnt,
        "overage_turns": overage_turns_cnt,
        "subscription_covered_pct": covered_pct,
        "total_input_tokens": total_input,
        "prompt_tokens_uncached": total_uncached,
        "cached_tokens": total_cached,
        "total_output_tokens": total_output,
        "thinking_tokens": total_thinking,
        "answer_tokens": total_answer,
        "cache_hit_ratio_pct": round(cache_hit_ratio_pct, 2),
        "estimated_cost_usd": round(total_cost, 4),
        "avoided_cost_usd": round(total_cost, 4),
        "avoided_cost_gbp": round(total_cost * usd_to_gbp_fx, 4),
        "models_used": sorted(list(models_used)),
        "first_turn_ts": first_turn_ts,
        "last_turn_ts": last_turn_ts,
        "turns": enriched_turns,
    }


def compute_simulation_presets(
    initial_quota_state: Optional[Dict[str, Any]] = None,
    pricing_models: Optional[Dict[str, Any]] = None,
    plan_config: Optional[Dict[str, Any]] = None,
    fx_rate: float = 0.79,
) -> Dict[str, Any]:
    """
    Compute deterministic simulation results for standard multi-agent archetypes (ADR-035).
    Evaluates archetypes against the active quota state and plan configuration.
    """
    archetypes = get_archetype_presets()
    plan_tier = (plan_config or {}).get("tier", "pro") if plan_config else "pro"

    results: Dict[str, Any] = {}
    for arch_id, arch_spec in archetypes.items():
        sim_res = simulate_archetype(
            arch_id,
            initial_quota_state=initial_quota_state,
            plan_tier=plan_tier,
            pricing_models=pricing_models,
            fx_rate=fx_rate,
        )
        plan_comp = compare_plan_tiers(
            arch_spec,
            initial_quota_state=initial_quota_state,
            pricing_models=pricing_models,
            fx_rate=fx_rate,
        )
        sim_res["plan_comparison"] = plan_comp
        results[arch_id] = sim_res

    return {
        "active_plan_tier": plan_tier,
        "archetypes": archetypes,
        "results": results,
    }


def compute_cache_coaching_metrics(
    conversation_summaries: List[Dict[str, Any]],
    pricing_models: Dict[str, Any],
    usd_to_gbp_fx: float = 0.79,
) -> Dict[str, Any]:
    """
    Detect cross-provider model flips (Gemini <-> Claude/GPT) that evict KV caches,
    causing massive uncached prompt replays. Quantifies wasted tokens and avoided cost.
    (ADR-030 / docs/FINDINGS.md §5).
    """
    total_flips = 0
    wasted_tokens_total = 0
    wasted_cost_usd_total = 0.0
    incidents = []

    for convo in conversation_summaries:
        cid = convo.get("convo_id") or convo.get("conversation_id", "")
        title = convo.get("title", "Untitled Session")
        ws_name = convo.get("workspace_name", "Unknown Workspace")
        turns = convo.get("turns", [])
        if len(turns) < 2:
            continue

        for i in range(1, len(turns)):
            prev_t = turns[i - 1]
            curr_t = turns[i]
            prev_mid = str(prev_t.get("model_id", "unknown"))
            curr_mid = str(curr_t.get("model_id", "unknown"))
            prev_track = get_provider_quota_track(prev_mid, pricing_models)
            curr_track = get_provider_quota_track(curr_mid, pricing_models)

            # Check for cross-provider flip between Gemini and Claude/GPT
            if prev_track != curr_track and prev_track in ("gemini", "claude_gpt") and curr_track in ("gemini", "claude_gpt"):
                curr_uncached = curr_t.get("prompt_tokens_uncached", 0)
                curr_cached = curr_t.get("cached_tokens", 0)
                curr_total_inp = curr_uncached + curr_cached

                # If prompt is substantial (>= 25k tokens) and cache was blown (hit ratio < 20%)
                cache_hit_pct = (curr_cached / curr_total_inp * 100.0) if curr_total_inp > 0 else 0.0
                if curr_total_inp >= 25000 and cache_hit_pct < 20.0:
                    # In steady-state, cache hit is ~90%. Wasted uncached tokens = ~90% of total input that had to be re-read
                    wasted_tokens = int(curr_total_inp * 0.90) - curr_cached
                    if wasted_tokens > 0:
                        total_flips += 1
                        wasted_tokens_total += wasted_tokens
                        rates = get_model_rates(curr_mid, pricing_models, timestamp=curr_t.get("timestamp"))
                        prompt_rate = rates.get("prompt_uncached", rates.get("prompt_price_per_m", 0.0))
                        cache_rate = rates.get("prompt_cached", rates.get("cached_price_per_m", 0.0))
                        diff_rate = max(0.0, prompt_rate - cache_rate)
                        wasted_cost = (wasted_tokens / 1_000_000.0) * diff_rate
                        wasted_cost_usd_total += wasted_cost

                        incidents.append({
                            "convo_id": cid,
                            "title": title,
                            "workspace_name": ws_name,
                            "timestamp": curr_t.get("timestamp"),
                            "step_idx": curr_t.get("step_idx"),
                            "from_model": get_model_display_name(prev_mid, pricing_models),
                            "to_model": get_model_display_name(curr_mid, pricing_models),
                            "from_track": prev_track,
                            "to_track": curr_track,
                            "total_input_tokens": curr_total_inp,
                            "uncached_tokens": curr_uncached,
                            "cached_tokens": curr_cached,
                            "wasted_tokens": wasted_tokens,
                            "wasted_cost_usd": round(wasted_cost, 4),
                            "wasted_cost_gbp": round(wasted_cost * usd_to_gbp_fx, 4),
                        })

    # Sort incidents by wasted tokens descending
    incidents.sort(key=lambda x: x["wasted_tokens"], reverse=True)

    return {
        "model_flips_detected": total_flips,
        "wasted_uncached_tokens": wasted_tokens_total,
        "wasted_avoided_cost_usd": round(wasted_cost_usd_total, 4),
        "wasted_avoided_cost_gbp": round(wasted_cost_usd_total * usd_to_gbp_fx, 4),
        "top_incidents": incidents[:10],
        "coaching_tip": "Cross-provider model flips (Gemini ↔ Claude) evict KV caches, incurring up to 80k uncached token re-reads. Stick to one provider family within deep coding sessions."
    }


def aggregate_global_telemetry(
    conversation_summaries: List[Dict[str, Any]],
    pricing_models: Dict[str, Any],
    all_raw_turns: Optional[List[Dict[str, Any]]] = None,
    reference_time: Optional[datetime.datetime] = None,
    exhaustion_intervals: Optional[List[Dict[str, Any]]] = None,
    live_quota: Optional[Dict[str, Any]] = None,
    discovered_databases: Optional[int] = None,
    scanned_databases: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Compute overall dashboard metrics, rolling quota allowances, and dual-track cost totals.
    Fuses continuous sliding window token limits with log-anchored 429 exhaustion intervals
    and cost-weighted rate card convergence with live desktop indicator synchronization.
    """
    total_conversations = len(conversation_summaries)
    total_turns = sum(c.get("turn_count", 0) for c in conversation_summaries)
    total_input = sum(c.get("total_input_tokens", 0) for c in conversation_summaries)
    total_uncached = sum(c.get("prompt_tokens_uncached", 0) for c in conversation_summaries)
    total_cached = sum(c.get("cached_tokens", 0) for c in conversation_summaries)
    total_output = sum(c.get("total_output_tokens", 0) for c in conversation_summaries)
    total_thinking = sum(c.get("thinking_tokens", 0) for c in conversation_summaries)
    total_answer = sum(c.get("answer_tokens", 0) for c in conversation_summaries)
    total_imputed_cost = sum(c.get("estimated_cost_usd", 0.0) for c in conversation_summaries)

    overall_cache_hit_ratio = (total_cached / total_input * 100.0) if total_input > 0 else 0.0

    # Grouping by workspace
    by_workspace: Dict[str, Dict[str, Any]] = {}
    for c in conversation_summaries:
        ws = c.get("workspace", "Unknown Workspace")
        if ws not in by_workspace:
            by_workspace[ws] = {
                "workspace": ws,
                "conversation_count": 0,
                "turn_count": 0,
                "total_input_tokens": 0,
                "cached_tokens": 0,
                "total_output_tokens": 0,
                "estimated_cost_usd": 0.0,
            }
        by_workspace[ws]["conversation_count"] += 1
        by_workspace[ws]["turn_count"] += c.get("turn_count", 0)
        by_workspace[ws]["total_input_tokens"] += c.get("total_input_tokens", 0)
        by_workspace[ws]["cached_tokens"] += c.get("cached_tokens", 0)
        by_workspace[ws]["total_output_tokens"] += c.get("total_output_tokens", 0)
        by_workspace[ws]["estimated_cost_usd"] += c.get("estimated_cost_usd", 0.0)

    for ws_data in by_workspace.values():
        inp = ws_data["total_input_tokens"]
        cac = ws_data["cached_tokens"]
        ws_data["cache_hit_ratio_pct"] = round((cac / inp * 100.0) if inp > 0 else 0.0, 2)
        ws_data["estimated_cost_usd"] = round(ws_data["estimated_cost_usd"], 4)

    currency_cfg = pricing_models.get("currency", {})
    usd_to_gbp_fx = currency_cfg.get("usd_to_gbp_fx_rate", 0.79)
    sub_cfg = pricing_models.get("subscription", {})
    pack_cfg = currency_cfg.get("credit_pack", {})
    cents_per_credit = sub_cfg.get("cents_per_credit", 1.0)
    cost_per_credit_gbp = pack_cfg.get("cost_per_credit_gbp", 0.009596)

    # Auto-extract log exhaustion intervals if not supplied
    if exhaustion_intervals is None:
        try:
            from src.log_reader import extract_exhaustion_intervals
            exhaustion_intervals = extract_exhaustion_intervals()
        except Exception:
            exhaustion_intervals = []

    normalized_intervals = []
    for inv in (exhaustion_intervals or []):
        inv_copy = dict(inv)
        s = inv_copy.get("start")
        if isinstance(s, str):
            s = parse_timestamp(s)
        inv_copy["start"] = s
        e = inv_copy.get("end")
        if isinstance(e, str):
            e = parse_timestamp(e)
        inv_copy["end"] = e
        normalized_intervals.append(inv_copy)
    exhaustion_intervals = normalized_intervals

    ledger_intervals = [inv for inv in exhaustion_intervals if inv.get("from_ledger")]
    live_intervals = [inv for inv in exhaustion_intervals if not inv.get("from_ledger")]

    # Hierarchical grouping by project and Git branch with dual-track cost accounting (ADR-022)
    incident_turns: Dict[str, List[Tuple[str, str, Dict[str, Any], Dict[str, Any]]]] = defaultdict(list)
    projects_map: Dict[str, Dict[str, Any]] = {}

    for c in conversation_summaries:
        c["subscription_covered_turns"] = 0
        c["overage_turns"] = 0
        c["actual_overage_credits"] = 0.0
        c["actual_overage_usd"] = 0.0
        c["actual_overage_gbp"] = 0.0
        ws_path = c.get("workspace_path", "")
        ws_name = c.get("workspace_name") or c.get("workspace") or "Unknown Workspace"
        proj_key = ws_path if ws_path else ws_name

        if proj_key not in projects_map:
            projects_map[proj_key] = {
                "project_name": ws_name,
                "workspace_path": ws_path,
                "branches_map": {},
            }

        b_map = projects_map[proj_key]["branches_map"]

        def _get_or_init_branch(b_name: str) -> Dict[str, Any]:
            if b_name not in b_map:
                b_map[b_name] = {
                    "branch_name": b_name,
                    "conversation_count": 0,
                    "turn_count": 0,
                    "subscription_covered_turns": 0,
                    "overage_turns": 0,
                    "actual_overage_credits": 0.0,
                    "actual_overage_usd": 0.0,
                    "actual_overage_gbp": 0.0,
                    "avoided_cost_usd": 0.0,
                    "avoided_cost_gbp": 0.0,
                    "total_input_tokens": 0,
                    "prompt_tokens_uncached": 0,
                    "cached_tokens": 0,
                    "total_output_tokens": 0,
                    "estimated_cost_usd": 0.0,
                    "estimated_cost_gbp": 0.0,
                }
            return b_map[b_name]

        turns = c.get("turns", [])
        fallback_branch = c.get("git_branch") or "main"

        if not turns:
            # Metadata-only conversation without individual turn objects
            b = _get_or_init_branch(fallback_branch)
            b["conversation_count"] += 1
            b["turn_count"] += c.get("turn_count", 0)
            b["total_input_tokens"] += c.get("total_input_tokens", 0)
            b["prompt_tokens_uncached"] += c.get("prompt_tokens_uncached", 0)
            b["cached_tokens"] += c.get("cached_tokens", 0)
            b["total_output_tokens"] += c.get("total_output_tokens", 0)
            cost_usd = c.get("estimated_cost_usd", 0.0)
            b["avoided_cost_usd"] += cost_usd
            b["avoided_cost_gbp"] += cost_usd * usd_to_gbp_fx
            b["estimated_cost_usd"] += cost_usd
            b["estimated_cost_gbp"] += cost_usd * usd_to_gbp_fx
            b["subscription_covered_turns"] += c.get("turn_count", 0)
            c["subscription_covered_turns"] += c.get("turn_count", 0)
        else:
            # Dynamic Git reflog temporal branch attribution (ADR-046 / M33)
            branch_turns_map = defaultdict(list)
            for t in turns:
                t_branch = resolve_turn_branch(ws_path, t.get("timestamp"), fallback=fallback_branch)
                branch_turns_map[t_branch].append(t)

            c_total_turns = len(turns)
            c_input = c.get("total_input_tokens", 0)
            c_uncached = c.get("prompt_tokens_uncached", 0)
            c_cached = c.get("cached_tokens", 0)
            c_output = c.get("total_output_tokens", 0)
            c_cost = c.get("estimated_cost_usd", 0.0)

            has_turn_tokens = any((t.get("total_input_tokens") or t.get("prompt_tokens_uncached") or t.get("cached_tokens")) for t in turns)
            has_turn_costs = any(t.get("estimated_cost_usd") for t in turns)

            for t_branch, b_turns in branch_turns_map.items():
                b = _get_or_init_branch(t_branch)
                b["conversation_count"] += 1
                b_turn_cnt = len(b_turns)
                b["turn_count"] += b_turn_cnt

                if has_turn_tokens:
                    b_uncached = sum(t.get("prompt_tokens_uncached", 0) for t in b_turns)
                    b_cached = sum(t.get("cached_tokens", 0) for t in b_turns)
                    b_inp = sum(t.get("total_input_tokens") or (t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0)) for t in b_turns)
                    b_out = sum(t.get("output_tokens_total") or t.get("total_output_tokens", 0) for t in b_turns)
                else:
                    ratio = b_turn_cnt / c_total_turns if c_total_turns > 0 else 1.0
                    b_inp = int(round(c_input * ratio))
                    b_uncached = int(round(c_uncached * ratio))
                    b_cached = int(round(c_cached * ratio))
                    b_out = int(round(c_output * ratio))

                if has_turn_costs:
                    b_cost = sum(t.get("estimated_cost_usd", 0.0) for t in b_turns)
                else:
                    ratio = b_turn_cnt / c_total_turns if c_total_turns > 0 else 1.0
                    b_cost = c_cost * ratio

                b["total_input_tokens"] += b_inp
                b["prompt_tokens_uncached"] += b_uncached
                b["cached_tokens"] += b_cached
                b["total_output_tokens"] += b_out
                b["avoided_cost_usd"] += b_cost
                b["avoided_cost_gbp"] += b_cost * usd_to_gbp_fx
                b["estimated_cost_usd"] += b_cost
                b["estimated_cost_gbp"] += b_cost * usd_to_gbp_fx

                for t in b_turns:
                    t_dt = parse_timestamp(t.get("timestamp"))
                    if not t_dt:
                        b["subscription_covered_turns"] += 1
                        c["subscription_covered_turns"] += 1
                        continue

                    matched_ledger = None
                    for inv in ledger_intervals:
                        s = inv.get("start")
                        e = inv.get("end")
                        if isinstance(s, str):
                            s = parse_timestamp(s)
                        if isinstance(e, str):
                            e = parse_timestamp(e)
                        if s and e and s <= t_dt <= e:
                            matched_ledger = inv
                            break
                    if matched_ledger:
                        s_dt = matched_ledger.get("start")
                        s_str = s_dt.isoformat() if hasattr(s_dt, "isoformat") else str(s_dt)
                        inc_id = matched_ledger.get("incident_id") or s_str
                        incident_turns[inc_id].append((proj_key, t_branch, c, t))
                        continue

                    matched_live = None
                    for inv in live_intervals:
                        s = inv.get("start")
                        e = inv.get("end")
                        if isinstance(s, str):
                            s = parse_timestamp(s)
                        if isinstance(e, str):
                            e = parse_timestamp(e)
                        if s and e and s <= t_dt <= e:
                            matched_live = inv
                            break
                    if matched_live and get_provider_quota_track(t.get("model_id"), pricing_models) == "gemini":
                        mid = str(t.get("model_id", "unknown"))
                        burn = calculate_credit_burn(
                            mid,
                            turns_count=1,
                            pricing_models=pricing_models,
                            cents_per_credit=cents_per_credit,
                            cost_per_credit_gbp=cost_per_credit_gbp,
                        )
                        b["overage_turns"] += 1
                        b["actual_overage_credits"] += burn["credits"]
                        b["actual_overage_usd"] += burn["credit_burn_usd"]
                        b["actual_overage_gbp"] += burn["credit_burn_gbp"]

                        c["overage_turns"] += 1
                        c["actual_overage_credits"] += burn["credits"]
                        c["actual_overage_usd"] += burn["credit_burn_usd"]
                        c["actual_overage_gbp"] += burn["credit_burn_gbp"]
                        continue

                    b["subscription_covered_turns"] += 1
                    c["subscription_covered_turns"] += 1

    # Allocate confirmed ledger incidents across projects, branches, and conversations
    for inv in ledger_intervals:
        s_dt = inv.get("start")
        s_str = s_dt.isoformat() if hasattr(s_dt, "isoformat") else str(s_dt)
        inc_id = inv.get("incident_id") or s_str
        t_list = incident_turns.get(inc_id, [])
        if t_list:
            inc_credits = inv.get("credits_burned") or inv.get("credits_debited") or inv.get("calibrated_deduction_credits") or 0
            inc_usd = inv.get("credit_burn_usd") or inv.get("calibrated_deduction_usd") or 0.0
            inc_gbp = inv.get("credit_burn_gbp") or inv.get("calibrated_deduction_gbp") or 0.0
            total_k = len(t_list)
            total_cost = sum(t[3].get("estimated_cost_usd", 0.0) for t in t_list)
            use_cost_weighting = total_cost > 0

            # Allocate across branches
            branch_turns_map = defaultdict(list)
            for pk, bn, convo, turn in t_list:
                branch_turns_map[(pk, bn)].append(turn)

            for (pk, bn), b_turns in branch_turns_map.items():
                cnt = len(b_turns)
                if use_cost_weighting:
                    b_cost = sum(t.get("estimated_cost_usd", 0.0) for t in b_turns)
                    frac = b_cost / total_cost
                else:
                    frac = cnt / total_k
                b_map = projects_map[pk]["branches_map"][bn]
                b_map["actual_overage_credits"] += inc_credits * frac
                b_map["actual_overage_usd"] += inc_usd * frac
                b_map["actual_overage_gbp"] += inc_gbp * frac
                b_map["overage_turns"] += cnt

            # Allocate across conversations
            convo_turns_map = defaultdict(list)
            convo_lookup = {}
            for pk, bn, convo, turn in t_list:
                c_key = id(convo)
                convo_turns_map[c_key].append(turn)
                convo_lookup[c_key] = convo

            for c_id, c_turns in convo_turns_map.items():
                cnt = len(c_turns)
                if use_cost_weighting:
                    c_cost = sum(t.get("estimated_cost_usd", 0.0) for t in c_turns)
                    frac = c_cost / total_cost
                else:
                    frac = cnt / total_k
                convo = convo_lookup[c_id]
                convo["actual_overage_credits"] += inc_credits * frac
                convo["actual_overage_usd"] += inc_usd * frac
                convo["actual_overage_gbp"] += inc_gbp * frac
                convo["overage_turns"] += cnt

    for c in conversation_summaries:
        c_turns = c.get("turn_count", len(c.get("turns", [])))
        c_cov = c.get("subscription_covered_turns", 0)
        c["subscription_covered_pct"] = round((c_cov / c_turns * 100.0) if c_turns > 0 else 100.0, 1)
        c["actual_overage_credits"] = int(round(c.get("actual_overage_credits", 0.0)))
        c["actual_overage_usd"] = round(c.get("actual_overage_usd", 0.0), 4)
        c["actual_overage_gbp"] = round(c.get("actual_overage_gbp", 0.0), 4)

    projects = []
    for proj_key, p_data in projects_map.items():
        branches_list = []
        for b in p_data["branches_map"].values():
            b_inp = b["total_input_tokens"]
            b_cac = b["cached_tokens"]
            b_turns = b["turn_count"]
            b_cov = b["subscription_covered_turns"]
            b["cache_hit_ratio_pct"] = round((b_cac / b_inp * 100.0) if b_inp > 0 else 0.0, 2)
            b["subscription_covered_pct"] = round((b_cov / b_turns * 100.0) if b_turns > 0 else 100.0, 1)
            b["actual_overage_credits"] = int(round(b["actual_overage_credits"]))
            b["actual_overage_usd"] = round(b["actual_overage_usd"], 4)
            b["actual_overage_gbp"] = round(b["actual_overage_gbp"], 4)
            b["avoided_cost_usd"] = round(b["avoided_cost_usd"], 4)
            b["avoided_cost_gbp"] = round(b["avoided_cost_gbp"], 4)
            b["estimated_cost_usd"] = b["avoided_cost_usd"]
            b["estimated_cost_gbp"] = b["avoided_cost_gbp"]
            branches_list.append(b)

        # Sort branches within project by processed tokens descending
        branches_list.sort(
            key=lambda b: b["total_input_tokens"] + b["total_output_tokens"],
            reverse=True,
        )

        p_total_input = sum(b["total_input_tokens"] for b in branches_list)
        p_cached = sum(b["cached_tokens"] for b in branches_list)
        p_uncached = sum(b["prompt_tokens_uncached"] for b in branches_list)
        p_output = sum(b["total_output_tokens"] for b in branches_list)
        p_turns = sum(b["turn_count"] for b in branches_list)
        p_convos = sum(b["conversation_count"] for b in branches_list)
        p_cov_turns = sum(b["subscription_covered_turns"] for b in branches_list)
        p_ovg_turns = sum(b["overage_turns"] for b in branches_list)
        p_ovg_credits = sum(b["actual_overage_credits"] for b in branches_list)
        p_ovg_usd = round(sum(b["actual_overage_usd"] for b in branches_list), 4)
        p_ovg_gbp = round(sum(b["actual_overage_gbp"] for b in branches_list), 4)
        p_avoided_usd = round(sum(b["avoided_cost_usd"] for b in branches_list), 4)
        p_avoided_gbp = round(sum(b["avoided_cost_gbp"] for b in branches_list), 4)
        p_cache_pct = round((p_cached / p_total_input * 100.0) if p_total_input > 0 else 0.0, 2)
        p_cov_pct = round((p_cov_turns / p_turns * 100.0) if p_turns > 0 else 100.0, 1)

        projects.append({
            "project_name": p_data["project_name"],
            "workspace_path": p_data["workspace_path"],
            "conversation_count": p_convos,
            "turn_count": p_turns,
            "subscription_covered_turns": p_cov_turns,
            "overage_turns": p_ovg_turns,
            "subscription_covered_pct": p_cov_pct,
            "actual_overage_credits": p_ovg_credits,
            "actual_overage_usd": p_ovg_usd,
            "actual_overage_gbp": p_ovg_gbp,
            "avoided_cost_usd": p_avoided_usd,
            "avoided_cost_gbp": p_avoided_gbp,
            "estimated_cost_usd": p_avoided_usd,
            "estimated_cost_gbp": p_avoided_gbp,
            "total_input_tokens": p_total_input,
            "prompt_tokens_uncached": p_uncached,
            "cached_tokens": p_cached,
            "total_output_tokens": p_output,
            "cache_hit_ratio_pct": p_cache_pct,
            "branches": branches_list,
        })

    # Sort projects descending by total processed tokens
    projects.sort(
        key=lambda p: p["total_input_tokens"] + p["total_output_tokens"],
        reverse=True,
    )

    # Collect all flat turns if not passed
    flat_turns = all_raw_turns or []
    if not flat_turns:
        for c in conversation_summaries:
            flat_turns.extend(c.get("turns", []))


    # Quota Calculations (5h Rolling, 1w Rolling, Thursday Weekly Cycle, and Monthly Billing Horizon)
    ref_dt = reference_time or datetime.datetime.now(datetime.timezone.utc)
    if ref_dt.tzinfo is None:
        ref_dt = ref_dt.replace(tzinfo=datetime.timezone.utc)

    rolling_5h = compute_rolling_window_telemetry(flat_turns, window_hours=5.0, reference_time=ref_dt, pricing_models=pricing_models)
    recovery_schedule = compute_window_recovery_schedule(flat_turns, window_hours=5.0, reference_time=ref_dt, limit=5, pricing_models=pricing_models)
    rolling_5h["recovery_schedule"] = recovery_schedule

    rolling_1w = compute_rolling_window_telemetry(flat_turns, window_hours=168.0, reference_time=ref_dt, pricing_models=pricing_models)
    peaks = compute_historical_peaks(flat_turns, pricing_models=pricing_models)

    # Dynamic Weekly Cycle Bounds (temporal subscription or live quota)
    explicit_reset = None
    if live_quota and live_quota.get("available") and live_quota.get("gemini_weekly", {}).get("reset_time"):
        explicit_reset = parse_timestamp(live_quota["gemini_weekly"]["reset_time"])

    weekly_cycle_bounds = get_weekly_cycle_bounds(ref_dt, explicit_reset_dt=explicit_reset)
    weekly_cycle_start = parse_timestamp(weekly_cycle_bounds["cycle_start_utc"])
    weekly_cycle = compute_rolling_window_telemetry(
        flat_turns,
        reference_time=ref_dt,
        pricing_models=pricing_models,
        start_time=weekly_cycle_start,
    )
    weekly_cycle.update(weekly_cycle_bounds)

    temporal_resolver = get_temporal_resolver()
    sub_cfg = temporal_resolver.resolve_subscription(ref_dt)
    gemini_multiplier = temporal_resolver.get_capacity_multiplier(ref_dt, provider="gemini")
    cg_multiplier = temporal_resolver.get_capacity_multiplier(ref_dt, provider="claude_gpt")

    quota_limits = sub_cfg.get("quota_limits", {})
    burst_limit = quota_limits.get("burst_5h_tokens", 168000000)
    gemini_5h_capacity_usd = quota_limits.get("gemini_5h_capacity_usd", 20.00) * gemini_multiplier
    gemini_weekly_capacity_usd = quota_limits.get("gemini_weekly_capacity_usd", 129.00) * gemini_multiplier
    cg_5h_capacity_usd = quota_limits.get("claude_5h_capacity_usd", 10.00) * cg_multiplier
    cg_weekly_capacity_usd = quota_limits.get("claude_weekly_capacity_usd", 35.00) * cg_multiplier
    cents_per_credit = sub_cfg.get("cents_per_credit", 1.0)

    # Step-level quota partitioning (ADR-019):
    # Evaluates get_provider_quota_track strictly per step/turn to prevent cross-track contamination in multi-agent swarms
    gemini_turns = [
        t for t in flat_turns
        if get_provider_quota_track(t.get("model_id"), pricing_models) == "gemini"
    ]
    claude_gpt_turns = [
        t for t in flat_turns
        if get_provider_quota_track(t.get("model_id"), pricing_models) == "claude_gpt"
    ]

    # --- Track 1: Gemini Models ---
    gemini_5h = compute_rolling_window_telemetry(
        gemini_turns, window_hours=5.0, reference_time=ref_dt, pricing_models=pricing_models
    )
    gemini_5h["recovery_schedule"] = compute_window_recovery_schedule(
        gemini_turns, window_hours=5.0, reference_time=ref_dt, limit=5, pricing_models=pricing_models
    )
    gemini_5h["capacity_usd"] = gemini_5h_capacity_usd
    gemini_5h_used_pct = round(min(100.0, (gemini_5h["imputed_value_usd"] / gemini_5h_capacity_usd) * 100.0), 1) if gemini_5h_capacity_usd > 0 else 0.0
    gemini_5h["used_pct"] = gemini_5h_used_pct
    gemini_5h["remaining_pct"] = round(max(0.0, 100.0 - gemini_5h_used_pct), 1)

    gemini_weekly = compute_rolling_window_telemetry(
        gemini_turns,
        reference_time=ref_dt,
        pricing_models=pricing_models,
        start_time=weekly_cycle_start,
    )
    gemini_weekly.update(weekly_cycle_bounds)
    gemini_weekly["reset_display"] = weekly_cycle_bounds["reset_display"]
    gemini_weekly["message"] = f"It will fully refresh in {weekly_cycle_bounds['human_remaining']}"
    gemini_weekly["capacity_usd"] = gemini_weekly_capacity_usd
    gemini_weekly_used_pct = round(min(100.0, (gemini_weekly["imputed_value_usd"] / gemini_weekly_capacity_usd) * 100.0), 1) if gemini_weekly_capacity_usd > 0 else 0.0
    gemini_weekly["used_pct"] = gemini_weekly_used_pct
    gemini_weekly["remaining_pct"] = round(max(0.0, 100.0 - gemini_weekly_used_pct), 1)

    # --- Track 2: Claude & GPT Models ---
    cg_5h = compute_rolling_window_telemetry(
        claude_gpt_turns, window_hours=5.0, reference_time=ref_dt, pricing_models=pricing_models
    )
    cg_5h["recovery_schedule"] = compute_window_recovery_schedule(
        claude_gpt_turns, window_hours=5.0, reference_time=ref_dt, limit=5, pricing_models=pricing_models
    )
    cg_5h["capacity_usd"] = cg_5h_capacity_usd
    cg_5h_used_pct = round(min(100.0, (cg_5h["imputed_value_usd"] / cg_5h_capacity_usd) * 100.0), 1) if cg_5h_capacity_usd > 0 else 0.0
    cg_5h["used_pct"] = cg_5h_used_pct
    cg_5h["remaining_pct"] = round(max(0.0, 100.0 - cg_5h_used_pct), 1)

    # Claude/GPT 7-day (168h) rolling window
    cg_weekly = compute_rolling_window_telemetry(
        claude_gpt_turns, window_hours=168.0, reference_time=ref_dt, pricing_models=pricing_models
    )
    # Determine Claude/GPT rolling age-out horizon
    cg_window_start = ref_dt - datetime.timedelta(days=7)
    cg_active_turns = []
    for t in claude_gpt_turns:
        t_dt = parse_timestamp(t.get("timestamp"))
        if t_dt and cg_window_start <= t_dt <= ref_dt:
            cg_active_turns.append(t_dt)

    if cg_active_turns:
        latest_cg_turn = max(cg_active_turns)
        full_refresh_dt = latest_cg_turn + datetime.timedelta(days=7)
        cg_diff = max(datetime.timedelta(0), full_refresh_dt - ref_dt)
        cg_sec = int(cg_diff.total_seconds())
        cg_days = cg_sec // 86400
        cg_hours = (cg_sec % 86400) // 3600
        cg_mins = (cg_sec % 3600) // 60
        cg_d_txt = f"{cg_days} day" if cg_days == 1 else f"{cg_days} days"
        cg_h_txt = f"{cg_hours} hour" if cg_hours == 1 else f"{cg_hours} hours"
        cg_m_txt = f"{cg_mins} min" if cg_mins == 1 else f"{cg_mins} mins"
        cg_human = f"{cg_d_txt}, {cg_h_txt}" if cg_days > 0 else f"{cg_h_txt}, {cg_m_txt}"
        cg_reset_disp = full_refresh_dt.strftime("%d %b %Y, %H:%M UTC")
        cg_message = f"It will fully refresh in {cg_human}"
    else:
        cg_days = 0
        cg_hours = 0
        cg_mins = 0
        cg_human = "0 hours"
        cg_reset_disp = "Fully refreshed"
        cg_message = "Fully refreshed (100% capacity available)"

    cg_weekly["days_remaining"] = cg_days
    cg_weekly["hours_remaining"] = cg_hours
    cg_weekly["minutes_remaining"] = cg_mins
    cg_weekly["human_remaining"] = cg_human
    cg_weekly["reset_display"] = cg_reset_disp
    cg_weekly["message"] = cg_message
    cg_weekly["capacity_usd"] = cg_weekly_capacity_usd
    cg_weekly_used_pct = round(min(100.0, (cg_weekly["imputed_value_usd"] / cg_weekly_capacity_usd) * 100.0), 1) if cg_weekly_capacity_usd > 0 else 0.0
    cg_weekly["used_pct"] = cg_weekly_used_pct
    cg_weekly["remaining_pct"] = round(max(0.0, 100.0 - cg_weekly_used_pct), 1)

    # Optional Live Desktop Indicator Synchronization (ADR-021)
    desktop_sync_active = False
    if live_quota and live_quota.get("available"):
        desktop_sync_active = True
        if live_quota.get("gemini_weekly"):
            gw = live_quota["gemini_weekly"]
            gemini_weekly["live_desktop_sync"] = True
            gemini_weekly["remaining_pct"] = gw["remaining_pct"]
            gemini_weekly["used_pct"] = gw["used_pct"]
            gemini_weekly["reset_time"] = gw["reset_time"]
            if gw.get("description"):
                gemini_weekly["message"] = gw["description"]
        if live_quota.get("gemini_5h"):
            g5 = live_quota["gemini_5h"]
            gemini_5h["live_desktop_sync"] = True
            gemini_5h["remaining_pct"] = g5["remaining_pct"]
            gemini_5h["used_pct"] = g5["used_pct"]
            gemini_5h["reset_time"] = g5["reset_time"]
            if g5.get("description"):
                gemini_5h["message"] = g5["description"]
        if live_quota.get("claude_weekly"):
            cw = live_quota["claude_weekly"]
            cg_weekly["live_desktop_sync"] = True
            cg_weekly["remaining_pct"] = cw["remaining_pct"]
            cg_weekly["used_pct"] = cw["used_pct"]
            cg_weekly["reset_time"] = cw["reset_time"]
        if live_quota.get("claude_5h"):
            c5 = live_quota["claude_5h"]
            cg_5h["live_desktop_sync"] = True
            cg_5h["remaining_pct"] = c5["remaining_pct"]
            cg_5h["used_pct"] = c5["used_pct"]
            cg_5h["reset_time"] = c5["reset_time"]

    exhaustion_alarm = compute_exhaustion_alarm_state(
        gemini_weekly_used_pct=gemini_weekly.get("used_pct", 0.0),
        gemini_weekly_remaining_pct=gemini_weekly.get("remaining_pct", 100.0),
        gemini_5h_used_pct=gemini_5h.get("used_pct", 0.0),
        cg_weekly_remaining_pct=cg_weekly.get("remaining_pct", 100.0),
        weekly_cycle_bounds=weekly_cycle_bounds,
    )

    runway = compute_quota_runway(
        gemini_weekly=gemini_weekly,
        weekly_cycle_bounds=weekly_cycle_bounds,
        gemini_5h=gemini_5h,
        reference_time=ref_dt,
    )

    providers_quotas = {
        "desktop_sync": {
            "active": desktop_sync_active,
            "description": live_quota.get("description", "") if live_quota else "",
        },
        "gemini": {
            "track": "gemini",
            "display_name": "Gemini Models",
            "credit_spillover": True,
            "five_hour": gemini_5h,
            "weekly": gemini_weekly,
            "exhaustion_alarm": exhaustion_alarm,
            "runway": runway,
        },
        "claude_gpt": {
            "track": "claude_gpt",
            "display_name": "Claude and GPT Models",
            "credit_spillover": False,
            "five_hour": cg_5h,
            "weekly": cg_weekly,
        },
    }

    # Map conversation IDs to metadata for window session attribution (M3)
    convo_meta_map = {
        (c.get("convo_id") or c.get("conversation_id")): {
            "title": c.get("title", "Untitled Session"),
            "workspace_name": c.get("workspace_name", "Unknown Workspace"),
            "workspace_path": c.get("workspace_path", ""),
            "git_branch": c.get("git_branch", "main"),
        }
        for c in conversation_summaries
        if (c.get("convo_id") or c.get("conversation_id"))
    }

    def _decorate_sessions(sessions: List[Dict[str, Any]]) -> None:
        for s in sessions:
            cid = s.get("convo_id")
            meta = convo_meta_map.get(cid, {})
            s["title"] = meta.get("title", "Untitled Session")
            s["workspace_name"] = meta.get("workspace_name", "Unknown Workspace")
            s["workspace_path"] = meta.get("workspace_path", "")
            s["git_branch"] = meta.get("git_branch", "main")

    _decorate_sessions(rolling_5h.get("active_sessions_5h", []))
    _decorate_sessions(gemini_5h.get("active_sessions_5h", []))
    _decorate_sessions(cg_5h.get("active_sessions_5h", []))

    # Monthly Billing Horizon (anchored to configured renewal_day)
    renewal_day = sub_cfg.get("renewal_day", 13)
    monthly_plan_price_gbp = sub_cfg.get("monthly_price_gbp", 79.99)
    monthly_plan_price_usd = sub_cfg.get("monthly_price_usd", 99.99)
    monthly_billing_bounds = get_monthly_billing_bounds(
        ref_dt,
        billing_day=renewal_day,
        plan_price_gbp=monthly_plan_price_gbp,
        plan_price_usd=monthly_plan_price_usd,
    )
    monthly_cycle_start = parse_timestamp(monthly_billing_bounds["cycle_start_utc"])
    monthly_telemetry = compute_rolling_window_telemetry(
        flat_turns,
        reference_time=ref_dt,
        pricing_models=pricing_models,
        start_time=monthly_cycle_start,
    )
    monthly_billing_bounds["total_processed_tokens"] = monthly_telemetry["total_processed_tokens"]
    monthly_billing_bounds["turn_count"] = monthly_telemetry["turn_count"]
    monthly_billing_bounds["cache_hit_ratio_pct"] = monthly_telemetry["cache_hit_ratio_pct"]
    monthly_billing_bounds["imputed_value_usd"] = monthly_telemetry["imputed_value_usd"]
    cents_per_credit = sub_cfg.get("cents_per_credit", 1.0)

    currency_cfg = load_currency_config()
    usd_to_gbp_fx = currency_cfg.get("usd_to_gbp_fx_rate", 0.79)
    pack_cfg = currency_cfg.get("credit_pack", {})
    cost_per_credit_gbp = pack_cfg.get("cost_per_credit_gbp", 0.009596)

    # Auto-extract log exhaustion intervals if not supplied
    if exhaustion_intervals is None:
        try:
            from src.log_reader import extract_exhaustion_intervals
            exhaustion_intervals = extract_exhaustion_intervals()
        except Exception:
            exhaustion_intervals = []

    # Two-pointer sliding window overage detection & model credit burn attribution
    valid_turns = []
    for t in flat_turns:
        t_dt = parse_timestamp(t.get("timestamp"))
        if t_dt:
            tok = t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0) + t.get("output_tokens_total", 0)
            valid_turns.append((t_dt, tok, t))

    valid_turns.sort(key=lambda x: x[0])

    window_5h = datetime.timedelta(hours=5)
    left = 0
    cur_sum = 0
    total_ai_credits_burned = 0.0
    total_credit_burn_usd = 0.0
    total_credit_burn_gbp = 0.0

    hourly_activity_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "hour_timestamp": "",
        "hour_display": "",
        "turns_count": 0,
        "credits_burned": 0.0,
        "credit_burn_usd": 0.0,
        "credit_burn_gbp": 0.0,
        "models": defaultdict(int),
    })

    recent_overage = False
    ref_dt = reference_time or datetime.datetime.now(datetime.timezone.utc)
    if ref_dt.tzinfo is None:
        ref_dt = ref_dt.replace(tzinfo=datetime.timezone.utc)

    ledger_intervals = [inv for inv in (exhaustion_intervals or []) if inv.get("from_ledger")]
    live_intervals = [inv for inv in (exhaustion_intervals or []) if not inv.get("from_ledger")]

    # 1. Populate confirmed deductions from persistent ledger
    for inv in ledger_intervals:
        start_val = inv.get("start")
        if isinstance(start_val, str):
            start_val = parse_timestamp(start_val)
        h_key = inv.get("hour_timestamp") or (start_val.strftime("%Y-%m-%dT%H:00:00Z") if start_val else "")
        h_disp = inv.get("hour_display") or (start_val.strftime("%d %b %Y, %H:00:00 UTC") if start_val else "")
        h_entry = hourly_activity_map[h_key]
        h_entry["hour_timestamp"] = h_key
        h_entry["hour_display"] = h_disp
        h_entry["turns_count"] = inv.get("turns_count", 0)
        h_entry["credits_burned"] = inv.get("credits_burned", 0)
        h_entry["credit_burn_usd"] = inv.get("credit_burn_usd", 0.0)
        h_entry["credit_burn_gbp"] = inv.get("credit_burn_gbp", 0.0)
        if inv.get("models"):
            for m_name, m_cnt in inv["models"].items():
                h_entry["models"][m_name] += m_cnt
        total_ai_credits_burned += inv.get("credits_burned", 0)
        total_credit_burn_usd += inv.get("credit_burn_usd", 0.0)
        total_credit_burn_gbp += inv.get("credit_burn_gbp", 0.0)

    # 2. Process any live non-ledger exhaustion intervals turn-by-turn
    for right in range(len(valid_turns)):
        t_dt, tok, t = valid_turns[right]
        cur_sum += tok
        while valid_turns[right][0] - valid_turns[left][0] > window_5h:
            cur_sum -= valid_turns[left][1]
            left += 1

        in_live_interval = any(
            inv.get("start") and inv.get("end") and inv["start"] <= t_dt <= inv["end"]
            for inv in live_intervals
        )

        if in_live_interval and get_provider_quota_track(t.get("model_id"), pricing_models) == "gemini":
            mid = str(t.get("model_id", "unknown"))
            burn = calculate_credit_burn(
                mid,
                turns_count=1,
                pricing_models=pricing_models,
                cents_per_credit=cents_per_credit,
                cost_per_credit_gbp=cost_per_credit_gbp,
            )
            credits = burn["credits"]
            usd = burn["credit_burn_usd"]
            gbp = burn["credit_burn_gbp"]

            total_ai_credits_burned += credits
            total_credit_burn_usd += usd
            total_credit_burn_gbp += gbp

            if ref_dt - datetime.timedelta(hours=2) <= t_dt <= ref_dt:
                recent_overage = True

            hour_key = t_dt.strftime("%Y-%m-%dT%H:00:00Z")
            hour_display = t_dt.strftime("%d %b %Y, %H:00:00 UTC")
            h_entry = hourly_activity_map[hour_key]
            h_entry["hour_timestamp"] = hour_key
            h_entry["hour_display"] = hour_display
            h_entry["turns_count"] += 1
            h_entry["credits_burned"] += credits
            h_entry["credit_burn_usd"] += usd
            h_entry["credit_burn_gbp"] += gbp
            h_entry["models"][get_model_display_name(mid, pricing_models)] += 1

    # Format hourly activity sorted descending
    hourly_credit_activity = []
    for h_key in sorted(hourly_activity_map.keys(), reverse=True):
        item = hourly_activity_map[h_key]
        item["credits_burned"] = int(round(item["credits_burned"]))
        item["credit_burn_usd"] = round(item["credit_burn_usd"], 2)
        item["credit_burn_gbp"] = round(item["credit_burn_gbp"], 2)
        item["models"] = dict(item["models"])
        hourly_credit_activity.append(item)

    # Status determination (anchored to active 429 log interval, live desktop quota, or M16 exhaustion alarm)
    active_log_interval = any(
        inv.get("start") and inv["start"] <= ref_dt and (inv.get("end") is None or ref_dt <= inv["end"])
        for inv in (exhaustion_intervals or [])
    )
    is_near_burst_limit = rolling_5h.get("total_processed_tokens", 0) >= burst_limit

    # Check live desktop quota for weekly exhaustion (ADR-028)
    live_weekly_exhausted = False
    if live_quota and live_quota.get("available"):
        gw_live = live_quota.get("gemini_weekly", {})
        if gw_live.get("remaining_pct", 100.0) <= 0.1:
            live_weekly_exhausted = True

    if active_log_interval:
        subscription_status = "BURNING_AI_CREDITS"
    elif live_weekly_exhausted or exhaustion_alarm.get("gemini_weekly_exhausted"):
        subscription_status = "WEEKLY_EXHAUSTED"
    elif recent_overage:
        subscription_status = "RECOVERED_COOLDOWN"
    else:
        subscription_status = "SAFE_IN_QUOTA"

    serialized_intervals = []
    for inv in (exhaustion_intervals or []):
        serialized_intervals.append({
            "start": inv["start"].isoformat() if hasattr(inv.get("start"), "isoformat") else inv.get("start"),
            "end": inv["end"].isoformat() if hasattr(inv.get("end"), "isoformat") else inv.get("end"),
            "events_count": inv.get("events_count", 1),
            "code": inv.get("code", 429),
            "reason": inv.get("reason", "RESOURCE_EXHAUSTED"),
        })

    sub_price_gbp = sub_cfg.get("monthly_price_gbp", 18.99)
    sub_price_usd = sub_cfg.get("monthly_price_usd", 19.99)
    base_pack_credits = pack_cfg.get("credits", 2500)
    bank_credits_burned = int(round(total_ai_credits_burned))
    single_pack_price_gbp = pack_cfg.get("price_gbp", 23.99)
    single_pack_price_usd = pack_cfg.get("price_usd", 25.00)
    pack_size = pack_cfg.get("pack_size", base_pack_credits)

    # Check if persistent ledger specifies packs_purchased
    ledger_pack = {}
    if exhaustion_intervals:
        for inv in exhaustion_intervals:
            if inv.get("from_ledger") and inv.get("prepaid_pack"):
                ledger_pack = inv["prepaid_pack"]
                break

    explicit_packs = pack_cfg.get("packs_purchased") or ledger_pack.get("packs_purchased")
    if pack_cfg.get("auto_reload") and pack_size > 0:
        import math
        needed_packs = math.ceil(bank_credits_burned / pack_size) if bank_credits_burned > 0 else 1
        packs_count = max(int(explicit_packs) if explicit_packs else 1, needed_packs)
        bank_total_credits = packs_count * pack_size
        total_pack_price_gbp = round(packs_count * single_pack_price_gbp, 2)
        total_pack_price_usd = round(packs_count * single_pack_price_usd, 2)
    else:
        packs_count = int(explicit_packs) if explicit_packs else 1
        bank_total_credits = packs_count * pack_size
        total_pack_price_gbp = round(packs_count * single_pack_price_gbp, 2)
        total_pack_price_usd = round(packs_count * single_pack_price_usd, 2)
    bank_credits_rem = max(0, bank_total_credits - bank_credits_burned)

    cycle_tokens = monthly_billing_bounds.get("total_processed_tokens", 0)
    cycle_turns = monthly_billing_bounds.get("turn_count", 0)
    cycle_imputed_usd = monthly_billing_bounds.get("imputed_value_usd", 0.0)
    cycle_imputed_gbp = round(cycle_imputed_usd * usd_to_gbp_fx, 2)
    cycle_roi = round(cycle_imputed_gbp / sub_price_gbp, 1) if sub_price_gbp > 0 else 1.0

    subagent_metrics = compute_subagent_metrics(flat_turns, pricing_models)
    daily_velocity = compute_daily_velocity(
        gemini_turns,
        weekly_cycle_start=weekly_cycle_start,
        reference_time=ref_dt,
        pricing_models=pricing_models,
        weekly_capacity_usd=gemini_weekly_capacity_usd,
    )

    # What-If Workload Simulator & Stress Planner Presets (M21 / ADR-035)
    sim_quota_state = {
        "gemini": {
            "rolling_5h_used_usd": gemini_5h.get("imputed_value_usd", 0.0),
            "weekly_used_usd": gemini_weekly.get("imputed_value_usd", 0.0),
            "credits_remaining": bank_credits_rem,
        },
        "claude_gpt": {
            "rolling_5h_used_usd": cg_5h.get("imputed_value_usd", 0.0),
            "weekly_used_usd": cg_weekly.get("imputed_value_usd", 0.0),
        },
    }
    simulator_presets = compute_simulation_presets(
        initial_quota_state=sim_quota_state,
        pricing_models=pricing_models,
        plan_config=sub_cfg,
        fx_rate=usd_to_gbp_fx,
    )

    # Cache coaching & cross-provider model-flip diagnostics (M5)
    cache_coaching = compute_cache_coaching_metrics(
        conversation_summaries,
        pricing_models=pricing_models,
        usd_to_gbp_fx=usd_to_gbp_fx,
    )

    return {
        "summary": {
            "total_conversations": total_conversations,
            "discovered_databases": discovered_databases if discovered_databases is not None else total_conversations,
            "scanned_databases": scanned_databases if scanned_databases is not None else total_conversations,
            "total_turns": total_turns,
            "total_input_tokens": total_input,
            "prompt_tokens_uncached": total_uncached,
            "cached_tokens": total_cached,
            "total_output_tokens": total_output,
            "thinking_tokens": total_thinking,
            "answer_tokens": total_answer,
            "cache_hit_ratio_pct": round(overall_cache_hit_ratio, 2),
            "cache_coaching": cache_coaching,
            "total_imputed_value_usd": round(total_imputed_cost, 4),
            "total_imputed_value_gbp": round(total_imputed_cost * usd_to_gbp_fx, 4),
            "total_avoided_cost_usd": round(total_imputed_cost, 4),
            "total_avoided_cost_gbp": round(total_imputed_cost * usd_to_gbp_fx, 4),
            "subscription_covered_turns": sum(p["subscription_covered_turns"] for p in projects),
            "subscription_covered_pct": round(sum(p["subscription_covered_turns"] for p in projects) / total_turns * 100.0, 1) if total_turns > 0 else 100.0,
            "total_overage_turns": sum(p["overage_turns"] for p in projects),
            "total_ai_credits_burned": bank_credits_burned,
            "actual_overage_credits": bank_credits_burned,
            "total_credit_burn_usd": round(total_credit_burn_usd, 2),
            "actual_overage_usd": round(total_credit_burn_usd, 2),
            "total_credit_burn_gbp": round(total_credit_burn_gbp, 2),
            "actual_overage_gbp": round(total_credit_burn_gbp, 2),
            "currency_default": currency_cfg.get("default", "GBP"),
            "cost_per_credit_gbp": cost_per_credit_gbp,
            "usd_to_gbp_fx_rate": usd_to_gbp_fx,
            "subscription_status": subscription_status,
            "tier": sub_cfg.get("tier", "pro"),
            "subscription_name": sub_cfg.get("name", "Google One AI Premium (Antigravity Pro)"),
            "monthly_subscription_price_gbp": sub_price_gbp,
            "monthly_subscription_price_usd": sub_price_usd,
            "gemini_capacity_multiplier": gemini_multiplier,
            "claude_capacity_multiplier": cg_multiplier,
            "subscription_history": temporal_resolver.subscription_history,
            "promotions": temporal_resolver.promotions,
            "active_promotions": temporal_resolver.resolve_promotions(ref_dt, provider="all"),
            "temporal_provenance": temporal_resolver.get_provenance_summary(ref_dt),
            "use_ai_credits": sub_cfg.get("use_ai_credits", True),
            "cents_per_credit": cents_per_credit,
            "burst_5h_limit_tokens": burst_limit,
            "is_near_burst_limit": is_near_burst_limit,
            "weekly_reset_utc": weekly_cycle_bounds["cycle_end_utc"],
            "weekly_reset_display": weekly_cycle_bounds["reset_display"],
            "weekly_reset_human": weekly_cycle_bounds["human_remaining"],
            "monthly_renewal_utc": monthly_billing_bounds["renewal_date"],
            "monthly_renewal_display": monthly_billing_bounds["renewal_display"],
            "monthly_renewal_human": monthly_billing_bounds["human_remaining"],
            "monthly_billing_day": renewal_day,
            "credit_bank_total": bank_total_credits,
            "packs_purchased": packs_count,
            "single_pack_price_gbp": single_pack_price_gbp,
            "single_pack_price_usd": single_pack_price_usd,
            "credit_pack_price_gbp": total_pack_price_gbp,
            "credit_pack_price_usd": total_pack_price_usd,
            "credits_remaining": bank_credits_rem,
            "credit_bank_remaining_gbp": round(bank_credits_rem * cost_per_credit_gbp, 2),
            "credit_bank_remaining_usd": round(bank_credits_rem * (cents_per_credit / 100.0), 2),
            "credit_bank_burn_pct": round((bank_credits_burned / bank_total_credits) * 100.0, 1) if bank_total_credits > 0 else 0.0,
            "monthly_cycle_tokens": cycle_tokens,
            "monthly_cycle_turns": cycle_turns,
            "monthly_cycle_imputed_value_usd": cycle_imputed_usd,
            "monthly_cycle_imputed_value_gbp": cycle_imputed_gbp,
            "monthly_subscription_roi": cycle_roi,
            "subagent_metrics": subagent_metrics,
            # Backward-compatible aliases:
            "monthly_plan_credits": bank_total_credits,
            "monthly_credits_burned": bank_credits_burned,
            "monthly_credits_remaining": bank_credits_rem,
        },
        "quotas": {
            "rolling_5h": rolling_5h,
            "rolling_1w": rolling_1w,
            "weekly_cycle": weekly_cycle,
            "monthly_billing": monthly_billing_bounds,
            "historical_peaks": peaks,
            "providers": providers_quotas,
            "runway": runway,
            "daily_velocity": daily_velocity,
        },
        "temporal": temporal_resolver.get_provenance_summary(ref_dt),
        "simulator_presets": simulator_presets,
        "simulations": simulator_presets,
        "currency": currency_cfg,
        "hourly_credit_activity": hourly_credit_activity,
        "exhaustion_intervals": serialized_intervals,
        "workspaces": list(by_workspace.values()),
        "projects": projects,
        "conversations": conversation_summaries,
    }
