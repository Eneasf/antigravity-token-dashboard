"""
Provider quota silos (Track 1 & 2), active session decoration, and credit bank reconciliation.
"""

from collections import defaultdict
import datetime
import math
from typing import Any, Dict, List, Optional, Set, Tuple

from src.aggregator_cycles import (
    compute_exhaustion_alarm_state,
    compute_quota_runway,
)
from src.aggregator_pricing import (
    calculate_credit_burn,
    get_model_display_name,
    get_provider_quota_track,
    load_currency_config,
    parse_timestamp,
)
from src.aggregator_windows import (
    compute_rolling_window_telemetry,
    compute_window_recovery_schedule,
)
from src.temporal import get_temporal_resolver, load_raw_pricing


def compute_provider_quota_silos(
    flat_turns: List[Dict[str, Any]],
    ref_dt: datetime.datetime,
    pricing_models: Dict[str, Any],
    weekly_cycle_bounds: Dict[str, Any],
    weekly_cycle_start: Optional[datetime.datetime],
    live_quota: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute dual-track provider quota silos (ADR-019 / ADR-028).
    Track 1: Gemini Models (5-hour rolling + weekly reset cycle + exhaustion alarms)
    Track 2: Claude & GPT Models (5-hour rolling + 7-day rolling window)
    """
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
    g5_start_time = None
    if live_quota and live_quota.get("available") and live_quota.get("gemini_5h", {}) and live_quota["gemini_5h"].get("reset_time"):
        g5_reset_dt = parse_timestamp(live_quota["gemini_5h"]["reset_time"])
        if g5_reset_dt and g5_reset_dt > ref_dt:
            g5_start_time = max(
                ref_dt - datetime.timedelta(hours=5.0),
                g5_reset_dt - datetime.timedelta(hours=5.0),
            )

    gemini_5h = compute_rolling_window_telemetry(
        gemini_turns,
        window_hours=5.0,
        reference_time=ref_dt,
        pricing_models=pricing_models,
        start_time=g5_start_time,
    )
    gemini_5h["recovery_schedule"] = compute_window_recovery_schedule(
        gemini_turns, window_hours=5.0, reference_time=ref_dt, limit=5, pricing_models=pricing_models
    )
    gemini_5h["capacity_usd"] = gemini_5h_capacity_usd
    g5_burn_usd = gemini_5h.get("quota_burn_usd", gemini_5h["imputed_value_usd"])
    gemini_5h_used_pct = round(min(100.0, (g5_burn_usd / gemini_5h_capacity_usd) * 100.0), 1) if gemini_5h_capacity_usd > 0 else 0.0
    gemini_5h["used_pct"] = gemini_5h_used_pct
    gemini_5h["remaining_pct"] = round(max(0.0, 100.0 - gemini_5h_used_pct), 1)

    # Discrete 5-Hour Reset Epoch Anchor (ADR-082)
    if gemini_turns and gemini_5h_used_pct > 0:
        window_start_ts = (g5_start_time or (ref_dt - datetime.timedelta(hours=5.0))).timestamp()
        turns_in_window = [
            t for t in gemini_turns
            if (parse_timestamp(t.get("timestamp")) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)).timestamp() >= window_start_ts
        ]
        if turns_in_window:
            earliest_dt = min(
                parse_timestamp(t.get("timestamp"))
                for t in turns_in_window
                if parse_timestamp(t.get("timestamp")) is not None
            )
            reset_dt = earliest_dt + datetime.timedelta(hours=5.0)
            rem_sec = max(0, int((reset_dt - ref_dt).total_seconds()))
            rem_min = rem_sec // 60
            gemini_5h["reset_time"] = reset_dt.isoformat()
            if rem_min >= 60:
                h = rem_min // 60
                m = rem_min % 60
                rem_str = f"{h} hour{'s' if h != 1 else ''}, {m} minute{'s' if m != 1 else ''}" if m else f"{h} hour{'s' if h != 1 else ''}"
            else:
                rem_str = f"{rem_min} minute{'s' if rem_min != 1 else ''}"
            gemini_5h["message"] = f"You have used some of your 5-hour limit, it will fully refresh in {rem_str}."
        else:
            gemini_5h["message"] = "Fully refreshed (100% capacity available)"
    else:
        gemini_5h["message"] = "Fully refreshed (100% capacity available)"

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
    gw_burn_usd = gemini_weekly.get("quota_burn_usd", gemini_weekly["imputed_value_usd"])
    gemini_weekly_used_pct = round(min(100.0, (gw_burn_usd / gemini_weekly_capacity_usd) * 100.0), 1) if gemini_weekly_capacity_usd > 0 else 0.0
    gemini_weekly["used_pct"] = gemini_weekly_used_pct
    gemini_weekly["remaining_pct"] = round(max(0.0, 100.0 - gemini_weekly_used_pct), 1)

    # --- Track 2: Claude & GPT Models ---
    c5_start_time = None
    if live_quota and live_quota.get("available") and live_quota.get("claude_5h", {}) and live_quota["claude_5h"].get("reset_time"):
        c5_reset_dt = parse_timestamp(live_quota["claude_5h"]["reset_time"])
        if c5_reset_dt and c5_reset_dt > ref_dt:
            c5_start_time = max(
                ref_dt - datetime.timedelta(hours=5.0),
                c5_reset_dt - datetime.timedelta(hours=5.0),
            )

    cg_5h = compute_rolling_window_telemetry(
        claude_gpt_turns,
        window_hours=5.0,
        reference_time=ref_dt,
        pricing_models=pricing_models,
        start_time=c5_start_time,
    )
    cg_5h["recovery_schedule"] = compute_window_recovery_schedule(
        claude_gpt_turns, window_hours=5.0, reference_time=ref_dt, limit=5, pricing_models=pricing_models
    )
    cg_5h["capacity_usd"] = cg_5h_capacity_usd
    c5_burn_usd = cg_5h.get("quota_burn_usd", cg_5h["imputed_value_usd"])
    cg_5h_used_pct = round(min(100.0, (c5_burn_usd / cg_5h_capacity_usd) * 100.0), 1) if cg_5h_capacity_usd > 0 else 0.0
    cg_5h["used_pct"] = cg_5h_used_pct
    cg_5h["remaining_pct"] = round(max(0.0, 100.0 - cg_5h_used_pct), 1)

    # Discrete 5-Hour Reset Epoch Anchor for Track 2 (ADR-082)
    if claude_gpt_turns and cg_5h_used_pct > 0:
        window_start_ts = (c5_start_time or (ref_dt - datetime.timedelta(hours=5.0))).timestamp()
        cg_turns_in_window = [
            t for t in claude_gpt_turns
            if (parse_timestamp(t.get("timestamp")) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)).timestamp() >= window_start_ts
        ]
        if cg_turns_in_window:
            earliest_dt = min(
                parse_timestamp(t.get("timestamp"))
                for t in cg_turns_in_window
                if parse_timestamp(t.get("timestamp")) is not None
            )
            reset_dt = earliest_dt + datetime.timedelta(hours=5.0)
            rem_sec = max(0, int((reset_dt - ref_dt).total_seconds()))
            rem_min = rem_sec // 60
            cg_5h["reset_time"] = reset_dt.isoformat()
            if rem_min >= 60:
                h = rem_min // 60
                m = rem_min % 60
                rem_str = f"{h} hour{'s' if h != 1 else ''}, {m} minute{'s' if m != 1 else ''}" if m else f"{h} hour{'s' if h != 1 else ''}"
            else:
                rem_str = f"{rem_min} minute{'s' if rem_min != 1 else ''}"
            cg_5h["message"] = f"You have used some of your 5-hour limit, it will fully refresh in {rem_str}."
        else:
            cg_5h["message"] = "Fully refreshed (100% capacity available)"
    else:
        cg_5h["message"] = "Fully refreshed (100% capacity available)"

    # Claude/GPT 7-day (168h) rolling or live-anchored weekly window
    cw_start_time = None
    cw_explicit_reset = None
    if live_quota and live_quota.get("available") and live_quota.get("claude_weekly", {}) and live_quota["claude_weekly"].get("reset_time"):
        cw_explicit_reset = parse_timestamp(live_quota["claude_weekly"]["reset_time"])
        if cw_explicit_reset and cw_explicit_reset > ref_dt:
            cw_start_time = max(
                ref_dt - datetime.timedelta(days=7),
                cw_explicit_reset - datetime.timedelta(days=7),
            )

    cg_weekly = compute_rolling_window_telemetry(
        claude_gpt_turns,
        window_hours=168.0,
        reference_time=ref_dt,
        pricing_models=pricing_models,
        start_time=cw_start_time,
    )
    # Determine Claude/GPT rolling age-out horizon
    cg_window_start = cw_start_time or (ref_dt - datetime.timedelta(days=7))
    cg_active_turns = []
    for t in claude_gpt_turns:
        t_dt = parse_timestamp(t.get("timestamp"))
        if t_dt and cg_window_start <= t_dt <= ref_dt:
            cg_active_turns.append(t_dt)

    if cw_explicit_reset and cw_explicit_reset > ref_dt:
        full_refresh_dt = cw_explicit_reset
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
    elif cg_active_turns:
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
    cw_burn_usd = cg_weekly.get("quota_burn_usd", cg_weekly["imputed_value_usd"])
    cg_weekly_used_pct = round(min(100.0, (cw_burn_usd / cg_weekly_capacity_usd) * 100.0), 1) if cg_weekly_capacity_usd > 0 else 0.0
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

    raw_pricing = load_raw_pricing()
    raw_tracks = raw_pricing.get("quota_tracks", []) if isinstance(raw_pricing, dict) else []
    gemini_track_cfg = next((t for t in raw_tracks if isinstance(t, dict) and t.get("id") == "gemini"), {})
    cg_track_cfg = next((t for t in raw_tracks if isinstance(t, dict) and t.get("id") == "claude_gpt"), {})

    gemini_track_obj = {
        "id": "gemini",
        "track": "gemini",
        "display_name": gemini_track_cfg.get("display_name", "Gemini Models"),
        "short_name": gemini_track_cfg.get("short_name", "Gemini"),
        "icon": gemini_track_cfg.get("icon", "✦"),
        "is_primary": bool(gemini_track_cfg.get("is_primary", True)),
        "credit_spillover": bool(gemini_track_cfg.get("credit_spillover", True)),
        "five_hour": gemini_5h,
        "weekly": gemini_weekly,
        "exhaustion_alarm": exhaustion_alarm,
        "runway": runway,
    }
    cg_track_obj = {
        "id": "claude_gpt",
        "track": "claude_gpt",
        "display_name": cg_track_cfg.get("display_name", "Claude and GPT Models"),
        "short_name": cg_track_cfg.get("short_name", "Claude / GPT"),
        "icon": cg_track_cfg.get("icon", "◈"),
        "is_primary": bool(cg_track_cfg.get("is_primary", False)),
        "credit_spillover": bool(cg_track_cfg.get("credit_spillover", False)),
        "five_hour": cg_5h,
        "weekly": cg_weekly,
    }

    providers_quotas = {
        "desktop_sync": {
            "active": desktop_sync_active,
            "description": live_quota.get("description", "") if live_quota else "",
        },
        "gemini": gemini_track_obj,
        "claude_gpt": cg_track_obj,
        "tracks": [gemini_track_obj, cg_track_obj],
    }

    return {
        "providers_quotas": providers_quotas,
        "gemini_5h": gemini_5h,
        "gemini_weekly": gemini_weekly,
        "cg_5h": cg_5h,
        "cg_weekly": cg_weekly,
        "gemini_turns": gemini_turns,
        "claude_gpt_turns": claude_gpt_turns,
        "gemini_multiplier": gemini_multiplier,
        "cg_multiplier": cg_multiplier,
        "burst_limit": burst_limit,
        "gemini_weekly_capacity_usd": gemini_weekly_capacity_usd,
        "cents_per_credit": cents_per_credit,
        "sub_cfg": sub_cfg,
        "exhaustion_alarm": exhaustion_alarm,
        "runway": runway,
    }


def decorate_active_sessions(
    sessions_lists: List[List[Dict[str, Any]]],
    conversation_summaries: List[Dict[str, Any]],
) -> None:
    """Map conversation IDs to metadata and decorate active session lists in-place."""
    convo_meta_map = {
        (c.get("convo_id") or c.get("conversation_id")): {
            "title": c.get("title", "Untitled Session"),
            "workspace_name": c.get("workspace_name", "Unknown Workspace"),
            "workspace_path": c.get("workspace_path", ""),
            "git_branch": c.get("git_branch", "main"),
            "agent_name": c.get("agent_name", "default"),
            "agent_description": c.get("agent_description", ""),
            "is_subagent": bool(c.get("is_subagent", False)),
            "subagent_role": c.get("subagent_role", ""),
            "parent_convo_id": c.get("parent_convo_id", ""),
        }
        for c in conversation_summaries
        if (c.get("convo_id") or c.get("conversation_id"))
    }

    for sessions in sessions_lists:
        for s in sessions:
            cid = s.get("convo_id")
            meta = convo_meta_map.get(cid, {})
            s["title"] = meta.get("title", "Untitled Session")
            s["workspace_name"] = meta.get("workspace_name", "Unknown Workspace")
            s["workspace_path"] = meta.get("workspace_path", "")
            s["git_branch"] = meta.get("git_branch", "main")
            s["agent_name"] = meta.get("agent_name", "default")
            s["agent_description"] = meta.get("agent_description", "")
            s["is_subagent"] = meta.get("is_subagent", False)
            s["subagent_role"] = meta.get("subagent_role", "")
            s["parent_convo_id"] = meta.get("parent_convo_id", "")


def reconcile_credit_burn_and_overage(
    flat_turns: List[Dict[str, Any]],
    exhaustion_intervals: Optional[List[Dict[str, Any]]],
    pricing_models: Dict[str, Any],
    sub_cfg: Dict[str, Any],
    ref_dt: datetime.datetime,
    rolling_5h: Dict[str, Any],
    burst_limit: int,
    live_quota: Optional[Dict[str, Any]] = None,
    exhaustion_alarm: Optional[Dict[str, Any]] = None,
    monthly_billing_bounds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Reconcile persistent ledger deductions with live 429 intervals using two-pointer sliding window.
    Determines status flags, hourly credit activity, and credit bank pack balances (ADR-002 / ADR-028).
    """
    currency_cfg = load_currency_config()
    usd_to_gbp_fx = currency_cfg.get("usd_to_gbp_fx_rate", 0.79)
    pack_cfg = currency_cfg.get("credit_pack", {})
    cost_per_credit_gbp = pack_cfg.get("cost_per_credit_gbp", 0.009596)
    cents_per_credit = sub_cfg.get("cents_per_credit", 1.0)

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
        if inv.get("event_type") == "QUOTA_RESET_BONUS" or inv.get("reason") == "QUOTA_RESET_BONUS":
            h_entry["event_type"] = inv.get("event_type") or "QUOTA_RESET_BONUS"
            h_entry["reason"] = inv.get("reason") or "QUOTA_RESET_BONUS"
            h_entry["description"] = inv.get("description") or ""
            h_entry["bonus_pct_forgiven"] = float(inv.get("bonus_pct_forgiven") or 0.0)
            h_entry["bonus_credits_forgiven"] = int(inv.get("bonus_credits_forgiven") or 0)
            h_entry["bonus_value_usd"] = float(inv.get("bonus_value_usd") or 0.0)
            h_entry["bonus_value_gbp"] = float(inv.get("bonus_value_gbp") or 0.0)
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
        inv.get("reason") != "QUOTA_RESET_BONUS"
        and inv.get("event_type") != "QUOTA_RESET_BONUS"
        and inv.get("start")
        and inv["start"] <= ref_dt
        and (inv.get("end") is None or ref_dt <= inv["end"])
        for inv in (exhaustion_intervals or [])
    )
    is_near_burst_limit = rolling_5h.get("total_processed_tokens", 0) >= burst_limit

    # Check live desktop quota for weekly or 5h exhaustion (ADR-028 / ADR-094)
    live_weekly_exhausted = False
    live_5h_exhausted = False
    if live_quota and live_quota.get("available"):
        gw_live = live_quota.get("gemini_weekly") or {}
        if isinstance(gw_live, dict) and gw_live.get("remaining_pct", 100.0) <= 0.1:
            live_weekly_exhausted = True
        g5_live = live_quota.get("gemini_5h") or {}
        if isinstance(g5_live, dict) and (
            g5_live.get("remaining_pct", 100.0) <= 0.0
            or (
                g5_live.get("remaining_fraction") is not None
                and float(g5_live.get("remaining_fraction", 1.0)) <= 0.0
            )
        ):
            live_5h_exhausted = True

    if active_log_interval:
        subscription_status = "BURNING_AI_CREDITS"
    elif live_weekly_exhausted or (exhaustion_alarm and exhaustion_alarm.get("gemini_weekly_exhausted")):
        subscription_status = "WEEKLY_EXHAUSTED"
    elif live_5h_exhausted:
        subscription_status = "BURNING_AI_CREDITS"
    elif recent_overage:
        subscription_status = "RECOVERED_COOLDOWN"
    else:
        subscription_status = "SAFE_IN_QUOTA"

    serialized_intervals = []
    for inv in (exhaustion_intervals or []):
        entry = {
            "start": inv["start"].isoformat() if hasattr(inv.get("start"), "isoformat") else inv.get("start"),
            "end": inv["end"].isoformat() if hasattr(inv.get("end"), "isoformat") else inv.get("end"),
            "events_count": inv.get("events_count", 1),
            "code": inv.get("code", 429),
            "reason": inv.get("reason", "RESOURCE_EXHAUSTED"),
        }
        if inv.get("event_type") == "QUOTA_RESET_BONUS" or inv.get("reason") == "QUOTA_RESET_BONUS":
            entry["event_type"] = inv.get("event_type") or "QUOTA_RESET_BONUS"
            entry["bonus_pct_forgiven"] = inv.get("bonus_pct_forgiven", 0.0)
            entry["bonus_credits_forgiven"] = inv.get("bonus_credits_forgiven", 0)
        serialized_intervals.append(entry)

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

    monthly_bounds = monthly_billing_bounds or {}
    cycle_tokens = monthly_bounds.get("total_processed_tokens", 0)
    cycle_turns = monthly_bounds.get("turn_count", 0)
    cycle_imputed_usd = monthly_bounds.get("imputed_value_usd", 0.0)
    cycle_imputed_gbp = round(cycle_imputed_usd * usd_to_gbp_fx, 2)
    cycle_roi = round(cycle_imputed_gbp / sub_price_gbp, 1) if sub_price_gbp > 0 else 1.0

    return {
        "total_ai_credits_burned": total_ai_credits_burned,
        "bank_credits_burned": bank_credits_burned,
        "total_credit_burn_usd": total_credit_burn_usd,
        "total_credit_burn_gbp": total_credit_burn_gbp,
        "hourly_credit_activity": hourly_credit_activity,
        "subscription_status": subscription_status,
        "is_near_burst_limit": is_near_burst_limit,
        "serialized_intervals": serialized_intervals,
        "sub_price_gbp": sub_price_gbp,
        "sub_price_usd": sub_price_usd,
        "single_pack_price_gbp": single_pack_price_gbp,
        "single_pack_price_usd": single_pack_price_usd,
        "total_pack_price_gbp": total_pack_price_gbp,
        "total_pack_price_usd": total_pack_price_usd,
        "bank_total_credits": bank_total_credits,
        "bank_credits_rem": bank_credits_rem,
        "packs_count": packs_count,
        "cost_per_credit_gbp": cost_per_credit_gbp,
        "cents_per_credit": cents_per_credit,
        "currency_cfg": currency_cfg,
        "usd_to_gbp_fx": usd_to_gbp_fx,
        "cycle_tokens": cycle_tokens,
        "cycle_turns": cycle_turns,
        "cycle_imputed_usd": cycle_imputed_usd,
        "cycle_imputed_gbp": cycle_imputed_gbp,
        "cycle_roi": cycle_roi,
    }
