// ==========================================
// Dashboard: Projects & Workspaces
// ==========================================

function renderPortfolioView() {
  const projects = (globalDashboardData && globalDashboardData.projects) || [];
  const kpisContainer = document.getElementById("projects-portfolio-kpis");
  const tbody = document.getElementById("projects-table-tbody");

  if (!kpisContainer || !tbody) return;

  // Calculate aggregate portfolio metrics
  const totalProjects = projects.length;
  let totalBranches = 0;
  let totalInputTokens = 0;
  let totalCachedTokens = 0;
  let totalOutputTokens = 0;
  let totalCoveredTurns = 0;
  let totalOverageTurns = 0;
  let totalOverageCredits = 0;
  let totalOverageUsd = 0.0;
  let totalOverageGbp = 0.0;
  let totalAvoidedUsd = 0.0;
  let totalAvoidedGbp = 0.0;

  projects.forEach(p => {
    const branches = p.branches || [];
    totalBranches += branches.length;
    totalInputTokens += (p.total_input_tokens || 0);
    totalCachedTokens += (p.cached_tokens || 0);
    totalOutputTokens += (p.total_output_tokens || 0);
    totalCoveredTurns += (p.subscription_covered_turns !== undefined ? p.subscription_covered_turns : p.turn_count || 0);
    totalOverageTurns += (p.overage_turns || 0);
    totalOverageCredits += (p.actual_overage_credits || 0);
    totalOverageUsd += (p.actual_overage_usd || 0.0);
    totalOverageGbp += (p.actual_overage_gbp || 0.0);
    const pAvoidedUsd = p.avoided_cost_usd !== undefined ? p.avoided_cost_usd : (p.estimated_cost_usd || 0.0);
    const pAvoidedGbp = p.avoided_cost_gbp !== undefined ? p.avoided_cost_gbp : (p.estimated_cost_gbp || 0.0);
    totalAvoidedUsd += pAvoidedUsd;
    totalAvoidedGbp += pAvoidedGbp;
  });

  const totalTurns = totalCoveredTurns + totalOverageTurns;
  const portfolioCoveragePct = totalTurns > 0
    ? ((totalCoveredTurns / totalTurns) * 100.0).toFixed(1)
    : "100.0";

  // Render Portfolio KPIs
  kpisContainer.innerHTML = `
    <div class="kpi-card" id="projects-kpi-monitored">
      <div class="kpi-label">Monitored Projects</div>
      <div class="kpi-value highlight-camel">${formatNumber(totalProjects)}</div>
      <div class="kpi-sub">Distinct repository workspaces</div>
    </div>
    <div class="kpi-card" id="projects-kpi-branches">
      <div class="kpi-label">Active Git Branches</div>
      <div class="kpi-value highlight-purple">${formatNumber(totalBranches)}</div>
      <div class="kpi-sub">Tracked feature &amp; mainlines</div>
    </div>
    <div class="kpi-card" id="projects-kpi-coverage">
      <div class="kpi-label">Subscription Coverage</div>
      <div class="kpi-value highlight-green">${portfolioCoveragePct}%</div>
      <div class="kpi-sub">${formatNumber(totalCoveredTurns)} of ${formatNumber(totalTurns)} turns at £0 marginal cost</div>
    </div>
    <div class="kpi-card" id="projects-kpi-avoided">
      <div class="kpi-label">Total Avoided Cost</div>
      <div class="kpi-value highlight-green">${formatCurrency(totalAvoidedUsd, totalAvoidedGbp, 2)}</div>
      <div class="kpi-sub">Plan Value (vs. ${formatCurrency(totalOverageUsd, totalOverageGbp, 2)} overage spend)</div>
    </div>
  `;

  // Render Projects Table
  tbody.innerHTML = "";
  if (projects.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No project telemetry found in recorded conversations.</td></tr>';
    return;
  }

  projects.forEach((p, pIdx) => {
    const branches = p.branches || [];
    const tr = document.createElement("tr");
    tr.style.cursor = "pointer";

    const pathSnippet = p.workspace_path
      ? `<span style="font-size: 0.75rem; color: var(--text-muted); display: block; margin-top: 3px; font-family: ui-monospace, monospace;">${escapeHtml(p.workspace_path)}</span>`
      : "";

    const pOvgCredits = p.actual_overage_credits || 0;
    const pOvgUsd = p.actual_overage_usd || 0.0;
    const pOvgGbp = p.actual_overage_gbp || 0.0;
    const pAvoidedUsd = p.avoided_cost_usd !== undefined ? p.avoided_cost_usd : (p.estimated_cost_usd || 0.0);
    const pAvoidedGbp = p.avoided_cost_gbp !== undefined ? p.avoided_cost_gbp : (p.estimated_cost_gbp || 0.0);
    const pCovPct = p.subscription_covered_pct !== undefined ? p.subscription_covered_pct : 100.0;

    let coverageBadge = '';
    if (pOvgCredits === 0) {
      coverageBadge = '<span class="code-pill" style="color: var(--accent-green); background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3); font-weight: 600;">100% Covered</span>';
    } else {
      coverageBadge = `<span class="code-pill" style="color: var(--accent-amber); background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); font-weight: 600;">${pCovPct.toFixed(1)}% Covered (${formatNumber(p.overage_turns)} in Overage)</span>`;
    }

    let overageDisplay = '';
    if (pOvgCredits === 0) {
      overageDisplay = `<span style="color: var(--text-muted); font-size: 0.8125rem;">£0.00 <span style="font-size: 0.75rem;">(0 credits)</span></span>`;
    } else {
      overageDisplay = `<strong style="color: var(--accent-amber); font-size: 0.875rem;">${formatCurrency(pOvgUsd, pOvgGbp, 2)}</strong><span style="font-size: 0.75rem; color: var(--accent-amber); display: block;">${formatNumber(pOvgCredits)} credits burned</span>`;
    }

    tr.innerHTML = `
      <td>
        <strong style="color: var(--text-main);">${escapeHtml(p.project_name)}</strong>
        ${pathSnippet}
      </td>
      <td><span class="code-pill">${branches.length} ${branches.length === 1 ? 'branch' : 'branches'}</span></td>
      <td>${formatNumber(p.turn_count)}</td>
      <td>
        ${formatNumber(p.total_input_tokens)}
        <span style="font-size: 0.75rem; color: var(--text-muted); display: block;">${formatNumber(p.cached_tokens)} cached</span>
      </td>
      <td><strong class="highlight-green">${(p.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></td>
      <td>${coverageBadge}</td>
      <td>${overageDisplay}</td>
      <td>
        <strong class="highlight-green" style="font-size: 0.875rem;">${formatCurrency(pAvoidedUsd, pAvoidedGbp, 2)}</strong>
        <span style="font-size: 0.75rem; color: var(--text-muted); display: block;">API Equivalent Value</span>
      </td>
      <td>
        <button class="tab-btn" style="padding: 4px 8px; font-size: 0.75rem;" data-action="toggle-project-branches" data-project-idx="${pIdx}">
          <span id="btn-branch-arrow-${pIdx}">▼</span> Branches
        </button>
      </td>
    `;

    tr.addEventListener("click", () => toggleProjectBranches(pIdx));
    tbody.appendChild(tr);

    // Branch drawer row
    const drawerTr = document.createElement("tr");
    drawerTr.id = `project-branches-${pIdx}`;
    drawerTr.className = "branch-drawer-row";
    drawerTr.style.display = "none";
    drawerTr.style.background = "var(--th-bg)";

    let branchesHtml = "";
    const sortedBranches = [...branches].sort((a, b) => {
      const tsA = a.last_active_timestamp || "";
      const tsB = b.last_active_timestamp || "";
      if (tsA && tsB) return tsB.localeCompare(tsA);
      if (tsB) return 1;
      if (tsA) return -1;
      return (b.total_input_tokens + b.total_output_tokens) - (a.total_input_tokens + a.total_output_tokens);
    });

    sortedBranches.forEach(b => {
      const bOvgCredits = b.actual_overage_credits || 0;
      const bOvgUsd = b.actual_overage_usd || 0.0;
      const bOvgGbp = b.actual_overage_gbp || 0.0;
      const bAvoidedUsd = b.avoided_cost_usd !== undefined ? b.avoided_cost_usd : (b.estimated_cost_usd || 0.0);
      const bAvoidedGbp = b.avoided_cost_gbp !== undefined ? b.avoided_cost_gbp : (b.estimated_cost_gbp || 0.0);

      let bStatusBadge = '';
      if (bOvgCredits === 0) {
        bStatusBadge = '<span class="code-pill" style="color: var(--accent-green); font-size: 0.75rem; background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.25);">100% Covered (£0.00)</span>';
      } else {
        bStatusBadge = `<span class="code-pill" style="color: var(--accent-amber); font-size: 0.75rem; background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.25);">${formatNumber(bOvgCredits)} credits (${formatCurrency(bOvgUsd, bOvgGbp, 2)})</span>`;
      }

      const timeStr = b.last_active_timestamp ? formatUkTimestamp(b.last_active_timestamp) : "";
      const timePill = timeStr ? `<span class="branch-time-pill" title="Last Active: ${timeStr}">${timeStr}</span>` : "";

      branchesHtml += `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid var(--card-border); gap: 16px; flex-wrap: wrap;">
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <span class="code-pill" style="font-weight: 600; color: var(--accent-purple);">${escapeHtml(b.branch_name)}</span>
            ${timePill}
            <span style="font-size: 0.75rem; color: var(--text-muted);">${formatNumber(b.conversation_count)} sessions • ${formatNumber(b.turn_count)} turns</span>
          </div>
          <div style="display: flex; align-items: center; gap: 16px; font-size: 0.8125rem;">
            <span>Input: <strong>${formatNumber(b.total_input_tokens)}</strong></span>
            <span class="highlight-green">Cache: <strong>${(b.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></span>
            ${bStatusBadge}
            <span class="highlight-green" style="font-weight: 700;">Avoided: ${formatCurrency(bAvoidedUsd, bAvoidedGbp, 2)}</span>
          </div>
        </div>
      `;
    });

    drawerTr.innerHTML = `
      <td colspan="9" style="padding: 12px 16px;">
        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 8px; font-weight: 600; display: flex; justify-content: space-between; align-items: center;">
          <span>Branch Cost Attribution: ${escapeHtml(p.project_name)}</span>
          <span style="font-weight: 500; font-size: 0.6875rem; text-transform: none; color: var(--accent-purple);">Sorted: Most Recent First ↓</span>
        </div>
        <div style="border: 1px solid var(--card-border); border-radius: 8px; overflow: hidden; background: var(--card-bg);">
          ${branchesHtml}
        </div>
      </td>
    `;
    tbody.appendChild(drawerTr);
  });
}

