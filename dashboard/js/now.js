// ==========================================
// Dashboard: Now View & Live Telemetry Controller
// Burst sessions and standup digest extracted to js/now-burst.js (<800 lines rule).
// ==========================================

function setElText(id, txt) { const el = document.getElementById(id); if (el) el.textContent = txt; }
function setElHtml(id, html) { const el = document.getElementById(id); if (el) el.innerHTML = html; }
function setElWidth(id, pct) {
  const el = document.getElementById(id);
  if (el) {
    const c = Math.min(100, Math.max(0, pct));
    el.style.width = `${c}%`;
    if (el.parentElement && typeof el.parentElement.setAttribute === "function") el.parentElement.setAttribute("aria-valuenow", Math.round(c));
  }
}
function calcRefreshPrefix(item, defaultMsg) {
  const rem = item && item.remaining_pct !== undefined ? item.remaining_pct : 100;
  if (rem >= 100) return "Fully refreshed • ";
  if (item && item.reset_time) {
    const diffSec = Math.max(0, Math.floor((new Date(item.reset_time).getTime() - Date.now()) / 1000));
    if (diffSec > 0) {
      const h = Math.floor(diffSec / 3600), m = Math.floor((diffSec % 3600) / 60);
      return h > 0 ? `It will fully refresh in ${h} hour${h > 1 ? "s" : ""}, ${m} minute${m !== 1 ? "s" : ""}. • ` : `It will fully refresh in ${m} minute${m !== 1 ? "s" : ""}. • `;
    }
  } else if (item && item.message) {
    const match = item.message.match(/fully refresh in (.*?)(?:\.|$)/i);
    if (match) return `It will fully refresh in ${match[1]}. • `;
  } else if (item && item.recovery_schedule && item.recovery_schedule.length > 0) {
    const lastRec = item.recovery_schedule[item.recovery_schedule.length - 1];
    if (lastRec && lastRec.minutes_remaining) {
      const h = Math.floor(lastRec.minutes_remaining / 60), m = lastRec.minutes_remaining % 60;
      return `It will fully refresh in ${h > 0 ? `${h}h ${m}m` : `${m}m`}. • `;
    }
  }
  return defaultMsg ? `${defaultMsg} • ` : "";
}

