// ==========================================
// Dashboard: Subagent Swarms & Tool Analytics
// ==========================================

var activeSwarmList = [];
var selectedSwarmId = null;
var activeSwarmProjectFilter = "all";
var activeSwarmSortOrder = "recent";
var activeSwarmsSubview = "dag";

function switchSwarmsSubview(subview) {
  activeSwarmsSubview = (subview === "skills") ? "skills" : "dag";
  const btnDag = document.getElementById("btn-subview-dag");
  const btnSkills = document.getElementById("btn-subview-skills");
  const viewDag = document.getElementById("swarms-subview-dag");
  const viewSkills = document.getElementById("swarms-subview-skills");

  if (btnDag) {
    btnDag.classList.toggle("active", activeSwarmsSubview === "dag");
    btnDag.setAttribute("aria-selected", activeSwarmsSubview === "dag" ? "true" : "false");
  }
  if (btnSkills) {
    btnSkills.classList.toggle("active", activeSwarmsSubview === "skills");
    btnSkills.setAttribute("aria-selected", activeSwarmsSubview === "skills" ? "true" : "false");
  }
  if (viewDag) viewDag.style.display = (activeSwarmsSubview === "dag") ? "block" : "none";
  if (viewSkills) {
    viewSkills.style.display = (activeSwarmsSubview === "skills") ? "block" : "none";
    if (activeSwarmsSubview === "skills" && typeof renderSkillsSubView === "function" && typeof globalDashboardData !== "undefined" && globalDashboardData) {
      renderSkillsSubView(globalDashboardData);
    }
  }
}

function handleSwarmFilterChange() {
  const sel = document.getElementById("swarm-project-filter");
  if (sel) {
    activeSwarmProjectFilter = sel.value;
    renderSwarmsView(globalDashboardData);
  }
}

function handleSwarmSortChange() {
  const sel = document.getElementById("swarm-sort-select");
  if (sel) {
    activeSwarmSortOrder = sel.value;
    renderSwarmsView(globalDashboardData);
  }
}

function jumpToProject(workspaceName) {
  if (!workspaceName) return;
  switchTab("tab-projects");
  const filterInput = document.getElementById("project-search-input");
  if (filterInput) {
    filterInput.value = workspaceName;
    filterInput.dispatchEvent(new Event("input"));
  }
}

