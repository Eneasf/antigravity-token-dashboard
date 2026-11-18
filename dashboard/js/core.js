// ==========================================
// Dashboard: Core State, Shell, Navigation & Boot
// Utilities and formatters extracted to js/core-utils.js (<800 lines rule).
// ==========================================
var globalDashboardData = null;
var activeModelWindow = "5h";
var activeCurrency = "GBP";
var activeTheme = "light";
var activeViewId = "view-now";
if (typeof window !== "undefined") {
  window.activeCurrency = activeCurrency;
  window.activeTheme = activeTheme;
  window.activeViewId = activeViewId;
}
var activeFilteredConversations = [];
var activeConvoForTurns = null;

function updateCurrencyViews() {
  const summary = (globalDashboardData && globalDashboardData.summary) || {};

  // Toggle button active states across header and sidebar dock
  const btnGbp = document.getElementById("btn-curr-gbp");
  const btnUsd = document.getElementById("btn-curr-usd");
  const dockBtnGbp = document.getElementById("dock-btn-curr-gbp");
  const dockBtnUsd = document.getElementById("dock-btn-curr-usd");

  [btnGbp, dockBtnGbp].forEach(btn => {
    if (btn) {
      if (activeCurrency === "GBP") btn.classList.add("active");
      else btn.classList.remove("active");
    }
  });
  [btnUsd, dockBtnUsd].forEach(btn => {
    if (btn) {
      if (activeCurrency === "USD") btn.classList.add("active");
      else btn.classList.remove("active");
    }
  });

  // Card 3: Monthly Pro / Plan Subscription
  const subPriceEl = document.getElementById("quota-sub-price");
  const isFreeTier = (summary.monthly_subscription_price_gbp || 0) === 0 && (summary.monthly_subscription_price_usd || 0) === 0;
  if (subPriceEl) {
    if (isFreeTier) {
      subPriceEl.textContent = activeCurrency === "GBP" ? "£0.00 / mo" : "$0.00 / mo";
    } else {
      subPriceEl.textContent = formatCurrency(
        summary.monthly_subscription_price_usd || 0.0,
        summary.monthly_subscription_price_gbp || 0.0,
        2
      ) + " / mo";
    }
  }
  const subStatusEl = document.getElementById("quota-sub-status");
  if (subStatusEl) {
    if (isFreeTier) {
      subStatusEl.textContent = "Free Tier • £0 monthly subscription fee";
    } else {
      const symbol = activeCurrency === "GBP" ? "£" : "$";
      subStatusEl.textContent = `Renews in ${summary.monthly_renewal_human || "19 days"} • ${symbol}0 marginal cost in quota`;
    }
  }
  const subRoiEl = document.getElementById("quota-sub-roi");
  if (subRoiEl) {
    subRoiEl.textContent = formatCurrency(
      summary.monthly_cycle_imputed_value_usd !== undefined ? summary.monthly_cycle_imputed_value_usd : summary.total_imputed_value_usd,
      summary.monthly_cycle_imputed_value_gbp !== undefined ? summary.monthly_cycle_imputed_value_gbp : summary.total_imputed_value_gbp,
      2
    ) + " API equiv";
  }
  const subRoiMultiplier = document.getElementById("quota-sub-roi-multiplier");
  if (subRoiMultiplier) {
    if (isFreeTier) {
      subRoiMultiplier.textContent = "100% Free (£0 fee)";
    } else {
      const roi = summary.monthly_subscription_roi !== undefined ? summary.monthly_subscription_roi : 1.0;
      subRoiMultiplier.textContent = `${roi.toFixed(1)}x ROI`;
    }
  }

  // Card 4: Prepaid Overage Credit Bank (2,500 Credits)
  const bankSub = document.getElementById("quota-bank-sub");
  if (bankSub) {
    const packPrice = formatCurrency(summary.credit_pack_price_usd || 25.0, summary.credit_pack_price_gbp || 23.99, 2);
    const packsCount = summary.packs_purchased || Math.round((summary.credit_bank_total || 2500) / 2500);
    const packLabel = packsCount > 1 ? `${packsCount} Packs` : "Pack";
    bankSub.textContent = `${packLabel}: ${formatNumber(summary.credit_bank_total || 2500)} credits (${packPrice}) • Auto-reload active`;
  }
  const creditBurnEl = document.getElementById("quota-credit-burn");
  if (creditBurnEl) {
    creditBurnEl.textContent = formatCurrency(
      summary.total_credit_burn_usd,
      summary.total_credit_burn_gbp,
      2
    );
  }
  const bankBalEl = document.getElementById("quota-bank-balance");
  if (bankBalEl) {
    bankBalEl.textContent = formatCurrency(
      summary.credit_bank_remaining_usd !== undefined ? summary.credit_bank_remaining_usd : (summary.total_credit_burn_usd || 0),
      summary.credit_bank_remaining_gbp !== undefined ? summary.credit_bank_remaining_gbp : (summary.total_credit_burn_gbp || 0),
      2
    );
  }
  const execCreditBalEl = document.getElementById("exec-credit-balance");
  if (execCreditBalEl) {
    if (summary.credit_bank_remaining_gbp !== undefined && typeof formatCurrency === "function") {
      execCreditBalEl.textContent = formatCurrency(
        summary.credit_bank_remaining_usd !== undefined ? summary.credit_bank_remaining_usd : (summary.total_credit_burn_usd || 0),
        summary.credit_bank_remaining_gbp,
        2
      );
    }
  }
  const creditsRemHero = document.getElementById("quota-credits-remaining-hero");
  if (creditsRemHero) {
    const rem = summary.credits_remaining !== undefined ? summary.credits_remaining : 2500;
    creditsRemHero.textContent = `${formatNumber(rem)} Left`;
  }
  const creditsBurnedCount = document.getElementById("quota-credits-burned-count");
  if (creditsBurnedCount) {
    creditsBurnedCount.textContent = formatNumber(summary.total_ai_credits_burned || 0);
  }
  const creditsProg = document.getElementById("quota-credits-progress");
  if (creditsProg) {
    const totalBank = summary.credit_bank_total || 2500;
    const totalBurn = summary.total_ai_credits_burned || 0;
    const pctBurn = Math.min(100, Math.max(0, (totalBurn / totalBank) * 100));
    creditsProg.style.width = pctBurn + "%";
  }

  // KPI lifetime financials
  const totalAvoidedUsd = summary.total_avoided_cost_usd !== undefined ? summary.total_avoided_cost_usd : summary.total_imputed_value_usd;
  const totalAvoidedGbp = summary.total_avoided_cost_gbp !== undefined ? summary.total_avoided_cost_gbp : summary.total_imputed_value_gbp;
  const formattedAvoided = formatCurrency(
    totalAvoidedUsd,
    totalAvoidedGbp,
    2
  );
  const kpiTotalCost = document.getElementById("kpi-total-cost");
  if (kpiTotalCost) {
    kpiTotalCost.innerHTML = `<span id="kpi-imputed-val">${formattedAvoided}</span>`;
  }

  const kpiTurnsSub = document.getElementById("kpi-turns-sub");
  if (kpiTurnsSub) {
    const ovgUsd = summary.actual_overage_usd !== undefined ? summary.actual_overage_usd : (summary.total_credit_burn_usd || 0);
    const ovgGbp = summary.actual_overage_gbp !== undefined ? summary.actual_overage_gbp : (summary.total_credit_burn_gbp || 0);
    const covPct = summary.subscription_covered_pct !== undefined ? summary.subscription_covered_pct : 100.0;
    kpiTurnsSub.textContent = `Plan Value (vs. ${formatCurrency(ovgUsd, ovgGbp, 2)} overage) • ${covPct.toFixed(1)}% covered`;
  }

  // Reconciliation table header and subtitle
  const thCashBurn = document.getElementById("th-cash-burn");
  if (thCashBurn) {
    thCashBurn.textContent = activeCurrency === "GBP" ? "Cash Burn (£0.0096/credit)" : "Cash Burn ($0.01/credit)";
  }
  const recSubtitle = document.getElementById("reconciliation-subtitle");
  if (recSubtitle) {
    recSubtitle.textContent = activeCurrency === "GBP"
      ? "Deterministic hourly deductions reconciling with official Google One activity statement (£23.99 / 2,500 credits = £0.0096 / credit)"
      : "Deterministic hourly deductions reconciling with official Google One activity statement ($0.01 / credit)";
  }

  // Re-render active view data tables lazily
  if (activeViewId === "view-now") {
    if (typeof renderExecutiveHero === "function" && globalDashboardData) {
      renderExecutiveHero(globalDashboardData);
    }
    if (typeof renderModelMatrix === "function") renderModelMatrix(activeModelWindow);
    if (typeof renderRecentSessions === "function") renderRecentSessions();
    if (typeof renderRecoveryTimeline === "function") renderRecoveryTimeline();
    if (typeof renderActiveBurstSessions === "function" && globalDashboardData) {
      const q5h = (globalDashboardData.quotas && globalDashboardData.quotas.providers && globalDashboardData.quotas.providers.gemini && globalDashboardData.quotas.providers.gemini.five_hour) || (globalDashboardData.quotas && globalDashboardData.quotas.rolling_5h) || {};
      renderActiveBurstSessions(q5h.active_sessions_5h || []);
    }
    if (typeof renderCacheCoaching === "function" && globalDashboardData && globalDashboardData.summary) {
      renderCacheCoaching(globalDashboardData.summary.cache_coaching);
    }
  } else {
    renderActiveTab(activeViewId);
    if (activeViewId === "view-sessions" && activeConvoForTurns && typeof renderTurnsTable === "function") {
      renderTurnsTable(activeConvoForTurns);
    }
  }
}
function updateWindowToggleStyles() {
  const b5h = document.getElementById("btn-toggle-5h");
  const b1w = document.getElementById("btn-toggle-1w");
  if (!b5h || !b1w) return;
  const quotas = (globalDashboardData && globalDashboardData.quotas) || {};
  const weekly = quotas.weekly_cycle || quotas.rolling_1w || {};
  const dayName = weekly.reset_day_name || "Sunday";
  const dayAbbr = dayName.slice(0, 3);
  b1w.textContent = `Weekly Cycle (${dayAbbr}–${dayAbbr})`;
  if (activeModelWindow === "5h") {
    b5h.classList.add("active");
    b1w.classList.remove("active");
  } else {
    b1w.classList.add("active");
    b5h.classList.remove("active");
  }
}
function updateThemeViews() {
  document.documentElement.setAttribute("data-theme", activeTheme);
  try {
    localStorage.setItem("antigravity_dashboard_theme", activeTheme);
  } catch (e) {}

  const btnLight = document.getElementById("btn-theme-light");
  const btnDark = document.getElementById("btn-theme-dark");
  const dockBtnLight = document.getElementById("dock-btn-theme-light");
  const dockBtnDark = document.getElementById("dock-btn-theme-dark");

  [btnLight, dockBtnLight].forEach(btn => {
    if (btn) {
      if (activeTheme === "light") btn.classList.add("active");
      else btn.classList.remove("active");
    }
  });
  [btnDark, dockBtnDark].forEach(btn => {
    if (btn) {
      if (activeTheme === "dark") btn.classList.add("active");
      else btn.classList.remove("active");
    }
  });

  if (activeTheme === "light") {
    document.documentElement.classList.add("light");
    document.documentElement.classList.remove("dark");
    if (document.body) {
      document.body.classList.add("theme-light");
      document.body.classList.remove("theme-dark");
    }
  } else {
    document.documentElement.classList.add("dark");
    document.documentElement.classList.remove("light");
    if (document.body) {
      document.body.classList.add("theme-dark");
      document.body.classList.remove("theme-light");
    }
  }

  updateCurrencyViews();
  updateWindowToggleStyles();
}
// ==========================================
function toggleSidebar() {
  const dock = document.getElementById("sidebar-dock"); if (dock) {
    dock.classList.toggle("expanded");
  }
}
function setCurrency(curr) {
  activeCurrency = curr;
  if (typeof window !== "undefined") window.activeCurrency = curr;
  updateCurrencyViews();
}
function setTheme(theme) {
  activeTheme = theme;
  if (typeof window !== "undefined") window.activeTheme = theme;
  updateThemeViews();
}
function toggleSidebarExpand() {
  const container = document.getElementById("app-layout-container");
  if (!container) return;
  const isExpanded = container.classList.toggle("sidebar-expanded");
  const footerLabel = document.getElementById("dock-collapse-label"); if (footerLabel) {
    footerLabel.textContent = isExpanded ? "Collapse Sidebar" : "Expand Sidebar";
  }
  try {
    localStorage.setItem("antigravity_sidebar_expanded", isExpanded ? "true" : "false");
  } catch (e) {}
}
function toggleSidebarCollapse() {
  toggleSidebarExpand();
}

