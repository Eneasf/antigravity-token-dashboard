#!/usr/bin/env python3
"""
Deterministic exporter: Extracts Antigravity runtime telemetry and updates dashboard/index.html.
"""

import argparse
from collections import defaultdict
import contextlib
import datetime
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Ensure repository root is on Python module search path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def atomic_write_text(target_path: Path, content: str, encoding: str = "utf-8") -> None:
    """Atomically write content to target_path using a unique temporary file."""
    parent_dir = target_path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)
    prefix = f".{target_path.name}."
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=parent_dir,
            prefix=prefix,
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)
        os.replace(tmp_path, target_path)
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


_STATUS_FILE_LOCK = threading.Lock()


@contextlib.contextmanager
def status_file_lock(target_path: Union[str, Path]):
    """Serialize quota status read-modify-write cycles across threads and processes."""
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_file_path = target.parent / f".{target.name}.lock"
    with _STATUS_FILE_LOCK:
        lock_fd = open(lock_file_path, "a+", encoding="utf-8")
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                lock_fd.close()
            except OSError:
                pass

from src.aggregator import (
    load_pricing,
    aggregate_conversation_telemetry,
    aggregate_global_telemetry,
    classify_session_mode,
    detect_file_churn,
    _extract_file_paths_from_tool_call,
)
from src.log_reader import (
    DEFAULT_LOG_PATH,
    DEFAULT_LEDGER_PATH,
    extract_exhaustion_intervals,
    get_latest_exhaustion_event_utc,
)
from src.telemetry_reader import (
    read_conversation_turns,
    read_all_turns,
)
from antigravity_telemetry import (
    DEFAULT_ANTIGRAVITY_DIR,
    discover_all_conversations,
    read_single_conversation_metadata,
    get_model_truncation_threshold,
    get_model_compaction_threshold,
    load_model_catalog,
    load_model_census,
    resolve_wire_model_id,
    evaluate_truncation_severity,
)
from src.temporal import load_raw_pricing
from src.swarm import (
    DEFAULT_VAULT_PATH,
    build_swarms_summary,
    compute_recursive_session_rollups,
    extract_swarm_lineage,
)
from src.tool_analytics import extract_tool_analytics
from src.weekly_trends import (
    get_weekly_trends,
    sync_weekly_trends_to_vault,
)
from src.vault import (
    VaultMarker,
    get_vault_truncation_markers,
    load_latest_quota_snapshot_fallback,
    scan_conversation_truncation,
)
from antigravity_telemetry.reader import (
    get_conversation_title,
    get_workspace_mapping,
)
from src.aggregator_coaching import compute_live_ticker


DEFAULT_STATUS_PATH = Path.home() / ".antigravity_quota_status.json"
_HOST_DEFAULT_ANTIGRAVITY_DIR = DEFAULT_ANTIGRAVITY_DIR
_HOST_DEFAULT_VAULT_PATH = DEFAULT_VAULT_PATH


def _resolve_vault_file_for_dir(antigravity_dir_path: Path, is_custom_dir: bool) -> Path:
    """Resolve the active telemetry Vault DB path while preserving custom/patched test isolation."""
    is_patched_ag_dir = DEFAULT_ANTIGRAVITY_DIR.resolve() != _HOST_DEFAULT_ANTIGRAVITY_DIR.resolve()
    if is_custom_dir or (is_patched_ag_dir and DEFAULT_VAULT_PATH == _HOST_DEFAULT_VAULT_PATH):
        return antigravity_dir_path / "antigravity_vault.db"
    return DEFAULT_VAULT_PATH


def _load_vault_quota_fallback_for_dir(
    vault_file: Path,
    antigravity_dir_path: Path,
    is_custom_dir: bool,
    reference_time: Optional[datetime.datetime],
    label: str = "Vault",
) -> Optional[Dict[str, Any]]:
    """Load non-expired Vault quota fallback when live RPC is offline and isolation permits."""
    if not vault_file.exists():
        return None
    if is_custom_dir and vault_file != (antigravity_dir_path / "antigravity_vault.db"):
        return None
    try:
        return load_latest_quota_snapshot_fallback(vault_file, reference_time=reference_time)
    except Exception as exc:
        logger.warning("%s quota fallback failed: %s", label, exc)
        return None


def is_subagent_conversation(meta: Optional[Dict[str, Any]]) -> bool:
    """
    Returns True if the metadata indicates this conversation is a delegated subagent or worker.
    Antigravity marks subagents via:
    1. Wire field 17: is_subagent == True
    2. Wire field 5: parent_convo_id is non-empty
    3. Wire field 8: subagent_type is non-empty
    """
    if not meta:
        return False
    if meta.get("is_subagent"):
        return True
    if meta.get("parent_convo_id"):
        return True
    if meta.get("subagent_type"):
        return True
    return False


def evaluate_session_node(c: dict, census: Optional[dict] = None) -> dict:
    """Evaluate a single conversation node for active capacity load, compaction drift, and risk score."""
    if census is None:
        census = load_model_census()
    convo_id = c.get("convo_id", "")
    title = c.get("title") or convo_id or "Active Conversation"
    agent_name = c.get("agent_name", "default")
    is_sub = bool(is_subagent_conversation(c))
    subagent_role = c.get("subagent_role", "")
    parent_convo_id = c.get("parent_convo_id", "")
    branch = c.get("git_branch") or "main"
    workspace = c.get("workspace_name") or "Antigravity Workspace"
    turns = c.get("turns", [])

    turn_velocity = 0
    active_model = ""
    if turns:
        # Latest turn represents current active context load (Dual-State ADR-092)
        last_turn = turns[-1]
        active_tokens = last_turn.get("total_input_tokens", 0)
        active_model = last_turn.get("model_id") or last_turn.get("model_name") or ""
        if len(turns) >= 2:
            prev_turn = turns[-2]
            turn_velocity = max(0, active_tokens - prev_turn.get("total_input_tokens", 0))
    else:
        active_tokens = c.get("peak_prompt_depth") or (c.get("total_input_tokens", 0) / max(c.get("turn_count", 1), 1))

    if not active_model and c.get("models_used"):
        active_model = c.get("models_used", [""])[-1] or ""

    nominal_threshold = get_model_truncation_threshold(active_model, census)
    compaction_threshold = get_model_compaction_threshold(active_model, census)
    comp_count = int(c.get("compaction_count") or (1 if c.get("has_truncated") else 0))
    epoch = int(c.get("compaction_epoch") or ((comp_count + 1) if (comp_count > 0 or c.get("has_truncated")) else 1))

    ratio = active_tokens / compaction_threshold if compaction_threshold > 0 else 0
    headroom_to_warning = max(0, int(compaction_threshold * 0.75) - int(active_tokens))
    headroom_to_compaction = max(0, int(compaction_threshold) - int(active_tokens))

    # Multi-factor risk & drift classification (ADR-082 / ADR-092)
    if epoch >= 3:
        active_session_severity = "critical"
        drift_risk = "critical"
        drift_message = f"Epoch {epoch} Drift: Turn 1 evicted"
    elif ratio >= 0.9:
        active_session_severity = "critical"
        drift_risk = "warning"
        drift_message = "Compaction Imminent (~1 turn)"
    elif turn_velocity >= 40000 and ratio >= 0.65:
        active_session_severity = "warning"
        drift_risk = "warning"
        drift_message = f"Velocity Spike (+{turn_velocity // 1000}k tok/turn)"
    elif ratio >= 0.75:
        active_session_severity = "warning"
        drift_risk = "caution"
        drift_message = f"Near Compaction (+{headroom_to_compaction} tok)"
    elif epoch == 2:
        active_session_severity = "warning"
        drift_risk = "caution"
        drift_message = "Epoch 2: History compressed"
    else:
        active_session_severity = "safe"
        drift_risk = "safe"
        drift_message = f"Safe (+{headroom_to_warning} to warning)"

    # Base risk score for weakest-link election
    # When safe, prioritize user-facing orchestrators (150 base) over subagents (100 base).
    # When warning (200 base) or critical (300 base), bubbling up at-risk subagents takes absolute priority.
    if active_session_severity == "critical":
        score = 300.0 + (ratio * 100.0) + (50.0 if epoch >= 3 else 0.0)
    elif active_session_severity == "warning":
        score = 200.0 + (ratio * 100.0)
    else:
        base_safe = 150.0 if not is_sub else 100.0
        score = base_safe + (ratio * 100.0)

    return {
        "id": convo_id,
        "title": title,
        "convo_id": convo_id,
        "agent_name": agent_name,
        "is_subagent": is_sub,
        "subagent_role": subagent_role,
        "parent_convo_id": parent_convo_id,
        "branch": branch,
        "workspace": workspace,
        "tokens": int(active_tokens),
        "threshold": compaction_threshold,
        "nominal_threshold": nominal_threshold,
        "compaction_threshold": compaction_threshold,
        "compaction_count": comp_count,
        "compaction_epoch": epoch,
        "severity": active_session_severity,
        "drift_risk": drift_risk,
        "drift_message": drift_message,
        "turn_velocity": int(turn_velocity),
        "headroom_to_warning": headroom_to_warning,
        "headroom_to_compaction": headroom_to_compaction,
        "is_current": True,
        "_risk_score": score,
        "last_turn_ts": c.get("last_turn_ts", ""),
    }


def extract_active_swarms_hierarchy(
    convos: List[dict],
    census: Optional[dict] = None,
    reference_time: Optional[datetime.datetime] = None,
    recency_minutes: int = 30,
    swarm_recency_minutes: Optional[int] = None,
) -> Tuple[List[dict], Optional[dict]]:
    """
    Extract active swarms grouped by workspace/project and parent orchestrators,
    and elect the weakest-link node (highest risk) across all active cascades.
    Preserves full parent-child descendant trees for any active orchestrator or subagent.
    """
    if not convos:
        return [], None

    if census is None:
        census = load_model_census()

    ref_dt = reference_time or datetime.datetime.now(datetime.timezone.utc)

    # 1. Index all conversations and build parent-child lineage across full corpus
    convo_by_id: Dict[str, dict] = {}
    children_by_parent: Dict[str, List[str]] = defaultdict(list)
    parent_by_child: Dict[str, str] = {}

    for c in convos:
        cid = str(c.get("convo_id") or "").strip()
        if cid:
            convo_by_id[cid] = c

    for cid, c in convo_by_id.items():
        pid = str(c.get("parent_convo_id") or "").strip()
        if pid and pid in convo_by_id and pid != cid:
            parent_by_child[cid] = pid
            if cid not in children_by_parent[pid]:
                children_by_parent[pid].append(cid)
        for ch in c.get("child_ids") or []:
            ch_id = str(ch or "").strip()
            if ch_id and ch_id in convo_by_id and ch_id != cid:
                if ch_id not in parent_by_child:
                    parent_by_child[ch_id] = cid
                if ch_id not in children_by_parent[cid]:
                    children_by_parent[cid].append(ch_id)

    def _get_root_id(cid: str) -> str:
        curr = cid
        visited = {curr}
        while curr in parent_by_child:
            nxt = parent_by_child[curr]
            if nxt in visited or nxt not in convo_by_id:
                break
            visited.add(nxt)
            curr = nxt
        return curr

    def _get_descendants(root_id: str) -> List[str]:
        desc: List[str] = []
        visited = {root_id}
        queue = list(children_by_parent.get(root_id, []))
        while queue:
            curr = queue.pop(0)
            if curr not in visited and curr in convo_by_id:
                visited.add(curr)
                desc.append(curr)
                for nxt in children_by_parent.get(curr, []):
                    if nxt not in visited:
                        queue.append(nxt)
        return desc

    # 2. Filter conversations in the immediate recency window (and optional multi-agent swarm window)
    immediate_active_convos: List[dict] = []
    swarm_active_convos: List[dict] = []
    for c in convos:
        last_ts = c.get("last_turn_ts")
        if not last_ts:
            continue
        try:
            dt = datetime.datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            delta_sec = (ref_dt - dt).total_seconds()
            if 0 <= delta_sec <= recency_minutes * 60:
                immediate_active_convos.append(c)
            elif swarm_recency_minutes and 0 <= delta_sec <= swarm_recency_minutes * 60:
                cid = str(c.get("convo_id") or "").strip()
                if cid:
                    root_id = _get_root_id(cid)
                    if len(_get_descendants(root_id)) > 0:
                        swarm_active_convos.append(c)
        except Exception:
            pass

    active_convos = immediate_active_convos + swarm_active_convos

    # If no conversation is active within the recency window, there are 0 active swarms.
    # For current_session fallback (e.g. idle workspace or offline fixtures), elect the latest
    # non-subagent conversation (or convos[0] if all are subagents).
    if not active_convos:
        primary_candidates = [c for c in convos if not is_subagent_conversation(c)]
        fallback_convo = primary_candidates[0] if primary_candidates else convos[0]
        fallback_node = evaluate_session_node(fallback_convo, census)
        fallback_node["is_current"] = True
        clean_fallback = {k: v for k, v in fallback_node.items() if not k.startswith("_")}
        return [], clean_fallback

    # 3. Evaluate nodes and elect weakest link from immediate active sessions (or swarm active fallback)
    evaluated_by_id: Dict[str, dict] = {}

    def _eval_cached(c_dict: dict) -> dict:
        cid = str(c_dict.get("convo_id") or "")
        if cid and cid in evaluated_by_id:
            return evaluated_by_id[cid]
        node = evaluate_session_node(c_dict, census)
        if cid:
            evaluated_by_id[cid] = node
        return node

    weakest_pool = immediate_active_convos if immediate_active_convos else swarm_active_convos
    evaluated_weakest_pool = [_eval_cached(c) for c in weakest_pool]

    all_titles_by_id = {
        c.get("convo_id"): (c.get("title") or c.get("convo_id"))
        for c in convos
        if c.get("convo_id")
    }

    weakest = max(
        evaluated_weakest_pool,
        key=lambda n: (n["_risk_score"], n.get("last_turn_ts") or ""),
        default=None,
    )
    if weakest:
        has_multi_candidates = (
            len(evaluated_weakest_pool) > 1
            or len(active_convos) > 1
            or any(
                len(_get_descendants(_get_root_id(str(c.get("convo_id") or "")))) > 0
                for c in weakest_pool
            )
        )
        if has_multi_candidates and weakest.get("severity") != "safe":
            weakest["is_weakest_link"] = True
        else:
            weakest["is_weakest_link"] = False
        if weakest["is_subagent"] and weakest["parent_convo_id"]:
            parent_id = weakest["parent_convo_id"]
            if parent_id in all_titles_by_id:
                weakest["parent_title"] = all_titles_by_id[parent_id]

    # 4. Collect active root orchestrators and unparented active subagents per workspace
    active_root_ids_by_ws: Dict[str, List[str]] = defaultdict(list)
    unparented_subs_by_ws: Dict[str, List[dict]] = defaultdict(list)

    for c in active_convos:
        node = _eval_cached(c)
        cid = node.get("convo_id", "")
        ws = node["workspace"] or "Default Workspace"
        raw_parent = str(node.get("parent_convo_id") or "").strip()

        if node["is_subagent"]:
            if raw_parent:
                # Strict lineage binding: if explicit parent_convo_id is not in convos corpus,
                # do not attach this subagent to an unrelated orchestrator.
                if raw_parent not in convo_by_id:
                    continue
                root_id = _get_root_id(cid)
                root_convo = convo_by_id.get(root_id, c)
                root_ws = root_convo.get("workspace_name") or ws
                if root_id not in active_root_ids_by_ws[root_ws]:
                    active_root_ids_by_ws[root_ws].append(root_id)
            else:
                unparented_subs_by_ws[ws].append(node)
        else:
            root_id = _get_root_id(cid) if cid else ""
            if root_id and root_id not in active_root_ids_by_ws[ws]:
                active_root_ids_by_ws[ws].append(root_id)

    # 5. Build orchestrator + descendant subagent trees per workspace
    swarms: List[dict] = []
    all_workspaces = list(dict.fromkeys(list(active_root_ids_by_ws.keys()) + list(unparented_subs_by_ws.keys())))

    for ws in all_workspaces:
        root_ids = active_root_ids_by_ws.get(ws, [])
        unparented_subs = unparented_subs_by_ws.get(ws, [])

        trees_for_ws: List[dict] = []
        for r_id in root_ids:
            r_convo = convo_by_id.get(r_id)
            if not r_convo:
                continue
            orch_node = _eval_cached(r_convo)
            desc_ids = _get_descendants(r_id)
            desc_nodes = [_eval_cached(convo_by_id[d_id]) for d_id in desc_ids if d_id in convo_by_id]
            trees_for_ws.append({
                "orch_node": orch_node,
                "sub_nodes": desc_nodes,
                "latest_ts": max(
                    [orch_node.get("last_turn_ts") or ""] + [sn.get("last_turn_ts") or "" for sn in desc_nodes]
                ),
            })

        # If a workspace only had unparented subagents active, promote the first as fallback orchestrator
        if not trees_for_ws and unparented_subs:
            first_sub = unparented_subs[0]
            trees_for_ws.append({
                "orch_node": first_sub,
                "sub_nodes": unparented_subs[1:],
                "latest_ts": first_sub.get("last_turn_ts") or "",
            })
            unparented_subs = []

        # Attach any unparented subagents in this workspace to the most recent orchestrator tree
        if trees_for_ws and unparented_subs:
            latest_tree = max(trees_for_ws, key=lambda t: t["latest_ts"])
            existing_ids = {sn["convo_id"] for sn in latest_tree["sub_nodes"]} | {latest_tree["orch_node"]["convo_id"]}
            for usub in unparented_subs:
                if usub["convo_id"] not in existing_ids:
                    latest_tree["sub_nodes"].append(usub)
                    existing_ids.add(usub["convo_id"])

        # Prefer multi-agent trees (with subagents) over standalone 0-subagent sessions in the same workspace
        multi_agent_trees = [t for t in trees_for_ws if len(t["sub_nodes"]) > 0]
        standalone_trees = [t for t in trees_for_ws if len(t["sub_nodes"]) == 0]

        if multi_agent_trees:
            multi_agent_trees.sort(key=lambda t: t["latest_ts"], reverse=True)
            selected_trees = multi_agent_trees[:2]
        elif standalone_trees:
            selected_trees = [max(standalone_trees, key=lambda t: t["latest_ts"])]
        else:
            selected_trees = []

        for tree in selected_trees:
            orch_node = tree["orch_node"]
            sub_nodes = tree["sub_nodes"]
            sub_nodes.sort(key=lambda n: n.get("last_turn_ts") or "", reverse=True)

            subagents = []
            for n in sub_nodes:
                subagents.append({
                    "convo_id": n["convo_id"],
                    "title": n["title"],
                    "subagent_role": n["subagent_role"] or "subagent",
                    "tokens": n["tokens"],
                    "threshold": n["threshold"],
                    "nominal_threshold": n["nominal_threshold"],
                    "compaction_threshold": n["compaction_threshold"],
                    "compaction_epoch": n["compaction_epoch"],
                    "severity": n["severity"],
                    "is_weakest_link": bool(
                        weakest and weakest.get("is_weakest_link") and n["convo_id"] == weakest["convo_id"]
                    ),
                    "turn_velocity": n["turn_velocity"],
                })

            swarm_nodes = [orch_node] + sub_nodes
            severities = [n["severity"] for n in swarm_nodes]
            if "critical" in severities:
                worst_sev = "critical"
            elif "warning" in severities:
                worst_sev = "warning"
            else:
                worst_sev = "safe"

            orch_clean = {k: v for k, v in orch_node.items() if not k.startswith("_")}
            orch_clean["is_weakest_link"] = bool(
                weakest and weakest.get("is_weakest_link") and orch_node["convo_id"] == weakest["convo_id"]
            )

            swarms.append({
                "workspace": ws,
                "branch": orch_node["branch"],
                "worst_severity": worst_sev,
                "orchestrator": orch_clean,
                "subagents": subagents,
            })

    sev_rank = {"critical": 0, "warning": 1, "safe": 2}
    swarms.sort(
        key=lambda s: (
            sev_rank.get(s["worst_severity"], 3),
            0 if len(s.get("subagents", [])) > 0 else 1,
            s["workspace"],
            -(len(s.get("subagents", []))),
        )
    )

    clean_weakest = {k: v for k, v in weakest.items() if not k.startswith("_")} if weakest else None
    if clean_weakest is not None:
        clean_weakest["is_current"] = True
    return swarms, clean_weakest