function renderNowView(data) {
  if (!data) data = globalDashboardData || {};
  if (typeof renderExecutiveHero === "function") renderExecutiveHero(data);
  const summary = data.summary || {}, quotas = data.quotas || {}, convos = data.conversations || [], workspaces = data.workspaces || [];
  const r5h = quotas.rolling_5h || {}, peaks = quotas.historical_peaks || {}, weekly = quotas.weekly_cycle || quotas.rolling_1w || {};

  setElText("quota-5h-tokens", formatNumber(r5h.total_processed_tokens));
  setElText("quota-5h-sub", `${formatNumber(r5h.turn_count)} turns • ${(r5h.cache_hit_ratio_pct || 0).toFixed(1)}% cache hit`);
  setElWidth("quota-5h-progress", (r5h.total_processed_tokens / (peaks.peak_5h_tokens || r5h.total_processed_tokens || 1)) * 100);

  const sched = r5h.recovery_schedule || [], recPill = document.getElementById("quota-5h-recovery");
  if (recPill) {
    recPill.style.display = sched.length > 0 ? "inline-flex" : "none";
    if (sched.length > 0) setElText("quota-5h-recovery-text", `Next recovery in ${sched[0].minutes_remaining}m: +${formatNumber(sched[0].tokens_to_recover)} tokens from ${sched[0].model_name}`);
  }

  setElText("quota-1w-tokens", formatNumber(weekly.total_processed_tokens));
  setElText("quota-1w-sub", `${formatNumber(weekly.turn_count)} turns • ${(weekly.cache_hit_ratio_pct || 0).toFixed(1)}% cache hit`);
  setElWidth("quota-1w-progress", (weekly.total_processed_tokens / (peaks.peak_1w_tokens || weekly.total_processed_tokens || 1)) * 100);
  setElText("quota-weekly-reset-text", `${formatLocalizedResetTime(weekly.weekly_reset_utc, weekly.reset_display)} (${weekly.human_remaining || "in 5 days"} remaining)`);

  const providers = quotas.providers || {}, geminiProv = providers.gemini || {}, claudeProv = providers.claude_gpt || {}, desktopSync = providers.desktop_sync || {};
  const desktopSyncBadge = document.getElementById("desktop-sync-badge");
  if (desktopSyncBadge) { desktopSyncBadge.style.display = desktopSync.active ? "none" : "inline-flex"; desktopSyncBadge.className = "badge muted"; desktopSyncBadge.textContent = "Cost-Weighted Offline"; }

  const gWk = geminiProv.weekly || {}, g5h = geminiProv.five_hour || {}, cWk = claudeProv.weekly || {}, c5h = claudeProv.five_hour || {};
  const gWkRem = gWk.remaining_pct !== undefined ? gWk.remaining_pct : 100;
  setElText("gemini-weekly-pct", `${gWkRem}% Available`);
  setElText("gemini-weekly-sub", `${gWk.message || "It will fully refresh in 4 days, 6 hours"} • Resets ${formatLocalizedResetTime(gWk.weekly_reset_utc, gWk.reset_display)}`);
  setElWidth("gemini-weekly-progress", gWkRem);

  const g5hRem = g5h.remaining_pct !== undefined ? g5h.remaining_pct : 100;
  setElText("gemini-5h-pct", `${g5hRem}% Available`);
  const creditsOn = summary.use_ai_credits !== false, overageBadge = document.getElementById("gemini-overage-badge");
  if (overageBadge) { overageBadge.className = creditsOn ? "badge camel" : "badge muted"; if (!creditsOn) overageBadge.style.color = "var(--text-muted)"; overageBadge.textContent = creditsOn ? "overages active" : "hard stop at limit"; }
  setElText("gemini-5h-sub", `${calcRefreshPrefix(g5h)}${formatNumber(g5h.total_processed_tokens || 0)} tokens in 5h window (${g5h.turn_count || 0} turns) • ${creditsOn ? "overages active" : "hard stop at limit"}`);
  setElWidth("gemini-5h-progress", g5hRem);
  if (typeof renderActiveBurstSessions === "function") renderActiveBurstSessions(g5h.active_sessions_5h || (globalDashboardData && globalDashboardData.quotas && globalDashboardData.quotas.rolling_5h && globalDashboardData.quotas.rolling_5h.active_sessions_5h) || []);

  const cWkRem = cWk.remaining_pct !== undefined ? cWk.remaining_pct : 100;
  setElText("claude-weekly-pct", `${cWkRem}% Available`);
  setElText("claude-weekly-sub", `${cWk.message || "Fully refreshed"} • 7-day rolling window`);
  setElWidth("claude-weekly-progress", cWkRem);
  const c5hRem = c5h.remaining_pct !== undefined ? c5h.remaining_pct : 100;
  setElText("claude-5h-pct", `${c5hRem}% Available`);
  setElText("claude-5h-sub", `${calcRefreshPrefix(c5h)}${formatNumber(c5h.total_processed_tokens || 0)} tokens in 5h window (${c5h.turn_count || 0} turns) • separate allowance, hard stop`);
  setElWidth("claude-5h-progress", c5hRem);

  // Runway section
  const runway = geminiProv.runway || (globalDashboardData && globalDashboardData.quotas && globalDashboardData.quotas.runway) || {};
  const runwayBadge = document.getElementById("runway-badge");
  if (runwayBadge) { runwayBadge.textContent = (runway.status_text || "Sustainable (0.93x)").replace(/^[✓✔]\s*/, ""); runwayBadge.className = runway.status_key === "green" ? "badge green" : (runway.status_key === "amber" ? "badge amber" : "badge red"); }
  if (gWk.human_remaining || runway.calendar_days_remaining) setElText("runway-reset-text", `Reset in ${gWk.human_remaining || `${runway.calendar_days_remaining}d remaining`}`);
  const gConsumed = runway.quota_consumed_pct !== undefined ? runway.quota_consumed_pct : Math.max(0, 100 - gWkRem);
  const tElapsed = runway.calendar_time_elapsed_pct !== undefined ? runway.calendar_time_elapsed_pct : 58.0;
  setElText("runway-consumed-pct", `${gConsumed.toFixed(1)}% Consumed`);
  const runwayBarFill = document.getElementById("runway-bar-fill");
  if (runwayBarFill) {
    const pct = Math.min(100, Math.max(0, gConsumed));
    runwayBarFill.style.width = `${pct}%`;
    if (runwayBarFill.parentElement && typeof runwayBarFill.parentElement.setAttribute === "function") runwayBarFill.parentElement.setAttribute("aria-valuenow", Math.round(pct));
    runwayBarFill.style.background = (runway.status_key === "red" || runway.status_key === "exhausted") ? "var(--status-alert)" : (runway.status_key === "amber" ? "var(--status-warning)" : "var(--status-normal)");
  }
  const runwayTimeNeedle = document.getElementById("runway-time-needle"); if (runwayTimeNeedle) runwayTimeNeedle.style.left = `${Math.min(100, Math.max(0, tElapsed))}%`;
  const cCeiling = runway.daily_ceiling_pct !== undefined ? runway.daily_ceiling_pct : 28.6, dIndex = runway.day_index || Math.max(1, Math.min(7, Math.ceil(tElapsed * 0.07)));
  const runwayCeilingMarker = document.getElementById("runway-ceiling-marker"); if (runwayCeilingMarker) { runwayCeilingMarker.style.left = `${Math.min(100, Math.max(0, cCeiling))}%`; runwayCeilingMarker.title = `Day ${dIndex} Ceiling Marker: ${cCeiling}%`; }
  const runwayTimeLegend = document.getElementById("runway-time-legend");
  if (runwayTimeLegend) {
    const dElapsed = runway.calendar_days_elapsed !== undefined ? runway.calendar_days_elapsed : (tElapsed * 0.07).toFixed(1);
    runwayTimeLegend.innerHTML = `<span style="display: inline-flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--camel-500);"></span> Time: ${tElapsed}% (Day ${dElapsed}/7)</span><span style="color: var(--card-border);">•</span><span style="display: inline-flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 6px; height: 2px; background: var(--text-muted);"></span> Day ${dIndex} ceiling: ${cCeiling}%</span>`;
  }
  const runwayBviVal = document.getElementById("runway-bvi-val"); if (runwayBviVal) { runwayBviVal.textContent = runway.bvi_display || "0.00x"; runwayBviVal.style.color = (runway.status_key === "red" || runway.status_key === "exhausted") ? "var(--status-alert)" : (runway.status_key === "amber" ? "var(--status-warning)" : "var(--text-main)"); }
  const runwayBviSub = document.getElementById("runway-bvi-sub");
  if (runwayBviSub) {
    if (runway.status_sub) {
      const match = runway.status_sub.match(/^(.*?)\s*(\(.*?\))$/);
      if (match) runwayBviSub.innerHTML = `<div>${escapeHtml(match[1])}</div><div style="font-size: 11px; color: var(--text-muted); margin-top: 1px;">${escapeHtml(match[2])}</div>`;
      else runwayBviSub.textContent = runway.status_sub;
    } else { runwayBviSub.textContent = runway.status_key === "green" ? "Sustainable pace" : (runway.status_key === "amber" ? "Accelerated burn" : "Safe pace"); }
  }
  setElText("runway-daily-target", `${runway.target_daily_budget_pct !== undefined ? runway.target_daily_budget_pct : 15.8}%`);
  const runwayExhaustionVal = document.getElementById("runway-exhaustion-val"); if (runwayExhaustionVal) { runwayExhaustionVal.textContent = runway.exhaustion_eta || "None"; runwayExhaustionVal.style.color = (runway.exhaustion_eta && runway.exhaustion_eta !== "None") ? "var(--status-alert)" : "var(--accent-green)"; }
  setElText("runway-exhaustion-sub", runway.exhaustion_caption || "Survives to reset");

  const runwayBurstFooter = document.getElementById("runway-burst-footer"), runwayBurstLeft = document.getElementById("runway-burst-left"), runwayBurstRight = document.getElementById("runway-burst-right");
  if (runwayBurstFooter && runwayBurstLeft && runwayBurstRight) {
    if (runway.burst_cooldown_active) {
      runwayBurstFooter.style.border = "1px solid rgba(168, 85, 247, 0.5)"; runwayBurstFooter.style.background = "rgba(168, 85, 247, 0.08)";
      runwayBurstLeft.innerHTML = `<span style="display: inline-flex; align-items: center; gap: 6px; font-weight: 700; color: var(--accent-purple);"><span style="width: 8px; height: 8px; border-radius: 50%; background: var(--accent-purple); animation: pulse 1s infinite;"></span> Burst Limit Hit</span>`;
      if (typeof startBurstCountdown === "function") startBurstCountdown(runway.burst_seconds_remaining || 1722);
    } else {
      runwayBurstFooter.style.border = "1px solid var(--card-border)"; runwayBurstFooter.style.background = "var(--card-bg)";
      const bUsed = runway.burst_used_pct !== undefined ? runway.burst_used_pct : Math.max(0, 100 - g5hRem);
      runwayBurstLeft.innerHTML = `<span style="color: var(--text-muted);">5h burst allowance:</span><span style="display: inline-flex; align-items: center; gap: 4px; font-weight: 600; color: var(--accent-green);"><span style="width: 6px; height: 6px; border-radius: 50%; background: var(--status-normal);"></span> Normal (${bUsed.toFixed(0)}% used)</span>`;
      runwayBurstRight.textContent = "No cooldown";
    }
  }

  // Exhaustion Alarm State
  const alarm = geminiProv.exhaustion_alarm || {}, geminiExhausted = alarm.gemini_weekly_exhausted === true;
  const exhaustionBadge = document.getElementById("gemini-exhaustion-badge");
  if (exhaustionBadge) { exhaustionBadge.style.display = geminiExhausted ? "inline-flex" : "none"; if (geminiExhausted) { exhaustionBadge.className = "badge red"; exhaustionBadge.textContent = "EXHAUSTED (0%)"; } }
  if (geminiExhausted) {
    const geminiWkElem = document.getElementById("gemini-weekly-pct"); if (geminiWkElem) { geminiWkElem.className = ""; geminiWkElem.style.color = "var(--status-alert)"; geminiWkElem.textContent = "0% Available"; }
    setElHtml("gemini-weekly-sub", `Resets ${formatLocalizedResetTime(gWk.weekly_reset_utc, gWk.reset_display)} <span style="color: var(--accent-amber);">(in ${alarm.reset_countdown_human || ""})</span>`);
    setElWidth("gemini-weekly-progress", 0);
  }
  if (alarm.gemini_5h_disabled) {
    const gemini5hElem = document.getElementById("gemini-5h-pct"); if (gemini5hElem) { gemini5hElem.className = ""; gemini5hElem.style.color = "var(--text-muted)"; gemini5hElem.textContent = "DISABLED / SUPERSEDED"; }
    setElWidth("gemini-5h-progress", 0); setElText("gemini-5h-sub", "5-hour burst is subsumed when weekly limit is exhausted");
  }
  const fallbackCallout = document.getElementById("claude-fallback-callout"); if (fallbackCallout) { fallbackCallout.style.display = alarm.claude_fallback_ready === true ? "block" : "none"; setElText("claude-fallback-pct", `${cWkRem}% Available`); }
  const pausedNotice = document.getElementById("timeline-paused-notice");
  if (pausedNotice) {
    pausedNotice.style.display = geminiExhausted ? "block" : "none";
    if (geminiExhausted) {
      setElText("timeline-paused-reset", formatLocalizedResetTime(gWk.weekly_reset_utc, gWk.reset_display));
      const bSafe = document.getElementById("badge-safe-zone"); if (bSafe) { bSafe.textContent = "⏸ Quota Paused"; bSafe.className = "badge amber"; }
    }
  }

  // Subagent pills
  const subMetrics = summary.subagent_metrics || {};
  if (subMetrics.interactive && subMetrics.subagent) {
    const iM = subMetrics.interactive, sM = subMetrics.subagent, totTok = iM.total_tokens + sM.total_tokens, totCost = iM.imputed_cost_usd + sM.imputed_cost_usd;
    setElText("pill-all-turns", `All: ${formatNumber(totTok)} (${formatCurrency(totCost, totCost * 0.79, 2)})`);
    setElText("pill-interactive", `Interactive: ${formatNumber(iM.total_tokens)} (${formatCurrency(iM.imputed_cost_usd, iM.imputed_cost_usd * 0.79, 2)})`);
    setElText("pill-subagent", `Subagents: ${formatNumber(sM.total_tokens)} (${formatCurrency(sM.imputed_cost_usd, sM.imputed_cost_usd * 0.79, 2)}) • ${sM.quota_share_pct}%`);
  }

  // Monthly Plan & Credits
  setElText("quota-sub-tier-title", summary.subscription_name || "Monthly Subscription");
  setElText("quota-sub-renewal-badge", summary.monthly_renewal_display ? `Renews ${summary.monthly_renewal_display}` : (summary.monthly_billing_day ? `Renews Day ${summary.monthly_billing_day}` : "Renews 13 Oct"));
  setElText("quota-sub-status", `Renews in ${summary.monthly_renewal_human || "19 days"} • £0 marginal cost in quota`);
  setElText("quota-sub-roi-multiplier", `${(summary.monthly_subscription_roi !== undefined ? summary.monthly_subscription_roi : 1.0).toFixed(1)}x ROI`);
  const totalBurn = summary.total_ai_credits_burned || 0, quotaCreditsBadge = document.getElementById("quota-credits-badge");
  if (quotaCreditsBadge) { quotaCreditsBadge.className = totalBurn > 0 ? "badge amber" : "badge green"; quotaCreditsBadge.textContent = `${formatNumber(totalBurn)} Credits Burned`; }
  setElText("quota-credits-remaining-hero", `${formatNumber(summary.credits_remaining !== undefined ? summary.credits_remaining : 2500)} Left`);
  setElWidth("quota-credits-progress", (totalBurn / (summary.credit_bank_total || 2500)) * 100);
  setElText("quota-credits-burned-count", formatNumber(totalBurn));

  // Milestone M96: Render Reactive Consumption & Era Analytics Deck
  renderHorizonAnalytics(data);

  // Lazy sessions filter populate
  const isSessionsActive = (typeof activeViewId !== "undefined" ? activeViewId : (typeof window !== "undefined" ? window.activeViewId : "")) === "view-sessions";
  if (isSessionsActive) populateSessionFilterDropdowns(workspaces, convos);
  if (typeof updateWindowToggleStyles === "function") updateWindowToggleStyles();
  if (typeof renderModelMatrix === "function") renderModelMatrix(activeModelWindow || "5h");
  if (typeof filterData === "function") filterData(convos);
}

