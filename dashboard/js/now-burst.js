// ==========================================
// Dashboard: Burst Sessions, Standup Digest & Timeline Helpers
// Extracted from js/now.js (<800 lines rule).
// ==========================================

function generateStandupMarkdown(data) {
  if (!data) return "";
  const s = data.summary || {};
  const quotas = data.quotas || {};
  const prov = quotas.providers || {};
  const gem = prov.gemini || {};
  const cg = prov.claude_gpt || {};
  const gem5h = gem.five_hour || {};
  const gemWk = gem.weekly || {};
  const cg5h = cg.five_hour || {};
  const cgWk = cg.weekly || {};
  const runway = gem.runway || {};

  const planName = s.subscription_tier_name || s.subscription_tier || "Google AI Ultra (20 TB - 5x AI Usage)";
  const planTier = s.subscription_tier || "ultra_5x";
  const subGbp = (s.monthly_subscription_price_gbp || 79.99).toFixed(2);
  const imputedGbp = (s.total_imputed_value_gbp || 0).toFixed(2);
  const imputedUsd = (s.total_imputed_value_usd || 0).toFixed(2);

  const totalToks = (s.total_processed_tokens || 0).toLocaleString();
  const inputToks = (s.total_input_tokens || 0).toLocaleString();
  const outputToks = (s.total_output_tokens || 0).toLocaleString();
  const cachedToks = (s.total_cached_tokens || 0).toLocaleString();
  const cachePct = (s.cache_hit_ratio_pct || 0).toFixed(1);

  const creditsBurned = (s.total_ai_credits_burned || 0).toLocaleString();
  const burnGbp = (s.total_credit_burn_gbp || 0).toFixed(2);
  const burnUsd = (s.total_credit_burn_usd || 0).toFixed(2);
  const creditsRem = (quotas.credit_bank?.remaining_credits || 1360).toLocaleString();

  const resetDisp = typeof formatLocalizedResetTime === "function"
    ? formatLocalizedResetTime(gemWk.weekly_reset_utc, gemWk.reset_display)
    : (gemWk.reset_display || "Weekly Reset");
  const bvi = (runway.burn_velocity_index || 0).toFixed(2);
  const subStatus = s.subscription_status || "SAFE_IN_QUOTA";

  const gem5hUsed = (gem5h.used_pct || 0).toFixed(1);
  const gem5hRem = Math.max(0, 100 - (gem5h.used_pct || 0)).toFixed(1);
  const gemWkUsed = (gemWk.used_pct || 0).toFixed(1);
  const gemWkRem = Math.max(0, 100 - (gemWk.used_pct || 0)).toFixed(1);

  const cg5hUsed = (cg5h.used_pct || 0).toFixed(1);
  const cg5hRem = Math.max(0, 100 - (cg5h.used_pct || 0)).toFixed(1);
  const cgWkUsed = (cgWk.used_pct || 0).toFixed(1);
  const cgWkRem = Math.max(0, 100 - (cgWk.used_pct || 0)).toFixed(1);

  const byModel = s.by_model || {};
  const sortedModels = Object.entries(byModel).sort((a, b) => (b[1].total_processed_tokens || 0) - (a[1].total_processed_tokens || 0));
  const topModelsLines = sortedModels.slice(0, 3).map(([mid, mdata]) => {
    const mname = mdata.name || mid;
    const mtoks = (mdata.total_processed_tokens || 0).toLocaleString();
    const mturns = mdata.turn_count || 0;
    const mcost = (mdata.estimated_cost_gbp || 0).toFixed(2);
    return `  - **${mname}**: ${mturns} turns, ${mtoks} tokens (£${mcost})`;
  });

  const modelsBlock = topModelsLines.length > 0 ? topModelsLines.join("\n") : "  - No model activity recorded.";

  return [
    "### Antigravity Telemetry Standup Digest",
    `**Plan**: ${planName} (\`${planTier}\`) | **Weekly Cycle Reset**: ${resetDisp} | **Status**: \`${subStatus}\``,
    "",
    "#### 1. Token Throughput & Cache Efficiency",
    `- **Total Processed**: ${totalToks} tokens`,
    `- **Input vs Output**: ${inputToks} input / ${outputToks} output`,
    `- **Context Cache Hit**: ${cachedToks} cached (${cachePct}% hit ratio)`,
    "",
    "#### 2. Economic Value & AI Credit Ledger",
    `- **Imputed Avoided API Cost**: £${imputedGbp} ($${imputedUsd})`,
    `- **Monthly Plan Cost**: £${subGbp}/mo`,
    `- **AI Credit Deductions**: ${creditsBurned} credits (£${burnGbp} / $${burnUsd}) | ${creditsRem} credits remaining in bank`,
    "",
    "#### 3. Quota Runway & Headroom",
    `- **Gemini 5-Hour Limit**: ${gem5hUsed}% used (${gem5hRem}% remaining)`,
    `- **Gemini Weekly Runway**: ${gemWkUsed}% used (${gemWkRem}% remaining) | BVI: ${bvi}x`,
    `- **Claude/GPT 5-Hour Limit**: ${cg5hUsed}% used (${cg5hRem}% remaining)`,
    `- **Claude/GPT Weekly**: ${cgWkUsed}% used (${cgWkRem}% remaining)`,
    "",
    "#### 4. Top Active Models",
    modelsBlock,
  ].join("\n") + "\n";
}

