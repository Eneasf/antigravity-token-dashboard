# Engineering, UI & Ceremony Audit — 19 Sep 2026

**Scope**: whole repository at commit `5f71122` on `main` (clean tree, 209/209 tests passing in 69 s).
**Method**: read `AGENTS.md`, `CLAUDE.md`, `README.md`, `VDONE.md`, `docs/HANDOVER.md`, the 12 Sep audit, all of `src/`, `scripts/`, `antigravity_telemetry/`, `macos/`, `e2e/`, `tests/`; rendered `dashboard/index.html` with the live 21 MB `data.js` over a local HTTP server at 1440×900 (both themes, all six tabs) and 375×812; **executed every side-effect-free gate in `VDONE.md`** (114 of 258) to measure how many still pass. No code was changed. This document supersedes nothing; it sits beside `AUDIT_2026-09-12_CODE_AND_UX.md` and reports on what happened to it.
**Audience**: the maintaining agent and the owner. Every item has a priority, an effort, a branch name and an acceptance check. The six owner decisions that gate implementation were taken in the same session and are recorded in §7; nothing in this document is waiting on the owner.

---

## 0. Executive Summary

The engine is still the strong part. The read-only invariant holds everywhere (`?mode=ro` on all upstream connections), the exporter is deterministic in CI, the package split and the offline fixtures happened, and the suite is green.

The problems have moved. Seven days after the last audit the project has three new kinds of debt, and all three are self-inflicted by process rather than by the domain:

| Area | Verdict | Headline |
|---|---|---|
| **Ceremony** | **Bloated, and the gates have rotted** | `VDONE.md` is 1,485 lines / 139 KB and growing ~15 KB per milestone. Of the 114 gates that can be run without side effects, **33 fail today (29%)**. Nobody runs old gates, so they are proofs of the past, not gates. README is a 21-entry changelog wearing a feature list. HANDOVER's "Open Work Register" lists 13 items, 11 of them "Completed". |
| **Correctness** | Good core, five visible cracks | Header says "Renews 24 Sep" (hardcoded) while the Billing tab says 13 Oct; header says "Safe in Pro Quota" next to "Ultra Tier Active"; simulator defaults to the Pro plan and predicts a 5h blow-out that cannot happen on Ultra; LaTeX labels are back on the simulator (gate V103 claims they are gone); two exporters collided at 11:05 today and one crashed (`data.js.tmp` vanished) because there is no export lock. |
| **Performance** | Quietly degrading | A dry-run export now takes **25 s**; the watcher fires one after every 2 s of settle. The "3-second live" HUD is honest about `meta.js`, but the page data is at best 25–30 s stale. `data.js` grew from 14 MB to 21 MB in a week and is fully parsed on every load. The vault is **2.04 GB on disk plus a 2.0 GB `.bak`**, 1.26 GB of it raw step payload blobs, with no retention rule. |
| **UI** | Same shape as last week, more chrome | The 12 Sep items U4–U8 (paging, contradictory hero signals, mobile header, accessibility, polish) are untouched. Mobile header is 508 px of an 812 px viewport. 0 of 76 SVGs have a title; 0 tab or progressbar roles; 106 text nodes under 11 px. The new truncation alarm (M46/M47) is permanently red and dominates every tab. |
| **Docs drift** | The integrity test protects the wrong thing | `SYSTEM_DESIGN.md` still says `index.html` is "~1,778 lines, 74 KB" (it is 1,635 lines / 113 KB; `app.js` is 5,467 lines / 242 KB). ADR-048 says light theme is the default; the code defaults to dark. README says 59 ADRs in one paragraph and 55 in another; HANDOVER has 61. `package.json` is 1.43.0, the README badge is v2.5.0, and tags mix `v1.47.0` and `v2.5.0`. |

**Top five actions, in order**: **D1** (cut `VDONE.md` to active gates and add a test that executes them), **C1** (export lock and single writer), **C2** (fix the four hardcoded labels and the simulator default plan), **D2** (README to a 150-line front door plus `CHANGELOG.md`), **P1** (vault retention and `.bak` removal).

**Blunt version for the owner**: the last audit's *engineering* items were done well and fast. Its *process* items (P2, P3, P4) were skipped, and the process is now the thing generating most of the new defects. Every milestone adds ~40 lines to `VDONE.md`, ~6 lines to README's feature list, one 800-character ADR row, and a mandatory daemon restart. That is why gates rot, docs drift, and the same header bug can ship past a "100% gates passed" proof. Fixing this is one docs-only milestone. Not fixing it means every future milestone costs more and proves less.

---

## 1. Measured Facts (reproduce before disputing)

