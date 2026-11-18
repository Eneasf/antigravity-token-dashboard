# Milestone 39: Live Token Ticker HUD, White Space Optimization & macOS Menu Bar Monitor

**Milestone Slice Record**  
**Designation**: `M39` / `v1.39.0`  
**Date**: September 2026  
**Status**: Completed  
**Branch**: `feat/live-token-ticker`  
**Associated ADR**: ADR-053  

---

## 1. Context & Motivation

Following the implementation of the 3-second live auto-refresh in Milestone 38, inspection of the web dashboard highlighted visual and functional opportunities:
1. **Prominent White Space in Navigation Bar**: The top tab navigation bar (`.tab-nav`) had ample unutilized horizontal space to the right of the tab buttons (`Now`, `Sessions`, `Projects`, `Swarms & Tools`, `Billing`, `Plan`), creating an uneven visual weight on widescreen displays.
2. **Real-Time Token Ticker Requirement**: With the telemetry watcher and client polling synchronized at 3-second intervals, users requested a dynamic **Live Token Ticker HUD** displaying instant burn velocity (tokens/min, tokens/sec), last turn token footprint, active model name, and elapsed time since the latest interaction.
3. **Bandwidth Invariant (Zero-Bandwidth Micro-Polling)**: The telemetry dataset (`dashboard/data.js`) is ~18.8 MB. Polling `data.js` every 3 seconds would consume ~376 MB/minute of bandwidth. A lightweight carrier was required so that high-frequency polling consumes less than 1 KB per request.
4. **Native macOS Menu Bar Companion**: In addition to the web dashboard, users requested live token burn velocity in the macOS top menu bar monitor (`AntigravityBar`), dynamically surfacing current throughput when actively generating code and collapsing when idle.

---

## 2. Technical Decisions & Architectural Implementation

### 2.1 Telemetry Aggregator Live Velocity & Ticker Math (`src/aggregator.py`)
- Added `compute_live_ticker(db_records, pricing_models=None)`:
  - Scans recent turns within a 5-minute rolling window (`datetime.timedelta(minutes=5)`).
  - Calculates instantaneous token velocity: `burn_rate_tok_per_min` and `burn_rate_tok_per_sec`.
  - Determines active streaming state (`is_streaming = True` if the latest turn occurred within 45 seconds).
  - Resolves internal integer `model_id` (e.g. `'1318'`, `'1016'`) to calibrated human names (e.g. `Gemini 3.8 Flash (High)`) via `pricing_models`.
  - Extracts latest turn metrics: `last_turn_tokens`, `last_turn_prompt`, `last_turn_output`, `last_turn_cached`, `last_turn_thoughts`, `last_turn_ts`, and `seconds_since_last_turn`.
- Attached `live_ticker` block to root telemetry payload in `aggregate_global_telemetry()`.

### 2.2 Zero-Bandwidth Micro-Polling (`dashboard/meta.js`)
- Enriched `scripts/export_dashboard.py` to embed the `ticker` block directly inside `dashboard/meta.js` and `dashboard/meta.json` (~570 bytes).
- Also updated `scripts/build_demo_showcase.py` to inject synthetic live ticker telemetry into `dashboard/meta.demo.js`.
- In `dashboard/app.js`, `checkAndReloadTelemetry()` fetches `meta.js` every 3 seconds:
  - Updates the Token Ticker HUD immediately with zero delay.
  - Compares `meta.payload_sha1` against current hash; `data.js` (~18.8 MB) is **only downloaded when conversation count or hash changes**.
  - Includes a 1-second local clock ticker (`updateTickerClock`) to smoothly increment elapsed seconds (`"X s ago"`) between polls.

### 2.3 Web Dashboard Token Ticker HUD & Flexbox Layout
- **Layout Restructure**:
  - Restructured `.tab-nav` in `dashboard/index.html` and `dashboard/demo.html` into a flex container (`justify-content: space-between`).
  - Left container: `.tab-buttons-group` containing navigation tab buttons.
  - Right container: `#token-ticker-hud` occupying former white space.
- **HUD Component Hierarchy**:
  - `#ticker-beacon`: Animated status dot with `@keyframes pulse-ticker-beacon` (`● LIVE STREAM` in green when active, `● MONITORING` in subtle secondary when idle).
  - `#ticker-rate`: Large tabular monospaced burn rate (`⚡ 2.1M tok/min` or `⚡ 0 tok/min`).
  - `#ticker-delta`: Turn delta pill (`▲ +250.3k tok`) with `@keyframes delta-flash-anim` that flashes bright green on turn change.
  - `#ticker-model`: Subagent/desktop model pill (`Gemini 3.8 Flash (High)`).
  - `#ticker-time`: Real-time clock badge (`🕒 8s ago`).