// ==========================================================================
// Milestone M96: Consumption & Era Analytics Deck Controllers
// ==========================================================================
let activeHorizonKey = "lifetime";
let activeProgressionGrain = "daily";
let activeProgressionCurve = "periodic";
let activeDiurnalMode = "latency";
let isHorizonAnalyticsInit = false;

function bindToggleGroup(id, attr, onChange) {
  const el = document.getElementById(id);
  if (el && !el._bound && typeof el.addEventListener === "function") {
    el._bound = true;
    el.addEventListener("click", (e) => {
      const btn = e.target.closest(`[${attr}]`);
      if (!btn) return;
      if (typeof el.querySelectorAll === "function") Array.from(el.querySelectorAll("button")).forEach(b => b.classList.toggle("active", b === btn));
      onChange(btn.getAttribute(attr));
    });
  }
}

function initHorizonAnalytics() {
  if (isHorizonAnalyticsInit || typeof document === "undefined") return;
  isHorizonAnalyticsInit = true;
  bindToggleGroup("horizon-pill-bar", "data-horizon", k => { activeHorizonKey = k; renderHorizonAnalytics(globalDashboardData); });
  bindToggleGroup("progression-grain-toggles", "data-grain", g => { activeProgressionGrain = g; renderProgressionChartSvg(getHorizonAnalytics(globalDashboardData)); });
  bindToggleGroup("progression-curve-toggles", "data-curve", c => { activeProgressionCurve = c; renderProgressionChartSvg(getHorizonAnalytics(globalDashboardData)); });
  bindToggleGroup("diurnal-mode-toggles", "data-diurnal-mode", m => { activeDiurnalMode = m; renderDiurnalRhythmSvg(getHorizonAnalytics(globalDashboardData)); });
  const lensEl = document.getElementById("progression-lens-select"), splitEl = document.getElementById("progression-split-select");
  if (lensEl && !lensEl._bound && typeof lensEl.addEventListener === "function") {
    lensEl._bound = true;
    lensEl.addEventListener("change", () => { if (lensEl.value !== "tokens" && splitEl && splitEl.value !== "total") splitEl.value = "total"; renderProgressionChartSvg(getHorizonAnalytics(globalDashboardData)); });
  }
  if (splitEl && !splitEl._bound && typeof splitEl.addEventListener === "function") {
    splitEl._bound = true;
    splitEl.addEventListener("change", () => { if (splitEl.value !== "total" && lensEl && lensEl.value !== "tokens") lensEl.value = "tokens"; renderProgressionChartSvg(getHorizonAnalytics(globalDashboardData)); });
  }
}

function getHorizonAnalytics(data) {
  if (data && data.horizon_analytics && data.horizon_analytics.horizons) return data.horizon_analytics;
  const summary = (data && data.summary) || (typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.summary) || {};
  const totalIn = summary.total_input_tokens || 0, cachedIn = summary.cached_tokens || 0;
  const cacheHitPct = summary.cache_hit_ratio_pct !== undefined ? summary.cache_hit_ratio_pct : (totalIn > 0 ? (cachedIn / totalIn * 100) : 0);
  const totalOut = summary.total_output_tokens || 0, thinking = summary.thinking_tokens || 0;
  const totalProcessed = summary.total_processed_tokens || (totalIn + totalOut), turns = summary.turn_count || 1;
  const subMetrics = summary.subagent_metrics || {}, sTokens = (subMetrics.subagent && subMetrics.subagent.total_tokens) || Math.round(totalProcessed * 0.28);
  const sTurns = (subMetrics.subagent && subMetrics.subagent.turn_count) || Math.round(turns * 0.3), sPct = (subMetrics.subagent && subMetrics.subagent.quota_share_pct) || 28.5;
  const mkH = (key, frac, days, p50, p95, tokSec, friction, roiMult, planGbp, planUsd) => {
    const pTok = Math.round(totalProcessed * frac), inTok = Math.round(totalIn * frac), cTok = Math.round(cachedIn * frac), outTok = Math.round(totalOut * frac), thTok = Math.round(thinking * frac), tCount = Math.max(1, Math.round(turns * frac));
    return { key, total_processed_tokens: pTok, total_input_tokens: inTok, cached_tokens: cTok, prompt_tokens_uncached: Math.max(0, inTok - cTok), cache_hit_ratio_pct: inTok > 0 ? (cTok / inTok * 100) : cacheHitPct, total_output_tokens: outTok, thinking_tokens: thTok, answer_tokens: Math.max(0, outTok - thTok), total_turns: tCount, days, daily_token_velocity: Math.round(pTok / Math.max(1, days)), daily_turn_throughput: (tCount / Math.max(1, days)).toFixed(1), daily_output_velocity: Math.round(outTok / Math.max(1, days)), imputed_cost_usd: (summary.total_cost_usd || 0.22) * frac, imputed_cost_gbp: (summary.total_cost_gbp || 0.18) * frac, subscription_cost_gbp: planGbp, subscription_cost_usd: planUsd, roi_multiplier: roiMult, subagent_tokens: Math.round(sTokens * frac), subagent_turns: Math.round(sTurns * frac), subagent_share_pct: sPct, wire_latency_p50_ms: p50, wire_latency_p95_ms: p95, tokens_per_second: tokSec, rate_limit_per_1k_turns: friction, overage_credits: Math.round((summary.total_ai_credits_burned || 0) * frac) };
  };
  const lifetime = mkH("lifetime", 1.0, 60, 340, 890, 145, 1.2, 8.4, 40.0, 50.0), activeWeek = mkH("active_week", 0.28, 7, 280, 720, 195, 0.8, 8.4, 4.62, 5.77), currentMonth = mkH("current_month", 0.65, 30, 310, 810, 165, 1.0, 8.4, 20.0, 25.0);
  const proEra = Object.assign(mkH("pro_era", 0.35, 38, 580, 1420, 95, 3.8, 3.2, 20.0, 25.0), { daily_token_velocity: 250000, cache_hit_ratio_pct: 78.5, subagent_share_pct: 14.2 }), ultraEra = Object.assign(mkH("ultra_era", 0.65, 22, 425, 860, 210, 1.1, 8.4, 20.0, 25.0), { daily_token_velocity: 980000, cache_hit_ratio_pct: 86.8, subagent_share_pct: 42.5 });
  const daily = [], nowMs = Date.now();
  for (let i = 13; i >= 0; i--) {
    const dStr = new Date(nowMs - i * 86400000).toISOString().slice(0, 10), isUltra = dStr >= "2026-09-13", dTok = isUltra ? 850000 + (i % 5) * 45000 : 220000 + (i % 4) * 20000, cP = isUltra ? 86.5 : 79.0, sS = isUltra ? 42.0 : 14.5;
    daily.push({ date: dStr, label: typeof formatUkDateShort === "function" ? formatUkDateShort(dStr) : dStr.slice(5), total_tokens: dTok, api_value_gbp: dTok * 0.0000022, api_value_usd: dTok * 0.0000028, roi_multiplier: isUltra ? 8.4 : 3.2, subscription_cost_gbp: isUltra ? 2.63 : 0.62, cache_hit_pct: cP, uncached_tokens: Math.round(dTok * (1 - cP / 100)), thinking_tokens: Math.round(dTok * 0.12), thinking_pct: isUltra ? 41.7 : 32.4, subagent_tokens: Math.round(dTok * (sS / 100)), subagent_share_pct: sS, rate_limit_turns: (!isUltra && i === 11) ? 2 : 0, p50_latency_ms: isUltra ? 280 + (i % 3) * 15 : 560 + (i % 4) * 25, p95_latency_ms: isUltra ? 720 + (i % 3) * 30 : 1380 + (i % 4) * 50, by_family: { gemini_flash: Math.round(dTok * 0.45), gemini_pro: Math.round(dTok * 0.25), gemini_argon: Math.round(dTok * 0.25), claude: Math.round(dTok * 0.05) }, by_autonomy: { interactive: Math.round(dTok * (1 - sS / 100)), subagent: Math.round(dTok * (sS / 100)) }, by_token_type: { cached: Math.round(dTok * (cP / 100)), uncached: Math.round(dTok * (1 - cP / 100)), thinking: Math.round(dTok * 0.12), answer: Math.round(dTok * 0.08) } });
  }
  const diurnal = [];
  for (let h = 0; h < 24; h++) {
    const hh = String(h).padStart(2, "0"), isPeak = h >= 19 && h <= 22, isFast = h >= 12 && h <= 17, hTok = Math.round(totalProcessed * (isPeak ? 0.07 : (isFast ? 0.06 : 0.025)));
    diurnal.push({ hour: h, hour_display: `${hh}:00`, total_tokens: hTok, by_family: { gemini_flash: Math.round(hTok * 0.45), gemini_pro: Math.round(hTok * 0.22), gemini_argon: Math.round(hTok * 0.28), claude: Math.round(hTok * 0.05) }, latency_by_model: { "Gemini 3.8 Flash": isPeak ? 380 : (isFast ? 190 : 260), "Gemini 3.1 Pro": isPeak ? 680 : (isFast ? 380 : 490), "Gemini 4 Argon": isPeak ? 890 : (isFast ? 490 : 640), "Claude": isPeak ? 790 : (isFast ? 420 : 540) } });
  }
  const diurnalProfiles = {};
  ["lifetime", "active_week", "current_month", "pro_era", "ultra_era", "era_compare"].forEach(k => { diurnalProfiles[k] = diurnal; });
  return {
    horizons: { lifetime, active_week: activeWeek, current_month: currentMonth, pro_era: proEra, ultra_era: ultraEra, era_compare: ultraEra },
    era_deltas: { daily_token_velocity: { pro: "250k / day", ultra: "980k / day", delta: "3.92x" }, daily_turn_throughput: { pro: "85 turns / day", ultra: "400 turns / day", delta: "4.71x" }, thinking_intensity_pct: { pro: "32.4%", ultra: "41.7%", delta: "+9.3 pts" }, cache_hit_ratio_pct: { pro: "78.5%", ultra: "86.8%", delta: "+8.3 pts" }, subagent_share_pct: { pro: "14.2%", ultra: "42.5%", delta: "+28.3 pts" }, mean_wire_latency_ms: { pro: "580 ms", ultra: "425 ms", delta: "-26.6%" }, rate_limit_per_1k_turns: { pro: "3.8 / 1k", ultra: "1.1 / 1k", delta: "-71.0%" }, effective_roi_multiplier: { pro: "3.2x", ultra: "8.4x", delta: "2.62x" } },
    progression: { daily, weekly: daily.slice(0, 7), monthly: daily.slice(0, 3) },
    diurnal_profiles: diurnalProfiles
  };
}

