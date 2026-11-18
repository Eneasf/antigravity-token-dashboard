/**
 * Turn-by-Turn Telemetry Inspector & Turns Table Component
 * Milestone 55 (Row 9: C5 - Minified data.js & Lazy Turns)
 *
 * Extracted from dashboard/js/sessions.js to enforce the <800 lines budget.
 * Handles:
 *   - openTurnsDrawer(convo)
 *   - closeInspectorDrawer()
 *   - renderTurnsTable(convo, sortOrder)
 *   - toggleTurnSort()
 *   - closeTurnsCard()
 *   - Lazy loading of turns.js / turns.demo.js via window.__TELEMETRY_TURNS__
 */

// Sorting & active session state
let turnSortOrder = "desc";
let currentConvoForTurns = null;
let currentDrawerConvo = null;
let turnsScriptLoading = false;
const turnsLoadCallbacks = [];

/**
 * Determine whether demo mode is active.
 */
function isTurnsDemoMode() {
  if (typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.summary && globalDashboardData.summary.is_demo) {
    return true;
  }
  try {
    const params = new URLSearchParams(window.location.search);
    if (params.get("demo") === "1" || params.get("demo") === "true") return true;
    if (window.location.hostname && window.location.hostname.includes("github.io")) return true;
  } catch (e) {}
  return false;
}

/**
 * Dynamically load turns.js or turns.demo.js on demand.
 */
function loadTurnsScript(callback) {
  if (typeof window.__TELEMETRY_TURNS__ !== "undefined") {
    if (typeof callback === "function") callback(null, window.__TELEMETRY_TURNS__);
    return;
  }

  if (typeof callback === "function") {
    turnsLoadCallbacks.push(callback);
  }

  if (turnsScriptLoading) return;
  turnsScriptLoading = true;

  const scriptSrc = isTurnsDemoMode() ? "turns.demo.js" : "turns.js";
  const script = document.createElement("script");
  script.src = scriptSrc;
  script.async = true;

  script.onload = function() {
    turnsScriptLoading = false;
    window.__TELEMETRY_TURNS__ = window.__TELEMETRY_TURNS__ || {};
    const cbs = turnsLoadCallbacks.slice();
    turnsLoadCallbacks.length = 0;
    cbs.forEach(cb => {
      try {
        cb(null, window.__TELEMETRY_TURNS__);
      } catch (err) {
        console.error("Error in turns script load callback:", err);
      }
    });
  };

  script.onerror = function() {
    turnsScriptLoading = false;
    const cbs = turnsLoadCallbacks.slice();
    turnsLoadCallbacks.length = 0;
    const err = new Error("Failed to load telemetry turns script (" + scriptSrc + ")");
    cbs.forEach(cb => {
      try {
        cb(err);
      } catch (cbErr) {
        console.error("Error in turns script error callback:", cbErr);
      }
    });
  };

  document.head.appendChild(script);
}

let lastFocusedElementBeforeDrawer = null;