| Fact | Value | How measured |
|---|---|---|
| Unit tests | 209 pass, 69 s wall | `python3 -m unittest discover -s tests` |
| Of which Playwright bridge | ~60 s, skipped in CI | `tests/test_playwright_e2e.py`; `.github/workflows/ci.yml` never runs `npx` |
| `VDONE.md` | 1,485 lines, 139 KB, 16.6k words, 258 `CHECK` gates, 3 duplicated IDs (V13, V14, V15) | `wc`, `grep -c CHECK`, `grep -oE '^### V[0-9]+' \| sort \| uniq -d` |
| Runnable gates that fail today | **33 of 114** (V5, V8, V9, V13, V14, V17, V18, V20, V32, V33, V38, V40, V43, V45, V49, V54, V55, V56, V62, V64, V71, V75, V81, V82, V85, V90, V105, V109, V137, V157, V177, V206, V243) | Script in §8 (runs only `python3 -c` gates; skips anything that exports, restarts or touches git) |
| Gates that parse `injected-dashboard-data` | 11 (the hook is literally `{}` since ADR-024) | `grep -c injected-dashboard-data VDONE.md` |
| README | 536 lines, 5.9k words; "Core Capabilities" = 21 numbered milestone entries over 131 lines | `wc`, `grep -nE '^### [0-9]+\.'` |
| HANDOVER | 184 lines but 67 KB; 22 table rows over 700 chars, longest 1,144; §4 has 13 items, 11 "Completed" | `awk 'length>700'` |
| Milestone docs | 46 files, 3,559 lines, 259 KB, and their gates are copied verbatim into `VDONE.md` | `cat docs/milestones/*.md \| wc` |
| `AGENTS.md` | 106 lines, ~2.3k tokens (inside its own budget) | `wc -w` |
| `dashboard/app.js` | 5,467 lines; `initDashboard()` 803 lines; 71 `innerHTML`, 61 inline `onclick`, 254 inline `style=` in JS + 332 in HTML; `initDashboard` re-registers 15 listeners on every data reload | `grep -c`, awk function-gap |
| `dashboard/demo.html` | byte-identical to `index.html` except line 20 | `diff` |
| Accessibility | 0 `role=tab/tablist/tabpanel`, 0 `role=progressbar`, 0/76 SVGs titled, 0/11 tables captioned, 106 text nodes < 11 px | browser console, all tabs rendered |
| Mobile 375×812 | header 508 px tall (3-line `<h1>` + 9 stacked badges); no horizontal overflow | `getBoundingClientRect` |
| `data.js` | 21.2 MB on disk (14.5 MB minified), 190 sessions, 30,405 turns; 14 MB on 12 Sep | `ls -la`, `JSON.stringify(...).length` |
| Export | dry-run, offline: **25.1 s**; watcher settle window 2 s | `time python3 scripts/export_dashboard.py --dry-run --no-live-quota` |
| Export collision | `[!] Error updating dashboard: [Errno 2] No such file or directory: '.../data.js.tmp' -> '.../data.js'` and `reentrant call inside <_io.BufferedWriter name='<stdout>'>` | `~/Library/Logs/Antigravity/telemetry_watcher.stderr.log`, 19 Sep 11:05 |
| Export writers with no lock | 3: watcher daemon, `AntigravityBar` refresh (`StatusStore.swift:122`), every V-gate that calls `export_dashboard.py` | `grep -nE 'flock\|fcntl\|lock' scripts/*.py` returns nothing |
| Vault | `data/antigravity_vault.db` 2.04 GB + `antigravity_vault.db.bak` 2.0 GB; `steps_archive` 63,504 rows, 75 MB `raw_metadata_blob`, **1,257 MB `raw_step_payload_blob`**; no `DELETE`/`VACUUM`/retention | `sqlite3 -readonly 'file:...?mode=ro'` |
| Theme default | HTML bootstrap: `theme = (saved === "light") ? "light" : "dark"`; CSS `:root` = dark tokens; ADR-048 and README say light is canonical | `dashboard/index.html:24`, `styles.css:33` |
| Hardcoded labels | `Billing: Renews 24 Sep` (`app.js:704`, `index.html:145`), `Safe in Pro Quota` (`app.js:690`), `100% Pro plan` (`app.js:3887`, `index.html:756`), `SQLite WAL Hook` (`index.html:175`) | grep |
| LaTeX in UI | `Average Prompt Context ($C_{prompt}$)`, `Session Pacing ($\Delta t$)` (`index.html:1201`, `:1237`) — gate V103 says zero | grep |
| Version identifiers | `package.json` 1.43.0; README badge v2.5.0; `git describe` → v1.47.0; highest tag v2.5.0; 63 tags | `git tag --sort=-v:refname` |
| ADR count claims | README line 33: 59; README line 299: 55; HANDOVER rows: 61 | grep |
| Personal path in public source | `StatusStore.swift:159` hardcodes `Documents/<private-dashboard-repo>`; publish needles only check `Users/<owner>` and `home/<owner>` | grep |
| Sessions table | 191 rows rendered at once, no paging | DOM count |

---

## 2. Scorecard Against the 12 Sep Audit

| 12 Sep item | Status on 19 Sep | Evidence |
|---|---|---|
| A1 cap removed, A2 timezone labels, A4 `meta.js`, A5 cost-weighted overage | **Done** | V95, V96, V101, V149; 191 DBs scanned; no "BST" literal in HTML |
| A3 stale gates rewritten | **Partly.** V1/V5 text changed; 11 gates still parse the empty hook and fail | §1 row "Gates that parse `injected-dashboard-data`" |
| C2 split HTML/CSS/JS | **Done**, but the JS is now 5,467 lines in one file and the inline handlers were kept (61) | `grep -c onclick=` |
| C5/C6 CI fixtures, `--no-live-quota` | **Done** | `ci.yml`, ADR-044 |
| C1 aggregator split | **Discarded (ADR-044)**. Respectfully: `aggregate_global_telemetry` is now 987 lines (was ~900). The reason given ("100% test-covered") is the reason it is *safe* to split, not a reason not to | `src/aggregator.py:1306` to EOF |
| C3 personal defaults as function defaults | **Not verified this pass** | — |
| C4 integrity test improvements | **Not done**; still substring-based; it did not catch the ADR-048/dark drift, the 1,778-line claim, or the version mismatch | `tests/test_docs_integrity.py` |
| M1–M6 (status file, pre-flight CLI, window attribution, weekly trends, cache coaching, markdown export) | **All done** | V110, V144, V119, V125, V120, V145 |
| U1 jobs-based tabs | **Done** (Now/Sessions/Projects/Swarms/Billing/Plan) | `switchTab` |
| U2 engineering vocabulary | **Half done.** ADR badges are gone. "Dual-Track Quotas", "Cost-Weighted Quota", "Dynamic Family Routing", "Zero cross-track contamination", "Isolation Policy: Zero Cross-Track Spillover", "Fallback Reserve Capacity", "Dual-Benchmark Throttle & Pacing Governor", "BVI", "SQLite WAL Hook" are all still on the Now tab | screenshot, Now tab |
| U3 simulator labels | **Regressed.** LaTeX is back; gate V103 still "passes" because it greps for `$N$` only | `index.html:1201` |
| U4 sessions paging/sort/search | **Sort and search done, paging not** | 191-row table |
| U5 contradictory hero signals | **Not done**, and a new one was added: "Credit Overages OFF" on Now vs "Spills over to Google One AI Credit Bank: 100 credits will be debited" on Plan | screenshots |
| U6 mobile header | **Not done** (508 px) | §1 |
| U7 accessibility | **Not done** (0 roles, 0 SVG titles) | §1 |
| U8 polish (4-decimal money in tables, badge count per title) | **Partly**: summary KPIs are 2-decimal; Model Matrix still shows `£18.8071`, `£3.2207` | screenshot, Now tab bottom |
| P1 doc drift | **Partly**: `SYSTEM_DESIGN.md:34` still claims 1,778 lines / 74 KB | grep |
| P2 HANDOVER §4 has no open work | **Not done** | 11/13 "Completed" |
| P3 slim `VDONE.md` | **Not done**; it tripled (43 KB → 139 KB) | `wc -c` |
| P4 mark AGENTS §4/§5 Antigravity-specific | **Not done** | `AGENTS.md` |
| P5 note on missing M04/M05 | **Not done** | grep "M04" HANDOVER → nothing |
| §7.1 `docs/FINDINGS.md`, §7.2 package | **Done** | files exist, package installs |

