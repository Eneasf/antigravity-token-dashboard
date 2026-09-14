"""
What-If Workload Simulator & Multi-Agent Capacity Planner (Milestone 21).

Pure Python 3 standard library engine for simulating token consumption,
cache hit dynamics, rolling quota headroom, credit bank spillover, and HTTP 429
rate limit lockouts across Gemini and Claude/GPT provider tracks (ADR-019 & ADR-030).
"""

from copy import deepcopy
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from src.temporal import (
    DEFAULT_PRICING_FILE,
    PLAN_PRESETS,
    TemporalPricingResolver,
    get_temporal_resolver,
    load_pricing,
    load_raw_pricing,
)

DEFAULT_FX_RATE: float = 0.79
DEFAULT_CREDIT_COST_GBP: float = 0.009596
DEFAULT_CREDIT_COST_USD: float = 0.010000


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
    if pricing_models and mid in pricing_models:
        family = str(pricing_models[mid].get("family", "")).lower()

    if family.startswith("claude") or family.startswith("gpt"):
        return "claude_gpt"

    mid_lower = mid.lower()
    if mid_lower.startswith("claude") or mid_lower.startswith("gpt"):
        return "claude_gpt"

    return "gemini"


def get_model_rates(
    model_id: Any,
    pricing_models: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Resolve active rate card for a given model ID."""
    if pricing_models is None:
        pricing_models = load_pricing()

    mid = str(model_id) if model_id is not None else "default"
    if pricing_models and mid in pricing_models:
        rates = pricing_models[mid].get("rates_per_million", {})
        if rates:
            return deepcopy(rates)

    if pricing_models and "default" in pricing_models:
        return deepcopy(pricing_models["default"].get("rates_per_million", {
            "prompt_uncached": 0.75,
            "prompt_cached": 0.075,
            "candidate_output": 3.75,
        }))

    return {
        "prompt_uncached": 0.75,
        "prompt_cached": 0.075,
        "candidate_output": 3.75,
    }


def calculate_turn_tokens(
    prompt_tokens: int,
    cache_hit_ratio: float,
    thinking_tokens: int,
    answer_tokens: int,
) -> Dict[str, Any]:
    """
    Calculate uncached, cached, and output token breakdown for a turn.

    Accepts cache_hit_ratio as either a fraction [0.0, 1.0] or percentage [0.0, 100.0].
    Returns integer token counts and rounded cache_hit_ratio_pct.
    """
    prompt = max(0, int(prompt_tokens))
    thinking = max(0, int(thinking_tokens))
    answer = max(0, int(answer_tokens))

    ratio_val = float(cache_hit_ratio)
    if ratio_val > 1.0:
        ratio_fraction = ratio_val / 100.0
    else:
        ratio_fraction = ratio_val
    ratio_fraction = max(0.0, min(1.0, ratio_fraction))

    cached_tokens = int(round(prompt * ratio_fraction))
    prompt_uncached = max(0, prompt - cached_tokens)
    total_input = prompt
    total_output = thinking + answer
    total_processed = total_input + total_output

    cache_hit_pct = round((cached_tokens / total_input * 100.0) if total_input > 0 else 0.0, 2)

    return {
        "prompt_tokens_uncached": prompt_uncached,
        "cached_tokens": cached_tokens,
        "thinking_tokens": thinking,
        "answer_tokens": answer,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_processed_tokens": total_processed,
        "cache_hit_ratio_pct": cache_hit_pct,
    }


def calculate_turn_cost(
    tokens_dict: Dict[str, Any],
    rates: Dict[str, float],
    fx_rate: float = DEFAULT_FX_RATE,
) -> Dict[str, float]:
    """
    Calculate turn cost in USD and GBP from token dictionary and rate card.

    Rates are denominated in USD per million tokens.
    """
    p_uncached = rates.get("prompt_uncached", 0.0)
    p_cached = rates.get("prompt_cached", 0.0)
    p_output = rates.get("candidate_output", 0.0)

    uncached = tokens_dict.get("prompt_tokens_uncached", 0)
    cached = tokens_dict.get("cached_tokens", 0)
    output = tokens_dict.get(
        "total_output_tokens",
        tokens_dict.get("thinking_tokens", 0) + tokens_dict.get("answer_tokens", 0),
    )

    cost_usd = (uncached / 1e6 * p_uncached) + (cached / 1e6 * p_cached) + (output / 1e6 * p_output)
    cost_usd = round(cost_usd, 6)
    cost_gbp = round(cost_usd * fx_rate, 6)

    return {
        "cost_usd": cost_usd,
        "cost_gbp": cost_gbp,
    }


def get_archetype_presets() -> Dict[str, Dict[str, Any]]:
    """
    Return standard multi-agent workload archetypes for what-if simulation.
    """
    return {
        "deep_refactor_swarm": {
            "id": "deep_refactor_swarm",
            "name": "Deep Refactor Swarm",
            "model_id": "1016",
            "turn_count": 40,
            "prompt_tokens": 120000,
            "cache_hit_ratio_pct": 88.0,
            "thinking_tokens": 8000,
            "answer_tokens": 1500,
            "duration_minutes_per_turn": 2.5,
            "description": "Multi-agent deep architecture refactor using Pro reasoning.",
        },
        "codebase_audit": {
            "id": "codebase_audit",
            "name": "Codebase Audit & Security Scan",
            "model_id": "1318",
            "turn_count": 60,
            "prompt_tokens": 200000,
            "cache_hit_ratio_pct": 94.0,
            "thinking_tokens": 2500,
            "answer_tokens": 1000,
            "duration_minutes_per_turn": 1.5,
            "description": "High-context whole-codebase scan with deep caching.",
        },
        "rapid_prototyping_burst": {
            "id": "rapid_prototyping_burst",
            "name": "Rapid Prototyping Burst",
            "model_id": "1319",
            "turn_count": 25,
            "prompt_tokens": 45000,
            "cache_hit_ratio_pct": 75.0,
            "thinking_tokens": 1500,
            "answer_tokens": 800,
            "duration_minutes_per_turn": 1.0,
            "description": "Interactive fast-iteration development cycle.",
        },
        "claude_opus_deep_dive": {
            "id": "claude_opus_deep_dive",
            "name": "Claude Opus 4.6 Stress Test",
            "model_id": "1026",
            "turn_count": 35,
            "prompt_tokens": 95000,
            "cache_hit_ratio_pct": 92.0,
            "thinking_tokens": 6000,
            "answer_tokens": 1200,
            "duration_minutes_per_turn": 2.0,
            "description": "Tests Claude rate limits and the strict 30-95 turn boundary.",
        },
        "subagent_fleet": {
            "id": "subagent_fleet",
            "name": "Subagent Fleet (Lite/Fast)",
            "model_id": "1050",
            "turn_count": 100,
            "prompt_tokens": 30000,
            "cache_hit_ratio_pct": 85.0,
            "thinking_tokens": 500,
            "answer_tokens": 600,
            "duration_minutes_per_turn": 0.5,
            "description": "Parallel background subagent workers executing mechanical tasks.",
        },
    }


def simulate_turn_sequence(
    turns: List[Dict[str, Any]],
    initial_quota_state: Optional[Dict[str, Any]] = None,
    plan_config: Optional[Union[Dict[str, Any], str]] = None,
    pricing_models: Optional[Dict[str, Any]] = None,
    fx_rate: float = DEFAULT_FX_RATE,
) -> Dict[str, Any]:
    """
    Simulate a sequence of turns against rolling quota limits and provider tracks.

    Evaluates burst capacity, weekly macro-capacity, Google One AI credit spillover
    (for Gemini), and HTTP 429 lockout risks (for Claude/GPT and weekly exhaustion).
    """
    if pricing_models is None:
        pricing_models = load_pricing()

    # 1. Resolve Plan Configuration & Tier
    if isinstance(plan_config, str):
        plan_tier = plan_config.lower()
        plan_dict = None
    elif isinstance(plan_config, dict):
        plan_tier = str(plan_config.get("tier", "pro")).lower()
        plan_dict = plan_config
    else:
        plan_tier = "pro"
        plan_dict = None

    if plan_dict is None:
        matched = next((p for p in PLAN_PRESETS if p.get("tier", "").lower() == plan_tier), None)
        if matched:
            plan_dict = deepcopy(matched)
        else:
            plan_dict = deepcopy(PLAN_PRESETS[0])

    quota_limits = plan_dict.get("quota_limits", {})
    gemini_5h_cap = float(quota_limits.get("gemini_5h_capacity_usd", 20.00))
    gemini_weekly_cap = float(quota_limits.get("gemini_weekly_capacity_usd", 129.00))
    claude_5h_cap = float(quota_limits.get("claude_5h_capacity_usd", 10.00))
    claude_weekly_cap = float(quota_limits.get("claude_weekly_capacity_usd", 35.00))

    # 2. Determine Provider Track
    if "provider_track" in plan_dict:
        provider_track = plan_dict["provider_track"]
    elif "target_provider" in plan_dict:
        provider_track = plan_dict["target_provider"]
    else:
        claude_count = sum(
            1 for t in turns if get_provider_quota_track(t.get("model_id"), pricing_models) == "claude_gpt"
        )
        provider_track = "claude_gpt" if claude_count > 0 else "gemini"

    # 3. Promotional Capacity Multipliers
    promo_mult = float(plan_dict.get("promotional_multiplier", 1.0))
    try:
        resolver = get_temporal_resolver()
        temporal_mult = resolver.get_capacity_multiplier(provider=provider_track)
        if temporal_mult > 1.0:
            promo_mult *= temporal_mult
    except Exception:
        pass

    if provider_track == "claude_gpt":
        burst_capacity_usd = round(claude_5h_cap * promo_mult, 4)
        weekly_capacity_usd = round(claude_weekly_cap * promo_mult, 4)
    else:
        burst_capacity_usd = round(gemini_5h_cap * promo_mult, 4)
        weekly_capacity_usd = round(gemini_weekly_cap * promo_mult, 4)

    # 4. Starting Quota State
    starting_5h_used_usd = 0.0
    starting_weekly_used_usd = 0.0
    if initial_quota_state:
        p_sub = initial_quota_state.get(provider_track)
        state_dict = p_sub if isinstance(p_sub, dict) else initial_quota_state
        starting_5h_used_usd = float(
            state_dict.get(
                "starting_5h_used_usd",
                state_dict.get(
                    "current_5h_used_usd",
                    state_dict.get(
                        "rolling_5h_used_usd",
                        state_dict.get("used_5h_usd", 0.0),
                    ),
                ),
            )
        )
        starting_weekly_used_usd = float(
            state_dict.get(
                "starting_weekly_used_usd",
                state_dict.get(
                    "current_weekly_used_usd",
                    state_dict.get(
                        "weekly_used_usd",
                        state_dict.get("used_weekly_usd", 0.0),
                    ),
                ),
            )
        )

    # 5. Process Turns Sequence
    total_prompt_tokens = 0
    total_prompt_uncached = 0
    total_cached_tokens = 0
    total_thinking_tokens = 0
    total_answer_tokens = 0
    total_output_tokens = 0
    total_processed_tokens = 0
    total_cost_usd = 0.0

    turns_trajectory: List[Dict[str, Any]] = []
    elapsed_minutes = 0.0
    turns_to_exhaustion: Optional[int] = None
    time_to_exhaustion_minutes: Optional[float] = None
    cumulative_5h_usd = starting_5h_used_usd

    turn_count = len(turns)

    for i, t in enumerate(turns, start=1):
        mid = str(t.get("model_id", "default"))
        p_tok = int(t.get("prompt_tokens", 0))
        hit_ratio = float(t.get("cache_hit_ratio", t.get("cache_hit_ratio_pct", 0.0)))
        think_tok = int(t.get("thinking_tokens", 0))
        ans_tok = int(t.get("answer_tokens", 0))
        dur_min = float(t.get("duration_minutes", t.get("duration_minutes_per_turn", 0.0)))

        elapsed_minutes += dur_min

        tok_breakdown = calculate_turn_tokens(p_tok, hit_ratio, think_tok, ans_tok)
        total_prompt_tokens += tok_breakdown["total_input_tokens"]
        total_prompt_uncached += tok_breakdown["prompt_tokens_uncached"]
        total_cached_tokens += tok_breakdown["cached_tokens"]
        total_thinking_tokens += tok_breakdown["thinking_tokens"]
        total_answer_tokens += tok_breakdown["answer_tokens"]
        total_output_tokens += tok_breakdown["total_output_tokens"]
        total_processed_tokens += tok_breakdown["total_processed_tokens"]

        rates = get_model_rates(mid, pricing_models)
        cost_info = calculate_turn_cost(tok_breakdown, rates, fx_rate=fx_rate)
        turn_cost = cost_info["cost_usd"]
        total_cost_usd += turn_cost
        cumulative_5h_usd = round(cumulative_5h_usd + turn_cost, 6)

        turn_exhausted = bool(cumulative_5h_usd > burst_capacity_usd)
        if turn_exhausted and turns_to_exhaustion is None:
            turns_to_exhaustion = i
            time_to_exhaustion_minutes = round(elapsed_minutes, 2)

        u_pct = round((cumulative_5h_usd / burst_capacity_usd * 100.0) if burst_capacity_usd > 0 else 0.0, 2)
        r_pct = round(max(0.0, 100.0 - u_pct), 2)

        turns_trajectory.append({
            "turn": i,
            "model_id": mid,
            "cost_usd": turn_cost,
            "cumulative_5h_usd": round(cumulative_5h_usd, 4),
            "used_5h_pct": u_pct,
            "remaining_5h_pct": r_pct,
            "exhausted": turn_exhausted,
        })

    # 6. Overall Metrics
    imputed_value_usd = round(total_cost_usd, 4)
    imputed_value_gbp = round(imputed_value_usd * fx_rate, 4)

    cache_hit_ratio_pct = round(
        (total_cached_tokens / total_prompt_tokens * 100.0) if total_prompt_tokens > 0 else 0.0, 2
    )

    final_5h_used_usd = round(starting_5h_used_usd + total_cost_usd, 4)
    final_5h_used_pct = round(
        (final_5h_used_usd / burst_capacity_usd * 100.0) if burst_capacity_usd > 0 else 0.0, 2
    )
    final_5h_remaining_pct = round(max(0.0, 100.0 - final_5h_used_pct), 2)

    final_weekly_used_usd = round(starting_weekly_used_usd + total_cost_usd, 4)
    final_weekly_used_pct = round(
        (final_weekly_used_usd / weekly_capacity_usd * 100.0) if weekly_capacity_usd > 0 else 0.0, 2
    )
    final_weekly_remaining_pct = round(max(0.0, 100.0 - final_weekly_used_pct), 2)

    weekly_load_added_pct = round(
        (imputed_value_usd / weekly_capacity_usd * 100.0) if weekly_capacity_usd > 0 else 0.0, 2
    )

    burst_exhausted = bool(final_5h_used_usd > burst_capacity_usd)
    weekly_exhausted = bool(final_weekly_used_usd > weekly_capacity_usd)
    over_burst_usd = max(0.0, round(final_5h_used_usd - burst_capacity_usd, 4))

    if turns_to_exhaustion is not None:
        over_burst_turns = max(0, turn_count - turns_to_exhaustion + 1)
    else:
        over_burst_turns = 0

    # 7. Credit Spillover & Exhaustion Evaluation
    credit_spillover_applicable = (provider_track == "gemini")
    credits_debited = 0
    credit_cost_gbp = 0.0
    credit_cost_usd = 0.0
    credit_bank_exhaustion_risk = False

    if credit_spillover_applicable and burst_exhausted and over_burst_turns > 0:
        total_credits = 0.0
        start_idx = turns_to_exhaustion - 1 if turns_to_exhaustion is not None else 0
        for ob_t in turns[start_idx:]:
            ob_mid = str(ob_t.get("model_id", "default"))
            if pricing_models and ob_mid in pricing_models:
                rate = pricing_models[ob_mid].get("credits_per_turn", 2.5)
            elif pricing_models and "default" in pricing_models:
                rate = pricing_models["default"].get("credits_per_turn", 2.5)
            else:
                rate = 2.5
            total_credits += float(rate)

        credits_debited = int(round(total_credits))
        if credits_debited == 0 and over_burst_usd > 0:
            credits_debited = max(1, int(round(over_burst_usd / DEFAULT_CREDIT_COST_USD)))

        credit_cost_gbp = round(credits_debited * DEFAULT_CREDIT_COST_GBP, 4)
        credit_cost_usd = round(credits_debited * DEFAULT_CREDIT_COST_USD, 4)

        if initial_quota_state:
            p_sub = initial_quota_state.get(provider_track)
            c_dict = p_sub if isinstance(p_sub, dict) else initial_quota_state
            rem_credits = c_dict.get(
                "credits_remaining",
                c_dict.get(
                    "credit_bank_remaining_credits",
                    c_dict.get("credit_bank_remaining"),
                ),
            )
            if rem_credits is None and isinstance(initial_quota_state, dict):
                rem_credits = initial_quota_state.get("credits_remaining")
            if rem_credits is not None and credits_debited > float(rem_credits):
                credit_bank_exhaustion_risk = True

            rem_usd = c_dict.get("credit_bank_remaining_usd")
            if rem_usd is None and isinstance(initial_quota_state, dict):
                rem_usd = initial_quota_state.get("credit_bank_remaining_usd")
            if rem_usd is not None and credit_cost_usd > float(rem_usd):
                credit_bank_exhaustion_risk = True

    # 8. Hard HTTP 429 Block Risk & Status
    hard_429_block_risk = bool((provider_track == "claude_gpt" and burst_exhausted) or weekly_exhausted)

    if (provider_track == "claude_gpt" and burst_exhausted) or weekly_exhausted:
        status_key = "lockout"
        status_label = "HTTP 429 Lockout"
        risk_level = "CRITICAL_429"
    elif burst_exhausted:
        status_key = "cooldown"
        status_label = "Burst Cooldown"
        risk_level = "HIGH_EXHAUSTION"
    elif final_5h_remaining_pct < 50.0:
        status_key = "caution"
        status_label = "Caution (Heavy Load)"
        risk_level = "MODERATE"
    else:
        status_key = "safe"
        status_label = "Safe Zone"
        risk_level = "SAFE"

    # 9. Clear Actionable Recommendation
    if status_key == "safe":
        recommendation = (
            f"Workload is well within limits ({final_5h_remaining_pct:.1f}% burst headroom remaining). "
            "Safe to proceed without rate limit risk."
        )
    elif status_key == "caution":
        recommendation = (
            f"Workload creates heavy load ({final_5h_remaining_pct:.1f}% burst headroom remaining). "
            "Recommend monitoring execution pacing or adding brief inter-turn spacing."
        )
    elif status_key == "cooldown":
        recommendation = (
            f"Workload exceeds 5h burst allowance by ${over_burst_usd:.2f} (exhausted at turn {turns_to_exhaustion}). "
            f"Gemini spills over to Google One credit bank ({credits_debited} credits debited, £{credit_cost_gbp:.2f} / ${credit_cost_usd:.2f}). "
            "To eliminate credit burn, consider upgrading to Google AI Ultra / Enterprise (5x capacity) or switching to Gemini Flash."
        )
    else:  # lockout
        if provider_track == "claude_gpt":
            recommendation = (
                f"CRITICAL: Claude/GPT burst exceeded by ${over_burst_usd:.2f} at turn {turns_to_exhaustion} "
                "with ZERO credit spillover (ADR-019 & ADR-030). Immediate HTTP 429 hard block! "
                "Switch to Gemini Flash/Pro or upgrade plan tier to proceed."
            )
        else:
            recommendation = (
                f"CRITICAL: Weekly quota limit of ${weekly_capacity_usd:.2f} exhausted. "
                "Hierarchical rate limiter blocks execution until Thursday cycle refresh. "
                "Upgrade to Google AI Ultra / Enterprise (5x capacity) or activate Google One credits to continue."
            )

    return {
        "turn_count": turn_count,
        "total_prompt_tokens": total_prompt_tokens,
        "total_prompt_uncached": total_prompt_uncached,
        "total_cached_tokens": total_cached_tokens,
        "total_thinking_tokens": total_thinking_tokens,
        "total_answer_tokens": total_answer_tokens,
        "total_output_tokens": total_output_tokens,
        "total_processed_tokens": total_processed_tokens,
        "cache_hit_ratio_pct": cache_hit_ratio_pct,
        "imputed_value_usd": imputed_value_usd,
        "imputed_value_gbp": imputed_value_gbp,
        "provider_track": provider_track,
        "plan_tier": plan_tier,
        "burst_capacity_usd": burst_capacity_usd,
        "weekly_capacity_usd": weekly_capacity_usd,
        "starting_5h_used_usd": starting_5h_used_usd,
        "starting_weekly_used_usd": starting_weekly_used_usd,
        "final_5h_used_usd": final_5h_used_usd,
        "final_5h_used_pct": final_5h_used_pct,
        "final_5h_remaining_pct": final_5h_remaining_pct,
        "final_weekly_used_usd": final_weekly_used_usd,
        "final_weekly_used_pct": final_weekly_used_pct,
        "final_weekly_remaining_pct": final_weekly_remaining_pct,
        "weekly_load_added_pct": weekly_load_added_pct,
        "burst_exhausted": burst_exhausted,
        "weekly_exhausted": weekly_exhausted,
        "turns_to_exhaustion": turns_to_exhaustion,
        "time_to_exhaustion_minutes": time_to_exhaustion_minutes,
        "over_burst_usd": over_burst_usd,
        "over_burst_turns": over_burst_turns,
        "status_key": status_key,
        "status_label": status_label,
        "risk_level": risk_level,
        "credit_spillover_applicable": credit_spillover_applicable,
        "credits_debited": credits_debited,
        "credit_cost_gbp": credit_cost_gbp,
        "credit_cost_usd": credit_cost_usd,
        "credit_bank_exhaustion_risk": credit_bank_exhaustion_risk,
        "hard_429_block_risk": hard_429_block_risk,
        "recommendation": recommendation,
        "turns_trajectory": turns_trajectory,
    }


def simulate_workload(
    model_id: str = "1318",
    turn_count: int = 25,
    prompt_tokens: int = 50000,
    cache_hit_ratio_pct: float = 80.0,
    thinking_tokens: int = 2000,
    answer_tokens: int = 1000,
    duration_minutes_per_turn: float = 2.0,
    initial_quota_state: Optional[Dict[str, Any]] = None,
    plan_tier: str = "pro",
    pricing_models: Optional[Dict[str, Any]] = None,
    fx_rate: float = DEFAULT_FX_RATE,
) -> Dict[str, Any]:
    """
    Convenience wrapper generating `turn_count` identical turns and executing simulation.
    """
    turns = [
        {
            "model_id": model_id,
            "prompt_tokens": prompt_tokens,
            "cache_hit_ratio": cache_hit_ratio_pct,
            "thinking_tokens": thinking_tokens,
            "answer_tokens": answer_tokens,
            "duration_minutes": duration_minutes_per_turn,
        }
        for _ in range(turn_count)
    ]
    res = simulate_turn_sequence(
        turns=turns,
        initial_quota_state=initial_quota_state,
        plan_config=plan_tier,
        pricing_models=pricing_models,
        fx_rate=fx_rate,
    )
    res["model_id"] = model_id
    return res


def simulate_archetype(
    archetype_id: str,
    initial_quota_state: Optional[Dict[str, Any]] = None,
    plan_tier: str = "pro",
    pricing_models: Optional[Dict[str, Any]] = None,
    fx_rate: float = DEFAULT_FX_RATE,
) -> Dict[str, Any]:
    """
    Execute simulation using one of the 5 standard archetype presets.
    """
    presets = get_archetype_presets()
    if archetype_id not in presets:
        raise ValueError(
            f"Unknown archetype ID: '{archetype_id}'. Available presets: {list(presets.keys())}"
        )

    arch = presets[archetype_id]
    result = simulate_workload(
        model_id=arch["model_id"],
        turn_count=arch["turn_count"],
        prompt_tokens=arch["prompt_tokens"],
        cache_hit_ratio_pct=arch["cache_hit_ratio_pct"],
        thinking_tokens=arch["thinking_tokens"],
        answer_tokens=arch["answer_tokens"],
        duration_minutes_per_turn=arch["duration_minutes_per_turn"],
        initial_quota_state=initial_quota_state,
        plan_tier=plan_tier,
        pricing_models=pricing_models,
        fx_rate=fx_rate,
    )
    result["archetype_id"] = archetype_id
    result["archetype_name"] = arch["name"]
    result["archetype_description"] = arch["description"]
    result["model_id"] = arch["model_id"]
    return result


def compare_plan_tiers(
    workload_spec: Dict[str, Any],
    initial_quota_state: Optional[Dict[str, Any]] = None,
    pricing_models: Optional[Dict[str, Any]] = None,
    fx_rate: float = DEFAULT_FX_RATE,
) -> List[Dict[str, Any]]:
    """
    Simulate the exact same workload across ['pro', 'enterprise_5x', 'ultra_10x'].

    Returns comparative summary list for tier evaluation and upgrade recommendations.
    """
    tiers = ["pro", "enterprise_5x", "ultra_10x"]
    tier_names = {
        "pro": "Google AI Pro (2 TB)",
        "enterprise_5x": "Google AI Ultra (20 TB - 5x AI Usage)",
        "ultra_5x": "Google AI Ultra (20 TB - 5x AI Usage)",
        "ultra_10x": "Antigravity Ultra (10x Capacity)",
    }

    summaries: List[Dict[str, Any]] = []

    for tier in tiers:
        if "turns" in workload_spec:
            sim = simulate_turn_sequence(
                turns=workload_spec["turns"],
                initial_quota_state=initial_quota_state,
                plan_config=tier,
                pricing_models=pricing_models,
                fx_rate=fx_rate,
            )
        elif "archetype_id" in workload_spec:
            sim = simulate_archetype(
                archetype_id=workload_spec["archetype_id"],
                initial_quota_state=initial_quota_state,
                plan_tier=tier,
                pricing_models=pricing_models,
                fx_rate=fx_rate,
            )
        else:
            sim = simulate_workload(
                model_id=workload_spec.get("model_id", "1318"),
                turn_count=workload_spec.get("turn_count", 25),
                prompt_tokens=workload_spec.get("prompt_tokens", 50000),
                cache_hit_ratio_pct=workload_spec.get("cache_hit_ratio_pct", 80.0),
                thinking_tokens=workload_spec.get("thinking_tokens", 2000),
                answer_tokens=workload_spec.get("answer_tokens", 1000),
                duration_minutes_per_turn=workload_spec.get("duration_minutes_per_turn", 2.0),
                initial_quota_state=initial_quota_state,
                plan_tier=tier,
                pricing_models=pricing_models,
                fx_rate=fx_rate,
            )

        summaries.append({
            "tier": tier,
            "tier_name": tier_names.get(tier, tier),
            "burst_capacity_usd": sim["burst_capacity_usd"],
            "final_5h_used_usd": sim["final_5h_used_usd"],
            "final_5h_used_pct": sim["final_5h_used_pct"],
            "burst_exhausted": sim["burst_exhausted"],
            "turns_to_exhaustion": sim["turns_to_exhaustion"],
            "over_burst_usd": sim["over_burst_usd"],
            "credits_debited": sim["credits_debited"],
            "risk_level": sim["risk_level"],
            "status_label": sim["status_label"],
        })

    return summaries
