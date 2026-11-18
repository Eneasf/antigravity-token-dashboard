# Milestone 42: Production Design System Rollout & UI Unification

**Milestone Slice Record**  
**Designation**: `M42` / `v1.42.0`  
**Date**: September 2026  
**Status**: Completed  
**Branch**: `feat/m42-design-system-alignment`  
**Associated ADR**: ADR-056  

---

## 1. Context & Motivation

With the creation of the canonical **Eneas Design System** (grounded in `~/.gemini/config/skills/design-standards/SKILL.md` and Health OS Milestone 30), this milestone aligns the entire Antigravity Token Consumption, Context Caching & Quota Dashboard to eliminate generic AI defaults (*Tailwind/shadcn fatigue*, generic blue/purple gradients, bubbly `rounded-2xl` corners, and Lucide icon soup) in favor of a cohesive, bespoke editorial engineering aesthetic:
1. **Warm Editorial Palette**: Dark mode anchored in Smoked Obsidian (`#0A0C0E`), Light mode anchored in Warm Parchment (`#FBFBFA`), with Smoked Espresso (`#42352C`), Camel (`#D4A373`), Emerald Mint (`#10B981`), and Acute Rose (`#F43F5E`).
2. **Typography Standard**: `Schibsted Grotesk` (Display & Body) paired with `Geist Mono` (Data, Code, & Tables), strictly enforcing `font-feature-settings: 'tnum' 1` across all numbers and timers.
3. **Dual App Shell Navigation**: Pattern A Collapsible Sidebar Dock (`64px` icon dock / `240px` expanded with Phosphor SVG icons) alongside Pattern B Top Command Strip fallback, controlled via persistent `localStorage` preference switcher (`user_shell_preference`), and mobile bottom dock (<768px with 48px tap targets).
4. **Slide-Over Inspector Drawer**: 440px slide-over inspector drawer (`#desktop-inspector-drawer`) with backdrop blur replacing in-page `#turns-card` layout jumping.
5. **Procedural SVG Visualizations**: Smooth Catmull-Rom cubic bezier splines, 1.75px stroke, 18% max gradient fill opacity, right-margin pinned corridor labels (`text-anchor="end"`), and tactile 6px DAG cards.

---

## 2. Technical Decisions & Architectural Implementation

### 2.1 3-Tier CSS Custom Property Dictionary (`dashboard/styles.css`)
- **Tier 1 (Primitives)**: `--color-obsidian-950: #0A0C0E`, `--color-parchment-50: #FBFBFA`, `--color-espresso-900: #42352C`, `--color-camel-500: #D4A373`, `--color-mint-500: #10B981`, `--color-rose-500: #F43F5E`.
- **Tier 2 (Semantic Surfaces & Text)**: Semantic tokens for canvas, cards, subdock, overlay, and text hierarchy (`--text-primary`, `--text-secondary`, `--text-muted`, `--text-accent`).
- **Tier 3 (Components & Borders)**: Hairline tactile borders (`--border-hairline`, `--border-focus`), 6px card radius (`--radius-card: 6px`), tactile active depress physics (`:active scale(0.96) translateY(1px)`), and `@media (prefers-reduced-motion: reduce)` motion accessibility guards.

### 2.2 Google Fonts Embed & Tabular Numerals (`dashboard/index.html`, `dashboard/demo.html`)
- Embedded `Schibsted Grotesk` (weights 400–800) and `Geist Mono` (weights 400–700) via preconnected Google Fonts links.
- Enforced tabular numerals (`font-feature-settings: 'tnum' 1`) across all metric values, quota percentages, countdown clocks, and table cells.

### 2.3 Dual App Shell Architecture & Synchronized Navigation (`dashboard/app.js`)
- **Collapsible Sidebar Dock (`#sidebar-dock`)**: Brand anchor with toggle expansion (`toggleSidebar()`), inline Phosphor SVG icons for all 6 tabs (`Now`, `Sessions`, `Projects`, `Swarms`, `Billing`, `Plan`), and integrated footer controls for currency, theme, and shell layout switcher (`toggleShellMode()`).
- **Shell Mode Persistence**: Persists user choice in `localStorage` under keys `user_shell_preference` and `antigravity_shell_mode`, toggling layout container classes between `shell-mode-side` and `shell-mode-top`.
- **3-Way Navigation Sync**: `switchTab(tabId)` simultaneously synchronizes active classes across top bar buttons (`#tab-*`), sidebar dock items (`#dock-tab-*`), and mobile bottom nav items (`#mob-tab-*`).
- **Theme & Currency Sync**: `updateThemeViews()` and `updateCurrencyViews()` bidirectionally synchronize controls across both the top command strip and sidebar dock.

