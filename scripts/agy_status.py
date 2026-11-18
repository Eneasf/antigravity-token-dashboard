#!/usr/bin/env python3
"""
Fast executive quota status CLI (<5ms).

Reads ~/.antigravity_quota_status.json to provide instantaneous quota and cooldown
status suitable for shell prompts (Starship, zsh, fish), tmux status bars, and desktop widgets.
"""

import argparse
import json
import os
from pathlib import Path
import sys

DEFAULT_STATUS_FILE = Path.home() / ".antigravity_quota_status.json"


def get_status_data(status_path: Path = DEFAULT_STATUS_FILE) -> dict:
    """Read and parse quota status JSON file with graceful fallbacks."""
    if status_path.exists():
        try:
            return json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    # Fallback to local dashboard/data.json if status hook is not yet written
    repo_root = Path(__file__).resolve().parent.parent
    data_json = repo_root / "dashboard" / "data.json"
    if data_json.exists():
        try:
            data = json.loads(data_json.read_text(encoding="utf-8"))
            prov = data.get("quotas", {}).get("providers", {})
            gem = prov.get("gemini", {})
            cg = prov.get("claude_gpt", {})
            return {
                "status": data.get("summary", {}).get("subscription_status", "SAFE_IN_QUOTA"),
                "gemini_5h_pct": round(float(gem.get("five_hour", {}).get("used_pct", 0.0)), 1),
                "gemini_weekly_pct": round(float(gem.get("weekly", {}).get("used_pct", 0.0)), 1),
                "claude_5h_pct": round(float(cg.get("five_hour", {}).get("used_pct", 0.0)), 1),
                "claude_weekly_pct": round(float(cg.get("weekly", {}).get("used_pct", 0.0)), 1),
                "cooldown_active": gem.get("runway", {}).get("burst_cooldown_active", False),
                "weekly_reset_utc": gem.get("weekly", {}).get("weekly_reset_utc", ""),
                "updated_at": data.get("temporal", {}).get("evaluation_time_utc", ""),
            }
        except (OSError, json.JSONDecodeError, ValueError, KeyError):
            pass

    return {
        "status": "NO_DATA",
        "gemini_5h_pct": 0.0,
        "gemini_weekly_pct": 0.0,
        "claude_5h_pct": 0.0,
        "claude_weekly_pct": 0.0,
        "cooldown_active": False,
        "weekly_reset_utc": "",
        "updated_at": "",
    }


def _extract_tracks(data: dict) -> list[dict]:
    """Normalize provider tracks from v2 tracks[] or legacy v1 fields."""
    tracks = data.get("tracks")
    if isinstance(tracks, list) and len(tracks) > 0:
        out = []
        for t in tracks:
            if not isinstance(t, dict):
                continue
            tid = str(t.get("id") or "")
            is_primary = bool(t.get("is_primary", tid == "gemini"))
            wins = {
                str(w.get("window_id")): w
                for w in (t.get("windows") or [])
                if isinstance(w, dict) and w.get("window_id")
            }
            w5 = wins.get("5h", {})
            ww = wins.get("weekly", {})
            u5 = float(w5.get("used_pct", 0.0) or 0.0)
            r5 = float(w5.get("remaining_pct", max(0.0, min(100.0, 100.0 - u5))))
            uw = float(ww.get("used_pct", 0.0) or 0.0)
            rw = float(ww.get("remaining_pct", max(0.0, min(100.0, 100.0 - uw))))
            summary_label = (
                "Gemini"
                if tid == "gemini"
                else ("Claude" if tid == "claude_gpt" else str(t.get("short_name") or t.get("name") or tid))
            )
            short_code = (
                "G"
                if tid == "gemini"
                else ("C" if tid == "claude_gpt" else (summary_label[:1].upper() or "T"))
            )
            out.append({
                "id": tid,
                "name": str(t.get("name") or summary_label),
                "short_name": str(t.get("short_name") or summary_label),
                "summary_label": summary_label,
                "short_code": short_code,
                "is_primary": is_primary,
                "rem_5h": max(0.0, min(100.0, r5)),
                "rem_1w": max(0.0, min(100.0, rw)),
                "recovery_desc": str(w5.get("recovery_desc") or data.get("gemini_5h_recovery_desc", "100% headroom")),
                "reset_desc": str(ww.get("reset_desc") or data.get("weekly_reset_desc", "Weekly reset")),
                "bvi": ww.get("bvi", data.get("bvi", "1.0")),
                "bvi_label": str(ww.get("bvi_label") or data.get("bvi_verdict", "On Track")),
                "is_cooldown": bool(w5.get("is_cooldown") or ww.get("is_cooldown")),
            })
        if out:
            return out

    gem_5h_rem = max(0.0, min(100.0, 100.0 - float(data.get("gemini_5h_pct", 0.0))))
    gem_1w_rem = max(0.0, min(100.0, 100.0 - float(data.get("gemini_weekly_pct", 0.0))))
    claude_5h_rem = max(0.0, min(100.0, 100.0 - float(data.get("claude_5h_pct", 0.0))))
    claude_1w_rem = max(0.0, min(100.0, 100.0 - float(data.get("claude_weekly_pct", 0.0))))
    return [
        {
            "id": "gemini",
            "name": "Gemini",
            "short_name": "Gemini",
            "summary_label": "Gemini",
            "short_code": "G",
            "is_primary": True,
            "rem_5h": gem_5h_rem,
            "rem_1w": gem_1w_rem,
            "recovery_desc": str(data.get("gemini_5h_recovery_desc", "100% headroom")),
            "reset_desc": str(data.get("weekly_reset_desc", "Weekly reset")),
            "bvi": data.get("bvi", "1.0"),
            "bvi_label": str(data.get("bvi_verdict", "On Track")),
            "is_cooldown": bool(data.get("cooldown_active", False)),
        },
        {
            "id": "claude_gpt",
            "name": "Claude/GPT",
            "short_name": "Claude/GPT",
            "summary_label": "Claude",
            "short_code": "C",
            "is_primary": False,
            "rem_5h": claude_5h_rem,
            "rem_1w": claude_1w_rem,
            "recovery_desc": "",
            "reset_desc": "7-day rolling window",
            "bvi": None,
            "bvi_label": "",
            "is_cooldown": False,
        },
    ]


