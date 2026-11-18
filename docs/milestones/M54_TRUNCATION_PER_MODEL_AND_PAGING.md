# M54 · Truncation per Model & Paged Sessions · 2026-09-20 · v2.12.0

## Why
Previous telemetry treated peak prompt depth >= 200k as critical truncation across all models, generating permanent false red alarms for 1M-context Gemini sessions. Sessions tab was dominated by the truncation audit above the fold. This milestone calibrates truncation thresholds per model family, demotes the header badge to amber-on-hover, pages the Sessions table (25 rows), and collapses the audit widget.

## What changed
- `antigravity_telemetry/models.json`: Added context_truncation_tokens (1M Gemini, 200k Claude/GPT).
- `antigravity_telemetry/__init__.py`: Added get_model_truncation_threshold and evaluate_truncation_severity.
- `scripts/export_dashboard.py`: Evaluated severity using model threshold and 80% boundary.
- `dashboard/js/sessions.js`: Per-model threshold resolution, table pagination (25/page), demoted header badge.
- `dashboard/index.html`: Reordered Sessions view (Conversations first, audit collapsed).
- `dashboard/styles.css`: Sticky table header, amber-hover badge, pagination controls styling.
- `tests/test_truncation_thresholds.py`: Unit test for per-model thresholds and 244k tokens scenario.
- `e2e/truncation-and-paging.spec.js`: Playwright interaction specs for paging and header badge.

## Decisions taken
- ADR-068: Per-model context truncation thresholds in models.json with 200k fallback for unknown IDs, demoted amber-on-hover header badge, and paged Sessions explorer table.

## Gates & proofs
- B1 Truncation unit test: OK (7/7 tests passed in 0.005s)
- B2 Model roster integrity: OK (7/7 tests passed in 0.037s)
- B3 Truncation & paging spec: OK (5/5 passed in 15.3s)
- B4 Header red badge demoted: OK (1 passed in 2.3s)
- B5 Sessions paged <= 25: OK (1 passed in 2.4s)
- B6 First h2 is Conversations: OK (1 passed in 2.5s)
- B7 Paging interaction spec: OK (1 passed in 3.5s)
- B8 Layout regressions spec: OK (2 passed in 4.5s)

## Ops check
[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 57220) | verified: 2026-09-20T14:25:51+01:00

## Screenshots
- `docs/milestones/screenshots/m54-desktop-conversations-page1.png`
- `docs/milestones/screenshots/m54-desktop-conversations-page2.png`
- `docs/milestones/screenshots/m54-desktop-accordion-expanded.png`
- `docs/milestones/screenshots/m54-mobile-conversations-page1.png`

## Closing report
Merged:   M54 · v2.12.0 · Truncation per Model & Paged Sessions
Open now: Row 9 (C5): Minified data.js, lazy-loaded turns.js per session (`perf/lazy-turns`) [P1]
Next slice will touch: scripts/export_dashboard.py, dashboard/js/
Needs owner: nothing
Freeze:   lifted
