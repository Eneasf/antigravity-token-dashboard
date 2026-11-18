# Milestone 41: Popover Contrast & Executive Visual Hierarchy

**Milestone Slice Record**  
**Designation**: `M41` / `v1.41.0`  
**Date**: September 2026  
**Status**: Completed  
**Branch**: `feat/menubar-contrast-polish`  
**Associated ADR**: ADR-055  

---

## 1. Context & Motivation

In Milestone 40, live usage feedback revealed that neon green text elements and the neon green progress bar in the macOS popover card (`AntigravityBar`) were difficult to read in Light Mode:
1. **Low Contrast Ratio (WCAG Failure)**: macOS default `Color.green` (~`#34C759`) provides only a ~2.4:1 contrast ratio against light backgrounds, failing WCAG AA (requires 4.5:1 for readable text).
2. **"Green Glare" / Over-Saturation**: Green was applied simultaneously across 6 elements (`SAFE`, `88.0%`, the progress bar, `121k/m`, `▲ +152.4k`, and `45.8M tok · 88.0% free`), creating visual competition and eye strain.
3. **Contrast with Weekly Quota**: The Weekly Quota Runway above it demonstrated superior readability because its percentage (`89.9%`) was rendered in high-contrast primary text (`.primary` / crisp dark charcoal).

---

## 2. Technical Decisions & Architectural Implementation

### 2.1 Semantic Typography & Color Model (`StatusModel.swift`)
- **`textHealthColor`**: Numbers and metrics now render in high-contrast primary text (`.primary`, 100% black/dark charcoal in Light Mode, crisp ivory in Dark Mode) during nominal healthy operation (>35% headroom). Color is reserved strictly for true alert states: shifting to **warm amber** (`.orange`) when <=35%, and **vivid red** (`.red`) when <15% (or cooldown).
- **`burstBarColor`**: Replaced neon lime `Color.green` with a refined, solid Deep Forest Emerald (`Color(red: 5/255.0, green: 150/255.0, blue: 105/255.0)`, `#059669`).
- **`streamingDotColor`**: Defined clean mint emerald (`#10B981`) for the active live streaming beacon dot.
- **`healthColor`**: Calibrated default fallback to Deep Forest Emerald.

### 2.2 High-Contrast Executive Popover Layout (`PopoverContentView.swift`)
- **5-Hour Rolling Burst Section**:
  - Headroom percentage (`88.0%`) rendered using `store.status.textHealthColor` (crisp `.primary` black text, ~13:1 contrast).
  - Progress bar rendered using `store.status.burstBarColor` (Forest Emerald `#059669`).
- **Live Token Ticker Card (`LiveTokenTickerCard`)**:
  - Live speed `121k/m`: Rendered in bold monospaced primary text (`.foregroundColor(.primary)`).
  - Turn delta badge `▲ +152.4k`: Styled with a clean neutral separator background (`Color(NSColor.separatorColor).opacity(0.2)`) and dark primary text.
  - 5h Burst runway line: `45.8M tok · 88.0% free` rendered using `status.textHealthColor` (bold `.primary` dark text).
- **Status Badge View (`StatusBadgeView`)**:
  - During safe operation: Subtle neutral pill (`Color(NSColor.separatorColor).opacity(0.15)`) with secondary text and emerald dot.
  - During warning/critical: Retains saturated amber/red alert styling.

### 2.3 Native Compilation & Packaging (`dist/AntigravityBar.app`)
- Recompiled release binary via `scripts/build_menubar.py` (431,720 bytes) with ad-hoc code signing.
- Live restart via `scripts/setup_menubar.py restart`.

---

## 3. Verifiable Quality Gates (`VDONE.md`)

| Gate | Description | Check Command | Status |
|---|---|---|---|
| **V229** | Swift StatusModel Semantic Text & Bar Colors | `python3 -c "m = open('macos/.../StatusModel.swift').read(); assert 'textHealthColor' in m and 'burstBarColor' in m"` | **Passed** |
| **V230** | High-Contrast Executive Hierarchy in Popover | `python3 -c "v = open('macos/.../PopoverContentView.swift').read(); assert 'textHealthColor' in v and 'burstBarColor' in v"` | **Passed** |
| **V231** | Swift Native Menu Bar Compilation | `python3 scripts/build_menubar.py` | **Passed (431 KB)** |
| **V232** | Full Test Suite & Docs Integrity | `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py` | **Passed (214 tests)** |
| **V233** | Live Daemon Verification & Process Health | `python3 scripts/setup_menubar.py status && python3 scripts/setup_service.py status` | **Passed** |
| **V234** | Working Tree Hygiene & Clean Commits | `git status` | **Passed** |

