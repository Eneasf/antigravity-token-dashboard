# M55 · Minified data.js, Lazy Turns & Truncation Marker · 2026-09-20 · v2.13.0
## Why
Payload data.js grew to 24 MB causing parsing latency on first paint. We minify data.js and decouple session turns into on-demand turns.js. We also fold in ground truth context truncation marker detection (<CONTEXT_SUMMARY>). See ADR-069.

## What changed
- scripts/export_dashboard.py: Minified data.js, decoupled turns to turns.js, scanned <CONTEXT_SUMMARY> markers.
- scripts/build_demo_showcase.py: Added turns.demo.js generation and minified data.demo.js.
- src/aggregator.py: Added peak_prompt_depth and default truncation fields to conversation summaries.
- src/vault.py: Added read-only queries to extract <CONTEXT_SUMMARY> markers and pre-marker depths from steps_archive.
- dashboard/index.html: Registered js/sessions-turns.js script.
- dashboard/js/sessions.js: Split turns drawer/table logic out, reducing file from 934 to 774 lines.
- dashboard/js/sessions-turns.js: New modular script handling lazy-loading turns.js and rendering turn trajectories.
- tests/test_lazy_turns.py: Unit and determinism tests for minified data.js, turns.js, and truncation markers.
- tests/test_export_dashboard.py: Updated assertions for minified JSON format without whitespace.
- e2e/lazy-turns.spec.js: Playwright interaction tests for drawer and lazy turns loading.
- docs/SYSTEM_DESIGN.md, docs/TELEMETRY_SPEC.md, docs/REPO_MAP.md: Architectural, schema, and repo map docs.

## Decisions taken
- ADR-069: Minify data.js (<1 MB) decoupling turns to turns.js on-demand; record <CONTEXT_SUMMARY> has_truncated markers.

## Gates & proofs
- B1 Data.js size: PASS (660,475 bytes < 3 MB)
- B2 Truncation marker: PASS (12/12 conversations in vault match data.json has_truncated)
- B3 Truncation fields: PASS (all truncated conversations have valid step and depth)
- B4 Lazy turns file: PASS (window.__TELEMETRY_TURNS__ populated with 220 sessions)
- B5 Lazy turns test: PASS (Ran 6 tests in 2.402s | OK)
- B6 Turns interaction: PASS (npx playwright test e2e/lazy-turns.spec.js 2 passed in 16.7s)
- B7 Determinism diff: PASS (data.js and turns.js byte-identical across export runs)

## Ops check
[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 40052) | verified: 2026-09-20T15:10:22+01:00

## Screenshots
- Desktop before/after: docs/milestones/screenshots/m55-desktop-before-1440x900.png, docs/milestones/screenshots/m55-desktop-inspector-1440x900.png
- Mobile before/after: docs/milestones/screenshots/m55-mobile-before-375x812.png, docs/milestones/screenshots/m55-mobile-inspector-375x812.png

## Verifier report
PASS: 100% of acceptance gates and verification checks passed cleanly.

## Closing report
Merged:   M55 · v2.13.0 · Minified data.js, Lazy Turns & Truncation Marker
Open now: - **Row 10 (C6)**: PRAGMA integrity check, remove stray .bak file, vault size in meta.json (`chore/vault-bak-removal`) [P1]
Next slice will touch: data/antigravity_vault.db, scripts/export_dashboard.py, src/vault.py, docs/SYSTEM_DESIGN.md
Needs owner: nothing
Freeze:   in effect until rows 1–5 merge
