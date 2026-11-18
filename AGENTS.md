# Agent Guidelines & Repository Protocols

This repository houses the deterministic analytics engine, live telemetry watcher, and dashboard for monitoring **Antigravity Token Consumption, Context Caching, and API Cost Benchmarking** across Google Antigravity workspaces.

> **Size budget:** Keep this file focused and under **~150 lines / ~4k tokens**. When a new rule would push past that, incident details move to the ADR log (`docs/DECISIONS.md`) with a one-line pointer here.

---

## §1. Repository Execution Contract (Read by ALL Agents)

| Parameter | Value | Description |
| :--- | :--- | :--- |
| **`PROJECT_TYPE`** | `web` | Telemetry analytics engine & static dashboard with Playwright a11y harness |
| **`TEST_CMD`** | `python3 -m unittest discover -s tests` | Offline unit tests & telemetry invariant gates (zero external deps, ADR-001) |
| **`QUALITY_GATE_CMD`**| `git diff --check && python3 -m unittest tests/test_docs_integrity.py && python3 scripts/build_demo_showcase.py && npx playwright test e2e/dashboard-boot.spec.js` | Strict whitespace, doc integrity, and headless dashboard boot gate (Plan 3 A3-1) |
| **`PROTECTED_PATHS`** | `~/.gemini/antigravity/conversations/*.db`, `antigravity_telemetry/models.json`, `docs/DECISIONS.md`, `dashboard/index.html`, `~/.antigravity_quota_status.json`, `~/.antigravity_refresh_requested`, `~/Library/LaunchAgents/com.antigravity.*`, active daemons, `AGENTS.md` | Read-only runtime DBs, canonical model roster, ADR registry, offline data hook, quota status, LaunchAgents, active daemons, contract |
| **`BACKLOG_SOURCE`** | `docs/BACKLOG.md` | Delete-on-close open work register (`GADR-033`) |
| **`VERSION_STRATEGY`**| `semver-git-tag` | Milestone tagging (`git tag v1.<M>.0`) and parity on `main` |

### Core Telemetry Safety & Repository Invariants (Universal)
1. **Strict Read-Only DB Access (ADR-001)**: Antigravity runtime databases (`~/.gemini/antigravity/conversations/*.db`) are actively accessed by the IDE. Connect strictly via URI read-only mode: `sqlite3.connect(f'file:{db}?mode=ro', uri=True)`.
2. **Zero External API Dependencies (ADR-001)**: All metrics derive deterministically from local SQLite DBs and `agyhub_summaries_proto.pb`. Zero external network calls.
3. **Canonical Model Roster (Gate V136)**: Ground-truth roster in `antigravity_telemetry/models.json` (schema v2). Never invent or alias model names.
4. **Dual-Remote Isolation**: Continuous commits push to `origin`. Never push directly to `public` (`Eneasf/antigravity-token-dashboard`); public releases require explicit user instruction via `scripts/publish_to_public.py`.
5. **Zero Credential Fabrication**: Never inject synthetic git authors (`-c user.name=...`). Use authentic system credentials.
6. **Hard-Coded Host Isolation & Path Protection (Rule AC-4)**: Never mutate or delete host quota files, refresh signals, LaunchAgents (`~/Library/LaunchAgents/com.antigravity.*`), active daemon / watcher processes, or dashboard `AGENTS.md`. Strictly forbid running `scripts/ops_check.py` or running `export_dashboard.py` without `--output-dir` in test checkouts; all test suites must redirect exports to scratch folders.
7. **SQLite Concurrency Resilience (GADR-013 / ADR-081)**: Shared telemetry and vault databases must enable WAL mode (`PRAGMA journal_mode=WAL;`), set `sqlite3.connect(..., timeout=60.0)`, configure `PRAGMA busy_timeout = 60000;`, commit read transactions before long traversals, and wrap writes in exponential backoff retry handlers.
8. **Telemetry Semantic Layer & Schema Catalog (ADR-089 / ADR-090)**: Consult `docs/DATA_DICTIONARY.md` for table grains, reference codes, and canonical analytical views (`v_active_sessions`, `v_turns`, `v_hourly_token_velocity`, `v_rate_limit_events`) to prevent full-table disk scans.

---

## §2. Implementer Domain Invariants (Read ONLY by Implementer)

