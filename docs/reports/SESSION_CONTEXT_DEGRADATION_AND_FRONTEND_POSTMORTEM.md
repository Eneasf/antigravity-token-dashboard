# Session Context Degradation, DOM Structural Hierarchy & Frontend Post-Mortem

> [!IMPORTANT]
> **Historical Provenance Notice**: This post-mortem documents an empirical incident from 2026-09-19 during Milestone 42/43. It captures early telemetry analysis of context degradation prior to the formal discovery and codification of Protobuf Field 30 compaction dynamics (ADR-068/069), 10-request FIFO prompt queues, and discrete quota reset epochs (ADR-082).

**Document Version:** 1.0.0  
**Date:** 2026-09-19  
**Session ID:** `53cc6f51-d996-4a1d-a41d-2522ec5bc38d`  
**Related ADRs:** ADR-008, ADR-059, ADR-060  

---

## 1. Executive Summary

During frontend enhancements in Milestone 42 and 43, users reported visual layout breakages:
1. The sidebar was unexpectedly collapsed to an icon-only strip with missing text labels.
2. The What-If Simulator archetypes row exhibited an aggressive horizontal scrollbar cutting off cards.
3. Header controls appeared unresponsive.
4. Despite multiple diagnostic passes, the root cause went undetected by the AI agent until an external model diagnosed it immediately.

This post-mortem documents:
- The exact **DOM structural hierarchy bug** that derailed the CSS flexbox engine.
- The **empirical telemetry analysis** of this active session (`53cc6f51...`), revealing extreme context saturation.
- Research into **LLM attention degradation ("Lost in the Middle")** and its impact on agent reasoning.
- Concrete **operational protocols (ADR-060)** to ensure future sessions maintain high diagnostic accuracy.

---

## 2. Root Cause Analysis: The DOM Tag Hierarchy Breakdown

### The Defect
At the bottom of `dashboard/index.html` (lines 1619–1626), an accidental duplication of the drawer markup was introduced:

```html
      <div id="drawer-body" class="drawer-body">
        <!-- Injected dynamic inspection content -->
      </div>
    </aside>
      <div id="drawer-body" class="drawer-body">
        <!-- Injected dynamic inspection content -->
      </div>
    </aside>
```

### The Mechanism of Failure
1. **HTML Loose Error-Correction**: Unlike XML, HTML parsers do not throw fatal exceptions on unmatched or duplicate closing tags. When the browser parser encountered the unexpected second closing `</aside>`, it silently "repaired" the DOM tree by closing the nearest open ancestor element—in this case, `#app-layout-container`.
2. **Flexbox Hijacking**: `#app-layout-container` is the root CSS flexbox container (`display: flex; flex-direction: row;`). Terminating it prematurely popped trailing elements and drawer containers completely outside the grid/flex layout into `<body>`, triggering unexpected overflow calculations, scrollbars, and broken layout constraints.
3. **Headless Test Masking**: Automated Playwright tests queried elements by ID (`#tab-now`, `#desktop-inspector-drawer`) and asserted that the elements existed and were clickable. Because the browser DOM tree still contained the nodes, automated tests passed cleanly even though the visual hierarchy was broken.

### Contributing Frontend Factors
- **Sidebar Default State**: `dashboard/app.js` evaluated `localStorage.getItem("antigravity_sidebar_expanded") === "true"`, defaulting fresh visitors to a collapsed 64px icon rail. It must default to expanded (`!== "false"`).
- **Simulator Horizontal Scrollbar**: `.sim-archetypes-row` used `display: flex; overflow-x: auto; flex-shrink: 0;` which required >1320px width, forcing horizontal scrolling on standard viewports. Replacing this with `display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));` wraps cards cleanly.
- **Browser Asset Caching**: `index.html` loaded `styles.css` and `app.js` without version query parameters, causing browsers to serve stale cached stylesheets on standard reload.

---

## 3. Empirical Session Telemetry (Database Audit)

A direct, read-only audit of `~/.gemini/antigravity/conversations/53cc6f51-d996-4a1d-a41d-2522ec5bc38d.db` produced the following measured footprint:

