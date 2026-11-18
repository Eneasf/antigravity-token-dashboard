/**
 * Sessions Tree Aggregation & Accordion UI Component
 * Milestone D (Phase 3: Sessions Explorer Tree UI)
 *
 * Renders expandable parent-child accordion rows in tree view.
 * Renders badges/chips showing cumulative tree metrics (tree_total_tokens, tree_total_cost_usd,
 * tree_children_count) alongside direct metrics.
 * Indented child session rows with role/subagent badges and generation indicators.
 * Keeps dashboard/js/sessions.js strictly <= 750 lines (ADR-066).
 */

var expandedTreeConvoIds = new Set();

/**
 * Resolve direct children for a conversation session.
 * Inspects conversation.child_ids, searches globalDashboardData.conversations for matching parent_convo_id,
 * and falls back to matching nodes in globalDashboardData.swarms if subagents are only in DAG telemetry.
 */
function getChildConversations(parentConvo) {
  if (!parentConvo) return [];
  const parentId = String(parentConvo.convo_id || parentConvo.id || "").trim();
  if (!parentId) return [];

  const allConvos = (typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.conversations)
    ? globalDashboardData.conversations
    : [];

  const convoMap = new Map();
  allConvos.forEach(c => {
    const cid = String(c.convo_id || c.id || "").trim();
    if (cid) convoMap.set(cid, c);
  });

  const matched = [];
  const matchedIds = new Set();

  // 1. Direct child_ids array if present
  if (Array.isArray(parentConvo.child_ids) && parentConvo.child_ids.length > 0) {
    parentConvo.child_ids.forEach(chId => {
      const chIdStr = String(chId).trim();
      if (!chIdStr || chIdStr === parentId || matchedIds.has(chIdStr)) return;
      if (convoMap.has(chIdStr)) {
        matched.push(convoMap.get(chIdStr));
        matchedIds.add(chIdStr);
      }
    });
  }

  // 2. Scan all conversations for parent_convo_id === parentId
  allConvos.forEach(c => {
    const cid = String(c.convo_id || c.id || "").trim();
    const pid = String(c.parent_convo_id || c.parent_id || "").trim();
    if (pid === parentId && cid !== parentId && !matchedIds.has(cid)) {
      matched.push(c);
      matchedIds.add(cid);
    }
  });

  // 3. Fallback: inspect swarm nodes if subagents are in swarm topologies
  if (matched.length === 0 && typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.swarms) {
    const swarmsList = globalDashboardData.swarms.swarms || [];
    for (const sw of swarmsList) {
      const nodes = sw.nodes || [];
      const hasParent = nodes.some(n => String(n.id).trim() === parentId && n.is_root);
      if (hasParent) {
        nodes.forEach(n => {
          const nid = String(n.id).trim();
          if (nid && nid !== parentId && !matchedIds.has(nid)) {
            // Synthesize child conversation record from swarm node
            const costUsd = n.cost_usd || 0;
            const costGbp = n.cost_gbp !== undefined ? n.cost_gbp : (costUsd * 0.79);
            matched.push({
              convo_id: nid,
              title: n.role || "Subagent Worker",
              workspace: parentConvo.workspace || n.workspace || (sw && (sw.workspace_name || sw.workspace)) || "Unknown",
              turn_count: n.turns || 1,
              total_input_tokens: n.input_tokens || n.total_tokens || 0,
              cached_tokens: n.cached_tokens || 0,
              cache_hit_ratio_pct: n.cache_hit_pct || 0,
              subscription_covered_pct: 100,
              actual_overage_credits: 0,
              avoided_cost_usd: costUsd,
              avoided_cost_gbp: costGbp,
              is_subagent: true,
              subagent_role: n.role || "Worker",
              model_id: n.model_id,
              model_name: n.model_name,
              generation: (n.model_id === "1198" || n.model_id === "1322") ? 2 : 1
            });
            matchedIds.add(nid);
          }
        });
      }
    }
  }

  return matched;
}

/**
 * Render generation indicator badge for child subagent.
 */
function renderGenerationBadge(conv) {
  if (!conv) return "";
  const mId = String(conv.model_id || "").trim();
  const mName = String(conv.model_name || "").toLowerCase();

  // Model 1198 (Flash Lite Gen 2) or Model 1322 (Fast Agent Gen 2)
  if (mId === "1198" || mId === "1322" || mName.includes("gen 2") || conv.generation === 2) {
    return '<span class="badge-gen badge-gen-2" title="Generation 2 Model Architecture (Adaptive Reasoning / Fast Autonomous)">Gen 2</span>';
  }
  // Model 1050 (Flash Lite Gen 1) or Model 1132 (Fast Agent Gen 1)
  if (mId === "1050" || mId === "1132" || mName.includes("gen 1") || conv.generation === 1) {
    return '<span class="badge-gen badge-gen-1" title="Generation 1 Model Architecture">Gen 1</span>';
  }
  // Model 1318 / 1319 / 1320 (Gemini 3.8 / 3.7)
  if (["1318", "1319", "1320", "1298", "1299", "1300"].includes(mId)) {
    return '<span class="badge-gen badge-gen-preview" title="Gemini 3.8 / 3.7 Preview Lineage">Flash 3.8</span>';
  }
  return "";
}

