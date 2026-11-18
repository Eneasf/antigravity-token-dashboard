# Milestone Slice 02: Rolling Quotas, Model Allowances & Imputed Subscription Value

- **Date**: 2026-09-05
- **Active Branch**: `feat/rolling-quota-allowances`
- **Status**: **VERIFIED & COMPLETED**
- **Associated ADR**: ADR-009 (Rolling Quota & Subscription Value Dual-Track Modeling)

---

## 1. Scope & Delivered Components

1. **Model Allowance Profiling & Taxonomy ([`config/pricing.json`](../../config/pricing.json))**:
   - Mapped 15+ internal Antigravity model identifiers (`1318` Flash High, `1298` Flash Core, `1016` Deep Reasoning, `1322` Fast Assistant, `1319` Pro, `1132`, `1035`, `1301`, etc.) with human-readable display names, families, and baseline API rates.
   - Declared subscription parameters: Pro tier, active 5-hour burst window, and 168-hour (7-day) weekly window.

2. **Rolling Window & Recovery Engine ([`src/aggregator.py`](../../src/aggregator.py))**:
   - `compute_rolling_window_telemetry`: Filters turns strictly within sliding time windows, partitions consumption by `model_id` (uncached prompt, cached prompt, candidate output, thinking vs answer), and computes window cache efficiency and imputed dollar value.
   - `compute_window_recovery_schedule`: Calculates the sliding-window roll-off timeline, identifying the earliest upcoming turns in the window and the exact minutes remaining until capacity is restored.
   - `compute_historical_peaks`: Two-pointer sliding window algorithm discovering maximum 5-hour and 7-day token bursts ever achieved across your entire conversation history.

3. **Dual-Track Financial Architecture**:
   - **Imputed Subscription Value**: Dollar equivalent of tokens delivered ($44.90 across 1.30B tokens) covered completely by the Pro subscription for $0 added cost.
   - **Out-of-Pocket Credit Burn**: Tracks actual billable overage ($0.00 while protected by quota).

4. **Visual Dashboard Surface ([`dashboard/index.html`](../../dashboard/index.html))**:
   - **Quota Command Bar**:
     - **5-Hour Quota Meter**: Visual fill percentage vs historical peak and real-time recovery countdown banner (*"Next recovery in 52m: +27,099 tokens from Gemini 3.8 Flash (High)"*).
     - **1-Week Quota Meter**: 7-day token volume and weekly pacing gauge.
     - **Subscription Value Card**: Clear display of imputed value and credit protection status badge (`● Safe in Pro Quota`).
   - **Model Allowance Matrix**:
     - Interactive toggle between 5-Hour and 1-Week windows displaying turn counts, uncached tokens, cached tokens, thinking tokens, total processed volume, and cache hit ratios for each model.

---

## 2. Verification Proofs & Quality Gates (`VDONE.md`)

### Gate V4: Unit Test Suite
```bash
python3 -m unittest discover -s tests
```
**Output**:
```
........
----------------------------------------------------------------------
Ran 8 tests in 0.002s

OK
```

### Gate V5: Quota & Hook Contract Verification
```bash
python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert 'rolling_5h' in d['quotas']; assert 'by_model' in d['quotas']['rolling_5h']; assert d['summary']['subscription_status'] == 'SAFE_IN_QUOTA'; print('Verified: Quota telemetry, model matrix, and subscription status intact.')"
```
**Output**:
```
Verified: Quota telemetry, model matrix, and subscription status intact.
```

### Gate V1 Live Telemetry Run:
```bash
python3 scripts/export_dashboard.py
```
**Output**:
```
Successfully exported 87 conversation sessions to dashboard/index.html
Total Input: 1,302,727,535 | Cached: 93.03% | Imputed Value: $44.9045 | Status: SAFE_IN_QUOTA
```
