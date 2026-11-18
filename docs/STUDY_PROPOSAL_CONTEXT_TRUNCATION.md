# Study Proposal — What Actually Triggers Antigravity Context Truncation

> [!NOTE]
> **Study Completed & Superseded**: This proposal was executed on 21 September 2026. The full empirical findings, compaction mechanics (Protobuf Field 30 / Step Type 23), and state preservation analysis are published in [STUDY_SUMMARY_PRESERVATION_VS_CONTEXT.md](STUDY_SUMMARY_PRESERVATION_VS_CONTEXT.md). This document is preserved for historical methodology reference.

**Status**: Completed and superseded on 21 Sep 2026 by [STUDY_SUMMARY_PRESERVATION_VS_CONTEXT.md](STUDY_SUMMARY_PRESERVATION_VS_CONTEXT.md) (originally parked on 20 Sep 2026).
**Why it exists**: Milestone 54 set the Gemini truncation threshold to the stated 1M context window. The vault shows the IDE truncating Gemini sessions far below that, and not at any fixed depth. Until this study is done the dashboard's truncation alarm is knowingly dormant for Gemini (owner decision, 20 Sep 2026).
**Data safety**: every query below opens the vault or the upstream databases with `?mode=ro` (AGENTS.md §2.1). Nothing here writes.

---

## 1. What the data already says (19–20 Sep 2026, `data/antigravity_vault.db`)

Antigravity injects a `<CONTEXT_SUMMARY>` step when it compresses history. That marker is the ground truth for "this session was truncated". It appears in seven conversations:

| Session | Dominant model | Peak depth before first marker | Markers |
|---|---|---|---|
| 53cc6f51 | Gemini 3.8 Flash (High) | 269,704 | 6 |
| 525fa800 | Gemini 3.8 Flash (High) | 264,334 | 1 |
| abe62c2e | Gemini 3.8 Flash (High) | 246,134 | 1 |
| a7a661cc | Gemini 3.8 Flash (High) | 244,608 | 4 |
| dd893c19 | Gemini 3.1 Pro (High) | 129,541 | 1 |
| 9d378547 | Gemini 3.1 Pro (High) | 81,729 | 10 |
| 40d6b8b8 | Gemini 3.8 Flash (Medium) | 70,860 | 1 |

Three facts that any explanation has to fit:

1. **All seven are Gemini.** No Claude or GPT session in the vault has ever exceeded 166k prompt depth, so their behaviour is unobserved, not proven.
2. **Depth alone does not predict it.** Forty-five Gemini sessions went past 250k (highest 290,407) with no marker at all. Three truncations happened below 130k.
3. **Four of the seven cluster at 244k–270k**, which matches the postmortem's "~200k–250k" observation; the other three do not.

Reproduce the table:

```bash
sqlite3 -readonly "file:data/antigravity_vault.db?mode=ro" "
WITH marks AS (SELECT convo_id, MIN(step_idx) AS first_mark, COUNT(*) AS n
               FROM steps_archive WHERE payload_text LIKE '%CONTEXT_SUMMARY%' GROUP BY convo_id)
SELECT substr(m.convo_id,1,8), m.n,
  (SELECT MAX(COALESCE(prompt_tokens_uncached,0)+COALESCE(cached_tokens,0))
     FROM steps_archive s WHERE s.convo_id=m.convo_id AND s.step_idx < m.first_mark)
FROM marks m ORDER BY 3 DESC;"
```

## 2. Hypotheses worth testing

Ranked by how cheaply the vault can answer them.

| # | Hypothesis | What would confirm it | Data needed |
|---|---|---|---|
| H1 | Truncation is triggered by a **single large step** (one tool output or file view) pushing the next prompt over a limit, not by gradual growth | The step immediately before each marker has an unusually large uncached delta versus the session's median | `prompt_tokens_uncached` per step, already in vault |
| H2 | Truncation depends on **turn count or step count**, not tokens | Marker sessions share a step-count range that non-marker sessions above 250k do not | `step_idx`, already in vault |
| H3 | Truncation follows a **model switch** mid-session (cache invalidation forces a full replay that trips the limit) | The marker appears within a few steps of a `model_id` change | `model_id` per step, already in vault |
| H4 | The limit is **per model family and version**, set by the IDE, and changed over time (Antigravity updates) | Marker depth correlates with session date, not with model | `timestamp`, already in vault |
| H5 | Truncation is tied to **subagent fan-out** (parent context absorbs subagent results) | Marker sessions have `invoke_subagent` calls shortly before the marker | `tool_calls_json`, already in vault |
| H6 | Truncation is **time-based** (session wall-clock or idle gap) | Marker follows a long gap between steps | `timestamp` deltas |

Everything needed for H1–H6 is already stored. No new upstream parsing is required.

## 3. Method (one afternoon)

1. Build a per-step table for the seven marker sessions and for a control group of the fifteen deepest non-marker sessions: `step_idx, timestamp, model_id, depth, uncached_delta, has_tool_call, is_subagent_call, is_marker`.
2. For each marker, look at the twenty steps before it. Compute: max uncached delta, any model change, any subagent call, wall-clock gap, step count so far.
3. Compare against the same statistics at the deepest point of each control session.
4. Whichever feature separates the two groups cleanly is the trigger. If none does, the trigger is not in the telemetry and the honest dashboard answer is "truncation observed" (marker) rather than "truncation predicted" (depth).

## 4. What to change in the dashboard afterwards

- Replace the depth-only severity with: **critical = marker observed**; **warning = the confirmed trigger condition from §3**; otherwise normal. Keep `context_truncation_tokens` in `models.json` as the model window for reference.
- Flip the unit test that currently asserts 244,000 tokens on Gemini is safe (session a7a661cc was truncated at 244,608).
- Log the finding as an ADR superseding ADR-068.

## 5. Cheap preparation that can be done any time (optional, ~1 h)

Have the exporter record the marker per conversation so the study starts from `data.json` instead of hand-written vault queries. Data only; no threshold, badge or alarm changes. Paste into any session that already touches `scripts/export_dashboard.py`:

```text
For each conversation, scan step text for "<CONTEXT_SUMMARY>" and write
has_truncated (bool), first_truncation_step and depth_at_truncation into the
conversation record in data.json. Data only: no change to any threshold,
severity, badge or alarm. Gate: the vault conversations whose payload_text
contains the marker (query with mode=ro) are exactly the ones with
has_truncated true.
```

## 6. Out of scope

Predicting truncation on Claude or GPT. There is no observation to fit. Revisit if a Claude session ever passes 200k.