// ==========================================
// Table Scroll Fades & Overflow Indicators (M61 / U8)
// ==========================================
function updateTableScrollFade(wrapper) {
  if (!wrapper) return;
  const container = wrapper.closest ? wrapper.closest('.table-scroll-container') : null;
  if (!container) return;
  const isAtEnd = (wrapper.scrollLeft + wrapper.clientWidth) >= (wrapper.scrollWidth - 3);
  if (isAtEnd) {
    container.classList.add('is-scrolled-end');
  } else {
    container.classList.remove('is-scrolled-end');
  }
}
if (typeof window !== "undefined") {
  window.updateTableScrollFade = updateTableScrollFade;
  window.initScrollFades = initScrollFades;
}

function initScrollFades() {
  const wrappers = document.querySelectorAll('.table-scroll-wrapper');
  wrappers.forEach(function(w) {
    updateTableScrollFade(w);
  });
}

document.addEventListener('scroll', function(e) {
  const target = e.target;
  if (target && target.classList && target.classList.contains('table-scroll-wrapper')) {
    updateTableScrollFade(target);
  }
}, true);

if (typeof window !== "undefined") {
  window.addEventListener('resize', function() {
    initScrollFades();
  });
}

var isBooted = false;
function bootOnce() {
  if (isBooted) return;
  isBooted = true;
  initShellMode();
  initMicroTooltips();
  // Determine initial theme: check data-theme on <html> first, then localStorage
  const docTheme = document.documentElement.getAttribute("data-theme");
  if (docTheme === "light" || docTheme === "dark") {
    activeTheme = docTheme;
  } else {
    try {
      const savedTheme = localStorage.getItem("antigravity_dashboard_theme");
      if (savedTheme === "light" || savedTheme === "dark") {
        activeTheme = savedTheme;
      }
    } catch (e) {}
  }
  updateThemeViews();
  // Setup global delegated click handling for data-action elements (CSP-compliant)
  document.addEventListener("click", (event) => {
    const target = event.target.closest("[data-action]");
    if (!target) return;
    const action = target.getAttribute("data-action");
    if (!action) return;
    if (action === "switch-tab") {
      const tabId = target.getAttribute("data-tab");
      if (tabId) switchTab(tabId);
    } else if (action === "set-currency") {
      const curr = target.getAttribute("data-currency");
      if (curr && curr !== activeCurrency) {
        activeCurrency = curr;
        updateCurrencyViews();
      }
    } else if (action === "set-theme") {
      const theme = target.getAttribute("data-theme");
      if (theme && theme !== activeTheme) {
        activeTheme = theme;
        updateThemeViews();
      }
    } else if (action === "set-shell-mode") {
      const shell = target.getAttribute("data-shell");
      if (shell) setShellMode(shell);
    } else if (action === "toggle-sidebar") {
      toggleSidebarExpand();
    } else if (action === "clear-convo-filters") {
      clearConvoFilters();
    } else if (action === "toggle-convo-sort") {
      const sortKey = target.getAttribute("data-sort-key");
      if (sortKey) toggleConvoSort(sortKey);
    } else if (action === "close-turns-card") {
      closeTurnsCard();
    } else if (action === "select-archetype") {
      const arch = target.getAttribute("data-archetype");
      if (arch) selectArchetypePreset(arch);
    } else if (action === "close-inspector-drawer") {
      closeInspectorDrawer();
    } else if (action === "toggle-turn-sort") {
      toggleTurnSort();
    } else if (action === "toggle-project-branches") {
      event.stopPropagation();
      const pIdx = parseInt(target.getAttribute("data-project-idx"), 10);
      if (!isNaN(pIdx)) toggleProjectBranches(pIdx);
    } else if (action === "inspect-session") {
      const convoId = target.getAttribute("data-convo-id");
      if (convoId) {
        if (typeof inspectSessionById === "function") inspectSessionById(convoId);
        else if (typeof inspectSession === "function") inspectSession(convoId);
      }
    } else if (action === "select-swarm") {
      const swarmId = target.getAttribute("data-swarm-id");
      if (swarmId) selectSwarmById(swarmId);
    } else if (action === "inspect-swarm-node") {
      const nodeId = target.getAttribute("data-node-id");
      if (nodeId) inspectSwarmNode(nodeId);
    } else if (action === "toggle-burst-sessions") {
      toggleBurstSessionsList();
    } else if (action === "copy-handover-summary") {
      const convoId = target.getAttribute("data-convo-id");
      if (convoId && typeof window.copyHandoverSummary === "function") {
        window.copyHandoverSummary(convoId, target);
      }
    } else if (action === "toggle-context-audit-drawer") {
      if (typeof window.toggleContextAuditDrawer === "function") {
        window.toggleContextAuditDrawer();
      }
    } else if (action === "toggle-header-overflow") {
      event.stopPropagation();
      const menu = document.getElementById("header-overflow-menu");
      const btn = document.getElementById("btn-header-overflow");
      if (menu) {
        const isHidden = menu.style.display === "none" || !menu.style.display;
        menu.style.display = isHidden ? "flex" : "none";
        if (btn) btn.setAttribute("aria-expanded", isHidden ? "true" : "false");
      }
    } else if (action === "copy-standup") {
      const menu = document.getElementById("header-overflow-menu");
      const btn = document.getElementById("btn-header-overflow");
      if (menu) menu.style.display = "none";
      if (btn) btn.setAttribute("aria-expanded", "false");
    }
  });
  // Close header overflow menu on outside click
  document.addEventListener("click", (e) => {
    const menu = document.getElementById("header-overflow-menu");
    const btn = document.getElementById("btn-header-overflow");
    if (menu && menu.style.display !== "none" && !menu.contains(e.target) && !btn?.contains(e.target)) {
      menu.style.display = "none";
      if (btn) btn.setAttribute("aria-expanded", "false");
    }
  });
  // Setup window toggles
  const btnToggle5h = document.getElementById("btn-toggle-5h"); if (btnToggle5h) {
    btnToggle5h.addEventListener("click", () => {
      activeModelWindow = "5h";
      updateWindowToggleStyles();
      renderModelMatrix("5h");
    });
  }
  const btnToggle1w = document.getElementById("btn-toggle-1w"); if (btnToggle1w) {
    btnToggle1w.addEventListener("click", () => {
      activeModelWindow = "1w";
      updateWindowToggleStyles();
      renderModelMatrix("1w");
    });
  }
  // Shell mode toggle button in dock
  const btnShellToggle = document.getElementById("btn-shell-toggle"); if (btnShellToggle) {
    btnShellToggle.addEventListener("click", () => {
      toggleShellMode();
    });
  }
  // Standup Summary Markdown Copy
  const btnCopyStandup = document.getElementById("btn-copy-standup");
  const btnCopyStandupText = document.getElementById("btn-copy-standup-text");
  if (btnCopyStandup) {
    btnCopyStandup.addEventListener("click", async () => {
      const data = globalDashboardData || window.__TELEMETRY_DATA__;
      if (!data) return;
      const text = generateStandupMarkdown(data);
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          const ta = document.createElement("textarea");
          ta.value = text;
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          document.body.removeChild(ta);
        }
        if (btnCopyStandupText) btnCopyStandupText.textContent = "Copied!";
        setTimeout(() => {
          if (btnCopyStandupText) btnCopyStandupText.textContent = "Copy Summary";
        }, 2000);
      } catch (err) {
        console.error("Failed to copy standup digest:", err);
      }
    });
  }
  // Event Listeners for Filters
  const wsSelect = document.getElementById("workspace-filter"); if (wsSelect) {
    wsSelect.addEventListener("change", () => filterData((globalDashboardData && globalDashboardData.conversations) || []));
  }
  const agentFilter = document.getElementById("agent-filter"); if (agentFilter) {
    agentFilter.addEventListener("change", () => filterData((globalDashboardData && globalDashboardData.conversations) || []));
  }
  const subagentViewFilter = document.getElementById("subagent-view-filter"); if (subagentViewFilter) {
    subagentViewFilter.addEventListener("change", () => filterData((globalDashboardData && globalDashboardData.conversations) || []));
  }
  const convoSelect = document.getElementById("convo-filter"); if (convoSelect) {
    convoSelect.addEventListener("change", () => filterData((globalDashboardData && globalDashboardData.conversations) || []));
  }
  const searchInput = document.getElementById("convo-search-input"); if (searchInput) {
    searchInput.addEventListener("input", () => filterData((globalDashboardData && globalDashboardData.conversations) || []));
  }
  // Subsystems boot (listeners & controls)
  initAutoRefresh();
  initPlanManagerModal();
  initSimulator();
  if (typeof initWeeklyTrends === "function") {
    initWeeklyTrends();
  }
  // Deep linking via URL hash, parameters, or stored active tab
  function handleTabRouting() {
    try {
      let targetTab = null;
      if (window.location && window.location.hash) {
        const rawHash = window.location.hash.replace(/^#/, "");
        if (rawHash.startsWith("tab-")) {
          targetTab = rawHash;
        } else if (["now", "sessions", "projects", "swarms", "billing", "plan", "quotas", "credits", "simulator"].includes(rawHash)) {
          targetTab = "tab-" + (rawHash === "quotas" ? "now" : (rawHash === "credits" ? "billing" : (rawHash === "simulator" ? "plan" : rawHash)));
        }
      }
      if (!targetTab) {
        const urlParams = new URLSearchParams(window.location.search);
        targetTab = urlParams.get("tab");
      }
      if (!targetTab) {
        try { targetTab = localStorage.getItem("antigravity_active_tab"); } catch(e) {}
      }
      if (targetTab && ["tab-now", "tab-sessions", "tab-projects", "tab-swarms", "tab-billing", "tab-plan", "tab-quotas", "tab-credits", "tab-simulator"].includes(targetTab)) {
        switchTab(targetTab);
      } else {
        switchTab("tab-now");
      }
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get("expand_project") !== null) {
        const pIdx = parseInt(urlParams.get("expand_project"), 10) || 0;
        setTimeout(() => toggleProjectBranches(pIdx), 50);
      }
    } catch (e) {}
  }
  handleTabRouting();
  window.addEventListener("hashchange", handleTabRouting);
  initScrollFades();
}
function renderActiveTab(targetViewId) {
  const vid = targetViewId || activeViewId || "view-now";
  if (vid === "view-now") {
    renderRecentSessions();
  } else if (vid === "view-sessions") {
    if (typeof populateSessionFilterDropdowns === "function") {
      populateSessionFilterDropdowns();
    }
    if (typeof renderConversationsTable === "function") {
      renderConversationsTable(activeFilteredConversations);
    }
  } else if (vid === "view-projects") {
    if (typeof renderPortfolioView === "function") {
      renderPortfolioView();
    }
  } else if (vid === "view-swarms") {
    if (typeof renderSwarmsView === "function" && globalDashboardData) {
      renderSwarmsView(globalDashboardData);
    }
    if (typeof renderToolAnalytics === "function" && globalDashboardData) {
      renderToolAnalytics(globalDashboardData);
    }
  } else if (vid === "view-billing") {
    if (typeof renderHourlyCreditActivity === "function") {
      renderHourlyCreditActivity();
    }
    if (typeof renderWeeklyTrends === "function" && globalDashboardData) {
      renderWeeklyTrends(globalDashboardData);
    }
  } else if (vid === "view-plan") {
    if (typeof runSimulation === "function") {
      runSimulation();
    }
    if (typeof renderPlanManagerContent === "function") {
      renderPlanManagerContent();
    }
  }
}