* **Context Hygiene**: The Implementer reads strictly §1 and §2 of this document.
* **Git & Branching Cadence**: State `Active Branch:`. Propose `feat/<name>` for substantial changes. Commits use Conventional Commits. Clean working tree (`git status`) at every commit point.
* **Byte-Deterministic Artifacts (ADR-004)**: Tracking generator scripts (e.g. `scripts/export_dashboard.py`) must produce byte-identical output given identical inputs.
* **Host Isolation & Path Protection (Rule AC-4)**: Strictly forbid running `scripts/ops_check.py` or running `export_dashboard.py` without `--output-dir` in test checkouts; all test suites must redirect exports to scratch folders.
* **Documentation Integrity & Tree Synchronization (Doc Integrity)**: When authoring, renaming, or deleting modules in `src/`, `antigravity_telemetry/`, `scripts/`, or `tests/test_*.py`, immediately register the module path in `docs/REPO_MAP.md` before staging commits, and run `$QUALITY_GATE_CMD` locally before requesting verification.
* **Safe Acceptance Gate Formulation (GADR-014)**: Never embed script imports with dummy comments (`# --dry-run`) to satisfy static linters (`tests/test_vdone_gates.py`). Gating CLI argument parser presence must be done via formal unit tests in `tests/` (e.g. `tests/test_export_dashboard.py`).
* **Verifiable Acceptance Gates (VDONE.md)**: "Done if proven, not if declared." Write executable `CHECK` + `EXPECT` gates in `VDONE.md` before coding. Any UI change requires a headless Playwright `pageerror` gate (ADR-080).
* **Live Pipeline Operational Standard (ADR-047)**: When telemetry ingestion, formulas, or UI change: (1) run live export `python3 scripts/export_dashboard.py`, (2) restart LaunchAgent `python3 scripts/setup_service.py restart`, (3) run `scripts/ops_check.py`.
* **Subagent Delegation (ADR-007 / GADR-031)**: 3-tier model allocation (`flash_lite` mechanical, `flash` standard, `inherit` complex). Zero collision invariant across concurrent subagents. Mandatory pre-flight disclosure.
* **Milestone Closing & Backlog Compaction (ADR-008 / GADR-033)**: Respect context boundaries. Delete completed items from `docs/BACKLOG.md` (zero `[x]` rows) and reset `VDONE.md` `§B` only after `git status --porcelain` is verified clean (GADR-004).

---

## §3. Auditor & Challenger Invariants (Read ONLY by Auditor / Challenger)

* **Context Hygiene**: The Auditor and Challenger read strictly §1 and §3 of this document.
* **UI/Accessibility Inspection (`PROJECT_TYPE == web`)**: Serve `dashboard/index.html` across standard viewports (`1440x900`, `375x812`) and themes (`light`, `dark`). Run axe-core accessibility checks.
* **Zero Mutation & Artifact Quarantine (Principle 11 & GADR-003)**: Scratch files and test artifacts go strictly to git-ignored scratch paths (`test-artifacts/`, `tmp/`), never to tracked documentation directories. Close with `git status --short`.
* **Adversarial Fact-Checking**: Auditor MUST dispatch the read-only Challenger subagent to classify all findings as `EVIDENCED`, `GUESSED`, or `CONTRADICTED` before publishing.
* **Scope Isolation**: Auditor edits only `docs/AUDIT_<date>_<scope>.md` and appends accepted findings to `docs/BACKLOG.md`. Never edit application code.

---

## §4. Verifier Invariants (Read ONLY by Verifier)

* **Context Hygiene**: The Verifier reads strictly §1 and §4 of this document.
* **Zero Mutation (Principle 11)**: Verifier has strictly read-only tools. Re-derive acceptance gates independently.
* **Tree Purity Audit (GADR-005)**: Run `git status --porcelain` immediately before and after running test commands. Any dirtied tree triggers an immediate verification strike.
* **Suite & Quality Proofs**: Run `$TEST_CMD` and `$QUALITY_GATE_CMD`. Enforce GADR-002 `< 90s` duration ceiling. Any single gate failure yields an overall `FAIL`.

---

## §5. Reflector Retrospective Governance (Read ONLY by Reflector)

* **Context Hygiene**: The Reflector reads strictly §1 and §5 of this document.
* **Event-Driven Retrospectives (GADR-006)**: Dispatched after $\ge 3$ audit rows or on verification strikes. Clean single runs skip reflection.
* **Proposal-Only Evolution**: Agent prompts receive only affirmative, forward-looking rules (Pink Elephant Invariant). All changes require explicit owner sign-off.
* **Tri-Scope Routing**: Cross-repo lessons route to `~/.gemini/config/DECISIONS.md` (GADRs), tech stacks to `skills/`, and local invariants to `<repo>/AGENTS.md`.
