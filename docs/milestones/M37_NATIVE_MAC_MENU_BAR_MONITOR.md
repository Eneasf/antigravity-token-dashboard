# Milestone 37: Native macOS Menu Bar Monitor & Enriched Status Hook

**Milestone Slice Record**  
**Designation**: `M37` / `v2.3.0`  
**Date**: September 2026  
**Status**: Completed  
**Branch**: `feat/mac-menu-bar`  
**Associated ADR**: ADR-051  

---

## 1. Context & Motivation

While the dashboard provides in-depth visualization across projects, sessions, billing, and swarms, developers actively coding inside Google Antigravity IDE rarely keep a secondary browser tab visible. 

As identified in the September 2026 Architecture Audit (Row 9, Item M1), an ambient, out-of-browser telemetry surface was needed to provide glanceable peripheral awareness of quota limits directly while writing code.

Key requirements and architectural constraints:
1. **Zero-Overhead Glanceability**: Display real-time 5-hour rolling burst headroom and 1-week quota runway numbers directly in the macOS top menu bar without opening browser tabs.
2. **Apple-Native SF Symbols**: Use native SF Symbols (`bolt.fill` for 5h burst power and `calendar` for weekly quota allowance) with exact font baseline alignment.
3. **Adaptive Health-Aware Typography**: Monochrome typography during normal/healthy work (>35% headroom) to avoid visual fatigue, transitioning to warm amber on caution (15%–35%), and vivid red on exhaustion or 429 burst cooldown (<15%).
4. **Interactive Popover Card**: Clicking the menu bar item reveals an interactive SwiftUI popover showing progress bars, roll-off recovery countdowns, weekly reset schedules, BVI pacing verdicts, Claude/GPT secondary allowances, and quick actions ("Open Dashboard", "Refresh Telemetry", "Quit").
5. **Thin-Client View Architecture**: The native Swift app is a pure reactive view layer with zero duplicate business logic. It observes `~/.antigravity_quota_status.json` via event-driven kernel filesystem events (`DispatchSourceFileSystemObject`), waking up instantly in <1ms upon file changes and consuming 0.0% CPU when idle (~22 MB RAM).
6. **Automated Packaging & Service Management**: Scripted compilation via `scripts/build_menubar.py` producing `dist/AntigravityBar.app` (`LSUIElement=true`, no Dock icon) with complete lifecycle management in `scripts/setup_menubar.py`.

---

## 2. Deliverables & Architectural Changes

### 2.1 Enriched Executive Status Hook (`scripts/export_dashboard.py` & `scripts/agy_status.py`)
- Extended `write_quota_status_file` in `scripts/export_dashboard.py` to atomically generate:
  - `gemini_5h_remaining_pct`, `gemini_weekly_remaining_pct`
  - `claude_5h_remaining_pct`, `claude_weekly_remaining_pct`
  - `gemini_5h_recovery_desc`: Dynamic roll-off countdown string (e.g. `"Next roll-off in 9m (100% in 11m)"`)
  - `weekly_reset_desc`: Human-readable calendar reset string (e.g. `"Sunday 17:58:04 UTC (4 days, 20 hours remaining)"`)
  - `bvi`: Current Bayesian M-estimate Burn Velocity Index (e.g. `0.63`)
  - `bvi_verdict`: Formatted velocity verdict (e.g. `"Day 3: +29.1% buffer (13.8% vs 42.9%)"`)
  - `plan_name`: Authoritative subscription tier (`"Google AI Ultra (5x)"`)
  - `active_project`, `active_branch`: Most recent workspace attribution
  - `credit_balance`: Active prepaid credit bank status (`"1,360 / 5,000 credits (£13.05)"`)
  - `dashboard_path`: Absolute path to `dashboard/index.html`
- Added `--verbose` flag to `scripts/agy_status.py` for rich multi-line terminal inspection.