### 2.4 Slide-Over Inspector Drawer & Universal HTML Tooltip (`dashboard/app.js`)
- **Slide-Over Drawer (`#desktop-inspector-drawer`)**: Implemented `openTurnsDrawer(convo)` and `closeInspectorDrawer()`, sliding in from the right with backdrop blur (`#drawer-backdrop`). Populates conversation KPI strip, model distribution, thinking tokens, and turn trajectory table. Bound to conversation clicks in Recent Sessions and Conversations tables, with keyboard `Escape` dismissal.
- **Universal Floating HTML Tooltip (`#app-micro-tooltip`)**: Implemented `initMicroTooltips()` dynamically bound to `[data-tooltip]` elements with 12px viewport edge-clamping and smooth fade transitions.

### 2.5 Procedural SVG Modernization & Spline Curves (`dashboard/app.js`)
- **Catmull-Rom Spline Engine (`getSplinePath`)**: Converts coordinate points into smooth cubic bezier SVG paths (`C` commands), eliminating sharp linear polyline joints.
- **Weekly Trends SVG (`#weekly-trends-svg`)**: Upgraded to 1.75px cubic spline curves, 18% max gradient fill opacity, Warm Editorial colorways (Camel `#D4A373` for tokens, Mint `#10B981` for cost, Violet `#A855F7` for BVI), single live terminal pulse node, and pinned corridor labels to far right margin (`text-anchor="end"`).
- **Simulation Trajectory SVG (`#sim-trajectory-svg`)**: Upgraded to 1.75px spline curve, Warm Camel gradient fill, Acute Rose (`#F43F5E`) burst boundary, and right-margin pinned labels (`text-anchor="end"`).
- **Multi-Agent Swarm DAG (`.swarm-dag-svg`)**: Styled node cards with 6px tactile radius (`rx="6"`), hairline borders (`stroke-width="1.2"`), tier-matched Warm Editorial colors, and Geist Mono tabular numerals.

---

## 3. Verifiable Quality Gates (`VDONE.md`)

| Gate | Description | Check Command | Status |
|---|---|---|---|
| **V235** | 3-Tier CSS Custom Property Dictionary & Warm Editorial Tokens | `python3 -c "css = open('dashboard/styles.css').read(); assert '--surface-canvas' in css and '--radius-card: 6px' in css"` | **Passed** |
| **V236** | Typography & Google Fonts Embed (`Schibsted Grotesk` + `Geist Mono`) | `python3 -c "html = open('dashboard/index.html').read(); assert 'Schibsted+Grotesk' in html; css = open('dashboard/styles.css').read(); assert "'tnum'" in css"` | **Passed** |
| **V237** | Dual App Shell Architecture & Persistent Shell Preference | `python3 -c "html = open('dashboard/index.html').read(); assert 'sidebar-dock' in html; js = open('dashboard/app.js').read(); assert 'user_shell_preference' in js and 'toggleSidebar' in js"` | **Passed** |
| **V238** | 440px Slide-Over Inspector Drawer & Floating HTML Tooltips | `python3 -c "html = open('dashboard/index.html').read(); assert 'desktop-inspector-drawer' in html; js = open('dashboard/app.js').read(); assert 'openTurnsDrawer' in js and 'closeInspectorDrawer' in js"` | **Passed** |
| **V239** | SVG Chart Modernization & Tactile DAG | `python3 -c "js = open('dashboard/app.js').read(); assert 'weekly-trends-svg' in js and 'sim-trajectory-svg' in js and 'text-anchor="end"' in js"` | **Passed** |
| **V240** | Offline HTML Data Hook Invariant (ADR-004 / ADR-024) | `python3 -c "html = open('dashboard/index.html').read(); assert '<script id="injected-dashboard-data" type="application/json">' in html"` | **Passed** |
| **V241** | Full Regression & Docs Integrity Test Suite | `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py` | **Passed (214 tests)** |
| **V242** | Live Daemon Verification & Process Health (ADR-047) | `python3 scripts/export_dashboard.py && python3 scripts/setup_service.py restart && python3 scripts/setup_service.py status` | **Passed (PID 74352)** |
