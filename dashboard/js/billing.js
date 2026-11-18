// ==========================================
// Dashboard: Billing & Historical Weekly Trends
// ==========================================

var activeTrendMetric = "tokens"; // 'tokens' | 'cost' | 'bvi' | 'roi'

function renderHourlyCreditActivity() {
  const activity = (globalDashboardData && globalDashboardData.hourly_credit_activity) || [];
  const summary = (globalDashboardData && globalDashboardData.summary) || {};
  const card = document.getElementById("credit-reconciliation-card");
  const tbody = document.getElementById("reconciliation-tbody");
  const badge = document.getElementById("reconciliation-total-badge");

  if (!card || !tbody) return;

  const totalBurn = summary.total_ai_credits_burned || 0;
  const formattedTotalCost = formatCurrency(summary.total_credit_burn_usd, summary.total_credit_burn_gbp, 2);
  if (badge) {
    if (totalBurn > 0) {
      badge.textContent = `${formatNumber(totalBurn)} Credits Burned (${formattedTotalCost})`;
    } else {
      badge.textContent = "0 Credits Burned";
    }
  }

  if (!activity || activity.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No AI credit deductions recorded. Usage within Pro subscription quota.</td></tr>';
    return;
  }

  tbody.innerHTML = "";
  activity.forEach(item => {
    const tr = document.createElement("tr");
    const modelsArr = Object.entries(item.models || {}).map(
      ([mName, count]) => `${escapeHtml(mName)} (${formatNumber(count)} turns)`
    );
    const modelsText = modelsArr.length > 0 ? modelsArr.join(", ") : "Gemini Pro / Flash";
    const isBonus = item.event_type === "QUOTA_RESET_BONUS" || item.reason === "QUOTA_RESET_BONUS";

    if (isBonus) {
      const bonusPct = item.bonus_pct_forgiven ? `+${item.bonus_pct_forgiven.toFixed(1)}%` : "100%";
      const bonusCredits = item.bonus_credits_forgiven || 0;
      const bonusValueText = (item.bonus_value_usd || item.bonus_value_gbp)
        ? `${formatCurrency(item.bonus_value_usd, item.bonus_value_gbp, 2)} forgiven`
        : "£0.00 ($0.00)";
      const descTitle = item.description ? ` title="${escapeHtml(item.description)}"` : "";
      tr.innerHTML = `
        <td><strong>${escapeHtml(item.hour_display || item.hour_timestamp)}</strong></td>
        <td><span class="badge green"${descTitle} style="font-size: 0.72rem; padding: 2px 8px;">Unscheduled Quota Reset (${bonusPct} Bonus)</span></td>
        <td>${formatNumber(item.turns_count)}</td>
        <td><strong class="highlight-green">0 (+${formatNumber(bonusCredits)} forgiven)</strong></td>
        <td><strong class="highlight-green">${bonusValueText}</strong></td>
        <td style="font-size: 0.8125rem; color: var(--text-muted);">${modelsText}</td>
      `;
    } else {
      tr.innerHTML = `
        <td><strong>${escapeHtml(item.hour_display || item.hour_timestamp)}</strong></td>
        <td><span class="code-pill">Google One AI Credit Burn</span></td>
        <td>${formatNumber(item.turns_count)}</td>
        <td><strong class="highlight-red">-${formatNumber(item.credits_burned)}</strong></td>
        <td><strong class="highlight-red">${formatCurrency(item.credit_burn_usd, item.credit_burn_gbp, 2)}</strong></td>
        <td style="font-size: 0.8125rem; color: var(--text-muted);">${modelsText}</td>
      `;
    }
    tbody.appendChild(tr);
  });
}

