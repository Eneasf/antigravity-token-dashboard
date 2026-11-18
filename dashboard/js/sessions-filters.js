// ==========================================
// Dashboard: Sessions Filters, Sorting & Pagination Controller
// Extracted from js/sessions.js (<800 lines rule).
// ==========================================

// --- Model Truncation Thresholds (ADR-068 / M54) ---
function getModelTruncationThreshold(modelId) {
  const mIdStr = modelId != null ? String(modelId) : "";
  const pricingModels = (typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.pricing_models)
    ? globalDashboardData.pricing_models
    : null;
  const pm = pricingModels ? (pricingModels[mIdStr] || pricingModels[modelId]) : null;

  // 1. Check globalDashboardData.pricing_models?.[modelId]?.context_truncation_tokens
  if (pm && typeof pm.context_truncation_tokens === "number" && pm.context_truncation_tokens > 0) {
    return pm.context_truncation_tokens;
  }

  // 2. Check globalDashboardData.pricing_models?.[modelId]?.family
  if (pm && typeof pm.family === "string") {
    const fam = pm.family.toLowerCase();
    if (fam.includes("gemini")) return 1000000;
    if (fam.includes("claude") || fam.includes("gpt")) return 200000;
  }

  // 3. Known model roster lookup
  const geminiModels = [
    "1427", "1437", "1438",
    "1667", "1681", "1669",
    "1417", "1418", "1419",
    "1528", "1525", "1526", "1527",
    "1318", "1319", "1320", "1298", "1299", "1300",
    "1071", "1072", "1073", "1016", "1036", "1050",
    "1322", "1132", "1301", "1020", "1198"
  ];
  const claudeModels = ["1035", "1026", "1400", "1401", "1402", "1403", "1404", "1405"];
  const gptModels = ["342"];

  if (geminiModels.includes(mIdStr)) return 1000000;
  if (claudeModels.includes(mIdStr)) return 200000;
  if (gptModels.includes(mIdStr)) return 200000;

  const mLower = mIdStr.toLowerCase();
  if (mLower.includes("gemini") || mLower.includes("argon") || mLower.includes("carbon") || mLower.includes("hydrogen") || mLower.includes("orchestrator")) return 1000000;
  if (mLower.includes("claude") || mLower.includes("gpt")) return 200000;

  // 4. Default fallback
  return 200000;
}

// --- Empirical Model Compaction Ceilings (ADR-082 / Plan M85) ---
function getModelCompactionThreshold(modelId) {
  const mIdStr = modelId != null ? String(modelId) : "";
  const pricingModels = (typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.pricing_models)
    ? globalDashboardData.pricing_models
    : null;
  const pm = pricingModels ? (pricingModels[mIdStr] || pricingModels[modelId]) : null;

  if (pm && typeof pm.compaction_threshold_tokens === "number" && pm.compaction_threshold_tokens > 0) {
    return pm.compaction_threshold_tokens;
  }
  if (pm && typeof pm.family === "string") {
    const fam = pm.family.toLowerCase();
    if (fam.includes("pro") || fam.includes("claude") || fam.includes("gpt")) return 80000;
    if (fam.includes("flash") || fam.includes("argon") || fam.includes("carbon") || fam.includes("hydrogen") || fam.includes("orchestrator")) return 250000;
  }
  const flashModels = ["1427", "1437", "1438", "1667", "1681", "1669", "1417", "1418", "1419", "1528", "1525", "1526", "1527", "1318", "1319", "1320", "1050", "1198", "1322", "1132", "1301", "1020"];
  const flash37Models = ["1298", "1299", "1300", "1071", "1072", "1073"];
  const proClaudeModels = ["1016", "1036", "1035", "1026", "1400", "1401", "1402", "1403", "1404", "1405", "342"];

  if (flashModels.includes(mIdStr)) return 250000;
  if (flash37Models.includes(mIdStr)) return 165000;
  if (proClaudeModels.includes(mIdStr)) return 80000;
  return 200000;
}

// Client-side pagination state for #conversations-table
var convoCurrentPage = 0;
var CONVO_PAGE_SIZE = 25;

