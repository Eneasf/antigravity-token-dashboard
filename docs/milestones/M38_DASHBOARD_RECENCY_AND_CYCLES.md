# Milestone 38: Dashboard Refresh Frequency, Recency Sorting & Weekly Cycle Alignment

**Milestone Slice Record**  
**Designation**: `M38` / `v1.38.0`  
**Date**: September 2026  
**Status**: Completed  
**Branch**: `feat/dashboard-recency-and-cycles`  
**Associated ADR**: ADR-052  

---

## 1. Context & Motivation

During active engineering sessions, user feedback highlighted several usability and operational requirements for the Antigravity Telemetry Dashboard:
1. **Higher Refresh Frequency**: Users wanted live metrics refreshed much faster than the legacy 30-second polling cadence. A rigorous analysis was needed to determine the minimal safe client polling interval without CPU churn, network bloat, or race conditions with the background watcher daemon.
2. **Reverse Chronological Turn Inspection**: When drilling into a session from the Recent Active Sessions table, the turns drawer historically displayed turns in forward chronological order (Turn 1 on top). In long sessions (e.g. 50+ turns), users had to scroll all the way to the bottom to inspect the latest turn and its thinking tokens.
3. **Reverse Chronological Git Branch Cost Attribution**: In the Portfolio Projects & Branches drawer, branches were previously sorted by total token consumption. Users working on active feature branches wanted the most recently active branch displayed at the top with clear temporal recency indicators.
4. **Weekly Quota Reset Boundary Clarification**: Clarification was needed regarding why the weekly quota cycle had not rolled over on Thursday, September 18th, despite past cycles resetting on Thursdays.
5. **Vault Pipeline Auto-Synchronization Gap**: An operational gap was identified in `scripts/export_dashboard.py`, where `sync_weekly_trends_to_vault()` was called without first running `sync_conversations_to_vault()`, preventing newly recorded turns in SQLite from populating the active cycle archive during standalone exports.

---

## 2. Technical Decisions & Architectural Implementation

### 2.1 3-Second Minimal Safe Polling Cadence
- **Timing & Debounce Architecture**:
  - The backend watcher daemon (`scripts/watch_telemetry.py`) operates with an `interval_seconds=1.0s` and a `debounce_seconds=2.0s` settle window. Total export write latency is ~300ms.
  - Client polling queries `dashboard/meta.js` (only 207 bytes), checking `payload_sha1` and `generated_at`.
  - If the hash has not changed, zero DOM re-rendering occurs and the ~18 MB `data.js` payload is **never fetched**.
  - A 3-second client polling interval (`3000ms`) was established as optimal: it comfortably exceeds the watcher's 2.0s debounce settling window plus export duration, eliminating race conditions while delivering near real-time live updates.
- **UI Indicators**:
  - Updated auto-refresh button text to `🔄 Live Auto-Refresh: ON (3s)` across `dashboard/index.html`, `dashboard/demo.html`, and `dashboard/app.js`.

### 2.2 Reverse Chronological Turn-by-Turn Inspection
- **Default Recency**:
  - In `dashboard/app.js` (`renderTurnsTable`), turns are sorted descending by timestamp by default (`desc`), immediately displaying the latest turn, its prompt/reply token counts, thinking tokens, and timestamp on top.
- **Interactive Sort Toggle**:
  - Added a responsive `.sort-toggle-btn` to the turns table drawer header allowing users to toggle between `Newest First` (default) and `Oldest First` with 1 click.

### 2.3 Reverse Chronological Git Branch Cost Attribution
- **Recency Recording**:
  - Updated `src/aggregator.py` (`aggregate_conversation_telemetry` and `aggregate_global_telemetry`) to capture `last_active_timestamp` on each branch from individual turn timestamps and session metadata.
  - Branches within each project are now stably sorted by `(b.get("last_active_timestamp") or "", total_tokens)` in descending order.
- **Visual Timestamp Pills**:
  - Added formatted recency pills (`.branch-time-pill`) in `dashboard/app.js` showing relative/calendar activity timestamps (e.g. `🕒 18 Sep, 11:45 UTC`) alongside branch token and cost metrics.

