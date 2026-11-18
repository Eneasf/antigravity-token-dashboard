# Milestone 47: Unified Dashboard Context Safety Strip & Active Branch Attribution

## 1. Goal
Disentangle active conversation context health from the historical 24-hour degraded audit log across the Web Dashboard, macOS Menu Bar (`AntigravityBar`), and executive status hooks (`~/.antigravity_quota_status.json`). Replace misleading red banners with a calm, compact 1-row status bar (~38px) when the active thread is safe, while pinning the current active branch and attributing historical offender sessions with Git branches and workspaces.

## 2. Technical Implementation
- **Executive Status Hook Schema (`scripts/export_dashboard.py`)**:
  - Enriched `~/.antigravity_quota_status.json` with `current_session` containing `convo_id`, `title`, `branch`, `workspace`, `tokens`, `severity`, `headroom_to_warning`, and `is_current: True`.
  - Enriched `degraded_sessions` entries with `convo_id`, `branch`, `workspace`, and boolean `is_current` disambiguation.
- **Native macOS Menu Bar Monitor (`macos/AntigravityBar`)**:
  - Updated `StatusModel.swift` to decode `branch`, `workspace`, `is_current`, `headroom_to_warning`, and optional `current_session: DegradedSession?`.
  - Refactored `PopoverContentView.swift` into modular SwiftUI structs (`PinnedActiveBranchCard`, `HistoricalOffendersList`) to resolve Swift 6 type-checker timeouts.
  - Rendered a pinned active branch hero card at the top of the expanded drawer and branch badges on historical offender rows.
- **Web Dashboard Integration (`dashboard/styles.css`, `dashboard/app.js`)**:
  - Replaced intrusive 70px alert banner with a compact 1-row status strip (`.context-safety-strip`, ~38px height) supporting `.status-safe`, `.status-warning`, and `.status-critical`.
  - Disentangled header badge: shows non-alarming `● Context Safe · N in audit` when the active session is <80k tokens.
  - Implemented inline expandable accordion drawer (`.context-safety-accordion`, toggled via `toggleContextAuditDrawer()`) containing:
    1. **Pinned Active Branch Hero Card**: Highlights the currently active conversation, token count, branch badge, workspace attribution, and headroom indicator (`+45k tokens to warning`).
    2. **Historical Offenders Table**: Displays historical degraded sessions with distinct branch badges, workspace attribution, and `[Copy Handover]` buttons.
- **Synthetic Demo Showcase (`scripts/build_demo_showcase.py`)**:
  - Rebuilt `dashboard/data.demo.js` and `dashboard/demo.html` reflecting current session attribution.

## 3. Verifications
- **Gate V257**: `scripts/export_dashboard.py` verified; `~/.antigravity_quota_status.json` carries `current_session` and branch attribution. Exit code 0.
- **Gate V258**: `scripts/build_menubar.py` packaged `dist/AntigravityBar.app`; 3/3 tests passed in `tests/test_menubar_packaging.py`. Exit code 0.
- **Gate V259**: `dashboard/app.js` checked via `node -c` (exit code 0); DOM elements and styles verified. Exit code 0.
- **Gate V260**: Full test suite (209 tests) passed cleanly in 70s; `test_docs_integrity.py` passed (7/7); LaunchAgent daemon restarted (`RUNNING / REGISTERED`); `AntigravityBar` kickstarted (`RUNNING`).