function initWeeklyTrends() {
  const btnTokens = document.getElementById("btn-trend-tokens");
  const btnCost = document.getElementById("btn-trend-cost");
  const btnBvi = document.getElementById("btn-trend-bvi");
  const btnRoi = document.getElementById("btn-trend-roi");

  if (btnTokens && !btnTokens._bound) {
    btnTokens._bound = true;
    btnTokens.addEventListener("click", () => {
      activeTrendMetric = "tokens";
      updateTrendMetricButtons();
      renderWeeklyTrends(globalDashboardData);
    });
  }
  if (btnCost && !btnCost._bound) {
    btnCost._bound = true;
    btnCost.addEventListener("click", () => {
      activeTrendMetric = "cost";
      updateTrendMetricButtons();
      renderWeeklyTrends(globalDashboardData);
    });
  }
  if (btnBvi && !btnBvi._bound) {
    btnBvi._bound = true;
    btnBvi.addEventListener("click", () => {
      activeTrendMetric = "bvi";
      updateTrendMetricButtons();
      renderWeeklyTrends(globalDashboardData);
    });
  }
  if (btnRoi && !btnRoi._bound) {
    btnRoi._bound = true;
    btnRoi.addEventListener("click", () => {
      activeTrendMetric = "roi";
      updateTrendMetricButtons();
      renderWeeklyTrends(globalDashboardData);
    });
  }
}

function updateTrendMetricButtons() {
  const btnTokens = document.getElementById("btn-trend-tokens");
  const btnCost = document.getElementById("btn-trend-cost");
  const btnBvi = document.getElementById("btn-trend-bvi");
  const btnRoi = document.getElementById("btn-trend-roi");

  if (btnTokens) btnTokens.classList.toggle("active", activeTrendMetric === "tokens");
  if (btnCost) btnCost.classList.toggle("active", activeTrendMetric === "cost");
  if (btnBvi) btnBvi.classList.toggle("active", activeTrendMetric === "bvi");
  if (btnRoi) btnRoi.classList.toggle("active", activeTrendMetric === "roi");
}

function renderWeeklyTrends(data) {
  const card = document.getElementById("weekly-trends-card");
  if (!card) return;

  const trends = (data && data.weekly_trends) || (globalDashboardData && globalDashboardData.weekly_trends) || { cycles: [], summary: {} };
  const cycles = trends.cycles || [];
  const summary = trends.summary || {};

  // Badge & KPIs
  const badge = document.getElementById("trends-cycle-count-badge");
  if (badge) {
    badge.textContent = `${summary.cycles_analyzed || cycles.length} Cycles Analyzed`;
  }

  const kpiAvgTokens = document.getElementById("trends-kpi-avg-tokens");
  if (kpiAvgTokens) {
    kpiAvgTokens.textContent = summary.average_tokens_per_week ? formatCompactNumber(summary.average_tokens_per_week) : "—";
  }

  const kpiAvgCost = document.getElementById("trends-kpi-avg-cost");
  if (kpiAvgCost) {
    if (activeCurrency === "GBP") {
      kpiAvgCost.textContent = summary.average_cost_per_week_gbp ? `£${summary.average_cost_per_week_gbp.toFixed(2)}` : "—";
    } else {
      kpiAvgCost.textContent = summary.average_cost_per_week_usd ? `$${summary.average_cost_per_week_usd.toFixed(2)}` : "—";
    }
  }

  const kpiPeakTokens = document.getElementById("trends-kpi-peak-tokens");
  if (kpiPeakTokens) {
    kpiPeakTokens.textContent = summary.peak_week_tokens ? formatCompactNumber(summary.peak_week_tokens) : "—";
  }

  const kpiPeakLabel = document.getElementById("trends-kpi-peak-label");
  if (kpiPeakLabel) {
    kpiPeakLabel.textContent = summary.peak_week_label && summary.peak_week_label !== "—" ? `Peak: ${summary.peak_week_label}` : "Highest recorded week";
  }

  const kpiGrowth = document.getElementById("trends-kpi-growth");
  if (kpiGrowth) {
    const g = summary.token_growth_rate_pct || 0;
    kpiGrowth.textContent = `${g >= 0 ? "+" : ""}${g.toFixed(1)}%`;
    kpiGrowth.style.color = g > 20 ? "var(--accent-amber)" : (g >= 0 ? "var(--accent-green)" : "var(--text-muted)");
  }

  // Render SVG Chart
  renderWeeklyTrendsSvg(cycles, activeTrendMetric);

  // Render Table
  renderWeeklyTrendsTable(cycles);
}

