"""
Deterministic Horizon Analytics Engine (Milestone M96).

Computes 5-horizon analytics, model-family partitioning, two-era progression series,
and 24-hour diurnal latency profiles across Google Antigravity workspaces.
"""

from collections import defaultdict
import datetime
import math
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from antigravity_telemetry import load_model_catalog, resolve_wire_model_id
from src.aggregator_cycles import get_monthly_billing_bounds, get_weekly_cycle_bounds
from src.aggregator_pricing import (
    SUBAGENT_MODEL_IDS,
    compute_turn_cost,
    get_model_display_name,
    get_model_rates,
    parse_timestamp,
)
from src.temporal import load_pricing, load_raw_pricing

DEFAULT_ERA_CUTOVER_UTC = "2026-09-13T17:58:04Z"

CANONICAL_FAMILIES: List[str] = [
    "gemini_carbon",
    "gemini_orchestrator",
    "gemini_argon",
    "gemini_hydrogen",
    "gemini_flash",
    "gemini_pro",
    "claude",
    "other",
]

HORIZON_KEYS: List[str] = [
    "active_week",
    "current_month",
    "pro_era",
    "ultra_era",
    "lifetime",
]

HORIZON_LABELS: Dict[str, str] = {
    "active_week": "Active Week",
    "current_month": "Current Month",
    "pro_era": "Pro Era",
    "ultra_era": "Ultra 5x Era",
    "lifetime": "Lifetime",
}


def resolve_era_cutover(pricing_data: Optional[Dict[str, Any]]) -> str:
    """Resolve the era cutover timestamp from subscription_history or default."""
    if pricing_data and "subscription_history" in pricing_data:
        sub_hist = pricing_data["subscription_history"]
        if isinstance(sub_hist, list):
            for entry in sub_hist:
                if isinstance(entry, dict) and entry.get("tier") in ("ultra_5x", "ultra") and entry.get("valid_from"):
                    return str(entry["valid_from"])
    return DEFAULT_ERA_CUTOVER_UTC


def classify_model_family(
    model_id: Any,
    model_name: Optional[str] = None,
    pricing_models: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Classify turn model into one of 6 canonical family buckets:
    - gemini_carbon: if 'carbon' or 1427/1437/1438 in model_id/name lower
    - gemini_argon: if 'argon' or 1417/1418/1419 in model_id/name lower
    - gemini_flash: if 'flash' or 'fast' in model_id/name lower
    - gemini_pro: if 'gemini' and 'pro' in model_id/name lower
    - claude: if 'claude', 'sonnet', or 'opus' in model_id/name lower
    - other: fallback
    """
    raw_mid = str(model_id or "")
    mid = resolve_wire_model_id(raw_mid) if raw_mid else ""
    if mid:
        catalog = load_model_catalog()
        models_meta = catalog.get("models", {})
        families_meta = catalog.get("families", {})
        if mid in models_meta:
            fam_id = models_meta[mid].get("family", "")
            horizon_key = families_meta.get(fam_id, {}).get("horizon_key")
            if horizon_key in CANONICAL_FAMILIES:
                return str(horizon_key)

    mname = str(model_name or "")
    if not mname and mid and pricing_models:
        mname = get_model_display_name(mid, pricing_models)
    target = f"{raw_mid} {mid} {mname}".lower()

    if "orchestrator" in target or mid in ("1667", "1669", "1681"):
        return "gemini_orchestrator"
    if "carbon" in target or mid in ("1427", "1437", "1438"):
        return "gemini_carbon"
    if "hydrogen" in target or mid in ("1525", "1526", "1527", "1528"):
        return "gemini_hydrogen"
    if "argon" in target or mid in ("1417", "1418", "1419"):
        return "gemini_argon"
    if "flash" in target or "fast" in target:
        return "gemini_flash"
    if "gemini" in target and "pro" in target:
        return "gemini_pro"
    if "claude" in target or "sonnet" in target or "opus" in target:
        return "claude"
    return "other"


def _calc_percentile(sorted_vals: List[float], p: float) -> float:
    """Compute exact percentile with linear interpolation."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(sorted_vals[int(k)], 2)
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return round(d0 + d1, 2)


def _is_subagent_turn(turn: Dict[str, Any], convo_map: Dict[str, bool]) -> bool:
    """Determine whether turn belongs to a subagent session."""
    if "is_subagent" in turn and turn["is_subagent"] is not None:
        return bool(turn["is_subagent"])
    cid = str(turn.get("convo_id") or "")
    if cid and cid in convo_map:
        return convo_map[cid]
    mid = str(turn.get("model_id") or "")
    if mid in SUBAGENT_MODEL_IDS:
        return True
    return False


def _is_rate_limit(turn: Dict[str, Any]) -> bool:
    """Check if turn encountered rate limit / 429 error."""
    rl = turn.get("rate_limit_flag")
    if rl is not None and (rl == 1 or rl is True):
        return True
    if turn.get("is_rate_limit"):
        return True
    err = str(turn.get("error_code") or "")
    if "429" in err or "RESOURCE_EXHAUSTED" in err:
        return True
    status = str(turn.get("status") or "")
    if "RESOURCE_EXHAUSTED" in status:
        return True
    return False


def _calc_latency_and_tps(turns_list: List[Dict[str, Any]]) -> Tuple[float, float, float, float]:
    """Returns (latency_p50_ms, latency_p95_ms, latency_mean_ms, tokens_per_sec)."""
    lats = [
        float(t["latency_ms"])
        for t in turns_list
        if t.get("latency_ms") is not None and float(t["latency_ms"]) > 0
    ]
    if lats:
        sorted_lats = sorted(lats)
        mean_lat = round(sum(sorted_lats) / len(sorted_lats), 2)
        p50 = _calc_percentile(sorted_lats, 50.0)
        p95 = _calc_percentile(sorted_lats, 95.0)
    else:
        mean_lat = 0.0
        p50 = 0.0
        p95 = 0.0

    turns_with_lat = [
        t for t in turns_list
        if t.get("latency_ms") is not None and float(t["latency_ms"]) > 0
    ]
    if turns_with_lat:
        tot_sec = sum(float(t["latency_ms"]) for t in turns_with_lat) / 1000.0
        tot_out = sum(t.get("output_tokens_total", 0) for t in turns_with_lat)
        if tot_out == 0:
            tot_out = sum(
                (t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0) + t.get("output_tokens_total", 0))
                for t in turns_with_lat
            )
        tps = round(tot_out / tot_sec, 2) if tot_sec > 0 else 0.0
    else:
        tps = 0.0

    return p50, p95, mean_lat, tps