def compute_current_session(
    payload: dict,
    census: Optional[dict] = None,
    reference_time: Optional[datetime.datetime] = None,
) -> Optional[dict]:
    """Compute active current session metadata and severity rating for executive telemetry."""
    convos = payload.get("conversations", [])
    if not convos:
        return None
    if census is None:
        census = load_model_census()

    swarms, weakest = extract_active_swarms_hierarchy(convos, census, reference_time)
    if weakest:
        weakest["is_current"] = True
        return weakest

    node = evaluate_session_node(convos[0], census)
    node["is_current"] = True
    return {k: v for k, v in node.items() if not k.startswith("_")}


def _iso_to_epoch(iso_str: Optional[str]) -> Optional[float]:
    """Parse an ISO-8601 timestamp string into a UTC Unix epoch float."""
    if not iso_str or not isinstance(iso_str, str):
        return None
    try:
        dt = datetime.datetime.fromisoformat(iso_str.strip().replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return round(dt.timestamp(), 3)
    except Exception:
        return None


def build_export_catalog(pricing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Assemble the unified schema_version=2 catalog dict for payload['catalog'] (data.js / data.json)."""
    model_cat = load_model_catalog()
    try:
        raw_pricing = load_raw_pricing()
    except Exception:
        raw_pricing = {}
    raw_models = raw_pricing.get("models", {}) if isinstance(raw_pricing, dict) else {}
    pricing_models = pricing if isinstance(pricing, dict) else {}
    default_rates = raw_pricing.get(
        "default_rates_per_million",
        {"input_uncached": 1.25, "input_cached": 0.125, "output": 5.0},
    )

    models_out: Dict[str, Any] = {}
    for mid, m_meta in (model_cat.get("models") or {}).items():
        if not isinstance(m_meta, dict):
            continue
        rm = raw_models.get(mid) or pricing_models.get(mid) or {}
        rates = rm.get("rates_per_million", default_rates)
        q_weights = rm.get("quota_weights_per_million", rates)
        models_out[mid] = {
            **m_meta,
            "id": mid,
            "rates_per_million": rates,
            "quota_weights_per_million": q_weights,
            "credits_per_turn": rm.get("credits_per_turn", 2.5),
        }

    return {
        "schema_version": int(model_cat.get("schema_version", 2)),
        "defaults": model_cat.get("defaults", {}),
        "families": model_cat.get("families", {}),
        "models": models_out,
        "quota_tracks": raw_pricing.get("quota_tracks", []),
        "plan_tiers": raw_pricing.get("plan_tiers", {}),
        "simulator_archetypes": raw_pricing.get("simulator_archetypes", []),
    }


def _resolve_weekly_bvi_status(
    wk_bvi: Optional[float],
    wk_used: float,
    rw: Dict[str, Any],
    wk_bvi_label: Optional[str],
    prev_wk: Dict[str, Any],
    has_payload: bool,
) -> Optional[str]:
    """Map runway status_key / buffer state to bvi_status without Day-1 false deficits."""
    if wk_bvi is None:
        return None
    status_key = str(rw.get("status_key") or "").lower()
    if status_key == "green":
        return "sustainable"
    if status_key == "amber":
        return "deficit"
    if status_key in ("red", "exhausted"):
        return "overburn"

    label_lower = str(wk_bvi_label or "").lower()
    if wk_used <= 0.0 or "buffer" in label_lower or "sustainable" in label_lower or "on track" in label_lower:
        return "sustainable"
    if "overburn" in label_lower:
        return "overburn"
    if "deficit" in label_lower:
        return "overburn" if wk_bvi > 1.3 else "deficit"
    if not has_payload and prev_wk.get("bvi_status") in ("sustainable", "deficit", "overburn"):
        return str(prev_wk["bvi_status"])
    return "overburn" if wk_bvi > 1.3 else "sustainable"


def build_or_patch_status_tracks(
    status_data: Dict[str, Any],
    payload: Optional[Dict[str, Any]] = None,
    raw_pricing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Populate schema_version=2 executive status contract fields (generated_at_utc,
    generated_at_epoch, plan, and metadata-driven tracks[]) on status_data while
    preserving 100% of v1 backward-compatible top-level keys.
    """
    if raw_pricing is None:
        try:
            raw_pricing = load_raw_pricing()
        except Exception:
            raw_pricing = {}

    updated_at = str(status_data.get("updated_at") or datetime.datetime.now(datetime.timezone.utc).isoformat())
    status_data["schema_version"] = 2
    status_data["generated_at_utc"] = updated_at
    status_data["generated_at_epoch"] = _iso_to_epoch(updated_at) or round(time.time(), 3)

    summary = (payload or {}).get("summary", {}) if isinstance(payload, dict) else {}
    existing_plan = status_data.get("plan") if isinstance(status_data.get("plan"), dict) else {}
    tier_id = str(
        summary.get("subscription_tier")
        or summary.get("tier")
        or existing_plan.get("tier_id")
        or "ultra_5x"
    )
    plan_tiers = raw_pricing.get("plan_tiers", {}) if isinstance(raw_pricing, dict) else {}
    tier_cfg = plan_tiers.get(tier_id, {}) if isinstance(plan_tiers, dict) else {}
    badge_label = str(
        tier_cfg.get("badge_label")
        or existing_plan.get("badge")
        or ("AI ULTRA · 5X" if "ultra" in tier_id.lower() else ("AI PRO · 1X" if "pro" in tier_id.lower() else "AI TEAM"))
    )
    burned = int(summary.get("total_ai_credits_burned", 0) or 0)
    pool = int(
        summary.get(
            "monthly_plan_credits",
            existing_plan.get("credit_pool", tier_cfg.get("included_monthly_credits", 5000)),
        )
        or 5000
    )
    rem_credits = int(
        summary.get(
            "monthly_credits_remaining",
            summary.get("credits_remaining", existing_plan.get("credits_remaining", max(0, pool - burned))),
        )
    )
    rem_gbp = float(summary.get("credit_bank_remaining_gbp", existing_plan.get("credit_balance_gbp", 0.0)) or 0.0)
    status_data["plan"] = {
        "tier_id": tier_id,
        "name": str(status_data.get("plan_name") or existing_plan.get("name") or tier_cfg.get("name") or "Google AI Ultra (5x)"),
        "badge": badge_label,
        "credit_pool": pool,
        "credits_remaining": rem_credits,
        "credit_balance_gbp": round(rem_gbp, 2),
    }

    quota_tracks = raw_pricing.get("quota_tracks") if isinstance(raw_pricing, dict) else None
    if not isinstance(quota_tracks, list) or not quota_tracks:
        quota_tracks = [
            {
                "id": "gemini",
                "name": "Gemini",
                "display_name": "Gemini (Carbon / Argon / Flash)",
                "short_name": "Gemini",
                "icon": "sparkles",
                "color_token": "--accent-primary",
                "reset_cadence": "fixed_weekly",
                "credit_spillover": True,
                "is_primary": True,
                "sort_rank": 1,
            },
            {
                "id": "claude_gpt",
                "name": "Claude & GPT",
                "display_name": "Claude 5.5 / 4.6 & GPT-OSS",
                "short_name": "Claude/GPT",
                "icon": "cpu",
                "color_token": "--accent-purple",
                "reset_cadence": "rolling_7d",
                "credit_spillover": False,
                "is_primary": False,
                "sort_rank": 2,
            },
        ]

    prov = (payload or {}).get("quotas", {}).get("providers", {}) if isinstance(payload, dict) else {}
    existing_tracks_by_id: Dict[str, Dict[str, Any]] = {}
    if isinstance(status_data.get("tracks"), list):
        for et in status_data["tracks"]:
            if isinstance(et, dict) and et.get("id"):
                existing_tracks_by_id[str(et["id"])] = et

    tracks_out: List[Dict[str, Any]] = []
    sorted_tracks = sorted(
        [t for t in quota_tracks if isinstance(t, dict)],
        key=lambda t: int(t.get("sort_rank", 99)),
    )
    for t_cfg in sorted_tracks:
        tid = str(t_cfg.get("id") or "gemini")
        is_primary = bool(t_cfg.get("is_primary", tid == "gemini"))
        p_entry = prov.get(tid, {}) if isinstance(prov, dict) else {}
        fh = p_entry.get("five_hour", {}) if isinstance(p_entry, dict) else {}
        wk = p_entry.get("weekly", {}) if isinstance(p_entry, dict) else {}
        rw = p_entry.get("runway", {}) if isinstance(p_entry, dict) else {}

        prev_track = existing_tracks_by_id.get(tid, {})
        prev_wins = {
            str(w.get("window_id")): w
            for w in (prev_track.get("windows") or [])
            if isinstance(w, dict) and w.get("window_id")
        }
        prev_5h = prev_wins.get("5h", {})
        prev_wk = prev_wins.get("weekly", {})

        if tid == "gemini":
            fh_used = float(status_data.get("gemini_5h_pct", fh.get("used_pct", prev_5h.get("used_pct", 0.0))) or 0.0)
            fh_rem = float(status_data.get("gemini_5h_remaining_pct", round(max(0.0, min(100.0, 100.0 - fh_used)), 1)))
            fh_tokens = int(fh.get("total_processed_tokens", status_data.get("gemini_5h_tokens", prev_5h.get("used_tokens", 0))) or 0)
            fh_reset_utc = str(fh.get("reset_time") or prev_5h.get("reset_utc") or "")
            fh_recovery_desc = str(status_data.get("gemini_5h_recovery_desc") or prev_5h.get("recovery_desc") or "")
            fh_cooldown = bool(status_data.get("cooldown_active", rw.get("burst_cooldown_active", fh_used >= 100.0)))

            wk_used = float(status_data.get("gemini_weekly_pct", wk.get("used_pct", prev_wk.get("used_pct", 0.0))) or 0.0)
            wk_rem = float(status_data.get("gemini_weekly_remaining_pct", round(max(0.0, min(100.0, 100.0 - wk_used)), 1)))
            wk_tokens = int(wk.get("total_processed_tokens", prev_wk.get("used_tokens", 0)) or 0)
            wk_reset_utc = str(status_data.get("weekly_reset_utc") or wk.get("weekly_reset_utc") or prev_wk.get("reset_utc") or "")
            wk_reset_desc = str(status_data.get("weekly_reset_desc") or prev_wk.get("reset_desc") or "")
            wk_bvi = float(status_data.get("bvi", rw.get("bvi_bayes", rw.get("burn_velocity_index", prev_wk.get("bvi") or 1.0))))
            wk_bvi_pacing = rw.get("calendar_time_elapsed_pct", prev_wk.get("bvi_pacing_pct"))
            wk_bvi_label = str(status_data.get("bvi_verdict") or rw.get("status_sub") or rw.get("status_text") or prev_wk.get("bvi_label") or "On Track")
        elif tid == "claude_gpt":
            fh_used = float(status_data.get("claude_5h_pct", fh.get("used_pct", prev_5h.get("used_pct", 0.0))) or 0.0)
            fh_rem = float(status_data.get("claude_5h_remaining_pct", round(max(0.0, min(100.0, 100.0 - fh_used)), 1)))
            fh_tokens = int(fh.get("total_processed_tokens", prev_5h.get("used_tokens", 0)) or 0)
            fh_reset_utc = str(fh.get("reset_time") or prev_5h.get("reset_utc") or "")
            fh_recovery_desc = str(fh.get("message") or prev_5h.get("recovery_desc") or "")
            fh_cooldown = bool(fh_used >= 100.0)

            wk_used = float(status_data.get("claude_weekly_pct", wk.get("used_pct", prev_wk.get("used_pct", 0.0))) or 0.0)
            wk_rem = float(status_data.get("claude_weekly_remaining_pct", round(max(0.0, min(100.0, 100.0 - wk_used)), 1)))
            wk_tokens = int(wk.get("total_processed_tokens", prev_wk.get("used_tokens", 0)) or 0)
            wk_reset_utc = str(wk.get("weekly_reset_utc") or wk.get("reset_time") or prev_wk.get("reset_utc") or "")
            wk_reset_desc = str(wk.get("message") or wk.get("reset_display") or prev_wk.get("reset_desc") or "7-day rolling window")
            wk_bvi = None
            wk_bvi_pacing = None
            wk_bvi_label = None
        else:
            fh_used = float(fh.get("used_pct", prev_5h.get("used_pct", 0.0)) or 0.0)
            fh_rem = round(max(0.0, min(100.0, 100.0 - fh_used)), 1)
            fh_tokens = int(fh.get("total_processed_tokens", prev_5h.get("used_tokens", 0)) or 0)
            fh_reset_utc = str(fh.get("reset_time") or prev_5h.get("reset_utc") or "")
            fh_recovery_desc = str(fh.get("message") or prev_5h.get("recovery_desc") or "")
            fh_cooldown = bool(fh_used >= 100.0)

            wk_used = float(wk.get("used_pct", prev_wk.get("used_pct", 0.0)) or 0.0)
            wk_rem = round(max(0.0, min(100.0, 100.0 - wk_used)), 1)
            wk_tokens = int(wk.get("total_processed_tokens", prev_wk.get("used_tokens", 0)) or 0)
            wk_reset_utc = str(wk.get("weekly_reset_utc") or wk.get("reset_time") or prev_wk.get("reset_utc") or "")
            wk_reset_desc = str(wk.get("message") or wk.get("reset_display") or prev_wk.get("reset_desc") or "")
            wk_bvi = float(rw.get("burn_velocity_index")) if rw.get("burn_velocity_index") is not None else prev_wk.get("bvi")
            wk_bvi_pacing = rw.get("calendar_time_elapsed_pct", prev_wk.get("bvi_pacing_pct"))
            wk_bvi_label = rw.get("status_sub") or rw.get("status_text") or prev_wk.get("bvi_label")

        wk_bvi_status = _resolve_weekly_bvi_status(
            wk_bvi=wk_bvi,
            wk_used=wk_used,
            rw=rw if isinstance(rw, dict) else {},
            wk_bvi_label=wk_bvi_label,
            prev_wk=prev_wk if isinstance(prev_wk, dict) else {},
            has_payload=isinstance(payload, dict) and bool(prov),
        )

        tracks_out.append({
            "id": tid,
            "name": str(t_cfg.get("display_name") or t_cfg.get("name") or tid),
            "short_name": str(t_cfg.get("short_name") or t_cfg.get("name") or tid),
            "icon": str(t_cfg.get("icon") or ("sparkles" if is_primary else "cpu")),
            "color_token": str(t_cfg.get("color_token") or ("--accent-primary" if is_primary else "--accent-purple")),
            "reset_cadence": str(t_cfg.get("reset_cadence") or ("fixed_weekly" if is_primary else "rolling_7d")),
            "credit_spillover": bool(t_cfg.get("credit_spillover", is_primary)),
            "is_primary": is_primary,
            "sort_rank": int(t_cfg.get("sort_rank", 1 if is_primary else 2)),
            "windows": [
                {
                    "window_id": "5h",
                    "label": "5-Hour Burst",
                    "icon": "bolt.fill",
                    "used_pct": round(fh_used, 1),
                    "remaining_pct": round(fh_rem, 1),
                    "used_tokens": fh_tokens,
                    "reset_utc": fh_reset_utc if fh_reset_utc else None,
                    "reset_epoch": _iso_to_epoch(fh_reset_utc),
                    "recovery_desc": fh_recovery_desc,
                    "is_cooldown": fh_cooldown,
                    "severity": "critical" if (fh_used >= 90.0 or fh_cooldown) else ("warning" if fh_used >= 75.0 else "safe"),
                },
                {
                    "window_id": "weekly",
                    "label": "Weekly Allowance" if is_primary else "7-Day Rolling",
                    "icon": "calendar",
                    "used_pct": round(wk_used, 1),
                    "remaining_pct": round(wk_rem, 1),
                    "used_tokens": wk_tokens,
                    "reset_utc": wk_reset_utc if wk_reset_utc else None,
                    "reset_epoch": _iso_to_epoch(wk_reset_utc),
                    "reset_desc": wk_reset_desc,
                    "is_cooldown": bool(wk_used >= 100.0),
                    "severity": "critical" if wk_used >= 90.0 else ("warning" if wk_used >= 75.0 else "safe"),
                    "bvi": round(float(wk_bvi), 2) if wk_bvi is not None else None,
                    "bvi_status": wk_bvi_status,
                    "bvi_pacing_pct": round(float(wk_bvi_pacing), 1) if wk_bvi_pacing is not None else None,
                    "bvi_label": wk_bvi_label,
                },
            ],
        })

    status_data["tracks"] = tracks_out
    return status_data


def write_quota_status_file(
    payload: dict,
    status_path: Optional[Path] = None,
    watcher_info: Optional[dict] = None,
) -> Path:
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

    gem_5h_used = float(gem_5h.get("used_pct", 0.0))
    gem_5h_rem = round(max(0.0, min(100.0, 100.0 - gem_5h_used)), 1)
    gem_wk_used = float(gem_weekly.get("used_pct", 0.0))
    gem_wk_rem = round(max(0.0, min(100.0, 100.0 - gem_wk_used)), 1)
    cg_5h_used = float(cg_5h.get("used_pct", 0.0))
    cg_5h_rem = round(max(0.0, min(100.0, 100.0 - cg_5h_used)), 1)
    cg_wk_used = float(cg_weekly.get("used_pct", 0.0))
    cg_wk_rem = round(max(0.0, min(100.0, 100.0 - cg_wk_used)), 1)

    # 5h Recovery Description (Discrete 5-Hour Limit Reset, ADR-082)
    reset_msg = gem_5h.get("message") or gem_5h.get("description")
    reset_time_str = gem_5h.get("reset_time")
    rec_sched = gem_5h.get("recovery_schedule", [])
    if reset_msg:
        gemini_5h_recovery_desc = reset_msg
    elif reset_time_str:
        try:
            r_dt = datetime.datetime.fromisoformat(reset_time_str.replace("Z", "+00:00"))
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            rem_sec = max(0, int((r_dt - now_dt).total_seconds()))
            rem_m = rem_sec // 60
            if rem_m >= 60:
                h = rem_m // 60
                m = rem_m % 60
                rem_str = f"{h}h {m}m" if m else f"{h}h"
            else:
                rem_str = f"{rem_m}m"
            time_part = r_dt.strftime("%H:%M UTC")
            gemini_5h_recovery_desc = f"Fully refreshes in {rem_str} ({time_part})"
        except Exception:
            gemini_5h_recovery_desc = f"Fully refreshes at {reset_time_str}"
    elif rec_sched:
        first_min = rec_sched[0].get("minutes_remaining", 0)
        last_min = rec_sched[-1].get("minutes_remaining", 0)
        if last_min >= 60:
            h = last_min // 60
            m = last_min % 60
            full_str = f"{h}h {m}m" if m else f"{h}h"
        else:
            full_str = f"{last_min}m"
        gemini_5h_recovery_desc = f"Next roll-off in {first_min}m (100% in {full_str})"
    elif gem_5h_used > 0:
        gemini_5h_recovery_desc = "Fully refreshes 5h after cycle start"
    else:
        gemini_5h_recovery_desc = "100% Headroom (0 used)"

    # Weekly Reset Description
    wk_human = gem_weekly.get("human_remaining") or ""
    wk_day = gem_weekly.get("reset_day_name") or ""
    wk_time = gem_weekly.get("reset_time_utc") or ""
    if wk_human and wk_day:
        weekly_reset_desc = f"{wk_day} {wk_time} ({wk_human} remaining)"
    elif gem_weekly.get("reset_display"):
        weekly_reset_desc = str(gem_weekly.get("reset_display"))
    else:
        weekly_reset_desc = "Weekly reset at cycle boundary"

    # Plan Name
    s = payload.get("summary", {})
    tier = s.get("tier", "ultra_5x")
    plan_name = s.get("subscription_tier_name") or ("Google AI Ultra (5x)" if tier == "ultra_5x" else "Google One AI Pro")

    # Active Project & Branch
    convos = payload.get("conversations", [])
    active_project = convos[0].get("workspace_name") or "Antigravity Workspace" if convos else "Antigravity Workspace"
    active_branch = convos[0].get("git_branch") or "main" if convos else "main"

    degraded_count = 0
    critical_count = 0
    degraded_sessions = []
    census = load_model_census()

    ref_dt = None
    if payload.get("temporal", {}).get("resolved_at_utc"):
        try:
            ref_dt = datetime.datetime.fromisoformat(payload["temporal"]["resolved_at_utc"].replace("Z", "+00:00"))
        except Exception:
            pass
    eff_ref_dt = ref_dt or datetime.datetime.now(datetime.timezone.utc)
    now_ms = eff_ref_dt.timestamp() * 1000

    active_swarms = payload.get("active_swarms")
    if active_swarms is None:
        active_swarms, weakest = extract_active_swarms_hierarchy(
            convos, census, ref_dt, swarm_recency_minutes=1440
        )
    else:
        weakest = None

    # Calculate active session severity based on weakest-link or current session
    current_session = payload.get("current_session") or weakest or compute_current_session(payload, census, ref_dt)
    active_session_severity = current_session["severity"] if current_session else "safe"
    epoch = current_session["compaction_epoch"] if current_session else 1
    active_agent_role = (current_session.get("subagent_role") if current_session.get("is_subagent") else current_session.get("agent_name", "default")) if current_session else "default"
    if current_session:
        active_project = current_session.get("workspace") or active_project
        active_branch = current_session.get("branch") or active_branch

    for c in convos:
        last_turn_str = c.get("last_turn_ts")
        if not last_turn_str:
            continue
        try:
            last_turn_dt = datetime.datetime.fromisoformat(last_turn_str.replace('Z', '+00:00'))
            if (now_ms - last_turn_dt.timestamp() * 1000) > 24 * 60 * 60 * 1000:
                continue
        except Exception:
            continue
        
        turns = c.get("turns", [])
        model_id = ""
        if turns:
            peak_turn = max(turns, key=lambda t: t.get("total_input_tokens", 0), default=None)
            peak_depth = peak_turn.get("total_input_tokens", 0) if peak_turn else 0
            model_id = (peak_turn.get("model_id") or peak_turn.get("model_name") or "") if peak_turn else ""
            if not model_id and c.get("models_used"):
                model_id = c.get("models_used", [""])[-1] or ""
        else:
            peak_depth = c.get("peak_prompt_depth") or (c.get("total_input_tokens", 0) / max(c.get("turn_count", 1), 1))
            if c.get("models_used"):
                model_id = c.get("models_used", [""])[-1] or ""
            
        thresh = get_model_compaction_threshold(model_id, census)
        nom_thresh = get_model_truncation_threshold(model_id, census)
        ratio = peak_depth / thresh if thresh > 0 else 0
        c_comp_count = int(c.get("compaction_count") or (1 if c.get("has_truncated") else 0))
        c_epoch = int(c.get("compaction_epoch") or ((c_comp_count + 1) if (c_comp_count > 0 or c.get("has_truncated")) else 1))

        is_curr = bool(current_session and c.get("convo_id") and c.get("convo_id") == current_session.get("convo_id"))
        sess_title = c.get("title") or c.get("convo_id", "Unknown Session")
        sess_branch = c.get("git_branch") or active_branch
        sess_ws = c.get("workspace_name") or active_project

        if c_epoch >= 3 or ratio >= 0.9:
            critical_count += 1
            degraded_count += 1
            degraded_sessions.append({
                "convo_id": c.get("convo_id", ""),
                "title": sess_title,
                "branch": sess_branch,
                "workspace": sess_ws,
                "tokens": int(peak_depth),
                "threshold": thresh,
                "nominal_threshold": nom_thresh,
                "compaction_threshold": thresh,
                "compaction_epoch": c_epoch,
                "severity": "critical",
                "is_current": is_curr,
            })
        elif c_epoch == 2 or ratio >= 0.75:
            degraded_count += 1
            degraded_sessions.append({
                "convo_id": c.get("convo_id", ""),
                "title": sess_title,
                "branch": sess_branch,
                "workspace": sess_ws,
                "tokens": int(peak_depth),
                "threshold": thresh,
                "nominal_threshold": nom_thresh,
                "compaction_threshold": thresh,
                "compaction_epoch": c_epoch,
                "severity": "warning",
                "is_current": is_curr,
            })
            
    # Sort degraded sessions by tokens descending
    degraded_sessions.sort(key=lambda x: x["tokens"], reverse=True)

    # Credit balance
    burned = s.get("total_ai_credits_burned", 0)
    pool = s.get("monthly_plan_credits", 5000)
    rem_credits = s.get("monthly_credits_remaining", max(0, pool - burned))
    rem_gbp = s.get("credit_bank_remaining_gbp", 0.0)
    credit_balance = f"{rem_credits:,} / {pool:,} credits (£{rem_gbp:.2f})"

    repo_root = Path(__file__).resolve().parent.parent
    dashboard_path = str(repo_root / "dashboard" / "index.html")

    status_data = {
        "status": status,
        "gemini_5h_pct": round(gem_5h_used, 1),
        "gemini_5h_remaining_pct": gem_5h_rem,
        "gemini_weekly_pct": round(gem_wk_used, 1),
        "gemini_weekly_remaining_pct": gem_wk_rem,
        "claude_5h_pct": round(cg_5h_used, 1),
        "claude_5h_remaining_pct": cg_5h_rem,
        "claude_weekly_pct": round(cg_wk_used, 1),
        "claude_weekly_remaining_pct": cg_wk_rem,
        "cooldown_active": cooldown,
        "weekly_reset_utc": gem_weekly.get("weekly_reset_utc", ""),
        "weekly_reset_desc": weekly_reset_desc,
        "gemini_5h_recovery_desc": gemini_5h_recovery_desc,
        "bvi": round(float(runway.get("bvi_bayes", runway.get("burn_velocity_index", 1.0))), 2),
        "bvi_verdict": runway.get("status_sub") or runway.get("status_text") or "On Track",
        "degraded_count": degraded_count,
        "critical_count": critical_count,
        "active_session_severity": active_session_severity,
        "compaction_epoch": epoch if current_session else 1,
        "active_agent_role": active_agent_role,
        "current_session": current_session,
        "active_swarms": active_swarms or [],
        "degraded_sessions": degraded_sessions,
        "plan_name": plan_name,
        "active_project": active_project,
        "active_branch": active_branch,
        "credit_balance": credit_balance,
        "dashboard_path": dashboard_path,
        "updated_at": payload.get("temporal", {}).get("resolved_at_utc") or payload.get("temporal", {}).get("evaluation_time_utc") or datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "recent_burn_rate_tok_per_min": payload.get("live_ticker", {}).get("burn_rate_tok_per_min", 0),
        "recent_burn_rate_tok_per_sec": payload.get("live_ticker", {}).get("burn_rate_tok_per_sec", 0.0),
        "last_turn_tokens": payload.get("live_ticker", {}).get("last_turn_tokens", 0),
        "last_turn_cache_pct": payload.get("live_ticker", {}).get("last_turn_cache_pct", 0.0),
        "last_turn_model": payload.get("live_ticker", {}).get("last_turn_model", ""),
        "last_turn_ts": payload.get("live_ticker", {}).get("last_turn_ts", ""),
        "is_streaming": payload.get("live_ticker", {}).get("is_streaming", False),
        "seconds_since_last_turn": payload.get("live_ticker", {}).get("seconds_since_last_turn", 999999),
        "gemini_5h_tokens": payload.get("live_ticker", {}).get("gemini_5h_tokens", 0),
        "last_turn_ttft_ms": payload.get("live_ticker", {}).get("last_turn_ttft_ms"),
        "last_turn_latency_ms": payload.get("live_ticker", {}).get("last_turn_latency_ms"),
        "session_median_ttft_ms": payload.get("live_ticker", {}).get("session_median_ttft_ms"),
        "kv_cache_wiped": payload.get("live_ticker", {}).get("kv_cache_wiped", False),
        "quota_regime": payload.get("quota_regime", {}),
        "watcher": None,
    }

    try:
        with status_file_lock(target):
            existing_watcher = None
            if watcher_info is None and not payload.get("watcher") and target.exists():
                try:
                    with open(target, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                    if isinstance(existing_data, dict) and isinstance(existing_data.get("watcher"), dict):
                        existing_watcher = existing_data["watcher"]
                except (json.JSONDecodeError, OSError) as e:
                    sys.stderr.write(f"[!] Warning: failed to read existing quota status at {target}: {e}\n")
                except Exception as e:
                    sys.stderr.write(f"[!] Unexpected error reading quota status: {e}\n")

            status_data["watcher"] = watcher_info or payload.get("watcher") or existing_watcher
            build_or_patch_status_tracks(status_data, payload=payload)
            atomic_write_text(target, json.dumps(status_data, indent=2, sort_keys=True) + "\n")
            return target
    except (PermissionError, OSError):
        if status_path is not None:
            raise
        return None


def compute_ticker_latency_fields(
    payload: dict,
    all_turns: List[dict],
) -> dict:
    """
    Compute live ticker TTFT, latency, session median TTFT, and KV cache wipe state (Milestone 94).
    """
    import statistics

    conversations = payload.get("conversations", [])
    current_sess = payload.get("current_session")
    active_cid = current_sess.get("convo_id") if current_sess else None
    if not active_cid and conversations:
        active_cid = conversations[0].get("convo_id")

    active_turns: List[dict] = []
    for c in conversations:
        if c.get("convo_id") == active_cid:
            active_turns = c.get("turns", [])
            break

    latest_turn = None
    if all_turns:
        latest_turn = max(
            all_turns,
            key=lambda t: (t.get("timestamp") or "", t.get("step_idx") or 0),
            default=None,
        )

    last_ttft = latest_turn.get("ttft_ms") if latest_turn else None
    last_lat = latest_turn.get("latency_ms") if latest_turn else None

    session_median_ttft = None
    if active_turns:
        valid_ttfts = [
            float(t["ttft_ms"])
            for t in active_turns
            if t.get("ttft_ms") is not None and float(t["ttft_ms"]) > 0
        ]
        if valid_ttfts:
            session_median_ttft = round(statistics.median(valid_ttfts), 2)
    elif all_turns and last_ttft is not None and last_ttft > 0:
        session_median_ttft = last_ttft

    kv_cache_wiped = False
    if latest_turn:
        cid = latest_turn.get("convo_id") or active_cid
        target_convo_turns = []
        for c in conversations:
            if c.get("convo_id") == cid:
                target_convo_turns = c.get("turns", [])
                break
        if not target_convo_turns and active_turns:
            target_convo_turns = active_turns

        sorted_c_turns = sorted(
            target_convo_turns,
            key=lambda t: (t.get("timestamp") or "", t.get("step_idx") or 0),
        )

        curr_idx = None
        for i, t in enumerate(sorted_c_turns):
            if t.get("step_idx") == latest_turn.get("step_idx") and t.get("timestamp") == latest_turn.get("timestamp"):
                curr_idx = i
                break

        if curr_idx is not None and curr_idx > 0:
            prev_t = sorted_c_turns[curr_idx - 1]
            raw_prev = str(prev_t.get("model_id") or prev_t.get("model_name") or "")
            raw_curr = str(latest_turn.get("model_id") or latest_turn.get("model_name") or "")
            prev_mid = (resolve_wire_model_id(raw_prev) or raw_prev) if raw_prev else ""
            curr_mid = (resolve_wire_model_id(raw_curr) or raw_curr) if raw_curr else ""
            total_inp = latest_turn.get("total_input_tokens") or (
                (latest_turn.get("prompt_tokens_uncached") or 0) + (latest_turn.get("cached_tokens") or 0)
            )
            cached_tok = latest_turn.get("cached_tokens") or 0
            if (
                prev_mid
                and curr_mid
                and prev_mid != curr_mid
                and total_inp >= 40000
                and (cached_tok / total_inp) < 0.20
            ):
                kv_cache_wiped = True

    return {
        "last_turn_ttft_ms": last_ttft,
        "last_turn_latency_ms": last_lat,
        "session_median_ttft_ms": session_median_ttft,
        "kv_cache_wiped": kv_cache_wiped,
    }


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


_IN_MEMORY_CONVO_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_ANTIGRAVITY_DIR: Optional[str] = None
_FAST_QUOTA_CACHE: Dict[str, Any] = {
    "polled_at": 0.0,
    "live_quota": None,
}
_IN_MEMORY_VAULT_CACHE: Dict[str, Any] = {
    "vault_path": None,
    "fingerprint": None,
    "pricing_hash": None,
    "swarms_list": None,
    "swarms_summary": None,
    "tool_analytics": None,
    "vault_truncations": None,
    "parent_child_counts": None,
    "prompts_by_convo": None,
    "tool_calls_by_convo": None,
    "modes_summary": None,
    "horizon_analytics": None,
}


def clear_exporter_cache() -> None:
    """Clear in-process memory caches and reset state (useful for tests and forced scans)."""
    global _IN_MEMORY_CONVO_CACHE, _IN_MEMORY_VAULT_CACHE, _CACHE_ANTIGRAVITY_DIR, _FAST_QUOTA_CACHE
    _IN_MEMORY_CONVO_CACHE.clear()
    _CACHE_ANTIGRAVITY_DIR = None
    _FAST_QUOTA_CACHE = {
        "polled_at": 0.0,
        "live_quota": None,
    }
    _IN_MEMORY_VAULT_CACHE = {
        "vault_path": None,
        "fingerprint": None,
        "pricing_hash": None,
        "swarms_list": None,
        "swarms_summary": None,
        "tool_analytics": None,
        "vault_truncations": None,
        "parent_child_counts": None,
        "prompts_by_convo": None,
        "tool_calls_by_convo": None,
        "modes_summary": None,
        "horizon_analytics": None,
    }


def get_cache_db_path(dashboard_dir: Path) -> Path:
    """Path to SQLite-backed persistent export cache."""
    return Path(dashboard_dir) / ".export_cache.db"


def init_export_cache_db(cache_path: Path) -> sqlite3.Connection:
    """Initialize SQLite export cache with WAL mode and resilient tables."""
    conn = sqlite3.connect(str(cache_path), timeout=60.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 60000;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_cache (
            convo_id TEXT PRIMARY KEY,
            db_path TEXT,
            mtime_ns INTEGER,
            size_bytes INTEGER,
            meta_json TEXT,
            raw_turns_json TEXT,
            summary_json TEXT,
            pricing_hash TEXT,
            intervals_hash TEXT,
            updated_at REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vault_cache (
            key TEXT PRIMARY KEY,
            vault_path TEXT,
            mtime_ns INTEGER,
            size_bytes INTEGER,
            pricing_hash TEXT,
            payload_json TEXT,
            updated_at REAL
        )
    """)
    conn.commit()
    return conn


def get_cache_connection(cache_path: Path) -> Optional[sqlite3.Connection]:
    """Safely connect to SQLite export cache, self-healing corruption if needed."""
    try:
        return init_export_cache_db(cache_path)
    except (sqlite3.DatabaseError, OSError) as e:
        sys.stderr.write(f"[!] Warning: export cache DB corrupt or inaccessible ({e}), recreating...\n")
        try:
            if cache_path.exists():
                cache_path.unlink()
            for suffix in ("-wal", "-shm"):
                sidecar = cache_path.parent / f"{cache_path.name}{suffix}"
                if sidecar.exists():
                    sidecar.unlink()
            return init_export_cache_db(cache_path)
        except Exception as exc:
            sys.stderr.write(f"[!] Warning: failed to recreate export cache DB: {exc}\n")
            return None


def compute_config_hash(obj: Any) -> str:
    """Compute deterministic SHA-256 digest of config dictionary or list."""
    try:
        raw = json.dumps(obj, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    except Exception:
        return "default"


def get_conversation_db_fingerprint(db_path: Union[Path, str]) -> Optional[Tuple[int, int]]:
    """Return (effective_mtime_ns, effective_size_bytes) for db + wal."""
    try:
        p = Path(db_path)
        st = p.stat()
        mtime_ns = st.st_mtime_ns
        size_bytes = st.st_size
        wal_path = p.parent / f"{p.name}-wal"
        if wal_path.exists():
            try:
                wal_st = wal_path.stat()
                mtime_ns = max(mtime_ns, wal_st.st_mtime_ns)
                size_bytes += wal_st.st_size
            except OSError:
                pass
        return (mtime_ns, size_bytes)
    except OSError:
        return None


def _copy_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Shallow copy summary and its turns list to prevent cache mutations."""
    res = dict(summary)
    if "turns" in summary and isinstance(summary["turns"], list):
        res["turns"] = [dict(t) for t in summary["turns"]]
    return res


def load_incremental_conversations(
    antigravity_dir: Union[Path, str],
    pricing: Dict[str, Any],
    exhaustion_intervals: Optional[List[Dict[str, Any]]] = None,
    dashboard_dir: Optional[Path] = None,
    max_conversations: Optional[int] = None,
    force_full_scan: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int]:
    """
    Incrementally load conversations using mtime/size fingerprints.
    Returns: (convo_summaries, all_turns, discovered_count, scanned_count)
    """
    global _IN_MEMORY_CONVO_CACHE, _CACHE_ANTIGRAVITY_DIR

    conv_dir = Path(antigravity_dir) / "conversations"
    if not conv_dir.exists():
        return [], [], 0, 0

    resolved_conv = str(conv_dir.resolve())
    if _CACHE_ANTIGRAVITY_DIR != resolved_conv:
        _IN_MEMORY_CONVO_CACHE.clear()
        _CACHE_ANTIGRAVITY_DIR = resolved_conv

    if force_full_scan:
        clear_exporter_cache()

    # 1. Fast stat scan across all DBs + WALs (~5-8ms across 500+ DBs)
    discovered_entries = []
    try:
        for entry in os.scandir(conv_dir):
            if entry.name.endswith(".db") and entry.is_file():
                try:
                    st = entry.stat()
                    mtime_ns = st.st_mtime_ns
                    size_bytes = st.st_size
                    wal_path = conv_dir / f"{entry.name}-wal"
                    if wal_path.exists():
                        try:
                            wal_st = wal_path.stat()
                            mtime_ns = max(mtime_ns, wal_st.st_mtime_ns)
                            size_bytes += wal_st.st_size
                        except OSError:
                            pass
                    discovered_entries.append((mtime_ns, size_bytes, entry.name, Path(entry.path)))
                except OSError:
                    continue
    except OSError:
        pass

    # Sort descending by mtime_ns, with entry.name as tie-breaker
    discovered_entries.sort(key=lambda x: (x[0], x[2]), reverse=True)
    discovered_count = len(discovered_entries)
    if max_conversations is not None:
        target_entries = discovered_entries[:max_conversations]
    else:
        target_entries = discovered_entries
    scanned_count = len(target_entries)

    pricing_hash = compute_config_hash(pricing)
    intervals_hash = compute_config_hash(exhaustion_intervals)

    # 2. Connect to SQLite persistent cache if available
    cache_conn = None
    if dashboard_dir is not None:
        cache_conn = get_cache_connection(get_cache_db_path(dashboard_dir))

    # Pre-populate in-memory cache from SQLite cache only when missing target IDs
    missing_cache_ids = [
        entry[3].stem for entry in target_entries
        if entry[3].stem not in _IN_MEMORY_CONVO_CACHE
    ]
    if cache_conn is not None and not force_full_scan and missing_cache_ids:
        try:
            cur = cache_conn.cursor()
            if len(missing_cache_ids) <= 50:
                placeholders = ",".join("?" for _ in missing_cache_ids)
                rows_iter = cur.execute(
                    f"SELECT convo_id, db_path, mtime_ns, size_bytes, meta_json, CASE WHEN summary_json IS NULL THEN raw_turns_json ELSE NULL END, summary_json, pricing_hash, intervals_hash FROM conversation_cache WHERE convo_id IN ({placeholders})",
                    missing_cache_ids,
                )
            else:
                rows_iter = cur.execute(
                    "SELECT convo_id, db_path, mtime_ns, size_bytes, meta_json, CASE WHEN summary_json IS NULL THEN raw_turns_json ELSE NULL END, summary_json, pricing_hash, intervals_hash FROM conversation_cache"
                )
            for row in rows_iter:
                try:
                    cid, db_p, mt, sz, m_json, r_json, s_json, p_h, i_h = row
                    if cid not in _IN_MEMORY_CONVO_CACHE:
                        parsed_sum = json.loads(s_json) if s_json else None
                        _IN_MEMORY_CONVO_CACHE[cid] = {
                            "fingerprint": (mt, sz),
                            "db_path": db_p,
                            "meta": json.loads(m_json) if m_json else {},
                            "raw_turns": (json.loads(r_json) if r_json else []) if parsed_sum is None else None,
                            "summary": parsed_sum,
                            "pricing_hash": p_h,
                            "intervals_hash": i_h,
                        }
                except Exception:
                    continue
        except Exception as exc:
            sys.stderr.write(f"[!] Warning: error reading conversation cache: {exc}\n")

    # Prune conversations that no longer exist
    current_ids = {entry[3].stem for entry in discovered_entries}
    stale_ids = [cid for cid in _IN_MEMORY_CONVO_CACHE if cid not in current_ids]
    for sid in stale_ids:
        _IN_MEMORY_CONVO_CACHE.pop(sid, None)
    if cache_conn is not None and stale_ids:
        try:
            cache_conn.executemany("DELETE FROM conversation_cache WHERE convo_id = ?", [(sid,) for sid in stale_ids])
            cache_conn.commit()
        except Exception:
            pass

    workspace_mapping = None
    convo_summaries = []
    all_turns = []
    to_persist = []

    for mtime_ns, size_bytes, filename, db_path in target_entries:
        convo_id = db_path.stem
        cached = _IN_MEMORY_CONVO_CACHE.get(convo_id)

        if not force_full_scan and cached and cached.get("fingerprint") == (mtime_ns, size_bytes):
            # Cache HIT
            meta = cached["meta"]
            cached_sum = cached.get("summary")
            if isinstance(meta, dict) and str(meta.get("title") or "").startswith("Conversation "):
                fresh_title = get_conversation_title(convo_id, antigravity_dir)
                if fresh_title and not fresh_title.startswith("Conversation "):
                    meta["title"] = fresh_title
                    if isinstance(cached_sum, dict):
                        cached_sum["title"] = fresh_title
            raw_turns = cached.get("raw_turns")
            if not raw_turns and cached_sum is not None:
                raw_turns = cached_sum.get("turns", [])
            if (
                cached_sum is not None
                and cached.get("pricing_hash") == pricing_hash
                and cached.get("intervals_hash") == intervals_hash
            ):
                summary = _copy_summary(cached_sum)
                raw_turns = summary.get("turns", [])
            else:
                if not raw_turns and db_path.exists():
                    raw_turns = read_conversation_turns(db_path)
                if raw_turns:
                    summary = aggregate_conversation_telemetry(meta, raw_turns, pricing, exhaustion_intervals=exhaustion_intervals)
                    cached["summary"] = _copy_summary(summary)
                    cached["raw_turns"] = None
                    cached["pricing_hash"] = pricing_hash
                    cached["intervals_hash"] = intervals_hash
                    to_persist.append((
                        convo_id,
                        str(db_path),
                        mtime_ns,
                        size_bytes,
                        json.dumps(meta),
                        json.dumps(raw_turns),
                        json.dumps(summary),
                        pricing_hash,
                        intervals_hash,
                        time.time(),
                    ))
                else:
                    summary = None
        else:
            # Cache MISS: read single conversation from SQLite DB
            if workspace_mapping is None:
                workspace_mapping = get_workspace_mapping(antigravity_dir)

            auth_meta = read_single_conversation_metadata(db_path)
            ws_name = auth_meta.get("workspace_name")
            if not ws_name or ws_name == "Unknown Workspace":
                ws_name = workspace_mapping.get(convo_id, "Unknown Workspace")

            meta = {
                "convo_id": convo_id,
                "db_path": str(db_path),
                "title": get_conversation_title(convo_id, antigravity_dir),
                "workspace": ws_name,
                "workspace_path": auth_meta.get("workspace_path", ""),
                "workspace_name": ws_name,
                "git_branch": auth_meta.get("git_branch", "main"),
                "last_modified": mtime_ns / 1e9,
                "size_bytes": size_bytes,
                "agent_name": auth_meta.get("agent_name", "default"),
                "agent_description": auth_meta.get("agent_description", ""),
                "agent_config_uri": auth_meta.get("agent_config_uri", ""),
                "is_subagent": auth_meta.get("is_subagent", False),
                "parent_convo_id": auth_meta.get("parent_convo_id", ""),
                "subagent_type": auth_meta.get("subagent_type", ""),
                "subagent_role": auth_meta.get("subagent_role", ""),
            }
            raw_turns = read_conversation_turns(db_path)
            if raw_turns:
                summary = aggregate_conversation_telemetry(meta, raw_turns, pricing, exhaustion_intervals=exhaustion_intervals)
            else:
                summary = None

            _IN_MEMORY_CONVO_CACHE[convo_id] = {
                "fingerprint": (mtime_ns, size_bytes),
                "db_path": str(db_path),
                "meta": meta,
                "raw_turns": None if summary is not None else raw_turns,
                "summary": _copy_summary(summary) if summary is not None else None,
                "pricing_hash": pricing_hash,
                "intervals_hash": intervals_hash,
            }
            to_persist.append((
                convo_id,
                str(db_path),
                mtime_ns,
                size_bytes,
                json.dumps(meta),
                json.dumps(raw_turns),
                json.dumps(summary) if summary else None,
                pricing_hash,
                intervals_hash,
                time.time(),
            ))

        if summary is not None:
            convo_summaries.append(summary)
            if raw_turns:
                all_turns.extend(raw_turns)

    if cache_conn is not None and to_persist:
        try:
            cache_conn.executemany("""
                INSERT OR REPLACE INTO conversation_cache
                (convo_id, db_path, mtime_ns, size_bytes, meta_json, raw_turns_json, summary_json, pricing_hash, intervals_hash, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, to_persist)
            cache_conn.commit()
        except Exception as exc:
            sys.stderr.write(f"[!] Warning: failed to persist to export cache: {exc}\n")

    if cache_conn is not None:
        try:
            cache_conn.close()
        except Exception:
            pass

    return convo_summaries, all_turns, discovered_count, scanned_count


def _get_vault_logical_fingerprint(vault_file: Path) -> Optional[Tuple[int, int]]:
    """
    Compute a fast (<1ms) logical content fingerprint of conversations, steps, and tool calls
    in vault_file so non-conversation table writes (e.g. quota_snapshots_archive, weekly_cycles_archive)
    do not falsely invalidate vault_analytics or horizon_analytics caches.
    """
    if not vault_file.exists():
        return None
    conn = None
    try:
        conn = sqlite3.connect(f"file:{vault_file}?mode=ro", uri=True, timeout=5.0)
        cur = conn.cursor()
        s_max_rowid = (cur.execute("SELECT COALESCE(MAX(rowid), 0) FROM steps_archive").fetchone() or [0])[0]
        c_cnt = 0
        c_max_ts = ""
        try:
            c_cnt, c_max_ts = cur.execute(
                "SELECT COUNT(*), COALESCE(MAX(synced_at), '') FROM conversations_archive"
            ).fetchone() or (0, "")
        except sqlite3.Error:
            pass
        t_max_id = 0
        try:
            t_max_id = (cur.execute("SELECT COALESCE(MAX(id), 0) FROM tool_calls_archive").fetchone() or [0])[0]
        except sqlite3.Error:
            pass
        sync_mtime = ""
        try:
            row_m = cur.execute(
                "SELECT value FROM vault_sync_state WHERE key = 'conversations_last_sync_mtime'"
            ).fetchone()
            if row_m and row_m[0]:
                sync_mtime = str(row_m[0])
        except sqlite3.Error:
            pass
        digest_str = f"{s_max_rowid}:{c_cnt}:{c_max_ts}:{t_max_id}:{sync_mtime}"
        h = int(hashlib.sha256(digest_str.encode("utf-8")).hexdigest()[:15], 16)
        return (int(s_max_rowid) * 1_000_000 + int(c_cnt), h)
    except (sqlite3.Error, OSError):
        try:
            v_st = vault_file.stat()
            v_mtime = v_st.st_mtime_ns
            v_size = v_st.st_size
            v_wal = vault_file.parent / f"{vault_file.name}-wal"
            if v_wal.exists():
                try:
                    w_st = v_wal.stat()
                    v_mtime = max(v_mtime, w_st.st_mtime_ns)
                    v_size += w_st.st_size
                except OSError:
                    pass
            return (v_mtime, v_size)
        except OSError:
            return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass


def load_vault_analytics_cached(
    vault_file: Path,
    pricing: Dict[str, Any],
    cache_conn: Optional[sqlite3.Connection] = None,
    force_full_scan: bool = False,
    vault_synced_rows: bool = False,
) -> Dict[str, Any]:
    """
    Load or retrieve cached vault analytics.
    Returns dict:
      swarms_list, swarms_summary, tool_analytics, vault_truncations,
      parent_child_counts, prompts_by_convo, tool_calls_by_convo
    """
    global _IN_MEMORY_VAULT_CACHE

    if not vault_file.exists():
        empty_swarms = extract_swarm_lineage(vault_path=vault_file, pricing_models=pricing)
        empty_summary = build_swarms_summary(empty_swarms, pricing_models=pricing)
        empty_tools = extract_tool_analytics(vault_path=vault_file)
        return {
            "swarms_list": empty_swarms,
            "swarms_summary": empty_summary,
            "tool_analytics": empty_tools,
            "vault_truncations": {},
            "parent_child_counts": {},
            "prompts_by_convo": {},
            "tool_calls_by_convo": {},
        }

    v_fp = _get_vault_logical_fingerprint(vault_file)
    if v_fp is None:
        empty_swarms = extract_swarm_lineage(vault_path=vault_file, pricing_models=pricing)
        empty_summary = build_swarms_summary(empty_swarms, pricing_models=pricing)
        empty_tools = extract_tool_analytics(vault_path=vault_file)
        return {
            "swarms_list": empty_swarms,
            "swarms_summary": empty_summary,
            "tool_analytics": empty_tools,
            "vault_truncations": {},
            "parent_child_counts": {},
            "prompts_by_convo": {},
            "tool_calls_by_convo": {},
        }

    is_mocked = hasattr(extract_swarm_lineage, "mock_calls") or hasattr(extract_tool_analytics, "mock_calls")
    p_hash = compute_config_hash(pricing)

    # 1. In-memory cache hit
    if (
        not force_full_scan
        and not vault_synced_rows
        and _IN_MEMORY_VAULT_CACHE.get("vault_path") == str(vault_file)
        and _IN_MEMORY_VAULT_CACHE.get("fingerprint") == v_fp
        and _IN_MEMORY_VAULT_CACHE.get("pricing_hash") == p_hash
        and _IN_MEMORY_VAULT_CACHE.get("swarms_list") is not None
    ):
        if is_mocked:
            s_list = extract_swarm_lineage(vault_path=vault_file, pricing_models=pricing)
            s_sum = build_swarms_summary(s_list, pricing_models=pricing)
            t_ana = extract_tool_analytics(vault_path=vault_file)
            return {
                "swarms_list": s_list,
                "swarms_summary": s_sum,
                "tool_analytics": t_ana,
                "vault_truncations": _IN_MEMORY_VAULT_CACHE["vault_truncations"],
                "parent_child_counts": dict(_IN_MEMORY_VAULT_CACHE["parent_child_counts"]),
                "prompts_by_convo": _IN_MEMORY_VAULT_CACHE.get("prompts_by_convo") or {},
                "tool_calls_by_convo": _IN_MEMORY_VAULT_CACHE.get("tool_calls_by_convo") or {},
            }
        return {
            "swarms_list": _IN_MEMORY_VAULT_CACHE["swarms_list"],
            "swarms_summary": _IN_MEMORY_VAULT_CACHE["swarms_summary"],
            "tool_analytics": _IN_MEMORY_VAULT_CACHE["tool_analytics"],
            "vault_truncations": _IN_MEMORY_VAULT_CACHE["vault_truncations"],
            "parent_child_counts": dict(_IN_MEMORY_VAULT_CACHE["parent_child_counts"]),
            "prompts_by_convo": _IN_MEMORY_VAULT_CACHE.get("prompts_by_convo") or {},
            "tool_calls_by_convo": _IN_MEMORY_VAULT_CACHE.get("tool_calls_by_convo") or {},
        }

    # 2. Persistent SQLite cache hit
    if not force_full_scan and not is_mocked and not vault_synced_rows:
        candidate_conns = []
        if cache_conn is not None:
            candidate_conns.append((cache_conn, False))
        default_cache_db = get_cache_db_path(REPO_ROOT / "dashboard")
        if vault_file == DEFAULT_VAULT_PATH and default_cache_db.exists():
            try:
                ro_conn = sqlite3.connect(f"file:{default_cache_db}?mode=ro", uri=True, timeout=5.0)
                candidate_conns.append((ro_conn, True))
            except sqlite3.Error:
                pass
        for c_conn, should_close in candidate_conns:
            try:
                cur = c_conn.cursor()
                cur.execute("SELECT mtime_ns, size_bytes, pricing_hash, payload_json FROM vault_cache WHERE key = 'vault_analytics'")
                row = cur.fetchone()
                if row and row[0] == v_fp[0] and row[1] == v_fp[1] and row[2] == p_hash:
                    data = json.loads(row[3])
                    v_truncs = {}
                    for cid, m in data.get("vault_truncations", {}).items():
                        v_truncs[cid] = VaultMarker(m[0], m[1], m[2])
                    res = {
                        "swarms_list": data.get("swarms_list", []),
                        "swarms_summary": data.get("swarms_summary") or build_swarms_summary([], pricing_models=pricing),
                        "tool_analytics": data.get("tool_analytics") or {},
                        "vault_truncations": v_truncs,
                        "parent_child_counts": data.get("parent_child_counts", {}),
                        "prompts_by_convo": data.get("prompts_by_convo", {}),
                        "tool_calls_by_convo": data.get("tool_calls_by_convo", {}),
                    }
                    _IN_MEMORY_VAULT_CACHE["vault_path"] = str(vault_file)
                    _IN_MEMORY_VAULT_CACHE["fingerprint"] = v_fp
                    _IN_MEMORY_VAULT_CACHE["pricing_hash"] = p_hash
                    _IN_MEMORY_VAULT_CACHE.update(res)
                    res["parent_child_counts"] = dict(res["parent_child_counts"])
                    return res
            except Exception as exc:
                if not should_close:
                    sys.stderr.write(f"[!] Warning: failed reading vault cache: {exc}\n")
            finally:
                if should_close:
                    try:
                        c_conn.close()
                    except sqlite3.Error:
                        pass

    # 3. Cache MISS: query vault directly
    swarms_list = extract_swarm_lineage(vault_path=vault_file, pricing_models=pricing)
    swarms_summary = build_swarms_summary(swarms_list, pricing_models=pricing)
    tool_analytics = extract_tool_analytics(vault_path=vault_file)
    vault_truncations = get_vault_truncation_markers(vault_path=vault_file)

    parent_child_counts = {}
    prompts_by_convo = {}
    tool_calls_by_convo = {}
    vconn = None
    try:
        vconn = sqlite3.connect(f"file:{vault_file}?mode=ro", uri=True, timeout=60.0)
        vconn.execute("PRAGMA busy_timeout = 60000;")
        vcur = vconn.cursor()
        try:
            for pid, count in vcur.execute(
                "SELECT parent_convo_id, COUNT(*) FROM conversations_archive WHERE parent_convo_id IS NOT NULL AND parent_convo_id != '' GROUP BY parent_convo_id"
            ):
                parent_child_counts[pid] = count
        except sqlite3.Error as e:
            sys.stderr.write(f"[!] Warning: subagent correlation query failed: {e}\n")

        try:
            for cid_val, p_text in vcur.execute(
                "SELECT convo_id, payload_text FROM steps_archive WHERE step_type = 14 AND payload_text IS NOT NULL AND payload_text != ''"
            ):
                prompts_by_convo.setdefault(cid_val, []).append(p_text)
        except sqlite3.Error as e:
            logger.debug("steps_archive prompt query skipped: %s", e, exc_info=True)

        try:
            for cid_val, t_name, target_path, fallback_args_json in vcur.execute(
                """
                SELECT convo_id, tool_name,
                       CASE WHEN json_valid(arguments_json) THEN
                           COALESCE(
                               json_extract(arguments_json, '$.TargetFile'),
                               json_extract(arguments_json, '$.target_file'),
                               json_extract(arguments_json, '$.Path'),
                               json_extract(arguments_json, '$.file_path'),
                               json_extract(arguments_json, '$.path'),
                               json_extract(arguments_json, '$.filename')
                           )
                       ELSE NULL END AS target_path,
                       CASE WHEN NOT json_valid(arguments_json)
                              OR json_type(arguments_json, '$.TargetFiles') IS NOT NULL
                              OR json_type(arguments_json, '$.files') IS NOT NULL
                            THEN arguments_json
                            ELSE NULL END AS fallback_args_json
                FROM tool_calls_archive
                WHERE tool_name IN ('replace_file_content', 'write_to_file', 'multi_replace_file_content', 'write_file', 'edit_file')
                """
            ):
                if isinstance(target_path, str) and target_path.strip():
                    tool_calls_by_convo.setdefault(cid_val, []).append({"tool_name": t_name, "TargetFile": target_path.strip()})
                if fallback_args_json is not None:
                    for p in _extract_file_paths_from_tool_call({"tool_name": t_name, "arguments_json": fallback_args_json}):
                        if not (isinstance(target_path, str) and p == target_path.strip()):
                            tool_calls_by_convo.setdefault(cid_val, []).append({"tool_name": t_name, "TargetFile": p})
        except sqlite3.Error as e:
            logger.debug("tool_calls_archive file-churn query skipped: %s", e, exc_info=True)
    except (sqlite3.Error, OSError) as e:
        sys.stderr.write(f"[!] Warning: vault analytics read-only query failed: {e}\n")
    finally:
        if vconn is not None:
            try:
                vconn.close()
            except sqlite3.Error:
                pass

    trunc_serializable = {
        cid: [m[0], m[1], getattr(m, "compaction_count", 1)]
        for cid, m in vault_truncations.items()
    }
    payload_to_store = {
        "swarms_list": swarms_list,
        "swarms_summary": swarms_summary,
        "tool_analytics": tool_analytics,
        "vault_truncations": trunc_serializable,
        "parent_child_counts": parent_child_counts,
        "prompts_by_convo": prompts_by_convo,
        "tool_calls_by_convo": tool_calls_by_convo,
    }

    if not is_mocked:
        if cache_conn is not None:
            try:
                cache_conn.execute("""
                    INSERT OR REPLACE INTO vault_cache
                    (key, vault_path, mtime_ns, size_bytes, pricing_hash, payload_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, ("vault_analytics", str(vault_file), v_fp[0], v_fp[1], p_hash, json.dumps(payload_to_store), time.time()))
                cache_conn.commit()
            except Exception as exc:
                sys.stderr.write(f"[!] Warning: failed persisting vault cache to SQLite: {exc}\n")

        _IN_MEMORY_VAULT_CACHE["vault_path"] = str(vault_file)
        _IN_MEMORY_VAULT_CACHE["fingerprint"] = v_fp
        _IN_MEMORY_VAULT_CACHE["pricing_hash"] = p_hash
        _IN_MEMORY_VAULT_CACHE.update(payload_to_store)
        _IN_MEMORY_VAULT_CACHE["vault_truncations"] = vault_truncations

    return {
        "swarms_list": swarms_list,
        "swarms_summary": swarms_summary,
        "tool_analytics": tool_analytics,
        "vault_truncations": vault_truncations,
        "parent_child_counts": dict(parent_child_counts),
        "prompts_by_convo": prompts_by_convo,
        "tool_calls_by_convo": tool_calls_by_convo,
    }


def _apply_truncation_markers_to_conversations(
    conversations: List[Dict[str, Any]],
    vault_truncations: Dict[str, Any],
    vault_available: bool,
    antigravity_dir: Path,
    probe_live_recent_limit: int = 0,
) -> None:
    """Populate has_truncated, compaction_count, compaction_epoch, and depth_at_truncation on conversation dicts."""
    for idx, convo in enumerate(conversations):
        cid = convo.get("convo_id", "")
        if not convo.get("peak_prompt_depth"):
            convo["peak_prompt_depth"] = max(
                (t.get("total_input_tokens", 0) for t in convo.get("turns", [])),
                default=0,
            )

        applied = False
        if vault_available and cid in vault_truncations:
            v_res = vault_truncations[cid]
            fmark, depth = v_res[0], v_res[1]
            v_comp_count = getattr(v_res, "compaction_count", 1)
            comp_count = v_comp_count
            if idx < probe_live_recent_limit:
                db_path = Path(convo["db_path"]) if "db_path" in convo else (antigravity_dir / "conversations" / f"{cid}.db")
                t_res = scan_conversation_truncation(db_path)
                if t_res[0]:
                    live_count = getattr(t_res, "compaction_count", 1)
                    if live_count > comp_count:
                        comp_count = live_count
            convo["has_truncated"] = True
            convo["compaction_count"] = comp_count
            convo["compaction_epoch"] = getattr(v_res, "epoch", comp_count + 1) if comp_count == v_comp_count else (comp_count + 1)
            convo["first_truncation_step"] = fmark
            convo["depth_at_truncation"] = depth if (depth is not None and depth > 0) else max(convo.get("peak_prompt_depth", 0), 1)
            applied = True
        elif not vault_available or idx < probe_live_recent_limit:
            db_path = Path(convo["db_path"]) if "db_path" in convo else (antigravity_dir / "conversations" / f"{cid}.db")
            t_res = scan_conversation_truncation(db_path)
            has_trunc, fmark, depth = t_res[0], t_res[1], t_res[2]
            if has_trunc:
                comp_count = getattr(t_res, "compaction_count", 1)
                convo["has_truncated"] = True
                convo["compaction_count"] = comp_count
                convo["compaction_epoch"] = getattr(t_res, "epoch", comp_count + 1)
                convo["first_truncation_step"] = fmark
                convo["depth_at_truncation"] = depth if (depth is not None and depth > 0) else max(convo.get("peak_prompt_depth", 0), 1)
                applied = True

        if not applied:
            convo["has_truncated"] = False
            convo["compaction_count"] = 0
            convo["compaction_epoch"] = 1
            convo["first_truncation_step"] = None
            convo["depth_at_truncation"] = None


def _export_telemetry_impl(
    antigravity_dir: Path = DEFAULT_ANTIGRAVITY_DIR,
    dashboard_path: Path = REPO_ROOT / "dashboard" / "index.html",
    log_path: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
    max_conversations: Optional[int] = None,
    dry_run: bool = False,
    embed: bool = False,
    status_path: Optional[Path] = None,
    no_live_quota: bool = False,
    reference_time: Optional[datetime.datetime] = None,
    output_dir: Optional[Path] = None,
    force_full_scan: bool = False,
) -> dict:
    t_start = time.time()
    pricing = load_pricing()
    census = load_model_census()
    pricing_models = pricing
    for mid, cinfo in census.items():
        if mid in pricing_models:
            pricing_models[mid]["context_truncation_tokens"] = cinfo.get("context_truncation_tokens", 200000)

    antigravity_dir = Path(antigravity_dir)
    is_custom_dir = antigravity_dir.resolve() != DEFAULT_ANTIGRAVITY_DIR.resolve()
    if is_custom_dir:
        if log_path is None:
            log_path = antigravity_dir / "language_server.log"
        if ledger_path is None:
            ledger_path = antigravity_dir / "exhaustion_ledger.json"
    else:
        if log_path is None:
            log_path = DEFAULT_LOG_PATH
        if ledger_path is None:
            ledger_path = DEFAULT_LEDGER_PATH
    if log_path is not None:
        log_path = Path(log_path)
    if ledger_path is not None:
        ledger_path = Path(ledger_path)

    exhaustion_intervals = extract_exhaustion_intervals(log_path=log_path, ledger_path=ledger_path)

    cache_dir = Path(output_dir) if output_dir is not None else (dashboard_path.parent if dashboard_path is not None else REPO_ROOT / "dashboard")
    cache_dir.mkdir(parents=True, exist_ok=True)
    convo_summaries, all_turns, discovered_count, scanned_count = load_incremental_conversations(
        antigravity_dir=antigravity_dir,
        pricing=pricing,
        exhaustion_intervals=exhaustion_intervals,
        dashboard_dir=cache_dir,
        max_conversations=max_conversations,
        force_full_scan=force_full_scan,
    )

    # Vault resolution (resolved prior to live quota fallback and global aggregation)
    vault_file = _resolve_vault_file_for_dir(antigravity_dir, is_custom_dir)

    # Live desktop quota synchronization when targeting default Antigravity installation
    live_quota = None
    if not no_live_quota and not is_custom_dir:
        try:
            from src.quota_client import fetch_live_quota_summary
            live_quota = fetch_live_quota_summary()
            if live_quota:
                _FAST_QUOTA_CACHE["polled_at"] = time.time()
                _FAST_QUOTA_CACHE["live_quota"] = live_quota
        except Exception:
            live_quota = None

    # Fall back to last non-expired Vault snapshot when live RPC is temporarily unreachable
    if not no_live_quota and live_quota is None:
        live_quota = _load_vault_quota_fallback_for_dir(
            vault_file,
            antigravity_dir,
            is_custom_dir,
            reference_time,
            label="Vault",
        )

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
        include_horizon_analytics=not vault_file.exists(),
    )
    if "temporal" in payload and isinstance(payload["temporal"], dict) and "models" in payload["temporal"]:
        for mid, cinfo in census.items():
            if mid in payload["temporal"]["models"]:
                payload["temporal"]["models"][mid]["context_truncation_tokens"] = cinfo.get("context_truncation_tokens", 200000)
    payload["pricing_models"] = pricing
    payload["catalog"] = build_export_catalog(pricing)

    # Early executive quota status hook write so Mac menu bar receives quota/429 state before Vault sync
    ticker_lat_early = compute_ticker_latency_fields(payload, all_turns)
    if "live_ticker" not in payload or not isinstance(payload["live_ticker"], dict):
        payload["live_ticker"] = {}
    payload["live_ticker"].update(ticker_lat_early)

    if status_path is not None and not dry_run:
        try:
            early_vault_avail = vault_file.exists()
            early_truncs: Dict[str, Any] = {}
            if early_vault_avail:
                cached_vt = _IN_MEMORY_VAULT_CACHE.get("vault_truncations")
                if cached_vt is not None and _IN_MEMORY_VAULT_CACHE.get("vault_path") == str(vault_file):
                    early_truncs = cached_vt
                else:
                    early_truncs = get_vault_truncation_markers(vault_file)
            _apply_truncation_markers_to_conversations(
                payload.get("conversations", []),
                early_truncs,
                early_vault_avail,
                antigravity_dir,
                probe_live_recent_limit=5,
            )
            write_quota_status_file(payload, status_path=status_path)
        except Exception as exc:
            logger.warning("Early status hook write failed: %s", exc)

    # Vault synchronization (runs exactly once per export cycle; Feature 2 / ADR-081)
    vault_synced_rows = False
    if not is_custom_dir and not dry_run:
        if live_quota and live_quota.get("source") != "vault_fallback":
            try:
                from src.vault import sync_quota_snapshot_to_vault
                sync_quota_snapshot_to_vault(
                    live_quota,
                    vault_path=vault_file,
                    active_status=payload.get("summary", {}).get("subscription_status", "SAFE_IN_QUOTA"),
                )
            except Exception as e:
                sys.stderr.write(f"[!] Warning: vault quota snapshot sync failed: {e}\n")
        try:
            from src.vault import sync_conversations_to_vault, sync_subscription_to_vault
            sync_subscription_to_vault(force=force_full_scan)
            sync_res = sync_conversations_to_vault(antigravity_dir=antigravity_dir, force=force_full_scan)
            if isinstance(sync_res, dict) and (sync_res.get("conversations_synced", 0) > 0 or sync_res.get("steps_synced", 0) > 0):
                vault_synced_rows = True
        except (sqlite3.Error, OSError) as e:
            sys.stderr.write(f"[!] Warning: vault conversation sync failed: {e}\n")
        except Exception as e:
            sys.stderr.write(f"[!] Unexpected error in vault conversation sync: {e}\n")
        try:
            sync_weekly_trends_to_vault()
        except (sqlite3.Error, OSError) as e:
            sys.stderr.write(f"[!] Warning: vault weekly trends sync failed: {e}\n")
        except Exception as e:
            sys.stderr.write(f"[!] Unexpected error in vault weekly trends sync: {e}\n")
    trends_vault = vault_file

    cache_conn = get_cache_connection(get_cache_db_path(cache_dir)) if cache_dir is not None else None
    try:
        # Subagent swarm lineage, tool analytics, and truncation markers via cached vault query
        vault_analytics = load_vault_analytics_cached(
            vault_file=vault_file,
            pricing=pricing,
            cache_conn=cache_conn,
            force_full_scan=force_full_scan,
            vault_synced_rows=vault_synced_rows,
        )

        swarms_list = vault_analytics["swarms_list"]
        payload["swarms"] = vault_analytics["swarms_summary"]
        payload["tool_analytics"] = vault_analytics["tool_analytics"]

        # Agent persona workflow attribution (M64)
        from src.aggregator_attribution import compute_agent_workflow_attribution
        payload["agent_attribution"] = compute_agent_workflow_attribution(convo_summaries, pricing_models=pricing)

        # Historical weekly cycles trends (M4 / ADR-039 / M38)
        can_use_trends_cache = (
            trends_vault is not None
            and not vault_synced_rows
            and not force_full_scan
            and ledger_path is None
            and reference_time is None
            and not hasattr(get_weekly_trends, "mock_calls")
            and _IN_MEMORY_VAULT_CACHE.get("vault_path") == str(vault_file)
            and _IN_MEMORY_VAULT_CACHE.get("weekly_trends") is not None
        )
        if can_use_trends_cache:
            payload["weekly_trends"] = _IN_MEMORY_VAULT_CACHE["weekly_trends"]
        else:
            trends_kwargs = {
                "fallback_turns": all_turns,
                "pricing_models": pricing,
                "ledger_path": ledger_path,
                "reference_time": reference_time,
            }
            if trends_vault is not None:
                trends_kwargs["vault_path"] = trends_vault
            payload["weekly_trends"] = get_weekly_trends(**trends_kwargs)
            if trends_vault is not None and ledger_path is None and reference_time is None and not hasattr(get_weekly_trends, "mock_calls"):
                _IN_MEMORY_VAULT_CACHE["weekly_trends"] = payload["weekly_trends"]

        # Multi-Horizon Consumption & Era Progression (Milestone M96)
        if vault_file.exists():
            h_vfp = _get_vault_logical_fingerprint(vault_file)
            max_live_ts = max((str(t.get("timestamp") or "") for t in all_turns), default="")
            horizon_hash = compute_config_hash([
                compute_config_hash(pricing),
                compute_config_hash(exhaustion_intervals),
                len(all_turns),
                max_live_ts,
                len(convo_summaries),
                reference_time.isoformat() if reference_time else "",
            ])
            can_use_cache = (
                not vault_synced_rows
                and not force_full_scan
                and _IN_MEMORY_VAULT_CACHE.get("vault_path") == str(vault_file)
                and _IN_MEMORY_VAULT_CACHE.get("horizon_key") == (h_vfp, horizon_hash)
                and _IN_MEMORY_VAULT_CACHE.get("horizon_analytics") is not None
            )
            if can_use_cache:
                payload["horizon_analytics"] = _IN_MEMORY_VAULT_CACHE["horizon_analytics"]
            else:
                cached_horizon = None
                if not force_full_scan and not vault_synced_rows and cache_conn is not None and h_vfp is not None:
                    try:
                        h_cur = cache_conn.cursor()
                        h_cur.execute(
                            "SELECT mtime_ns, size_bytes, pricing_hash, payload_json FROM vault_cache WHERE key = 'horizon_analytics'"
                        )
                        h_row = h_cur.fetchone()
                        if h_row and h_row[0] == h_vfp[0] and h_row[1] == h_vfp[1] and h_row[2] == horizon_hash:
                            cached_horizon = json.loads(h_row[3])
                    except Exception:
                        cached_horizon = None

                if cached_horizon is not None:
                    payload["horizon_analytics"] = cached_horizon
                else:
                    from src.horizon_analytics import compute_horizon_analytics, load_merged_vault_and_live_turns
                    merged_turns, merged_convos = load_merged_vault_and_live_turns(
                        vault_file,
                        all_turns,
                        convo_summaries,
                    )
                    payload["horizon_analytics"] = compute_horizon_analytics(
                        turns=merged_turns,
                        conversations=merged_convos,
                        pricing_data=pricing,
                        ledger_incidents=exhaustion_intervals,
                        reference_time=reference_time,
                    )
                    if cache_conn is not None and h_vfp is not None:
                        try:
                            cache_conn.execute(
                                """
                                INSERT OR REPLACE INTO vault_cache
                                (key, vault_path, mtime_ns, size_bytes, pricing_hash, payload_json, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    "horizon_analytics",
                                    str(vault_file),
                                    h_vfp[0],
                                    h_vfp[1],
                                    horizon_hash,
                                    json.dumps(payload["horizon_analytics"]),
                                    time.time(),
                                ),
                            )
                            cache_conn.commit()
                        except Exception:
                            pass
                _IN_MEMORY_VAULT_CACHE["horizon_key"] = (h_vfp, horizon_hash)
                _IN_MEMORY_VAULT_CACHE["horizon_analytics"] = payload["horizon_analytics"]
    finally:
        if cache_conn is not None:
            try:
                cache_conn.close()
            except Exception:
                pass

    # Quota Regime & Burn-Rate Drift Evaluation (Milestone M97)
    try:
        from src.quota_regime import DEFAULT_REGIME_LEDGER_PATH, evaluate_vault_quota_regime
        is_default_dashboard = dashboard_path.resolve() == (REPO_ROOT / "dashboard" / "index.html").resolve()
        should_persist_regime = (not is_custom_dir and not dry_run and output_dir is None and is_default_dashboard)
        can_use_regime_cache = (
            not should_persist_regime
            and not vault_synced_rows
            and not force_full_scan
            and not is_custom_dir
            and not hasattr(evaluate_vault_quota_regime, "mock_calls")
            and _IN_MEMORY_VAULT_CACHE.get("vault_path") == str(vault_file)
            and _IN_MEMORY_VAULT_CACHE.get("quota_regime") is not None
        )
        if can_use_regime_cache:
            payload["quota_regime"] = _IN_MEMORY_VAULT_CACHE["quota_regime"]
        else:
            eff_regime_ledger = (antigravity_dir / "quota_regime_ledger.json") if is_custom_dir else DEFAULT_REGIME_LEDGER_PATH
            payload["quota_regime"] = evaluate_vault_quota_regime(
                vault_path=vault_file,
                ledger_path=eff_regime_ledger,
                persist=should_persist_regime,
                extra_live_turns=all_turns,
            )
            if not is_custom_dir and not hasattr(evaluate_vault_quota_regime, "mock_calls"):
                _IN_MEMORY_VAULT_CACHE["quota_regime"] = payload["quota_regime"]
    except Exception as e:
        sys.stderr.write(f"[!] Warning: quota regime evaluation failed: {e}\n")
        payload["quota_regime"] = {
            "status": "NOMINAL",
            "drift_ratio": 1.0,
            "coupling_ratio_5h_to_weekly": 4.0,
            "pending_review_count": 0,
            "events": [],
            "model_coverage": {},
        }

    # Truncation marker fold-in (Milestone 55 / Row 9 / ADR-068 / STUDY_PROPOSAL)
    vault_truncations = vault_analytics["vault_truncations"]
    vault_available = vault_file.exists()

    # Correlate child subagents for main sessions
    parent_child_counts = dict(vault_analytics["parent_child_counts"])

    for convo in payload.get("conversations", []):
        pid = convo.get("parent_convo_id")
        if pid:
            parent_child_counts[pid] = parent_child_counts.get(pid, 0) + 1

    for convo in payload.get("conversations", []):
        cid = convo.get("convo_id", "")
        convo["subagents_count"] = parent_child_counts.get(cid, 0)

    _apply_truncation_markers_to_conversations(
        payload.get("conversations", []),
        vault_truncations,
        vault_available,
        antigravity_dir,
    )

    # Phase 2 (Milestone C): Recursive Session Tree Rollups & Mode Classification
    compute_recursive_session_rollups(payload.get("conversations", []), lineage_data=swarms_list)

    prompts_by_convo = vault_analytics["prompts_by_convo"]
    tool_calls_by_convo = vault_analytics["tool_calls_by_convo"]

    modes_counts = {"boost": 0, "teamwork": 0, "goal": 0, "standard": 0}
    file_churn_sessions = 0
    for convo in payload.get("conversations", []):
        cid_val = convo.get("convo_id", "")
        if "session_mode" not in convo or force_full_scan or vault_synced_rows:
            convo["session_mode"] = classify_session_mode(convo, steps_archive_records=prompts_by_convo.get(cid_val))
            t_calls = tool_calls_by_convo.get(cid_val, [] if vault_available else None)
            churn_res = detect_file_churn(t_calls if t_calls is not None else convo, vault_path=vault_file if vault_available else None)
            convo["has_file_churn"] = churn_res["has_churn"]
            convo["file_churn_max"] = churn_res["max_modifications"]
        modes_counts[convo["session_mode"]] = modes_counts.get(convo["session_mode"], 0) + 1

        if convo.get("has_file_churn"):
            file_churn_sessions += 1

    payload["modes_summary"] = {
        **modes_counts,
        "file_churn_sessions": file_churn_sessions,
    }

    for convo in payload.get("conversations", []):
        cid_val = convo.get("convo_id", "")
        if cid_val in _IN_MEMORY_CONVO_CACHE:
            c_entry = _IN_MEMORY_CONVO_CACHE[cid_val]
            if c_entry.get("summary") is not None:
                c_entry["summary"]["session_mode"] = convo.get("session_mode")
                c_entry["summary"]["has_file_churn"] = convo.get("has_file_churn")
                c_entry["summary"]["file_churn_max"] = convo.get("file_churn_max")

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

    # Compute executive current_session and active_swarms hierarchy (M91 / ADR-092)
    swarms, cur_sess = extract_active_swarms_hierarchy(
        payload.get("conversations", []),
        census,
        reference_time=reference_time,
        swarm_recency_minutes=1440,
    )
    if cur_sess is not None:
        cur_sess["is_current"] = True
        payload["current_session"] = cur_sess
    payload["active_swarms"] = swarms

    ticker_lat = compute_ticker_latency_fields(payload, all_turns)
    if "live_ticker" not in payload or not isinstance(payload["live_ticker"], dict):
        payload["live_ticker"] = {}
    payload["live_ticker"].update(ticker_lat)

    # Decouple turns for minified data.js and turns.js (Milestone 55 / Row 9 / Gate B1, B4)
    turns_payload = {c["convo_id"]: c.get("turns", []) for c in payload.get("conversations", [])}
    payload_without_turns = {**payload}
    payload_without_turns["conversations"] = [
        {**c, "turns": []} for c in payload.get("conversations", [])
    ]

    json_str = json.dumps(payload, indent=2, sort_keys=True)
    data_js_minified = json.dumps(payload_without_turns, separators=(",", ":"), sort_keys=True)
    turns_js_minified = json.dumps(turns_payload, separators=(",", ":"), sort_keys=True)

    r5h = payload.get("quotas", {}).get("rolling_5h", {})
    r1w = payload.get("quotas", {}).get("rolling_1w", {})
    sched = r5h.get("recovery_schedule", [])

    if dry_run:
        export_duration = time.time() - t_start
        if reference_time is not None:
            export_seconds = 0.0
        else:
            export_seconds = round(export_duration, 2)
        payload["export_seconds"] = export_seconds
        print(f"[DRY-RUN] Discovered {discovered_count} DBs (scanned {scanned_count}), extracted {len(convo_summaries)} active sessions.")
        print(f"[DRY-RUN] Lifetime Input: {payload['summary']['total_input_tokens']:,} | Cached: {payload['summary']['cache_hit_ratio_pct']}%")
        print(f"[DRY-RUN] Pro Subscription Status: {payload['summary']['subscription_status']} (Imputed Value: ${payload['summary']['total_imputed_value_usd']:.4f} | AI Credits Burned: {payload['summary']['total_ai_credits_burned']:,} credits (£{payload['summary']['total_credit_burn_gbp']:.2f} / ${payload['summary']['total_credit_burn_usd']:.2f}))")
        print(f"[DRY-RUN] 5-Hour Limit: {r5h.get('total_processed_tokens', 0):,} tokens ({r5h.get('turn_count', 0)} turns)")
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

    if output_dir is not None:
        dashboard_dir = Path(output_dir)
        dashboard_dir.mkdir(parents=True, exist_ok=True)
    else:
        if not dashboard_path.exists():
            print(f"Error: Dashboard file {dashboard_path} does not exist.", file=sys.stderr)
            sys.exit(1)

        html_content = dashboard_path.read_text(encoding="utf-8")
        pattern = r'(<script id="injected-dashboard-data" type="application/json">)(.*?)(</script>)'
        if not re.search(pattern, html_content, flags=re.DOTALL):
            print("Error: Could not find <script id=\"injected-dashboard-data\"> tag in dashboard HTML.", file=sys.stderr)
            sys.exit(1)
        dashboard_dir = dashboard_path.parent

    # Always write decoupled data projection files atomically
    data_js_path = dashboard_dir / "data.js"
    atomic_write_text(data_js_path, f"window.__TELEMETRY_DATA__ = {data_js_minified};\n")

    turns_js_path = dashboard_dir / "turns.js"
    atomic_write_text(turns_js_path, f"window.__TELEMETRY_TURNS__ = {turns_js_minified};\n")

    data_json_path = dashboard_dir / "data.json"
    atomic_write_text(data_json_path, json_str)

    # Write decoupled metadata file with deterministic SHA-1 hash for fast ticker gating (Decision 5)
    payload_sha1 = hashlib.sha1(json_str.encode("utf-8")).hexdigest()
    gen_at = payload.get("temporal", {}).get("resolved_at_utc") or payload.get("temporal", {}).get("evaluation_time_utc") or datetime.datetime.now(datetime.timezone.utc).isoformat()
    vault_bytes = vault_file.stat().st_size if vault_file.exists() else 0
    export_duration = time.time() - t_start
    if reference_time is not None:
        export_seconds = 0.0
    else:
        export_seconds = round(export_duration, 2)
    meta_payload = {
        "export_seconds": export_seconds,
        "payload_sha1": payload_sha1,
        "payload_bytes": len(json_str.encode("utf-8")),
        "vault_bytes": vault_bytes,
        "conversations_count": len(convo_summaries),
        "generated_at": gen_at,
        "ticker": payload.get("live_ticker", {}),
    }
    meta_json = json.dumps(meta_payload, indent=2, sort_keys=True)
    meta_js_path = dashboard_dir / "meta.js"
    atomic_write_text(meta_js_path, f"window.__TELEMETRY_META__ = {meta_json};\n")

    meta_json_path = dashboard_dir / "meta.json"
    atomic_write_text(meta_json_path, meta_json)

    if output_dir is None:
        if embed:
            new_html, count = re.subn(
                pattern,
                lambda m: f"{m.group(1)}\n{json_str}\n  {m.group(3)}",
                html_content,
                flags=re.DOTALL,
            )
            atomic_write_text(dashboard_path, new_html)
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
                atomic_write_text(dashboard_path, new_html)
            print(f"Successfully exported {len(convo_summaries)} conversation sessions to {data_js_path}")
    else:
        print(f"Successfully exported {len(convo_summaries)} conversation sessions to {data_js_path}")

    # Write external executive quota status hook
    effective_status_path = status_path if status_path is not None else (dashboard_dir / ".antigravity_quota_status.json" if output_dir is not None else None)
    if effective_status_path is not None:
        write_quota_status_file(payload, status_path=effective_status_path)

    payload["export_seconds"] = export_seconds
    print(f"Total Input: {payload['summary']['total_input_tokens']:,} | Cached: {payload['summary']['cache_hit_ratio_pct']}% | Imputed Value: £{payload['summary']['total_imputed_value_gbp']:.4f} (${payload['summary']['total_imputed_value_usd']:.4f}) | AI Credits Burned: {payload['summary']['total_ai_credits_burned']:,} credits (£{payload['summary']['total_credit_burn_gbp']:.2f} / ${payload['summary']['total_credit_burn_usd']:.2f}) | Status: {payload['summary']['subscription_status']}")
    return payload



def resolve_authoritative_session_db(
    candidate_db: Optional[Union[str, Path]],
    conv_dir: Path,
) -> Optional[Path]:
    """
    Pins to the authoritative user-facing conversation DB.
    1. If candidate_db is provided:
       Follows parent_convo_id ancestor links recursively until finding
       the root user-facing conversation (where is_subagent_conversation is False).
       If candidate_db is already user-facing, returns it immediately.
       If an ancestor chain is broken or missing, falls back to scanning conv_dir.
    2. If candidate_db is None or an unresolvable subagent:
       Scans conv_dir for the most recently modified user-facing DB
       (where is_subagent_conversation is False).
    """
    if candidate_db:
        p = Path(candidate_db)
        if p.exists():
            curr_p = p
            visited = set()
            while curr_p and curr_p.exists() and len(visited) < 5:
                if curr_p in visited:
                    break
                visited.add(curr_p)
                meta = read_single_conversation_metadata(curr_p) or {}
                if not is_subagent_conversation(meta):
                    return curr_p
                pid = meta.get("parent_convo_id")
                if not pid:
                    break
                parent_cand = conv_dir / f"{pid}.db" if conv_dir.exists() else curr_p.parent / f"{pid}.db"
                if not parent_cand.exists():
                    parent_cand = curr_p.parent / f"{pid}.db"
                if not parent_cand.exists():
                    break
                curr_p = parent_cand

    if not conv_dir.exists():
        return None

    db_candidates = []
    try:
        for entry in os.scandir(conv_dir):
            if entry.name.endswith(".db"):
                try:
                    st = entry.stat()
                    wal = conv_dir / f"{entry.name}-wal"
                    wal_mtime = wal.stat().st_mtime if wal.exists() else 0
                    effective_mtime = max(st.st_mtime, wal_mtime)
                    db_candidates.append((effective_mtime, Path(entry.path)))
                except OSError:
                    continue
    except OSError:
        pass

    if not db_candidates:
        return None

    db_candidates.sort(key=lambda x: x[0], reverse=True)

    # First pass: find the most recent interactive session where is_subagent_conversation is False
    for _, db_path in db_candidates:
        meta = read_single_conversation_metadata(db_path) or {}
        if not is_subagent_conversation(meta):
            return db_path

    # Fallback to the top candidate if no non-subagent db found
    return db_candidates[0][1]


def _write_fast_tier_status_update(
    status_target: Path,
    dashboard_dir: Path,
    epoch: int,
    active_session_severity: str,
    current_session: Dict[str, Any],
    target_node: Dict[str, Any],
    sub_node: Optional[Dict[str, Any]],
    elected_node: Dict[str, Any],
    gen_at: str,
    ticker: Dict[str, Any],
    fast_live_quota: Optional[Dict[str, Any]],
    recent_429: bool,
) -> None:
    """Apply fast-tier status updates to status_target under the shared status file lock."""
    fast_subagents = []
    if sub_node:
        fast_subagents.append({
            "convo_id": sub_node["convo_id"],
            "title": sub_node["title"],
            "subagent_role": sub_node["subagent_role"] or "subagent",
            "tokens": sub_node["tokens"],
            "threshold": sub_node["threshold"],
            "nominal_threshold": sub_node["nominal_threshold"],
            "compaction_threshold": sub_node["compaction_threshold"],
            "compaction_epoch": sub_node["compaction_epoch"],
            "severity": sub_node["severity"],
            "is_weakest_link": bool(elected_node == sub_node and sub_node.get("severity") != "safe"),
            "turn_velocity": sub_node["turn_velocity"],
        })
    fast_orch = {k: v for k, v in target_node.items() if not k.startswith("_")}
    fast_orch["is_weakest_link"] = bool(
        sub_node is not None and elected_node == target_node and target_node.get("severity") != "safe"
    )

    with status_file_lock(status_target):
        status_data = {}
        if status_target.exists():
            try:
                with open(status_target, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        status_data = loaded
            except Exception:
                status_data = {}

        status_data["compaction_epoch"] = epoch
        status_data["active_session_severity"] = active_session_severity
        status_data["current_session"] = current_session
        status_data["active_project"] = current_session["workspace"]
        status_data["active_branch"] = current_session["branch"]
        status_data["active_agent_role"] = (
            (current_session.get("subagent_role") if current_session.get("is_subagent") else current_session.get("agent_name", "default"))
            or "default"
        )

        existing_swarms = status_data.get("active_swarms")
        if isinstance(existing_swarms, list) and len(existing_swarms) > 0:
            merged_swarms = []
            matched_orch = False
            ws_has_multi_agent = any(
                isinstance(s, dict)
                and s.get("workspace") == current_session["workspace"]
                and len(s.get("subagents") or []) > 0
                for s in existing_swarms
            )
            for s in existing_swarms:
                if not isinstance(s, dict):
                    continue
                s_copy = dict(s)
                s_orch = dict(s_copy.get("orchestrator") or {})
                s_subs = [dict(sub) for sub in (s_copy.get("subagents") or []) if isinstance(sub, dict)]

                allow_weakest = elected_node.get("severity") != "safe" and (
                    sub_node is not None or len(existing_swarms) > 1 or len(s_subs) > 0
                )
                s_orch["is_weakest_link"] = bool(
                    allow_weakest and s_orch.get("convo_id") == elected_node.get("convo_id")
                )
                for sub_item in s_subs:
                    sub_item["is_weakest_link"] = bool(
                        allow_weakest and sub_item.get("convo_id") == elected_node.get("convo_id")
                    )

                if s_orch.get("convo_id") == fast_orch.get("convo_id"):
                    matched_orch = True
                    s_orch.update(fast_orch)
                    s_orch["is_weakest_link"] = bool(
                        allow_weakest and s_orch.get("convo_id") == elected_node.get("convo_id")
                    )
                    if allow_weakest:
                        current_session["is_weakest_link"] = True
                    for f_sub in fast_subagents:
                        replaced = False
                        for idx, existing_sub in enumerate(s_subs):
                            if existing_sub.get("convo_id") == f_sub.get("convo_id"):
                                s_subs[idx] = f_sub
                                replaced = True
                                break
                        if not replaced:
                            s_subs.insert(0, f_sub)

                sevs = [s_orch.get("severity", "safe")] + [sub_item.get("severity", "safe") for sub_item in s_subs]
                s_copy["worst_severity"] = "critical" if "critical" in sevs else ("warning" if "warning" in sevs else "safe")
                s_copy["orchestrator"] = s_orch
                s_copy["subagents"] = s_subs
                merged_swarms.append(s_copy)

            if not matched_orch:
                new_entry = {
                    "workspace": current_session["workspace"],
                    "branch": current_session["branch"],
                    "worst_severity": active_session_severity,
                    "orchestrator": fast_orch,
                    "subagents": fast_subagents,
                }
                if len(fast_subagents) > 0:
                    merged_swarms.insert(0, new_entry)
                elif not ws_has_multi_agent:
                    replaced_ws = False
                    for idx, s_item in enumerate(merged_swarms):
                        if s_item.get("workspace") == current_session["workspace"] and len(s_item.get("subagents") or []) == 0:
                            merged_swarms[idx] = new_entry
                            replaced_ws = True
                            break
                    if not replaced_ws:
                        merged_swarms.insert(0, new_entry)

            sev_rank = {"critical": 0, "warning": 1, "safe": 2}
            merged_swarms.sort(
                key=lambda s: (
                    sev_rank.get(s.get("worst_severity", "safe"), 3),
                    0 if len(s.get("subagents") or []) > 0 else 1,
                    s.get("workspace", ""),
                    -(len(s.get("subagents") or [])),
                )
            )
            status_data["active_swarms"] = merged_swarms
        else:
            status_data["active_swarms"] = [{
                "workspace": current_session["workspace"],
                "branch": current_session["branch"],
                "worst_severity": active_session_severity,
                "orchestrator": fast_orch,
                "subagents": fast_subagents,
            }]
        status_data["updated_at"] = gen_at
        status_data["recent_burn_rate_tok_per_min"] = ticker.get("burn_rate_tok_per_min", 0)
        status_data["recent_burn_rate_tok_per_sec"] = ticker.get("burn_rate_tok_per_sec", 0.0)
        status_data["last_turn_tokens"] = ticker.get("last_turn_tokens", 0)
        status_data["last_turn_cache_pct"] = ticker.get("last_turn_cache_pct", 0.0)
        status_data["last_turn_model"] = ticker.get("last_turn_model", "")
        status_data["last_turn_ts"] = ticker.get("last_turn_ts", "")
        status_data["is_streaming"] = ticker.get("is_streaming", False)
        status_data["seconds_since_last_turn"] = ticker.get("seconds_since_last_turn", 999999)
        status_data["gemini_5h_tokens"] = ticker.get("gemini_5h_tokens", status_data.get("gemini_5h_tokens", 0))
        status_data["last_turn_ttft_ms"] = (
            ticker.get("last_turn_ttft_ms")
            if ticker.get("last_turn_ttft_ms") is not None
            else status_data.get("last_turn_ttft_ms")
        )
        status_data["last_turn_latency_ms"] = (
            ticker.get("last_turn_latency_ms")
            if ticker.get("last_turn_latency_ms") is not None
            else status_data.get("last_turn_latency_ms")
        )
        status_data["session_median_ttft_ms"] = (
            ticker.get("session_median_ttft_ms")
            if ticker.get("session_median_ttft_ms") is not None
            else status_data.get("session_median_ttft_ms")
        )
        status_data["kv_cache_wiped"] = bool(ticker.get("kv_cache_wiped", False))

        if isinstance(fast_live_quota, dict):
            gem_q = fast_live_quota.get("gemini") if isinstance(fast_live_quota.get("gemini"), dict) else {}
            g5h_q = fast_live_quota.get("gemini_5h") or gem_q.get("five_hour")
            if isinstance(g5h_q, dict) and g5h_q.get("remaining_fraction") is not None:
                rem_pct = round(max(0.0, min(100.0, float(g5h_q["remaining_fraction"]) * 100.0)), 1)
                status_data["gemini_5h_remaining_pct"] = rem_pct
                status_data["gemini_5h_pct"] = round(100.0 - rem_pct, 1)
                if rem_pct <= 0.0:
                    status_data["status"] = "BURNING_AI_CREDITS"
                    status_data["cooldown_active"] = True
            gwk_q = fast_live_quota.get("gemini_weekly") or gem_q.get("weekly")
            if isinstance(gwk_q, dict) and gwk_q.get("remaining_fraction") is not None:
                wk_rem_pct = round(max(0.0, min(100.0, float(gwk_q["remaining_fraction"]) * 100.0)), 1)
                status_data["gemini_weekly_remaining_pct"] = wk_rem_pct
                status_data["gemini_weekly_pct"] = round(100.0 - wk_rem_pct, 1)

        if recent_429:
            status_data["status"] = "BURNING_AI_CREDITS"
            status_data["cooldown_active"] = True
            status_data["gemini_5h_remaining_pct"] = 0.0
            status_data["gemini_5h_pct"] = 100.0

        if "status" not in status_data:
            status_data["status"] = "SAFE_IN_QUOTA"
        if "gemini_5h_pct" not in status_data:
            status_data["gemini_5h_pct"] = ticker.get("gemini_5h_used_pct", 0.0)
        if "gemini_5h_remaining_pct" not in status_data:
            status_data["gemini_5h_remaining_pct"] = ticker.get("gemini_5h_remaining_pct", 100.0)
        if "dashboard_path" not in status_data:
            status_data["dashboard_path"] = str(dashboard_dir / "index.html")

        build_or_patch_status_tracks(status_data)
        atomic_write_text(status_target, json.dumps(status_data, indent=2, sort_keys=True) + "\n")


def export_fast_tier(
    antigravity_dir: Path = DEFAULT_ANTIGRAVITY_DIR,
    dashboard_path: Path = REPO_ROOT / "dashboard" / "index.html",
    status_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    active_db: Optional[Path] = None,
    pricing: Optional[Dict[str, Any]] = None,
    census: Optional[Dict[str, Any]] = None,
    reference_time: Optional[datetime.datetime] = None,
    log_path: Optional[Path] = None,
) -> dict:
    """
    Fast Tier export (<20ms): write only dashboard/meta.js and ~/.antigravity_quota_status.json
    on active session WAL modifications (ADR-082 / Milestone 86).
    """
    t_start = time.time()

    if output_dir is not None:
        dashboard_dir = Path(output_dir)
    elif dashboard_path is not None:
        dashboard_dir = Path(dashboard_path).parent
    else:
        dashboard_dir = REPO_ROOT / "dashboard"

    dashboard_dir.mkdir(parents=True, exist_ok=True)
    lock_path = dashboard_dir / ".export.lock"
    status_target = Path(status_path) if status_path is not None else (dashboard_dir / ".antigravity_quota_status.json" if output_dir is not None else DEFAULT_STATUS_PATH)

    # Try non-blocking advisory lock to avoid colliding with active Heavy Tier rollup
    lock_file = None
    try:
        lock_file = open(lock_path, "a+")
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        if lock_file is not None:
            try:
                lock_file.close()
            except OSError:
                pass
        return {"status": "skipped", "reason": "lock_held", "tier": "fast"}

    try:
        antigravity_dir_path = Path(antigravity_dir)
        is_custom_dir = antigravity_dir_path.resolve() != DEFAULT_ANTIGRAVITY_DIR.resolve()
        eff_log_path = Path(log_path) if log_path is not None else ((antigravity_dir_path / "language_server.log") if is_custom_dir else DEFAULT_LOG_PATH)

        conv_dir = antigravity_dir_path / "conversations"
        target_db = resolve_authoritative_session_db(active_db, conv_dir)
        if target_db is None or not target_db.exists():
            if not conv_dir.exists():
                return {"status": "skipped", "reason": "no_conv_dir", "tier": "fast"}
            return {"status": "skipped", "reason": "no_dbs", "tier": "fast"}

        # Read active conversation turns and metadata (<5ms)
        try:
            meta = read_single_conversation_metadata(target_db) or {}
            turns = read_conversation_turns(target_db) or []
        except (sqlite3.Error, OSError) as e:
            return {"status": "skipped", "reason": f"db_read_error: {e}", "tier": "fast"}

        # Scan truncation & compaction epoch (<3ms)
        t_res = scan_conversation_truncation(target_db)
        has_trunc = bool(t_res[0]) if t_res else False
        comp_count = getattr(t_res, "compaction_count", 1 if has_trunc else 0)
        epoch = getattr(t_res, "epoch", comp_count + 1 if has_trunc else 1)
        curr_convo_id = meta.get("convo_id", target_db.stem)
        if not meta.get("title"):
            meta["title"] = get_conversation_title(target_db.stem, antigravity_dir_path)
        for t in turns:
            t.setdefault("convo_id", curr_convo_id)

        if census is None:
            census = load_model_census()
        if pricing is None:
            pricing = load_pricing()

        target_data = {
            **meta,
            "turns": turns,
            "compaction_count": comp_count,
            "compaction_epoch": epoch,
            "has_truncated": has_trunc,
        }
        target_node = evaluate_session_node(target_data, census)
        target_node["is_current"] = True
        elected_node = target_node

        sub_node = None
        sub_data = None
        active_sub_turns: List[dict] = []
        if active_db and active_db != target_db and active_db.exists():
            try:
                active_sub_meta = read_single_conversation_metadata(active_db) or {}
                sub_cid = active_sub_meta.get("convo_id", active_db.stem)
                if not active_sub_meta.get("title"):
                    active_sub_meta["title"] = get_conversation_title(active_db.stem, antigravity_dir_path)
                active_sub_turns = read_conversation_turns(active_db) or []
                for t in active_sub_turns:
                    t.setdefault("convo_id", sub_cid)
                sub_tres = scan_conversation_truncation(active_db)
                sub_trunc = bool(sub_tres[0]) if sub_tres else False
                sub_comp = getattr(sub_tres, "compaction_count", 1 if sub_trunc else 0)
                sub_ep = getattr(sub_tres, "epoch", sub_comp + 1 if sub_trunc else 1)
                sub_data = {
                    **active_sub_meta,
                    "turns": active_sub_turns,
                    "compaction_count": sub_comp,
                    "compaction_epoch": sub_ep,
                    "has_truncated": sub_trunc,
                }
                sub_node = evaluate_session_node(sub_data, census)
                if sub_node["_risk_score"] > target_node["_risk_score"]:
                    sub_node["parent_title"] = meta.get("title") or curr_convo_id
                    sub_node["is_current"] = True
                    elected_node = sub_node
            except Exception:
                active_sub_turns = []

        if sub_node is not None and elected_node.get("severity") != "safe":
            elected_node["is_weakest_link"] = True
        else:
            elected_node["is_weakest_link"] = False

        current_session = {k: v for k, v in elected_node.items() if not k.startswith("_")}
        active_session_severity = current_session["severity"]
        epoch = current_session["compaction_epoch"]

        # Read existing meta.json to preserve heavy tier sha1 and byte statistics
        meta_json_path = dashboard_dir / "meta.json"
        meta_payload = {}
        if meta_json_path.exists():
            try:
                with open(meta_json_path, "r", encoding="utf-8") as f:
                    meta_payload = json.load(f)
            except Exception:
                meta_payload = {}

        old_ticker = meta_payload.get("ticker", {})
        g5h = {
            "total_processed": old_ticker.get("gemini_5h_tokens", 0),
            "remaining_pct": old_ticker.get("gemini_5h_remaining_pct", 100.0),
            "used_pct": old_ticker.get("gemini_5h_used_pct", 0.0),
        }

        ref_now = reference_time if reference_time is not None else datetime.datetime.now(datetime.timezone.utc)
        latest_429_dt = get_latest_exhaustion_event_utc(eff_log_path)
        recent_429 = bool(
            latest_429_dt is not None
            and 0.0 <= (ref_now - latest_429_dt).total_seconds() <= 3600.0
        )

        # Throttled (15s) live Connect-RPC quota refresh on default host installation
        fast_live_quota = _FAST_QUOTA_CACHE.get("live_quota")
        if not is_custom_dir and output_dir is None:
            now_mono = time.time()
            if (now_mono - float(_FAST_QUOTA_CACHE.get("polled_at", 0.0))) >= 15.0:
                try:
                    from src.quota_client import fetch_live_quota_summary
                    polled = fetch_live_quota_summary()
                    _FAST_QUOTA_CACHE["polled_at"] = now_mono
                    if polled:
                        _FAST_QUOTA_CACHE["live_quota"] = polled
                        fast_live_quota = polled
                        try:
                            from src.vault import sync_quota_snapshot_to_vault
                            sync_quota_snapshot_to_vault(
                                polled,
                                active_status="BURNING_AI_CREDITS" if recent_429 else "SAFE_IN_QUOTA",
                            )
                        except Exception:
                            pass
                except Exception:
                    _FAST_QUOTA_CACHE["polled_at"] = now_mono

        if fast_live_quota is None:
            fast_vault_file = _resolve_vault_file_for_dir(antigravity_dir_path, is_custom_dir)
            fast_live_quota = _load_vault_quota_fallback_for_dir(
                fast_vault_file,
                antigravity_dir_path,
                is_custom_dir,
                reference_time,
                label="Fast-tier Vault",
            )

        if isinstance(fast_live_quota, dict):
            gem_q = fast_live_quota.get("gemini") if isinstance(fast_live_quota.get("gemini"), dict) else {}
            g5h_q = fast_live_quota.get("gemini_5h") or gem_q.get("five_hour")
            if isinstance(g5h_q, dict) and g5h_q.get("remaining_fraction") is not None:
                rem_pct = round(max(0.0, min(100.0, float(g5h_q["remaining_fraction"]) * 100.0)), 1)
                g5h["remaining_pct"] = rem_pct
                g5h["used_pct"] = round(100.0 - rem_pct, 1)

        if recent_429:
            g5h["remaining_pct"] = 0.0
            g5h["used_pct"] = 100.0

        combined_turns = turns + active_sub_turns
        fast_convos = [target_data] + ([sub_data] if sub_data else [])
        ticker = compute_live_ticker(
            flat_turns=combined_turns,
            conversation_summaries=[meta] + ([sub_data] if sub_data else []),
            projects=[{"project_name": current_session["workspace"], "branches": [{"branch_name": current_session["branch"]}]}],
            reference_time=reference_time,
            pricing_models=pricing,
            gemini_5h=g5h,
        )
        lat_fields = compute_ticker_latency_fields(
            {"conversations": fast_convos, "current_session": current_session},
            combined_turns,
        )
        ticker["last_turn_ttft_ms"] = (
            lat_fields["last_turn_ttft_ms"]
            if lat_fields.get("last_turn_ttft_ms") is not None
            else old_ticker.get("last_turn_ttft_ms")
        )
        ticker["last_turn_latency_ms"] = (
            lat_fields["last_turn_latency_ms"]
            if lat_fields.get("last_turn_latency_ms") is not None
            else old_ticker.get("last_turn_latency_ms")
        )
        ticker["session_median_ttft_ms"] = (
            lat_fields["session_median_ttft_ms"]
            if lat_fields.get("session_median_ttft_ms") is not None
            else old_ticker.get("session_median_ttft_ms")
        )
        ticker["kv_cache_wiped"] = bool(lat_fields.get("kv_cache_wiped", False))

        gen_at = reference_time.isoformat() if reference_time else datetime.datetime.now(datetime.timezone.utc).isoformat()
        export_seconds = round(time.time() - t_start, 4)
        meta_payload["ticker"] = ticker
        meta_payload["generated_at"] = gen_at
        meta_payload["export_seconds"] = export_seconds
        if "payload_sha1" not in meta_payload:
            meta_payload["payload_sha1"] = ""
        if "payload_bytes" not in meta_payload:
            meta_payload["payload_bytes"] = 0
        if "vault_bytes" not in meta_payload:
            meta_payload["vault_bytes"] = 0
        if "conversations_count" not in meta_payload:
            meta_payload["conversations_count"] = 1

        meta_json = json.dumps(meta_payload, indent=2, sort_keys=True)
        meta_js_path = dashboard_dir / "meta.js"
        atomic_write_text(meta_js_path, f"window.__TELEMETRY_META__ = {meta_json};\n")
        atomic_write_text(meta_json_path, meta_json)

        # Update executive status file under shared thread + process file lock
        _write_fast_tier_status_update(
            status_target=status_target,
            dashboard_dir=dashboard_dir,
            epoch=epoch,
            active_session_severity=active_session_severity,
            current_session=current_session,
            target_node=target_node,
            sub_node=sub_node,
            elected_node=elected_node,
            gen_at=gen_at,
            ticker=ticker,
            fast_live_quota=fast_live_quota,
            recent_429=recent_429,
        )

        duration_ms = (time.time() - t_start) * 1000
        return {
            "status": "success",
            "tier": "fast",
            "duration_ms": duration_ms,
            "epoch": epoch,
            "active_session": current_session,
            "ticker": ticker,
            "meta_path": str(meta_js_path),
            "status_path": str(status_target),
        }
    finally:
        if lock_file is not None:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                lock_file.close()
            except OSError:
                pass



def export_telemetry(
    antigravity_dir: Path = DEFAULT_ANTIGRAVITY_DIR,
    dashboard_path: Path = REPO_ROOT / "dashboard" / "index.html",
    log_path: Optional[Path] = None,
    ledger_path: Optional[Path] = None,
    max_conversations: Optional[int] = None,
    dry_run: bool = False,
    embed: bool = False,
    status_path: Optional[Path] = None,
    no_live_quota: bool = False,
    reference_time: Optional[datetime.datetime] = None,
    output_dir: Optional[Path] = None,
    force_full_scan: bool = False,
    fast_tier: bool = False,
    active_db: Optional[Path] = None,
) -> dict:
    """Extract telemetry and export to decoupled data.js and dashboard HTML with advisory lock."""
    if fast_tier:
        return export_fast_tier(
            antigravity_dir=antigravity_dir,
            dashboard_path=dashboard_path,
            status_path=status_path,
            output_dir=output_dir,
            active_db=active_db,
            reference_time=reference_time,
            log_path=log_path,
        )
    # Exclusive advisory export lock (C1 / Milestone 49 / AGENTS.md §2.5 Single Exporter Rule)
    if output_dir is not None:
        lock_dir = Path(output_dir)
    elif dashboard_path is not None:
        lock_dir = Path(dashboard_path).parent
    else:
        lock_dir = REPO_ROOT / "dashboard"

    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / ".export.lock"

    try:
        lock_file = open(lock_path, "a+")
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        holder_pid = "?"
        try:
            lock_file.seek(0)
            holder_pid = lock_file.read().strip() or "?"
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write(f"[!] Warning: failed to read lock holder PID: {e}\n")
        except Exception as e:
            sys.stderr.write(f"[!] Unexpected error reading lock holder PID: {e}\n")
        try:
            lock_file.close()
        except OSError as e:
            sys.stderr.write(f"[!] Warning: failed to close lock file: {e}\n")
        except Exception as e:
            sys.stderr.write(f"[!] Unexpected error closing lock file: {e}\n")
        print(f"[skip] export already running (pid {holder_pid})")
        return {"status": "skipped", "reason": "lock_held", "holder_pid": holder_pid}

    try:
        try:
            lock_file.seek(0)
            lock_file.truncate(0)
            lock_file.write(f"{os.getpid()}\n")
            lock_file.flush()
        except OSError as e:
            sys.stderr.write(f"[!] Warning: failed to record export lock PID: {e}\n")
        except Exception as e:
            sys.stderr.write(f"[!] Unexpected error writing export lock PID: {e}\n")

        return _export_telemetry_impl(
            antigravity_dir=antigravity_dir,
            dashboard_path=dashboard_path,
            log_path=log_path,
            ledger_path=ledger_path,
            max_conversations=max_conversations,
            dry_run=dry_run,
            embed=embed,
            status_path=status_path,
            no_live_quota=no_live_quota,
            reference_time=reference_time,
            output_dir=output_dir,
            force_full_scan=force_full_scan,
        )
    finally:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except OSError as e:
            sys.stderr.write(f"[!] Warning: failed to unlock export lock: {e}\n")
        except Exception as e:
            sys.stderr.write(f"[!] Unexpected error unlocking export lock: {e}\n")
        try:
            lock_file.close()
        except OSError as e:
            sys.stderr.write(f"[!] Warning: failed to close export lock file: {e}\n")
        except Exception as e:
            sys.stderr.write(f"[!] Unexpected error closing export lock file: {e}\n")


def build_parser() -> argparse.ArgumentParser:
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
        default=None,
        help="Path to ~/Library/Logs/Antigravity/language_server.log",
    )
    parser.add_argument(
        "--ledger-path",
        type=Path,
        default=None,
        help="Path to data/exhaustion_ledger.json",
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
        "--status-file",
        dest="status_path",
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
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to output data.js, data.json, and meta.js without modifying dashboard/",
    )
    parser.add_argument(
        "--reference-time",
        type=str,
        default=None,
        help="Explicit evaluation timestamp (ISO-8601, e.g. '2026-09-13T20:00:00Z') for deterministic testing",
    )
    parser.add_argument(
        "--force-full-scan",
        action="store_true",
        default=False,
        help="Force full scan of all conversation databases ignoring mtime gating",
    )
    parser.add_argument(
        "--fast-tier",
        "--fast",
        action="store_true",
        default=False,
        help="Fast Tier export (<20ms): write only dashboard/meta.js and ~/.antigravity_quota_status.json",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    ref_dt = None
    if args.reference_time:
        try:
            ref_dt = datetime.datetime.fromisoformat(args.reference_time.replace("Z", "+00:00"))
        except Exception:
            from src.aggregator import parse_timestamp
            ref_dt = parse_timestamp(args.reference_time)

    if args.fast_tier:
        cli_status_path = args.status_path if args.status_path is not None else (None if args.output_dir is not None else DEFAULT_STATUS_PATH)
        res = export_fast_tier(
            antigravity_dir=args.antigravity_dir,
            dashboard_path=args.dashboard_path,
            status_path=cli_status_path,
            output_dir=args.output_dir,
            reference_time=ref_dt,
        )
        if args.json:
            print(json.dumps(res, indent=2, sort_keys=True))
        elif res.get("status") == "success":
            print(f"Fast Tier export complete in {res.get('duration_ms', 0):.2f}ms (Epoch: E{res.get('epoch', 1)})")
        else:
            print(f"Fast Tier export skipped ({res.get('reason')})")
        sys.exit(0)

    if args.json or args.markdown:
        pricing = load_pricing()
        census = load_model_census()
        pricing_models = pricing
        for mid, cinfo in census.items():
            if mid in pricing_models:
                pricing_models[mid]["context_truncation_tokens"] = cinfo.get("context_truncation_tokens", 200000)

        is_custom_dir = Path(args.antigravity_dir).resolve() != DEFAULT_ANTIGRAVITY_DIR.resolve()
        eff_log_path = args.log_path
        eff_ledger_path = args.ledger_path
        if is_custom_dir:
            if eff_log_path is None:
                eff_log_path = args.antigravity_dir / "language_server.log"
            if eff_ledger_path is None:
                eff_ledger_path = args.antigravity_dir / "exhaustion_ledger.json"
        else:
            if eff_log_path is None:
                eff_log_path = DEFAULT_LOG_PATH
            if eff_ledger_path is None:
                eff_ledger_path = DEFAULT_LEDGER_PATH

        intervals = extract_exhaustion_intervals(log_path=eff_log_path, ledger_path=eff_ledger_path)
        cache_dir = Path(args.output_dir) if args.output_dir is not None else (args.dashboard_path.parent if args.dashboard_path else REPO_ROOT / "dashboard")
        summaries, all_turns, discovered_count, scanned_count = load_incremental_conversations(
            antigravity_dir=args.antigravity_dir,
            pricing=pricing,
            exhaustion_intervals=intervals,
            dashboard_dir=cache_dir,
            max_conversations=args.max_conversations,
            force_full_scan=args.force_full_scan,
        )
        payload = aggregate_global_telemetry(
            summaries,
            pricing,
            all_raw_turns=all_turns,
            exhaustion_intervals=intervals,
            discovered_databases=discovered_count,
            scanned_databases=scanned_count,
            reference_time=ref_dt,
        )
        if "temporal" in payload and isinstance(payload["temporal"], dict) and "models" in payload["temporal"]:
            for mid, cinfo in census.items():
                if mid in payload["temporal"]["models"]:
                    payload["temporal"]["models"][mid]["context_truncation_tokens"] = cinfo.get("context_truncation_tokens", 200000)
        payload["pricing_models"] = pricing
        payload["catalog"] = build_export_catalog(pricing)
        if args.markdown and not args.json:
            digest = generate_markdown_digest(payload)
            if args.markdown_file:
                atomic_write_text(args.markdown_file, digest, encoding="utf-8")
                print(f"Successfully wrote Markdown digest to {args.markdown_file}")
            else:
                print(digest, end="")
            return
        v_file = (args.antigravity_dir / "antigravity_vault.db") if is_custom_dir else DEFAULT_VAULT_PATH
        v_truncs = get_vault_truncation_markers(vault_path=v_file) if v_file.exists() else {}
        v_avail = v_file.exists()
        _apply_truncation_markers_to_conversations(
            payload.get("conversations", []),
            v_truncs,
            v_avail,
            args.antigravity_dir,
        )
        from src.aggregator_attribution import compute_agent_workflow_attribution
        payload["agent_attribution"] = compute_agent_workflow_attribution(payload.get("conversations", []), pricing_models=pricing)
        if v_file.exists():
            from src.horizon_analytics import compute_horizon_analytics, load_merged_vault_and_live_turns
            merged_turns, merged_convos = load_merged_vault_and_live_turns(
                v_file,
                all_turns,
                payload.get("conversations", []),
            )
            payload["horizon_analytics"] = compute_horizon_analytics(
                turns=merged_turns,
                conversations=merged_convos,
                pricing_data=pricing,
                ledger_incidents=intervals,
                reference_time=ref_dt,
            )
        try:
            from src.quota_regime import DEFAULT_REGIME_LEDGER_PATH, evaluate_vault_quota_regime
            eff_regime_ledger = (args.antigravity_dir / "quota_regime_ledger.json") if is_custom_dir else DEFAULT_REGIME_LEDGER_PATH
            payload["quota_regime"] = evaluate_vault_quota_regime(
                vault_path=v_file,
                ledger_path=eff_regime_ledger,
                persist=False,
                extra_live_turns=all_turns,
            )
        except Exception:
            payload["quota_regime"] = {
                "status": "NOMINAL",
                "drift_ratio": 1.0,
                "coupling_ratio_5h_to_weekly": 4.0,
                "pending_review_count": 0,
                "events": [],
                "model_coverage": {},
            }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
            return

    cli_status_path = args.status_path if args.status_path is not None else (None if args.output_dir is not None else DEFAULT_STATUS_PATH)
    res = export_telemetry(
        antigravity_dir=args.antigravity_dir,
        dashboard_path=args.dashboard_path,
        log_path=args.log_path,
        ledger_path=args.ledger_path,
        max_conversations=args.max_conversations,
        dry_run=args.dry_run,
        embed=args.embed,
        status_path=cli_status_path,
        no_live_quota=args.no_live_quota,
        reference_time=ref_dt,
        output_dir=args.output_dir,
        force_full_scan=args.force_full_scan,
    )
    if isinstance(res, dict) and res.get("status") == "skipped":
        sys.exit(0)


if __name__ == "__main__":
    main()
