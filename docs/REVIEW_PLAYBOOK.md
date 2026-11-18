---
name: review-playbook
description: Codebase, UI/UX and ceremony audit procedure. Use when asked to audit, review, or verify a repository, a branch, a PR, or an implementer's milestone; when asked for a "FAST check" or a "DEEP audit"; or when the Auditor or Implementer agent needs its procedure. Detects repo parameters, measures instead of reading, executes the project's own gates, renders the UI, compares against the previous audit, and produces findings with executable gates and a backlog the Implementer can consume. Do NOT use to implement fixes.
---

# Review Playbook — Codebase, UI/UX and Ceremony Audit

**Version 2.1 (21 Sep 2026).** Single canonical file; supersedes the v1 draft and the v2 draft that briefly coexisted. Changes from v1: audit tiers with an explicit skip list, a linter parameter, an AST-based function scan, tap-target and async-state checks, a real contrast check (axe-core), a fixed Challenger schema, principle 11 (zero mutation), batched parameter confirmation, and a Playwright runner for reviewers that have no browser tool. Changes from v2: the contrast check now measures contrast, the function-diff snippet runs, paths are parameterised, and the evolution log records only defects that occurred.

A reusable, repository-agnostic procedure for any AI agent (or human) asked to audit a codebase, its UI/UX and its process ceremony, and to produce a remediation plan that a *different* agent will implement. Repository-specific values appear only in the §0.2 example table.

**Source of truth is this file in git; the global `review-playbook` skill is an installed copy.** After editing here, reinstall with `cp docs/REVIEW_PLAYBOOK.md ~/.gemini/config/skills/review-playbook/SKILL.md`. The reviewer detects the §0 parameters itself and confirms them with you. Give it the prompt in §8. Extend by adding checks to §3–§6 and logging them in §10; never remove §1. Command snippets are shell, Python, and browser JavaScript; translate §3.4, §4.2 and §6.3 for other stacks.

---

## 0. Parameters — detected by the agent, confirmed by the owner

The reviewer never asks the owner to fill in a form. It detects every value, posts one table with evidence and confidence, and then asks about `ask` rows one at a time, each with its best guess as the recommended answer. It does not start Phase A until the owner says "go".

### 0.1 Detection procedure

| Parameter | How to detect | Confidence rule |
|---|---|---|
| `AUDIT_TIER` | `FAST` if the request names a branch, PR or diff under ~5 files; `DEEP` for a milestone, a release, an architectural change or a scheduled audit | `sure` if the request says; else `likely: DEEP` and confirm |
| `GOVERNANCE_DOCS` | `ls AGENTS.md CLAUDE.md CONTRIBUTING.md VDONE.md GATES.md README.md docs/*.md 2>/dev/null`; keep files whose first 30 lines contain "must", "never", "gate", "decision" or "ADR" | `sure` if ≥2 found; else `ask` |
| `PREVIOUS_AUDIT` | `ls -t docs/AUDIT_*.md docs/*audit* docs/*review* 2>/dev/null \| head -1` | `sure` if found; `none` otherwise (no question) |
| `TEST_CMD` | In order: `.github/workflows/*.yml` `run:` lines with test/pytest/unittest/npm test; `Makefile` `test:`; `package.json` `scripts.test`; `pyproject.toml` `[tool.pytest]`; fallback: a `tests/` dir → `python3 -m unittest discover -s tests` | `sure` from CI; `likely` from manifest; `ask` if fallback |
| `LINTER_CMD` | `ruff`, `flake8`, `eslint`, `biome`, `clippy` in CI or manifests | `sure` if found; `none` otherwise |
| `GATE_FILE` | `grep -lE 'CHECK|EXPECT|acceptance' VDONE.md GATES.md docs/*.md 2>/dev/null` | `sure` if one file; `none` if zero |
| `UI_ENTRY` | `find . -maxdepth 3 -name 'index.html' -not -path '*/node_modules/*'`; `package.json` `scripts.dev`/`start`; `.claude/launch.json`; README lines containing `open` or `http://` | `sure` if exactly one; `ask` if several or none |
| `UI_SERVE_CMD` | Static HTML → `python3 -m http.server <port> -d <dir>`; a dev script → that; else README | `likely` |
| `UI_VIEWPORTS` | Default `1440x900` and `375x812`; override from `playwright.config.*` or README | `sure` |
| `UI_THEMES` | `grep -lE 'data-theme|prefers-color-scheme' <css/html>`; default `light,dark` if found, else `default` | `sure` |
| `SAFETY_RULES` | Headings in `GOVERNANCE_DOCS` containing "safety", "read-only", "never", "invariant"; `.gitignore` entries for databases or credentials | `sure` if a section exists; else `ask`: "Is there anything I must not touch or write while measuring?" |
| `DECISION_LOG` | `grep -lE 'ADR|Decision|Open Work|Backlog' docs/*.md HANDOVER.md CHANGELOG.md 2>/dev/null` | `sure` if one file; `none` if zero |
| `MILESTONE_DIR` | `ls -d docs/milestones docs/changes docs/adr 2>/dev/null` | `sure` if found; `none` otherwise |
| `DAEMON_LOG` | Log paths named in `GOVERNANCE_DOCS`, launch templates (`*.plist`, `*.service`), or `logging` config | `sure` if named; `none` otherwise |
| `CYCLE_CMD` | The command that produces the project's main artefact offline (an export, a build, a report), from README quickstart or CI | `likely`; `none` if no such thing |
| `OWNER_PROFILE` | `PREVIOUS_AUDIT` audience line; `CONTRIBUTING.md`; otherwise unknown | `ask` once: "Developer or non-developer owner?" |
| `OUTPUT` | `docs/AUDIT_<today>_<scope>.md`, or the naming pattern of `PREVIOUS_AUDIT` | `sure` |