function switchTab(tabId) {
  const tabMap = {
    "tab-now": "view-now",
    "tab-sessions": "view-sessions",
    "tab-projects": "view-projects",
    "tab-swarms": "view-swarms",
    "tab-billing": "view-billing",
    "tab-plan": "view-plan",
    // Direct and backward-compatibility aliases
    "swarms": "view-swarms",
    "sessions": "view-sessions",
    "projects": "view-projects",
    "billing": "view-billing",
    "plan": "view-plan",
    "now": "view-now",
    "tab-quotas": "view-now",
    "tab-credits": "view-billing",
    "tab-simulator": "view-plan"
  };
  activeViewId = tabMap[tabId] || "view-now";
  if (typeof window !== "undefined") {
    window.activeViewId = activeViewId;
  }
  const normalizedTabId = (tabId === "tab-quotas" || tabId === "now") ? "tab-now" :
                          (tabId === "tab-credits" || tabId === "billing") ? "tab-billing" :
                          (tabId === "tab-simulator" || tabId === "plan") ? "tab-plan" :
                          (tabId === "swarms") ? "tab-swarms" :
                          (tabId === "sessions") ? "tab-sessions" :
                          (tabId === "projects") ? "tab-projects" : tabId;
  try {
    localStorage.setItem("antigravity_active_tab", normalizedTabId);
  } catch(e) {}
  // Update tab buttons across top bar, sidebar dock, and mobile bottom nav
  ["tab-now", "tab-sessions", "tab-projects", "tab-swarms", "tab-billing", "tab-plan"].forEach(tid => {
    const baseName = tid.replace("tab-", "");
    const isAct = (tid === normalizedTabId);
    [document.getElementById(tid),
     document.getElementById(`dock-tab-${baseName}`),
     document.getElementById(`mob-tab-${baseName}`)].forEach(el => {
      if (el) {
        el.classList.toggle("active", isAct);
        el.setAttribute("aria-selected", isAct ? "true" : "false");
      }
    });
  });
  // Update views
  ["view-now", "view-sessions", "view-projects", "view-swarms", "view-billing", "view-plan"].forEach(vid => {
    const v = document.getElementById(vid);
    if (v) {
      const isAct = (vid === activeViewId);
      v.classList.toggle("active", isAct);
      v.style.display = isAct ? "block" : "none";
    }
  });
  renderActiveTab(activeViewId);
  initScrollFades();
}

