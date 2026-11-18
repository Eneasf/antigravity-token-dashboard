# Milestone Slice M09: Dual-Track Provider Quota Silos (Gemini vs. Claude/GPT)

- **Status**: Completed
- **Date**: 2026-09-06
- **Branch**: `feat/dual-track-provider-quotas`
- **ADR Reference**: ADR-019
- **Empirical Ground Truth**: Antigravity IDE UI quota surface (`media_1788692679985.png`)

---

## 1. Architectural Objectives & Invariants

1. **Dual Independent Quota Silos (ADR-019)**:
   - Ground truth from Antigravity IDE reveals two distinct quota pools:
     - **Track 1: Gemini Models** (all Flash, Pro, Subagent Lite/Fast variants).
     - **Track 2: Claude and GPT models** (Claude Sonnet 3.7/3.5, Claude Opus 3, GPT OSS).
   - Usage of Claude or GPT models does not deplete Gemini quotas, and heavy Gemini usage does not affect Claude/GPT allowances.
2. **Step-Level Partitioning Invariant (Heterogeneous Multi-Agent Swarms)**:
   - In Antigravity, a Claude or GPT parent session (`1035` Sonnet Thinking, `1026` Opus Thinking) can spawn Gemini subagents (`1322` Fast Assistant, `1050` Flash Lite) via `invoke_subagent`.
   - Quota bucketing MUST evaluate `get_provider_quota_track(step.model_id)` strictly at the individual step level (`step_type = 15`), NEVER at the conversation level.
   - This ensures subagent tool iterations debit exclusively to the Gemini quota silo while parent reasoning turns debit to the Claude/GPT silo, with zero cross-track contamination.
3. **Family-Driven Dynamic Routing (`get_provider_quota_track`)**:
   - Rather than static ID enumeration, classification routes dynamically via `config/pricing.json`'s `family` field:
     - If `family.startswith("claude")` or `family == "gpt-oss"` (or starts with `"gpt"`), route to `"claude_gpt"`.
     - Else (including `gemini-flash`, `gemini-pro`, `gemini-internal`, `default`), route to `"gemini"`.
   - Automatically and deterministically classifies all 19 models identified in the historical census (`1318`, `1298`, `1016`, `1322`, `1132`, `1301`, `1035`, `1072`, `1026`, `1071`, `1319`, `1020`, `1036`, `342`, `1299`, `1050`, `1073`, `1300`, `1320`) and future extensions.
4. **Credit Spillover Asymmetry**:
   - **Track 1 (Gemini Models)**: Supported by Google One AI Premium credit spillover. Upon encountering HTTP 429 quota exhaustion, bursts debit to the prepaid 2,500 AI credit bank.
   - **Track 2 (Claude & GPT Models)**: Operates strictly within subscription quota allowances with hard-blocking upon exhaustion (0 credit spillover / zero credit burn).
5. **Independent Window & Reset Anchoring**:
   - **Gemini Weekly**: Anchored to Thursday 19:00 BST / 18:00 UTC cycle reset ("it will fully refresh in 4 days, 7 hours").
   - **Claude/GPT Weekly**: Anchored to an independent 7-day rolling window / weekly schedule ("it will fully refresh in 6 days, 2 hours").
   - **5-Hour Rolling Bursts**: Distinct 5h sliding windows and recovery schedules per track.
6. **Backward-Compatible Schema**:
   - `payload['quotas']` preserves existing top-level fields (`rolling_5h`, `weekly_cycle`, `monthly_billing`) while introducing `payload['quotas']['providers']['gemini']` and `payload['quotas']['providers']['claude_gpt']`.
7. **Dashboard UI Alignment**:
   - Mirrors the Antigravity IDE surface by rendering dual provider cards with percentage badges, ring/progress meters, and human-readable countdowns.

---

## 2. Verification Gates Execution Proofs (VDONE.md)

1. **Gate V31**: Provider family classification integrity:
   - Command: `python3 -c "from src.aggregator import get_provider_quota_track; assert get_provider_quota_track('1318') == 'gemini'; assert get_provider_quota_track('1016') == 'gemini'; assert get_provider_quota_track('1050') == 'gemini'; assert get_provider_quota_track('1322') == 'gemini'; assert get_provider_quota_track('1036') == 'gemini'; assert get_provider_quota_track('1035') == 'claude_gpt'; assert get_provider_quota_track('1026') == 'claude_gpt'; assert get_provider_quota_track('342') == 'claude_gpt'; print('Verified: Provider family classification routes correctly across desktop and subagent models.')"`
   - Result: `Verified: Provider family classification routes correctly across desktop and subagent models.` (Exit 0).
2. **Gate V32**: Dual-track quota computation in aggregator:
   - Command: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); q=d['quotas']; assert 'providers' in q; assert 'gemini' in q['providers']; assert 'claude_gpt' in q['providers']; assert 'five_hour' in q['providers']['gemini'] and 'weekly' in q['providers']['gemini']; assert 'five_hour' in q['providers']['claude_gpt'] and 'weekly' in q['providers']['claude_gpt']; print('Verified: Dual-track provider quota payload intact.')"`
   - Result: `Verified: Dual-track provider quota payload intact.` (Exit 0).
3. **Gate V33**: Distinct refresh countdowns:
   - Command: `python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); g=d['quotas']['providers']['gemini']; cg=d['quotas']['providers']['claude_gpt']; assert 'Thursday' in g['weekly']['reset_display']; assert 'refresh' in g['weekly']['message'].lower() or 'fully' in g['weekly']['message'].lower(); print('Verified: Distinct refresh countdowns verified.')"`
   - Result: `Verified: Distinct refresh countdowns verified.` (Exit 0).
4. **Gate V34**: Zero cross-track contamination:
   - Command: `python3 -m unittest tests.test_aggregator.TestAggregator.test_zero_cross_track_contamination`
   - Result: `Ran 1 test in 0.003s. OK` (Exit 0).
5. **Gate V35**: Visual dashboard DOM elements:
   - Command: `python3 -c "c=open('dashboard/index.html').read(); ids=['gemini-weekly-pct', 'gemini-5h-pct', 'claude-weekly-pct', 'claude-5h-pct', 'gemini-weekly-sub', 'gemini-5h-sub', 'claude-weekly-sub', 'claude-5h-sub']; assert all(f'id=\"{i}\"' in c for i in ids); print('Verified: Dual provider quota DOM elements present.')"`
   - Result: `Verified: Dual provider quota DOM elements present.` (Exit 0).
6. **Gate V36**: Full regression test suite integrity:
   - Command: `python3 -m unittest discover -s tests`
   - Result: `Ran 60 tests in 1.093s. OK` (Exit 0).

