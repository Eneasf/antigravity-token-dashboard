#!/usr/bin/env python3
"""
capture_showcase_screenshots.py

Generates high-resolution, privacy-safe UI screenshots in crisp Light Mode for the README.
1. Inlines a rich, realistic, 100% sanitized synthetic demo profile (clean project names, zero local paths).
2. Sets data-theme="light" across all captured view wrappers.
3. Generates standalone HTML view wrappers with direct styling isolation:
   - showcase_hero_quotas.png (Hero Deck & Provider Quota Silos in Light Mode)
   - showcase_swarm_lineage.png (Subagent Swarm Lineage DAG Explorer in Light Mode)
   - showcase_simulator.png (Interactive What-If Workload Simulator in Light Mode)
   - showcase_projects_branches.png (Portfolio & Git Branch Costing with branches expanded)
   - showcase_turns_inspector.png (Turn-by-Turn Telemetry & Thinking Token Inspector)
   - github_social_preview.png (1280x640 Social Card)
4. Captures Retina screenshots via headless Chrome and cleans up temporary files.
"""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "dashboard" / "index.html"
ASSETS_DIR = REPO_ROOT / "docs" / "assets"
CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def get_sanitized_showcase_data() -> dict:
    """Return a realistic, synthetic demo dataset with zero PII reflecting Google AI Ultra (5x)."""
    return {
        "summary": {
            "subscription_status": "SAFE_IN_QUOTA",
            "active_plan": "Google AI Ultra (5x Capacity)",
            "plan_cost_gbp": 79.99,
            "plan_cost_usd": 99.99,
            "plan_renewal_date": "2026-10-13",
            "total_input_tokens": 184520300,
            "total_output_tokens": 3890120,
            "cached_tokens": 173810000,
            "cache_hit_ratio_pct": 94.20,
            "avoided_cost_gbp": 462.80,
            "avoided_cost_usd": 585.50,
            "actual_overage_credits": 0,
            "actual_overage_gbp": 0.0,
            "actual_overage_usd": 0.0,
            "turn_count": 1840,
            "overage_turns": 0,
            "usd_to_gbp_fx_rate": 0.79,
        },
        "quotas": {
            "providers": {
                "gemini": {
                    "provider": "Google Gemini",
                    "family": "gemini",
                    "weekly": {
                        "remaining_pct": 84.2,
                        "used_pct": 15.8,
                        "reset_display": "Sunday, 20 Sep 2026, 17:58 UTC",
                        "reset_countdown_human": "6 days, 22 hours",
                        "status": "NORMAL",
                    },
                    "five_hour": {
                        "remaining_pct": 94.6,
                        "used_pct": 5.4,
                        "tokens_in_window": 18420100,
                        "turns_in_window": 164,
                        "status": "NORMAL",
                        "reset_time": "2026-09-14T03:30:00Z",
                    },
                    "runway": {
                        "bvi": 0.78,
                        "bvi_display": "0.78x",
                        "status_text": "✓ Sustainable (0.78x)",
                        "status_key": "green",
                        "status_sub": "Day 1: +12.4% buffer",
                        "consumed_pct": 15.8,
                        "calendar_time_elapsed_pct": 28.2,
                        "target_daily_budget_pct": 14.3,
                        "exhaustion_eta": "None",
                    },
                    "alarm": {
                        "gemini_weekly_exhausted": False,
                        "gemini_5h_disabled": False,
                    },
                },
                "claude_gpt": {
                    "provider": "Anthropic & OpenAI (Vertex)",
                    "family": "claude_gpt",
                    "weekly": {
                        "remaining_pct": 96.2,
                        "used_pct": 3.8,
                        "reset_display": "7-day rolling window",
                        "status": "NORMAL",
                    },
                    "five_hour": {
                        "remaining_pct": 100.0,
                        "used_pct": 0.0,
                        "tokens_in_window": 0,
                        "turns_in_window": 0,
                        "status": "NORMAL",
                    },
                },
            },
        },
        "currency": {"active": "GBP", "symbol": "£", "usd_to_gbp_rate": 0.79},
        "workspaces": [
            {"workspace": "antigravity-telemetry-engine", "conversation_count": 1, "turn_count": 820, "total_input_tokens": 98240100, "cached_tokens": 92810000, "cache_hit_ratio_pct": 94.47, "estimated_cost_usd": 242.10},
            {"workspace": "cloud-infra-orchestrator", "conversation_count": 1, "turn_count": 490, "total_input_tokens": 48100000, "cached_tokens": 45200000, "cache_hit_ratio_pct": 93.97, "estimated_cost_usd": 128.40},
            {"workspace": "multi-agent-reasoning-framework", "conversation_count": 1, "turn_count": 310, "total_input_tokens": 24200000, "cached_tokens": 22800000, "cache_hit_ratio_pct": 94.21, "estimated_cost_usd": 84.20},
            {"workspace": "document-parsing-engine", "conversation_count": 1, "turn_count": 220, "total_input_tokens": 13980200, "cached_tokens": 12990000, "cache_hit_ratio_pct": 92.92, "estimated_cost_usd": 30.80},
        ],
        "projects": [
            {
                "project_name": "antigravity-telemetry-engine",
                "workspace_path": "/Users/developer/workspaces/antigravity-telemetry-engine",
                "turn_count": 820,
                "total_input_tokens": 98240100,
                "cached_tokens": 92810000,
                "cache_hit_ratio_pct": 94.47,
                "actual_overage_credits": 0,
                "actual_overage_gbp": 0.0,
                "actual_overage_usd": 0.0,
                "estimated_cost_usd": 242.10,
                "estimated_cost_gbp": 191.26,
                "avoided_cost_usd": 242.10,
                "avoided_cost_gbp": 191.26,
                "branches": [
                    {
                        "branch_name": "main",
                        "turn_count": 610,
                        "total_input_tokens": 74900000,
                        "cached_tokens": 70800000,
                        "cache_hit_ratio_pct": 94.53,
                        "avoided_cost_gbp": 145.50,
                        "avoided_cost_usd": 184.18,
                        "actual_overage_credits": 0,
                    },
                    {
                        "branch_name": "feat/git-temporal-branch-attribution",
                        "turn_count": 210,
                        "total_input_tokens": 23340100,
                        "cached_tokens": 22010000,
                        "cache_hit_ratio_pct": 94.30,
                        "avoided_cost_gbp": 45.76,
                        "avoided_cost_usd": 57.92,
                        "actual_overage_credits": 0,
                    },
                ],
            },
            {
                "project_name": "cloud-infra-orchestrator",
                "workspace_path": "/Users/developer/workspaces/cloud-infra-orchestrator",
                "turn_count": 490,
                "total_input_tokens": 48100000,
                "cached_tokens": 45200000,
                "cache_hit_ratio_pct": 93.97,
                "actual_overage_credits": 0,
                "actual_overage_gbp": 0.0,
                "actual_overage_usd": 0.0,
                "avoided_cost_usd": 128.40,
                "avoided_cost_gbp": 101.44,
                "branches": [
                    {
                        "branch_name": "main",
                        "turn_count": 490,
                        "total_input_tokens": 48100000,
                        "cached_tokens": 45200000,
                        "cache_hit_ratio_pct": 93.97,
                        "avoided_cost_gbp": 101.44,
                        "avoided_cost_usd": 128.40,
                        "actual_overage_credits": 0,
                    },
                ],
            },
            {
                "project_name": "multi-agent-reasoning-framework",
                "workspace_path": "/Users/developer/workspaces/multi-agent-reasoning-framework",
                "turn_count": 310,
                "total_input_tokens": 24200000,
                "cached_tokens": 22800000,
                "cache_hit_ratio_pct": 94.21,
                "actual_overage_credits": 0,
                "actual_overage_gbp": 0.0,
                "actual_overage_usd": 0.0,
                "avoided_cost_usd": 84.20,
                "avoided_cost_gbp": 66.52,
                "branches": [
                    {"branch_name": "main", "turn_count": 310, "total_input_tokens": 24200000, "cached_tokens": 22800000, "cache_hit_ratio_pct": 94.21, "avoided_cost_gbp": 66.52, "avoided_cost_usd": 84.20, "actual_overage_credits": 0},
                ],
            },
        ],
        "conversations": [
            {
                "convo_id": "c-101",
                "title": "Git Reflog Temporal Branch Attribution Engine",
                "workspace": "antigravity-telemetry-engine",
                "git_branch": "feat/git-temporal-branch-attribution",
                "turn_count": 4,
                "total_input_tokens": 512800,
                "cached_tokens": 486200,
                "cache_hit_ratio_pct": 94.81,
                "avoided_cost_gbp": 0.84,
                "avoided_cost_usd": 1.06,
                "models_used": ["Gemini 3.8 Flash (High)"],
                "turns": [
                    {
                        "step_idx": 1,
                        "timestamp": "2026-09-13T14:10:00+00:00",
                        "model_name": "Gemini 3.8 Flash (High)",
                        "prompt_tokens_uncached": 9420,
                        "cached_tokens": 112100,
                        "total_input_tokens": 121520,
                        "candidate_tokens": 820,
                        "thinking_tokens": 1850,
                        "output_tokens_total": 2670,
                        "cache_hit_ratio_pct": 92.25,
                        "avoided_cost_gbp": 0.18,
                        "avoided_cost_usd": 0.23,
                        "response_id": "resp-7a8f9c2d1e",
                        "is_overage": False,
                    },
                    {
                        "step_idx": 2,
                        "timestamp": "2026-09-13T14:15:30+00:00",
                        "model_name": "Gemini 3.8 Flash (High)",
                        "prompt_tokens_uncached": 6120,
                        "cached_tokens": 124200,
                        "total_input_tokens": 130320,
                        "candidate_tokens": 940,
                        "thinking_tokens": 2400,
                        "output_tokens_total": 3340,
                        "cache_hit_ratio_pct": 95.30,
                        "avoided_cost_gbp": 0.19,
                        "avoided_cost_usd": 0.24,
                        "response_id": "resp-3b4c5d6e7f",
                        "is_overage": False,
                    },
                    {
                        "step_idx": 3,
                        "timestamp": "2026-09-13T14:22:10+00:00",
                        "model_name": "Gemini 3.1 Pro (High)",
                        "prompt_tokens_uncached": 7800,
                        "cached_tokens": 128400,
                        "total_input_tokens": 136200,
                        "candidate_tokens": 1450,
                        "thinking_tokens": 4800,
                        "output_tokens_total": 6250,
                        "cache_hit_ratio_pct": 94.27,
                        "avoided_cost_gbp": 0.28,
                        "avoided_cost_usd": 0.35,
                        "response_id": "resp-9e8d7c6b5a",
                        "is_overage": False,
                    },
                    {
                        "step_idx": 4,
                        "timestamp": "2026-09-13T14:28:45+00:00",
                        "model_name": "Gemini 3.8 Flash (High)",
                        "prompt_tokens_uncached": 3260,
                        "cached_tokens": 121500,
                        "total_input_tokens": 124760,
                        "candidate_tokens": 610,
                        "thinking_tokens": 980,
                        "output_tokens_total": 1590,
                        "cache_hit_ratio_pct": 97.39,
                        "avoided_cost_gbp": 0.14,
                        "avoided_cost_usd": 0.18,
                        "response_id": "resp-1f2e3d4c5b",
                        "is_overage": False,
                    },
                ],
            }
        ],
        "swarms": {
            "total_swarms": 12,
            "total_subagents": 28,
            "unique_projects": ["antigravity-telemetry-engine", "cloud-infra-orchestrator", "multi-agent-reasoning-framework"],
            "total_swarm_tokens": 64210900,
            "total_cached_tokens": 60486000,
            "global_cache_hit_pct": 94.2,
            "avg_tokens_per_turn": 34897,
            "swarms": [
                {
                    "swarm_id": "swarm-arch-01",
                    "root_id": "c-root-1",
                    "root_title": "Full-Stack Telemetry Refactoring & Swarm Pipeline",
                    "workspace_name": "antigravity-telemetry-engine",
                    "total_swarm_tokens": 28410000,
                    "total_input_tokens": 26800000,
                    "total_cached_tokens": 25245600,
                    "cache_hit_pct": 94.2,
                    "tokens_per_turn": 38917,
                    "subagents_count": 3,
                    "duration_seconds": 1125,
                    "duration_formatted": "18m 45s",
                    "avoided_cost_usd": 48.20,
                    "avoided_cost_gbp": 38.08,
                    "tier_breakdown": {
                        "mechanical": {"count": 1, "turns": 6, "tokens": 4200000, "cost_usd": 2.10},
                        "engineering": {"count": 1, "turns": 12, "tokens": 9800000, "cost_usd": 14.50},
                        "architecture": {"count": 1, "turns": 8, "tokens": 14410000, "cost_usd": 31.60},
                        "other": {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0},
                    },
                    "nodes": [
                        {
                            "id": "c-root-1",
                            "title": "Lead Architect Task",
                            "role": "Root Orchestrator",
                            "tier": "orchestrator",
                            "model_id": "1016",
                            "model_name": "Gemini 3.1 Pro (High)",
                            "turn_count": 14,
                            "tokens_total": 12500000,
                            "input_tokens": 11800000,
                            "cached_tokens": 11200000,
                            "cache_hit_pct": 94.9,
                            "output_tokens": 700000,
                            "thinking_tokens": 580000,
                            "answer_tokens": 120000,
                            "cost_usd": 28.40,
                            "cost_gbp": 22.44,
                            "created_at": "2026-09-13T14:00:00Z",
                            "is_root": True,
                        },
                        {
                            "id": "c-sub-1",
                            "parent_id": "c-root-1",
                            "title": "Protobuf Wire Parser Specialist",
                            "role": "Wire Parser Specialist",
                            "tier": "engineering",
                            "model_id": "1322",
                            "model_name": "Gemini Fast Agent Assistant",
                            "turn_count": 12,
                            "tokens_total": 9800000,
                            "input_tokens": 9200000,
                            "cached_tokens": 8700000,
                            "cache_hit_pct": 94.6,
                            "output_tokens": 600000,
                            "thinking_tokens": 450000,
                            "answer_tokens": 150000,
                            "cost_usd": 14.50,
                            "cost_gbp": 11.46,
                            "created_at": "2026-09-13T14:05:00Z",
                            "is_root": False,
                        },
                        {
                            "id": "c-sub-2",
                            "parent_id": "c-root-1",
                            "title": "Mechanical Regex & Log Auditor",
                            "role": "Log Auditor (Mechanical)",
                            "tier": "mechanical",
                            "model_id": "1050",
                            "model_name": "Gemini Flash Lite",
                            "turn_count": 6,
                            "tokens_total": 4200000,
                            "input_tokens": 3950000,
                            "cached_tokens": 3720000,
                            "cache_hit_pct": 94.2,
                            "output_tokens": 250000,
                            "thinking_tokens": 180000,
                            "answer_tokens": 70000,
                            "cost_usd": 2.10,
                            "cost_gbp": 1.66,
                            "created_at": "2026-09-13T14:08:00Z",
                            "is_root": False,
                        },
                        {
                            "id": "c-sub-3",
                            "parent_id": "c-root-1",
                            "title": "Schema Migration Verification",
                            "role": "Schema Architect",
                            "tier": "architecture",
                            "model_id": "1036",
                            "model_name": "Gemini 3.1 Pro (Low Reasoning)",
                            "turn_count": 8,
                            "tokens_total": 1910000,
                            "input_tokens": 1850000,
                            "cached_tokens": 1625600,
                            "cache_hit_pct": 87.9,
                            "output_tokens": 60000,
                            "thinking_tokens": 40000,
                            "answer_tokens": 20000,
                            "cost_usd": 3.20,
                            "cost_gbp": 2.53,
                            "created_at": "2026-09-13T14:12:00Z",
                            "is_root": False,
                        },
                    ],
                    "edges": [
                        {"source": "c-root-1", "target": "c-sub-1", "role": "Wire Parser Specialist", "tier": "engineering"},
                        {"source": "c-root-1", "target": "c-sub-2", "role": "Log Auditor (Mechanical)", "tier": "mechanical"},
                        {"source": "c-root-1", "target": "c-sub-3", "role": "Schema Architect", "tier": "architecture"},
                    ],
                }
            ],
        },
        "tool_analytics": {
            "total_executions": 10197,
            "total_errors": 42,
            "error_rate_pct": 0.41,
            "bypassed_executions": 128,
            "bypass_ratio_pct": 1.25,
            "unique_tools_count": 23,
            "top_tools": [
                {"tool_name": "run_command", "count": 4820, "error_count": 12, "bypass_count": 98, "pct_of_total": 47.3},
                {"tool_name": "view_file", "count": 2450, "error_count": 4, "bypass_count": 0, "pct_of_total": 24.0},
                {"tool_name": "replace_file_content", "count": 1340, "error_count": 18, "bypass_count": 0, "pct_of_total": 13.1},
                {"tool_name": "grep_search", "count": 980, "error_count": 2, "bypass_count": 0, "pct_of_total": 9.6},
                {"tool_name": "write_to_file", "count": 607, "error_count": 6, "bypass_count": 0, "pct_of_total": 6.0},
            ],
        },
        "exhaustion_intervals": [],
        "hourly_credit_activity": [],
    }


