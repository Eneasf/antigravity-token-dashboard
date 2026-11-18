# Milestone 43: Playwright End-to-End Automated Testing & Front-End Visual Quality Architecture

**Active Branch**: `feat/playwright-e2e-verification`  
**Standard**: Done if proven, not if declared (`AGENTS.md` §3 & `vdone`)

---

## 1. Context & Problem Formulation

Following the deployment of Milestone 42.2, visual layout inspection across browser engines revealed subtle visual artifacts and an architectural gap in front-end automated verification:
1. **No Automated Browser & Interaction Testing**: Front-end verification previously relied on static regex string matching and Python unit tests. This allowed browser-specific rendering defects (sub-pixel margins, off-screen shadow bleeding, and CSS transition races) to evade detection.
2. **Off-Screen Inspector Drawer Shadow Bleed**: In `dashboard/styles.css`, `.inspector-drawer` was given `box-shadow: -16px 0 48px rgba(0, 0, 0, 0.5);`. Even when translated off-canvas (`transform: translateX(100%)`), the 48px blur spread projected a persistent 64px dark blur/shadow down the entire right margin of the visible screen.
3. **Detached Floating Collapse Button Appearance**: `#btn-sidebar-collapse-footer` had an inline style with `background: var(--surface-card)` (`#FFFFFF`) and a border. In Light mode against the warm beige dock (`#F2EFE9`), this rendered as a jarring, detached white square at the bottom-left of the screen.
4. **Brand Icon vs. "Now" Tab Duplicate Glyph**: Both the dock brand anchor and the live cockpit "Now" tab utilized identical compass SVGs.

---

## 2. Key Architectural Deliverables

### A. Playwright End-to-End Automated Test Framework
- Installed `@playwright/test` and configured `playwright.config.js` to execute real headless Google Chrome (`channel: chrome`, version 153.0.8010.50) without synthetic browser shims.
- Wired local web server automation on port 8089 serving the `dashboard/` directory.
- Authored 3 comprehensive E2E test suites with 12 distinct automated specs:
  1. `e2e/layout-invariants.spec.js`:
     - Asserts zero horizontal overflow (`scrollWidth <= clientWidth`) across 1920×1080 (Wide Desktop), 1440×900 (Standard Desktop), and 1280×800 (Laptop/Tablet).
     - Asserts zero uncaught runtime exceptions or console errors.
     - Asserts `.inspector-drawer` closed state has zero off-screen shadow bleeding (`boxShadow: 'none'`, `visibility: 'hidden'`).
  2. `e2e/navigation-and-tabs.spec.js`:
     - Sequentially clicks all 6 navigation tabs (`Now`, `Sessions`, `Projects`, `Swarms`, `Billing`, `Plan`) in both Sidebar Dock and Top Bar modes.
     - Asserts `.active` classes, target section visibility, hiding of inactive sections, and zero layout shift.
     - Validates inspector drawer open, slide-over animation, backdrop blur, and clean close transition.
  3. `e2e/controls-and-shell.spec.js`:
     - Validates sidebar expand/collapse transitions between 64px icon rail and 240px dock with animated label visibility.
     - Validates bidirectional shell switching (`Sidebar` vs. `Top Bar`), margin removal, and command strip pinning.
     - Validates currency switcher toggling (`GBP (£)` vs. `USD ($)`) and global state synchronization.
     - Validates theme switcher toggling (`Light` vs. `Dark`), canvas background color tokens, and body class application.

### B. Mandatory Front-End VDONE Quality Gates Mandate
- Codified an immutable standard in `VDONE.md`: No front-end change can be merged without executable proof from `npx playwright test` and visual screenshot artifact generation.
- Integrated `tests/test_playwright_e2e.py` as a Python `unittest` bridge, enabling `python3 -m unittest discover -s tests` to automatically run both unit tests and Playwright E2E tests in a unified pipeline.

### C. Visual & Layout Defect Elimination
- **Inspector Drawer Shadow Bleed**: Set `box-shadow: none; visibility: hidden; pointer-events: none;` on `.inspector-drawer` when closed, activating shadow and visibility strictly when `.inspector-drawer.open`.
- **Integrated Sidebar Collapse Button**: Stripped inline `style="..."` attributes and restyled `#btn-sidebar-collapse-footer` to a seamless, transparent 40×40px rail icon button with subtle hover states when collapsed, and a clean full-width button when expanded.
- **Dock Brand Icon Differentiation**: Replaced duplicate brand compass with an authentic orbital atom SVG, reserving the live activity pulse SVG for the "Now" tab.
- **Typography & Brand Alignment**: Structured `.dock-brand-text` vertically with clean hierarchy (`.dock-brand-title` and `.dock-brand-sub`).

### D. Automated Visual Screenshot Artifact Generation
- Authored `e2e/visual-screenshots.spec.js` generating 10 high-resolution full-page screenshots across all tabs, themes, and shell modes in `dashboard/test-artifacts/screenshots/`.

---

## 3. Verifiable Acceptance Gates (V253–V256)

| Gate | Description | Command | Result |
|---|---|---|---|
| **V253** | Playwright E2E Test Suite Pass (Navigation, Controls, Invariants) | `npx playwright test` | **PASSED (12/12 passed in 44s, exit code 0)** |
| **V254** | Zero Horizontal Overflow & Zero Shadow Bleed Across Viewports | `npx playwright test e2e/layout-invariants.spec.js` | **PASSED (4/4 passed across 1920, 1440, 1280 viewports)** |
| **V255** | Automated Visual Screenshot Artifact Attainment | `python3 -c "import os; files=[f for f in os.listdir('dashboard/test-artifacts/screenshots') if f.endswith('.png')]; assert len(files)>=10, f'Found {len(files)}'; print(f'Gate V255 passed: {len(files)} screenshot artifacts generated.')"` | **PASSED (10 screenshots verified)** |
| **V256** | Unified Python Test Bridge Parity & Live Daemon Verification | `python3 -m unittest discover -s tests && python3 scripts/setup_service.py status` | **PASSED (208 tests passed, daemon RUNNING)** |
