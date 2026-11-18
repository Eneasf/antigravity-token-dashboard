"""
Coaching metrics, KV cache flip detection, multi-agent workload simulation, and live token ticker.
"""

from collections import defaultdict
import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from src.aggregator_pricing import (
    get_model_display_name,
    get_model_rates,
    get_provider_quota_track,
    parse_timestamp,
)
from src.simulator import (
    compare_plan_tiers,
    get_archetype_presets,
    simulate_archetype,
    simulate_workload,
)


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
    raw_archetypes = get_archetype_presets()
    plan_tier = (plan_config or {}).get("tier", "pro") if plan_config else "pro"
    pro_era_model_map = {
        "deep_refactor_swarm": "1016",
        "claude_opus_deep_dive": "1026",
        "subagent_fleet": "1050",
    }

    archetypes: Dict[str, Dict[str, Any]] = {}
    results: Dict[str, Any] = {}
    for arch_id, raw_spec in raw_archetypes.items():
        arch_spec = dict(raw_spec)
        if plan_tier == "pro" and arch_id in pro_era_model_map:
            arch_spec["model_id"] = pro_era_model_map[arch_id]
        archetypes[arch_id] = arch_spec

        sim_res = simulate_workload(
            model_id=arch_spec["model_id"],
            turn_count=arch_spec["turn_count"],
            prompt_tokens=arch_spec["prompt_tokens"],
            cache_hit_ratio_pct=arch_spec["cache_hit_ratio_pct"],
            thinking_tokens=arch_spec["thinking_tokens"],
            answer_tokens=arch_spec["answer_tokens"],
            duration_minutes_per_turn=arch_spec["duration_minutes_per_turn"],
            initial_quota_state=initial_quota_state,
            plan_tier=plan_tier,
            pricing_models=pricing_models,
            fx_rate=fx_rate,
        )
        sim_res["archetype_id"] = arch_id
        sim_res["archetype_name"] = arch_spec["name"]
        sim_res["archetype_description"] = arch_spec["description"]
        sim_res["model_id"] = arch_spec["model_id"]

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


try:
    from antigravity_telemetry import (
        load_model_catalog,
        load_model_census,
        resolve_wire_model_id,
    )
except ImportError:
    def load_model_census() -> Dict[str, Any]:
        return {}

    def load_model_catalog() -> Dict[str, Any]:
        return {}

    def resolve_wire_model_id(raw_id: Any, catalog: Optional[Dict[str, Any]] = None) -> str:
        return str(raw_id or "unknown").strip()

try:
    from src.temporal import load_pricing
except ImportError:
    def load_pricing() -> Dict[str, Any]:
        return {}

FALLBACK_FAMILIES = {
    "1018": "gemini-flash",
    "1027": "claude-opus",
}


def normalize_model_id(raw_mid: Any) -> str:
    """Normalize model ID by resolving wire aliases and stripping placeholders via antigravity_telemetry."""
    if raw_mid is None:
        return "unknown"
    s = str(raw_mid).strip()
    if not s or s.lower() == "unknown":
        return "unknown"
    return resolve_wire_model_id(s)


def is_kv_cache_wiped(prev_mid: Any, curr_mid: Any, total_inp: int, cached_tok: int) -> bool:
    """
    Return True when a mid-session model switch past 40k tokens wipes the KV cache (<20% hit rate) (GADR-018).
    Even intra-family thinking-level changes (e.g. 1427 -> 1437 or 1318 -> 1320) invalidate the KV cache.
    """
    p_norm = normalize_model_id(prev_mid)
    c_norm = normalize_model_id(curr_mid)
    if not p_norm or not c_norm or p_norm == "unknown" or c_norm == "unknown" or p_norm == c_norm:
        return False
    inp = int(total_inp or 0)
    cac = int(cached_tok or 0)
    if inp < 40000:
        return False
    return (cac / inp) < 0.20


