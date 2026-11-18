# Milestone 67 Evolution Resolution Receipt

**Originating Proposal**: `evolution_proposal_2026-09-26.md`  
**Milestone Analyzed**: Milestone 67 (`perf/vault-sync-mtime-gating` / Finding C1)  
**Governance Deciders**: Eneas & Antigravity Global Architecture  
**Date**: 2026-09-26  
**Status**: CLOSED LOOP (Decisions Settled & Routed)

---

## 1. What Was Adopted Globally (Ecosystem-Wide)

These changes have been ratified in the global runtime (`~/.gemini/config/`) and local governance incubator (`agentic-work`):

1. **GADR-013: SQLite Concurrency Resilience in Active Daemon Runtimes**
   - *Target*: `~/.gemini/config/DECISIONS.md`
   - *Ratified Standard*: In desktop and telemetry runtimes where background LaunchAgents (`com.antigravity.telemetry.watcher`) and foreground CLI / test suites access shared databases:
     1. Enable WAL mode (`PRAGMA journal_mode=WAL;`) across all connections so readers and writers do not block each other.
     2. Set `sqlite3.connect(..., timeout=60.0)` and execute `PRAGMA busy_timeout = 60000;`.
     3. Commit or close read transactions immediately before executing directory traversals or CPU-heavy operations.
     4. Wrap write operations in exponential backoff retry handlers (catching `sqlite3.OperationalError: database is locked`, min 5 attempts).
2. **Universal Gate Isolation Rule**
   - *Target*: `skills/vdone/SKILL.md` (Quality Rules v2.2.1)
   - *Ratified Standard*: `CHECK` commands must be strictly side-effect free. When inspecting CLI parser flags or module reflection, invoke standard safe introspection flags (`--help`, `--version`) or run dedicated unit tests.

---

## 2. What the Repository Must Adopt (Local Action)

The following changes have been incorporated into this repository:

1. **Local Telemetry Safety Invariant**:
   - *Target*: `AGENTS.md` §1 (Rule 7)
   - *Rule*: Mandates GADR-013 SQLite concurrency patterns (`timeout=60.0`, `busy_timeout=60000`, WAL mode, retry backoffs) for all vault access.
2. **Local Implementer Invariant (Documentation Integrity & Safe Gates)**:
   - *Target*: `AGENTS.md` §2
   - *Rule*: Register any new, renamed, or deleted module in `docs/REPO_MAP.md` immediately before staging commits, and run `$QUALITY_GATE_CMD` locally before requesting verification.
3. **Local Architecture Decision Record**:
   - *Target*: `docs/HANDOVER.md` §2
   - *Entry*: `ADR-081: SQLite Concurrency Resilience & Repo Map Integrity`.

---

## 3. Discarded Suggestions & Rationale (Negative Memory)

To prevent future sessions from re-proposing rejected patterns:

* **Proposal**: Appending inline comment tags (`# --dry-run`) to satisfy static gate linters (`tests/test_vdone_gates.py`).
* **Verdict**: **REJECTED (Anti-Pattern / GADR-014)**.
* **Rationale**: Shell comments are ignored during actual command execution. Using comments to bypass regex linters subverts host isolation rules (Rule AC-4) without offering runtime safety. 
* **Way Forward**: Verify parser configurations via dedicated unit tests in `tests/test_export_dashboard.py` (e.g. `CHECK python3 -m unittest tests.test_export_dashboard.TestCLIParser`) rather than embedding inline reflection scripts in `VDONE.md`.
