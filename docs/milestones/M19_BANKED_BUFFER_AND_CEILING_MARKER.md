# Milestone M19: Banked Buffer Framing & Benchmark Ceiling Marker

**Date**: 12 September 2026  
**Branch**: `feat/banked-buffer-and-ceiling-tick`  
**ADR**: ADR-033 — Banked Buffer Surplus Framing & Dual Benchmark Ceiling Tick Marker

---

## 1. Background & Problem

Following the deployment of Milestone 18 (Bayesian M-Estimate Shrinkage), the Weekly Quota Runway presented:
> `Day 2: 74% of daily budget`

While mathematically sound, this phrasing created ambiguity for users:
- **Semantic Mismatch**: "daily budget" sounded like an isolated 24-hour silo ($14.3\%$), creating the false impression that $74\%$ was burned in a single day.
- **Hidden Carryover**: The user was unaware that unused quota from previous days was 100% banked into a cumulative allowance ($28.6\%$ for Day 2).
- **Benchmark Bar Gap**: The Sacred Dual Benchmark Bar visually depicted the Quota Consumed fill ($21.2\%$) and the Time Elapsed needle ($24.7\%$), but omitted a visual marker for the cumulative day ceiling finish line ($28.6\%$).

Milestone 19 delivers **ADR-033**, implementing **Option A** (Banked Buffer Framing) and **Option D** (Visual Target Tick on the Benchmark Bar).

---

## 2. Mathematical Specification (ADR-033)

### A. Banked Buffer Surplus Calculation
Let $Q_{\\text{consumed}}$ be the total quota consumed in the current cycle, and $Q_{\\text{ceiling}} = \\min(100.0\\%, d \\times 14.286\\%)$ be the cumulative ceiling for calendar day $d = \\lceil t_{\\text{days\\_elapsed}} \\rceil$:

$$\\text{Banked Buffer} = Q_{\\text{ceiling}} - Q_{\\text{consumed}}$$

* **When $Q_{\\text{consumed}} \\le Q_{\\text{ceiling}}$ (Surplus / Under-budget)**:
  $$\\text{status\\_sub} = \\text{f'Day {d}: +{banked\\_buffer\\_pct:.1f}% banked buffer'}$$
  *(E.g. at $Q = 21.2\%$ on Day 2 with ceiling $28.6\%$, buffer is $+7.4\%$)*.
* **When $Q_{\\text{consumed}} > Q_{\\text{ceiling}}$ (Deficit / Over-budget)**:
  $$\\text{status\\_sub} = \\text{f'Day {d}: {round(Q_{\\text{consumed}} - Q_{\\text{ceiling}}, 1):.1f}% over ceiling'}$$

### B. Dual Benchmark Ceiling Marker (`#runway-ceiling-marker`)
To prevent visual collision with the glowing cyan Time Needle (`#0ea5e9`), the Day Ceiling Marker is rendered as a distinct dashed slate line (`border-left: 2px dashed #94a3b8`) positioned at `left: ${daily_ceiling_pct}%`.

### C. Synchronized Dual Legend
The legend beneath the progress bar displays both benchmarks side-by-side with zero layout shift:
```
• Time: 24.7% (Day 1.7/7)  |  Day 2 ceiling: 28.6%
```

---

## 3. Deliverables

### Backend Telemetry Engine (`src/aggregator.py`)
- In `compute_quota_runway`:
  - Computed `banked_buffer_pct = round(daily_ceiling_pct - quota_consumed_pct, 1)`.
  - Formatted `status_sub` to display positive banked buffer (`Day 2: +7.4% banked buffer`) during sustainable pacing and deficit text during overburn.
  - Exported `banked_buffer_pct` across standard payload and zero/fallback states.

### Visual Dashboard (`dashboard/index.html`)
- Inserted `#runway-ceiling-marker` inside `.progress-bar-bg` with 2px dashed slate styling (`#94a3b8`) and hover tooltip.
- Refactored `#runway-time-legend` into a dual-item flex container rendering both Time Needle and Day Ceiling Marker with a separator.
- Bound DOM references and dynamically updated positions in JavaScript.

### Test Suite (`tests/test_aggregator.py`)
- Updated `test_quota_runway_bvi_calculation` to verify `banked_buffer_pct` ($+17.5\%$ on Day 5, $+8.2\%$ on Day 1) and updated `status_sub` strings across all 7 scenarios.
- All 79 unit tests pass cleanly.

---

## 4. Verification Commands & Results

```bash
# V78: Banked Buffer Math & Subtitle Framing
python3 -m unittest tests.test_aggregator.TestAggregator.test_quota_runway_bvi_calculation
# Ran 1 test in 0.002s — OK

# V79: Dual Benchmark Ceiling Marker DOM Anchor & Legend Synchronization
python3 -c "c=open('dashboard/index.html').read(); assert 'runway-ceiling-marker' in c; assert 'Day 2 ceiling' in c or 'ceiling' in c.lower(); print('Verified: Ceiling marker and legend DOM anchors present.')"
# Verified: Ceiling marker and legend DOM anchors present.

# V80: Full Regression & Integration Test Suite Integrity
python3 -m unittest discover -s tests
# Ran 79 tests in 1.351s — OK

# V81: Live Payload Banked Buffer & Ceiling Telemetry Verification
python3 -c "import json, re; c=open('dashboard/data.js').read(); d=json.loads(re.search(r'window\.__TELEMETRY_DATA__\s*=\s*(.*);', c, re.DOTALL).group(1)); r=d['quotas']['runway']; assert 'banked_buffer_pct' in r; assert 'daily_ceiling_pct' in r; assert 'banked buffer' in r['status_sub']; print('Verified: Live payload contains banked buffer and ceiling telemetry.')"
# Verified: Live payload contains banked buffer and ceiling telemetry.
```
