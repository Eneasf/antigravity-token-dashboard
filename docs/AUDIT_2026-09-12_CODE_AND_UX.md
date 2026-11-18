# Engineering & UI/UX Audit — 12 Sep 2026

**Scope**: whole repository at commit `4485972` on `main` (clean tree, 111/111 tests passing).
**Method**: read `AGENTS.md`, `README.md`, `docs/HANDOVER.md`, `VDONE.md`, all of `src/`, `scripts/`, `tests/`, and `config/pricing.json`; rendered `dashboard/index.html` with the live `data.js` payload over a local HTTP server at 1440×900 and 375×812 in both themes; inspected all four tabs. No code was changed.
**Audience**: the maintaining AI agent and the repository owner. Every recommendation carries a priority, an effort estimate, and the acceptance evidence expected under `VDONE.md`. The six owner decisions that gate implementation were taken in the same session and are recorded in §6; nothing in this document is waiting on the owner except the tab-plan sign-off noted in §6 #4.

---

## 0. Executive Summary

The engine is unusually well built for a personal tool: zero-dependency protobuf decoding, strict read-only SQLite access, deterministic exports, a 111-test suite, and a disciplined ADR/milestone trail. The weaknesses are almost all on the *presentation and product* side, plus a handful of correctness cracks that the documentation has not caught up with:

| Area | Verdict | Headline |
|---|---|---|
| Intended use | Clear, but the tool has outgrown its framing | It is now a **quota governor and spend-forecasting cockpit**, not a "token consumption dashboard". The name, README hero, and tab structure still describe the M01 version. |
| Correctness | Good core, four real cracks | Lifetime totals silently truncate at 100 of 144 databases; "19:00 BST" is baked as a string and becomes wrong on 25 Oct; two stale `VDONE.md` gates check a data hook that is now empty; the 30-second auto-refresh re-parses a 14 MB file every tick. |
| Code quality | Strong engine, monolithic UI | `src/aggregator.py` (2,100 lines) and `dashboard/index.html` (4,529 lines, 211 KB, ~2,800 lines of inline JS) are the two files every change touches. The README still calls the HTML "lean 1,778-line". |
| Dashboard UX | Information-rich, hierarchy-poor | Weekly quota is shown three times above the fold; internal ADR badges leak into the product UI; the 100-row conversation table has no sort, search, or paging; the simulator renders raw LaTeX in its labels; the header collapses into a badge stack on mobile. |
| Docs & process | Excellent discipline, some drift | `VDONE.md` still says `Active Branch: feat/what-if-workload-simulator`; three docs quote the obsolete line count; `HANDOVER.md` §4 "Open Work" lists only completed items. |

Top five actions, in order: **A1** (raise or remove the 100-conversation cap), **A2** (timezone-correct reset labels), **U1** (re-tab the dashboard around user jobs), **U3** (fix simulator labels and preset carousel), **P1** (refresh `VDONE.md`/README drift and add a docs test for it).

---

## 1. Intended Use — What This Repo Actually Is Now

### 1.1 Observed purpose vs. stated purpose

The README's first line still says "token consumption, context caching efficiency, reasoning tokens, and quota velocity". The last ten milestones (M12–M21) were about something else:

- **Will I get throttled, and when?** (5h burst, weekly runway, Bayesian pacing, exhaustion ETA, alarm states)
- **What is my subscription worth and what did overage actually cost me?** (dual-tier accounting, credit bank, statement reconciliation)
- **What happens if I run this workload?** (What-If simulator, tier sensitivity)
- **Which project or branch is burning the budget?** (M11/M12)

That is a **quota governor + spend forecaster** for a single Antigravity subscriber. The three questions a user opens the page to answer are, in order: *Am I safe right now? How long until I'm not? What did this cost me?* The current layout answers the first question well (the hero deck), the second in three different places, and the third only after a tab switch.

**Recommendation R1 — rename the mission, keep the repo name.** Update the README tagline, the `<h1>`, and `HANDOVER.md` §1 to describe the tool as an *Antigravity quota governor and subscription value dashboard*. Effort: 1 h. Gate: `grep -c "quota governor" README.md dashboard/index.html docs/HANDOVER.md` returns ≥3.

### 1.2 Missing capabilities that the existing data already supports

These are the highest-value additions because the aggregator already computes the inputs. None require new upstream parsing.