def _sum_overage_gbp(
    incidents: List[Dict[str, Any]],
    start_dt: datetime.datetime,
    end_dt: datetime.datetime,
) -> float:
    """Sum credit burn GBP for ledger incidents within [start_dt, end_dt]."""
    tot = 0.0
    for inc in incidents:
        ts = inc.get("hour_timestamp") or inc.get("start_utc") or inc.get("timestamp")
        inc_dt = parse_timestamp(ts)
        if inc_dt and start_dt <= inc_dt <= end_dt:
            tot += float(inc.get("credit_burn_gbp") or 0.0)
    return round(tot, 2)


def _aggregate_horizon_metrics(
    key: str,
    label: str,
    start_utc: str,
    end_utc: str,
    h_turns: List[Dict[str, Any]],
    subscription_cost_gbp: float,
    overage_cost_gbp: float,
    convo_map: Dict[str, bool],
    pricing_models: Dict[str, Any],
    fx_rate: float,
) -> Dict[str, Any]:
    """Compute the 34 standard metrics for a single horizon."""
    total_turns = len(h_turns)
    uncached = sum(t.get("prompt_tokens_uncached", 0) for t in h_turns)
    cached = sum(t.get("cached_tokens", 0) for t in h_turns)
    total_input = uncached + cached
    total_output = sum(t.get("output_tokens_total", 0) for t in h_turns)
    thinking = sum(t.get("thinking_tokens", 0) for t in h_turns)
    answer = sum(t.get("answer_tokens", 0) for t in h_turns)
    total_processed = total_input + total_output

    cache_hit_pct = round((cached / total_input * 100.0), 2) if total_input > 0 else 0.0
    thinking_share_pct = round((thinking / total_output * 100.0), 2) if total_output > 0 else 0.0

    cost_usd = 0.0
    for t in h_turns:
        mid = str(t.get("model_id") or "default")
        rates = get_model_rates(mid, pricing_models, timestamp=t.get("timestamp"))
        cost_usd += compute_turn_cost(t, rates=rates)
    imputed_cost_usd = round(cost_usd, 2)
    imputed_cost_gbp = round(imputed_cost_usd * fx_rate, 2)

    total_spend = round(subscription_cost_gbp + overage_cost_gbp, 2)
    roi_multiplier = round(imputed_cost_gbp / total_spend, 2) if total_spend > 0 else 0.0

    sub_turns_cnt = 0
    sub_tokens = 0
    interactive_tokens = 0
    for t in h_turns:
        t_toks = t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0) + t.get("output_tokens_total", 0)
        if _is_subagent_turn(t, convo_map):
            sub_turns_cnt += 1
            sub_tokens += t_toks
        else:
            interactive_tokens += t_toks
    subagent_share_pct = round((sub_tokens / total_processed * 100.0), 2) if total_processed > 0 else 0.0

    rl_turns = sum(1 for t in h_turns if _is_rate_limit(t))
    rl_per_1k = round((rl_turns / total_turns * 1000.0), 2) if total_turns > 0 else 0.0

    p50, p95, mean_lat, tps = _calc_latency_and_tps(h_turns)

    dates: Set[str] = set()
    for t in h_turns:
        t_dt = parse_timestamp(t.get("timestamp"))
        if t_dt:
            dates.add(t_dt.strftime("%Y-%m-%d"))
    active_days = max(1, len(dates)) if total_turns > 0 else 1

    daily_avg_tokens = round(total_processed / active_days, 2)
    daily_avg_turns = round(total_turns / active_days, 2)
    daily_avg_value_gbp = round(imputed_cost_gbp / active_days, 2)
    daily_output_vel = round(total_output / active_days, 2)

    fam_map = {fam: 0 for fam in CANONICAL_FAMILIES}
    for t in h_turns:
        fam = classify_model_family(t.get("model_id"), t.get("model_name"), pricing_models)
        t_toks = t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0) + t.get("output_tokens_total", 0)
        fam_map[fam] += t_toks

    return {
        "key": key,
        "label": label,
        "start_utc": start_utc,
        "end_utc": end_utc,
        "active_days": active_days,
        "total_turns": total_turns,
        "total_input_tokens": total_input,
        "cached_tokens": cached,
        "prompt_tokens_uncached": uncached,
        "cache_hit_ratio_pct": cache_hit_pct,
        "total_output_tokens": total_output,
        "thinking_tokens": thinking,
        "answer_tokens": answer,
        "thinking_share_pct": thinking_share_pct,
        "total_processed_tokens": total_processed,
        "total_tokens": total_processed,
        "imputed_cost_usd": imputed_cost_usd,
        "imputed_cost_gbp": imputed_cost_gbp,
        "subscription_cost_gbp": round(subscription_cost_gbp, 2),
        "subscription_cost_usd": round(subscription_cost_gbp / fx_rate, 2),
        "overage_cost_gbp": round(overage_cost_gbp, 2),
        "roi_multiplier": roi_multiplier,
        "subagent_turns": sub_turns_cnt,
        "subagent_tokens": sub_tokens,
        "interactive_tokens": interactive_tokens,
        "subagent_share_pct": subagent_share_pct,
        "rate_limit_turns": rl_turns,
        "rate_limit_count": rl_turns,
        "rate_limit_per_1k_turns": rl_per_1k,
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
        "latency_mean_ms": mean_lat,
        "wire_latency_p50_ms": p50,
        "wire_latency_p95_ms": p95,
        "tokens_per_sec": tps,
        "tokens_per_second": tps,
        "daily_avg_tokens": daily_avg_tokens,
        "daily_avg_turns": daily_avg_turns,
        "daily_avg_value_gbp": daily_avg_value_gbp,
        "daily_token_velocity": daily_avg_tokens,
        "daily_turn_throughput": daily_avg_turns,
        "daily_output_velocity": daily_output_vel,
        "by_family": fam_map,
    }


