#!/usr/bin/env python3
"""
Autonomous ingestion and reconciliation script for Google One AI credit statements,
receipts, invoices, and bank charge notices.

Records deductions deterministically into data/exhaustion_ledger.json
and data/antigravity_vault.db.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Default repository paths
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER_PATH = REPO_ROOT / "data" / "exhaustion_ledger.json"
DEFAULT_VAULT_PATH = REPO_ROOT / "data" / "antigravity_vault.db"

# Fallback conversion rates if not in ledger prepaid_pack
DEFAULT_COST_PER_CREDIT_GBP = 0.009596
DEFAULT_COST_PER_CREDIT_USD = 0.01


def parse_iso_datetime(dt_str: str) -> datetime:
    """Parse ISO 8601 string into a UTC timezone-aware datetime."""
    clean = dt_str.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as e:
        raise ValueError(f"Invalid ISO 8601 timestamp '{dt_str}': {e}")


def timestamps_match(ts1: Optional[str], ts2: Optional[str]) -> bool:
    """Check if two timestamp strings represent the exact same UTC moment."""
    if not ts1 or not ts2:
        return False
    if ts1 == ts2:
        return True
    try:
        return parse_iso_datetime(ts1) == parse_iso_datetime(ts2)
    except Exception:
        return False


def generate_incident_id(dt: datetime, existing_ids: Set[str]) -> str:
    """Generate a unique incident ID in format exc-YYYYMMDD-HH (or with suffix if collision occurs)."""
    base = f"exc-{dt.strftime('%Y%m%d-%H')}"
    if base not in existing_ids:
        return base
    # Sub-second or minute/second resolution if hour-level collision
    sub_id = f"exc-{dt.strftime('%Y%m%d-%H%M%S')}"
    if sub_id not in existing_ids:
        return sub_id
    counter = 1
    while f"{base}-{counter:02d}" in existing_ids:
        counter += 1
    return f"{base}-{counter:02d}"


def calculate_costs_and_credits(
    credits_burned: Optional[float],
    amount: Optional[float],
    currency: str,
    pack: Dict[str, Any],
) -> Tuple[float, float, float]:
    """
    Calculate and balance (credits_burned, credit_burn_gbp, credit_burn_usd).
    Respects rates defined in the ledger's prepaid_pack.
    """
    cost_per_credit_gbp = pack.get("cost_per_credit_gbp", DEFAULT_COST_PER_CREDIT_GBP)
    cost_per_credit_usd = pack.get("cost_per_credit_usd", DEFAULT_COST_PER_CREDIT_USD)
    curr = (currency or "GBP").upper().strip()

    c_burned = float(credits_burned) if credits_burned is not None else None
    c_amount = float(amount) if amount is not None else None

    if c_burned is not None and c_burned > 0:
        if c_amount is not None and c_amount > 0:
            if curr == "GBP":
                gbp = round(c_amount, 2)
                usd = round(c_burned * cost_per_credit_usd, 2)
            elif curr == "USD":
                usd = round(c_amount, 2)
                gbp = round(c_burned * cost_per_credit_gbp, 2)
            else:
                gbp = round(c_amount, 2)
                usd = round(c_burned * cost_per_credit_usd, 2)
        else:
            gbp = round(c_burned * cost_per_credit_gbp, 2)
            usd = round(c_burned * cost_per_credit_usd, 2)
    elif c_amount is not None and c_amount > 0:
        if curr == "GBP":
            gbp = round(c_amount, 2)
            c_burned = round(gbp / cost_per_credit_gbp)
            usd = round(c_burned * cost_per_credit_usd, 2)
        elif curr == "USD":
            usd = round(c_amount, 2)
            c_burned = round(usd / cost_per_credit_usd)
            gbp = round(c_burned * cost_per_credit_gbp, 2)
        else:
            gbp = round(c_amount, 2)
            c_burned = round(gbp / cost_per_credit_gbp)
            usd = round(c_burned * cost_per_credit_usd, 2)
    else:
        c_burned = 0.0
        gbp = 0.0
        usd = 0.0

    return c_burned, gbp, usd


def parse_models_arg(models_val: Any, turns_count: int) -> Dict[str, int]:
    """Parse models argument into a dictionary of {model_name: count}."""
    if isinstance(models_val, dict):
        return {str(k): int(v) for k, v in models_val.items()}

    if isinstance(models_val, list):
        if not models_val:
            return {"Gemini 3.8 Flash (High)": turns_count or 1}
        each = max(1, turns_count // len(models_val)) if turns_count > 0 else 0
        return {str(m).strip(): each for m in models_val if str(m).strip()}

    if isinstance(models_val, str):
        val = models_val.strip()
        if val.startswith("{") and val.endswith("}"):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, dict):
                    return {str(k): int(v) for k, v in parsed.items()}
            except Exception:
                pass
        if val.startswith("[") and val.endswith("]"):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    each = max(1, turns_count // len(parsed)) if turns_count > 0 else 0
                    return {str(m).strip(): each for m in parsed if str(m).strip()}
            except Exception:
                pass

        parts = [p.strip() for p in val.split(",") if p.strip()]
        if parts:
            each = max(1, turns_count // len(parts)) if turns_count > 0 else 0
            return {p: each for p in parts}

    return {"Gemini 3.8 Flash (High)": turns_count or 1}


def record_in_vault(vault_path: Path, incident: Dict[str, Any]) -> bool:
    """Record incident into log_events_archive in antigravity_vault.db if it exists."""
    if not vault_path.exists():
        return False

    import sqlite3

    try:
        conn = sqlite3.connect(str(vault_path))
        try:
            cur = conn.cursor()
            # Ensure log_events_archive table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS log_events_archive (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    event_type TEXT,
                    code INTEGER,
                    reason TEXT,
                    message TEXT,
                    payload_json TEXT,
                    created_at TEXT
                )
            """)

            cur.execute("PRAGMA table_info(log_events_archive)")
            existing_cols = [r[1] for r in cur.fetchall()]

            event_id = incident.get("incident_id")
            timestamp = incident.get("hour_timestamp") or incident.get("start_utc")
            event_type = "STATEMENT_RECONCILIATION"
            code = incident.get("code", 429)
            reason = incident.get("reason", "RESOURCE_EXHAUSTED")
            message = incident.get("description") or f"Statement deduction: {incident.get('credits_burned')} credits"
            payload_json = json.dumps(incident, sort_keys=True)
            created_at = datetime.now(timezone.utc).isoformat()

            data_map = {
                "event_id": event_id,
                "event_fingerprint": event_id,
                "timestamp": timestamp,
                "timestamp_iso": timestamp,
                "level": "INFO",
                "event_type": event_type,
                "code": code,
                "reason": reason,
                "message": message,
                "raw_line": message,
                "payload_json": payload_json,
                "created_at": created_at,
                "file_offset": 0,
            }

            cols_to_insert = [c for c in existing_cols if c in data_map]
            if not cols_to_insert:
                return False

            placeholders = ", ".join(["?"] * len(cols_to_insert))
            col_names = ", ".join(cols_to_insert)
            sql = f"INSERT OR REPLACE INTO log_events_archive ({col_names}) VALUES ({placeholders})"
            cur.execute(sql, [data_map[c] for c in cols_to_insert])
            conn.commit()
            return True
        finally:
            conn.close()
    except Exception as e:
        print(f"[WARN] Failed to write to vault database at {vault_path}: {e}", file=sys.stderr)
        return False


