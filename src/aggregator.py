"""
Analytics and aggregation engine for Antigravity token telemetry.

Decomposed into cohesive submodules:
  - aggregator_pricing: rate cards, credit burn, subagent classification, timestamp parsing
  - aggregator_cycles: weekly/monthly cycle bounds, exhaustion alarms, quota runway, daily velocity
  - aggregator_windows: rolling windows, recovery schedules, historical peaks, conversation telemetry
  - aggregator_coaching: simulation presets, cache coaching, live ticker
  - aggregator_attribution: workspace grouping, Git reflog project/branch attribution
  - aggregator_quotas: provider quota silos, session decoration, credit bank reconciliation

All public symbols are re-exported here for 100% backward compatibility.
"""

import datetime
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple, Union

DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "antigravity_vault.db"

# Re-export pricing & model rate helpers
from src.aggregator_pricing import (
    DEFAULT_PRICING_FILE,
    DEFAULT_SUBSCRIPTION_FILE,
    SUBAGENT_MODEL_IDS,
    calculate_credit_burn,
    classify_turn_type,
    compute_subagent_metrics,
    compute_turn_cost,
    get_model_display_name,
    get_model_rates,
    get_provider_quota_track,
    load_currency_config,
    load_subscription_config,
    parse_timestamp,
)

# Re-export cycle & runway helpers
from src.aggregator_cycles import (
    WEEKDAY_MAP,
    compute_daily_velocity,
    compute_exhaustion_alarm_state,
    compute_quota_runway,
    get_monthly_billing_bounds,
    get_weekly_cycle_bounds,
)

# Re-export window & conversation helpers
from src.aggregator_windows import (
    aggregate_conversation_telemetry,
    compute_historical_peaks,
    compute_rolling_window_telemetry,
    compute_window_recovery_schedule,
)

# Re-export coaching & simulation helpers
from src.aggregator_coaching import (
    compute_cache_coaching_metrics,
    compute_live_ticker,
    compute_simulation_presets,
)

# Re-export attribution helpers
from src.aggregator_attribution import (
    compute_agent_workflow_attribution,
    compute_project_branch_attribution,
    compute_workspace_metrics,
    extract_project_branch_attribution,
    normalize_exhaustion_intervals,
)

# Re-export quota silos & reconciliation helpers
from src.aggregator_quotas import (
    compute_provider_quota_silos,
    decorate_active_sessions,
    reconcile_credit_burn_and_overage,
)

# Upstream and sibling re-exports preserved for backward compatibility
from antigravity_telemetry import load_model_census
from src.git_timeline import resolve_turn_branch
from src.simulator import (
    compare_plan_tiers,
    get_archetype_presets,
    simulate_archetype,
    simulate_workload,
)
from src.temporal import (
    TemporalPricingResolver,
    get_temporal_resolver,
    load_pricing,
    load_raw_pricing,
    parse_temporal_timestamp,
)
from src.horizon_analytics import compute_horizon_analytics

__all__ = [
    "DEFAULT_PRICING_FILE",
    "DEFAULT_SUBSCRIPTION_FILE",
    "SUBAGENT_MODEL_IDS",
    "WEEKDAY_MAP",
    "TemporalPricingResolver",
    "aggregate_conversation_telemetry",
    "aggregate_global_telemetry",
    "calculate_credit_burn",
    "classify_session_mode",
    "classify_turn_type",
    "compare_plan_tiers",
    "compute_cache_coaching_metrics",
    "compute_daily_velocity",
    "compute_exhaustion_alarm_state",
    "compute_historical_peaks",
    "compute_horizon_analytics",
    "compute_live_ticker",
    "compute_agent_workflow_attribution",
    "compute_project_branch_attribution",
    "compute_provider_quota_silos",
    "compute_quota_runway",
    "compute_rolling_window_telemetry",
    "compute_simulation_presets",
    "compute_subagent_metrics",
    "compute_turn_cost",
    "compute_window_recovery_schedule",
    "compute_workspace_metrics",
    "decorate_active_sessions",
    "detect_file_churn",
    "extract_project_branch_attribution",
    "get_archetype_presets",
    "get_model_display_name",
    "get_model_rates",
    "get_monthly_billing_bounds",
    "get_provider_quota_track",
    "get_temporal_resolver",
    "get_weekly_cycle_bounds",
    "is_session_file_churn",
    "load_currency_config",
    "load_model_census",
    "load_pricing",
    "load_raw_pricing",
    "load_subscription_config",
    "normalize_exhaustion_intervals",
    "parse_temporal_timestamp",
    "parse_timestamp",
    "reconcile_credit_burn_and_overage",
    "resolve_turn_branch",
    "simulate_archetype",
    "simulate_workload",
]