def _aggregate_progression_bucket(
    bucket_key: str,
    label: str,
    start_utc: str,
    end_utc: str,
    era: str,
    b_turns: List[Dict[str, Any]],
    subscription_cost_gbp: float,
    overage_gbp: float,
    convo_map: Dict[str, bool],
    pricing_models: Dict[str, Any],
    fx_rate: float,
) -> Dict[str, Any]:
    """Compute the 28 standard metrics for a progression series bucket."""
    turns_cnt = len(b_turns)
    uncached = sum(t.get("prompt_tokens_uncached", 0) for t in b_turns)
    cached = sum(t.get("cached_tokens", 0) for t in b_turns)
    input_toks = uncached + cached
    output_toks = sum(t.get("output_tokens_total", 0) for t in b_turns)
    total_tokens = input_toks + output_toks
    thinking = sum(t.get("thinking_tokens", 0) for t in b_turns)
    answer = sum(t.get("answer_tokens", 0) for t in b_turns)

    cache_hit_pct = round((cached / input_toks * 100.0), 2) if input_toks > 0 else 0.0
    thinking_share_pct = round((thinking / output_toks * 100.0), 2) if output_toks > 0 else 0.0

    cost_usd = 0.0
    for t in b_turns:
        mid = str(t.get("model_id") or "default")
        rates = get_model_rates(mid, pricing_models, timestamp=t.get("timestamp"))
        cost_usd += compute_turn_cost(t, rates=rates)
    imputed_cost_usd = round(cost_usd, 2)
    imputed_cost_gbp = round(imputed_cost_usd * fx_rate, 2)

    total_spend = round(subscription_cost_gbp + overage_gbp, 2)
    roi_multiplier = round(imputed_cost_gbp / total_spend, 2) if total_spend > 0 else 0.0

    sub_tokens = 0
    interactive_tokens = 0
    for t in b_turns:
        t_toks = t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0) + t.get("output_tokens_total", 0)
        if _is_subagent_turn(t, convo_map):
            sub_tokens += t_toks
        else:
            interactive_tokens += t_toks
    subagent_share_pct = round((sub_tokens / total_tokens * 100.0), 2) if total_tokens > 0 else 0.0

    rl_turns = sum(1 for t in b_turns if _is_rate_limit(t))
    rl_per_1k = round((rl_turns / turns_cnt * 1000.0), 2) if turns_cnt > 0 else 0.0

    p50, p95, mean_lat, tps = _calc_latency_and_tps(b_turns)

    fam_map = {fam: 0 for fam in CANONICAL_FAMILIES}
    for t in b_turns:
        fam = classify_model_family(t.get("model_id"), t.get("model_name"), pricing_models)
        t_toks = t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0) + t.get("output_tokens_total", 0)
        fam_map[fam] += t_toks

    return {
        "bucket_key": bucket_key,
        "label": label,
        "start_utc": start_utc,
        "end_utc": end_utc,
        "era": era,
        "turns": turns_cnt,
        "total_tokens": total_tokens,
        "cached_tokens": cached,
        "uncached_tokens": uncached,
        "thinking_tokens": thinking,
        "answer_tokens": answer,
        "cache_hit_pct": cache_hit_pct,
        "thinking_share_pct": thinking_share_pct,
        "subagent_tokens": sub_tokens,
        "interactive_tokens": interactive_tokens,
        "subagent_share_pct": subagent_share_pct,
        "imputed_cost_gbp": imputed_cost_gbp,
        "imputed_cost_usd": imputed_cost_usd,
        "api_value_gbp": imputed_cost_gbp,
        "api_value_usd": imputed_cost_usd,
        "date": bucket_key,
        "thinking_pct": thinking_share_pct,
        "subscription_cost_gbp": round(subscription_cost_gbp, 2),
        "overage_gbp": round(overage_gbp, 2),
        "roi_multiplier": roi_multiplier,
        "rate_limit_turns": rl_turns,
        "rate_limit_per_1k_turns": rl_per_1k,
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
        "latency_mean_ms": mean_lat,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "tokens_per_sec": tps,
        "by_family": fam_map,
    }


