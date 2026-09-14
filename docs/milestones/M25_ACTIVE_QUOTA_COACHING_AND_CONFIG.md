# Milestone 25: Active Quota Intelligence, Cache Coaching & Clean Config (M3 + M5 + M7)

## 1. Executive Summary

Milestone 25 fulfills the first wave of senior audit recommendations by implementing:
1. **Per-Session 5-Hour Burst Attribution (M3)**: Partitions all turns occurring in the rolling 5-hour window by `convo_id`, aggregating token volumes, turns, primary models, and avoided costs. In the dashboard, an interactive drawer renders beneath the 5h burst card on the `Now` tab with a 1-click drill-down link into `Sessions`.
2. **Cache-Efficiency Coaching & Cross-Provider Model-Flip Diagnostics (M5)**: Detects when developers flip between provider model families (e.g. Gemini $\leftrightarrow$ Claude/GPT) during deep coding sessions, completely evicting KV caches and incurring massive (70k–80k token) uncached prompt replays. Quantifies wasted tokens and costs, displaying an executive coaching banner and incident inspector on the `Sessions` tab.
3. **Plan Configuration Decoupling & CLI Calibrator (M7 / ADR-038)**: Purges scattered personal fallback constants (`18.99`, `19.99`, `24`), introduces `config/pricing.sample.json` for new users and public forks, and provides an atomic CLI calibration utility (`scripts/configure_plan.py`).

---

## 2. Architecture & Data Contracts (ADR-038)

### 5-Hour Active Sessions Payload (`quotas.rolling_5h.active_sessions_5h`)
```json
[
  {
    "convo_id": "2764cc5e-b510-475a-86bc-93778f6c71ec",
    "title": "Milestone 24 Subagent Swarm",
    "workspace_name": "Geminu token consumption dashboard.",
    "workspace_path": "/path/to/Gemini token consumption dashboard.",
    "git_branch": "main",
    "turn_count": 154,
    "total_processed_tokens": 19113883,
    "prompt_tokens_uncached": 1284500,
    "cached_tokens": 17829383,
    "total_input_tokens": 19113883,
    "total_output_tokens": 0,
    "cache_hit_ratio_pct": 93.28,
    "imputed_value_usd": 0.1542,
    "imputed_value_gbp": 0.1218,
    "primary_model_id": "1318",
    "primary_model_name": "Gemini 3.8 Flash (High)"
  }
]
```

### Cache-Efficiency Coaching Payload (`summary.cache_coaching`)
```json
{
  "model_flips_detected": 3,
  "wasted_uncached_tokens": 127983,
  "wasted_avoided_cost_usd": 0.4779,
  "wasted_avoided_cost_gbp": 0.3775,
  "coaching_tip": "Cross-provider model flips (Gemini ↔ Claude) evict KV caches, incurring up to 80k uncached token re-reads. Stick to one provider family within deep coding sessions.",
  "top_incidents": [
    {
      "convo_id": "14d542c3-0bb0-4385-ba1a-b052667cc59f",
      "title": "OCR Plan Analysis Pipeline",
      "workspace_name": "My health dashboard",
      "timestamp": "2026-09-09T21:15:41.625046+00:00",
      "step_idx": 806,
      "from_model": "Claude Opus (Thinking)",
      "to_model": "Gemini 3.8 Flash (High)",
      "from_track": "claude_gpt",
      "to_track": "gemini",
      "total_input_tokens": 87078,
      "uncached_tokens": 78925,
      "cached_tokens": 8153,
      "wasted_tokens": 70217,
      "wasted_cost_usd": 0.0474,
      "wasted_cost_gbp": 0.0374
    }
  ]
}
```

---

## 3. Verifiable Quality Gates & Proofs

| Gate | Check Command | Status | Proof |
|---|---|---|---|
| **V119** | `python3 -c "from scripts.export_dashboard import export_telemetry; p=export_telemetry(dry_run=True); b=p['quotas']['rolling_5h']; assert 'active_sessions_5h' in b; assert len(b['active_sessions_5h']) >= 1; print(f'Verified: {len(b[\"active_sessions_5h\"])} active sessions.')"` | **PASSED** | Discovered active sessions in 5h burst window with titles, tokens, and model metadata. |
| **V120** | `python3 -c "from scripts.export_dashboard import export_telemetry; p=export_telemetry(dry_run=True); c=p['summary']['cache_coaching']; assert c['model_flips_detected'] >= 1; print(f'Verified: {c[\"model_flips_detected\"]} flips, {c[\"wasted_uncached_tokens\"]:,} wasted tokens.')"` | **PASSED** | 3 cross-provider flips detected on live data, 127,983 wasted tokens quantified. |
| **V121** | `test -f config/pricing.sample.json && python3 -c "import json; d=json.load(open('config/pricing.sample.json')); assert 'subscription' in d and 'models' in d; print('Verified: pricing.sample.json valid.')"` | **PASSED** | Sample plan configuration parsed and validated cleanly. |
| **V122** | `python3 scripts/configure_plan.py --show` | **PASSED** | Formatted ASCII summary and `--json` export verified with exit code 0. |
| **V123** | `test -f dashboard/app.js && node -c dashboard/app.js && python3 -c "h=open('dashboard/index.html').read(); j=open('dashboard/app.js').read(); c=open('dashboard/styles.css').read(); assert 'burst-sessions-drawer' in h and 'renderActiveBurstSessions' in j; assert 'cache-coaching-section' in h and 'renderCacheCoaching' in j; print('Verified: Frontend rendering functions for M3 & M5 present.')"` | **PASSED** | JavaScript syntax checked clean with `node -c`, all DOM anchors and renderers verified. |
| **V124** | `python3 -m unittest discover -s tests && python3 -m unittest tests/test_docs_integrity.py` | **PASSED** | 100% test suite passing cleanly with zero regression. |