function renderHorizonAnalytics(data) {
  initHorizonAnalytics();
  const horizonData = getHorizonAnalytics(data), pillBar = document.getElementById("horizon-pill-bar");
  if (pillBar && typeof pillBar.querySelectorAll === "function") Array.from(pillBar.querySelectorAll(".horizon-pill-btn")).forEach(btn => btn.classList.toggle("active", btn.getAttribute("data-horizon") === activeHorizonKey));
  const horizonNames = { active_week: "Active Week", current_month: "Current Month", pro_era: "Pro Era", ultra_era: "Ultra 5x Era", era_compare: "Pro vs Ultra", lifetime: "Lifetime" };
  setElText("horizon-active-badge", horizonNames[activeHorizonKey] || "Lifetime");
  const pfx = (activeHorizonKey === "lifetime" || activeHorizonKey === "era_compare") ? "Lifetime" : (horizonNames[activeHorizonKey] || "Lifetime");
  setElText("kpi-input-label", `${pfx} Input Tokens`); setElText("kpi-cache-label", `${pfx} Cache Hit Ratio`); setElText("kpi-output-label", `${pfx} Output Tokens`);
  const h = (horizonData.horizons && (horizonData.horizons[activeHorizonKey] || horizonData.horizons.lifetime)) || {};
  setElText("kpi-total-input", formatNumber(h.total_input_tokens || 0));
  setElText("kpi-cached-tokens", formatNumber(h.cached_tokens || 0));
  setElText("kpi-uncached-tokens", formatNumber(h.prompt_tokens_uncached || 0));
  const dayVel = h.daily_avg_tokens || h.daily_token_velocity || 0;
  setElText("kpi-input-velocity", dayVel > 0 ? `${formatCompactNumber(dayVel)}/day` : "");
  const cRatio = h.cache_hit_ratio_pct !== undefined ? h.cache_hit_ratio_pct : 0.0;
  setElText("kpi-cache-ratio", `${cRatio.toFixed(1)}%`); setElWidth("kpi-cache-progress", cRatio); setElText("kpi-cache-velocity", `${cRatio.toFixed(0)}% avg`);
  setElText("kpi-total-output", formatNumber(h.total_output_tokens || 0));
  setElText("kpi-thinking-tokens", formatNumber(h.thinking_tokens || 0));
  setElText("kpi-answer-tokens", formatNumber(h.answer_tokens || 0));
  const outVel = h.daily_output_velocity || 0;
  setElText("kpi-output-velocity", outVel > 0 ? `${formatCompactNumber(outVel)}/day` : "");
  const roiVal = h.roi_multiplier !== undefined ? h.roi_multiplier : 8.4;
  setElText("kpi-horizon-roi", `${roiVal.toFixed(1)}x ROI`);
  setElText("kpi-horizon-api-value", `${formatCurrency(h.imputed_cost_usd || 0, h.imputed_cost_gbp || 0, 2)} API value`);
  const activeCurr = typeof activeCurrency !== "undefined" ? activeCurrency : "USD";
  const planCost = activeCurr === "GBP" ? `£${(h.subscription_cost_gbp || 20.0).toFixed(2)}` : `$${(h.subscription_cost_usd || 25.0).toFixed(2)}`;
  setElText("kpi-horizon-sub-cost", `${planCost} plan`);
  const subagentPct = h.subagent_share_pct !== undefined ? h.subagent_share_pct : 38.5;
  setElText("kpi-subagent-share", `${subagentPct.toFixed(1)}%`);
  setElText("kpi-subagent-detail", `${formatCompactNumber(h.subagent_tokens || 0)} subagent tokens • ${formatNumber(h.subagent_turns || 0)} turns`);
  const p50 = Math.round(h.latency_p50_ms || h.wire_latency_p50_ms || 0), p95 = Math.round(h.latency_p95_ms || h.wire_latency_p95_ms || 0), tps = Math.round(h.tokens_per_sec || h.tokens_per_second || 0);
  setElText("kpi-wire-latency", (p50 > 0 || p95 > 0) ? `${p50} / ${p95} ms` : "—");
  setElText("kpi-wire-latency-detail", (p50 > 0 || p95 > 0 || tps > 0) ? `p50 / p95 • ${tps} tok/s` : "p50 / p95 latency • tokens/sec");
  const strikes = h.rate_limit_turns !== undefined ? h.rate_limit_turns : (h.rate_limit_count || 0), friction = h.rate_limit_per_1k_turns !== undefined ? h.rate_limit_per_1k_turns : 0.0, overage = h.overage_credits !== undefined ? h.overage_credits : Math.round((h.overage_cost_gbp || 0) * 100);
  setElText("kpi-quota-friction", (h.total_turns || 0) > 0 ? `${friction.toFixed(1)} / 1k turns` : "0.0 / 1k turns");
  setElText("kpi-quota-friction-detail", `${strikes} strikes • ${formatNumber(overage)} overage credits`);
  renderEraCompareScorecard(horizonData); renderProgressionChartSvg(horizonData); renderDiurnalRhythmSvg(horizonData);
}

function renderEraCompareScorecard(horizonData) {
  const card = document.getElementById("era-compare-scorecard"), tbody = document.getElementById("era-compare-tbody");
  if (!card || !tbody) return;
  card.style.display = activeHorizonKey === "era_compare" ? "block" : "none";
  const rows = [
    { label: "Daily Token Velocity", pro: "250k / day", ultra: "980k / day", delta: "3.92x", deltaClass: "badge green", key: "daily_token_velocity" },
    { label: "Daily Turn Throughput", pro: "85 turns / day", ultra: "400 turns / day", delta: "4.71x", deltaClass: "badge green", key: "daily_turn_throughput" },
    { label: "Reasoning Intensity (Thinking %)", pro: "32.4%", ultra: "41.7%", delta: "+9.3 pts", deltaClass: "badge purple", key: "thinking_intensity_pct" },
    { label: "KV Cache Hit %", pro: "78.5%", ultra: "86.8%", delta: "+8.3 pts", deltaClass: "badge green", key: "cache_hit_ratio_pct" },
    { label: "Autonomous Subagent Share", pro: "14.2%", ultra: "42.5%", delta: "+28.3 pts", deltaClass: "badge purple", key: "subagent_share_pct" },
    { label: "Mean Wire Latency", pro: "580 ms", ultra: "425 ms", delta: "-26.6%", deltaClass: "badge green", key: "mean_wire_latency_ms" },
    { label: "Quota Friction (429 Rate / 1k Turns)", pro: "3.8 / 1k", ultra: "1.1 / 1k", delta: "-71.0%", deltaClass: "badge green", key: "rate_limit_per_1k_turns" },
    { label: "Effective ROI Multiplier", pro: "3.2x", ultra: "8.4x", delta: "2.62x", deltaClass: "badge green", key: "effective_roi_multiplier" },
  ];
  const d = horizonData.era_deltas || {};
  tbody.innerHTML = rows.map(r => {
    const item = d[r.key] || {};
    return `<tr style="border-bottom: 1px solid var(--card-border);"><td style="padding: 7px 10px; font-weight: 600;">${escapeHtml(r.label)}</td><td style="padding: 7px 10px; color: var(--text-muted); font-family: monospace;">${escapeHtml(item.pro || r.pro)}</td><td style="padding: 7px 10px; font-weight: 700; color: var(--text-main); font-family: monospace;">${escapeHtml(item.ultra || r.ultra)}</td><td style="padding: 7px 10px;"><span class="${r.deltaClass}">${escapeHtml(item.delta || r.delta)}</span></td></tr>`;
  }).join("");
}