def _compute_diurnal_profile_for_turns(
    turns_list: List[Dict[str, Any]],
    pricing_models: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Compute 24-hour diurnal profile (00:00 - 23:00) with family stratification."""
    hourly_turns: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for t in turns_list:
        dt = parse_timestamp(t.get("timestamp"))
        if dt:
            hourly_turns[dt.hour].append(t)

    result = []
    for h in range(24):
        h_turns = hourly_turns.get(h, [])
        turns_cnt = len(h_turns)
        total_tokens = sum(
            (t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0) + t.get("output_tokens_total", 0))
            for t in h_turns
        )
        p50, p95, mean_lat, tps = _calc_latency_and_tps(h_turns)

        fam_tokens = {fam: 0 for fam in CANONICAL_FAMILIES}
        fam_latencies: Dict[str, List[float]] = {fam: [] for fam in CANONICAL_FAMILIES}
        for t in h_turns:
            fam = classify_model_family(t.get("model_id"), t.get("model_name"), pricing_models)
            t_toks = t.get("prompt_tokens_uncached", 0) + t.get("cached_tokens", 0) + t.get("output_tokens_total", 0)
            fam_tokens[fam] += t_toks
            lat = t.get("latency_ms")
            if lat is not None and float(lat) > 0:
                fam_latencies[fam].append(float(lat))

        fam_latency_ms = {}
        for fam in CANONICAL_FAMILIES:
            l_list = fam_latencies[fam]
            fam_latency_ms[fam] = _calc_percentile(sorted(l_list), 50.0) if l_list else 0.0

        result.append({
            "hour": h,
            "hour_utc": h,
            "label": f"{h:02d}:00",
            "hour_display": f"{h:02d}:00",
            "turns": turns_cnt,
            "total_tokens": total_tokens,
            "latency_p50_ms": p50,
            "latency_p95_ms": p95,
            "latency_mean_ms": mean_lat,
            "tokens_per_sec": tps,
            "by_family_tokens": fam_tokens,
            "by_family_latency_ms": fam_latency_ms,
            "by_family": {
                "Gemini 4 Carbon": fam_tokens.get("gemini_carbon", 0),
                "Gemini 4 Orchestrator": fam_tokens.get("gemini_orchestrator", 0),
                "Gemini 4 Hydrogen": fam_tokens.get("gemini_hydrogen", 0),
                "Gemini 3.8 Flash": fam_tokens.get("gemini_flash", 0),
                "Gemini 3.1 Pro": fam_tokens.get("gemini_pro", 0),
                "Gemini 4 Argon": fam_tokens.get("gemini_argon", 0),
                "Claude": fam_tokens.get("claude", 0),
            },
            "latency_by_model": {
                "Gemini 4 Carbon": fam_latency_ms.get("gemini_carbon", 0.0),
                "Gemini 4 Orchestrator": fam_latency_ms.get("gemini_orchestrator", 0.0),
                "Gemini 4 Hydrogen": fam_latency_ms.get("gemini_hydrogen", 0.0),
                "Gemini 3.8 Flash": fam_latency_ms.get("gemini_flash", 0.0),
                "Gemini 3.1 Pro": fam_latency_ms.get("gemini_pro", 0.0),
                "Gemini 4 Argon": fam_latency_ms.get("gemini_argon", 0.0),
                "Claude": fam_latency_ms.get("claude", 0.0),
            },
        })
    return result


def load_merged_vault_and_live_turns(
    vault_path: Optional[Union[Path, str]],
    live_turns: List[Dict[str, Any]],
    live_conversations: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Merge historical turns and conversations from SQLite vault with live turns and conversations,
    deduplicating by (convo_id, step_idx).

    Queries v_turns joined with conversations_archive in read-only URI mode.
    """
    if not vault_path:
        return list(live_turns), list(live_conversations)

    v_path = Path(vault_path)
    if not v_path.exists():
        return list(live_turns), list(live_conversations)

    merged_turns: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, int]] = set()
    convo_subagent_map: Dict[str, bool] = {}

    try:
        conn = sqlite3.connect(f"file:{v_path.resolve()}?mode=ro", uri=True, timeout=5.0)
        try:
            cur = conn.cursor()
            try:
                for row in cur.execute("SELECT convo_id, is_subagent FROM conversations_archive"):
                    cid, is_sub = row[0], bool(row[1])
                    if cid:
                        convo_subagent_map[str(cid)] = is_sub
            except sqlite3.Error:
                pass

            query = """
                SELECT
                    v.convo_id,
                    v.step_idx,
                    v.timestamp,
                    v.model_id,
                    v.model_name,
                    v.prompt_tokens_uncached,
                    v.cached_tokens,
                    v.total_input_tokens,
                    v.output_tokens_total,
                    v.thinking_tokens,
                    v.total_tokens,
                    v.rate_limit_flag,
                    v.error_code,
                    v.ttft_ms,
                    v.latency_ms,
                    COALESCE(c.is_subagent, 0) AS is_subagent
                FROM v_turns v
                LEFT JOIN conversations_archive c ON v.convo_id = c.convo_id
            """
            for row in cur.execute(query):
                cid = str(row[0] or "")
                s_idx = int(row[1] or 0)
                seen_keys.add((cid, s_idx))
                tot_out = int(row[8] or 0)
                thk = int(row[9] or 0)
                ans = max(0, tot_out - thk)
                merged_turns.append({
                    "convo_id": cid,
                    "step_idx": s_idx,
                    "timestamp": row[2],
                    "model_id": str(row[3] or ""),
                    "model_name": row[4] or "",
                    "prompt_tokens_uncached": int(row[5] or 0),
                    "cached_tokens": int(row[6] or 0),
                    "total_input_tokens": int(row[7] or 0),
                    "output_tokens_total": tot_out,
                    "thinking_tokens": thk,
                    "answer_tokens": ans,
                    "total_tokens": int(row[10] or 0),
                    "is_rate_limit": bool(row[11]),
                    "rate_limit_flag": bool(row[11]),
                    "error_code": row[12],
                    "ttft_ms": float(row[13]) if row[13] is not None else None,
                    "latency_ms": float(row[14]) if row[14] is not None else None,
                    "is_subagent": bool(row[15]),
                })
        finally:
            conn.close()
    except Exception:
        return list(live_turns), list(live_conversations)

    for t in live_turns:
        cid = str(t.get("convo_id") or "")
        s_idx = int(t.get("step_idx") or 0)
        if (cid, s_idx) not in seen_keys:
            seen_keys.add((cid, s_idx))
            merged_turns.append(t)

    merged_convos: List[Dict[str, Any]] = list(live_conversations)
    live_convo_ids = {str(c.get("convo_id") or c.get("id") or "") for c in live_conversations if (c.get("convo_id") or c.get("id"))}
    for cid, is_sub in convo_subagent_map.items():
        if cid not in live_convo_ids:
            merged_convos.append({
                "convo_id": cid,
                "id": cid,
                "is_subagent": is_sub,
            })
            live_convo_ids.add(cid)

    return merged_turns, merged_convos


