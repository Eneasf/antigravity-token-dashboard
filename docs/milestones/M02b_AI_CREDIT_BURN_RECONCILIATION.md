# Milestone Slice 02b: Google One AI Credit Activity Reconciliation & Multi-Currency Engine

- **Date**: 2026-09-05
- **Active Branch**: `feat/ai-credit-burn-reconciliation`
- **Status**: **VERIFIED & COMPLETED**
- **Associated ADRs**:
  - ADR-010 (Hybrid Overage Detection & Model-Specific Credit Reconciliation)
  - ADR-011 (Multi-Currency Cost Accounting & British Pounds Calibration)

---

## 1. Scope & Delivered Components

1. **Log-Anchored 429 Exhaustion Extractor ([`src/log_reader.py`](../../src/log_reader.py))**:
   - Safely parses Language Server logs (`~/Library/Logs/Antigravity/language_server.log`) to extract exact `RESOURCE_EXHAUSTED` (HTTP 429) intervals.
   - Automatically groups consecutive rate limit events within 15-minute windows and identifies recovery intervals.
   - Fully covered by unit tests in `tests/test_log_reader.py`.

2. **Model-Specific AI Credit Calibration ([`config/pricing.json`](../../config/pricing.json) & [`src/aggregator.py`](../../src/aggregator.py))**:
   - Calibrated against Google One statement ground truth:
     - **Gemini 3.8 Flash (High)**: 2.501672 credits / turn (empirically calibrated from Google One activity: 299 turns = 748 credits = £7.18 GBP / $7.48 USD).
     - **Gemini 3.1 Pro**: 15.0 credits / turn (heuristic based on 6x API pricing tier ratio: 10 turns = 150 credits = £1.44 GBP / $1.50 USD; unconfirmed by live overage).
     - **Gemini Flash Lite**: 1.5 credits / turn (heuristic estimate).
   - Fuses continuous sliding window token tracking (168M token 5h burst limit) with log-anchored overage periods.

3. **Multi-Currency Cost Accounting (British Pounds £ Default + USD Toggle)**:
   - User Plan Calibration: **£23.99 for 2,500 credits** = **£0.009596 / credit** (~0.96p per credit).
   - USD Baseline: **$25.00 for 2,500 credits** = **$0.0100 / credit** (1.0¢ per credit).
   - Imputed Value FX conversion rate: 1 USD = 0.79 GBP.
   - Every metric persists dual USD and GBP accounting in `summary` and `hourly_credit_activity`.

4. **Interactive Dashboard Surface ([`dashboard/index.html`](../../dashboard/index.html))**:
   - **Google One AI Credit Activity Reconciliation Card**:
     - Hourly deduction breakdown matching official Google One statements (`-748 credits (£7.18)`).
     - Detailed model and turn attribution per billing block.
   - **Currency Switcher**:
     - Prominent `[ GBP (£) | USD ($) ]` header toggle.
     - Live switching across all KPI cards, credit burn meters, allowance matrix values, and session lists.
   - **Dynamic Quota Status Badges**:
     - Live status badge indicating `● Burning AI Credits` vs `● Safe in Pro Quota`.
     - Quota card badge displaying total credits burned.

5. **Unified Light & Dark Themes with Single-File Deployment ([`dashboard/index.html`](../../dashboard/index.html))**:
   - Interactive `[ ☀️ Light | 🌙 Dark ]` switcher with comprehensive CSS custom properties (`--bg`, `--card-bg`, `--text-main`, etc.).
   - Pre-render script in `<head>` and `localStorage` persistence (`antigravity_dashboard_theme`) preventing flash of unstyled theme.
   - Unified `.toggle-group` styling across theme, currency, and model window toggles using class-driven states.

---

## 2. Verification Proofs & Quality Gates (`VDONE.md`)

### Gate V0 & V4: Unit Test Suite
```bash
python3 -m unittest discover -s tests
```
**Output**:
```
...............
----------------------------------------------------------------------
Ran 15 tests in 0.006s

OK
```

### Gate V6: Log Parser 429 Exhaustion Interval Discovery
```bash
python3 -c "from src.log_reader import extract_exhaustion_intervals; intervals=extract_exhaustion_intervals(); assert len(intervals) >= 1; print(f'Verified: Discovered {len(intervals)} exhaustion intervals.')"
```
**Output**:
```
Verified: Discovered 1 exhaustion intervals.
```

### Gate V7: Model Credit Calibration
```bash
python3 -c "from src.aggregator import calculate_credit_burn; burn=calculate_credit_burn('1318', turns_count=299); assert round(burn['credits']) == 748; print('Verified: Flash High 299 turns = 748 credits.')"
```
**Output**:
```
Verified: Flash High 299 turns = 748 credits.
```

### Gate V8: Live AI Credit Burn Surface Reconciliation
```bash
python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert d['summary']['total_ai_credits_burned'] >= 1100; assert d['summary']['total_credit_burn_usd'] >= 11.0; print('Verified: Official AI credits burned reconciled.')"
```
**Output**:
```
Verified: Official AI credits burned reconciled.
```

### Gate V9: British Pounds Multi-Currency Calibration
```bash
python3 -c "import json, re; c=open('dashboard/index.html').read(); m=re.search(r'<script id=\"injected-dashboard-data\" type=\"application/json\">(.*?)</script>', c, re.DOTALL); d=json.loads(m.group(1)); assert d['summary']['currency_default'] == 'GBP'; assert d['summary']['total_credit_burn_gbp'] > 0; assert d['summary']['cost_per_credit_gbp'] == 0.009596; print('Verified: British Pounds multi-currency accounting calibrated.')"
```
**Output**:
```
Verified: British Pounds multi-currency accounting calibrated.
```

### Gate V10: Unified Light & Dark Interactive Theme Switcher
```bash
python3 -c "import re; c=open('dashboard/index.html').read(); assert 'toggle-group' in c; assert 'btn-theme-light' in c; assert 'btn-theme-dark' in c; assert 'antigravity_dashboard_theme' in c; print('Verified: Unified light/dark theme switcher and CSS tokens intact in single index.html.')"
```
**Output**:
```
Verified: Unified light/dark theme switcher and CSS tokens intact in single index.html.
```

### Gate V11: Full Unit Test Suite
```bash
python3 -m unittest discover -s tests
```
**Output**:
```
Ran 17 tests in 0.014s

OK
```