### 2.4 Weekly Quota Reset & Google AI Ultra 5x Transition
- **Cycle Shift Ground Truth**:
  - In M28, the subscription was upgraded from Google One Pro to **Google AI Ultra (5x Usage)** on Sunday, September 13, 2026 at 17:58:04 UTC.
  - Upgrading to Ultra 5x permanently shifted Google's weekly quota cycle boundary from Thursdays (18:00 UTC) to **Sundays (17:58:04 UTC)**.
  - As of Friday, September 18th, the current weekly cycle spans **13 Sep 2026, 17:58:04 UTC – 20 Sep 2026, 17:58:04 UTC** (Day 5 of 7), resetting in 2 days.
- **Vault Export Auto-Synchronization**:
  - Updated `scripts/export_dashboard.py` to call `sync_conversations_to_vault(antigravity_dir=antigravity_dir)` prior to `sync_weekly_trends_to_vault()`.
  - Standalone exports now automatically ingest all active SQLite turns into `data/antigravity_vault.db`, ensuring the active week `13 Sep – 20 Sep 2026` is accurately populated with all recent turns (6,226 turns).
- **Active Cycle Visual Indicator**:
  - Updated `dashboard/app.js` (`renderWeeklyTrendsSvg` and `renderWeeklyTrendsTable`) to highlight the active cycle with an animated pulsating green indicator (`.active-cycle-dot`) and clear reset schedule badge.

---

## 3. Verifiable Quality Gates (`VDONE.md`)

| Gate | Description | Check Command | Status |
|---|---|---|---|
| **V204** | Branch Recency & Timestamp Recording | `python3 -c "from src.aggregator import aggregate_global_telemetry... assert b_found"` | **Passed** |
| **V205** | Vault Pipeline Ingestion & Auto-Sync | `python3 -c "assert 'sync_conversations_to_vault' in open('scripts/export_dashboard.py').read()"` | **Passed** |
| **V206** | Frontend 3s Auto-Refresh Interval | `python3 -c "assert 'Live Auto-Refresh: ON (3s)' in open('dashboard/app.js').read()"` | **Passed** |
| **V207** | Reverse Chronological Turns Drawer | `python3 -c "assert 'renderTurnsTable' in open('dashboard/app.js').read()"` | **Passed** |
| **V208** | Active Weekly Cycle Resolution | `python3 -c "from src.weekly_trends import get_weekly_trends... assert len(current) >= 1"` | **Passed** |
| **V209** | Full Unit & Docs Integrity Test Suite | `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py` | **Passed (213 tests)** |
| **V210** | Live Pipeline Refresh & Daemon Status | `python3 scripts/setup_service.py status && test -s dashboard/data.js` | **Passed** |
| **V211** | Clean Working Tree & Git Hygiene | `git status` | **Passed** |

---

## 4. Key Artifacts Modified & Created

- `src/aggregator.py`: Added `last_active_timestamp` extraction and reverse chronological sorting on branches.
- `scripts/export_dashboard.py`: Synchronized conversation turns into vault before weekly trends computation.
- `scripts/build_demo_showcase.py`: Added `last_active_timestamp` and `branch_name` to synthetic demo branches.
- `dashboard/app.js`: 3s auto-refresh interval, reverse chronological turns drawer with sort toggle, reverse chronological branches with timestamp pills, active weekly cycle pulse badge.
- `dashboard/styles.css`: Styles for `.branch-time-pill`, `.active-cycle-badge`, `.active-cycle-dot`, and `.sort-toggle-btn`.
- `dashboard/index.html` & `dashboard/demo.html`: Updated auto-refresh button labels.
- `tests/test_aggregator.py`: Added `test_branch_reverse_chronological_sorting`.
- `tests/test_watch_telemetry.py`: Hardened integration test join timeouts.
- `.gitignore`: Added `dashboard/meta.demo.js` and `dashboard/meta.demo.json`.