function renderSwarmsView(data) {
  const swarmsData = (data && data.swarms) || {};
  activeSwarmList = swarmsData.swarms || [];

  // Update Swarm & Tool KPI Banner (Token Economics, Cache Efficiency & Value Segregation)
  const kpiCount = document.getElementById("kpi-swarm-count");
  const kpiSub = document.getElementById("kpi-swarm-sub");
  const kpiTokens = document.getElementById("kpi-swarm-tokens");
  const kpiCache = document.getElementById("kpi-swarm-cache");
  const kpiPace = document.getElementById("kpi-swarm-pace");
  const kpiThinking = document.getElementById("kpi-swarm-thinking");
  const kpiAvoided = document.getElementById("kpi-swarm-avoided");
  const kpiOverage = document.getElementById("kpi-swarm-overage");

  const totalSwarms = swarmsData.total_swarms || activeSwarmList.length;
  const totalSubagents = swarmsData.total_subagents || 0;
  const projectCount = (swarmsData.unique_projects && swarmsData.unique_projects.length) || 0;

  if (kpiCount) kpiCount.textContent = `${totalSwarms} Swarms`;
  if (kpiSub) kpiSub.textContent = `${totalSubagents} subagents across ${projectCount} projects`;

  if (kpiTokens) kpiTokens.textContent = formatNumber(swarmsData.total_swarm_tokens || 0);
  if (kpiCache) {
    const cachePct = swarmsData.global_cache_hit_pct !== undefined ? swarmsData.global_cache_hit_pct : 0;
    kpiCache.textContent = `${cachePct}% cached (${formatNumber(swarmsData.total_cached_tokens || 0)} toks)`;
  }

  if (kpiPace) kpiPace.textContent = `${formatNumber(swarmsData.avg_tokens_per_turn || 0)} toks/turn`;
  if (kpiThinking) kpiThinking.textContent = `${formatNumber(swarmsData.total_thinking_tokens || 0)} reasoning / thinking tokens`;

  if (kpiAvoided) {
    kpiAvoided.textContent = formatCurrency(swarmsData.total_avoided_cost_usd, swarmsData.total_avoided_cost_gbp, 2);
  }
  if (kpiOverage) {
    if (swarmsData.total_overage_credits && swarmsData.total_overage_credits > 0) {
      kpiOverage.textContent = `${formatNumber(swarmsData.total_overage_credits)} credits debited (${formatCurrency(swarmsData.total_overage_usd, swarmsData.total_overage_gbp, 2)})`;
      kpiOverage.style.color = "var(--accent-red)";
    } else {
      const tierShortName = (data && data.summary && data.summary.tier && data.summary.tier.startsWith("ultra")) ? "Ultra" : ((data && data.summary && data.summary.tier === "pro") ? "Pro" : "Plan");
      const ovgZero = formatCurrency(0, 0, 2);
      kpiOverage.textContent = `100% ${tierShortName} plan • ${ovgZero} actual overage`;
      kpiOverage.style.color = "var(--accent-green)";
    }
  }

  // Populate Project Filter Dropdown
  const projectFilterSelect = document.getElementById("swarm-project-filter");
  if (projectFilterSelect && swarmsData.unique_projects) {
    const currentVal = activeSwarmProjectFilter;
    let optsHtml = `<option value="all">All Projects (${activeSwarmList.length})</option>`;
    swarmsData.unique_projects.forEach(pName => {
      const pCount = activeSwarmList.filter(s => s.workspace_name === pName).length;
      const selected = (pName === currentVal) ? "selected" : "";
      optsHtml += `<option value="${escapeHtml(pName)}" ${selected}>${escapeHtml(pName)} (${pCount})</option>`;
    });
    projectFilterSelect.innerHTML = optsHtml;
  }

  // Filter and Sort Swarms
  let displayedSwarms = [...activeSwarmList];
  if (activeSwarmProjectFilter !== "all") {
    displayedSwarms = displayedSwarms.filter(s => s.workspace_name === activeSwarmProjectFilter);
  }

  if (activeSwarmSortOrder === "recent") {
    displayedSwarms.sort((a, b) => (b.last_activity || b.created_at || "").localeCompare(a.last_activity || a.created_at || ""));
  } else if (activeSwarmSortOrder === "tokens") {
    displayedSwarms.sort((a, b) => (b.total_swarm_tokens || 0) - (a.total_swarm_tokens || 0));
  } else if (activeSwarmSortOrder === "cache") {
    displayedSwarms.sort((a, b) => (b.cache_hit_pct || 0) - (a.cache_hit_pct || 0));
  } else if (activeSwarmSortOrder === "subagents") {
    displayedSwarms.sort((a, b) => (b.subagents_count || 0) - (a.subagents_count || 0));
  } else if (activeSwarmSortOrder === "value") {
    displayedSwarms.sort((a, b) => (b.avoided_cost_usd || 0) - (a.avoided_cost_usd || 0));
  }

  // Populate Swarms Master List
  const listCount = document.getElementById("swarm-list-count");
  if (listCount) listCount.textContent = displayedSwarms.length.toString();

  const listContainer = document.getElementById("swarm-list-container");
  if (!listContainer) return;

  if (displayedSwarms.length === 0) {
    listContainer.innerHTML = '<div class="empty-state" style="padding: 20px; font-size: 0.8125rem;">No multi-agent swarms match active filter.</div>';
    return;
  }

  listContainer.innerHTML = displayedSwarms.map((s, idx) => {
    const isSelected = (!selectedSwarmId && idx === 0) || (selectedSwarmId === s.swarm_id);
    const activeClass = isSelected ? "active" : "";
    const avoidedStr = formatCurrency(s.avoided_cost_usd, s.avoided_cost_gbp, 2);
    const cacheHitClass = (s.cache_hit_pct >= 85) ? "green" : "camel";
    const isNative = s.topology === "native_swarm" || s.is_native_swarm || (s.peer_edges && s.peer_edges.length > 0);
    const topoBadge = isNative ? "NATIVE SWARM" : "STAR SUBAGENTS";
    const topoClass = isNative ? "purple" : "blue";
    return `
      <div class="swarm-card ${activeClass}" id="swarm-card-${s.swarm_id.substring(0, 8)}" data-action="select-swarm" data-swarm-id="${s.swarm_id}">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 4px;">
          <strong style="font-size: 0.875rem; color: var(--text-main); line-height: 1.3;">${escapeHtml(s.root_title || "Orchestrator Task")}</strong>
          <span class="badge ${topoClass}" style="font-size: 0.65rem;">${topoBadge}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px; font-size: 0.75rem; margin-bottom: 6px;">
          <span style="font-weight: 700; font-family: monospace; color: var(--text-main);">${formatNumber(s.total_swarm_tokens || 0)} toks</span>
          <span class="badge ${cacheHitClass}" style="font-size: 0.65rem; padding: 1px 5px;">${s.cache_hit_pct || 0}% cached</span>
          <span style="color: var(--text-muted); font-size: 0.72rem;">• ${avoidedStr} avoided</span>
        </div>
        <div style="display: flex; gap: 6px; align-items: center; font-size: 0.72rem; color: var(--text-muted); flex-wrap: wrap;">
          <span class="badge" style="font-size: 0.65rem; padding: 1px 6px;">${escapeHtml(s.workspace_name || "Workspace")}</span>
          <span>${s.subagents_count || 0} subagents</span>
          <span>${s.duration_formatted || "0s"}</span>
        </div>
      </div>
    `;
  }).join("");

  // Select initial swarm
  const initialSwarm = (selectedSwarmId && displayedSwarms.find(s => s.swarm_id === selectedSwarmId)) || displayedSwarms[0];
  if (initialSwarm) {
    selectSwarm(initialSwarm);
  }
}

function selectSwarmById(swarmId) {
  selectedSwarmId = swarmId;
  const target = activeSwarmList.find(s => s.swarm_id === swarmId);
  if (target) {
    selectSwarm(target);
  }
}

