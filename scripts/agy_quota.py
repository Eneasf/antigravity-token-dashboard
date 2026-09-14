#!/usr/bin/env python3
"""
CLI tool to inspect Antigravity desktop live quota status and pre-flight workload capacity.

Usage:
  python3 scripts/agy_quota.py [--json]
  python3 scripts/agy_quota.py --can-i-run <archetype|custom> [--turns <N>] [--model <ID>] [--allow-spillover] [--json]
"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from antigravity_telemetry import load_model_census
from scripts.agy_status import get_status_data
from src.quota_client import fetch_live_quota_summary
from src.simulator import (
    get_archetype_presets,
    get_provider_quota_track,
    simulate_workload,
)
from src.temporal import (
    PLAN_PRESETS,
    get_plan_preset,
    load_pricing,
    load_raw_pricing,
)


def run_preflight_budget_check(
    workload_type: str = "deep_refactor_swarm",
    turns: Optional[int] = None,
    model_id: Optional[str] = None,
    prompt_tokens: int = 50000,
    thinking_tokens: int = 2000,
    answer_tokens: int = 1000,
    cache_hit_ratio_pct: float = 80.0,
    allow_spillover: bool = False,
    plan_tier: Optional[str] = None,
    quota_state_override: Optional[Dict[str, Any]] = None,
    pricing_models: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Simulate a proposed multi-agent workload against live quota headroom.

    Returns a structured evaluation dictionary with a deterministic exit code:
      exit_code 0: SAFE / PROCEED
      exit_code 1: BLOCKED / 429 RISK / BURST EXHAUSTED
    """
    census = load_model_census()
    presets = get_archetype_presets()
    raw_pricing = load_raw_pricing()

    # 1. Resolve Plan Configuration
    if not plan_tier:
        plan_tier = str(raw_pricing.get("subscription", {}).get("tier", "ultra_5x"))

    plan_dict = get_plan_preset(plan_tier) or PLAN_PRESETS.get(plan_tier, PLAN_PRESETS["pro"])
    plan_name = plan_dict.get("name", plan_tier)
    ql = plan_dict.get("quota_limits", {})
    gemini_5h_cap = float(ql.get("gemini_5h_capacity_usd", 20.0))
    gemini_weekly_cap = float(ql.get("gemini_weekly_capacity_usd", 133.0))
    claude_5h_cap = float(ql.get("claude_5h_capacity_usd", 15.0))
    claude_weekly_cap = float(ql.get("claude_weekly_capacity_usd", 50.0))

    # 2. Resolve Workload Parameters
    if workload_type in presets:
        arch = deepcopy(presets[workload_type])
        target_turns = turns if turns is not None else arch["turn_count"]
        target_model = str(model_id) if model_id is not None else arch["model_id"]
        target_prompt = arch["prompt_tokens"]
        target_cache_pct = arch["cache_hit_ratio_pct"]
        target_thinking = arch["thinking_tokens"]
        target_answer = arch["answer_tokens"]
        target_duration = arch["duration_minutes_per_turn"]
        arch_id = workload_type
        arch_name = arch["name"]
    elif workload_type == "custom":
        target_turns = turns if turns is not None else 25
        target_model = str(model_id) if model_id is not None else "1318"
        target_prompt = prompt_tokens
        target_cache_pct = cache_hit_ratio_pct
        target_thinking = thinking_tokens
        target_answer = answer_tokens
        target_duration = 2.0
        arch_id = "custom"
        arch_name = "Custom Workload"
    else:
        raise ValueError(
            f"Unknown archetype ID: '{workload_type}'. Available presets: {list(presets.keys())} or 'custom'"
        )

    if target_model not in census:
        raise ValueError(
            f"Unknown model ID: '{target_model}'. Must be one of calibrated models: {list(census.keys())}"
        )

    # 3. Resolve Current Live Quota Headroom
    if quota_state_override:
        initial_quota_state = deepcopy(quota_state_override)
        rem_credits = int(initial_quota_state.get("credits_remaining", 1360))
        g5_used_pct = float(initial_quota_state.get("gemini", {}).get("used_5h_pct", 0.0))
        gw_used_pct = float(initial_quota_state.get("gemini", {}).get("used_weekly_pct", 0.0))
        c5_used_pct = float(initial_quota_state.get("claude_gpt", {}).get("used_5h_pct", 0.0))
        cw_used_pct = float(initial_quota_state.get("claude_gpt", {}).get("used_weekly_pct", 0.0))
        gemini_5h_used_usd = float(initial_quota_state.get("gemini", {}).get("starting_5h_used_usd", gemini_5h_cap * (g5_used_pct / 100.0)))
        gemini_weekly_used_usd = float(initial_quota_state.get("gemini", {}).get("starting_weekly_used_usd", gemini_weekly_cap * (gw_used_pct / 100.0)))
        claude_5h_used_usd = float(initial_quota_state.get("claude_gpt", {}).get("starting_5h_used_usd", claude_5h_cap * (c5_used_pct / 100.0)))
        claude_weekly_used_usd = float(initial_quota_state.get("claude_gpt", {}).get("starting_weekly_used_usd", claude_weekly_cap * (cw_used_pct / 100.0)))
    else:
        rem_credits = int(raw_pricing.get("credit_bank", {}).get("remaining_credits", 1360))
        live_quota = fetch_live_quota_summary()
        if live_quota and live_quota.get("available"):
            g5_used_pct = float(live_quota["gemini_5h"]["used_pct"]) if live_quota.get("gemini_5h") else 0.0
            gw_used_pct = float(live_quota["gemini_weekly"]["used_pct"]) if live_quota.get("gemini_weekly") else 0.0
            c5_used_pct = float(live_quota["claude_5h"]["used_pct"]) if live_quota.get("claude_5h") else 0.0
            cw_used_pct = float(live_quota["claude_weekly"]["used_pct"]) if live_quota.get("claude_weekly") else 0.0
        else:
            status_data = get_status_data()
            g5_used_pct = float(status_data.get("gemini_5h_pct", 0.0))
            gw_used_pct = float(status_data.get("gemini_weekly_pct", 0.0))
            c5_used_pct = float(status_data.get("claude_5h_pct", 0.0))
            cw_used_pct = float(status_data.get("claude_weekly_pct", 0.0))

        gemini_5h_used_usd = round(gemini_5h_cap * (g5_used_pct / 100.0), 4)
        gemini_weekly_used_usd = round(gemini_weekly_cap * (gw_used_pct / 100.0), 4)
        claude_5h_used_usd = round(claude_5h_cap * (c5_used_pct / 100.0), 4)
        claude_weekly_used_usd = round(claude_weekly_cap * (cw_used_pct / 100.0), 4)

        initial_quota_state = {
            "gemini": {
                "starting_5h_used_usd": gemini_5h_used_usd,
                "starting_weekly_used_usd": gemini_weekly_used_usd,
                "credits_remaining": rem_credits,
            },
            "claude_gpt": {
                "starting_5h_used_usd": claude_5h_used_usd,
                "starting_weekly_used_usd": claude_weekly_used_usd,
                "credits_remaining": rem_credits,
            },
            "credits_remaining": rem_credits,
        }

    # 4. Execute Simulation
    sim_res = simulate_workload(
        model_id=target_model,
        turn_count=target_turns,
        prompt_tokens=target_prompt,
        cache_hit_ratio_pct=target_cache_pct,
        thinking_tokens=target_thinking,
        answer_tokens=target_answer,
        duration_minutes_per_turn=target_duration,
        initial_quota_state=initial_quota_state,
        plan_tier=plan_dict,
        pricing_models=pricing_models,
    )

    provider_track = sim_res["provider_track"]
    model_meta = census.get(target_model, {})
    model_name = model_meta.get("name", target_model)

    starting_5h_used_usd = gemini_5h_used_usd if provider_track == "gemini" else claude_5h_used_usd
    starting_5h_cap = gemini_5h_cap if provider_track == "gemini" else claude_5h_cap
    starting_5h_rem_pct = round(max(0.0, 100.0 - (starting_5h_used_usd / starting_5h_cap * 100.0)), 1)

    starting_weekly_used_usd = gemini_weekly_used_usd if provider_track == "gemini" else claude_weekly_used_usd
    starting_weekly_cap = gemini_weekly_cap if provider_track == "gemini" else claude_weekly_cap
    starting_weekly_rem_pct = round(max(0.0, 100.0 - (starting_weekly_used_usd / starting_weekly_cap * 100.0)), 1)

    # 5. Evaluate Verdict & Process Exit Code
    if sim_res["hard_429_block_risk"] or sim_res["weekly_exhausted"]:
        verdict = "BLOCKED"
        verdict_label = "BLOCKED (429 RISK / EXHAUSTED)"
        reason = (
            "Weekly quota exhausted or hard HTTP 429 lockout triggered. "
            "Antigravity server will reject requests."
        )
        exit_code = 1
        safe_to_run = False
    elif sim_res["burst_exhausted"]:
        if provider_track == "claude_gpt":
            verdict = "BLOCKED"
            verdict_label = "BLOCKED (429 RISK - ZERO SPILLOVER)"
            reason = (
                f"Claude/GPT burst quota exhausted at turn {sim_res['turns_to_exhaustion']} "
                f"(exceeds allowance by ${sim_res['over_burst_usd']:.2f}). "
                "Zero credit spillover permitted on Track 2 (ADR-019 & ADR-030). Immediate HTTP 429 risk!"
            )
            exit_code = 1
            safe_to_run = False
        elif sim_res["credit_bank_exhaustion_risk"]:
            verdict = "BLOCKED"
            verdict_label = "BLOCKED (CREDIT BANK EXHAUSTION)"
            reason = (
                f"Gemini burst exhausted and requires {sim_res['credits_debited']} credits, "
                f"exceeding remaining credit bank pool ({rem_credits} credits remaining)."
            )
            exit_code = 1
            safe_to_run = False
        elif allow_spillover:
            verdict = "PROCEED_WITH_SPILLOVER"
            verdict_label = "PROCEED (CREDIT SPILLOVER ACTIVE)"
            reason = (
                f"Gemini burst allowance exceeded by ${sim_res['over_burst_usd']:.2f}; "
                f"spills over into Google One credit bank ({sim_res['credits_debited']} credits / "
                f"£{sim_res['credit_cost_gbp']:.2f} / ${sim_res['credit_cost_usd']:.2f})."
            )
            exit_code = 0
            safe_to_run = True
        else:
            verdict = "BLOCKED"
            verdict_label = "BLOCKED (BURST EXHAUSTED)"
            reason = (
                f"Gemini burst allowance exceeded by ${sim_res['over_burst_usd']:.2f} at turn {sim_res['turns_to_exhaustion']}. "
                "Credit spillover is disabled. Pass --allow-spillover to permit drawing from Google One credits."
            )
            exit_code = 1
            safe_to_run = False
    elif sim_res["final_5h_remaining_pct"] < 20.0 or sim_res["final_weekly_remaining_pct"] < 10.0:
        verdict = "PROCEED_WITH_CAUTION"
        verdict_label = "PROCEED (CAUTION - LOW HEADROOM)"
        reason = (
            f"Workload will consume significant headroom: {sim_res['final_5h_remaining_pct']:.1f}% burst headroom and "
            f"{sim_res['final_weekly_remaining_pct']:.1f}% weekly runway remaining."
        )
        exit_code = 0
        safe_to_run = True
    else:
        verdict = "SAFE_TO_PROCEED"
        verdict_label = "SAFE TO PROCEED"
        reason = (
            f"Workload is well within limits ({sim_res['final_5h_remaining_pct']:.1f}% burst headroom remaining). "
            "Safe to proceed without rate limit risk."
        )
        exit_code = 0
        safe_to_run = True

    return {
        "verdict": verdict,
        "verdict_label": verdict_label,
        "exit_code": exit_code,
        "safe_to_run": safe_to_run,
        "reason": reason,
        "recommendation": sim_res["recommendation"],
        "workload": {
            "archetype_id": arch_id,
            "archetype_name": arch_name,
            "model_id": target_model,
            "model_name": model_name,
            "provider_track": provider_track,
            "turn_count": target_turns,
            "cache_hit_ratio_pct": target_cache_pct,
            "imputed_value_usd": sim_res["imputed_value_usd"],
            "imputed_value_gbp": sim_res["imputed_value_gbp"],
            "plan_tier": plan_tier,
            "plan_name": plan_name,
        },
        "live_headroom": {
            "provider_track": provider_track,
            "burst_capacity_usd": starting_5h_cap,
            "starting_5h_used_usd": starting_5h_used_usd,
            "starting_5h_remaining_pct": starting_5h_rem_pct,
            "weekly_capacity_usd": starting_weekly_cap,
            "starting_weekly_used_usd": starting_weekly_used_usd,
            "starting_weekly_remaining_pct": starting_weekly_rem_pct,
            "credit_bank_remaining_credits": rem_credits,
        },
        "projected_state": {
            "final_5h_used_usd": sim_res["final_5h_used_usd"],
            "final_5h_used_pct": sim_res["final_5h_used_pct"],
            "final_5h_remaining_pct": sim_res["final_5h_remaining_pct"],
            "final_weekly_used_usd": sim_res["final_weekly_used_usd"],
            "final_weekly_used_pct": sim_res["final_weekly_used_pct"],
            "final_weekly_remaining_pct": sim_res["final_weekly_remaining_pct"],
            "burst_exhausted": sim_res["burst_exhausted"],
            "turns_to_exhaustion": sim_res["turns_to_exhaustion"],
            "over_burst_usd": sim_res["over_burst_usd"],
            "hard_429_block_risk": sim_res["hard_429_block_risk"],
            "credits_debited": sim_res["credits_debited"],
            "credit_cost_usd": sim_res["credit_cost_usd"],
            "credit_cost_gbp": sim_res["credit_cost_gbp"],
        },
    }


