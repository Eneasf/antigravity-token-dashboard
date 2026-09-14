#!/usr/bin/env python3
"""
Deterministic exporter: Extracts Antigravity runtime telemetry and updates dashboard/index.html.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Optional

# Ensure repository root is on Python module search path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.aggregator import (
    load_pricing,
    aggregate_conversation_telemetry,
    aggregate_global_telemetry,
)
from src.log_reader import (
    DEFAULT_LOG_PATH,
    extract_exhaustion_intervals,
)
from antigravity_telemetry import (
    DEFAULT_ANTIGRAVITY_DIR,
    discover_all_conversations,
    read_conversation_turns,
    read_all_turns,
)
from src.swarm import (
    build_swarms_summary,
    extract_swarm_lineage,
)
from src.tool_analytics import extract_tool_analytics
from src.weekly_trends import (
    get_weekly_trends,
    sync_weekly_trends_to_vault,
)


DEFAULT_STATUS_PATH = Path.home() / ".antigravity_quota_status.json"


def write_quota_status_file(payload: dict, status_path: Optional[Path] = None) -> Path:
    """Atomically write executive quota status hook (~/.antigravity_quota_status.json)."""
    target = status_path if status_path is not None else DEFAULT_STATUS_PATH
    prov = payload.get("quotas", {}).get("providers", {})
    gem = prov.get("gemini", {})
    cg = prov.get("claude_gpt", {})
    gem_5h = gem.get("five_hour", {})
    gem_weekly = gem.get("weekly", {})
    cg_5h = cg.get("five_hour", {})
    cg_weekly = cg.get("weekly", {})
    runway = gem.get("runway", {})

    status = payload.get("summary", {}).get("subscription_status", "SAFE_IN_QUOTA")
    cooldown = runway.get("burst_cooldown_active", False)

    status_data = {
        "status": status,
        "gemini_5h_pct": round(float(gem_5h.get("used_pct", 0.0)), 1),
        "gemini_weekly_pct": round(float(gem_weekly.get("used_pct", 0.0)), 1),
        "claude_5h_pct": round(float(cg_5h.get("used_pct", 0.0)), 1),
        "claude_weekly_pct": round(float(cg_weekly.get("used_pct", 0.0)), 1),
        "cooldown_active": cooldown,
        "weekly_reset_utc": gem_weekly.get("weekly_reset_utc", ""),
        "updated_at": payload.get("temporal", {}).get("resolved_at_utc") or payload.get("temporal", {}).get("evaluation_time_utc") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    try:
        target_parent = target.parent
        if not target_parent.exists():
            target_parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(status_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp_path, target)
        return target
    except (PermissionError, OSError) as e:
        if status_path is not None:
            raise
        return None


def generate_markdown_digest(payload: dict) -> str:
    """
    Generate a byte-deterministic Markdown summary block for standup digests and PRs.

    Adheres strictly to ADR-004: Byte-identical output given identical payload.
    Uses strictly payload timestamps and stably sorted models.
    """
    s = payload.get("summary", {})
    quotas = payload.get("quotas", {})
    prov = quotas.get("providers", {})
    gem = prov.get("gemini", {})
    cg = prov.get("claude_gpt", {})
    gem_5h = gem.get("five_hour", {})
    gem_wk = gem.get("weekly", {})
    cg_5h = cg.get("five_hour", {})
    cg_wk = cg.get("weekly", {})
    runway = gem.get("runway", {})

    plan_name = s.get("subscription_tier_name") or s.get("subscription_tier", "Google AI Ultra (20 TB - 5x AI Usage)")
    plan_tier = s.get("subscription_tier", "ultra_5x")
    sub_gbp = s.get("monthly_subscription_price_gbp", 79.99)
    imputed_gbp = s.get("total_imputed_value_gbp", 0.0)
    imputed_usd = s.get("total_imputed_value_usd", 0.0)

    total_tokens = s.get("total_processed_tokens", 0)
    input_tokens = s.get("total_input_tokens", 0)
    output_tokens = s.get("total_output_tokens", 0)
    cached_tokens = s.get("total_cached_tokens", 0)
    cache_pct = s.get("cache_hit_ratio_pct", 0.0)

    credits_burned = s.get("total_ai_credits_burned", 0)
    burn_gbp = s.get("total_credit_burn_gbp", 0.0)
    burn_usd = s.get("total_credit_burn_usd", 0.0)
    credits_remaining = quotas.get("credit_bank", {}).get("remaining_credits", 1360)

    reset_disp = gem_wk.get("reset_display") or quotas.get("weekly_cycle", {}).get("reset_display") or "Thursday 18:00 UTC"
    bvi = runway.get("burn_velocity_index", 0.0)
    sub_status = s.get("subscription_status", "SAFE_IN_QUOTA")

    gem_5h_used = round(float(gem_5h.get("used_pct", 0.0)), 1)
    gem_5h_rem = round(max(0.0, 100.0 - gem_5h_used), 1)
    gem_wk_used = round(float(gem_wk.get("used_pct", 0.0)), 1)
    gem_wk_rem = round(max(0.0, 100.0 - gem_wk_used), 1)

    cg_5h_used = round(float(cg_5h.get("used_pct", 0.0)), 1)
    cg_5h_rem = round(max(0.0, 100.0 - cg_5h_used), 1)
    cg_wk_used = round(float(cg_wk.get("used_pct", 0.0)), 1)
    cg_wk_rem = round(max(0.0, 100.0 - cg_wk_used), 1)

    # Top models by token volume (deterministic sort: tokens desc, model_id asc)
    by_model = s.get("by_model", {})
    sorted_models = sorted(
        by_model.items(),
        key=lambda item: (item[1].get("total_processed_tokens", 0), item[0]),
        reverse=True,
    )

    top_models_lines = []
    for mid, mdata in sorted_models[:3]:
        mname = mdata.get("name", mid)
        mtoks = mdata.get("total_processed_tokens", 0)
        mturns = mdata.get("turn_count", 0)
        mcost = mdata.get("estimated_cost_gbp", 0.0)
        top_models_lines.append(f"  - **{mname}**: {mturns} turns, {mtoks:,} tokens (£{mcost:.2f})")

    if not top_models_lines:
        top_models_lines.append("  - No model activity recorded.")

    models_block = "\n".join(top_models_lines)

    lines = [
        "### 📊 Antigravity Telemetry Standup Digest",
        f"**Plan**: {plan_name} (`{plan_tier}`) | **Weekly Cycle Reset**: {reset_disp} | **Status**: `{sub_status}`",
        "",
        "#### 1. Token Throughput & Cache Efficiency",
        f"- **Total Processed**: {total_tokens:,} tokens",
        f"- **Input vs Output**: {input_tokens:,} input / {output_tokens:,} output",
        f"- **Context Cache Hit**: {cached_tokens:,} cached ({cache_pct:.1f}% hit ratio)",
        "",
        "#### 2. Economic Value & AI Credit Ledger",
        f"- **Imputed Avoided API Cost**: £{imputed_gbp:.2f} (${imputed_usd:.2f})",
        f"- **Monthly Plan Cost**: £{sub_gbp:.2f}/mo",
        f"- **AI Credit Deductions**: {credits_burned:,} credits (£{burn_gbp:.2f} / ${burn_usd:.2f}) | {credits_remaining:,} credits remaining in bank",
        "",
        "#### 3. Quota Runway & Headroom",
        f"- **Gemini 5-Hour Burst**: {gem_5h_used:.1f}% used ({gem_5h_rem:.1f}% remaining)",
        f"- **Gemini Weekly Runway**: {gem_wk_used:.1f}% used ({gem_wk_rem:.1f}% remaining) | BVI: {bvi:.2f}x",
        f"- **Claude/GPT 5-Hour Burst**: {cg_5h_used:.1f}% used ({cg_5h_rem:.1f}% remaining)",
        f"- **Claude/GPT Weekly**: {cg_wk_used:.1f}% used ({cg_wk_rem:.1f}% remaining)",
        "",
        "#### 4. Top Active Models",
        models_block,
    ]

    return "\n".join(lines) + "\n"


def export_telemetry(
    antigravity_dir: Path = DEFAULT_ANTIGRAVITY_DIR,
    dashboard_path: Path = REPO_ROOT / "dashboard" / "index.html",
    log_path: Optional[Path] = None,
    max_conversations: Optional[int] = None,
    dry_run: bool = False,
    embed: bool = False,
    status_path: Optional[Path] = None,
    no_live_quota: bool = False,
    reference_time: Optional[datetime.datetime] = None,
) -> dict:
    """Extract telemetry and export to decoupled data.js and dashboard HTML."""
    pricing = load_pricing()
    conv_dir = antigravity_dir / "conversations"
    discovered_count = len(list(conv_dir.glob("*.db"))) if conv_dir.exists() else 0
    conversations_meta = discover_all_conversations(antigravity_dir, max_conversations=max_conversations)
    scanned_count = len(conversations_meta)
    if discovered_count == 0:
        discovered_count = scanned_count
    exhaustion_intervals = extract_exhaustion_intervals(log_path=log_path)

    convo_summaries = []
    all_turns = []
    for meta in conversations_meta:
        db_path = Path(meta["db_path"])
        turns = read_conversation_turns(db_path)
        if turns:
            all_turns.extend(turns)
            summary = aggregate_conversation_telemetry(meta, turns, pricing, exhaustion_intervals=exhaustion_intervals)
            convo_summaries.append(summary)

    # Live desktop quota synchronization when targeting default Antigravity installation
    live_quota = None
    if not no_live_quota and antigravity_dir == DEFAULT_ANTIGRAVITY_DIR:
        try:
            from src.quota_client import fetch_live_quota_summary
            live_quota = fetch_live_quota_summary()
        except Exception:
            live_quota = None

    # Global aggregation with rolling window quotas and hybrid overage engine
    payload = aggregate_global_telemetry(
        convo_summaries,
        pricing,
        all_raw_turns=all_turns,
        exhaustion_intervals=exhaustion_intervals,
        live_quota=live_quota,
        discovered_databases=discovered_count,
        scanned_databases=scanned_count,
        reference_time=reference_time,
    )

    # Subagent swarm lineage and multi-agent economics
    swarms_list = extract_swarm_lineage(pricing_models=pricing)
    payload["swarms"] = build_swarms_summary(swarms_list, pricing_models=pricing)

    # Tool execution and skill performance analytics
    payload["tool_analytics"] = extract_tool_analytics()

    # Historical weekly cycles trends (M4 / ADR-039)
    if antigravity_dir == DEFAULT_ANTIGRAVITY_DIR:
        try:
            from src.vault import sync_subscription_to_vault
            sync_subscription_to_vault()
        except Exception:
            pass
        try:
            sync_weekly_trends_to_vault()
        except Exception:
            pass
        vault_file = None
    else:
        vault_file = antigravity_dir / "antigravity_vault.db"

    ledger_p = log_path.parent / "exhaustion_ledger.json" if log_path and log_path.parent else None
    trends_kwargs = {
        "fallback_turns": all_turns,
        "pricing_models": pricing,
        "ledger_path": ledger_p if ledger_p and ledger_p.exists() else None,
        "reference_time": reference_time,
    }
    if vault_file is not None:
        trends_kwargs["vault_path"] = vault_file
    payload["weekly_trends"] = get_weekly_trends(**trends_kwargs)

    # Sort conversations by first turn timestamp descending
    payload["conversations"].sort(
        key=lambda c: c.get("last_turn_ts") or c.get("first_turn_ts") or "",
        reverse=True,
    )

    # Trim unrendered fields from individual turns to optimize payload size (Decision 3)
    for convo in payload.get("conversations", []):
        for turn in convo.get("turns", []):
            turn.pop("session_id", None)
            turn.pop("agent_id", None)
            turn.pop("avoided_cost_gbp", None)

    json_str = json.dumps(payload, indent=2, sort_keys=True)

    r5h = payload.get("quotas", {}).get("rolling_5h", {})
    r1w = payload.get("quotas", {}).get("rolling_1w", {})
    sched = r5h.get("recovery_schedule", [])

    if dry_run:
        print(f"[DRY-RUN] Discovered {discovered_count} DBs (scanned {scanned_count}), extracted {len(convo_summaries)} active sessions.")
        print(f"[DRY-RUN] Lifetime Input: {payload['summary']['total_input_tokens']:,} | Cached: {payload['summary']['cache_hit_ratio_pct']}%")
        print(f"[DRY-RUN] Pro Subscription Status: {payload['summary']['subscription_status']} (Imputed Value: ${payload['summary']['total_imputed_value_usd']:.4f} | AI Credits Burned: {payload['summary']['total_ai_credits_burned']:,} credits (£{payload['summary']['total_credit_burn_gbp']:.2f} / ${payload['summary']['total_credit_burn_usd']:.2f}))")
        print(f"[DRY-RUN] Rolling 5-Hour: {r5h.get('total_processed_tokens', 0):,} tokens ({r5h.get('turn_count', 0)} turns)")
        if sched:
            print(f"[DRY-RUN] Next 5h Quota Recovery: in {sched[0]['minutes_remaining']}m (+{sched[0]['tokens_to_recover']:,} tokens from {sched[0]['model_name']})")
        print(f"[DRY-RUN] Rolling 1-Week: {r1w.get('total_processed_tokens', 0):,} tokens ({r1w.get('turn_count', 0)} turns)")
        if payload.get("hourly_credit_activity"):
            print(f"[DRY-RUN] Hourly Credit Deductions: {len(payload['hourly_credit_activity'])} billing blocks reconciled.")
        if payload.get("simulator_presets"):
            arch_count = len(payload["simulator_presets"].get("results", {}))
            print(f"[DRY-RUN] Workload Simulator: {arch_count} multi-agent archetypes pre-computed (plan: {payload['simulator_presets'].get('active_plan_tier')}).")
        if payload.get("swarms"):
            print(f"[DRY-RUN] Swarm Lineage: {payload['swarms'].get('total_swarms', 0)} multi-agent swarms discovered ({payload['swarms'].get('total_subagents', 0)} subagents).")
        if payload.get("tool_analytics"):
            print(f"[DRY-RUN] Tool Analytics: {payload['tool_analytics'].get('total_tool_calls', 0):,} tool invocations across {payload['tool_analytics'].get('unique_tools_count', 0)} tools.")
        if payload.get("weekly_trends"):
            wt = payload["weekly_trends"]
            cyc_cnt = len(wt.get("cycles", []))
            avg_toks = wt.get("summary", {}).get("average_tokens_per_week", 0)
            print(f"[DRY-RUN] Historical Trends: {cyc_cnt} weekly cycles archived (last 12 weeks avg: {avg_toks:,} tokens/wk).")
        return payload

    if not dashboard_path.exists():
        print(f"Error: Dashboard file {dashboard_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    html_content = dashboard_path.read_text(encoding="utf-8")
    pattern = r'(<script id="injected-dashboard-data" type="application/json">)(.*?)(</script>)'
    if not re.search(pattern, html_content, flags=re.DOTALL):
        print("Error: Could not find <script id=\"injected-dashboard-data\"> tag in dashboard HTML.", file=sys.stderr)
        sys.exit(1)

    # Always write decoupled data projection files atomically
    dashboard_dir = dashboard_path.parent
    data_js_path = dashboard_dir / "data.js"
    data_js_tmp = dashboard_dir / "data.js.tmp"
    data_js_tmp.write_text(f"window.__TELEMETRY_DATA__ = {json_str};\n", encoding="utf-8")
    os.replace(data_js_tmp, data_js_path)

    data_json_path = dashboard_dir / "data.json"
    data_json_tmp = dashboard_dir / "data.json.tmp"
    data_json_tmp.write_text(json_str, encoding="utf-8")
    os.replace(data_json_tmp, data_json_path)

    # Write decoupled metadata file with deterministic SHA-1 hash for fast ticker gating (Decision 5)
    payload_sha1 = hashlib.sha1(json_str.encode("utf-8")).hexdigest()
    gen_at = payload.get("temporal", {}).get("resolved_at_utc") or payload.get("temporal", {}).get("evaluation_time_utc") or datetime.datetime.now(datetime.timezone.utc).isoformat()
    meta_payload = {
        "payload_sha1": payload_sha1,
        "payload_bytes": len(json_str.encode("utf-8")),
        "conversations_count": len(convo_summaries),
        "generated_at": gen_at,
    }
    meta_json = json.dumps(meta_payload, indent=2, sort_keys=True)
    meta_js_path = dashboard_dir / "meta.js"
    meta_js_tmp = dashboard_dir / "meta.js.tmp"
    meta_js_tmp.write_text(f"window.__TELEMETRY_META__ = {meta_json};\n", encoding="utf-8")
    os.replace(meta_js_tmp, meta_js_path)

    meta_json_path = dashboard_dir / "meta.json"
    meta_json_tmp = dashboard_dir / "meta.json.tmp"
    meta_json_tmp.write_text(meta_json, encoding="utf-8")
    os.replace(meta_json_tmp, meta_json_path)

    if embed:
        new_html, count = re.subn(
            pattern,
            lambda m: f"{m.group(1)}\n{json_str}\n  {m.group(3)}",
            html_content,
            flags=re.DOTALL,
        )
        html_tmp = dashboard_path.with_suffix(".tmp")
        html_tmp.write_text(new_html, encoding="utf-8")
        os.replace(html_tmp, dashboard_path)
        print(f"Successfully embedded telemetry payload ({len(convo_summaries)} sessions) into {dashboard_path}")
    else:
        new_html = html_content
        needs_write = False
        if '<script src="meta.js"></script>' not in new_html:
            if '<script src="data.js"></script>' in new_html:
                new_html = new_html.replace(
                    '<script src="data.js"></script>',
                    '<script src="meta.js"></script>\n  <script src="data.js"></script>',
                )
                needs_write = True
            elif '</head>' in new_html:
                new_html = new_html.replace(
                    '</head>',
                    '  <script src="meta.js"></script>\n  <script src="data.js"></script>\n</head>',
                )
                needs_write = True
        elif '<script src="data.js"></script>' not in new_html:
            new_html = new_html.replace(
                '<script src="meta.js"></script>',
                '<script src="meta.js"></script>\n  <script src="data.js"></script>',
            )
            needs_write = True

        if needs_write:
            dashboard_path.write_text(new_html, encoding="utf-8")
        print(f"Successfully exported {len(convo_summaries)} conversation sessions to {data_js_path}")

    # Write external executive quota status hook (~/.antigravity_quota_status.json)
    write_quota_status_file(payload, status_path=status_path)

    print(f"Total Input: {payload['summary']['total_input_tokens']:,} | Cached: {payload['summary']['cache_hit_ratio_pct']}% | Imputed Value: £{payload['summary']['total_imputed_value_gbp']:.4f} (${payload['summary']['total_imputed_value_usd']:.4f}) | AI Credits Burned: {payload['summary']['total_ai_credits_burned']:,} credits (£{payload['summary']['total_credit_burn_gbp']:.2f} / ${payload['summary']['total_credit_burn_usd']:.2f}) | Status: {payload['summary']['subscription_status']}")
    return payload


def main():
    parser = argparse.ArgumentParser(description="Export Antigravity token telemetry to deterministic HTML dashboard.")
    parser.add_argument(
        "--antigravity-dir",
        type=Path,
        default=DEFAULT_ANTIGRAVITY_DIR,
        help="Path to ~/.gemini/antigravity directory",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Path to ~/Library/Logs/Antigravity/language_server.log",
    )
    parser.add_argument(
        "--dashboard-path",
        type=Path,
        default=REPO_ROOT / "dashboard" / "index.html",
        help="Path to dashboard/index.html",
    )
    parser.add_argument(
        "--max-conversations",
        type=int,
        default=None,
        help="Maximum conversations to scan (default: all discovered)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect telemetry and print summary without modifying dashboard",
    )
    parser.add_argument(
        "--embed",
        action="store_true",
        help="Embed full JSON payload directly into dashboard/index.html instead of decoupled data.js",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON payload to stdout",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Generate and print byte-deterministic Markdown standup digest to stdout",
    )
    parser.add_argument(
        "--markdown-file",
        type=Path,
        default=None,
        help="Path to write generated Markdown standup digest",
    )
    parser.add_argument(
        "--status-path",
        type=Path,
        default=None,
        help="Path to executive status JSON file (default: ~/.antigravity_quota_status.json)",
    )
    parser.add_argument(
        "--no-live-quota",
        action="store_true",
        help="Bypass live Connect-RPC quota synchronization (deterministic offline/CI mode)",
    )
    parser.add_argument(
        "--reference-time",
        type=str,
        default=None,
        help="Explicit evaluation timestamp (ISO-8601, e.g. '2026-09-13T20:00:00Z') for deterministic testing",
    )

    args = parser.parse_args()

    ref_dt = None
    if args.reference_time:
        try:
            ref_dt = datetime.datetime.fromisoformat(args.reference_time.replace("Z", "+00:00"))
        except Exception:
            from src.aggregator import parse_timestamp
            ref_dt = parse_timestamp(args.reference_time)

    if args.json or args.markdown:
        pricing = load_pricing()
        conv_dir = args.antigravity_dir / "conversations"
        discovered_count = len(list(conv_dir.glob("*.db"))) if conv_dir.exists() else 0
        meta = discover_all_conversations(args.antigravity_dir, max_conversations=args.max_conversations)
        scanned_count = len(meta)
        if discovered_count == 0:
            discovered_count = scanned_count
        intervals = extract_exhaustion_intervals(log_path=args.log_path)
        summaries = []
        all_turns = []
        for m in meta:
            t = read_conversation_turns(Path(m["db_path"]))
            if t:
                all_turns.extend(t)
                summaries.append(aggregate_conversation_telemetry(m, t, pricing, exhaustion_intervals=intervals))
        payload = aggregate_global_telemetry(
            summaries,
            pricing,
            all_raw_turns=all_turns,
            exhaustion_intervals=intervals,
            discovered_databases=discovered_count,
            scanned_databases=scanned_count,
            reference_time=ref_dt,
        )
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
            return
        if args.markdown:
            digest = generate_markdown_digest(payload)
            if args.markdown_file:
                args.markdown_file.write_text(digest, encoding="utf-8")
                print(f"Successfully wrote Markdown digest to {args.markdown_file}")
            else:
                print(digest, end="")
            return

    export_telemetry(
        antigravity_dir=args.antigravity_dir,
        dashboard_path=args.dashboard_path,
        log_path=args.log_path,
        max_conversations=args.max_conversations,
        dry_run=args.dry_run,
        embed=args.embed,
        status_path=args.status_path,
        no_live_quota=args.no_live_quota,
        reference_time=ref_dt,
    )


if __name__ == "__main__":
    main()