function toggleProjectBranches(pIdx) {
  const drawer = document.getElementById(`project-branches-${pIdx}`);
  const arrow = document.getElementById(`btn-branch-arrow-${pIdx}`);
  if (!drawer) return;
  if (drawer.style.display === "none") {
    drawer.style.display = "table-row";
    if (arrow) arrow.textContent = "▲";
  } else {
    drawer.style.display = "none";
    if (arrow) arrow.textContent = "▼";
  }
}

function renderModelMatrix(windowKey) {
  const quotas = (globalDashboardData && globalDashboardData.quotas) || {};
  const winObj = windowKey === "5h" ? (quotas.rolling_5h || {}) : (quotas.weekly_cycle || quotas.rolling_1w || {});
  const models = winObj.by_model || [];

  const tbody = document.getElementById("models-tbody");
  tbody.innerHTML = "";

  if (models.length === 0) {
    const label = windowKey === "5h" ? "5-hour" : "weekly cycle";
    tbody.innerHTML = `<tr><td colspan="9" class="empty-state">No model activity recorded in the ${label} window.</td></tr>`;
    return;
  }

  models.forEach(m => {
    const tr = document.createElement("tr");
    const mAvoidedUsd = m.avoided_cost_usd !== undefined ? m.avoided_cost_usd : (m.imputed_value_usd || 0.0);
    const mAvoidedGbp = m.avoided_cost_gbp !== undefined ? m.avoided_cost_gbp : (m.imputed_value_gbp || 0.0);
    tr.innerHTML = `
      <td><strong>${escapeHtml(m.model_name)}</strong><br><span style="font-size: 0.75rem; color: var(--text-muted);">ID: ${m.model_id}</span></td>
      <td>${formatNumber(m.turn_count)}</td>
      <td class="highlight-camel">${formatNumber(m.prompt_tokens_uncached)}</td>
      <td class="highlight-green">${formatNumber(m.cached_tokens)}</td>
      <td>${formatNumber(m.total_input_tokens)}</td>
      <td><strong>${(m.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></td>
      <td>${formatNumber(m.output_tokens_total)} <span style="font-size: 0.75rem; color: var(--accent-purple);">(${formatNumber(m.thinking_tokens)} thk)</span></td>
      <td><strong style="color: var(--camel-400);">${formatNumber(m.total_processed_tokens)}</strong></td>
      <td><strong class="highlight-green">${formatCurrency(mAvoidedUsd, mAvoidedGbp, 2)}</strong></td>
    `;
    tbody.appendChild(tr);
  });
}