function prevConvoPage() {
  if (convoCurrentPage > 0) {
    convoCurrentPage--;
    if (typeof renderConversationsTable === "function") {
      renderConversationsTable(activeFilteredConversations);
    }
  }
}

function nextConvoPage() {
  const total = (typeof activeFilteredConversations !== "undefined" && activeFilteredConversations) ? activeFilteredConversations.length : 0;
  if ((convoCurrentPage + 1) * CONVO_PAGE_SIZE < total) {
    convoCurrentPage++;
    if (typeof renderConversationsTable === "function") {
      renderConversationsTable(activeFilteredConversations);
    }
  }
}

var convoSortField = "turns";
var convoSortOrder = "desc";
var sessionsViewMode = "tree";

function setSessionsViewMode(mode) {
  sessionsViewMode = (mode === "flat") ? "flat" : "tree";
  const btnTree = document.getElementById("btn-view-tree");
  const btnFlat = document.getElementById("btn-view-flat");
  if (btnTree) {
    btnTree.classList.toggle("active", sessionsViewMode === "tree");
    btnTree.setAttribute("aria-pressed", sessionsViewMode === "tree" ? "true" : "false");
  }
  if (btnFlat) {
    btnFlat.classList.toggle("active", sessionsViewMode === "flat");
    btnFlat.setAttribute("aria-pressed", sessionsViewMode === "flat" ? "true" : "false");
  }
  filterData();
}

function sortConversations(list, field, order) {
  return [...list].sort((a, b) => {
    let valA = 0, valB = 0;
    if (field === "title") {
      const sA = (a.title || "").toLowerCase();
      const sB = (b.title || "").toLowerCase();
      return order === "asc" ? sA.localeCompare(sB) : sB.localeCompare(sA);
    } else if (field === "workspace") {
      const sA = (a.workspace || "").toLowerCase();
      const sB = (b.workspace || "").toLowerCase();
      return order === "asc" ? sA.localeCompare(sB) : sB.localeCompare(sA);
    } else if (field === "turns") {
      valA = a.turn_count || 0;
      valB = b.turn_count || 0;
    } else if (field === "input") {
      if (sessionsViewMode === "tree") {
        valA = (a.tree_total_input_tokens !== undefined && a.tree_total_input_tokens > 0) ? a.tree_total_input_tokens : (a.total_input_tokens || 0);
        valB = (b.tree_total_input_tokens !== undefined && b.tree_total_input_tokens > 0) ? b.tree_total_input_tokens : (b.total_input_tokens || 0);
      } else {
        valA = a.total_input_tokens || 0;
        valB = b.total_input_tokens || 0;
      }
    } else if (field === "cache") {
      valA = a.cache_hit_ratio_pct || 0;
      valB = b.cache_hit_ratio_pct || 0;
    } else if (field === "overage") {
      valA = a.actual_overage_credits || 0;
      valB = b.actual_overage_credits || 0;
    } else if (field === "cost") {
      if (sessionsViewMode === "tree") {
        valA = (a.tree_total_cost_usd !== undefined && a.tree_total_cost_usd > 0) ? a.tree_total_cost_usd : (a.avoided_cost_usd || a.estimated_cost_usd || 0);
        valB = (b.tree_total_cost_usd !== undefined && b.tree_total_cost_usd > 0) ? b.tree_total_cost_usd : (b.avoided_cost_usd || b.estimated_cost_usd || 0);
      } else {
        valA = a.avoided_cost_usd || a.estimated_cost_usd || 0;
        valB = b.avoided_cost_usd || b.estimated_cost_usd || 0;
      }
    }
    return order === "asc" ? valA - valB : valB - valA;
  });
}

function toggleConvoSort(field) {
  if (convoSortField === field) {
    convoSortOrder = convoSortOrder === "asc" ? "desc" : "asc";
  } else {
    convoSortField = field;
    convoSortOrder = "desc";
  }
  filterData();
}

function onConvoSearchChange() {
  filterData();
}

