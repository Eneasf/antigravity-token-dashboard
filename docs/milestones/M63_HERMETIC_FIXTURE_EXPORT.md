# M63 · Hermetic Fixture Export & Anonymized Baseline · 2026-09-21 · v2.20.1

## Why
Under Audit 2026-09-19 Row 18 (C12), previous test fixtures and golden export baselines inherited runtime telemetry paths (`language_server.log` and `exhaustion_ledger.json`) from the host environment (`~/.gemini/antigravity` and `~/Library/Logs/Antigravity/language_server.log`), inadvertently capturing personal overage history (3,640 credits across 9 exhaustion intervals) and developer host paths. Consequently, the M62 byte-identical export gate only held on the owner's local machine.

Milestone 63 implements strict hermetic export isolation for `--antigravity-dir` (anchoring `language_server.log` and `exhaustion_ledger.json` strictly to `<dir>` without home directory fallback), introduces isolated `$HOME` verification, provides synthetic zero-PII test logs and ledger files in `tests/fixtures/antigravity/`, and regenerates `tests/fixtures/aggregator_baseline_data.json` free of personal data.

## What changed
- **Hermetic Path Resolution**: Updated `scripts/export_dashboard.py` and `src/log_reader.py` so that when `antigravity_dir` is not the default, `language_server.log` and `exhaustion_ledger.json` resolve strictly within `<dir>` and never fall back to the host home directory or repository `data/`.
- **Synthetic Offline Fixtures**: Created `tests/fixtures/antigravity/language_server.log` (glog format, fixture conversation IDs `11111111-1111-1111-1111-111111111111` and `22222222-2222-2222-2222-222222222222`, two 429 events) and `tests/fixtures/antigravity/exhaustion_ledger.json` (two synthetic incidents, 125 credits total, zero PII).
- **Anonymized Golden Baseline**: Regenerated `tests/fixtures/aggregator_baseline_data.json` deterministically; confirmed zero occurrences of host overage (3640) and zero `/Users/` or personal usernames.
- **Isolated HOME Tests**: Added `test_hermetic_export_with_isolated_home` and `test_baseline_contains_only_synthetic_fixtures` in `tests/test_ci_fixtures.py`, plus `test_custom_antigravity_dir_resolves_local_log_and_ledger` in `tests/test_export_dashboard.py`.
- **Acceptance Gates & Manifests**: Configured VDONE.md acceptance gates B1-B4, recorded ADR-077 in `docs/HANDOVER.md`, updated M62 documentation, bumped package version to `2.20.1` across manifests, and authored changelog notes.

## Decisions taken
| ADR | Title | Status | Summary | Doc |
|---|---|---|---|---|
| ADR-077 | Hermetic Fixture Export & Anonymized Baseline | Adopted | When --antigravity-dir is custom, resolve language_server.log and exhaustion_ledger.json to <dir>, eliminating host PII and personal credit burn from golden fixtures. | [doc](milestones/M63_HERMETIC_FIXTURE_EXPORT.md) |

## Gates & proofs
- **B1 (Fixture export with isolated HOME)**: `python3 -c "import os, tempfile, subprocess, pathlib, shutil; empty = tempfile.mkdtemp(); out = tempfile.mkdtemp(); env = dict(os.environ, HOME=empty); subprocess.run(['python3', 'scripts/export_dashboard.py', '--antigravity-dir', 'tests/fixtures/antigravity', '--no-live-quota', '--reference-time', '2026-09-05T14:30:00Z', '--output-dir', out], env=env, check=True, capture_output=True); cur = (pathlib.Path(out)/'data.json').read_bytes(); base = pathlib.Path('tests/fixtures/aggregator_baseline_data.json').read_bytes(); shutil.rmtree(empty); shutil.rmtree(out); assert cur == base and len(cur) > 0; print('OK')"` -> `OK`.
- **B2 (Zero host credit burn in baseline)**: `python3 -c "from pathlib import Path; base = Path('tests/fixtures/aggregator_baseline_data.json').read_text(); assert '3640' not in base; print('OK')"` -> `OK`.
- **B3 (Baseline contains exactly 2 synthetic 429 events)**: `python3 -c "import json; from pathlib import Path; d = json.loads(Path('tests/fixtures/aggregator_baseline_data.json').read_text()); assert len(d.get('exhaustion_intervals', [])) == 2; print('OK')"` -> `OK`.
- **B4 (Docs and model integrity)**: `python3 -m unittest tests.test_docs_integrity tests.test_model_roster_integrity` -> `OK`.

### Ops check
```text
[OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 614) | verified: 2026-09-21T11:50:31+01:00
```