| ID | Capability | Why it matters | Data already present | Effort |
|---|---|---|---|---|
| **M1** | **Alerting outside the browser** — macOS notification (`osascript`) or a `~/.antigravity_quota_status.json` file the watcher writes, so a shell prompt, menu-bar app, or another agent can read `state: caution` without opening the dashboard | The watcher already runs as a LaunchAgent. Today the only consumer of its output is a browser tab, which is the one thing a user in an IDE does not have open. | `compute_exhaustion_alarm_state`, `compute_quota_runway` | 0.5 d |
| **M2** | **Pre-flight budget check CLI** — `python3 scripts/agy_quota.py --can-i-run <archetype>` returning exit 0/1 and a one-line verdict | The simulator's value is highest *before* a swarm launches, and swarms are launched from a terminal or another agent, not from the dashboard. `simulator.py` is already pure Python. | `src/simulator.py`, `compute_simulation_presets` | 0.5 d |
| **M3** | **Per-conversation quota attribution timeline** — which conversations consumed the current 5h window (a stacked bar or a sorted list under the burst card) | The hero says "51.6M tokens in 5h window (327 turns)" but not *which sessions*. When the user is throttled they want to know what to stop. | `compute_rolling_window_telemetry` already partitions by model; add `convo_id` partition | 0.5 d |
| **M4** | **Weekly trend history** — retain one summary row per weekly cycle (tokens, cost, overage, peak BVI) in the vault and chart the last 8–12 weeks | Every number on the page is "this cycle". There is no way to answer "is my usage growing?" or "was last week's overage unusual?" The vault (`data/antigravity_vault.db`) is the natural store. | `get_weekly_cycle_bounds`, `vault.py` | 1 d |
| **M5** | **Cache-efficiency coaching** — surface the top 5 turns by uncached replay (≥50k uncached tokens) with the conversation title and a "model flip" flag | ADR-030 documents that cross-provider flips cause 70–80k uncached replay spikes. The data proves it, but the UI never tells the user *which* turns did it. | per-turn `prompt_tokens_uncached`, `model_id` | 0.5 d |
| **M6** | **Export / share** — a "Copy summary as Markdown" button and a `--markdown` flag on the exporter for pasting status into a standup or a handover doc | This repo's whole workflow is agent-to-agent handover via Markdown. The dashboard cannot produce any. | `summary` block of the payload | 0.25 d |
| ~~**M7**~~ | ~~Multi-user / multi-plan readiness~~ — **dropped** per §6 #3 (portfolio only) | — | — | — |

### 1.3 Things to consider retiring or repurposing

- **`hourly_credit_activity` reconciliation table (Credit Bank tab)** is a single table with 9 rows and the header says "Billing Hour (UTC)" while the cells show BST. This tab could be merged into a "Billing" section that also holds the monthly subscription card and the credit-bank card (currently in the Quotas tab), making one coherent money view. See U1.
- **`--embed` mode of `export_dashboard.py`** re-injects a 14 MB JSON into the tracked HTML. It exists for the pre-ADR-024 world. Keep the hook (AGENTS.md §3.5 requires it) but mark `--embed` deprecated in `--help` and README, and add a warning print. Effort 15 min.
- **`docs/COST_UTILITY_ANALYSIS_ULTRA.md` and `docs/CONVERSATION_TELEMETRY_ANALYSIS.md`** are analysis reports, not living docs. The former is already gitignored; the latter is tracked. Move both to `docs/reports/` (gitignored or not) so `docs/` holds only specs.

---

## 2. Code Quality — Findings

### 2.1 Correctness cracks (fix first)

**A1 — Lifetime totals silently exclude 44 of 144 conversation databases.** `export_dashboard.py` defaults `max_conversations=100`; the upstream directory holds 144 `.db` files today (ADR-020 counted 115, ADR-030 132). The "Lifetime Input Tokens", "Total Avoided Cost", and the Projects tab are therefore under-reported, and the number drifts every week as new conversations push old ones out. The header badge even says "100 Sessions" as if it were a fact about the data rather than a cap.
*Fix*: default to unlimited (`None`), keep `--max-conversations` as an opt-in speed knob, and put the true count and any cap into `summary.discovered_databases` / `summary.scanned_databases` so the UI can show "144 sessions". Check that `discover_all_conversations` ordering is by mtime descending so a cap, when set, drops the oldest.
*Gate*: `python3 scripts/export_dashboard.py --dry-run | grep Discovered` reports 144 DBs and 144 extracted (or documented reason for difference). Effort: 1 h plus a re-export timing check (the 100-cap may exist for speed; measure before removing).

**A2 — Reset time labels are hardcoded as "19:00 BST".** `aggregator.py:322-325` and `:377` format `"%d %b %Y, 19:00 BST"` as a literal. The underlying maths is 18:00 UTC. When BST ends on 25 Oct 2026, the display will read "19:00 BST" for an event that occurs at 18:00 GMT. It is also wrong for any non-UK user of the public repo. The HTML hardcodes the same string in five places (`badge-1w`, `quota-weekly-reset-text`, `gemini-weekly-sub` default, etc.).
*Fix*: emit `weekly_reset_utc` only (already present) and format in the browser with `Intl.DateTimeFormat` using the viewer's zone and `timeZoneName: 'short'`. Remove every literal "BST"/"19:00" from `index.html` and `aggregator.py` except in docs. **Decided (§6 #1)**: the reset is fixed at 18:00 UTC; keep the maths, fix only the label.
*Gate*: `grep -c "BST" dashboard/index.html src/aggregator.py` returns 0; a unit test with `reference_time` in December asserts the display string ends in "GMT"/"UTC".

