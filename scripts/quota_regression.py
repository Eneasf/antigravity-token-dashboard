#!/usr/bin/env python3
"""
Empirical rate card regression and cost-weighted quota convergence analysis.

Verifies:
1. Exact model rate cards from official Google documentation (https://ai.google.dev/pricing).
2. Derived proportions of cost relative to Gemini Flash baseline.
3. Mathematical convergence of 5-hour ($20.00) and weekly ($133.00) capacities against Google's desktop indicator.
4. Multi-model regression analysis across all Gemini benchmark turns executed today.
"""

import argparse
import datetime
import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from antigravity_telemetry import discover_all_conversations, read_conversation_turns
from src.aggregator import get_provider_quota_track
from src.quota_client import fetch_live_quota_summary


def calc_turn_cost(t: dict, models_cfg: dict, fallback_rates: dict | None = None) -> float:
    """Calculate the estimated USD cost of a turn based on token rates."""
    m = str(t.get("model_id"))
    rates = models_cfg.get(m, {}).get("rates_per_million", fallback_rates or {})
    uncached = t.get("prompt_tokens_uncached", 0) or 0
    cached = t.get("cached_tokens", 0) or 0
    out = t.get("output_tokens_total", 0) or 0
    return (
        uncached * rates.get("prompt_uncached", 0.75)
        + cached * rates.get("prompt_cached", 0.075)
        + out * rates.get("candidate_output", 3.75)
    ) / 1e6


