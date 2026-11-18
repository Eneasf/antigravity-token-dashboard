"""
Workspace grouping, Git reflog project/branch attribution, and incident overage allocation.
"""

from collections import defaultdict
import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from src.aggregator_pricing import (
    calculate_credit_burn,
    get_provider_quota_track,
    parse_timestamp,
)
from src.git_timeline import resolve_turn_branch


def compute_workspace_metrics(
    conversation_summaries: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Group conversation summaries by workspace and compute aggregate token and cost totals."""
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

    return by_workspace


def normalize_exhaustion_intervals(
    exhaustion_intervals: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Auto-extract log exhaustion intervals if not supplied and normalize start/end to datetimes."""
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
    return normalized_intervals


def extract_project_branch_attribution(
    conversation_summaries: List[Dict[str, Any]],
    pricing_models: Dict[str, Any],
    exhaustion_intervals: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Hierarchical grouping by project and Git branch with dual-track cost accounting (ADR-022 / ADR-046).
    Allocates confirmed ledger incidents and live 429 intervals across projects, branches, and conversations.
    """
    currency_cfg = pricing_models.get("currency", {})
    usd_to_gbp_fx = currency_cfg.get("usd_to_gbp_fx_rate", 0.79)
    sub_cfg = pricing_models.get("subscription", {})
    pack_cfg = currency_cfg.get("credit_pack", {})
    cents_per_credit = sub_cfg.get("cents_per_credit", 1.0)
    cost_per_credit_gbp = pack_cfg.get("cost_per_credit_gbp", 0.009596)

    normalized_intervals = normalize_exhaustion_intervals(exhaustion_intervals)
    ledger_intervals = [
        inv for inv in normalized_intervals
        if inv.get("from_ledger")
        and inv.get("reason") != "QUOTA_RESET_BONUS"
        and inv.get("event_type") != "QUOTA_RESET_BONUS"
    ]
    live_intervals = [inv for inv in normalized_intervals if not inv.get("from_ledger")]

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
                    "last_active_timestamp": "",
                }
            return b_map[b_name]

        turns = c.get("turns", [])
        fallback_branch = c.get("git_branch") or "main"

        if not turns:
            # Metadata-only conversation without individual turn objects
            b = _get_or_init_branch(fallback_branch)
            c_mod = c.get("last_modified") or c.get("first_turn_ts") or ""
            if isinstance(c_mod, (int, float)):
                c_mod = datetime.datetime.fromtimestamp(c_mod, tz=datetime.timezone.utc).isoformat()
            if c_mod and (not b.get("last_active_timestamp") or str(c_mod) > str(b.get("last_active_timestamp"))):
                b["last_active_timestamp"] = str(c_mod)
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
                    t_ts = t.get("timestamp") or ""
                    if t_ts and (not b.get("last_active_timestamp") or str(t_ts) > str(b.get("last_active_timestamp"))):
                        b["last_active_timestamp"] = str(t_ts)
                    t_dt = parse_timestamp(t_ts)
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

        # Sort branches within project in reverse chronological order (newest activity on top)
        branches_list.sort(
            key=lambda b: (b.get("last_active_timestamp") or "", b["total_input_tokens"] + b["total_output_tokens"]),
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

    return projects


compute_project_branch_attribution = extract_project_branch_attribution


def compute_agent_workflow_attribution(
    conversation_summaries: List[Dict[str, Any]],
    pricing_models: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute workflow role cost and token attribution (Auditor vs Implementer vs General).
    Child subagents inherit and roll up into their parent session's workflow role.
    """
    if pricing_models is None:
        from src.temporal import load_pricing
        pricing_models = load_pricing()

    currency_cfg = pricing_models.get("currency", {})
    usd_to_gbp_fx = currency_cfg.get("usd_to_gbp_fx_rate", 0.79)

    convo_agent_map: Dict[str, str] = {}
    convo_parent_map: Dict[str, str] = {}
    for c in conversation_summaries:
        cid = c.get("convo_id", "")
        if cid:
            convo_agent_map[cid] = c.get("agent_name") or "default"
            pid = c.get("parent_convo_id")
            if pid:
                convo_parent_map[cid] = pid

    def resolve_workflow_role(cid: str) -> str:
        visited = set()
        curr = cid
        while curr and curr in convo_parent_map and curr not in visited:
            visited.add(curr)
            curr = convo_parent_map[curr]
        return convo_agent_map.get(curr, convo_agent_map.get(cid, "default"))

    roles = {
        "auditor": {
            "role": "auditor",
            "display_name": "Auditor",
            "conversation_count": 0,
            "subagent_count": 0,
            "turn_count": 0,
            "direct_tokens": 0,
            "subagent_tokens": 0,
            "total_input_tokens": 0,
            "cached_tokens": 0,
            "total_output_tokens": 0,
            "thinking_tokens": 0,
            "total_tokens": 0,
            "direct_cost_usd": 0.0,
            "subagent_cost_usd": 0.0,
            "imputed_cost_usd": 0.0,
            "imputed_cost_gbp": 0.0,
        },
        "implementer": {
            "role": "implementer",
            "display_name": "Implementer",
            "conversation_count": 0,
            "subagent_count": 0,
            "turn_count": 0,
            "direct_tokens": 0,
            "subagent_tokens": 0,
            "total_input_tokens": 0,
            "cached_tokens": 0,
            "total_output_tokens": 0,
            "thinking_tokens": 0,
            "total_tokens": 0,
            "direct_cost_usd": 0.0,
            "subagent_cost_usd": 0.0,
            "imputed_cost_usd": 0.0,
            "imputed_cost_gbp": 0.0,
        },
        "default": {
            "role": "default",
            "display_name": "General Assistant",
            "conversation_count": 0,
            "subagent_count": 0,
            "turn_count": 0,
            "direct_tokens": 0,
            "subagent_tokens": 0,
            "total_input_tokens": 0,
            "cached_tokens": 0,
            "total_output_tokens": 0,
            "thinking_tokens": 0,
            "total_tokens": 0,
            "direct_cost_usd": 0.0,
            "subagent_cost_usd": 0.0,
            "imputed_cost_usd": 0.0,
            "imputed_cost_gbp": 0.0,
        },
    }

    for c in conversation_summaries:
        cid = c.get("convo_id", "")
        wf_role = resolve_workflow_role(cid)
        if wf_role not in roles:
            wf_role = "default"
        entry = roles[wf_role]

        is_sub = bool(c.get("is_subagent"))
        inp = c.get("total_input_tokens", 0)
        out = c.get("total_output_tokens", 0)
        cac = c.get("cached_tokens", 0)
        thk = c.get("thinking_tokens", 0)
        cost = c.get("avoided_cost_usd", c.get("estimated_cost_usd", 0.0))
        toks = inp + out

        if is_sub:
            entry["subagent_count"] += 1
            entry["subagent_tokens"] += toks
            entry["subagent_cost_usd"] += cost
        else:
            entry["conversation_count"] += 1
            entry["direct_tokens"] += toks
            entry["direct_cost_usd"] += cost

        entry["turn_count"] += c.get("turn_count", 0)
        entry["total_input_tokens"] += inp
        entry["cached_tokens"] += cac
        entry["total_output_tokens"] += out
        entry["thinking_tokens"] += thk
        entry["total_tokens"] += toks
        entry["imputed_cost_usd"] += cost

    total_cost_all = sum(r["imputed_cost_usd"] for r in roles.values())
    total_tokens_all = sum(r["total_tokens"] for r in roles.values())
    total_sessions = len(conversation_summaries)
    subagent_sessions = sum(1 for c in conversation_summaries if c.get("is_subagent"))
    main_sessions = total_sessions - subagent_sessions

    for r in roles.values():
        inp = r["total_input_tokens"]
        cac = r["cached_tokens"]
        r["cache_hit_ratio_pct"] = round((cac / inp * 100.0) if inp > 0 else 0.0, 2)
        r["direct_cost_usd"] = round(r["direct_cost_usd"], 4)
        r["subagent_cost_usd"] = round(r["subagent_cost_usd"], 4)
        r["imputed_cost_usd"] = round(r["imputed_cost_usd"], 4)
        r["imputed_cost_gbp"] = round(r["imputed_cost_usd"] * usd_to_gbp_fx, 4)
        r["share_pct"] = round((r["imputed_cost_usd"] / total_cost_all * 100.0) if total_cost_all > 0 else 0.0, 1)

    return {
        "by_role": roles,
        "total_sessions": total_sessions,
        "main_sessions": main_sessions,
        "subagent_sessions": subagent_sessions,
        "total_tokens": total_tokens_all,
        "total_imputed_cost_usd": round(total_cost_all, 4),
        "total_imputed_cost_gbp": round(total_cost_all * usd_to_gbp_fx, 4),
    }

