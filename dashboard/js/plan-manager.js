// ==========================================
// Dashboard: Plan Profile Manager Modal & Pricing Overrides
// ==========================================
let isPlanManagerModalInitialized = false;

function initPlanManagerModal() {
  if (isPlanManagerModalInitialized) return;
  isPlanManagerModalInitialized = true;

  const btnOpen = document.getElementById("btn-open-plan-manager");
  const btnClose = document.getElementById("btn-close-plan-modal");
  if (btnOpen) {
    btnOpen.addEventListener("click", () => {
      openPlanModal();
    });
  }
  if (btnClose) {
    btnClose.addEventListener("click", () => {
      closePlanModal();
    });
  }

  // Tab switching within Plan card
  const planCard = document.getElementById("plan-manager-card");
  if (planCard) {
    const tabBtns = planCard.querySelectorAll(".modal-tab-btn");
    tabBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        tabBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const targetTab = btn.getAttribute("data-modaltab");
        planCard.querySelectorAll(".modal-tab-content").forEach(view => {
          view.style.display = "none";
        });
        const targetView = document.getElementById(`modal-view-${targetTab}`);
        if (targetView) targetView.style.display = "block";
      });
    });
  }

  // Wire Save Plan button
  const btnSavePlan = document.getElementById("btn-save-plan");
  if (btnSavePlan) {
    btnSavePlan.addEventListener("click", applyPlanChange);
  }

  // Dynamic custom plan inputs toggle
  const tierSelect = document.getElementById("plan-tier-select");
  const customFields = document.getElementById("plan-custom-fields");
  if (tierSelect && customFields) {
    tierSelect.addEventListener("change", () => {
      customFields.style.display = tierSelect.value === "custom" ? "block" : "none";
    });
  }
  const customFeeUsdInput = document.getElementById("custom-fee-usd");
  if (customFeeUsdInput && tierSelect) {
    customFeeUsdInput.addEventListener("input", () => {
      if (tierSelect.value !== "custom") {
        tierSelect.value = "custom";
      }
    });
  }

  // Wire Add Promotion button
  const btnAddPromo = document.getElementById("btn-add-promo");
  if (btnAddPromo) {
    btnAddPromo.addEventListener("click", registerPromotion);
  }

  // Wire JSON buttons
  const btnCopyJson = document.getElementById("btn-copy-json");
  if (btnCopyJson) {
    btnCopyJson.addEventListener("click", () => {
      const editor = document.getElementById("modal-json-editor");
      if (editor) {
        navigator.clipboard.writeText(editor.value).then(() => {
          const orig = btnCopyJson.textContent;
          btnCopyJson.textContent = "Copied!";
          setTimeout(() => { btnCopyJson.textContent = orig; }, 2000);
        });
      }
    });
  }

  const btnDownloadJson = document.getElementById("btn-download-json");
  if (btnDownloadJson) {
    btnDownloadJson.addEventListener("click", () => {
      const editor = document.getElementById("modal-json-editor");
      if (editor) {
        const blob = new Blob([editor.value], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "pricing.json";
        a.click();
        URL.revokeObjectURL(url);
      }
    });
  }
}

function openPlanModal() {
  switchTab("tab-plan");
  const target = document.getElementById("plan-manager-card");
  if (target) {
    target.scrollIntoView({ behavior: "smooth" });
  }
  renderPlanManagerContent();
}

function closePlanModal() {
  // Inline embedded on Plan tab
}

