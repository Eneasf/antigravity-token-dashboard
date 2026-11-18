// ==========================================
// Dashboard: Model Taxonomy, Sorting & Historical Rate Engine
// Hydrated dynamically from getCatalog().models (ADR-066 / Row 13).
// ==========================================

function getCatalogModels() {
  const cat = typeof getCatalog === "function" ? getCatalog() : {};
  return (cat && cat.models) || {};
}

function resolveModelDisplay(mid, pricingModels = null) {
  const catModels = getCatalogModels();
  const cm = catModels[mid] || {};
  if (!pricingModels && typeof globalDashboardData !== "undefined" && globalDashboardData) {
    const temporal = globalDashboardData.temporal || {};
    pricingModels = temporal.models || (globalDashboardData.pricing && globalDashboardData.pricing.models) || {};
  }
  const pm = (pricingModels && pricingModels[mid]) || {};
  let rawName = cm.taxonomy_name || cm.name || pm.name || `Model ${mid}`;
  let reasoning = cm.reasoning_label || "";

  if (!reasoning) {
    if (rawName.includes("(XHigh)")) reasoning = "XHigh Reasoning";
    else if (rawName.includes("(High)")) reasoning = "High Reasoning";
    else if (rawName.includes("(Medium)")) reasoning = "Medium Reasoning";
    else if (rawName.includes("(Low)")) reasoning = "Low Reasoning";
    else if (rawName.includes("(Thinking)")) reasoning = "Thinking Enabled";
    else if (rawName.includes("(Subagent)")) reasoning = "Autonomous Subagent";
  }

  let cleanName = (cm.name || rawName).replace(/\s*\((XHigh|High|Medium|Low|Thinking|Subagent|Legacy)\)\s*/gi, "").trim();
  const baseRates = pm.rates_per_million || cm.rates_per_million || {
    prompt_uncached: 0.75,
    prompt_cached: 0.075,
    candidate_output: 3.75
  };

  return {
    name: cleanName || `Model ${mid}`,
    reasoning: reasoning,
    rates: baseRates,
    status: cm.status || "active",
    sunset_date: cm.sunset_date || null
  };
}

function getModelSortRank(mid) {
  const catModels = getCatalogModels();
  if (catModels[mid] && catModels[mid].sort_rank !== undefined) {
    return catModels[mid].sort_rank;
  }
  const info = resolveModelDisplay(mid);
  const n = (info.name + " " + info.reasoning).toLowerCase();
  if (n.includes("orchestrator")) return 7;
  if (n.includes("hydrogen")) return 10;
  if (n.includes("carbon")) return 4;
  if (n.includes("argon")) return 8;
  if (n.includes("3.8") && n.includes("flash")) return 15;
  if (n.includes("3.7") && n.includes("flash")) return 25;
  if (n.includes("3.6") && n.includes("flash")) return 35;
  if (n.includes("pro")) return 45;
  if (n.includes("flash") || n.includes("agent")) return 60;
  if (n.includes("sonnet")) return 80;
  if (n.includes("opus")) return 81;
  if (n.includes("claude")) return 85;
  if (n.includes("gpt")) return 90;
  return 100;
}