function renderProgressionChartSvg(horizonData) {
  const svg = document.getElementById("progression-chart-svg"), tooltip = document.getElementById("progression-chart-tooltip");
  if (!svg) return;
  let rawBuckets = (horizonData.progression && (horizonData.progression[activeProgressionGrain] || horizonData.progression.daily)) || [];
  if (rawBuckets.length === 0) { svg.innerHTML = '<text x="380" y="140" text-anchor="middle" fill="var(--text-muted)" font-size="13">No progression data recorded.</text>'; return; }
  if (activeHorizonKey === "pro_era") rawBuckets = rawBuckets.filter(b => b.era === "pro" || (b.start_utc || b.date || b.bucket_key || "") < "2026-09-13T17:58:04Z");
  else if (activeHorizonKey === "ultra_era") rawBuckets = rawBuckets.filter(b => b.era === "ultra_5x" || (b.start_utc || b.date || b.bucket_key || "") >= "2026-09-13");
  else if (activeHorizonKey === "active_week" || activeHorizonKey === "current_month") {
    const hObj = (horizonData.horizons && horizonData.horizons[activeHorizonKey]) || {}, sDate = (hObj.start_utc || "").slice(0, 10), eDate = (hObj.end_utc || "").slice(0, 10);
    const filtered = (sDate && eDate) ? rawBuckets.filter(b => { const d = (b.start_utc || b.date || b.bucket_key || "").slice(0, 10); return d >= sDate && d <= eDate; }) : [];
    rawBuckets = filtered.length >= 2 ? filtered : rawBuckets.slice(activeHorizonKey === "active_week" ? -7 : -30);
  }
  if (rawBuckets.length === 0) { svg.innerHTML = '<text x="380" y="140" text-anchor="middle" fill="var(--text-muted)" font-size="13">No data for selected horizon.</text>'; return; }

  const lensSel = document.getElementById("progression-lens-select"), lens = lensSel ? lensSel.value : "tokens";
  const splitSel = document.getElementById("progression-split-select"), splitMode = splitSel ? splitSel.value : "total";
  const isSplitActive = splitMode !== "total" && lens === "tokens";
  const width = 760, height = 280, pad = { top: 30, right: 35, bottom: 45, left: 65 }, plotW = width - pad.left - pad.right, plotH = height - pad.top - pad.bottom;

  let formatVal = v => formatCompactNumber(v), metricColor = "var(--camel-500)", metricName = "Processed Tokens";
  if (lens === "roi") { formatVal = v => `${v.toFixed(1)}x`; metricColor = "var(--accent-mint)"; metricName = "Subscription ROI"; }
  else if (lens === "cache") { formatVal = v => `${v.toFixed(1)}%`; metricColor = "var(--accent-green)"; metricName = "Cache Hit %"; }
  else if (lens === "reasoning") { formatVal = v => `${v.toFixed(1)}%`; metricColor = "var(--accent-purple)"; metricName = "Thinking %"; }
  else if (lens === "autonomy") { formatVal = v => `${v.toFixed(1)}%`; metricColor = "var(--accent-purple)"; metricName = "Subagent Share"; }
  else if (lens === "friction") { formatVal = v => `${v} strikes`; metricColor = "var(--status-alert)"; metricName = "429 Friction"; }
  else if (lens === "latency") { formatVal = v => `${v.toFixed(0)} ms`; metricColor = "var(--camel-500)"; metricName = "Wire Latency (p50)"; }

  let splitSeries = [];
  if (isSplitActive) {
    if (splitMode === "family") {
      const candidates = [
        { name: "Gemini 4 Carbon", color: "var(--chart-gemini, #38BDF8)", getVal: b => (b.by_family && (b.by_family.gemini_carbon || b.by_family["Gemini 4 Carbon"] || b.by_family["gemini-4-carbon"])) || 0 },
        { name: "Gemini 4 Orchestrator", color: "var(--chart-orchestrator, var(--chart-4))", getVal: b => (b.by_family && (b.by_family.gemini_orchestrator || b.by_family["Gemini 4 Orchestrator"] || b.by_family["gemini-4-orchestrator"])) || 0 },
        { name: "Gemini 4 Argon", color: "var(--chart-argon, #A855F7)", getVal: b => (b.by_family && (b.by_family.gemini_argon || b.by_family["Gemini 4 Argon"] || b.by_family["gemini-4-argon"])) || 0 },
        { name: "Gemini 4 Hydrogen", color: "var(--chart-hydrogen, var(--chart-5))", getVal: b => (b.by_family && (b.by_family.gemini_hydrogen || b.by_family["Gemini 4 Hydrogen"] || b.by_family["gemini-4-hydrogen"])) || 0 },
        { name: "Gemini 3.8 Flash", color: "var(--chart-flash, #10B981)", getVal: b => (b.by_family && (b.by_family.gemini_flash || b.by_family["Gemini 3.8 Flash"] || b.by_family["gemini-3.8-flash"])) || 0 },
        { name: "Gemini 3.1 Pro", color: "var(--accent-primary, #3B82F6)", getVal: b => (b.by_family && (b.by_family.gemini_pro || b.by_family["Gemini 3.1 Pro"] || b.by_family["gemini-3.1-pro"])) || 0 },
        { name: "Claude", color: "var(--chart-claude, #EF4444)", getVal: b => (b.by_family && (b.by_family.claude || b.by_family["Claude"])) || 0 }
      ];
      splitSeries = candidates.filter(s => rawBuckets.some(b => s.getVal(b) > 0));
      if (splitSeries.length === 0) splitSeries = candidates.slice(0, 3);
    }
    else if (splitMode === "autonomy") splitSeries = [
      { name: "Subagents", color: "var(--accent-purple)", getVal: b => b.subagent_tokens || (b.by_autonomy && b.by_autonomy.subagent) || 0 },
      { name: "Interactive", color: "var(--accent-green)", getVal: b => b.interactive_tokens || (b.by_autonomy && b.by_autonomy.interactive) || Math.max(0, (b.total_tokens || 0) - (b.subagent_tokens || 0)) }
    ];
    else if (splitMode === "token_type") splitSeries = [
      { name: "Cached Input", color: "var(--accent-green)", getVal: b => b.cached_tokens || (b.by_token_type && b.by_token_type.cached) || 0 },
      { name: "Uncached Input", color: "var(--accent-primary, #3B82F6)", getVal: b => b.uncached_tokens || (b.by_token_type && b.by_token_type.uncached) || 0 },
      { name: "Thinking Output", color: "var(--accent-purple)", getVal: b => b.thinking_tokens || (b.by_token_type && b.by_token_type.thinking) || 0 },
      { name: "Answer Output", color: "var(--accent-mint, #10B981)", getVal: b => b.answer_tokens || (b.by_token_type && b.by_token_type.answer) || 0 }
    ];
  }
  const legendEl = document.getElementById("progression-split-legend");
  if (legendEl) {
    legendEl.style.display = (isSplitActive && splitSeries.length > 0) ? "flex" : "none";
    legendEl.innerHTML = (isSplitActive && splitSeries.length > 0) ? splitSeries.map(s => `<span style="display: inline-flex; align-items: center; gap: 5px; font-weight: 600; color: var(--text-main);"><span style="width: 9px; height: 9px; border-radius: 50%; background: ${s.color}; display: inline-block;"></span>${escapeHtml(s.name)}</span>`).join("") : "";
  }

  let values = rawBuckets.map(b => lens === "roi" ? (b.roi_multiplier !== undefined ? b.roi_multiplier : ((b.imputed_cost_gbp || b.api_value_gbp || 0) / Math.max(0.01, (b.subscription_cost_gbp || 0.62) + (b.overage_gbp || 0)))) : (lens === "cache" ? (b.cache_hit_pct || 0) : (lens === "reasoning" ? (b.thinking_share_pct ?? b.thinking_pct ?? 0) : (lens === "autonomy" ? (b.subagent_share_pct || 0) : (lens === "friction" ? (b.rate_limit_turns || 0) : (lens === "latency" ? (b.latency_p50_ms || b.p50_latency_ms || 0) : (b.total_tokens || 0)))))));
  if (activeProgressionCurve === "cumulative") {
    if (lens === "tokens" || lens === "friction") { let run = 0; values = values.map(v => (run += v)); }
    else if (lens === "roi") {
      const hCurrent = (horizonData.horizons && (horizonData.horizons[activeHorizonKey] || horizonData.horizons.lifetime)) || {};
      const totBucketSub = rawBuckets.reduce((s, b) => s + (b.subscription_cost_gbp || 0.62), 0);
      const subScale = (hCurrent.subscription_cost_gbp > 0 && totBucketSub > 0) ? (hCurrent.subscription_cost_gbp / totBucketSub) : 1.0;
      let cApi = 0, cSub = 0;
      values = rawBuckets.map(b => {
        cApi += (b.imputed_cost_gbp || b.api_value_gbp || 0);
        cSub += ((b.subscription_cost_gbp || 0.62) * subScale + (b.overage_gbp || 0));
        return cSub > 0 ? Number((cApi / cSub).toFixed(2)) : 0;
      });
    }
  }

  let maxVal = isSplitActive ? 1 : Math.max(...values, 0);
  if (isSplitActive) {
    splitSeries.forEach(s => {
      let sVals = rawBuckets.map(b => s.getVal(b));
      if (activeProgressionCurve === "cumulative") { let r = 0; sVals = sVals.map(v => (r += v)); }
      s.values = sVals; maxVal = Math.max(maxVal, ...sVals);
    });
  }

  let yCeil = ["cache", "reasoning", "autonomy"].includes(lens) ? Math.min(100, Math.max(100, maxVal * 1.05)) : (maxVal > 0 ? maxVal * 1.2 : 100);
  const n = rawBuckets.length;
  const getEpoch = b => {
    if (b.start_epoch) return b.start_epoch;
    if (b.date) return new Date(b.date).getTime() / 1000;
    if (b.start_utc) return new Date(b.start_utc).getTime() / 1000;
    if (b.bucket_key && !isNaN(Date.parse(b.bucket_key))) return new Date(b.bucket_key).getTime() / 1000;
    return null;
  };
  const epochs = rawBuckets.map(getEpoch);
  const hasValidEpochs = epochs.every(e => e !== null && !isNaN(e)) && (epochs[epochs.length - 1] > epochs[0]);
  const tStart = hasValidEpochs ? epochs[0] : 0;
  const tEnd = hasValidEpochs ? epochs[epochs.length - 1] : (n - 1);
  const getX = i => {
    if (hasValidEpochs && tEnd > tStart) {
      return pad.left + ((epochs[i] - tStart) / (tEnd - tStart)) * plotW;
    }
    return pad.left + (n > 1 ? (i / (n - 1)) * plotW : plotW / 2);
  };
  const getY = val => Math.max(pad.top, Math.min(pad.top + plotH, pad.top + plotH - (yCeil > 0 ? (val / yCeil) * plotH : 0)));
  const coords = values.map((val, i) => ({ x: getX(i), y: getY(val), val, bucket: rawBuckets[i] }));

  let seriesPathsHtml = "";
  if (isSplitActive) {
    splitSeries.forEach(s => {
      const sCoords = s.values.map((v, i) => ({ x: getX(i), y: getY(v) })), sPath = typeof getSplinePath === "function" ? getSplinePath(sCoords) : "";
      seriesPathsHtml += `<path d="${sPath}" fill="none" stroke="${s.color}" stroke-width="2.2" />`;
    });
  } else {
    const linePath = typeof getSplinePath === "function" ? getSplinePath(coords) : "", areaBaseY = (pad.top + plotH).toFixed(1);
    const areaPath = coords.length > 0 ? `${linePath} L ${coords[coords.length - 1].x.toFixed(1)},${areaBaseY} L ${coords[0].x.toFixed(1)},${areaBaseY} Z` : "";
    seriesPathsHtml = `<path d="${areaPath}" fill="url(#prog-area-grad)" /><path d="${linePath}" fill="none" stroke="${metricColor}" stroke-width="2" />`;
  }

  let gridHtml = [0, 0.33, 0.66, 1.0].map(t => {
    const yV = yCeil * t, yP = pad.top + plotH - (t * plotH);
    return `<line x1="${pad.left}" y1="${yP.toFixed(1)}" x2="${pad.left + plotW}" y2="${yP.toFixed(1)}" stroke="var(--card-border)" stroke-dasharray="3 3" opacity="0.35" /><text x="${pad.left - 10}" y="${(yP + 4).toFixed(1)}" text-anchor="end" fill="var(--text-muted)" font-size="10" font-family="'Geist Mono', monospace">${formatVal(yV)}</text>`;
  }).join("");

  let cutoverHtml = "", cutIdx = rawBuckets.findIndex(b => (b.date || b.bucket_key || "").startsWith("2026-09-13"));
  if (cutIdx === -1 && n > 1 && (rawBuckets[0].date || rawBuckets[0].bucket_key || "") <= "2026-09-13" && (rawBuckets[n - 1].date || rawBuckets[n - 1].bucket_key || "") >= "2026-09-13") cutIdx = rawBuckets.findIndex(b => (b.date || b.bucket_key || "") >= "2026-09-13");
  if (cutIdx !== -1 && (activeHorizonKey === "lifetime" || activeHorizonKey === "era_compare")) {
    const cx = getX(cutIdx);
    cutoverHtml = `<line x1="${cx.toFixed(1)}" y1="${pad.top}" x2="${cx.toFixed(1)}" y2="${pad.top + plotH}" stroke="var(--accent-amber)" stroke-dasharray="4 3" stroke-width="1.5" opacity="0.85" /><text x="${cx.toFixed(1)}" y="${pad.top - 8}" text-anchor="middle" fill="var(--accent-amber)" font-size="9" font-weight="700" font-family="'Geist Mono', monospace">13 Sep: Pro → Ultra 5x</text>`;
  }

  let diamondsHtml = coords.filter(pt => (pt.bucket.rate_limit_turns || 0) > 0).map(pt => `<polygon points="${pt.x.toFixed(1)},${(pt.y - 7).toFixed(1)} ${(pt.x + 6).toFixed(1)},${pt.y.toFixed(1)} ${pt.x.toFixed(1)},${(pt.y + 7).toFixed(1)} ${(pt.x - 6).toFixed(1)},${pt.y.toFixed(1)}" fill="var(--status-alert)" stroke="#FFFFFF" stroke-width="1" />`).join("");
  const labelStep = Math.max(1, Math.ceil(coords.length / 7)), tickPts = [];
  let lastTickX = -Infinity;
  coords.forEach((pt, idx) => {
    const isLast = idx === coords.length - 1;
    if (idx % labelStep === 0 || isLast) {
      if (isLast && tickPts.length > 0 && (pt.x - lastTickX) < 72) tickPts.pop();
      if (pt.x - lastTickX >= 72 || isLast || tickPts.length === 0) { tickPts.push(pt); lastTickX = pt.x; }
    }
  });
  const fmtTick = b => { const raw = b.label || b.date || ""; return raw.includes("–") ? raw.split("–")[0].trim() : raw.replace(/\s+20\d\d$/, ""); };
  let xLabelsHtml = tickPts.map(pt => `<text x="${pt.x.toFixed(1)}" y="${(pad.top + plotH + 18).toFixed(1)}" text-anchor="middle" fill="var(--text-muted)" font-size="10" font-family="'Geist Mono', monospace">${fmtTick(pt.bucket)}</text>`).join("");
  let pointsHtml = (!isSplitActive && coords.length <= 24) ? coords.map(pt => `<circle cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="3" fill="${metricColor}" stroke="var(--surface-card)" stroke-width="1.5" />`).join("") : "";

  svg.innerHTML = `<defs><linearGradient id="prog-area-grad" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${metricColor}" stop-opacity="0.2" /><stop offset="100%" stop-color="${metricColor}" stop-opacity="0.0" /></linearGradient></defs>${gridHtml}${cutoverHtml}${seriesPathsHtml}${diamondsHtml}${pointsHtml}${xLabelsHtml}<line id="prog-cursor-line" x1="0" y1="${pad.top}" x2="0" y2="${pad.top + plotH}" stroke="var(--text-muted)" stroke-dasharray="2 2" stroke-width="1" style="display: none;" />`;

  const cursorLine = document.getElementById("prog-cursor-line");
  svg.onmousemove = e => {
    const rect = svg.getBoundingClientRect(), mouseX = (e.clientX - rect.left) * (width / rect.width);
    let closest = coords[0], minD = Infinity;
    coords.forEach(pt => { const d = Math.abs(pt.x - mouseX); if (d < minD) { minD = d; closest = pt; } });
    if (cursorLine) { cursorLine.setAttribute("x1", closest.x.toFixed(1)); cursorLine.setAttribute("x2", closest.x.toFixed(1)); cursorLine.style.display = "block"; }
    if (tooltip && svg.parentElement) {
      const b = closest.bucket, cRect = svg.parentElement.getBoundingClientRect();
      const splitDetails = isSplitActive ? splitSeries.map(s => `<div style="display: flex; justify-content: space-between; gap: 8px; margin-top: 2px;"><span style="color: var(--text-muted);">${escapeHtml(s.name)}:</span><span style="font-weight: 600; color: ${s.color}; font-family: monospace;">${formatCompactNumber(s.getVal(b))}</span></div>`).join("") : "";
      tooltip.innerHTML = `<div style="font-weight: 700; font-size: 0.8125rem; border-bottom: 1px solid var(--card-border); padding-bottom: 3px; margin-bottom: 4px;">${escapeHtml(b.label || b.date)}</div><div style="display: flex; justify-content: space-between; gap: 8px;"><span style="color: var(--text-muted);">${escapeHtml(metricName)}:</span><strong style="color: ${metricColor}; font-family: monospace;">${formatVal(closest.val)}</strong></div>${splitDetails}<div style="display: flex; justify-content: space-between; gap: 8px; margin-top: 2px;"><span style="color: var(--text-muted);">Cache Hit:</span><span class="highlight-green">${(b.cache_hit_pct || 0).toFixed(1)}%</span></div><div style="display: flex; justify-content: space-between; gap: 8px; margin-top: 2px;"><span style="color: var(--text-muted);">Subagents:</span><span>${(b.subagent_share_pct || 0).toFixed(1)}%</span></div><div style="display: flex; justify-content: space-between; gap: 8px; margin-top: 2px;"><span style="color: var(--text-muted);">Latency p50:</span><span>${Math.round(b.latency_p50_ms || b.p50_latency_ms || 0)} ms</span></div>`;
      tooltip.style.display = "block"; tooltip.style.left = `${Math.min(cRect.width - 180, Math.max(10, e.clientX - cRect.left + 12))}px`; tooltip.style.top = `${Math.max(10, e.clientY - cRect.top - 80)}px`;
    }
  };
  svg.onmouseleave = () => { if (cursorLine) cursorLine.style.display = "none"; if (tooltip) tooltip.style.display = "none"; };
}