Net: the engineering backlog closed at roughly 80%. The process backlog closed at 0%.

---

## 3. Code & Correctness Findings

Each item: **what**, **why it matters**, **fix**, **gate**. Effort is for the maintaining agent.

### C1 — No export lock; three writers race on `dashboard/data.js` and the vault. *P0, 2 h*

**What**: `scripts/export_dashboard.py` writes `data.js.tmp` then `os.replace`s it. The watcher daemon, the menu bar app's refresh button (`StatusStore.swift:122` runs the same script), and every `VDONE.md` gate that shells out to the exporter can all run concurrently. Today at 11:05 two runs overlapped; one deleted the other's `.tmp` and crashed. Both also called `sync_conversations_to_vault()` against the same 2 GB SQLite file with a 5 s busy timeout.
**Why it matters**: a half-written `data.js` is a blank dashboard; a vault write collision is how the `.bak` file got there. This will recur every time the owner clicks "refresh" in the menu bar while the watcher is mid-export.
**Fix**:
1. In `export_telemetry`, take an exclusive advisory lock (`fcntl.flock`) on `dashboard/.export.lock` for the whole run. If the lock is held, print `[skip] export already running (pid N)` and exit 0 quickly.
2. Use a unique temp name (`tempfile.NamedTemporaryFile(dir=dashboard/, delete=False)`) instead of the fixed `data.js.tmp`, then `os.replace`.
3. Make the menu bar "refresh" button *signal* the watcher (touch a `~/.antigravity_refresh_requested` file the watcher polls, or `kill -USR1` the daemon PID from the plist) instead of spawning a second exporter. If that is too much for one slice, at least have the Swift side check the lock file and show "export in progress".
4. Remove `export_dashboard.py` from every `VDONE.md` gate (see D1); ops checks move to `scripts/ops_check.py`.
**Gate**: `tests/test_export_lock.py` starts two `export_telemetry()` calls in threads against the fixture dir; exactly one produces output, the other returns the skip code; `data.js` is byte-identical to a single run. `grep -c 'data.js.tmp' scripts/export_dashboard.py` returns 0.

### C2 — Four hardcoded labels and one wrong default contradict the data on screen. *P0, 3 h*

| Label | Where | What it should be |
|---|---|---|
| `Billing: Renews 24 Sep (24 days, 2 hours left)` | `app.js:704`, `index.html:145` | The date is a string literal; only the countdown is live. Today the Billing tab correctly says 13 Oct. Render from `summary.monthly_renewal_utc` with `Intl.DateTimeFormat`. |
| `● Safe in Pro Quota` | `app.js:690` | Tier-agnostic: `Safe in quota` or `Safe in ${tierShortName} quota`. It currently sits 8 px from a badge that says "Ultra Tier Active". |
| `100% Pro plan • £0.00 actual overage` | `app.js:3887`, `index.html:756` | Same tier substitution. |
| `SQLite WAL Hook` | `index.html:175` | Not user information. Replace with a data-freshness pill: `Local · read-only · updated 16:33` (from `meta.js` `generated_at`). |
| Simulator default plan = Google AI Pro ($20 5h / $129 wk) | Plan tab | The account is Ultra 5x ($100 / $645). The default forecast says "Burst Cooldown, Exceeded +101.5%" for a workload that would use 40% of the real 5h cap. Default the tier selector to `summary.tier`. |
| "Spills over to Google One AI Credit Bank: 100 credits will be debited" | Plan tab callout | `use_ai_credits` is `false` in `pricing.json`, and the Now tab says "Credit Overages OFF". The simulator must read the same flag and say "hard stop at limit" instead. |

**Gate**: `grep -cE 'Renews 24 Sep|Safe in Pro Quota|100% Pro plan|SQLite WAL Hook' dashboard/index.html dashboard/app.js` returns 0. A Playwright test loads the fixture payload with `tier: ultra_5x` and asserts the header status badge text, the billing badge date, and the simulator's selected tier all match the payload. Add a fixture variant with `use_ai_credits: false` and assert the simulator callout contains "hard stop".

### C3 — `initDashboard()` runs on every data reload and re-registers listeners. *P1, 3 h*

**What**: `checkAndReloadTelemetry` calls `initDashboard()` whenever `payload_sha1` changes (`app.js:1682`, `:1698`). `initDashboard` calls `initShellMode`, `initMicroTooltips`, `initAutoRefresh`, `initPlanManagerModal`, `initSimulator`, `initWeeklyTrends`, which together add 15 `addEventListener`s each time, including a new `visibilitychange` listener and a new click handler on the auto-refresh button. The network log showed paired `meta.js` requests 1 ms apart within a minute of load.
**Why it matters**: after a working day with the tab open, each toggle fires N times, each `visibilitychange` fires N reloads of a 21 MB file, and the 803-line function rebuilds every table on every tick.
**Fix**: split `initDashboard` into `bootOnce()` (listeners, shell, tooltips, modal, simulator wiring; guarded by a module-level `booted` flag) and `render(data)` (pure DOM from data). `checkAndReloadTelemetry` calls only `render`. While there, replace the 61 inline `onclick=` with delegated listeners in `bootOnce` so the demo on GitHub Pages can later ship a CSP.
**Gate**: Playwright test: load page, trigger three simulated reloads by rewriting `meta.js`, then assert `getEventListeners(document).visibilitychange.length === 1` (via CDP) and that clicking the currency toggle changes the DOM exactly once.

### C4 — Truncation alarm uses one global 200k threshold and is permanently red. *P1, 2 h*

