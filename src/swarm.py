"""
Subagent Swarm Lineage Explorer & Multi-Agent Economics Engine.

Extracts parent-child relationships, subagent tier breakdowns, and swarm economics
from the Antigravity Telemetry Vault (data/antigravity_vault.db) and upstream SQLite DBs.

Adheres strictly to:
- ADR-001: Strict Read-Only SQLite Access (`?mode=ro`, uri=True).
- ADR-007: 3-Tier Subagent Allocation & Pre-Flight Disclosure.
- ADR-018: Dedicated Local Telemetry Vault, Hybrid Lossless Archival & Lineage Topology.
- ADR-020: Autonomous Subagent 3-Tier Routing Matrix (1050 Lite, 1322 Fast, 1036 Pro Low).
- ADR-037: Subagent Swarm Lineage DAG & Tool Performance Intelligence Architecture.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

from antigravity_telemetry import (
    load_model_catalog,
    resolve_wire_model_id,
)
from antigravity_telemetry.reader import DEFAULT_ANTIGRAVITY_DIR
from src.aggregator import (
    compute_turn_cost,
    get_model_display_name,
    get_model_rates,
    load_pricing,
)
from src.temporal import resolve_tier_model

DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "antigravity_vault.db"

# Canonical subagent tier mappings (ADR-020 / ADR-007)
TIER_MECHANICAL = "mechanical"      # flash_lite -> Model 1050 (Gen 1) / Model 1198 (Gen 2)
TIER_ENGINEERING = "engineering"    # flash -> Model 1322 / Flash 3.8 (1318-1320) / Hydrogen (1525-1528) / Orch Exec (1669)
TIER_ARCHITECTURE = "architecture"  # Carbon (1427/1437/1438), Orchestrator planners (1667/1681), Argon (1417-1419), Claude 5.5, Pro (1036/1016)
TIER_OTHER = "other"


def classify_subagent_tier(model_id_or_tier: Optional[str]) -> str:
    """Classify subagent model ID or requested tier into standard 3-tier taxonomy."""
    if not model_id_or_tier:
        return TIER_OTHER
    val = str(model_id_or_tier).strip().lower()
    if val in ("inherit", "unknown", "unknown-model"):
        return TIER_OTHER
    if val in ("1050", "1198", "1317", "flash_lite", "gemini-flash-lite", "flash-lite", "mechanical"):
        return TIER_MECHANICAL
    if val in (
        "1322", "1318", "1319", "1320", "1132", "1301",
        "1525", "1526", "1527", "1528", "1669",
        "flash", "gemini-flash", "fast_agent", "fast-agent", "engineering",
        "hydrogen", "gemini-hydrogen", "orchestrator-executor", "orchestrator-hydrogen",
    ):
        return TIER_ENGINEERING
    if val in (
        "1036", "1016", "1417", "1418", "1419", "1427", "1437", "1438", "1667", "1681",
        "1026", "1027", "1035", "1400", "1401", "1402", "1403", "1404", "1405", "342",
        "pro", "pro_low", "pro_high", "gemini-pro", "gemini-argon", "argon",
        "gemini-carbon", "carbon", "gemini-orchestrator", "orchestrator", "architecture",
    ):
        return TIER_ARCHITECTURE
    try:
        resolved = resolve_wire_model_id(val)
        cat_models = load_model_catalog().get("models", {})
        if resolved in cat_models and isinstance(cat_models[resolved], dict):
            st = cat_models[resolved].get("swarm_tier")
            if st in (TIER_MECHANICAL, TIER_ENGINEERING, TIER_ARCHITECTURE):
                return str(st)
    except Exception:
        pass
    return TIER_OTHER


def _get_short_badge(model_id: str, fallback_name: str = "") -> str:
    """Resolve compact model badge from antigravity_telemetry/models.json."""
    try:
        resolved = resolve_wire_model_id(model_id)
        cat_models = load_model_catalog().get("models", {})
        if resolved in cat_models and isinstance(cat_models[resolved], dict):
            badge = cat_models[resolved].get("short_badge") or cat_models[resolved].get("short_name")
            if badge:
                return str(badge)
    except Exception:
        pass
    return fallback_name or f"Model {model_id}"


def _extract_member_name(role_or_title: str, agent_name: str = "") -> str:
    """Extract clean worker roster name from Swarm Worker (<name>) or agent_name."""
    m = re.search(r"Swarm Worker \(([^)]+)\)", role_or_title or "", re.IGNORECASE)
    if m:
        return m.group(1).strip()
    if agent_name and agent_name not in ("default", "unknown"):
        return agent_name.strip()
    return (role_or_title or "worker").strip()


def format_duration(seconds: float) -> str:
    """Format duration in seconds into human-readable representation."""
    if seconds < 0:
        return "0s"
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    m, sec = divmod(s, 60)
    if m < 60:
        return f"{m}m {sec}s" if sec > 0 else f"{m}m"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def extract_swarm_lineage(
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
    antigravity_dir: Union[str, Path] = DEFAULT_ANTIGRAVITY_DIR,
    pricing_models: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Extract multi-agent swarm lineages from the Telemetry Vault or upstream DBs.

    Discovers all parent-child relationships, resolves DAG roots, and aggregates
    swarm economics (total tokens, duration, cost attribution, and 3-tier subagent breakdown).

    Returns a list of swarm dictionaries sorted by total tokens / cost descending.
    """
    if pricing_models is None:
        pricing_models = load_pricing()

    v_file = Path(vault_path).resolve()
    if not v_file.exists():
        return []

    conn = None
    try:
        conn = sqlite3.connect(f"file:{v_file}?mode=ro", uri=True, timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000;")
        cur = conn.cursor()

        # 1. Authoritative invoke_subagent tool calls
        cur.execute(
            """
            SELECT convo_id, arguments_json, result_summary, timestamp
            FROM tool_calls_archive
            WHERE tool_name = 'invoke_subagent'
            ORDER BY id ASC
            """
        )
        invokes = cur.fetchall()

        parent_child_pairs: List[Tuple[str, str]] = []
        subagent_metadata: Dict[str, Dict[str, Any]] = {}

        uuid_regex = re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            re.IGNORECASE,
        )

        for caller_id, args_json, res_summary, ts in invokes:
            args = {}
            if args_json:
                try:
                    args = json.loads(args_json)
                except (json.JSONDecodeError, TypeError):
                    args = {}
            subagent_specs = args.get("Subagents", []) if isinstance(args, dict) else []
            if not subagent_specs and isinstance(args, dict) and any(k in args for k in ("Role", "TypeName", "Prompt", "Model")):
                subagent_specs = [args]
            combined_text = (res_summary or "") + " " + (args_json or "")
            found_cids = uuid_regex.findall(combined_text)
            
            # Deduplicate while preserving order, and filter out caller_id itself
            seen = set()
            candidate_children = []
            for c in found_cids:
                if c != caller_id and c not in seen:
                    seen.add(c)
                    candidate_children.append(c)

            # Pair subagent specs with found conversation IDs
            for i, sa_spec in enumerate(subagent_specs):
                child_id = candidate_children[i] if i < len(candidate_children) else None
                if child_id and child_id != caller_id:
                    parent_child_pairs.append((caller_id, child_id))
                    subagent_metadata[child_id] = {
                        "role": sa_spec.get("Role") or sa_spec.get("TypeName") or "Specialist Subagent",
                        "model_requested": sa_spec.get("Model") or "inherit",
                        "type_name": sa_spec.get("TypeName") or "self",
                        "parent_id": caller_id,
                        "created_at": ts,
                    }

        # 2. Add parents from conversations_archive (from M08 sync), prioritizing explicit subagents
        cur.execute(
            """
            SELECT convo_id, parent_convo_id, title, COALESCE(is_subagent, 0), COALESCE(subagent_role, '')
            FROM conversations_archive
            WHERE parent_convo_id IS NOT NULL AND parent_convo_id != ''
            ORDER BY COALESCE(is_subagent, 0) DESC, CASE WHEN COALESCE(subagent_role, '') != '' THEN 1 ELSE 0 END DESC
            """
        )
        for child_id, parent_id, c_title, c_is_sub, c_sub_role in cur.fetchall():
            if child_id != parent_id:
                # Add if not creating a direct cycle
                if (parent_id, child_id) not in parent_child_pairs and (child_id, parent_id) not in parent_child_pairs:
                    parent_child_pairs.append((parent_id, child_id))
                if child_id not in subagent_metadata:
                    # Heuristic role from subagent_role or child title
                    role = c_sub_role or "Subagent"
                    if role == "Subagent" and c_title:
                        role_match = re.search(r"You are the ([A-Za-z0-9_\- ]+) subagent", c_title)
                        if role_match:
                            role = role_match.group(1).strip()
                        else:
                            role = c_title[:35]
                    subagent_metadata[child_id] = {
                        "role": role,
                        "model_requested": "unknown",
                        "type_name": "self",
                        "parent_id": parent_id,
                        "created_at": "",
                    }

        # 3. Load all conversations details (including turn1_input_tokens when present)
        cur.execute("PRAGMA table_info(conversations_archive)")
        c_cols = {r[1] for r in cur.fetchall()}
        t1_select = (
            ", COALESCE(turn1_input_tokens, 0), COALESCE(turn1_cached_tokens, 0)"
            if "turn1_input_tokens" in c_cols
            else ", 0, 0"
        )
        cur.execute(
            f"""
            SELECT
                convo_id, parent_convo_id, workspace_name, workspace_path,
                title, turn_count, total_input_tokens, total_output_tokens,
                cached_tokens, thinking_tokens, estimated_cost_usd,
                first_turn_ts, last_turn_ts, agent_name, is_subagent, subagent_role
                {t1_select}
            FROM conversations_archive
            """
        )
        convo_rows = cur.fetchall()
        convos: Dict[str, Dict[str, Any]] = {}
        for r in convo_rows:
            cid = r[0]
            convos[cid] = {
                "convo_id": cid,
                "parent_convo_id": r[1],
                "workspace_name": r[2] or "Unknown Workspace",
                "workspace_path": r[3] or "",
                "title": r[4] or "Untitled Session",
                "turn_count": r[5] or 0,
                "total_input_tokens": r[6] or 0,
                "total_output_tokens": r[7] or 0,
                "cached_tokens": r[8] or 0,
                "thinking_tokens": r[9] or 0,
                "estimated_cost_usd": r[10] or 0.0,
                "first_turn_ts": r[11] or "",
                "last_turn_ts": r[12] or "",
                "agent_name": r[13] or "default" if len(r) > 13 else "default",
                "is_subagent": bool(r[14]) if len(r) > 14 else False,
                "subagent_role": r[15] or "" if len(r) > 15 else "",
                "turn1_input_tokens": int(r[16] or 0) if len(r) > 16 else 0,
                "turn1_cached_tokens": int(r[17] or 0) if len(r) > 17 else 0,
            }

        # 3b. Native /swarm discovery from tool_calls_archive ('swarm' tool calls) and brain/*/.system_generated/swarm/
        native_swarm_roots: Dict[str, Dict[str, Any]] = {}
        worker_spawner_by_name: Dict[Tuple[str, str], str] = {}
        cur.execute(
            """
            SELECT convo_id, arguments_json, result_summary, timestamp
            FROM tool_calls_archive
            WHERE tool_name = 'swarm'
            ORDER BY id ASC
            """
        )
        for caller_id, args_json, res_summary, ts in cur.fetchall():
            if not args_json:
                continue
            try:
                args = json.loads(args_json)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(args, dict):
                continue
            action = str(args.get("action") or "").strip().lower()
            if action == "title" and args.get("title"):
                native_swarm_roots.setdefault(caller_id, {})["swarm_title"] = str(args["title"])
            elif action == "add" and args.get("name"):
                w_name = str(args.get("name")).strip()
                native_swarm_roots.setdefault(caller_id, {}).setdefault("added_workers", []).append({
                    "name": w_name,
                    "model": str(args.get("model") or "inherit"),
                    "fork": args.get("fork"),
                    "workspace": str(args.get("workspace") or "inherit"),
                    "timestamp": ts,
                })
                # Track if a non-root worker spawned a helper
                c_role = convos.get(caller_id, {}).get("subagent_role", "")
                if c_role.startswith("Swarm Worker ("):
                    p_root = convos.get(caller_id, {}).get("parent_convo_id") or caller_id
                    worker_spawner_by_name[(p_root, w_name)] = caller_id

        # Authoritative Native /swarm roster from brain/<swarm_id>/.system_generated/swarm/members.json
        authoritative_swarm_parent: Dict[str, str] = {}
        brain_root = Path(antigravity_dir) / "brain"
        if brain_root.exists():
            for members_file in sorted(brain_root.glob("*/.system_generated/swarm/members.json")):
                try:
                    m_data = json.loads(members_file.read_text(encoding="utf-8"))
                    members = m_data.get("members", []) if isinstance(m_data, dict) else []
                    coord_id = next(
                        (
                            str(m.get("conversation_id")).strip()
                            for m in members
                            if isinstance(m, dict) and m.get("role") == "coordinator" and m.get("conversation_id")
                        ),
                        members_file.parent.parent.parent.name,
                    )
                    if not coord_id or coord_id not in convos:
                        continue
                    s_info = native_swarm_roots.setdefault(coord_id, {})
                    s_info["swarm_dir"] = members_file.parent
                    swarm_json_file = members_file.parent / "swarm.json"
                    if swarm_json_file.exists():
                        try:
                            sj = json.loads(swarm_json_file.read_text(encoding="utf-8"))
                            if isinstance(sj, dict) and sj.get("title"):
                                s_info["swarm_title"] = str(sj["title"])
                        except Exception:
                            pass
                    for m in members:
                        if not isinstance(m, dict) or m.get("role") == "coordinator":
                            continue
                        w_cid = str(m.get("conversation_id") or "").strip()
                        w_name = str(m.get("name") or "worker").strip()
                        w_model = str(m.get("model") or "inherit").strip()
                        if not w_cid or w_cid == coord_id:
                            continue
                        spawner_cid = worker_spawner_by_name.get((coord_id, w_name), coord_id)
                        authoritative_swarm_parent[w_cid] = spawner_cid
                        subagent_metadata[w_cid] = {
                            "role": f"Swarm Worker ({w_name})",
                            "member_name": w_name,
                            "model_requested": w_model,
                            "type_name": "swarm_worker",
                            "parent_id": spawner_cid,
                            "created_at": convos.get(w_cid, {}).get("first_turn_ts", ""),
                        }
                except Exception:
                    pass

        # Override any poisoned Strategy-4 sibling parent_convo_id links with authoritative swarm parent links
        if authoritative_swarm_parent:
            filtered_pairs: List[Tuple[str, str]] = [
                (pid, cid)
                for pid, cid in parent_child_pairs
                if cid not in authoritative_swarm_parent and cid not in native_swarm_roots
            ]
            for w_cid, spawner_cid in authoritative_swarm_parent.items():
                filtered_pairs.append((spawner_cid, w_cid))
            parent_child_pairs = filtered_pairs

        # 4. Load dominant model_id per conversation from steps_archive
        cur.execute(
            """
            SELECT convo_id, model_id, model_name, COUNT(*) as cnt
            FROM steps_archive
            WHERE model_id IS NOT NULL AND model_id != ''
            GROUP BY convo_id, model_id
            ORDER BY cnt DESC
            """
        )
        convo_models: Dict[str, Tuple[str, str]] = {}
        for cid, mid, mname, _ in cur.fetchall():
            if cid not in convo_models:
                convo_models[cid] = (mid, mname or get_model_display_name(mid, pricing_models))

        # Build clean acyclic tree mapping
        child_to_parent: Dict[str, str] = {}
        parent_to_children: Dict[str, List[str]] = {}

        for pid, cid in parent_child_pairs:
            # Prevent cycle: if cid is already an ancestor of pid, ignore
            ancestor = child_to_parent.get(pid)
            has_cycle = False
            while ancestor:
                if ancestor == cid:
                    has_cycle = True
                    break
                ancestor = child_to_parent.get(ancestor)

            if not has_cycle and cid not in child_to_parent:
                child_to_parent[cid] = pid
                parent_to_children.setdefault(pid, []).append(cid)

        # Identify all authoritative swarm roots (orchestrators that have children and are NOT children themselves)
        all_parents = set(parent_to_children.keys())
        true_roots = [p for p in all_parents if p not in child_to_parent]

        currency_cfg = pricing_models.get("currency", {})
        usd_to_gbp_fx = currency_cfg.get("usd_to_gbp_fx_rate", 0.79)

        swarms: List[Dict[str, Any]] = []

        for root_id in true_roots:
            root_info = convos.get(root_id, {
                "convo_id": root_id,
                "title": "Orchestrator Session",
                "workspace_name": "Workspace",
                "workspace_path": "",
                "turn_count": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "cached_tokens": 0,
                "thinking_tokens": 0,
                "estimated_cost_usd": 0.0,
                "first_turn_ts": "",
                "last_turn_ts": "",
            })

            # Traverse all descendants recursively
            descendants: List[str] = []
            queue = list(parent_to_children.get(root_id, []))
            visited = {root_id}

            while queue:
                curr_cid = queue.pop(0)
                if curr_cid not in visited:
                    visited.add(curr_cid)
                    descendants.append(curr_cid)
                    queue.extend(parent_to_children.get(curr_cid, []))

            if not descendants:
                continue

            # Compute swarm economics & detailed token metrics
            total_swarm_turns = 0
            total_swarm_tokens = 0
            total_input_tokens = 0
            total_cached_tokens = 0
            total_output_tokens = 0
            total_thinking_tokens = 0
            total_answer_tokens = 0
            total_swarm_cost_usd = 0.0
            root_tokens = 0
            root_cost_usd = float(root_info.get("estimated_cost_usd", 0.0))
            subagents_tokens = 0
            subagents_cost_usd = 0.0

            tier_stats = {
                TIER_MECHANICAL: {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "label": "Tier 1: Mechanical (Flash Lite)"},
                TIER_ENGINEERING: {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "label": "Tier 2: Engineering (Fast Agent)"},
                TIER_ARCHITECTURE: {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "label": "Tier 3: Architecture (Pro Low)"},
                TIER_OTHER: {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "label": "Other / Custom Model"},
            }

            nodes: List[Dict[str, Any]] = []
            edges: List[Dict[str, Any]] = []

            min_ts = root_info.get("first_turn_ts") or ""
            max_ts = root_info.get("last_turn_ts") or ""

            # 1. Root node
            root_mid, root_mname = convo_models.get(root_id, ("1318", "Gemini 3.8 Flash (High)"))
            r_inp = int(root_info.get("total_input_tokens", 0))
            r_out = int(root_info.get("total_output_tokens", 0))
            r_cac = int(root_info.get("cached_tokens", 0))
            r_thk = int(root_info.get("thinking_tokens", 0))
            r_ans = max(0, r_out - r_thk)
            r_cache_pct = round((r_cac / r_inp * 100.0) if r_inp > 0 else 0.0, 1)
            r_toks = r_inp + r_out

            root_tokens = r_toks
            total_swarm_tokens += r_toks
            total_input_tokens += r_inp
            total_cached_tokens += r_cac
            total_output_tokens += r_out
            total_thinking_tokens += r_thk
            total_answer_tokens += r_ans
            total_swarm_turns += int(root_info.get("turn_count", 0))
            total_swarm_cost_usd += root_cost_usd

            root_agent = root_info.get("agent_name") or "default"
            is_native_swarm = (
                root_id in native_swarm_roots
                or any(
                    (convos.get(d_cid, {}).get("subagent_role") or subagent_metadata.get(d_cid, {}).get("role") or "").startswith("Swarm Worker (")
                    for d_cid in descendants
                )
            )
            topology_mode = "native_swarm" if is_native_swarm else "star_subagent"

            if is_native_swarm:
                root_role_title = "Swarm Coordinator"
                root_member_name = "coordinator"
            elif root_agent == "implementer":
                root_role_title = "Implementer (Orchestrator)"
                root_member_name = root_agent
            elif root_agent == "auditor":
                root_role_title = "Auditor (Orchestrator)"
                root_member_name = root_agent
            elif root_agent != "default":
                root_role_title = f"{root_agent.capitalize()} (Orchestrator)"
                root_member_name = root_agent
            else:
                root_role_title = "Root Orchestrator"
                root_member_name = "coordinator"

            r_t1_inp = int(root_info.get("turn1_input_tokens", 0))
            r_t1_cac = int(root_info.get("turn1_cached_tokens", 0))

            nodes.append({
                "id": root_id,
                "title": root_info.get("title", root_role_title),
                "role": root_role_title,
                "agent_name": root_agent,
                "member_name": root_member_name,
                "tier": "orchestrator",
                "model_id": root_mid,
                "model_name": root_mname,
                "short_badge": _get_short_badge(root_mid, root_mname),
                "is_infra": False,
                "depth": 0,
                "turn1_input_tokens": r_t1_inp,
                "turn1_cached_tokens": r_t1_cac,
                "board_posts": 0,
                "turn_count": int(root_info.get("turn_count", 0)),
                "tokens_total": r_toks,
                "input_tokens": r_inp,
                "cached_tokens": r_cac,
                "cache_hit_pct": r_cache_pct,
                "output_tokens": r_out,
                "thinking_tokens": r_thk,
                "answer_tokens": r_ans,
                "cost_usd": round(root_cost_usd, 4),
                "cost_gbp": round(root_cost_usd * usd_to_gbp_fx, 4),
                "created_at": root_info.get("first_turn_ts", ""),
                "is_root": True,
            })

            # 2. Child nodes and edges
            for cid in descendants:
                c_info = convos.get(cid, {})
                c_pid = child_to_parent.get(cid, root_id)
                meta = subagent_metadata.get(cid, {})
                c_agent = c_info.get("agent_name") or meta.get("agent_name") or "default"
                c_sub_role = c_info.get("subagent_role") or meta.get("role") or ""

                c_mid, c_mname = convo_models.get(cid, ("", ""))
                req_model = str(meta.get("model_requested") or "")
                tier_key = classify_subagent_tier(c_mid or req_model)
                if not c_mid:
                    c_ts = c_info.get("first_turn_ts") or meta.get("timestamp")
                    if req_model.lower() == "inherit" and root_mid:
                        c_mid = root_mid
                        tier_key = classify_subagent_tier(c_mid)
                    elif tier_key == TIER_MECHANICAL:
                        c_mid = resolve_tier_model(tier_key, c_ts)
                    elif tier_key == TIER_ENGINEERING:
                        c_mid = "1322"
                    else:
                        c_mid = resolve_tier_model(req_model or "pro", c_ts)
                    c_mname = get_model_display_name(c_mid, pricing_models)

                c_inp = int(c_info.get("total_input_tokens", 0))
                c_out = int(c_info.get("total_output_tokens", 0))
                c_cac = int(c_info.get("cached_tokens", 0))
                c_thk = int(c_info.get("thinking_tokens", 0))
                c_ans = max(0, c_out - c_thk)
                c_cache_pct = round((c_cac / c_inp * 100.0) if c_inp > 0 else 0.0, 1)
                c_toks = c_inp + c_out
                c_turns = int(c_info.get("turn_count", 0))
                c_cost = float(c_info.get("estimated_cost_usd", 0.0))
                c_t1_inp = int(c_info.get("turn1_input_tokens", 0))
                c_t1_cac = int(c_info.get("turn1_cached_tokens", 0))

                subagents_tokens += c_toks
                subagents_cost_usd += c_cost
                total_swarm_tokens += c_toks
                total_input_tokens += c_inp
                total_cached_tokens += c_cac
                total_output_tokens += c_out
                total_thinking_tokens += c_thk
                total_answer_tokens += c_ans
                total_swarm_turns += c_turns
                total_swarm_cost_usd += c_cost

                # Accumulate tier stats
                tier_stats[tier_key]["count"] += 1
                tier_stats[tier_key]["turns"] += c_turns
                tier_stats[tier_key]["tokens"] += c_toks
                tier_stats[tier_key]["cost_usd"] += c_cost

                # Update time bounds
                f_ts = c_info.get("first_turn_ts")
                l_ts = c_info.get("last_turn_ts")
                if f_ts and (not min_ts or f_ts < min_ts):
                    min_ts = f_ts
                if l_ts and (not max_ts or l_ts > max_ts):
                    max_ts = l_ts

                role_label = c_sub_role or meta.get("role") or c_info.get("title") or f"Subagent ({tier_key.title()})"
                member_name = meta.get("member_name") or _extract_member_name(c_sub_role or role_label, c_agent)
                is_infra = bool(
                    member_name.lower().startswith("monitor")
                    or member_name.lower().startswith("narrator")
                )
                node_depth = 0 if is_infra else (1 if c_pid == root_id else 2)
                if len(role_label) > 40:
                    role_label = role_label[:37] + "..."

                nodes.append({
                    "id": cid,
                    "parent_id": c_pid,
                    "title": c_info.get("title", role_label),
                    "role": role_label,
                    "agent_name": c_agent,
                    "member_name": member_name,
                    "subagent_role": c_sub_role,
                    "tier": tier_key,
                    "model_id": c_mid,
                    "model_name": c_mname,
                    "short_badge": _get_short_badge(c_mid, c_mname),
                    "is_infra": is_infra,
                    "depth": node_depth,
                    "turn1_input_tokens": c_t1_inp,
                    "turn1_cached_tokens": c_t1_cac,
                    "board_posts": 0,
                    "turn_count": c_turns,
                    "tokens_total": c_toks,
                    "input_tokens": c_inp,
                    "cached_tokens": c_cac,
                    "cache_hit_pct": c_cache_pct,
                    "output_tokens": c_out,
                    "thinking_tokens": c_thk,
                    "answer_tokens": c_ans,
                    "cost_usd": round(c_cost, 4),
                    "cost_gbp": round(c_cost * usd_to_gbp_fx, 4),
                    "created_at": f_ts or meta.get("created_at", ""),
                    "is_root": False,
                })

                edges.append({
                    "source": c_pid,
                    "target": cid,
                    "role": role_label,
                    "tier": tier_key,
                })

            # 3. Parse board.jsonl (when present) for peer_edges, board_posts, and synthesizer depth promotion
            peer_edges: List[Dict[str, Any]] = []
            swarm_dir = native_swarm_roots.get(root_id, {}).get("swarm_dir")
            if swarm_dir is None:
                candidate_dir = Path(antigravity_dir) / "brain" / root_id / ".system_generated" / "swarm"
                if candidate_dir.exists():
                    swarm_dir = candidate_dir

            if swarm_dir is not None and (swarm_dir / "board.jsonl").exists():
                board_file = swarm_dir / "board.jsonl"
                member_to_node: Dict[str, Dict[str, Any]] = {}
                for n_obj in nodes:
                    m_key = str(n_obj.get("member_name") or "").strip()
                    if m_key:
                        member_to_node[m_key] = n_obj
                    if n_obj.get("is_root"):
                        member_to_node["coordinator"] = n_obj

                seq_to_author: Dict[int, Tuple[str, str]] = {}
                board_entries: List[Dict[str, Any]] = []
                try:
                    for raw_line in board_file.read_text(encoding="utf-8").splitlines():
                        raw_line = raw_line.strip()
                        if not raw_line:
                            continue
                        entry = json.loads(raw_line)
                        if not isinstance(entry, dict):
                            continue
                        board_entries.append(entry)
                        seq_num = int(entry.get("seq") or 0)
                        author = str(entry.get("agent") or "").strip()
                        kind = str(entry.get("kind") or "").strip()
                        if seq_num > 0 and author:
                            seq_to_author[seq_num] = (author, kind)
                        if kind != "brief" and author in member_to_node:
                            member_to_node[author]["board_posts"] = int(member_to_node[author].get("board_posts", 0)) + 1
                except Exception:
                    board_entries = []

                mention_counts: Dict[Tuple[str, str], int] = {}
                citation_seqs: Dict[Tuple[str, str], List[int]] = {}
                cited_peers_by_member: Dict[str, set] = {}

                mention_rx = re.compile(r"@([a-zA-Z0-9_-]+)")
                citation_rx = re.compile(r"#(\d+)")

                for entry in board_entries:
                    if str(entry.get("kind") or "") == "brief":
                        continue
                    author = str(entry.get("agent") or "").strip()
                    text = str(entry.get("text") or "")
                    if not author or author not in member_to_node or not text:
                        continue
                    src_cid = member_to_node[author]["id"]

                    for m_match in mention_rx.finditer(text):
                        tgt_member = m_match.group(1).strip()
                        if tgt_member not in member_to_node or tgt_member == author:
                            continue
                        if (author != "coordinator" and tgt_member != "coordinator") or author.startswith("monitor"):
                            tgt_cid = member_to_node[tgt_member]["id"]
                            mention_counts[(src_cid, tgt_cid)] = mention_counts.get((src_cid, tgt_cid), 0) + 1

                    for c_match in citation_rx.finditer(text):
                        ref_seq = int(c_match.group(1))
                        cited_author, cited_kind = seq_to_author.get(ref_seq, ("", ""))
                        if (
                            not cited_author
                            or cited_kind == "brief"
                            or cited_author not in member_to_node
                            or cited_author == author
                        ):
                            continue
                        if author != "coordinator" and cited_author != "coordinator":
                            tgt_cid = member_to_node[cited_author]["id"]
                            seqs_list = citation_seqs.setdefault((src_cid, tgt_cid), [])
                            if ref_seq not in seqs_list:
                                seqs_list.append(ref_seq)
                            cited_peers_by_member.setdefault(author, set()).add(cited_author)

                for (src_cid, tgt_cid), cnt in mention_counts.items():
                    peer_edges.append({
                        "source": src_cid,
                        "target": tgt_cid,
                        "kind": "mention",
                        "count": cnt,
                        "label": f"@{cnt}" if cnt > 1 else "@mention",
                    })
                for (src_cid, tgt_cid), seqs_list in citation_seqs.items():
                    label_str = ", ".join(f"#{s}" for s in sorted(seqs_list)[:3])
                    peer_edges.append({
                        "source": src_cid,
                        "target": tgt_cid,
                        "kind": "citation",
                        "count": len(seqs_list),
                        "label": label_str,
                    })

                for m_name, peers in cited_peers_by_member.items():
                    if len(peers) >= 2 and m_name in member_to_node:
                        n_obj = member_to_node[m_name]
                        if not n_obj.get("is_root") and not n_obj.get("is_infra"):
                            n_obj["depth"] = max(2, int(n_obj.get("depth", 1)))

            # Calculate duration
            duration_sec = 0.0
            if min_ts and max_ts:
                try:
                    dt_start = datetime.fromisoformat(min_ts.replace("Z", "+00:00"))
                    dt_end = datetime.fromisoformat(max_ts.replace("Z", "+00:00"))
                    duration_sec = max(0.0, (dt_end - dt_start).total_seconds())
                except (ValueError, TypeError):
                    duration_sec = 0.0

            for t_data in tier_stats.values():
                t_data["cost_usd"] = round(t_data["cost_usd"], 4)
                t_data["cost_gbp"] = round(t_data["cost_usd"] * usd_to_gbp_fx, 4)

            swarm_cache_pct = round((total_cached_tokens / total_input_tokens * 100.0) if total_input_tokens > 0 else 0.0, 1)
            toks_per_turn = round(total_swarm_tokens / total_swarm_turns) if total_swarm_turns > 0 else 0
            burn_rate_min = round((total_swarm_tokens / (duration_sec / 60.0)), 1) if duration_sec >= 60 else None

            # Cost segregation: Imputed API Value (avoided cost) vs Actual Overages
            avoided_cost_usd = round(total_swarm_cost_usd, 4)
            avoided_cost_gbp = round(total_swarm_cost_usd * usd_to_gbp_fx, 4)
            actual_overage_credits = 0  # In-quota subscription coverage
            actual_overage_gbp = 0.0

            infra_nodes = [n for n in nodes if n.get("is_infra")]
            infra_workers_count = len(infra_nodes)
            infra_tokens = sum(int(n.get("tokens_total", 0)) for n in infra_nodes)
            infra_cost_usd = round(sum(float(n.get("cost_usd", 0.0)) for n in infra_nodes), 4)
            turn1_ambient_tokens = sum(int(n.get("turn1_input_tokens", 0)) for n in nodes)
            swarm_title = (
                native_swarm_roots.get(root_id, {}).get("swarm_title")
                or root_info.get("title", "Multi-Agent Swarm Orchestrator")
            )

            swarm_payload = {
                "swarm_id": root_id,
                "root_convo_id": root_id,
                "root_title": root_info.get("title", "Multi-Agent Swarm Orchestrator"),
                "swarm_title": swarm_title,
                "topology_mode": topology_mode,
                "root_agent_name": root_agent,
                "root_role_title": root_role_title,
                "workspace_name": root_info.get("workspace_name", "Workspace"),
                "workspace_path": root_info.get("workspace_path", ""),
                "created_at": min_ts,
                "last_activity": max_ts,
                "duration_seconds": round(duration_sec, 1),
                "duration_formatted": format_duration(duration_sec),
                "total_turns": total_swarm_turns,
                "total_swarm_tokens": total_swarm_tokens,
                "total_input_tokens": total_input_tokens,
                "total_cached_tokens": total_cached_tokens,
                "cache_hit_pct": swarm_cache_pct,
                "total_output_tokens": total_output_tokens,
                "total_thinking_tokens": total_thinking_tokens,
                "total_answer_tokens": total_answer_tokens,
                "tokens_per_turn": toks_per_turn,
                "burn_rate_tokens_per_min": burn_rate_min,
                "avoided_cost_usd": avoided_cost_usd,
                "avoided_cost_gbp": avoided_cost_gbp,
                "actual_overage_credits": actual_overage_credits,
                "actual_overage_gbp": actual_overage_gbp,
                "is_overage": False,
                # Backward-compatible aliases
                "total_swarm_cost_usd": avoided_cost_usd,
                "total_swarm_cost_gbp": avoided_cost_gbp,
                "root_tokens": root_tokens,
                "root_cost_usd": round(root_cost_usd, 4),
                "root_cost_gbp": round(root_cost_usd * usd_to_gbp_fx, 4),
                "subagents_count": len(descendants),
                "subagents_tokens": subagents_tokens,
                "subagents_cost_usd": round(subagents_cost_usd, 4),
                "subagents_cost_gbp": round(subagents_cost_usd * usd_to_gbp_fx, 4),
                "subagent_share_pct": round((subagents_cost_usd / total_swarm_cost_usd * 100.0) if total_swarm_cost_usd > 0 else 0.0, 1),
                "infra_workers_count": infra_workers_count,
                "infra_tokens": infra_tokens,
                "infra_cost_usd": infra_cost_usd,
                "turn1_ambient_tokens": turn1_ambient_tokens,
                "tier_breakdown": tier_stats,
                "nodes": nodes,
                "edges": edges,
                "peer_edges": peer_edges,
            }
            swarms.append(swarm_payload)

        # Order swarms by default by most recent activity timestamp descending
        swarms.sort(key=lambda s: s.get("last_activity") or s.get("created_at") or "", reverse=True)
        return swarms
    except (sqlite3.Error, OSError) as exc:
        import sys
        sys.stderr.write(f"[swarm] Error loading swarms from vault: {exc}\n")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except sqlite3.Error:
                pass


