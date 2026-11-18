# Milestone 44: Layout Fix & Playwright Upgrades

## Objective
Fix the catastrophic 50/50 flex layout collapse introduced in M42, and fundamentally overhaul the Playwright E2E suite to use true geometric assertions and pixel-perfect visual regression testing so this class of bug is permanently mitigated.

## Technical Execution
- **HTML Layout Fix**: Removed 4 lines of duplicated markup (`</aside>` and `<div id="drawer-body">`) at the bottom of `dashboard/index.html` that prematurely closed the floating inspector drawer and injected a hidden flex-container directly into the `.app-layout-container`, hijacking 50% of the screen space.
- **Geometric Viewport Assertions**: Upgraded `e2e/layout-invariants.spec.js` to assert that `.main-viewport` physically measures `window.innerWidth - 64` via `.boundingBox().width`. Added a strict mobile resize test (375x812) to verify CSS media queries.
- **Visual Regression**: Upgraded `e2e/visual-screenshots.spec.js` to use `expect(page).toHaveScreenshot()` across 10 distinct states, replacing weak filesystem checks with true pixel-by-pixel regression constraints.
- **Behavioral Upgrades**: Upgraded navigation tests to assert the visibility of unique view content rather than CSS classes. Created `e2e/simulator-interactions.spec.js` to assert the What-If Simulator dynamically recalculates mathematical risk when a user inputs a £500 value.

## Agent Topology (ADR-007 Compliance)
- **Coordinator**: Fixed HTML layout synchronously.
- **Subagent 1 (flash)**: Upgraded `layout-invariants.spec.js`
- **Subagent 2 (flash)**: Upgraded `visual-screenshots.spec.js`
- **Subagent 3 (flash)**: Upgraded `navigation-and-tabs.spec.js` & `simulator-interactions.spec.js`

## Verifications Passed
- `npx playwright test` (14 assertions passing against strict baseline snapshots)
- `python3 -m unittest discover -s tests` (208 assertions passing, CI bridge intact)
