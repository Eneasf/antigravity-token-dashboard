# Milestone 46: Degraded Sessions Warnings & Context Boundary Hygiene

## 1. Goal
Implement a UI warning system to detect and alert users when an active AI session approaches or crosses the catastrophic >200k token truncation limit (as analyzed in ADR-060 / postmortem). Prevent "Context Rot" by encouraging users to generate handover summaries and start fresh `@Conversation` contexts.

## 2. Technical Implementation
- **Logic Engine**: Added `checkDegradedSessions` to `dashboard/app.js` using a 2-tier severity model:
  - **Tier 1 (Warning / Amber)**: >80,000 peak prompt depth.
  - **Tier 2 (Critical / Red)**: >200,000 peak prompt depth (Emergency Truncation zone).
  - **Auto-Reset**: Active 24-hour recency filter using `last_turn_ts`.
- **Top Menu Header**: Injected a dynamic red/amber badge next to the session count spanning the Mac-style menu bar.
- **Explicit Now Tab Banner**: Injected a high-visibility contextual warning banner at the top of the `#view-now` tab.
- **Sessions Tab Widget**: Engineered a dedicated degraded sessions widget at the top of `#view-sessions`.
- **Handover Workflow**: Implemented `copyHandoverSummary(convoId)` to automatically extract the session title and workspace name to the clipboard for rapid continuation.

## 3. Verifications
- `python3 scripts/export_dashboard.py` passed cleanly without syntax errors and generated `data.js`.
- LaunchAgent `setup_service.py restart` returned `RUNNING / REGISTERED`.
- 208 Unit Tests passed cleanly.