### 0.2 Confirmation format (one message, before Phase A)

```
Parameters detected — say "go" to accept, or correct any row. Rows marked → will be asked one at a time.
AUDIT_TIER        DEEP                                                     (likely: milestone tag on HEAD) →
GOVERNANCE_DOCS   AGENTS.md CLAUDE.md VDONE.md README.md docs/HANDOVER.md  (sure)
PREVIOUS_AUDIT    docs/AUDIT_2026-09-19_UI_CODE_AND_CEREMONY.md            (sure)
TEST_CMD          python3 -m unittest discover -s tests                    (sure: .github/workflows/ci.yml:34)
LINTER_CMD        none                                                     (sure: nothing in CI or manifests)
GATE_FILE         VDONE.md                                                 (sure)
UI_ENTRY          dashboard/index.html via python3 -m http.server 8091 -d dashboard   (sure: playwright.config.js)
UI_VIEWPORTS      1440x900, 375x812   UI_THEMES light,dark                 (sure)
SAFETY_RULES      AGENTS.md §2: upstream *.db opened with ?mode=ro only    (sure)
DECISION_LOG      docs/HANDOVER.md    MILESTONE_DIR docs/milestones/        (sure)
DAEMON_LOG        ~/Library/Logs/Antigravity/telemetry_watcher.*.log       (sure: plist template)
CYCLE_CMD         python3 scripts/export_dashboard.py --dry-run --no-live-quota   (sure: README)
OWNER_PROFILE     non-developer, blunt findings                            (likely: previous audit) →
OUTPUT            docs/AUDIT_2026-09-28_<scope>.md                         (sure)
```

After "go", the table is copied verbatim into the audit's §1.

### 0.3 What each tier runs

| Phase | `FAST` (~20 min, a branch or PR) | `DEEP` (~2.5 h, a milestone or the whole repo) |
|---|---|---|
| A Survey | `git status`, `git diff --stat <base>`, tags, versions | all of §2 |
| B Code | tests touched by the diff; §B gates in `GATE_FILE`; §3.3 on changed files; §3.4 on changed files | all of §3 |
| C UI | only the flows the diff touches, both viewports, both themes | all of §4 on every tab |
| D Docs | §5 numbers rule on touched docs; version alignment | all of §5 |
| E Milestone loop | n/a | n/a (Phase E is its own mode, see §6) |
| Output | the three-part verdict of §6.7 in chat; no audit file | full document per §7 |

---

## 1. Principles (never remove)

