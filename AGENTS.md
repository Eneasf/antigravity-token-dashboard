# Agent Guidelines & Repository Protocols

This repository houses the deterministic analytics engine, live telemetry watcher, and dashboard for monitoring **Antigravity Token Consumption, Context Caching, and API Cost Benchmarking** across Google Antigravity workspaces.

> **Size budget:** Keep this file focused and under **~150 lines / ~4k tokens**. When a new rule would push past that, incident details move to the ADR log (`docs/HANDOVER.md` §2) with a one-line pointer here.

---

## 1. Git Workflow & Hygiene Standards

All AI agents working on this codebase must strictly observe the following git lifecycle rules:

1. **Active Branch Transparency**:
   - Always state the currently active branch in conversation updates (e.g. `Active Branch: <branch-name>`).
2. **Branch Creation & Scoping**:
   - Proactively propose a dedicated feature branch (`feat/<feature-name>`) before writing code for significant architectural changes, new subsystems, schema migrations, or multi-file refactoring.
3. **Commit Cadence & Cleanliness**:
   - Create focused, atomic commits using the Conventional Commits format (`feat(...)`, `fix(...)`, `docs(...)`, `style(...)`, `refactor(...)`, `test(...)`, `chore(...)`).
   - Keep the working tree 100% clean (`git status`) at every commit and merge point. Never leave untracked scratch files, temporary logs, or unignored editor artifacts.
   - Maintain `.gitignore` to prevent derived database files, temporary test caches, and OS artifacts from entering git history.
4. **Byte-Deterministic Generated Artifacts (ADR-004)**:
   - Any script that writes or updates tracked files (such as `scripts/export_dashboard.py`) must produce byte-identical output given identical inputs. No wall-clock timestamps or unordered dictionary keys that trigger content-free git diffs.
5. **Review & Merge Protocol**:
   - Explicitly notify the user when a logical milestone is complete and ready to commit or merge into `main`.
   - Verify all unit tests and quality gates pass cleanly (`python3 -m unittest discover -s tests`) before proposing a merge.
6. **Remote Origin Parity & Milestone Tagging**:
   - Maintain 100% parity between local `main` and `origin/main`. After merging a milestone into `main`, immediately push to remote:
     ```bash
     git push origin main
     ```
   - Proactively tag completed milestones with semantic version tags (`git tag v1.<M>.0 && git push origin v1.<M>.0`) to establish immutable historical release bookmarks on GitHub.
7. **Identity Integrity & Zero Credential Fabrication**:
   - Never fabricate, guess, or inject synthetic user identities (e.g. `-c user.name=...`, `-c user.email=...`). When sandboxed git commands fail on `~/.gitconfig`, run with `BypassSandbox: true` to respect the authentic user identity or local `.git/config`.
8. **Dual-Remote Isolation & Explicit Public Release Protocol**:
   - **`origin`**: Private development remote. All continuous commits, merges, and milestone tags push here.
   - **`public`** (`Eneasf/antigravity-token-dashboard`): Public showcase remote. **NEVER automatically push to `public`.** Pushes to the public repository are strictly initiated via `scripts/publish_to_public.py` upon explicit, unambiguous instruction from the user.

---

## 2. Upstream Telemetry Safety & Invariants

1. **Strict Read-Only Access to Antigravity DBs (ADR-001)**:
   - Antigravity runtime databases located in `~/.gemini/antigravity/conversations/*.db` are actively read and written by the Electron app and Language Server.
   - **Never open these databases for writing.** Always connect using URI read-only mode:
     ```python
     sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
     ```
   - Respect SQLite Write-Ahead Logging (`*.db-wal` and `*.db-shm`). Queries must be non-blocking and tolerant of live concurrent transactions.
2. **Zero External API Dependencies (Deterministic & Offline)**:
   - All token analytics, prompt lengths, cached tokens, and candidate output counts derive entirely from the locally stored runtime protobuf telemetry. Zero external network calls required.
3. **Event Sourcing & Projection Invariant**:
   - The upstream SQLite stores (`~/.gemini/antigravity/conversations/`) and workspace summaries (`agyhub_summaries_proto.pb`) are the **sole systems of record**. Any local cache or aggregator is strictly a disposable read projection that can be 100% regenerated from scratch at any time.