### 2.2 Native Swift 6 Menu Bar App (`macos/AntigravityBar/`)
- `Package.swift`: Swift package targeting macOS 13+ with executable target `AntigravityBar`.
- `StatusModel.swift`: Codable model with computed properties for remaining percentages, health thresholds, and color resolution.
- `StatusStore.swift`: Observable store decoding JSON with event-driven file monitoring (`DispatchSourceFileSystemObject`), atomic replacement re-arming, and fallback heartbeat.
- `StatusBarController.swift`: Configures `NSStatusItem`, constructs attributed string with SF Symbols and adaptive health colors, and coordinates popover presentation.
- `PopoverContentView.swift`: Responsive SwiftUI card popover containing:
  - Header with plan badge and status pill
  - 5-Hour Rolling Burst section with progress bar, headroom %, and roll-off note
  - Weekly Quota Runway section with progress bar, runway %, reset date, and BVI verdict
  - Claude & GPT track secondary allowance pill
  - Active workspace and credit bank metadata
  - 1-click action buttons: "Open Dashboard", "Refresh Telemetry", "Quit"
- `main.swift`: AppKit entrypoint setting `NSApp.setActivationPolicy(.accessory)` to run strictly as a background menu bar agent with no Dock presence.

### 2.3 Packaging Pipeline & Lifecycle CLI (`scripts/build_menubar.py` & `scripts/setup_menubar.py`)
- `scripts/build_menubar.py`:
  - Compiles Swift package in release mode (`swift build -c release`).
  - Packages executable into `dist/AntigravityBar.app`.
  - Injects `Contents/Info.plist` with `<key>LSUIElement</key><true/>`.
  - Applies ad-hoc code signature (`codesign --force --deep --sign -`).
- `scripts/setup_menubar.py`:
  - CLI commands: `status`, `start`, `stop`, `restart`, `install-service`, `uninstall-service`.
  - Supports automated LaunchAgent auto-start at login (`~/Library/LaunchAgents/com.antigravity.menubar.plist`).

### 2.4 Automated Test Suites (`tests/test_quota_status_enrichment.py` & `tests/test_menubar_packaging.py`)
- `tests/test_quota_status_enrichment.py`: Validates atomic writing of all enriched fields and compatibility with `scripts/agy_status.py`.
- `tests/test_menubar_packaging.py`: Validates Swift compiler detection, app bundle directory assembly, `Info.plist` metadata, and CLI status reporting.

---

## 3. Acceptance Verification Proofs

| Gate ID | Check Command | Measured Proof | Verdict |
|---|---|---|---|
| **V197** | `python3 scripts/export_dashboard.py && python3 -c "import json, os; d = json.load(open(os.path.expanduser('~/.antigravity_quota_status.json'))); assert 'gemini_5h_remaining_pct' in d; assert 'weekly_reset_desc' in d; print('Verified: Enriched status hook generated with complete schema.')"` | Output printed `Verified: Enriched status hook generated with complete schema.` (Exit code 0). | **PASSED** |
| **V198** | `cd macos/AntigravityBar && swift build -c release && test -f .build/release/AntigravityBar && echo "Verified: Swift binary compiled successfully."` | Compiled Mach-O 64-bit executable (369 KB) in 2.77s with 0 warnings, 0 errors (Exit code 0). | **PASSED** |
| **V199** | `python3 scripts/build_menubar.py && test -d dist/AntigravityBar.app && plutil -p dist/AntigravityBar.app/Contents/Info.plist \| grep -q 'LSUIElement.*1' && echo "Verified: AntigravityBar.app bundle assembled with LSUIElement."` | Packaged `dist/AntigravityBar.app`, confirmed `LSUIElement => 1` and applied ad-hoc code signature (Exit code 0). | **PASSED** |
| **V200** | `python3 scripts/setup_menubar.py status` | Confirmed bundle installed, binary executable, and process running live (Exit code 0). | **PASSED** |
| **V201** | `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py` | Ran 205 unit tests across all test suites, all passing cleanly with 0 failures, 0 errors (Exit code 0). | **PASSED** |
| **V202** | `python3 scripts/setup_service.py status && python3 -c "import os; assert os.path.exists('dashboard/data.js') and os.path.getsize('dashboard/data.js') > 1000000; print('Verified: dashboard/data.js fresh and non-empty.')"` | Watcher daemon running (PID 36819), `dashboard/data.js` fresh and non-empty (Exit code 0). | **PASSED** |