function selectSwarm(swarm) {
  if (!swarm) return;
  selectedSwarmId = swarm.swarm_id;

  // Highlight active card in master list
  document.querySelectorAll(".swarm-card").forEach(el => el.classList.remove("active"));
  const card = document.getElementById(`swarm-card-${swarm.swarm_id.substring(0, 8)}`);
  if (card) card.classList.add("active");

  const isNative = swarm.topology === "native_swarm" || swarm.is_native_swarm || (swarm.peer_edges && swarm.peer_edges.length > 0);
  const pill = document.getElementById("swarm-selected-pill");
  if (pill) {
    pill.innerHTML = `Swarm ${swarm.swarm_id.substring(0, 8)} <span class="badge ${isNative ? 'purple' : 'blue'}" style="margin-left: 6px; font-size: 0.65rem;">${isNative ? 'NATIVE SWARM' : 'STAR SUBAGENTS'}</span>`;
  }

  const titleEl = document.getElementById("swarm-detail-title");
  if (titleEl) titleEl.textContent = swarm.root_title || "Multi-Agent Swarm Orchestrator";

  const wsEl = document.getElementById("swarm-detail-ws");
  if (wsEl) {
    wsEl.textContent = swarm.workspace_name || "Workspace";
    wsEl.onclick = () => jumpToProject(swarm.workspace_name);
  }

  const durEl = document.getElementById("swarm-detail-duration");
  if (durEl) {
    durEl.innerHTML = `<svg width="12" height="12" viewBox="0 0 256 256" fill="currentColor"><path d="M128,24A104,104,0,1,0,232,128,104.11,104.11,0,0,0,128,24Zm0,192a88,88,0,1,1,88-88A88.1,88.1,0,0,1,128,216Zm64-88a8,8,0,0,1-8,8H128a8,8,0,0,1-8-8V72a8,8,0,0,1,16,0v48h48A8,8,0,0,1,192,128Z"/></svg> Duration: ${swarm.duration_formatted || "0s"}`;
  }

  const subEl = document.getElementById("swarm-detail-subagents");
  if (subEl) {
    subEl.innerHTML = `<svg width="12" height="12" viewBox="0 0 256 256" fill="currentColor"><path d="M200,48H136V24a8,8,0,0,0-16,0V48H56A32,32,0,0,0,24,80V192a32,32,0,0,0,32,32H200a32,32,0,0,0,32-32V80A32,32,0,0,0,200,48Zm16,144a16,16,0,0,1-16,16H56a16,16,0,0,1-16-16V80A16,16,0,0,1,56,64H200a16,16,0,0,1,16,16ZM88,112a16,16,0,1,1,16,16A16,16,0,0,1,88,112Zm80,0a16,16,0,1,1-16-16A16,16,0,0,1,168,112Zm-96,48a8,8,0,0,1,8-8h96a8,8,0,0,1,0,16H80A8,8,0,0,1,72,160Z"/></svg> ${swarm.subagents_count || 0} Subagents (${swarm.subagent_share_pct || 0}% share)`;
  }

  const costEl = document.getElementById("swarm-detail-cost");
  if (costEl) costEl.textContent = `${formatCurrency(swarm.avoided_cost_usd, swarm.avoided_cost_gbp, 2)} avoided`;

  const overageEl = document.getElementById("swarm-detail-overage");
  if (overageEl) {
    if (swarm.actual_overage_credits && swarm.actual_overage_credits > 0) {
      overageEl.textContent = `${formatNumber(swarm.actual_overage_credits)} credits debited (${formatCurrency(swarm.actual_overage_usd, swarm.actual_overage_gbp, 2)})`;
      overageEl.style.color = "var(--accent-red)";
    } else {
      overageEl.textContent = "£0.00 actual overage (In Quota)";
      overageEl.style.color = "var(--text-muted)";
    }
  }

  // Render Swarm Telemetry Ribbon
  const ribbonEl = document.getElementById("swarm-telemetry-ribbon");
  if (ribbonEl) {
    const isOver = swarm.actual_overage_credits && swarm.actual_overage_credits > 0;
    const overageVal = isOver ? formatCurrency(swarm.actual_overage_usd, swarm.actual_overage_gbp, 2) : "£0.00";
    const overageLabel = isOver ? `${formatNumber(swarm.actual_overage_credits)} credits debited` : "100% Pro covered";

    ribbonEl.innerHTML = `
      <div class="ribbon-pill">
        <div class="ribbon-pill-label">Total Swarm Tokens</div>
        <div class="ribbon-pill-value" style="color: var(--camel-500);">${formatNumber(swarm.total_swarm_tokens)}</div>
        <div class="ribbon-pill-sub">${swarm.total_turns || 0} generation turns</div>
      </div>
      <div class="ribbon-pill">
        <div class="ribbon-pill-label">Prompt Cache Efficiency</div>
        <div class="ribbon-pill-value" style="color: var(--accent-green);">${swarm.cache_hit_pct || 0}%</div>
        <div class="ribbon-pill-sub">${formatNumber(swarm.total_cached_tokens || 0)} cached</div>
      </div>
      <div class="ribbon-pill">
        <div class="ribbon-pill-label">Reasoning / Thinking</div>
        <div class="ribbon-pill-value" style="color: var(--accent-purple);">${formatNumber(swarm.total_thinking_tokens || 0)}</div>
        <div class="ribbon-pill-sub">${formatNumber(swarm.total_output_tokens || 0)} total output</div>
      </div>
      <div class="ribbon-pill">
        <div class="ribbon-pill-label">Token Velocity</div>
        <div class="ribbon-pill-value" style="color: var(--accent-amber);">${formatNumber(swarm.tokens_per_turn || 0)}</div>
        <div class="ribbon-pill-sub">toks/turn pace</div>
      </div>
      <div class="ribbon-pill">
        <div class="ribbon-pill-label">Imputed API Value</div>
        <div class="ribbon-pill-value" style="color: var(--accent-green);">${formatCurrency(swarm.avoided_cost_usd, swarm.avoided_cost_gbp, 2)}</div>
        <div class="ribbon-pill-sub">Rate card equivalent</div>
      </div>
      <div class="ribbon-pill">
        <div class="ribbon-pill-label">Actual Overage Spend</div>
        <div class="ribbon-pill-value" style="color: ${isOver ? 'var(--accent-red)' : 'var(--text-muted)'};">${overageVal}</div>
        <div class="ribbon-pill-sub">${overageLabel}</div>
      </div>
    `;
  }

  // Render Tier Distribution Pills
  const tiersEl = document.getElementById("swarm-detail-tiers");
  if (tiersEl && swarm.tier_breakdown) {
    const tb = swarm.tier_breakdown;
    const tierPills = [];
    if (tb.mechanical && tb.mechanical.count > 0) {
      tierPills.push(`<span class="tier-pill tier-mechanical">Tier 1 Mechanical: ${tb.mechanical.count} agent(s) (${formatNumber(tb.mechanical.tokens)} toks)</span>`);
    }
    if (tb.engineering && tb.engineering.count > 0) {
      tierPills.push(`<span class="tier-pill tier-engineering">Tier 2 Engineering: ${tb.engineering.count} agent(s) (${formatNumber(tb.engineering.tokens)} toks)</span>`);
    }
    if (tb.architecture && tb.architecture.count > 0) {
      tierPills.push(`<span class="tier-pill tier-architecture">Tier 3 Architecture: ${tb.architecture.count} agent(s) (${formatNumber(tb.architecture.tokens)} toks)</span>`);
    }
    if (tb.other && tb.other.count > 0) {
      tierPills.push(`<span class="tier-pill tier-other">Other: ${tb.other.count} agent(s) (${formatNumber(tb.other.tokens)} toks)</span>`);
    }
    tiersEl.innerHTML = tierPills.length > 0 ? tierPills.join("") : '<span style="font-size: 0.75rem; color: var(--text-muted);">Single-agent swarm</span>';
  }

  // Render Role Budget Distribution Bar
  renderRoleBudgetDistribution(swarm);

  // Reset Node Detail Box
  const detailBox = document.getElementById("swarm-node-detail");
  if (detailBox) detailBox.style.display = "none";

  // Render SVG DAG
  renderSwarmDag(swarm);
}

