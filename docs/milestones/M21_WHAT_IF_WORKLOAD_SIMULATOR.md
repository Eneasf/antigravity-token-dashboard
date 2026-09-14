# Milestone M21: Interactive "What-If" Workload Simulator & Quota Stress Planner

**Date**: 12 September 2026  
**Branch**: `feat/what-if-workload-simulator`  
**ADR**: ADR-035 — Interactive "What-If" Workload Simulator & Quota Stress Planner

---

## 1. Background & Problem

Following Milestone 20's establishment of dynamic plan profiles (`Pro 2TB`, `Enterprise 5x`, `Ultra 10x`, `Custom`), model pricing rate cards, and promotional capacity multipliers, developers required an interactive way to forecast multi-agent swarm workloads before executing them:
- **Blind Burst Execution**: Launching multi-agent tasks (e.g. 40 turns of Gemini 3.1 Pro or Claude 3 Opus) frequently risked unexpected 5h burst exhaustion or HTTP 429 lockouts mid-run.
- **Divergent Provider Spillover Behavior (ADR-019 & ADR-030)**:
  - On **Gemini Models (Track 1)**, exceeding the 5h burst spills over into prepaid Google One AI Credit packs at model compute rates (e.g. 2.5 credits/turn for Flash). Developers could not predict the exact credit and cash deduction before running the session.
  - On **Claude & GPT Models (Track 2)**, zero credit spillover exists. Exceeding quota triggers an immediate, unrecoverable HTTP 429 hard block (the empirical ~30-95 turn boundary on Claude Opus documented in ADR-030).
- **Subscription Headroom & Upgrade Justification**: Developers had no deterministic way to evaluate whether upgrading from Pro (£18.99/mo) to Enterprise 5x (£49.99/mo) or Ultra 10x would alleviate their specific bottleneck without trial and error.

Milestone 21 delivers **ADR-035**, introducing a pure-Python deterministic simulation engine (`src/simulator.py`), aggregator integration with standard multi-agent archetypes (`src/aggregator.py`), and a rich visual UI tab in `dashboard/index.html` featuring real-time sliders, safety gauges, and plan tier sensitivity benchmarking.

---

## 2. Architecture & Design Specification (ADR-035)

### A. Mathematical Formulation (`src/simulator.py`)

Given a planned session of $N$ turns on model $M$ with prompt context $C_{prompt}$, cache hit ratio $R_{cache}$, thinking tokens $T_{thinking}$, and candidate answer output $T_{answer}$:

1. **Token Derivations**:
   $$\begin{aligned}
   T_{uncached} &= \text{round}(C_{prompt} \times (1 - R_{cache})) \\
   T_{cached} &= C_{prompt} - T_{uncached} \\
   T_{output} &= T_{thinking} + T_{answer} \\
   T_{processed} &= C_{prompt} + T_{output}
   \end{aligned}$$

2. **Imputed Cost per Turn**:
   $$\text{Cost}_{USD} = \frac{T_{uncached} \times r_{uncached} + T_{cached} \times r_{cached} + T_{output} \times r_{output}}{10^6}$$
   $$\text{Total Cost}_{USD} = N \times \text{Cost}_{USD}, \quad \text{Total Cost}_{GBP} = \text{Total Cost}_{USD} \times 0.79$$

3. **Quota Headroom & Exhaustion Progression**:
   For turns $t = 1 \dots N$, cumulative 5h load is:
   $$L_{5h}(t) = U_{5h}^{start} + t \times \text{Cost}_{USD}$$
   Exhaustion turn $t_{exhaustion}$ is the minimum $t$ where $L_{5h}(t) > C_{5h}^{burst}$.

4. **Dual-Track Spillover vs. Hard Lockout**:
   - **Track 1 (`gemini`)**:
     $$\text{Credits Debited} = \text{round}(N_{over} \times c_{turn}), \quad \text{where } N_{over} = N - t_{exhaustion} + 1$$
     $$\text{Spillover Cost}_{GBP} = \text{Credits Debited} \times £0.009596$$
   - **Track 2 (`claude_gpt`)**:
     $$\text{Credits Debited} = 0, \quad \text{Hard 429 Lockout Risk} = \text{True if } L_{5h}(N) > C_{5h}$$

