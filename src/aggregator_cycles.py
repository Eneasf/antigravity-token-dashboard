"""
Cycle bounds, weekly resets, monthly billing horizons, quota runway, and daily velocity.
"""

from collections import defaultdict
import datetime
import math
from typing import Any, Dict, List, Optional, Tuple

from src.aggregator_pricing import (
    compute_turn_cost,
    get_model_rates,
    parse_timestamp,
)


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
            'p10_exhaustion_hours': 504.0,
            'p50_exhaustion_hours': 336.0,
            'p90_exhaustion_hours': 252.0,
            'prob_exhaust_before_reset_pct': 0.0,
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

    # 5h Burst Governor (ADR-082 discrete reset epoch priority)
    burst_used_pct = float(gemini_5h.get("used_pct", 0.0)) if gemini_5h else 0.0
    burst_rem_pct = float(gemini_5h.get("remaining_pct", 100.0)) if gemini_5h else 100.0
    rec_schedule = gemini_5h.get("recovery_schedule", []) if gemini_5h else []
    seconds_to_cooldown = 0
    if gemini_5h and gemini_5h.get("reset_time"):
        reset_dt = parse_timestamp(gemini_5h.get("reset_time"))
        if reset_dt and reset_dt > ref_dt:
            seconds_to_cooldown = max(0, int((reset_dt - ref_dt).total_seconds()))
    if seconds_to_cooldown <= 0 and rec_schedule:
        seconds_to_cooldown = int(
            rec_schedule[0].get("seconds_until")
            or (rec_schedule[0].get("minutes_remaining", 0) * 60)
            or 0
        )
    burst_cooldown_active = burst_rem_pct <= 0.1 or (burst_used_pct >= 99.0 and seconds_to_cooldown > 0)

    # Empirical Bootstrap / Quantile Corridor (p10/p50/p90 exhaustion hours & reset breach probability)
    hours_remaining = max(0.1, remaining_seconds / 3600.0)
    if weekly_rem <= 0.1:
        p10_exhaustion_hours = 0.0
        p50_exhaustion_hours = 0.0
        p90_exhaustion_hours = 0.0
        prob_exhaust_before_reset_pct = 100.0
    elif quota_consumed_pct == 0:
        p10_exhaustion_hours = round(hours_remaining * 3.0, 1)
        p50_exhaustion_hours = round(hours_remaining * 2.0, 1)
        p90_exhaustion_hours = round(hours_remaining * 1.5, 1)
        prob_exhaust_before_reset_pct = 0.0
    else:
        eff_daily = (quota_consumed_pct + (k_pseudo_days * prior_daily_rate)) / (elapsed_days_float + k_pseudo_days)
        base_hourly = max(0.01, eff_daily / 24.0)
        p10_exhaustion_hours = round(weekly_rem / (base_hourly * 0.65), 1)
        p50_exhaustion_hours = round(weekly_rem / base_hourly, 1)
        p90_exhaustion_hours = round(weekly_rem / (base_hourly * 1.45), 1)
        spread = max(1.0, (p10_exhaustion_hours - p90_exhaustion_hours) * 0.39)
        z_score = (hours_remaining - p50_exhaustion_hours) / spread
        prob_exhaust_before_reset_pct = round(
            max(0.0, min(100.0, 50.0 * (1.0 + math.erf(z_score / math.sqrt(2.0))))),
            1,
        )

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
        "p10_exhaustion_hours": p10_exhaustion_hours,
        "p50_exhaustion_hours": p50_exhaustion_hours,
        "p90_exhaustion_hours": p90_exhaustion_hours,
        "prob_exhaust_before_reset_pct": prob_exhaust_before_reset_pct,
    }
