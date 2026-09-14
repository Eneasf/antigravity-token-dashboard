# Milestone 36: Live Interactive Showcase & GitHub Pages Deployment

**Milestone Slice Record**  
**Designation**: `M36` / `v2.2.0`  
**Date**: September 2026  
**Status**: Completed  
**Branch**: `feat/github-pages-showcase`  
**Associated ADR**: ADR-050  

---

## 1. Context & Motivation

To demonstrate the full telemetry, analytics, and visualization capabilities of the Antigravity token consumption dashboard without requiring prospective users to clone the repository or configure local databases, an interactive public showcase was requested.

Key requirements and architectural constraints:
1. **Focus on Real System Dynamics**: Showcase focus centers on **Projects & Git Branches**, **Turn-by-Turn Thinking Tokens**, **Subagent Swarms**, and **Tool Intelligence**, rather than speculative plan simulation.
2. **Zero PII & Data Privacy (ADR-001 / ADR-049)**: Never deploy or export personal local SQLite databases (`~/.gemini/antigravity`) to public hosting. The public demo data must be 100% synthetic, realistic, and verified by sanitization gates.
3. **Byte-Deterministic Demo Generation (ADR-004 / ADR-050)**: The generator must produce byte-identical JSON/JS artifacts given identical seeds, with zero wall-clock jitter.
4. **Automated Continuous Deployment**: GitHub Actions workflow deploying to GitHub Pages on pushes to `main`, guarded by pre-flight sanitization and schema compliance tests.
5. **Local Verification Gate**: The entire pipeline and UI must be fully verifiable locally before pushing or publishing.

---

## 2. Deliverables & Architectural Changes

### 2.1 Deterministic Synthetic Demo Generator (`scripts/build_demo_showcase.py`)
- Engineered a standalone CLI script producing a full-fidelity `dashboard/data.js` and `dashboard/meta.js`.
- Generates 4 representative modern engineering projects with active Git branches:
  - `agentic-code-reviewer` (`feat/ast-tree-sitter`, `main`)
  - `distributed-kv-cache` (`feat/consistent-hashing`, `perf/zero-copy`)
  - `realtime-telemetry-api` (`feat/websocket-multiplex`, `fix/backpressure`)
  - `cloud-infrastructure-bot` (`feat/terraform-drift-detector`)
- Synthesizes 25 multi-model sessions across canonical calibrated models (`1318`, `1035`, `1026`, `1016`, `1050`, `342`).
- Models turn-by-turn thinking tokens (reasoning effort breakdown: Thinking vs. Answer output tokens).
- Synthesizes 3-tier subagent swarm hierarchy DAG (Tier 1 Mechanical, Tier 2 Engineering, Tier 3 Architecture) with realistic parent-child relationships and avoided API spend calculations.
- Aggregates tool intelligence across 18 tool categories with sandbox bypass statistics, error rates, and skill attribution.
- Guaranteed 100% zero PII: all synthetic conversation IDs follow the format `00000000-0000-0000-0001-0000000000XX`, and project paths use standard POSIX conventions (`/workspace/...`).

### 2.2 Frontend Demo Mode Presentation
- **`dashboard/index.html`**: Added accessible `#demo-mode-banner` containing a highlighted Demo Mode pill, descriptive copy explaining that the data is synthetic, and a direct link to the GitHub repository.
- **`dashboard/styles.css`**: Added responsive styling for `.demo-banner`, `.demo-pill`, `.demo-text`, and `.demo-github-link`, supporting both Light and Dark modes.
- **`dashboard/app.js`**: In `initDashboard()`, detect demo mode automatically if `summary.is_demo === true` or if the document hostname contains `github.io`. Unhides the banner seamlessly on launch.

### 2.3 Continuous Deployment Pipeline (`.github/workflows/deploy_pages.yml`)
- Automates GitHub Pages deployment upon push to `main` when dashboard or demo scripts change.
- Runs only on the public repository (`if: github.repository == 'Eneasf/antigravity-token-dashboard'`), so pushes to the private development remote never attempt a Pages deploy.
- Link-preview metadata (Open Graph / Twitter card) and a 1200x630 `dashboard/og-card.png` so shared links show a title, description and image.
- Enforces pre-flight quality gates before deployment:
  - `python3 -m unittest tests/test_sanitization.py`
  - `python3 -m unittest tests/test_demo_showcase.py`
- Generates fresh `dashboard/data.js` and `dashboard/meta.js` during CI build and uploads the `dashboard/` directory using `actions/upload-pages-artifact@v3` and `actions/deploy-pages@v4`.

### 2.4 Test Suite (`tests/test_demo_showcase.py`)
- 10 automated test gates:
  1. `test_generate_synthetic_payload_schema`: Validates schema keys and payload structure.
  2. `test_is_demo_flag_present`: Validates `is_demo: True` in summary.
  3. `test_projects_and_branches_completeness`: Validates $\ge 4$ projects and realistic branch counts.
  4. `test_turn_inspector_fields`: Validates thinking tokens and reasoning breakdown.
  5. `test_swarms_hierarchy_dag`: Validates subagent swarms and multi-tier DAG nodes.
  6. `test_tool_analytics_data`: Validates tool categories, call counts, and sandbox bypass detection.
  7. `test_weekly_trends_and_billing`: Validates 12 historical weekly cycles, BVI trendlines, and reconciled credit activity.
  8. `test_quota_silos_and_model_matrix`: Validates dual-track provider quota silos, runway governor, and 5h/1w model allowance matrices.
  9. `test_byte_deterministic_file_writing`: Validates bit-for-bit identical output across consecutive runs.
  10. `test_zero_pii_in_generated_payload`: Validates zero local paths, real user directories, or private conversation UUIDs.

---

## 3. Acceptance Verification Proofs

| Gate | Check Command | Measured Result | Status |
|---|---|---|---|
| **V189** | `python3 scripts/build_demo_showcase.py --out /tmp/demo_test.js` | Schema valid, 4 projects, 25 sessions | **PASSED** |
| **V190** | `python3 -m unittest tests/test_demo_showcase.py` | 10/10 tests pass (0.036s) | **PASSED** |
| **V191** | `cmp /tmp/demo1.js /tmp/demo2.js` | Files are identical (exit code 0) | **PASSED** |
| **V192** | Browser / DOM inspection of `#demo-mode-banner` | Banner renders with demo pill and repo link | **PASSED** |
| **V193** | Lint check of `.github/workflows/deploy_pages.yml` | Workflow YAML syntax valid | **PASSED** |
| **V194** | `python3 -m unittest discover -s tests` | 200 tests pass cleanly | **PASSED** |

---

*Milestone certified by Antigravity Governance Engine.*