function renderRateHistoryTable(temporal = null, pricingModels = null) {
  const rateTbody = document.getElementById("rate-history-tbody");
  if (!rateTbody) return;

  if (!temporal && typeof globalDashboardData !== "undefined" && globalDashboardData) {
    temporal = globalDashboardData.temporal || {};
  }
  temporal = temporal || {};

  if (!pricingModels && typeof globalDashboardData !== "undefined" && globalDashboardData) {
    pricingModels = temporal.models || (globalDashboardData.pricing && globalDashboardData.pricing.models) || {};
  }
  pricingModels = pricingModels || {};

  const rateHistory = temporal.rate_history || {};
  const availability = temporal.availability || {};
  const catModels = getCatalogModels();

  const rows = [];
  const allModelIds = Array.from(new Set([
    ...Object.keys(rateHistory),
    ...Object.keys(availability),
    ...Object.keys(catModels),
    ...Object.keys(pricingModels)
  ]));
  allModelIds.sort((a, b) => {
    const rankA = getModelSortRank(a);
    const rankB = getModelSortRank(b);
    if (rankA !== rankB) return rankA - rankB;
    return a.localeCompare(b);
  });

  allModelIds.forEach(mid => {
    if (mid === "default") return;
    const avail = availability[mid] || (catModels[mid] ? { status: catModels[mid].status } : { status: "ga" });
    const statusBadge = avail.status === "ga" || avail.status === "active" ? '<span class="badge green">GA</span>'
      : (avail.status === "preview" ? '<span class="badge camel">Preview</span>'
      : (avail.status === "sunset" || avail.status === "deprecated" ? '<span class="badge red">Sunset</span>'
      : `<span class="badge">${escapeHtml(avail.status || "GA")}</span>`));

    const info = resolveModelDisplay(mid, pricingModels);
    const reasoningBadge = info.reasoning ? `<span class="badge purple" style="font-size: 0.6875rem; margin-top: 3px; display: inline-flex; align-items: center; gap: 3px;">${escapeHtml(info.reasoning)}</span>` : '';

    const revisions = rateHistory[mid];
    if (revisions && revisions.length > 0) {
      revisions.forEach((rev) => {
        const r = rev.rates_per_million || info.rates;
        const nowMs = Date.now();
        const isHistorical = !!(rev.valid_to && new Date(rev.valid_to).getTime() < nowMs);
        const isScheduled = !!(rev.valid_from && new Date(rev.valid_from).getTime() > nowMs);
        const intervalText = `${rev.valid_from ? formatUkDate(rev.valid_from) : 'Start'} → ${rev.valid_to ? formatUkDate(rev.valid_to) : 'Present'}`;
        const eraBadge = isHistorical
          ? '<span class="badge" style="background: rgba(148, 163, 184, 0.15); color: var(--text-muted); font-size: 0.6875rem; margin-left: 6px; border: 1px solid rgba(148, 163, 184, 0.3);">Former Rate</span>'
          : (isScheduled
            ? '<span class="badge camel" style="font-size: 0.6875rem; margin-left: 6px;">Scheduled Rate</span>'
            : '<span class="badge green" style="font-size: 0.6875rem; margin-left: 6px;">Active Current</span>');
        const revisionSub = revisions.length > 1
          ? `<div style="font-size: 0.6875rem; color: var(--text-muted); margin-top: 3px; font-weight: 500;">${isHistorical ? 'Historical Revision' : (isScheduled ? 'Scheduled Standard Revision' : 'Current Active Revision')}</div>`
          : '';
        const rowStyle = (isHistorical || isScheduled)
          ? 'border-bottom: 1px solid var(--card-border); opacity: 0.78;'
          : 'border-bottom: 1px solid var(--card-border);';

        rows.push(`
          <tr style="${rowStyle}">
            <td style="padding: 6px 8px;"><span class="code-pill">${escapeHtml(mid)}</span></td>
            <td style="padding: 6px 8px;">
              <div style="font-weight: 600; color: var(--text-main);">${escapeHtml(info.name)}</div>
              ${reasoningBadge}
              ${revisionSub}
            </td>
            <td style="padding: 6px 8px;">${statusBadge}</td>
            <td style="padding: 6px 8px;">
              <span>${escapeHtml(intervalText)}</span>
              ${eraBadge}
            </td>
            <td style="padding: 6px 8px; text-align: right; font-variant-numeric: tabular-nums;">$${(r.prompt_uncached || 0).toFixed(2)}</td>
            <td style="padding: 6px 8px; text-align: right; font-variant-numeric: tabular-nums;">$${(r.prompt_cached || 0).toFixed(3)}</td>
            <td style="padding: 6px 8px; text-align: right; font-variant-numeric: tabular-nums;">$${(r.candidate_output || 0).toFixed(2)}</td>
          </tr>
        `);
      });
    } else {
      const r = info.rates;
      rows.push(`
        <tr style="border-bottom: 1px solid var(--card-border);">
          <td style="padding: 6px 8px;"><span class="code-pill">${escapeHtml(mid)}</span></td>
          <td style="padding: 6px 8px;">
            <div style="font-weight: 600; color: var(--text-main);">${escapeHtml(info.name)}</div>
            ${reasoningBadge}
          </td>
          <td style="padding: 6px 8px;">${statusBadge}</td>
          <td style="padding: 6px 8px;">
            <span>Standard (Current)</span>
            <span class="badge green" style="font-size: 0.6875rem; margin-left: 6px;">Active Current</span>
          </td>
          <td style="padding: 6px 8px; text-align: right; font-variant-numeric: tabular-nums;">$${(r.prompt_uncached || 0).toFixed(2)}</td>
          <td style="padding: 6px 8px; text-align: right; font-variant-numeric: tabular-nums;">$${(r.prompt_cached || 0).toFixed(3)}</td>
          <td style="padding: 6px 8px; text-align: right; font-variant-numeric: tabular-nums;">$${(r.candidate_output || 0).toFixed(2)}</td>
        </tr>
      `);
    }
  });
  rateTbody.innerHTML = rows.join("");
}

if (typeof window !== "undefined") {
  window.resolveModelDisplay = resolveModelDisplay;
  window.getModelSortRank = getModelSortRank;
  window.renderRateHistoryTable = renderRateHistoryTable;
  window.Antigravity = window.Antigravity || {};
  window.Antigravity.resolveModelDisplay = resolveModelDisplay;
  window.Antigravity.getModelSortRank = getModelSortRank;
  window.Antigravity.renderRateHistoryTable = renderRateHistoryTable;
}
