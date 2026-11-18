/**
 * Sessions Explorer Component
 * Milestone 55 (Row 9: C5 - Minified data.js & Lazy Turns)
 *
 * Turns drawer and turns table logic extracted to js/sessions-turns.js (<800 lines rule).
 * Filters, sorting, and pagination logic extracted to js/sessions-filters.js (<800 lines rule).
 */

// ==========================================
// 3. Universal Floating Glass Tooltip (ADR-048)
// ==========================================
function renderConversationsTable(list) {
  if (typeof sessionsViewMode !== "undefined" && sessionsViewMode === "tree" && typeof renderTreeConversationsTable === "function") {
    renderTreeConversationsTable(list);
    return;
  }
  list = list || [];
  const tbody = document.getElementById("conversations-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  const totalItems = list.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / CONVO_PAGE_SIZE));
  if (convoCurrentPage >= totalPages) convoCurrentPage = Math.max(0, totalPages - 1);
  const pageItems = list.slice(convoCurrentPage * CONVO_PAGE_SIZE, (convoCurrentPage + 1) * CONVO_PAGE_SIZE);

  const countEl = document.getElementById("convo-table-count");
  if (countEl) countEl.textContent = `${totalItems} conversations`;

  const pageInfo = document.getElementById("convo-page-info");
  if (pageInfo) {
    pageInfo.textContent = `Page ${convoCurrentPage + 1} of ${totalPages} (${totalItems} conversations)`;
  }
  const prevBtn = document.getElementById("btn-convo-prev");
  if (prevBtn) {
    prevBtn.disabled = (convoCurrentPage === 0);
  }
  const nextBtn = document.getElementById("btn-convo-next");
  if (nextBtn) {
    nextBtn.disabled = (convoCurrentPage >= totalPages - 1);
  }

  if (totalItems === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No conversations match the current filter.</td></tr>';
    return;
  }
  pageItems.forEach(c => {
    const tr = document.createElement("tr");
    tr.style.cursor = "pointer";
    const cOvgCredits = c.actual_overage_credits || 0;
    const cOvgUsd = c.actual_overage_usd || 0.0;
    const cOvgGbp = c.actual_overage_gbp || 0.0;
    const cAvoidedUsd = c.avoided_cost_usd !== undefined ? c.avoided_cost_usd : (c.estimated_cost_usd || 0.0);
    const cAvoidedGbp = c.avoided_cost_gbp !== undefined ? c.avoided_cost_gbp : (c.estimated_cost_gbp || 0.0);
    const cCovPct = c.subscription_covered_pct !== undefined ? c.subscription_covered_pct : 100.0;
    let coverageBadge = '';
    if (cOvgCredits === 0) {
      coverageBadge = '<span class="code-pill" style="color: var(--accent-green); background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3); font-weight: 600;">100% Covered</span>';
    } else {
      coverageBadge = `<span class="code-pill" style="color: var(--accent-amber); background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); font-weight: 600;">${cCovPct.toFixed(1)}% Covered</span>`;
    }
    let overageDisplay = '';
    if (cOvgCredits === 0) {
      overageDisplay = `<span style="color: var(--text-muted); font-size: 0.8125rem;">${formatCurrency(0, 0, 2)} <span style="font-size: 0.75rem;">(0 credits)</span></span>`;
    } else {
      overageDisplay = `<strong style="color: var(--accent-amber); font-size: 0.875rem;">${formatCurrency(cOvgUsd, cOvgGbp, 2)}</strong><span style="font-size: 0.75rem; color: var(--accent-amber); display: block;">${formatNumber(cOvgCredits)} credits burned</span>`;
    }
    const isSub = Boolean(c.is_subagent);
    const agName = c.agent_name || "default";
    let personaBadges = '';
    if (isSub) {
      const subRole = escapeHtml(c.subagent_role || c.subagent_type || "Worker");
      const pId = c.parent_convo_id ? escapeHtml(c.parent_convo_id.slice(0, 8)) : "";
      personaBadges = `
        <div style="margin-top: 4px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
          <span class="badge-agent badge-subagent-pill">Subagent: ${subRole}</span>
          ${pId ? `<span style="font-size: 0.72rem; color: var(--text-muted);">↳ child of ${pId}…</span>` : ''}
        </div>
      `;
    } else {
      let roleBadge = '';
      if (agName === "auditor") {
        roleBadge = '<span class="badge-agent badge-agent-auditor">Auditor</span>';
      } else if (agName === "implementer") {
        roleBadge = '<span class="badge-agent badge-agent-implementer">Implementer</span>';
      } else {
        roleBadge = '<span class="badge-agent badge-agent-general">General</span>';
      }
      let swarmPill = '';
      const subCount = c.subagents_count || 0;
      if (subCount > 0) {
        swarmPill = `<span class="badge-agent badge-swarm-link" title="Spawned ${subCount} subagent workers. Click to view swarm topology." data-action="switch-tab" data-tab="tab-swarms">${subCount} subagents</span>`;
      }
      personaBadges = `
        <div style="margin-top: 4px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
          ${roleBadge}
          ${swarmPill}
        </div>
      `;
    }

    tr.innerHTML = `
      <td>
        <div style="display: flex; flex-direction: column; gap: 2px;">
          <strong>${escapeHtml(c.title || "Untitled")}</strong>
          <span style="font-size: 0.75rem; color: var(--text-muted);">${c.convo_id}</span>
          ${personaBadges}
        </div>
      </td>
      <td><span class="code-pill">${escapeHtml(c.workspace || "Unknown")}</span></td>
      <td>${formatNumber(c.turn_count)}</td>
      <td>
        ${formatNumber(c.total_input_tokens)}
        <span style="font-size: 0.75rem; color: var(--text-muted); display: block;">${formatNumber(c.cached_tokens)} cached</span>
      </td>
      <td><strong class="highlight-green">${(c.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></td>
      <td>${coverageBadge}</td>
      <td>${overageDisplay}</td>
      <td><strong class="highlight-green">${formatCurrency(cAvoidedUsd, cAvoidedGbp, 2)}</strong></td>
    `;
    tr.addEventListener("click", () => {
      document.getElementById("convo-filter").value = c.convo_id;
      activeConvoForTurns = c;
      renderTurnsTable(c);
      openTurnsDrawer(c);
    });
    tbody.appendChild(tr);
  });
}
function renderRecentSessions() {
  const tbody = document.getElementById("recent-sessions-tbody");
  if (!tbody) return;
  const convos = (globalDashboardData && globalDashboardData.conversations) || [];
  if (convos.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No conversation sessions found.</td></tr>';
    return;
  }
  const recent = convos.slice(0, 6);
  tbody.innerHTML = "";
  recent.forEach(c => {
    const tr = document.createElement("tr");
    const cAvoidedUsd = c.avoided_cost_usd !== undefined ? c.avoided_cost_usd : (c.estimated_cost_usd || 0.0);
    const cAvoidedGbp = c.avoided_cost_gbp !== undefined ? c.avoided_cost_gbp : (c.estimated_cost_gbp || 0.0);
    const cCovPct = c.subscription_covered_pct !== undefined ? c.subscription_covered_pct : 100.0;
    const covBadge = (c.actual_overage_credits || 0) === 0
      ? '<span class="code-pill" style="color: var(--accent-green); background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3); font-weight: 600;">100% Covered</span>'
      : `<span class="code-pill" style="color: var(--accent-amber); background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); font-weight: 600;">${cCovPct.toFixed(0)}% Covered</span>`;
    
    const isSub = Boolean(c.is_subagent);
    const agName = c.agent_name || "default";
    let roleBadge = '';
    if (isSub) {
      roleBadge = '<span class="badge-agent badge-subagent-pill" style="font-size: 0.625rem; padding: 1px 5px;">Subagent</span>';
    } else if (agName === "auditor") {
      roleBadge = '<span class="badge-agent badge-agent-auditor" style="font-size: 0.625rem; padding: 1px 5px;">Auditor</span>';
    } else if (agName === "implementer") {
      roleBadge = '<span class="badge-agent badge-agent-implementer" style="font-size: 0.625rem; padding: 1px 5px;">Implementer</span>';
    }

    tr.innerHTML = `
      <td>
        <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
          <strong>${escapeHtml(c.title || "Untitled")}</strong>
          ${roleBadge}
        </div>
        <span style="font-size: 0.72rem; color: var(--text-muted);">${c.convo_id}</span>
      </td>
      <td><span class="code-pill">${escapeHtml(c.workspace || "Unknown")}</span></td>
      <td>${formatNumber(c.turn_count)}</td>
      <td>${formatNumber(c.total_input_tokens)}</td>
      <td><strong class="highlight-green">${(c.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></td>
      <td>${covBadge}</td>
      <td><strong class="highlight-green">${formatCurrency(cAvoidedUsd, cAvoidedGbp, 2)}</strong></td>
      <td><button class="badge" style="cursor: pointer; background: var(--card-bg); border: 1px solid var(--card-border); font-size: 0.75rem; padding: 2px 8px;" data-action="inspect-session" data-convo-id="${c.convo_id}">Inspect &rarr;</button></td>
    `;
    tbody.appendChild(tr);
  });
}
function inspectSession(convoId) {
  switchTab("tab-sessions");
  const convoFilter = document.getElementById("convo-filter");
  if (convoFilter) convoFilter.value = convoId;
  const convos = (globalDashboardData && globalDashboardData.conversations) || [];
  const selected = convos.find(c => c.convo_id === convoId);
  if (selected) {
    activeFilteredConversations = [selected];
    activeConvoForTurns = selected;
    renderConversationsTable(activeFilteredConversations);
    renderTurnsTable(selected);
    openTurnsDrawer(selected);
  }
}
function renderCacheCoaching(coaching) {
  const container = document.getElementById("cache-coaching-section");
  if (!container) return;
  if (!coaching) {
    container.innerHTML = "";
    return;
  }
  const flips = coaching.cross_model_flips !== undefined ? coaching.cross_model_flips : (coaching.model_flips_detected || 0);
  const intraFamilyFlips = coaching.intra_family_flips || 0;
  const intraTrackFlips = coaching.intra_track_flips || 0;
  const crossProviderFlips = coaching.cross_provider_flips || 0;
  const wastedTok = formatNumber(coaching.estimated_flip_waste_tokens !== undefined ? coaching.estimated_flip_waste_tokens : (coaching.wasted_uncached_tokens || 0));
  const wastedCostVal = coaching.estimated_flip_waste_usd !== undefined ? coaching.estimated_flip_waste_usd : (coaching.wasted_avoided_cost_usd || 0);
  const wastedCostGbpVal = coaching.estimated_flip_waste_gbp !== undefined ? coaching.estimated_flip_waste_gbp : (coaching.wasted_avoided_cost_gbp || 0);
  const wastedCost = activeCurrency === "GBP"
    ? `£${wastedCostGbpVal.toFixed(2)}`
    : `$${wastedCostVal.toFixed(2)}`;
  const tip = escapeHtml(coaching.coaching_tip || "");
  const incidents = coaching.flip_incidents || coaching.top_incidents || [];
  if (flips === 0) {
    container.innerHTML = `
      <div class="section-card" style="padding: 12px 18px; display: flex; align-items: center; justify-content: space-between; border-left: 4px solid var(--status-normal);">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 50%; background: rgba(16, 185, 129, 0.15); color: var(--status-normal); font-weight: 700; font-size: 0.75rem;">✓</span>
          <div>
            <div style="font-weight: 600; font-size: 0.875rem; color: var(--text-main);">Cache Continuity Excellent</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">Zero KV prompt cache evictions detected across your sessions (intra-family, intra-track, or cross-provider).</div>
          </div>
        </div>
        <span class="badge green" style="font-size: 0.7rem;">90%+ Cache Reuse</span>
      </div>
    `;
    return;
  }

  let breakdownBadges = "";
  if (intraFamilyFlips > 0) {
    breakdownBadges += `<span class="badge amber" style="font-size: 0.7rem; padding: 2px 8px;">${intraFamilyFlips} Intra-Family Tier Flips</span>`;
  }
  if (intraTrackFlips > 0) {
    breakdownBadges += `<span class="badge blue" style="font-size: 0.7rem; padding: 2px 8px;">${intraTrackFlips} Intra-Track Flips</span>`;
  }
  if (crossProviderFlips > 0) {
    breakdownBadges += `<span class="badge purple" style="font-size: 0.7rem; padding: 2px 8px;">${crossProviderFlips} Cross-Provider Flips</span>`;
  }

  const incidentsHtml = incidents.slice(0, 5).map(inc => {
    const title = escapeHtml(inc.title || "Untitled Session");
    const ws = escapeHtml(inc.workspace_name || "");
    const fromM = escapeHtml(inc.from_model || "Prev Model");
    const toM = escapeHtml(inc.to_model || "Next Model");
    const wasted = formatNumber(inc.wasted_tokens || 0);
    const cid = escapeHtml(inc.convo_id || "");
    const cost = activeCurrency === "GBP" ? `£${(inc.wasted_cost_gbp || 0).toFixed(2)}` : `$${(inc.wasted_cost_usd || 0).toFixed(2)}`;
    const flipType = inc.flip_type || "cross_provider";
    let typeBadge = "";
    if (flipType === "intra_family") {
      typeBadge = `<span class="badge amber" style="font-size: 0.65rem; padding: 1px 6px;">Intra-Family</span>`;
    } else if (flipType === "intra_track") {
      typeBadge = `<span class="badge blue" style="font-size: 0.65rem; padding: 1px 6px;">Intra-Track</span>`;
    } else if (flipType === "cross_provider") {
      typeBadge = `<span class="badge purple" style="font-size: 0.65rem; padding: 1px 6px;">Cross-Provider</span>`;
    }
    const cleanType = flipType.replace(/_/g, " ");
    return `
      <div style="background: var(--quota-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 10px 14px; margin-top: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <div>
          <div style="font-weight: 600; font-size: 0.8125rem; color: var(--text-main); display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <span>${title}</span>
            ${typeBadge}
            <span class="model-flip-tag">${fromM} ➔ ${toM}</span>
          </div>
          <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 2px;">
            ${ws ? `${ws} • ` : ""}Step #${inc.step_idx || "—"} • ${cleanType} • Incurred <strong>+${wasted}</strong> uncached replay tokens (${cost})
          </div>
        </div>
        <button class="btn-secondary" style="font-size: 0.72rem; padding: 4px 10px; cursor: pointer;" data-action="inspect-session" data-convo-id="${cid}">
          Inspect Session →
        </button>
      </div>
    `;
  }).join("");

  container.innerHTML = `
    <div class="cache-coaching-card">
      <div class="cache-coaching-header">
        <div>
          <div class="cache-coaching-title">
            <span>Cache-Efficiency Coaching: KV Cache Eviction Penalty</span>
            <span class="badge amber" style="font-size: 0.7rem;">${flips} Evictions Detected</span>
          </div>
          ${breakdownBadges ? `<div style="display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap;">${breakdownBadges}</div>` : ""}
          <div style="font-size: 0.78125rem; color: var(--text-muted); margin-top: 6px; max-width: 750px; line-height: 1.4;">
            ${tip}
          </div>
          <div style="margin-top: 8px; font-size: 0.75rem; color: var(--text-secondary); background: rgba(245, 158, 11, 0.08); border-left: 3px solid var(--status-warning); padding: 8px 12px; border-radius: 4px; max-width: 750px; line-height: 1.4;">
            <strong>GADR-018 Subagent Routing Discipline:</strong> Select model reasoning effort tiers (e.g. Carbon / Argon High/Med/Low) at Turn 1. Never flip tiers mid-stream in deep sessions (>40k tokens). Delegate mechanical sweeps or research to <code>Model: "flash"</code> subagents to preserve the parent's warm KV cache (~98% reuse).
          </div>
        </div>
      </div>

      <div class="coaching-grid">
        <div class="coaching-stat-pill">
          <span class="coaching-stat-lbl">Model Flips Detected</span>
          <span class="coaching-stat-val" style="color: var(--status-warning);">${flips}</span>
        </div>
        <div class="coaching-stat-pill">
          <span class="coaching-stat-lbl">Wasted Replay Tokens</span>
          <span class="coaching-stat-val" style="color: var(--status-alert);">${wastedTok}</span>
        </div>
        <div class="coaching-stat-pill">
          <span class="coaching-stat-lbl">Wasted Avoided Value</span>
          <span class="coaching-stat-val" style="color: var(--status-warning);">${wastedCost}</span>
        </div>
        <div class="coaching-stat-pill">
          <span class="coaching-stat-lbl">Typical Cache Reuse</span>
          <span class="coaching-stat-val" style="color: var(--status-normal);">~90%</span>
        </div>
      </div>

      <div>
        <div style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px;">
          Top Replay Invalidation Incidents
        </div>
        ${incidentsHtml}
      </div>
    </div>
  `;
}
// --- DEGRADED SESSIONS & CONTEXT SAFETY (ADR-060 / ADR-061 / M47) ---
window.__contextDrawerExpanded = false;

window.toggleContextAuditDrawer = function() {
  window.__contextDrawerExpanded = !window.__contextDrawerExpanded;
  updateDegradedUI(window.__lastDegradedSessions || [], window.__lastCurrentSession || null);
};

function checkDegradedSessions(convos, liveCurrentSession) {
  const degradedSessions = [];
  const nowMs = Date.now();
  const ONE_DAY_MS = 24 * 60 * 60 * 1000;

  // Milestone 88: Authoritative Live Session from data.current_session
  // Completed historical sessions at convos[0] must never trigger false-alarm warning on Now tab.
  const liveSessionSource = liveCurrentSession
    || (typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.current_session)
    || (typeof window !== "undefined" && window.__TELEMETRY_DATA__ && window.__TELEMETRY_DATA__.current_session)
    || null;

  let currentSession = null;
  if (liveSessionSource && liveSessionSource.is_active !== false && !liveSessionSource.completed) {
    const thresh = liveSessionSource.threshold || liveSessionSource.compaction_threshold || 200000;
    const tokens = liveSessionSource.tokens || 0;
    const epoch = liveSessionSource.compaction_epoch || 1;
    const ratio = thresh > 0 ? (tokens / thresh) : 0;
    const headroomWarn = liveSessionSource.headroom_to_warning !== undefined
      ? liveSessionSource.headroom_to_warning
      : Math.max(0, Math.round(0.8 * thresh) - Math.round(tokens));
    const headroomComp = liveSessionSource.headroom_to_compaction !== undefined
      ? liveSessionSource.headroom_to_compaction
      : Math.max(0, Math.round(thresh) - Math.round(tokens));

    let activeSessionSeverity = "safe";
    let driftRisk = liveSessionSource.drift_risk || "safe";
    let driftMessage = liveSessionSource.drift_message || `Safe (+${formatNumber(headroomWarn)} to warning)`;

    if (liveSessionSource.tokens !== undefined) {
      if (ratio >= 0.9) {
        activeSessionSeverity = "critical";
        driftRisk = "critical";
        driftMessage = liveSessionSource.drift_message || "Compaction Imminent (~1 turn)";
      } else if (ratio >= 0.8) {
        activeSessionSeverity = "warning";
        driftRisk = "caution";
        driftMessage = `Near Compaction (+${formatNumber(headroomComp)} tok)`;
      } else if (epoch >= 2) {
        activeSessionSeverity = "safe";
        driftRisk = "info";
        driftMessage = `Epoch ${epoch} compacted (+${formatNumber(headroomWarn)} to warning)`;
      } else {
        driftRisk = "safe";
      }
    } else if (liveSessionSource.severity) {
      activeSessionSeverity = liveSessionSource.severity;
    }

    currentSession = {
      convo_id: liveSessionSource.convo_id || liveSessionSource.id || "Active Conversation",
      title: liveSessionSource.title || "Active Conversation",
      branch: liveSessionSource.branch || liveSessionSource.git_branch || "main",
      workspace: liveSessionSource.workspace || liveSessionSource.workspace_name || "Current Workspace",
      tokens: Math.round(tokens),
      threshold: thresh,
      nominal_threshold: liveSessionSource.nominal_threshold || thresh,
      compaction_threshold: thresh,
      compaction_count: liveSessionSource.compaction_count || 0,
      compaction_epoch: epoch,
      severity: activeSessionSeverity,
      drift_risk: driftRisk,
      drift_message: driftMessage,
      headroom_to_warning: headroomWarn,
      headroom_to_compaction: headroomComp,
      is_current: true
    };
  }

  for (const c of convos) {
    if (!c.last_turn_ts) continue;
    // Check 24-hour recency
    const lastTurnMs = new Date(c.last_turn_ts).getTime();
    if (nowMs - lastTurnMs > ONE_DAY_MS) {
      continue; // Assume abandoned/archived
    }
    let peakDepth = 0;
    let mId = null;
    const cTurns = (c.turns && c.turns.length > 0)
      ? c.turns
      : ((typeof window !== "undefined" && window.__TELEMETRY_TURNS__ && window.__TELEMETRY_TURNS__[c.convo_id]) || null);
    if (cTurns && cTurns.length > 0) {
      let maxTok = -1;
      let pTurn = null;
      for (const t of cTurns) {
        const tok = t.total_input_tokens || 0;
        if (tok > maxTok) {
          maxTok = tok;
          pTurn = t;
        }
      }
      peakDepth = maxTok >= 0 ? maxTok : 0;
      mId = pTurn ? (pTurn.model_id || pTurn.model_name) : null;
    } else if (c.peak_prompt_depth != null && typeof c.peak_prompt_depth === "number" && c.peak_prompt_depth > 0) {
      peakDepth = c.peak_prompt_depth;
    } else if (c.depth_at_truncation != null && typeof c.depth_at_truncation === "number" && c.depth_at_truncation > 0) {
      peakDepth = c.depth_at_truncation;
    } else {
      peakDepth = (c.total_input_tokens || 0) / (c.turn_count || 1);
    }
    if (!mId && c.models_used && c.models_used.length > 0) {
      mId = c.models_used[c.models_used.length - 1];
    }
    const thresh = getModelTruncationThreshold(mId);
    let severity = null;
    if (peakDepth >= thresh) {
      severity = "critical";
    } else if (peakDepth >= 0.8 * thresh) {
      severity = "warning";
    }
    if (severity) {
      const is_current = Boolean(currentSession && (c.convo_id === currentSession.convo_id || (currentSession.id && c.convo_id === currentSession.id) || (c.id && c.id === currentSession.convo_id)));
      degradedSessions.push({
        ...c,
        peakDepth: Math.round(peakDepth),
        threshold: thresh,
        severity,
        branch: c.git_branch || "main",
        workspace: c.workspace_name || c.workspace || "Workspace",
        is_current
      });
    }
  }
  window.__lastDegradedSessions = degradedSessions;
  window.__lastCurrentSession = currentSession;
  // Update UI Elements
  updateDegradedUI(degradedSessions, currentSession);
}

function updateDegradedUI(sessions, currentSession) {
  sessions = sessions || window.__lastDegradedSessions || [];
  currentSession = currentSession || window.__lastCurrentSession || null;

  const headerBadge = document.getElementById("degraded-badge-header");
  const tabBadge = document.getElementById("degraded-badge-top-tab");
  const nowContainer = document.getElementById("now-degraded-warning-container");
  const sessionsContainer = document.getElementById("sessions-degraded-widget-container");

  const activeSev = currentSession ? currentSession.severity : "safe";
  const historicalSessions = sessions.filter(s => !s.is_current && (!currentSession || (s.convo_id !== currentSession.convo_id && (!currentSession.id || s.convo_id !== currentSession.id))));

  // 1. Header Badge: Demote to amber-on-hover! NEVER set headerBadge.className = "badge red"
  if (headerBadge) {
    if (currentSession && (activeSev === "critical" || activeSev === "warning")) {
      headerBadge.className = "badge amber-hover";
      const label = currentSession.is_subagent ? `Subagent [${escapeHtml(currentSession.subagent_role || "worker")}]` : `Active Context`;
      headerBadge.innerHTML = `<svg width="12" height="12" viewBox="0 0 256 256" fill="currentColor"><path d="M236.8,188.09,149.35,36.22h0a24.76,24.76,0,0,0-42.7,0L19.2,188.09a23.51,23.51,0,0,0,0,23.72A24.35,24.35,0,0,0,40.55,224h174.9a24.35,24.35,0,0,0,21.33-12.19A23.51,23.51,0,0,0,236.8,188.09ZM222.93,204a8.33,8.33,0,0,1-7.48,4H40.55a8.33,8.33,0,0,1-7.48-4,7.48,7.48,0,0,1,0-7.8l87.45-151.87a8.76,8.76,0,0,1,15,0L223,196.2A7.48,7.48,0,0,1,222.93,204ZM120,144V104a8,8,0,0,1,16,0v40a8,8,0,0,1-16,0Zm20,36a12,12,0,1,1-12-12A12,12,0,0,1,140,180Z"/></svg> ${label}: ${formatNumber(currentSession.tokens)} / ${formatNumber(currentSession.threshold)}`;
      headerBadge.title = (currentSession.is_subagent ? "Active subagent context depth: " : "Active session context depth: ") + formatNumber(currentSession.tokens) + " tokens (" + activeSev + "). Click to inspect.";
      headerBadge.style.display = "inline-flex";
    } else if (historicalSessions.length > 0) {
      headerBadge.className = "badge amber-hover";
      headerBadge.innerHTML = `<svg width="10" height="10" viewBox="0 0 256 256" fill="var(--status-normal)"><circle cx="128" cy="128" r="96"/></svg> Context Safe · ${historicalSessions.length} in audit`;
      headerBadge.title = historicalSessions.length + " historical session(s) in audit log";
      headerBadge.style.display = "inline-flex";
    } else {
      headerBadge.style.display = "none";
    }
  }

  // 2. Tab Badge: Number of historical + active degraded sessions
  if (tabBadge) {
    const totalDegraded = historicalSessions.length + (currentSession && activeSev !== "safe" ? 1 : 0);
    tabBadge.className = activeSev === "critical" ? "badge amber" : (activeSev === "warning" ? "badge amber" : "badge");
    tabBadge.textContent = totalDegraded;
    tabBadge.style.display = totalDegraded > 0 ? "inline-flex" : "none";
  }

  // Helper: Build Pinned Active Branch Card HTML
  function renderPinnedActiveBranch(curr) {
    if (!curr) return "";
    const thresh = curr.threshold || 200000;
    const color = curr.severity === "critical" ? "var(--accent-red)" : (curr.severity === "warning" ? "var(--accent-camel)" : "var(--accent-green)");
    const statusLabel = curr.drift_message
      ? `<span style="color: ${color}; font-weight: 700;">${curr.drift_message}</span>`
      : (curr.severity === "critical"
          ? `<span style="color: var(--accent-red); font-weight: 700;">Truncated (>${formatCompactNumber(thresh)})</span>`
          : (curr.severity === "warning"
              ? `<span style="color: var(--accent-camel); font-weight: 700;">Degraded (>${formatCompactNumber(0.8 * thresh)})</span>`
              : `<span style="color: var(--accent-green); font-weight: 600;">Safe (+${formatNumber(curr.headroom_to_warning)} to warning)</span>`));
    return `
      <div class="pinned-current-branch status-${curr.severity}">
        <div>
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 3px;">
            <span style="font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; color: ${color}; display: inline-flex; align-items: center; gap: 4px;">
              <svg width="12" height="12" viewBox="0 0 256 256" fill="currentColor"><path d="M208,64a24,24,0,0,0-23.71,20.25l-45.71,9.14A39.9,39.9,0,0,0,104,73.18V64a24,24,0,1,0-16,0v78.82A39.9,39.9,0,0,0,72,160a24,24,0,1,0,24,24,40.09,40.09,0,0,0-8-24V89.82A40,40,0,0,0,135.43,109l45.71-9.14A24,24,0,1,0,208,64ZM96,40a8,8,0,1,1-8,8A8,8,0,0,1,96,40Zm-8,144a8,8,0,1,1,8,8A8,8,0,0,1,88,184Zm120-112a8,8,0,1,1,8,8A8,8,0,0,1,208,72Z"/></svg>
              ${curr.is_subagent ? `SUBAGENT [${escapeHtml(curr.subagent_role || "WORKER")}]:` : `ACTIVE BRANCH:`}
            </span>
            <span class="offender-branch-badge">${escapeHtml(curr.branch)}</span>
            <span style="font-size: 0.75rem; color: var(--text-muted);">• Workspace: ${escapeHtml(curr.workspace)}</span>
            ${curr.is_subagent && curr.parent_title ? `<span style="font-size: 0.75rem; color: var(--text-muted);">• ↳ child of ${escapeHtml(curr.parent_title)}</span>` : ''}
          </div>
          <div style="font-weight: 600; font-size: 0.8125rem; color: var(--text-main);">
            ${escapeHtml(curr.title)}
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 12px;">
          <div style="text-align: right;">
            <div style="font-family: var(--font-mono); font-weight: 700; font-size: 0.875rem; color: ${color};">
              ${formatNumber(curr.tokens)} active tokens ${curr.compaction_epoch && curr.compaction_epoch > 1 ? `<span class="badge" style="font-size: 0.6875rem; padding: 1px 4px; vertical-align: middle;">E${curr.compaction_epoch}</span>` : ''}
            </div>
            <div style="font-size: 0.6875rem;">
              ${statusLabel}
            </div>
          </div>
          ${curr.severity !== "safe" ? `
            <button class="btn-secondary" style="font-size: 0.75rem; padding: 5px 10px; display: inline-flex; align-items: center; gap: 5px;" data-action="copy-handover-summary" data-convo-id="${curr.convo_id}">
              <svg width="12" height="12" viewBox="0 0 256 256" fill="currentColor"><path d="M216,32H88a8,8,0,0,0-8,8V80H40a8,8,0,0,0-8,8V216a8,8,0,0,0,8,8H168a8,8,0,0,0,8-8V176h40a8,8,0,0,0,8-8V40A8,8,0,0,0,216,32ZM160,208H48V96H160Zm48-48H176V88a8,8,0,0,0-8-8H96V48H208Z"/></svg>
              Copy Handover
            </button>
          ` : ''}
        </div>
      </div>
    `;
  }

  // Helper: Build Historical Sessions List HTML
  function renderHistoricalSessionsList(sessList) {
    if (!sessList || sessList.length === 0) return `<div style="font-size: 0.75rem; color: var(--text-muted); padding: 8px 0;">No historical degraded sessions in the last 24 hours.</div>`;
    return sessList.sort((a, b) => b.peakDepth - a.peakDepth).map(s => {
      const rowColor = s.severity === "critical" ? "var(--accent-red)" : "var(--accent-camel)";
      const dotSvg = s.severity === "critical"
        ? `<svg width="8" height="8" viewBox="0 0 256 256" fill="var(--accent-red)"><circle cx="128" cy="128" r="96"/></svg>`
        : `<svg width="8" height="8" viewBox="0 0 256 256" fill="var(--accent-camel)"><circle cx="128" cy="128" r="96"/></svg>`;
      return `
        <div class="offender-session-row">
          <div style="display: flex; align-items: center; gap: 8px; min-width: 0;">
            <span style="flex-shrink: 0;">${dotSvg}</span>
            <div style="min-width: 0;">
              <div style="font-weight: 600; font-size: 0.8125rem; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                ${escapeHtml(s.title || 'Untitled Session')}
              </div>
              <div style="display: flex; align-items: center; gap: 6px; margin-top: 2px;">
                <span class="offender-branch-badge">${escapeHtml(s.branch)}</span>
                <span style="font-size: 0.72rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">• ${escapeHtml(s.workspace)}</span>
              </div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 12px; flex-shrink: 0;">
            <span style="color: ${rowColor}; font-weight: 700; font-size: 0.8125rem; font-family: var(--font-mono);">${formatNumber(s.peakDepth)} tok</span>
            <button class="btn-secondary" style="font-size: 0.7rem; padding: 4px 8px; display: inline-flex; align-items: center; gap: 4px;" data-action="copy-handover-summary" data-convo-id="${s.convo_id}">
              <svg width="10" height="10" viewBox="0 0 256 256" fill="currentColor"><path d="M216,32H88a8,8,0,0,0-8,8V80H40a8,8,0,0,0-8,8V216a8,8,0,0,0,8,8H168a8,8,0,0,0,8-8V176h40a8,8,0,0,0,8-8V40A8,8,0,0,0,216,32ZM160,208H48V96H160Zm48-48H176V88a8,8,0,0,0-8-8H96V48H208Z"/></svg>
              Handover
            </button>
          </div>
        </div>
      `;
    }).join('');
  }

  // 3. Now Tab Status Strip: SHOW ONLY when active session is >= 80% of threshold!
  if (nowContainer) {
    if (!currentSession || currentSession.severity === "safe") {
      nowContainer.style.display = "none";
    } else {
      let iconSvg = "";
      let titleText = "";
      let subText = "";
      const thresh = currentSession.threshold || 200000;
      if (activeSev === "critical") {
        iconSvg = `<svg width="15" height="15" viewBox="0 0 256 256" fill="var(--accent-red)"><path d="M236.8,188.09,149.35,36.22h0a24.76,24.76,0,0,0-42.7,0L19.2,188.09a23.51,23.51,0,0,0,0,23.72A24.35,24.35,0,0,0,40.55,224h174.9a24.35,24.35,0,0,0,21.33-12.19A23.51,23.51,0,0,0,236.8,188.09ZM222.93,204a8.33,8.33,0,0,1-7.48,4H40.55a8.33,8.33,0,0,1-7.48-4,7.48,7.48,0,0,1,0-7.8l87.45-151.87a8.76,8.76,0,0,1,15,0L223,196.2A7.48,7.48,0,0,1,222.93,204ZM120,144V104a8,8,0,0,1,16,0v40a8,8,0,0,1-16,0Zm20,36a12,12,0,1,1-12-12A12,12,0,0,1,140,180Z"/></svg>`;
        titleText = `<span style="color: var(--accent-red);">Active Session Truncated (>${formatCompactNumber(thresh)})</span>`;
        subText = `Memory truncation active. Handover needed immediately. (${historicalSessions.length} historical session${historicalSessions.length === 1 ? '' : 's'} in audit)`;
      } else {
        iconSvg = `<svg width="15" height="15" viewBox="0 0 256 256" fill="var(--accent-camel)"><path d="M236.8,188.09,149.35,36.22h0a24.76,24.76,0,0,0-42.7,0L19.2,188.09a23.51,23.51,0,0,0,0,23.72A24.35,24.35,0,0,0,40.55,224h174.9a24.35,24.35,0,0,0,21.33-12.19A23.51,23.51,0,0,0,236.8,188.09ZM222.93,204a8.33,8.33,0,0,1-7.48,4H40.55a8.33,8.33,0,0,1-7.48-4,7.48,7.48,0,0,1,0-7.8l87.45-151.87a8.76,8.76,0,0,1,15,0L223,196.2A7.48,7.48,0,0,1,222.93,204ZM120,144V104a8,8,0,0,1,16,0v40a8,8,0,0,1-16,0Zm20,36a12,12,0,1,1-12-12A12,12,0,0,1,140,180Z"/></svg>`;
        titleText = `<span style="color: var(--accent-camel);">Active Session Degraded (>${formatCompactNumber(0.8 * thresh)})</span>`;
        subText = `Approaching truncation. Wrap up soon. (${historicalSessions.length} historical session${historicalSessions.length === 1 ? '' : 's'} in audit)`;
      }
      const isExp = window.__contextDrawerExpanded;
      const btnLabel = isExp ? "Close Audit Log" : `View Audit Log (${historicalSessions.length})`;
      nowContainer.innerHTML = `
        <div class="context-safety-strip status-${activeSev}">
          <div class="context-safety-left">
            <span class="context-safety-icon">${iconSvg}</span>
            <span class="context-safety-title">${titleText}</span>
            <span class="context-safety-sub">${subText}</span>
          </div>
          <button class="btn-secondary" style="font-size: 0.75rem; padding: 4px 10px; display: inline-flex; align-items: center; gap: 6px; cursor: pointer;" data-action="toggle-context-audit-drawer">
            <span>${btnLabel}</span>
            <svg width="10" height="10" viewBox="0 0 256 256" fill="currentColor" style="transform: ${isExp ? 'rotate(180deg)' : 'none'}; transition: transform 0.2s;"><path d="M213.66,101.66l-80,80a8,8,0,0,1-11.32,0l-80-80A8,8,0,0,1,53.66,90.34L128,164.69l74.34-74.35a8,8,0,0,1,11.32,11.32Z"/></svg>
          </button>
        </div>
        ${isExp ? `
          <div class="context-safety-accordion">
            ${renderPinnedActiveBranch(currentSession)}
            <div style="font-size: 0.6875rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 10px 0 6px 0;">
              Historical Sessions (Past 24 Hours)
            </div>
            <div>
              ${renderHistoricalSessionsList(historicalSessions)}
            </div>
          </div>
        ` : ''}
      `;
      nowContainer.style.display = "block";
    }
  }

  // 4. Sessions Tab Widget: Render as a collapsible accordion!
  if (sessionsContainer) {
    if ((!sessions || sessions.length === 0) && (!currentSession || currentSession.severity === "safe")) {
      sessionsContainer.style.display = "none";
    } else {
      window.__sessionsAuditAccordionOpen = Boolean(window.__sessionsAuditAccordionOpen);
      const isAccordionOpen = window.__sessionsAuditAccordionOpen;
      const badgeSevClass = activeSev === 'critical' ? 'red' : (activeSev === 'warning' ? 'amber' : 'green');
      const badgeText = activeSev === 'safe' ? 'Active Safe' : (activeSev === 'critical' ? 'Active Truncated' : 'Active Degraded');
      const btnLabel = isAccordionOpen ? "Collapse Audit" : "Expand Audit";

      sessionsContainer.innerHTML = `
        <div class="section-card" style="border: 1px solid var(--card-border); background: var(--card-bg); margin-bottom: 20px;">
          <div class="section-header" style="margin-bottom: 0; padding-bottom: ${isAccordionOpen ? '12px' : '0'}; border-bottom: ${isAccordionOpen ? '1px solid var(--card-border)' : 'none'}; display: flex; justify-content: space-between; align-items: center;">
            <div>
              <h3 class="section-title" style="display: flex; align-items: center; gap: 8px; font-size: 1rem; margin: 0;">
                <span>Context Boundary &amp; Truncation Audit (${historicalSessions.length} in audit)</span>
                <span class="badge ${badgeSevClass}">${badgeText}</span>
              </h3>
              ${isAccordionOpen ? `
                <p style="font-size: 0.8125rem; color: var(--text-muted); margin-top: 4px;">
                  Audit of conversations that have approached or crossed memory truncation thresholds in the past 24 hours.
                </p>
              ` : ''}
            </div>
            <button class="btn-secondary" style="font-size: 0.75rem; padding: 4px 10px; display: inline-flex; align-items: center; gap: 6px; cursor: pointer;" data-action="toggle-sessions-audit-accordion">
              <span>${btnLabel}</span>
              <svg width="10" height="10" viewBox="0 0 256 256" fill="currentColor" style="transform: ${isAccordionOpen ? 'rotate(180deg)' : 'none'}; transition: transform 0.2s;"><path d="M213.66,101.66l-80,80a8,8,0,0,1-11.32,0l-80-80A8,8,0,0,1,53.66,90.34L128,164.69l74.34-74.35a8,8,0,0,1,11.32,11.32Z"/></svg>
            </button>
          </div>
          ${isAccordionOpen ? `
            <div style="padding-top: 14px;">
              ${renderPinnedActiveBranch(currentSession)}
              <div style="font-size: 0.6875rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin: 14px 0 8px 0;">
                Historical Offenders (Past 24 Hours)
              </div>
              <div>
                ${renderHistoricalSessionsList(historicalSessions)}
              </div>
            </div>
          ` : ''}
        </div>
      `;
      sessionsContainer.style.display = "block";
    }
  }
}

// Handlers for audit accordion
window.toggleSessionsAuditAccordion = function() {
  window.__sessionsAuditAccordionOpen = !window.__sessionsAuditAccordionOpen;
  updateDegradedUI(window.__lastDegradedSessions || [], window.__lastCurrentSession || null);
};

// Delegated click handler for audit accordion
document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.getAttribute("data-action");
  if (action === "toggle-sessions-audit-accordion") {
    if (typeof window.toggleSessionsAuditAccordion === "function") window.toggleSessionsAuditAccordion();
  }
});
window.copyHandoverSummary = function(convoId, clickedEl) {
  const convo = (typeof activeFilteredConversations !== "undefined" && activeFilteredConversations.find(c => c.convo_id === convoId)) || 
                (globalDashboardData && globalDashboardData.conversations && globalDashboardData.conversations.find(c => c.convo_id === convoId)) ||
                (window.__lastDegradedSessions && window.__lastDegradedSessions.find(c => c.convo_id === convoId)) ||
                (window.__lastCurrentSession && window.__lastCurrentSession.convo_id === convoId ? window.__lastCurrentSession : null);
  if (!convo) return;
  const text = `I am starting a fresh thread for workspace: ${convo.workspace_name || convo.workspace}. 
Branch: ${convo.git_branch || convo.branch || 'main'}.
We were working on: "${convo.title}". 
Please analyze the current state of the workspace and propose our next steps.`;
  navigator.clipboard.writeText(text).then(() => {
    // Temporary feedback
    const btn = clickedEl || (typeof event !== "undefined" && event && event.target ? event.target.closest("button") : null);
    if (btn) {
      const origHtml = btn.innerHTML;
      btn.textContent = "Copied!";
      setTimeout(() => btn.innerHTML = origHtml, 2000);
    }
  }).catch(err => {
    console.error('Could not copy text: ', err);
  });
};