def format_status_summary(data: dict) -> str:
    """One-line concise executive summary suitable for shell prompts and status bars."""
    tracks = _extract_tracks(data)

    raw_status = str(data.get("status", "SAFE"))
    if "SAFE" in raw_status:
        status_label = "SAFE"
    elif "EXHAUSTED" in raw_status:
        status_label = "EXHAUSTED"
    elif "COOLDOWN" in raw_status:
        status_label = "COOLDOWN"
    else:
        status_label = raw_status

    if data.get("cooldown_active") or any(t["is_cooldown"] for t in tracks if t["is_primary"]):
        if "COOLDOWN" not in status_label:
            status_label += " (COOLDOWN)"

    segments = []
    for t in tracks:
        if t["is_primary"]:
            segments.append(f"{t['summary_label']} 5h: {t['rem_5h']:.1f}% rem | 1w: {t['rem_1w']:.1f}% rem")
        else:
            rem_val = t["rem_1w"]
            rem_str = f"{int(round(rem_val))}%" if rem_val.is_integer() else f"{rem_val:.1f}%"
            segments.append(f"{t['summary_label']}: {rem_str}")

    return f"[AGY: {' | '.join(segments)} | Status: {status_label}]"


def format_status_short(data: dict) -> str:
    """Ultra-compact badge for narrow terminal prompt lines."""
    tracks = _extract_tracks(data)

    raw_status = str(data.get("status", "SAFE"))
    if "SAFE" in raw_status:
        status_label = "SAFE"
    elif "EXHAUSTED" in raw_status:
        status_label = "EXHAUSTED"
    elif "COOLDOWN" in raw_status:
        status_label = "COOLDOWN"
    else:
        status_label = raw_status

    if data.get("cooldown_active") or any(t["is_cooldown"] for t in tracks if t["is_primary"]):
        status_label = "COOL"

    badges = []
    for t in tracks:
        r5 = int(round(t["rem_5h"]))
        rw = int(round(t["rem_1w"]))
        if t["is_primary"]:
            badges.append(f"{t['short_code']}:{r5}%/{rw}%")
        else:
            badges.append(f"{t['short_code']}:{rw}%")

    return f"AGY: {' '.join(badges)} ({status_label})"


def format_status_verbose(data: dict) -> str:
    """Multi-line rich executive breakdown for terminal inspection."""
    tracks = _extract_tracks(data)
    plan_obj = data.get("plan") if isinstance(data.get("plan"), dict) else {}
    plan_title = data.get("plan_name") or plan_obj.get("name") or "Plan"
    lines = [
        f"Antigravity Quota Monitor: {plan_title} [{data.get('status', 'SAFE')}]",
    ]
    for t in tracks:
        if t["is_primary"]:
            lines.append(f"  {t['short_name']} 5h Burst:    {t['rem_5h']:.1f}% headroom ({t['recovery_desc']})")
            lines.append(f"  {t['short_name']} Weekly:      {t['rem_1w']:.1f}% runway ({t['reset_desc']})")
            lines.append(f"  Weekly Pacing:      BVI {t['bvi']}x | {t['bvi_label']}")
        else:
            lines.append(f"  {t['short_name']} Track:   {t['rem_1w']:.1f}% weekly remaining (5h: {t['rem_5h']:.1f}%)")
    lines.extend([
        f"  Active Context:     {data.get('active_project', 'Default')} on branch '{data.get('active_branch', 'main')}'",
        f"  Credit Bank:        {data.get('credit_balance', 'N/A')}",
        f"  Updated:            {data.get('updated_at', 'N/A')}",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fast Antigravity executive quota status inspector (<5ms).")
    parser.add_argument(
        "--status-file",
        "--status-path",
        dest="status_file",
        type=Path,
        default=DEFAULT_STATUS_FILE,
        help="Path to quota status JSON file (default: ~/.antigravity_quota_status.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw status JSON payload",
    )
    parser.add_argument(
        "--short",
        action="store_true",
        help="Output ultra-compact badge for narrow status prompts",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Output multi-line rich executive breakdown",
    )

    args = parser.parse_args()
    data = get_status_data(args.status_file)

    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    elif args.short:
        print(format_status_short(data))
    elif args.verbose:
        print(format_status_verbose(data))
    else:
        print(format_status_summary(data))


if __name__ == "__main__":
    main()