**What**: `export_dashboard.py:129,167` and `app.js:5182,5216` treat `peak_prompt_depth >= 200000` as "Truncated (>200k) — Handover needed immediately", regardless of model. It fires a red badge in the header, a red strip on the Now tab, and a red block at the top of Sessions. Today all three are lit for a session on Gemini 3.1 Pro.
**Why it matters**: if the threshold is right for Claude Opus but wrong for a 1M-context Gemini model, the loudest element on every tab is a false alarm and users learn to ignore it. If it is right, it still should not be more prominent than the quota state the tool exists to show.
**Fix** (decided, §7 #4: per model family): (a) take the truncation boundary per model family from the ADR-060 postmortem evidence and put it in `models.json` (`context_truncation_tokens`, 200000 as the fallback for unknown IDs); (b) compute severity from `peak / threshold(model_id)`; (c) demote the header badge to amber-on-hover and keep the Sessions-tab widget as the one full-size surface; the Now-tab strip shows only when the *current* session is above 80% of its threshold.
**Gate**: unit test with two sessions at 244k tokens on models with 200k and 1M thresholds asserts critical vs normal. Playwright: with the fixture payload, the header contains at most one red badge.

### C5 — `data.js` is 21 MB, pretty-printed, and fully embedded on every load. *P1, 4 h*

**What**: `json.dumps(payload, indent=2, sort_keys=True)` (`export_dashboard.py:455`) adds ~30% whitespace; the file carries all 30,405 turns of all 190 sessions; the browser parses all of it before first paint; growth is ~1 MB/day.
**Fix** (keep determinism; `sort_keys=True` stays):
1. `separators=(",", ":")` and `indent=None` for `data.js`; keep `data.json` pretty if humans read it.
2. Move `conversations[*].turns` into a second file `turns.js` loaded lazily when the Sessions inspector opens a session (`window.__TELEMETRY_TURNS__[convo_id]`), or one file per session under `dashboard/turns/<id>.js`. `summary`, `quotas`, `projects`, `swarms`, `weekly_trends` stay in `data.js`.
3. Cap turns in the main payload to the current weekly cycle; older turns are in the vault and can be fetched on demand.
**Gate**: `ls -l dashboard/data.js` under 3 MB with the live dataset; CI determinism diff still empty; first-paint (Playwright `domcontentloaded` to hero visible) under 1 s on the fixture.

### C6 — Vault has no retention and a 2 GB stray backup. *P1, 1 h (retention declined, see §7 #3)*

**What**: `steps_archive` stores `raw_step_payload_blob` for every step, forever (1.26 GB). `antigravity_vault.db.bak` (2.0 GB) is a manual copy that nothing reads. Both are under `data/`, gitignored, but they make every `sync_conversations_to_vault()` slower and Time Machine larger.
**Fix** (decided, §7 #3: keep everything, delete the `.bak` only): confirm `PRAGMA integrity_check` on the live vault, delete `antigravity_vault.db.bak`, log the vault size after each sync in `meta.json` (`vault_bytes`) so the dashboard and the owner can watch growth. Document in `SYSTEM_DESIGN.md` §Vault that the archive is lossless and unbounded by design, with the observed growth rate, so a future retention decision has a number to start from.
**Gate**: `python3 -c "import sqlite3; c=sqlite3.connect('file:data/antigravity_vault.db?mode=ro', uri=True); print(c.execute('PRAGMA integrity_check').fetchone())"` prints `ok`; `test -e data/antigravity_vault.db.bak` fails; `meta.json` contains `vault_bytes`.

### C7 — Watcher cadence cannot keep up with export cost. *P2, 2 h*

**What**: settle window 2 s, export 25 s (offline dry-run; live is longer because of vault sync). During active coding the daemon is permanently exporting; the log shows exports at 16:25:10, 16:28:24, 16:33:58.
**Fix**: make the settle window adaptive (`max(2 s, last_export_duration)`), log export duration in the stdout log, and expose it in `meta.json` as `export_seconds` so the HUD can show "data 28 s old" instead of implying 3 s.
**Gate**: `grep 'export took' ~/Library/Logs/Antigravity/telemetry_watcher.stdout.log | tail -1` prints a duration; `meta.json` contains `export_seconds`.

### C8 — `demo.html` is a copy of `index.html`. *P2, 1 h*

**What**: 1,635 identical lines except `data.js` → `data.demo.js`. Every UI change must be made twice, and a parity gate (V247/V252) exists only because the duplication exists.
**Fix**: delete `demo.html`; `index.html` reads `?demo=1` (already handled in `checkAndReloadTelemetry`) and injects `<script src="data.demo.js">` from the bootstrap snippet when present. Update `deploy_pages.yml` to publish `index.html` with `data.demo.js` renamed to `data.js`, which it already effectively does.
**Gate**: `test -e dashboard/demo.html` fails; Playwright loads `/index.html?demo=1` and asserts the demo banner is visible.

### C9 — Personal folder path compiled into the public menu bar app. *P2, 30 min*

**What**: `StatusStore.swift:159` falls back to `~/Documents/<private-dashboard-repo>` (private repo folder name). The publish sanitiser only checks `Users/<owner>` and `home/<owner>`.
**Fix**: read the repo path from the status hook (`dashboard_path` already exists) and from an env var `ANTIGRAVITY_DASHBOARD_REPO`; drop the literal. Add private workspace folder substrings to `forbidden_needles` in `publish_to_public.py`.
**Gate**: `git grep -i '<private-repo-needle>' -- ':!scripts/publish_to_public.py' ':!tests/test_sanitization.py'` returns nothing.

### C10 — Menu bar app spawns `pgrep` every 5 s. *P3, 1 h*

**What**: `StatusStore.checkWatcherStatus()` runs `/usr/bin/pgrep -f watch_telemetry.py` on a 5 s timer *and* on every file event. README claims "0.0% idle CPU".
**Fix**: have the watcher write its PID and a heartbeat timestamp into the status hook (`watcher: {pid, heartbeat_utc}`); the app reads it and shows "inactive" when the heartbeat is older than 30 s. No process spawning.
**Gate**: `grep -c pgrep macos/AntigravityBar/Sources/AntigravityBar/StatusStore.swift` returns 0; status hook contains `watcher.heartbeat_utc`.

### C11 — `aggregate_global_telemetry` is 987 lines (ADR-044 deferred the split). *P3, 1 d*

**What**: the function grew by ~90 lines in a week. ADR-044's argument was "stable and 100% covered, zero user value". The user value is in the next ten milestones: every one of them edits this function, and the diff review cost scales with its length.
**Fix**: reopen as a zero-behaviour-change refactor when the next backend milestone is planned, not before. Extract along the seams that already exist as local variables: projects/branches, provider silos, runway, temporal provenance, simulator presets, payload assembly. Keep the public function name. Prove with `diff data.json` before/after at a fixed `--reference-time`.
**Gate**: byte-identical `data.json` on the fixture; longest function in `src/aggregator.py` under 250 lines.

---

## 4. UI & UX Findings

### U1 — The Now tab still explains itself in engineering terms. *P1, 2 h*

Every card on the Now tab carries two or three provenance pills. Observed strings: "Dual-Track Quotas", "Live Desktop Sync", "Live Auto-Refresh: ON (3s)", "Cost-Weighted Quota", "Dynamic Family Routing", "Zero cross-track contamination", "Isolation Policy: Zero Cross-Track Spillover", "Fallback Reserve Capacity: 100% Ready (Zero Contamination)", "Dual-Benchmark Throttle & Pacing Governor", "5h Burst Governor", "VELOCITY (BVI)", "Credit Overages OFF", "Track 1 / Track 2", "Hard-Blocking".
**Fix**: one label per card, plain English, mechanism behind an `ⓘ` tooltip that already exists (`initMicroTooltips`). Suggested copy:

| Now | Proposed |
|---|---|
| Antigravity Provider Quota Silos · Dual-Track Quotas | **Quota right now** |
| Gemini Models · Credit Overages OFF · Track 1 | **Gemini** · *hard stop at limit* (tooltip: overage credits disabled in plan) |
| Weekly Quota Runway · On Track (0.58x) · Dual-Benchmark Throttle & Pacing Governor | **Weekly pace** · *Under budget (0.58× of even pace)* |
| VELOCITY (BVI) 0.58x · Day 4: +36.7% buffer (21.1% vs 57.2%) | **Pace** 0.58× · *Day 4: used 21% of week, even pace would be 57%* |
| Claude & GPT Models · Hard-Blocking · Track 2 · Isolation Policy: Zero Cross-Track Spillover | **Claude & GPT** · *separate allowance, hard stop* |
| Fallback Reserve Capacity 100% Ready (Zero Contamination) | delete (it is the same fact as the 100% bar above it) |

**Gate**: `grep -ciE 'contamination|spillover|governor|dual-track|dual-benchmark|family routing|isolation policy' dashboard/index.html dashboard/app.js` returns 0 outside comments and tooltips.

### U2 — Header carries 9 badges, 3 of them toggles, and the `<h1>` is 32 px of marketing. *P1, 3 h*

At 1440 px the header is two rows of pills; at 375 px it is 508 px tall before any data appears (screenshot in §1). The title repeats the sidebar brand. The three toggle groups (currency, theme, shell) are settings, not status, and already exist in the sidebar footer.
**Fix**: header = one line: compact title (`clamp(18px, 2.2vw, 26px)`), status pill (Safe / Caution / Exhausted, derived from `subscription_status`), tier pill, freshness pill, and an overflow `⋯` menu for Copy Summary and the toggles when the sidebar is collapsed or on mobile. Keep the sidebar footer toggles as the primary home for settings. Remove the duplicate `#currency-toggle-group`, `#theme-toggle-group`, `#header-shell-toggle` from the header on viewports under 960 px.
**Gate**: Playwright at 375×812: `header` height under 160 px; at 1440×900: under 72 px; the existing zero-overflow test still passes.

### U3 — Sessions tab leads with the truncation audit, not with sessions. *P1, 1 h (after C4)*

The first screen of "Sessions" is "Context Boundary & Truncation Audit" with 12 red-dotted rows and "Handover" buttons; the Conversations Explorer (the actual job of the tab) starts below the fold.
**Fix**: order = search/filter bar → Conversations table (paged, 25 rows, sticky header) → truncation audit as a collapsed accordion with a count badge. Paging: client-side `slice(page*25, (page+1)*25)` with prev/next, sort applies before paging.
**Gate**: Playwright: `#view-sessions table tbody tr` count ≤ 25 on load; the first `h2` in `#view-sessions` reads "Conversations".

### U4 — Simulator: LaTeX labels, Pro default, storage-size tier names. *P1, 2 h*

Observed: `Average Prompt Context ($C_{prompt}$)`, `Session Pacing ($\Delta t$)`, tier dropdown "Google AI Pro (2 TB / 5 TB / 10 TB) ($20 5h / $129 wk) 1x Capacity". This is the 12 Sep U3 item, regressed.
**Fix**: labels "Average prompt size (tokens)" and "Minutes between turns"; tier names "Pro (1×)", "Ultra (5×)", "Ultra (20×)"; default tier from `summary.tier` (C2). Fix gate V103 so it actually greps for `\$[A-Za-z\\]` in the HTML.
**Gate**: `grep -cE '\$[A-Za-z\\{]' dashboard/index.html` returns 0.

### U5 — Accessibility baseline is still absent. *P2, 4 h*

0 tab roles, 0 progressbar roles, 0 SVG titles, 0 table captions, 106 sub-11 px text nodes, colour-only status in badges.
**Fix**: `role="tablist"` on `.dock-nav-list` and `.tab-buttons-group`, `role="tab" aria-selected` on each button, `role="tabpanel" aria-labelledby` on each `.tab-view`; `role="progressbar" aria-valuenow/min/max aria-label` on every `.progress-fill` parent; `<title>` on the recovery timeline, trend chart and DAG SVGs; `<caption class="sr-only">` per table; raise `--font-xs` to 11 px minimum; add a `✓ / ! / ×` glyph to status badges so colour is not the only signal. Focus rings: `:focus-visible { outline: 2px solid var(--border-focus) }` for buttons (currently only inputs and selects have focus styles).
**Gate**: Playwright + `@axe-core/playwright` (one devDependency): zero "serious" or "critical" violations on all six tabs in both themes.

### U6 — Numbers and units. *P2, 1 h*

Model Matrix shows `£18.8071` and `£3.2207`; Weekly Trends shows `1.24B` and `328.4M` in the same row family as `£41.06`; the ticker shows `147.6k/m` (per minute) next to `118.1M tok` (per 5 h) with no unit on the first.
**Fix**: money to 2 decimals everywhere except the per-turn inspector; `147.6k tok/min`; one compact-number formatter (there are currently three: `formatCompactNumber`, `formatTokensCompact`, `formatCompactTokens`).
**Gate**: `grep -cE 'function format(Compact|Tokens)' dashboard/app.js` returns 1; Playwright asserts no `£\d+\.\d{3,}` outside `#turns-table`.

### U7 — Theme default contradicts ADR-048 and the README. *P2, 30 min*

Decided (§7 #1): **light is the default**. Restore the bootstrap in `index.html:24` (`theme = (saved === "dark") ? "dark" : "light"`), make `:root` carry the light tokens in `styles.css:1-33`, and set `let activeTheme = "light"` in `app.js`. ADR-048 stays Adopted; showcase PNGs are already light and stay.
**Gate**: V177 passes; Playwright with cleared `localStorage` asserts `document.documentElement.dataset.theme === "light"`.

### U8 — Mobile is functional, not designed. *P3, 3 h (mostly delivered by U2)*

After U2, remaining items: the ticker HUD clips on the left at 375 px (`9% Cache` visible, model name cut); tables need `overflow-x: auto` wrappers with a right-edge fade; the bottom nav is good and should stay.
**Gate**: Playwright at 375×812 screenshots of all six tabs attached to the milestone doc; no element's `getBoundingClientRect().left < 0`.

---

## 5. Ceremony & Documentation Bloat

This section answers the owner's direct question. The verdict is: **the ceremony is now the main source of defects**, and it can be cut by ~85% without losing a single guarantee.

### 5.1 `VDONE.md` — from 1,485 lines to under 150

**Diagnosis**
- It is an append-only log. 258 gates across 47 milestones, none retired. Sections are titled "Phase 1..11" and "Milestone 2..47" interchangeably; "Phase 10" is used twice (M30 and M36); V13–V15 are used twice.
- 144 of 258 gates have side effects (export, daemon restart, `git`, Playwright) and cannot run in CI. Of the 114 that can, 33 fail. So the file proves nothing about the present.
- Every gate is copied verbatim into the milestone doc, so the information exists twice.
- ADR-047 (`AGENTS.md` §3.6) mandates a "Live Operational Gate" in every milestone that restarts the daemon and re-exports live data. That is an *ops check*, not an *acceptance gate*, and it is why every milestone's V-block is 40 lines.
- Gates are written to pass, not to catch: V105 "Two-Decimal Money" checks that an element id exists; V103 "zero LaTeX" greps for one token; V243 contains `or True`.

**Proposed shape** (write this as the whole file):

```markdown
# VDONE — Active Acceptance Gates
Active branch: (run `git rev-parse --abbrev-ref HEAD`; never write it here)

## A. Always-on gates (run by tests/test_vdone_gates.py and by CI)
A1 Unit suite            CHECK python3 -m unittest discover -s tests -p 'test_*.py' -k 'not playwright'   EXPECT OK, < 15 s
A2 Determinism           CHECK (export fixture twice; diff)                                                  EXPECT empty diff
A3 Docs integrity        CHECK python3 -m unittest tests.test_docs_integrity                               EXPECT OK
A4 Model roster          CHECK python3 -m unittest tests.test_model_roster_integrity                       EXPECT OK
A5 No stale numbers      CHECK python3 -m unittest tests.test_docs_integrity -k numbers                    EXPECT OK
A6 Clean tree            CHECK git status --porcelain                                                       EXPECT empty
A7 Front-end             CHECK npx playwright test                                                          EXPECT OK (local + nightly CI)

## B. Current milestone gates (M48) — deleted when the milestone closes; the proofs go into docs/milestones/M48_*.md
B1 ...  CHECK ...  EXPECT ...
```

**Mechanics**
1. Create `tests/test_vdone_gates.py`: parses `VDONE.md`, runs every `CHECK` in section A and B whose command starts with `python3 -c`, `python3 -m unittest`, `grep`, `test`, or `diff`; asserts exit 0. Anything else in a CHECK is a test failure ("side-effecting command in VDONE"). This makes rot impossible: a stale gate fails the suite.
2. Move ops checks (export live, restart daemon, restart menu bar, status) into `scripts/ops_check.py` that prints a one-line summary. The milestone doc's "Verification" section records that line. ADR-047 is amended: "ops_check at milestone close", not "gates in VDONE".
3. Archive: move today's `VDONE.md` to `docs/milestones/VDONE_ARCHIVE_M01-M47.md` once, unchanged, for history. Do not maintain it.
4. Milestone close ritual: section B is emptied, its gates and proofs are pasted into the milestone doc, and the doc gets the `ops_check` line. That is the only copy.

**Gate for D1**: `wc -l VDONE.md` < 150; `python3 -m unittest tests.test_vdone_gates` passes; `grep -c 'export_dashboard\|setup_service\|setup_menubar' VDONE.md` returns 0.

### 5.2 `README.md` — from 536 lines to ~150, plus `CHANGELOG.md`

**Diagnosis**
- "Core Capabilities" is 21 numbered sections, one per milestone, in milestone order, each citing its ADR and milestone number. That is a changelog. A reader who wants to know what the tool does has to read M37, then M24, then M09/17/32.
- Two disclaimers, ten badges, an 80-line Mermaid diagram, a 100-line repository tree that duplicates `docs/`, and a "Documentation Hub" table that duplicates `CLAUDE.md`'s orientation table.
- `tests/test_docs_integrity.py` requires **every** `src/`, `scripts/`, `tests/` filename to appear in README. That rule guarantees README grows with the code forever and rewards stale mentions.
- Numeric claims in prose ("59 ADRs", "55 ADRs", "356 KB, 0.0% idle CPU", "<320 lines", "19 models") drift within days.

**Proposed shape**
1. **Top**: one sentence, one hero screenshot, three bullets: what it reads, what it shows, what it never does (write/proxy/bill).
2. **Quickstart**: the existing §Quickstart, trimmed to the five commands a new user needs.
3. **What you get**: six short paragraphs, one per tab (Now, Sessions, Projects, Swarms, Billing, Plan), each with one screenshot. No milestone or ADR numbers.
4. **Calibration note**: the one sentence agreed on 12 Sep (single subscription, edit `config/pricing.json`).
5. **Docs**: five links (Findings, Telemetry Spec, System Design, Package README, Handover). Delete the hub table.
6. **Contributing / License**: two lines each.
7. Move the 21 capability entries to `CHANGELOG.md` in Keep-a-Changelog format, one `## [vX.Y.Z] – date` per milestone, three bullets max each. Future milestones add there, never to README.
8. Move the repository tree to `docs/REPO_MAP.md` and point `test_docs_integrity` at *that* file. README no longer has to name every file.
9. Delete every number that can drift; where a number matters, make it a CHECK in VDONE §A5.

**Gate for D2**: `wc -l README.md` < 180; `grep -cE 'Milestone [0-9]+|ADR-[0-9]+' README.md` returns 0; `test -f CHANGELOG.md`; `test -f docs/REPO_MAP.md`; docs integrity passes against `REPO_MAP.md`.

### 5.3 `docs/HANDOVER.md` — keep the role, halve the words

**Diagnosis**: the ADR table is the right idea, but rows are 700–1,100 characters of narrative ("Formally discarded and indefinitely deferred Item 1 from the Senior Engineering Audit…"). §4 is titled "Open Work Register" and contains almost only closed work, so a fresh agent reads it and finds nothing to do. No ADR has ever been marked Superseded, although ADR-048 (light default) is contradicted by the code.

**Fix**
1. ADR row format: `| ID | Title | Status | One sentence, ≤ 160 chars | link to milestone doc |`. The reasoning lives in the milestone doc. Rewrite the 61 rows once (mechanical, ~2 h).
2. Add statuses `Superseded (by ADR-nnn)` and `Retired`. ADR-048 stays Adopted (light default restored, §7 #1); mark ADR-004's "inject JSON into index.html" as superseded by ADR-024; mark ADR-044 Superseded when row 17 lands (§7 #6).
3. §4 becomes two lists: **Open** (this audit's backlog rows that remain, one line each, with branch name) and **Closed this quarter** (one line each). Closed items older than a quarter are deleted; the milestone docs have them.
4. §3 Milestone Index: one line per milestone (`M47 · 2026-09-18 · Context safety strip · doc link`). Delete the "verified test commands" column; VDONE §A covers it.
5. Add the missing note that M04 and M05 were never used.

**Gate for D3**: `awk 'length > 300' docs/HANDOVER.md | wc -l` returns 0; §4 "Open" list is non-empty and every entry names a branch.

### 5.4 `AGENTS.md` and `CLAUDE.md` — mostly fine; four edits

`AGENTS.md` is inside its own budget (106 lines) and is the best-written file in the repo. `CLAUDE.md` is correctly a pointer. Edits:

1. §3.6 (ADR-047): replace "VDONE.md must include a dedicated Live Operational Gate" with "run `scripts/ops_check.py` at milestone close and record its one-line output in the milestone doc". This is the single rule change that stops VDONE bloat.
2. §4 and §5: prefix with `> Antigravity IDE only. Other agents: skip this section.` (12 Sep P4).
3. Add §1.9 **Documentation numbers rule**: "Prose documents never state counts, sizes, durations or line numbers that can drift (test counts, ADR counts, file sizes). If a number matters, it is a CHECK in `VDONE.md` §A or a badge computed in CI." This rule would have prevented six of the drifts in §1.
4. Add §2.5 **Single exporter rule**: "Only one `export_dashboard.py` may run at a time (advisory lock). UI clients request a refresh; they do not spawn exporters." (C1)
5. `CLAUDE.md`: delete the Orientation table (it duplicates README §Docs and `HANDOVER.md` §1); keep the four "Read first" bullets.

### 5.5 Milestone docs — a fixed template

Current docs range from 27 to 168 lines and mix design narrative with gate copies. Template (≤ 60 lines):

```
# Mnn · <title> · <date> · <tag>
## Why (2–4 lines, the user need, link to ADR row)
## What changed (files touched, one line each)
## Decisions taken (ADR-nnn one-liners added to HANDOVER)
## Gates & proofs (the section-B gates from VDONE at close, with actual output)
## Ops check (one line from scripts/ops_check.py)
## Screenshots (UI milestones only; before/after pairs)
```

### 5.6 Test suite ceremony

- Move `tests/test_playwright_e2e.py` out of the default discovery (`tests/e2e_bridge/`) so `python3 -m unittest discover -s tests` takes ~8 s instead of 69 s and does not depend on Chrome. CI gets a separate `e2e` job on `ubuntu-latest` with `npx playwright install --with-deps chromium` and the demo payload; nightly, not per-push, until it proves stable.
- The seven `print()` calls and the exporter's stdout leak ("Successfully exported 0 conversation sessions…") during tests should be captured (`contextlib.redirect_stdout`) so a failing test is visible.
- `tests/test_docs_integrity.py` gains: (a) a check that every `python3 -c` gate in VDONE exits 0 (or delegate to `test_vdone_gates`); (b) a check that no file under `docs/` or README contains `\d+,\d{3} lines` or `\d+ KB` or `\d+ tests` outside `docs/milestones/` and `docs/AUDIT_*`; (c) a check that `package.json` version equals the highest `v*` tag.

### 5.7 Versioning

One scheme. Recommended: semantic `v2.x.y` from here (the README badge already says v2.5.0); stop the `v1.<M>.0` milestone tags; `package.json` and `pyproject.toml` versions are bumped by the same commit that tags. Delete the release badge from README or have CI derive it.

---

## 6. Prioritised Backlog

One branch per row. Rows 1–3 are a single docs-only milestone (**M48 "Consolidation"**) and should be done first, in one session, before any feature work. Rows marked "after N" touch the same files as row N.

| # | Item | Type | Pri | Effort | Branch | Blocking decision |
|---|---|---|---|---|---|---|
| 1 | D1 — `VDONE.md` to §A/§B, `test_vdone_gates.py`, `ops_check.py`, archive old file, amend ADR-047 in AGENTS §3.6 | docs+test | P0 | 4 h | `docs/m48-consolidation` | — |
| 2 | D2 — README front door, `CHANGELOG.md`, `docs/REPO_MAP.md`, integrity test retargeted, numbers rule | docs+test | P0 | 4 h | same | — |
| 3 | D3 — HANDOVER ADR rows ≤ 160 chars, Superseded status, real Open list, one-line milestone index, M04/M05 note; AGENTS §4/§5 marker; CLAUDE table removed; semantic `v2.x.y` version scheme (§7 #5) | docs | P0 | 3 h | same | decided |
| 4 | C1 — export lock, unique temp file, menu bar requests refresh instead of spawning | fix | P0 | 2 h | `fix/export-lock` | — |
| 5 | C2 + U4 + U7 — hardcoded labels, simulator default tier and overage flag, LaTeX labels, honest V103, light theme default restored (§7 #1) | fix | P0 | 4.5 h | `fix/labels-and-simulator-defaults` | decided |
| 6 | C3 — `bootOnce()` / `render()` split, delegated listeners | refactor | P1 | 3 h | `refactor/dashboard-boot` | — |
| 7 | U1 + U2 — plain-language Now tab, one-line header, mobile header | ui | P1 | 5 h | `ui/plain-header` | after 6 |
| 8 | C4 + U3 — per-model truncation threshold (§7 #4), demoted alarm, Sessions tab order + paging | fix+ui | P1 | 4 h | `feat/truncation-per-model` | decided |
| 9 | C5 — compact `data.js`, lazy `turns.js` | perf | P1 | 4 h | `perf/lazy-turns` | — |
| 10 | C6 — integrity check, `.bak` removal, vault size in `meta.json` (no retention, §7 #3) | ops | P1 | 1 h | `chore/vault-bak-removal` | decided |
| 11 | C7 — adaptive settle window, export duration in log and meta | perf | P2 | 2 h | `perf/watcher-cadence` | after 4 |
| 12 | C8 — delete `demo.html`, `?demo=1` | cleanup | P2 | 1 h | `chore/single-index` | after 6 |
| 13 | C9 + C10 — Swift path literal, pgrep → heartbeat | fix | P2 | 1.5 h | `fix/menubar-hygiene` | — |
| 14 | U5 + U6 — a11y roles/titles/captions, axe in Playwright, one number formatter, 2-decimal money | ui | P2 | 5 h | `ui/a11y-baseline` | after 7 |
| 15 | 5.6 — e2e out of default discovery, nightly CI e2e job, stdout capture | test | P2 | 2 h | `ci/e2e-nightly` | — |
| 16 | U8 — mobile pass, ticker clipping, table scroll wrappers | ui | P3 | 3 h | `ui/mobile-pass` | after 7 |
| 17 | C11 — aggregator split (reopen ADR-044, §7 #6), strictly last | refactor | P3 | 1 d | `refactor/aggregator-modules` | decided |

Total for P0 + P1: roughly 4.5 working days. Rows 1–3 alone remove ~200 KB of documentation and make the remaining gates executable. Feature milestones are frozen until rows 1–5 are merged (§7 #2).

### 6.1 Instructions for the maintaining agent

1. Read `AGENTS.md`, then this file. State `Active Branch:` in every update. Do rows 1–3 as **M48 "Consolidation"** before anything else; it changes the rules the later rows are verified under.
2. For row 1, do not "improve" old gates. Archive the file whole, write the new one from the template in §5.1, and write `tests/test_vdone_gates.py` first so the new file is executable from its first commit.
3. For row 2, the 21 capability sections move to `CHANGELOG.md` *as they are*; do not rewrite them. README gets new, short text.
4. Every UI row (7, 8, 14, 16) attaches before/after screenshot pairs at 1440×900 and 375×812 to its milestone doc, captured with the existing `e2e/visual-screenshots.spec.js`.
5. Rows 4, 9, 10, 11 change export behaviour. Prove determinism with the fixture (`--antigravity-dir tests/fixtures/antigravity --no-live-quota --reference-time 2026-09-05T14:30:00Z`, run twice, `diff`). Never run two live exports concurrently while row 4 is unmerged.
6. Feature freeze is in effect (§7 #2): do not start a new dashboard feature milestone until rows 1–5 are merged. If asked to, say so, cite §7 #2, and ask the owner to lift the freeze explicitly.
7. Update `HANDOVER.md` §4 "Open" with the rows of this table that remain, one line each. This file is point-in-time; do not edit it, supersede it.
8. `AGENTS.md` §5 (context boundary) applies: rows 1–3 are one session; rows 4–5 are one session; do not chain more than one refactor row in a single thread.

---

## 7. Owner Decisions (taken 19 Sep 2026)

All six questions were answered by the owner in the audit session. They are settled; the maintaining agent implements against them without re-asking and logs each as an ADR one-liner when its backlog row lands.

| # | Question | Decision | Consequence |
|---|---|---|---|
| 1 | Theme default: light or dark? | **Light.** | Restore `index.html:24` bootstrap and `:root` tokens to light; gate V177 passes again; ADR-048 stays Adopted; showcase PNGs stay as they are. |
| 2 | Freeze feature milestones until M48 (rows 1–5) lands? | **Yes, freeze.** | The agent declines new feature milestones until rows 1–5 are merged. If asked for one, it says so and points to this table. |
| 3 | Vault retention for raw step payload blobs? | **Keep everything; delete the `.bak` only.** | No retention rule. Row 10 shrinks to: `PRAGMA integrity_check` on the live vault, delete `antigravity_vault.db.bak`, write vault size into `meta.json`. The owner accepts ~1 GB/month growth at current usage; revisit if export time or disk becomes a problem. |
| 4 | Truncation threshold: global 200k or per model family? | **Per model family**, 200k fallback for unknown IDs. | Thresholds go into `models.json` from the ADR-060 evidence; header badge demoted to amber-on-hover; Sessions tab keeps the full widget. |
| 5 | Version scheme? | **Semantic `v2.x.y` only.** | Stop `v1.<M>.0` tags. `package.json`, `pyproject.toml` and the tag are bumped in the same commit. README badge is CI-derived or removed. |
| 6 | Reopen the aggregator split (ADR-044)? | **Yes, but last** (row 17). | Zero-behaviour-change refactor after all other rows, proven by byte-identical `data.json` on the fixture. ADR-044 gets status Superseded when row 17 lands. |

---

## 8. Appendix — gate execution script used for §1

Saved outside the repo during the audit; reproduce with:

```python
import re, subprocess, pathlib
txt = pathlib.Path("VDONE.md").read_text()
gates = re.findall(r"^### (V\d+)[^\n]*\n- \*\*CHECK\*\*: `(.*?)`\s*$", txt, flags=re.M)
BAD = ("export_dashboard","setup_service","setup_menubar","build_menubar","git ","unittest",
       "watch_telemetry","npx","playwright","capture_showcase","publish_to_public","launchctl",
       "build_demo","ingest_statement","configure_plan","quota_regression","agy_quota",
       "build_ci_fixtures","setup_github")
ran = failed = 0
for gid, cmd in gates:
    if not cmd.startswith("python3 -c") or any(b in cmd for b in BAD):
        continue
    ran += 1
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        failed += 1
        print("FAIL", gid, (p.stderr.strip().splitlines() or ["?"])[-1][:100])
print(f"ran {ran}, failed {failed}")
```

Result on 19 Sep 2026 at `5f71122`: `ran 114, failed 33`.
