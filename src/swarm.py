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

from src.aggregator import (
    compute_turn_cost,
    get_model_display_name,
    get_model_rates,
    load_pricing,
)
from src.telemetry_reader import DEFAULT_ANTIGRAVITY_DIR

DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "antigravity_vault.db"

# Canonical subagent tier mappings (ADR-020 / ADR-007)
TIER_MECHANICAL = "mechanical"      # flash_lite -> Model 1050
TIER_ENGINEERING = "engineering"    # flash -> Model 1322
TIER_ARCHITECTURE = "architecture"  # pro -> Model 1036 (or 1016)
TIER_OTHER = "other"


def classify_subagent_tier(model_id_or_tier: Optional[str]) -> str:
    """Classify subagent model ID or requested tier into standard 3-tier taxonomy."""
    if not model_id_or_tier:
        return TIER_OTHER
    val = str(model_id_or_tier).strip().lower()
    if val in ("1050", "flash_lite", "gemini-flash-lite", "flash-lite"):
        return TIER_MECHANICAL
    elif val in ("1322", "flash", "gemini-flash", "fast_agent", "fast-agent"):
        return TIER_ENGINEERING
    elif val in ("1036", "1016", "pro", "pro_low", "pro_high", "gemini-pro"):
        return TIER_ARCHITECTURE
    return TIER_OTHER


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
                except Exception:
                    pass
            subagent_specs = args.get("Subagents", []) if isinstance(args, dict) else []
            combined_text = (res_summary or "") + " " + (args_json or "")
            found_cids = uuid_regex.findall(combined_text)
            # Filter out caller_id itself
            candidate_children = [c for c in found_cids if c != caller_id]

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

        # 2. Add parents from conversations_archive (from M08 sync)
        cur.execute(
            """
            SELECT convo_id, parent_convo_id, title
            FROM conversations_archive
            WHERE parent_convo_id IS NOT NULL AND parent_convo_id != ''
            """
        )
        for child_id, parent_id, c_title in cur.fetchall():
            if child_id != parent_id:
                # Add if not creating a direct cycle
                if (parent_id, child_id) not in parent_child_pairs and (child_id, parent_id) not in parent_child_pairs:
                    parent_child_pairs.append((parent_id, child_id))
                if child_id not in subagent_metadata:
                    # Heuristic role from child title
                    role = "Subagent"
                    if c_title:
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

        # 3. Load all conversations details
        cur.execute(
            """
            SELECT
                convo_id, parent_convo_id, workspace_name, workspace_path,
                title, turn_count, total_input_tokens, total_output_tokens,
                cached_tokens, thinking_tokens, estimated_cost_usd,
                first_turn_ts, last_turn_ts
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
            }

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

            nodes.append({
                "id": root_id,
                "title": root_info.get("title", "Root Orchestrator"),
                "role": "Root Orchestrator",
                "tier": "orchestrator",
                "model_id": root_mid,
                "model_name": root_mname,
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

                c_mid, c_mname = convo_models.get(cid, ("", ""))
                tier_key = classify_subagent_tier(c_mid or meta.get("model_requested"))
                if not c_mid:
                    c_mid = "1050" if tier_key == TIER_MECHANICAL else ("1322" if tier_key == TIER_ENGINEERING else "1036")
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

                role_label = meta.get("role") or c_info.get("title") or f"Subagent ({tier_key.title()})"
                if len(role_label) > 40:
                    role_label = role_label[:37] + "..."

                nodes.append({
                    "id": cid,
                    "parent_id": c_pid,
                    "title": c_info.get("title", role_label),
                    "role": role_label,
                    "tier": tier_key,
                    "model_id": c_mid,
                    "model_name": c_mname,
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

            # Calculate duration
            duration_sec = 0.0
            if min_ts and max_ts:
                try:
                    dt_start = datetime.fromisoformat(min_ts.replace("Z", "+00:00"))
                    dt_end = datetime.fromisoformat(max_ts.replace("Z", "+00:00"))
                    duration_sec = max(0.0, (dt_end - dt_start).total_seconds())
                except Exception:
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

            swarm_payload = {
                "swarm_id": root_id,
                "root_convo_id": root_id,
                "root_title": root_info.get("title", "Multi-Agent Swarm Orchestrator"),
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
                "tier_breakdown": tier_stats,
                "nodes": nodes,
                "edges": edges,
            }
            swarms.append(swarm_payload)

        # Order swarms by default by most recent activity timestamp descending
        swarms.sort(key=lambda s: s.get("last_activity") or s.get("created_at") or "", reverse=True)
        return swarms
    except Exception:
        return []
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
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

    return {
        "total_swarms": total_swarms,
        "total_subagents": total_subagents,
        "total_swarm_turns": total_turns,
        "total_swarm_tokens": total_tokens,
        "total_input_tokens": total_input_tokens,
        "total_cached_tokens": total_cached_tokens,
        "global_cache_hit_pct": global_cache_hit_pct,
        "total_output_tokens": total_output_tokens,
        "total_thinking_tokens": total_thinking_tokens,
        "total_answer_tokens": total_answer_tokens,
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