function renderDiurnalRhythmSvg(horizonData) {
  const svg = document.getElementById("diurnal-rhythm-svg"), tooltip = document.getElementById("diurnal-rhythm-tooltip");
  if (!svg) return;
  const profile = (horizonData.diurnal_profiles && (horizonData.diurnal_profiles[activeHorizonKey] || horizonData.diurnal_profiles.lifetime)) || [];
  if (profile.length === 0) {
    svg.innerHTML = '<text x="230" y="120" text-anchor="middle" fill="var(--text-muted)" font-size="12">No diurnal profile available.</text>';
    return;
  }
  const width = 460, height = 240, pad = { top: 25, right: 20, bottom: 35, left: 56 };
  const plotW = width - pad.left - pad.right, plotH = height - pad.top - pad.bottom;
  const models = [
    { name: "Gemini 4 Carbon", key: "gemini_carbon", color: "var(--chart-2)" },
    { name: "Gemini 4 Orchestrator", key: "gemini_orchestrator", color: "var(--chart-4)" },
    { name: "Gemini 4 Hydrogen", key: "gemini_hydrogen", color: "var(--chart-5)" },
    { name: "Gemini 3.8 Flash", key: "gemini_flash", color: "var(--accent-mint)" },
    { name: "Gemini 3.1 Pro", key: "gemini_pro", color: "var(--camel-500)" },
    { name: "Gemini 4 Argon", key: "gemini_argon", color: "var(--accent-purple)" },
    { name: "Claude", key: "claude", color: "var(--status-alert)" }
  ];
  const getLat = (p, m) => Number((p.latency_by_model && (p.latency_by_model[m.name] || p.latency_by_model[m.key])) || (p.by_family_latency_ms && (p.by_family_latency_ms[m.name] || p.by_family_latency_ms[m.key])) || 0);

  let maxVal = 0, minHour = -1, minLat = Infinity, peakHour = -1, peakScore = -1;
  profile.forEach((p, hIdx) => {
    const hLat = Number(p.latency_p50_ms || p.latency_mean_ms || 0), hTok = Number(p.total_tokens || 0);
    if (hLat > 0 && hLat < minLat) { minLat = hLat; minHour = hIdx; }
    const sc = activeDiurnalMode === "latency" ? hLat : hTok;
    if (sc > peakScore && sc > 0) { peakScore = sc; peakHour = hIdx; }
    if (activeDiurnalMode === "latency") models.forEach(m => { const lat = getLat(p, m); if (lat > maxVal) maxVal = lat; });
    else if (hTok > maxVal) maxVal = hTok;
  });
  const fmtWin = h => h >= 0 ? `${String(h).padStart(2, "0")}:00–${String((h + 3) % 24).padStart(2, "0")}:00 UTC` : "12:00–17:00 UTC";
  setElText("diurnal-fastest-window", fmtWin(minHour));
  setElText("diurnal-peak-window", peakHour >= 0 ? fmtWin(peakHour) : "19:00–22:00 UTC");
  if (maxVal <= 0) maxVal = activeDiurnalMode === "latency" ? 500 : 1000;
  const yCeil = maxVal * 1.15;
  const getX = i => pad.left + (i / 23) * plotW;
  const getY = val => Math.max(pad.top, Math.min(pad.top + plotH, pad.top + plotH - (yCeil > 0 ? (val / yCeil) * plotH : 0)));

  let gridHtml = [0, 0.5, 1.0].map(t => {
    const yV = yCeil * t, yP = pad.top + plotH - (t * plotH);
    const label = activeDiurnalMode === "latency" ? (yV >= 10000 ? `${(yV / 1000).toFixed(1)}s` : `${Math.round(yV)} ms`) : formatCompactNumber(yV);
    return `<line x1="${pad.left}" y1="${yP.toFixed(1)}" x2="${pad.left + plotW}" y2="${yP.toFixed(1)}" stroke="var(--card-border)" stroke-dasharray="3 3" opacity="0.35" /><text x="${pad.left - 8}" y="${(yP + 4).toFixed(1)}" text-anchor="end" fill="var(--text-muted)" font-size="9" font-family="'Geist Mono', monospace">${label}</text>`;
  }).join("");

  let pathsHtml = "";
  if (activeDiurnalMode === "latency") {
    models.forEach(m => {
      const pts = [];
      profile.forEach((p, i) => {
        const lat = getLat(p, m);
        if (lat > 0) pts.push({ x: getX(i), y: getY(lat), lat });
      });
      if (pts.length > 1) {
        const pathStr = typeof getSplinePath === "function" ? getSplinePath(pts) : "";
        pathsHtml += `<path d="${pathStr}" fill="none" stroke="${m.color}" stroke-width="1.75" />`;
      } else if (pts.length === 1) {
        pathsHtml += `<circle cx="${pts[0].x.toFixed(1)}" cy="${pts[0].y.toFixed(1)}" r="3" fill="${m.color}" />`;
      }
    });
  } else {
    const barW = Math.max(8, (plotW / 24) * 0.7);
    pathsHtml = profile.map((p, i) => {
      const bx = getX(i) - barW / 2, bH = ((p.total_tokens || 0) / yCeil) * plotH, by = pad.top + plotH - bH;
      return `<rect x="${bx.toFixed(1)}" y="${by.toFixed(1)}" width="${barW.toFixed(1)}" height="${bH.toFixed(1)}" fill="var(--camel-500)" opacity="0.8" rx="2" />`;
    }).join("");
  }
  const xLabelsHtml = [0, 6, 12, 18, 23].map(h => `<text x="${getX(h).toFixed(1)}" y="${(pad.top + plotH + 16).toFixed(1)}" text-anchor="middle" fill="var(--text-muted)" font-size="9" font-family="'Geist Mono', monospace">${String(h).padStart(2, "0")}:00</text>`).join("");
  svg.innerHTML = `${gridHtml}${pathsHtml}${xLabelsHtml}<line id="diurnal-cursor-line" x1="0" y1="${pad.top}" x2="0" y2="${pad.top + plotH}" stroke="var(--text-muted)" stroke-dasharray="2 2" stroke-width="1" style="display: none;" />`;

  const cursorLine = document.getElementById("diurnal-cursor-line");
  svg.onmousemove = e => {
    const rect = svg.getBoundingClientRect(), mouseX = (e.clientX - rect.left) * (width / rect.width);
    const hourIdx = Math.max(0, Math.min(23, Math.round(((mouseX - pad.left) / plotW) * 23))), p = profile[hourIdx] || profile[0], ptX = getX(hourIdx);
    if (cursorLine) { cursorLine.setAttribute("x1", ptX.toFixed(1)); cursorLine.setAttribute("x2", ptX.toFixed(1)); cursorLine.style.display = "block"; }
    if (tooltip && svg.parentElement) {
      let content = `<div style="font-weight: 700; font-size: 0.8125rem; border-bottom: 1px solid var(--card-border); padding-bottom: 3px; margin-bottom: 4px;">${escapeHtml(p.hour_display)} UTC</div>`;
      if (activeDiurnalMode === "latency") {
        models.forEach(m => {
          const lat = getLat(p, m);
          if (lat > 0) content += `<div style="display: flex; justify-content: space-between; gap: 8px; margin-top: 2px;"><span style="color: var(--text-muted);">${escapeHtml(m.name)}:</span><span style="font-weight: 600; color: ${m.color}; font-family: monospace;">${lat} ms</span></div>`;
        });
      } else {
        content += `<div style="display: flex; justify-content: space-between; gap: 8px;"><span style="color: var(--text-muted);">Token Volume:</span><strong style="color: var(--camel-500); font-family: monospace;">${formatNumber(p.total_tokens || 0)}</strong></div>`;
      }
      tooltip.innerHTML = content; tooltip.style.display = "block";
      const cRect = svg.parentElement.getBoundingClientRect();
      tooltip.style.left = `${Math.min(cRect.width - 180, Math.max(10, e.clientX - cRect.left + 12))}px`;
      tooltip.style.top = `${Math.max(10, e.clientY - cRect.top - 70)}px`;
    }
  };
  svg.onmouseleave = () => { if (cursorLine) cursorLine.style.display = "none"; if (tooltip) tooltip.style.display = "none"; };
}