def get_model_family(
    model_id: str,
    pricing_models: Optional[Dict[str, Any]] = None,
    census: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Resolve model family for KV cache affinity grouping:
      - 'gemini-carbon' (1427, 1437, 1438)
      - 'gemini-orchestrator' (1667, 1681 planners; 1669 Hydrogen executor)
      - 'gemini-hydrogen' (1525, 1526, 1527, 1528)
      - 'gemini-argon' (1417, 1418, 1419)
      - 'gemini-flash' (1318, 1319, 1320, 1298, 1299, 1300, 1071, 1072, 1073, 1018, 1020, 1322, 1132, 1301)
      - 'gemini-pro' (1016, 1036)
      - 'gemini-flash-lite' (1050, 1198)
      - 'claude-sonnet' (1035, 1403, 1404, 1405)
      - 'claude-opus' (1026, 1027, 1400, 1401, 1402)
      - 'gpt-oss' (342)
    """
    norm_mid = normalize_model_id(model_id)
    if pricing_models:
        m_map = pricing_models.get("models", pricing_models)
        if isinstance(m_map, dict) and norm_mid in m_map and isinstance(m_map[norm_mid], dict):
            fam = m_map[norm_mid].get("family")
            if fam:
                return str(fam).strip().lower()
        if norm_mid in pricing_models and isinstance(pricing_models[norm_mid], dict):
            fam = pricing_models[norm_mid].get("family")
            if fam:
                return str(fam).strip().lower()

    if census is None:
        try:
            census = load_model_census()
        except Exception:
            census = {}

    if census and norm_mid in census and isinstance(census[norm_mid], dict):
        fam = census[norm_mid].get("family")
        if fam:
            return str(fam).strip().lower()

    if norm_mid in FALLBACK_FAMILIES:
        return FALLBACK_FAMILIES[norm_mid]

    low = norm_mid.lower()
    if "orchestrator" in low or norm_mid in ("1667", "1669", "1681"):
        return "gemini-orchestrator"
    if "hydrogen" in low or norm_mid in ("1525", "1526", "1527", "1528"):
        return "gemini-hydrogen"
    if "carbon" in low:
        return "gemini-carbon"
    if "argon" in low:
        return "gemini-argon"
    if "flash-lite" in low:
        return "gemini-flash-lite"
    if "flash" in low:
        return "gemini-flash"
    if "pro" in low:
        return "gemini-pro"
    if "opus" in low:
        return "claude-opus"
    if "sonnet" in low:
        return "claude-sonnet"
    if "gpt" in low:
        return "gpt-oss"

    return "unknown"


def compute_cache_coaching_metrics(
    conversation_summaries: List[Dict[str, Any]],
    pricing_models: Optional[Dict[str, Any]] = None,
    usd_to_gbp_fx: float = 0.79,
) -> Dict[str, Any]:
    """
    Detect cross-provider, intra-family, and intra-track model flips that evict KV caches,
    causing massive uncached prompt replays. Quantifies wasted tokens, avoided cost,
    and provides GADR-018 coaching guidance.
    (ADR-030 / GADR-018 / M94).
    """
    if pricing_models is None:
        try:
            pricing_models = load_pricing()
        except Exception:
            pricing_models = {}

    try:
        census = load_model_census()
    except Exception:
        census = {}

    total_flips = 0
    cross_provider_flips = 0
    intra_family_flips = 0
    intra_track_flips = 0

    wasted_tokens_total = 0
    wasted_cost_usd_total = 0.0
    incidents: List[Dict[str, Any]] = []

    for convo in conversation_summaries:
        cid = convo.get("convo_id") or convo.get("conversation_id") or convo.get("id", "")
        title = convo.get("title", "Untitled Session")
        ws_name = convo.get("workspace_name", "Unknown Workspace")
        turns = convo.get("turns", [])
        if len(turns) < 2:
            continue

        for i in range(1, len(turns)):
            prev_t = turns[i - 1]
            curr_t = turns[i]

            prev_raw_m = prev_t.get("model") or prev_t.get("model_id") or "unknown"
            curr_raw_m = curr_t.get("model") or curr_t.get("model_id") or "unknown"
            prev_mid = normalize_model_id(prev_raw_m)
            curr_mid = normalize_model_id(curr_raw_m)

            if not prev_mid or not curr_mid or prev_mid == "unknown" or curr_mid == "unknown":
                continue
            if prev_mid == curr_mid:
                continue

            prev_track = prev_t.get("quota_track") or get_provider_quota_track(prev_mid, pricing_models)
            curr_track = curr_t.get("quota_track") or get_provider_quota_track(curr_mid, pricing_models)

            prev_family = get_model_family(prev_mid, pricing_models, census)
            curr_family = get_model_family(curr_mid, pricing_models, census)

            curr_cached = int(curr_t.get("cached") if curr_t.get("cached") is not None else curr_t.get("cached_tokens", 0))
            curr_uncached = curr_t.get("prompt_tokens_uncached")

            if curr_t.get("input") is not None:
                curr_input = int(curr_t["input"])
                if curr_uncached is None:
                    curr_uncached = max(0, curr_input - curr_cached)
                else:
                    curr_uncached = int(curr_uncached)
            elif curr_uncached is not None:
                curr_uncached = int(curr_uncached)
                curr_input = curr_uncached + curr_cached
            elif curr_t.get("total_input_tokens") is not None:
                curr_input = int(curr_t["total_input_tokens"])
                if curr_uncached is None:
                    curr_uncached = max(0, curr_input - curr_cached)
                else:
                    curr_uncached = int(curr_uncached)
            else:
                curr_input = curr_cached
                curr_uncached = 0

            prev_cached = int(prev_t.get("cached") if prev_t.get("cached") is not None else prev_t.get("cached_tokens", 0))

            hit_ratio = (curr_cached / curr_input) if curr_input > 0 else 0.0

            is_cross_provider = (
                prev_track != curr_track
                and prev_track in ("gemini", "claude_gpt")
                and curr_track in ("gemini", "claude_gpt")
            )
            is_intra_family = (
                prev_track == curr_track
                and prev_family == curr_family
                and prev_family != "unknown"
            )
            is_intra_track = (
                prev_track == curr_track
                and not is_intra_family
            )

            is_flip = False
            flip_type = ""

            if is_cross_provider:
                flip_type = "cross_provider"
                if curr_input >= 40000 or (curr_input >= 25000 and hit_ratio < 0.50):
                    is_flip = True
            elif is_intra_family:
                flip_type = "intra_family"
                if is_kv_cache_wiped(prev_mid, curr_mid, curr_input, curr_cached):
                    is_flip = True
            elif is_intra_track:
                flip_type = "intra_track"
                if is_kv_cache_wiped(prev_mid, curr_mid, curr_input, curr_cached):
                    is_flip = True

            if not is_flip:
                continue

            # In steady-state, cache hit is ~90% of input, or the warm cache from prev_turn was evicted
            wasted_tokens = max(int(curr_input * 0.90) - curr_cached, prev_cached - curr_cached, 0)
            if wasted_tokens <= 0:
                continue

            curr_cost = curr_t.get("cost")
            curr_uncached_cost = curr_t.get("uncached_cost")
            if curr_cost is not None and curr_uncached_cost is not None:
                wasted_cost = max(0.0, float(curr_cost) - float(curr_uncached_cost) * 0.10)
            else:
                rates = get_model_rates(curr_mid, pricing_models, timestamp=curr_t.get("timestamp"))
                prompt_rate = rates.get("prompt_uncached", rates.get("prompt_price_per_m", 0.0))
                cache_rate = rates.get("prompt_cached", rates.get("cached_price_per_m", 0.0))
                diff_rate = max(0.0, prompt_rate - cache_rate)
                wasted_cost = (wasted_tokens / 1_000_000.0) * diff_rate

            total_flips += 1
            if flip_type == "cross_provider":
                cross_provider_flips += 1
            elif flip_type == "intra_family":
                intra_family_flips += 1
            elif flip_type == "intra_track":
                intra_track_flips += 1

            wasted_tokens_total += wasted_tokens
            wasted_cost_usd_total += wasted_cost

            from_model_name = get_model_display_name(prev_mid, pricing_models)
            to_model_name = get_model_display_name(curr_mid, pricing_models)

            incidents.append({
                "convo_id": cid,
                "title": title,
                "workspace_name": ws_name,
                "timestamp": curr_t.get("timestamp"),
                "step_idx": curr_t.get("step_idx") or curr_t.get("turn"),
                "flip_type": flip_type,
                "from_model": from_model_name,
                "to_model": to_model_name,
                "from_track": prev_track,
                "to_track": curr_track,
                "from_family": prev_family,
                "to_family": curr_family,
                "total_input_tokens": curr_input,
                "uncached_tokens": curr_uncached,
                "cached_tokens": curr_cached,
                "wasted_tokens": wasted_tokens,
                "wasted_cost_usd": round(wasted_cost, 4),
                "wasted_cost_gbp": round(wasted_cost * usd_to_gbp_fx, 4),
            })

    # Sort incidents by wasted tokens descending
    incidents.sort(key=lambda x: x["wasted_tokens"], reverse=True)

    if total_flips == 0:
        severity = "none"
        coaching_tip = "Zero model flips detected. KV cache continuity is optimal across all active sessions."
    elif total_flips >= 3 or wasted_cost_usd_total >= 1.0 or wasted_tokens_total >= 200000:
        severity = "high"
    else:
        severity = "medium"

    if total_flips > 0:
        tips = []
        if intra_family_flips > 0:
            tips.append(
                "GADR-018 Warning: Mid-session reasoning effort / model dropdown switches "
                "(Carbon / Argon High/Med/Low or Flash) evict 100% of the KV cache (~12 warm turns of quota burn); "
                "switch tiers only at Turn 1 or delegate to Model: 'flash' subagents."
            )
        if cross_provider_flips > 0:
            tips.append(
                "Cross-provider model flips (Gemini ↔ Claude) evict KV caches, "
                "incurring up to 80k uncached token re-reads. Stick to one provider family within deep coding sessions."
            )
        if intra_track_flips > 0 and intra_family_flips == 0:
            tips.append(
                "Intra-track model switches (e.g. Carbon ↔ Argon ↔ Flash) evict KV caches at deep context. "
                "Prefer delegating routine sub-tasks to Model: 'flash' subagents rather than switching the parent model mid-session."
            )
        coaching_tip = " ".join(tips)

    return {
        "cross_model_flips": total_flips,
        "model_flips_detected": total_flips,
        "cross_provider_flips": cross_provider_flips,
        "intra_family_flips": intra_family_flips,
        "intra_track_flips": intra_track_flips,
        "wasted_uncached_tokens": wasted_tokens_total,
        "estimated_flip_waste_tokens": wasted_tokens_total,
        "wasted_avoided_cost_usd": round(wasted_cost_usd_total, 4),
        "estimated_flip_waste_usd": round(wasted_cost_usd_total, 4),
        "wasted_avoided_cost_gbp": round(wasted_cost_usd_total * usd_to_gbp_fx, 4),
        "estimated_flip_waste_gbp": round(wasted_cost_usd_total * usd_to_gbp_fx, 4),
        "top_incidents": incidents[:10],
        "flip_incidents": incidents,
        "coaching_tip": coaching_tip,
        "severity": severity,
    }


def compute_live_ticker(
    flat_turns: List[Dict[str, Any]],
    conversation_summaries: List[Dict[str, Any]],
    projects: List[Dict[str, Any]],
    reference_time: Optional[datetime.datetime] = None,
    pricing_models: Optional[Dict[str, Any]] = None,
    gemini_5h: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Calculate instantaneous short-window token velocity and active turn metadata
    for the live 3-second Token Ticker HUD (ADR-053 / M39 & M40).
    """
    ref_dt = reference_time or datetime.datetime.now(datetime.timezone.utc)
    if ref_dt.tzinfo is None:
        ref_dt = ref_dt.replace(tzinfo=datetime.timezone.utc)

    window_5m = datetime.timedelta(minutes=5)
    tokens_in_5m = 0
    turns_in_5m = 0

    latest_turn = None
    latest_dt = None

    for t in flat_turns:
        ts = t.get("timestamp")
        t_dt = parse_timestamp(ts)
        if not t_dt:
            continue
        if latest_dt is None or t_dt > latest_dt:
            latest_dt = t_dt
            latest_turn = t
        if (ref_dt - window_5m) <= t_dt <= (ref_dt + datetime.timedelta(seconds=10)):
            tok = t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0) + t.get("output_tokens_total", 0)
            if tok == 0 and t.get("total_input_tokens"):
                tok = t.get("total_input_tokens", 0) + t.get("total_output_tokens", 0)
            tokens_in_5m += tok
            turns_in_5m += 1

    burn_rate_tok_per_min = int(round(tokens_in_5m / 5.0))
    burn_rate_tok_per_sec = round(tokens_in_5m / 300.0, 1)

    # Active Project & Branch resolution
    active_project = "Default"
    active_branch = "main"
    if projects:
        active_project = projects[0].get("project_name", "Default")
        branches = projects[0].get("branches", [])
        if branches:
            active_branch = branches[0].get("branch_name", "main")

    if latest_turn and latest_dt:
        seconds_ago = max(0, int((ref_dt - latest_dt).total_seconds()))
        last_tok = latest_turn.get("prompt_tokens_uncached", 0) + latest_turn.get("cached_tokens", 0) + latest_turn.get("output_tokens_total", 0)
        if last_tok == 0 and latest_turn.get("total_input_tokens"):
            last_tok = latest_turn.get("total_input_tokens", 0) + latest_turn.get("total_output_tokens", 0)
        last_prompt = latest_turn.get("prompt_tokens_uncached", 0) + latest_turn.get("cached_tokens", 0)
        if last_prompt == 0:
            last_prompt = latest_turn.get("total_input_tokens", 0)
        last_cached = latest_turn.get("cached_tokens", 0)
        last_out = latest_turn.get("output_tokens_total", 0) or latest_turn.get("total_output_tokens", 0)
        last_thoughts = latest_turn.get("thoughts_tokens", 0) or latest_turn.get("thinking_tokens", 0)
        last_cache_pct = round((last_cached / float(last_prompt) * 100.0), 1) if last_prompt > 0 else 0.0

        mid = str(latest_turn.get("model_id") or "")
        model_cfg = {}
        if pricing_models:
            model_cfg = pricing_models.get(mid) or pricing_models.get("models", {}).get(mid) or {}
        last_model = latest_turn.get("model_name") or model_cfg.get("name") or (f"Model {mid}" if mid else "Unknown Model")
        last_ts = latest_turn.get("timestamp") or latest_dt.isoformat()

        # If turn is within 120s, classify as actively streaming
        is_streaming = (seconds_ago <= 120)
        if burn_rate_tok_per_min == 0 and seconds_ago <= 60:
            burn_rate_tok_per_min = int(round(last_tok / max(1.0, seconds_ago / 60.0)))
            burn_rate_tok_per_sec = round(last_tok / max(1.0, float(seconds_ago)), 1)
    else:
        seconds_ago = 999999
        last_tok = 0
        last_prompt = 0
        last_cached = 0
        last_out = 0
        last_thoughts = 0
        last_cache_pct = 0.0
        last_model = ""
        last_ts = ""
        is_streaming = False

    # Extract 5h burst totals from rolling telemetry
    g5h_tokens = 0
    g5h_rem_pct = 100.0
    g5h_used_pct = 0.0
    if gemini_5h:
        g5h_tokens = int(gemini_5h.get("total_processed", gemini_5h.get("total_processed_tokens", 0)))
        g5h_rem_pct = float(gemini_5h.get("remaining_pct", 100.0))
        g5h_used_pct = float(gemini_5h.get("used_pct", 0.0))

    return {
        "burn_rate_tok_per_min": burn_rate_tok_per_min,
        "burn_rate_tok_per_sec": burn_rate_tok_per_sec,
        "recent_turns_5m": turns_in_5m,
        "recent_tokens_5m": tokens_in_5m,
        "last_turn_tokens": last_tok,
        "last_turn_prompt": last_prompt,
        "last_turn_cached": last_cached,
        "last_turn_cache_pct": last_cache_pct,
        "last_turn_output": last_out,
        "last_turn_thoughts": last_thoughts,
        "last_turn_model": last_model,
        "last_turn_ts": last_ts,
        "seconds_since_last_turn": seconds_ago,
        "active_project": active_project,
        "active_branch": active_branch,
        "is_streaming": is_streaming,
        "gemini_5h_tokens": g5h_tokens,
        "gemini_5h_remaining_pct": g5h_rem_pct,
        "gemini_5h_used_pct": g5h_used_pct,
    }