- **Responsive & Design System Standards**:
  - Full support for dark and light themes, 1px hairline borders (`--color-border`), monospaced tabular numerals (`font-variant-numeric: tabular-nums`).
  - Graceful collapse on narrow viewports (`@media (max-width: 900px)` hides model/delta pills; `@media (max-width: 600px)` wraps cleanly).

### 2.4 Native macOS Menu Bar Monitor (`AntigravityBar`)
- **Telemetry Hook Enrichment (`~/.antigravity_quota_status.json`)**:
  - Added `recent_burn_rate_tok_per_min`, `recent_burn_rate_tok_per_sec`, `last_turn_tokens`, `last_turn_model`, `last_turn_ts`, `is_streaming`, and `seconds_since_last_turn`.
- **Swift Data Model (`StatusModel.swift`)**:
  - Added Codable ticker fields with formatted helpers `formattedBurnRate` (`"2.1M/m"`, `"45k/m"`), `formattedLastTurnTokens` (`"250.3k"`), and `isStreamingActive`.
- **Dynamic Status Bar Title (`StatusBarController.swift`)**:
  - Idle state: `📅 92%  ⚡ 74%`
  - Active/Streaming state: `📅 92%  ⚡ 74%  ▲ 2.1M/m` (with green SF Symbol `arrow.up.right`).
- **Live Token Ticker Card (`PopoverContentView.swift`)**:
  - Added dedicated card in the native popover with live streaming indicator, velocity rate, last turn token footprint, model badge, and elapsed time.

---

## 3. Verifiable Quality Gates (`VDONE.md`)

| Gate | Description | Check Command | Status |
|---|---|---|---|
| **V212** | Telemetry Aggregator & Live Ticker Math | `python3 -c "from src.aggregator import aggregate_global_telemetry... assert 'live_ticker' in res"` | **Passed** |
| **V213** | Lightweight Meta.js Ticker Schema & Status Hook | `python3 -c "assert 'ticker' in open('dashboard/meta.js').read()"` | **Passed** |
| **V214** | Web Dashboard HUD & White Space Layout | `python3 -c "assert 'token-ticker-hud' in open('dashboard/index.html').read()"` | **Passed** |
| **V215** | Frontend 3s Ticker Polling & Delta Flash | `python3 -c "assert 'updateTokenTicker' in open('dashboard/app.js').read()"` | **Passed** |
| **V216** | Swift Menu Bar App Compilation & Bundle | `python3 scripts/build_menubar.py` | **Passed** |
| **V217** | Full Test Suite & Docs Integrity | `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py` | **Passed (214 tests)** |
| **V218** | Live Pipeline Refresh & Daemon Status | `python3 scripts/setup_service.py status && python3 scripts/setup_menubar.py status` | **Passed** |
| **V219** | Working Tree Hygiene & Clean Commits | `git status` | **Passed** |

---

## 4. Key Artifacts Modified & Created

- `src/aggregator.py`: Implemented `compute_live_ticker()` and attached `live_ticker` to global payload.
- `scripts/export_dashboard.py`: Enriched `meta.js` and `~/.antigravity_quota_status.json` with ticker metrics.
- `scripts/build_demo_showcase.py`: Added synthetic `live_ticker` to demo telemetry and `meta.demo.js`.
- `dashboard/index.html` & `dashboard/demo.html`: Restructured `.tab-nav` into flex layout and inserted `#token-ticker-hud`.
- `dashboard/styles.css`: Added styles, animations (`pulse-ticker-beacon`, `delta-flash-anim`), and responsive breakpoints for the HUD.
- `dashboard/app.js`: Added `updateTokenTicker()` and `updateTickerClock()`, hooked into 3s `meta.js` polling.
- `macos/AntigravityBar/Sources/AntigravityBar/StatusModel.swift`: Added ticker properties and formatting helpers.
- `macos/AntigravityBar/Sources/AntigravityBar/StatusBarController.swift`: Dynamic burn rate in status bar title.
- `macos/AntigravityBar/Sources/AntigravityBar/PopoverContentView.swift`: Added `LiveTokenTickerCard` to popover view.
- `tests/test_aggregator.py`: Added `test_live_ticker_computation`.
- `docs/milestones/M39_LIVE_TOKEN_TICKER_AND_WHITE_SPACE.md`: Created milestone slice documentation.
