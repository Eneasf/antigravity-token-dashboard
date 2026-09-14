"""
Tool Execution & Skill Performance Analytics Engine.

Aggregates tool invocations, execution frequencies, sandbox bypass ratios,
and error rates from the Antigravity Telemetry Vault (data/antigravity_vault.db).

Adheres strictly to:
- ADR-001: Strict Read-Only SQLite Access (`?mode=ro`, uri=True).
- ADR-018: Dedicated Local Telemetry Vault, Hybrid Lossless Archival & Lineage Topology.
- ADR-037: Subagent Swarm Lineage DAG & Tool Performance Intelligence Architecture.
"""

import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Union

DEFAULT_VAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "antigravity_vault.db"

# Canonical tool category classifications
TOOL_CATEGORIES: Dict[str, str] = {
    # Terminal & Execution
    "run_command": "terminal",
    "manage_task": "terminal",
    "schedule": "terminal",
    # Filesystem & Code
    "view_file": "filesystem",
    "write_to_file": "filesystem",
    "replace_file_content": "filesystem",
    "multi_replace_file_content": "filesystem",
    "grep_search": "filesystem",
    "find_by_name": "filesystem",
    "list_dir": "filesystem",
    # Subagent Orchestration
    "invoke_subagent": "subagents",
    "send_message": "subagents",
    "manage_subagents": "subagents",
    "define_subagent": "subagents",
    # Web & Browser
    "search_web": "web",
    "read_url_content": "web",
    "mcp_chrome_devtools_evaluate_script": "web",
    "mcp_chrome_devtools_new_page": "web",
    # User Interaction
    "ask_question": "interactive",
    "ask_permission": "interactive",
    "list_permissions": "interactive",
    # Media & Creative
    "generate_image": "media",
    # MCP & Extensibility
    "call_mcp_tool": "mcp",
}


def classify_tool_category(tool_name: str) -> str:
    """Classify tool name into standard operational category."""
    if tool_name in TOOL_CATEGORIES:
        return TOOL_CATEGORIES[tool_name]
    if tool_name.startswith("mcp_") or "mcp" in tool_name:
        return "mcp"
    return "other"


def is_error_result(result_summary: Optional[str]) -> bool:
    """Heuristic check for execution failure in result summary."""
    if not result_summary:
        return False
    res = result_summary.lower()
    # Explicit success with code 0 is NOT an error
    if "exited with code 0" in res:
        return False
    # Non-zero exit codes
    if "exited with code" in res and "exited with code 0" not in res:
        return True
    # Common error keywords in stderr/output
    if any(k in res for k in ("fatal:", "traceback (most recent call last):", "permission denied", "operation not permitted")):
        return True
    if "error:" in res or "exception:" in res:
        return True
    return False


def is_sandbox_bypass(arguments_json: Optional[str]) -> bool:
    """Detect if tool execution was configured with BypassSandbox: true."""
    if not arguments_json:
        return False
    # Normalized check avoiding space sensitivity
    cleaned = arguments_json.replace(" ", "")
    return '"BypassSandbox":true' in cleaned or '"BypassSandbox":True' in cleaned


def extract_tool_analytics(
    vault_path: Union[str, Path] = DEFAULT_VAULT_PATH,
) -> Dict[str, Any]:
    """
    Extract comprehensive tool execution and skill activation analytics from the Vault.

    Adheres strictly to ADR-001 (read-only SQLite access).
    Returns dictionary with total calls, unique tools, per-tool metrics, categories,
    and skill activation analytics.
    """
    v_file = Path(vault_path).resolve()
    if not v_file.exists():
        return {
            "total_tool_calls": 0,
            "unique_tools_count": 0,
            "tools": {},
            "top_tools": [],
            "categories": {},
            "skills": [],
            "total_skill_activations": 0,
        }

    conn = None
    try:
        conn = sqlite3.connect(f"file:{v_file}?mode=ro", uri=True, timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000;")
        cur = conn.cursor()

        # 1. Total tool calls count
        cur.execute("SELECT COUNT(*) FROM tool_calls_archive")
        total_calls_row = cur.fetchone()
        total_calls = total_calls_row[0] if total_calls_row else 0

        # 2. Per-tool metrics
        cur.execute(
            """
            SELECT tool_name, arguments_json, result_summary
            FROM tool_calls_archive
            """
        )
        tool_data: Dict[str, Dict[str, Any]] = {}
        category_counts: Dict[str, int] = {}

        for t_name, args_raw, res_raw in cur.fetchall():
            if not t_name:
                continue

            if t_name not in tool_data:
                cat = classify_tool_category(t_name)
                tool_data[t_name] = {
                    "tool_name": t_name,
                    "category": cat,
                    "call_count": 0,
                    "sandbox_bypass_count": 0,
                    "error_count": 0,
                }

            tool_data[t_name]["call_count"] += 1
            cat = tool_data[t_name]["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1

            if is_sandbox_bypass(args_raw):
                tool_data[t_name]["sandbox_bypass_count"] += 1

            if is_error_result(res_raw):
                tool_data[t_name]["error_count"] += 1

        # Calculate percentages and rates
        for t_info in tool_data.values():
            cnt = t_info["call_count"]
            t_info["frequency_pct"] = round((cnt / total_calls * 100.0) if total_calls > 0 else 0.0, 2)
            t_info["sandbox_bypass_pct"] = round((t_info["sandbox_bypass_count"] / cnt * 100.0) if cnt > 0 else 0.0, 1)
            t_info["error_rate_pct"] = round((t_info["error_count"] / cnt * 100.0) if cnt > 0 else 0.0, 1)

        # Ranked list of top tools
        top_tools = sorted(tool_data.values(), key=lambda t: t["call_count"], reverse=True)

        # Categorical distribution
        categories = {}
        for cat_name, c_cnt in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            categories[cat_name] = {
                "category": cat_name,
                "call_count": c_cnt,
                "frequency_pct": round((c_cnt / total_calls * 100.0) if total_calls > 0 else 0.0, 1),
            }

        # 3. Skill activations
        cur.execute(
            """
            SELECT skill_name, skill_path, activation_type, COUNT(*) as cnt
            FROM skills_archive
            GROUP BY skill_name
            ORDER BY cnt DESC
            """
        )
        skills_list = []
        total_skill_activations = 0
        for s_name, s_path, s_type, cnt in cur.fetchall():
            # Clean skill names (remove wildcards or format placeholders)
            clean_name = s_name.strip()
            if clean_name in ("*", "{sk}"):
                continue
            skills_list.append({
                "skill_name": clean_name,
                "skill_path": s_path or f"skills/{clean_name}/SKILL.md",
                "activation_type": s_type or "referenced",
                "activation_count": cnt,
            })
            total_skill_activations += cnt

        return {
            "total_tool_calls": total_calls,
            "unique_tools_count": len(tool_data),
            "tools": tool_data,
            "top_tools": top_tools,
            "categories": categories,
            "skills": skills_list,
            "total_skill_activations": total_skill_activations,
        }
    except Exception:
        return {
            "total_tool_calls": 0,
            "unique_tools_count": 0,
            "tools": {},
            "top_tools": [],
            "categories": {},
            "skills": [],
            "total_skill_activations": 0,
        }
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