def build_incident_record(
    raw_data: Dict[str, Any],
    existing_ids: Set[str],
    prepaid_pack: Dict[str, Any],
) -> Dict[str, Any]:
    """Normalize and construct an incident record matching exhaustion_ledger.json schema."""
    # 1. Determine timestamps
    start_str = raw_data.get("start_utc")
    hour_str = raw_data.get("hour_timestamp")
    end_str = raw_data.get("end_utc")

    now_utc = datetime.now(timezone.utc)

    if start_str:
        start_dt = parse_iso_datetime(start_str)
    elif hour_str:
        start_dt = parse_iso_datetime(hour_str)
    else:
        start_dt = now_utc

    if hour_str:
        hour_dt = parse_iso_datetime(hour_str)
    else:
        hour_dt = start_dt.replace(minute=0, second=0, microsecond=0)

    if end_str:
        end_dt = parse_iso_datetime(end_str)
    else:
        end_dt = start_dt + timedelta(hours=1)

    hour_timestamp = hour_dt.strftime("%Y-%m-%dT%H:00:00Z")
    start_utc = start_dt.isoformat()
    end_utc = end_dt.isoformat()

    hour_display = raw_data.get("hour_display")
    if not hour_display:
        hour_display = hour_dt.strftime("%d %b %Y, %H:00:00 UTC")

    # 2. Incident ID
    incident_id = raw_data.get("incident_id")
    if not incident_id:
        incident_id = generate_incident_id(hour_dt, existing_ids)

    # 3. Financial and credit calculations
    credits_raw = raw_data.get("credits_burned")
    amount_raw = raw_data.get("amount")
    currency_raw = raw_data.get("currency", "GBP")

    c_burned, cost_gbp, cost_usd = calculate_costs_and_credits(
        credits_raw, amount_raw, currency_raw, prepaid_pack
    )

    # Format credits_burned as int if whole number
    credits_val: Any = int(c_burned) if c_burned.is_integer() else round(c_burned, 2)

    # 4. Turns count estimation
    turns_count = raw_data.get("turns_count")
    if turns_count is None:
        turns_count = int(round(c_burned / 2.5)) if c_burned > 0 else 0
    else:
        turns_count = int(turns_count)

    # 5. Models breakdown
    models = parse_models_arg(raw_data.get("models"), turns_count)

    # 6. Description and Reason
    reason = raw_data.get("reason") or "RESOURCE_EXHAUSTED"
    desc = raw_data.get("description")
    if not desc:
        if raw_data.get("reason") and raw_data.get("reason") != "RESOURCE_EXHAUSTED":
            desc = raw_data.get("reason")
        else:
            desc = f"Confirmed statement deduction: -{credits_val} credits (£{cost_gbp:.2f} / ${cost_usd:.2f})"

    return {
        "code": int(raw_data.get("code", 429)),
        "credit_burn_gbp": cost_gbp,
        "credit_burn_usd": cost_usd,
        "credits_burned": credits_val,
        "description": desc,
        "end_utc": end_utc,
        "hour_display": hour_display,
        "hour_timestamp": hour_timestamp,
        "incident_id": incident_id,
        "models": models,
        "reason": reason,
        "start_utc": start_utc,
        "turns_count": turns_count,
    }