**A3 — Two `VDONE.md` gates test the wrong thing.** V5 (and any gate that reads `injected-dashboard-data`) parses the JSON inside the HTML hook. Since ADR-024 that hook is literally `{}`, so the gate would fail (`'quotas'` KeyError) if anyone ran it. V1's EXPECT still says "writes deterministic JSON into `dashboard/index.html`". `VDONE.md` also opens with `Active Branch: feat/what-if-workload-simulator` while on `main`.
*Fix*: rewrite V1/V5 against `dashboard/data.json`; make the branch line a `git rev-parse --abbrev-ref HEAD` CHECK rather than a static claim; add a `tests/test_vdone_gates.py` that at minimum executes every gate whose CHECK is a pure `python3 -c` one-liner (see P1).

**A4 — Auto-refresh re-downloads and re-parses 14 MB every 30 seconds.** `checkAndReloadTelemetry()` appends `<script src="data.js?t=…">` on every tick and then calls `initDashboard()`, which rebuilds the entire DOM (including the 100-row conversation table and the Projects table) whether or not anything changed. On `file://` this is a 14 MB disk read + JSON parse + full re-render every 30 s for as long as the tab is open.
*Fix*: have the exporter also write a tiny `dashboard/meta.js` (`window.__TELEMETRY_META__ = {generated_at, payload_sha1}`) — deterministic because the hash is of content, not time — and have the ticker load only that; reload `data.js` only when the hash changes. Second step: trim per-turn fields that the UI never reads (`session_id`, `agent_id`, `avoided_cost_gbp` which is derivable from usd × fx) — `conversations` is 10.5 of the 14 MB.
*Gate*: with the watcher idle, network/disk reads over 5 minutes = 10 × meta.js only.

