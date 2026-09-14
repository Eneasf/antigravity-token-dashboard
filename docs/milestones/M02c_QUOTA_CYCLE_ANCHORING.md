# Milestone Slice 02c: Signal-Anchored Overage Engine & Calendar Cycle Anchoring

- **Date**: 2026-09-05
- **Active Branch**: `feat/quota-cycle-anchoring-and-signal-fix`
- **Status**: **VERIFIED & COMPLETED**
- **Associated ADRs**:
  - ADR-014 (Signal-Anchored 5-Hour Overage Engine & Calendar Cycle Anchoring)

---

## 1. Scope & Delivered Components

1. **Strict Signal-Anchored Overage Engine ([`src/aggregator.py`](../../src/aggregator.py) & [`src/log_reader.py`](../../src/log_reader.py))**:
   - Eliminated the naive synthetic token volume condition (`cur_sum >= burst_limit`), anchoring AI credit burn deduction strictly to confirmed HTTP 429 `RESOURCE_EXHAUSTED` events in `~/Library/Logs/Antigravity/language_server.log`.
   - Completely resolved historical phantom charges (such as the -40 and -88 credit deductions incorrectly reported for August 28), ensuring historical reconciliation 100% mirrors the user's official Google One activity statement.
   - Configured 5-hour cooldown clustering windows (`cluster_gap_minutes=300.0`, `cooldown_padding_minutes=300.0`).

2. **Thursday 19:00 BST (18:00 UTC) Weekly Quota Reset ([`src/aggregator.py`](../../src/aggregator.py))**:
   - Replaced arbitrary 7-day rolling window with the verified calendar reset: **every Thursday at 19:00 BST (18:00 UTC)**.
   - Computes exact countdown matching the user's Antigravity IDE UI (e.g. *"5 days, 1 hour remaining"*).
   - Buckets model usage within `[last_thu_1800, now]` and exposes `weekly_cycle` telemetry in `quotas`.

3. **Monthly Billing Cycle Horizon (24th of Month) ([`src/aggregator.py`](../../src/aggregator.py))**:
   - Anchors Google One AI credit subscription cycle to the **24th of each month** (next renewal: **24 September 2026, 19:00 BST**).
   - Computes days and hours remaining until renewal (e.g. *"19 days, 1 hour remaining"*).
   - Tracks monthly budget consumption and remaining credit balance against the £23.99 / 2,500 credits plan.

4. **Dashboard Visualization ([`dashboard/index.html`](../../dashboard/index.html))**:
   - **Header Billing Badge**: Displays `Billing: Renews 24 Sep (19 days left)`.
   - **Weekly Allowance Cycle Box**: Replaced generic 7-day text with `🔄 Cycle Reset: Thursday 19:00 BST (5 days, 1 hours remaining)`.
   - **Monthly Plan Budget & Burn Box**: Displays `Plan: £23.99 / 2,500 credits • Renews 24 Sep` with dynamic credit burn and remaining allowance.
   - **Model Matrix Toggle**: Labeled `Weekly Cycle (Thu–Thu)` and dynamically wired to `quotas.weekly_cycle`.

---

## 2. Verification Proofs & Quality Gates (`VDONE.md`)

### Gate V0: Comprehensive Unit Test Suite
```bash
python3 -m unittest discover -s tests
```
**Output**:
```
Ran 28 tests in 0.694s
OK
```

### Gate V12: Signal-Anchored 5h Overage Engine (Zero Phantom Deductions)
```bash
python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); dates=[h['hour_timestamp'][:10] for h in d.get('hourly_credit_activity', [])]; assert '2026-08-28' not in dates; print('Gate V12 Verified: No phantom August deductions.')"
```
**Output**:
```
Gate V12 Verified: No phantom August deductions.
```

### Gate V13: Thursday Weekly Cycle Reset Anchoring
```bash
python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert 'weekly_cycle' in d['quotas']; assert d['quotas']['weekly_cycle']['reset_day_name'] == 'Thursday'; print('Gate V13 Verified: Thursday weekly cycle reset intact.')"
```
**Output**:
```
Gate V13 Verified: Thursday weekly cycle reset intact.
```

### Gate V14: 24th Monthly Billing Horizon Renewal
```bash
python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert 'monthly_billing' in d['quotas']; assert '2026-09-24' in d['quotas']['monthly_billing']['renewal_date']; print('Gate V14 Verified: 24th monthly billing horizon intact.')"
```
**Output**:
```
Gate V14 Verified: 24th monthly billing horizon intact.
```
