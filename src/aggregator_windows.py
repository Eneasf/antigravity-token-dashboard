"""
Rolling window telemetry, recovery schedules, historical peaks, and conversation-level metrics.
"""

from collections import defaultdict
import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from src.aggregator_pricing import (
    compute_turn_cost,
    get_model_display_name,
    get_model_quota_weights,
    get_model_rates,
    parse_timestamp,
)


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
        "quota_burn_usd": 0.0,
    })

    total_imputed_value = 0.0
    total_quota_burn = 0.0

    for t in window_turns:
        mid = str(t.get("model_id", "unknown"))
        rates = get_model_rates(mid, pricing_models, timestamp=t.get("timestamp"))
        weights = get_model_quota_weights(mid, pricing_models, timestamp=t.get("timestamp"))
        cost = compute_turn_cost(t, rates)
        q_burn = compute_turn_cost(t, weights)
        total_imputed_value += cost
        total_quota_burn += q_burn

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
        m_entry["quota_burn_usd"] += q_burn

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
        m_entry["quota_burn_usd"] = round(m_entry["quota_burn_usd"], 4)
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
        "quota_burn_usd": round(total_quota_burn, 4),
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
            "seconds_until": int(round(seconds_remaining)),
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
                if inv.get("reason") == "QUOTA_RESET_BONUS" or inv.get("event_type") == "QUOTA_RESET_BONUS":
                    continue
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

    peak_prompt_depth = max(
        (t.get("total_input_tokens", 0) or (t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0)) for t in enriched_turns),
        default=0,
    )

    return {
        "convo_id": conversation_meta.get("convo_id", ""),
        "title": conversation_meta.get("title", "Untitled Conversation"),
        "workspace": conversation_meta.get("workspace_name") or conversation_meta.get("workspace", "Unknown Workspace"),
        "workspace_path": conversation_meta.get("workspace_path", ""),
        "workspace_name": conversation_meta.get("workspace_name") or conversation_meta.get("workspace", "Unknown Workspace"),
        "git_branch": conversation_meta.get("git_branch", "main"),
        "agent_name": conversation_meta.get("agent_name", "default"),
        "agent_description": conversation_meta.get("agent_description", ""),
        "agent_config_uri": conversation_meta.get("agent_config_uri", ""),
        "is_subagent": bool(conversation_meta.get("is_subagent", False)),
        "parent_convo_id": conversation_meta.get("parent_convo_id", ""),
        "subagent_type": conversation_meta.get("subagent_type", ""),
        "subagent_role": conversation_meta.get("subagent_role", ""),
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
        "has_truncated": False,
        "first_truncation_step": None,
        "depth_at_truncation": None,
        "peak_prompt_depth": peak_prompt_depth,
        "turns": enriched_turns,
    }