function render(data) {
  if (data && typeof data === "object") {
    globalDashboardData = data;
  } else if (window.__TELEMETRY_DATA__ && typeof window.__TELEMETRY_DATA__ === "object") {
    globalDashboardData = window.__TELEMETRY_DATA__;
  } else {
    const dataEl = document.getElementById("injected-dashboard-data");
    try {
      globalDashboardData = JSON.parse(dataEl ? dataEl.textContent || "{}" : "{}");
    } catch (e) {
      console.error("Failed to parse injected telemetry data:", e);
      return;
    }
  }
  // Check for saved plan override in localStorage
  try {
    const savedPlanStr = localStorage.getItem("antigravity_selected_plan");
    if (savedPlanStr) {
      const savedPlan = JSON.parse(savedPlanStr);
      applyPlanToGlobalData(savedPlan, false);
    }
  } catch (e) {
    console.warn("Could not load saved plan override:", e);
  }
  const summary = globalDashboardData.summary || {};
  const quotas = globalDashboardData.quotas || {};
  const convos = globalDashboardData.conversations || [];
  const workspaces = globalDashboardData.workspaces || [];
  // Toggle Demo Mode Showcase Banner
  const isDemo = summary.is_demo || (window.location && ((window.location.search && (window.location.search.includes("demo=1") || window.location.search.includes("demo=true"))) || (window.location.hostname && window.location.hostname.includes("github.io"))));
  const demoBanner = document.getElementById("demo-mode-banner"); if (demoBanner) {
    demoBanner.style.display = isDemo ? "block" : "none";
  }
  activeFilteredConversations = convos;
  activeConvoForTurns = null;
  // Update Header Badges & Subscription Status
  document.getElementById("session-count-badge").textContent = `${convos.length} Sessions`;
  const subscriptionStatus = summary.subscription_status || "SAFE_IN_QUOTA";
  const statusBadge = document.getElementById("sub-status-badge");
  if (summary.tier === "free") { statusBadge.className = "badge camel"; statusBadge.textContent = "Free Quota Allowance"; }
  else if (subscriptionStatus === "SAFE_IN_QUOTA") {
    statusBadge.className = "badge green";
    const tierShortName = (summary.tier && summary.tier.startsWith("ultra")) ? "Ultra" : ((summary.tier === "pro") ? "Pro" : (summary.tier ? summary.tier.toUpperCase() : "Quota"));
    statusBadge.textContent = `Safe · ${tierShortName} Quota`;
  } else if (subscriptionStatus === "WEEKLY_EXHAUSTED") { statusBadge.className = "badge red"; statusBadge.textContent = "Weekly Quota Exhausted"; }
  else if (subscriptionStatus === "RECOVERED_COOLDOWN") { statusBadge.className = "badge camel"; statusBadge.textContent = "Recovered (Cooldown)"; }
  else { statusBadge.className = "badge amber"; statusBadge.textContent = "Burning AI Credits"; }
  const billingBadge = document.getElementById("billing-cycle-badge"); if (billingBadge) {
    let renStr = summary.monthly_renewal_display || "Renewal";
    if (summary.monthly_renewal_utc) { try { const d = new Date(summary.monthly_renewal_utc); if (!isNaN(d.getTime())) renStr = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" }).format(d); } catch (e) {} }
    billingBadge.textContent = `Billing: Renews ${renStr} (${summary.monthly_renewal_human || "19 days"} left)`;
  }
  const freshnessBadge = document.getElementById("data-freshness-badge"); if (freshnessBadge) {
    let tStr = "";
    if (window.__TELEMETRY_META__?.generated_at) { try { const d = new Date(window.__TELEMETRY_META__.generated_at); if (!isNaN(d.getTime())) tStr = ` · updated ${new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", hour12: false }).format(d)}`; } catch (e) {} }
    freshnessBadge.textContent = `Local · read-only${tStr}`;
  }
  const tierBadge = document.getElementById("header-tier-badge"); if (tierBadge) {
    const pName = (summary.temporal_provenance && summary.temporal_provenance.active_plan && summary.temporal_provenance.active_plan.name) || summary.subscription_name || "Pro Tier";
    tierBadge.textContent = pName.includes("Enterprise") ? "Enterprise Tier Active" : (pName.includes("Ultra") ? "Ultra Tier Active" : "Pro Tier Active");
  }
  // Populate 5h Window Box (safe checks)
  // Render Now View cards & tickers
  if (typeof renderNowView === "function") {
    renderNowView(globalDashboardData);
  }
  updateThemeViews();
  renderRecoveryTimeline();
  if (typeof renderActiveBurstSessions === "function") {
    const q5h = (quotas.providers && quotas.providers.gemini && quotas.providers.gemini.five_hour) || quotas.rolling_5h || {};
    renderActiveBurstSessions(q5h.active_sessions_5h || []);
  }
  if (typeof renderCacheCoaching === "function") {
    renderCacheCoaching(summary.cache_coaching);
  }
  // Initialize Token Ticker HUD (ADR-053 / M39)
  if (window.__TELEMETRY_META__ && window.__TELEMETRY_META__.ticker) {
    updateTokenTicker(window.__TELEMETRY_META__.ticker);
  } else if (globalDashboardData && globalDashboardData.live_ticker) {
    updateTokenTicker(globalDashboardData.live_ticker);
  }
  // --- M42 & M88: Degraded Sessions Check (Live Active Session Scoped) ---
  if (typeof checkDegradedSessions === "function") {
    checkDegradedSessions(convos, globalDashboardData && globalDashboardData.current_session);
  }
  // Plan Profile Manager defaults (summary.tier)
  const tierSelect = document.getElementById("plan-tier-select"); if (tierSelect && summary.tier) {
    if (Array.from(tierSelect.options).some(opt => opt.value === summary.tier)) {
      tierSelect.value = summary.tier;
    }
    const customFields = document.getElementById("plan-custom-fields"); if (customFields) {
      customFields.style.display = tierSelect.value === "custom" ? "block" : "none";
    }
  }
  // Simulator plan default & run
  const planSelect = document.getElementById("sim-plan-select"); if (planSelect && summary.tier) {
    if (Array.from(planSelect.options).some(opt => opt.value === summary.tier)) {
      planSelect.value = summary.tier;
    }
  }
  updateCurrencyViews();
  if (activeViewId !== "view-now") {
    renderActiveTab(activeViewId);
  }
  // Deep linking: open_turns if specified
  try {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("open_turns") !== null && convos.length > 0) {
      const cIdx = parseInt(urlParams.get("open_turns"), 10) || 0;
      if (convos[cIdx] && convoSelect) {
        convoSelect.value = convos[cIdx].convo_id;
        activeConvoForTurns = convos[cIdx];
        renderTurnsTable(convos[cIdx]);
      }
    }
  } catch (e) {}
  initScrollFades();
}
function initDashboard() {
  bootOnce();
  render(globalDashboardData);
}
window.bootOnce = bootOnce;
window.render = render;
window.renderActiveTab = renderActiveTab;
window.initDashboard = initDashboard;
window.switchTab = switchTab;
window.setCurrency = setCurrency;
window.setTheme = setTheme;
window.setShellMode = setShellMode;

window.Antigravity = window.Antigravity || {};
window.Antigravity.bootOnce = bootOnce;
window.Antigravity.render = render;
window.Antigravity.renderActiveTab = renderActiveTab;
window.Antigravity.initDashboard = initDashboard;
window.Antigravity.switchTab = switchTab;
window.Antigravity.setCurrency = setCurrency;
window.Antigravity.setTheme = setTheme;
window.Antigravity.setShellMode = setShellMode;

document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
});
