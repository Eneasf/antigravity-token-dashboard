#!/usr/bin/env python3
"""
build_demo_showcase.py

Generates a rich, realistic, byte-deterministic synthetic telemetry payload for the
Antigravity Token Consumption & Quota Dashboard GitHub Pages showcase.

Focuses squarely on the system's core observational superpowers:
1. Authoritative Project & Git Branch Attribution (multi-workspace aggregation)
2. Turn-by-Turn Telemetry & Reasoning Inspector (thinking vs candidate tokens)
3. Subagent Swarms & Multi-Agent Lineage DAG (3-tier routing economics)
4. Runtime Tool Execution Analytics (sandbox bypass ratios, failure rates)
5. Dual-Track Quota Silos & 5-Hour Burst Recovery Staircase

Zero dependencies (Python 3.9+ stdlib only).
Zero PII (100% synthetic workspaces, synthetic UUIDs, and synthetic response IDs).
Byte-deterministic: identical output given identical parameters.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_canonical_models() -> Dict[str, Dict[str, Any]]:
    """Load models from antigravity_telemetry/models.json or fallback."""
    models_file = REPO_ROOT / "antigravity_telemetry" / "models.json"
    if models_file.exists():
        try:
            return json.loads(models_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "1318": {"name": "Gemini 3.8 Flash (High)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "high"},
        "1319": {"name": "Gemini 3.8 Flash (Medium)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "medium"},
        "1320": {"name": "Gemini 3.8 Flash (Low)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "low"},
        "1298": {"name": "Gemini 3.7 Flash (High)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "high"},
        "1016": {"name": "Gemini 3.1 Pro (High)", "family": "gemini-pro", "provider": "google", "reasoning_effort": "high"},
        "1036": {"name": "Gemini 3.1 Pro (Low)", "family": "gemini-pro", "provider": "google", "reasoning_effort": "low"},
        "1322": {"name": "Gemini Fast Agent Assistant", "family": "gemini-flash", "provider": "google", "reasoning_effort": "low"},
        "1050": {"name": "Gemini Flash Lite (Subagent)", "family": "gemini-flash", "provider": "google", "reasoning_effort": "low"},
        "1035": {"name": "Claude Sonnet 4.6 (Thinking)", "family": "claude-sonnet", "provider": "anthropic", "reasoning_effort": "high"},
        "1026": {"name": "Claude Opus 4.6 (Thinking)", "family": "claude-opus", "provider": "anthropic", "reasoning_effort": "high"},
        "342": {"name": "GPT-OSS 120B (Medium)", "family": "gpt-oss", "provider": "openai", "reasoning_effort": "medium"},
    }


def generate_synthetic_payload() -> Dict[str, Any]:
    """Build a comprehensive, realistic, and sanitized showcase telemetry payload."""
    models_roster = get_canonical_models()
    base_ref_time = datetime.datetime(2026, 9, 14, 12, 0, 0, tzinfo=datetime.timezone.utc)

    # 1. Projects & Workspaces
    projects_data = [
        {
            "workspace_root": "/workspace/agentic-code-reviewer",
            "project_name": "agentic-code-reviewer",
            "total_turns": 95,
            "total_input_tokens": 19400000,
            "cached_tokens": 17950000,
            "cache_hit_ratio_pct": 92.5,
            "total_output_tokens": 1280000,
            "thinking_tokens": 820000,
            "estimated_cost_gbp": 61.30,
            "estimated_cost_usd": 77.60,
            "branches": [
                {
                    "branch": "main",
                    "turn_count": 45,
                    "total_input_tokens": 9200000,
                    "cached_tokens": 8590000,
                    "cache_hit_ratio_pct": 93.4,
                    "estimated_cost_gbp": 28.40,
                    "estimated_cost_usd": 35.95,
                },
                {
                    "branch": "feat/ast-parser",
                    "turn_count": 32,
                    "total_input_tokens": 6800000,
                    "cached_tokens": 6200000,
                    "cache_hit_ratio_pct": 91.2,
                    "estimated_cost_gbp": 21.10,
                    "estimated_cost_usd": 26.70,
                },
                {
                    "branch": "feat/multi-model-eval",
                    "turn_count": 18,
                    "total_input_tokens": 3400000,
                    "cached_tokens": 3160000,
                    "cache_hit_ratio_pct": 92.9,
                    "estimated_cost_gbp": 11.80,
                    "estimated_cost_usd": 14.95,
                },
            ],
        },
        {
            "workspace_root": "/workspace/distributed-kv-cache",
            "project_name": "distributed-kv-cache",
            "total_turns": 50,
            "total_input_tokens": 10000000,
            "cached_tokens": 9070000,
            "cache_hit_ratio_pct": 90.7,
            "total_output_tokens": 690000,
            "thinking_tokens": 420000,
            "estimated_cost_gbp": 31.70,
            "estimated_cost_usd": 40.10,
            "branches": [
                {
                    "branch": "main",
                    "turn_count": 28,
                    "total_input_tokens": 5900000,
                    "cached_tokens": 5430000,
                    "cache_hit_ratio_pct": 92.0,
                    "estimated_cost_gbp": 18.50,
                    "estimated_cost_usd": 23.40,
                },
                {
                    "branch": "fix/eviction-race-condition",
                    "turn_count": 22,
                    "total_input_tokens": 4100000,
                    "cached_tokens": 3640000,
                    "cache_hit_ratio_pct": 88.8,
                    "estimated_cost_gbp": 13.20,
                    "estimated_cost_usd": 16.70,
                },
            ],
        },
        {
            "workspace_root": "/workspace/realtime-telemetry-api",
            "project_name": "realtime-telemetry-api",
            "total_turns": 53,
            "total_input_tokens": 10900000,
            "cached_tokens": 10110000,
            "cache_hit_ratio_pct": 92.8,
            "total_output_tokens": 740000,
            "thinking_tokens": 380000,
            "estimated_cost_gbp": 34.70,
            "estimated_cost_usd": 43.90,
            "branches": [
                {
                    "branch": "main",
                    "turn_count": 34,
                    "total_input_tokens": 7100000,
                    "cached_tokens": 6690000,
                    "cache_hit_ratio_pct": 94.2,
                    "estimated_cost_gbp": 22.60,
                    "estimated_cost_usd": 28.60,
                },
                {
                    "branch": "feat/connect-rpc-gateway",
                    "turn_count": 19,
                    "total_input_tokens": 3800000,
                    "cached_tokens": 3420000,
                    "cache_hit_ratio_pct": 90.0,
                    "estimated_cost_gbp": 12.10,
                    "estimated_cost_usd": 15.30,
                },
            ],
        },
        {
            "workspace_root": "/workspace/cloud-infrastructure-bot",
            "project_name": "cloud-infrastructure-bot",
            "total_turns": 36,
            "total_input_tokens": 7800000,
            "cached_tokens": 7230000,
            "cache_hit_ratio_pct": 92.7,
            "total_output_tokens": 540000,
            "thinking_tokens": 210000,
            "estimated_cost_gbp": 25.00,
            "estimated_cost_usd": 31.60,
            "branches": [
                {
                    "branch": "feat/terraform-drift-detector",
                    "turn_count": 22,
                    "total_input_tokens": 4950000,
                    "cached_tokens": 4620000,
                    "cache_hit_ratio_pct": 93.3,
                    "estimated_cost_gbp": 15.80,
                    "estimated_cost_usd": 20.00,
                },
                {
                    "branch": "main",
                    "turn_count": 14,
                    "total_input_tokens": 2850000,
                    "cached_tokens": 2610000,
                    "cache_hit_ratio_pct": 91.6,
                    "estimated_cost_gbp": 9.20,
                    "estimated_cost_usd": 11.60,
                },
            ],
        },
    ]

    # 2. Conversations & Turn Inspector Sequences
    conversations = []
    convo_templates = [
        ("00000000-0000-0000-0001-000000000001", "Architecture & Wire Protocol Decoding", "agentic-code-reviewer", "main", "1036", 12),
        ("00000000-0000-0000-0001-000000000002", "AST Graph Extraction & Lint Validation", "agentic-code-reviewer", "feat/ast-parser", "1322", 10),
        ("00000000-0000-0000-0001-000000000003", "Cross-Model Benchmark Evaluation", "agentic-code-reviewer", "feat/multi-model-eval", "1035", 8),
        ("00000000-0000-0000-0001-000000000004", "LRU Cache Interval Pruning & Concurrency", "distributed-kv-cache", "main", "1016", 14),
        ("00000000-0000-0000-0001-000000000005", "Eviction Deadlock Bug RCA & Fix", "distributed-kv-cache", "fix/eviction-race-condition", "1318", 9),
        ("00000000-0000-0000-0001-000000000006", "Connect-RPC Ingestion Endpoint Handlers", "realtime-telemetry-api", "feat/connect-rpc-gateway", "1026", 7),
        ("00000000-0000-0000-0001-000000000007", "Zero-Dependency SQLite Mode=ro Connector", "realtime-telemetry-api", "main", "1318", 15),
        ("00000000-0000-0000-0001-000000000008", "Terraform Drift Detection Plan Validator", "cloud-infrastructure-bot", "main", "342", 11),
        ("00000000-0000-0000-0001-000000000009", "Zero-Copy Deserializer Microbenchmarks", "distributed-kv-cache", "perf/zero-copy", "1318", 16),
        ("00000000-0000-0000-0001-000000000010", "Automated Policy As Code Drift Remediation", "cloud-infrastructure-bot", "feat/terraform-drift-detector", "1035", 14),
    ]

    all_turns = []
    session_offset_minutes = 0

    for cid, title, proj, branch, default_model, turn_count in convo_templates:
        convo_turns = []
        cur_cached = 25000
        first_ts = None
        last_ts = None

        for step in range(1, turn_count + 1):
            session_offset_minutes += 7
            t_delta = datetime.timedelta(minutes=session_offset_minutes)
            turn_time = base_ref_time - t_delta
            turn_iso = turn_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            if not last_ts:
                last_ts = turn_iso
            first_ts = turn_iso

            # Model allocation logic
            mid = default_model
            if step % 4 == 0:
                mid = "1050"  # mechanical subagent
            elif step % 3 == 0:
                mid = "1322"  # standard engineering

            m_info = models_roster.get(mid, {"name": f"Model {mid}", "family": "gemini-flash"})
            m_name = m_info.get("name", mid)

            # Realistic progressive prompt caching
            uncached = 3200 + (step * 250)
            cached = cur_cached + (step * 4500)
            total_in = uncached + cached
            cur_cached = cached

            # Reasoning tokens calculation
            is_thinking = "thinking" in m_name.lower() or mid in ("1016", "1035", "1026", "1318")
            thinking = 2400 + (step * 180) if is_thinking else 0
            answer = 950 + (step * 90)
            total_out = thinking + answer
            cache_pct = round((cached / total_in) * 100.0, 2)

            resp_id = f"resp_demo_{cid[:8]}_s{step:02d}"
            turn_obj = {
                "convo_id": cid,
                "step_idx": step,
                "timestamp": turn_iso,
                "model_id": mid,
                "model_name": m_name,
                "prompt_tokens_uncached": uncached,
                "cached_tokens": cached,
                "total_input_tokens": total_in,
                "thinking_tokens": thinking,
                "answer_tokens": answer,
                "output_tokens_total": total_out,
                "cache_hit_ratio_pct": cache_pct,
                "response_id": resp_id,
                "is_overage": False,
                "credit_burn": 0,
                "avoided_cost_usd": round((uncached * 0.00000075) + (cached * 0.000000075) + (total_out * 0.00000375), 4),
                "avoided_cost_gbp": round(((uncached * 0.00000075) + (cached * 0.000000075) + (total_out * 0.00000375)) * 0.79, 4),
            }
            convo_turns.append(turn_obj)
            all_turns.append(turn_obj)

        total_convo_in = sum(t["total_input_tokens"] for t in convo_turns)
        total_convo_cached = sum(t["cached_tokens"] for t in convo_turns)
        total_convo_out = sum(t["output_tokens_total"] for t in convo_turns)
        convo_cache_pct = round((total_convo_cached / total_convo_in) * 100.0, 2) if total_convo_in else 0.0

        convo_summary = {
            "convo_id": cid,
            "title": title,
            "project_name": proj,
            "workspace_path": f"/workspace/{proj}",
            "git_branch": branch,
            "first_turn_ts": first_ts,
            "last_turn_ts": last_ts,
            "turn_count": turn_count,
            "total_input_tokens": total_convo_in,
            "total_cached_tokens": total_convo_cached,
            "cache_hit_ratio_pct": convo_cache_pct,
            "total_output_tokens": total_convo_out,
            "total_processed_tokens": total_convo_in + total_convo_out,
            "turns": convo_turns,
        }
        conversations.append(convo_summary)

    # Sort conversations newest first
    conversations.sort(key=lambda c: c["last_turn_ts"], reverse=True)

    # 3. Subagent Swarms & Multi-Agent Lineage DAG
    swarms_list = [
        # --- SWARM 1: agentic-code-reviewer ---
        {
            "swarm_id": "00000001-0000-0000-0002-000000000001",
            "root_convo_id": "00000000-0000-0000-0001-000000000001",
            "root_title": "Architecture & AST Wire Protocol Lead",
            "workspace_name": "agentic-code-reviewer",
            "workspace_path": "/workspace/agentic-code-reviewer",
            "git_branch": "feat/ast-tree-sitter",
            "created_at": "2026-09-14T11:35:00Z",
            "last_activity": "2026-09-14T11:51:45Z",
            "duration_seconds": 1005.0,
            "duration_formatted": "16m 45s",
            "total_turns": 48,
            "total_swarm_tokens": 7840000,
            "total_input_tokens": 7320000,
            "total_cached_tokens": 6855000,
            "cache_hit_pct": 93.6,
            "total_output_tokens": 520000,
            "total_thinking_tokens": 102000,
            "total_answer_tokens": 418000,
            "tokens_per_turn": 163333,
            "burn_rate_tokens_per_min": 468060,
            "avoided_cost_usd": 38.50,
            "avoided_cost_gbp": 30.40,
            "actual_overage_credits": 0,
            "actual_overage_gbp": 0.0,
            "actual_overage_usd": 0.0,
            "is_overage": False,
            "subagents_count": 3,
            "subagent_share_pct": 56.4,
            "tier_breakdown": {
                "mechanical": {"count": 1, "turns": 8, "tokens": 750000, "cost_usd": 1.40, "cost_gbp": 1.10, "label": "Tier 1: Mechanical (Flash Lite)"},
                "engineering": {"count": 1, "turns": 14, "tokens": 2150000, "cost_usd": 8.40, "cost_gbp": 6.60, "label": "Tier 2: Engineering (Fast Agent)"},
                "architecture": {"count": 2, "turns": 26, "tokens": 4940000, "cost_usd": 28.70, "cost_gbp": 22.70, "label": "Tier 3: Architecture (Pro Low)"},
                "other": {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "cost_gbp": 0.0, "label": "Other / Custom Model"},
            },
            "nodes": [
                {
                    "id": "node_ast_root",
                    "parent_id": None,
                    "is_root": True,
                    "title": "Architecture & AST Lead",
                    "role": "Architecture & AST Lead",
                    "tier": "architecture",
                    "model_id": "1026",
                    "model_name": "Claude Opus 4.6 (Thinking)",
                    "turn_count": 16,
                    "tokens_total": 3420000,
                    "input_tokens": 3180000,
                    "cached_tokens": 2980000,
                    "cache_hit_pct": 93.7,
                    "output_tokens": 240000,
                    "thinking_tokens": 52000,
                    "answer_tokens": 188000,
                    "cost_usd": 21.50,
                    "cost_gbp": 17.00,
                    "created_at": "2026-09-14T11:35:00Z",
                },
                {
                    "id": "node_ast_parser",
                    "parent_id": "node_ast_root",
                    "is_root": False,
                    "title": "Tree-Sitter Grammar Parser",
                    "role": "Tree-Sitter Parser",
                    "tier": "engineering",
                    "model_id": "1318",
                    "model_name": "Gemini 3.8 Flash (High)",
                    "turn_count": 14,
                    "tokens_total": 2150000,
                    "input_tokens": 2010000,
                    "cached_tokens": 1880000,
                    "cache_hit_pct": 93.5,
                    "output_tokens": 140000,
                    "thinking_tokens": 22000,
                    "answer_tokens": 118000,
                    "cost_usd": 8.40,
                    "cost_gbp": 6.60,
                    "created_at": "2026-09-14T11:38:20Z",
                },
                {
                    "id": "node_ast_validator",
                    "parent_id": "node_ast_root",
                    "is_root": False,
                    "title": "AST Diff & Patch Validator",
                    "role": "AST Patch Validator",
                    "tier": "architecture",
                    "model_id": "1036",
                    "model_name": "Gemini 3.1 Pro (Low)",
                    "turn_count": 10,
                    "tokens_total": 1520000,
                    "input_tokens": 1420000,
                    "cached_tokens": 1310000,
                    "cache_hit_pct": 92.3,
                    "output_tokens": 100000,
                    "thinking_tokens": 28000,
                    "answer_tokens": 72000,
                    "cost_usd": 7.20,
                    "cost_gbp": 5.70,
                    "created_at": "2026-09-14T11:42:15Z",
                },
                {
                    "id": "node_ast_linter",
                    "parent_id": "node_ast_root",
                    "is_root": False,
                    "title": "Unit Test Runner & Linter",
                    "role": "Test & Linter Runner",
                    "tier": "mechanical",
                    "model_id": "1050",
                    "model_name": "Gemini Flash Lite (Subagent)",
                    "turn_count": 8,
                    "tokens_total": 750000,
                    "input_tokens": 710000,
                    "cached_tokens": 685000,
                    "cache_hit_pct": 96.5,
                    "output_tokens": 40000,
                    "thinking_tokens": 0,
                    "answer_tokens": 40000,
                    "cost_usd": 1.40,
                    "cost_gbp": 1.10,
                    "created_at": "2026-09-14T11:47:00Z",
                },
            ],
            "edges": [
                {"source": "node_ast_root", "target": "node_ast_parser"},
                {"source": "node_ast_root", "target": "node_ast_validator"},
                {"source": "node_ast_root", "target": "node_ast_linter"},
            ],
            "root_agent": {"agent_id": "node_ast_root", "role": "Architecture Lead", "tier": "complex_architecture"},
            "subagents": [
                {"agent_id": "node_ast_parser", "parent_id": "node_ast_root", "role": "Tree-Sitter Parser", "tier": "standard_engineering"},
                {"agent_id": "node_ast_validator", "parent_id": "node_ast_root", "role": "AST Validator", "tier": "complex_architecture"},
                {"agent_id": "node_ast_linter", "parent_id": "node_ast_root", "role": "Linter Runner", "tier": "mechanical_execution"},
            ],
        },
        # --- SWARM 2: distributed-kv-cache ---
        {
            "swarm_id": "00000002-0000-0000-0002-000000000002",
            "root_convo_id": "00000000-0000-0000-0001-000000000004",
            "root_title": "Zero-Copy KV Concurrency Engine",
            "workspace_name": "distributed-kv-cache",
            "workspace_path": "/workspace/distributed-kv-cache",
            "git_branch": "perf/zero-copy",
            "created_at": "2026-09-14T10:10:00Z",
            "last_activity": "2026-09-14T10:31:10Z",
            "duration_seconds": 1270.0,
            "duration_formatted": "21m 10s",
            "total_turns": 54,
            "total_swarm_tokens": 8350000,
            "total_input_tokens": 7820000,
            "total_cached_tokens": 7365000,
            "cache_hit_pct": 94.2,
            "total_output_tokens": 530000,
            "total_thinking_tokens": 78000,
            "total_answer_tokens": 452000,
            "tokens_per_turn": 154630,
            "burn_rate_tokens_per_min": 394488,
            "avoided_cost_usd": 32.50,
            "avoided_cost_gbp": 25.70,
            "actual_overage_credits": 0,
            "actual_overage_gbp": 0.0,
            "actual_overage_usd": 0.0,
            "is_overage": False,
            "subagents_count": 4,
            "subagent_share_pct": 64.7,
            "tier_breakdown": {
                "mechanical": {"count": 2, "turns": 14, "tokens": 1100000, "cost_usd": 2.00, "cost_gbp": 1.60, "label": "Tier 1: Mechanical (Flash Lite)"},
                "engineering": {"count": 2, "turns": 25, "tokens": 4300000, "cost_usd": 14.30, "cost_gbp": 11.30, "label": "Tier 2: Engineering (Fast Agent)"},
                "architecture": {"count": 1, "turns": 15, "tokens": 2950000, "cost_usd": 16.20, "cost_gbp": 12.80, "label": "Tier 3: Architecture (Pro Low)"},
                "other": {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "cost_gbp": 0.0, "label": "Other / Custom Model"},
            },
            "nodes": [
                {
                    "id": "node_kv_root",
                    "parent_id": None,
                    "is_root": True,
                    "title": "Distributed Memory Architect",
                    "role": "Memory Architect",
                    "tier": "architecture",
                    "model_id": "1035",
                    "model_name": "Claude Sonnet 4.6 (Thinking)",
                    "turn_count": 15,
                    "tokens_total": 2950000,
                    "input_tokens": 2750000,
                    "cached_tokens": 2580000,
                    "cache_hit_pct": 93.8,
                    "output_tokens": 200000,
                    "thinking_tokens": 44000,
                    "answer_tokens": 156000,
                    "cost_usd": 16.20,
                    "cost_gbp": 12.80,
                    "created_at": "2026-09-14T10:10:00Z",
                },
                {
                    "id": "node_kv_ring",
                    "parent_id": "node_kv_root",
                    "is_root": False,
                    "title": "Lockless Ring Buffer Specialist",
                    "role": "Ring Buffer Engineer",
                    "tier": "engineering",
                    "model_id": "1322",
                    "model_name": "Gemini Fast Agent Assistant",
                    "turn_count": 14,
                    "tokens_total": 2420000,
                    "input_tokens": 2260000,
                    "cached_tokens": 2120000,
                    "cache_hit_pct": 93.8,
                    "output_tokens": 160000,
                    "thinking_tokens": 18000,
                    "answer_tokens": 142000,
                    "cost_usd": 8.20,
                    "cost_gbp": 6.50,
                    "created_at": "2026-09-14T10:14:20Z",
                },
                {
                    "id": "node_kv_deser",
                    "parent_id": "node_kv_root",
                    "is_root": False,
                    "title": "Zero-Copy Deserializer",
                    "role": "Zero-Copy Deserializer",
                    "tier": "engineering",
                    "model_id": "1318",
                    "model_name": "Gemini 3.8 Flash (High)",
                    "turn_count": 11,
                    "tokens_total": 1880000,
                    "input_tokens": 1760000,
                    "cached_tokens": 1650000,
                    "cache_hit_pct": 93.8,
                    "output_tokens": 120000,
                    "thinking_tokens": 16000,
                    "answer_tokens": 104000,
                    "cost_usd": 6.10,
                    "cost_gbp": 4.80,
                    "created_at": "2026-09-14T10:18:40Z",
                },
                {
                    "id": "node_kv_race",
                    "parent_id": "node_kv_root",
                    "is_root": False,
                    "title": "Race Condition Detector",
                    "role": "Race Condition Audit",
                    "tier": "mechanical",
                    "model_id": "1050",
                    "model_name": "Gemini Flash Lite (Subagent)",
                    "turn_count": 8,
                    "tokens_total": 620000,
                    "input_tokens": 590000,
                    "cached_tokens": 570000,
                    "cache_hit_pct": 96.6,
                    "output_tokens": 30000,
                    "thinking_tokens": 0,
                    "answer_tokens": 30000,
                    "cost_usd": 1.10,
                    "cost_gbp": 0.90,
                    "created_at": "2026-09-14T10:22:15Z",
                },
                {
                    "id": "node_kv_bench",
                    "parent_id": "node_kv_root",
                    "is_root": False,
                    "title": "Microbenchmark Harness",
                    "role": "Microbenchmark Lead",
                    "tier": "mechanical",
                    "model_id": "1050",
                    "model_name": "Gemini Flash Lite (Subagent)",
                    "turn_count": 6,
                    "tokens_total": 480000,
                    "input_tokens": 460000,
                    "cached_tokens": 445000,
                    "cache_hit_pct": 96.7,
                    "output_tokens": 20000,
                    "thinking_tokens": 0,
                    "answer_tokens": 20000,
                    "cost_usd": 0.90,
                    "cost_gbp": 0.70,
                    "created_at": "2026-09-14T10:26:00Z",
                },
            ],
            "edges": [
                {"source": "node_kv_root", "target": "node_kv_ring"},
                {"source": "node_kv_root", "target": "node_kv_deser"},
                {"source": "node_kv_root", "target": "node_kv_race"},
                {"source": "node_kv_root", "target": "node_kv_bench"},
            ],
            "root_agent": {"agent_id": "node_kv_root", "role": "Memory Architect", "tier": "complex_architecture"},
            "subagents": [
                {"agent_id": "node_kv_ring", "parent_id": "node_kv_root", "role": "Ring Buffer Specialist", "tier": "standard_engineering"},
                {"agent_id": "node_kv_deser", "parent_id": "node_kv_root", "role": "Zero-Copy Deserializer", "tier": "standard_engineering"},
                {"agent_id": "node_kv_race", "parent_id": "node_kv_root", "role": "Race Detector", "tier": "mechanical_execution"},
                {"agent_id": "node_kv_bench", "parent_id": "node_kv_root", "role": "Benchmark Runner", "tier": "mechanical_execution"},
            ],
        },
        # --- SWARM 3: realtime-telemetry-api ---
        {
            "swarm_id": "00000003-0000-0000-0002-000000000003",
            "root_convo_id": "00000000-0000-0000-0001-000000000006",
            "root_title": "Connect-RPC Protocol & Security Audit",
            "workspace_name": "realtime-telemetry-api",
            "workspace_path": "/workspace/realtime-telemetry-api",
            "git_branch": "feat/connect-rpc-gateway",
            "created_at": "2026-09-14T09:00:00Z",
            "last_activity": "2026-09-14T09:14:30Z",
            "duration_seconds": 870.0,
            "duration_formatted": "14m 30s",
            "total_turns": 31,
            "total_swarm_tokens": 4770000,
            "total_input_tokens": 4450000,
            "total_cached_tokens": 4140000,
            "cache_hit_pct": 93.0,
            "total_output_tokens": 320000,
            "total_thinking_tokens": 53000,
            "total_answer_tokens": 267000,
            "tokens_per_turn": 153871,
            "burn_rate_tokens_per_min": 328965,
            "avoided_cost_usd": 21.70,
            "avoided_cost_gbp": 17.20,
            "actual_overage_credits": 0,
            "actual_overage_gbp": 0.0,
            "actual_overage_usd": 0.0,
            "is_overage": False,
            "subagents_count": 2,
            "subagent_share_pct": 50.7,
            "tier_breakdown": {
                "mechanical": {"count": 1, "turns": 9, "tokens": 780000, "cost_usd": 1.50, "cost_gbp": 1.20, "label": "Tier 1: Mechanical (Flash Lite)"},
                "engineering": {"count": 1, "turns": 10, "tokens": 1640000, "cost_usd": 5.40, "cost_gbp": 4.30, "label": "Tier 2: Engineering (Fast Agent)"},
                "architecture": {"count": 1, "turns": 12, "tokens": 2350000, "cost_usd": 14.80, "cost_gbp": 11.70, "label": "Tier 3: Architecture (Pro Low)"},
                "other": {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "cost_gbp": 0.0, "label": "Other / Custom Model"},
            },
            "nodes": [
                {
                    "id": "node_rpc_root",
                    "parent_id": None,
                    "is_root": True,
                    "title": "Security & Protocol Auditor",
                    "role": "Protocol Auditor",
                    "tier": "architecture",
                    "model_id": "1026",
                    "model_name": "Claude Opus 4.6 (Thinking)",
                    "turn_count": 12,
                    "tokens_total": 2350000,
                    "input_tokens": 2180000,
                    "cached_tokens": 2010000,
                    "cache_hit_pct": 92.2,
                    "output_tokens": 170000,
                    "thinking_tokens": 38000,
                    "answer_tokens": 132000,
                    "cost_usd": 14.80,
                    "cost_gbp": 11.70,
                    "created_at": "2026-09-14T09:00:00Z",
                },
                {
                    "id": "node_rpc_schema",
                    "parent_id": "node_rpc_root",
                    "is_root": False,
                    "title": "Protobuf Schema Validator",
                    "role": "Schema Validator",
                    "tier": "engineering",
                    "model_id": "1318",
                    "model_name": "Gemini 3.8 Flash (High)",
                    "turn_count": 10,
                    "tokens_total": 1640000,
                    "input_tokens": 1530000,
                    "cached_tokens": 1420000,
                    "cache_hit_pct": 92.8,
                    "output_tokens": 110000,
                    "thinking_tokens": 15000,
                    "answer_tokens": 95000,
                    "cost_usd": 5.40,
                    "cost_gbp": 4.30,
                    "created_at": "2026-09-14T09:04:15Z",
                },
                {
                    "id": "node_rpc_fuzz",
                    "parent_id": "node_rpc_root",
                    "is_root": False,
                    "title": "Fuzzing & Malformed Payload Scanner",
                    "role": "Fuzzing Scanner",
                    "tier": "mechanical",
                    "model_id": "1050",
                    "model_name": "Gemini Flash Lite (Subagent)",
                    "turn_count": 9,
                    "tokens_total": 780000,
                    "input_tokens": 740000,
                    "cached_tokens": 710000,
                    "cache_hit_pct": 95.9,
                    "output_tokens": 40000,
                    "thinking_tokens": 0,
                    "answer_tokens": 40000,
                    "cost_usd": 1.50,
                    "cost_gbp": 1.20,
                    "created_at": "2026-09-14T09:08:45Z",
                },
            ],
            "edges": [
                {"source": "node_rpc_root", "target": "node_rpc_schema"},
                {"source": "node_rpc_root", "target": "node_rpc_fuzz"},
            ],
            "root_agent": {"agent_id": "node_rpc_root", "role": "Protocol Auditor", "tier": "complex_architecture"},
            "subagents": [
                {"agent_id": "node_rpc_schema", "parent_id": "node_rpc_root", "role": "Schema Validator", "tier": "standard_engineering"},
                {"agent_id": "node_rpc_fuzz", "parent_id": "node_rpc_root", "role": "Fuzzing Scanner", "tier": "mechanical_execution"},
            ],
        },
        # --- SWARM 4: cloud-infrastructure-bot ---
        {
            "swarm_id": "00000004-0000-0000-0002-000000000004",
            "root_convo_id": "00000000-0000-0000-0001-000000000008",
            "root_title": "Terraform State Drift Reconciler & CI/CD",
            "workspace_name": "cloud-infrastructure-bot",
            "workspace_path": "/workspace/cloud-infrastructure-bot",
            "git_branch": "feat/terraform-drift-detector",
            "created_at": "2026-09-14T08:15:00Z",
            "last_activity": "2026-09-14T08:30:20Z",
            "duration_seconds": 920.0,
            "duration_formatted": "15m 20s",
            "total_turns": 33,
            "total_swarm_tokens": 5140000,
            "total_input_tokens": 4810000,
            "total_cached_tokens": 4510000,
            "cache_hit_pct": 93.8,
            "total_output_tokens": 330000,
            "total_thinking_tokens": 52000,
            "total_answer_tokens": 278000,
            "tokens_per_turn": 155758,
            "burn_rate_tokens_per_min": 335217,
            "avoided_cost_usd": 22.90,
            "avoided_cost_gbp": 18.00,
            "actual_overage_credits": 0,
            "actual_overage_gbp": 0.0,
            "actual_overage_usd": 0.0,
            "is_overage": False,
            "subagents_count": 2,
            "subagent_share_pct": 48.6,
            "tier_breakdown": {
                "mechanical": {"count": 1, "turns": 8, "tokens": 680000, "cost_usd": 1.20, "cost_gbp": 0.90, "label": "Tier 1: Mechanical (Flash Lite)"},
                "engineering": {"count": 1, "turns": 11, "tokens": 1820000, "cost_usd": 6.20, "cost_gbp": 4.90, "label": "Tier 2: Engineering (Fast Agent)"},
                "architecture": {"count": 1, "turns": 14, "tokens": 2640000, "cost_usd": 15.50, "cost_gbp": 12.20, "label": "Tier 3: Architecture (Pro Low)"},
                "other": {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "cost_gbp": 0.0, "label": "Other / Custom Model"},
            },
            "nodes": [
                {
                    "id": "node_tf_root",
                    "parent_id": None,
                    "is_root": True,
                    "title": "Cloud Infrastructure Architect",
                    "role": "Infra Architect",
                    "tier": "architecture",
                    "model_id": "1035",
                    "model_name": "Claude Sonnet 4.6 (Thinking)",
                    "turn_count": 14,
                    "tokens_total": 2640000,
                    "input_tokens": 2460000,
                    "cached_tokens": 2290000,
                    "cache_hit_pct": 93.1,
                    "output_tokens": 180000,
                    "thinking_tokens": 36000,
                    "answer_tokens": 144000,
                    "cost_usd": 15.50,
                    "cost_gbp": 12.20,
                    "created_at": "2026-09-14T08:15:00Z",
                },
                {
                    "id": "node_tf_hcl",
                    "parent_id": "node_tf_root",
                    "is_root": False,
                    "title": "HCL AST & Policy Evaluator",
                    "role": "HCL AST Evaluator",
                    "tier": "engineering",
                    "model_id": "1318",
                    "model_name": "Gemini 3.8 Flash (High)",
                    "turn_count": 11,
                    "tokens_total": 1820000,
                    "input_tokens": 1700000,
                    "cached_tokens": 1590000,
                    "cache_hit_pct": 93.5,
                    "output_tokens": 120000,
                    "thinking_tokens": 16000,
                    "answer_tokens": 104000,
                    "cost_usd": 6.20,
                    "cost_gbp": 4.90,
                    "created_at": "2026-09-14T08:19:30Z",
                },
                {
                    "id": "node_tf_state",
                    "parent_id": "node_tf_root",
                    "is_root": False,
                    "title": "State Lock & Dry-Run Tester",
                    "role": "State Lock Tester",
                    "tier": "mechanical",
                    "model_id": "1050",
                    "model_name": "Gemini Flash Lite (Subagent)",
                    "turn_count": 8,
                    "tokens_total": 680000,
                    "input_tokens": 650000,
                    "cached_tokens": 630000,
                    "cache_hit_pct": 96.9,
                    "output_tokens": 30000,
                    "thinking_tokens": 0,
                    "answer_tokens": 30000,
                    "cost_usd": 1.20,
                    "cost_gbp": 0.90,
                    "created_at": "2026-09-14T08:24:00Z",
                },
            ],
            "edges": [
                {"source": "node_tf_root", "target": "node_tf_hcl"},
                {"source": "node_tf_root", "target": "node_tf_state"},
            ],
            "root_agent": {"agent_id": "node_tf_root", "role": "Infra Architect", "tier": "complex_architecture"},
            "subagents": [
                {"agent_id": "node_tf_hcl", "parent_id": "node_tf_root", "role": "HCL Evaluator", "tier": "standard_engineering"},
                {"agent_id": "node_tf_state", "parent_id": "node_tf_root", "role": "State Lock Tester", "tier": "mechanical_execution"},
            ],
        },
    ]

    total_swarm_tokens = sum(s["total_swarm_tokens"] for s in swarms_list)
    total_input_tokens = sum(s["total_input_tokens"] for s in swarms_list)
    total_cached_tokens = sum(s["total_cached_tokens"] for s in swarms_list)
    total_output_tokens = sum(s["total_output_tokens"] for s in swarms_list)
    total_thinking_tokens = sum(s["total_thinking_tokens"] for s in swarms_list)
    total_answer_tokens = sum(s["total_answer_tokens"] for s in swarms_list)
    total_swarm_turns = sum(s["total_turns"] for s in swarms_list)
    global_cache_pct = round((total_cached_tokens / total_input_tokens * 100.0), 1) if total_input_tokens else 0.0
    avg_tokens_per_turn = round(total_swarm_tokens / total_swarm_turns) if total_swarm_turns else 0
    total_avoided_usd = sum(s["avoided_cost_usd"] for s in swarms_list)
    total_avoided_gbp = sum(s["avoided_cost_gbp"] for s in swarms_list)
    unique_projects = sorted(list(set(s["workspace_name"] for s in swarms_list)))

    global_tiers = {
        "mechanical": {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "cost_gbp": 0.0, "label": "Tier 1: Mechanical (Flash Lite)"},
        "engineering": {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "cost_gbp": 0.0, "label": "Tier 2: Engineering (Fast Agent)"},
        "architecture": {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "cost_gbp": 0.0, "label": "Tier 3: Architecture (Pro Low)"},
        "other": {"count": 0, "turns": 0, "tokens": 0, "cost_usd": 0.0, "cost_gbp": 0.0, "label": "Other / Custom Model"},
    }
    for s in swarms_list:
        for t_k, t_data in s.get("tier_breakdown", {}).items():
            if t_k in global_tiers:
                global_tiers[t_k]["count"] += t_data.get("count", 0)
                global_tiers[t_k]["turns"] += t_data.get("turns", 0)
                global_tiers[t_k]["tokens"] += t_data.get("tokens", 0)
                global_tiers[t_k]["cost_usd"] += t_data.get("cost_usd", 0.0)
                global_tiers[t_k]["cost_gbp"] += t_data.get("cost_gbp", 0.0)

    for k in global_tiers:
        global_tiers[k]["cost_usd"] = round(global_tiers[k]["cost_usd"], 4)
        global_tiers[k]["cost_gbp"] = round(global_tiers[k]["cost_gbp"], 4)

    swarms_summary = {
        "total_swarms": len(swarms_list),
        "total_subagents": sum(s["subagents_count"] for s in swarms_list),
        "total_swarm_turns": total_swarm_turns,
        "total_swarm_tokens": total_swarm_tokens,
        "total_input_tokens": total_input_tokens,
        "total_cached_tokens": total_cached_tokens,
        "global_cache_hit_pct": global_cache_pct,
        "total_output_tokens": total_output_tokens,
        "total_thinking_tokens": total_thinking_tokens,
        "total_answer_tokens": total_answer_tokens,
        "avg_tokens_per_turn": avg_tokens_per_turn,
        "total_avoided_cost_usd": round(total_avoided_usd, 2),
        "total_avoided_cost_gbp": round(total_avoided_gbp, 2),
        "total_overage_credits": 0,
        "total_overage_usd": 0.0,
        "total_overage_gbp": 0.0,
        "unique_projects": unique_projects,
        "unique_projects_count": len(unique_projects),
        "global_tier_breakdown": global_tiers,
        "swarms": swarms_list,
        # Backward-compatible aliases
        "total_tokens": total_swarm_tokens,
        "total_turns": total_swarm_turns,
        "tier_routing": {
            "mechanical_execution": {
                "tier_name": "Tier 1: Mechanical Execution",
                "default_model": "1050 (Gemini Flash Lite)",
                "turns": global_tiers["mechanical"]["turns"],
                "turns_pct": round(global_tiers["mechanical"]["turns"] / total_swarm_turns * 100, 1),
                "tokens": global_tiers["mechanical"]["tokens"],
                "tokens_pct": round(global_tiers["mechanical"]["tokens"] / total_swarm_tokens * 100, 1),
            },
            "standard_engineering": {
                "tier_name": "Tier 2: Standard Engineering",
                "default_model": "1322 / 1318 (Gemini Flash)",
                "turns": global_tiers["engineering"]["turns"],
                "turns_pct": round(global_tiers["engineering"]["turns"] / total_swarm_turns * 100, 1),
                "tokens": global_tiers["engineering"]["tokens"],
                "tokens_pct": round(global_tiers["engineering"]["tokens"] / total_swarm_tokens * 100, 1),
            },
            "complex_architecture": {
                "tier_name": "Tier 3: Complex Architecture",
                "default_model": "1026 / 1035 (Claude Thinking) / 1016 (Gemini 3.1 Pro)",
                "turns": global_tiers["architecture"]["turns"],
                "turns_pct": round(global_tiers["architecture"]["turns"] / total_swarm_turns * 100, 1),
                "tokens": global_tiers["architecture"]["tokens"],
                "tokens_pct": round(global_tiers["architecture"]["tokens"] / total_swarm_tokens * 100, 1),
            },
        },
    }

    # 4. Tool Execution & Performance Intelligence
    tool_items = [
        {"tool_name": "view_file", "calls": 1540, "errors": 12, "error_pct": 0.78, "bypasses": 0, "bypass_pct": 0.0},
        {"tool_name": "run_command", "calls": 980, "errors": 42, "error_pct": 4.29, "bypasses": 135, "bypass_pct": 13.78},
        {"tool_name": "replace_file_content", "calls": 820, "errors": 19, "error_pct": 2.32, "bypasses": 0, "bypass_pct": 0.0},
        {"tool_name": "grep_search", "calls": 670, "errors": 4, "error_pct": 0.60, "bypasses": 0, "bypass_pct": 0.0},
        {"tool_name": "write_to_file", "calls": 340, "errors": 2, "error_pct": 0.59, "bypasses": 0, "bypass_pct": 0.0},
        {"tool_name": "list_dir", "calls": 290, "errors": 1, "error_pct": 0.34, "bypasses": 0, "bypass_pct": 0.0},
        {"tool_name": "manage_task", "calls": 210, "errors": 3, "error_pct": 1.43, "bypasses": 0, "bypass_pct": 0.0},
        {"tool_name": "find_by_name", "calls": 140, "errors": 0, "error_pct": 0.0, "bypasses": 0, "bypass_pct": 0.0},
        {"tool_name": "schedule", "calls": 95, "errors": 0, "error_pct": 0.0, "bypasses": 0, "bypass_pct": 0.0},
        {"tool_name": "ask_question", "calls": 35, "errors": 0, "error_pct": 0.0, "bypasses": 0, "bypass_pct": 0.0},
        {"tool_name": "invoke_subagent", "calls": 24, "errors": 0, "error_pct": 0.0, "bypasses": 0, "bypass_pct": 0.0},
        {"tool_name": "read_url_content", "calls": 18, "errors": 1, "error_pct": 5.56, "bypasses": 0, "bypass_pct": 0.0},
    ]

    total_tool_calls = sum(t["calls"] for t in tool_items)
    total_tool_errors = sum(t["errors"] for t in tool_items)
    total_tool_bypasses = sum(t["bypasses"] for t in tool_items)

    tool_analytics_data = {
        "total_tool_calls": total_tool_calls,
        "unique_tools_count": len(tool_items),
        "total_errors": total_tool_errors,
        "overall_error_rate_pct": round((total_tool_errors / total_tool_calls) * 100.0, 2),
        "total_sandbox_bypasses": total_tool_bypasses,
        "sandbox_bypass_rate_pct": round((total_tool_bypasses / total_tool_calls) * 100.0, 2),
        "tools": tool_items,
    }

    # 5. Summary Statistics
    total_input = sum(p["total_input_tokens"] for p in projects_data)
    total_cached = sum(p["cached_tokens"] for p in projects_data)
    total_output = sum(p["total_output_tokens"] for p in projects_data)
    total_thinking = sum(p["thinking_tokens"] for p in projects_data)
    total_processed = total_input + total_output
    cache_hit_pct = round((total_cached / total_input) * 100.0, 2)

    total_gbp = sum(p["estimated_cost_gbp"] for p in projects_data)
    total_usd = sum(p["estimated_cost_usd"] for p in projects_data)

    summary_data = {
        "is_demo": True,
        "demo_title": "Interactive Showcase Demo (Synthetic Telemetry Benchmark)",
        "subscription_tier": "pro",
        "subscription_tier_name": "Google AI Pro (2 TB - Standard Quota)",
        "subscription_status": "SAFE_IN_QUOTA",
        "monthly_subscription_price_gbp": 18.99,
        "monthly_subscription_price_usd": 19.99,
        "monthly_renewal_human": "9 days",
        "monthly_cycle_imputed_value_usd": round(total_usd, 2),
        "monthly_cycle_imputed_value_gbp": round(total_gbp, 2),
        "monthly_subscription_roi": round(total_gbp / 18.99, 1) if total_gbp > 0 else 7.3,
        "credit_pack_price_usd": 25.00,
        "credit_pack_price_gbp": 23.99,
        "packs_purchased": 1,
        "credit_bank_total": 2500,
        "credits_remaining": 2150,
        "total_ai_credits_burned": 350,
        "total_credit_burn_gbp": 3.36,
        "total_credit_burn_usd": 4.25,
        "credit_bank_remaining_usd": 20.75,
        "credit_bank_remaining_gbp": 20.63,
        "total_processed_tokens": total_processed,
        "total_input_tokens": total_input,
        "total_cached_tokens": total_cached,
        "total_output_tokens": total_output,
        "total_thinking_tokens": total_thinking,
        "cache_hit_ratio_pct": cache_hit_pct,
        "total_imputed_value_gbp": round(total_gbp, 2),
        "total_imputed_value_usd": round(total_usd, 2),
        "by_model": {
            "1318": {"name": "Gemini 3.8 Flash (High)", "turn_count": 68, "total_processed_tokens": 14200000, "estimated_cost_gbp": 44.50},
            "1016": {"name": "Gemini 3.1 Pro (High)", "turn_count": 34, "total_processed_tokens": 9800000, "estimated_cost_gbp": 38.20},
            "1322": {"name": "Gemini Fast Agent Assistant", "turn_count": 42, "total_processed_tokens": 7100000, "estimated_cost_gbp": 22.40},
            "1050": {"name": "Gemini Flash Lite (Subagent)", "turn_count": 30, "total_processed_tokens": 3250000, "estimated_cost_gbp": 6.80},
            "1035": {"name": "Claude Sonnet 4.6 (Thinking)", "turn_count": 18, "total_processed_tokens": 4100000, "estimated_cost_gbp": 16.20},
            "1026": {"name": "Claude Opus 4.6 (Thinking)", "turn_count": 12, "total_processed_tokens": 2850000, "estimated_cost_gbp": 11.40},
            "342": {"name": "GPT-OSS 120B (Medium)", "turn_count": 9, "total_processed_tokens": 1250000, "estimated_cost_gbp": 3.40},
        },
        "subagent_metrics": {
            "interactive": {
                "total_tokens": 12800000,
                "imputed_cost_usd": 48.50,
                "turn_count": 52,
            },
            "subagent": {
                "total_tokens": 26100000,
                "imputed_cost_usd": 91.30,
                "turn_count": 86,
                "quota_share_pct": 67.1,
            },
        },
    }

    # 6. Quotas, Silos & Model Allowance Matrix
    recovery_schedule = [
        {"minutes_remaining": 14, "tokens_to_recover": 640000, "model_name": "Gemini 3.8 Flash (High)"},
        {"minutes_remaining": 48, "tokens_to_recover": 480000, "model_name": "Claude Sonnet 4.6 (Thinking)"},
        {"minutes_remaining": 112, "tokens_to_recover": 820000, "model_name": "Gemini 3.1 Pro (High)"},
        {"minutes_remaining": 175, "tokens_to_recover": 350000, "model_name": "Gemini Fast Agent Assistant"},
        {"minutes_remaining": 230, "tokens_to_recover": 160000, "model_name": "GPT-OSS 120B (Medium)"},
    ]

    active_sessions_5h = [
        {
            "convo_id": "00000000-0000-0000-0001-000000000001",
            "title": "Architecture & AST Wire Protocol Lead",
            "workspace_name": "agentic-code-reviewer",
            "total_processed_tokens": 850000,
            "turn_count": 16,
            "primary_model_name": "Gemini 3.8 Flash (High)",
        },
        {
            "convo_id": "00000000-0000-0000-0001-000000000003",
            "title": "Zero-Copy Ring Buffer & Microbenchmarks",
            "workspace_name": "distributed-kv-cache",
            "total_processed_tokens": 620000,
            "turn_count": 14,
            "primary_model_name": "Gemini 3.8 Flash (High)",
        },
        {
            "convo_id": "00000000-0000-0000-0001-000000000005",
            "title": "Connect-RPC Gateway Protocol & Fuzzing",
            "workspace_name": "realtime-telemetry-api",
            "total_processed_tokens": 380000,
            "turn_count": 8,
            "primary_model_name": "Gemini 3.1 Pro (High)",
        },
    ]

    rolling_5h_by_model = [
        {
            "model_id": "1318",
            "model_name": "Gemini 3.8 Flash (High)",
            "turn_count": 24,
            "prompt_tokens_uncached": 80000,
            "cached_tokens": 1170000,
            "total_input_tokens": 1250000,
            "cache_hit_ratio_pct": 93.6,
            "output_tokens_total": 92000,
            "thinking_tokens": 22000,
            "total_processed_tokens": 1342000,
            "avoided_cost_usd": 4.80,
            "avoided_cost_gbp": 3.80,
        },
        {
            "model_id": "1016",
            "model_name": "Gemini 3.1 Pro (High)",
            "turn_count": 10,
            "prompt_tokens_uncached": 45000,
            "cached_tokens": 575000,
            "total_input_tokens": 620000,
            "cache_hit_ratio_pct": 92.7,
            "output_tokens_total": 52000,
            "thinking_tokens": 28000,
            "total_processed_tokens": 672000,
            "avoided_cost_usd": 3.00,
            "avoided_cost_gbp": 2.40,
        },
        {
            "model_id": "1050",
            "model_name": "Gemini Flash Lite (Subagent)",
            "turn_count": 8,
            "prompt_tokens_uncached": 10000,
            "cached_tokens": 230000,
            "total_input_tokens": 240000,
            "cache_hit_ratio_pct": 95.8,
            "output_tokens_total": 12000,
            "thinking_tokens": 0,
            "total_processed_tokens": 252000,
            "avoided_cost_usd": 0.60,
            "avoided_cost_gbp": 0.50,
        },
        {
            "model_id": "1035",
            "model_name": "Claude Sonnet 4.6 (Thinking)",
            "turn_count": 5,
            "prompt_tokens_uncached": 15000,
            "cached_tokens": 205000,
            "total_input_tokens": 220000,
            "cache_hit_ratio_pct": 93.2,
            "output_tokens_total": 24000,
            "thinking_tokens": 18000,
            "total_processed_tokens": 244000,
            "avoided_cost_usd": 1.50,
            "avoided_cost_gbp": 1.20,
        },
        {
            "model_id": "1026",
            "model_name": "Claude Opus 4.6 (Thinking)",
            "turn_count": 3,
            "prompt_tokens_uncached": 8000,
            "cached_tokens": 92000,
            "total_input_tokens": 100000,
            "cache_hit_ratio_pct": 92.0,
            "output_tokens_total": 16000,
            "thinking_tokens": 12000,
            "total_processed_tokens": 116000,
            "avoided_cost_usd": 1.00,
            "avoided_cost_gbp": 0.80,
        },
    ]

    rolling_1w_by_model = [
        {
            "model_id": "1318",
            "model_name": "Gemini 3.8 Flash (High)",
            "turn_count": 68,
            "prompt_tokens_uncached": 930000,
            "cached_tokens": 13270000,
            "total_input_tokens": 14200000,
            "cache_hit_ratio_pct": 93.5,
            "output_tokens_total": 980000,
            "thinking_tokens": 120000,
            "total_processed_tokens": 15180000,
            "avoided_cost_usd": 56.30,
            "avoided_cost_gbp": 44.50,
        },
        {
            "model_id": "1016",
            "model_name": "Gemini 3.1 Pro (High)",
            "turn_count": 34,
            "prompt_tokens_uncached": 710000,
            "cached_tokens": 9090000,
            "total_input_tokens": 9800000,
            "cache_hit_ratio_pct": 92.8,
            "output_tokens_total": 780000,
            "thinking_tokens": 95000,
            "total_processed_tokens": 10580000,
            "avoided_cost_usd": 48.40,
            "avoided_cost_gbp": 38.20,
        },
        {
            "model_id": "1322",
            "model_name": "Gemini Fast Agent Assistant",
            "turn_count": 42,
            "prompt_tokens_uncached": 410000,
            "cached_tokens": 6690000,
            "total_input_tokens": 7100000,
            "cache_hit_ratio_pct": 94.2,
            "output_tokens_total": 420000,
            "thinking_tokens": 0,
            "total_processed_tokens": 7520000,
            "avoided_cost_usd": 28.40,
            "avoided_cost_gbp": 22.40,
        },
        {
            "model_id": "1050",
            "model_name": "Gemini Flash Lite (Subagent)",
            "turn_count": 30,
            "prompt_tokens_uncached": 120000,
            "cached_tokens": 3130000,
            "total_input_tokens": 3250000,
            "cache_hit_ratio_pct": 96.3,
            "output_tokens_total": 150000,
            "thinking_tokens": 0,
            "total_processed_tokens": 3400000,
            "avoided_cost_usd": 8.60,
            "avoided_cost_gbp": 6.80,
        },
        {
            "model_id": "1035",
            "model_name": "Claude Sonnet 4.6 (Thinking)",
            "turn_count": 18,
            "prompt_tokens_uncached": 270000,
            "cached_tokens": 3830000,
            "total_input_tokens": 4100000,
            "cache_hit_ratio_pct": 93.4,
            "output_tokens_total": 310000,
            "thinking_tokens": 64000,
            "total_processed_tokens": 4410000,
            "avoided_cost_usd": 20.50,
            "avoided_cost_gbp": 16.20,
        },
        {
            "model_id": "1026",
            "model_name": "Claude Opus 4.6 (Thinking)",
            "turn_count": 12,
            "prompt_tokens_uncached": 220000,
            "cached_tokens": 2630000,
            "total_input_tokens": 2850000,
            "cache_hit_ratio_pct": 92.3,
            "output_tokens_total": 240000,
            "thinking_tokens": 42000,
            "total_processed_tokens": 3090000,
            "avoided_cost_usd": 14.40,
            "avoided_cost_gbp": 11.40,
        },
        {
            "model_id": "342",
            "model_name": "GPT-OSS 120B (Medium)",
            "turn_count": 9,
            "prompt_tokens_uncached": 100000,
            "cached_tokens": 1150000,
            "total_input_tokens": 1250000,
            "cache_hit_ratio_pct": 92.0,
            "output_tokens_total": 85000,
            "thinking_tokens": 15000,
            "total_processed_tokens": 1335000,
            "avoided_cost_usd": 4.30,
            "avoided_cost_gbp": 3.40,
        },
    ]

    quotas_data = {
        "providers": {
            "gemini": {
                "five_hour": {
                    "capacity_usd": 100.0,
                    "used_usd": 21.00,
                    "used_pct": 21.0,
                    "remaining_pct": 79.0,
                    "total_processed_tokens": 1850000,
                    "turn_count": 38,
                    "status": "SAFE",
                    "reset_time": "2026-09-14T14:45:00Z",
                    "recovery_schedule": recovery_schedule,
                    "active_sessions_5h": active_sessions_5h,
                },
                "weekly": {
                    "capacity_usd": 645.0,
                    "used_usd": 206.40,
                    "used_pct": 32.0,
                    "remaining_pct": 68.0,
                    "weekly_reset_utc": "2026-09-20T17:58:04Z",
                    "reset_display": "Sunday 17:58 UTC",
                    "human_remaining": "4d 6h",
                    "message": "It will fully refresh in 4 days, 6 hours",
                    "status": "SAFE",
                },
                "runway": {
                    "burn_velocity_index": 0.84,
                    "bvi_display": "0.84x",
                    "status_key": "green",
                    "status_text": "Sustainable (0.84x)",
                    "status_sub": "Safe pace (12.8% buffer)",
                    "quota_consumed_pct": 32.0,
                    "calendar_time_elapsed_pct": 58.0,
                    "calendar_days_elapsed": "4.1",
                    "calendar_days_remaining": 3,
                    "day_number": 4,
                    "day_index": 4,
                    "daily_ceiling_pct": 57.1,
                    "target_daily_budget_pct": 14.3,
                    "target_daily_budget_usd": 92.14,
                    "exhaustion_eta": "None",
                    "exhaustion_caption": "Survives to reset",
                    "burst_used_pct": 21.0,
                    "burst_cooldown_active": False,
                },
            },
            "claude_gpt": {
                "five_hour": {
                    "capacity_usd": 50.0,
                    "used_usd": 8.20,
                    "used_pct": 16.4,
                    "remaining_pct": 83.6,
                    "total_processed_tokens": 580000,
                    "turn_count": 12,
                    "status": "SAFE",
                },
                "weekly": {
                    "capacity_usd": 175.0,
                    "used_usd": 42.10,
                    "used_pct": 24.1,
                    "remaining_pct": 75.9,
                    "message": "Fully refreshed • 7-day rolling window",
                    "status": "SAFE",
                },
            },
        },
        "rolling_5h": {
            "total_processed_tokens": 2430000,
            "turn_count": 50,
            "recovery_schedule": recovery_schedule,
            "active_sessions_5h": active_sessions_5h,
            "by_model": rolling_5h_by_model,
        },
        "rolling_1w": {
            "total_processed_tokens": 34900000,
            "turn_count": 192,
            "reset_day_name": "Sunday",
            "by_model": rolling_1w_by_model,
        },
        "weekly_cycle": {
            "total_processed_tokens": 34900000,
            "turn_count": 192,
            "reset_day_name": "Sunday",
            "by_model": rolling_1w_by_model,
        },
        "credit_bank": {
            "remaining_credits": 2150,
            "total_purchased": 2500,
            "is_prepaid_overage_pool": True,
        },
    }

    # 7. Google One AI Credit Activity Reconciliation (Hourly Statement Blocks)
    hourly_credit_activity = [
        {
            "hour_timestamp": "2026-09-06T14:00:00Z",
            "hour_display": "06 Sep 2026, 14:00:00 UTC",
            "turns_count": 18,
            "credits_burned": 200,
            "credit_burn_usd": 2.43,
            "credit_burn_gbp": 1.92,
            "models": {
                "Gemini 3.1 Pro (High)": 12,
                "Claude Sonnet 4.6 (Thinking)": 6,
            },
        },
        {
            "hour_timestamp": "2026-09-06T15:00:00Z",
            "hour_display": "06 Sep 2026, 15:00:00 UTC",
            "turns_count": 14,
            "credits_burned": 150,
            "credit_burn_usd": 1.82,
            "credit_burn_gbp": 1.44,
            "models": {
                "Gemini 3.8 Flash (High)": 9,
                "Claude Opus 4.6 (Thinking)": 5,
            },
        },
    ]

    # 8. Weekly Trends (12 Cycles - Calibrated to 34.9M Avg & 41.8M Peak)
    weekly_cycle_specs = [
        (1,  "2026-06-23T00:00:00Z", "2026-06-29T23:59:59Z", "23 Jun – 29 Jun 2026", 142, 25300000, 23100000, 1800000, 108.40, 85.60, 0.68, 0),
        (2,  "2026-06-30T00:00:00Z", "2026-07-06T23:59:59Z", "30 Jun – 06 Jul 2026", 158, 27100000, 24800000, 2000000, 114.20, 90.20, 0.72, 0),
        (3,  "2026-07-07T00:00:00Z", "2026-07-13T23:59:59Z", "07 Jul – 13 Jul 2026", 175, 29800000, 27400000, 2200000, 125.80, 99.40, 0.81, 0),
        (4,  "2026-07-14T00:00:00Z", "2026-07-20T23:59:59Z", "14 Jul – 20 Jul 2026", 160, 28900000, 26600000, 2100000, 121.50, 96.00, 0.69, 0),
        (5,  "2026-07-21T00:00:00Z", "2026-07-27T23:59:59Z", "21 Jul – 27 Jul 2026", 189, 32100000, 29600000, 2400000, 134.60, 106.30, 0.88, 0),
        (6,  "2026-07-28T00:00:00Z", "2026-08-03T23:59:59Z", "28 Jul – 03 Aug 2026", 204, 33800000, 31300000, 2600000, 142.10, 112.30, 0.79, 0),
        (7,  "2026-08-04T00:00:00Z", "2026-08-10T23:59:59Z", "04 Aug – 10 Aug 2026", 215, 34900000, 32300000, 2700000, 148.50, 117.30, 0.85, 0),
        (8,  "2026-08-11T00:00:00Z", "2026-08-17T23:59:59Z", "11 Aug – 17 Aug 2026", 195, 33200000, 30700000, 2500000, 139.70, 110.40, 0.76, 0),
        (9,  "2026-08-18T00:00:00Z", "2026-08-24T23:59:59Z", "18 Aug – 24 Aug 2026", 242, 38800000, 36100000, 3000000, 178.40, 140.90, 0.94, 0),
        (10, "2026-08-25T00:00:00Z", "2026-08-31T23:59:59Z", "25 Aug – 31 Aug 2026", 218, 35500000, 33000000, 2700000, 149.20, 117.90, 0.82, 0),
        (11, "2026-09-01T00:00:00Z", "2026-09-07T23:59:59Z", "01 Sep – 07 Sep 2026", 248, 37700000, 35000000, 2800000, 168.50, 133.10, 1.14, 350),
        (12, "2026-09-08T00:00:00Z", "2026-09-14T12:00:00Z", "08 Sep – 14 Sep 2026", 192, 32400000, 30100000, 2500000, 136.20, 107.60, 0.78, 0),
    ]

    trends_cycles = []
    for spec in weekly_cycle_specs:
        idx, c_start, c_end, c_lbl, c_turns, in_toks, cached_toks, out_toks, cost_usd, cost_gbp, bvi, ovg_credits = spec
        total_proc = in_toks + out_toks
        uncached = in_toks - cached_toks
        cache_pct = round((cached_toks / in_toks) * 100.0, 1)
        ovg_gbp = round(ovg_credits * 0.0096, 2) if ovg_credits > 0 else 0.0
        ovg_usd = round(ovg_gbp * 1.265, 2) if ovg_credits > 0 else 0.0
        is_cur = (idx == 12)

        trends_cycles.append({
            "cycle_key": f"cycle-2026-w{25 + idx}",
            "cycle_start_utc": c_start,
            "cycle_end_utc": c_end,
            "label": c_lbl,
            "total_turns": c_turns,
            "total_input_tokens": in_toks,
            "cached_tokens": cached_toks,
            "prompt_tokens_uncached": uncached,
            "total_output_tokens": out_toks,
            "total_processed_tokens": total_proc,
            "cache_hit_ratio_pct": cache_pct,
            "estimated_cost_usd": cost_usd,
            "estimated_cost_gbp": cost_gbp,
            "actual_overage_credits": ovg_credits,
            "actual_overage_usd": ovg_usd,
            "actual_overage_gbp": ovg_gbp,
            "peak_bvi": bvi,
            "is_current_cycle": is_cur,
            # Backward-compatible aliases
            "cycle_idx": idx,
            "start_time": c_start,
            "end_time": c_end,
            "total_tokens": total_proc,
            "avoided_cost_gbp": cost_gbp,
            "paid_overage_gbp": ovg_gbp,
            "peak_burn_velocity": bvi,
        })

    peak_c = max(trends_cycles, key=lambda c: c["total_processed_tokens"])
    prev_completed_growth = round(
        ((trends_cycles[10]["total_processed_tokens"] - trends_cycles[9]["total_processed_tokens"])
         / trends_cycles[9]["total_processed_tokens"]) * 100.0,
        1,
    )

    weekly_trends = {
        "cycles": trends_cycles,
        "total_cycles_recorded": len(trends_cycles),
        "summary": {
            "cycles_analyzed": len(trends_cycles),
            "total_archived_cycles": len(trends_cycles),
            "average_tokens_per_week": int(round(sum(c["total_processed_tokens"] for c in trends_cycles) / len(trends_cycles))),
            "average_cost_per_week_usd": round(sum(c["estimated_cost_usd"] for c in trends_cycles) / len(trends_cycles), 2),
            "average_cost_per_week_gbp": round(sum(c["estimated_cost_gbp"] for c in trends_cycles) / len(trends_cycles), 2),
            "peak_week_tokens": peak_c["total_processed_tokens"],
            "peak_week_label": peak_c["label"],
            "peak_week_cost_usd": peak_c["estimated_cost_usd"],
            "token_growth_rate_pct": prev_completed_growth,
            "overage_cycles_count": sum(1 for c in trends_cycles if c["actual_overage_credits"] > 0),
            "total_overage_credits": sum(c["actual_overage_credits"] for c in trends_cycles),
            "average_cache_hit_pct": round(sum(c["cache_hit_ratio_pct"] for c in trends_cycles) / len(trends_cycles), 1),
        },
    }

    # 9. Assemble Full Payload
    return {
        "summary": summary_data,
        "projects": projects_data,
        "conversations": conversations,
        "swarms": swarms_summary,
        "tool_analytics": tool_analytics_data,
        "quotas": quotas_data,
        "weekly_trends": weekly_trends,
        "hourly_credit_activity": hourly_credit_activity,
    }


def generate_demo_html(index_path: Path, demo_path: Path) -> None:
    """Generate standalone demo.html pointing directly to data.demo.js."""
    if not index_path.exists():
        return
    html = index_path.read_text(encoding="utf-8")
    demo_html = html.replace('<script src="data.js"></script>', '<script src="data.demo.js"></script>')
    demo_path.parent.mkdir(parents=True, exist_ok=True)
    demo_path.write_text(demo_html, encoding="utf-8")
    print(f"[*] Wrote standalone demo HTML to {demo_path}")


def write_demo_files(out_data_path: Path, out_meta_path: Path | None = None) -> None:
    """Generate and write deterministic synthetic demo data and optional meta hash."""
    payload = generate_synthetic_payload()
    json_payload = json.dumps(payload, indent=2, sort_keys=True)

    out_data_path.parent.mkdir(parents=True, exist_ok=True)
    out_data_path.write_text(f"window.__TELEMETRY_DATA__ = {json_payload};\n", encoding="utf-8")
    print(f"[*] Wrote synthetic demo payload to {out_data_path}")

    # Also keep data.demo.js synchronized if writing to another target like data.js
    if out_data_path.name != "data.demo.js" and out_data_path.parent.name == "dashboard":
        demo_js = out_data_path.parent / "data.demo.js"
        demo_js.write_text(f"window.__TELEMETRY_DATA__ = {json_payload};\n", encoding="utf-8")

    if out_meta_path:
        out_meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_content = 'window.__TELEMETRY_HASH__ = "demo_showcase_hash_v210";\n'
        out_meta_path.write_text(meta_content, encoding="utf-8")
        print(f"[*] Wrote demo meta hash to {out_meta_path}")

    # Synchronize demo.html if index.html is located in same directory
    index_html = out_data_path.parent / "index.html"
    demo_html = out_data_path.parent / "demo.html"
    generate_demo_html(index_html, demo_html)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic Antigravity demo showcase payload.")
    parser.add_argument("--out", default="dashboard/data.demo.js", help="Path to write demo data.js (default: dashboard/data.demo.js)")
    parser.add_argument("--meta-out", default=None, help="Optional path to write demo meta.js")
    args = parser.parse_args()

    out_data = Path(args.out)
    out_meta = Path(args.meta_out) if args.meta_out else None
    write_demo_files(out_data, out_meta)
    print("✓ Synthetic demo showcase generation complete.")


if __name__ == "__main__":
    main()
