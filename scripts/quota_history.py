#!/usr/bin/env python3
"""
scripts/quota_history.py - Quota Exhaustion & Throttling History CLI.

Deterministic, zero-dependency analytics tool to audit macro statement exhaustion
incidents (Google One credit deductions) and micro turn-level 429 rejections
directly from the Telemetry Vault (data/antigravity_vault.db) and exhaustion ledger.

Usage:
    python3 scripts/quota_history.py                  # Full summary
    python3 scripts/quota_history.py --incidents      # Macro statement deductions only
    python3 scripts/quota_history.py --turns          # Turn-level 429 throttles only
    python3 scripts/quota_history.py --json           # Machine-readable JSON output
    python3 scripts/quota_history.py --vault-path <p> # Custom vault database path
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
from typing import Any, Dict, List, Optional

DEFAULT_VAULT_PATH = Path("data/antigravity_vault.db")
DEFAULT_LEDGER_PATH = Path("data/exhaustion_ledger.json")


def get_db_connection(vault_path: Path) -> sqlite3.Connection:
    """Connect to SQLite database in strict URI read-only mode."""
    if not vault_path.exists():
        raise FileNotFoundError(f"Vault database not found at {vault_path}")
    conn = sqlite3.connect(f"file:{vault_path.resolve()}?mode=ro", uri=True, timeout=60.0)
    conn.execute("PRAGMA busy_timeout = 60000;")
    return conn


def load_macro_incidents(
    conn: Optional[sqlite3.Connection], ledger_path: Path
) -> List[Dict[str, Any]]:
    """Load macro statement deduction incidents from ledger and/or vault log_events_archive."""
    incidents = []

    # Prefer exhaustion_ledger.json if available
    if ledger_path.exists():
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                incidents = data.get("incidents", [])
                if incidents:
                    return incidents
        except Exception:
            pass

    # Fallback to log_events_archive in vault DB
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT event_fingerprint, timestamp_iso, code, reason, raw_line
                FROM log_events_archive
                WHERE code = 429 OR reason = 'RESOURCE_EXHAUSTED'
                ORDER BY timestamp_iso ASC
                """
            )
            for row in cur.fetchall():
                fp, ts, code, reason, raw_line = row
                incidents.append(
                    {
                        "incident_id": fp,
                        "hour_timestamp": ts,
                        "code": code,
                        "reason": reason,
                        "description": raw_line,
                        "models": {},
                        "credits_burned": 0,
                    }
                )
        except sqlite3.Error:
            pass

    return incidents


