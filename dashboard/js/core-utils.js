// ==========================================
// Dashboard: Core Utilities, Formatters & Tooltips
// ==========================================

function getCatalog() {
  return (typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.catalog) ||
         (typeof window !== "undefined" && window.__TELEMETRY_DATA__ && window.__TELEMETRY_DATA__.catalog) ||
         { models: {}, families: {}, quota_tracks: [], plan_tiers: {}, simulator_archetypes: [] };
}

function formatNumber(num) {
  return (num || 0).toLocaleString();
}

function formatCompactNumber(num) {
  if (num === null || num === undefined) return "0";
  const abs = Math.abs(num);
  if (abs >= 1000000000) return (num / 1000000000).toFixed(1) + "B";
  if (abs >= 1000000) return (num / 1000000).toFixed(1) + "M";
  if (abs >= 1000) return (num / 1000).toFixed(1) + "k";
  return num.toString();
}

function formatLocalizedResetTime(utcTimestamp, fallbackDisplay) {
  if (utcTimestamp) {
    try {
      const d = new Date(utcTimestamp);
      if (!isNaN(d.getTime())) {
        return new Intl.DateTimeFormat(undefined, {
          weekday: "long",
          hour: "2-digit",
          minute: "2-digit",
          timeZoneName: "short",
        }).format(d);
      }
    } catch (e) {}
  }
  return fallbackDisplay || (typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.quotas && globalDashboardData.quotas.weekly_cycle && globalDashboardData.quotas.weekly_cycle.reset_display) || "Weekly Reset";
}

function formatCurrency(usdVal, gbpVal, decimals = 2) {
  const summary = (typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.summary) || {};
  const fxRate = summary.usd_to_gbp_fx_rate || 0.79;
  const curr = typeof activeCurrency !== "undefined" ? activeCurrency : "GBP";
  if (curr === "GBP") {
    const val = (gbpVal !== undefined && gbpVal !== null) ? gbpVal : ((usdVal || 0) * fxRate);
    return "£" + Number(val || 0).toFixed(decimals);
  } else {
    return "$" + Number(usdVal || 0).toFixed(decimals);
  }
}

function formatCost(val, decimals = 2) {
  return formatCurrency(val, null, decimals);
}

// Micro tooltip controller (ADR-048)
function initMicroTooltips() {
  const tooltip = document.getElementById("app-micro-tooltip");
  if (!tooltip) return;
  document.addEventListener("mouseover", (e) => {
    const target = e.target.closest("[data-tooltip]");
    if (!target) return;
    const text = target.getAttribute("data-tooltip");
    if (!text) return;
    tooltip.innerHTML = text;
    tooltip.style.display = "block";
    tooltip.style.opacity = "1";
  });
  document.addEventListener("mousemove", (e) => {
    if (tooltip.style.display !== "block") return;
    const pad = 12;
    const tipWidth = tooltip.offsetWidth || 180;
    const tipHeight = tooltip.offsetHeight || 36;
    let left = e.clientX + pad;
    let top = e.clientY + pad;
    if (left + tipWidth > window.innerWidth - 12) {
      left = e.clientX - tipWidth - pad;
    }
    if (top + tipHeight > window.innerHeight - 12) {
      top = e.clientY - tipHeight - pad;
    }
    tooltip.style.left = `${Math.max(12, left)}px`;
    tooltip.style.top = `${Math.max(12, top)}px`;
  });
  document.addEventListener("mouseout", (e) => {
    const target = e.target.closest("[data-tooltip]");
    if (!target) return;
    tooltip.style.opacity = "0";
    tooltip.style.display = "none";
  });
}

// Keyboard escape dismissal for drawers, menus and modals
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    if (typeof closeInspectorDrawer === "function") closeInspectorDrawer();
    if (typeof closePlanModal === "function") closePlanModal();
    const menu = document.getElementById("header-overflow-menu");
    if (menu && menu.style.display !== "none") {
      menu.style.display = "none";
      const btn = document.getElementById("btn-header-overflow");
      if (btn) btn.setAttribute("aria-expanded", "false");
    }
  }
});

function getSplinePath(points) {
  if (!points || points.length === 0) return "";
  if (points.length === 1) return `M ${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`;
  if (points.length === 2) {
    return `M ${points[0].x.toFixed(1)},${points[0].y.toFixed(1)} L ${points[1].x.toFixed(1)},${points[1].y.toFixed(1)}`;
  }
  let d = `M ${points[0].x.toFixed(1)},${points[0].y.toFixed(1)}`;
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i === 0 ? 0 : i - 1];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[i + 2 < points.length ? i + 2 : i + 1];
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${p2.x.toFixed(1)},${p2.y.toFixed(1)}`;
  }
  return d;
}

function escapeHtml(str) {
  return (str || "").toString()
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatUkDateShort(isoStr) {
  if (!isoStr) return "";
  const dt = new Date(isoStr);
  if (isNaN(dt.getTime())) {
    const parts = isoStr.slice(0, 10).split("-");
    if (parts.length === 3) {
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const mIdx = parseInt(parts[1], 10) - 1;
      return `${parts[2]} ${months[mIdx] || parts[1]}`;
    }
    return isoStr;
  }
  const day = String(dt.getUTCDate()).padStart(2, "0");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${day} ${months[dt.getUTCMonth()]}`;
}

