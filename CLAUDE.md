# CLAUDE.md

**This file is deliberately a pointer, not a copy.**

The working agreement for this repository lives in **[`AGENTS.md`](AGENTS.md)** — polymorphic contract parameters, telemetry read safety boundaries, git hygiene, verifiable gates (`vdone`), and subagent allocation standards. It is agent-neutral because multiple AI agents and human developers collaborate in this codebase.

## Read First

**[`AGENTS.md`](AGENTS.md)** — in full, or your designated role slice:

- **§1** Repository Execution Contract & Core Telemetry Safety — `$PROJECT_TYPE`, `$TEST_CMD`, strict read-only DB access (`?mode=ro`), canonical model roster, and offline invariant.
- **§2** Implementer Invariants — git workflow, `VDONE.md` gates, live daemon ops, subagent model allocation, and 5-line closing report.
- **§3** Auditor & Challenger Invariants — UI rendering at 1440x900/375x812, axe-core a11y checks, adversarial fact-checking, zero mutation.
- **§4** Verifier Invariants — independent gate verification, tree purity pre/post checks, test suite execution.
- **§5** Reflector Governance — proposal-only retrospective evolutions and tri-scope routing.

## Why this file does not restate those rules

Duplicated instructions drift. Having a single canonical working agreement ensures all AI models, assistants, and human contributors adhere to the same ground truth without conflicting rule copies.
