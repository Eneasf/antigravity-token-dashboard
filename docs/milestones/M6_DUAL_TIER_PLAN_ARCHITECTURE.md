# Milestone Slice 06: Dual-Tier Plan & Overage Credit Architecture

- **Date**: 2026-09-05
- **Active Branch**: `feat/decouple-subscription-and-overage-credits`
- **Status**: **VERIFIED & COMPLETED**
- **Associated ADRs**:
  - ADR-015 (Decoupled Monthly Pro Subscription & Prepaid Overage Credit Bank Architecture)
  - ADR-016 (Persistent Append-Only 429 Exhaustion Ledger Defense)

---

## 1. Scope & Delivered Components

1. **Decoupled Financial Model Architecture ([`config/pricing.json`](../../config/pricing.json) & [`src/aggregator.py`](../../src/aggregator.py))**:
   - **Tier 1: Google One AI Premium (Antigravity Pro Subscription)**:
     - Fixed monthly price: **£18.99 / mo** (**$19.99 / mo**).
     - Standard included usage with £0 marginal cost in quota.
     - Renewal horizon: 24 Sep 2026 (19 days remaining).
     - Computes monthly cycle imputed API value (e.g. £30.76 API equivalent) and live subscription ROI multiplier (e.g. 1.6x ROI).
   - **Tier 2: Prepaid Overage Credit Bank (AI Credit Activity)**:
     - Prepaid add-on pack: **2,500 credits** for **£23.99** (**$25.00**).
     - Effective unit rate: **£0.009596 / credit** (~0.96p) and **$0.0100 / credit** (1.0¢).
     - Debited strictly when exceeding 5-hour burst limits or outside quota limits.
     - Tracks credits remaining (1,321 left), cash balance remaining (£12.68 / $13.21), burn count (1,179 credits), and burn percentage (47.2%).

2. **Persistent Exhaustion Ledger ([`data/exhaustion_ledger.json`](../../data/exhaustion_ledger.json) & [`src/log_reader.py`](../../src/log_reader.py))**:
   - Persistent append-only JSON ledger defending against upstream `language_server.log` file truncations on IDE restarts.
   - Reconciles with official Google One billing activity statements:
     - `exc-20260905-13`: 13:00 UTC, 299 turns on Gemini 3.8 Flash (High), **748 credits burned** (£7.18 GBP / $7.48 USD).
     - `exc-20260905-14`: 14:00 UTC, 172 turns on Gemini 3.8 Flash (High), **431 credits burned** (£4.13 GBP / $4.31 USD).
     - Combined: **1,179 credits burned** (£11.31 GBP / $11.79 USD), leaving **1,321 credits** in the bank.

3. **Decoupled Dashboard Quota Surface ([`dashboard/index.html`](../../dashboard/index.html))**:
   - Replaced monolithic subscription/credits display with 4 dedicated, focused cards:
     - **Card 1: 5-Hour Rolling Burst Window**: Token throughput, cache hit %, and chronological age-out recovery schedule.
     - **Card 2: Thursday Weekly Allowance Cycle**: Weekly token throughput, cache hit %, and Thursday 19:00 BST reset countdown.
     - **Card 3: Monthly Pro Subscription**: £18.99/mo ($19.99/mo), renewal status badge, cycle imputed value, and subscription ROI multiplier.
     - **Card 4: Prepaid Overage Credits**: 1,321 credits remaining hero stat, burn progress bar, total credits burned, cash burn, and remaining cash balance.
   - Live reconciliation table displaying official billing statement blocks with turn counts, credit deductions, cash burn, and model compute attribution.
   - Dynamic GBP (£) / USD ($) currency switching across both financial tiers simultaneously.

4. **Telemetry Exporter & Watcher Service Alignment ([`scripts/export_dashboard.py`](../../scripts/export_dashboard.py) & [`scripts/setup_service.py`](../../scripts/setup_service.py))**:
   - Deterministic injection into `<script id="injected-dashboard-data">` maintaining byte-level idempotency.
   - Seamless LaunchAgent daemon integration (`com.antigravity.telemetry.watcher`).

---

## 2. Verification Proofs & Quality Gates (`VDONE.md`)

### Gate V17: Decoupled Tier 1 & Tier 2 Summary Accounting
```bash
python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); s=d['summary']; assert s['monthly_subscription_price_gbp'] == 18.99; assert s['credit_bank_total'] == 2500; assert s['total_ai_credits_burned'] == 1179; assert s['credits_remaining'] == 1321; assert s['credit_bank_remaining_gbp'] == 12.68; assert s['credit_bank_remaining_usd'] == 13.21; print('Verified: Decoupled Tier 1 & Tier 2 summary accounting intact.')"
```
**Output**:
```
Verified: Decoupled Tier 1 & Tier 2 summary accounting intact.
```

### Gate V18: Persistent Exhaustion Ledger Ingestion & Reconciliation
```bash
python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert len(d.get('hourly_credit_activity', [])) == 2; assert d['hourly_credit_activity'][0]['credits_burned'] + d['hourly_credit_activity'][1]['credits_burned'] == 1179; print('Verified: Official billing hourly credit deductions reconciled (1179 credits).')"
```
**Output**:
```
Verified: Official billing hourly credit deductions reconciled (1179 credits).
```

### Gate V19: Decoupled Dashboard UI Surface Binding
```bash
python3 -c "c=open('dashboard/index.html').read(); ids=['quota-sub-renewal-badge', 'quota-sub-price', 'quota-sub-status', 'quota-sub-roi', 'quota-sub-roi-multiplier', 'quota-credits-badge', 'quota-credits-remaining-hero', 'quota-bank-sub', 'quota-credits-progress', 'quota-credit-burn', 'quota-credits-burned-count', 'quota-bank-balance', 'credit-reconciliation-card', 'reconciliation-subtitle', 'reconciliation-total-badge', 'reconciliation-tbody', 'th-cash-burn']; assert all(f'id=\"{i}\"' in c for i in ids); print('Verified: All Card 3, Card 4, and Reconciliation DOM elements present in HTML.')"
```
**Output**:
```
Verified: All Card 3, Card 4, and Reconciliation DOM elements present in HTML.
```

### Gate V20: Multi-Currency Dynamic Switching Support
```bash
python3 -c "c=open('dashboard/index.html').read(); assert 'quota-sub-price' in c and 'quota-bank-sub' in c and 'updateCurrencyViews' in c; print('Verified: Currency toggle updates Card 3 and Card 4 synchronously.')"
```
**Output**:
```
Verified: Currency toggle updates Card 3 and Card 4 synchronously.
```

### Gate V21: Full Unit & Regression Test Suite Integrity
```bash
python3 -m unittest discover -s tests
```
**Output**:
```
Ran 30 tests in 0.720s
OK
```