function clearConvoFilters() {
  const searchInput = document.getElementById("convo-search-input");
  if (searchInput) searchInput.value = "";
  const wsFilter = document.getElementById("workspace-filter");
  if (wsFilter) wsFilter.value = "all";
  const agentFilter = document.getElementById("agent-filter");
  if (agentFilter) agentFilter.value = "all";
  const subagentViewFilter = document.getElementById("subagent-view-filter");
  if (subagentViewFilter) subagentViewFilter.value = "main_only";
  const convoFilter = document.getElementById("convo-filter");
  if (convoFilter) convoFilter.value = "all";
  filterData();
}

function filterData(convos) {
  convoCurrentPage = 0;
  convos = convos || (globalDashboardData && globalDashboardData.conversations) || [];
  const wsFilter = document.getElementById("workspace-filter");
  const convoFilter = document.getElementById("convo-filter");
  const agentFilter = document.getElementById("agent-filter");
  const subagentViewFilter = document.getElementById("subagent-view-filter");
  const searchInput = document.getElementById("convo-search-input");

  const wsVal = wsFilter ? wsFilter.value : "all";
  const convoVal = convoFilter ? convoFilter.value : "all";
  const agentVal = agentFilter ? agentFilter.value : "all";
  const subagentViewVal = subagentViewFilter ? subagentViewFilter.value : "main_only";
  const query = (searchInput ? searchInput.value : "").trim().toLowerCase();

  let filtered = convos;

  function convoMatchesSearch(c, q) {
    if (!q) return true;
    if (!c) return false;
    return Boolean(
      (c.title && c.title.toLowerCase().includes(q)) ||
      (c.convo_id && c.convo_id.toLowerCase().includes(q)) ||
      (c.workspace && c.workspace.toLowerCase().includes(q)) ||
      (c.agent_name && c.agent_name.toLowerCase().includes(q)) ||
      (c.subagent_role && c.subagent_role.toLowerCase().includes(q))
    );
  }

  function convoMatchesAgent(c, agVal) {
    if (!agVal || agVal === "all") return true;
    if (!c) return false;
    const ag = (c.agent_name || "default").toLowerCase();
    const role = (c.subagent_role || "").toLowerCase();
    const target = agVal.toLowerCase();
    return ag === target || role.includes(target);
  }

  // 1. Hierarchy & Query Filtering
  if (sessionsViewMode === "tree") {
    if (subagentViewVal === "subagents_only") {
      filtered = convos.filter(c => Boolean(c.is_subagent));
      if (wsVal !== "all") filtered = filtered.filter(c => c.workspace === wsVal);
      if (agentVal !== "all") filtered = filtered.filter(c => convoMatchesAgent(c, agentVal));
      if (query) filtered = filtered.filter(c => convoMatchesSearch(c, query));
    } else {
      // In Tree View mode, show root conversations, but inspect children so queries and role filters find matching subagents
      const roots = convos.filter(c => !c.is_subagent && !c.parent_convo_id);
      filtered = roots.filter(root => {
        if (wsVal !== "all" && root.workspace !== wsVal) return false;

        const rootDirectAgent = convoMatchesAgent(root, agentVal);
        const rootDirectSearch = convoMatchesSearch(root, query);
        if (rootDirectAgent && rootDirectSearch) return true;

        // Check if any child subagent in the tree matches
        if (typeof getChildConversations === "function") {
          const children = getChildConversations(root);
          const hasMatchingChild = children.some(ch => convoMatchesAgent(ch, agentVal) && convoMatchesSearch(ch, query));
          if (hasMatchingChild) {
            // Auto-expand tree row so user sees matching subagent
            if (typeof expandedTreeConvoIds !== "undefined" && (query || agentVal !== "all")) {
              expandedTreeConvoIds.add(root.convo_id);
            }
            return true;
          }
        }
        return false;
      });
    }
  } else {
    // Flat View mode
    if (subagentViewVal === "main_only") {
      filtered = filtered.filter(c => !c.is_subagent);
    } else if (subagentViewVal === "subagents_only") {
      filtered = filtered.filter(c => Boolean(c.is_subagent));
    }
    if (agentVal !== "all") {
      filtered = filtered.filter(c => convoMatchesAgent(c, agentVal));
    }
    if (wsVal !== "all") {
      filtered = filtered.filter(c => c.workspace === wsVal);
    }
    if (query) {
      filtered = filtered.filter(c => convoMatchesSearch(c, query));
    }
  }

  const isSessionsActive = (typeof activeViewId !== "undefined" ? activeViewId : (typeof window !== "undefined" ? window.activeViewId : "")) === "view-sessions";
  if (convoVal !== "all") {
    const selected = convos.find(c => c.convo_id === convoVal);
    activeFilteredConversations = selected ? [selected] : [];
    activeConvoForTurns = selected;
    if (typeof renderConversationsTable === "function" && isSessionsActive) renderConversationsTable(activeFilteredConversations);
    if (selected && typeof renderTurnsTable === "function") renderTurnsTable(selected);
  } else {
    activeFilteredConversations = sortConversations(filtered, convoSortField, convoSortOrder);
    activeConvoForTurns = null;
    if (typeof renderConversationsTable === "function" && isSessionsActive) renderConversationsTable(activeFilteredConversations);
    const turnsCard = document.getElementById("turns-card");
    if (turnsCard) turnsCard.style.display = "none";
  }
  if (typeof window !== "undefined") {
    window.activeFilteredConversations = activeFilteredConversations;
  }
}