**A5 — Overage attribution is per-turn linear but the ledger is per-incident.** In `aggregate_global_telemetry` a ledger incident's credits are split across branches/conversations by *turn count* (`frac = cnt / total_k`). A single Opus turn costs 30× a Flash-Lite turn (ADR-030), so a conversation of 5 Opus turns and one of 50 Flash-Lite turns during the same incident get 9%/91% of the bill instead of roughly the reverse. This is a modelling choice, not a bug, but it is undocumented and the Projects tab presents the result as "Actual Overage" in bold amber.
*Fix*: weight by `estimated_cost_usd` (already on each turn) or by `calculate_credit_burn` credits; document the rule in `TELEMETRY_SPEC.md`; add a test with two conversations of different models. **Decided (§6 #2)**: weight by per-turn `estimated_cost_usd`. Effort 2 h.

### 2.2 Structure and maintainability

**C1 — `src/aggregator.py` is 2,100 lines with one 900-line function.** `aggregate_global_telemetry` (lines 1238–~2100) does project grouping, overage allocation, rolling windows, provider silos, alarm state, runway, temporal provenance, simulator presets, and payload assembly. Every milestone adds to it. Tests exist (1,428 lines) but they are integration-style against the whole payload.
*Recommendation*: split into modules along the ADR seams that already exist conceptually — `aggregator/projects.py` (ADR-022/023), `aggregator/quotas.py` (ADR-009/019/021), `aggregator/runway.py` (ADR-031/032/033), `aggregator/payload.py` (assembly). Keep `src/aggregator.py` as a thin re-export so nothing imports break, and `test_docs_integrity` continues to pass because filenames still appear in README. Do this as its own milestone (M22) with zero behaviour change, proven by byte-identical `data.json` before/after. Effort: 1 d.

**C2 — `dashboard/index.html` is 4,529 lines: 650 CSS, 1,100 HTML, 2,770 JS.** The README, `SYSTEM_DESIGN.md`, and ADR-024 all describe it as "~1,778 lines, 74 KB"; it is 211 KB. The JS has 29 `innerHTML` writes and 21 inline `onclick=` handlers; all rendering functions read the `globalDashboardData` global; `applyPlanToGlobalData` *mutates* that global in place so a "what-if" plan choice silently changes the numbers on every other tab until reload.
*Recommendation*: (a) split into `dashboard/index.html` + `dashboard/app.css` + `dashboard/app.js` — three plain files, no bundler, still works over `file://` (AGENTS.md §3.5 data-hook rule unaffected); (b) make `applyPlanToGlobalData` produce a *derived* view object rather than mutating the source; (c) replace inline handlers with `addEventListener` in `initDashboard` so CSP-strict hosts (the public showcase on GitHub Pages, if ever) work. Effort: 1 d. Update the three docs' line counts in the same commit.

**C3 — Personal calibration constants are scattered as defaults.** `18.99`, `23.99`, `24` (billing day), `129.00`, `20.0`, `0.79` (fx) appear as function-default arguments in `aggregator.py`, `temporal.py`, `simulator.py`, `quota_regression.py`, `ingest_statement.py`, and as literals in the HTML (`£18.99`, `2,500 Left`, `Renews 24 Sep`). `config/pricing.json` is supposed to be the single source (ADR-005) and mostly is, but the defaults mean a missing key degrades to *the owner's* plan rather than failing loudly.
*Recommendation*: make the defaults `None` and raise/`warnings.warn` when a key is absent; in HTML, render placeholders (`—`) until data arrives. Effort: 2 h.

**C4 — `test_docs_integrity.py` is substring-based.** "Every module in `src/` must appear in README" is checked with `filename in readme_text`. That passes as long as the string occurs anywhere, including a stale sentence. It caught nothing about the 1,778-line claim, the branch name in `VDONE.md`, or the fact that `HANDOVER.md` §4 "Open Work Register" contains only "Status: Completed" items. Add: (a) a test that `VDONE.md`'s branch line matches `git rev-parse`, or remove the line; (b) a test that every `python3 -c …` gate in `VDONE.md` exits 0; (c) a test that `HANDOVER.md` §4 has at least one item not marked Completed, or rename the section.

**C5 — CI runs the exporter against an empty machine.** `.github/workflows/ci.yml` executes `python scripts/export_dashboard.py` on GitHub runners with no `~/.gemini`. It "passes" by producing an all-zero payload. Better: commit a small anonymised fixture DB (the tests already build one in memory — `tests/test_export_dashboard.py`) and run the exporter with `--antigravity-dir tests/fixtures/antigravity` so CI proves a real extraction path and byte-determinism (`run twice, diff data.json`).

**C6 — `quota_client.py` makes a network call during export.** `export_telemetry` calls `fetch_live_quota_summary()` whenever the default dir is used. It is localhost Connect-RPC to the Language Server, so AGENTS.md §2.2 "zero external API" holds, but the exporter now has a side channel that can differ run-to-run (breaking ADR-004 byte-determinism when the desktop indicator moves). Document this exception in ADR-021 and add `--no-live-quota` for deterministic runs; CI should use it.

### 2.3 Things done well (keep doing them)

- **Read-only invariant is real**, not just documented: `mode=ro` URI plus exponential-backoff retry on `OperationalError` in `telemetry_reader.py`.
- **Atomic writes** (`.tmp` + `os.replace`) for every generated file.
- **Debounce controller** in the watcher is a clean, separately tested class.
- **Temporal resolver** (`temporal.py`) is a good abstraction: interval-based, back-compatible, and it makes historical re-costing possible.
- **Publish guardrails** (`publish_to_public.py`) grep for the owner's home path and refuse to ship the personal ledger. Extend the PII needle list to include the workspace names visible in the Projects tab (e.g. "My health dashboard") — the screenshot generator already anonymises paths, so the pattern exists.
- **Milestone slice docs** with verification proofs are genuinely useful for a fresh agent session.

### 2.4 Single-user vs. public-usable — decided: portfolio only

Everything (plan, currency, reset day, billing day, model-ID calibration) is tuned to one UK subscriber. **Decided (§6 #3)**: the public showcase is a portfolio piece. Do not build a first-run wizard or local-config override. Add one README sentence stating the calibration and pointing to `config/pricing.json`. C3 (fail loudly on missing config keys) still applies because it protects the owner's own setup.

---

## 3. Dashboard — Intended Use, Layout, and Presentation

### 3.1 What works

- The **hero deck** (Gemini | Runway | Claude/GPT) is the right idea: the three things that determine "can I work right now" are above the fold, and the centre panel's needle-vs-ceiling bar is a genuinely good visual for pacing.
- **Theme implementation** is solid: CSS variables, no flash on load, persisted. Light theme is the more legible of the two; dark theme's `--text-muted` on card backgrounds is borderline for 12–13 px text.
- **Projects tab** is the cleanest view in the product: one table, one job, good column choices, expandable branches.
- Currency toggle applies consistently everywhere I checked.
- No console errors; no external network requests; works over `file://`.

### 3.2 Problems, in priority order

**U1 — Weekly quota appears three times above the fold; the tabs are organised by milestone, not by user job.**
Screen inventory at 1440×900, Quotas tab active:
1. Hero left wing: "Weekly Allowance 59.7% available"
2. Hero centre: "Weekly consumed 40.3%" (same number, inverted)
3. Quotas tab card 2: "Weekly Allowance Cycle 363,790,403 tokens"
Plus the 5h burst twice (hero left wing and Quotas card 1). Meanwhile "what did this cost me" (credit bank, monthly subscription) is split between Quotas-tab cards 3–4 and the Credit Bank tab, and "which sessions did it" is a 100-row table at the bottom of the Quotas tab.

*Proposed re-tabbing around jobs-to-be-done*:

| Tab | Job | Contents (moved from) |
|---|---|---|
| **Now** (default) | Am I safe? How long? | Hero deck only, plus the 5h recovery timeline and the model allowance matrix. Remove the 4-card macro banner (its numbers are all in the hero). |
| **Sessions** | What is using it? | Conversations Explorer (from Quotas), turns inspector, plus M3 "which sessions are in the 5h window". Add search, column sort, and paging (25 rows). |
| **Projects** | Where is the budget going? | Unchanged. Add M4 weekly trend sparkline per project when available. |
| **Billing** | What did it cost? | Monthly subscription card, credit-bank card (from Quotas), lifetime KPIs (from Quotas), reconciliation table (from Credit Bank), avoided-cost KPI. |
| **Plan** | What if? | Simulator, and move the Plan Profile & Promotion Manager here from the header modal — it is configuration, not status. |

Effort: 1 d (it is mostly moving markup; `switchTab` already supports N tabs). Gate: each numeric fact appears exactly once on the default tab; verified by a checklist in the milestone doc with a screenshot.

**U2 — Internal engineering vocabulary leaks into the product surface.** Badges reading "ADR-019 Dual-Track", "Cost-Weighted Quota (ADR-021)", "ADR-022 Multi-Project", "ADR-035", "SQLite WAL Hook", "Dynamic Family Routing", "Zero Cross-Track Spillover", "Isolation Policy", "BVI", "Dual Benchmark Needle", "Sacred Dual Benchmark Bar" (in docs), "Day 3: +2.6% banked buffer". These are milestone provenance, not user information. A professional dashboard shows *what*, and puts *why/how* behind an `ⓘ` tooltip or a "Methodology" link.
*Fix*: remove every `ADR-` badge from `index.html`; replace "SQLite WAL Hook" with a data-source indicator ("Local telemetry • read-only"); rename BVI to "Burn rate" with tooltip "1.22× the pace that would exhaust the week exactly at reset"; replace "banked buffer" with "ahead of pace by 2.6%". Effort: 2 h. Gate: `grep -c "ADR-" dashboard/index.html` returns 0 outside HTML comments.

**U3 — Simulator tab has visible rendering defects.**
- Slider labels render raw LaTeX: "Turn Count ($N$)", "Average Prompt Context ($C_{prompt}$)", "Session Pacing ($\Delta t$)" (`index.html:1364-1409`). There is no MathJax; these are literally shown with dollar signs and braces.
- The archetype preset carousel is clipped at the right edge ("Claude Op…" cut off at 1440 px) with no scroll affordance.
- The tier comparison table labels plans by Google One *storage* size ("Google AI Pro (2 TB / 5 TB / 10 TB)", "Ultra (20 TB) 5x", "Ultra (30 TB) 20x"). Storage is irrelevant to a token dashboard; the meaningful axis is the capacity multiplier.
- "Session Pacing" slider affects nothing visible in the trajectory chart (the x-axis is turns, not time).
*Fix*: plain-English labels; `overflow-x: auto` + fade hint or wrap the presets to two rows; relabel tiers as "Pro (1×) / Ultra (5×) / Ultra (20×)"; either make the trajectory x-axis time when pacing is set, or drop the slider. Effort: 3 h.

**U4 — Conversations Explorer is a 100-row dump.** No sort, no text search, no paging, no sticky header, IDs in 10 px grey, and it lives at the bottom of the default tab. The row-level "⚠ 0.0% Covered" badges for conversations with 4–9 turns during an incident window dominate the visual weight while contributing pennies.
*Fix*: move to a Sessions tab (U1); add client-side sort on click, a search box, 25-row paging; collapse "Actual Overage" and "Subscription Coverage" into one column ("£0.15 · 15 credits" or "✓ covered"); reserve amber for overage ≥ £1. Effort: 4 h.

**U5 — Contradictory or unexplained signals in the hero.**
- Centre panel: status "✓ On Track (1.22×)" but the Exhaustion tile says "~Wed 06:54", which is *before* the Thursday reset. A reader has to know that BVI > 1 means "faster than nominal" and that the tile is a projection under the *unsmoothed* rate. Show one of: "On track" or an exhaustion ETA before reset, not both, or label the tile "If current pace holds".
- Left wing: "5-HOUR ROLLING BURST 69.8% available" while the Quotas-tab card says "51,614,716 tokens, 327 turns" — same fact, one in percent of a *cost* capacity, one in tokens. Pick one unit per concept; put the other in a tooltip.
- "Credit Overages OFF" badge next to "Gemini Models" is ambiguous: is it a setting, or a state? (It is `use_ai_credits: false` in pricing.json.) Rename "Overage: disabled (hard stop at limit)".
- "● Live Desktop Sync" was green while the page was served statically with no Language Server present. The badge should derive from `quotas.providers.*.live_synced` (or a timestamp age), not default to green.

**U6 — Mobile layout is functional but not designed.** One media query at 960 px. At 375 px the header becomes a 7-badge stack taller than the viewport, the `<h1>` wraps to three lines at 32 px, the hero cards stack (good), and the tab bar stacks into four full-width rows. Nobody will use this on a phone often, but a quick glance at "am I throttled?" on a phone is exactly the mobile use case.
*Fix*: at < 640 px collapse header badges into a single status line + overflow menu; `clamp()` the h1; make the tab bar a horizontally scrolling segmented control. Effort: 3 h.

**U7 — Accessibility baseline is absent.** One `aria-` attribute in 4,529 lines. Tabs are `<button onclick>` without `role="tablist"/"tab"/"tabpanel"` or `aria-selected`; progress bars are `<div>` with `width:%` and no `role="progressbar"`/`aria-valuenow`; the recovery timeline SVG has no `<title>`; colour is the only signal for safe/caution/exhausted in several places. Effort: 3 h for the tab/progress/SVG basics. Gate: axe-core (or Chrome Lighthouse) accessibility score ≥ 90.

**U8 — Visual polish.**
- Emoji as icons (♊ 🤖 📊 📁 💳 🧪 ⚙️ ☀️ 🌙 ⏱ 💎 🔄) render differently per OS and read as informal. Replace with a small inline SVG icon set (12 icons) or drop them; the labels are sufficient.
- Monospace `code-pill` is used both for genuine identifiers (model IDs, hashes) and for ordinary labels ("Flash & Pro Family", "Sonnet, Opus & GPT OSS", "Resets Thu 19:00"). Reserve monospace for identifiers.
- Numbers use up to four decimals in currency (`£279.2091`, `£4.7084`). Two decimals for money; four only in the turn inspector where per-turn costs are fractions of a penny.
- Section titles carry two or three badges each. Cap at one.
- The filesystem paths under project names are useful but contain the owner's home directory; the public screenshot generator already anonymises them. Add a "compact paths" toggle (show `~/Documents/…`).

### 3.3 Suggested default-tab wireframe (text)

```
┌ Header: title · status pill (Safe / Caution / Exhausted) · currency · theme · data freshness ┐
┌ Gemini ─────────────┐ ┌ Weekly runway ───────────────┐ ┌ Claude / GPT ───────────┐
│ Week  ▓▓▓▓▓░░ 60%   │ │ needle vs ceiling bar         │ │ Week  ▓▓▓▓▓▓▓ 100%      │
│ 5h    ▓▓▓▓▓▓░ 70%   │ │ pace 1.22× · ETA Thu 19:00 ✓ │ │ 5h    ▓▓▓▓▓▓▓ 100%      │
│ next recovery +2m   │ │ (if pace holds: Wed 06:54)   │ │ hard stop, no overage   │
└─────────────────────┘ └──────────────────────────────┘ └─────────────────────────┘
┌ 5h recovery timeline (SVG) ─────────────────┐ ┌ In this 5h window: top sessions ┐
└─────────────────────────────────────────────┘ └─────────────────────────────────┘
┌ Model allowance matrix (5h | week toggle) ───────────────────────────────────────┐
```

---

## 4. Documentation & Process Findings

**P1 — Drift that the integrity test does not catch.** Fix in one `docs:` commit: README architecture diagram and `SYSTEM_DESIGN.md` line 34 ("~1,778 lines, 74 KB" → actual); ADR-024 summary (same); `VDONE.md` branch line; V1/V5 gate text; README "111 tests, ~1.5s" (fine today, but make it a CHECK not a claim). Then extend `test_docs_integrity.py` per C4 so it cannot recur.

**P2 — `HANDOVER.md` §4 "Open Work Register" has no open work.** All seven entries are "Status: Completed". Either move them to §3 and list *actual* open items (this audit's A1–A5, U1–U8), or rename §4 "Recently Closed". A fresh agent reading §4 today would conclude there is nothing to do.

**P3 — `VDONE.md` is 43 KB and growing monotonically.** 119 headings. Gates from M01–M20 are historical proofs, not active gates. Keep only the current milestone's gates plus a fixed "always-on" set (V0 tests, V3 clean tree, byte-determinism, docs integrity) in `VDONE.md`; archive the rest into each milestone's slice doc (they already duplicate there). Target < 8 KB.

**P4 — AGENTS.md §4 (subagent tiers `flash_lite`/`flash`/`pro`) and §5 (`@Conversation` handoff) are Antigravity-IDE-specific.** Since CLAUDE.md declares the agreement "agent-neutral", mark those two sections "Antigravity-specific; other agents: skip" so a non-Antigravity agent does not try to comply with model names it cannot select.

**P5 — Milestone numbering skips M04–M05.** Harmless, but a fresh agent will look for them. Add a one-line note in `HANDOVER.md` §3.

---

## 5. Prioritised Backlog for the Maintaining Agent

Work top-down. Each row is one branch and one milestone slice unless marked "docs only". Do **not** start U1 (re-tabbing) and C2 (file split) in parallel; they touch the same file.

| # | Item | Type | Priority | Effort | Branch | Blocking decision |
|---|---|---|---|---|---|---|
| 1 | A1 — remove 100-conversation cap; surface true counts | fix | P0 | 1 h | `fix/conversation-cap` | decided (§6 #5): remove; report timing if > 30 s |
| 2 | A2 — timezone-aware reset labels, maths unchanged | fix | P0 | 3 h | `fix/reset-timezone` | decided (§6 #1): fixed 18:00 UTC |
| 3 | P1 + A3 — docs/VDONE drift + gate rewrite + integrity tests (C4) | docs+test | P0 | 3 h | `docs/drift-2026-09` | — |
| 4 | A4 — meta.js change-detection for auto-refresh; trim turn fields | perf | P1 | 4 h | `perf/refresh-meta` | — |
| 5 | U3 — simulator labels, carousel overflow, tier names | ui | P1 | 3 h | `fix/simulator-polish` | — |
| 6 | U2 — strip ADR/engineering vocabulary from UI | ui | P1 | 2 h | `ui/plain-language` | — |
| 7 | U1 + U4 — re-tab around jobs; Sessions tab with sort/search/paging | ui | P1 | 1.5 d | `feat/jobs-based-tabs` | decided (§6 #4): approved in principle; agent drafts tab plan in milestone doc, owner signs off in chat first |
| 8 | C2 — split index.html into html/css/js; derived plan view; no inline handlers | refactor | P1 | 1 d | `refactor/dashboard-split` | after #7 |
| 9 | M1 — quota status file written by the watcher (notifications deferred) | feat | P2 | 0.5 d | `feat/quota-status-file` | decided (§6 #6): status file first |
| 10 | M2 — `--can-i-run` pre-flight CLI | feat | P2 | 0.5 d | `feat/preflight-cli` | — |
| 11 | A5 — cost-weighted overage attribution | fix | P2 | 2 h | `fix/overage-weighting` | decided (§6 #2): per-turn cost |
| 12 | C1 — split aggregator.py (byte-identical payload proof) | refactor | P2 | 1 d | `refactor/aggregator-modules` | — |
| 13 | U5, U6, U7, U8 — hero clarity, mobile, a11y, polish | ui | P2 | 1.5 d | `ui/polish-pass` | — |
| 14 | M3, M5 — window attribution, cache coaching | feat | P2 | 1 d | `feat/session-attribution` | — |
| 15 | C5, C6 — CI fixture DB; `--no-live-quota` | ci | P2 | 3 h | `ci/fixture-export` | — |
| 16 | M4 — weekly history in vault + trend chart | feat | P3 | 1 d | `feat/weekly-history` | — |
| 17 | P3 — slim VDONE.md | docs | P3 | 1 h | docs only | — |
| ~~18~~ | ~~M7 / §2.4 — public-usable configuration~~ | — | dropped | — | — | decided (§6 #3): portfolio only; add one README calibration sentence instead (fold into row 3) |

### 5.1 Instructions for the maintaining agent

1. Read this file and `AGENTS.md` before touching anything. State `Active Branch:` in every update, per §1.1 of the agreement.
2. Before starting any row, write its gates into `VDONE.md` (CHECK + EXPECT). Suggested gates are given inline above; convert them to executable commands.
3. Every UI row must include a before/after screenshot pair in its milestone slice, captured with `scripts/capture_showcase_screenshots.py` (extend it to take the new tab names as an argument).
4. Rows 7 and 8 modify `dashboard/index.html` heavily. Run `python3 scripts/export_dashboard.py` and open the page after each, and confirm `<script id="injected-dashboard-data">` still exists (AGENTS.md §3.5).
5. Rows 1, 4, 11, 12 change the payload. Prove determinism: run the exporter twice with `--no-live-quota` (after row 15) and `diff dashboard/data.json` must be empty. Prove no behavioural regression for row 12 by diffing `data.json` before and after the refactor with a fixed `reference_time`.
6. All owner decisions are recorded in §6. Implement against them; do not re-ask. The one remaining sign-off is the tab plan for row 7 (§6 #4): draft it in the milestone doc and confirm in chat before moving markup.
7. Update `HANDOVER.md` §4 to list the rows of this backlog that remain open, and remove them as they close. This file itself is a point-in-time audit; do not edit it, supersede it with a new dated audit.

---

## 6. Owner Decisions (recorded 12 Sep 2026)

All six open questions were answered by the owner in the audit session. These are settled; the maintaining agent should implement against them without re-asking. Log each as an ADR when its backlog row lands.

| # | Question | Decision | Consequence for the backlog |
|---|---|---|---|
| 1 | Weekly reset: fixed 18:00 UTC or 19:00 UK local? | **Fixed 18:00 UTC.** | A2: keep the maths, make only the label timezone-aware (`Intl.DateTimeFormat`, viewer zone, short zone name). Remove every literal "BST"/"19:00". |
| 2 | Overage incident attribution: turn count or cost? | **By per-turn rate-card cost** (`estimated_cost_usd`). | A5: weight `frac` by cost, not `cnt`. Document in `TELEMETRY_SPEC.md`; add a two-model test. |
| 3 | Public repo: usable by others or portfolio? | **Portfolio / showcase only.** | Row 18 (M7, local config wizard) is **dropped**. Add one README sentence stating the tool is calibrated to a single UK Pro subscription and that `config/pricing.json` is the place to edit. C3 (fail loudly on missing keys) still applies. |
| 4 | Five-tab layout (Now / Sessions / Projects / Billing / Plan)? | **Approved in principle, pending the maintaining agent's own revision.** | Row 7: before implementing, the agent writes a short tab plan (one paragraph per tab, what moves where) into the M22 milestone doc and gets owner sign-off in chat. Deviations from §3.2 are allowed if justified there. |
| 5 | Remove the 100-conversation cap? | **Remove it.** | A1: default `max_conversations=None`; keep `--max-conversations` as an opt-in speed knob; header shows the true scanned count. If a full export exceeds ~30 s, report the timing to the owner before merging. |
| 6 | Alerts outside the browser? | **Status file first.** | Row 9 (M1): watcher writes `~/.antigravity_quota_status.json` `{state, gemini_5h_pct, gemini_weekly_pct, claude_weekly_pct, exhaustion_eta_utc, generated_at}` atomically on every export. macOS notifications are deferred to a later row, not dropped. |

---

## 7. Community Direction (recorded 12 Sep 2026)

**Context.** The owner is not a professional developer and wants the project to gain traction so that someone in the coding community can take it to the next layer. The public showcase repo had 0 stars, 0 forks, and 0 watchers one day after creation. The dashboard is calibrated to one subscription (§6 #3), so the dashboard itself is unlikely to be the thing that travels. Two assets in this repo are rare and portable: the reverse-engineered telemetry knowledge and the decoder/reader code. The recommendation is to make those two things the public face of the project and let the dashboard be the demo.

**Honest framing of the investment so far** (from `dashboard/data.json`, 12 Sep): this project consumed 6,396 of 16,166 lifetime turns (40%) and caused 1,502 of 3,640 overage credits (41%, £14.40 of £34.93). Milestones M18–M21 added refinement and simulation features that no external user has asked for. Advisory, not a rule: when proposing a new dashboard milestone beyond the §5 backlog, the agent should say in chat what user need it serves so the owner can weigh it.

### 7.1 Suggested item 1 — Publish the findings as a standalone document (recommended, ~2 h)

Create `docs/FINDINGS.md` (and mirror it as the top of the public README) containing only *what was learned*, with no process or milestone vocabulary:

1. **Where Antigravity stores telemetry**: `~/.gemini/antigravity/conversations/*.db`, table `steps`, column `metadata` (protobuf wire format), WAL files, the `agyhub_summaries_proto.pb` workspace map, and `trajectory_metadata_blob` for workspace path and Git branch. Cite `docs/TELEMETRY_SPEC.md` for the field map (9.2 uncached prompt, 9.5 cached, 9.3 output, 9.9 thinking, 9.10 answer).
2. **The model-ID census**: the table of numeric IDs to model names and reasoning levels (`1318` Flash High, `1319` Flash Medium, `1016` Pro High, `1036` Pro Low, `1050` Flash Lite, `1035` Sonnet, `1026` Opus, `342` GPT OSS, and the subagent routing IDs), with the date observed, since Google can change them.
3. **The quota model as observed**: 5-hour rolling burst plus a weekly window resetting Thursday 18:00 UTC; consumption is cost-weighted, not token-weighted; Gemini exhaustion spills into prepaid credits while Claude/GPT hard-blocks with no spillover; weekly Gemini capacity calibrated at ~$129 and 5h at ~$20 from a real exhaustion event; the 5h window is superseded when the weekly hits zero.
4. **Cache behaviour**: steady-state cache hit ~93–95%; cross-provider model flips invalidate the cache and cause 70–80k-token uncached replays; Opus runs hit limits within 30–95 turns.
5. **Credit burn rates** per model as reconciled against Google One statements (e.g. ~2.5 credits per Flash High turn).
6. **What is uncertain**: everything above is from one account, one region, one plan tier, observed Aug–Sep 2026. State this plainly.

Each finding should carry the observation date and the ADR it came from, so a reader can judge staleness. Post the link where Antigravity users are (the Antigravity Discord or subreddit, and a Hacker News "Show HN" once item 2 exists). This is the artefact most likely to earn a star or a collaborator, because it answers questions people are already asking and cannot answer themselves.

### 7.2 Suggested item 2 — Extract the decoder and reader into a small importable package (recommended, ~1 d)

Split the reusable core out of the dashboard so a developer can `pip install` it or vendor one directory:

- **Package name**: `antigravity_telemetry` (directory `antigravity_telemetry/` at repo root, or a sibling repo if the owner prefers the dashboard repo to stay a showcase).
- **Contents**: `proto_parser.py` (wire decoder), `telemetry_reader.py` (read-only SQLite + WAL-safe retry), the model-ID table as a JSON data file, and a single public function `read_all_turns(antigravity_dir) -> list[Turn]` returning plain dicts with the fields in `TELEMETRY_SPEC.md`. Nothing about pricing, quotas, currency, or plans.
- **Constraints to keep**: zero third-party dependencies; `?mode=ro` invariant (AGENTS.md §2.1) enforced in code; the existing tests for the parser and reader move with the code unchanged.
- **Packaging**: a minimal `pyproject.toml`, MIT licence (already present), a README of under one screen showing one code example and one CLI example (`python -m antigravity_telemetry dump --json`).
- **Dashboard relationship**: `src/aggregator.py` and the exporter import from the package; behaviour unchanged, proven by byte-identical `dashboard/data.json` before and after.
- **Do not** publish to PyPI until at least one outside person has used it from GitHub; a package with no users is maintenance without benefit.

Gate: `python -c "import antigravity_telemetry as t; print(len(t.read_all_turns()))"` prints the same turn count as the exporter's dry run; `test_docs_integrity` updated to cover the new directory.

### 7.3 Item 3 — Freeze the dashboard after the P0 fixes: **TBD**

Not decided. The owner will revisit after items 1 and 2 have had time to attract feedback. Until then, the maintaining agent takes note of this suggestion and **continues working through the backlog in §5 as normal** unless the owner says to stop. No freeze is in effect.
