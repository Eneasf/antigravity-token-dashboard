# Milestone M18: Bayesian M-Estimate Shrinkage & Diurnal Daily-Budget Pacing

**Date**: 10 September 2026  
**Branch**: `feat/weekly-quota-exhaustion`  
**ADR**: ADR-032 — Bayesian M-Estimate Shrinkage & Diurnal Daily-Budget Pacing for Quota Runway

---

## 1. Background & Empirical Problem

At the opening of each weekly quota cycle (Thursday 19:00 BST reset), developers who engage in concentrated 1–3 hour coding sessions encountered an acute **cycle-start false alarm**:
- In the user's live session on Thursday evening, **$6.1\%$** of weekly quota was consumed in **$2.5$ hours** ($T = 1.5\%$ of the 168-hour week).
- The daily sustainable budget is $\approx 14.3\%/\text{day}$ ($100\% / 7$). The user consumed less than half of Day 1's budget (43%).
- However, raw point-slope velocity $\text{BVI} = \frac{6.1\%}{1.5\%} = \mathbf{4.07\times}$ triggered a red **`⛔ Overburn (4.07x)`** alarm and extrapolated exhaustion to **`~Sat 10:43 (Exhausts 5.3d early!)`** because it assumed non-stop 24/7 prompt execution with zero sleep.
- Additionally, a CSS styling issue in `dashboard/index.html` left the subtitle `"Critical overburn"` hardcoded in green text.

Milestone 18 delivers **ADR-032**, replacing raw point-slope division with **Bayesian M-Estimate Shrinkage** coupled with a **Diurnal Daily-Budget Envelope Guardrail**.

---

## 2. Mathematical Specification (ADR-032)

### A. Bayesian M-Estimate Shrinkage ($k = 1.0\text{ day}$)
Rather than dividing raw small sample deltas, empirical burn velocity is blended with an informative prior ($\theta_0 = 14.286\%/\text{day}$ nominal pace):

$$\text{Daily Burn}_{\text{Bayes}} = \frac{Q_{\text{consumed}} + k \cdot \theta_0}{t_{\text{days\_elapsed}} + k \cdot 1.0}$$

$$\text{BVI}_{\text{Bayes}} = \frac{\text{Daily Burn}_{\text{Bayes}}}{\theta_0}$$

* **At $T = 0.1\text{d}$, $Q = 6.1\%$**:
  $$\text{Daily Burn} = \frac{6.1\% + 14.29\%}{0.1 + 1.0} = \frac{20.39\%}{1.1} = 18.54\%/\text{day} \longrightarrow \mathbf{1.29\times}$$
* **At $T = 4.0\text{d}$, $Q = 60.0\%$**:
  $$\text{Daily Burn} = \frac{60.0\% + 14.29\%}{4.0 + 1.0} = \frac{74.29\%}{5.0} = 14.86\%/\text{day} \longrightarrow \mathbf{1.04\times}$$
* **Catastrophic Infinite Loop ($T = 0.125\text{d}$, $Q = 50.0\%$)**:
  $$\text{Daily Burn} = \frac{50.0\% + 14.29\%}{0.125 + 1.0} = 57.1\%/\text{day} \longrightarrow \mathbf{4.00\times} \text{ (Immediate Red Alarm)}$$

### B. Cumulative Daily Allowance Floor (Control Envelope)
Let day index $d = \max(1, \lceil t_{\text{days\_elapsed}} \rceil)$. The cumulative budget ceiling for Day $d$ is:
$$Q_{\text{daily\_ceiling}} = \min(100.0\%, d \times 14.286\%)$$

* **Guardrail Rule**: If $Q_{\text{consumed}} \le Q_{\text{daily\_ceiling}}$, status is **strictly Nominal Green**:
  $$\text{status\_key} = \text{'green'}$$
  $$\text{status\_text} = \text{f'✓ On Track ({bvi:.2f}x)'}$$
  $$\text{status\_sub} = \text{f'Day {d}: {int(round(day\_budget\_used\_pct))}% of daily budget'}$$
* If $Q_{\text{consumed}} > Q_{\text{daily\_ceiling}}$, status escalates to Amber ($\text{BVI} \le 1.3$) or Red ($\text{BVI} > 1.3$).

### C. Realistic Exhaustion Extrapolation
Exhaustion is projected using $\text{Daily Burn}_{\text{Bayes}}$:
$$\text{Days to Exhaustion} = \frac{\text{Quota Remaining}}{\text{Daily Burn}_{\text{Bayes}}}$$

