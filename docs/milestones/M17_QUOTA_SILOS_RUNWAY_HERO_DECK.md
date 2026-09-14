# Milestone M17: Promoted 3-Panel Quota Silos & Runway Governor Hero Deck

**Date**: 10 September 2026  
**Branch**: `feat/weekly-quota-exhaustion`  
**ADR**: ADR-031 — Promoted 3-Panel Provider Quota Silos & Runway Governor Hero Deck

---

## 1. Background & Architectural Rationale

Following empirical weekly quota exhaustion and multi-provider usage dynamics (ADR-028, ADR-030), the top-level UX required a decisive hierarchy inversion. Telemetry and quota headroom across multi-model providers (Gemini, Claude, GPT) represent the primary operational cockpit for developers running high-volume autonomous agents and interactive sessions.

### Key Architectural Invariants
1. **Hero Hierarchy Inversion**:
   - The 3-panel command deck (`#dual-provider-quotas-section`) is promoted to the top hero position directly under `<header>` and above `.tab-nav`.
   - The secondary 4-box macro banner (`.quota-banner`) and the historical SVG recovery curve card (`#recovery-timeline-card`) are moved below the navigation tabs into the `Quotas & Telemetry` tab view (`#view-quotas`).
2. **3-Panel Balanced Topology**:
   - **Left Wing (`#provider-card-gemini`)**: Google Gemini Track (Flash, Pro, Subagents) displaying Weekly Allowance and 5-Hour Burst headroom with exhaustion state badges.
   - **Center Anchor (`#provider-card-runway`)**: Weekly Quota Runway & Throttle Governor.
     - **Sacred Dual-Benchmark Bar**: Quota consumed percentage fill against a static vertical calendar time elapsed needle. Units and scale remain strictly uniform.
     - **Burn Velocity Index (BVI)**: Real-time ratio of consumed quota percentage to calendar time percentage elapsed (\(\text{BVI} = \frac{\% \text{ Quota Consumed}}{\% \text{ Time Elapsed}}\)).
     - **Target Daily Budget**: Sustainable daily consumption percentage (\(\frac{\text{Remaining } \%}{\text{Days Left}}\)).
     - **Exhaustion Forecast**: Extrapolated depletion ETA ("Survives to reset" vs. "Exhausts Xd early").
     - **In-Place Burst Governor**: Permanent `h-10` (38px) footer container displaying nominal green state or an active amber cooldown clock with live 1-second ticks that self-resolves at `00:00` without layout shift.
   - **Right Wing (`#provider-card-claude`)**: Anthropic & OpenAI Track (Claude 3.7 Sonnet, Claude 3 Opus, GPT-4o) displaying Track 2 weekly allowance and 5-hour burst capacity.
3. **Decoupled Telemetry Separation (ADR-024)**:
   - `dashboard/index.html` remains clean, static, cacheable presentation markup.
   - Dynamic telemetry state is injected solely via `dashboard/data.js` (`window.__TELEMETRY_DATA__`).

---

## 2. Deliverables

### Backend Engine (`src/aggregator.py`)
1. **`compute_quota_runway(quotas, now=None)`**:
   - Computes cycle boundaries based on the Thursday 19:00 BST reference anchor (`ANCHOR_CYCLE_START`).
   - Determines `calendar_time_elapsed_pct` and `calendar_days_remaining`.
   - Calculates `burn_velocity_index` with boundary-safe clamping at \(T < 0.5\%\).
   - Computes `target_daily_budget_pct` and `exhaustion_eta`.
   - Formulates status descriptors (`'CRITICAL'`, `'ELEVATED'`, `'NOMINAL'`, `'CYCLE_START'`).
   - Surfaces 5h burst governor state (`burst_cooldown_active`, `burst_seconds_remaining`, `burst_used_pct`).
2. **Telemetry Wiring**:
   - Embedded into `providers_quotas["gemini"]["runway"]` and exposed at `quotas["runway"]`.

### Visual Dashboard (`dashboard/index.html`)
1. **DOM Structure**:
   - Reordered DOM: `<header>` $\rightarrow$ `#dual-provider-quotas-section` $\rightarrow$ `.tab-nav` $\rightarrow$ `#view-quotas` (`.quota-banner`, `#recovery-timeline-card-section`).
   - Replaced former 3rd card in `#dual-provider-quotas-section` with `#provider-card-runway` in the center and `#provider-card-claude` on the right.
2. **Client-Side Rendering & Governor Clock**:
   - Bound runway metrics (`runway-bvi-val`, `runway-status-badge`, `runway-time-needle`, `runway-quota-fill`, `runway-daily-budget`, `runway-exhaust-eta`, `runway-burst-footer`).
   - Implemented `startBurstCountdown(secondsRemaining)` with 1-second interval self-clearing at `00:00`.

### Unit Tests (`tests/test_aggregator.py`)
- Added `test_quota_runway_bvi_calculation` covering:
  - Nominal burn rate (\(\text{BVI} \approx 0.93\times\))
  - Elevated burn rate (\(\text{BVI} \approx 1.24\times\))
  - Critical overburn (\(\text{BVI} \approx 1.52\times\))
  - Opening cycle boundary (\(T = 0.0\%\))
  - Active burst cooldown timer propagation

---

## 3. Verification Commands & Results

```bash
# V70: Quota Runway & BVI Calculation
python3 -m unittest tests.test_aggregator.TestAggregator.test_quota_runway_bvi_calculation
# Ran 1 test in 0.000s — OK

# V71: Inverted Page Layout & DOM Hierarchy
python3 -c "c=open('dashboard/index.html').read(); header_pos=c.find('<header'); hero_pos=c.find('id=\"dual-provider-quotas-section\"'); tab_pos=c.find('class=\"tab-nav\"'); banner_pos=c.find('class=\"quota-banner\"'); assert header_pos < hero_pos < tab_pos < banner_pos; ids=['provider-card-gemini', 'provider-card-runway', 'provider-card-claude', 'runway-bvi-val', 'runway-dual-bar', 'runway-burst-footer']; assert all(i in c for i in ids); print('Verified: Hero deck promoted above tabs; all DOM anchors present.')"
# Verified: Hero deck promoted above tabs; all DOM anchors present.

# V72: Full Test Suite Integrity
python3 -m unittest discover -s tests
# Ran 79 tests in 0.968s — OK

# V73: Byte-Deterministic Exporter Integrity
python3 scripts/export_dashboard.py --dry-run
# [DRY-RUN] Discovered 100 DBs, extracted 100 active sessions — OK
```

---

## 4. Mathematical Model Summary

| Metric | Formula | Description |
| :--- | :--- | :--- |
| **Time Elapsed %** | \(T = \frac{t_{\text{now}} - t_{\text{start}}}{t_{\text{end}} - t_{\text{start}}} \times 100\) | Calendar progress through Thursday-to-Thursday cycle. |
| **Quota Consumed %** | \(Q = 100 - \text{Remaining } \%\) | Accumulated Gemini API rate-card burn. |
| **Burn Velocity Index (BVI)** | \(\text{BVI} = \frac{Q}{T}\) | Burn speed normalized against time. Nominal = 1.00x. Clamped at \(T < 0.5\%\). |
| **Target Daily Budget %** | \(B_{\text{day}} = \frac{\text{Remaining } \%}{\text{Days Remaining}}\) | Sustainable quota allowance per remaining calendar day. |
| **Exhaustion Forecast (Days)** | \(D_{\text{exhaust}} = \frac{\text{Remaining } \%}{Q / \text{Days Elapsed}}\) | Projected runway before 0% quota exhaustion. |
