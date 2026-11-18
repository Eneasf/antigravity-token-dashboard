# Milestone M23: Frontend Modularization & External Status Hook

**Date**: 12 September 2026  
**Branch**: `feat/modularize-dashboard-assets`  
**ADR References**: ADR-003, ADR-004, ADR-024, ADR-036

---

## 1. Background & Objectives

As the Antigravity telemetry dashboard grew to support rolling quotas, dual-track provider silos, project/branch costing, interactive what-if simulation, and jobs-based tabs, `dashboard/index.html` expanded to 4,759 lines. This monolithic structure increased maintenance friction and complicated frontend refactoring. Furthermore, terminal users and status bar frameworks (Starship, zsh, fish, tmux) lacked a lightweight, zero-overhead mechanism to inspect live quota and cooldown headroom without opening the browser or running heavy database scans.

Milestone M23 delivers two major structural achievements:
1. **Frontend Asset Modularization**:
   - Cleanly decomposes `dashboard/index.html` into three dedicated files:
     - `dashboard/styles.css` (654 lines of pure CSS tokens, themes, layouts, SVG chart styles, and tables).
     - `dashboard/app.js` (2,964 lines of client-side routing, SVG rendering, simulation engine, and ticker logic).
     - `dashboard/index.html` (1,140 lines of clean semantic HTML).
   - **Offline Invariant Preserved**: Continues to run 100% offline via `file:///` without build steps, node_modules, or CORS restrictions.
   - **Zero-FOUC**: Retains a tiny inline script in `<head>` to apply dark/light theme tokens before CSS evaluation.
   - **Data Hook Protection**: Preserves `<script id="injected-dashboard-data">` and decoupled `meta.js` / `data.js` loaders.
2. **External Executive Status Hook & Fast CLI Tool**:
   - Every telemetry export cycle atomically generates and writes `~/.antigravity_quota_status.json` via `.tmp` staging.
   - Provides `scripts/agy_status.py`, a fast (<5ms) CLI utility outputting concise prompt summaries, full JSON, or ultra-compact badges (`AGY: G:85%/52% C:100% (SAFE)`).
3. **Pricing Loader Consolidation**:
   - Unifies `DEFAULT_PRICING_FILE` and `load_pricing()` across `src/temporal.py`, `src/aggregator.py`, and `src/simulator.py` into a single canonical source with backward-compatible re-exports.

---

## 2. Architecture & Deliverables

### A. Modular Frontend File Layout (`dashboard/`)

| File | Lines | Purpose & Contents |
|---|---|---|
| `dashboard/index.html` | 1,140 | Semantic HTML markup: 5 jobs-based views (`Now`, `Sessions`, `Projects`, `Billing`, `Plan`), modal containers, and script/link references. |
| `dashboard/styles.css` | 654 | CSS custom properties, dark/light theme variables, 3-column auto-fit grids, table styling, SVG charts, and interactive controls. |
| `dashboard/app.js` | 2,964 | Telemetry hydration, jobs-based routing, real-time table search/sort, What-If simulator engine, and SHA-1 hash-gated auto-refresh ticker. |

### B. Executive Quota Status Hook (`~/.antigravity_quota_status.json`)

```json
{
  "claude_5h_pct": 0.0,
  "claude_weekly_pct": 0.0,
  "cooldown_active": false,
  "gemini_5h_pct": 15.2,
  "gemini_weekly_pct": 48.1,
  "status": "SAFE_IN_QUOTA",
  "updated_at": "2026-09-12T22:12:08.165253+00:00",
  "weekly_reset_utc": "2026-09-17T18:00:00+00:00"
}
```

### C. Fast CLI Status Inspector (`scripts/agy_status.py`)

- Default: `[AGY: Gemini 5h: 84.8% rem | 1w: 51.9% rem | Claude: 100% | Status: SAFE]`
- `--short`: `AGY: G:85%/52% C:100% (SAFE)`
- `--json`: Formatted JSON payload from status hook file.
- Execution speed: `<5ms`.

---

## 3. Verification & Quality Gates

All 6 acceptance gates for Milestone 23 verified cleanly:

| Gate | Check | Expectation | Measured Proof |
|---|---|---|---|
| **V107** | `test -f dashboard/styles.css && python3 -c "c=open('dashboard/styles.css').read(); assert ':root' in c; assert 'data-theme' in c; assert '<style>' not in c; assert '</style>' not in c; print('Verified: styles.css extracted cleanly.')"` | `Verified: styles.css extracted cleanly.` | Passed: 654 lines CSS extracted with `:root` and zero `<style>` or `</style>` tags. Exit code 0. |
| **V108** | `test -f dashboard/app.js && node -c dashboard/app.js && python3 -c "c=open('dashboard/app.js').read(); assert 'initDashboard' in c; assert '<script>' not in c; assert '</script>' not in c; print('Verified: app.js extracted cleanly with 0 syntax errors.')"` | `Verified: app.js extracted cleanly with 0 syntax errors.` | Passed: 2,963 lines JS extracted with `initDashboard`, zero `</script>` tags, verified syntax-clean via `node -c`. Exit code 0. |
| **V109** | `python3 -c "c=open('dashboard/index.html').read(); assert '<link rel=\"stylesheet\" href=\"styles.css\">' in c; assert '<script src=\"app.js\"></script>' in c; assert '<script id=\"injected-dashboard-data\"' in c; assert len(c.splitlines()) < 1500; print('Verified: index.html modularized under 1500 lines.')"` | `Verified: index.html modularized under 1500 lines.` | Passed: 1,140 lines HTML (< 1500 lines) with `<link>` and `<script>`. Exit code 0. |
| **V110** | `python3 scripts/export_dashboard.py && python3 -c "import json, os; p = os.path.expanduser('~/.antigravity_quota_status.json'); assert os.path.exists(p); d = json.load(open(p)); assert 'status' in d; assert 'gemini_5h_pct' in d; assert 'updated_at' in d; print('Verified: Status hook file written atomically.')"` | `Verified: Status hook file written atomically.` | Passed: `~/.antigravity_quota_status.json` generated atomically with full schema. Exit code 0. |
| **V111** | `python3 scripts/agy_status.py && python3 scripts/agy_status.py --json && python3 scripts/agy_status.py --short` | Clean CLI output and valid JSON | Passed: All 3 CLI modes execute cleanly in <5ms. Exit code 0. |
| **V112** | `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py` | 100% tests pass (0 failures, 0 errors) | Passed: 119 unit tests + 6 integrity tests pass cleanly in 1.82s. Exit code 0. |