def ingest_incident(
    incident_data: Dict[str, Any],
    ledger_path: Path = DEFAULT_LEDGER_PATH,
    vault_path: Path = DEFAULT_VAULT_PATH,
    dry_run: bool = False,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Ingest a single incident record into exhaustion_ledger.json and antigravity_vault.db.
    Returns (added_bool, status_message, incident_dict).
    """
    ledger_path = Path(ledger_path)
    vault_path = Path(vault_path)

    # 1. Load existing ledger
    if ledger_path.exists():
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                ledger = json.load(f)
        except Exception as e:
            return False, f"Failed to read existing ledger at {ledger_path}: {e}", None
    else:
        ledger = {
            "version": 1,
            "description": "Persistent append-only ledger of confirmed Google One AI credit exhaustion incidents and baseline deductions.",
            "prepaid_pack": {
                "total_credits": 2500,
                "purchase_price_gbp": 23.99,
                "purchase_price_usd": 25.0,
                "cost_per_credit_gbp": DEFAULT_COST_PER_CREDIT_GBP,
                "cost_per_credit_usd": DEFAULT_COST_PER_CREDIT_USD,
            },
            "incidents": [],
        }

    incidents: List[Dict[str, Any]] = ledger.get("incidents", [])
    existing_ids = {inc.get("incident_id") for inc in incidents if inc.get("incident_id")}
    pack = ledger.get("prepaid_pack", {})

    # 2. Construct normalized incident
    incident = build_incident_record(incident_data, existing_ids, pack)
    inc_id = incident["incident_id"]
    start_utc = incident["start_utc"]
    end_utc = incident["end_utc"]

    # 3. Duplicate check (by ID or exact matching start/end interval)
    for existing in incidents:
        if existing.get("incident_id") == inc_id:
            msg = f"[SKIP] Incident ID already exists in ledger: '{inc_id}'"
            return False, msg, existing
        if (
            existing.get("start_utc")
            and existing.get("end_utc")
            and timestamps_match(existing.get("start_utc"), start_utc)
            and timestamps_match(existing.get("end_utc"), end_utc)
        ):
            msg = f"[SKIP] Incident with exact time interval already exists: {start_utc} -> {end_utc} ('{existing.get('incident_id')}')"
            return False, msg, existing

    if dry_run:
        msg = f"[DRY-RUN] Would append incident {inc_id} ({incident['credits_burned']} credits, £{incident['credit_burn_gbp']:.2f} / ${incident['credit_burn_usd']:.2f})"
        return True, msg, incident

    # 4. Append and sort incidents chronologically
    incidents.append(incident)
    incidents.sort(key=lambda x: x.get("start_utc") or x.get("hour_timestamp") or "")
    ledger["incidents"] = incidents

    # 5. Atomically write back to ledger_path with indented sorted JSON
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = ledger_path.with_suffix(f".tmp.{os.getpid()}")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, ledger_path)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        return False, f"Failed writing to ledger {ledger_path}: {e}", None

    # 6. Record into Vault if antigravity_vault.db exists
    vault_recorded = False
    if vault_path.exists():
        vault_recorded = record_in_vault(vault_path, incident)

    vault_info = " and recorded in Vault" if vault_recorded else ""
    msg = (
        f"[OK] Reconciled deduction: {incident['credits_burned']:,} credits "
        f"(£{incident['credit_burn_gbp']:.2f} / ${incident['credit_burn_usd']:.2f}) "
        f"for incident '{inc_id}' ({incident['hour_display']}){vault_info}."
    )
    return True, msg, incident


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest and reconcile Google One AI credit statement deductions."
    )
    parser.add_argument(
        "--incident-id",
        type=str,
        default=None,
        help="Custom incident identifier (e.g. exc-20260906-09). Auto-generated if omitted.",
    )
    parser.add_argument(
        "--hour-timestamp",
        type=str,
        default=None,
        help="ISO 8601 hour timestamp (e.g. 2026-09-06T09:00:00Z).",
    )
    parser.add_argument(
        "--hour-display",
        type=str,
        default=None,
        help="Human-readable hour string (e.g. '06 Sep 2026, 09:00 BST').",
    )
    parser.add_argument(
        "--credits-burned",
        type=float,
        default=None,
        help="Amount of Google One AI credits debited (e.g. 748 or 1179).",
    )
    parser.add_argument(
        "--amount",
        type=float,
        default=None,
        help="Monetary charge debited (e.g. 7.18 or 11.31).",
    )
    parser.add_argument(
        "--currency",
        type=str,
        default="GBP",
        help="Currency of monetary charge (default: GBP, options: GBP, USD).",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Models involved, either comma-separated or JSON dict (e.g. 'Gemini 3.8 Flash (High)').",
    )
    parser.add_argument(
        "--start-utc",
        type=str,
        default=None,
        help="Start UTC timestamp in ISO 8601 format.",
    )
    parser.add_argument(
        "--end-utc",
        type=str,
        default=None,
        help="End UTC timestamp in ISO 8601 format.",
    )
    parser.add_argument(
        "--turns-count",
        type=int,
        default=None,
        help="Number of conversation turns involved in exhaustion interval.",
    )
    parser.add_argument(
        "--reason",
        type=str,
        default="RESOURCE_EXHAUSTED",
        help="Reason code or note (default: RESOURCE_EXHAUSTED).",
    )
    parser.add_argument(
        "--description",
        type=str,
        default=None,
        help="Detailed narrative description of the incident / receipt citation.",
    )
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=DEFAULT_LEDGER_PATH,
        help="Path to data/exhaustion_ledger.json (default: data/exhaustion_ledger.json).",
    )
    parser.add_argument(
        "--vault-path",
        type=Path,
        default=DEFAULT_VAULT_PATH,
        help="Path to data/antigravity_vault.db (default: data/antigravity_vault.db).",
    )
    parser.add_argument(
        "--json",
        dest="json_input",
        type=str,
        default=None,
        help="Raw JSON string or file path containing incident object or list of incidents.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate ingestion without writing to ledger or vault.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    # 1. Process from JSON input if supplied
    if args.json_input:
        content = args.json_input.strip()
        possible_path = Path(content)
        if possible_path.is_file():
            try:
                content = possible_path.read_text(encoding="utf-8")
            except Exception as e:
                print(f"Error reading JSON file '{possible_path}': {e}", file=sys.stderr)
                return 1

        try:
            parsed = json.loads(content)
        except Exception as e:
            print(f"Error parsing JSON content: {e}", file=sys.stderr)
            return 1

        # Determine if parsed is list, ledger, or single incident
        if isinstance(parsed, dict) and "incidents" in parsed:
            items = parsed["incidents"]
        elif isinstance(parsed, list):
            items = parsed
        elif isinstance(parsed, dict):
            items = [parsed]
        else:
            print("Error: JSON must be an incident object, list of incidents, or ledger object.", file=sys.stderr)
            return 1

        success_count = 0
        for item in items:
            # Command-line overrides for missing keys in item
            if args.currency and "currency" not in item:
                item["currency"] = args.currency
            if args.ledger_path and "ledger_path" not in item:
                item["ledger_path"] = args.ledger_path
            if args.vault_path and "vault_path" not in item:
                item["vault_path"] = args.vault_path

            success, msg, _ = ingest_incident(
                item,
                ledger_path=args.ledger_path,
                vault_path=args.vault_path,
                dry_run=args.dry_run,
            )
            print(msg)
            if success:
                success_count += 1

        return 0 if (success_count > 0 or not items) else 1

    # 2. Process from CLI arguments
    incident_data: Dict[str, Any] = {
        "incident_id": args.incident_id,
        "hour_timestamp": args.hour_timestamp,
        "hour_display": args.hour_display,
        "credits_burned": args.credits_burned,
        "amount": args.amount,
        "currency": args.currency,
        "models": args.models,
        "start_utc": args.start_utc,
        "end_utc": args.end_utc,
        "turns_count": args.turns_count,
        "reason": args.reason,
        "description": args.description,
    }

    success, msg, _ = ingest_incident(
        incident_data,
        ledger_path=args.ledger_path,
        vault_path=args.vault_path,
        dry_run=args.dry_run,
    )
    print(msg)
    return 0 if success or "[SKIP]" in msg else 1


if __name__ == "__main__":
    sys.exit(main())
