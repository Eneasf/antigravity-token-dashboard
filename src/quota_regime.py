"""
Quota Regime & Burn-Rate Drift Detector (Milestone 97).

Provides:
1. Automatic detection of unscheduled server-side quota flushes (`QUOTA_RESET_BONUS`)
   when `gemini_weekly_remaining` (or `claude_weekly_remaining`) jumps upward by >= 5.0%
   more than 1 hour ahead of the scheduled `weekly_reset_utc`.
2. Rolling burn-rate drift evaluation (`BURN_RATE_SHIFT` / `COUPLING_RATIO_SHIFT`)
   across `v_quota_burn_intervals` and `v_turns`, comparing observed Connect-RPC
   deductions against calibrated per-model token weights.
3. Persistent audit trail in `quota_regime_events_archive` (SQLite Vault) and
   `data/quota_regime_ledger.json`, with human-in-the-loop review states
   (`PENDING_REVIEW` -> `CONFIRMED` | `DISMISSED`).
4. Standardized 6-turn sequential `view_file` calibration probe generator for
   verifying unprobed models (`1417`, `1418`, `1419`, `1318`, `1319`, `1320`).
"""

from bisect import bisect_right
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from src.vault_schema import DEFAULT_VAULT_PATH, get_vault_connection


def _execute_sql_with_retry(
    cur: sqlite3.Cursor,
    sql: str,
    params: Tuple[Any, ...] = (),
    max_retries: int = 5,
    base_delay: float = 0.1,
) -> sqlite3.Cursor:
    """Execute SQL statement with exponential backoff on sqlite3.OperationalError (database is locked)."""
    for attempt in range(max_retries):
        try:
            return cur.execute(sql, params)
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
            else:
                raise
    return cur.execute(sql, params)


def _commit_with_retry(
    conn: sqlite3.Connection,
    max_retries: int = 5,
    base_delay: float = 0.1,
) -> None:
    """Commit connection with exponential backoff on sqlite3.OperationalError (database is locked)."""
    for attempt in range(max_retries):
        try:
            conn.commit()
            return
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))
            else:
                raise

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGIME_LEDGER_PATH = REPO_ROOT / "data" / "quota_regime_ledger.json"
DEFAULT_EXHAUSTION_LEDGER_PATH = REPO_ROOT / "data" / "exhaustion_ledger.json"

# Post-2026-10-17 Calibrated Quota Baseline Weights (USD per 1M tokens inside $25 5h / $100 weekly bucket)
CALIBRATED_QUOTA_WEIGHTS_POST_OCT17: Dict[str, Dict[str, float]] = {
    # Gemini 4 Carbon family (1427 High, 1437 Medium, 1438 Low): empirical 0.5000x of Intro API ($1.00 / $0.050 / $5.00 = $50 5h / $200 wk)
    "1427": {"prompt_uncached": 1.00, "prompt_cached": 0.05, "candidate_output": 5.00},
    "1437": {"prompt_uncached": 1.00, "prompt_cached": 0.05, "candidate_output": 5.00},
    "1438": {"prompt_uncached": 1.00, "prompt_cached": 0.05, "candidate_output": 5.00},
    # Gemini 4 Orchestrator family (1667 Carbon 0.50x planner, 1681 Argon 0.50x planner, 1669 Hydrogen 1/6x executor via exit_plan_mode; Phase 2 verified)
    "1667": {"prompt_uncached": 1.00, "prompt_cached": 0.05, "candidate_output": 5.00},
    "1681": {"prompt_uncached": 1.00, "prompt_cached": 0.05, "candidate_output": 5.00},
    "1669": {"prompt_uncached": 0.25, "prompt_cached": 0.0125, "candidate_output": 1.25},
    # Gemini 4 Argon family (1417 High, 1418 Medium, 1419 Low): empirical 0.5000x of Intro API ($1.00 / $0.050 / $5.00 = $50 5h / $200 wk)
    "1417": {"prompt_uncached": 1.00, "prompt_cached": 0.05, "candidate_output": 5.00},
    "1418": {"prompt_uncached": 1.00, "prompt_cached": 0.05, "candidate_output": 5.00},
    "1419": {"prompt_uncached": 1.00, "prompt_cached": 0.05, "candidate_output": 5.00},
    # Gemini 4 Hydrogen family (1528 XHigh, 1525 High, 1526 Medium, 1527 Low): empirical 1/6th of $1.50/$0.075/$7.50 API ($0.25 / $0.0125 / $1.25 = $150 5h / $600 wk)
    "1528": {"prompt_uncached": 0.25, "prompt_cached": 0.0125, "candidate_output": 1.25},
    "1525": {"prompt_uncached": 0.25, "prompt_cached": 0.0125, "candidate_output": 1.25},
    "1526": {"prompt_uncached": 0.25, "prompt_cached": 0.0125, "candidate_output": 1.25},
    "1527": {"prompt_uncached": 0.25, "prompt_cached": 0.0125, "candidate_output": 1.25},
    # Gemini 3.8 Flash family (1318 High, 1319 Medium, 1320 Low, 1322 Fast): 1/6th of API rate
    "1318": {"prompt_uncached": 0.125, "prompt_cached": 0.0125, "candidate_output": 0.625},
    "1319": {"prompt_uncached": 0.125, "prompt_cached": 0.0125, "candidate_output": 0.625},
    "1320": {"prompt_uncached": 0.125, "prompt_cached": 0.0125, "candidate_output": 0.625},
    "1322": {"prompt_uncached": 0.125, "prompt_cached": 0.0125, "candidate_output": 0.625},
}

# Pre-2026-10-17 Quota Baseline Weights (Oct 13-16 initial Argon launch where cached was $0.10/1M)
CALIBRATED_QUOTA_WEIGHTS_PRE_OCT17: Dict[str, Dict[str, float]] = {
    "1427": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1437": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1438": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1667": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1681": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1669": {"prompt_uncached": 1.50, "prompt_cached": 0.075, "candidate_output": 7.50},
    "1417": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1418": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1419": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1528": {"prompt_uncached": 1.50, "prompt_cached": 0.075, "candidate_output": 7.50},
    "1525": {"prompt_uncached": 1.50, "prompt_cached": 0.075, "candidate_output": 7.50},
    "1526": {"prompt_uncached": 1.50, "prompt_cached": 0.075, "candidate_output": 7.50},
    "1527": {"prompt_uncached": 1.50, "prompt_cached": 0.075, "candidate_output": 7.50},
    "1318": {"prompt_uncached": 0.125, "prompt_cached": 0.0125, "candidate_output": 0.625},
    "1319": {"prompt_uncached": 0.125, "prompt_cached": 0.0125, "candidate_output": 0.625},
    "1320": {"prompt_uncached": 0.125, "prompt_cached": 0.0125, "candidate_output": 0.625},
    "1322": {"prompt_uncached": 0.125, "prompt_cached": 0.0125, "candidate_output": 0.625},
}