function inspectSessionById(convoId) {
  if (typeof switchTab === "function") switchTab("tab-sessions");
  const convos = (globalDashboardData && globalDashboardData.conversations) || [];
  const target = convos.find(c => c.convo_id === convoId);
  const convoFilter = document.getElementById("convo-filter");
  const searchInput = document.getElementById("convo-search-input");
  if (target) {
    if (convoFilter) convoFilter.value = convoId;
    if (searchInput) searchInput.value = "";
    filterData();
    const turnsCard = document.getElementById("turns-card");
    if (turnsCard) turnsCard.scrollIntoView({ behavior: "smooth" });
  } else {
    if (searchInput) {
      searchInput.value = convoId;
      filterData();
    }
  }
}

function inspectSessionInExplorer(titleOrId) {
  if (typeof switchTab === "function") switchTab("tab-sessions");
  const searchInput = document.getElementById("convo-search-input");
  if (searchInput) {
    searchInput.value = titleOrId;
    filterData();
  }
}

// Delegated click handler for pagination and view controls
document.addEventListener("click", (event) => {
  const target = event.target.closest("[data-action], #btn-convo-prev, #btn-convo-next");
  if (!target) return;
  const action = target.getAttribute("data-action");
  if (action === "prev-convo-page" || target.id === "btn-convo-prev") {
    prevConvoPage();
  } else if (action === "next-convo-page" || target.id === "btn-convo-next") {
    nextConvoPage();
  } else if (action === "toggle-sessions-view") {
    const mode = target.getAttribute("data-view-mode");
    if (mode && typeof setSessionsViewMode === "function") {
      setSessionsViewMode(mode);
    }
  }
});

// Window exports for global interoperability
if (typeof window !== "undefined") {
  window.getModelTruncationThreshold = getModelTruncationThreshold;
  window.convoCurrentPage = convoCurrentPage;
  window.CONVO_PAGE_SIZE = CONVO_PAGE_SIZE;
  window.prevConvoPage = prevConvoPage;
  window.nextConvoPage = nextConvoPage;
  window.convoSortField = convoSortField;
  window.convoSortOrder = convoSortOrder;
  window.sortConversations = sortConversations;
  window.toggleConvoSort = toggleConvoSort;
  window.onConvoSearchChange = onConvoSearchChange;
  window.clearConvoFilters = clearConvoFilters;
  window.filterData = filterData;
  window.sessionsViewMode = sessionsViewMode;
  window.setSessionsViewMode = setSessionsViewMode;
  window.inspectSessionById = inspectSessionById;
  window.inspectSessionInExplorer = inspectSessionInExplorer;
}