* If $\text{Days to Exhaustion} \ge \text{Days Remaining}$, $\text{ETA} = \text{'None'}$ (`'Survives to reset'`).
* If $Q_{\text{consumed}} \le Q_{\text{daily\_ceiling}}$, caption displays `'Safe buffer (Day d)'` rather than early panic.
* If over cumulative budget, caption displays `'Tight buffer (Xd)'` or `'Exhausts Xd early!'`.

---

## 3. Deliverables

### Backend Telemetry Engine (`src/aggregator.py`)
- Refactored `compute_quota_runway()`:
  - Implemented Bayesian M-estimate daily burn with $k = 1.0$ pseudo-day prior weight.
  - Implemented cumulative daily budget ceiling $Q_{\text{daily\_ceiling}} = \min(100.0, d \times \theta_0)$.
  - Applied the daily allowance guardrail: clamped status to `green` when $Q \le Q_{\text{daily\_ceiling}}$.
  - Computed exhaustion date from smoothed Bayesian velocity.
  - Exported `bvi_raw`, `bvi_bayes`, `day_index`, `daily_ceiling_pct`, `day_budget_used_pct`, and `status_sub`.

### Visual Dashboard (`dashboard/index.html`)
- Fixed subtitle color binding: dynamically applied status color to `runwayBviSub.style.color` (`var(--accent-green)` for green, `#f59e0b` for amber, `#ef4444` for red).
- Rendered contextual day pacing: `Day 1: 52% of daily budget` directly below BVI.

### Unit Tests (`tests/test_aggregator.py`)
- Updated `test_quota_runway_bvi_calculation`:
  - Verified cycle-start Day 0.1 normal session ($Q=6.1\%$) stays green under Day 1 ceiling ($6.1\% \le 14.3\%$) with "Safe buffer (Day 1)".
  - Verified catastrophic Day 1 runaway ($Q=50\%$) immediately breaches ceiling and triggers red alarm ($4.08\times$).
  - Verified mid-cycle sustainable pacing and prior dilution.

---

## 4. Verification Commands & Results

```bash
# V74: Bayesian M-Estimate & Daily Ceiling Guardrail
python3 -m unittest tests.test_aggregator.TestAggregator.test_quota_runway_bvi_calculation
# Ran 1 test in 0.002s — OK

# V75: Dynamic Subtitle Text & Color Binding
python3 -c "c=open('dashboard/index.html').read(); assert 'runwayBviSub.style.color' in c; print('Verified: Subtitle color dynamically bound.')"
# Verified: Subtitle color dynamically bound.

# V76: Full Regression & Integration Test Suite Integrity
python3 -m unittest discover -s tests
# Ran 79 tests in 0.976s — OK

# V77: Live Smoothed Payload Verification
python3 -c "import json, re; c=open('dashboard/data.js').read(); d=json.loads(re.search(r'window\.__TELEMETRY_DATA__\s*=\s*(.*);', c, re.DOTALL).group(1)); r=d['quotas']['runway']; assert r['status_key'] == 'green'; assert 'bvi_bayes' in r; print('Verified: Live payload smoothed and nominal green.')"
# Verified: Live payload smoothed and nominal green.
```

---

## 5. Visual Telemetry Evidence: Before vs. After

| Metric Dimension | Before: Raw Linear Math | After: Bayesian M-Estimate + Daily Ceiling |
| :--- | :--- | :--- |
| **Status Badge** | `⛔ Overburn (4.69x)` (Red Alert) | `✓ On Track (1.41x)` (Emerald Green) |
| **Subtitle Context** | `"Critical overburn"` *(hardcoded green bug)* | `"Day 1: 57% of daily budget"` *(dynamic green)* |
| **Pacing Index** | `4.69x` (Instantaneous 24/7 extrapolation) | `1.41x` (Smoothed Bayesian daily burn) |
| **Exhaustion Date** | `~Sat 04:55 (Exhausts 5.5d early!)` | `~Tue 09:41 (Safe buffer (Day 1))` |
| **Underlying Burn** | 7.5% Consumed in 2.7h ($T = 1.6\%$) | 8.2% Consumed in 2.8h ($T = 1.6\%$) |
| **Daily Allowance** | Ignored (treated as continuous 24h burn) | **Guarded**: Safe pace because $Q \le 14.3\%$ Day-1 ceiling |

### Telemetry Artifacts Stored
* **Before Screenshot**: [`docs/assets/m18_before_raw_overburn.png`](../assets/m18_before_raw_overburn.png)
* **After Screenshot**: [`docs/assets/m18_after_bayesian_smoothed.png`](../assets/m18_after_bayesian_smoothed.png)