function handleDrawerKeydown(e) {
  if (e.key === "Escape") {
    e.preventDefault();
    closeInspectorDrawer();
    return;
  }
  if (e.key === "Tab") {
    const drawer = document.getElementById("desktop-inspector-drawer");
    if (!drawer) return;
    const focusable = drawer.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
}

/**
 * Open the inspector drawer.
 */
function openInspectorDrawer() {
  lastFocusedElementBeforeDrawer = document.activeElement;
  const drawer = document.getElementById("desktop-inspector-drawer");
  const backdrop = document.getElementById("drawer-backdrop");
  if (drawer) {
    drawer.setAttribute("role", "dialog");
    drawer.setAttribute("aria-modal", "true");
    drawer.classList.add("open");
    drawer.style.visibility = "visible";
    const closeBtn = drawer.querySelector('[data-action="close-drawer"]') || drawer.querySelector('button');
    if (closeBtn) closeBtn.focus();
    drawer.removeEventListener("keydown", handleDrawerKeydown);
    drawer.addEventListener("keydown", handleDrawerKeydown);
  }
  if (backdrop) backdrop.classList.add("open");
}
window.openInspectorDrawer = openInspectorDrawer;

/**
 * Close the inspector drawer.
 */
function closeInspectorDrawer() {
  const drawer = document.getElementById("desktop-inspector-drawer");
  const backdrop = document.getElementById("drawer-backdrop");
  if (drawer) {
    drawer.classList.remove("open");
    drawer.style.visibility = "";
    drawer.removeEventListener("keydown", handleDrawerKeydown);
  }
  if (backdrop) backdrop.classList.remove("open");
  document.body.style.overflow = "";
  if (lastFocusedElementBeforeDrawer && typeof lastFocusedElementBeforeDrawer.focus === "function") {
    try { lastFocusedElementBeforeDrawer.focus(); } catch (e) {}
    lastFocusedElementBeforeDrawer = null;
  }
}
window.closeInspectorDrawer = closeInspectorDrawer;

/**
 * Close the inline turns card in the Sessions explorer.
 */
function closeTurnsCard() {
  const card = document.getElementById("turns-card");
  if (card) card.style.display = "none";
  const convoFilter = document.getElementById("convo-filter");
  if (convoFilter) convoFilter.value = "all";
  if (typeof activeConvoForTurns !== "undefined") {
    activeConvoForTurns = null;
  }
  currentConvoForTurns = null;
}
window.closeTurnsCard = closeTurnsCard;

/**
 * Toggle sorting of turns (newest first vs oldest first).
 */
function toggleTurnSort() {
  const newOrder = turnSortOrder === "desc" ? "asc" : "desc";
  turnSortOrder = newOrder;

  if (currentConvoForTurns) {
    renderTurnsTable(currentConvoForTurns, newOrder);
  }
  const drawer = document.getElementById("desktop-inspector-drawer");
  if (drawer && drawer.classList.contains("open") && currentDrawerConvo) {
    const turns = (currentDrawerConvo.turns && currentDrawerConvo.turns.length > 0)
      ? currentDrawerConvo.turns
      : ((window.__TELEMETRY_TURNS__ && window.__TELEMETRY_TURNS__[currentDrawerConvo.convo_id]) || []);
    renderTurnsDrawerContent(currentDrawerConvo, turns, newOrder);
  }
}
window.toggleTurnSort = toggleTurnSort;

/**
 * Format milliseconds into a compact string (e.g. 75ms or 1.8s).
 */
function formatLatencyMs(ms) {
  if (ms === null || ms === undefined || isNaN(ms) || ms <= 0) return null;
  if (ms >= 1000) {
    return (ms / 1000).toFixed(1) + "s";
  }
  return Math.round(ms) + "ms";
}

/**
 * Render a compact TTFT / Latency badge.
 */
function renderLatencyBadge(t) {
  const ttft = formatLatencyMs(t.ttft_ms);
  const lat = formatLatencyMs(t.latency_ms);
  if (!ttft && !lat) return '<span style="color: var(--text-muted); font-family: \'Geist Mono\', monospace; font-size: 0.7rem;">—</span>';
  if (ttft && lat) {
    return `<span class="code-pill" style="font-family: 'Geist Mono', monospace; font-size: 0.7rem; white-space: nowrap;" title="Time to First Token: ${ttft}, Total Turn Latency: ${lat}">TTFT ${ttft} &bull; ${lat}</span>`;
  } else if (ttft) {
    return `<span class="code-pill" style="font-family: 'Geist Mono', monospace; font-size: 0.7rem; white-space: nowrap;" title="Time to First Token: ${ttft}">TTFT ${ttft}</span>`;
  } else {
    return `<span class="code-pill" style="font-family: 'Geist Mono', monospace; font-size: 0.7rem; white-space: nowrap;" title="Total Turn Latency: ${lat}">${lat}</span>`;
  }
}

/**
 * Find step indices where a turn at >=40k tokens suffered a 0% KV cache hit on a model switch.
 */
function findKvCacheWipeSteps(turns) {
  const wipeSet = new Set();
  if (!turns || turns.length < 2) return wipeSet;
  const chrono = [...turns].sort((a, b) => {
    const tsA = a.timestamp || "";
    const tsB = b.timestamp || "";
    if (tsA && tsB) return tsA.localeCompare(tsB);
    return (a.step_idx || 0) - (b.step_idx || 0);
  });
  for (let i = 1; i < chrono.length; i++) {
    const prev = chrono[i - 1];
    const curr = chrono[i];
    const prevM = prev.model_name || prev.model_id;
    const currM = curr.model_name || curr.model_id;
    const totalIn = curr.total_input_tokens || ((curr.prompt_tokens_uncached || 0) + (curr.cached_tokens || 0));
    const cached = curr.cached_tokens || 0;
    if (prevM && currM && prevM !== currM && totalIn >= 40000 && cached === 0) {
      wipeSet.add(curr.step_idx);
    }
  }
  return wipeSet;
}

/**
 * Renders turns drawer body content.
 */
function renderTurnsDrawerContent(convo, turns, sortOrder) {
  sortOrder = sortOrder || turnSortOrder || "desc";
  const body = document.getElementById("drawer-body");
  if (!body) return;

  turns = turns || [];
  const avoidedUsd = convo.avoided_cost_usd !== undefined ? convo.avoided_cost_usd : (convo.estimated_cost_usd || 0.0);
  const avoidedGbp = convo.avoided_cost_gbp !== undefined ? convo.avoided_cost_gbp : (convo.estimated_cost_gbp || 0.0);

  if (turns.length === 0) {
    body.innerHTML = '<div class="empty-state" style="padding: 40px;">No turns recorded for this conversation.</div>';
    return;
  }

  // KPI Bar in Drawer
  const totalInput = convo.total_input_tokens || 0;
  const cacheHitPct = convo.cache_hit_ratio_pct || 0.0;
  const cachedTokens = convo.cached_tokens || 0;
  const ovgCredits = convo.actual_overage_credits || 0;

  let kpiHtml = `
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 8px; margin-bottom: 16px; background: var(--surface-subdock); padding: 12px; border-radius: 6px; border: 1px solid var(--card-border);">
      <div>
        <div style="font-size: 0.6875rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Input Tokens</div>
        <div style="font-size: 0.9375rem; font-weight: 700; font-family: 'Geist Mono', monospace; color: var(--text-main);">${formatNumber(totalInput)}</div>
      </div>
      <div>
        <div style="font-size: 0.6875rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Cache Hit Ratio</div>
        <div style="font-size: 0.9375rem; font-weight: 700; font-family: 'Geist Mono', monospace; color: var(--accent-mint);">${cacheHitPct.toFixed(1)}%</div>
        <div style="font-size: 0.6875rem; color: var(--text-muted); font-family: 'Geist Mono', monospace;">${formatCompactNumber(cachedTokens)} cached</div>
      </div>
      <div>
        <div style="font-size: 0.6875rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Avoided Cost</div>
        <div style="font-size: 0.9375rem; font-weight: 700; font-family: 'Geist Mono', monospace; color: var(--accent-mint);">${formatCurrency(avoidedUsd, avoidedGbp, 2)}</div>
      </div>
      <div>
        <div style="font-size: 0.6875rem; color: var(--text-muted); text-transform: uppercase; font-weight: 600;">Plan Quota Status</div>
        <div style="font-size: 0.8125rem; font-weight: 700;">${ovgCredits > 0 ? '<span style="color: var(--accent-amber);">429 Overage</span>' : '<span style="color: var(--accent-mint);">100% In Plan</span>'}</div>
      </div>
    </div>
    <div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
      <span style="font-size: 0.8125rem; font-weight: 700; color: var(--text-primary);">${turns.length} Turn Trajectory</span>
      <button class="sort-toggle-btn" data-action="toggle-turn-sort" title="Reverse sort order">Reverse Order</button>
    </div>
    <div class="table-container" style="max-height: calc(100vh - 240px); overflow-y: auto;">
      <table class="data-table" style="font-size: 0.775rem;">
        <thead>
          <tr>
            <th>#</th>
            <th>Time</th>
            <th>Model</th>
            <th>Tokens</th>
            <th>Cache</th>
            <th>TTFT / Latency</th>
            <th>Thinking</th>
            <th>Avoided</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
  `;

  const kvWipeSteps = findKvCacheWipeSteps(turns);

  // Sort turns reverse chronological or chronological
  const sortedTurns = [...turns].sort((a, b) => {
    const tsA = a.timestamp || "";
    const tsB = b.timestamp || "";
    if (tsA && tsB) {
      return sortOrder === "desc" ? tsB.localeCompare(tsA) : tsA.localeCompare(tsB);
    }
    const idxA = a.step_idx || 0;
    const idxB = b.step_idx || 0;
    return sortOrder === "desc" ? (idxB - idxA) : (idxA - idxB);
  });

  sortedTurns.forEach(t => {
    const ts = t.timestamp ? formatUkTimestamp(t.timestamp) : "N/A";
    const isOvg = Boolean(t.is_overage);
    const statusBadge = isOvg
      ? '<span class="code-pill" style="color: var(--accent-amber); background: rgba(245,158,11,0.12); font-weight: 600;">429 Overage</span>'
      : '<span class="code-pill" style="color: var(--accent-mint); background: rgba(16,185,129,0.12); font-weight: 600;">In Plan</span>';
    const tAvoidedUsd = t.avoided_cost_usd !== undefined ? t.avoided_cost_usd : (t.estimated_cost_usd || 0.0);
    const tAvoidedGbp = t.avoided_cost_gbp !== undefined ? t.avoided_cost_gbp : (t.estimated_cost_gbp || 0.0);
    const totalIn = t.total_input_tokens || ((t.prompt_tokens_uncached || 0) + (t.cached_tokens || 0));
    const thk = t.thinking_tokens || 0;
    const latBadge = renderLatencyBadge(t);
    const kvWipe = kvWipeSteps.has(t.step_idx)
      ? ' <span class="code-pill" style="color: var(--accent-amber); background: rgba(245,158,11,0.15); border: 1px solid rgba(245,158,11,0.3); font-size: 0.65rem; font-weight: 600;" title="KV Cache Evicted: 0% hit on model switch at >=40k tokens">&#9889; KV Evicted</span>'
      : '';

    kpiHtml += `
      <tr>
        <td><strong>#${t.step_idx}</strong></td>
        <td style="font-size: 0.7rem; color: var(--text-muted); white-space: nowrap;">${ts}</td>
        <td><span class="code-pill">${escapeHtml(t.model_name || t.model_id)}</span>${kvWipe}</td>
        <td style="font-family: 'Geist Mono', monospace;">${formatNumber(totalIn)}</td>
        <td><strong style="color: var(--accent-mint); font-family: 'Geist Mono', monospace;">${(t.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></td>
        <td>${latBadge}</td>
        <td style="font-family: 'Geist Mono', monospace; color: var(--accent-purple);">${thk > 0 ? formatNumber(thk) : '—'}</td>
        <td><strong style="color: var(--accent-mint); font-family: 'Geist Mono', monospace;">${formatCurrency(tAvoidedUsd, tAvoidedGbp, 4)}</strong></td>
        <td>${statusBadge}</td>
      </tr>
    `;
  });

  kpiHtml += `
        </tbody>
      </table>
    </div>
  `;
  body.innerHTML = kpiHtml;
}

/**
 * Open slide-over drawer for turn inspection with lazy turns loading.
 */
function openTurnsDrawer(convo) {
  if (!convo) return;
  currentDrawerConvo = convo;

  const drawer = document.getElementById("desktop-inspector-drawer");
  const backdrop = document.getElementById("drawer-backdrop");
  const heading = document.getElementById("drawer-heading");
  const subheading = document.getElementById("drawer-subheading");
  const body = document.getElementById("drawer-body");
  if (!drawer || !body) return;

  const title = convo.title || "Untitled Session";
  const ws = convo.workspace || "Default Workspace";
  const totalTurns = convo.turn_count || (convo.turns ? convo.turns.length : 0);
  const avoidedUsd = convo.avoided_cost_usd !== undefined ? convo.avoided_cost_usd : (convo.estimated_cost_usd || 0.0);
  const avoidedGbp = convo.avoided_cost_gbp !== undefined ? convo.avoided_cost_gbp : (convo.estimated_cost_gbp || 0.0);

  if (heading) heading.textContent = title;
  if (subheading) subheading.textContent = `${ws} • ${totalTurns} turns • Avoided API Cost: ${formatCurrency(avoidedUsd, avoidedGbp, 2)}`;

  // Case a: convo.turns already populated
  if (convo.turns && convo.turns.length > 0) {
    renderTurnsDrawerContent(convo, convo.turns, turnSortOrder);
    drawer.classList.add("open");
    if (backdrop) backdrop.classList.add("open");
    document.body.style.overflow = "hidden";
    return;
  }

  // Case b: window.__TELEMETRY_TURNS__ already loaded
  if (typeof window.__TELEMETRY_TURNS__ !== "undefined") {
    convo.turns = window.__TELEMETRY_TURNS__[convo.convo_id] || [];
    renderTurnsDrawerContent(convo, convo.turns, turnSortOrder);
    drawer.classList.add("open");
    if (backdrop) backdrop.classList.add("open");
    document.body.style.overflow = "hidden";
    return;
  }

  // Case c: lazy load turns script
  body.innerHTML = `
    <div class="empty-state" style="padding: 60px 20px; text-align: center;">
      <svg width="28" height="28" viewBox="0 0 24 24" style="animation: spin 0.8s linear infinite; display: inline-block; margin-bottom: 12px;">
        <style>@keyframes spin { to { transform: rotate(360deg); } }</style>
        <circle cx="12" cy="12" r="10" stroke="var(--card-border)" stroke-width="3" fill="none" />
        <path d="M12 2 A 10 10 0 0 1 22 12" stroke="var(--accent-mint)" stroke-width="3" fill="none" stroke-linecap="round" />
      </svg>
      <div style="font-size: 0.875rem; font-weight: 600; color: var(--text-main); margin-bottom: 4px;">Loading session trajectory...</div>
      <div style="font-size: 0.75rem; color: var(--text-muted);">Fetching turn-by-turn telemetry decomposition</div>
    </div>
  `;
  drawer.classList.add("open");
  if (backdrop) backdrop.classList.add("open");
  document.body.style.overflow = "hidden";

  loadTurnsScript(function(err, turnsMap) {
    if (err) {
      if (currentDrawerConvo && currentDrawerConvo.convo_id === convo.convo_id) {
        body.innerHTML = `
          <div class="empty-state" style="padding: 40px; text-align: center; color: var(--accent-red);">
            <div style="font-weight: 600; margin-bottom: 4px;">Failed to load session turns</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(err.message || "Failed to load telemetry turns")}</div>
          </div>
        `;
      }
      return;
    }
    convo.turns = (turnsMap && turnsMap[convo.convo_id]) || [];
    if (currentDrawerConvo && currentDrawerConvo.convo_id === convo.convo_id) {
      renderTurnsDrawerContent(convo, convo.turns, turnSortOrder);
    }
  });
}
window.openTurnsDrawer = openTurnsDrawer;

/**
 * Render turns table HTML content inside #turns-card.
 */
function renderTurnsTableContent(convo, turns, sortOrder) {
  const turnsCard = document.getElementById("turns-card");
  if (!turnsCard) return;

  if (!turns || turns.length === 0) {
    turnsCard.style.display = "none";
    return;
  }

  sortOrder = sortOrder || turnSortOrder || "desc";
  turnsCard.style.display = "block";
  const titleEl = document.getElementById("turns-title");
  if (titleEl) titleEl.textContent = `Turns for: ${convo.title || "Untitled"}`;
  const sortLabel = sortOrder === "desc" ? "Most recent on top ↓" : "Oldest on top ↑";
  const countEl = document.getElementById("turns-table-count");
  if (countEl) {
    countEl.innerHTML = `${turns.length} turns &bull; <button class="sort-toggle-btn" data-action="toggle-turn-sort" title="Click to reverse sort order">${sortLabel}</button>`;
  }

  const tbody = document.getElementById("turns-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  // Sort turns in reverse chronological order by default (most recent on top)
  const sortedTurns = [...turns].sort((a, b) => {
    const tsA = a.timestamp || "";
    const tsB = b.timestamp || "";
    if (tsA && tsB) {
      return sortOrder === "desc" ? tsB.localeCompare(tsA) : tsA.localeCompare(tsB);
    }
    const idxA = a.step_idx || 0;
    const idxB = b.step_idx || 0;
    return sortOrder === "desc" ? (idxB - idxA) : (idxA - idxB);
  });

  const kvWipeSteps = findKvCacheWipeSteps(turns);

  sortedTurns.forEach(t => {
    const tr = document.createElement("tr");
    const ts = t.timestamp ? formatUkTimestamp(t.timestamp) : "N/A";
    const isOvg = Boolean(t.is_overage);
    let statusBadge = '';
    if (isOvg) {
      statusBadge = '<span class="code-pill" style="color: var(--accent-amber); background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); font-weight: 600;">429 Overage</span>';
    } else {
      statusBadge = '<span class="code-pill" style="color: var(--accent-green); background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3); font-weight: 600;">In Plan</span>';
    }
    const tAvoidedUsd = t.avoided_cost_usd !== undefined ? t.avoided_cost_usd : (t.estimated_cost_usd || 0.0);
    const tAvoidedGbp = t.avoided_cost_gbp !== undefined ? t.avoided_cost_gbp : (t.estimated_cost_gbp || 0.0);
    const latBadge = (t.ttft_ms || t.latency_ms) ? renderLatencyBadge(t) : '';
    const kvWipe = kvWipeSteps.has(t.step_idx)
      ? ' <span class="code-pill" style="color: var(--accent-amber); background: rgba(245,158,11,0.15); border: 1px solid rgba(245,158,11,0.3); font-size: 0.65rem; font-weight: 600;" title="KV Cache Evicted: 0% hit on model switch at >=40k tokens">&#9889; KV Evicted</span>'
      : '';
    tr.innerHTML = `
      <td>#${t.step_idx}</td>
      <td style="font-size: 0.75rem; color: var(--text-muted);">${ts}</td>
      <td>
        <span class="code-pill">${escapeHtml(t.model_name || t.model_id)}</span>${kvWipe}
        ${latBadge ? `<div style="margin-top: 3px;">${latBadge}</div>` : ''}
      </td>
      <td class="highlight-camel">${formatNumber(t.prompt_tokens_uncached)}</td>
      <td class="highlight-green">${formatNumber(t.cached_tokens)}</td>
      <td>${formatNumber(t.total_input_tokens)}</td>
      <td><strong>${(t.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></td>
      <td>${formatNumber(t.output_tokens_total)} <span style="font-size: 0.75rem; color: var(--accent-purple);">(${formatNumber(t.thinking_tokens)} thk)</span></td>
      <td>${statusBadge}</td>
      <td><strong class="highlight-green">${formatCurrency(tAvoidedUsd, tAvoidedGbp, 4)}</strong></td>
      <td><span class="code-pill" style="max-width: 120px; display: inline-block; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(t.response_id || "N/A")}</span></td>
    `;
    tbody.appendChild(tr);
  });

  turnsCard.scrollIntoView({ behavior: "smooth" });
}

/**
 * Render turns table inside Sessions explorer with lazy loading.
 */
function renderTurnsTable(convo, sortOrder = "desc") {
  const turnsCard = document.getElementById("turns-card");
  if (!convo) {
    if (turnsCard) turnsCard.style.display = "none";
    return;
  }
  currentConvoForTurns = convo;
  turnSortOrder = sortOrder;

  // Case a: convo.turns already populated
  if (convo.turns && convo.turns.length > 0) {
    renderTurnsTableContent(convo, convo.turns, sortOrder);
    return;
  }

  // Case b: window.__TELEMETRY_TURNS__ already loaded
  if (typeof window.__TELEMETRY_TURNS__ !== "undefined") {
    convo.turns = window.__TELEMETRY_TURNS__[convo.convo_id] || [];
    if (convo.turns.length === 0) {
      if (turnsCard) turnsCard.style.display = "none";
      return;
    }
    renderTurnsTableContent(convo, convo.turns, sortOrder);
    return;
  }

  // Case c: lazy load turns script
  if (turnsCard) {
    turnsCard.style.display = "block";
    const titleEl = document.getElementById("turns-title");
    if (titleEl) titleEl.textContent = `Turns for: ${convo.title || "Untitled"}`;
    const countEl = document.getElementById("turns-table-count");
    if (countEl) countEl.innerHTML = '<span style="color: var(--text-muted);">Loading trajectory...</span>';
    const tbody = document.getElementById("turns-tbody");
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="11" class="empty-state" style="padding: 30px; text-align: center;">
            <svg width="24" height="24" viewBox="0 0 24 24" style="animation: spin 0.8s linear infinite; display: inline-block; margin-bottom: 8px;">
              <style>@keyframes spin { to { transform: rotate(360deg); } }</style>
              <circle cx="12" cy="12" r="10" stroke="var(--card-border)" stroke-width="3" fill="none" />
              <path d="M12 2 A 10 10 0 0 1 22 12" stroke="var(--accent-mint)" stroke-width="3" fill="none" stroke-linecap="round" />
            </svg>
            <div style="font-size: 0.8125rem; color: var(--text-muted);">Loading session trajectory...</div>
          </td>
        </tr>
      `;
    }
    turnsCard.scrollIntoView({ behavior: "smooth" });
  }

  loadTurnsScript(function(err, turnsMap) {
    if (err) {
      if (currentConvoForTurns && currentConvoForTurns.convo_id === convo.convo_id) {
        const tbody = document.getElementById("turns-tbody");
        if (tbody) {
          tbody.innerHTML = `
            <tr>
              <td colspan="11" class="empty-state" style="padding: 24px; text-align: center; color: var(--accent-red);">
                Failed to load session trajectory (${escapeHtml(err.message || "Error")}).
              </td>
            </tr>
          `;
        }
      }
      return;
    }

    convo.turns = (turnsMap && turnsMap[convo.convo_id]) || [];
    if (currentConvoForTurns && currentConvoForTurns.convo_id === convo.convo_id) {
      if (convo.turns.length === 0) {
        if (turnsCard) turnsCard.style.display = "none";
      } else {
        renderTurnsTableContent(convo, convo.turns, turnSortOrder);
      }
    }
  });
}
window.renderTurnsTable = renderTurnsTable;