function renderActiveBurstSessions(sessions) {
  const container = document.getElementById("burst-sessions-drawer");
  if (!container) return;
  if (!sessions || sessions.length === 0) {
    container.innerHTML = "";
    return;
  }

  const topSessions = sessions.slice(0, 5);
  const rowsHtml = topSessions.map((s, idx) => {
    const cid = typeof escapeHtml === "function" ? escapeHtml(s.convo_id || "") : (s.convo_id || "");
    const turns = s.turn_count || 0;
    const tok = typeof formatNumber === "function" ? formatNumber(s.total_processed_tokens || 0) : (s.total_processed_tokens || 0);
    const model = typeof escapeHtml === "function" ? escapeHtml(s.primary_model_name || "Flash") : (s.primary_model_name || "Flash");
    const title = typeof escapeHtml === "function" ? escapeHtml(s.title || "Untitled Session") : (s.title || "Untitled Session");
    const ws = typeof escapeHtml === "function" ? escapeHtml(s.workspace_name || "") : (s.workspace_name || "");
    const isSub = Boolean(s.is_subagent);
    const agName = s.agent_name || "default";
    let roleBadge = '';
    if (isSub) {
      roleBadge = '<span class="badge-agent badge-subagent-pill" style="font-size: 0.625rem; padding: 1px 5px;">Subagent</span>';
    } else if (agName === "auditor") {
      roleBadge = '<span class="badge-agent badge-agent-auditor" style="font-size: 0.625rem; padding: 1px 5px;">Auditor</span>';
    } else if (agName === "implementer") {
      roleBadge = '<span class="badge-agent badge-agent-implementer" style="font-size: 0.625rem; padding: 1px 5px;">Implementer</span>';
    }

    return `
      <div class="burst-session-row">
        <div style="display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1;">
          <div class="burst-session-title" data-action="inspect-session" data-convo-id="${cid}" title="${title} (${ws})" style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <span>${idx + 1}. ${title}</span>
            ${roleBadge}
          </div>
          <div style="font-size: 0.6875rem; color: var(--text-muted); display: flex; gap: 6px; align-items: center;">
            <span>${turns} turns</span>
            <span>•</span>
            <span style="color: var(--camel-500);">${model}</span>
          </div>
        </div>
        <div style="text-align: right; margin-left: 8px;">
          <div style="font-family: monospace; font-weight: 600; font-size: 0.75rem; color: var(--text-main);">${tok}</div>
          <div style="font-size: 0.6875rem; color: var(--camel-500); cursor: pointer;" data-action="inspect-session" data-convo-id="${cid}">Inspect →</div>
        </div>
      </div>
    `;
  }).join("");

  container.innerHTML = `
    <div class="active-burst-sessions">
      <div class="burst-sessions-toggle" data-action="toggle-burst-sessions">
        <span style="display: flex; align-items: center; gap: 6px;">
          <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--camel-500);"></span>
          <span>Top Burst Sessions in 5h</span>
          <span class="badge camel" style="font-size: 0.65rem; padding: 1px 6px;">${sessions.length} Active</span>
        </span>
        <span id="burst-sessions-toggle-icon" style="font-size: 0.75rem; color: var(--text-muted); transition: transform 0.2s ease;">▶</span>
      </div>
      <div id="burst-sessions-list-container" class="burst-sessions-list" style="display: none;">
        ${rowsHtml}
      </div>
    </div>
  `;
}

function toggleBurstSessionsList() {
  const list = document.getElementById("burst-sessions-list-container");
  const icon = document.getElementById("burst-sessions-toggle-icon");
  if (!list) return;
  if (list.style.display === "flex") {
    list.style.display = "none";
    if (icon) icon.textContent = "▶";
  } else {
    list.style.display = "flex";
    if (icon) icon.textContent = "▼";
  }
}

function renderRecoveryTimeline() {
  // Obsolete 5-Hour Recovery Timeline card removed in favor of Runway Burst Governor hero deck.
}

function updateTimelineTick() {
  // Timeline tick retired.
}

