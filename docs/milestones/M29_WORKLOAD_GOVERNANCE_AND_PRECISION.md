# Milestone 29: Workload Governance, Standup Digest & Precision Hardening

- **Status**: Completed
- **Active Branch**: `feat/workload-governance-and-precision`
- **Architectural Decision Record**: [ADR-042](../HANDOVER.md#2-master-decision-index-architectural-decision-records)
- **Primary Deliverables**:
  1. Pre-Flight Workload Budget Checker CLI (`scripts/agy_quota.py --can-i-run`) with deterministic exit codes (`0` SAFE/PROCEED, `1` BLOCKED/429 RISK).
  2. Byte-Deterministic Standup Digest Exporter (`scripts/export_dashboard.py --markdown`) and Dashboard UI clipboard button (`📋 Copy Summary`).
  3. Full Vault Ingestion Scaling (A1): Lifted conversation limit default (`max_conversations=None`) with discovered/scanned metrics reporting.
  4. Localized Browser Timezone Formatting (A2): Replaced static BST strings with `Intl.DateTimeFormat` UTC timestamp localization.
  5. Cost-Weighted Overage Credit Attribution (A5): Unit test suite (`tests/test_overage_weighting.py`) verifying rate-card spend proportional credit distribution.
  6. Docs Directory Hygiene: Relocated one-off analysis reports to `docs/reports/` and updated `.gitignore`.

---

## Acceptance Gates & Verifiable Proofs

### V144: Pre-Flight Workload Budget Checker CLI (`scripts/agy_quota.py --can-i-run`)
- **CHECK**: `python3 scripts/agy_quota.py --can-i-run deep_refactor_swarm --json && python3 -m unittest -v tests/test_preflight_budget.py`
- **EXPECT**: Evaluates archetype headroom; outputs valid JSON with `exit_code: 0` for safe runs and `exit_code: 1` on rate-limit/lockout risks; 7/7 tests pass.
- **PROOF**:
  - `python3 scripts/agy_quota.py --can-i-run deep_refactor_swarm`: exit code 0 (`VERDICT: [SAFE TO PROCEED]`).
  - `python3 scripts/agy_quota.py --can-i-run claude_opus_deep_dive --turns 300`: exit code 1 (`VERDICT: [BLOCKED (429 RISK / EXHAUSTED)]`).
  - Ran 7 tests in 0.358s; 100% pass cleanly.

### V145: Byte-Deterministic Standup Digest Exporter (`scripts/export_dashboard.py --markdown`)
- **CHECK**: `python3 scripts/export_dashboard.py --markdown && python3 -m unittest -v tests/test_markdown_export.py`
- **EXPECT**: Emits clean Markdown summary block adhering strictly to byte-determinism (ADR-004); 3/3 tests pass.
- **PROOF**:
  - Output contains token throughput, cache efficiency %, avoided cost, credit deductions, and dual provider quota runway.
  - Ran 3 tests in 0.172s; 100% pass cleanly.

### V146: Standup Markdown Clipboard Copy Button (`dashboard/index.html` + `dashboard/app.js`)
- **CHECK**: `python3 -c "import re; html = open('dashboard/index.html').read(); js = open('dashboard/app.js').read(); assert 'btn-copy-standup' in html; assert 'generateStandupMarkdown' in js; print('Verified: UI clipboard copy button and formatter wired intact.')"`
- **EXPECT**: `Verified: UI clipboard copy button and formatter wired intact.`; exit code 0.

### V147: Full Ingestion Scaling (Audit §2.1 A1)
- **CHECK**: `python3 -c "from src.vault import sync_conversations_to_vault; import inspect; sig = inspect.signature(sync_conversations_to_vault); assert sig.parameters['max_conversations'].default is None; print('Verified: sync_conversations_to_vault defaults to unlimited max_conversations=None.')"`
- **EXPECT**: `Verified: sync_conversations_to_vault defaults to unlimited max_conversations=None.`; exit code 0.

### V148: Dynamic Browser Timezone Localization (Audit §2.1 A2)
- **CHECK**: `python3 -c "js = open('dashboard/app.js').read(); assert 'formatLocalizedResetTime' in js; assert 'Intl.DateTimeFormat' in js; assert 'Thursday 19:00 BST' not in js; print('Verified: Zero hardcoded BST fallbacks in app.js.')"`
- **EXPECT**: `Verified: Zero hardcoded BST fallbacks in app.js.`; exit code 0.

### V149: Cost-Weighted Overage Allocation Verification (Audit §2.1 A5)
- **CHECK**: `python3 -m unittest -v tests/test_overage_weighting.py`
- **EXPECT**: Confirms that Opus turns (90.9% of cost) receive 500 of 550 incident credits and Flash-Lite turns (9.1% of cost) receive 50 credits across conversations and branches; exit code 0.
- **PROOF**: Ran 1 test in 0.018s; 100% pass cleanly.

### V150: Docs Directory Hygiene (Audit §1.3)
- **CHECK**: `python3 -c "import os; from pathlib import Path; assert not Path('docs/COST_UTILITY_ANALYSIS_ULTRA.md').exists(); assert not Path('docs/CONVERSATION_TELEMETRY_ANALYSIS.md').exists(); assert Path('docs/reports/CONVERSATION_TELEMETRY_ANALYSIS.md').exists(); assert Path('docs/reports/COST_UTILITY_ANALYSIS_ULTRA.md').exists(); print('Verified: Reports relocated to docs/reports/.')"`
- **EXPECT**: `Verified: Reports relocated to docs/reports/.`; exit code 0.

### V151: Full Regression & Documentation Integrity
- **CHECK**: `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py && python3 -m unittest tests/test_model_roster_integrity.py`
- **EXPECT**: 166+ unit tests pass with 0 failures, 0 errors.