/**
 * Toggle row accordion expansion in Tree View.
 */
function toggleTreeRow(convoId, event) {
  if (event) {
    event.stopPropagation();
  }
  if (!convoId) return;

  if (expandedTreeConvoIds.has(convoId)) {
    expandedTreeConvoIds.delete(convoId);
  } else {
    expandedTreeConvoIds.add(convoId);
  }

  const listToRender = (typeof activeFilteredConversations !== "undefined" && activeFilteredConversations)
    ? activeFilteredConversations
    : ((typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.conversations) || []);

  // Re-render table to update accordion DOM while preserving page and scroll
  if (typeof renderConversationsTable === "function") {
    renderConversationsTable(listToRender);
  }
}

/**
 * Main Tree View table renderer for #conversations-tbody.
 */
function renderTreeConversationsTable(list) {
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
    pageInfo.textContent = `Page ${convoCurrentPage + 1} of ${totalPages} (${totalItems} root sessions)`;
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
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No conversations match active filters.</td></tr>';
    return;
  }

  pageItems.forEach(c => {
    const isExpanded = expandedTreeConvoIds.has(c.convo_id);
    const children = getChildConversations(c);
    const childCount = (c.tree_children_count !== undefined && c.tree_children_count > 0)
      ? c.tree_children_count
      : children.length;
    const hasChildren = childCount > 0;

    // Currency and overage
    const cOvgCredits = c.actual_overage_credits || 0;
    const cOvgUsd = c.actual_overage_usd || 0.0;
    const cOvgGbp = c.actual_overage_gbp || 0.0;
    const cAvoidedUsd = c.avoided_cost_usd !== undefined ? c.avoided_cost_usd : (c.estimated_cost_usd || 0.0);
    const cAvoidedGbp = c.avoided_cost_gbp !== undefined ? c.avoided_cost_gbp : (c.estimated_cost_gbp || 0.0);
    const cCovPct = c.subscription_covered_pct !== undefined ? c.subscription_covered_pct : 100.0;

    // Tree Rollups
    const treeCostUsd = (c.tree_total_cost_usd !== undefined && c.tree_total_cost_usd > 0)
      ? c.tree_total_cost_usd
      : (cAvoidedUsd + children.reduce((acc, ch) => acc + (ch.avoided_cost_usd || ch.estimated_cost_usd || 0), 0));
    const treeCostGbp = (c.tree_total_cost_gbp !== undefined && c.tree_total_cost_gbp > 0)
      ? c.tree_total_cost_gbp
      : (treeCostUsd * 0.79);

    const treeInputTokens = (c.tree_total_input_tokens !== undefined && c.tree_total_input_tokens > 0)
      ? c.tree_total_input_tokens
      : (c.total_input_tokens + children.reduce((acc, ch) => acc + (ch.total_input_tokens || ch.input_tokens || 0), 0));

    const treeTotalTokens = treeInputTokens + (c.tree_total_output_tokens || c.total_output_tokens || 0);

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

    const agName = c.agent_name || "default";
    let roleBadge = '';
    if (agName === "auditor") {
      roleBadge = '<span class="badge-agent badge-agent-auditor">Auditor</span>';
    } else if (agName === "implementer") {
      roleBadge = '<span class="badge-agent badge-agent-implementer">Implementer</span>';
    } else {
      roleBadge = '<span class="badge-agent badge-agent-general">General</span>';
    }

    // Cumulative Tree Badge
    let treeBadge = '';
    if (hasChildren) {
      treeBadge = `
        <span class="badge-agent badge-tree-rollup" title="Cumulative tree burn: ${formatNumber(treeTotalTokens)} tokens across ${childCount} subagents">
          ${childCount} subagent${childCount > 1 ? 's' : ''} | Tree: ${formatNumber(treeTotalTokens)} toks • ${formatCurrency(treeCostUsd, treeCostGbp, 2)}
        </span>
        <span class="tree-direct-sub" style="font-size: var(--font-xs); color: var(--text-muted);">
          (Direct: ${formatNumber(c.total_input_tokens + (c.total_output_tokens || 0))} • ${formatCurrency(cAvoidedUsd, cAvoidedGbp, 2)})
        </span>
      `;
    }

    const tr = document.createElement("tr");
    tr.className = `convo-row tree-parent-row ${isExpanded ? "expanded" : ""}`;
    tr.setAttribute("data-convo-id", c.convo_id);
    tr.style.cursor = "pointer";

    // Toggle button markup
    const toggleButtonHtml = hasChildren
      ? `<button type="button" class="tree-toggle-btn tactile-press ${isExpanded ? 'open' : ''}" data-action="toggle-tree-row" data-convo-id="${c.convo_id}" aria-expanded="${isExpanded ? 'true' : 'false'}" aria-label="Toggle ${childCount} subagents for ${escapeHtml(c.title || 'conversation')}">
           <svg class="tree-chevron ${isExpanded ? 'open' : ''}" width="12" height="12" viewBox="0 0 256 256" fill="currentColor" aria-hidden="true">
             <path d="M181.66,133.66l-80,80a8,8,0,0,1-11.32-11.32L164.69,128,90.34,53.66a8,8,0,0,1,11.32-11.32l80,80A8,8,0,0,1,181.66,133.66Z"/>
           </svg>
         </button>`
      : `<span class="tree-toggle-spacer" aria-hidden="true" style="display: inline-block; width: 20px; flex-shrink: 0;"></span>`;

    // Input & Cost columns in Tree mode
    const inputDisplay = hasChildren
      ? `<div>
           <strong style="color: var(--text-main);">${formatNumber(treeInputTokens)}</strong>
           <span style="font-size: 0.72rem; color: var(--text-muted); display: block;">direct: ${formatNumber(c.total_input_tokens)}</span>
           <span style="font-size: 0.72rem; color: var(--text-muted); display: block;">${formatNumber(c.cached_tokens)} cached</span>
         </div>`
      : `<div>
           ${formatNumber(c.total_input_tokens)}
           <span style="font-size: 0.75rem; color: var(--text-muted); display: block;">${formatNumber(c.cached_tokens)} cached</span>
         </div>`;

    const costDisplay = hasChildren
      ? `<div>
           <strong class="highlight-green">${formatCurrency(treeCostUsd, treeCostGbp, 2)}</strong>
           <span style="font-size: 0.72rem; color: var(--text-muted); display: block;">direct: ${formatCurrency(cAvoidedUsd, cAvoidedGbp, 2)}</span>
         </div>`
      : `<strong class="highlight-green">${formatCurrency(cAvoidedUsd, cAvoidedGbp, 2)}</strong>`;

    tr.innerHTML = `
      <td>
        <div style="display: flex; align-items: flex-start; gap: 8px;">
          ${toggleButtonHtml}
          <div style="display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1;">
            <strong>${escapeHtml(c.title || "Untitled")}</strong>
            <span style="font-size: 0.72rem; color: var(--text-muted); font-family: monospace;">${c.convo_id}</span>
            <div style="margin-top: 4px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
              ${roleBadge}
              ${treeBadge}
            </div>
          </div>
        </div>
      </td>
      <td><span class="code-pill">${escapeHtml(c.workspace || "Unknown")}</span></td>
      <td>${formatNumber(c.turn_count)}</td>
      <td>${inputDisplay}</td>
      <td><strong class="highlight-green">${(c.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></td>
      <td>${coverageBadge}</td>
      <td>${overageDisplay}</td>
      <td>${costDisplay}</td>
    `;

    tr.addEventListener("click", (evt) => {
      // If click was on toggle button, do not open turn drawer
      if (evt.target.closest('[data-action="toggle-tree-row"]')) return;
      const convoFilter = document.getElementById("convo-filter");
      if (convoFilter) convoFilter.value = c.convo_id;
      if (typeof activeConvoForTurns !== "undefined") activeConvoForTurns = c;
      if (typeof renderTurnsTable === "function") renderTurnsTable(c);
      if (typeof openTurnsDrawer === "function") openTurnsDrawer(c);
    });

    tbody.appendChild(tr);

    // If expanded, render child rows
    if (isExpanded && hasChildren) {
      children.forEach((child, chIdx) => {
        const chTr = document.createElement("tr");
        chTr.className = "tree-child-row";
        chTr.setAttribute("data-convo-id", child.convo_id);
        chTr.setAttribute("data-parent-id", c.convo_id);
        chTr.style.cursor = "pointer";

        const chAvoidedUsd = child.avoided_cost_usd !== undefined ? child.avoided_cost_usd : (child.estimated_cost_usd || 0.0);
        const chAvoidedGbp = child.avoided_cost_gbp !== undefined ? child.avoided_cost_gbp : (child.estimated_cost_gbp || 0.0);
        const chCovPct = child.subscription_covered_pct !== undefined ? child.subscription_covered_pct : 100.0;
        const chOvgCredits = child.actual_overage_credits || 0;
        const chOvgUsd = child.actual_overage_usd || 0.0;
        const chOvgGbp = child.actual_overage_gbp || 0.0;

        let chCovBadge = '';
        if (chOvgCredits === 0) {
          chCovBadge = '<span class="code-pill" style="color: var(--accent-green); background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3); font-size: var(--font-xs); font-weight: 600;">100% Covered</span>';
        } else {
          chCovBadge = `<span class="code-pill" style="color: var(--accent-amber); background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); font-size: var(--font-xs); font-weight: 600;">${chCovPct.toFixed(0)}%</span>`;
        }

        let chOverageDisplay = '';
        if (chOvgCredits === 0) {
          chOverageDisplay = `<span style="color: var(--text-muted); font-size: 0.75rem;">${formatCurrency(0, 0, 2)}</span>`;
        } else {
          chOverageDisplay = `<strong style="color: var(--accent-amber); font-size: 0.8125rem;">${formatCurrency(chOvgUsd, chOvgGbp, 2)}</strong>`;
        }

        const roleName = escapeHtml(child.subagent_role || child.subagent_type || "Worker");
        const genBadge = renderGenerationBadge(child);
        const childTitle = child.title && child.title !== child.convo_id ? child.title : `Subagent ${roleName} #${chIdx + 1}`;

        chTr.innerHTML = `
          <td>
            <div class="tree-child-cell" style="display: flex; align-items: flex-start; gap: 8px; padding-left: 28px;">
              <span class="tree-branch-connector" aria-hidden="true">↳</span>
              <div style="display: flex; flex-direction: column; gap: 2px; min-width: 0;">
                <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                  <strong style="font-size: 0.8125rem; color: var(--text-main);">${escapeHtml(childTitle)}</strong>
                  <span class="badge-agent badge-subagent-pill" style="font-size: var(--font-xs);">${roleName}</span>
                  ${genBadge}
                </div>
                <span style="font-size: var(--font-xs); color: var(--text-muted); font-family: monospace;">${child.convo_id}</span>
              </div>
            </div>
          </td>
          <td><span class="code-pill" style="font-size: var(--font-xs);">${escapeHtml(child.workspace || c.workspace || "Unknown")}</span></td>
          <td style="font-size: 0.8125rem;">${formatNumber(child.turn_count || 1)}</td>
          <td style="font-size: 0.8125rem;">
            ${formatNumber(child.total_input_tokens || child.total_tokens || 0)}
            ${child.cached_tokens ? `<span style="font-size: var(--font-xs); color: var(--text-muted); display: block;">${formatNumber(child.cached_tokens)} cached</span>` : ''}
          </td>
          <td><strong class="highlight-green" style="font-size: 0.8125rem;">${(child.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></td>
          <td>${chCovBadge}</td>
          <td>${chOverageDisplay}</td>
          <td><strong class="highlight-green" style="font-size: 0.8125rem;">${formatCurrency(chAvoidedUsd, chAvoidedGbp, 2)}</strong></td>
        `;

        chTr.addEventListener("click", () => {
          const convoFilter = document.getElementById("convo-filter");
          if (convoFilter) convoFilter.value = child.convo_id;
          if (typeof activeConvoForTurns !== "undefined") activeConvoForTurns = child;
          if (typeof renderTurnsTable === "function") renderTurnsTable(child);
          if (typeof openTurnsDrawer === "function") openTurnsDrawer(child);
        });

        tbody.appendChild(chTr);
      });
    }
  });
}

// Delegated click handler for tree actions
document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action]");
  if (!target) return;
  const action = target.getAttribute("data-action");

  if (action === "toggle-tree-row") {
    const convoId = target.getAttribute("data-convo-id");
    if (convoId) {
      toggleTreeRow(convoId, event);
    }
  } else if (action === "toggle-sessions-view") {
    const mode = target.getAttribute("data-view-mode");
    if (mode && typeof window.setSessionsViewMode === "function") {
      window.setSessionsViewMode(mode);
    }
  }
});

// Window exports
if (typeof window !== "undefined") {
  window.expandedTreeConvoIds = expandedTreeConvoIds;
  window.getChildConversations = getChildConversations;
  window.renderGenerationBadge = renderGenerationBadge;
  window.toggleTreeRow = toggleTreeRow;
  window.renderTreeConversationsTable = renderTreeConversationsTable;
}