def build_swarms_summary(
    swarms: List[Dict[str, Any]],
    pricing_models: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build portfolio-level swarm summary across all multi-agent swarms.
    """
    if pricing_models is None:
        pricing_models = load_pricing()

    currency_cfg = pricing_models.get("currency", {})
    usd_to_gbp_fx = currency_cfg.get("usd_to_gbp_fx_rate", 0.79)

    total_swarms = len(swarms)
    total_subagents = sum(s.get("subagents_count", 0) for s in swarms)
    total_turns = sum(s.get("total_turns", 0) for s in swarms)
    total_tokens = sum(s.get("total_swarm_tokens", 0) for s in swarms)
    total_input_tokens = sum(s.get("total_input_tokens", 0) for s in swarms)
    total_cached_tokens = sum(s.get("total_cached_tokens", 0) for s in swarms)
    global_cache_hit_pct = round((total_cached_tokens / total_input_tokens * 100.0) if total_input_tokens > 0 else 0.0, 1)
    total_output_tokens = sum(s.get("total_output_tokens", 0) for s in swarms)
    total_thinking_tokens = sum(s.get("total_thinking_tokens", 0) for s in swarms)
    total_answer_tokens = sum(s.get("total_answer_tokens", 0) for s in swarms)

    total_avoided_usd = sum(s.get("avoided_cost_usd", s.get("total_swarm_cost_usd", 0.0)) for s in swarms)
    total_avoided_gbp = sum(s.get("avoided_cost_gbp", s.get("total_swarm_cost_gbp", 0.0)) for s in swarms)
    total_overage_credits = sum(s.get("actual_overage_credits", 0) for s in swarms)
    total_overage_gbp = sum(s.get("actual_overage_gbp", 0.0) for s in swarms)
    total_overage_usd = round(total_overage_gbp / usd_to_gbp_fx, 4) if usd_to_gbp_fx > 0 else 0.0

    unique_projects = sorted(list(set(s.get("workspace_name", "Workspace") for s in swarms if s.get("workspace_name"))))
    avg_tokens_per_turn = round(total_tokens / total_turns) if total_turns > 0 else 0

    global_tiers = {
        TIER_MECHANICAL: {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "cost_gbp": 0.0, "label": "Tier 1: Mechanical (Flash Lite)"},
        TIER_ENGINEERING: {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "cost_gbp": 0.0, "label": "Tier 2: Engineering (Fast Agent)"},
        TIER_ARCHITECTURE: {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "cost_gbp": 0.0, "label": "Tier 3: Architecture (Pro Low)"},
        TIER_OTHER: {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "cost_gbp": 0.0, "label": "Other / Custom Model"},
    }

    for s in swarms:
        tb = s.get("tier_breakdown", {})
        for k, v in tb.items():
            if k in global_tiers:
                global_tiers[k]["count"] += v.get("count", 0)
                global_tiers[k]["turns"] += v.get("turns", 0)
                global_tiers[k]["tokens"] += v.get("tokens", 0)
                global_tiers[k]["cost_usd"] += v.get("cost_usd", 0.0)
                global_tiers[k]["cost_gbp"] += v.get("cost_gbp", 0.0)

    for k in global_tiers:
        global_tiers[k]["cost_usd"] = round(global_tiers[k]["cost_usd"], 4)
        global_tiers[k]["cost_gbp"] = round(global_tiers[k]["cost_gbp"], 4)

    native_swarms_count = sum(1 for s in swarms if s.get("topology_mode") == "native_swarm")
    star_swarms_count = total_swarms - native_swarms_count
    total_infra_tokens = sum(int(s.get("infra_tokens", 0)) for s in swarms)
    total_turn1_ambient_tokens = sum(int(s.get("turn1_ambient_tokens", 0)) for s in swarms)

    return {
        "total_swarms": total_swarms,
        "native_swarms_count": native_swarms_count,
        "star_swarms_count": star_swarms_count,
        "total_subagents": total_subagents,
        "total_swarm_turns": total_turns,
        "total_swarm_tokens": total_tokens,
        "total_input_tokens": total_input_tokens,
        "total_cached_tokens": total_cached_tokens,
        "global_cache_hit_pct": global_cache_hit_pct,
        "total_output_tokens": total_output_tokens,
        "total_thinking_tokens": total_thinking_tokens,
        "total_answer_tokens": total_answer_tokens,
        "total_infra_tokens": total_infra_tokens,
        "total_turn1_ambient_tokens": total_turn1_ambient_tokens,
        "avg_tokens_per_turn": avg_tokens_per_turn,
        "total_avoided_cost_usd": round(total_avoided_usd, 4),
        "total_avoided_cost_gbp": round(total_avoided_gbp, 4),
        "total_overage_credits": total_overage_credits,
        "total_overage_usd": round(total_overage_usd, 4),
        "total_overage_gbp": round(total_overage_gbp, 4),
        "unique_projects": unique_projects,
        "unique_projects_count": len(unique_projects),
        # Backward-compatible aliases
        "total_swarm_cost_usd": round(total_avoided_usd, 4),
        "total_swarm_cost_gbp": round(total_avoided_gbp, 4),
        "global_tier_breakdown": global_tiers,
        "swarms": swarms,
    }


def _safe_int_val(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    try:
        s = str(val).strip()
        return int(s) if s else default
    except (ValueError, TypeError):
        return default


def _safe_float_val(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    if isinstance(val, float):
        return val
    if isinstance(val, int):
        return float(val)
    try:
        s = str(val).strip()
        return float(s) if s else default
    except (ValueError, TypeError):
        return default


def compute_recursive_session_rollups(
    conversations: Union[List[Dict[str, Any]], Dict[str, Dict[str, Any]]],
    lineage_data: Optional[Any] = None,
) -> Union[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Compute recursive session tree rollups across parent orchestrators and descendant subagents.

    Calculates:
    - tree_total_input_tokens: parent input + sum of descendant input tokens
    - tree_total_output_tokens: parent output + sum of descendant output tokens
    - tree_total_thinking_tokens: parent thinking + sum of descendant thinking tokens
    - tree_total_cost_usd: parent cost + sum of descendant cost
    - tree_children_count: total count of descendant subagents
    - has_children: boolean (True if session has direct subagent children)
    - child_ids: list of direct child conversation IDs
    """
    if conversations is None:
        return []

    is_dict = isinstance(conversations, dict)
    raw_list = list(conversations.values()) if is_dict else (conversations if isinstance(conversations, list) else [])
    convo_list = [c for c in raw_list if isinstance(c, dict)]

    convo_map: Dict[str, Dict[str, Any]] = {}
    for c in convo_list:
        cid = str(c.get("convo_id") or c.get("id") or "").strip()
        if cid:
            convo_map[cid] = c

    parent_to_children: Dict[str, List[str]] = {}

    def add_child(parent_id: Any, child_id: Any) -> None:
        if parent_id is None or child_id is None:
            return
        p = str(parent_id).strip()
        ch = str(child_id).strip()
        if not p or not ch or p == ch:
            return
        if p.lower() in ("none", "null", "undefined") or ch.lower() in ("none", "null", "undefined"):
            return
        if p in convo_map and ch in convo_map:
            p_parent = str(convo_map[p].get("parent_convo_id") or convo_map[p].get("parent_id") or "").strip()
            if p_parent == ch and not convo_map[ch].get("is_subagent"):
                return
        if p in parent_to_children.get(ch, []):
            return
        children = parent_to_children.setdefault(p, [])
        if ch not in children:
            children.append(ch)

    lineage_node_info: Dict[str, Dict[str, Any]] = {}

    def _process_swarm_dict(s_dict: Dict[str, Any]) -> None:
        if not isinstance(s_dict, dict):
            return
        if "edges" in s_dict and isinstance(s_dict["edges"], list):
            for edge in s_dict["edges"]:
                if isinstance(edge, dict):
                    add_child(edge.get("source"), edge.get("target"))
        if "nodes" in s_dict and isinstance(s_dict["nodes"], list):
            for node in s_dict["nodes"]:
                if isinstance(node, dict) and "id" in node:
                    nid = str(node["id"]).strip()
                    if nid:
                        lineage_node_info[nid] = node
                    if node.get("parent_id"):
                        add_child(node.get("parent_id"), node.get("id"))

    if lineage_data is not None:
        if isinstance(lineage_data, list):
            for item in lineage_data:
                if isinstance(item, tuple) and len(item) == 2:
                    add_child(item[0], item[1])
                elif isinstance(item, dict):
                    if "edges" in item or "nodes" in item:
                        _process_swarm_dict(item)
                    if "source" in item and "target" in item:
                        add_child(item.get("source"), item.get("target"))
                    elif "parent_id" in item and "child_id" in item:
                        add_child(item.get("parent_id"), item.get("child_id"))
                    elif "parent" in item and "child" in item:
                        add_child(item.get("parent"), item.get("child"))
        elif isinstance(lineage_data, dict):
            if "swarms" in lineage_data and isinstance(lineage_data["swarms"], list):
                for s in lineage_data["swarms"]:
                    _process_swarm_dict(s)
            elif "edges" in lineage_data or "nodes" in lineage_data:
                _process_swarm_dict(lineage_data)
            elif "parent_to_children" in lineage_data and isinstance(lineage_data["parent_to_children"], dict):
                for p, chs in lineage_data["parent_to_children"].items():
                    if isinstance(chs, (list, tuple, set)):
                        for ch in chs:
                            add_child(p, ch)
                    elif isinstance(chs, str):
                        add_child(p, chs)
            else:
                for k, v in lineage_data.items():
                    if isinstance(v, (list, tuple, set)):
                        for ch in v:
                            if isinstance(ch, (str, int)):
                                add_child(k, ch)
                    elif isinstance(v, (str, int)) and (str(v) in convo_map or str(k) in convo_map):
                        add_child(k, v)

    for c in convo_list:
        cid = str(c.get("convo_id") or c.get("id") or "").strip()
        pid = c.get("parent_convo_id") or c.get("parent_id")
        if pid and cid:
            add_child(pid, cid)
        if "child_ids" in c and isinstance(c["child_ids"], (list, tuple, set)):
            for ch in c["child_ids"]:
                add_child(cid, ch)

    for p_id, ch_ids in parent_to_children.items():
        for ch_id in ch_ids:
            if ch_id in convo_map:
                ch_conv = convo_map[ch_id]
                if not ch_conv.get("parent_convo_id"):
                    ch_conv["parent_convo_id"] = p_id
                ch_conv["is_subagent"] = True
                if not ch_conv.get("subagent_role") and ch_id in lineage_node_info:
                    role_val = lineage_node_info[ch_id].get("role") or lineage_node_info[ch_id].get("subagent_role")
                    if role_val and str(role_val).lower() != "orchestrator":
                        ch_conv["subagent_role"] = str(role_val)

    def _get_inp(conv: Dict[str, Any]) -> int:
        return _safe_int_val(conv.get("total_input_tokens")) or _safe_int_val(conv.get("input_tokens"))

    def _get_out(conv: Dict[str, Any]) -> int:
        return _safe_int_val(conv.get("total_output_tokens")) or _safe_int_val(conv.get("output_tokens"))

    def _get_thk(conv: Dict[str, Any]) -> int:
        return _safe_int_val(conv.get("thinking_tokens"))

    def _get_cost(conv: Dict[str, Any]) -> float:
        return _safe_float_val(conv.get("estimated_cost_usd")) or _safe_float_val(conv.get("cost_usd"))

    for c in convo_list:
        cid = str(c.get("convo_id") or c.get("id") or "").strip()
        if not cid:
            c["tree_total_input_tokens"] = _get_inp(c)
            c["tree_total_output_tokens"] = _get_out(c)
            c["tree_total_thinking_tokens"] = _get_thk(c)
            c["tree_total_cost_usd"] = round(_get_cost(c), 4)
            c["tree_children_count"] = 0
            c["has_children"] = False
            c["child_ids"] = []
            continue

        direct_children = list(parent_to_children.get(cid, []))

        # BFS traversal for all descendants with cycle detection
        descendants: List[str] = []
        visited = {cid}
        queue = list(direct_children)

        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                descendants.append(curr)
                for nxt in parent_to_children.get(curr, []):
                    if nxt not in visited:
                        queue.append(nxt)

        desc_inp = 0
        desc_out = 0
        desc_thk = 0
        desc_cost = 0.0

        for d_id in descendants:
            if d_id in convo_map:
                dc = convo_map[d_id]
                desc_inp += _get_inp(dc)
                desc_out += _get_out(dc)
                desc_thk += _get_thk(dc)
                desc_cost += _get_cost(dc)
            elif d_id in lineage_node_info:
                dn = lineage_node_info[d_id]
                desc_inp += _get_inp(dn)
                desc_out += _get_out(dn)
                desc_thk += _get_thk(dn)
                desc_cost += _get_cost(dn)

        c["tree_total_input_tokens"] = _get_inp(c) + desc_inp
        c["tree_total_output_tokens"] = _get_out(c) + desc_out
        c["tree_total_thinking_tokens"] = _get_thk(c) + desc_thk
        c["tree_total_cost_usd"] = round(_get_cost(c) + desc_cost, 4)
        c["tree_children_count"] = len(descendants)
        c["has_children"] = len(direct_children) > 0
        c["child_ids"] = direct_children

    return conversations
