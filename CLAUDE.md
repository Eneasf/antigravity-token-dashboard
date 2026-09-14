# CLAUDE.md

**This file is deliberately a pointer, not a copy.**

The working agreement for this repository lives in **[`AGENTS.md`](AGENTS.md)** — git hygiene and branching, verifiable gates (`vdone`), documentation and handover integrity, subagent allocation standards, and telemetry read safety boundaries. It is agent-neutral because multiple AI agents and human developers collaborate in this codebase.

## Read First

**[`AGENTS.md`](AGENTS.md)** — in full, before making changes. In particular:

- **§1** Git workflow — state active branch; propose a feature branch for schema, subsystem, or multi-file work; ensure 100% clean working tree at every commit point; byte-deterministic artifacts.
- **§2** Telemetry Read Safety — **non-negotiable**. Antigravity runtime databases (`~/.gemini/antigravity/conversations/*.db`) must **always** be opened in strict read-only mode (`?mode=ro`) to prevent lock contention or corruption with the running IDE.
- **§3** Plan Slices, Verifiable Gates & Handover — "Done if proven, not if declared" (`VDONE.md`); milestone slice documents in `docs/milestones/`; ADR table and open work register in `docs/HANDOVER.md`.
- **§4** Subagent Delegation — 3-tier model allocation (`flash_lite`, `flash`, `inherit`/`pro`), zero collision invariant, mandatory pre-flight disclosure.
- **§5** Context Boundary & Handover — Proactively call milestone boundaries and guide fresh session handoff.

## Why this file does not restate those rules

Duplicated instructions drift. Having a single canonical working agreement ensures all AI models, assistants, and human contributors adhere to the same ground truth without conflicting rule copies.

## Orientation

| Document | Purpose |
|---|---|
| [`AGENTS.md`](AGENTS.md) | **The working agreement.** Canonical source of repository protocols. |
| [`VDONE.md`](VDONE.md) | **Active acceptance gates.** Executable checks and measured expectations. |
| [`docs/SYSTEM_DESIGN.md`](docs/SYSTEM_DESIGN.md) | System architecture, SQLite WAL extraction, and protobuf decoding engine. |
| [`docs/TELEMETRY_SPEC.md`](docs/TELEMETRY_SPEC.md) | Protobuf field schemas (`steps.metadata`), turn types, and metric definitions. |
| [`docs/HANDOVER.md`](docs/HANDOVER.md) | Master hub — decisions (ADR log), milestones, verified state, open work register. |
| [`docs/milestones/`](docs/milestones/) | Permanent milestone slice documents with test proofs. |
| [`README.md`](README.md) | High-level system overview, quickstart, and CLI guide. |
| [`config/pricing.json`](config/pricing.json) | Token and caching pricing tables by model tier. |
| [`dashboard/index.html`](dashboard/index.html) | Standalone deterministic dashboard interface. |