1. **Measure, do not read.** Every claim in a document is a hypothesis. Line counts, test counts, "zero dependencies", "light theme default", "gates pass": run the command and record the number. The audit carries a facts table with the command beside each value.
2. **Execute the project's own proofs.** If the repo has acceptance gates, run every one that is side-effect-free and count the failures. A gate nobody runs is a claim, not a gate.
3. **Render the UI, do not infer it.** Load the real entry point at the real viewports, in every theme, on every tab, with storage cleared. Read the DOM with a script; screenshot for the human.
4. **Compare against the last audit.** Every previous recommendation gets one of: done, partly, not done, regressed, discarded (with the stated reason). The scorecard is what tells the owner whether the process works.
5. **Ceremony is code.** Rules, gates, handover, changelog rot like code and cost more when they rot. Measure size, growth, duplication and truthfulness with the same rigour as `src/`.
6. **One action per finding.** What, why it matters, fix, executable gate, effort, branch name, priority. A finding without a gate is an opinion.
7. **Do not implement.** The reviewer changes nothing. It writes the audit, commits only that file if asked, and stops.
8. **Blunt, plain, short.** The owner may not be a developer. One sentence on what is wrong, then the evidence.
9. **One reviewer, many runners, one challenger.** Never split the review by area across parallel reviewers; the findings that matter come from cross-referencing docs, code, UI and gates in one head. Delegate only *measurement* (a runner executes a phase's commands and returns the facts table) and *challenge* (after the draft, a read-only agent grades every finding and number as EVIDENCED, GUESSED or CONTRADICTED with the query it ran; GUESSED becomes an owner question, CONTRADICTED is dropped).
10. **Visual truth over DOM heuristics.** Valid ARIA on an element that is clipped, covered or unreadable is still a defect. When a DOM count and a screenshot disagree, the screenshot wins.
11. **Zero mutation during the audit.** The repository, its databases and caches are left byte-identical. Temporary files go only in a scratch directory outside the repo; servers started for rendering are stopped; automated tests, Playwright scripts, and verification runners must write output artifacts (screenshots, traces, temporary databases) exclusively to git-ignored scratch paths (e.g. `test-artifacts/`, `tmp/`), never to tracked documentation directories (`docs/milestones/screenshots/`); the closing message includes `git status --short` output as proof.

---

## 2. Phase A — Survey (15 min)

```bash
git rev-parse --abbrev-ref HEAD; git status --short; git log --oneline | head -30; git remote -v
git ls-files | wc -l
git ls-files -z | xargs -0 du -k 2>/dev/null | sort -rn | head -20
cat .gitignore; du -sh .git
wc -lc $GOVERNANCE_DOCS docs/*.md src/* scripts/* tests/* <ui files> 2>/dev/null | sort -k2 -rn | head -60
find . -maxdepth 4 \( -name '*.tmp' -o -name '*.bak' -o -name '*.orig' -o -name '*~' \) -not -path '*/node_modules/*' | head
ls -la data/ dist/ build/ 2>/dev/null
```

Record: branch, commit, cleanliness, tracked count, largest tracked files, largest on-disk files, temp or backup leftovers, remotes and how far each lags.

## 3. Phase B — Code (45 min)

### 3.1 Run the proofs

```bash
time $TEST_CMD 2>&1 | tail -5          # count, duration, noise printed during tests
$LINTER_CMD 2>&1 | tail -20            # if any
```

### 3.2 Execute the gates (if `GATE_FILE` exists)

Adapt the regex to the gate format. Skip anything that exports, restarts, deploys, pushes, commits or writes outside a temp dir. Report: total gates, runnable, failed, duplicated IDs, gates that name files that no longer exist, and tautological gates (`or True`, `exit 0`, no assertion).

```python
import re, subprocess, pathlib
txt = pathlib.Path("$GATE_FILE").read_text()
gates = re.findall(r"^### (V\d+)[^\n]*\n- \*\*CHECK\*\*: `(.*?)`\s*$", txt, flags=re.M)   # adapt
BAD = ("export_", "setup_", "build_", "git ", "npx", "playwright", "launchctl", "publish", "restart", "deploy", "rm ", "DROP ")
ran = failed = skipped = 0
for gid, cmd in gates:
    if not cmd.startswith("python3 -c") or any(b in cmd for b in BAD):
        skipped += 1; continue
    ran += 1
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        failed += 1; print("FAIL", gid, (p.stderr.strip().splitlines() or ["?"])[-1][:100])
print(f"total {len(gates)}, ran {ran}, failed {failed}, skipped (side-effecting) {skipped}")
```

### 3.3 Safety invariants

For each rule in `SAFETY_RULES`, grep for the violation, not the compliance. Examples from a read-only-database, zero-network, single-writer project:

```bash
grep -rnE 'sqlite3\.connect\(' src scripts | grep -v 'mode=ro'
grep -rnE 'urllib|requests\.|http\.client|socket' src scripts | grep -v '#'
grep -rnE 'flock|fcntl|\.lock' scripts src                          # expect a hit if a single-writer rule exists
```

### 3.4 Structure and hot spots

```bash
# Longest functions (Python, AST)
python3 - <<'EOF'
import ast, glob
rows = []
for p in glob.glob('src/**/*.py', recursive=True) + glob.glob('scripts/**/*.py', recursive=True):
    try: tree = ast.parse(open(p).read())
    except Exception: continue
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rows.append(((n.end_lineno or n.lineno) - n.lineno + 1, p, n.name))
for L, p, n in sorted(rows, reverse=True)[:12]: print(f"{L:5d}  {p}:{n}")
EOF
# Longest functions (JS, by gap between top-level declarations)
grep -nE '^(async )?function ' <js files> | awk -F: 'NR>1{print $1-prev, prevname} {prev=$1; prevname=$2}' | sort -rn | head
# Risky web patterns
grep -c 'innerHTML' <js files>; grep -c 'onclick=' <html> <js files>; grep -c 'style="' <html>; grep -c '!important' <css>
# Duplicate helpers, duplicate files
grep -ohE '^(async )?function [A-Za-z0-9_]+' <js files> | sort | uniq -d
diff -q <file A> <file B>
```

### 3.5 Runtime behaviour

```bash
tail -n 20 $DAEMON_LOG.stdout; cat $DAEMON_LOG.stderr          # crashes, races, reentrancy
time $CYCLE_CMD                                                 # real cost per cycle, offline
grep -rnE 'flock|fcntl|Lock\(' <writers>                        # who else writes the same artefact?
```

### 3.6 Data growth

Anything that accumulates: databases, payloads, caches, backups. Size now, size at the last audit, growth per day, retention rule or none.

## 4. Phase C — UI/UX (45 min)

Serve `UI_ENTRY`; clear `localStorage` and `sessionStorage` before the first load so defaults are real. Everything below runs per viewport, per theme, per tab.

### 4.0 Runner for reviewers without a browser tool

Write this to a scratch directory outside the repo (principle 11) and run it with `node` from the repo root, where Playwright is installed. It prints one JSON object per tab and saves screenshots beside itself.

```javascript
// audit_ui.mjs  — node audit_ui.mjs <baseURL> <tabSelectorCSV> [<viewportWxH>] [<theme>]
import { chromium } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const [base, tabs, vp = '1440x900', theme = 'light'] = process.argv.slice(2);
const [w, h] = vp.split('x').map(Number);
const browser = await chromium.launch(); const page = await browser.newPage({ viewport: { width: w, height: h } });
await page.goto(base); await page.evaluate(() => { localStorage.clear(); sessionStorage.clear(); }); await page.reload();
await page.evaluate(t => document.documentElement.setAttribute('data-theme', t), theme);
for (const sel of tabs.split(',')) {
  if (sel) await page.click(sel); await page.waitForTimeout(500);
  const dom = await page.evaluate(AUDIT_SCRIPT);                     // paste §4.2 body as a string constant
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  dom.axeViolations = axe.violations.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }));
  await page.screenshot({ path: `${vp}-${theme}-${(sel || 'home').replace(/\W/g, '')}.png`, fullPage: true });
  console.log(JSON.stringify({ tab: sel, vp, theme, ...dom }));
}
await browser.close();
```

### 4.1 Per tab: screenshot, console, network

Console errors (discount errors you caused, such as a server you stopped). Network: what loads, how large, how often; look for double fetches and polls that reload more than they need.

### 4.2 DOM audit script

```javascript
({
  theme: document.documentElement.dataset.theme || 'default',
  headerH: Math.round(document.querySelector('header')?.getBoundingClientRect().height || 0),
  overflowX: document.documentElement.scrollWidth - innerWidth,                       // > 0 is a defect
  badges: [...document.querySelectorAll('header .badge')].map(b => b.textContent.trim()),
  h2s: [...document.querySelectorAll('h2')].map(h => h.textContent.trim()),
  tabRoles: document.querySelectorAll('[role=tab],[role=tablist],[role=tabpanel]').length,
  progressRoles: document.querySelectorAll('[role=progressbar]').length,
  svgs: document.querySelectorAll('svg').length,
  svgsAccessible: [...document.querySelectorAll('svg')].filter(s => s.querySelector('title') || s.getAttribute('aria-label') || s.getAttribute('aria-hidden') === 'true').length,
  tables: [...document.querySelectorAll('table')].map(t => ({ rows: t.rows.length, caption: !!t.caption || !!t.getAttribute('aria-label') })),
  textUnder11px: [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 && e.textContent.trim() && parseFloat(getComputedStyle(e).fontSize) < 11).length,
  smallTapTargets: [...document.querySelectorAll('button, a, input, select, [role=button]')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (r.width < 44 || r.height < 44); }).length,
  clippedText: [...document.querySelectorAll('h1,h2,h3,button,.badge')].filter(e => e.scrollWidth > e.clientWidth + 1).length,
  internalTermsOnScreen: (document.body.innerText.match(/<JARGON_REGEX>|\bundefined\b|\bNaN\b|TODO|FIXME/g) || []).length
})
```

Contrast is **not** measured here; it comes from axe in §4.0 (`color-contrast` violations). A heuristic on opacity is not a contrast check.

### 4.3 Asynchronous and edge states

Loading (does layout jump?), empty (zero rows, zero series), error (payload missing or corrupt: informative card or blank page?), in-flight buttons (disabled with a pending state?). Force them by intercepting the data request in the runner or by serving an empty fixture.

### 4.4 Contradictions

Every number that appears twice must agree (header vs tab, card vs card, summary vs table sum). Every label naming a plan, date, tier or state is checked against the payload. Hardcoded strings are found with `grep -n '<literal>' <html> <js>`.

### 4.5 Interactions, not just load

Script the three most important flows (apply a setting, open an inspector, change a control) and read state afterwards: DOM, the data object, `localStorage`, then reload and read again. Load-only snapshots miss deleted behaviour.

### 4.6 Checklist

Header height at phone width; title clipping; tab roles and focus rings; colour-only status; unit and money formatting consistency; tables without paging or sticky headers; engineering vocabulary on the product surface; contradictory signals; defaults that do not match the user's real configuration; tap targets under 44 px; axe serious/critical count.

## 5. Phase D — Docs and ceremony (30 min)

```bash
wc -lc $GOVERNANCE_DOCS; for f in $GOVERNANCE_DOCS; do echo "$f: $(git log --oneline -- $f | wc -l) commits"; done
grep -nE '[0-9,]+ lines|[0-9]+ KB|[0-9]+ tests|[0-9]+ (ADRs|decisions|modules)' $GOVERNANCE_DOCS docs/*.md      # drifting numbers
grep '"version"' package.json 2>/dev/null; grep '^version' pyproject.toml Cargo.toml 2>/dev/null; git tag --sort=-v:refname | head -3; grep -n 'Release\|badge/' README.md
awk 'length > 300' $DECISION_LOG | wc -l                                                                          # unreadable rows
awk '/Open/,0' $DECISION_LOG | grep -ciE 'completed|done|closed'                                                  # closed work listed as open
diff <(grep -E '^### ' $GATE_FILE) <(grep -rhE '^### ' $MILESTONE_DIR/) | head                                     # duplication
# Rotting backlog: open rows older than 14 days, and open rows whose branch was never created
awk '/Open/,/Closed/' $DECISION_LOG | grep -E '^- ' | while read -r row; do b=$(echo "$row" | grep -oE '`[^`]+`' | head -1 | tr -d '`'); [ -n "$b" ] && ! git rev-parse -q --verify "$b" >/dev/null && ! git log --all --oneline | grep -q "$b" && echo "NO BRANCH YET: $row"; done
git log -1 --format=%cd --date=short -- $DECISION_LOG                                                              # last time Open changed
```

Judge each governance file on four questions: Is it true today? Is it read before work starts? Does it grow without bound? Is anything in it stated twice elsewhere? A file failing two gets a restructure proposal with a target size.

## 6. Phase E — Reviewing an implementer's milestone

Do not read the implementer's report first. Re-derive:

1. `git log`, tags, versions, clean tree, open-work list in `$DECISION_LOG` updated, and `git status --short` empty.
2. `TEST_CMD` and the gate runner, yourself.
3. **Function-level diff for any refactor or file split.** Comments and whitespace stripped; list functions missing, changed, duplicated. A "pure move" that changes bodies is a cut.

```python
# JS: python3 fn_diff.py <old file from `git show <tag>:<path>`> <new js dir>
import re, glob, sys
def norm(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S); s = re.sub(r'(?m)(^|[^:"\'])//.*$', r'\1', s)
    return re.sub(r'\s+', '', s)
def funcs(src):
    idx = [(m.start(), m.group(1)) for m in re.finditer(r'^(?:async\s+)?function\s+([A-Za-z0-9_]+)', src, re.M)]
    return {n: norm(src[s:(idx[i+1][0] if i+1 < len(idx) else len(src))]) for i, (s, n) in enumerate(idx)}
old = funcs(open(sys.argv[1]).read()); new = {}
for p in glob.glob(sys.argv[2] + '/*.js'): new.update(funcs(open(p).read()))
for k, v in old.items():
    if k not in new: print('MISSING', k)
    elif new[k] != v: print('CHANGED', k, len(v), '->', len(new[k]))
print('identical', sum(1 for k in old if k in new and new[k] == old[k]), 'of', len(old))
```

```python
# Python: python3 fn_diff_py.py <old file> <new file or dir>
import ast, glob, os, sys
def funcs(path):
    out = {}
    for p in ([path] if os.path.isfile(path) else glob.glob(path + '/**/*.py', recursive=True)):
        tree = ast.parse(open(p).read())
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)): out[n.name] = ast.unparse(n)
    return out
old, new = funcs(sys.argv[1]), funcs(sys.argv[2])
for k in old:
    if k not in new: print('MISSING', k)
    elif new[k] != old[k]: print('CHANGED', k)
print('identical', sum(1 for k in old if k in new and new[k] == old[k]), 'of', len(old))
```

4. **Byte-identical artefact proof** for refactors: produce the project's main artefact with the pre-refactor code and the post-refactor code *in the same environment* (same machine, same untracked files) and `cmp`. A fresh worktree may differ for environmental reasons; that difference is itself a finding (a non-hermetic build).
5. For a UI change: render and exercise the changed interaction by hand at both viewports.
6. For a data or threshold change: query the source of truth (read-only) and check the new numbers against observed events, not against documentation or vendor specs.
7. Verdict, three parts: what is fine (one paragraph); what drifted (table with evidence); a fix-up prompt for the implementer with disjoint-scope subagents and an independent verifier.

## 7. Output — the audit document

Fixed sections, in order. Under ~450 lines; findings not worth a gate are not worth writing.

```
0. Executive summary: 5-row verdict table (area, verdict, headline) + top five actions + a blunt paragraph for the owner
1. Measured facts: the §0.2 parameter table, then value + how measured
2. Scorecard against the previous audit
3. Code and correctness findings   (C1…)   each: what / why / fix / gate / effort / branch / priority
4. UI and UX findings              (U1…)   same shape, with the §4.2 numbers and axe counts
5. Ceremony and documentation      (D1…)   same shape + target size per file
6. Prioritised backlog: # / item / type / priority / effort / branch / blocking decision + instructions for the maintaining agent
7. Owner decisions: question / recommendation / consequence → after the owner answers, rewritten as "taken" with consequences applied to §3–§6
8. Appendix: scripts used; the Challenger's table verbatim
```

Rules: no numbers in prose that are not in the facts table; every finding names a branch; decisions are asked one at a time in chat and then recorded; the file is never edited after the decisions are in, only superseded.

**An audit is not finished until its rows are in the open-work list.** After the decisions are recorded, the reviewer appends every §6 row to `$DECISION_LOG` "Open" as `- **Row N (ids)**: title (`branch`) [priority] — from AUDIT_<date>`. That list, not the audit file, is what the implementer reads. Gate: `grep -c 'AUDIT_<date>' $DECISION_LOG` equals the number of §6 rows. When the implementer's Closing Report says "Open now: none", the reviewer runs one `FAST` audit of `main` in chat; nothing found closes the cycle, anything found becomes a new row.

## 8. Reviewer prompt (paste to the auditing agent)

```text
You are auditing this repository as a UI expert and code engineer. You will
not implement anything. Read docs/REVIEW_PLAYBOOK.md and follow it phase by
phase.

Start with §0: detect every parameter using §0.1, post the §0.2 table in one
message with evidence and confidence, then ask me one question at a time only
for the rows marked →, each with your best guess as the recommended answer.
Do not start Phase A until I say "go". Run the tier from AUDIT_TIER per §0.3.
If the repo has no UI, no gate file or no previous audit, say so in the table
and skip those phases; do not ask about them.

Non-negotiable: measure everything you report (command beside every fact);
execute every side-effect-free gate in <GATE_FILE> and report the failure
count; render <UI_ENTRY> at <UI_VIEWPORTS> in every theme and tab with storage
cleared, using the §4.0 runner if you have no browser tool, and report axe
serious/critical counts; exercise the three most important interactions by
script; respect <SAFETY_RULES> while measuring; leave the repository
byte-identical and end with `git status --short` as proof. If a previous
audit exists, produce the §2 scorecard before writing new findings.

Delegation (§1.9): you keep all judgement. Up to three read-only measurement
runners, one per phase (B, C, D), each returning only a facts table; they
write no findings. After drafting, one read-only Challenger that receives the
draft and reports, for every finding and every recommended number:
| Finding | Claim | Verification query | EVIDENCED / GUESSED / CONTRADICTED | Action |
Rewrite GUESSED items as owner questions in §7, drop CONTRADICTED ones, and
append the table verbatim to §8. Never split the review across parallel
reviewers.

Output: <OUTPUT> in the §7 shape. Findings need a gate, an effort, a branch
name and a priority. End with the owner-decision table, then ask the decisions
one at a time in chat and record the answers in §7. Commit only that file,
only if asked. Be blunt and plain; the owner may not be a developer.
```

## 9. Implementer prompt (paste to the maintaining agent, one session per row)

```text
Active Branch: main (verify and state it).
Read the working agreement (<GOVERNANCE_DOCS>), the latest audit's §6 and §7,
then the open-work list in <DECISION_LOG>.

Take the lowest-numbered open row(s) the audit table allows in one session
(respect "after N" dependencies; never combine two refactor rows). State
which and why. Rename this conversation "<Mnn> · <rows> · <title>" before any
file edit.

Delegation: split the row into subagents with disjoint file ownership whenever
it touches more than one of: backend, UI scripts, styles/markup, tests, docs.
One agent per set, pre-flight disclosure before spawning. Implementers never
see a line budget or a deadline; if a file grows past the budget they split
it, they do not shorten code. Stage only files your agents own; leave
untracked files you did not create alone. A read-only Verifier runs last,
re-derives the gates by its own method, runs the suite and e2e, and for UI
rows exercises the changed interaction by hand at both viewports; its
PASS/FAIL report is posted verbatim. Nothing merges on FAIL. The parent
integrates and commits; it does not edit code when subagents are in play.

Write the row's gates into <GATE_FILE> (executable CHECK + EXPECT, runnable by
the gate test) and post them before implementing. UI and refactor rows need an
interaction gate, never load-only snapshots. Owner decisions in the audit are
final; do not re-ask.

Done means: suite OK, gate test OK, e2e OK with before/after screenshots at
both viewports for UI rows, Verifier all PASS, ops check recorded, milestone
doc written with the Verifier report included, gate section emptied into it,
open-work row moved from Open to Closed, semantic version bumped, merged to
main, tagged, pushed to origin only. End with the five-line Closing Report
(Merged / Open now / Next slice will touch / Needs owner / Freeze), then stop.
```

## 10. Extending this playbook

Add a check when a defect slips past an audit, in the phase that should have caught it, with the exact command. Keep §1 as it is. Record only defects that actually occurred, with the milestone or commit that shows them.

| Date | Added | Motivated by |
|---|---|---|
| 2026-09-20 | §6.3 function-level diff for refactors | M53 split cut ~700 code lines from `plan.js` to meet an 800-line budget; the load-only DOM equality gate passed |
| 2026-09-20 | §4.5 interactions, not just load | same defect: the Plan Manager stopped recomputing caps and persisting, invisible at load |
| 2026-09-20 | §6.7 thresholds checked against observed events | M54 set Gemini truncation to the 1M model window; vault markers showed IDE truncation at 70k–270k |
| 2026-09-21 | §6.4 byte-identical proof in the same environment | M62 fixture export differed in a fresh worktree because the exporter read the owner's log and ledger from `$HOME` |
| 2026-09-21 | §4.0 runner, §4.2 contrast via axe | v2 draft's "contrast check" only tested opacity; an agent without a browser tool could not run Phase C |
| 2026-09-22 | §4.0 Headless pageerror gate for UI milestones | M64 deleted variable declarations in `now.js`; Python tests passed while browser load crashed |
| 2026-09-22 | §1.11 Screenshot artifact quarantine | Row 7 visual tests overwrote tracked PNGs in `docs/milestones/screenshots/`, dirtying working tree |