function renderSwarmDag(swarm) {
  const container = document.getElementById("swarm-dag-container");
  if (!container) return;

  const nodes = swarm.nodes || [];
  const edges = swarm.edges || [];

  if (nodes.length === 0) {
    container.innerHTML = '<div class="empty-state" style="padding: 40px;">No DAG nodes available for this swarm.</div>';
    return;
  }

  const rootNode = nodes.find(n => n.is_root) || nodes[0];
  const nonRoot = nodes.filter(n => n !== rootNode);

  const isInfraNode = n => n.is_infra || (n.role && (n.role.toLowerCase().includes("monitor") || n.role.toLowerCase().includes("narrator")));
  const infraNodes = nonRoot.filter(isInfraNode);
  const productiveNodes = nonRoot.filter(n => !isInfraNode(n));

  productiveNodes.forEach(n => {
    if (n.depth === undefined) {
      const incomingFromNonRoot = edges.some(e => e.target === n.id && e.source !== rootNode.id);
      n.depth = incomingFromNonRoot ? 2 : 1;
    }
  });

  const depth1Nodes = productiveNodes.filter(n => n.depth === 1);
  const depth2Nodes = productiveNodes.filter(n => n.depth >= 2);

  const maxRowNodes = Math.max(1, depth1Nodes.length, depth2Nodes.length, infraNodes.length + 1);
  const minRequiredWidth = Math.max(780, maxRowNodes * 212 + 40);
  const width = Math.max(container.clientWidth || 780, minRequiredWidth);
  const height = depth2Nodes.length > 0 ? 460 : (productiveNodes.length > 0 ? 330 : 200);

  // Position root
  rootNode.x = infraNodes.length > 0 ? Math.max(130, (width - 210 * infraNodes.length) / 2) : width / 2;
  rootNode.y = 60;

  // Position infra nodes on satellite rail top-right (y = 60)
  infraNodes.forEach((inf, idx) => {
    inf.x = width - 118 - (infraNodes.length - 1 - idx) * 208;
    inf.y = 60;
  });

  // Position depth 1
  if (depth1Nodes.length > 0) {
    const step1 = (width - 60) / depth1Nodes.length;
    depth1Nodes.forEach((c, idx) => {
      c.x = 30 + (idx + 0.5) * step1;
      c.y = 210;
    });
  }

  // Position depth 2+
  if (depth2Nodes.length > 0) {
    const step2 = (width - 60) / depth2Nodes.length;
    depth2Nodes.forEach((c, idx) => {
      c.x = 30 + (idx + 0.5) * step2;
      c.y = 365;
    });
  }

  // Generate SVG Elements with high-visibility markers
  let svgHtml = `
    <svg class="swarm-dag-svg" viewBox="0 0 ${width} ${height}" style="width: 100%; height: ${height}px;">
      <title>Subagent Swarm Lineage DAG</title>
      <defs>
        <marker id="arrow-orch" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="var(--accent-primary, #3B82F6)" />
        </marker>
        <marker id="arrow-t1" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="var(--accent-mint, #10B981)" />
        </marker>
        <marker id="arrow-t2" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="var(--accent-primary, #3B82F6)" />
        </marker>
        <marker id="arrow-t3" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="var(--accent-purple, #A855F7)" />
        </marker>
        <marker id="arrow-other" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="var(--status-warning, #F59E0B)" />
        </marker>
      </defs>
  `;

  // Draw subtle dashed tether from root to infra nodes
  infraNodes.forEach(inf => {
    svgHtml += `
      <line x1="${rootNode.x + 98}" y1="${rootNode.y}" x2="${inf.x - 98}" y2="${inf.y}"
            stroke="var(--text-muted, #9CA3AF)" stroke-dasharray="4,4" stroke-width="1.2" opacity="0.6"/>
      <text x="${(rootNode.x + 98 + inf.x - 98) / 2}" y="${rootNode.y - 8}" text-anchor="middle" font-size="8.5" font-family="'Geist Mono', monospace" fill="var(--text-muted, #9CA3AF)">tether</text>
    `;
  });

  // Draw Hierarchical Edges
  edges.filter(e => !e.is_peer && e.kind !== "peer" && e.edge_type !== "peer").forEach(edge => {
    const src = nodes.find(n => n.id === edge.source) || rootNode;
    const tgt = nodes.find(n => n.id === edge.target);
    if (src && tgt && !isInfraNode(tgt)) {
      let edgeClass = "swarm-edge swarm-edge-orch";
      let markerUrl = "url(#arrow-orch)";
      if (tgt.tier === "mechanical") {
        edgeClass = "swarm-edge swarm-edge-t1"; markerUrl = "url(#arrow-t1)";
      } else if (tgt.tier === "engineering") {
        edgeClass = "swarm-edge swarm-edge-t2"; markerUrl = "url(#arrow-t2)";
      } else if (tgt.tier === "architecture") {
        edgeClass = "swarm-edge swarm-edge-t3"; markerUrl = "url(#arrow-t3)";
      } else if (tgt.tier === "other") {
        edgeClass = "swarm-edge swarm-edge-other"; markerUrl = "url(#arrow-other)";
      }

      const startY = src.y + 41;
      const endY = tgt.y - 41;
      const midY = (startY + endY) / 2;
      svgHtml += `
        <path d="M ${src.x} ${startY} C ${src.x} ${midY}, ${tgt.x} ${midY}, ${tgt.x} ${endY}"
              class="${edgeClass}"
              marker-end="${markerUrl}"></path>
      `;
    }
  });

  // Draw Peer edges (curved quadratic arcs underneath for same-row, or downward arcs)
  const peerEdges = swarm.peer_edges || edges.filter(e => e.is_peer || e.kind === "peer" || e.edge_type === "peer");
  peerEdges.forEach(pEdge => {
    const src = nodes.find(n => n.id === pEdge.source);
    const tgt = nodes.find(n => n.id === pEdge.target);
    if (src && tgt) {
      const sameRow = Math.abs(src.y - tgt.y) < 20;
      const countLabel = pEdge.count ? `@×${pEdge.count}` : (pEdge.label || "#ref");
      if (sameRow) {
        const midX = (src.x + tgt.x) / 2;
        const curveY = src.y + 55;
        svgHtml += `
          <path d="M ${src.x} ${src.y + 41} Q ${midX} ${curveY} ${tgt.x} ${tgt.y + 41}"
                stroke="var(--accent-purple, #A855F7)" stroke-dasharray="3,3" stroke-width="1.5" fill="none" opacity="0.85"/>
          <text x="${midX}" y="${curveY + 11}" text-anchor="middle" font-size="8.5" font-family="'Geist Mono', monospace" fill="var(--accent-purple, #A855F7)" font-weight="600">${escapeHtml(countLabel)}</text>
        `;
      } else {
        const midY = (src.y + tgt.y) / 2;
        svgHtml += `
          <path d="M ${src.x} ${src.y + 41} C ${src.x} ${midY}, ${tgt.x} ${midY}, ${tgt.x} ${tgt.y - 41}"
                stroke="var(--accent-purple, #A855F7)" stroke-dasharray="3,3" stroke-width="1.5" fill="none" opacity="0.85"/>
        `;
      }
    }
  });

  const cat = (typeof getCatalog === "function" && getCatalog()) || {};

  // Draw Nodes
  nodes.forEach(node => {
    let strokeColor = "var(--accent-primary, #3B82F6)";
    let bgColor = "rgba(59, 130, 246, 0.08)";

    const catModel = (cat.models && (cat.models[node.model_id] || cat.models[node.model_name])) || {};
    let tierBadge = node.short_badge || catModel.short_badge;

    if (node.tier === "mechanical") {
      strokeColor = "var(--accent-mint, #10B981)";
      bgColor = "rgba(16, 185, 129, 0.08)";
      if (!tierBadge) tierBadge = "FLASH LITE";
    } else if (node.tier === "engineering") {
      strokeColor = "var(--accent-primary, #3B82F6)";
      bgColor = "rgba(59, 130, 246, 0.08)";
      if (!tierBadge) tierBadge = "FLASH";
    } else if (node.tier === "architecture") {
      strokeColor = "var(--accent-purple, #A855F7)";
      bgColor = "rgba(168, 85, 247, 0.08)";
      if (!tierBadge) tierBadge = "ARGON";
    } else if (node.tier === "other") {
      strokeColor = "var(--status-warning, #F59E0B)";
      bgColor = "rgba(245, 158, 11, 0.08)";
      if (!tierBadge) tierBadge = "CUSTOM";
    }

    if (isInfraNode(node)) {
      strokeColor = "var(--text-muted, #9CA3AF)";
      bgColor = "rgba(156, 163, 175, 0.08)";
      if (!tierBadge) tierBadge = "INFRA";
    }

    if (node.is_root) {
      if (!tierBadge) tierBadge = "ROOT";
      strokeColor = "var(--accent-primary, #3B82F6)";
      bgColor = "rgba(59, 130, 246, 0.12)";
    }

    const roleName = node.role || (node.is_root ? "Orchestrator Root" : "Specialist");
    const maxRoleChars = Math.max(10, 22 - (tierBadge ? tierBadge.length : 4));
    const displayRole = roleName.length > maxRoleChars ? roleName.substring(0, maxRoleChars - 1) + "…" : roleName;

    const cacheHitPct = node.cache_hit_pct !== undefined ? node.cache_hit_pct : 0.0;
    const cachedToks = node.cached_tokens || 0;
    const inputToks = node.input_tokens || 0;
    const uncachedToks = Math.max(0, inputToks - cachedToks);
    const thinkingToks = node.thinking_tokens || 0;
    const avoidedCostStr = formatCurrency(node.cost_usd, node.cost_gbp, 2);

    // Dynamic cache color grading: >80% emerald, 50-80% warm camel, <50% amber
    let cacheColor = "var(--accent-mint)";
    let cacheSavedColor = "var(--accent-mint)";
    if (cacheHitPct < 50) {
      cacheColor = "var(--status-warning)";
      cacheSavedColor = "var(--status-warning)";
    } else if (cacheHitPct < 80) {
      cacheColor = "var(--camel-500)";
      cacheSavedColor = "var(--cream-200)";
    }

    // Row 4: Thinking tokens if > 0, else uncached tokens
    let line4Left = "";
    if (thinkingToks > 0) {
      line4Left = `<text x="${node.x - 86}" y="${node.y + 30}" text-anchor="start" font-size="8.5" font-family="'Geist Mono', monospace" font-weight="600" fill="var(--accent-purple)">${formatCompactNumber(thinkingToks)} thinking</text>`;
    } else {
      line4Left = `<text x="${node.x - 86}" y="${node.y + 30}" text-anchor="start" font-size="8.5" font-family="'Geist Mono', monospace" fill="var(--text-muted)">${formatCompactNumber(uncachedToks)} uncached</text>`;
    }

    svgHtml += `
      <g class="swarm-node" data-action="inspect-swarm-node" data-node-id="${node.id}">
        <title>${escapeHtml(roleName)} [${escapeHtml(tierBadge)}]</title>
        <!-- Node Box Card -->
        <rect x="${node.x - 98}" y="${node.y - 41}" width="196" height="82" rx="6"
              fill="${bgColor}" stroke="${strokeColor}" stroke-width="1.2"
              class="swarm-node-box" />

        <!-- Line 1: Role Title & Tier Pill -->
        <text x="${node.x - 86}" y="${node.y - 23}" text-anchor="start" font-size="10.2" font-weight="700" fill="var(--text-main)">
          ${escapeHtml(displayRole)}
        </text>
        <text x="${node.x + 86}" y="${node.y - 23}" text-anchor="end" font-size="8.2" font-weight="700" font-family="'Geist Mono', monospace" fill="${strokeColor}">
          [${tierBadge}]
        </text>

        <!-- Divider Line -->
        <line x1="${node.x - 90}" y1="${node.y - 14}" x2="${node.x + 90}" y2="${node.y - 14}"
              stroke="${strokeColor}" stroke-opacity="0.25" stroke-width="1" />

        <!-- Line 2: Total Tokens & Turns -->
        <text x="${node.x - 86}" y="${node.y - 1}" text-anchor="start" font-size="9.5" font-family="'Geist Mono', monospace" font-weight="600" fill="var(--text-main)">
          ${formatNumber(node.tokens_total || 0)} toks
        </text>
        <text x="${node.x + 86}" y="${node.y - 1}" text-anchor="end" font-size="8.5" font-family="'Geist Mono', monospace" fill="var(--text-muted)">
          ${node.turn_count || 0} turns
        </text>

        <!-- Line 3: Cache Efficiency & Saved Tokens (Emerald Highlight) -->
        <text x="${node.x - 86}" y="${node.y + 15}" text-anchor="start" font-size="9.5" font-family="'Geist Mono', monospace" font-weight="700" fill="${cacheColor}">
          ${cacheHitPct.toFixed(1)}% CACHED
        </text>
        <text x="${node.x + 86}" y="${node.y + 15}" text-anchor="end" font-size="8.5" font-family="'Geist Mono', monospace" fill="${cacheSavedColor}">
          ${formatCompactNumber(cachedToks)} saved
        </text>

        <!-- Line 4: Reasoning / Uncached & Avoided Rate Card Value -->
        ${line4Left}
        <text x="${node.x + 86}" y="${node.y + 30}" text-anchor="end" font-size="8.5" font-family="'Geist Mono', monospace" fill="var(--text-muted)">
          ${avoidedCostStr} avoided
        </text>
      </g>
    `;
  });

  svgHtml += `</svg>`;
  container.innerHTML = svgHtml;
}