def print_preflight_summary(eval_res: Dict[str, Any]):
    """Format clean ASCII terminal summary card for pre-flight budget check."""
    w = eval_res["workload"]
    lh = eval_res["live_headroom"]
    ps = eval_res["projected_state"]

    print("=" * 70)
    print(" ANTIGRAVITY PRE-FLIGHT WORKLOAD BUDGET CHECKER")
    print("=" * 70)
    print(f" Workload Archetype   : {w['archetype_name']} ({w['archetype_id']})")
    print(f" Model                : {w['model_id']} ({w['model_name']}) [Track: {w['provider_track']}]")
    print(f" Planned Turns        : {w['turn_count']} turns")
    print(f" Cache Hit Ratio      : {w['cache_hit_ratio_pct']:.1f}%")
    print(f" Imputed Value / Cost : ${w['imputed_value_usd']:.2f} (£{w['imputed_value_gbp']:.2f})")
    print(f" Active Plan Tier     : {w['plan_name']} ({w['plan_tier']})")
    print("-" * 70)
    print(" LIVE QUOTA HEADROOM (BEFORE WORKLOAD)")
    print(
        f" 5-Hour Burst Used    : ${lh['starting_5h_used_usd']:.2f} / ${lh['burst_capacity_usd']:.2f} "
        f"({100.0 - lh['starting_5h_remaining_pct']:.1f}% used -> {lh['starting_5h_remaining_pct']:.1f}% remaining)"
    )
    print(
        f" Weekly Allowance     : ${lh['starting_weekly_used_usd']:.2f} / ${lh['weekly_capacity_usd']:.2f} "
        f"({100.0 - lh['starting_weekly_remaining_pct']:.1f}% used -> {lh['starting_weekly_remaining_pct']:.1f}% remaining)"
    )
    if w["provider_track"] == "gemini":
        print(f" Credit Bank Headroom : {lh['credit_bank_remaining_credits']} credits available")
    print("-" * 70)
    print(" PROJECTED POST-WORKLOAD HEADROOM")
    print(
        f" Projected 5h Burst   : {ps['final_5h_used_pct']:.1f}% used -> {ps['final_5h_remaining_pct']:.1f}% remaining"
    )
    print(
        f" Projected Weekly     : {ps['final_weekly_used_pct']:.1f}% used -> {ps['final_weekly_remaining_pct']:.1f}% remaining"
    )
    print(f" Burst Exhausted      : {'YES (Turn ' + str(ps['turns_to_exhaustion']) + ')' if ps['burst_exhausted'] else 'No'}")
    print(f" 429 Lockout Risk     : {'CRITICAL (HTTP 429)' if ps['hard_429_block_risk'] else 'No'}")
    if ps["credits_debited"] > 0:
        print(f" Credit Spillover     : {ps['credits_debited']} credits debited (£{ps['credit_cost_gbp']:.2f} / ${ps['credit_cost_usd']:.2f})")
    else:
        print(" Credit Spillover     : None (0 credits debited)")
    print("-" * 70)
    print(f" VERDICT: [{eval_res['verdict_label']}] (exit {eval_res['exit_code']})")
    print(f" Reason : {eval_res['reason']}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Query Antigravity desktop live quota status and pre-flight budget.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON response")
    parser.add_argument(
        "--can-i-run",
        type=str,
        default=None,
        metavar="ARCHETYPE",
        help="Simulate a workload archetype ('deep_refactor_swarm', 'codebase_audit', 'rapid_prototyping_burst', 'claude_opus_deep_dive', 'subagent_fleet', or 'custom')",
    )
    parser.add_argument("--turns", type=int, default=None, help="Turn count override for workload simulation")
    parser.add_argument("--model", type=str, default=None, help="Model ID override for workload simulation")
    parser.add_argument("--prompt-tokens", type=int, default=50000, help="Prompt tokens per turn for custom workload (default: 50,000)")
    parser.add_argument("--thinking-tokens", type=int, default=2000, help="Thinking tokens per turn for custom workload (default: 2,000)")
    parser.add_argument("--answer-tokens", type=int, default=1000, help="Answer tokens per turn for custom workload (default: 1,000)")
    parser.add_argument("--cache-hit-pct", type=float, default=80.0, help="Cache hit percentage for custom workload (default: 80.0%%)")
    parser.add_argument("--plan", type=str, default=None, help="Plan tier override (e.g. 'pro', 'ultra_5x')")
    parser.add_argument(
        "--allow-spillover",
        action="store_true",
        help="Allow Gemini 5h burst spillover into Google One credit bank as SAFE/PROCEED (exit 0)",
    )

    args = parser.parse_args()

    # Pre-Flight Workload Budget Checker Mode
    if args.can_i_run:
        try:
            eval_res = run_preflight_budget_check(
                workload_type=args.can_i_run,
                turns=args.turns,
                model_id=args.model,
                prompt_tokens=args.prompt_tokens,
                thinking_tokens=args.thinking_tokens,
                answer_tokens=args.answer_tokens,
                cache_hit_ratio_pct=args.cache_hit_pct,
                allow_spillover=args.allow_spillover,
                plan_tier=args.plan,
            )
        except ValueError as e:
            print(f"[-] Error in pre-flight budget check: {e}", file=sys.stderr)
            sys.exit(2)

        if args.json:
            print(json.dumps(eval_res, indent=2))
        else:
            print_preflight_summary(eval_res)

        sys.exit(eval_res["exit_code"])

    # Standard Quota Status Inspection Mode
    quota = fetch_live_quota_summary()
    if not quota or not quota.get("available"):
        print("[-] Antigravity desktop language server is not running or quota is unavailable.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(quota, indent=2))
        return

    print("=" * 60)
    print(" ANTIGRAVITY LIVE DESKTOP QUOTA STATUS")
    print("=" * 60)

    gw = quota.get("gemini_weekly")
    g5 = quota.get("gemini_5h")
    cw = quota.get("claude_weekly")
    c5 = quota.get("claude_5h")

    if gw:
        print(f"\n[Track 1: Gemini Models - Weekly]")
        print(f"  Remaining: {gw['remaining_pct']}% (Used: {gw['used_pct']}%)")
        print(f"  Reset Time: {gw['reset_time']}")
        if gw.get("description"):
            print(f"  Status: {gw['description']}")

    if g5:
        print(f"\n[Track 1: Gemini Models - 5-Hour Burst]")
        print(f"  Remaining: {g5['remaining_pct']}% (Used: {g5['used_pct']}%)")
        print(f"  Reset Time: {g5['reset_time']}")
        if g5.get("description"):
            print(f"  Status: {g5['description']}")

    if cw:
        print(f"\n[Track 2: Claude & GPT Models - Weekly]")
        print(f"  Remaining: {cw['remaining_pct']}% (Used: {cw['used_pct']}%)")
        print(f"  Reset Time: {cw['reset_time']}")

    if c5:
        print(f"\n[Track 2: Claude & GPT Models - 5-Hour Burst]")
        print(f"  Remaining: {c5['remaining_pct']}% (Used: {c5['used_pct']}%)")
        print(f"  Reset Time: {c5['reset_time']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