function formatUkDate(isoStr) {
  if (!isoStr) return "—";
  const dt = new Date(isoStr);
  if (isNaN(dt.getTime())) {
    const parts = isoStr.slice(0, 10).split("-");
    if (parts.length === 3) {
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const mIdx = parseInt(parts[1], 10) - 1;
      return `${parts[2]} ${months[mIdx] || parts[1]} ${parts[0]}`;
    }
    return isoStr;
  }
  const day = String(dt.getUTCDate()).padStart(2, "0");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${day} ${months[dt.getUTCMonth()]} ${dt.getUTCFullYear()}`;
}

function formatUkTimestamp(isoStr) {
  if (!isoStr) return "N/A";
  const dt = new Date(isoStr);
  if (isNaN(dt.getTime())) return isoStr.replace("T", " ").replace("+00:00", "Z");
  const day = String(dt.getUTCDate()).padStart(2, "0");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const mon = months[dt.getUTCMonth()];
  const year = dt.getUTCFullYear();
  const hh = String(dt.getUTCHours()).padStart(2, "0");
  const mm = String(dt.getUTCMinutes()).padStart(2, "0");
  const ss = String(dt.getUTCSeconds()).padStart(2, "0");
  return `${day} ${mon} ${year}, ${hh}:${mm}:${ss} UTC`;
}

// ==========================================
// Shell Layout Mode Controller (M42.1 / M58)
// ==========================================
function setShellMode(mode) {
  const container = document.getElementById("app-layout-container");
  const label = document.getElementById("shell-toggle-label");
  const targetMode = (mode === "top") ? "top" : "side";
  if (container) {
    container.classList.remove("shell-mode-side");
    container.classList.remove("shell-mode-top");
    container.classList.add(`shell-mode-${targetMode}`);
  }
  const btnSide = document.getElementById("btn-shell-side");
  const btnTop = document.getElementById("btn-shell-top");
  if (btnSide) btnSide.classList.toggle("active", targetMode === "side");
  if (btnTop) btnTop.classList.toggle("active", targetMode === "top");
  if (label) {
    label.textContent = targetMode === "side" ? "Top Bar" : "Sidebar";
  }
  try {
    localStorage.setItem("user_shell_preference", targetMode);
    localStorage.setItem("antigravity_shell_mode", targetMode);
  } catch (e) {}
}

function toggleShellMode() {
  const container = document.getElementById("app-layout-container");
  const isTop = container && container.classList.contains("shell-mode-top");
  setShellMode(isTop ? "side" : "top");
}

function initShellMode() {
  let saved = null;
  try {
    saved = localStorage.getItem("user_shell_preference") || localStorage.getItem("antigravity_shell_mode");
  } catch (e) {}
  if (!saved && window.__INITIAL_SHELL__) {
    saved = window.__INITIAL_SHELL__;
  }
  const effectiveMode = saved || "side";
  setShellMode(effectiveMode);
  try {
    const isExpanded = localStorage.getItem("antigravity_sidebar_expanded") === "true";
    const container = document.getElementById("app-layout-container");
    if (isExpanded && container && effectiveMode === "side") {
      container.classList.add("sidebar-expanded");
      const footerLabel = document.getElementById("dock-collapse-label");
      if (footerLabel) footerLabel.textContent = "Collapse Sidebar";
    }
  } catch (e) {}
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

// Window exports for backward compatibility and test suites
if (typeof window !== "undefined") {
  window.getCatalog = getCatalog;
  window.formatNumber = formatNumber;
  window.formatCompactNumber = formatCompactNumber;
  window.formatLocalizedResetTime = formatLocalizedResetTime;
  window.formatCurrency = formatCurrency;
  window.formatCost = formatCost;
  window.initMicroTooltips = initMicroTooltips;
  window.getSplinePath = getSplinePath;
  window.escapeHtml = escapeHtml;
  window.formatUkDateShort = formatUkDateShort;
  window.formatUkDate = formatUkDate;
  window.formatUkTimestamp = formatUkTimestamp;
  window.setShellMode = setShellMode;
  window.toggleShellMode = toggleShellMode;
  window.initShellMode = initShellMode;
  window.updateTableScrollFade = updateTableScrollFade;
  window.initScrollFades = initScrollFades;
  window.__updateTableScrollFade = updateTableScrollFade;
  window.__initScrollFades = initScrollFades;

  window.Antigravity = window.Antigravity || {};
  window.Antigravity.getCatalog = getCatalog;
  window.Antigravity.formatNumber = formatNumber;
  window.Antigravity.formatCompactNumber = formatCompactNumber;
  window.Antigravity.formatCurrency = formatCurrency;
  window.Antigravity.escapeHtml = escapeHtml;
}