function renderPlanManagerContent() {
  const summary = (globalDashboardData && globalDashboardData.summary) || {};
  const temporal = (globalDashboardData && globalDashboardData.temporal) || {};
  const activePlan = temporal.active_plan || {
    tier: summary.tier || "pro",
    name: summary.subscription_name || "Google One AI Premium (Antigravity Pro)",
    monthly_price_gbp: summary.monthly_subscription_price_gbp || 0.0,
    monthly_price_usd: summary.monthly_subscription_price_usd || 0.0,
    renewal_day: summary.monthly_billing_day || 24,
    quota_limits: {
      gemini_5h_capacity_usd: 20.00,
      gemini_weekly_capacity_usd: 129.00,
      claude_5h_capacity_usd: 10.00,
      claude_weekly_capacity_usd: 35.00,
    }
  };

  // 1. Active Plan card
  const nameEl = document.getElementById("modal-active-plan-name");
  if (nameEl) nameEl.textContent = activePlan.name || "Google One AI Premium (Antigravity Pro)";
  const pricesEl = document.getElementById("modal-active-plan-prices");
  if (pricesEl) {
    pricesEl.textContent = `£${(activePlan.monthly_price_gbp || 0.0).toFixed(2)} / $${(activePlan.monthly_price_usd || 0.0).toFixed(2)} per month • Renews day ${activePlan.renewal_day || 24}`;
  }
  const ql = activePlan.quota_limits || {};
  const gemEl = document.getElementById("modal-active-gemini-cap");
  if (gemEl) {
    gemEl.textContent = `$${(ql.gemini_5h_capacity_usd || 20.00).toFixed(2)} / $${(ql.gemini_weekly_capacity_usd || 129.00).toFixed(2)}`;
  }
  const clEl = document.getElementById("modal-active-claude-cap");
  if (clEl) {
    clEl.textContent = `$${(ql.claude_5h_capacity_usd || 10.00).toFixed(2)} / $${(ql.claude_weekly_capacity_usd || 35.00).toFixed(2)}`;
  }

  // Preselect plan-tier-select to current summary.tier
  const tierPresetSelect = document.getElementById("plan-tier-select");
  if (tierPresetSelect && summary.tier) {
    if (Array.from(tierPresetSelect.options).some(opt => opt.value === summary.tier)) {
      tierPresetSelect.value = summary.tier;
    }
    const customFields = document.getElementById("plan-custom-fields");
    if (customFields) {
      customFields.style.display = tierPresetSelect.value === "custom" ? "block" : "none";
    }
  }

  // Default effective date input to today
  const dateInput = document.getElementById("plan-effective-date");
  if (dateInput && !dateInput.value) {
    dateInput.value = new Date().toISOString().slice(0, 10);
  }

  // 2. Subscription History Table
  const historyList = temporal.subscription_history || summary.subscription_history || [
    {
      tier: "pro",
      name: "Google One AI Premium (Antigravity Pro)",
      valid_from: "2024-01-01T00:00:00Z",
      valid_to: null,
      monthly_price_gbp: 18.99,
      monthly_price_usd: 19.99
    }
  ];
  const histTbody = document.getElementById("plan-history-tbody");
  if (histTbody) {
    histTbody.innerHTML = historyList.map(h => {
      const isActive = !h.valid_to || new Date(h.valid_to) >= new Date();
      const badgeHtml = isActive ? '<span class="badge green">Active</span>' : '<span class="badge">Historical</span>';
      return `
        <tr style="border-bottom: 1px solid var(--card-border);">
          <td style="padding: 8px;"><span class="code-pill">${escapeHtml(h.tier)}</span></td>
          <td style="padding: 8px; font-weight: 600;">${escapeHtml(h.name)}</td>
          <td style="padding: 8px; font-family: monospace;">${h.valid_from ? escapeHtml(formatUkDate(h.valid_from)) : 'Inception'}</td>
          <td style="padding: 8px; font-family: monospace;">${h.valid_to ? escapeHtml(formatUkDate(h.valid_to)) : 'Current (Open)'}</td>
          <td style="padding: 8px; text-align: right; font-variant-numeric: tabular-nums;">£${(h.monthly_price_gbp || 0).toFixed(2)}</td>
          <td style="padding: 8px;">${badgeHtml}</td>
        </tr>
      `;
    }).join("");
  }

  // 3. Promotions List
  const promosList = document.getElementById("promotions-list");
  const promos = temporal.promotions_catalog || summary.promotions || [];
  if (promosList) {
    if (promos.length === 0) {
      promosList.innerHTML = '<div style="font-size: 0.8125rem; color: var(--text-muted); padding: 12px; border: 1px dashed var(--card-border); border-radius: 8px; text-align: center;">No capacity promotions active. Register a promotional multiplier below.</div>';
    } else {
      promosList.innerHTML = promos.map(p => {
        const now = new Date();
        const fromDt = p.valid_from ? new Date(p.valid_from) : null;
        const toDt = p.valid_to ? new Date(p.valid_to) : null;
        let status = '<span class="badge green">Active</span>';
        if (fromDt && now < fromDt) status = '<span class="badge camel">Upcoming</span>';
        else if (toDt && now > toDt) status = '<span class="badge">Expired</span>';

        return `
          <div style="background: var(--quota-bg); border: 1px solid var(--quota-border); border-radius: 8px; padding: 12px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div>
              <div style="font-weight: 700; font-size: 0.875rem; color: var(--text-main); display: flex; align-items: center; gap: 8px;">
                <span>${escapeHtml(p.name)}</span>
                <span class="badge purple">${p.multiplier}x Multiplier</span>
                ${status}
              </div>
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">
                Target: <strong style="color: var(--text-main);">${escapeHtml(p.target_provider || 'all')}</strong> •
                Window: ${p.valid_from ? formatUkDate(p.valid_from) : 'Open'} to ${p.valid_to ? formatUkDate(p.valid_to) : 'Open'}
              </div>
              ${p.description ? `<div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 2px;">${escapeHtml(p.description)}</div>` : ''}
            </div>
          </div>
        `;
      }).join("");
    }
  }

  // Default promo date inputs
  const pFrom = document.getElementById("promo-from-input");
  const pTo = document.getElementById("promo-to-input");
  if (pFrom && !pFrom.value) pFrom.value = new Date().toISOString().slice(0, 10);
  if (pTo && !pTo.value) {
    const nextWk = new Date(Date.now() + 14 * 86400000);
    pTo.value = nextWk.toISOString().slice(0, 10);
  }

  // 4. Rate History Table (Delegated to js/plan-rates.js)
  const pricingModels = temporal.models || (globalDashboardData && globalDashboardData.pricing && globalDashboardData.pricing.models) || {};
  if (typeof renderRateHistoryTable === "function") {
    renderRateHistoryTable(temporal, pricingModels);
  }

  // 5. JSON Config Viewer
  updateJsonConfigEditor();
}

function updateJsonConfigEditor() {
  const editor = document.getElementById("modal-json-editor");
  if (!editor) return;
  const summary = (globalDashboardData && globalDashboardData.summary) || {};
  const temporal = (globalDashboardData && globalDashboardData.temporal) || {};

  const configExport = {
    subscription: temporal.active_plan || {
      tier: summary.tier || "pro",
      name: summary.subscription_name || "Google One AI Premium (Antigravity Pro)",
      monthly_price_gbp: summary.monthly_subscription_price_gbp || 0.0,
      monthly_price_usd: summary.monthly_subscription_price_usd || 0.0,
      renewal_day: summary.monthly_billing_day || 24,
      use_ai_credits: false,
      cents_per_credit: 1.0,
      windows: { burst_hours: 5, weekly_hours: 168 },
      quota_limits: {
        burst_5h_tokens: 168000000,
        gemini_5h_capacity_usd: 20.00,
        gemini_weekly_capacity_usd: 129.00,
        claude_5h_capacity_usd: 10.00,
        claude_weekly_capacity_usd: 35.00
      }
    },
    subscription_history: temporal.subscription_history || summary.subscription_history || [],
    promotions: temporal.promotions_catalog || summary.promotions || [],
    rate_history: temporal.rate_history || {},
    availability: temporal.availability || {}
  };

  editor.value = JSON.stringify(configExport, null, 2);
}

function applyPlanToGlobalData(chosen, shouldSave = true) {
  if (!globalDashboardData) globalDashboardData = {};
  if (!globalDashboardData.summary) globalDashboardData.summary = {};
  if (!globalDashboardData.quotas) globalDashboardData.quotas = {};
  if (!globalDashboardData.temporal) globalDashboardData.temporal = {};

  globalDashboardData.summary.tier = chosen.tier;
  globalDashboardData.summary.subscription_name = chosen.name;
  globalDashboardData.summary.monthly_subscription_price_gbp = chosen.monthly_price_gbp;
  globalDashboardData.summary.monthly_subscription_price_usd = chosen.monthly_price_usd;

  const ql = chosen.quota_limits || {};
  if (!globalDashboardData.quotas.subscription) globalDashboardData.quotas.subscription = {};
  globalDashboardData.quotas.subscription.quota_limits = ql;

  // Re-scale provider quotas
  if (globalDashboardData.quotas.providers) {
    const p = globalDashboardData.quotas.providers;
    if (p.gemini) {
      if (p.gemini.weekly) {
        const usedUsd = p.gemini.weekly.processed_cost_usd || 0;
        const cap = ql.gemini_weekly_capacity_usd || 129.0;
        p.gemini.weekly.capacity_usd = cap;
        p.gemini.weekly.remaining_pct = Math.max(0, Math.round(((cap - usedUsd) / cap) * 100));
      }
      if (p.gemini.five_hour) {
        const usedUsd = p.gemini.five_hour.processed_cost_usd || 0;
        const cap = ql.gemini_5h_capacity_usd || 20.0;
        p.gemini.five_hour.capacity_usd = cap;
        p.gemini.five_hour.remaining_pct = Math.max(0, Math.round(((cap - usedUsd) / cap) * 100));
      }
    }
    if (p.claude_gpt) {
      if (p.claude_gpt.weekly) {
        const usedUsd = p.claude_gpt.weekly.processed_cost_usd || 0;
        const cap = ql.claude_weekly_capacity_usd !== undefined ? ql.claude_weekly_capacity_usd : 35.0;
        p.claude_gpt.weekly.capacity_usd = cap;
        p.claude_gpt.weekly.remaining_pct = cap > 0 ? Math.max(0, Math.round(((cap - usedUsd) / cap) * 100)) : 0;
      }
      if (p.claude_gpt.five_hour) {
        const usedUsd = p.claude_gpt.five_hour.processed_cost_usd || 0;
        const cap = ql.claude_5h_capacity_usd !== undefined ? ql.claude_5h_capacity_usd : 10.0;
        p.claude_gpt.five_hour.capacity_usd = cap;
        p.claude_gpt.five_hour.remaining_pct = cap > 0 ? Math.max(0, Math.round(((cap - usedUsd) / cap) * 100)) : 0;
      }
    }
  }

  globalDashboardData.temporal.active_plan = {
    ...chosen,
    valid_from: chosen.valid_from || new Date().toISOString(),
    valid_to: null
  };

  if (!globalDashboardData.temporal.subscription_history) {
    globalDashboardData.temporal.subscription_history = [];
  }
  const exists = globalDashboardData.temporal.subscription_history.some(h => h.tier === chosen.tier && h.valid_from === chosen.valid_from);
  if (!exists) {
    globalDashboardData.temporal.subscription_history.push({
      ...chosen,
      valid_from: chosen.valid_from || new Date().toISOString(),
      valid_to: null
    });
  }

  if (shouldSave) {
    try {
      localStorage.setItem("antigravity_selected_plan", JSON.stringify(chosen));
    } catch (e) {
      console.warn("Could not persist plan to localStorage:", e);
    }
  }

  // Update header tier badge
  const headerBadge = document.getElementById("header-tier-badge");
  if (headerBadge) {
    if (chosen.tier === "free") {
      headerBadge.textContent = "Free Tier Active";
    } else if (chosen.tier === "plus_2tb") {
      headerBadge.textContent = "Google AI Plus Active";
    } else if (chosen.tier === "ultra_5x" || chosen.tier === "enterprise_5x") {
      headerBadge.textContent = "Google AI Ultra Active";
    } else if (chosen.tier === "ultra_10x") {
      headerBadge.textContent = "Ultra Max Active";
    } else if (chosen.tier === "custom") {
      headerBadge.textContent = "Custom Tier Active";
    } else {
      headerBadge.textContent = "Google AI Pro Active";
    }
  }
}

function applyPlanChange() {
  const select = document.getElementById("plan-tier-select");
  const dateInput = document.getElementById("plan-effective-date");
  if (!select) return;

  const tierKey = select.value;
  const effectiveDate = (dateInput && dateInput.value) ? dateInput.value + "T00:00:00Z" : new Date().toISOString();

  const cat = typeof getCatalog === "function" ? getCatalog() : {};
  const catTiers = (cat && cat.plan_tiers) || {};
  const cUsd = parseFloat(document.getElementById("custom-fee-usd")?.value || "0");
  let chosen = catTiers[tierKey] || catTiers.pro || {
    tier: "pro",
    name: "Google AI Pro (2 TB)",
    monthly_price_gbp: 18.99,
    monthly_price_usd: 19.99,
    renewal_day: 24,
    quota_limits: {
      burst_5h_tokens: 168000000,
      gemini_5h_capacity_usd: 20.00,
      gemini_weekly_capacity_usd: 129.00,
      claude_5h_capacity_usd: 10.00,
      claude_weekly_capacity_usd: 35.00
    }
  };
  if (tierKey === "custom" || cUsd > 0) {
    if (select.value !== "custom") {
      select.value = "custom";
    }
    const cGbp = parseFloat(document.getElementById("custom-fee-gbp")?.value || "0");
    const cG5h = parseFloat(document.getElementById("custom-gemini-5h")?.value || "20");
    const cGWk = parseFloat(document.getElementById("custom-gemini-weekly")?.value || "129");
    const cC5h = parseFloat(document.getElementById("custom-claude-5h")?.value || "10");
    const cCWk = parseFloat(document.getElementById("custom-claude-weekly")?.value || "35");
    chosen = {
      tier: "custom",
      name: "Custom Capacity Plan",
      monthly_price_gbp: cGbp,
      monthly_price_usd: cUsd,
      renewal_day: 1,
      quota_limits: {
        burst_5h_tokens: 250000000,
        gemini_5h_capacity_usd: cG5h,
        gemini_weekly_capacity_usd: cGWk,
        claude_5h_capacity_usd: cC5h,
        claude_weekly_capacity_usd: cCWk
      }
    };
  }

  chosen.valid_from = effectiveDate;
  chosen.valid_to = null;

  applyPlanToGlobalData(chosen, true);

  renderPlanManagerContent();
  updateCurrencyViews();

  // Refresh simulator if on plan view
  runSimulation();

  if (cUsd >= 500) {
    const riskBadge = document.getElementById("sim-risk-badge");
    if (riskBadge) {
      riskBadge.textContent = "Critical Risk";
      riskBadge.className = "code-pill red";
    }
    const statusBadge = document.getElementById("sim-status-badge");
    if (statusBadge) {
      statusBadge.className = "badge red";
      statusBadge.textContent = "Critical Risk";
    }
  }

  // Refresh provider quota displays
  const gWk = (globalDashboardData.quotas.providers && globalDashboardData.quotas.providers.gemini && globalDashboardData.quotas.providers.gemini.weekly) || {};
  const g5h = (globalDashboardData.quotas.providers && globalDashboardData.quotas.providers.gemini && globalDashboardData.quotas.providers.gemini.five_hour) || {};
  const gemWkElem = document.getElementById("gemini-weekly-pct");
  if (gemWkElem) gemWkElem.textContent = `${gWk.remaining_pct !== undefined ? gWk.remaining_pct : 100}% Available`;
  const gemWkProg = document.getElementById("gemini-weekly-progress");
  if (gemWkProg) gemWkProg.style.width = `${Math.min(100, Math.max(0, gWk.remaining_pct !== undefined ? gWk.remaining_pct : 100))}%`;
  const gem5hElem = document.getElementById("gemini-5h-pct");
  if (gem5hElem) gem5hElem.textContent = `${g5h.remaining_pct !== undefined ? g5h.remaining_pct : 100}% Available`;
  const gem5hProg = document.getElementById("gemini-5h-progress");
  if (gem5hProg) gem5hProg.style.width = `${Math.min(100, Math.max(0, g5h.remaining_pct !== undefined ? g5h.remaining_pct : 100))}%`;
}

function registerPromotion() {
  const nameIn = document.getElementById("promo-name-input");
  const provIn = document.getElementById("promo-provider-select");
  const multIn = document.getElementById("promo-multiplier-input");
  const fromIn = document.getElementById("promo-from-input");
  const toIn = document.getElementById("promo-to-input");

  const name = (nameIn && nameIn.value) ? nameIn.value.trim() : "Custom Promotion";
  const provider = (provIn && provIn.value) ? provIn.value : "gemini";
  const multiplier = (multIn && multIn.value) ? parseFloat(multIn.value) : 2.0;
  const validFrom = (fromIn && fromIn.value) ? fromIn.value + "T00:00:00Z" : new Date().toISOString();
  const validTo = (toIn && toIn.value) ? toIn.value + "T23:59:59Z" : null;

  const newPromo = {
    id: `promo_${Date.now().toString(36)}`,
    name: name,
    target_provider: provider,
    multiplier: multiplier,
    valid_from: validFrom,
    valid_to: validTo,
    description: `${multiplier}x overlay for ${provider}`
  };

  if (!globalDashboardData) globalDashboardData = {};
  if (!globalDashboardData.temporal) globalDashboardData.temporal = {};
  if (!globalDashboardData.temporal.promotions_catalog) {
    globalDashboardData.temporal.promotions_catalog = [];
  }
  globalDashboardData.temporal.promotions_catalog.push(newPromo);

  renderPlanManagerContent();
}
