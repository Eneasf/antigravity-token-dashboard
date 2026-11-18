# Milestone Slice M13: Interactive Sliding-Window Quota Age-Out Timeline & Visual Recovery Gauge

- **Status**: Completed
- **Date**: 2026-09-07
- **Branch**: `feat/sliding-window-recovery-timeline`
- **ADR Reference**: ADR-025
- **Mathematical Invariant**: Continuous 5-Hour Sliding-Window Quota Age-Out (Turns age out strictly at `turn_timestamp + 5 hours`; quota capacity recovers incrementally turn-by-turn).

---

## 1. Architectural Objectives & Invariants

1. **Continuous Sliding-Window Mechanics vs. "All-or-Nothing" Misconception (ADR-025)**:
   - Antigravity 5-hour quota does not reset in an "all-or-nothing" fashion at a fixed clock boundary.
   - Instead, it operates as a strict mathematical sliding window: any turn executed at timestamp $T$ rolls out of the active 5-hour window evaluation at $T + 5\text{ hours}$.
   - Quota headroom recovers continuously and incrementally as historical turns cross the 5-hour age-out boundary.
2. **Backend Trajectory Projection Engine (`src/aggregator.py`)**:
   - Implemented `compute_window_recovery_trajectory()`:
     - Partitions the upcoming 5-hour recovery window $[T_{\text{now}}, T_{\text{now}} + 5\text{h}]$ into 20 uniform 15-minute intervals.
     - Projects the cumulative token drop-offs and available quota headroom percentage at each step:
       $$\text{Available Pct}(t) = \min\left(100.0, \frac{\text{Capacity} - (\text{Used} - \text{Cumulative Recovered}(t))}{\text{Capacity}} \times 100\right)$$
     - Guarantees strict mathematical monotonicity: $\text{Available Pct}(t_{i+1}) \ge \text{Available Pct}(t_i)$.
     - Derives milestone arrival times:
       - `minutes_to_safe_zone`: Minutes until quota headroom reaches $\ge 50\%$.
       - `minutes_to_comfortable_zone`: Minutes until quota headroom reaches $\ge 80\%$.
       - `minutes_to_full_recovery`: Minutes until quota headroom reaches $100\%$ (all current turns aged out).
     - Extracts top upcoming turn roll-offs with exact timestamps, model names, and token recovery counts.
     - Attached to `rolling_5h`, `gemini_5h`, and `cg_5h` quota payload dictionaries.
3. **Responsive Visual SVG Gauge (`dashboard/index.html`)**:
   - Designed `#recovery-timeline-card` featuring:
     - Metric header: Available Headroom %, Next Drop-Off countdown, Safe Zone arrival time, and Full Recovery ETA.
     - High-contrast responsive SVG container with viewBox `0 0 1000 240`.
     - 4 horizontal threshold guide-rails: 100% (Full), 80% (Comfortable), 50% (Safe Zone alert in amber), 25%, and 0%.
     - Step-line (`path` with step-after interpolation) and semi-transparent area fill gradient reflecting the staircase nature of discrete turn roll-offs.
     - Vertical scrubber line, interactive node circles, and floating inspection tooltip showing interval delta, tokens recovered, and time remaining.
     - Next roll-off badges list showing model, token count, and exact minute countdown.
4. **Live Client-Side Clock Ticker & Seamless Auto-Refresh (ADR-024 / ADR-025)**:
   - Client-side 30-second interval ticker (`updateTimelineTick()`): updates minute countdowns and incrementally shifts projected available capacity without reloading the page.
   - Decoupled `data.js` script reloading (`checkAndReloadTelemetry()`): dynamic cache-busted `<script>` tag injection reloads telemetry seamlessly in the background when new turns are recorded by Antigravity or the watcher daemon.
   - Tab-focus auto-refresh (`document.addEventListener('visibilitychange', ...)`): immediately checks for updated data when the user switches back to the dashboard tab.
   - Header toggle button: `[ 🔄 Live Auto-Refresh: ON (30s) ]` for user control.

---

## 2. Verified Acceptance Gates (VDONE.md)

1. **Gate V53**: Recovery Trajectory Mathematical Integrity & Monotonicity (`python3 -m unittest tests.test_aggregator.TestAggregator.test_recovery_trajectory_monotonicity`). (PASS)
2. **Gate V54**: Injected Trajectory Schema Attainment verified against active decoupled data projection `dashboard/data.json` across all quota windows (`rolling_5h`, `gemini_5h`, `cg_5h`). (PASS)
3. **Gate V55**: SVG Timeline DOM Elements & Container verified in `dashboard/index.html` (`#recovery-timeline-card`, `#svg-recovery-chart`, `#svg-recovery-container`, `#svg-step-area`, `#svg-step-line`). (PASS)
4. **Gate V56**: Live 30s Clock Tick & Tab Focus Auto-Refresh Mechanisms verified in `dashboard/index.html` (`updateTimelineTick`, `visibilitychange`, `btn-auto-refresh`, dynamic `data.js` reload). (PASS)
5. **Gate V57**: Full Regression & Integration Test Suite Integrity (`python3 -m unittest discover -s tests`: 72/72 tests passing in 1.207s). (PASS)
