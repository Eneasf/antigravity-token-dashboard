"""
Safe log reader for Antigravity runtime logs.

Extracts rate limiting events, 429 RESOURCE_EXHAUSTED errors,
and overage time intervals from ~/Library/Logs/Antigravity/language_server.log.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

DEFAULT_LOG_PATH = Path.home() / "Library" / "Logs" / "Antigravity" / "language_server.log"
DEFAULT_LEDGER_PATH = Path(__file__).resolve().parent.parent / "data" / "exhaustion_ledger.json"

# glog format (often prefixed with "ERROR: logging before google.Init: "):
# e.g., ERROR: logging before google.Init: I0905 13:35:13.877653    8813 run.go:371] ...
GLOG_TIMESTAMP_PATTERN = re.compile(
    r"[IWEF](\d{2})(\d{2})\s+(\d{2}):(\d{2}):(\d{2})\.(\d{6})"
)
EXHAUSTION_PATTERN = re.compile(
    r"(RESOURCE_EXHAUSTED|code 429|exhausted your capacity)", re.IGNORECASE
)


def parse_glog_timestamp(line: str, year: Optional[int] = None) -> Optional[datetime]:
    """Parse Google glog timestamp from a log line into a UTC datetime."""
    match = GLOG_TIMESTAMP_PATTERN.search(line)
    if not match:
        return None

    month = int(match.group(1))
    day = int(match.group(2))
    hour = int(match.group(3))
    minute = int(match.group(4))
    second = int(match.group(5))
    microsecond = int(match.group(6))

    if year is None:
        year = datetime.now(timezone.utc).year

    try:
        return datetime(
            year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc
        )
    except ValueError:
        return None


def extract_raw_exhaustion_events(log_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Scan log file and return all discrete 429 RESOURCE_EXHAUSTED events."""
    path = log_path or DEFAULT_LOG_PATH
    if not path.exists():
        return []

    year = datetime.now(timezone.utc).year
    try:
        mtime = path.stat().st_mtime
        year = datetime.fromtimestamp(mtime, tz=timezone.utc).year
    except Exception:
        pass

    events = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                if EXHAUSTION_PATTERN.search(line):
                    ts = parse_glog_timestamp(line, year=year)
                    events.append({
                        "line_no": line_no,
                        "timestamp": ts,
                        "timestamp_iso": ts.isoformat() if ts else None,
                        "raw_line": line.strip(),
                    })
    except (PermissionError, OSError):
        return []

    return events


def reconstruct_ledger_from_vault(vault_path: Path) -> Dict[str, Any]:
    """Reconstruct exhaustion ledger from log_events_archive in antigravity_vault.db."""
    import sqlite3
    if not vault_path.exists():
        return {"version": 1, "incidents": []}

    incidents = []
    try:
        conn = sqlite3.connect(f"file:{vault_path.resolve()}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='log_events_archive'")
        if not cur.fetchone():
            conn.close()
            return {"version": 1, "incidents": []}

        cur.execute("""
            SELECT event_fingerprint, timestamp, raw_line, code, reason
            FROM log_events_archive
            WHERE event_type = 'STATEMENT_RECONCILIATION'
            ORDER BY timestamp ASC
        """)
        rows = cur.fetchall()
        conn.close()

        deduction_pattern = re.compile(
            r"-(\d+)\s+credits.*?\((\d{2}\s+[A-Za-z]{3}\s+\d{4},\s+\d{2}:\d{2}(?::\d{2})?\s+[A-Za-z]+)\)"
        )

        for fp, ts, raw_line, code, reason in rows:
            credits_burned = 0
            hour_disp = None
            if raw_line:
                m = deduction_pattern.search(raw_line)
                if m:
                    credits_burned = int(m.group(1))
                    hour_disp = m.group(2)
                else:
                    m2 = re.search(r"-(\d+)\s+credits", raw_line)
                    if m2:
                        credits_burned = int(m2.group(1))

            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else datetime.now(timezone.utc)
            except Exception:
                dt = datetime.now(timezone.utc)

            if not hour_disp:
                hour_disp = dt.strftime("%d %b %Y, %H:00:00 UTC")

            cost_gbp = round(credits_burned * 0.009596, 2)
            cost_usd = round(credits_burned * 0.01, 2)
            end_dt = dt + timedelta(hours=1)
            turns_cnt = int(round(credits_burned / 2.5)) if credits_burned > 0 else 0

            incidents.append({
                "code": code or 429,
                "credit_burn_gbp": cost_gbp,
                "credit_burn_usd": cost_usd,
                "credits_burned": credits_burned,
                "description": raw_line or f"Confirmed statement deduction: -{credits_burned} credits",
                "end_utc": end_dt.isoformat(),
                "hour_display": hour_disp,
                "hour_timestamp": dt.strftime("%Y-%m-%dT%H:00:00Z"),
                "incident_id": fp or f"exc-{dt.strftime('%Y%m%d-%H')}",
                "models": {"Gemini 3.8 Flash (High)": turns_cnt},
                "reason": reason or "RESOURCE_EXHAUSTED",
                "start_utc": dt.isoformat(),
                "turns_count": turns_cnt,
            })
    except Exception:
        return {"version": 1, "incidents": []}

    return {
        "version": 1,
        "description": "Persistent append-only ledger of confirmed Google One AI credit exhaustion incidents and baseline deductions.",
        "prepaid_pack": {
            "auto_reload": True,
            "cost_per_credit_gbp": 0.009596,
            "cost_per_credit_usd": 0.01,
            "pack_size": 2500,
            "packs_purchased": 2,
            "purchase_price_gbp": 47.98,
            "purchase_price_usd": 50.0,
            "total_credits": 5000,
        },
        "incidents": incidents,
    }