def load_throttled_turns(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Load micro turn-level 429 rejections from v_turns / steps_archive."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT 
            date(timestamp) AS event_date,
            strftime('%Y-%m-%d %H:00:00', timestamp) AS event_hour,
            COALESCE(NULLIF(model_name, ''), 'Unknown Model') AS model_name,
            COUNT(*) AS throttled_turns,
            MIN(timestamp) AS first_ts,
            MAX(timestamp) AS last_ts
        FROM v_turns
        WHERE rate_limit_flag = 1
        GROUP BY event_date, event_hour, model_name
        ORDER BY event_hour ASC, model_name ASC
        """
    )
    results = []
    for row in cur.fetchall():
        results.append(
            {
                "event_date": row[0] or "Unknown",
                "event_hour": row[1] or "Unknown",
                "model_name": row[2],
                "throttled_turns": row[3],
                "first_ts": row[4],
                "last_ts": row[5],
            }
        )
    return results


def build_audit_report(vault_path: Path, ledger_path: Path) -> Dict[str, Any]:
    """Compile comprehensive quota audit report."""
    conn = None
    try:
        conn = get_db_connection(vault_path)
    except FileNotFoundError:
        conn = None

    incidents = load_macro_incidents(conn, ledger_path)
    turns = load_throttled_turns(conn) if conn else []

    deduction_incidents = [
        i for i in incidents
        if i.get("event_type") != "QUOTA_RESET_BONUS" and i.get("reason") != "QUOTA_RESET_BONUS"
    ]
    bonus_resets = [
        i for i in incidents
        if i.get("event_type") == "QUOTA_RESET_BONUS" or i.get("reason") == "QUOTA_RESET_BONUS"
    ]

    total_credits_burned = sum(i.get("credits_burned", 0) for i in deduction_incidents)
    total_burn_usd = sum(i.get("credit_burn_usd", 0.0) for i in deduction_incidents)
    total_burn_gbp = sum(i.get("credit_burn_gbp", 0.0) for i in deduction_incidents)
    total_bonus_credits_forgiven = sum(i.get("bonus_credits_forgiven", 0) for i in bonus_resets)
    total_bonus_value_usd = sum(i.get("bonus_value_usd", 0.0) for i in bonus_resets)
    total_bonus_value_gbp = sum(i.get("bonus_value_gbp", 0.0) for i in bonus_resets)
    total_throttled_turns = sum(t.get("throttled_turns", 0) for t in turns)

    affected_models = set()
    for inc in deduction_incidents:
        for m in inc.get("models", {}).keys():
            affected_models.add(m)
    for t in turns:
        affected_models.add(t["model_name"])

    report = {
        "summary": {
            "macro_incidents_count": len(deduction_incidents),
            "bonus_resets_count": len(bonus_resets),
            "total_credits_burned": total_credits_burned,
            "total_burn_usd": round(total_burn_usd, 2),
            "total_burn_gbp": round(total_burn_gbp, 2),
            "total_bonus_credits_forgiven": total_bonus_credits_forgiven,
            "total_bonus_value_usd": round(total_bonus_value_usd, 2),
            "total_bonus_value_gbp": round(total_bonus_value_gbp, 2),
            "turn_level_throttles_count": total_throttled_turns,
            "distinct_models_count": len(affected_models),
            "affected_models": sorted(list(affected_models)),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        "macro_incidents": incidents,
        "throttled_turn_windows": turns,
    }

    if conn:
        conn.close()
    return report


def render_table(headers: List[str], rows: List[List[Any]]) -> str:
    """Simple ASCII table formatter."""
    if not rows:
        return "  (No records found)\n"
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    row_lines = [
        " | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row))
        for row in rows
    ]
    return f"{header_line}\n{sep_line}\n" + "\n".join(row_lines) + "\n"


def print_cli_summary(report: Dict[str, Any], show_incidents: bool = True, show_turns: bool = True) -> None:
    """Print human-readable CLI summary."""
    s = report["summary"]
    print("=" * 80)
    print("  ANTIGRAVITY TELEMETRY VAULT: QUOTA EXHAUSTION & THROTTLING AUDIT")
    print("=" * 80)
    print(f"  Macro Exhaustion Incidents: {s['macro_incidents_count']} confirmed deductions")
    print(f"  Total Credits Burned:       {s['total_credits_burned']:,} credits (£{s['total_burn_gbp']:.2f} / ${s['total_burn_usd']:.2f})")
    if s.get("bonus_resets_count", 0) > 0:
        print(f"  Unscheduled Quota Resets:   {s['bonus_resets_count']} bonus reset (+{s['total_bonus_credits_forgiven']:,} credits / £{s['total_bonus_value_gbp']:.2f} / ${s['total_bonus_value_usd']:.2f} forgiven)")
    print(f"  Turn-Level Throttles (429): {s['turn_level_throttles_count']} model generation turns")
    print(f"  Affected Models ({s['distinct_models_count']}):       {', '.join(s['affected_models'])}")
    print("=" * 80)

    if show_incidents:
        print("\n--- 1. MACRO STATEMENT DEDUCTIONS & QUOTA EVENTS ---")
        headers = ["Incident ID", "Timestamp (UTC)", "Credits", "Burn GBP", "Burn USD", "Active Models (Turns)"]
        rows = []
        for inc in report["macro_incidents"]:
            models_summary = ", ".join(f"{k} ({v})" for k, v in inc.get("models", {}).items())
            is_bonus = inc.get("event_type") == "QUOTA_RESET_BONUS" or inc.get("reason") == "QUOTA_RESET_BONUS"
            if is_bonus:
                f_cred = f"0 (+{inc.get('bonus_credits_forgiven', 0)} forgiven)"
                f_gbp = f"+£{inc.get('bonus_value_gbp', 0.0):.2f} bonus"
                f_usd = f"+${inc.get('bonus_value_usd', 0.0):.2f} bonus"
            else:
                f_cred = inc.get("credits_burned", 0)
                f_gbp = f"£{inc.get('credit_burn_gbp', 0.0):.2f}"
                f_usd = f"${inc.get('credit_burn_usd', 0.0):.2f}"
            rows.append([
                inc.get("incident_id", ""),
                inc.get("hour_timestamp", ""),
                f_cred,
                f_gbp,
                f_usd,
                models_summary or "N/A",
            ])
        print(render_table(headers, rows))

    if show_turns:
        print("\n--- 2. MICRO TURN-LEVEL 429 REJECTIONS (v_turns with rate_limit_flag=1) ---")
        headers = ["Hour Window (UTC)", "Model Name", "Throttled Turns", "First Seen (UTC)", "Last Seen (UTC)"]
        rows = []
        for t in report["throttled_turn_windows"]:
            rows.append([
                t["event_hour"],
                t["model_name"],
                t["throttled_turns"],
                t["first_ts"][:19] if t["first_ts"] else "",
                t["last_ts"][:19] if t["last_ts"] else "",
            ])
        print(render_table(headers, rows))


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit quota exhaustions and 429 throttles from Telemetry Vault.")
    parser.add_argument("--vault-path", type=Path, default=DEFAULT_VAULT_PATH, help="Path to antigravity_vault.db")
    parser.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER_PATH, help="Path to exhaustion_ledger.json")
    parser.add_argument("--summary", action="store_true", help="Display full summary (default)")
    parser.add_argument("--incidents", action="store_true", help="Display only macro statement deduction incidents")
    parser.add_argument("--turns", action="store_true", help="Display only micro turn-level 429 rejections")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

    report = build_audit_report(args.vault_path, args.ledger_path)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    if args.incidents:
        print_cli_summary(report, show_incidents=True, show_turns=False)
    elif args.turns:
        print_cli_summary(report, show_incidents=False, show_turns=True)
    else:
        print_cli_summary(report, show_incidents=True, show_turns=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
