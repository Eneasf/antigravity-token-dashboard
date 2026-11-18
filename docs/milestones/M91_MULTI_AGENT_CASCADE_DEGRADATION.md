# Milestone 91: Multi-Agent Swarms, Weakest-Link Risk Scoring & Native Popover Cascade Trees

**Date**: 2026-10-07  
**Scope**: Telemetry Engine (`scripts/export_dashboard.py`), Weakest-Link Risk Model, Dual-State Context Degradation, Native macOS Menu Bar Popover (`PopoverContentView.swift`, `StatusModel.swift`), Web Dashboard (`dashboard/js/sessions.js`), Automated Test Suite (`tests/test_multiagent_degradation.py`)  
**Branch**: `feat/multi-agent-cascade-degradation`  
**Verdict**: **PASS**  

---

## 1. Overview & Architectural Motivation

As Antigravity agentic workflows expanded into multi-project concurrency and cascading swarms (such as `/boost`, multi-agent orchestrator hierarchies, and concurrent task runners across independent repositories), the previous context degradation telemetry suffered from critical blind spots:

1. **Multi-Project Concurrency Blindness**: When running multiple autonomous agents across distinct project workspaces concurrently, users had zero visibility into which project was healthy and which was accumulating dangerous token depth or nearing context boundaries.
2. **Subagent Invisibility & Cascade Blindness**: In cascading workflows (e.g. `/boost`, orchestrator + subagent chains), `scripts/export_dashboard.py` explicitly filtered out subagent conversations (`is_subagent_conversation`), making subagent degradation completely invisible until sudden truncation or unrecoverable drift occurred.
3. **Historic Peak False Alarms**: The previous telemetry tracked `max(turns, key=lambda t: t['total_input_tokens'])`. If a session expanded to 240k tokens and subsequently compacted or restarted down to 35k tokens, the monitor remained permanently stuck displaying a "Critical 240k" warning even though the current turn was completely safe.
4. **Lack of Risk Prioritization**: Without an automated weakest-link election mechanism, users monitoring the macOS menu bar or web dashboard could not identify which specific agent node in an orchestrator-subagent tree was the immediate bottleneck.

Milestone 91 introduces a unified architectural solution ratified in **ADR-092**.

---

## 2. Architecture Decisions Adopted

### ADR-092: Multi-Agent Swarm Grouping, Weakest-Link Risk Scoring & Dual-State Context Metrics

- **Decoupling Current Capacity from Compaction Epoch**:
  - Evaluates current capacity load against the **latest turn ($t_n$) prompt depth**, preventing post-compaction false alarms.
  - Retains memory fidelity tracking via **Compaction Epoch ($E1..E3+$)** and drift state indicators (`Safe E1`, `Caution E2`, `High Risk E3+`).
- **Weakest-Link Risk Scoring**:
  - Implements priority-weighted base scoring:
    - `critical` ($\ge 90\%$ capacity or $\ge 300\text{k}$ tok): base $300 + (\text{pct} \times 100)$
    - `warning` ($\ge 70\%$ capacity or $\ge 200\text{k}$ tok): base $200 + (\text{pct} \times 100)$
    - `safe` orchestrator: base $150 + (\text{pct} \times 50)$
    - `safe` subagent: base $100 + (\text{pct} \times 50)$
  - Ensures any subagent entering warning or critical states immediately preempts safe orchestrators as the primary alert.
- **Velocity Spike Detection**:
  - Detects single-turn token growth $\ge 40{,}000$ tokens/turn and flags `velocity_spike: true`, providing early warning against runaway payload swelling before context boundaries are crossed.
- **Multi-Project Swarm Hierarchy**:
  - Groups active sessions within a 30-minute recency window (with fixture fallback) by workspace.
  - Structures trees into orchestrator parent nodes and child subagents, identifying the weakest link within each group.
- **macOS Menu Bar Popover Progressive Disclosure**:
  - Pinned active session card surfaces subagent role badges (`arrow.triangle.branch`) and parent links (`↳ child of <parent>`).
  - Added collapsible `Active Swarms & Projects` section rendering workspace headers, orchestrator status, and nested subagent micro-meters with `⚠️ WEAKEST LINK` highlights.
- **Web Dashboard Integration**:
  - Updates Now tab header badge and pinned active session card with subagent role badges, parent links, and epoch indicators.

---

## 3. Data Schema & Contracts

### Enriched Status Payload (`~/.antigravity_quota_status.json`)

```json
{
  "degraded_session": {
    "convo_id": "sub-1",
    "title": "Subagent: Codebase Researcher",
    "workspace_name": "Project Alpha",
    "git_branch": "main",
    "is_subagent": true,
    "subagent_role": "research",
    "parent_convo_id": "orch-1",
    "tokens": 230000,
    "tokens_latest_turn": 230000,
    "threshold": 250000,
    "percentage": 92.0,
    "severity": "critical",
    "compaction_epoch": 1,
    "velocity_spike": false,
    "drift_risk": "critical",
    "drift_message": "Compaction Imminent (92%)"
  },
  "active_swarms": [
    {
      "workspace_name": "Project Alpha",
      "weakest_link_id": "sub-1",
      "orchestrator": {
        "convo_id": "orch-1",
        "title": "Orchestrator Session",
        "tokens": 50000,
        "percentage": 20.0,
        "severity": "safe"
      },
      "subagents": [
        {
          "convo_id": "sub-1",
          "title": "Subagent: Codebase Researcher",
          "subagent_role": "research",
          "parent_convo_id": "orch-1",
          "tokens": 230000,
          "percentage": 92.0,
          "severity": "critical"
        }
      ]
    }
  ]
}
```

---

## 4. Verification Gate Proofs

- **Gate A1-1 & A1-2 (Unit Test Verification)**:
  `python3 -m unittest tests/test_multiagent_degradation.py`
  $\rightarrow$ **Ran 5 tests in 0.006s, OK**.
- **Gate A2-1 (Documentation Integrity)**:
  `python3 -m unittest tests/test_docs_integrity.py`
  $\rightarrow$ **Ran 12 tests in 2.94s, OK**.
- **Gate A2-2 (VDONE Gate Runner)**:
  `python3 -m unittest tests/test_vdone_gates.py`
  $\rightarrow$ **Ran 4 tests in 7.68s, OK**.
- **Gate A3-1 (Headless Playwright Boot)**:
  `npx playwright test e2e/dashboard-boot.spec.js`
  $\rightarrow$ **1 passed in 9.2s, OK (0 console/page errors)**.
- **Gate A4-1 (Native Swift Package Compilation)**:
  `swift build --package-path macos/AntigravityBar`
  $\rightarrow$ **Build complete (0 warnings, 0 errors)**.
- **Gate A5-1 (Golden Fixture Determinism)**:
  `python3 scripts/export_dashboard.py --antigravity-dir tests/fixtures/sample_antigravity --output-dir tmp/a5_m91 && grep -q 'active_swarms' tmp/a5_m91/meta.json`
  $\rightarrow$ **Deterministic export verified (A5_OK)**.
- **Gate Quality (Git Whitespace Check)**:
  `git diff --check`
  $\rightarrow$ **Clean (0 errors)**.
