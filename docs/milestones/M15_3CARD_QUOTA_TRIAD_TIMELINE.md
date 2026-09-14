# Milestone Slice M15: 3-Card Single-Row Quota Triad, Marker Time-Clustering & Trajectory Downsampling

- **Status**: Completed
- **Date**: 2026-09-08
- **Branch**: `feat/timeline-ux-refinement`
- **ADR Reference**: ADR-027
- **Mathematical Invariant**: Milestone-Preserving Full-Window Quota Age-Out Trajectory (Spans $0\text{m}$ to $300\text{m}$, preserves top token spikes $>50\text{k}$ tokens, Safe Zone $50\%$, Comfortable $80\%$, and completes to $100\%$ capacity).

---

## 1. Architectural Objectives & Invariants

1. **3-Card Single-Row Quota Triad (`dashboard/index.html`)**:
   - Eliminated the isolated, detached full-width recovery timeline card located below the provider silos.
   - Relocated `#recovery-timeline-card` into the `#dual-provider-quotas-section` CSS grid (`repeat(auto-fit, minmax(320px, 1fr))`) as the 3rd child `.quota-box` alongside Gemini Models and Claude & GPT Models.
   - Saves ~300px of dead vertical scrolling, placing all primary quota status, fallback capacity, and temporal recovery horizons above the fold.

2. **Milestone-Preserving Trajectory Downsampling (`src/aggregator.py`)**:
   - Diagnosed and resolved the root-cause truncation bug where `trajectory_points[:50]` truncated 850+ turn sessions into an early 2-minute burst ($T \approx 129\text{m}$), causing the SVG graph to draw a flat line at $50\%$ all the way to $5\text{h}$ and omitting the $+268\text{k}$ turn at $192\text{m}$.
   - Implemented `downsample_trajectory_points()`:
     - Retains immediate upcoming turns (first 3 points for live countdown badges).
     - Retains window-closing turns (last 2 points reaching $100\%$ capacity at $300\text{m}$).
     - Retains top 15 largest individual turn roll-offs by `tokens_recovered` across the entire 5-hour window.
     - Retains turns crossing the $50\%$ Safe Zone and $80\%$ Comfortable Zone thresholds.
     - Performs stratified 15-minute uniform bucket sampling across the 20 intervals.
     - Produces a compact, strictly monotonic array ($\le 60$ points) spanning the full 5-hour horizon.

3. **Edge-to-Edge Hero Card & Expanded SVG Plotting Area (`dashboard/index.html`)**:
   - Replaced cramped 130px "box-in-a-box" letterbox sub-container with edge-to-edge container (`height: 175px`) directly on card surface.
   - Calibrated SVG viewBox to `0 0 380 160` with plot dimensions $336\text{px} \times 122\text{px}$ (+54% vertical plot expansion), providing extensive vertical breathing room for 0% to 100% capacity step curves.
   - Simplified card header into an uncluttered single line: left `⏱ 5-Hour Recovery` + dynamic Safe Zone status badge (`#badge-safe-zone`), right `[🔄 30s]` auto-refresh button.
   - Organized secondary metrics into a sleek subtitle strip (`#badge-next-recovery` and `#badge-full-refresh`).
   - Clustered turns occurring within $\pm 4$ minutes into unified milestone nodes, eliminating stacked circle collisions.
   - Distinguished major roll-offs ($>100\text{k}$ tokens aggregate or $>50\text{k}$ single turn) with golden/amber markers (`#f59e0b`) and standard turns with emerald dots (`#10b981`).
   - Themed SVG grid and tick lines using `var(--card-border)` for seamless light/dark theme contrast.
   - Polished single-line footer with top divider: `⭐ Largest drop-off` + `● Synced`.

4. **Context Caching TTL vs. Sliding-Window Quota Specification**:
   - Updated `docs/TELEMETRY_SPEC.md` §9 and `docs/SYSTEM_DESIGN.md` §8 to formally document that 5-hour quota recovery is purely a mathematical moving summation rate limiter ($\text{Used}(T) = \sum_{t > T - 5\text{h}} \text{Cost}(t)$), completely separate from server-side prompt prefix cache TTL (typically 1 hour).

---

## 2. Verified Acceptance Gates (VDONE.md)

1. **Gate V61**: Milestone-Preserving Downsampling & Full-Window Trajectory Span (`python3 -m unittest tests.test_aggregator.TestAggregator.test_downsample_trajectory_points_full_window_span`). (PASS)
2. **Gate V62**: 3-Card Single-Row Quota Layout DOM Verification in `dashboard/index.html` (`#recovery-timeline-card`, `.quota-box`, `repeat(auto-fit, minmax(320px, 1fr))`, `#svg-recovery-chart`). (PASS)
3. **Gate V63**: Full Regression & Integration Test Suite Integrity (`python3 -m unittest discover -s tests`: 75/75 tests passing in 1.400s). (PASS)