function renderWeeklyTrendsSvg(cycles, metric) {
  const svg = document.getElementById("weekly-trends-svg");
  const container = document.getElementById("weekly-trends-svg-container");
  const tooltip = document.getElementById("weekly-trends-tooltip");
  if (!svg || !container) return;

  if (!cycles || cycles.length === 0) {
    svg.innerHTML = `
      <text x="380" y="110" text-anchor="middle" fill="var(--text-muted)" font-size="14">
        No historical weekly cycles recorded in vault.
      </text>`;
    return;
  }

  const width = 760;
  const height = 220;
  const padding = { top: 25, right: 35, bottom: 45, left: 65 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  // Values according to metric
  let values = [];
  let formatVal = (v) => v.toString();
  let metricColor = "var(--camel-500)"; // Warm Camel
  let metricName = "Processed Tokens";

  if (metric === "cost") {
    values = cycles.map(c => activeCurrency === "GBP" ? (c.estimated_cost_gbp || 0) : (c.estimated_cost_usd || 0));
    const sym = activeCurrency === "GBP" ? "£" : "$";
    formatVal = (v) => `${sym}${v.toFixed(2)}`;
    metricColor = "var(--accent-mint)"; // Emerald Mint
    metricName = activeCurrency === "GBP" ? "Estimated Value (£)" : "Estimated Value ($)";
  } else if (metric === "bvi") {
    values = cycles.map(c => c.peak_bvi || 0);
    formatVal = (v) => `${v.toFixed(2)}x`;
    metricColor = "var(--accent-purple)"; // Warm Violet
    metricName = "Peak Burn Velocity (BVI)";
  } else if (metric === "roi") {
    values = cycles.map(c => {
      if (c.roi_multiplier !== undefined) return c.roi_multiplier;
      const s = c.cycle_start_utc ? c.cycle_start_utc.slice(0, 10) : "";
      const isUltra = s >= "2026-09-13";
      const costGbp = c.estimated_cost_gbp || 0;
      const subGbp = isUltra ? 18.46 : 4.38;
      const ovgGbp = c.actual_overage_gbp || 0;
      const denomGbp = subGbp + ovgGbp;
      return denomGbp > 0 ? Number((costGbp / denomGbp).toFixed(2)) : 0.0;
    });
    formatVal = (v) => `${v.toFixed(1)}x`;
    metricColor = "var(--accent-purple)";
    metricName = "Subscription ROI";
  } else {
    values = cycles.map(c => c.total_processed_tokens || 0);
    formatVal = (v) => formatCompactNumber(v);
    metricColor = "var(--camel-500)"; // Warm Camel
    metricName = "Processed Tokens";
  }

  const maxVal = Math.max(...values, 0);
  let yCeil = maxVal;
  if (metric === "bvi") {
    yCeil = Math.max(2.0, maxVal * 1.2);
  } else if (metric === "roi") {
    yCeil = Math.max(5.0, maxVal * 1.25);
  } else if (metric === "cost") {
    yCeil = Math.max(10.0, maxVal * 1.25);
  } else {
    yCeil = Math.max(1000000, maxVal * 1.15);
  }
  if (yCeil <= 0) yCeil = 1;

  const n = cycles.length;
  const getX = (i) => padding.left + (n > 1 ? (i / (n - 1)) * plotW : plotW / 2);
  const getY = (val) => padding.top + plotH - (val / yCeil) * plotH;

  // Coordinate arrays
  const coords = values.map((val, i) => ({
    x: getX(i),
    y: getY(val),
    val,
    cycle: cycles[i],
    idx: i
  }));

  // Build Cubic Spline Area and Line paths (Warm Editorial)
  const linePath = getSplinePath(coords);
  const areaBaseY = (padding.top + plotH).toFixed(1);
  const areaPath = `${linePath} L ${coords[coords.length - 1].x.toFixed(1)},${areaBaseY} L ${coords[0].x.toFixed(1)},${areaBaseY} Z`;

  // Grid lines & labels (4 levels)
  let gridHtml = "";
  const ticks = [0, 0.333, 0.666, 1.0];
  ticks.forEach(t => {
    const yVal = yCeil * t;
    const yPos = padding.top + plotH - (t * plotH);
    gridHtml += `
      <line x1="${padding.left}" y1="${yPos.toFixed(1)}" x2="${padding.left + plotW}" y2="${yPos.toFixed(1)}" stroke="var(--card-border)" stroke-dasharray="3 3" opacity="0.4" />
      <text x="${padding.left - 10}" y="${(yPos + 4).toFixed(1)}" text-anchor="end" fill="var(--text-muted)" font-size="10" font-family="'Geist Mono', monospace">${formatVal(yVal)}</text>
    `;
  });

  // Reference 1.0x line for BVI pinned to far right margin
  let refLineHtml = "";
  if (metric === "bvi" && yCeil >= 1.0) {
    const refY = getY(1.0);
    refLineHtml = `
      <line x1="${padding.left}" y1="${refY.toFixed(1)}" x2="${padding.left + plotW}" y2="${refY.toFixed(1)}" stroke="var(--accent-mint)" stroke-dasharray="4 2" stroke-width="1.2" opacity="0.7" />
      <text x="${padding.left + plotW - 4}" y="${(refY - 4).toFixed(1)}" text-anchor="end" fill="var(--accent-mint)" font-size="9" font-weight="600" font-family="'Geist Mono', monospace">1.0x Sustainable</text>
    `;
  }

  // Overage highlights
  let overageHtml = "";
  coords.forEach(pt => {
    if (pt.cycle.actual_overage_credits > 0) {
      const colW = Math.max(22, (plotW / n) * 0.8);
      overageHtml += `
        <rect x="${(pt.x - colW / 2).toFixed(1)}" y="${padding.top}" width="${colW.toFixed(1)}" height="${plotH}" fill="rgba(245, 158, 11, 0.1)" rx="4" />
        <text x="${pt.x.toFixed(1)}" y="${padding.top + 12}" text-anchor="middle" fill="var(--status-warning)" font-size="8.5" font-weight="700" font-family="'Geist Mono', monospace">OVERAGE</text>
      `;
    }
  });

  // X Axis Labels (UK format: e.g. "03 Sep")
  let xLabelsHtml = "";
  coords.forEach((pt, i) => {
    const sDt = pt.cycle.cycle_start_utc ? formatUkDateShort(pt.cycle.cycle_start_utc) : `W${i + 1}`;
    const isCur = pt.cycle.is_current_cycle;
    const labelText = isCur ? `${sDt} ●` : sDt;
    xLabelsHtml += `
      <text x="${pt.x.toFixed(1)}" y="${(padding.top + plotH + 18).toFixed(1)}" text-anchor="middle" fill="${isCur ? 'var(--accent-mint)' : 'var(--text-muted)'}" font-size="10" font-weight="${isCur ? '700' : '500'}" font-family="'Geist Mono', monospace">
        ${labelText}
      </text>
    `;
  });

  // Data Points
  let pointsHtml = "";
  coords.forEach((pt, i) => {
    const isCur = pt.cycle.is_current_cycle || (i === coords.length - 1);
    const hasOvg = pt.cycle.actual_overage_credits > 0;
    const pointClass = `trendline-point ${metric} ${hasOvg ? 'overage' : ''} ${isCur ? 'current' : ''}`;
    let halo = "";
    if (isCur) {
      halo = `<circle cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="7" fill="none" stroke="${metricColor}" stroke-width="1.5" stroke-dasharray="2 2" opacity="0.8" />`;
    }
    pointsHtml += `
      ${halo}
      <circle class="${pointClass}" cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="4" data-idx="${pt.idx}" fill="${metricColor}" />
    `;
  });

  // Era Cutover Line at 2026-09-13 (Pro -> Ultra 5x)
  let cutoverHtml = "";
  let cutoverIdx = -1;
  for (let i = 0; i < cycles.length; i++) {
    const c = cycles[i];
    const s = c.cycle_start_utc ? c.cycle_start_utc.slice(0, 10) : "";
    const e = c.cycle_end_utc ? c.cycle_end_utc.slice(0, 10) : "";
    if ((s && s <= "2026-09-13" && (!e || e >= "2026-09-13")) || (s && s.startsWith("2026-09-13"))) {
      cutoverIdx = i;
      break;
    }
  }
  if (cutoverIdx === -1 && cycles.length > 1) {
    const firstStart = cycles[0].cycle_start_utc ? cycles[0].cycle_start_utc.slice(0, 10) : "";
    const lastStart = cycles[cycles.length - 1].cycle_start_utc ? cycles[cycles.length - 1].cycle_start_utc.slice(0, 10) : "";
    if (firstStart <= "2026-09-13" && lastStart >= "2026-09-13") {
      for (let i = 0; i < cycles.length; i++) {
        const s = cycles[i].cycle_start_utc ? cycles[i].cycle_start_utc.slice(0, 10) : "";
        if (s >= "2026-09-13") {
          cutoverIdx = i;
          break;
        }
      }
    }
  }
  if (cutoverIdx !== -1) {
    const cx = getX(cutoverIdx);
    cutoverHtml = `
      <line x1="${cx.toFixed(1)}" y1="${padding.top}" x2="${cx.toFixed(1)}" y2="${padding.top + plotH}" stroke="var(--accent-amber)" stroke-dasharray="4 3" stroke-width="1.5" opacity="0.85" />
      <text x="${cx.toFixed(1)}" y="${padding.top - 8}" text-anchor="middle" fill="var(--accent-amber)" font-size="9" font-weight="700" font-family="'Geist Mono', monospace">13 Sep: Ultra 5x</text>
    `;
  }

  // Assemble full SVG
  svg.innerHTML = `
    <defs>
      <linearGradient id="trends-area-grad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${metricColor}" stop-opacity="0.18" />
        <stop offset="100%" stop-color="${metricColor}" stop-opacity="0.0" />
      </linearGradient>
    </defs>
    ${overageHtml}
    ${gridHtml}
    ${refLineHtml}
    ${cutoverHtml}
    <path class="trendline-area" d="${areaPath}" fill="url(#trends-area-grad)" />
    <path class="trendline-stroke ${metric}" d="${linePath}" stroke-width="1.75" />
    ${xLabelsHtml}
    ${pointsHtml}
    <line id="trendline-cursor-line" x1="0" y1="${padding.top}" x2="0" y2="${padding.top + plotH}" class="trendline-cursor-line" style="display: none;" />
  `;

  // Attach mouse interaction
  const cursorLine = document.getElementById("trendline-cursor-line");

  const updateScrubber = (clientX, clientY) => {
    const rect = svg.getBoundingClientRect();
    const scaleX = width / rect.width;
    const mouseSvgX = (clientX - rect.left) * scaleX;

    let closest = coords[0];
    let minDiff = Infinity;
    coords.forEach(pt => {
      const diff = Math.abs(pt.x - mouseSvgX);
      if (diff < minDiff) {
        minDiff = diff;
        closest = pt;
      }
    });

    if (cursorLine) {
      cursorLine.setAttribute("x1", closest.x.toFixed(1));
      cursorLine.setAttribute("x2", closest.x.toFixed(1));
      cursorLine.style.display = "block";
    }

    if (tooltip) {
      const c = closest.cycle;
      const isCur = c.is_current_cycle;
      const hasOvg = c.actual_overage_credits > 0;
      const ovgText = hasOvg
        ? `<div style="margin-top: 4px; padding: 3px 6px; background: rgba(245,158,11,0.15); border: 1px solid rgba(245,158,11,0.3); border-radius: 4px; color: var(--status-warning); font-weight: 700;">${formatNumber(c.actual_overage_credits)} credits burned (${formatCurrency(c.actual_overage_usd, c.actual_overage_gbp, 2)})</div>`
        : "";
      const statusText = isCur
        ? `<div style="margin-top: 6px; padding: 4px 8px; background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.3); border-radius: 4px; color: var(--accent-green); font-weight: 600; font-size: 0.72rem;"><span class="active-cycle-dot"></span> Active Cycle &bull; Resets Sun 17:58 UTC</div>`
        : "";

      tooltip.innerHTML = `
        <div style="font-weight: 700; font-size: 0.8125rem; margin-bottom: 4px; color: var(--text-main); border-bottom: 1px solid var(--card-border); padding-bottom: 3px;">
          ${c.label}
        </div>
        <div style="display: flex; justify-content: space-between; gap: 8px;">
          <span style="color: var(--text-muted);">${metricName}:</span>
          <strong style="color: ${metricColor}; font-family: monospace;">${formatVal(closest.val)}</strong>
        </div>
        <div style="display: flex; justify-content: space-between; gap: 8px; margin-top: 2px;">
          <span style="color: var(--text-muted);">Turns:</span>
          <span>${formatNumber(c.total_turns)} turns</span>
        </div>
        <div style="display: flex; justify-content: space-between; gap: 8px; margin-top: 2px;">
          <span style="color: var(--text-muted);">Cache Hit:</span>
          <span class="highlight-green">${(c.cache_hit_ratio_pct || 0).toFixed(1)}%</span>
        </div>
        <div style="display: flex; justify-content: space-between; gap: 8px; margin-top: 2px;">
          <span style="color: var(--text-muted);">API Value:</span>
          <span>${formatCurrency(c.estimated_cost_usd, c.estimated_cost_gbp, 2)}</span>
        </div>
        <div style="display: flex; justify-content: space-between; gap: 8px; margin-top: 2px;">
          <span style="color: var(--text-muted);">Peak BVI:</span>
          <span class="code-pill">${(c.peak_bvi || 0).toFixed(2)}x</span>
        </div>
        ${ovgText}
        ${statusText}
      `;
      tooltip.style.display = "block";

      // Position tooltip inside container
      const contRect = container.getBoundingClientRect();
      let leftPx = (clientX - contRect.left) + 12;
      let topPx = (clientY - contRect.top) - 20;
      if (leftPx + 240 > contRect.width) {
        leftPx = (clientX - contRect.left) - 250;
      }
      tooltip.style.left = `${Math.max(10, leftPx)}px`;
      tooltip.style.top = `${Math.max(10, topPx)}px`;
    }
  };

  svg.onmousemove = (e) => updateScrubber(e.clientX, e.clientY);
  svg.onmouseleave = () => {
    if (cursorLine) cursorLine.style.display = "none";
    if (tooltip) tooltip.style.display = "none";
  };
}

function renderWeeklyTrendsTable(cycles) {
  const tbody = document.getElementById("weekly-trends-tbody");
  if (!tbody) return;

  if (!cycles || cycles.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No historical weekly cycles recorded.</td></tr>';
    return;
  }

  // Display newest cycles first
  const reversed = cycles.slice().reverse();
  tbody.innerHTML = reversed.map(c => {
    const isCur = c.is_current_cycle;
    const hasOvg = c.actual_overage_credits > 0;
    const curBadge = isCur ? '<span class="active-cycle-badge" style="font-size: 0.6875rem; margin-left: 6px;"><span class="active-cycle-dot"></span> Active</span>' : "";
    const ovgBadge = hasOvg
      ? `<span class="badge amber" style="font-size: 0.72rem; padding: 2px 6px;">-${formatNumber(c.actual_overage_credits)} credits (${formatCurrency(c.actual_overage_usd, c.actual_overage_gbp, 2)})</span>`
      : '<span style="color: var(--text-muted);">—</span>';

    const bviColor = c.peak_bvi > 1.0 ? "var(--accent-amber)" : "var(--accent-green)";
    const statusBadge = isCur
      ? '<span class="active-cycle-badge" style="font-size: 0.72rem;"><span class="active-cycle-dot"></span> Active (In Progress)</span>'
      : (hasOvg ? '<span class="badge amber" style="font-size: 0.72rem;">! Exceeded Quota</span>' : '<span class="badge green" style="font-size: 0.72rem;">✓ In Quota</span>');

    return `
      <tr>
        <td style="font-weight: 600; white-space: nowrap;">
          ${c.label} ${curBadge}
        </td>
        <td>${formatNumber(c.total_turns)}</td>
        <td>
          <strong style="color: var(--camel-400);">${formatCompactNumber(c.total_processed_tokens)}</strong>
          <span style="font-size: 0.72rem; color: var(--text-muted); display: block;">
            ${formatCompactNumber(c.cached_tokens)} cached / ${formatCompactNumber(c.prompt_tokens_uncached)} uncached
          </span>
        </td>
        <td>
          <span class="highlight-green">${(c.cache_hit_ratio_pct || 0).toFixed(1)}%</span>
        </td>
        <td style="font-family: monospace;">
          ${formatCurrency(c.estimated_cost_usd, c.estimated_cost_gbp, 2)}
        </td>
        <td>${ovgBadge}</td>
        <td>
          <span class="code-pill" style="color: ${bviColor}; font-weight: 700;">
            ${(c.peak_bvi || 0).toFixed(2)}x
          </span>
        </td>
        <td>${statusBadge}</td>
      </tr>
    `;
  }).join("");
}

function renderQuotaRegimeHistory(data) {
  const card = document.getElementById("credit-reconciliation-card");
  if (!card) return;

  const regime = (data && data.quota_regime) || (globalDashboardData && globalDashboardData.quota_regime);
  if (!regime || !Array.isArray(regime.events) || regime.events.length === 0) return;

  let container = document.getElementById("quota-regime-audit-section");
  if (!container) {
    container = document.createElement("div");
    container.id = "quota-regime-audit-section";
    container.style.marginTop = "20px";
    container.style.paddingTop = "16px";
    container.style.borderTop = "1px solid var(--card-border)";
    card.appendChild(container);
  }

  const status = regime.status || "NOMINAL";
  const pendingCount = regime.pending_review_count || 0;
  const statusBadge = pendingCount > 0
    ? `<span class="badge amber" style="font-size: 0.72rem;">! ${pendingCount} Pending Review</span>`
    : `<span class="badge green" style="font-size: 0.72rem;">✓ ${escapeHtml(status)} (${(regime.drift_ratio || 1.0).toFixed(2)}x vs Calibrated)</span>`;

  const rowsHtml = regime.events.map(ev => {
    const rev = ev.review_status || "PENDING_REVIEW";
    const revBadge = rev === "CONFIRMED"
      ? `<span class="badge green" style="font-size: 0.6875rem; padding: 2px 6px;">✓ Confirmed</span>`
      : (rev === "DISMISSED"
        ? `<span class="code-pill" style="font-size: 0.6875rem;">Dismissed</span>`
        : `<span class="badge amber" style="font-size: 0.6875rem; padding: 2px 6px;">! Pending Review</span>`);

    const d5h = typeof ev.delta_5h_pct === "number" ? `${ev.delta_5h_pct >= 0 ? "+" : ""}${ev.delta_5h_pct.toFixed(2)}%` : "—";
    const dwk = typeof ev.delta_weekly_pct === "number" ? `${ev.delta_weekly_pct >= 0 ? "+" : ""}${ev.delta_weekly_pct.toFixed(2)}%` : "—";
    const detDate = (ev.detected_at_utc || "").replace("T", " ").replace("Z", " UTC");

    return `
      <tr>
        <td style="white-space: nowrap; font-family: monospace; font-size: 0.75rem;">${escapeHtml(detDate)}</td>
        <td><span class="code-pill" style="font-size: 0.72rem;">${escapeHtml(ev.event_type || "")}</span></td>
        <td style="font-family: monospace; font-size: 0.75rem;">${escapeHtml(ev.snapshot_range || "—")} (${formatNumber(ev.turns_analyzed || 0)} turns)</td>
        <td style="font-family: monospace; font-size: 0.75rem;">5h: ${d5h} / Wk: ${dwk}</td>
        <td>${revBadge}</td>
        <td style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(ev.summary || "")}</td>
      </tr>
    `;
  }).join("");

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; flex-wrap: wrap; gap: 8px;">
      <div>
        <h3 style="font-size: 0.9375rem; font-weight: 700; color: var(--text-main); margin: 0;">Quota Regime &amp; Burn-Rate Calibration Audit Trail</h3>
        <p style="font-size: 0.75rem; color: var(--text-muted); margin: 2px 0 0 0;">
          Historical server-side quota resets, burn-rate shifts, and empirical model calibration status (<code>scripts/quota_regression.py --review</code>)
        </p>
      </div>
      <div>${statusBadge}</div>
    </div>
    <div class="table-scroll-container">
      <div class="table-scroll-wrapper" role="region" tabindex="0" aria-label="Quota Regime Audit Trail (scrollable table)">
        <table id="quota-regime-table">
          <caption class="sr-only">Quota Regime and Burn-Rate Calibration Audit Trail</caption>
          <thead>
            <tr>
              <th>Detected (UTC)</th>
              <th>Regime Event</th>
              <th>Evidence Window</th>
              <th>Quota Delta</th>
              <th>Verification</th>
              <th>Empirical Summary</th>
            </tr>
          </thead>
          <tbody id="quota-regime-tbody">${rowsHtml}</tbody>
        </table>
      </div>
    </div>
  `;
}

function renderBillingView(data) {
  renderWeeklyTrends(data);
  renderHourlyCreditActivity();
  renderQuotaRegimeHistory(data);
}
window.renderBillingView = renderBillingView;
