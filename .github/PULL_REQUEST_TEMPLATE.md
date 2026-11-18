## Description
<!-- Provide a concise description of the changes made in this PR. -->

## Associated Issue
<!-- Link to the issue this PR closes or addresses, e.g., Closes #12 -->

## Type of Change
- [ ] Model ID Calibration (`config/pricing.json`)
- [ ] Bug Fix (non-breaking fix for parser, watcher, or exporter)
- [ ] Telemetry Parser Refinement
- [ ] Documentation or Milestone Update
- [ ] Test Harness or Tooling Enhancement

## Architectural Invariants & Quality Checklist
- [ ] **Zero Third-Party Dependencies**: My changes use strictly Python standard library modules.
- [ ] **Unit Tests**: All unit tests pass cleanly locally (`python3 -m unittest discover -s tests`).
- [ ] **Deterministic Output**: If modifying exporters, outputs remain byte-deterministic (`python3 scripts/export_dashboard.py`).
- [ ] **Read-Only SQLite**: Any SQLite access uses strict read-only URI mode (`?mode=ro`).
- [ ] **No Secrets or PII**: Verified that no personal paths, conversation databases, or private API keys are included in this PR.
- [ ] **Conventional Commits**: Commit messages follow the Conventional Commits format (`feat(...)`, `fix(...)`).
