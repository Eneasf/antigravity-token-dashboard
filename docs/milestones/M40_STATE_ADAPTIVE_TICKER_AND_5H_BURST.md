# Milestone 40: State-Adaptive Token Ticker HUD & macOS Menu Bar 5h Burst Integration

**Milestone Slice Record**  
**Designation**: `M40` / `v1.40.0`  
**Date**: September 2026  
**Status**: Completed  
**Branch**: `feat/adaptive-ticker-hud`  
**Associated ADR**: ADR-054  

---

## 1. Context & Motivation

Following the deployment of the initial Token Ticker HUD in Milestone 39, review and live usage revealed key usability and cognitive considerations:
1. **Clock Counter Redundancy**: The `🕒 0s ago` counter created constant peripheral visual jitter by ticking upward every second. Real-time liveness is more gracefully communicated through a soft pulsing/breathing LED dot.
2. **Text Label Clutter**: Static text labels (`LIVE STREAM` / `MONITORING`) took up unnecessary horizontal width.
3. **Dead Velocity During Idle Periods**: Displaying `⚡ 0 tok/min` during idle periods provided zero actionable signal. Velocity is meaningful only when actively generating code.
4. **Permanent 5-Hour Burst Runway Anchor**: In Antigravity, the 5-hour rolling burst is the hard ceiling that halts active workflows. Developers need continuous visibility into both the cumulative token volume (`18.4M tok`) and the remaining percentage (`74% free`) in both active streaming and idle states.
5. **macOS Top Menu Bar Parity**: The macOS status bar monitor (`AntigravityBar`) needed to display the 5-hour token volume alongside the headroom percentage (`⚡ 74% (18.4M)`), appending a glowing green dot `●` and live burn velocity (`▲ 2.1M/m`) when actively streaming.

---

## 2. Technical Decisions & Architectural Implementation

### 2.1 Aggregator 5h Burst & Cache Rate Integration (`src/aggregator.py`)
- Updated `compute_live_ticker(flat_turns, conversation_summaries, projects, reference_time, pricing_models, gemini_5h)`:
  - Added `gemini_5h` parameter to extract `gemini_5h_tokens` (`total_processed`), `gemini_5h_remaining_pct`, and `gemini_5h_used_pct`.
  - Added `last_turn_cache_pct` calculation (`(cached / prompt) * 100.0`).
- Updated `aggregate_global_telemetry` to pass `gemini_5h=gemini_5h` into `compute_live_ticker`.
- Updated `scripts/export_dashboard.py` (`write_quota_status_file`) to record `gemini_5h_tokens` and `last_turn_cache_pct` into `~/.antigravity_quota_status.json` and `dashboard/meta.js`.

### 2.2 Streamlined State-Adaptive DOM Layout (`dashboard/index.html` & `dashboard/demo.html`)
- **Restructured HUD**:
  - `#ticker-beacon-dot`: Soft pulsing/breathing LED dot without text label.
  - `#ticker-rate-container`: Dynamic velocity pill (`⚡ 1.7M/m`) that automatically dissolves when idle (`display: none`).
  - `#ticker-delta-pill`: Turn delta badge (`▲ +85.3k` when streaming, `Last: +85.3k` when idle).
  - `#ticker-engine`: Unified engine badge merging model name and cache efficiency (`Gemini 3.8 Flash · 95.7% Cache`).
  - `#ticker-5h`: Permanent 5-hour burst anchor (`5h: 18.4M tok · 74% free`) with dynamic health coloring (`critical` < 20%, `warning` < 40%, green nominal).
  - Decommissioned and removed `#ticker-clock` (`0s ago`) and `tickerClockTimer`.

### 2.3 Modern CSS & Keyframe Animations (`dashboard/styles.css`)
- Replaced label styling with a clean 8px circular LED dot (`.ticker-beacon-dot.streaming` with `@keyframes pulse-ticker-beacon`).
- Styled `.ticker-engine-pill` and `.ticker-5h-pill` with monospaced tabular numerals (`font-feature-settings: 'tnum'`).
- Added smooth opacity and transition effects for active vs. idle state toggling.

### 2.4 Frontend Controller (`dashboard/app.js`)
- Rebuilt `updateTokenTicker()` to evaluate streaming state (`isStreaming = is_streaming || rate > 0`).
- Dynamically toggles velocity visibility, updates turn delta with flash animation on turn changes, formats unified engine pill, and renders 5-hour volume and headroom.
- Completely removed `updateTickerClock` and 1-second interval timer.

### 2.5 Native macOS Menu Bar Monitor (`AntigravityBar`)
- **StatusModel.swift**: Added `gemini_5h_tokens: Int?`, `last_turn_cache_pct: Double?`, `formatted5hTokens`, and `formattedLastTurnCache`.
- **StatusBarController.swift**:
  - While Active: `●  📅 92%  ⚡ 74% (18.4M)  ▲ 2.1M/m` (small green glowing dot, 5h tokens in parentheses, green burn speed).
  - While Idle: `📅 92%  ⚡ 74% (18.4M)` (contracts cleanly, no speed clutter).
- **PopoverContentView.swift**:
  - Updated `LiveTokenTickerCard` into a 2-row layout:
    - Row 1: Pulsing green dot (or calm gray), speed `⚡ 1.7M/m` (when active), turn delta badge (`▲ +85.3k`), model & cache (`Gemini 3.8 Flash · 95.7% Cache`).
    - Row 2: 5h burst runway `5h Burst: 18.4M tok · 74.4% free` with dynamic health color.

---

## 3. Verifiable Quality Gates (`VDONE.md`)

| Gate | Description | Check Command | Status |
|---|---|---|---|
| **V220** | Aggregator 5h Tokens & Cache in Live Ticker | `python3 -c "from src.aggregator import aggregate_global_telemetry... assert 'gemini_5h_tokens' in t"` | **Passed** |
| **V221** | Enriched Status Hook & Meta.js | `python3 -c "assert 'gemini_5h_tokens' in open('dashboard/meta.js').read()"` | **Passed** |
| **V222** | Streamlined Non-Redundant DOM | `python3 -c "assert 'ticker-5h' in open('dashboard/index.html').read() and 'ticker-time' not in open('dashboard/index.html').read()"` | **Passed** |
| **V223** | Modern CSS & State-Adaptive Styles | `python3 -c "assert 'ticker-5h' in open('dashboard/styles.css').read()"` | **Passed** |
| **V224** | Frontend Controller & Timer Decommission | `python3 -c "assert 'ticker-5h' in open('dashboard/app.js').read() and 'updateTickerClock' not in open('dashboard/app.js').read()"` | **Passed** |
| **V225** | Swift Menu Bar 5h Tokens & App Bundle | `python3 scripts/build_menubar.py` | **Passed** |
| **V226** | Full Test Suite & Docs Integrity | `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py` | **Passed (214 tests)** |
| **V227** | Live Pipeline Refresh & Daemon Status | `python3 scripts/setup_service.py status && python3 scripts/setup_menubar.py status` | **Passed** |
| **V228** | Working Tree Hygiene & Clean Commits | `git status` | **Passed** |
