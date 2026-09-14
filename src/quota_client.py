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
from typing import Any, Dict, Optional
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path.home() / "Library" / "Logs" / "Antigravity" / "language_server.log"
RPC_METHOD = "/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary"


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
        )
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
        )
        for p_str in re.findall(r":(\d+)\s+\(LISTEN\)", lsof_res.stdout):
            p_val = int(p_str)
            if p_val not in candidate_ports:
                candidate_ports.append(p_val)
    except Exception:
        pass

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


def fetch_live_quota_summary(
    credentials: Optional[Dict[str, Any]] = None,
    timeout: float = 2.0,
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

    parsed: Dict[str, Any] = {
        "available": True,
        "raw": raw_response,
        "description": raw_response.get("description", ""),
        "gemini_weekly": None,
        "gemini_5h": None,
        "claude_weekly": None,
        "claude_5h": None,
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
            if "gemini" in d_name:
                if window == "weekly" or b_id == "gemini-weekly":
                    parsed["gemini_weekly"] = bucket_info
                elif window == "5h" or b_id == "gemini-5h":
                    parsed["gemini_5h"] = bucket_info
            elif "claude" in d_name or "gpt" in d_name or "3p" in b_id:
                if window == "weekly" or b_id == "3p-weekly":
                    parsed["claude_weekly"] = bucket_info
                elif window == "5h" or b_id == "3p-5h":
                    parsed["claude_5h"] = bucket_info

    return parsed