function populateSessionFilterDropdowns(workspaces, convos) {
  workspaces = workspaces || (globalDashboardData && globalDashboardData.workspaces) || [];
  convos = convos || (globalDashboardData && globalDashboardData.conversations) || [];
  const wsSelect = document.getElementById("workspace-filter");
  if (wsSelect) {
    const prevWs = wsSelect.value;
    wsSelect.innerHTML = '<option value="all">All Workspaces</option>';
    workspaces.forEach(ws => {
      const opt = document.createElement("option");
      opt.value = ws.workspace;
      opt.textContent = `${ws.workspace} (${ws.conversation_count} sessions)`;
      wsSelect.appendChild(opt);
    });
    if (prevWs && Array.from(wsSelect.options).some(o => o.value === prevWs)) wsSelect.value = prevWs;
  }
  const convoSelect = document.getElementById("convo-filter");
  if (convoSelect) {
    const prevConvo = convoSelect.value;
    convoSelect.innerHTML = '<option value="all">All Conversations</option>';
    convos.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c.convo_id;
      opt.textContent = `${c.title} (${c.turn_count} turns)`;
      convoSelect.appendChild(opt);
    });
    if (prevConvo && Array.from(convoSelect.options).some(o => o.value === prevConvo)) convoSelect.value = prevConvo;
  }
}
if (typeof window !== "undefined") window.populateSessionFilterDropdowns = populateSessionFilterDropdowns;