---

### B. Standard Multi-Agent Archetype Presets

| Archetype ID | Name | Model | Turns | Prompt Context | Cache % | Thinking | Pace | Focus Area |
|---|---|---|---|---|---|---|---|---|
| `deep_refactor_swarm` | Deep Refactor Swarm | Gemini 3.1 Pro High (`1016`) | 40 | 120,000 | 88% | 8,000 | 2.5 min | Architecture refactoring & heavy reasoning |
| `codebase_audit` | Codebase Audit & Scan | Gemini 3.8 Flash High (`1318`) | 60 | 200,000 | 94% | 2,500 | 1.5 min | Full codebase audits & security scans |
| `rapid_prototyping_burst` | Rapid Prototyping Burst | Gemini 3.8 Flash Med (`1319`) | 25 | 45,000 | 75% | 1,500 | 1.0 min | Fast interactive feature iteration |
| `claude_opus_deep_dive` | Claude 3 Opus Stress | Claude Opus Thinking (`1026`) | 35 | 95,000 | 92% | 6,000 | 2.0 min | ADR-030 empirical 30-95 turn 429 boundary |
| `subagent_fleet` | Subagent Fleet (Lite) | Gemini Flash Lite (`1050`) | 100 | 30,000 | 85% | 500 | 0.5 min | High-throughput mechanical tasks |

---

### C. Visual UI Surface (`dashboard/index.html`)

- **Navigation**: Dedicated top-level tab `<button id="tab-simulator">🧪 What-If Simulator</button>`.
- **Archetype Bar**: One-click quick-select pills populating all parameters instantly.
- **Controls Column**: Real-time sliders for turn count ($1-150$), prompt context ($1\text{k}-500\text{k}$), cache ratio ($0-99\%$), thinking depth ($0-32\text{k}$), and pacing ($0.2-10\text{ min/turn}$).
- **Predictive Outcome Column**:
  - **Dynamic Health Gauge**: Visually indicates Safe Zone ($\ge 50\%$), Caution ($20-50\%$), Cooldown (burst exceeded on Gemini), or 429 Lockout (Claude burst or weekly exhausted).
  - **KPI Grid**: 5h Burst Load, Weekly Runway Impact, Imputed Developer Value, and HTTP 429 / Credit Spillover Risk.
  - **SVG Trajectory Chart**: Responsive turn-by-turn quota curve plotted against the 100% burst threshold.
  - **Tier Sensitivity Table**: Direct side-by-side comparison across Pro, Enterprise 5x, and Ultra 10x.

---

## 3. Verification & Acceptance Gates (VDONE.md)

| Gate | Description | Check Command | Status |
|---|---|---|---|
| **V88** | Deterministic Simulator Unit Tests | `python3 -m unittest tests.test_simulator` | **PASSED** (16/16 tests in 0.021s) |
| **V89** | Aggregator Simulation Integration | `python3 -m unittest tests.test_aggregator.TestAggregator.test_workload_simulation_integration` | **PASSED** (1 test in 0.033s) |
| **V90** | Interactive Simulator DOM Elements | Python DOM assertion script | **PASSED** (All 12 DOM anchors verified) |
| **V91** | Exporter Determinism & Dry-Run | `python3 scripts/export_dashboard.py --dry-run` | **PASSED** (Clean dry-run reporting presets) |
| **V92** | Decoupled Payload Verification | `python3 -c "...assert 'simulator_presets' in d..."` | **PASSED** (Decoupled payload hook intact) |
| **V93** | Full Test Suite Integrity | `python3 -m unittest discover -s tests` | **PASSED** (105/105 tests in 1.296s) |
| **V94** | Working Tree Cleanliness | `git status --porcelain` | **PASSED** (100% clean tree) |

---

## 4. Key Takeaways & Operational Guidelines

1. **Zero External API Dependencies**: The simulator is completely deterministic and offline, running in standard Python and native browser JavaScript without telemetry exfiltration.
2. **Hard Claude vs. Soft Gemini Invariant**: Exceeding quota on Claude cannot be resolved with credits; it immediately hard-blocks. The simulator guides developers toward Gemini or Enterprise upgrades when planning high-reasoning workloads.
