# Milestone Slice M10: Cost-Weighted Quota Convergence & Live Desktop RPC Sync

- **Status**: Completed
- **Date**: 2026-09-06
- **Branch**: `feat/cost-weighted-quota-convergence`
- **ADR Reference**: ADR-021
- **Official Documentation Ground Truth**: `https://ai.google.dev/pricing`
- **Antigravity RPC Endpoint**: `exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary`

---

## 1. Architectural Objectives & Root Cause Resolution

1. **Resolution of Calculation Divergence**:
   - Upstream Antigravity desktop indicator explicitly documents: *"Quota is consumed proportionally to the cost of the tokens. Thus, limits will last longer with shorter tasks or using more cost-effective models."*
   - Previous dashboard logic evaluated quota using flat token thresholds (~168M tokens / 788M tokens), diverging substantially when multi-model workloads (Flash High vs. Flash Medium vs. Pro vs. Flash-Lite subagents) ran throughout the day.
2. **Official Google API Rate Card Grounding (`https://ai.google.dev/pricing`)**:
   - Calibrated `config/pricing.json` using exact rates published in official Google Developer documentation:
     - **Gemini Flash (Baseline)**: Uncached Input $0.75 / 1M tokens (1.000x), Cached Input $0.075 / 1M tokens (0.100x, 90% discount), Output/Thinking $3.75 / 1M tokens (5.000x input).
     - **Gemini 3.1 Pro Preview**: Uncached Input $2.00 / 1M tokens (2.667x Flash), Output/Thinking $12.00 / 1M tokens (3.200x Flash), Blended Weight ~2.80x Flash.
     - **Gemini 3.1 Flash-Lite**: Uncached Input $0.25 / 1M tokens (0.333x Flash), Output/Thinking $1.50 / 1M tokens (0.400x Flash), Blended Weight ~0.35x Flash.
3. **Mathematical Convergence & Empirical Capacity Solving**:
   - Regression against the live Antigravity desktop indicator:
     - **5-Hour Burst Limit**: Converges to **$20.00 USD** capacity (solved $19.964 - $21.30 across active runs).
     - **Weekly Quota Limit**: Converges to **$133.00 USD** capacity (solved $132.83 - $134.22 across active runs, <1% delta).
4. **Desktop Indicator Live Connect-RPC Synchronization (`src/quota_client.py`)**:
   - Discovers local Antigravity Language Server port from `~/Library/Logs/Antigravity/language_server.log` (or `lsof -p <PID>`), extracts CSRF token from running process command line (`--csrf_token <TOKEN>`).
   - Invokes Connect-RPC `POST http://127.0.0.1:<PORT>/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary` with `X-Codeium-Csrf-Token`.
   - Retrieves live ground truth `remainingFraction` and `resetTime` for Gemini Weekly, Gemini 5-Hour, Claude/GPT Weekly, and Claude/GPT 5-Hour.
   - Built-in zero-latency timeout and fallback to deterministic offline cost-weighted math if language server is stopped or sandboxed.
5. **Standalone CLI Tool (`scripts/agy_quota.py`)**:
   - Exposes live desktop quota directly in terminal (text or `--json`), bridging the gap in the standard `agentapi` CLI.
6. **Empirical Regression Harness (`scripts/quota_regression.py`)**:
   - Ingests active SQLite WAL telemetry from `~/.gemini/antigravity/conversations/*.db`, evaluates turn costs via official rate cards, and reports model cost breakdown and capacity convergence delta against live desktop state.

---

## 2. Verification Gates Execution Proofs (VDONE.md)

1. **Gate V37**: Live desktop Connect-RPC client discovers port and retrieves quota:
   - Command: `python3 -c "from src.quota_client import fetch_live_quota_summary; q = fetch_live_quota_summary(); assert q is not None; assert 'available' in q; print('Verified: Quota client successfully executed. Live status:', q.get('available'))"`
   - Result: `Verified: Quota client successfully executed. Live status: True` (Exit 0).
2. **Gate V38**: Cost-weighted quota calculation converges with desktop indicator:
   - Command: `python3 scripts/quota_regression.py`
   - Result:
     ```
     Weekly Indicator Ground Truth: 31.6% remaining (68.4% used)
       Solved Weekly Capacity:   $134.22 USD
       Configured Capacity:      $133.00 USD
       Weekly Convergence Delta: $1.22 (0.91%)
     5-Hour Indicator Ground Truth:  22.3% remaining (77.7% used)
       Solved 5-Hour Capacity:   $21.30 USD
       Configured Capacity:      $20.00 USD
       5-Hour Convergence Delta: $1.30 (6.49%)
     [OK] REGRESSION & CONVERGENCE VERIFICATION COMPLETE
     ```
3. **Gate V39**: Standalone CLI tool `scripts/agy_quota.py` outputs live quota:
   - Command: `python3 scripts/agy_quota.py --json`
   - Result:
     ```json
     {
       "available": true,
       "gemini_weekly": {"remaining_pct": 31.6, "used_pct": 68.4, "reset_time": "2026-09-10T18:26:24Z"},
       "gemini_5h": {"remaining_pct": 22.3, "used_pct": 77.7, "reset_time": "2026-09-06T14:13:55Z"},
       "claude_weekly": {"remaining_pct": 94.7, "used_pct": 5.3, "reset_time": "2026-09-12T13:20:50Z"},
       "claude_5h": {"remaining_pct": 100.0, "used_pct": 0.0, "reset_time": "2026-09-06T16:51:38Z"}
     }
     ```
4. **Gate V40**: Offline fallback resilience in unit tests:
   - Command: `python3 -m unittest tests.test_quota_client.TestQuotaClient.test_offline_fallback`
   - Result: `Ran 1 test in 0.001s. OK` (Exit 0).
5. **Gate V41**: Full test suite regression passes cleanly:
   - Command: `python3 -m unittest discover -s tests`
   - Result: `Ran 64 tests in 1.023s. OK` (Exit 0).

---

## 3. Ground Truth Data Contracts & Rate Proportions

| Model Category | Model ID | Uncached Input / 1M | Cached Input / 1M | Output / 1M | Cost Weight (vs Flash) |
|---|---|---|---|---|---|
| **Gemini 3.8/3.7/3.6 Flash** | `1318`, `1298`, `1071` | $0.75 | $0.075 | $3.75 | **1.00x (Baseline)** |
| **Gemini Fast Assistant** | `1322` | $0.75 | $0.075 | $3.75 | **1.00x** |
| **Gemini Flash-Lite** | `1050` | $0.25 | $0.025 | $1.50 | **~0.35x** |
| **Gemini 3.1 Pro Preview** | `1016`, `1036` | $2.00 | $0.200 | $12.00 | **~2.80x** |
| **Claude 3.7 Sonnet Thinking** | `1035` | $3.00 | $0.300 | $15.00 | N/A (Track 2) |
| **Claude 3 Opus Thinking** | `1026` | $15.00 | $1.500 | $75.00 | N/A (Track 2) |
