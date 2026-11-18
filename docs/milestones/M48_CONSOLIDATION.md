# M48 · Consolidation & Ceremony Reduction · 2026-09-19 · v2.6.0

## Why
Consolidated bloated acceptance registers into an automated side-effect-free test suite, eliminated documentation drift, established semantic versioning, and prepped repo for feature-freeze execution (audit rows 1–3).

## What changed
- `VDONE.md`: Streamlined to active §A/§B gates (<150 lines); archived V0–V260 to `docs/milestones/VDONE_ARCHIVE_M01-M47.md`.
- `README.md`: Refactored into clean front door (<180 lines, 0 milestone/ADR numbers); moved capabilities to `CHANGELOG.md` and tree to `docs/REPO_MAP.md`.
- `docs/HANDOVER.md`: ADR rows <=160 chars, max lines <=300 chars, §4 Open rows 4–17 with branches, M04/M05 note.
- `AGENTS.md`: Added §1.9 numbers rule, §2.5 single exporter, amended §3.6 ops check, prefixed §4/§5 IDE markers.
- `CLAUDE.md`: Removed redundant orientation table.
- `tests/`: Created `test_vdone_gates.py`, retargeted `test_docs_integrity.py` to `docs/REPO_MAP.md`, updated `test_sanitization.py`.
- `scripts/ops_check.py`: Created automated operational verification script.
- `package.json` & `pyproject.toml`: Bumped to version 2.6.0.

## Decisions taken
- ADR-004 marked `Superseded (by ADR-024)`.
- Semantic `v2.x.y` versioning scheme adopted across project packages and git tags (audit §7 #5).

## Gates & proofs
- B1 VDONE size budget: 24 lines (EXPECT < 150) -> PASS
- B2 README size budget: 90 lines (EXPECT < 180) -> PASS
- B3 Gate runner proof: `python3 -m unittest tests.test_vdone_gates` -> Ran 3 tests in 10.477s, OK
- B4 No ops in VDONE: 0 matches (EXPECT 0) -> PASS
- B5 No milestone or ADR numbers in README: 0 matches (EXPECT 0) -> PASS
- B6–B8 Archive, Changelog, Repo map created and verified -> PASS
- B9 Handover line length: 0 lines > 300 chars (EXPECT 0) -> PASS
- B10 Handover M04/M05 note present: 1 match (EXPECT > 0) -> PASS
- B11 CLAUDE orientation table removed: 0 matches (EXPECT 0) -> PASS
- B12 Ops check script exists and executable -> PASS

## Ops check
`[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 57220) | verified: 2026-09-19T17:20:54+01:00`