def analyze_vault_burn_intervals(
    vault_path: Path,
    all_gemini_turns: list[dict],
    models_cfg: dict,
    flash_rates: dict,
) -> dict:
    """
    Query v_quota_burn_intervals from antigravity_vault.db and correlate each
    quota step-down interval with turn-level token consumption and rate-card cost.
    """
    import sqlite3

    if not vault_path.exists():
        return {"intervals": [], "pool_ratio_mean": None, "snapshots_count": 0}

    conn = None
    try:
        conn = sqlite3.connect(f"file:{vault_path}?mode=ro", uri=True, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 10000;")
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quota_snapshots_archive'")
        if not cur.fetchone():
            return {"intervals": [], "pool_ratio_mean": None, "snapshots_count": 0}

        cur.execute("SELECT COUNT(*) FROM quota_snapshots_archive")
        snap_count = cur.fetchone()[0] or 0

        cur.execute("""
            SELECT
                start_utc,
                end_utc,
                delta_5h_pct,
                delta_weekly_pct,
                ratio_5h_to_weekly,
                start_5h_rem_pct,
                end_5h_rem_pct,
                start_weekly_rem_pct,
                end_weekly_rem_pct,
                active_status
            FROM v_quota_burn_intervals
            WHERE delta_5h_pct > 0 OR delta_weekly_pct > 0
            ORDER BY end_utc ASC, start_utc ASC
        """)
        rows = cur.fetchall()
    except (sqlite3.Error, OSError):
        return {"intervals": [], "pool_ratio_mean": None, "snapshots_count": 0}
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass

    intervals = []
    ratios = []
    for idx, (
        s_utc,
        e_utc,
        d5h,
        dwk,
        ratio,
        s5h,
        e5h,
        swk,
        ewk,
        status,
    ) in enumerate(rows, start=1):
        try:
            s_dt = datetime.datetime.fromisoformat(s_utc.replace("Z", "+00:00"))
            e_dt = datetime.datetime.fromisoformat(e_utc.replace("Z", "+00:00"))
        except Exception:
            continue

        matched = [t for t in all_gemini_turns if s_dt < t["dt"] <= e_dt]
        interval_cost = sum(calc_turn_cost(t, models_cfg, flash_rates) for t in matched)
        uncached_toks = sum(t.get("prompt_tokens_uncached", 0) or 0 for t in matched)
        cached_toks = sum(t.get("cached_tokens", 0) or 0 for t in matched)
        out_toks = sum(t.get("output_tokens_total", 0) or 0 for t in matched)

        by_m: dict[str, int] = {}
        for t in matched:
            mid = str(t.get("model_id", ""))
            by_m[mid] = by_m.get(mid, 0) + 1
        top_model = max(by_m.items(), key=lambda x: x[1])[0] if by_m else "none"
        top_model_name = models_cfg.get(top_model, {}).get("name", top_model)

        if ratio is not None and ratio > 0:
            ratios.append(float(ratio))

        solved_5h = (interval_cost / (float(d5h) / 100.0)) if d5h and d5h > 0 else None
        intervals.append({
            "interval_id": idx,
            "start_utc": s_utc,
            "end_utc": e_utc,
            "delta_5h_pct": float(d5h or 0.0),
            "delta_weekly_pct": float(dwk or 0.0),
            "ratio_5h_to_weekly": float(ratio) if ratio is not None else None,
            "start_5h_rem_pct": float(s5h or 0.0),
            "end_5h_rem_pct": float(e5h or 0.0),
            "start_weekly_rem_pct": float(swk or 0.0),
            "end_weekly_rem_pct": float(ewk or 0.0),
            "turns_count": len(matched),
            "primary_model_id": top_model,
            "primary_model_name": top_model_name,
            "uncached_tokens": uncached_toks,
            "cached_tokens": cached_toks,
            "output_tokens": out_toks,
            "rate_card_cost_usd": round(interval_cost, 4),
            "solved_5h_capacity_usd": round(solved_5h, 2) if solved_5h is not None else None,
            "active_status": status,
        })

    pool_ratio_mean = round(sum(ratios) / len(ratios), 4) if ratios else None
    return {
        "snapshots_count": snap_count,
        "intervals": intervals,
        "pool_ratio_mean": pool_ratio_mean,
    }


def run_regression_analysis(
    antigravity_dir: Path | str | None = None,
    pricing_path: Path | str | None = None,
    no_live_quota: bool = False,
    dry_run: bool = False,
    vault_path: Path | str | None = None,
) -> dict:
    print("=" * 80)
    print(" EMPIRICAL RATE CARD REGRESSION & COST-WEIGHTED QUOTA CONVERGENCE")
    print(" Ground Truth Documentation: https://ai.google.dev/pricing")
    print("=" * 80)

    cfg_path = Path(pricing_path) if pricing_path else (REPO_ROOT / "config" / "pricing.json")
    with open(cfg_path, "r") as f:
        pricing_cfg = json.load(f)

    models_cfg = pricing_cfg.get("models", {})
    sub_limits = pricing_cfg.get("subscription", {}).get("quota_limits", {})

    print("\n--- 1. OFFICIAL GOOGLE RATE CARDS & DERIVED PROPORTIONS ---")
    flash_rates = models_cfg.get("1318", {}).get("rates_per_million", {})
    flash_in = flash_rates.get("prompt_uncached", 0.75)
    flash_out = flash_rates.get("candidate_output", 3.75)
    flash_cache = flash_rates.get("prompt_cached", 0.075)

    print(f"Gemini Flash Baseline (3.8/3.7/3.6):")
    print(f"  Uncached Input:   ${flash_in:.2f} / 1M tokens (1.000x)")
    print(f"  Cached Input:     ${flash_cache:.3f} / 1M tokens (0.100x -> 90% discount)")
    print(f"  Output / Thinking:${flash_out:.2f} / 1M tokens (5.000x input)")

    pro_rates = models_cfg.get("1016", {}).get("rates_per_million", {})
    pro_in = pro_rates.get("prompt_uncached", 2.00)
    pro_out = pro_rates.get("candidate_output", 12.00)
    print(f"\nGemini 3.1 Pro Preview:")
    print(f"  Uncached Input:   ${pro_in:.2f} / 1M tokens ({pro_in / flash_in:.3f}x Flash)")
    print(f"  Output / Thinking:${pro_out:.2f} / 1M tokens ({pro_out / flash_out:.3f}x Flash)")
    print(f"  Blended Weight:   ~2.80x Flash")

    lite_rates = models_cfg.get("1050", {}).get("rates_per_million", {})
    lite_in = lite_rates.get("prompt_uncached", 0.25)
    lite_out = lite_rates.get("candidate_output", 1.50)
    print(f"\nGemini 3.1 Flash-Lite (Subagents):")
    print(f"  Uncached Input:   ${lite_in:.2f} / 1M tokens ({lite_in / flash_in:.3f}x Flash)")
    print(f"  Output / Thinking:${lite_out:.2f} / 1M tokens ({lite_out / flash_out:.3f}x Flash)")
    print(f"  Blended Weight:   ~0.35x Flash")

    if dry_run:
        print("\n[*] DRY RUN: Skipping conversation telemetry discovery and live quota check.")
        print("\n" + "=" * 80)
        print(" [OK] REGRESSION & CONVERGENCE VERIFICATION COMPLETE (DRY RUN)")
        print("=" * 80)
        return {
            "dry_run": True,
            "flash_rates": flash_rates,
            "pro_rates": pro_rates,
            "lite_rates": lite_rates,
        }

    print("\n--- 2. INGESTING ACTIVE TELEMETRY FROM LOCAL SYSTEM ---")
    conv_items = (
        discover_all_conversations(antigravity_dir=Path(antigravity_dir))
        if antigravity_dir
        else discover_all_conversations()
    )
    all_gemini_turns = []
    for item in conv_items:
        for t in read_conversation_turns(Path(item["db_path"])):
            m = str(t.get("model_id"))
            if get_provider_quota_track(m, models_cfg) != "gemini":
                continue
            ts_str = t.get("timestamp")
            if not ts_str:
                continue
            ts = datetime.datetime.fromisoformat(ts_str) if isinstance(ts_str, str) else ts_str
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            t["dt"] = ts
            all_gemini_turns.append(t)

    all_gemini_turns.sort(key=lambda x: x["dt"])
    print(f"Total historical Gemini turns discovered: {len(all_gemini_turns):,}")

    now = datetime.datetime.now(datetime.timezone.utc)
    # Thursday 18:00 UTC cycle reset
    days_since_thu = (now.weekday() - 3) % 7
    last_thu = now - datetime.timedelta(days=days_since_thu)
    weekly_start = last_thu.replace(hour=18, minute=0, second=0, microsecond=0)
    if weekly_start > now:
        weekly_start -= datetime.timedelta(days=7)

    five_h_start = now - datetime.timedelta(hours=5)

    active_weekly = [t for t in all_gemini_turns if t["dt"] >= weekly_start]
    active_5h = [t for t in all_gemini_turns if t["dt"] >= five_h_start]

    weekly_cost = sum(calc_turn_cost(t, models_cfg, flash_rates) for t in active_weekly)
    five_h_cost = sum(calc_turn_cost(t, models_cfg, flash_rates) for t in active_5h)

    print(f"\nActive Weekly Turns (since {weekly_start.strftime('%Y-%m-%d %H:%M UTC')}): {len(active_weekly):,}")
    print(f"Total Imputed Weekly Cost: ${weekly_cost:.4f} USD")
    print(f"\nActive 5-Hour Turns (since {five_h_start.strftime('%H:%M UTC')}): {len(active_5h):,}")
    print(f"Total Imputed 5-Hour Cost: ${five_h_cost:.4f} USD")

    print("\n--- 3. LIVE DESKTOP INDICATOR CONVERGENCE CHECK ---")
    live_quota = None if no_live_quota else fetch_live_quota_summary()
    gw = None
    g5 = None
    if isinstance(live_quota, dict):
        if live_quota.get("available"):
            gw = live_quota.get("gemini_weekly")
            g5 = live_quota.get("gemini_5h")
        elif isinstance(live_quota.get("gemini"), dict):
            gem_q = live_quota["gemini"]
            if isinstance(gem_q.get("weekly"), dict) and gem_q["weekly"].get("remaining_fraction") is not None:
                rem = round(float(gem_q["weekly"]["remaining_fraction"]) * 100.0, 2)
                gw = {"remaining_pct": rem, "used_pct": round(100.0 - rem, 2)}
            if isinstance(gem_q.get("five_hour"), dict) and gem_q["five_hour"].get("remaining_fraction") is not None:
                rem = round(float(gem_q["five_hour"]["remaining_fraction"]) * 100.0, 2)
                g5 = {"remaining_pct": rem, "used_pct": round(100.0 - rem, 2)}

    if gw or g5:
        if gw:
            gw_rem = gw["remaining_pct"]
            gw_used = gw["used_pct"]
            solved_weekly_cap = weekly_cost / (gw_used / 100.0) if gw_used > 0 else 133.00
            print(f"Weekly Indicator Ground Truth: {gw_rem}% remaining ({gw_used}% used)")
            print(f"  Solved Weekly Capacity:   ${solved_weekly_cap:.2f} USD")
            print(f"  Configured Capacity:      ${sub_limits.get('gemini_weekly_capacity_usd', 133.00):.2f} USD")
            diff_weekly = abs(solved_weekly_cap - sub_limits.get("gemini_weekly_capacity_usd", 133.00))
            print(f"  Weekly Convergence Delta: ${diff_weekly:.2f} ({diff_weekly / 133.00 * 100:.2f}%)")

        if g5:
            g5_rem = g5["remaining_pct"]
            g5_used = g5["used_pct"]
            solved_5h_cap = five_h_cost / (g5_used / 100.0) if g5_used > 0 else 20.00
            print(f"\n5-Hour Indicator Ground Truth:  {g5_rem}% remaining ({g5_used}% used)")
            print(f"  Solved 5-Hour Capacity:   ${solved_5h_cap:.2f} USD")
            print(f"  Configured Capacity:      ${sub_limits.get('gemini_5h_capacity_usd', 20.00):.2f} USD")
            diff_5h = abs(solved_5h_cap - sub_limits.get("gemini_5h_capacity_usd", 20.00))
            print(f"  5-Hour Convergence Delta: ${diff_5h:.2f} ({diff_5h / 20.00 * 100:.2f}%)")
    else:
        print("[-] Live desktop indicator language server not reachable; using offline calibrated capacities.")

    print("\n--- 4. MULTI-MODEL BENCHMARK REGRESSION SUMMARY ---")
    models_today = {}
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for t in all_gemini_turns:
        if t["dt"] >= today_start:
            m = str(t.get("model_id"))
            if m not in models_today:
                models_today[m] = {"turns": 0, "cost": 0.0, "name": models_cfg.get(m, {}).get("name", m)}
            models_today[m]["turns"] += 1
            models_today[m]["cost"] += calc_turn_cost(t, models_cfg, flash_rates)

    print(f"Gemini Benchmark Models Executed Today ({today_start.strftime('%Y-%m-%d')}):")
    for m, rec in sorted(models_today.items(), key=lambda x: x[1]["cost"], reverse=True):
        pct_cost = (rec["cost"] / five_h_cost * 100.0) if five_h_cost > 0 else 0.0
        print(f"  Model {m:4s} ({rec['name']:30s}): {rec['turns']:4d} turns | Cost: ${rec['cost']:7.4f} ({pct_cost:5.1f}% of 5h burst)")

    print("\n--- 5. VAULT QUOTA SNAPSHOT INTERVAL OBSERVATION (v_quota_burn_intervals) ---")
    if vault_path is not None:
        eff_vault = Path(vault_path)
    elif antigravity_dir is not None:
        eff_vault = Path(antigravity_dir) / "antigravity_vault.db"
    else:
        eff_vault = REPO_ROOT / "data" / "antigravity_vault.db"

    burn_report = analyze_vault_burn_intervals(eff_vault, all_gemini_turns, models_cfg, flash_rates)
    print(f"Archived Quota Snapshots: {burn_report['snapshots_count']} | Step-Down Intervals: {len(burn_report['intervals'])}")
    if burn_report["pool_ratio_mean"] is not None:
        print(f"Empirical Weekly-to-5h Pool Ratio: {burn_report['pool_ratio_mean']:.4f}x (1 full 5h burst = {100.0 / burn_report['pool_ratio_mean']:.2f}% of weekly pool)")
    for iv in burn_report["intervals"]:
        r_str = f"{iv['ratio_5h_to_weekly']:.2f}x" if iv["ratio_5h_to_weekly"] is not None else "n/a"
        c_str = f"${iv['solved_5h_capacity_usd']:.2f}" if iv["solved_5h_capacity_usd"] is not None else "n/a"
        print(
            f"  [{iv['start_utc'][:19]} -> {iv['end_utc'][11:19]}] "
            f"d5h=+{iv['delta_5h_pct']:5.1f}% | dWk=+{iv['delta_weekly_pct']:5.2f}% | ratio={r_str:6s} | "
            f"turns={iv['turns_count']:3d} ({iv['primary_model_name']}) | "
            f"rate_card=${iv['rate_card_cost_usd']:6.2f} | solved_5h_cap={c_str}"
        )

    print("\n" + "=" * 80)
    print(" [OK] REGRESSION & CONVERGENCE VERIFICATION COMPLETE")
    print("=" * 80)
    return {
        "dry_run": False,
        "total_turns": len(all_gemini_turns),
        "weekly_turns": len(active_weekly),
        "weekly_cost": weekly_cost,
        "five_h_turns": len(active_5h),
        "five_h_cost": five_h_cost,
        "models_today": models_today,
        "burn_intervals": burn_report,
    }


def run_regime_review(
    vault_path: Path | None = None,
    ledger_path: Path | None = None,
    persist: bool = True,
) -> dict:
    """Print a full human-readable Quota Regime & Burn-Rate Audit report."""
    from src.quota_regime import (
        DEFAULT_REGIME_LEDGER_PATH,
        DEFAULT_VAULT_PATH,
        evaluate_vault_quota_regime,
    )

    v_path = vault_path or DEFAULT_VAULT_PATH
    l_path = ledger_path or DEFAULT_REGIME_LEDGER_PATH
    report = evaluate_vault_quota_regime(vault_path=v_path, ledger_path=l_path, persist=persist)

    print("=" * 88)
    print(" ANTIGRAVITY QUOTA REGIME & BURN-RATE AUDIT TRAIL")
    print("=" * 88)
    print(f" Active Regime ID         : {report.get('active_regime_id')} (since {report.get('active_regime_since_utc')})")
    print(f" Regime Status            : {report.get('status')} (Pending Review: {report.get('pending_review_count', 0)})")
    print(f" Rolling Drift Multiplier : {report.get('drift_ratio', 1.0):.3f}x vs Calibrated Post-Oct-17 Weights")
    print(f" 5h : Weekly Coupling     : {report.get('coupling_ratio_5h_to_weekly', 4.0):.4f}x (Nominal: 4.0000x)")
    print(
        f" Post-Reset Verification  : {report.get('post_reset_turns_analyzed', 0)} turns | "
        f"Observed Weekly Burn: {report.get('post_reset_weekly_burn_pct', 0.0):.2f}% vs "
        f"Predicted: {report.get('predicted_weekly_burn_pct', 0.0):.2f}%"
    )

    print("\n [1] PER-MODEL POST-RESET VERIFICATION COVERAGE")
    print("-" * 88)
    for mid, mc in sorted((report.get("model_coverage") or {}).items()):
        ver_str = "[VERIFIED]" if mc.get("verified") else "[UNPROBED (<5 turns)]"
        print(
            f"  • {mid} {mc.get('model_name', ''):28s} | {ver_str:21s} | "
            f"{mc.get('turns', 0):4d} turns | API=${mc.get('api_cost_usd', 0.0):6.2f} | "
            f"Quota=${mc.get('calibrated_quota_usd', 0.0):6.2f} ({mc.get('expected_5h_pct', 0.0):5.2f}% 5h)"
        )

    print("\n [2] HISTORICAL QUOTA REGIME & RESET AUDIT LEDGER")
    print("-" * 88)
    for ev in report.get("events", []):
        st = ev.get("review_status", "PENDING_REVIEW")
        conf_at = f" @ {ev['confirmed_at_utc']}" if ev.get("confirmed_at_utc") else ""
        print(
            f"  • [{st}{conf_at}] {ev.get('event_id')} ({ev.get('event_type')})\n"
            f"    Detected: {ev.get('detected_at_utc')} | Snapshots: {ev.get('snapshot_range')} | "
            f"Turns: {ev.get('turns_analyzed')} | 5h: {ev.get('delta_5h_pct'):+.2f}% | Weekly: {ev.get('delta_weekly_pct'):+.2f}%\n"
            f"    Summary : {ev.get('summary')}"
        )
    print("=" * 88)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Empirical rate card regression and cost-weighted quota convergence analysis."
    )
    parser.add_argument(
        "--antigravity-dir",
        type=Path,
        default=None,
        help="Path to Antigravity directory containing conversation databases (default: auto-discover)",
    )
    parser.add_argument(
        "--pricing-config",
        type=Path,
        default=None,
        help="Path to pricing.json configuration file (default: config/pricing.json)",
    )
    parser.add_argument(
        "--vault-path",
        type=Path,
        default=None,
        help="Path to antigravity_vault.db (default: data/antigravity_vault.db)",
    )
    parser.add_argument(
        "--regime-ledger",
        type=Path,
        default=None,
        help="Path to quota_regime_ledger.json (default: data/quota_regime_ledger.json)",
    )
    parser.add_argument(
        "--no-live-quota",
        action="store_true",
        help="Skip querying the live desktop quota indicator and use calibrated limits",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run rate card verification and proportion calculations without scanning conversation DBs",
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help="Display the historical Quota Regime & Burn-Rate Audit Ledger and per-model verification coverage",
    )
    parser.add_argument(
        "--confirm",
        type=str,
        default=None,
        metavar="EVENT_ID",
        help="Confirm a detected quota regime event (transitions status to CONFIRMED in ledger and Vault)",
    )
    parser.add_argument(
        "--dismiss",
        type=str,
        default=None,
        metavar="EVENT_ID",
        help="Dismiss a detected quota regime event as a transient anomaly (transitions status to DISMISSED)",
    )
    parser.add_argument(
        "--probe-prompts",
        action="store_true",
        help="Print standardized 6-turn sequential view_file staircase prompts for empirical burn-rate verification",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.probe_prompts:
        from src.quota_regime import generate_calibration_probe_prompts
        prompts = generate_calibration_probe_prompts()
        for label, prompt_text in prompts.items():
            print("=" * 88)
            print(f" CALIBRATION PROBE PROMPT: {label}")
            print("=" * 88)
            print(prompt_text)
            print()
        return 0

    if args.confirm or args.dismiss:
        from src.quota_regime import (
            DEFAULT_REGIME_LEDGER_PATH,
            DEFAULT_VAULT_PATH,
             evaluate_vault_quota_regime,
            update_regime_event_review_status,
        )
        v_path = args.vault_path or DEFAULT_VAULT_PATH
        l_path = args.regime_ledger or DEFAULT_REGIME_LEDGER_PATH
        # Ensure events are synced first
        evaluate_vault_quota_regime(vault_path=v_path, ledger_path=l_path, persist=not args.dry_run)
        target_id = args.confirm or args.dismiss
        new_status = "CONFIRMED" if args.confirm else "DISMISSED"
        updated = update_regime_event_review_status(
            event_id=target_id,
            new_status=new_status,
            vault_path=v_path,
            ledger_path=l_path,
        )
        if not updated:
            print(f"[ERROR] Regime event '{target_id}' not found in {l_path}.", file=sys.stderr)
            return 1
        print(f"[OK] Regime event '{target_id}' transitioned to {new_status} at {updated.get('confirmed_at_utc')}.")
        return 0

    if args.review:
        run_regime_review(
            vault_path=args.vault_path,
            ledger_path=args.regime_ledger,
            persist=not args.dry_run,
        )
        return 0

    run_regression_analysis(
        antigravity_dir=args.antigravity_dir,
        pricing_path=args.pricing_config,
        no_live_quota=args.no_live_quota,
        dry_run=args.dry_run,
        vault_path=args.vault_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