# Public API Rate Card Benchmark (USD per 1M tokens)
PUBLIC_API_RATES: Dict[str, Dict[str, float]] = {
    "1427": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1437": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1438": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1667": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1681": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1669": {"prompt_uncached": 1.50, "prompt_cached": 0.075, "candidate_output": 7.50},
    "1417": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1418": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1419": {"prompt_uncached": 2.00, "prompt_cached": 0.10, "candidate_output": 10.00},
    "1528": {"prompt_uncached": 1.50, "prompt_cached": 0.075, "candidate_output": 7.50},
    "1525": {"prompt_uncached": 1.50, "prompt_cached": 0.075, "candidate_output": 7.50},
    "1526": {"prompt_uncached": 1.50, "prompt_cached": 0.075, "candidate_output": 7.50},
    "1527": {"prompt_uncached": 1.50, "prompt_cached": 0.075, "candidate_output": 7.50},
    "1318": {"prompt_uncached": 0.75, "prompt_cached": 0.075, "candidate_output": 3.75},
    "1319": {"prompt_uncached": 0.75, "prompt_cached": 0.075, "candidate_output": 3.75},
    "1320": {"prompt_uncached": 0.75, "prompt_cached": 0.075, "candidate_output": 3.75},
    "1322": {"prompt_uncached": 0.75, "prompt_cached": 0.075, "candidate_output": 3.75},
}

MODEL_LABELS: Dict[str, str] = {
    "1427": "Gemini 4 Carbon (High)",
    "1437": "Gemini 4 Carbon (Medium)",
    "1438": "Gemini 4 Carbon (Low)",
    "1667": "Orchestrator (Carbon)",
    "1681": "Orchestrator (Argon)",
    "1669": "Orchestrator Executor (Hydrogen)",
    "1417": "Gemini 4 Argon (High)",
    "1418": "Gemini 4 Argon (Medium)",
    "1419": "Gemini 4 Argon (Low)",
    "1528": "Gemini 4 Hydrogen (XHigh)",
    "1525": "Gemini 4 Hydrogen (High)",
    "1526": "Gemini 4 Hydrogen (Medium)",
    "1527": "Gemini 4 Hydrogen (Low)",
    "1318": "Gemini 3.8 Flash (High)",
    "1319": "Gemini 3.8 Flash (Medium)",
    "1320": "Gemini 3.8 Flash (Low)",
    "1322": "Gemini Fast Agent Assistant",
}


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _parse_iso(ts_str: Optional[str]) -> Optional[datetime]:
    if not ts_str or not isinstance(ts_str, str):
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return None


def compute_turn_quota_usd(
    model_id: str,
    uncached: int,
    cached: int,
    output: int,
    weights_map: Optional[Dict[str, Dict[str, float]]] = None,
) -> float:
    w_map = weights_map or CALIBRATED_QUOTA_WEIGHTS_POST_OCT17
    rates = w_map.get(str(model_id), {"prompt_uncached": 0.75, "prompt_cached": 0.075, "candidate_output": 3.75})
    return (
        (uncached or 0) * rates["prompt_uncached"]
        + (cached or 0) * rates["prompt_cached"]
        + (output or 0) * rates["candidate_output"]
    ) / 1e6


def check_early_weekly_reset_bonus(
    prev_snapshot: Optional[Dict[str, Any]],
    curr_snapshot: Dict[str, Any],
    weekly_capacity_usd: float = 100.0,
    usd_to_gbp: float = 0.79,
) -> Optional[Dict[str, Any]]:
    """
    Detect if an unscheduled early weekly quota flush (`QUOTA_RESET_BONUS`) occurred
    between `prev_snapshot` and `curr_snapshot`.

    Triggers strictly when:
    1. `prev_weekly_rem` <= 0.95 (>= 5.0% used) and `curr_weekly_rem - prev_weekly_rem` >= 0.05.
    2. `curr_timestamp` is more than 1 hour (3600s) BEFORE `prev_weekly_reset_utc`.
    """
    if not prev_snapshot or not curr_snapshot:
        return None

    prev_rem = prev_snapshot.get("gemini_weekly_remaining")
    curr_rem = curr_snapshot.get("gemini_weekly_remaining")
    prev_reset_str = prev_snapshot.get("gemini_weekly_reset_utc")
    curr_ts_str = curr_snapshot.get("timestamp_utc")

    if prev_rem is None or curr_rem is None or not prev_reset_str or not curr_ts_str:
        return None

    prev_rem_f = float(prev_rem)
    curr_rem_f = float(curr_rem)
    jump_frac = curr_rem_f - prev_rem_f
    if prev_rem_f > 0.95 or jump_frac < 0.05:
        return None

    prev_reset_dt = _parse_iso(prev_reset_str)
    curr_dt = _parse_iso(curr_ts_str)
    if not prev_reset_dt or not curr_dt:
        return None

    seconds_before_scheduled = (prev_reset_dt - curr_dt).total_seconds()
    if seconds_before_scheduled <= 3600.0:
        return None

    pct_forgiven = round(jump_frac * 100.0, 1)
    val_usd = round(pct_forgiven * (weekly_capacity_usd / 100.0), 2)
    val_gbp = round(val_usd * usd_to_gbp, 2)
    credits_forgiven = int(round(val_usd * 100))
    date_slug = curr_dt.strftime("%Y%m%d")
    event_id = f"exc-{date_slug}-01"

    prev_id = prev_snapshot.get("id")
    curr_id = curr_snapshot.get("id")
    snap_range = f"#{prev_id} -> #{curr_id}" if (prev_id is not None and curr_id is not None) else ""
    prev_5h_rem = prev_snapshot.get("gemini_5h_remaining")
    curr_5h_rem = curr_snapshot.get("gemini_5h_remaining")
    pre_reset_5h_rem_pct = round(float(prev_5h_rem) * 100.0, 2) if prev_5h_rem is not None else 100.0
    post_reset_5h_rem_pct = round(float(curr_5h_rem) * 100.0, 2) if curr_5h_rem is not None else 100.0
    delta_5h_pct = (
        round((float(curr_5h_rem) - float(prev_5h_rem)) * 100.0, 2)
        if (prev_5h_rem is not None and curr_5h_rem is not None)
        else 0.0
    )
    turns_analyzed = int(curr_snapshot.get("turns_analyzed") or prev_snapshot.get("turns_analyzed") or 0)

    return {
        "id": event_id,
        "event_id": f"reg-{date_slug}-bonus",
        "timestamp_iso": curr_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prev_timestamp_utc": prev_snapshot.get("timestamp_utc") or "",
        "hour_bucket": curr_dt.strftime("%Y-%m-%dT%H:00:00Z"),
        "snapshot_range": snap_range,
        "turns_analyzed": turns_analyzed,
        "pre_reset_5h_rem_pct": pre_reset_5h_rem_pct,
        "post_reset_5h_rem_pct": post_reset_5h_rem_pct,
        "delta_5h_pct": delta_5h_pct,
        "code": 200,
        "reason": "QUOTA_RESET_BONUS",
        "event_type": "QUOTA_RESET_BONUS",
        "level": "I",
        "credits_burned": 0,
        "bonus_pct_forgiven": pct_forgiven,
        "bonus_credits_forgiven": credits_forgiven,
        "bonus_value_usd": val_usd,
        "bonus_value_gbp": val_gbp,
        "hours_early": round(seconds_before_scheduled / 3600.0, 1),
        "prev_weekly_reset_utc": prev_reset_str,
        "new_weekly_reset_utc": curr_snapshot.get("gemini_weekly_reset_utc") or "",
        "description": (
            f"Unscheduled server-side quota flush forgave {pct_forgiven}% of Gemini Weekly quota "
            f"({credits_forgiven:,} credits / ${val_usd:.2f} / £{val_gbp:.2f} equivalent) "
            f"{seconds_before_scheduled / 86400.0:.1f} days ahead of scheduled {prev_reset_str} reset."
        ),
    }