def compute_horizon_analytics(
    turns: List[Dict[str, Any]],
    conversations: Optional[List[Dict[str, Any]]] = None,
    pricing_data: Optional[Dict[str, Any]] = None,
    ledger_incidents: Optional[List[Dict[str, Any]]] = None,
    reference_time: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    """
    Deterministic horizon analytics engine for Antigravity telemetry (Milestone M96).
    """
    if pricing_data is None:
        try:
            pricing_data = load_raw_pricing()
        except Exception:
            pricing_data = {}

    pricing_models = pricing_data.get("models") or load_pricing()
    fx_rate = float(pricing_data.get("currency", {}).get("usd_to_gbp_fx_rate", 0.79))
    incidents = ledger_incidents or []

    # Map conversation subagent flag
    convo_map: Dict[str, bool] = {}
    if conversations:
        for c in conversations:
            cid = c.get("id") or c.get("convo_id")
            if cid:
                convo_map[str(cid)] = bool(c.get("is_subagent"))

    # Cutover timestamp
    era_cutover_utc = resolve_era_cutover(pricing_data)
    cutover_dt = parse_timestamp(era_cutover_utc)
    if cutover_dt is None:
        cutover_dt = datetime.datetime(2026, 9, 13, 17, 58, 4, tzinfo=datetime.timezone.utc)

    # Reference time
    if reference_time is not None:
        ref_dt = reference_time
        if ref_dt.tzinfo is None:
            ref_dt = ref_dt.replace(tzinfo=datetime.timezone.utc)
        else:
            ref_dt = ref_dt.astimezone(datetime.timezone.utc)
    else:
        latest_ts = None
        if turns:
            valid_ts = [parse_timestamp(t.get("timestamp")) for t in turns if parse_timestamp(t.get("timestamp"))]
            if valid_ts:
                latest_ts = max(valid_ts)
        ref_dt = latest_ts or datetime.datetime.now(datetime.timezone.utc)

    is_ultra_ref = ref_dt >= cutover_dt

    # 1. Partition turns into Pro vs Ultra
    pro_turns: List[Dict[str, Any]] = []
    ultra_turns: List[Dict[str, Any]] = []
    for t in turns:
        t_dt = parse_timestamp(t.get("timestamp"))
        if t_dt:
            if t_dt < cutover_dt:
                pro_turns.append(t)
            else:
                ultra_turns.append(t)

    # 2. Cycle bounds for active_week and current_month
    weekly_bounds = get_weekly_cycle_bounds(reference_time=ref_dt)
    w_start_dt = parse_timestamp(weekly_bounds["cycle_start_utc"])
    w_end_dt = parse_timestamp(weekly_bounds["cycle_end_utc"])

    active_week_turns = [
        t for t in turns
        if parse_timestamp(t.get("timestamp")) and w_start_dt <= parse_timestamp(t.get("timestamp")) <= w_end_dt
    ]

    billing_day = 13 if is_ultra_ref else 24
    plan_price_gbp = 79.99 if is_ultra_ref else 18.99
    monthly_bounds = get_monthly_billing_bounds(
        reference_time=ref_dt,
        billing_day=billing_day,
        plan_price_gbp=plan_price_gbp,
    )
    m_start_dt = parse_timestamp(monthly_bounds["cycle_start_utc"])
    m_end_dt = parse_timestamp(monthly_bounds["renewal_date"])

    current_month_turns = [
        t for t in turns
        if parse_timestamp(t.get("timestamp")) and m_start_dt <= parse_timestamp(t.get("timestamp")) <= m_end_dt
    ]

    # Subscription costs for horizons
    sub_cost_week = round(79.99 * 12.0 / 52.0, 2) if is_ultra_ref else round(18.99 * 12.0 / 52.0, 2)
    sub_cost_month = 79.99 if is_ultra_ref else 18.99

    # Elapsed months in Pro era
    if pro_turns:
        p_ts_list = [parse_timestamp(t.get("timestamp")) for t in pro_turns if parse_timestamp(t.get("timestamp"))]
        p_min = min(p_ts_list)
        p_max = max(p_ts_list)
        p_days = max(0.0, (p_max - p_min).total_seconds() / 86400.0)
        p_months = max(1, int(math.ceil(p_days / 30.4375))) if p_days > 0 else 1
        sub_cost_pro = round(p_months * 18.99, 2)
        pro_start_utc = p_min.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        sub_cost_pro = 0.0
        pro_start_utc = era_cutover_utc

    # Elapsed months in Ultra era
    if ultra_turns:
        u_ts_list = [parse_timestamp(t.get("timestamp")) for t in ultra_turns if parse_timestamp(t.get("timestamp"))]
        u_min = min(u_ts_list)
        u_max = max(u_ts_list)
        u_days = max(0.0, (u_max - u_min).total_seconds() / 86400.0)
        u_months = max(1, int(math.ceil(u_days / 30.4375))) if u_days > 0 else 1
        sub_cost_ultra = round(u_months * 79.99, 2)
        ultra_end_utc = u_max.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        sub_cost_ultra = 0.0
        ultra_end_utc = era_cutover_utc

    sub_cost_lifetime = round(sub_cost_pro + sub_cost_ultra, 2)

    # Overages per horizon
    ov_week = _sum_overage_gbp(incidents, w_start_dt, w_end_dt) if w_start_dt and w_end_dt else 0.0
    ov_month = _sum_overage_gbp(incidents, m_start_dt, m_end_dt) if m_start_dt and m_end_dt else 0.0

    pro_cutover_minus_1 = cutover_dt - datetime.timedelta(seconds=1)
    p_start_bound = parse_timestamp(pro_start_utc) or cutover_dt
    ov_pro = _sum_overage_gbp(incidents, p_start_bound, pro_cutover_minus_1)

    u_end_bound = parse_timestamp(ultra_end_utc) or cutover_dt
    ov_ultra = _sum_overage_gbp(incidents, cutover_dt, u_end_bound)
    ov_lifetime = round(ov_pro + ov_ultra, 2)

    # Lifetime bounds
    if turns:
        all_ts = [parse_timestamp(t.get("timestamp")) for t in turns if parse_timestamp(t.get("timestamp"))]
        lifetime_start_utc = min(all_ts).strftime("%Y-%m-%dT%H:%M:%SZ") if all_ts else era_cutover_utc
        lifetime_end_utc = max(all_ts).strftime("%Y-%m-%dT%H:%M:%SZ") if all_ts else era_cutover_utc
    else:
        lifetime_start_utc = era_cutover_utc
        lifetime_end_utc = era_cutover_utc

    # 3. Build horizons dictionary
    horizons: Dict[str, Any] = {}
    horizons["active_week"] = _aggregate_horizon_metrics(
        key="active_week",
        label=HORIZON_LABELS["active_week"],
        start_utc=weekly_bounds["cycle_start_utc"],
        end_utc=weekly_bounds["cycle_end_utc"],
        h_turns=active_week_turns,
        subscription_cost_gbp=sub_cost_week,
        overage_cost_gbp=ov_week,
        convo_map=convo_map,
        pricing_models=pricing_models,
        fx_rate=fx_rate,
    )
    horizons["current_month"] = _aggregate_horizon_metrics(
        key="current_month",
        label=HORIZON_LABELS["current_month"],
        start_utc=monthly_bounds["cycle_start_utc"],
        end_utc=monthly_bounds["renewal_date"],
        h_turns=current_month_turns,
        subscription_cost_gbp=sub_cost_month,
        overage_cost_gbp=ov_month,
        convo_map=convo_map,
        pricing_models=pricing_models,
        fx_rate=fx_rate,
    )
    horizons["pro_era"] = _aggregate_horizon_metrics(
        key="pro_era",
        label=HORIZON_LABELS["pro_era"],
        start_utc=pro_start_utc,
        end_utc=era_cutover_utc,
        h_turns=pro_turns,
        subscription_cost_gbp=sub_cost_pro,
        overage_cost_gbp=ov_pro,
        convo_map=convo_map,
        pricing_models=pricing_models,
        fx_rate=fx_rate,
    )
    horizons["ultra_era"] = _aggregate_horizon_metrics(
        key="ultra_era",
        label=HORIZON_LABELS["ultra_era"],
        start_utc=era_cutover_utc,
        end_utc=ultra_end_utc,
        h_turns=ultra_turns,
        subscription_cost_gbp=sub_cost_ultra,
        overage_cost_gbp=ov_ultra,
        convo_map=convo_map,
        pricing_models=pricing_models,
        fx_rate=fx_rate,
    )
    horizons["lifetime"] = _aggregate_horizon_metrics(
        key="lifetime",
        label=HORIZON_LABELS["lifetime"],
        start_utc=lifetime_start_utc,
        end_utc=lifetime_end_utc,
        h_turns=turns,
        subscription_cost_gbp=sub_cost_lifetime,
        overage_cost_gbp=ov_lifetime,
        convo_map=convo_map,
        pricing_models=pricing_models,
        fx_rate=fx_rate,
    )

    # 4. Era comparison (Ultra 5x vs Pro)
    pro_h = horizons["pro_era"]
    ultra_h = horizons["ultra_era"]

    p_dtok = pro_h["daily_avg_tokens"]
    u_dtok = ultra_h["daily_avg_tokens"]
    daily_tokens_multiplier = round(u_dtok / p_dtok, 2) if p_dtok > 0 else 0.0

    p_dturn = pro_h["daily_avg_turns"]
    u_dturn = ultra_h["daily_avg_turns"]
    daily_turns_multiplier = round(u_dturn / p_dturn, 2) if p_dturn > 0 else 0.0

    p_dval = pro_h["daily_avg_value_gbp"]
    u_dval = ultra_h["daily_avg_value_gbp"]
    daily_value_multiplier = round(u_dval / p_dval, 2) if p_dval > 0 else 0.0

    cache_hit_delta_pct = round(ultra_h["cache_hit_ratio_pct"] - pro_h["cache_hit_ratio_pct"], 2)
    thinking_share_delta_pct = round(ultra_h["thinking_share_pct"] - pro_h["thinking_share_pct"], 2)
    subagent_share_delta_pct = round(ultra_h["subagent_share_pct"] - pro_h["subagent_share_pct"], 2)

    p_rl1k = pro_h["rate_limit_per_1k_turns"]
    u_rl1k = ultra_h["rate_limit_per_1k_turns"]
    if p_rl1k > 0:
        rate_limit_per_1k_delta_pct = round(((u_rl1k - p_rl1k) / p_rl1k) * 100.0, 2)
    else:
        rate_limit_per_1k_delta_pct = 100.0 if u_rl1k > 0 else 0.0

    p_lat = pro_h["latency_mean_ms"]
    u_lat = ultra_h["latency_mean_ms"]
    if p_lat > 0:
        latency_mean_delta_pct = round(((u_lat - p_lat) / p_lat) * 100.0, 2)
    else:
        latency_mean_delta_pct = 0.0

    era_comparison = {
        "cutover_utc": era_cutover_utc,
        "daily_tokens_multiplier": daily_tokens_multiplier,
        "daily_turns_multiplier": daily_turns_multiplier,
        "daily_value_multiplier": daily_value_multiplier,
        "cache_hit_delta_pct": cache_hit_delta_pct,
        "thinking_share_delta_pct": thinking_share_delta_pct,
        "subagent_share_delta_pct": subagent_share_delta_pct,
        "rate_limit_per_1k_delta_pct": rate_limit_per_1k_delta_pct,
        "latency_mean_delta_pct": latency_mean_delta_pct,
        "roi_pro_x": pro_h["roi_multiplier"],
        "roi_ultra_x": ultra_h["roi_multiplier"],
    }

    # 5. Progression series: daily, weekly, monthly
    # Group turns into daily buckets
    daily_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in turns:
        t_dt = parse_timestamp(t.get("timestamp"))
        if t_dt:
            d_key = t_dt.strftime("%Y-%m-%d")
            daily_groups[d_key].append(t)

    daily_series: List[Dict[str, Any]] = []
    for d_key in sorted(daily_groups.keys()):
        b_turns = daily_groups[d_key]
        y, m, d = int(d_key[:4]), int(d_key[5:7]), int(d_key[8:10])
        dt_start = datetime.datetime(y, m, d, 0, 0, 0, tzinfo=datetime.timezone.utc)
        dt_end = datetime.datetime(y, m, d, 23, 59, 59, tzinfo=datetime.timezone.utc)
        start_utc_str = dt_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_utc_str = dt_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        era_tag = "pro" if start_utc_str < era_cutover_utc else "ultra_5x"
        sub_cost_day = 2.63 if era_tag == "ultra_5x" else 0.62
        ov_day = _sum_overage_gbp(incidents, dt_start, dt_end)
        lbl = dt_start.strftime("%d %b %Y")
        bucket = _aggregate_progression_bucket(
            bucket_key=d_key,
            label=lbl,
            start_utc=start_utc_str,
            end_utc=end_utc_str,
            era=era_tag,
            b_turns=b_turns,
            subscription_cost_gbp=sub_cost_day,
            overage_gbp=ov_day,
            convo_map=convo_map,
            pricing_models=pricing_models,
            fx_rate=fx_rate,
        )
        daily_series.append(bucket)

    # Group turns into weekly buckets (Monday-anchored ISO weeks)
    weekly_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    week_dt_map: Dict[str, datetime.datetime] = {}
    for t in turns:
        t_dt = parse_timestamp(t.get("timestamp"))
        if t_dt:
            iso_y, iso_w, _ = t_dt.isocalendar()
            w_key = f"{iso_y:04d}-W{iso_w:02d}"
            weekly_groups[w_key].append(t)
            if w_key not in week_dt_map:
                week_dt_map[w_key] = t_dt

    weekly_series: List[Dict[str, Any]] = []
    for w_key in sorted(weekly_groups.keys()):
        b_turns = weekly_groups[w_key]
        iso_y, iso_w = int(w_key[:4]), int(w_key[6:8])
        mon = datetime.datetime.fromisocalendar(iso_y, iso_w, 1).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=datetime.timezone.utc
        )
        sun = datetime.datetime.fromisocalendar(iso_y, iso_w, 7).replace(
            hour=23, minute=59, second=59, microsecond=0, tzinfo=datetime.timezone.utc
        )
        start_utc_str = mon.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_utc_str = sun.strftime("%Y-%m-%dT%H:%M:%SZ")
        era_tag = "pro" if start_utc_str < era_cutover_utc else "ultra_5x"
        sub_cost_wk = 18.46 if era_tag == "ultra_5x" else 4.38
        ov_wk = _sum_overage_gbp(incidents, mon, sun)
        lbl = f"{mon.strftime('%d %b')} – {sun.strftime('%d %b %Y')}"
        bucket = _aggregate_progression_bucket(
            bucket_key=w_key,
            label=lbl,
            start_utc=start_utc_str,
            end_utc=end_utc_str,
            era=era_tag,
            b_turns=b_turns,
            subscription_cost_gbp=sub_cost_wk,
            overage_gbp=ov_wk,
            convo_map=convo_map,
            pricing_models=pricing_models,
            fx_rate=fx_rate,
        )
        weekly_series.append(bucket)

    # Group turns into monthly buckets (YYYY-MM)
    monthly_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in turns:
        t_dt = parse_timestamp(t.get("timestamp"))
        if t_dt:
            mo_key = t_dt.strftime("%Y-%m")
            monthly_groups[mo_key].append(t)

    monthly_series: List[Dict[str, Any]] = []
    for mo_key in sorted(monthly_groups.keys()):
        b_turns = monthly_groups[mo_key]
        y, m = int(mo_key[:4]), int(mo_key[5:7])
        mo_start = datetime.datetime(y, m, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        if m == 12:
            next_mo = datetime.datetime(y + 1, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        else:
            next_mo = datetime.datetime(y, m + 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        mo_end = next_mo - datetime.timedelta(seconds=1)
        start_utc_str = mo_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_utc_str = mo_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        era_tag = "pro" if start_utc_str < era_cutover_utc else "ultra_5x"
        sub_cost_mo = 79.99 if era_tag == "ultra_5x" else 18.99
        ov_mo = _sum_overage_gbp(incidents, mo_start, mo_end)
        lbl = mo_start.strftime("%B %Y")
        bucket = _aggregate_progression_bucket(
            bucket_key=mo_key,
            label=lbl,
            start_utc=start_utc_str,
            end_utc=end_utc_str,
            era=era_tag,
            b_turns=b_turns,
            subscription_cost_gbp=sub_cost_mo,
            overage_gbp=ov_mo,
            convo_map=convo_map,
            pricing_models=pricing_models,
            fx_rate=fx_rate,
        )
        monthly_series.append(bucket)

    progression_series = {
        "daily": daily_series,
        "weekly": weekly_series,
        "monthly": monthly_series,
    }

    # 6. Diurnal profiles (24-hour hour-by-hour) for each of the 5 horizons
    diurnal_profiles: Dict[str, List[Dict[str, Any]]] = {}
    diurnal_profiles["active_week"] = _compute_diurnal_profile_for_turns(active_week_turns, pricing_models)
    diurnal_profiles["current_month"] = _compute_diurnal_profile_for_turns(current_month_turns, pricing_models)
    diurnal_profiles["pro_era"] = _compute_diurnal_profile_for_turns(pro_turns, pricing_models)
    diurnal_profiles["ultra_era"] = _compute_diurnal_profile_for_turns(ultra_turns, pricing_models)
    diurnal_profiles["lifetime"] = _compute_diurnal_profile_for_turns(turns, pricing_models)

    # Convenience alias for frontend era_compare tab
    horizons["era_compare"] = horizons["ultra_era"]

    def _fmt_compact(val: float) -> str:
        if val >= 1_000_000:
            return f"{val / 1_000_000:.1f}M"
        if val >= 1_000:
            return f"{val / 1_000:.0f}k"
        return f"{val:.0f}"

    era_deltas = {
        "daily_token_velocity": {
            "pro": f"{_fmt_compact(pro_h['daily_avg_tokens'])} / day",
            "ultra": f"{_fmt_compact(ultra_h['daily_avg_tokens'])} / day",
            "delta": f"{daily_tokens_multiplier:.2f}x",
        },
        "daily_turn_throughput": {
            "pro": f"{pro_h['daily_avg_turns']:.0f} turns / day",
            "ultra": f"{ultra_h['daily_avg_turns']:.0f} turns / day",
            "delta": f"{daily_turns_multiplier:.2f}x",
        },
        "thinking_intensity_pct": {
            "pro": f"{pro_h['thinking_share_pct']:.1f}%",
            "ultra": f"{ultra_h['thinking_share_pct']:.1f}%",
            "delta": f"{thinking_share_delta_pct:+.1f} pts",
        },
        "cache_hit_ratio_pct": {
            "pro": f"{pro_h['cache_hit_ratio_pct']:.1f}%",
            "ultra": f"{ultra_h['cache_hit_ratio_pct']:.1f}%",
            "delta": f"{cache_hit_delta_pct:+.1f} pts",
        },
        "subagent_share_pct": {
            "pro": f"{pro_h['subagent_share_pct']:.1f}%",
            "ultra": f"{ultra_h['subagent_share_pct']:.1f}%",
            "delta": f"{subagent_share_delta_pct:+.1f} pts",
        },
        "mean_wire_latency_ms": {
            "pro": f"{pro_h['latency_mean_ms']:.0f} ms",
            "ultra": f"{ultra_h['latency_mean_ms']:.0f} ms",
            "delta": f"{latency_mean_delta_pct:+.1f}%",
        },
        "rate_limit_per_1k_turns": {
            "pro": f"{pro_h['rate_limit_per_1k_turns']:.1f} / 1k",
            "ultra": f"{ultra_h['rate_limit_per_1k_turns']:.1f} / 1k",
            "delta": f"{rate_limit_per_1k_delta_pct:+.1f}%",
        },
        "effective_roi_multiplier": {
            "pro": f"{pro_h['roi_multiplier']:.1f}x",
            "ultra": f"{ultra_h['roi_multiplier']:.1f}x",
            "delta": f"{round(ultra_h['roi_multiplier'] / pro_h['roi_multiplier'], 2):.2f}x" if pro_h['roi_multiplier'] > 0 else f"{ultra_h['roi_multiplier']:.1f}x",
        },
    }

    return {
        "era_cutover_utc": era_cutover_utc,
        "horizons": horizons,
        "era_comparison": era_comparison,
        "era_deltas": era_deltas,
        "progression_series": progression_series,
        "progression": progression_series,
        "diurnal_profiles": diurnal_profiles,
    }
