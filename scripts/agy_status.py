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
        except Exception:
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
        except Exception:
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


def format_status_summary(data: dict) -> str:
    """One-line concise executive summary suitable for shell prompts and status bars."""
    gem_5h_rem = max(0.0, min(100.0, 100.0 - float(data.get("gemini_5h_pct", 0.0))))
    gem_1w_rem = max(0.0, min(100.0, 100.0 - float(data.get("gemini_weekly_pct", 0.0))))
    claude_rem = max(0.0, min(100.0, 100.0 - float(data.get("claude_weekly_pct", 0.0))))

    raw_status = str(data.get("status", "SAFE"))
    if "SAFE" in raw_status:
        status_label = "SAFE"
    elif "EXHAUSTED" in raw_status:
        status_label = "EXHAUSTED"
    elif "COOLDOWN" in raw_status:
        status_label = "COOLDOWN"
    else:
        status_label = raw_status

    if data.get("cooldown_active"):
        status_label += " (COOLDOWN)"

    claude_str = f"{int(round(claude_rem))}%" if claude_rem.is_integer() else f"{claude_rem:.1f}%"

    return f"[AGY: Gemini 5h: {gem_5h_rem:.1f}% rem | 1w: {gem_1w_rem:.1f}% rem | Claude: {claude_str} | Status: {status_label}]"


def format_status_short(data: dict) -> str:
    """Ultra-compact badge for narrow terminal prompt lines."""
    gem_5h_rem = int(round(max(0.0, min(100.0, 100.0 - float(data.get("gemini_5h_pct", 0.0))))))
    gem_1w_rem = int(round(max(0.0, min(100.0, 100.0 - float(data.get("gemini_weekly_pct", 0.0))))))
    claude_rem = int(round(max(0.0, min(100.0, 100.0 - float(data.get("claude_weekly_pct", 0.0))))))

    raw_status = str(data.get("status", "SAFE"))
    if "SAFE" in raw_status:
        status_label = "SAFE"
    elif "EXHAUSTED" in raw_status:
        status_label = "EXHAUSTED"
    elif "COOLDOWN" in raw_status:
        status_label = "COOLDOWN"
    else:
        status_label = raw_status

    if data.get("cooldown_active"):
        status_label = "COOL"

    return f"AGY: G:{gem_5h_rem}%/{gem_1w_rem}% C:{claude_rem}% ({status_label})"


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

    args = parser.parse_args()
    data = get_status_data(args.status_file)

    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    elif args.short:
        print(format_status_short(data))
    else:
        print(format_status_summary(data))


if __name__ == "__main__":
    main()