## Verifier report
```markdown
# Milestone 63 (Audit Row 18) Verification Report
**Agent V (Independent Verification Specialist)**
**Active Branch:** `fix/hermetic-fixture-export`
**Scope:** Strictly Read-Only (0 files modified)
**Final Verdict:** **PASS** (100% Gates Verified)

---

## 1. Dual Export & Hermeticity Proof
| Execution Scenario | Command | Exit Code | SHA-256 Checksum | `cmp` vs Baseline |
| :--- | :--- | :---: | :---: | :---: |
| **Normal Export** | `python3 scripts/export_dashboard.py --antigravity-dir tests/fixtures/antigravity --no-live-quota --reference-time 2026-09-05T14:30:00Z --output-dir /tmp/exp_normal` | `0` | `bf8d6bcb7eecfe469f298e6a8d03f68d5a7de8d8a9874f524a3aab8cb8f235df` | **Byte-for-byte identical** |
| **Isolated `$HOME` Export** | `HOME=$(mktemp -d) python3 scripts/export_dashboard.py --antigravity-dir tests/fixtures/antigravity --no-live-quota --reference-time 2026-09-05T14:30:00Z --output-dir /tmp/exp_empty_home` | `0` | `bf8d6bcb7eecfe469f298e6a8d03f68d5a7de8d8a9874f524a3aab8cb8f235df` | **Byte-for-byte identical** |
| **Target Baseline** | `tests/fixtures/aggregator_baseline_data.json` | — | `bf8d6bcb7eecfe469f298e6a8d03f68d5a7de8d8a9874f524a3aab8cb8f235df` | **Reference** |

- Both exports produced byte-identical files matching `tests/fixtures/aggregator_baseline_data.json` exactly.
- Total input: 77,000 tokens | Cached: 85.45% | Imputed Value: £0.1772 ($0.2243) | AI Credits Burned: 125 credits (£1.20 / $1.25) | Status: BURNING_AI_CREDITS.

---

## 2. PII / Owner Host Data Absence Verification
| Check Target | Search Pattern | Target Path(s) | Match Count | Verdict |
| :--- | :--- | :--- | :---: | :---: |
| Host Credit Ledger Burn | `3640` | `tests/fixtures/aggregator_baseline_data.json` | **0** | **PASS** |
| macOS User Home Paths | `/Users/` | `tests/fixtures/antigravity/` & `tests/fixtures/aggregator_baseline_data.json` | **0** | **PASS** |
| User Username / Identity | `eneasf` (case-insensitive) | `tests/fixtures/antigravity/` & `tests/fixtures/aggregator_baseline_data.json` | **0** | **PASS** |

---

## 3. Acceptance Gates Verification Matrix (VDONE §A & §B)

| Gate | Description | Command | Expected | Actual Result | Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **A1** | Unit Test Suite | `python3 -m unittest discover -s tests -p 'test_*.py'` | `OK, < 60 s` | Ran 291 tests in 41.206s (total 41.506s) | **PASS** |
| **A2** | Docs Integrity | `python3 -m unittest tests.test_docs_integrity` | `OK` | Ran 11 tests in 1.001s, OK | **PASS** |
| **A3** | Model Roster Integrity | `python3 -m unittest tests.test_model_roster_integrity` | `OK` | Ran 7 tests in 0.043s, OK | **PASS** |
| **A4** | No Stale Numbers | `python3 -m unittest tests.test_docs_integrity -k test_stale_numbers` | `OK` | Ran 1 test in 0.023s, OK | **PASS** |
| **A5** | Fixture Determinism | `python3 -c "import tempfile, subprocess, pathlib, shutil; ..."` | `OK` | Exit 0, byte-identical output | **PASS** |
| **B1** | Isolated HOME Export | `python3 -c "import os, tempfile, ... assert cur == base ..."` | `OK` | Exit 0, `cur == base` verified | **PASS** |
| **B2** | Zero Host Credit Burn | `python3 -c "assert '3640' not in base ..."` | `OK` | Exit 0, `3640` absent | **PASS** |
| **B3** | Synthetic 429 Events | `python3 -c "assert len(d.get('exhaustion_intervals', [])) == 2 ..."` | `OK` | Exit 0, exactly 2 intervals | **PASS** |
| **B4** | Docs & Model Integrity | `python3 -m unittest tests.test_docs_integrity tests.test_model_roster_integrity` | `OK` | Ran 18 tests in 0.922s, OK | **PASS** |

---

## 4. Full Unit Test Suite Execution
- Command: `python3 -m unittest discover -s tests -p 'test_*.py'`
- Results:
  - Total tests run: 291
  - Failures: 0
  - Errors: 0
  - Wall-clock time: 41.206s (< 60s threshold)
  - Result: OK

---

## 5. Live Operations Check (ADR-047)
- Command: `python3 scripts/ops_check.py`
- Output:
  ```text
  [OPS CHECK] export: OK | daemon: RUNNING / REGISTERED | menubar: RUNNING (PID: 614) | verified: 2026-09-21T11:50:31+01:00
  ```
- Result: PASS (Export operational, daemon active & registered, menubar app running).

---

## Final Verdict
OVERALL VERDICT: PASS
All 9 verification gates, dual hermetic export comparisons, PII checks, test suites, and ops checks passed without error. Branch `fix/hermetic-fixture-export` is fully verified and ready for merge into `main`.
```

## Closing report
```
Merged:   M63 · v2.20.1 · Hermetic fixture export, isolated HOME & anonymized golden baseline
Open now: *(None. All 18 rows from the 2026-09-19 Audit backlog are completed and closed.)*
Next slice will touch: None (Milestone complete)
Needs owner: nothing
Freeze:   lifted
```
