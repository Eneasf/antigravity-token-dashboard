#!/usr/bin/env python3
"""
scripts/configure_plan.py

Lightweight CLI utility to inspect, calibrate, and update Antigravity plan
and pricing configuration in config/pricing.json (ADR-038 / M7).

Usage:
    python3 scripts/configure_plan.py --show
    python3 scripts/configure_plan.py --tier pro --billing-day 24
    python3 scripts/configure_plan.py --currency USD --monthly-price 19.99
    python3 scripts/configure_plan.py --tier enterprise_5x --billing-day 15
"""

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "pricing.json"
SAMPLE_CONFIG_PATH = REPO_ROOT / "config" / "pricing.sample.json"


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load pricing configuration, falling back to sample config if missing."""
    if not config_path.exists():
        if SAMPLE_CONFIG_PATH.exists():
            return json.loads(SAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    return json.loads(config_path.read_text(encoding="utf-8"))


def save_config_atomic(config: Dict[str, Any], config_path: Path) -> None:
    """Save configuration atomically via .tmp staging and os.replace."""
    tmp_path = config_path.parent / f"{config_path.name}.tmp"
    formatted_json = json.dumps(config, indent=2, sort_keys=False) + "\n"
    tmp_path.write_text(formatted_json, encoding="utf-8")
    os.replace(tmp_path, config_path)


def show_plan(config: Dict[str, Any], as_json: bool = False) -> None:
    """Display active plan and currency configuration."""
    if as_json:
        print(json.dumps({
            "subscription": config.get("subscription", {}),
            "currency": config.get("currency", {}),
        }, indent=2))
        return

    sub = config.get("subscription", {})
    curr = config.get("currency", {})
    ql = sub.get("quota_limits", {})
    def_curr = curr.get("default", "GBP")
    fx = curr.get("usd_to_gbp_fx_rate", 0.79)

    print("=" * 64)
    print("  ANTIGRAVITY ACTIVE PLAN & PRICING CONFIGURATION")
    print("=" * 64)
    print(f"  Tier Identifier   : {sub.get('tier', 'custom')}")
    print(f"  Plan Name         : {sub.get('name', 'Antigravity Plan')}")
    print(f"  Monthly Price     : £{sub.get('monthly_price_gbp', 0.0):.2f} / ${sub.get('monthly_price_usd', 0.0):.2f}")
    print(f"  Renewal Day       : Day {sub.get('renewal_day', 24)} of month")
    print(f"  Default Currency  : {def_curr} (USD->GBP FX: {fx})")
    print("-" * 64)
    print("  QUOTA CAPACITIES & BOUNDS")
    print(f"  Gemini 5h Burst   : ${ql.get('gemini_5h_capacity_usd', 20.0):.2f} USD")
    print(f"  Gemini Weekly     : ${ql.get('gemini_weekly_capacity_usd', 129.0):.2f} USD")
    print(f"  Claude/GPT 5h     : ${ql.get('claude_5h_capacity_usd', 10.0):.2f} USD")
    print(f"  Claude/GPT Weekly : ${ql.get('claude_weekly_capacity_usd', 35.0):.2f} USD")
    print(f"  5h Burst Tokens   : {ql.get('burst_5h_tokens', 168000000):,} tokens")
    print("=" * 64)


def apply_tier_preset(config: Dict[str, Any], tier: str) -> None:
    """Apply a recognized tier preset to config['subscription']."""
    try:
        from src.temporal import get_plan_preset
        preset = get_plan_preset(tier)
        if preset:
            sub = config.setdefault("subscription", {})
            for key in ["tier", "name", "monthly_price_gbp", "monthly_price_usd", "quota_limits", "windows"]:
                if key in preset:
                    sub[key] = preset[key]
            sub["tier"] = tier
            return
    except Exception:
        pass

    # Standard fallback presets
    sub = config.setdefault("subscription", {})
    sub["tier"] = tier
    ql = sub.setdefault("quota_limits", {})
    if tier == "pro":
        sub["name"] = "Google One AI Premium (Antigravity Pro)"
        sub["monthly_price_gbp"] = 18.99
        sub["monthly_price_usd"] = 19.99
        ql["gemini_5h_capacity_usd"] = 20.00
        ql["gemini_weekly_capacity_usd"] = 129.00
        ql["claude_5h_capacity_usd"] = 10.00
        ql["claude_weekly_capacity_usd"] = 35.00
        ql["burst_5h_tokens"] = 168000000
    elif tier in ("enterprise_5x", "ultra_5x"):
        sub["name"] = "Google AI Ultra / Enterprise 5x"
        sub["monthly_price_gbp"] = 79.99
        sub["monthly_price_usd"] = 99.99
        ql["gemini_5h_capacity_usd"] = 100.00
        ql["gemini_weekly_capacity_usd"] = 645.00
        ql["claude_5h_capacity_usd"] = 50.00
        ql["claude_weekly_capacity_usd"] = 175.00
        ql["burst_5h_tokens"] = 840000000
    elif tier == "ultra_10x":
        sub["name"] = "Google AI Ultra 10x"
        sub["monthly_price_gbp"] = 159.99
        sub["monthly_price_usd"] = 199.99
        ql["gemini_5h_capacity_usd"] = 200.00
        ql["gemini_weekly_capacity_usd"] = 1290.00
        ql["claude_5h_capacity_usd"] = 100.00
        ql["claude_weekly_capacity_usd"] = 350.00
        ql["burst_5h_tokens"] = 1680000000


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Antigravity Plan & Pricing Configuration CLI (ADR-038)."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="Path to pricing.json")
    parser.add_argument("--show", action="store_true", help="Display current active plan configuration and exit")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("--tier", type=str, choices=["pro", "enterprise_5x", "ultra_5x", "ultra_10x", "ultra_20x"], help="Apply preset tier")
    parser.add_argument("--name", type=str, help="Custom plan name")
    parser.add_argument("--currency", type=str, choices=["GBP", "USD", "EUR"], help="Default currency")
    parser.add_argument("--monthly-price", type=float, help="Monthly subscription price in default currency")
    parser.add_argument("--monthly-price-gbp", type=float, help="Monthly subscription price in GBP")
    parser.add_argument("--monthly-price-usd", type=float, help="Monthly subscription price in USD")
    parser.add_argument("--billing-day", type=int, choices=range(1, 32), metavar="1-31", help="Monthly renewal day")
    parser.add_argument("--fx-rate", type=float, help="USD to GBP exchange rate")
    parser.add_argument("--gemini-5h-capacity", type=float, help="Gemini 5-hour quota capacity in USD")
    parser.add_argument("--gemini-weekly-capacity", type=float, help="Gemini weekly quota capacity in USD")
    parser.add_argument("--claude-5h-capacity", type=float, help="Claude/GPT 5-hour quota capacity in USD")
    parser.add_argument("--claude-weekly-capacity", type=float, help="Claude/GPT weekly quota capacity in USD")
    parser.add_argument("--effective-from", type=str, help="ISO 8601 effective timestamp for tier change in subscription_history")

    args = parser.parse_args()

    config = load_config(args.config)

    if args.show or (len(sys.argv) == 1):
        show_plan(config, as_json=args.json)
        sys.exit(0)

    changed = False
    sub = config.setdefault("subscription", {})
    curr = config.setdefault("currency", {})
    ql = sub.setdefault("quota_limits", {})

    if args.tier:
        apply_tier_preset(config, args.tier)
        changed = True

    if args.name:
        sub["name"] = args.name
        changed = True

    if args.currency:
        curr["default"] = args.currency
        changed = True

    if args.fx_rate:
        curr["usd_to_gbp_fx_rate"] = args.fx_rate
        changed = True

    fx = curr.get("usd_to_gbp_fx_rate", 0.79)
    def_curr = curr.get("default", "GBP")

    if args.monthly_price is not None:
        if def_curr == "GBP":
            sub["monthly_price_gbp"] = args.monthly_price
            sub["monthly_price_usd"] = round(args.monthly_price / fx, 2) if fx > 0 else args.monthly_price
        else:
            sub["monthly_price_usd"] = args.monthly_price
            sub["monthly_price_gbp"] = round(args.monthly_price * fx, 2)
        changed = True

    if args.monthly_price_gbp is not None:
        sub["monthly_price_gbp"] = args.monthly_price_gbp
        changed = True

    if args.monthly_price_usd is not None:
        sub["monthly_price_usd"] = args.monthly_price_usd
        changed = True

    if args.billing_day is not None:
        sub["renewal_day"] = args.billing_day
        changed = True

    if args.gemini_5h_capacity is not None:
        ql["gemini_5h_capacity_usd"] = args.gemini_5h_capacity
        changed = True

    if args.gemini_weekly_capacity is not None:
        ql["gemini_weekly_capacity_usd"] = args.gemini_weekly_capacity
        changed = True

    if args.claude_5h_capacity is not None:
        ql["claude_5h_capacity_usd"] = args.claude_5h_capacity
        changed = True

    if args.claude_weekly_capacity is not None:
        ql["claude_weekly_capacity_usd"] = args.claude_weekly_capacity
        changed = True

    if changed:
        if args.tier and "subscription_history" in config:
            from copy import deepcopy
            import datetime
            ts = args.effective_from or datetime.datetime.now(datetime.timezone.utc).isoformat()
            if ts.endswith("+00:00"):
                ts = ts[:-6] + "Z"
            history = config["subscription_history"]
            for h in history:
                if h.get("valid_to") is None:
                    h["valid_to"] = ts
            new_h = deepcopy(sub)
            new_h["valid_from"] = ts
            new_h["valid_to"] = None
            history.append(new_h)

        save_config_atomic(config, args.config)
        print(f"[SUCCESS] Updated plan configuration in {args.config}")
        show_plan(config, as_json=args.json)
    else:
        show_plan(config, as_json=args.json)


if __name__ == "__main__":
    main()
