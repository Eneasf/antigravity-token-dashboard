# Milestone 76: Add Automated Test Harnesses for Quota Regression & GitHub Guardrails (C9)

**Date**: 2026-09-28
**Scope**: Row 10 (C9) from `docs/HANDOVER.md` §4 & `docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md`
**Branch**: `chore/scripts-governance-cleanup`
**Verdict**: **PASS**

---

## 1. Overview & Context

Audit finding `C9` from `docs/AUDIT_2026-09-26_BACKEND_AND_PIPELINES.md` identified orphaned developer and maintenance scripts:
- `scripts/setup_github_guardrails.py` and `scripts/quota_regression.py` lacked dedicated automated unit tests.
- `scripts/quota_regression.py` imported from `src.telemetry_reader` (an obsolete compatibility re-export shim) rather than canonical package `antigravity_telemetry`.
- The scripts lacked `--dry-run` and argument parsing capability, preventing safe offline execution and CI governance verification.
- Neither script was referenced in `README.md` or active acceptance gates.

Per Owner Decision 3:
> "Keep both and add automated dry-run test gates to prevent silent rot. Add test harnesses in tests/ verifying execution and returncode 0 without side effects. Implemented in Row 10."

---

## 2. Changes Implemented

- **`scripts/quota_regression.py`**:
  - Replaced legacy `from src.telemetry_reader import ...` import with direct canonical import `from antigravity_telemetry import discover_all_conversations, read_conversation_turns`.
  - Extracted module-level `calc_turn_cost(t, models_cfg, fallback_rates=None)` function for direct testability.
  - Added CLI argument parser (`build_parser()`) supporting `--antigravity-dir`, `--pricing-config`, `--no-live-quota`, and `--dry-run`.
  - Supported hermetic `--dry-run` execution that verifies rate cards and pricing proportions without accessing conversation databases.
  - Structured `run_regression_analysis()` to return a dictionary of calculated metrics.
- **`scripts/setup_github_guardrails.py`**:
  - Extracted payload builders `build_branch_protection_payload()` and `build_repo_settings_args()`.
  - Added CLI argument parser (`build_parser()`) supporting `--repo`, `--branch`, and `--dry-run`.
  - Implemented hermetic `--dry-run` mode simulating repository configurations and branch protection rules without network calls or GitHub mutations.
  - Hardened `run_gh_command` to return error tuple `(1, "", ...)` on `FileNotFoundError` rather than terminating the interpreter via `sys.exit(1)`.
- **`tests/test_quota_regression.py`** (New Test Suite):
  - Comprehensive unit and integration test suite covering turn cost calculations, pricing proportions, CLI parsing, hermetic dry-run execution, offline fixture regression, and live quota fallback/zero-division resilience.
- **`tests/test_setup_github_guardrails.py`** (New Test Suite):
  - Comprehensive unit and integration test suite covering branch protection payload schema, required checks, repo settings arguments, CLI parsing, offline dry-run mode, repo visibility parsing, and error/timeout handling.
- **`README.md`**:
  - Documented CLI entry points for `scripts/quota_regression.py` and `scripts/setup_github_guardrails.py` under Developer & Governance Utilities.
- **`docs/REPO_MAP.md`**:
  - Registered `tests/test_quota_regression.py` and `tests/test_setup_github_guardrails.py`.
- **`VDONE.md`**:
  - Formulated acceptance gates B1, B2, and B3.

---

## 3. Acceptance Gates (§B)

| Gate # | Check Command | Expected | Verdict |
| :---: | :--- | :--- | :--- |
| B1 | `python3 -m unittest tests/test_quota_regression.py` | `OK` | PASS |
| B2 | `python3 -m unittest tests/test_setup_github_guardrails.py` | `OK` | PASS |
| B3 | `python3 -c "from pathlib import Path; m = Path('docs/REPO_MAP.md').read_text(); assert 'test_quota_regression.py' in m and 'test_setup_github_guardrails.py' in m; print('OK')"` | `OK` | PASS |

Tested with: Unit test suites `tests/test_quota_regression.py` and `tests/test_setup_github_guardrails.py`; full offline test discovery suite; doc integrity test; headless Playwright dashboard boot spec.