def load_regime_ledger(ledger_path: Union[str, Path] = DEFAULT_REGIME_LEDGER_PATH) -> Dict[str, Any]:
    path = Path(ledger_path)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "events" in data:
                    return data
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "active_regime_id": "regime-20261017-post-reset",
        "active_regime_since_utc": "2026-10-17T01:46:18Z",
        "bucket_5h_usd": 25.0,
        "bucket_weekly_usd": 100.0,
        "expected_coupling_ratio": 4.0,
        "calibrated_weights_per_1m": CALIBRATED_QUOTA_WEIGHTS_POST_OCT17,
        "events": [],
    }


def sync_regime_events_to_vault_and_ledger(
    events: List[Dict[str, Any]],
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    ledger_path: Union[str, Path] = DEFAULT_REGIME_LEDGER_PATH,
    overwrite_status: bool = False,
) -> None:
    """Persist regime events into both `quota_regime_events_archive` and `quota_regime_ledger.json`."""
    ledger = load_regime_ledger(ledger_path)
    prev_events_json = json.dumps(ledger.get("events", []), sort_keys=True)
    by_id = {e["event_id"]: e for e in ledger.get("events", []) if isinstance(e, dict) and "event_id" in e}

    for ev in events:
        eid = ev["event_id"]
        if eid in by_id and not overwrite_status:
            # Preserve confirmed/dismissed events in full so background exports do not dirty quota_regime_ledger.json
            existing = by_id[eid]
            if existing.get("review_status") in ("CONFIRMED", "DISMISSED"):
                by_id[eid] = existing
                continue
        by_id[eid] = ev

    prev_weights = ledger.get("calibrated_weights_per_1m")
    ledger["calibrated_weights_per_1m"] = CALIBRATED_QUOTA_WEIGHTS_POST_OCT17
    ledger["events"] = sorted(by_id.values(), key=lambda x: x.get("detected_at_utc", ""))
    new_events_json = json.dumps(ledger["events"], sort_keys=True)
    events_hash = hashlib.sha256(new_events_json.encode("utf-8")).hexdigest()[:24]

    ledger_file = Path(ledger_path)
    weights_changed = prev_weights != CALIBRATED_QUOTA_WEIGHTS_POST_OCT17
    if not ledger_file.exists() or prev_events_json != new_events_json or weights_changed or overwrite_status:
        _atomic_write_json(ledger_file, ledger)

    conn = None
    try:
        conn = get_vault_connection(vault_path, busy_timeout=60000)
        cur = conn.cursor()
        if not overwrite_status:
            try:
                cur.execute("SELECT value FROM vault_sync_state WHERE key = 'quota_regime:events_hash'")
                h_row = cur.fetchone()
                cur.execute("SELECT COUNT(*) FROM quota_regime_events_archive")
                cnt_row = cur.fetchone()
                if h_row and h_row[0] == events_hash and cnt_row and cnt_row[0] == len(ledger["events"]):
                    return
            except sqlite3.Error:
                pass

        for ev in ledger["events"]:
            _execute_sql_with_retry(
                cur,
                """
                INSERT OR REPLACE INTO quota_regime_events_archive (
                    event_id, detected_at_utc, event_type, review_status, confirmed_at_utc,
                    snapshot_range, turns_analyzed, delta_5h_pct, delta_weekly_pct,
                    drift_ratio, coupling_ratio, solved_5h_api_usd, solved_weekly_api_usd,
                    summary, prev_baseline_json, observed_metrics_json, model_breakdown_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ev.get("event_id"),
                    ev.get("detected_at_utc"),
                    ev.get("event_type"),
                    ev.get("review_status", "PENDING_REVIEW"),
                    ev.get("confirmed_at_utc"),
                    ev.get("snapshot_range", ""),
                    int(ev.get("turns_analyzed", 0)),
                    float(ev.get("delta_5h_pct", 0.0)),
                    float(ev.get("delta_weekly_pct", 0.0)),
                    float(ev.get("drift_ratio", 1.0)),
                    float(ev.get("coupling_ratio", 4.0)),
                    float(ev.get("solved_5h_api_usd", 25.0)),
                    float(ev.get("solved_weekly_api_usd", 100.0)),
                    ev.get("summary", ""),
                    json.dumps(ev.get("prev_baseline", {})),
                    json.dumps(ev.get("observed_metrics", {})),
                    json.dumps(ev.get("model_breakdown", {})),
                ),
            )
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            _execute_sql_with_retry(
                cur,
                """
                INSERT INTO vault_sync_state (key, value, updated_at)
                VALUES ('quota_regime:events_hash', ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (events_hash, now_iso),
            )
        except sqlite3.Error:
            pass
        _commit_with_retry(conn)
    except (sqlite3.Error, OSError) as exc:
        logger.warning("Failed syncing regime events to vault: %s", exc)
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass


def evaluate_vault_quota_regime(
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    ledger_path: Union[str, Path] = DEFAULT_REGIME_LEDGER_PATH,
    persist: bool = True,
    extra_live_turns: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Evaluate historical and current post-reset quota intervals in `antigravity_vault.db`,
    computing:
    1. Current regime status (`NOMINAL`, `DISCOUNT_PROMO`, `BURN_SURGE`, or `PENDING_REVIEW`).
    2. Rolling 5-interval burn multiplier vs. calibrated baseline and vs. public API rates.
    3. Per-model verification coverage in the active regime (`1417`, `1418`, `1419`, `1318`, `1319`, `1320`, `1322`).
    4. Historical regime events (`reg-20261013-argon-launch`, `reg-20261017-bonus`, `reg-20261017-kv-discount`).
    """
    vault_file = Path(vault_path)
    ledger = load_regime_ledger(ledger_path)
    existing_by_id = {e["event_id"]: e for e in ledger.get("events", []) if isinstance(e, dict) and "event_id" in e}

    if not vault_file.exists():
        return {
            "status": "NOMINAL",
            "drift_ratio": 1.0,
            "coupling_ratio_5h_to_weekly": 4.0,
            "pending_review_count": 0,
            "events": ledger.get("events", []),
            "model_coverage": {},
        }

    conn = None
    try:
        conn = sqlite3.connect(f"file:{vault_file}?mode=ro", uri=True, timeout=10.0)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quota_snapshots_archive'")
        if not cur.fetchone():
            return {
                "status": "NOMINAL",
                "drift_ratio": 1.0,
                "coupling_ratio_5h_to_weekly": 4.0,
                "pending_review_count": 0,
                "events": ledger.get("events", []),
                "model_coverage": {},
            }

        snaps = [dict(r) for r in cur.execute("SELECT * FROM quota_snapshots_archive ORDER BY timestamp_utc ASC, id ASC")]
        cur.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='v_turns'")
        has_v_turns = bool(cur.fetchone())
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='steps_archive'")
        has_steps = bool(cur.fetchone())
        if has_v_turns and has_steps:
            vault_turns = [
                dict(r)
                for r in cur.execute(
                    """
                    SELECT convo_id, step_idx, timestamp, model_id, model_name,
                           prompt_tokens_uncached, cached_tokens, output_tokens_total, thinking_tokens
                    FROM v_turns
                    WHERE timestamp >= '2026-10-13T00:00:00Z'
                    UNION ALL
                    SELECT convo_id, step_idx, timestamp, model_id, model_name,
                           prompt_tokens_uncached, cached_tokens, output_tokens_total, thinking_tokens
                    FROM steps_archive
                    WHERE step_type = 23
                      AND COALESCE(prompt_tokens_uncached, 0) + COALESCE(cached_tokens, 0) + COALESCE(output_tokens_total, 0) > 0
                      AND timestamp >= '2026-10-13T00:00:00Z'
                    ORDER BY timestamp ASC
                    """
                )
            ]
        elif has_steps:
            vault_turns = [
                dict(r)
                for r in cur.execute(
                    """
                    SELECT convo_id, step_idx, timestamp, model_id, model_name,
                           prompt_tokens_uncached, cached_tokens, output_tokens_total, thinking_tokens
                    FROM steps_archive
                    WHERE step_type IN (15, 23)
                      AND (
                          step_type = 15
                          OR COALESCE(prompt_tokens_uncached, 0) + COALESCE(cached_tokens, 0) + COALESCE(output_tokens_total, 0) > 0
                      )
                      AND timestamp >= '2026-10-13T00:00:00Z'
                    ORDER BY timestamp ASC
                    """
                )
            ]
        else:
            vault_turns = [
                dict(r)
                for r in cur.execute(
                    """
                    SELECT convo_id, step_idx, timestamp, model_id, model_name,
                           prompt_tokens_uncached, cached_tokens, output_tokens_total, thinking_tokens
                    FROM v_turns
                    WHERE timestamp >= '2026-10-13T00:00:00Z'
                    ORDER BY timestamp ASC
                    """
                )
            ]
    except (sqlite3.Error, OSError) as exc:
        logger.warning("Failed reading vault for quota regime evaluation: %s", exc)
        return {
            "status": "NOMINAL",
            "drift_ratio": 1.0,
            "coupling_ratio_5h_to_weekly": 4.0,
            "pending_review_count": 0,
            "events": ledger.get("events", []),
            "model_coverage": {},
        }
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass

    # Merge any live turns not yet flushed to steps_archive
    seen_keys = {(t.get("convo_id"), t.get("step_idx"), t.get("timestamp")) for t in vault_turns}
    all_turns = list(vault_turns)
    if extra_live_turns:
        for lt in extra_live_turns:
            ts = lt.get("timestamp", "")
            if ts >= "2026-10-13T00:00:00Z":
                k = (lt.get("convo_id"), lt.get("step_idx"), ts)
                if k not in seen_keys:
                    seen_keys.add(k)
                    all_turns.append(lt)
    all_turns.sort(key=lambda x: x.get("timestamp", ""))
    turn_timestamps = [t.get("timestamp", "") for t in all_turns]

    # 1. Scan snapshots for early weekly reset bonuses and active step-down intervals
    early_resets: List[Dict[str, Any]] = []
    intervals: List[Dict[str, Any]] = []

    for i in range(1, len(snaps)):
        s0, s1 = snaps[i - 1], snaps[i]
        bonus = check_early_weekly_reset_bonus(s0, s1)
        if bonus:
            early_resets.append(bonus)

        r5_0, r5_1 = s0.get("gemini_5h_remaining"), s1.get("gemini_5h_remaining")
        rw_0, rw_1 = s0.get("gemini_weekly_remaining"), s1.get("gemini_weekly_remaining")
        if r5_0 is None or r5_1 is None or rw_0 is None or rw_1 is None:
            continue

        du5 = float(r5_0) - float(r5_1)
        duw = float(rw_0) - float(rw_1)
        # Skip intervals where 5h or weekly reset upward or barely moved
        if du5 <= 0.0005 or duw <= 0.0001:
            continue

        t0_str, t1_str = s0["timestamp_utc"], s1["timestamp_utc"]
        lo = bisect_right(turn_timestamps, t0_str)
        hi = bisect_right(turn_timestamps, t1_str)
        sub_turns = all_turns[lo:hi]
        if not sub_turns:
            continue

        cal_post_usd = 0.0
        cal_pre_usd = 0.0
        api_usd = 0.0
        for t in sub_turns:
            mid_val = t.get("model_id", "")
            unc_val = t.get("prompt_tokens_uncached", 0) or 0
            cac_val = t.get("cached_tokens", 0) or 0
            out_val = t.get("output_tokens_total", 0) or 0
            cal_post_usd += compute_turn_quota_usd(
                mid_val, unc_val, cac_val, out_val, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17
            )
            cal_pre_usd += compute_turn_quota_usd(
                mid_val, unc_val, cac_val, out_val, CALIBRATED_QUOTA_WEIGHTS_PRE_OCT17
            )
            api_usd += compute_turn_quota_usd(
                mid_val, unc_val, cac_val, out_val, PUBLIC_API_RATES
            )

        intervals.append({
            "start_id": s0["id"],
            "end_id": s1["id"],
            "start_utc": t0_str,
            "end_utc": t1_str,
            "du5_frac": du5,
            "duw_frac": duw,
            "du5_pct": round(du5 * 100.0, 4),
            "duw_pct": round(duw * 100.0, 4),
            "coupling_ratio": round(du5 / duw, 4) if duw > 0 else 4.0,
            "turns": sub_turns,
            "turns_count": len(sub_turns),
            "cal_post_usd": cal_post_usd,
            "cal_pre_usd": cal_pre_usd,
            "api_usd": api_usd,
        })

    # Partition intervals around the Oct 17 Argon KV-discount transition (first early reset),
    # keeping subsequent weekly reset bonuses inside the active post-Oct-17 regime.
    regime_cutoff_utc = early_resets[0]["timestamp_iso"] if early_resets else "2026-10-17T01:46:18Z"
    pre_intervals = [iv for iv in intervals if iv["end_utc"] < regime_cutoff_utc]
    post_intervals = [iv for iv in intervals if iv["end_utc"] >= regime_cutoff_utc]

    # Compute per-model coverage in the post-reset regime
    model_coverage: Dict[str, Dict[str, Any]] = {}
    for mid, label in MODEL_LABELS.items():
        model_coverage[mid] = {
            "model_id": mid,
            "model_name": label,
            "turns": 0,
            "uncached_tokens": 0,
            "cached_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "api_cost_usd": 0.0,
            "calibrated_quota_usd": 0.0,
            "expected_5h_pct": 0.0,
            "verified": False,
        }

    for iv in post_intervals:
        for t in iv["turns"]:
            mid = str(t.get("model_id", ""))
            if mid not in model_coverage:
                continue
            mc = model_coverage[mid]
            unc = int(t.get("prompt_tokens_uncached", 0) or 0)
            cac = int(t.get("cached_tokens", 0) or 0)
            out = int(t.get("output_tokens_total", 0) or 0)
            thk = int(t.get("thinking_tokens", 0) or 0)
            mc["turns"] += 1
            mc["uncached_tokens"] += unc
            mc["cached_tokens"] += cac
            mc["output_tokens"] += out
            mc["thinking_tokens"] += thk
            api_c = compute_turn_quota_usd(mid, unc, cac, out, PUBLIC_API_RATES)
            cal_c = compute_turn_quota_usd(mid, unc, cac, out, CALIBRATED_QUOTA_WEIGHTS_POST_OCT17)
            mc["api_cost_usd"] = round(mc["api_cost_usd"] + api_c, 4)
            mc["calibrated_quota_usd"] = round(mc["calibrated_quota_usd"] + cal_c, 4)
            mc["expected_5h_pct"] = round(mc["calibrated_quota_usd"] / 25.0 * 100.0, 4)
            mc["verified"] = mc["turns"] >= 5

    # Rolling 5-interval metrics in active regime
    recent_ivs = post_intervals[-5:] if len(post_intervals) >= 5 else post_intervals
    sum_du5_frac = sum(iv["du5_frac"] for iv in recent_ivs)
    sum_duw_frac = sum(iv["duw_frac"] for iv in recent_ivs)
    sum_cal_post_usd = sum(iv["cal_post_usd"] for iv in recent_ivs)
    sum_api_usd = sum(iv["api_usd"] for iv in recent_ivs)

    expected_du5_frac = sum_cal_post_usd / 25.0 if sum_cal_post_usd > 0 else 0.0
    drift_ratio = round(sum_du5_frac / expected_du5_frac, 3) if expected_du5_frac > 0.0005 else 1.0
    coupling_ratio = round(sum_du5_frac / sum_duw_frac, 4) if sum_duw_frac > 0.0001 else 4.0
    solved_5h_api_usd = round(sum_api_usd / sum_du5_frac, 2) if sum_du5_frac > 0.0005 else 25.0

    # Full post-reset totals
    tot_post_du5_frac = sum(iv["du5_frac"] for iv in post_intervals)
    tot_post_duw_frac = sum(iv["duw_frac"] for iv in post_intervals)
    tot_post_pre_usd = sum(iv["cal_pre_usd"] for iv in post_intervals)
    tot_post_post_usd = sum(iv["cal_post_usd"] for iv in post_intervals)
    tot_post_api_usd = sum(iv["api_usd"] for iv in post_intervals)
    tot_post_turns = sum(iv["turns_count"] for iv in post_intervals)

    # Construct historical & active regime events
    events_list: List[Dict[str, Any]] = []

    # Event 1: Pre-reset Oct 13-16 Argon Launch Baseline
    if pre_intervals:
        pre_du5 = sum(iv["du5_frac"] for iv in pre_intervals)
        pre_duw = sum(iv["duw_frac"] for iv in pre_intervals)
        pre_api = sum(iv["api_usd"] for iv in pre_intervals)
        pre_cal = sum(iv["cal_pre_usd"] for iv in pre_intervals)
        pre_turns = sum(iv["turns_count"] for iv in pre_intervals)
        events_list.append({
            "event_id": "reg-20261013-argon-launch",
            "detected_at_utc": pre_intervals[0]["start_utc"],
            "event_type": "BASELINE_ESTABLISHED",
            "review_status": existing_by_id.get("reg-20261013-argon-launch", {}).get("review_status", "CONFIRMED"),
            "confirmed_at_utc": existing_by_id.get("reg-20261013-argon-launch", {}).get("confirmed_at_utc", "2026-10-14T18:00:00Z"),
            "snapshot_range": f"#{pre_intervals[0]['start_id']} -> #{pre_intervals[-1]['end_id']}",
            "turns_analyzed": pre_turns,
            "delta_5h_pct": round(pre_du5 * 100.0, 2),
            "delta_weekly_pct": round(pre_duw * 100.0, 2),
            "drift_ratio": round(pre_du5 / (pre_cal / 25.0), 3) if pre_cal > 0 else 1.0,
            "coupling_ratio": round(pre_du5 / pre_duw, 4) if pre_duw > 0 else 4.0,
            "solved_5h_api_usd": round(pre_api / pre_du5, 2) if pre_du5 > 0 else 25.0,
            "solved_weekly_api_usd": round(pre_api / pre_duw, 2) if pre_duw > 0 else 100.0,
            "summary": (
                "Initial Gemini 4 Argon (1417-1419) & Ultra 5x calibration ($25 5h / $100 weekly at 4.0000x ratio; "
                "Argon billed at $2.00 / $0.10 / $10.00 per 1M; Flash 3.8 at 1/6x API weight)."
            ),
            "prev_baseline": {"gemini_5h_usd": 100.0, "gemini_weekly_usd": 645.0},
            "observed_metrics": {
                "gemini_5h_usd": 25.0,
                "gemini_weekly_usd": 100.0,
                "argon_rates_per_1m": {"uncached": 2.0, "cached": 0.10, "output": 10.0},
                "flash_quota_weight_vs_api": 0.167,
            },
            "model_breakdown": {},
        })

    # Event 2: Early Weekly Quota Reset Bonus(es)
    for idx, br in enumerate(early_resets):
        eid = br["event_id"]
        curr_ts = br["timestamp_iso"]
        cycle_start_ts = ""
        prev_reset_dt = _parse_iso(br.get("prev_weekly_reset_utc"))
        if prev_reset_dt is not None:
            cycle_start_ts = (prev_reset_dt - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        if idx > 0:
            prev_bonus_ts = early_resets[idx - 1]["timestamp_iso"]
            if prev_bonus_ts > cycle_start_ts:
                cycle_start_ts = prev_bonus_ts
        lo_turns = bisect_right(turn_timestamps, cycle_start_ts) if cycle_start_ts else 0
        hi_turns = bisect_right(turn_timestamps, curr_ts)
        turns_before_reset = max(0, hi_turns - lo_turns)
        turns_cnt = int(br.get("turns_analyzed") or turns_before_reset)
        events_list.append({
            "event_id": eid,
            "detected_at_utc": br["timestamp_iso"],
            "event_type": "QUOTA_RESET_BONUS",
            "review_status": existing_by_id.get(eid, {}).get("review_status", "CONFIRMED"),
            "confirmed_at_utc": existing_by_id.get(eid, {}).get("confirmed_at_utc", br["timestamp_iso"]),
            "snapshot_range": br.get("snapshot_range") or "",
            "turns_analyzed": turns_cnt,
            "delta_5h_pct": br.get("delta_5h_pct", 0.0),
            "delta_weekly_pct": -br["bonus_pct_forgiven"],
            "drift_ratio": 0.0,
            "coupling_ratio": 4.0,
            "solved_5h_api_usd": 25.0,
            "solved_weekly_api_usd": 100.0,
            "summary": br["description"],
            "prev_baseline": {"prev_weekly_reset_utc": br["prev_weekly_reset_utc"]},
            "observed_metrics": {
                "bonus_pct_forgiven": br["bonus_pct_forgiven"],
                "bonus_credits_forgiven": br["bonus_credits_forgiven"],
                "bonus_value_usd": br["bonus_value_usd"],
                "bonus_value_gbp": br["bonus_value_gbp"],
                "pre_reset_5h_rem_pct": br.get("pre_reset_5h_rem_pct", 100.0),
                "post_reset_5h_rem_pct": br.get("post_reset_5h_rem_pct", 100.0),
                "new_weekly_reset_utc": br["new_weekly_reset_utc"],
            },
            "model_breakdown": {},
        })

    # Event 3: Post-Reset Oct 17 Argon KV-Cache Discount Regime Shift
    if post_intervals and tot_post_du5_frac > 0.005:
        drift_vs_pre_oct17 = round(tot_post_du5_frac / (tot_post_pre_usd / 25.0), 3) if tot_post_pre_usd > 0 else 1.0
        drift_vs_post_oct17 = round(tot_post_du5_frac / (tot_post_post_usd / 25.0), 3) if tot_post_post_usd > 0 else 1.0
        eid_shift = "reg-20261017-kv-discount"
        events_list.append({
            "event_id": eid_shift,
            "detected_at_utc": post_intervals[0]["end_utc"],
            "event_type": "BURN_RATE_SHIFT",
            "review_status": existing_by_id.get(eid_shift, {}).get("review_status", "CONFIRMED"),
            "confirmed_at_utc": existing_by_id.get(eid_shift, {}).get("confirmed_at_utc", "2026-10-17T13:35:00Z"),
            "snapshot_range": f"#{post_intervals[0]['start_id']} -> #{post_intervals[-1]['end_id']}",
            "turns_analyzed": tot_post_turns,
            "delta_5h_pct": round(tot_post_du5_frac * 100.0, 2),
            "delta_weekly_pct": round(tot_post_duw_frac * 100.0, 2),
            "drift_ratio": drift_vs_pre_oct17,
            "coupling_ratio": round(tot_post_du5_frac / tot_post_duw_frac, 4) if tot_post_duw_frac > 0 else 4.0,
            "solved_5h_api_usd": round(tot_post_api_usd / tot_post_du5_frac, 2),
            "solved_weekly_api_usd": round(tot_post_api_usd / tot_post_duw_frac, 2) if tot_post_duw_frac > 0 else 100.0,
            "summary": (
                f"Post-reset Gemini 4 (Argon 1417-1419 & Carbon 1427/1437/1438) quota weights halved to 0.5000x of Intro API "
                f"($1.00 / $0.050 / $5.00 per 1M = $50 5h / $200 weekly; overall {drift_vs_pre_oct17:.2f}x burn vs pre-Oct-17 baseline, "
                f"{drift_vs_post_oct17:.2f}x vs calibrated weights across {tot_post_turns} turns); Flash 3.8 at 1/6x API rate."
            ),
            "prev_baseline": {
                "argon_rates_per_1m": {"uncached": 2.0, "cached": 0.10, "output": 10.0},
                "expected_weekly_pct": round(tot_post_pre_usd, 2),
            },
            "observed_metrics": {
                "argon_calibrated_rates_per_1m": {"uncached": 1.00, "cached": 0.05, "output": 5.00},
                "carbon_calibrated_rates_per_1m": {"uncached": 1.00, "cached": 0.05, "output": 5.00},
                "flash_calibrated_rates_per_1m": {"uncached": 0.125, "cached": 0.0125, "output": 0.625},
                "drift_vs_pre_oct17": drift_vs_pre_oct17,
                "drift_vs_calibrated_post_oct17": drift_vs_post_oct17,
                "predicted_weekly_pct": round(tot_post_post_usd, 4),
                "observed_weekly_pct": round(tot_post_duw_frac * 100.0, 4),
            },
            "model_breakdown": {
                mid: {
                    "turns": mc["turns"],
                    "expected_5h_pct": mc["expected_5h_pct"],
                    "api_cost_usd": mc["api_cost_usd"],
                    "verified": mc["verified"],
                }
                for mid, mc in model_coverage.items()
                if mc["turns"] > 0
            },
        })

    # Dynamic Future Drift Detector: if rolling 5-interval drift_ratio against POST-OCT17 weights
    # deviates outside [0.80, 1.20] with at least 1.5% 5h burn, open a new PENDING_REVIEW event!
    if sum_du5_frac >= 0.015 and (drift_ratio < 0.80 or drift_ratio > 1.20):
        latest_ts = recent_ivs[-1]["end_utc"]
        date_slug = latest_ts[:10].replace("-", "")
        dyn_id = f"reg-{date_slug}-drift"
        direction = "DISCOUNT_PROMO" if drift_ratio < 0.80 else "BURN_SURGE"
        events_list.append({
            "event_id": dyn_id,
            "detected_at_utc": latest_ts,
            "event_type": f"BURN_RATE_SHIFT ({direction})",
            "review_status": existing_by_id.get(dyn_id, {}).get("review_status", "PENDING_REVIEW"),
            "confirmed_at_utc": existing_by_id.get(dyn_id, {}).get("confirmed_at_utc"),
            "snapshot_range": f"#{recent_ivs[0]['start_id']} -> #{recent_ivs[-1]['end_id']}",
            "turns_analyzed": sum(iv["turns_count"] for iv in recent_ivs),
            "delta_5h_pct": round(sum_du5_frac * 100.0, 2),
            "delta_weekly_pct": round(sum_duw_frac * 100.0, 2),
            "drift_ratio": drift_ratio,
            "coupling_ratio": coupling_ratio,
            "solved_5h_api_usd": solved_5h_api_usd,
            "solved_weekly_api_usd": round(solved_5h_api_usd * coupling_ratio, 2),
            "summary": (
                f"Rolling 5-interval burn rate drifted to {drift_ratio:.2f}x of calibrated post-Oct-17 baseline "
                f"(solved 5h API capacity: ${solved_5h_api_usd:.2f}). Run `scripts/quota_regression.py --review`."
            ),
            "prev_baseline": CALIBRATED_QUOTA_WEIGHTS_POST_OCT17,
            "observed_metrics": {
                "drift_ratio": drift_ratio,
                "solved_5h_api_usd": solved_5h_api_usd,
                "coupling_ratio": coupling_ratio,
            },
            "model_breakdown": {},
        })

    merged_by_id: Dict[str, Dict[str, Any]] = dict(existing_by_id)
    for ev in events_list:
        eid = ev["event_id"]
        existing = merged_by_id.get(eid)
        if existing and existing.get("review_status") in ("CONFIRMED", "DISMISSED"):
            merged_by_id[eid] = existing
        else:
            merged_by_id[eid] = ev
    merged_events = sorted(merged_by_id.values(), key=lambda x: x.get("detected_at_utc", ""))

    if persist:
        sync_regime_events_to_vault_and_ledger(events_list, vault_path=vault_file, ledger_path=ledger_path)

    pending_events = [e for e in merged_events if e.get("review_status") == "PENDING_REVIEW"]
    if pending_events:
        regime_status = "PENDING_REVIEW"
    elif drift_ratio < 0.80:
        regime_status = "DISCOUNT_PROMO"
    elif drift_ratio > 1.20:
        regime_status = "BURN_SURGE"
    else:
        regime_status = "NOMINAL"

    return {
        "status": regime_status,
        "active_regime_id": ledger.get("active_regime_id", "regime-20261017-post-reset"),
        "active_regime_since_utc": regime_cutoff_utc,
        "latest_reset_bonus_utc": early_resets[-1]["timestamp_iso"] if early_resets else None,
        "drift_ratio": drift_ratio,
        "coupling_ratio_5h_to_weekly": coupling_ratio,
        "effective_5h_api_capacity_usd": solved_5h_api_usd,
        "effective_weekly_api_capacity_usd": round(solved_5h_api_usd * coupling_ratio, 2),
        "post_reset_turns_analyzed": tot_post_turns,
        "post_reset_5h_burn_pct": round(tot_post_du5_frac * 100.0, 2),
        "post_reset_weekly_burn_pct": round(tot_post_duw_frac * 100.0, 2),
        "predicted_weekly_burn_pct": round(tot_post_post_usd, 2),
        "pending_review_count": len(pending_events),
        "events": list(reversed(merged_events)),
        "model_coverage": model_coverage,
    }


def update_regime_event_review_status(
    event_id: str,
    new_status: str,
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    ledger_path: Union[str, Path] = DEFAULT_REGIME_LEDGER_PATH,
) -> Optional[Dict[str, Any]]:
    """Transition a regime event in `quota_regime_ledger.json` and Vault to `CONFIRMED` or `DISMISSED`."""
    if new_status not in ("CONFIRMED", "DISMISSED", "PENDING_REVIEW"):
        raise ValueError(f"Invalid review_status: {new_status}")

    ledger = load_regime_ledger(ledger_path)
    target = None
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for ev in ledger.get("events", []):
        if ev.get("event_id") == event_id:
            ev["review_status"] = new_status
            ev["confirmed_at_utc"] = now_iso if new_status in ("CONFIRMED", "DISMISSED") else None
            target = ev
            break

    if not target:
        return None

    sync_regime_events_to_vault_and_ledger(
        ledger["events"],
        vault_path=vault_path,
        ledger_path=ledger_path,
        overwrite_status=True,
    )
    return target


def generate_calibration_probe_prompts() -> Dict[str, str]:
    """Return standardized 6-turn sequential `view_file` staircase prompts for model burn-rate verification."""
    return {
        "1427 (Gemini 4 Carbon High)": (
            "Calibration probe for Gemini 4 Carbon (High) (model 1427). Please execute exactly 6 sequential "
            "`read_file` tool calls (one file per turn, do NOT batch them in parallel, so we build a clean "
            "6-turn KV cache staircase):\n"
            "1. Read lines 1-600 of `scripts/export_dashboard.py`\n"
            "2. Read lines 601-1200 of `scripts/export_dashboard.py`\n"
            "3. Read lines 1201-1800 of `scripts/export_dashboard.py`\n"
            "4. Read lines 1-600 of `src/aggregator_windows.py`\n"
            "5. Read lines 1-600 of `src/aggregator_cycles.py`\n"
            "6. Read lines 1-400 of `docs/DATA_DICTIONARY.md`\n"
            "After the 6th `read_file` call completes, write a detailed ~800-word architectural analysis of "
            "the end-to-end telemetry pipeline and token accounting invariants. Do not run any terminal commands or subagents."
        ),
        "1437 (Gemini 4 Carbon Medium)": (
            "Calibration probe for Gemini 4 Carbon (Medium) (model 1437). Please execute exactly 6 sequential "
            "`read_file` tool calls (one file per turn, do NOT batch them in parallel, so we build a clean "
            "6-turn KV cache staircase):\n"
            "1. Read lines 1-600 of `docs/HANDOVER.md`\n"
            "2. Read lines 1-600 of `src/vault.py`\n"
            "3. Read lines 601-1200 of `src/vault.py`\n"
            "4. Read lines 1-600 of `src/horizon_analytics.py`\n"
            "5. Read lines 1-600 of `src/quota_regime.py`\n"
            "6. Read lines 1-400 of `src/aggregator_quotas.py`\n"
            "After the 6th `read_file` call completes, write a detailed ~800-word architectural synthesis of "
            "how quota snapshots, credit burn reconciliation, and weekly cycles interact. Do not run any terminal commands or subagents."
        ),
        "1438 (Gemini 4 Carbon Low)": (
            "Calibration probe for Gemini 4 Carbon (Low) (model 1438). Please execute exactly 6 sequential "
            "`read_file` tool calls (one file per turn, do NOT batch them in parallel, so we build a clean "
            "6-turn KV cache staircase):\n"
            "1. Read lines 1-600 of `src/swarm.py`\n"
            "2. Read lines 1-496 of `src/aggregator_coaching.py`\n"
            "3. Read lines 1-600 of `dashboard/js/now-burst.js`\n"
            "4. Read lines 1-600 of `dashboard/js/now.js`\n"
            "5. Read lines 1-600 of `dashboard/js/sessions.js`\n"
            "6. Read lines 1-600 of `dashboard/js/simulator.js`\n"
            "After the 6th `read_file` call completes, write a detailed ~800-word architectural overview of "
            "swarm lineage, KV-cache coaching, and frontend telemetry rendering. Do not run any terminal commands or subagents."
        ),
        "1418 (Gemini 4 Argon Medium)": (
            "Calibration probe for Gemini 4 Argon (Medium) (model 1418). Please execute exactly 6 sequential "
            "`view_file` tool calls (one file per turn, do NOT batch them in parallel, so we build a clean "
            "6-turn KV cache staircase):\n"
            "1. View lines 1-600 of `docs/HANDOVER.md`\n"
            "2. View lines 601-1200 of `docs/HANDOVER.md`\n"
            "3. View lines 1-280 of `docs/reports/COST_UTILITY_ANALYSIS_ULTRA.md`\n"
            "4. View lines 1-600 of `src/vault.py`\n"
            "5. View lines 601-1200 of `src/vault.py`\n"
            "6. View lines 1-400 of `src/aggregator_quotas.py`\n"
            "After the 6th `view_file` call completes, write a detailed ~800-word architectural synthesis of "
            "how quota snapshots, credit burn reconciliation, and weekly cycles interact. Do not run any terminal commands or subagents."
        ),
        "1417 (Gemini 4 Argon High)": (
            "Calibration probe for Gemini 4 Argon (High) (model 1417). Please execute exactly 6 sequential "
            "`view_file` tool calls (one file per turn, do NOT batch them in parallel, so we build a clean "
            "6-turn KV cache staircase):\n"
            "1. View lines 1-600 of `scripts/export_dashboard.py`\n"
            "2. View lines 601-1200 of `scripts/export_dashboard.py`\n"
            "3. View lines 1201-1800 of `scripts/export_dashboard.py`\n"
            "4. View lines 1-600 of `src/aggregator_windows.py`\n"
            "5. View lines 1-600 of `src/aggregator_cycles.py`\n"
            "6. View lines 1-400 of `docs/DATA_DICTIONARY.md`\n"
            "After the 6th `view_file` call completes, write a detailed ~800-word architectural analysis of "
            "the end-to-end telemetry pipeline and token accounting invariants. Do not run any terminal commands or subagents."
        ),
        "1528 (Gemini 4 Hydrogen XHigh Isolated Phase 2)": (
            "Calibration probe for Gemini 4 Hydrogen (XHigh) (model 1528). Ensure >=6m Connect-RPC idle gap before and after. "
            "Execute exactly 6 sequential `read_file` tool calls (one per turn, no parallel batching):\n"
            "1. Read lines 1-400 of `antigravity_telemetry/__init__.py`\n"
            "2. Read lines 1-400 of `src/quota_regime.py`\n"
            "3. Read lines 401-800 of `src/quota_regime.py`\n"
            "4. Read lines 1-400 of `src/horizon_analytics.py`\n"
            "5. Read lines 1-400 of `src/aggregator_coaching.py`\n"
            "6. Read lines 1-300 of `docs/DATA_DICTIONARY.md`\n"
            "After turn 6, compare 1528 against 1525 (1/6x quota weight) with zero terminal commands."
        ),
        "1526 (Gemini 4 Hydrogen Medium Phase 2)": (
            "Calibration probe for Gemini 4 Hydrogen (Medium) (model 1526). Execute exactly 6 sequential "
            "`read_file` calls—one file slice per turn, NO parallel batching—so we build a clean 6-turn KV cache staircase:\n"
            "1. Read lines 1-400 of `antigravity_telemetry/__init__.py`\n"
            "2. Read lines 1-400 of `src/quota_regime.py`\n"
            "3. Read lines 401-800 of `src/quota_regime.py`\n"
            "4. Read lines 1-400 of `src/horizon_analytics.py`\n"
            "5. Read lines 1-400 of `src/aggregator_coaching.py`\n"
            "6. Read lines 1-300 of `docs/DATA_DICTIONARY.md`\n"
            "After turn 6 completes, summarize in ~200 words how family classification and quota-weight mapping interact. "
            "Do not run terminal commands, file edits, or subagents."
        ),
        "1667 / 1681 (Orchestrator Carbon vs Argon Phase 2 Real Multi-Step)": (
            "Phase 2 orchestration probe for Orchestrator (Carbon 1667) and Orchestrator (Argon 1681). "
            "Verify exit_plan_mode handoff to Orchestrator Executor (Hydrogen 1669, 1/6x), enter_plan_mode return "
            "to planner 1667/1681 (0.50x), and subagent Model='inherit' vs Model='flash' (1322) inheritance."
        ),
    }
