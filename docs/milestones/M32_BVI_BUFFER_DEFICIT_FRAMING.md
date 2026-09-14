# Milestone 32: Velocity BVI Dual-Line Framing & Buffer Deficit Parity

**Status**: Completed  
**Branch**: `feat/bvi-buffer-deficit-framing`  
**ADR Citation**: [ADR-045](../../docs/HANDOVER.md#adr-table)  
**Acceptance Gates**: V165–V170 in [`VDONE.md`](../../VDONE.md)  

---

## 1. Executive Summary

Milestone 32 resolves the semantic and mathematical ambiguity in the Weekly Quota Runway Velocity (BVI) card subtitle (`Day X: Y.Y% over ceiling`):

1. **Arithmetic Disambiguation (ADR-045)**:
   - Previously, when quota consumption exceeded the cumulative day ceiling, the subtitle rendered `Day 3: 12.3% over ceiling`.
   - Users naturally interpreted "12.3% over" as a relative ratio ($\text{Ceiling} \times 1.123 = 48.2\%$), whereas the underlying computation was a subtraction in absolute percentage points of the weekly quota pool ($55.2\% - 42.9\% = 12.3\text{ pp}$, which is actually $+28.7\%$ over ceiling).
2. **Dual-Line Ground-Truth Framing (Format 1)**:
   - **Line 1 (Verdict)**: Signed percentage with explicit outcome:
     - Deficit (Amber/Red): `Day {day_index}: -{deficit_pct:.1f}% deficit`
     - Surplus (Green): `Day {day_index}: +{banked_buffer_pct:.1f}% buffer`
   - **Line 2 (Arithmetic Proof)**: Unambiguous ground-truth operands:
     - `({quota_consumed_pct:.1f}% vs {daily_ceiling_pct:.1f}%)`
   - **Cognitive Clarity**: Exposing $(55.7\% \text{ vs } 42.9\%)$ immediately proves $55.7 - 42.9 = 12.8$, removing any ambiguity about whether $12.8\%$ is a ratio or a difference.
3. **Responsive Frontend Rendering (`dashboard/app.js`)**:
   - Parses the parenthetical context in `runway.status_sub` to render Line 1 in the card's alert color (red/amber/green) and Line 2 in secondary muted gray (`var(--text-muted)` at `0.62rem`).
   - Fits comfortably on mobile viewports (100–120px card width) and full desktop grids without wrapping or layout shifts.
   - Binds full status string as native HTML `title` tooltip on hover.

---

## 2. Changes Implemented

### Telemetry Engine (`src/aggregator.py`)
- Refactored `compute_quota_runway`:
  - Formatted `status_sub` across zero-boundary, surplus, and deficit states to adhere to Format 1:
    - Surplus: `Day {d}: +{buf:.1f}% buffer ({consumed:.1f}% vs {ceiling:.1f}%)`
    - Deficit: `Day {d}: -{def:.1f}% deficit ({consumed:.1f}% vs {ceiling:.1f}%)`
    - Depleted: `Quota depleted ({consumed:.1f}% vs {ceiling:.1f}%)`
    - Zero/Fallback: `Day 1: +14.3% buffer (0.0% vs 14.3%)`

### Visual Dashboard (`dashboard/app.js`)
- In `runwayBviSub` rendering logic:
  - Added regex parser to extract verdict and parenthetical operand context.
  - Rendered Line 1 in severity alert color and Line 2 in muted secondary gray (`style="font-size: 0.62rem; color: var(--text-muted); margin-top: 1px;"`).
  - Added hover tooltip (`runwayBviSub.title = runway.status_sub`).

### Regression Test Suite (`tests/test_aggregator.py`)
- Updated `test_quota_runway_bvi_calculation` across all 7 runway test cases to verify Format 1 strings.
- 100% of all unit tests pass cleanly.

---

## 3. Verification & Acceptance Gates

```bash
# V165: BVI Subtext Deficit vs. Buffer Formatting Parity
python3 -c "import datetime; from src.aggregator import compute_quota_runway; bounds = {'cycle_start_utc': '2026-08-29T18:00:00+00:00', 'cycle_end_utc': '2026-09-05T18:00:00+00:00'}; ref = datetime.datetime(2026, 9, 3, 14, 0, 0, tzinfo=datetime.timezone.utc); r_amb = compute_quota_runway({'remaining_pct': 28.0, 'used_pct': 72.0}, bounds, None, ref); assert r_amb['status_sub'] == 'Day 5: -0.5% deficit (72.0% vs 71.5%)', r_amb['status_sub']; r_grn = compute_quota_runway({'remaining_pct': 46.0, 'used_pct': 54.0}, bounds, None, ref); assert r_grn['status_sub'] == 'Day 5: +17.5% buffer (54.0% vs 71.5%)', r_grn['status_sub']; print('Verified: Deficit and buffer status_sub formatting with (actual vs ceiling) intact.')"

# V166: Unit Test Suite Regression & Scenario Coverage
python3 -m unittest tests.test_aggregator.TestAggregator.test_quota_runway_bvi_calculation

# V167: Frontend Responsive Dual-Line Rendering
python3 -c "c=open('dashboard/app.js').read(); assert 'runwayBviSub.innerHTML' in c; assert 'text-muted' in c; print('Verified: app.js renders dual-line BVI subtext.')"

# V168: Byte-Deterministic Exporter & Live Telemetry Verification
python3 scripts/export_dashboard.py --no-live-quota --dry-run

# V169: Comprehensive Documentation, Milestone & Model Roster Integrity
python3 -m unittest tests/test_docs_integrity.py && python3 -m unittest tests/test_model_roster_integrity.py

# V170: Full Test Suite Integrity
python3 -m unittest discover -s tests
```
