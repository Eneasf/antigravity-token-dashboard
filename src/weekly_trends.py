"""
Historical Vault Trends & Weekly Cycles Analytics Engine.

Computes and archives weekly cycle aggregates:
- Anchored to Thursday 18:00 UTC cycle reset boundaries (ADR-014).
- Token volumes: uncached prompt, cached prompt, output, processed.
- Cache efficiency: hit ratio percentage across cycles.
- Financial metrics: estimated developer API cost (£ / $) and plan avoided value.
- Reconciled out-of-pocket overage credit burn from exhaustion_ledger.json (ADR-016).
- Mathematical peak Burn Velocity Index (BVI) per cycle (ADR-031 / ADR-032).
- Retains historical weekly cycles in `data/antigravity_vault.db` (`weekly_cycles_archive`).

Adheres strictly to:
- ADR-001: Strict Read-Only SQLite Access (`?mode=ro`, uri=True).
- ADR-014: Signal-Anchored 5-Hour Overage Engine & Calendar Cycle Anchoring.
- ADR-016: Persistent Append-Only 429 Exhaustion Ledger Defense.
- ADR-018: Dedicated Local Telemetry Vault, Hybrid Lossless Archival & Lineage Topology.
- ADR-028: Empirical Weekly Quota Capacity Calibration ($129.00 USD).
- ADR-039: Historical Vault Trends & 8–12 Week SVG Trendline Chart.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

from src.aggregator import (
    compute_turn_cost,
    get_model_rates,
    get_weekly_cycle_bounds,
    load_pricing,
    parse_timestamp,
)

DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "antigravity_vault.db"
DEFAULT_LEDGER_PATH = Path(__file__).resolve().parent.parent / "data" / "exhaustion_ledger.json"

# Calibrated weekly quota capacity in USD (ADR-028)
WEEKLY_QUOTA_CAPACITY_USD = 129.00
NOMINAL_DAILY_RATE_PCT = 14.2857  # 100% / 7 days
DEFAULT_GBP_FX_RATE = 0.79


def load_ledger_incidents(ledger_path: Optional[Union[str, Path]] = DEFAULT_LEDGER_PATH) -> List[Dict[str, Any]]:
    """Safely load confirmed overage incidents from exhaustion_ledger.json."""
    if ledger_path is None:
        return []
    path = Path(ledger_path).resolve()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("incidents", [])
    except Exception:
        return []


def compute_weekly_cycles_from_turns(
    turns_or_steps: List[Dict[str, Any]],
    pricing_models: Optional[Dict[str, Any]] = None,
    ledger_incidents: Optional[List[Dict[str, Any]]] = None,
    reference_time: Optional[datetime] = None,
    weekly_capacity_usd: float = WEEKLY_QUOTA_CAPACITY_USD,
) -> List[Dict[str, Any]]:
    """
    Partition raw turns or step records into Thursday 18:00 UTC weekly cycles.

    Aggregates:
    - Turns count
    - Processed tokens (uncached prompt, cached, output)
    - Cache hit ratio %
    - Estimated API cost (USD and GBP)
    - Correlated actual overage credit deductions from ledger incidents
    - Peak Burn Velocity Index (BVI) across each cycle
    - Current active cycle identification flag

    Returns chronologically sorted list of cycle dictionaries.
    """
    if pricing_models is None:
        pricing_models = load_pricing()
    if ledger_incidents is None:
        ledger_incidents = load_ledger_incidents()

    ref_dt = reference_time or datetime.now(timezone.utc)
    if ref_dt.tzinfo is None:
        ref_dt = ref_dt.replace(tzinfo=timezone.utc)
    now_iso = ref_dt.isoformat()

    current_bounds = get_weekly_cycle_bounds(ref_dt)
    current_cycle_start = current_bounds["cycle_start_utc"]

    # Group turns by cycle_start_utc
    cycles_map: Dict[str, Dict[str, Any]] = {}

    for turn in turns_or_steps:
        ts_str = turn.get("timestamp") or ""
        if not ts_str:
            continue
        dt = parse_timestamp(ts_str)
        if not dt:
            continue

        bounds = get_weekly_cycle_bounds(dt)
        c_start = bounds["cycle_start_utc"]
        c_end = bounds["cycle_end_utc"]

        if c_start not in cycles_map:
            s_dt = parse_timestamp(c_start)
            e_dt = parse_timestamp(c_end)
            label = f"{s_dt.strftime('%d %b')} – {e_dt.strftime('%d %b %Y')}" if s_dt and e_dt else c_start[:10]
            cycle_key = s_dt.strftime("%Y-%m-%d_%H:%M") if s_dt else c_start[:10]

            cycles_map[c_start] = {
                "cycle_key": cycle_key,
                "cycle_start_utc": c_start,
                "cycle_end_utc": c_end,
                "label": label,
                "total_turns": 0,
                "total_input_tokens": 0,
                "cached_tokens": 0,
                "prompt_tokens_uncached": 0,
                "total_output_tokens": 0,
                "total_processed_tokens": 0,
                "cache_hit_ratio_pct": 0.0,
                "estimated_cost_usd": 0.0,
                "estimated_cost_gbp": 0.0,
                "actual_overage_credits": 0,
                "actual_overage_usd": 0.0,
                "actual_overage_gbp": 0.0,
                "peak_bvi": 0.0,
                "is_current_cycle": 1 if c_start == current_cycle_start else 0,
                "_turn_points": [],  # (dt, turn_cost_usd)
            }

        # Token metrics
        in_toks = int(turn.get("total_input_tokens") or 0)
        c_toks = int(turn.get("cached_tokens") or 0)
        u_toks = int(turn.get("prompt_tokens_uncached") or 0)
        out_toks = int(turn.get("output_tokens_total") or 0)
        if in_toks == 0 and (u_toks > 0 or c_toks > 0):
            in_toks = u_toks + c_toks

        # Cost calculation
        model_id = str(turn.get("model_id") or "")
        cost_usd = float(turn.get("estimated_cost_usd") or 0.0)
        if cost_usd == 0.0 and model_id:
            rates = get_model_rates(model_id, pricing_models)
            cost_usd = compute_turn_cost(
                {
                    "prompt_tokens_uncached": u_toks,
                    "cached_tokens": c_toks,
                    "output_tokens_total": out_toks,
                },
                rates,
            )

        c = cycles_map[c_start]
        c["total_turns"] += 1
        c["total_input_tokens"] += in_toks
        c["cached_tokens"] += c_toks
        c["prompt_tokens_uncached"] += u_toks
        c["total_output_tokens"] += out_toks
        c["total_processed_tokens"] += (in_toks + out_toks)
        c["estimated_cost_usd"] += cost_usd
        c["_turn_points"].append((dt, cost_usd))

    # Match overage incidents from ledger
    for incident in ledger_incidents:
        inc_ts_str = incident.get("hour_timestamp") or incident.get("start_utc") or ""
        inc_dt = parse_timestamp(inc_ts_str)
        if not inc_dt:
            continue
        inc_bounds = get_weekly_cycle_bounds(inc_dt)
        inc_cycle_start = inc_bounds["cycle_start_utc"]

        if inc_cycle_start in cycles_map:
            cyc = cycles_map[inc_cycle_start]
            cyc["actual_overage_credits"] += int(incident.get("credits_burned") or 0)
            cyc["actual_overage_usd"] += float(incident.get("credit_burn_usd") or 0.0)
            cyc["actual_overage_gbp"] += float(incident.get("credit_burn_gbp") or 0.0)

    # Finalize metrics and compute peak BVI
    result_cycles: List[Dict[str, Any]] = []
    for c_start, c in sorted(cycles_map.items(), key=lambda item: item[0]):
        # Cache hit ratio
        total_in = c["total_input_tokens"]
        c_in = c["cached_tokens"]
        c["cache_hit_ratio_pct"] = round((c_in / total_in) * 100.0, 2) if total_in > 0 else 0.0

        # Currency conversion
        c["estimated_cost_usd"] = round(c["estimated_cost_usd"], 4)
        c["estimated_cost_gbp"] = round(c["estimated_cost_usd"] * DEFAULT_GBP_FX_RATE, 4)
        c["actual_overage_usd"] = round(c["actual_overage_usd"], 2)
        c["actual_overage_gbp"] = round(c["actual_overage_gbp"], 2)

        # Mathematical Peak BVI calculation (ADR-031 / ADR-032 / ADR-034)
        # Evaluates Bayesian M-estimate daily burn velocity across turns against temporal capacity
        turn_points = sorted(c.pop("_turn_points", []), key=lambda tp: tp[0])
        peak_bvi = 0.0

        effective_capacity = weekly_capacity_usd
        cycle_start_dt = parse_timestamp(c["cycle_start_utc"])
        if cycle_start_dt is not None:
            try:
                from src.temporal import get_temporal_resolver
                resolver = get_temporal_resolver()
                sub_at_cycle = resolver.resolve_subscription(cycle_start_dt)
                effective_capacity = float(
                    sub_at_cycle.get("quota_limits", {}).get("gemini_weekly_capacity_usd", weekly_capacity_usd)
                )
            except Exception:
                effective_capacity = weekly_capacity_usd

        if turn_points and effective_capacity > 0:
            if cycle_start_dt:
                cum_cost = 0.0
                k_pseudo = 1.0
                for t_dt, t_cost in turn_points:
                    cum_cost += t_cost
                    elapsed_secs = max(0.0, (t_dt - cycle_start_dt).total_seconds())
                    elapsed_days = max(0.01, elapsed_secs / 86400.0)

                    # Quota consumed percentage against capacity
                    quota_consumed_pct = min(100.0, (cum_cost / effective_capacity) * 100.0)
                    effective_daily_rate = (quota_consumed_pct + (k_pseudo * NOMINAL_DAILY_RATE_PCT)) / (elapsed_days + k_pseudo)
                    bvi_val = effective_daily_rate / NOMINAL_DAILY_RATE_PCT
                    if bvi_val > peak_bvi:
                        peak_bvi = bvi_val

        c["peak_bvi"] = round(peak_bvi, 2)
        result_cycles.append(c)

    return result_cycles


def sync_weekly_trends_to_vault(
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    pricing_models: Optional[Dict[str, Any]] = None,
    ledger_path: Union[str, Path] = DEFAULT_LEDGER_PATH,
    reference_time: Optional[datetime] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Extract turns from `steps_archive` in the Vault, aggregate into weekly cycles,
    and persist into `weekly_cycles_archive`.

    Adheres to:
    - ADR-001: Strict Read-Only SQLite Access on upstream DBs.
    - ADR-018: Dedicated Local Telemetry Vault.
    - ADR-039: Historical Vault Trends & 8–12 Week SVG Trendline Chart.

    Returns:
    {
        'cycles_synced': int,
        'total_turns_archived': int,
        'total_overage_credits': int
    }
    """
    v_file = Path(vault_path).resolve()
    if not v_file.exists():
        from src.vault import init_vault
        conn = init_vault(v_file)
    else:
        conn = sqlite3.connect(str(v_file), timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000;")

    cur = conn.cursor()

    # Query count of step_type = 15 turns for fast-path cache validation
    cur.execute("SELECT COUNT(*) FROM steps_archive WHERE step_type = 15 AND timestamp != ''")
    turn_count_row = cur.fetchone()
    turn_count = turn_count_row[0] if turn_count_row else 0

    ref_dt = reference_time or datetime.now(timezone.utc)
    cur_bounds = get_weekly_cycle_bounds(ref_dt)
    cur_start_dt = parse_timestamp(cur_bounds["cycle_start_utc"])
    cur_key = cur_start_dt.strftime("%Y-%m-%d_%H:%M") if cur_start_dt else cur_bounds["cycle_start_utc"][:10]

    if not force:
        cur.execute(
            "SELECT key, value FROM vault_sync_state WHERE key IN ('weekly_trends:last_turn_count', 'weekly_trends:last_cycle_key')"
        )
        sync_state = dict(cur.fetchall())
        if (
            sync_state.get("weekly_trends:last_turn_count") == str(turn_count)
            and sync_state.get("weekly_trends:last_cycle_key") == cur_key
        ):
            cur.execute("SELECT COUNT(*), COALESCE(SUM(actual_overage_credits), 0) FROM weekly_cycles_archive")
            c_row = cur.fetchone()
            conn.close()
            return {
                "cycles_synced": c_row[0] if c_row else 0,
                "total_turns_archived": turn_count,
                "total_overage_credits": c_row[1] if c_row else 0,
            }

    # Query step_type = 15 turns from steps_archive
    cur.execute(
        """
        SELECT timestamp, model_id, total_input_tokens, cached_tokens,
               prompt_tokens_uncached, output_tokens_total
        FROM steps_archive
        WHERE step_type = 15 AND timestamp != ''
        ORDER BY timestamp ASC
        """
    )
    rows = cur.fetchall()

    turns: List[Dict[str, Any]] = []
    for ts, m_id, t_in, c_tok, u_tok, out_tok in rows:
        turns.append(
            {
                "timestamp": ts,
                "model_id": m_id,
                "total_input_tokens": t_in,
                "cached_tokens": c_tok,
                "prompt_tokens_uncached": u_tok,
                "output_tokens_total": out_tok,
            }
        )

    ledger_incidents = load_ledger_incidents(ledger_path)
    cycles = compute_weekly_cycles_from_turns(
        turns,
        pricing_models=pricing_models,
        ledger_incidents=ledger_incidents,
        reference_time=reference_time,
    )

    now_iso = ref_dt.isoformat()
    total_overage = 0

    for cyc in cycles:
        total_overage += cyc.get("actual_overage_credits", 0)
        cur.execute(
            """
            INSERT INTO weekly_cycles_archive (
                cycle_key, cycle_start_utc, cycle_end_utc, label, total_turns,
                total_input_tokens, cached_tokens, prompt_tokens_uncached,
                total_output_tokens, total_processed_tokens, cache_hit_ratio_pct,
                estimated_cost_usd, estimated_cost_gbp, actual_overage_credits,
                actual_overage_usd, actual_overage_gbp, peak_bvi, is_current_cycle,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cycle_key) DO UPDATE SET
                cycle_start_utc = excluded.cycle_start_utc,
                cycle_end_utc = excluded.cycle_end_utc,
                label = excluded.label,
                total_turns = excluded.total_turns,
                total_input_tokens = excluded.total_input_tokens,
                cached_tokens = excluded.cached_tokens,
                prompt_tokens_uncached = excluded.prompt_tokens_uncached,
                total_output_tokens = excluded.total_output_tokens,
                total_processed_tokens = excluded.total_processed_tokens,
                cache_hit_ratio_pct = excluded.cache_hit_ratio_pct,
                estimated_cost_usd = excluded.estimated_cost_usd,
                estimated_cost_gbp = excluded.estimated_cost_gbp,
                actual_overage_credits = excluded.actual_overage_credits,
                actual_overage_usd = excluded.actual_overage_usd,
                actual_overage_gbp = excluded.actual_overage_gbp,
                peak_bvi = excluded.peak_bvi,
                is_current_cycle = excluded.is_current_cycle,
                updated_at = excluded.updated_at
            """,
            (
                cyc["cycle_key"],
                cyc["cycle_start_utc"],
                cyc["cycle_end_utc"],
                cyc["label"],
                cyc["total_turns"],
                cyc["total_input_tokens"],
                cyc["cached_tokens"],
                cyc["prompt_tokens_uncached"],
                cyc["total_output_tokens"],
                cyc["total_processed_tokens"],
                cyc["cache_hit_ratio_pct"],
                cyc["estimated_cost_usd"],
                cyc["estimated_cost_gbp"],
                cyc["actual_overage_credits"],
                cyc["actual_overage_usd"],
                cyc["actual_overage_gbp"],
                cyc["peak_bvi"],
                cyc["is_current_cycle"],
                now_iso,
            ),
        )

    # Record sync state pointers
    cur.execute(
        """
        INSERT INTO vault_sync_state (key, value, updated_at)
        VALUES ('weekly_trends:last_turn_count', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (str(len(turns)), now_iso),
    )
    cur.execute(
        """
        INSERT INTO vault_sync_state (key, value, updated_at)
        VALUES ('weekly_trends:last_cycle_key', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (cur_key, now_iso),
    )

    conn.commit()
    conn.close()

    return {
        "cycles_synced": len(cycles),
        "total_turns_archived": len(turns),
        "total_overage_credits": total_overage,
    }


def get_weekly_trends(
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    limit_weeks: int = 12,
    fallback_turns: Optional[List[Dict[str, Any]]] = None,
    pricing_models: Optional[Dict[str, Any]] = None,
    ledger_path: Union[str, Path] = DEFAULT_LEDGER_PATH,
    reference_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Retrieve historical weekly cycles from the Vault (or compute from fallback turns).

    Returns:
    {
        'cycles': List[Dict[str, Any]],  # up to `limit_weeks` cycles, chronologically sorted
        'total_cycles_recorded': int,
        'summary': {
            'cycles_analyzed': int,
            'average_tokens_per_week': int,
            'average_cost_per_week_usd': float,
            'average_cost_per_week_gbp': float,
            'peak_week_tokens': int,
            'peak_week_label': str,
            'peak_week_cost_usd': float,
            'token_growth_rate_pct': float,
            'overage_cycles_count': int,
            'total_overage_credits': int
        }
    }
    """
    v_file = Path(vault_path).resolve()
    cycles: List[Dict[str, Any]] = []

    if v_file.exists():
        try:
            conn = sqlite3.connect(f"file:{v_file}?mode=ro", uri=True, timeout=5.0)
            conn.execute("PRAGMA busy_timeout = 5000;")
            cur = conn.cursor()
            cur.execute(
                """
                SELECT cycle_key, cycle_start_utc, cycle_end_utc, label,
                       total_turns, total_input_tokens, cached_tokens,
                       prompt_tokens_uncached, total_output_tokens,
                       total_processed_tokens, cache_hit_ratio_pct,
                       estimated_cost_usd, estimated_cost_gbp,
                       actual_overage_credits, actual_overage_usd,
                       actual_overage_gbp, peak_bvi, is_current_cycle
                FROM weekly_cycles_archive
                ORDER BY cycle_start_utc ASC
                """
            )
            rows = cur.fetchall()
            for r in rows:
                cycles.append(
                    {
                        "cycle_key": r[0],
                        "cycle_start_utc": r[1],
                        "cycle_end_utc": r[2],
                        "label": r[3],
                        "total_turns": r[4],
                        "total_input_tokens": r[5],
                        "cached_tokens": r[6],
                        "prompt_tokens_uncached": r[7],
                        "total_output_tokens": r[8],
                        "total_processed_tokens": r[9],
                        "cache_hit_ratio_pct": r[10],
                        "estimated_cost_usd": r[11],
                        "estimated_cost_gbp": r[12],
                        "actual_overage_credits": r[13],
                        "actual_overage_usd": r[14],
                        "actual_overage_gbp": r[15],
                        "peak_bvi": r[16],
                        "is_current_cycle": r[17],
                    }
                )
            conn.close()
        except Exception:
            cycles = []

    # Fallback in-memory calculation if vault had no rows or was missing
    if not cycles and fallback_turns:
        ledger_incidents = load_ledger_incidents(ledger_path)
        cycles = compute_weekly_cycles_from_turns(
            fallback_turns,
            pricing_models=pricing_models,
            ledger_incidents=ledger_incidents,
            reference_time=reference_time,
        )

    total_recorded = len(cycles)
    sliced_cycles = cycles[-limit_weeks:] if limit_weeks > 0 and len(cycles) > limit_weeks else list(cycles)

    # Compute macro summary metrics
    summary: Dict[str, Any] = {
        "cycles_analyzed": len(sliced_cycles),
        "average_tokens_per_week": 0,
        "average_cost_per_week_usd": 0.0,
        "average_cost_per_week_gbp": 0.0,
        "peak_week_tokens": 0,
        "peak_week_label": "—",
        "peak_week_cost_usd": 0.0,
        "token_growth_rate_pct": 0.0,
        "overage_cycles_count": 0,
        "total_overage_credits": 0,
    }

    if sliced_cycles:
        total_tokens = sum(c["total_processed_tokens"] for c in sliced_cycles)
        total_cost_usd = sum(c["estimated_cost_usd"] for c in sliced_cycles)
        total_cost_gbp = sum(c["estimated_cost_gbp"] for c in sliced_cycles)
        total_credits = sum(c["actual_overage_credits"] for c in sliced_cycles)
        overage_cnt = sum(1 for c in sliced_cycles if c["actual_overage_credits"] > 0)

        n = len(sliced_cycles)
        summary["average_tokens_per_week"] = int(round(total_tokens / n))
        summary["average_cost_per_week_usd"] = round(total_cost_usd / n, 2)
        summary["average_cost_per_week_gbp"] = round(total_cost_gbp / n, 2)
        summary["overage_cycles_count"] = overage_cnt
        summary["total_overage_credits"] = total_credits

        # Peak week
        peak_cyc = max(sliced_cycles, key=lambda c: c["total_processed_tokens"])
        summary["peak_week_tokens"] = peak_cyc["total_processed_tokens"]
        summary["peak_week_label"] = peak_cyc["label"]
        summary["peak_week_cost_usd"] = peak_cyc["estimated_cost_usd"]

        # Growth rate: compare last completed cycle against previous cycle
        completed_cycles = [c for c in sliced_cycles if not c.get("is_current_cycle")]
        if len(completed_cycles) >= 2:
            last_toks = completed_cycles[-1]["total_processed_tokens"]
            prev_toks = completed_cycles[-2]["total_processed_tokens"]
            if prev_toks > 0:
                summary["token_growth_rate_pct"] = round(((last_toks - prev_toks) / prev_toks) * 100.0, 1)

    return {
        "cycles": sliced_cycles,
        "total_cycles_recorded": total_recorded,
        "summary": summary,
    }
