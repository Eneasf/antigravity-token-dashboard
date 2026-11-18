# ADR-082: Discrete 5-Hour Quota Reset Epochs & Compaction Drift Safeguards

**Status:** Adopted (Supersedes ADR-025)
**Date:** 2026-09-30
**Authors:** Antigravity Engineering & Telemetry Architecture
**Deciders:** Eneas, Antigravity Orchestrator
**Cross-References:** ADR-009, ADR-019, ADR-025, ADR-043, ADR-060, ADR-071, ADR-081

---

## 1. Context & Problem Statement

### 1.1 The Rolling Burst Misconception (ADR-025)
In Milestone M13, ADR-025 modeled the Antigravity 5-hour quota as a continuous sliding window (a "leaky bucket" where each prompt was assumed to age out independently at timestamp $T + 5\text{h}$). To reflect this assumption, the telemetry engine implemented `compute_window_recovery_schedule` in `src/aggregator_windows.py`, projecting a synthetic 20-step staircase recovery timeline (`[+5%, +12%, +25%...]`) and rendering label strings such as `"Next roll-off in 41m (100% in 42m)"` across the macOS status topper and web dashboard.

### 1.2 Ground-Truth Connect-RPC Verification
On 2026-09-30, direct inspection of the running Google Antigravity Language Server via Connect-RPC (`/antigravity.v1.LanguageServer/RetrieveUserQuotaSummary`) returned:

```json
{
  "bucketId": "gemini-5h",
  "displayName": "Five Hour Limit Remaining",
  "description": "You have used some of your 5-hour limit, it will fully refresh in 25 minutes.",
  "window": "5h",
  "remainingFraction": 0.50195384,
  "resetTime": "2026-09-30T12:32:47Z"
}
```

This live telemetry provides definitive proof that:
1. **Official Google Terminology**: Upstream Google names this quota **"Five Hour Limit"** (`displayName: "Five Hour Limit Remaining"`). The word "Rolling" or "Burst" does not exist in Google's wire protocol.
2. **Single Discrete Reset Timestamp**: Upstream Google returns a single ISO timestamp `resetTime: "2026-09-30T12:32:47Z"`. There is no array or sequence of turn-by-turn expirations.
3. **Discrete 100% Capacity Restoration**: Upstream Google explicitly declares: *"it will fully refresh in 25 minutes"*. At the specified `resetTime`, 100% of the 5-hour limit capacity is restored simultaneously. There is no partial or incremental rolling recovery.
4. **The Exporter Priority Bug**: In `scripts/export_dashboard.py`, the exporter unconditionally evaluated `gem_5h.get("recovery_schedule")`. Because `compute_window_recovery_schedule` always generated a synthetic schedule, it was overwriting Google's authentic `reset_time` and `description` with artificial `"Next roll-off in Xm"` text.

### 1.3 Compaction Limits vs. Nominal Context Windows
An empirical research study conducted in `docs/STUDY_SUMMARY_PRESERVATION_VS_CONTEXT.md` revealed that Antigravity's internal prompt history maintains a **strict 10-request FIFO queue** (Protobuf Subfield 19). Compaction triggers automatically at empirical ceilings:
- Gemini 3.8 Flash: **~244k–270k tokens**
- Gemini 3.7 Flash: **~165k tokens**
- Gemini 3.1 Pro / Claude 3.7 Sonnet: **~80k tokens**

Because `antigravity_telemetry/models.json` previously listed only the nominal model context window (`1,000,000` tokens), the active session severity calculation evaluated `headroom_to_warning` against 800,000 tokens. An active session at 210,000 tokens displayed `"Safe (+590k to warning)"`, giving a dangerous false sense of security right before compaction struck. At Epoch 3+ ($\ge 3$ compactions), Turn 1 user constraints were evicted from the 10-turn FIFO queue, triggering a **78.4% redundant tool re-read penalty** and severe context amnesia.

---

## 2. Decision & Architectural Architecture

1. **Supersede ADR-025**: Formally supersede ADR-025. The continuous sliding window model and synthetic staircase recovery timeline are deprecated in favor of Google's authentic discrete epoch reset model.
2. **Standardize on Official Google Terminology ("5-Hour Limit")**:
   - Replace all user-facing instances of `"5-Hour Rolling Burst"` with `"5-Hour Limit"` (or `"5-Hour Quota"`) across the macOS menu bar topper (`AntigravityBar`), web dashboard, and telemetry reports.
3. **Fix Exporter Priority & Live Reset Countdown**:
   - In `scripts/export_dashboard.py`, prioritize `live_quota["gemini_5h"]["description"]` and `reset_time` over synthetic schedules.
   - Display discrete countdown text: `"Fully refreshes in Xm (HH:MM UTC)"` or Google's direct status description.
4. **Empirical Compaction Limits & Epoch Detection**:
   - Add `compaction_threshold_tokens` to `antigravity_telemetry/models.json` (250k Flash / 165k 3.7 / 80k Pro & Claude).
   - Upgrade `src/vault.py:scan_conversation_truncation` and `get_vault_truncation_markers` to count compactions (`COUNT(*)`) and compute the active compaction epoch.
   - Surface a 2D drift warning when `compaction_epoch >= 3` (*"Epoch 3+ Drift: Turn 1 evicted"*), advising the user to start a fresh thread via `@Conversation`.
5. **Adaptive Cadence & Tab Visibility Optimization**:
   - In `dashboard/js/now.js`, hook `document.addEventListener("visibilitychange")` to clear the polling interval when the tab is hidden, eliminating 1,200 background requests/hour.
   - Implement adaptive backoff (3s streaming active / 10s quiet / 30s dormant).

---

## 3. Consequences & Verification

- **Accuracy**: The menu bar topper and web dashboard reflect true server-side quota refresh countdowns matching the IDE and upstream Connect-RPC.
- **Context Safety**: Users are warned before reaching the 250k/80k compaction cliff and alerted immediately when Turn 1 constraints are evicted at Epoch 3+.
- **Resource Hygiene**: Background browser tabs no longer churn CPU or network resources.
- **Backward Compatibility**: `VaultMarker` and `TruncationResult` maintain 100% backward-compatible tuple unpacking for existing callers while providing rich epoch attributes.