4. **Canonical Model Roster & Reasoning Invariant (Gate V136)**:
   - All model IDs, names, families, and reasoning effort levels must adhere strictly to the ground-truth roster defined in `antigravity_telemetry/models.json` (19 calibrated models).
   - Never invent, extrapolate, or normalize internal Antigravity model names to generic public marketing names (e.g. `1035` is `Claude Sonnet 4.6 (Thinking)`, `1026` is `Claude Opus 4.6 (Thinking)`, `342` is `GPT-OSS 120B (Medium)`).
   - Any modification touching model taxonomy must pass `python3 -m unittest tests/test_model_roster_integrity.py`.

---

## 3. Plan Slices, Verifiable Gates & Handover Integrity

1. **Verifiable Quality Gates (`VDONE.md`)**:
   - "Done if proven, not if declared." Before executing non-trivial work, write acceptance gates in `VDONE.md`.
   - Each gate requires an executable `CHECK` command and a measured `EXPECT` output. Run all gates before declaring work complete.
2. **Milestone Slice Documents (`docs/milestones/`)**:
   - The durable history of completed work lives in `docs/milestones/` slice documents (test commands, schema versions, verification proofs). Ephemeral planning files must not clutter root.
3. **Master Handover Hub (`docs/HANDOVER.md`)**:
   - **ADR Table (§2)**: Every settled data contract, model mapping, or quota rule is formally logged.
   - **Milestone Index (§3)**: Tracks completed and active milestones with verified test commands.
   - **Open Work Register (§4)**: Explicitly logs known, deliberately deferred work with evidence, required changes, and verification criteria.
4. **Specification & README Attainment (Enforced by `tests/test_docs_integrity.py`)**:
   - Changes to behavior, CLI flags, or formulas must update `docs/SYSTEM_DESIGN.md`, `docs/TELEMETRY_SPEC.md`, and `README.md` concurrently.
   - All milestones must pass `python3 -m unittest tests.test_docs_integrity` ensuring all `src/` modules, scripts, milestones, and ADR citations are documented in `README.md`.
5. **Offline HTML Data Hook Protection**:
   - Never remove or break `<script id="injected-dashboard-data" type="application/json">` in `dashboard/index.html`.
6. **Live Pipeline & Daemon Operational Standard (ADR-047)**:
   - When a milestone touches telemetry ingestion, formulas, models, or UI presentation:
     a. Run live export (`python3 scripts/export_dashboard.py`) outside the sandbox to refresh `dashboard/data.js` against authentic databases (never stop at `--dry-run`).
     b. Restart the LaunchAgent daemon (`python3 scripts/setup_service.py restart`) and verify `RUNNING / REGISTERED` in `setup_service.py status`.
     c. `VDONE.md` must include a dedicated Live Operational Gate checking both `dashboard/data.js` freshness and daemon service status before declaring completion.


---

## 4. Subagent Delegation & Model Allocation (ADR-007)

1. **Parallelism & Disjoint Scopes**:
   - Parallel specialist subagents are authorized for disjoint tasks.
   - **Zero Collision Invariant**: Parallel subagents must never write to overlapping source files or test fixtures concurrently.
2. **3-Tier Model Allocation Standard**:
   - **Tier 1 (Mechanical Execution)**: `Model: "flash_lite"`. Zero-ambiguity tasks: regex log filtering, JSON formatting, deterministic unit test runs. *1-Strike Failsafe*: Escalate to Tier 2 on any error.
   - **Tier 2 (Standard Engineering)**: `Model: "flash"`. Standard code authoring, SQLite queries, parser updates, scripts.
   - **Tier 3 (Complex Architecture & UI)**: `Model: "inherit"` or `"pro"`. Multi-window rolling quota math, responsive SVG/HTML chart design, system design.
3. **Mandatory Pre-Flight Disclosure**:
   - Subagent invocations must be preceded by visible chat disclosure: Agent Role, Model Parameter, Disjoint Scope, and Task Rationale. No silent spawning.
4. **Mandatory Planning Topology Section**:
   - Every `implementation_plan.md` must include an `## Agent Topology & Delegation Strategy` section.

---

## 5. Proactive Context Boundary & Milestone Handover (ADR-008)

1. **Context Boundary Calling**:
   - Monitor session context length. When a logical milestone is completed and committed with a 100% clean tree, **never embark on a major new multi-file milestone in the same thread**.
2. **Fresh Session Handoff**:
   - Finalize the milestone slice in `docs/milestones/`, update `docs/HANDOVER.md`, prepare the next milestone's plan, and proactively instruct the user to start a fresh conversation using `@Conversation` context mention.
