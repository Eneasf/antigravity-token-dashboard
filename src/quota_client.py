"""
Live Antigravity Desktop Quota Client.

Connects to the local language_server Connect-RPC endpoint to retrieve ground-truth
quota summaries and remaining fractions directly from Google's backend.
"""

import json
import logging
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

from src.temporal import load_raw_pricing

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path.home() / "Library" / "Logs" / "Antigravity" / "language_server.log"
RPC_METHOD = "/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"
USER_STATUS_RPC_METHOD = "/exa.language_server_pb.LanguageServerService/GetUserStatus"


def discover_language_server_credentials(
    log_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    Discover running language_server PID, CSRF token, and HTTP port.
    Returns dict with {"pid": int, "csrf_token": str, "port": int} or None.
    """
    try:
        res = subprocess.run(
            ["ps", "-ww", "-E", "-e", "-o", "pid,command"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10.0,
        )
    except subprocess.TimeoutExpired:
        logger.debug("Subprocess timed out querying ps")
        return None
    except Exception as e:
        logger.debug(f"Failed to query ps: {e}")
        return None

    pid: Optional[int] = None
    csrf_token: Optional[str] = None

    for line in res.stdout.splitlines():
        if "language_server" in line and "--csrf_token" in line:
            m_csrf = re.search(r"--csrf_token\s+([a-f0-9-]+)", line)
            m_pid = re.match(r"^\s*(\d+)", line)
            if m_csrf and m_pid:
                csrf_token = m_csrf.group(1)
                pid = int(m_pid.group(1))
                if "--standalone" in line:
                    break

    if not pid or not csrf_token:
        return None

    # Try log file for port
    target_log = log_path or DEFAULT_LOG_PATH
    port: Optional[int] = None
    if target_log.exists():
        try:
            with open(target_log, "r", errors="ignore") as f:
                for line in f:
                    m_port = re.search(r"listening on random port at (\d+) for HTTP\b", line)
                    if m_port:
                        port = int(m_port.group(1))
        except Exception as e:
            logger.debug(f"Failed to read language_server log: {e}")

    # Fallback to lsof port discovery
    candidate_ports = [port] if port else []
    try:
        lsof_res = subprocess.run(
            ["lsof", "-nP", f"-p{pid}", "-iTCP", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        for p_str in re.findall(r":(\d+)\s+\(LISTEN\)", lsof_res.stdout):
            p_val = int(p_str)
            if p_val not in candidate_ports:
                candidate_ports.append(p_val)
    except subprocess.TimeoutExpired:
        logger.debug("Subprocess timed out querying lsof")
    except (subprocess.SubprocessError, OSError) as exc:
        logger.debug("Error querying lsof for port discovery: %s", exc)

    for candidate in candidate_ports:
        if not candidate:
            continue
        try:
            url = f"http://127.0.0.1:{candidate}{RPC_METHOD}"
            req = urllib.request.Request(
                url,
                data=b"{}",
                headers={
                    "Content-Type": "application/json",
                    "X-Codeium-Csrf-Token": csrf_token,
                },
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return {"pid": pid, "csrf_token": csrf_token, "port": candidate}
        except Exception:
            continue

    return None


def fetch_live_user_status(
    credentials: Optional[Dict[str, Any]] = None,
    timeout: float = 1.5,
) -> Optional[Dict[str, Any]]:
    """
    Query the live GetUserStatus Connect-RPC endpoint.
    Returns normalized dictionary with tier_id, tier_name, available_credits, and client_models.
    """
    creds = credentials or discover_language_server_credentials()
    if not creds:
        return None

    port = creds.get("port")
    csrf_token = creds.get("csrf_token")
    if not port or not csrf_token:
        return None

    url = f"http://127.0.0.1:{port}{USER_STATUS_RPC_METHOD}"
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "X-Codeium-Csrf-Token": csrf_token,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.debug("Failed to query GetUserStatus: %s", e)
        return None

    user_status = data.get("userStatus", data.get("response", {}).get("userStatus", {}))
    if not isinstance(user_status, dict) or not user_status:
        return None

    plan_status = user_status.get("planStatus", {}) if isinstance(user_status.get("planStatus"), dict) else {}
    user_tier = user_status.get("userTier", {}) if isinstance(user_status.get("userTier"), dict) else {}
    cascade_cfg = (
        user_status.get("cascadeModelConfigData", {})
        if isinstance(user_status.get("cascadeModelConfigData"), dict)
        else {}
    )
    raw_models = cascade_cfg.get("clientModelConfigs", []) if isinstance(cascade_cfg.get("clientModelConfigs"), list) else []

    client_models: List[Dict[str, Any]] = []
    for m in raw_models:
        if not isinstance(m, dict):
            continue
        m_choice = m.get("modelOrAlias", {}) if isinstance(m.get("modelOrAlias"), dict) else {}
        quota_info = m.get("quotaInfo", {}) if isinstance(m.get("quotaInfo"), dict) else {}
        client_models.append({
            "label": m.get("label", ""),
            "model": m_choice.get("model", ""),
            "remaining_fraction": float(quota_info.get("remainingFraction", 1.0)) if "remainingFraction" in quota_info else None,
            "reset_time": quota_info.get("resetTime", ""),
        })

    return {
        "available": True,
        "tier_id": user_tier.get("id", ""),
        "tier_name": user_tier.get("name", ""),
        "available_prompt_credits": int(plan_status.get("availablePromptCredits", 0) or 0),
        "available_flow_credits": int(plan_status.get("availableFlowCredits", 0) or 0),
        "client_models": client_models,
    }


def _match_track_id_from_config(
    d_name: str,
    b_id: str,
    quota_tracks: List[Dict[str, Any]],
) -> Optional[str]:
    """Match RPC group displayName and bucketId against config/pricing.json quota_tracks."""
    combined = f"{d_name} {b_id}".lower()
    for track in quota_tracks:
        if not isinstance(track, dict):
            continue
        t_id = str(track.get("id") or "")
        patterns = track.get("rpc_bucket_patterns", [])
        if any(str(pat).lower() in combined for pat in patterns if pat):
            return t_id
    return None


def fetch_live_quota_summary(
    credentials: Optional[Dict[str, Any]] = None,
    timeout: float = 2.0,
    include_user_status: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Query the live RetrieveUserQuotaSummary endpoint.
    Returns normalized dictionary with parsed buckets or None if unavailable.
    """
    creds = credentials or discover_language_server_credentials()
    if not creds:
        return None

    port = creds.get("port")
    csrf_token = creds.get("csrf_token")
    if not port or not csrf_token:
        return None

    url = f"http://127.0.0.1:{port}{RPC_METHOD}"
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "X-Codeium-Csrf-Token": csrf_token,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.debug(f"Failed to query RetrieveUserQuotaSummary: {e}")
        return None

    raw_response = data.get("response", {})
    groups = raw_response.get("groups", [])
    raw_pricing = load_raw_pricing()
    quota_tracks = raw_pricing.get("quota_tracks", []) if isinstance(raw_pricing, dict) else []

    parsed: Dict[str, Any] = {
        "available": True,
        "raw": raw_response,
        "description": raw_response.get("description", ""),
        "gemini_weekly": None,
        "gemini_5h": None,
        "claude_weekly": None,
        "claude_5h": None,
        "tracks": {},
    }

    for g in groups:
        d_name = g.get("displayName", "").lower()
        buckets = g.get("buckets", [])
        for b in buckets:
            b_id = b.get("bucketId", "")
            window = b.get("window", "")
            rem_frac = float(b.get("remainingFraction", 0.0))
            bucket_info = {
                "bucket_id": b_id,
                "display_name": b.get("displayName", ""),
                "description": b.get("description", ""),
                "window": window,
                "remaining_fraction": rem_frac,
                "remaining_pct": round(rem_frac * 100.0, 1),
                "used_fraction": round(max(0.0, 1.0 - rem_frac), 4),
                "used_pct": round(max(0.0, 100.0 - rem_frac * 100.0), 1),
                "reset_time": b.get("resetTime", ""),
            }
            matched_track = _match_track_id_from_config(d_name, b_id, quota_tracks)
            if matched_track:
                t_entry = parsed["tracks"].setdefault(matched_track, {"five_hour": None, "weekly": None})
                if window == "weekly" or "weekly" in b_id:
                    t_entry["weekly"] = bucket_info
                elif window == "5h" or "5h" in b_id:
                    t_entry["five_hour"] = bucket_info

            if matched_track == "gemini" or "gemini" in d_name:
                if window == "weekly" or b_id == "gemini-weekly":
                    parsed["gemini_weekly"] = bucket_info
                elif window == "5h" or b_id == "gemini-5h":
                    parsed["gemini_5h"] = bucket_info
            elif matched_track == "claude_gpt" or "claude" in d_name or "gpt" in d_name or "3p" in b_id:
                if window == "weekly" or b_id == "3p-weekly":
                    parsed["claude_weekly"] = bucket_info
                elif window == "5h" or b_id == "3p-5h":
                    parsed["claude_5h"] = bucket_info

    if include_user_status:
        parsed["user_status"] = fetch_live_user_status(credentials=creds, timeout=min(timeout, 1.5))

    return parsed