let burstCountdownTimer = null;
function startBurstCountdown(initialSeconds) {
  if (burstCountdownTimer) clearInterval(burstCountdownTimer);
  let secs = initialSeconds;
  const target = document.getElementById("runway-burst-right");
  if (!target) return;
  const fmt = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}m ${sec < 10 ? '0' : ''}${sec}s left`;
  };
  target.innerHTML = `<span style="font-weight: 700; font-family: monospace; color: var(--accent-purple);">${fmt(secs)}</span>`;
  burstCountdownTimer = setInterval(() => {
    secs--;
    if (secs <= 0) {
      clearInterval(burstCountdownTimer);
      burstCountdownTimer = null;
      const footer = document.getElementById("runway-burst-footer");
      const left = document.getElementById("runway-burst-left");
      if (footer) {
        footer.style.border = "1px solid var(--card-border)";
        footer.style.background = "var(--card-bg)";
      }
      if (left) {
        left.innerHTML = `<span style="color: var(--text-muted);">5h burst allowance:</span><span style="display: inline-flex; align-items: center; gap: 4px; font-weight: 600; color: var(--accent-green);"><span style="width: 6px; height: 6px; border-radius: 50%; background: var(--status-normal);"></span> Normal</span>`;
      }
      if (target) target.textContent = "No cooldown";
    } else {
      target.innerHTML = `<span style="font-weight: 700; font-family: monospace; color: var(--accent-purple);">${fmt(secs)}</span>`;
    }
  }, 1000);
}

// ==========================================
// Milestone 88: Executive Cockpit & Mac Menu Bar Parity
// ==========================================

function renderExecutiveHero(data) {
  if (!data) data = (typeof globalDashboardData !== "undefined" && globalDashboardData) || {};
  const summary = data.summary || {};
  const quotas = data.quotas || {};
  const providers = quotas.providers || {};
  const geminiProv = providers.gemini || {};
  const claudeProv = providers.claude_gpt || {};
  const gWk = geminiProv.weekly || {};
  const g5h = geminiProv.five_hour || {};
  const cWk = claudeProv.weekly || {};
  const r5h = quotas.rolling_5h || {};
  const weekly = quotas.weekly_cycle || quotas.rolling_1w || {};
  const curSess = data.current_session || (typeof window !== "undefined" && window.__lastCurrentSession) || null;

  // Plan name
  const planEl = document.getElementById("exec-plan-name");
  if (planEl) {
    const pName = summary.tier_display || summary.plan_name
      || (summary.temporal_provenance && summary.temporal_provenance.active_plan && summary.temporal_provenance.active_plan.name)
      || summary.subscription_name
      || (summary.tier === "ultra_5x" ? "Google AI Ultra (5x)" : (summary.tier === "pro" ? "Google One AI Pro" : "Google AI Ultra (5x)"));
    planEl.textContent = pName;
  }

  // Quota status badge
  const weeklyRem = gWk.remaining_pct !== undefined ? gWk.remaining_pct : 100;
  const h5Rem = g5h.remaining_pct !== undefined ? g5h.remaining_pct : (r5h.remaining_pct !== undefined ? r5h.remaining_pct : 100);
  const curSev = curSess ? curSess.severity : "safe";
  const subStatus = summary.subscription_status || "";

  let overallStatus = "safe";
  if (curSev === "critical" || subStatus === "WEEKLY_EXHAUSTED" || weeklyRem <= 10 || h5Rem <= 10) {
    overallStatus = "critical";
  } else if (curSev === "warning" || subStatus === "BURNING_AI_CREDITS" || subStatus === "RECOVERED_COOLDOWN" || weeklyRem <= 25 || h5Rem <= 25) {
    overallStatus = "warning";
  }

  const statusBadge = document.getElementById("exec-status-badge");
  const statusText = document.getElementById("exec-status-text");
  if (statusBadge) statusBadge.className = `exec-status-badge ${overallStatus}`;
  if (statusText) statusText.textContent = overallStatus === "critical" ? "CRITICAL" : (overallStatus === "warning" ? "CAUTION" : "SAFE");

  // Panel 1: Weekly Quota Runway
  const runway = geminiProv.runway || quotas.runway || {}, sKey = runway.status_key || "green";
  const isWkCritical = sKey === "red" || weeklyRem < 20 || subStatus === "WEEKLY_EXHAUSTED";
  const isWkWarning = !isWkCritical && (sKey === "amber" || weeklyRem < 40 || (runway.bvi && runway.bvi > 1.3));
  const wkHealthColor = isWkCritical ? "var(--status-error, #EF4444)" : (isWkWarning ? "var(--status-warning, #F59E0B)" : "");
  const execWkPct = document.getElementById("exec-weekly-pct");
  if (execWkPct) { execWkPct.textContent = `${weeklyRem.toFixed(1)}%`; execWkPct.style.color = wkHealthColor; }
  const execWkBar = document.getElementById("exec-weekly-bar");
  if (execWkBar) {
    const wPct = Math.min(100, Math.max(0, weeklyRem));
    execWkBar.style.width = `${wPct}%`; execWkBar.style.background = wkHealthColor;
    if (execWkBar.parentElement) execWkBar.parentElement.setAttribute("aria-valuenow", Math.round(wPct));
  }
  const execWkCountdown = document.getElementById("exec-weekly-countdown");
  if (execWkCountdown) {
    const rawReset = gWk.weekly_reset_utc || weekly.weekly_reset_utc || gWk.cycle_end_utc || weekly.cycle_end_utc;
    const locReset = typeof formatLocalizedResetTime === "function" ? formatLocalizedResetTime(rawReset, weekly.reset_display || gWk.reset_display) : (weekly.reset_display || gWk.reset_display || "Weekly Reset");
    execWkCountdown.textContent = `Resets ${locReset} • ${weekly.human_remaining || gWk.human_remaining || "4d 19h remaining"}`;
  }
  const execWkVerdict = document.getElementById("exec-weekly-verdict");
  if (execWkVerdict) {
    execWkVerdict.textContent = runway.status_sub || runway.status_text || "+19.5% pacing buffer (Sustainable)";
    execWkVerdict.className = `exec-detail-text ${isWkCritical ? 'highlight-red' : (isWkWarning ? 'highlight-amber' : 'highlight-green')}`;
  }

  // Panel 2: 5-Hour Limit
  const is5hCritical = h5Rem < 15 || (subStatus === "BURNING_AI_CREDITS" && h5Rem <= 0);
  const is5hWarning = !is5hCritical && (h5Rem <= 35 || subStatus === "RECOVERED_COOLDOWN");
  const h5HealthColor = is5hCritical ? "var(--status-error, #EF4444)" : (is5hWarning ? "var(--status-warning, #F59E0B)" : "");
  const exec5hPct = document.getElementById("exec-5h-pct");
  if (exec5hPct) { exec5hPct.textContent = `${h5Rem.toFixed(1)}%`; exec5hPct.style.color = h5HealthColor; }
  const exec5hBar = document.getElementById("exec-5h-bar");
  if (exec5hBar) {
    const bPct = Math.min(100, Math.max(0, h5Rem));
    exec5hBar.style.width = `${bPct}%`; exec5hBar.style.background = h5HealthColor;
    if (exec5hBar.parentElement) exec5hBar.parentElement.setAttribute("aria-valuenow", Math.round(bPct));
  }
  const exec5hTokens = document.getElementById("exec-5h-tokens");
  if (exec5hTokens) exec5hTokens.textContent = `${formatCompactNumber(r5h.total_processed_tokens || 0)} tok used in 5h window (${r5h.turn_count || 0} turns)`;
  const exec5hForecast = document.getElementById("exec-5h-forecast");
  if (exec5hForecast) {
    const sched = (g5h && g5h.recovery_schedule) || r5h.recovery_schedule || [];
    if (g5h && g5h.message) {
      exec5hForecast.textContent = g5h.message;
    } else if (sched.length > 0) {
      exec5hForecast.textContent = `Next recovery in ${sched[0].minutes_remaining}m (+${formatCompactNumber(sched[0].tokens_to_recover)} tok)`;
    } else if (h5Rem >= 99) {
      exec5hForecast.textContent = "100% Headroom • Fully refreshed";
    } else {
      exec5hForecast.textContent = `${h5Rem.toFixed(0)}% Headroom • Normal burn`;
    }
  }

  // Panel 3: Claude & GPT Track
  const cRem = cWk.remaining_pct !== undefined ? Number(cWk.remaining_pct) : 100;
  const c5h = claudeProv.five_hour || {}, c5hRem = c5h.remaining_pct !== undefined ? Number(c5h.remaining_pct) : 100;
  const cColor = cRem <= 15 ? "var(--status-error, #EF4444)" : (cRem <= 35 ? "var(--status-warning, #F59E0B)" : "");
  const cPctEl = document.getElementById("exec-claude-pct"), cBarEl = document.getElementById("exec-claude-bar"), cSubEl = document.getElementById("exec-claude-5h-sub"), claudeEl = document.getElementById("exec-claude-status");
  if (cPctEl) { cPctEl.textContent = `${cRem.toFixed(1)}%`; cPctEl.style.color = cColor; }
  if (cBarEl) { const cp = Math.min(100, Math.max(0, cRem)); cBarEl.style.width = `${cp}%`; cBarEl.style.background = cColor; if (cBarEl.parentElement) cBarEl.parentElement.setAttribute("aria-valuenow", Math.round(cp)); }
  if (claudeEl) claudeEl.textContent = `Claude & GPT Track: ${cRem}% remaining`;
  if (cSubEl) cSubEl.textContent = `5h burst: ${c5hRem.toFixed(0)}% free • Hard stop`;

  // Panel 4: Credit Bank & Active Context
  const creditEl = document.getElementById("exec-credit-balance"), cBar = document.getElementById("exec-credits-bar"), cPoolSub = document.getElementById("exec-credits-pool-sub");
  if (creditEl) {
    if (summary.credit_bank_remaining_gbp !== undefined && typeof formatCurrency === "function") creditEl.textContent = formatCurrency(summary.credit_bank_remaining_usd, summary.credit_bank_remaining_gbp, 2);
    else if (summary.credit_balance) creditEl.textContent = String(summary.credit_balance);
    else creditEl.textContent = "£0.00";
  }
  const cPool = summary.credit_bank_total || 7500, cLeft = summary.credits_remaining !== undefined ? summary.credits_remaining : Math.max(0, cPool - (summary.total_ai_credits_burned || 0));
  if (cBar) { const crPct = Math.min(100, Math.max(0, (cLeft / Math.max(1, cPool)) * 100)); cBar.style.width = `${crPct}%`; if (cBar.parentElement) cBar.parentElement.setAttribute("aria-valuenow", Math.round(crPct)); }
  if (cPoolSub) cPoolSub.textContent = `${formatNumber(cLeft)} / ${formatNumber(cPool)} credits remaining`;

  const contextEl = document.getElementById("exec-active-context");
  if (contextEl) {
    const ws = (curSess && (curSess.workspace || curSess.workspace_name)) || "Antigravity Workspace";
    const br = (curSess && (curSess.branch || curSess.git_branch)) || "main";
    contextEl.textContent = `${ws} (${br})`;
  }

  if (data.live_ticker) updateExecutiveHeroTicker(data.live_ticker);
  renderNowActiveSwarms(data);
}

function updateExecutiveHeroTicker(ticker) {
  if (!ticker) return;
  const isStreaming = Boolean(ticker.is_streaming || (ticker.burn_rate_tok_per_min || 0) > 0);
  const beacon = document.getElementById("exec-beacon-dot");
  if (beacon) beacon.className = "exec-velocity-beacon " + (isStreaming ? "streaming" : "idle");

  const burnRate = ticker.burn_rate_tok_per_min || 0;
  const burnEl = document.getElementById("exec-burn-rate");
  if (burnEl) {
    burnEl.textContent = burnRate > 0 ? `${formatCompactNumber(burnRate)}/m` : "0/m";
  }

  const deltaEl = document.getElementById("exec-delta-val");
  if (deltaEl) deltaEl.textContent = `▲ +${formatCompactNumber(ticker.last_turn_tokens || 0)}`;

  const modelEl = document.getElementById("exec-active-model");
  if (modelEl) modelEl.textContent = ticker.last_turn_model || "Gemini 3.8 Flash (High)";

  const cacheEl = document.getElementById("exec-active-cache");
  if (cacheEl) {
    let cachePct = ticker.last_turn_cache_pct;
    if (cachePct === undefined) {
      const prompt = ticker.last_turn_prompt || 0;
      const cached = ticker.last_turn_cached || 0;
      cachePct = prompt > 0 ? (cached / prompt) * 100 : 0.0;
    }
    cacheEl.textContent = `${Number(cachePct).toFixed(1)}% cache`;
  }

  const headroomEl = document.getElementById("exec-burst-headroom");
  if (headroomEl) {
    let remPct = ticker.gemini_5h_remaining_pct;
    if (remPct === undefined && typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.quotas && globalDashboardData.quotas.providers) {
      remPct = ((globalDashboardData.quotas.providers.gemini || {}).five_hour || {}).remaining_pct;
    }
    const remNum = remPct !== undefined ? Number(remPct) : 100;
    const cap = (typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.quotas && globalDashboardData.quotas.rolling_5h && globalDashboardData.quotas.rolling_5h.burst_headroom) || 190000000;
    const freeTokens = Math.max(0, Math.round(cap * (remNum / 100)));
    headroomEl.textContent = `${formatCompactNumber(freeTokens)} tok • ${remNum.toFixed(0)}% free`;
  }
}

// ==========================================
// Milestone 94: Active Multi-Agent Swarms & Weakest-Link Parity (#view-now)
// ==========================================

function buildConvoMetaIndex(data) {
  const index = {};
  if (!data) return index;

  if (Array.isArray(data.conversations)) {
    data.conversations.forEach(c => {
      if (c && c.convo_id) {
        index[c.convo_id] = {
          turnCount: c.turn_count || (c.turns ? c.turns.length : 0),
          modelsUsed: c.models_used || [],
          primaryModelName: c.primary_model_name || c.model_name || "",
          primaryModelId: c.primary_model_id || c.model_id || (c.models_used && c.models_used[0]) || "",
          tokens: c.total_input_tokens ? (c.total_input_tokens + (c.total_output_tokens || 0)) : c.tokens,
          agentName: c.agent_name || "",
          subagentRole: c.subagent_role || ""
        };
      }
    });
  }

  const swarmsData = (data.swarms && data.swarms.swarms) || [];
  if (Array.isArray(swarmsData)) {
    swarmsData.forEach(sw => {
      (sw.nodes || []).forEach(n => {
        const id = n.id || n.convo_id;
        if (id) {
          const existing = index[id] || {};
          index[id] = {
            ...existing,
            turnCount: n.turn_count || existing.turnCount || 0,
            primaryModelName: n.model_name || existing.primaryModelName || "",
            primaryModelId: n.model_id || existing.primaryModelId || "",
            tokensTotal: n.tokens_total || existing.tokensTotal || 0,
            role: n.role || n.subagent_role || existing.role || ""
          };
        }
      });
    });
  }

  const recents = data.recent_sessions || data.sessions || [];
  if (Array.isArray(recents)) {
    recents.forEach(s => {
      if (s && s.convo_id) {
        const existing = index[s.convo_id] || {};
        index[s.convo_id] = {
          ...existing,
          turnCount: s.turn_count || existing.turnCount || 0,
          primaryModelName: s.primary_model_name || existing.primaryModelName || "",
          primaryModelId: s.primary_model_id || existing.primaryModelId || "",
        };
      }
    });
  }

  return index;
}

function resolveModelBadge(node = {}, meta = {}) {
  const modelId = String(meta.primaryModelId || (meta.modelsUsed && meta.modelsUsed[0]) || node.model_id || "");
  const modelName = String(meta.primaryModelName || node.model_name || "");
  const role = String(node.subagent_role || meta.subagentRole || meta.role || "");

  if (modelId === "1667" || modelName.includes("Orchestrator (Carbon)") || modelName.includes("Orch Carbon")) return { name: "Orch Carbon", type: "orchestrator" };
  if (modelId === "1681" || modelName.includes("Orchestrator (Argon)") || modelName.includes("Orch Argon")) return { name: "Orch Argon", type: "orchestrator" };
  if (modelId === "1669" || modelName.includes("Orchestrator Executor") || modelName.includes("Orch Exec")) return { name: "Orch Exec", type: "orchestrator" };
  if (modelId === "1427" || modelName.includes("Carbon (High)") || modelName.includes("Carbon High")) return { name: "Carbon High", type: "carbon" };
  if (modelId === "1437" || modelName.includes("Carbon (Medium)") || modelName.includes("Carbon Med")) return { name: "Carbon Med", type: "carbon" };
  if (modelId === "1438" || modelName.includes("Carbon (Low)") || modelName.includes("Carbon Low")) return { name: "Carbon Low", type: "carbon" };
  if (modelId === "1417" || modelName.includes("Argon (High)") || modelName.includes("Argon High")) return { name: "Argon High", type: "argon" };
  if (modelId === "1418" || modelName.includes("Argon (Medium)") || modelName.includes("Argon Med")) return { name: "Argon Med", type: "argon" };
  if (modelId === "1419" || modelName.includes("Argon (Low)") || modelName.includes("Argon Low")) return { name: "Argon Low", type: "argon" };
  if (modelId === "1528" || modelName.includes("Hydrogen (XHigh)") || modelName.includes("Hydrogen XHigh")) return { name: "Hydrogen XHigh", type: "hydrogen" };
  if (modelId === "1525" || modelName.includes("Hydrogen (High)") || modelName.includes("Hydrogen High")) return { name: "Hydrogen High", type: "hydrogen" };
  if (modelId === "1526" || modelName.includes("Hydrogen (Medium)") || modelName.includes("Hydrogen Med")) return { name: "Hydrogen Med", type: "hydrogen" };
  if (modelId === "1527" || modelName.includes("Hydrogen (Low)") || modelName.includes("Hydrogen Low")) return { name: "Hydrogen Low", type: "hydrogen" };
  if (modelId === "1322" || modelName.includes("Fast Agent") || modelName.includes("Flash Assistant")) return { name: "Flash 3.8", type: "flash" };
  if (modelId === "1318" || (modelName.includes("Flash") && modelName.includes("High"))) return { name: "Flash 3.8", type: "flash" };
  if (modelId === "1319" || (modelName.includes("Flash") && (modelName.includes("Med") || modelName.includes("Medium")))) return { name: "Flash Med", type: "flash" };
  if (modelId === "1320" || (modelName.includes("Flash") && modelName.includes("Low"))) return { name: "Flash Low", type: "flash" };
  if (modelName.includes("Orchestrator")) return { name: "Orchestrator", type: "orchestrator" };
  if (modelName.includes("Hydrogen")) return { name: "Hydrogen High", type: "hydrogen" };
  if (modelName.includes("Carbon")) return { name: "Carbon Med", type: "carbon" };
  if (modelName.includes("Argon")) return { name: "Argon Med", type: "argon" };
  if (modelName.includes("Flash")) return { name: "Flash 3.8", type: "flash" };
  if (modelName.includes("Pro")) return { name: "Gemini Pro", type: "pro" };

  if (node.is_subagent || role.includes("Researcher") || role.includes("Workstream") || role.includes("Worker")) {
    return { name: "Flash 3.8", type: "flash" };
  }
  return { name: "Argon Med", type: "argon" };
}

function computeSwarmWeakestLink(swarm) {
  const orch = swarm.orchestrator || {};
  const subs = swarm.subagents || [];
  const allNodes = [orch, ...subs].filter(Boolean);
  let weakestNode = allNodes.find(n => n.is_weakest_link === true);
  if (!weakestNode && allNodes.length > 0) {
    weakestNode = allNodes.reduce((max, n) => {
      const nTokens = n.tokens || 0, nThresh = n.threshold || n.compaction_threshold || 250000;
      const maxTokens = max.tokens || 0, maxThresh = max.threshold || max.compaction_threshold || 250000;
      return (nThresh > 0 ? (nTokens / nThresh) * 100 : 0) > (maxThresh > 0 ? (maxTokens / maxThresh) * 100 : 0) ? n : max;
    }, allNodes[0]);
  }

  const tokens = weakestNode ? (weakestNode.tokens || 0) : 0;
  const thresh = weakestNode ? (weakestNode.threshold || weakestNode.compaction_threshold || 250000) : 250000;
  const utilPct = thresh > 0 ? Math.round((tokens / thresh) * 100) : 0;

  let riskLevel = "HEALTHY";
  let riskClass = "healthy";

  const worstSev = swarm.worst_severity || (weakestNode && weakestNode.severity) || "safe";
  if (worstSev === "critical" || utilPct >= 90) {
    riskLevel = "CRITICAL";
    riskClass = "critical";
  } else if (worstSev === "warning" || utilPct >= 75) {
    riskLevel = "ELEVATED";
    riskClass = "elevated";
  } else {
    riskLevel = "HEALTHY";
    riskClass = "healthy";
  }

  return {
    weakestNode,
    utilPct,
    riskLevel,
    riskClass,
    label: `${riskLevel} (${utilPct}%)`
  };
}

function renderNowActiveSwarms(data) {
  if (!data) data = (typeof globalDashboardData !== "undefined" && globalDashboardData) || {};

  let container = document.getElementById("now-active-swarms");
  if (!container) {
    container = document.createElement("div");
    container.id = "now-active-swarms";
    container.className = "now-active-swarms-container";

    const slot = document.getElementById("now-swarms-slot");
    const execCard = document.getElementById("executive-hero-card");
    if (slot) {
      slot.appendChild(container);
    } else if (execCard && execCard.parentNode) {
      execCard.parentNode.insertBefore(container, execCard.nextSibling);
    } else {
      const viewNow = document.getElementById("view-now");
      if (viewNow) viewNow.appendChild(container);
    }
  }

  if (!container.__hasSwarmEvents) {
    container.__hasSwarmEvents = true;
    if (typeof container.addEventListener === "function") {
      container.addEventListener("click", function(e) {
        const toggleBtn = e.target.closest('[data-action="toggle-swarm-subagents"]');
        if (toggleBtn) {
          e.preventDefault();
          const list = toggleBtn.nextElementSibling;
          const chevron = toggleBtn.querySelector(".now-swarm-toggle-chevron");
          if (list) {
            const isCurrentlyHidden = list.style.display === "none";
            list.style.display = isCurrentlyHidden ? "flex" : "none";
            if (chevron) chevron.textContent = isCurrentlyHidden ? "▼" : "▶";
            toggleBtn.setAttribute("aria-expanded", isCurrentlyHidden ? "true" : "false");
          }
          return;
        }

        const swarmsLink = e.target.closest('[data-tab="swarms"]');
        if (swarmsLink) {
          e.preventDefault();
          e.stopPropagation();
          if (typeof switchTab === "function") switchTab("tab-swarms");
        }
      });

      container.addEventListener("keydown", function(e) {
        if (e.key === "Enter" || e.key === " ") {
          const toggleBtn = e.target.closest('[data-action="toggle-swarm-subagents"]');
          if (toggleBtn) {
            e.preventDefault();
            toggleBtn.click();
          }
        }
      });
    }
  }

  const convoIndex = buildConvoMetaIndex(data);

  let swarmsToRender = [];
  let isFallback = false;

  const activeMultiSwarms = Array.isArray(data.active_swarms)
    ? data.active_swarms.filter(s => Array.isArray(s.subagents) && s.subagents.length > 0)
    : [];

  if (activeMultiSwarms.length > 0) {
    swarmsToRender = activeMultiSwarms;
  } else if (data.swarms && Array.isArray(data.swarms.swarms) && data.swarms.swarms.length > 0) {
    isFallback = !Array.isArray(data.active_swarms) || data.active_swarms.length === 0;
    swarmsToRender = data.swarms.swarms.slice(0, 3).map(sw => {
      const nodes = sw.nodes || [];
      const rootNode = nodes.find(n => n.is_root) || nodes[0] || {};
      const childNodes = nodes.filter(n => n !== rootNode);

      return {
        workspace: sw.workspace_name || "Antigravity Workspace",
        branch: "main",
        worst_severity: sw.is_overage ? "warning" : "safe",
        orchestrator: {
          title: sw.root_title || rootNode.title || "Root Orchestrator", convo_id: sw.root_convo_id || rootNode.id || "",
          tokens: rootNode.tokens_total || sw.root_tokens || 50000, threshold: 250000, compaction_threshold: 250000,
          compaction_epoch: 1, severity: "safe", is_weakest_link: false,
          model_name: rootNode.model_name || "Gemini 4 Argon (Medium)", model_id: rootNode.model_id || "1418", turn_count: rootNode.turn_count || 1
        },
        subagents: childNodes.map(c => ({
          title: c.title || c.role || "Subagent", convo_id: c.id || "", subagent_role: c.role || c.subagent_role || "Worker",
          tokens: c.tokens_total || 25000, threshold: 250000, compaction_epoch: 1, severity: "safe", is_weakest_link: false,
          model_name: c.model_name || "Gemini Fast Agent Assistant", model_id: c.model_id || "1322", turn_count: c.turn_count || 1
        }))
      };
    });
  } else if (Array.isArray(data.active_swarms) && data.active_swarms.length > 0) {
    swarmsToRender = data.active_swarms;
  }

  const safeEscape = (val) => (typeof escapeHtml === "function" ? escapeHtml(val || "") : (val || ""));
  const fmtNum = (val) => (typeof formatNumber === "function" ? formatNumber(val || 0) : (val || 0));

  const totalSwarmsCount = swarmsToRender.length;
  let statusBadgeHtml = '';
  if (isFallback) {
    statusBadgeHtml = `<span class="now-swarms-live-pill showcase" title="Showing top recent multi-agent hierarchy in showcase mode">Showcase Swarm Hierarchy</span>`;
  } else if (totalSwarmsCount > 0) {
    statusBadgeHtml = `<span class="now-swarms-live-pill" title="Real-time multi-agent hierarchies active in local workspace">● ${totalSwarmsCount} Active ${totalSwarmsCount === 1 ? 'Swarm' : 'Swarms'}</span>`;
  } else {
    statusBadgeHtml = `<span class="now-swarms-live-pill idle">0 Active Swarms</span>`;
  }

  if (totalSwarmsCount === 0) {
    container.innerHTML = `
      <div class="now-swarms-header">
        <div class="now-swarms-header-left">
          <svg class="now-swarms-icon" width="16" height="16" viewBox="0 0 256 256" fill="currentColor" aria-hidden="true">
            <path d="M224,168a24,24,0,0,0-17.76,8.24l-38.64-27.6A40,40,0,0,0,176,128a39.69,39.69,0,0,0-6.19-21.2l36.43-31.87A24,24,0,1,0,195.44,61.4L159,93.28A40,40,0,0,0,136,88.9V48h8a8,8,0,0,0,0-16H112a8,8,0,0,0,0,16h8V88.9a40,40,0,0,0-23,4.38L60.56,61.4A24,24,0,1,0,50.19,74.93L86.62,106.8A39.69,39.69,0,0,0,80.43,128a40,40,0,0,0,8.41,20.64l-38.64,27.6A24,24,0,1,0,60,192a23.86,23.86,0,0,0-1.76-9l37.2-26.57a40,40,0,0,0,65.12,0l37.2,26.57A23.86,23.86,0,0,0,196,192a24,24,0,1,0,28-24ZM48,80a8,8,0,1,1,8-8A8,8,0,0,1,48,80ZM40,200a8,8,0,1,1,8-8A8,8,0,0,1,40,200ZM208,64a8,8,0,1,1-8,8A8,8,0,0,1,208,64Zm8,136a8,8,0,1,1,8-8A8,8,0,0,1,216,200ZM128,152a24,24,0,1,1,24-24A24,24,0,0,1,128,152Z"/>
          </svg>
          <h3 class="now-swarms-title">Active Multi-Agent Swarms</h3>
          ${statusBadgeHtml}
        </div>
        <div class="now-swarms-header-right">
          <button class="now-swarms-view-btn tactile-press" data-action="switch-tab" data-tab="swarms" title="View interactive lineage DAG in Swarms &amp; Tools">
            View Full Swarm Topology →
          </button>
        </div>
      </div>
      <div class="now-swarms-empty-card">
        <span>No multi-agent swarms currently active. Swarms appear automatically when subagents are spawned.</span>
      </div>
    `;
    return;
  }

  const swarmCardsHtml = swarmsToRender.map((swarm, swIdx) => {
    const orch = swarm.orchestrator || {};
    const subs = swarm.subagents || [];
    const totalAgents = (swarm.orchestrator ? 1 : 0) + subs.length;
    const weakest = computeSwarmWeakestLink(swarm);

    const wsName = safeEscape(swarm.workspace || "Workspace");
    const branchName = safeEscape(swarm.branch || "main");
    const orchTitle = safeEscape(orch.title || "Multi-Agent Orchestrator");

    const orchMeta = convoIndex[orch.convo_id] || {};
    const orchModel = resolveModelBadge(orch, orchMeta);
    const orchTurns = orchMeta.turnCount || orch.turn_count || (orch.turn_velocity ? Math.round(orch.turn_velocity / 100) : 1);
    const orchThresh = orch.threshold || orch.compaction_threshold || 250000;
    const orchPct = orchThresh > 0 ? Math.round(((orch.tokens || 0) / orchThresh) * 100) : 0;
    const orchEpoch = orch.compaction_epoch || 1;

    let subagentsBlockHtml = '';
    if (subs.length > 0) {
      const subRows = subs.map(sub => {
        const subMeta = convoIndex[sub.convo_id] || {};
        const subModel = resolveModelBadge(sub, subMeta);
        const subTurns = subMeta.turnCount || sub.turn_count || 1;
        const subThresh = sub.threshold || 250000;
        const subPct = subThresh > 0 ? Math.round(((sub.tokens || 0) / subThresh) * 100) : 0;
        const subEpoch = sub.compaction_epoch || 1;
        const rawRole = String(sub.subagent_role || "Worker");
        const rawTitle = String(sub.title || sub.convo_id || "Subagent");
        const isGenericHexTitle = rawTitle.startsWith("Conversation ") && rawRole.length > 0;
        const subRole = safeEscape((isGenericHexTitle && (rawRole.includes(" ") || rawRole.length > 14)) ? "subagent" : rawRole);
        const subTitle = safeEscape(isGenericHexTitle ? rawRole : rawTitle);
        const isWeak = Boolean(sub.is_weakest_link || (weakest.weakestNode && weakest.weakestNode.convo_id === sub.convo_id));

        return `
          <div class="now-subagent-row ${isWeak ? 'is-weakest-link' : ''}">
            <div class="now-node-left">
              <span class="now-node-branch-symbol">↳</span>
              <span class="now-role-pill role-subagent">[${subRole}]</span>
              <span class="now-model-badge model-${subModel.type}">${subModel.name}</span>
              <span class="now-node-title" title="${subTitle}">${subTitle}</span>
              ${isWeak ? '<span class="now-weakest-pill">Weakest Link</span>' : ''}
            </div>
            <div class="now-node-right">
              <span class="now-epoch-pill">E${subEpoch}</span>
              <span class="now-node-turns">${subTurns} turns</span>
              <span class="now-node-tokens">${fmtNum(sub.tokens || 0)} tok</span>
              <span class="now-util-pill ${subPct >= 80 ? 'highlight-red' : (subPct >= 50 ? 'highlight-amber' : 'highlight-green')}">${subPct}% ctx</span>
            </div>
          </div>
        `;
      }).join("");

      subagentsBlockHtml = `
        <div class="now-swarm-toggle" data-action="toggle-swarm-subagents" role="button" tabindex="0" aria-expanded="true">
          <span class="now-swarm-toggle-label">
            <svg width="12" height="12" viewBox="0 0 256 256" fill="currentColor" aria-hidden="true"><path d="M200,48H136V24a8,8,0,0,0-16,0V48H56A32,32,0,0,0,24,80V192a32,32,0,0,0,32,32H200a32,32,0,0,0,32-32V80A32,32,0,0,0,200,48Zm16,144a16,16,0,0,1-16,16H56a16,16,0,0,1-16-16V80A16,16,0,0,1,56,64H200a16,16,0,0,1,16,16ZM88,112a16,16,0,1,1,16,16A16,16,0,0,1,88,112Zm80,0a16,16,0,1,1-16-16A16,16,0,0,1,168,112Zm-96,48a8,8,0,0,1,8-8h96a8,8,0,0,1,0,16H80A8,8,0,0,1,72,160Z"/></svg>
            Child Subagents (${subs.length})
          </span>
          <span class="now-swarm-toggle-chevron">▼</span>
        </div>
        <div class="now-subagents-list">
          ${subRows}
        </div>
      `;
    } else {
      subagentsBlockHtml = `
        <div class="now-swarm-single-note">Single orchestrator session (0 subagents spawned)</div>
      `;
    }

    const isOrchWeak = Boolean(orch.is_weakest_link || (weakest.weakestNode && weakest.weakestNode.convo_id === orch.convo_id));

    return `
      <div class="now-swarm-card" data-swarm-id="${swIdx}">
        <div class="now-swarm-header-row">
          <div class="now-swarm-header-title-group">
            <span class="now-swarm-ws-badge" title="Workspace Repository">${wsName} (${branchName})</span>
            <strong class="now-swarm-title" title="${orchTitle}">${orchTitle}</strong>
          </div>
          <div class="now-swarm-badges-group">
            <span class="now-agent-count-pill">${totalAgents} ${totalAgents === 1 ? 'agent' : 'agents'}</span>
            <span class="now-risk-badge risk-${weakest.riskClass}" title="Weakest-link context degradation risk">${weakest.label}</span>
          </div>
        </div>

        <div class="now-orchestrator-row ${isOrchWeak ? 'is-weakest-link' : ''}">
          <div class="now-node-left">
            <span class="now-role-pill role-orch">Orchestrator</span>
            <span class="now-model-badge model-${orchModel.type}">${orchModel.name}</span>
            <span class="now-node-title" title="${orchTitle}">${orchTitle}</span>
            ${isOrchWeak ? '<span class="now-weakest-pill">Weakest Link</span>' : ''}
          </div>
          <div class="now-node-right">
            <span class="now-epoch-pill">E${orchEpoch}</span>
            <span class="now-node-turns">${orchTurns} turns</span>
            <span class="now-node-tokens">${fmtNum(orch.tokens || 0)} tok</span>
            <span class="now-util-pill ${orchPct >= 80 ? 'highlight-red' : (orchPct >= 50 ? 'highlight-amber' : 'highlight-green')}">${orchPct}% ctx</span>
          </div>
        </div>

        ${subagentsBlockHtml}
      </div>
    `;
  }).join("");

  container.innerHTML = `
    <div class="now-swarms-header">
      <div class="now-swarms-header-left">
        <svg class="now-swarms-icon" width="16" height="16" viewBox="0 0 256 256" fill="currentColor" aria-hidden="true">
          <path d="M224,168a24,24,0,0,0-17.76,8.24l-38.64-27.6A40,40,0,0,0,176,128a39.69,39.69,0,0,0-6.19-21.2l36.43-31.87A24,24,0,1,0,195.44,61.4L159,93.28A40,40,0,0,0,136,88.9V48h8a8,8,0,0,0,0-16H112a8,8,0,0,0,0,16h8V88.9a40,40,0,0,0-23,4.38L60.56,61.4A24,24,0,1,0,50.19,74.93L86.62,106.8A39.69,39.69,0,0,0,80.43,128a40,40,0,0,0,8.41,20.64l-38.64,27.6A24,24,0,1,0,60,192a23.86,23.86,0,0,0-1.76-9l37.2-26.57a40,40,0,0,0,65.12,0l37.2,26.57A23.86,23.86,0,0,0,196,192a24,24,0,1,0,28-24ZM48,80a8,8,0,1,1,8-8A8,8,0,0,1,48,80ZM40,200a8,8,0,1,1,8-8A8,8,0,0,1,40,200ZM208,64a8,8,0,1,1-8,8A8,8,0,0,1,208,64Zm8,136a8,8,0,1,1,8-8A8,8,0,0,1,216,200ZM128,152a24,24,0,1,1,24-24A24,24,0,0,1,128,152Z"/>
        </svg>
        <h3 class="now-swarms-title">Active Multi-Agent Swarms</h3>
        ${statusBadgeHtml}
      </div>
      <div class="now-swarms-header-right">
        <button class="now-swarms-view-btn tactile-press" data-action="switch-tab" data-tab="swarms" title="View interactive lineage DAG in Swarms &amp; Tools">
          View Full Swarm Topology →
        </button>
      </div>
    </div>
    <div class="now-swarms-cards-list">
      ${swarmCardsHtml}
    </div>
  `;
}

// Window exports for global access and compatibility
if (typeof window !== "undefined") {
  window.generateStandupMarkdown = generateStandupMarkdown;
  window.renderActiveBurstSessions = renderActiveBurstSessions;
  window.toggleBurstSessionsList = toggleBurstSessionsList;
  window.renderRecoveryTimeline = renderRecoveryTimeline;
  window.updateTimelineTick = updateTimelineTick;
  window.startBurstCountdown = startBurstCountdown;
  window.renderExecutiveHero = renderExecutiveHero;
  window.updateExecutiveHeroTicker = updateExecutiveHeroTicker;
  window.renderNowActiveSwarms = renderNowActiveSwarms;
}