def _build_summary_payload(
    totals: Dict[str, Any],
    projects: List[Dict[str, Any]],
    sub_cfg: Dict[str, Any],
    recon: Dict[str, Any],
    weekly_cycle_bounds: Dict[str, Any],
    monthly_billing_bounds: Dict[str, Any],
    temporal_resolver: Any,
    ref_dt: datetime.datetime,
    renewal_day: int,
    gemini_multiplier: float,
    cg_multiplier: float,
    burst_limit: int,
    cache_coaching: Dict[str, Any],
    subagent_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Construct canonical dashboard summary dictionary."""
    usd_to_gbp_fx = recon["usd_to_gbp_fx"]
    currency_cfg = recon["currency_cfg"]
    total_turns = totals["total_turns"]
    total_imputed_cost = totals["total_imputed_cost"]
    bank_credits_burned = recon["bank_credits_burned"]
    total_credit_burn_usd = recon["total_credit_burn_usd"]
    total_credit_burn_gbp = recon["total_credit_burn_gbp"]
    cost_per_credit_gbp = recon["cost_per_credit_gbp"]
    cents_per_credit = recon["cents_per_credit"]
    bank_total_credits = recon["bank_total_credits"]
    bank_credits_rem = recon["bank_credits_rem"]

    return {
        "total_conversations": totals["total_conversations"],
        "discovered_databases": totals["discovered_databases"],
        "scanned_databases": totals["scanned_databases"],
        "total_turns": total_turns,
        "total_input_tokens": totals["total_input"],
        "prompt_tokens_uncached": totals["total_uncached"],
        "cached_tokens": totals["total_cached"],
        "total_output_tokens": totals["total_output"],
        "thinking_tokens": totals["total_thinking"],
        "answer_tokens": totals["total_answer"],
        "cache_hit_ratio_pct": round(totals["overall_cache_hit_ratio"], 2),
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
        "subscription_status": recon["subscription_status"],
        "tier": sub_cfg.get("tier", "pro"),
        "subscription_name": sub_cfg.get("name", "Google One AI Premium (Antigravity Pro)"),
        "monthly_subscription_price_gbp": recon["sub_price_gbp"],
        "monthly_subscription_price_usd": recon["sub_price_usd"],
        "gemini_capacity_multiplier": gemini_multiplier,
        "claude_capacity_multiplier": cg_multiplier,
        "subscription_history": temporal_resolver.subscription_history,
        "promotions": temporal_resolver.promotions,
        "active_promotions": temporal_resolver.resolve_promotions(ref_dt, provider="all"),
        "temporal_provenance": temporal_resolver.get_provenance_summary(ref_dt),
        "use_ai_credits": sub_cfg.get("use_ai_credits", True),
        "cents_per_credit": cents_per_credit,
        "burst_5h_limit_tokens": burst_limit,
        "is_near_burst_limit": recon["is_near_burst_limit"],
        "weekly_reset_utc": weekly_cycle_bounds["cycle_end_utc"],
        "weekly_reset_display": weekly_cycle_bounds["reset_display"],
        "weekly_reset_human": weekly_cycle_bounds["human_remaining"],
        "monthly_renewal_utc": monthly_billing_bounds["renewal_date"],
        "monthly_renewal_display": monthly_billing_bounds["renewal_display"],
        "monthly_renewal_human": monthly_billing_bounds["human_remaining"],
        "monthly_billing_day": renewal_day,
        "credit_bank_total": bank_total_credits,
        "packs_purchased": recon["packs_count"],
        "single_pack_price_gbp": recon["single_pack_price_gbp"],
        "single_pack_price_usd": recon["single_pack_price_usd"],
        "credit_pack_price_gbp": recon["total_pack_price_gbp"],
        "credit_pack_price_usd": recon["total_pack_price_usd"],
        "credits_remaining": bank_credits_rem,
        "credit_bank_remaining_gbp": round(bank_credits_rem * cost_per_credit_gbp, 2),
        "credit_bank_remaining_usd": round(bank_credits_rem * (cents_per_credit / 100.0), 2),
        "credit_bank_burn_pct": round((bank_credits_burned / bank_total_credits) * 100.0, 1) if bank_total_credits > 0 else 0.0,
        "monthly_cycle_tokens": recon["cycle_tokens"],
        "monthly_cycle_turns": recon["cycle_turns"],
        "monthly_cycle_imputed_value_usd": recon["cycle_imputed_usd"],
        "monthly_cycle_imputed_value_gbp": recon["cycle_imputed_gbp"],
        "monthly_subscription_roi": recon["cycle_roi"],
        "subagent_metrics": subagent_metrics,
        # Backward-compatible aliases:
        "monthly_plan_credits": bank_total_credits,
        "monthly_credits_burned": bank_credits_burned,
        "monthly_credits_remaining": bank_credits_rem,
    }


def _assemble_dashboard_payload(
    summary_payload: Dict[str, Any],
    rolling_5h: Dict[str, Any],
    rolling_1w: Dict[str, Any],
    weekly_cycle: Dict[str, Any],
    monthly_billing_bounds: Dict[str, Any],
    peaks: Dict[str, Any],
    providers_quotas: Dict[str, Any],
    runway: Dict[str, Any],
    daily_velocity: List[Dict[str, Any]],
    temporal_resolver: Any,
    ref_dt: datetime.datetime,
    simulator_presets: Dict[str, Any],
    recon: Dict[str, Any],
    by_workspace: Dict[str, Dict[str, Any]],
    projects: List[Dict[str, Any]],
    conversation_summaries: List[Dict[str, Any]],
    live_ticker: Dict[str, Any],
    horizon_analytics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Assemble complete dashboard dictionary structure."""
    return {
        "summary": summary_payload,
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
        "currency": recon["currency_cfg"],
        "hourly_credit_activity": recon["hourly_credit_activity"],
        "exhaustion_intervals": recon["serialized_intervals"],
        "workspaces": list(by_workspace.values()),
        "projects": projects,
        "conversations": conversation_summaries,
        "live_ticker": live_ticker,
        "horizon_analytics": horizon_analytics if horizon_analytics is not None else {},
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
    include_horizon_analytics: bool = True,
) -> Dict[str, Any]:
    """
    Compute overall dashboard metrics, rolling quota allowances, and dual-track cost totals.
    Fuses continuous sliding window token limits with log-anchored 429 exhaustion intervals
    and cost-weighted rate card convergence with live desktop indicator synchronization.
    """
    # 1. Compute totals and workspace grouping
    totals = {
        "total_conversations": len(conversation_summaries),
        "discovered_databases": discovered_databases if discovered_databases is not None else len(conversation_summaries),
        "scanned_databases": scanned_databases if scanned_databases is not None else len(conversation_summaries),
        "total_turns": sum(c.get("turn_count", 0) for c in conversation_summaries),
        "total_input": sum(c.get("total_input_tokens", 0) for c in conversation_summaries),
        "total_uncached": sum(c.get("prompt_tokens_uncached", 0) for c in conversation_summaries),
        "total_cached": sum(c.get("cached_tokens", 0) for c in conversation_summaries),
        "total_output": sum(c.get("total_output_tokens", 0) for c in conversation_summaries),
        "total_thinking": sum(c.get("thinking_tokens", 0) for c in conversation_summaries),
        "total_answer": sum(c.get("answer_tokens", 0) for c in conversation_summaries),
        "total_imputed_cost": sum(c.get("estimated_cost_usd", 0.0) for c in conversation_summaries),
    }
    totals["overall_cache_hit_ratio"] = (totals["total_cached"] / totals["total_input"] * 100.0) if totals["total_input"] > 0 else 0.0

    by_workspace = compute_workspace_metrics(conversation_summaries)

    # 2. Extract project and branch attribution with incident allocation
    normalized_intervals = normalize_exhaustion_intervals(exhaustion_intervals)
    projects = extract_project_branch_attribution(
        conversation_summaries=conversation_summaries,
        pricing_models=pricing_models,
        exhaustion_intervals=normalized_intervals,
    )

    # 3. Collect flat turns and reference time
    flat_turns = all_raw_turns or []
    if not flat_turns:
        for c in conversation_summaries:
            flat_turns.extend(c.get("turns", []))

    ref_dt = reference_time or datetime.datetime.now(datetime.timezone.utc)
    if ref_dt.tzinfo is None:
        ref_dt = ref_dt.replace(tzinfo=datetime.timezone.utc)

    # 4. Rolling windows & historical peaks
    rolling_5h = compute_rolling_window_telemetry(
        flat_turns, window_hours=5.0, reference_time=ref_dt, pricing_models=pricing_models
    )
    recovery_schedule = compute_window_recovery_schedule(
        flat_turns, window_hours=5.0, reference_time=ref_dt, limit=5, pricing_models=pricing_models
    )
    rolling_5h["recovery_schedule"] = recovery_schedule

    rolling_1w = compute_rolling_window_telemetry(
        flat_turns, window_hours=168.0, reference_time=ref_dt, pricing_models=pricing_models
    )
    peaks = compute_historical_peaks(flat_turns, pricing_models=pricing_models)

    # 5. Weekly cycle bounds & rolling telemetry
    explicit_reset = None
    gw_live_reset = (live_quota.get("gemini_weekly") or {}).get("reset_time") if live_quota and live_quota.get("available") else None
    if gw_live_reset:
        explicit_reset = parse_timestamp(gw_live_reset)

    weekly_cycle_bounds = get_weekly_cycle_bounds(ref_dt, explicit_reset_dt=explicit_reset)
    weekly_cycle_start = parse_timestamp(weekly_cycle_bounds["cycle_start_utc"])
    weekly_cycle = compute_rolling_window_telemetry(
        flat_turns,
        reference_time=ref_dt,
        pricing_models=pricing_models,
        start_time=weekly_cycle_start,
    )
    weekly_cycle.update(weekly_cycle_bounds)

    # 6. Provider quota silos (Track 1: Gemini, Track 2: Claude/GPT)
    silos = compute_provider_quota_silos(
        flat_turns=flat_turns,
        ref_dt=ref_dt,
        pricing_models=pricing_models,
        weekly_cycle_bounds=weekly_cycle_bounds,
        weekly_cycle_start=weekly_cycle_start,
        live_quota=live_quota,
    )
    providers_quotas = silos["providers_quotas"]
    gemini_5h = silos["gemini_5h"]
    gemini_weekly = silos["gemini_weekly"]
    cg_5h = silos["cg_5h"]
    cg_weekly = silos["cg_weekly"]
    gemini_turns = silos["gemini_turns"]
    gemini_multiplier = silos["gemini_multiplier"]
    cg_multiplier = silos["cg_multiplier"]
    burst_limit = silos["burst_limit"]
    gemini_weekly_capacity_usd = silos["gemini_weekly_capacity_usd"]
    sub_cfg = silos["sub_cfg"]
    exhaustion_alarm = silos["exhaustion_alarm"]
    runway = silos["runway"]

    # 7. Decorate active sessions in-place
    decorate_active_sessions(
        [
            rolling_5h.get("active_sessions_5h", []),
            gemini_5h.get("active_sessions_5h", []),
            cg_5h.get("active_sessions_5h", []),
        ],
        conversation_summaries,
    )

    # 8. Monthly billing bounds & monthly telemetry
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

    # 9. Reconcile credit bank, overage, and hourly activity
    recon = reconcile_credit_burn_and_overage(
        flat_turns=flat_turns,
        exhaustion_intervals=normalized_intervals,
        pricing_models=pricing_models,
        sub_cfg=sub_cfg,
        ref_dt=ref_dt,
        rolling_5h=rolling_5h,
        burst_limit=burst_limit,
        live_quota=live_quota,
        exhaustion_alarm=exhaustion_alarm,
        monthly_billing_bounds=monthly_billing_bounds,
    )

    temporal_resolver = get_temporal_resolver()

    # 10. Secondary aggregations: daily velocity, subagents, simulator, cache coaching, live ticker
    daily_velocity = compute_daily_velocity(
        gemini_turns,
        weekly_cycle_start=weekly_cycle_start,
        reference_time=ref_dt,
        pricing_models=pricing_models,
        weekly_capacity_usd=gemini_weekly_capacity_usd,
    )
    convo_subagent_map = {
        str(c.get("convo_id") or c.get("id") or ""): bool(
            c.get("is_subagent") or c.get("parent_convo_id") or c.get("subagent_role")
        )
        for c in conversation_summaries
        if isinstance(c, dict) and (c.get("convo_id") or c.get("id"))
    }
    subagent_metrics = compute_subagent_metrics(
        flat_turns, pricing_models, convo_subagent_map=convo_subagent_map
    )

    sim_quota_state = {
        "gemini": {
            "rolling_5h_used_usd": gemini_5h.get("imputed_value_usd", 0.0),
            "weekly_used_usd": gemini_weekly.get("imputed_value_usd", 0.0),
            "credits_remaining": recon["bank_credits_rem"],
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
        fx_rate=recon["usd_to_gbp_fx"],
    )
    cache_coaching = compute_cache_coaching_metrics(
        conversation_summaries,
        pricing_models=pricing_models,
        usd_to_gbp_fx=recon["usd_to_gbp_fx"],
    )
    live_ticker = compute_live_ticker(
        flat_turns=flat_turns,
        conversation_summaries=conversation_summaries,
        projects=projects,
        reference_time=ref_dt,
        pricing_models=pricing_models,
        gemini_5h=gemini_5h,
    )

    # 11. Assemble payload
    summary_payload = _build_summary_payload(
        totals=totals,
        projects=projects,
        sub_cfg=sub_cfg,
        recon=recon,
        weekly_cycle_bounds=weekly_cycle_bounds,
        monthly_billing_bounds=monthly_billing_bounds,
        temporal_resolver=temporal_resolver,
        ref_dt=ref_dt,
        renewal_day=renewal_day,
        gemini_multiplier=gemini_multiplier,
        cg_multiplier=cg_multiplier,
        burst_limit=burst_limit,
        cache_coaching=cache_coaching,
        subagent_metrics=subagent_metrics,
    )

    # 12. Horizon analytics (Milestone M96)
    if include_horizon_analytics:
        horizon_analytics = compute_horizon_analytics(
            turns=flat_turns,
            conversations=conversation_summaries,
            pricing_data=pricing_models if (isinstance(pricing_models, dict) and "subscription_history" in pricing_models) else None,
            ledger_incidents=normalized_intervals,
            reference_time=ref_dt,
        )
    else:
        horizon_analytics = {}

    return _assemble_dashboard_payload(
        summary_payload=summary_payload,
        rolling_5h=rolling_5h,
        rolling_1w=rolling_1w,
        weekly_cycle=weekly_cycle,
        monthly_billing_bounds=monthly_billing_bounds,
        peaks=peaks,
        providers_quotas=providers_quotas,
        runway=runway,
        daily_velocity=daily_velocity,
        temporal_resolver=temporal_resolver,
        ref_dt=ref_dt,
        simulator_presets=simulator_presets,
        recon=recon,
        by_workspace=by_workspace,
        projects=projects,
        conversation_summaries=conversation_summaries,
        live_ticker=live_ticker,
        horizon_analytics=horizon_analytics,
    )


# ==============================================================================
# Phase 2 (Milestone C): Session Mode Classification & File Churn Intelligence
# ==============================================================================

RE_BOOST_CMD = re.compile(r"""(?:^|[\s"'`(\[])[/\\]boost\b""", re.IGNORECASE)
RE_TEAMWORK_CMD = re.compile(r"""(?:^|[\s"'`(\[])[/\\]teamwork(?:-[a-z0-9_-]+)?\b""", re.IGNORECASE)
RE_GOAL_CMD = re.compile(r"""(?:^|[\s"'`(\[])[/\\]goal\b""", re.IGNORECASE)

MODIFICATION_TOOL_NAMES = {
    "replace_file_content",
    "write_to_file",
    "multi_replace_file_content",
    "write_file",
    "edit_file",
}


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely coerce any value to an integer without raising exceptions."""
    if val is None:
        return default
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    try:
        s = str(val).strip()
        return int(s) if s else default
    except (ValueError, TypeError):
        return default


def classify_session_mode(
    convo_data: Optional[Dict[str, Any]],
    steps_archive_records: Optional[Any] = None,
) -> str:
    """
    Classify the operational mode of an Antigravity session.

    Modes:
    - 'boost': Explicit /boost or \\boost in user prompt, or high thinking ratio (>= 0.30)
    - 'teamwork': Explicit /teamwork or \\teamwork in prompt, or swarm lineage (>= 2 subagents)
    - 'goal': Explicit /goal or \\goal in prompt, or marathon session (>= 300 turns)
    - 'standard': Default fallback when vault prompt text is unavailable or session is standard

    Returns one of: 'boost', 'teamwork', 'goal', 'standard'.
    """
    if convo_data is not None and not isinstance(convo_data, dict):
        return "standard"
    if convo_data is None:
        convo_data = {}

    # 1. Collect candidate prompt texts
    prompts: List[str] = []

    title = convo_data.get("title")
    if title and isinstance(title, str):
        prompts.append(title)

    for p_key in ("prompt", "user_prompt", "first_prompt", "initial_prompt"):
        p_val = convo_data.get(p_key)
        if p_val and isinstance(p_val, str):
            prompts.append(p_val)

    turns = convo_data.get("turns", [])
    if isinstance(turns, list):
        for t in turns:
            if isinstance(t, dict):
                for t_key in ("prompt", "user_input", "user_message", "message"):
                    t_val = t.get(t_key)
                    if t_val and isinstance(t_val, str):
                        prompts.append(t_val)

    if steps_archive_records is not None:
        rec_list = steps_archive_records if isinstance(steps_archive_records, (list, tuple, set)) else [steps_archive_records]
        for r in rec_list:
            if isinstance(r, str):
                prompts.append(r)
            elif isinstance(r, dict):
                stype = r.get("step_type")
                if stype in (14, "14", None):
                    txt = r.get("payload_text") or r.get("text") or r.get("prompt") or ""
                    if txt and isinstance(txt, str):
                        prompts.append(txt)
            elif isinstance(r, (list, tuple)):
                if len(r) == 1 and isinstance(r[0], str):
                    prompts.append(r[0])
                elif len(r) >= 2 and r[0] in (14, "14") and isinstance(r[1], str):
                    prompts.append(r[1])
                elif len(r) >= 3 and r[1] in (14, "14") and isinstance(r[2], str):
                    prompts.append(r[2])
                else:
                    for elem in r:
                        if isinstance(elem, str):
                            prompts.append(elem)

    # 2. Check explicit slash commands (highest precedence)
    for p in prompts:
        if RE_BOOST_CMD.search(p):
            return "boost"
        if RE_TEAMWORK_CMD.search(p):
            return "teamwork"
        if RE_GOAL_CMD.search(p):
            return "goal"

    # 3. Check heuristics: Swarm Lineage / Teamwork (>= 2 subagents)
    child_ids = convo_data.get("child_ids")
    child_count = len(child_ids) if isinstance(child_ids, (list, tuple, set)) else 0
    subagents = max(
        _safe_int(convo_data.get("subagents_count")),
        _safe_int(convo_data.get("tree_children_count")),
        child_count,
    )
    if subagents >= 2:
        return "teamwork"

    # 4. Check heuristics: Marathon Session / Goal (>= 300 turns)
    turn_cnt = _safe_int(convo_data.get("turn_count"))
    if not turn_cnt and isinstance(turns, list) and len(turns) > 0:
        turn_cnt = len(turns)
    if turn_cnt >= 300:
        return "goal"

    # 5. Check heuristics: Cognitive Rigor / Boost (high thinking ratio >= 0.30)
    thk = _safe_int(convo_data.get("thinking_tokens"))
    out_tok = _safe_int(convo_data.get("total_output_tokens")) or _safe_int(convo_data.get("output_tokens"))

    if out_tok == 0 and steps_archive_records and isinstance(steps_archive_records, (list, tuple, set)):
        for r in steps_archive_records:
            if isinstance(r, dict):
                thk += _safe_int(r.get("thinking_tokens"))
                out_tok += (
                    _safe_int(r.get("output_tokens_total"))
                    or _safe_int(r.get("output_tokens"))
                    or _safe_int(r.get("total_output_tokens"))
                )

    if out_tok > 0 and thk > 0:
        ratio = thk / float(out_tok)
        if ratio >= 0.30:
            return "boost"

    # 6. Fallback
    return "standard"


def _extract_file_paths_from_tool_call(item: Any) -> List[str]:
    """Extract modified target file paths from tool invocation."""
    paths: List[str] = []
    if isinstance(item, dict):
        t_name = str(item.get("tool_name") or item.get("name") or "").strip()
        if t_name not in MODIFICATION_TOOL_NAMES:
            return paths

        args = item.get("arguments") or item.get("args") or item.get("arguments_json")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                m = re.findall(r'"(?:TargetFile|target_file|file_path|Path|path|filename)"\s*:\s*"([^"]+)"', args)
                paths.extend(m)
                args = None

        if not isinstance(args, dict):
            args = item

        for k in ("TargetFile", "target_file", "file_path", "Path", "path", "filename", "TargetFiles", "files"):
            val = args.get(k)
            if isinstance(val, str) and val.strip():
                paths.append(val.strip())
            elif isinstance(val, (list, tuple)):
                for v in val:
                    if isinstance(v, str) and v.strip():
                        paths.append(v.strip())
    elif isinstance(item, (list, tuple)):
        t_name = None
        args_dict = None
        args_json = None
        for elem in item:
            if isinstance(elem, str) and elem in MODIFICATION_TOOL_NAMES:
                t_name = elem
            elif isinstance(elem, dict):
                args_dict = elem
            elif isinstance(elem, str) and ('"TargetFile"' in elem or '"file_path"' in elem or '"Path"' in elem or '"path"' in elem):
                args_json = elem

        if t_name:
            if args_dict is not None:
                for k in ("TargetFile", "target_file", "file_path", "Path", "path", "filename"):
                    val = args_dict.get(k)
                    if isinstance(val, str) and val.strip():
                        paths.append(val.strip())
            elif args_json is not None:
                try:
                    parsed = json.loads(args_json)
                    if isinstance(parsed, dict):
                        for k in ("TargetFile", "target_file", "file_path", "Path", "path", "filename"):
                            val = parsed.get(k)
                            if isinstance(val, str) and val.strip():
                                paths.append(val.strip())
                except (json.JSONDecodeError, TypeError):
                    m = re.findall(r'"(?:TargetFile|target_file|file_path|Path|path|filename)"\s*:\s*"([^"]+)"', args_json)
                    paths.extend(m)
    return paths


def detect_file_churn(
    tool_calls_or_convo: Any,
    threshold: int = 5,
    vault_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Detect file modification churn and thrashing within a session.

    Flags sessions where any single file has >= threshold modifications (default 5).

    Returns:
    {
        "has_churn": bool,
        "churn_files": Dict[str, int],
        "max_modifications": int,
        "total_modifications": int,
        "file_counts": Dict[str, int],
    }
    """
    counts: Dict[str, int] = {}
    v_path = Path(vault_path).resolve() if vault_path else DEFAULT_VAULT_PATH

    # Case 1: String convo_id passed, query vault
    if isinstance(tool_calls_or_convo, str) and v_path.exists():
        convo_id = tool_calls_or_convo
        conn = None
        try:
            conn = sqlite3.connect(f"file:{v_path}?mode=ro", uri=True, timeout=5.0)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT tool_name, arguments_json
                FROM tool_calls_archive
                WHERE convo_id = ? AND tool_name IN ('replace_file_content', 'write_to_file', 'multi_replace_file_content', 'write_file', 'edit_file')
                """,
                (convo_id,),
            )
            for t_name, args_json in cur.fetchall():
                for p in _extract_file_paths_from_tool_call({"tool_name": t_name, "arguments_json": args_json}):
                    counts[p] = counts.get(p, 0) + 1
        except (sqlite3.Error, OSError):
            pass
        finally:
            if conn:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass

    # Case 2: Dictionary convo_data
    elif isinstance(tool_calls_or_convo, dict):
        convo = tool_calls_or_convo
        items = []
        if "tool_calls" in convo and isinstance(convo["tool_calls"], list):
            items.extend(convo["tool_calls"])
        if "turns" in convo and isinstance(convo["turns"], list):
            for t in convo["turns"]:
                if isinstance(t, dict) and "tool_calls" in t and isinstance(t["tool_calls"], list):
                    items.extend(t["tool_calls"])

        if items:
            for it in items:
                for p in _extract_file_paths_from_tool_call(it):
                    counts[p] = counts.get(p, 0) + 1
        elif convo.get("convo_id") and v_path.exists():
            return detect_file_churn(convo["convo_id"], threshold=threshold, vault_path=v_path)

    # Case 3: List / sequence of tool calls or records
    elif isinstance(tool_calls_or_convo, (list, tuple)):
        for it in tool_calls_or_convo:
            for p in _extract_file_paths_from_tool_call(it):
                counts[p] = counts.get(p, 0) + 1

    churn_files = {f: c for f, c in counts.items() if c >= threshold}
    max_mods = max(counts.values()) if counts else 0
    has_churn = max_mods >= threshold

    return {
        "has_churn": has_churn,
        "churn_files": churn_files,
        "max_modifications": max_mods,
        "total_modifications": sum(counts.values()),
        "file_counts": counts,
    }


def is_session_file_churn(
    tool_calls_or_convo: Any,
    threshold: int = 5,
    vault_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Convenience boolean check if any single file has >= threshold modifications."""
    return detect_file_churn(tool_calls_or_convo, threshold=threshold, vault_path=vault_path)["has_churn"]