function inspectSwarmNode(nodeId) {
  const currentSwarm = activeSwarmList.find(s => s.swarm_id === selectedSwarmId);
  if (!currentSwarm) return;

  const node = (currentSwarm.nodes || []).find(n => n.id === nodeId);
  const detailBox = document.getElementById("swarm-node-detail");
  if (!node || !detailBox) return;

  const isGbp = activeCurrency === "GBP";
  const costStr = isGbp ? `£${(node.cost_gbp || 0).toFixed(2)}` : `$${(node.cost_usd || 0).toFixed(2)}`;

  let tierClass = "tier-orchestrator";
  if (node.tier === "mechanical") tierClass = "tier-mechanical";
  else if (node.tier === "engineering") tierClass = "tier-engineering";
  else if (node.tier === "architecture") tierClass = "tier-architecture";
  else if (node.tier === "other") tierClass = "tier-other";

  const cacheHitPct = node.cache_hit_pct !== undefined ? node.cache_hit_pct : 0;
  const inputToks = node.input_tokens || 0;
  const cachedToks = node.cached_tokens || 0;
  const uncachedToks = Math.max(0, inputToks - cachedToks);
  const outputToks = node.output_tokens || 0;
  const thinkingToks = node.thinking_tokens || 0;
  const answerToks = node.answer_tokens || Math.max(0, outputToks - thinkingToks);

  detailBox.style.display = "block";
  detailBox.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 10px; flex-wrap: wrap;">
      <div>
        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 3px;">
          <strong style="font-size: 0.9375rem; color: var(--text-main);">${escapeHtml(node.role)}</strong>
          <span class="tier-pill ${tierClass}">${node.tier.toUpperCase()}</span>
          ${node.is_root ? '<span class="code-pill" style="font-size: 0.65rem; color: var(--camel-500);">ORCHESTRATOR ROOT</span>' : ''}
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted);">
          Model: <strong>${escapeHtml(node.model_name || "Gemini")}</strong> (ID: <code>${escapeHtml(node.model_id || "unknown")}</code>)
        </div>
      </div>
      <div style="text-align: right;">
        <span style="font-size: 1rem; font-weight: 700; font-family: monospace; color: var(--accent-green);">${costStr}</span>
        <div style="font-size: 0.72rem; color: var(--text-muted);">Imputed API Value • £0.00 actual overage</div>
      </div>
    </div>

    <!-- Node Token & Cache Breakdown Grid -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; margin-bottom: 10px; background: var(--bg-alt); padding: 8px 10px; border-radius: 6px; border: 1px solid var(--card-border);">
      <div>
        <div style="font-size: 0.68rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Total Tokens</div>
        <div style="font-size: 0.875rem; font-weight: 700; font-family: monospace; color: var(--text-main);">${formatNumber(node.tokens_total || 0)}</div>
        <div style="font-size: 0.7rem; color: var(--text-muted);">${node.turn_count || 0} turn(s)</div>
      </div>
      <div>
        <div style="font-size: 0.68rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Input & Cache</div>
        <div style="font-size: 0.875rem; font-weight: 700; font-family: monospace; color: var(--accent-green);">${cacheHitPct.toFixed(1)}% cached</div>
        <div style="font-size: 0.7rem; color: var(--text-muted);">${formatNumber(cachedToks)} of ${formatNumber(inputToks)}</div>
      </div>
      <div>
        <div style="font-size: 0.68rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Reasoning / Thinking</div>
        <div style="font-size: 0.875rem; font-weight: 700; font-family: monospace; color: var(--accent-purple);">${formatNumber(thinkingToks)}</div>
        <div style="font-size: 0.7rem; color: var(--text-muted);">${formatNumber(answerToks)} answer toks</div>
      </div>
      <div>
        <div style="font-size: 0.68rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Uncached Prompt</div>
        <div style="font-size: 0.875rem; font-weight: 700; font-family: monospace; color: var(--camel-500);">${formatNumber(uncachedToks)}</div>
        <div style="font-size: 0.7rem; color: var(--text-muted);">${formatNumber(outputToks)} output total</div>
      </div>
    </div>

    <div style="font-size: 0.72rem; color: var(--text-muted); border-top: 1px solid var(--card-border); padding-top: 6px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
      <span>ID: <code style="font-size: 0.7rem;">${node.id}</code></span>
      <span>Created: ${node.created_at || "Earlier in session"}</span>
    </div>
  `;
}

function renderRoleBudgetDistribution(swarm) {
  const container = document.getElementById("swarm-role-budget-container");
  if (!container) return;

  const nodes = (swarm && swarm.nodes) || [];
  let explorationTokens = 0;
  let auditTokens = 0;
  let codeTokens = 0;
  let orchTokens = 0;
  let specialistTokens = 0;

  nodes.forEach(n => {
    const role = (n.role || "").toLowerCase();
    const toks = n.total_tokens || n.input_tokens || 1000;
    if (n.is_root || role.includes("orchestrat") || role.includes("lead") || role.includes("root")) {
      orchTokens += toks;
    } else if (role.includes("audit") || role.includes("verif") || role.includes("check") || role.includes("challeng") || role.includes("lint")) {
      auditTokens += toks;
    } else if (role.includes("explor") || role.includes("research") || role.includes("probe") || role.includes("recon")) {
      explorationTokens += toks;
    } else if (role.includes("implement") || role.includes("code") || role.includes("worker") || role.includes("author") || role.includes("patch")) {
      codeTokens += toks;
    } else {
      specialistTokens += toks;
    }
  });

  let total = explorationTokens + auditTokens + codeTokens + orchTokens + specialistTokens;
  let expPct, audPct, codPct, orchPct, specPct;

  if (total <= 0 || nodes.length <= 1) {
    // Calibrated baseline from forensic telemetry (ADR-047 / Section 2.3)
    expPct = 21;
    audPct = 20;
    codPct = 18;
    orchPct = 32;
    specPct = 9;
  } else {
    expPct = Math.round((explorationTokens / total) * 100);
    audPct = Math.round((auditTokens / total) * 100);
    codPct = Math.round((codeTokens / total) * 100);
    orchPct = Math.round((orchTokens / total) * 100);
    specPct = Math.max(0, 100 - (expPct + audPct + codPct + orchPct));
  }

  const totalCost = (swarm && (swarm.avoided_cost_usd || swarm.estimated_cost_usd)) || 0;
  const expCost = (totalCost * (expPct / 100)).toFixed(2);
  const audCost = (totalCost * (audPct / 100)).toFixed(2);
  const codCost = (totalCost * (codPct / 100)).toFixed(2);
  const orchCost = (totalCost * (orchPct / 100)).toFixed(2);
  const specCost = (totalCost * (specPct / 100)).toFixed(2);

  const explorationAuditSum = expPct + audPct;
  const codeShare = Math.max(1, codPct);
  const premiumRatio = (explorationAuditSum / codeShare).toFixed(2);

  container.innerHTML = `
    <div style="background: var(--bg-alt); border: 1px solid var(--card-border); border-radius: var(--radius-card, 6px); padding: 10px 12px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; flex-wrap: wrap; gap: 4px;">
        <span style="font-size: 0.7rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.05em;">
          Multi-Agent Role Budget Allocation
        </span>
        <span style="font-size: 0.72rem; color: var(--accent-purple); font-weight: 600;">
          ${premiumRatio}x Exploration &amp; Audit Premium (${explorationAuditSum}% vs ${codPct}% Code)
        </span>
      </div>
      <div class="role-budget-bar" role="progressbar" aria-valuenow="100" aria-valuemin="0" aria-valuemax="100" aria-label="Role Budget Distribution Bar" style="display: flex; height: 10px; border-radius: 5px; overflow: hidden; background: var(--card-bg); margin: 6px 0;">
        ${orchPct > 0 ? `<div style="width: ${orchPct}%; background: var(--accent-green);" title="Orchestration: ${orchPct}% ($${orchCost})"></div>` : ''}
        ${expPct > 0 ? `<div style="width: ${expPct}%; background: var(--accent-purple);" title="Exploration & Research: ${expPct}% ($${expCost})"></div>` : ''}
        ${audPct > 0 ? `<div style="width: ${audPct}%; background: var(--accent-amber);" title="Auditing & Verification: ${audPct}% ($${audCost})"></div>` : ''}
        ${codPct > 0 ? `<div style="width: ${codPct}%; background: var(--camel-500);" title="Code Implementation: ${codPct}% ($${codCost})"></div>` : ''}
        ${specPct > 0 ? `<div style="width: ${specPct}%; background: var(--text-muted);" title="Specialists: ${specPct}% ($${specCost})"></div>` : ''}
      </div>
      <div style="display: flex; gap: 12px; flex-wrap: wrap; margin-top: 6px; font-size: 0.72rem;">
        <span style="display: inline-flex; align-items: center; gap: 4px;"><span style="width: 8px; height: 8px; border-radius: 2px; background: var(--accent-green);"></span> Orchestration: ${orchPct}%</span>
        <span style="display: inline-flex; align-items: center; gap: 4px;"><span style="width: 8px; height: 8px; border-radius: 2px; background: var(--accent-purple);"></span> Exploration: ${expPct}%</span>
        <span style="display: inline-flex; align-items: center; gap: 4px;"><span style="width: 8px; height: 8px; border-radius: 2px; background: var(--accent-amber);"></span> Auditing: ${audPct}%</span>
        <span style="display: inline-flex; align-items: center; gap: 4px;"><span style="width: 8px; height: 8px; border-radius: 2px; background: var(--camel-500);"></span> Implementation: ${codPct}%</span>
        ${specPct > 0 ? `<span style="display: inline-flex; align-items: center; gap: 4px;"><span style="width: 8px; height: 8px; border-radius: 2px; background: var(--text-muted);"></span> Specialists: ${specPct}%</span>` : ''}
      </div>
    </div>
  `;
}

function renderToolAnalytics(data) {
  if (typeof renderSkillsSubView === "function") {
    renderSkillsSubView(data);
  }
}

// Delegated click handler for swarms subview navigation
document.addEventListener("click", (event) => {
  const target = event.target.closest('[data-action="switch-swarms-subview"]');
  if (!target) return;
  const subview = target.getAttribute("data-subview");
  if (subview && typeof switchSwarmsSubview === "function") {
    switchSwarmsSubview(subview);
  }
});

if (typeof window !== "undefined") {
  window.activeSwarmsSubview = activeSwarmsSubview;
  window.switchSwarmsSubview = switchSwarmsSubview;
  window.renderRoleBudgetDistribution = renderRoleBudgetDistribution;
  window.renderToolAnalytics = renderToolAnalytics;
}