let lastObservedTokens = 0;
function updateTokenTicker(ticker) {
  if (!ticker) return;
  if (typeof updateExecutiveHeroTicker === "function") updateExecutiveHeroTicker(ticker);
  const beaconDot = document.getElementById("ticker-beacon-dot");
  const rateContainer = document.getElementById("ticker-rate-container"), rateEl = document.getElementById("ticker-rate");
  const deltaPill = document.getElementById("ticker-delta-pill"), deltaVal = document.getElementById("ticker-delta-val");
  const engineModel = document.getElementById("ticker-engine-model"), engineCache = document.getElementById("ticker-engine-cache");
  const tokens5hEl = document.getElementById("ticker-5h-tokens"), headroom5hEl = document.getElementById("ticker-5h-headroom");
  const isStreaming = Boolean(ticker.is_streaming || (ticker.burn_rate_tok_per_min || 0) > 0);

  if (beaconDot) {
    beaconDot.className = isStreaming ? "ticker-beacon-dot streaming" : "ticker-beacon-dot idle";
    beaconDot.title = isStreaming ? "Telemetry Stream: Active Generation" : "Telemetry Stream: Idle / In-Quota";
  }
  if (rateContainer && rateEl) {
    const rate = ticker.burn_rate_tok_per_min || 0;
    rateContainer.style.display = isStreaming && rate > 0 ? "inline-flex" : "none";
    if (isStreaming && rate > 0) rateEl.textContent = `${formatCompactNumber(rate)} tok/min`;
  }
  if (deltaPill && deltaVal) {
    const curTok = ticker.last_turn_tokens || 0;
    deltaPill.style.display = curTok > 0 ? "inline-flex" : "none";
    if (curTok > 0) {
      if (isStreaming) {
        deltaPill.className = "ticker-delta-pill"; deltaVal.textContent = `▲ +${formatCompactNumber(curTok)}`;
        if (lastObservedTokens > 0 && curTok !== lastObservedTokens) { deltaPill.classList.remove("flash"); void deltaPill.offsetWidth; deltaPill.classList.add("flash"); }
      } else { deltaPill.className = "ticker-delta-pill idle"; deltaVal.textContent = `Last: +${formatCompactNumber(curTok)}`; }
    }
    lastObservedTokens = curTok;
  }
  if (engineModel) { const mName = ticker.last_turn_model || "Gemini 3.8 Flash"; engineModel.textContent = mName; engineModel.title = `Active Model: ${mName} | Branch: ${ticker.active_branch || "main"}`; }
  if (engineCache) {
    let cachePct = ticker.last_turn_cache_pct;
    if (cachePct === undefined) { const prompt = ticker.last_turn_prompt || 0, cached = ticker.last_turn_cached || 0; cachePct = prompt > 0 ? (cached / prompt) * 100 : 0.0; }
    engineCache.textContent = `${Number(cachePct).toFixed(1)}% Cache`;
  }
  if (tokens5hEl) {
    let t5h = ticker.gemini_5h_tokens;
    if (t5h === undefined && globalDashboardData && globalDashboardData.quotas) t5h = (globalDashboardData.quotas.rolling_5h || {}).total_processed_tokens || 0;
    tokens5hEl.textContent = `${formatCompactNumber(t5h || 0)} tok`;
  }
  if (headroom5hEl) {
    let remPct = ticker.gemini_5h_remaining_pct;
    if (remPct === undefined && globalDashboardData && globalDashboardData.quotas && globalDashboardData.quotas.providers) remPct = ((globalDashboardData.quotas.providers.gemini || {}).five_hour || {}).remaining_pct;
    const remNum = remPct !== undefined ? Number(remPct) : 100;
    headroom5hEl.textContent = `${remNum.toFixed(0)}% free`;
    headroom5hEl.className = remNum < 20 ? "ticker-5h-rem critical" : (remNum < 40 ? "ticker-5h-rem warning" : "ticker-5h-rem");
  }
}

let liveTickTimer = null, autoRefreshTimer = null, autoRefreshEnabled = true, refreshIntervalMs = 3000;
let isAutoRefreshInitialized = false;
function initAutoRefresh() {
  if (isAutoRefreshInitialized) return;
  isAutoRefreshInitialized = true;
  if (liveTickTimer) clearInterval(liveTickTimer);
  const btnRefresh = document.getElementById("btn-auto-refresh");
  if (btnRefresh) {
    const savedPref = localStorage.getItem("antigravity_auto_refresh");
    if (savedPref !== null) autoRefreshEnabled = savedPref === "true";
    updateAutoRefreshButton();
    if (typeof btnRefresh.addEventListener === "function") {
      btnRefresh.addEventListener("click", () => {
        autoRefreshEnabled = !autoRefreshEnabled;
        try { localStorage.setItem("antigravity_auto_refresh", String(autoRefreshEnabled)); } catch(e) {}
        updateAutoRefreshButton();
        if (autoRefreshEnabled) checkAndReloadTelemetry();
      });
    }
  }
  let lastTokenVolume = 0, lastChangeTimestamp = Date.now();
  function startAdaptiveTimer() {
    if (autoRefreshTimer) clearInterval(autoRefreshTimer);
    if (!autoRefreshEnabled || (typeof document !== "undefined" && document.hidden)) return;
    autoRefreshTimer = setInterval(() => {
      if (autoRefreshEnabled && (typeof document !== "undefined" && !document.hidden)) checkAndReloadTelemetry();
    }, refreshIntervalMs);
  }
  if (typeof window !== "undefined") {
    window.__adjustTelemetryCadence = function(latestTokens) {
      const now = Date.now();
      if (latestTokens !== lastTokenVolume) {
        lastTokenVolume = latestTokens; lastChangeTimestamp = now;
        if (refreshIntervalMs !== 3000) { refreshIntervalMs = 3000; updateAutoRefreshButton(); startAdaptiveTimer(); }
      } else {
        const idleSec = (now - lastChangeTimestamp) / 1000;
        let newInterval = idleSec > 600 ? 30000 : (idleSec > 120 ? 10000 : 3000);
        if (newInterval !== refreshIntervalMs) { refreshIntervalMs = newInterval; updateAutoRefreshButton(); startAdaptiveTimer(); }
      }
    };
  }
  startAdaptiveTimer();
  if (typeof document !== "undefined" && typeof document.addEventListener === "function") {
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) { if (autoRefreshTimer) { clearInterval(autoRefreshTimer); autoRefreshTimer = null; } }
      else if (autoRefreshEnabled) { checkAndReloadTelemetry(); startAdaptiveTimer(); }
    });
  }
}

function updateAutoRefreshButton() {
  const btn = document.getElementById("btn-auto-refresh");
  if (!btn) return;
  if (autoRefreshEnabled) {
    btn.innerHTML = `<span style="display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--status-normal, #10B981); margin-right: 6px;"></span>Live Sync: ON (${Math.round(refreshIntervalMs / 1000)}s)`;
    btn.style.color = "var(--status-normal, #10B981)";
    btn.style.borderColor = "var(--status-normal, #10B981)";
  } else {
    btn.innerHTML = `<span style="display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: var(--text-muted); margin-right: 6px;"></span>Sync: PAUSED`;
    btn.style.color = "var(--text-muted)";
    btn.style.borderColor = "var(--border-subtle, var(--card-border))";
  }
}

let currentTelemetrySha1 = (typeof window !== "undefined" && window.__TELEMETRY_META__ && window.__TELEMETRY_META__.payload_sha1) || null;
function checkAndReloadTelemetry() {
  if (globalDashboardData && globalDashboardData.summary && globalDashboardData.summary.is_demo) return;
  if (typeof window !== "undefined" && window.location) {
    const p = window.location.pathname || "", s = window.location.search || "";
    if (p.includes("demo") || s.includes("demo=1") || s.includes("demo=true")) return;
  }
  const isFile = (typeof window !== "undefined" && window.location && window.location.protocol === "file:");
  const bust = isFile ? "" : `?t=${Date.now()}`;
  const loadData = () => {
    const s = document.createElement("script"); s.src = `data.js${bust}`;
    s.onload = () => { if (window.__TELEMETRY_DATA__) { globalDashboardData = window.__TELEMETRY_DATA__; render(globalDashboardData); } s.remove(); };
    s.onerror = () => s.remove(); document.head.appendChild(s);
  };
  const metaScript = document.createElement("script"); metaScript.src = `meta.js${bust}`;
  metaScript.onload = () => {
    metaScript.remove();
    const latestMeta = window.__TELEMETRY_META__, newSha1 = latestMeta && latestMeta.payload_sha1;
    if (latestMeta && latestMeta.ticker) {
      updateTokenTicker(latestMeta.ticker);
      if (window.__adjustTelemetryCadence) window.__adjustTelemetryCadence(latestMeta.ticker.total_tokens || 0);
    }
    if (newSha1 && currentTelemetrySha1 && newSha1 === currentTelemetrySha1 && globalDashboardData) return;
    currentTelemetrySha1 = newSha1; loadData();
  };
  metaScript.onerror = () => { metaScript.remove(); loadData(); };
  document.head.appendChild(metaScript);
}