| Metric | Measured Value | Benchmark / Normal Session | Impact |
| :--- | :--- | :--- | :--- |
| **SQLite DB Size** | **45.15 MB** (`+ 3.93 MB` WAL = **49.08 MB**) | 1.0 – 3.0 MB | **16x larger** than normal |
| **Step Records** | **2,126 steps** | 40 – 80 steps | **26x more** steps |
| **Model Generations** | **1,049 turns** | 20 – 40 turns | **26x more** generations |
| **Peak Prompt Depth** | **269,704 tokens** | 25,000 – 45,000 tokens | Triggered emergency truncation |
| **Current Prompt Depth** | **101,617 tokens** | < 30,000 tokens | Operating on lossy `<CONTEXT_SUMMARY>` |
| **Cumulative Prompt Tokens** | **142,736,356 tokens** | 1.0M – 3.0M tokens | **142.7 Million** tokens processed |
| **Cumulative Cached Tokens** | **128,821,493 tokens** | 0.8M – 2.5M tokens | 90.2% cache hit ratio |
| **Cumulative Output Tokens** | **645,746 tokens** | 20k – 50k tokens | Candidate text volume |
| **Cumulative Thinking Tokens** | **311,048 tokens** | 10k – 30k tokens | Reasoning chains |
| **Total Session Lifetime Volume** | **143,382,102 tokens** | 1.5M – 3.5M tokens | Extreme session duration |

---

## 4. LLM Attention Degradation Research ("Context Rot")

Modern frontier models (Gemini 3.1 Pro, Gemini 3.8 Flash) possess large context limits (1M+ tokens), but research into transformer attention distribution demonstrates severe performance degradation as context expands:

### Attention Distribution Dynamics
1. **Attention Budget Dilution**: A transformer's softmax attention weights across sequence length $N$ must sum to 1. As $N$ expands toward $10^5$ or $10^6$ tokens, the attention weight allocated to each individual token diminishes proportionally, creating signal-to-noise ratio degradation.
2. **Primacy & Recency Bias ("Lost in the Middle")**: Models demonstrate sharp U-shaped recall curves, attending strongly to the system prompt (beginning) and immediate user input (end), while details buried in the intermediate 50k–200k tokens (such as file structures or stray markup) suffer up to a **60% drop in retrieval fidelity**.
3. **Tunnel Vision & Over-Abstraction**: Under extreme context load, reasoning models struggle to isolate small, concrete syntax errors (like an extra `</aside>` tag) and instead hallucinate complex structural failures, generating elaborate CSS or JavaScript workarounds that fail to resolve the underlying issue.
4. **Emergency Context Truncation**: When Antigravity reaches ~200k–250k prompt tokens, it runs a lossy summarizer and compresses conversation history into `<CONTEXT_SUMMARY>`. Once this occurs, earlier file views and tool outputs are permanently lost to the agent.

---

## 5. Architectural Decision Record: ADR-060

### Context Boundary Hardening, DOM Structural Linting & Agent Session Hygiene

#### Context
Long-running agentic sessions that span multiple features, refactorings, and test harness creations inevitably accumulate tens of megabytes of tool outputs. This context bloat directly impairs the model's diagnostic capabilities, causing simple structural bugs to be overlooked.

#### Decisions & Policies
1. **Hard 25-Turn Session Ceiling (Rule of 25)**:
   - AI agents must track turn count. Upon reaching 25 interactive turns or completing any major feature milestone, the agent must proactively call a session boundary and instruct the user to start a fresh thread via `@Conversation`.
2. **Mandatory Step 0 DOM Structural Linting**:
   - Before attempting any visual CSS or JavaScript debugging on layout defects, the agent must execute a structural DOM lint check (e.g., verifying balanced open/close tags across all HTML files). Never jump straight to CSS properties.
3. **Subagent Quarantine for High-Volume Tools**:
   - High-output operations (large test suites, Playwright runs, extensive repository greps) must be delegated to subagents (`invoke_subagent`). This prevents hundreds of kilobytes of ephemeral test output from bloating the parent agent's context window.
4. **`<CONTEXT_SUMMARY>` as a Hard Stop**:
   - The injection of `<CONTEXT_SUMMARY>` is an unambiguous system signal that the conversation history has been truncated. When this occurs, agents must immediately conclude active changes and recommend a fresh conversation.

---

## 6. Open Work & Next Session Action Plan

For the incoming fresh conversation:
1. **Apply HTML Fix**: Remove lines 1623–1626 in `dashboard/index.html` (the duplicate `drawer-body` and closing `</aside>`).
2. **Default Sidebar to Expanded**:
   - Set `class="app-layout shell-mode-side sidebar-expanded"` in `dashboard/index.html` and `dashboard/demo.html`.
   - Update `dashboard/app.js` to evaluate `localStorage.getItem("antigravity_sidebar_expanded") !== "false"`.
3. **Responsive Archetype Grid**:
   - Replace `.sim-archetypes-row` flexbox and `overflow-x: auto` with responsive CSS grid.
4. **Cache Busting**:
   - Add `?v=1.43.1` query strings to `styles.css` and `app.js` tags in `index.html` and `demo.html`.
5. **Verification**:
   - Run HTML tree validation.
   - Run `npx playwright test`.
   - Run Python test suite (`python3 -m unittest discover -s tests`).
   - Run live export outside sandbox (`python3 scripts/export_dashboard.py`).