def capture_view(html_file: Path, output_path: Path, width: int = 1400, height: int = 860):
    """Invoke headless Chrome to render and capture a page view in crisp Light Mode."""
    if output_path.exists():
        output_path.unlink()
    profile_dir = tempfile.mkdtemp(prefix="chrome_shot_")
    cmd = [
        CHROME_BIN,
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        f"--user-data-dir={profile_dir}",
        f"--window-size={width},{height}",
        f"--screenshot={output_path}",
        f"file://{html_file}",
    ]
    print(f"[*] Capturing view -> {output_path.name}...")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    start = time.time()
    while time.time() - start < 10:
        if output_path.exists() and output_path.stat().st_size > 5000:
            time.sleep(0.4)
            break
        time.sleep(0.2)
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except Exception:
        proc.kill()
    shutil.rmtree(profile_dir, ignore_errors=True)
    if not output_path.exists() or output_path.stat().st_size <= 5000:
        raise RuntimeError(f"Failed to capture {output_path.name}")


def main():
    if not Path(CHROME_BIN).exists():
        print(f"[!] Error: Google Chrome binary not found at {CHROME_BIN}", file=sys.stderr)
        sys.exit(1)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    raw_html = INDEX_HTML.read_text(encoding="utf-8")

    # Force Light Mode attribute on root html tag
    raw_html = raw_html.replace("<html lang=\"en\">", "<html lang=\"en\" data-theme=\"light\">")

    # Inlined synthetic demo data script replacing external data.js
    demo_data = get_sanitized_showcase_data()
    inlined_script = f"""
    <script>
      window.__TELEMETRY_DATA__ = {json.dumps(demo_data)};
      try {{
        localStorage.setItem("antigravity_dashboard_theme", "light");
      }} catch(e) {{}}
      document.documentElement.setAttribute("data-theme", "light");
    </script>
    """
    html_with_inline_data = raw_html.replace('<script src="data.js"></script>', inlined_script)

    temp_files = []

    try:
        # 1. Hero Quotas View (Light Mode)
        hero_html = REPO_ROOT / "dashboard" / "_temp_hero.html"
        hero_html.write_text(html_with_inline_data, encoding="utf-8")
        temp_files.append(hero_html)
        hero_png = ASSETS_DIR / "showcase_hero_quotas.png"
        capture_view(hero_html, hero_png, width=1400, height=720)

        # 1b. GitHub Social Preview (1280 x 640 recommended canvas, Light Mode)
        social_png = ASSETS_DIR / "github_social_preview.png"
        capture_view(hero_html, social_png, width=1280, height=640)

        # 2. Subagent Swarm Lineage DAG Explorer View (Light Mode)
        swarms_snippet = """
        <style>
          header, footer, #dual-provider-quotas-section, .tab-nav, #view-now, #view-sessions, #view-projects, #view-billing, #view-plan { display: none !important; }
          #view-swarms { display: block !important; margin: 24px auto !important; }
        </style>
        <script>
          window.addEventListener("DOMContentLoaded", () => {
            document.documentElement.setAttribute("data-theme", "light");
            if (typeof renderSwarmsView === "function") {
              renderSwarmsView(globalDashboardData);
            }
          });
        </script>
        """
        swarms_html = REPO_ROOT / "dashboard" / "_temp_swarms.html"
        swarms_html.write_text(html_with_inline_data.replace("</body>", swarms_snippet + "\n</body>"), encoding="utf-8")
        temp_files.append(swarms_html)
        swarms_png = ASSETS_DIR / "showcase_swarm_lineage.png"
        capture_view(swarms_html, swarms_png, width=1400, height=760)

        # 3. Interactive What-If Workload Simulator View (Light Mode)
        sim_snippet = """
        <style>
          header, footer, #dual-provider-quotas-section, .tab-nav, #view-now, #view-sessions, #view-projects, #view-swarms, #view-billing { display: none !important; }
          #view-plan { display: block !important; margin: 24px auto !important; }
        </style>
        <script>
          window.addEventListener("DOMContentLoaded", () => {
            document.documentElement.setAttribute("data-theme", "light");
            if (typeof initSimulator === "function") {
              initSimulator();
            }
          });
        </script>
        """
        sim_html = REPO_ROOT / "dashboard" / "_temp_simulator.html"
        sim_html.write_text(html_with_inline_data.replace("</body>", sim_snippet + "\n</body>"), encoding="utf-8")
        temp_files.append(sim_html)
        sim_png = ASSETS_DIR / "showcase_simulator.png"
        capture_view(sim_html, sim_png, width=1400, height=760)

        # 4. Projects & Git Branches Portfolio View (Light Mode)
        projects_snippet = """
        <style>
          header, footer, #dual-provider-quotas-section, .tab-nav, #view-quotas, #view-credits, #view-swarms, #view-plan { display: none !important; }
          #view-projects { display: block !important; margin: 24px auto !important; }
        </style>
        <script>
          window.addEventListener("DOMContentLoaded", () => {
            document.documentElement.setAttribute("data-theme", "light");
            renderPortfolioView();
            toggleProjectBranches(0);
          });
        </script>
        """
        projects_html = REPO_ROOT / "dashboard" / "_temp_projects.html"
        projects_html.write_text(html_with_inline_data.replace("</body>", projects_snippet + "\n</body>"), encoding="utf-8")
        temp_files.append(projects_html)
        projects_png = ASSETS_DIR / "showcase_projects_branches.png"
        capture_view(projects_html, projects_png, width=1400, height=700)

        # 5. Turn-by-Turn Telemetry & Thinking Token Inspector View (Light Mode)
        turns_snippet = """
        <style>
          header, footer, #dual-provider-quotas-section, .tab-nav, #view-projects, #view-credits, #view-swarms, #view-plan { display: none !important; }
          #view-sessions { display: block !important; margin: 20px auto !important; }
          #view-sessions > *:not(#turns-card) { display: none !important; }
          #turns-card { display: block !important; margin: 20px auto !important; }
        </style>
        <script>
          Element.prototype.scrollIntoView = function() {};
          window.addEventListener("DOMContentLoaded", () => {
            document.documentElement.setAttribute("data-theme", "light");
            initDashboard();
            const convos = (globalDashboardData && globalDashboardData.conversations) || [];
            if (convos.length > 0) {
              const convo = convos[0];
              const convoSelect = document.getElementById("convo-filter");
              if (convoSelect) convoSelect.value = convo.convo_id;
              activeConvoForTurns = convo;
              renderTurnsTable(convo);
            }
          });
        </script>
        """
        turns_html = REPO_ROOT / "dashboard" / "_temp_turns.html"
        turns_html.write_text(html_with_inline_data.replace("</body>", turns_snippet + "\n</body>"), encoding="utf-8")
        temp_files.append(turns_html)
        turns_png = ASSETS_DIR / "showcase_turns_inspector.png"
        capture_view(turns_html, turns_png, width=1400, height=480)

        print("\n✓ Successfully captured all 6 showcase screenshots in Light Mode:")
        print(f"  1. {hero_png.name}")
        print(f"  2. {swarms_png.name}")
        print(f"  3. {sim_png.name}")
        print(f"  4. {projects_png.name}")
        print(f"  5. {turns_png.name}")
        print(f"  6. {social_png.name}")

    finally:
        for f in temp_files:
            if f.exists():
                f.unlink()


if __name__ == "__main__":
    main()