def load_persistent_ledger(ledger_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load persistent overage exhaustion ledger from disk, falling back to vault reconstruction if missing."""
    if ledger_path is not None:
        path = Path(ledger_path)
        if not path.exists():
            return {"version": 1, "incidents": []}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"version": 1, "incidents": []}

    path = DEFAULT_LEDGER_PATH
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Self-healing from antigravity_vault.db if persistent JSON ledger is missing
    vault_path = path.parent / "antigravity_vault.db"
    if vault_path.exists():
        reconstructed = reconstruct_ledger_from_vault(vault_path)
        if reconstructed.get("incidents"):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(reconstructed, f, indent=2, sort_keys=True)
                    f.write("\n")
            except Exception:
                pass
            return reconstructed

    return {"version": 1, "incidents": []}



def extract_exhaustion_intervals(
    log_path: Optional[Path] = None,
    ledger_path: Optional[Any] = None,
    cluster_gap_minutes: float = 60.0,
    cooldown_padding_minutes: float = 60.0,
    round_to_hour_block: bool = False,
) -> List[Dict[str, Any]]:
    """
    Extract continuous exhaustion intervals, fusing permanent records from
    data/exhaustion_ledger.json with active live events from language_server.log.
    Guarantees that log truncations on application restarts do not lose historical credit burn.
    Pass ledger_path=False to disable persistent ledger loading (e.g. for pure log tests).
    """
    intervals: List[Dict[str, Any]] = []

    # 1. Load confirmed historical incidents from persistent ledger if enabled
    if ledger_path is not False:
        l_path = ledger_path if isinstance(ledger_path, Path) else DEFAULT_LEDGER_PATH
        ledger_data = load_persistent_ledger(l_path)
        for inc in ledger_data.get("incidents", []):
            start_ts = inc.get("start_utc")
            end_ts = inc.get("end_utc")
            if start_ts and end_ts:
                start_dt = datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_ts.replace("Z", "+00:00"))
                intervals.append({
                    "incident_id": inc.get("incident_id"),
                    "hour_timestamp": inc.get("hour_timestamp"),
                    "hour_display": inc.get("hour_display"),
                    "turns_count": inc.get("turns_count"),
                    "credits_burned": inc.get("credits_burned", inc.get("calibrated_deduction_credits")),
                    "credit_burn_gbp": inc.get("credit_burn_gbp", inc.get("calibrated_deduction_gbp")),
                    "credit_burn_usd": inc.get("credit_burn_usd", inc.get("calibrated_deduction_usd")),
                    "models": inc.get("models"),
                    "start": start_dt,
                    "end": end_dt,
                    "raw_first_event": start_dt,
                    "start_iso": start_dt.isoformat(),
                    "end_iso": end_dt.isoformat(),
                    "events_count": inc.get("events_count", 1),
                    "first_exhaustion_ts": start_dt.isoformat(),
                    "last_exhaustion_ts": end_dt.isoformat(),
                    "code": inc.get("code", 429),
                    "reason": inc.get("reason", "RESOURCE_EXHAUSTED"),
                    "calibrated_deduction_credits": inc.get("credits_burned", inc.get("calibrated_deduction_credits")),
                    "calibrated_deduction_gbp": inc.get("credit_burn_gbp", inc.get("calibrated_deduction_gbp")),
                    "calibrated_deduction_usd": inc.get("credit_burn_usd", inc.get("calibrated_deduction_usd")),
                    "prepaid_pack": ledger_data.get("prepaid_pack", {}),
                    "from_ledger": True,
                })

    # 2. Extract live raw events from runtime log
    events = extract_raw_exhaustion_events(log_path)
    dated_events = [e for e in events if e.get("timestamp") is not None]

    # Filter out events already covered by known ledger intervals
    new_events = []
    for e in dated_events:
        ts = e["timestamp"]
        already_covered = any(inv["start"] <= ts <= inv["end"] for inv in intervals)
        if not already_covered:
            new_events.append(e)

    if new_events:
        new_events.sort(key=lambda e: e["timestamp"])
        clusters: List[List[Dict[str, Any]]] = []
        current_cluster: List[Dict[str, Any]] = [new_events[0]]

        for e in new_events[1:]:
            prev_dt = current_cluster[-1]["timestamp"]
            cur_dt = e["timestamp"]
            if (cur_dt - prev_dt) <= timedelta(minutes=cluster_gap_minutes):
                current_cluster.append(e)
            else:
                clusters.append(current_cluster)
                current_cluster = [e]

        if current_cluster:
            clusters.append(current_cluster)

        for cluster in clusters:
            raw_start = cluster[0]["timestamp"]
            start_dt = raw_start.replace(minute=0, second=0, microsecond=0) if round_to_hour_block else raw_start
            last_dt = cluster[-1]["timestamp"]
            end_dt = last_dt + timedelta(minutes=cooldown_padding_minutes)

            intervals.append({
                "start": start_dt,
                "end": end_dt,
                "raw_first_event": raw_start,
                "start_iso": start_dt.isoformat(),
                "end_iso": end_dt.isoformat(),
                "events_count": len(cluster),
                "first_exhaustion_ts": raw_start.isoformat(),
                "last_exhaustion_ts": last_dt.isoformat(),
                "code": 429,
                "reason": "RESOURCE_EXHAUSTED",
                "from_ledger": False,
            })

    intervals.sort(key=lambda inv: inv["start"])
    return intervals
