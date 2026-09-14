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
  return fallbackDisplay || (globalDashboardData && globalDashboardData.quotas && globalDashboardData.quotas.weekly_cycle && globalDashboardData.quotas.weekly_cycle.reset_display) || "Weekly Reset";
}

function generateStandupMarkdown(data) {
  if (!data) return "";
  const s = data.summary || {};
  const quotas = data.quotas || {};
  const prov = quotas.providers || {};
  const gem = prov.gemini || {};
  const cg = prov.claude_gpt || {};
  const gem5h = gem.five_hour || {};
  const gemWk = gem.weekly || {};
  const cg5h = cg.five_hour || {};
  const cgWk = cg.weekly || {};
  const runway = gem.runway || {};

  const planName = s.subscription_tier_name || s.subscription_tier || "Google AI Ultra (20 TB - 5x AI Usage)";
  const planTier = s.subscription_tier || "ultra_5x";
  const subGbp = (s.monthly_subscription_price_gbp || 79.99).toFixed(2);
  const imputedGbp = (s.total_imputed_value_gbp || 0).toFixed(2);
  const imputedUsd = (s.total_imputed_value_usd || 0).toFixed(2);

  const totalToks = (s.total_processed_tokens || 0).toLocaleString();
  const inputToks = (s.total_input_tokens || 0).toLocaleString();
  const outputToks = (s.total_output_tokens || 0).toLocaleString();
  const cachedToks = (s.total_cached_tokens || 0).toLocaleString();
  const cachePct = (s.cache_hit_ratio_pct || 0).toFixed(1);

  const creditsBurned = (s.total_ai_credits_burned || 0).toLocaleString();
  const burnGbp = (s.total_credit_burn_gbp || 0).toFixed(2);
  const burnUsd = (s.total_credit_burn_usd || 0).toFixed(2);
  const creditsRem = (quotas.credit_bank?.remaining_credits || 1360).toLocaleString();

  const resetDisp = formatLocalizedResetTime(gemWk.weekly_reset_utc, gemWk.reset_display);
  const bvi = (runway.burn_velocity_index || 0).toFixed(2);
  const subStatus = s.subscription_status || "SAFE_IN_QUOTA";

  const gem5hUsed = (gem5h.used_pct || 0).toFixed(1);
  const gem5hRem = Math.max(0, 100 - (gem5h.used_pct || 0)).toFixed(1);
  const gemWkUsed = (gemWk.used_pct || 0).toFixed(1);
  const gemWkRem = Math.max(0, 100 - (gemWk.used_pct || 0)).toFixed(1);

  const cg5hUsed = (cg5h.used_pct || 0).toFixed(1);
  const cg5hRem = Math.max(0, 100 - (cg5h.used_pct || 0)).toFixed(1);
  const cgWkUsed = (cgWk.used_pct || 0).toFixed(1);
  const cgWkRem = Math.max(0, 100 - (cgWk.used_pct || 0)).toFixed(1);

  const byModel = s.by_model || {};
  const sortedModels = Object.entries(byModel).sort((a, b) => (b[1].total_processed_tokens || 0) - (a[1].total_processed_tokens || 0));
  const topModelsLines = sortedModels.slice(0, 3).map(([mid, mdata]) => {
    const mname = mdata.name || mid;
    const mtoks = (mdata.total_processed_tokens || 0).toLocaleString();
    const mturns = mdata.turn_count || 0;
    const mcost = (mdata.estimated_cost_gbp || 0).toFixed(2);
    return `  - **${mname}**: ${mturns} turns, ${mtoks} tokens (£${mcost})`;
  });

  const modelsBlock = topModelsLines.length > 0 ? topModelsLines.join("\n") : "  - No model activity recorded.";

  return [
    "### 📊 Antigravity Telemetry Standup Digest",
    `**Plan**: ${planName} (\`${planTier}\`) | **Weekly Cycle Reset**: ${resetDisp} | **Status**: \`${subStatus}\``,
    "",
    "#### 1. Token Throughput & Cache Efficiency",
    `- **Total Processed**: ${totalToks} tokens`,
    `- **Input vs Output**: ${inputToks} input / ${outputToks} output`,
    `- **Context Cache Hit**: ${cachedToks} cached (${cachePct}% hit ratio)`,
    "",
    "#### 2. Economic Value & AI Credit Ledger",
    `- **Imputed Avoided API Cost**: £${imputedGbp} ($${imputedUsd})`,
    `- **Monthly Plan Cost**: £${subGbp}/mo`,
    `- **AI Credit Deductions**: ${creditsBurned} credits (£${burnGbp} / $${burnUsd}) | ${creditsRem} credits remaining in bank`,
    "",
    "#### 3. Quota Runway & Headroom",
    `- **Gemini 5-Hour Burst**: ${gem5hUsed}% used (${gem5hRem}% remaining)`,
    `- **Gemini Weekly Runway**: ${gemWkUsed}% used (${gemWkRem}% remaining) | BVI: ${bvi}x`,
    `- **Claude/GPT 5-Hour Burst**: ${cg5hUsed}% used (${cg5hRem}% remaining)`,
    `- **Claude/GPT Weekly**: ${cgWkUsed}% used (${cgWkRem}% remaining)`,
    "",
    "#### 4. Top Active Models",
    modelsBlock,
  ].join("\n") + "\n";
}

let globalDashboardData = null;
let activeModelWindow = "5h";
let activeCurrency = "GBP"; // Default to British Pounds (£)
let activeTheme = "light"; // Default to Light Mode
let activeFilteredConversations = [];
let activeConvoForTurns = null;

function formatCurrency(usdVal, gbpVal, decimals = 4) {
  const summary = (globalDashboardData && globalDashboardData.summary) || {};
  const fxRate = summary.usd_to_gbp_fx_rate || 0.79;
  if (activeCurrency === "GBP") {
    const val = (gbpVal !== undefined && gbpVal !== null) ? gbpVal : ((usdVal || 0) * fxRate);
    return "£" + Number(val || 0).toFixed(decimals);
  } else {
    return "$" + Number(usdVal || 0).toFixed(decimals);
  }
}

function formatCost(val, decimals = 4) {
  return formatCurrency(val, null, decimals);
}

function updateCurrencyViews() {
  const summary = (globalDashboardData && globalDashboardData.summary) || {};

  // Toggle button active states using classList
  const btnGbp = document.getElementById("btn-curr-gbp");
  const btnUsd = document.getElementById("btn-curr-usd");
  if (btnGbp && btnUsd) {
    if (activeCurrency === "GBP") {
      btnGbp.classList.add("active");
      btnUsd.classList.remove("active");
    } else {
      btnUsd.classList.add("active");
      btnGbp.classList.remove("active");
    }
  }

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

  // Re-render data tables
  renderHourlyCreditActivity();
  renderModelMatrix(activeModelWindow);
  renderRecentSessions();
  renderConversationsTable(activeFilteredConversations);
  renderPortfolioView();
  renderRecoveryTimeline();
  if (activeConvoForTurns) {
    renderTurnsTable(activeConvoForTurns);
  }
  if (typeof runSimulation === "function") {
    runSimulation();
  }
  if (typeof renderSwarmsView === "function" && globalDashboardData) {
    renderSwarmsView(globalDashboardData);
  }
  if (typeof renderActiveBurstSessions === "function" && globalDashboardData) {
    const q5h = (globalDashboardData.quotas && globalDashboardData.quotas.providers && globalDashboardData.quotas.providers.gemini && globalDashboardData.quotas.providers.gemini.five_hour) || (globalDashboardData.quotas && globalDashboardData.quotas.rolling_5h) || {};
    renderActiveBurstSessions(q5h.active_sessions_5h || []);
  }
  if (typeof renderCacheCoaching === "function" && globalDashboardData && globalDashboardData.summary) {
    renderCacheCoaching(globalDashboardData.summary.cache_coaching);
  }
  if (typeof renderWeeklyTrends === "function" && globalDashboardData) {
    renderWeeklyTrends(globalDashboardData);
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
  if (btnLight && btnDark) {
    if (activeTheme === "light") {
      btnLight.classList.add("active");
      btnDark.classList.remove("active");
    } else {
      btnDark.classList.add("active");
      btnLight.classList.remove("active");
    }
  }

  updateCurrencyViews();
  updateWindowToggleStyles();
}

function initDashboard() {
  if (window.__TELEMETRY_DATA__ && typeof window.__TELEMETRY_DATA__ === "object") {
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

  activeFilteredConversations = convos;
  activeConvoForTurns = null;

  // Update Header Badges & Subscription Status
  document.getElementById("session-count-badge").textContent = `${convos.length} Sessions`;
  const subscriptionStatus = summary.subscription_status || "SAFE_IN_QUOTA";
  const statusBadge = document.getElementById("sub-status-badge");
  if (summary.tier === "free") {
    statusBadge.className = "badge blue";
    statusBadge.textContent = "● Free Quota Allowance";
  } else if (subscriptionStatus === "SAFE_IN_QUOTA") {
    statusBadge.className = "badge green";
    statusBadge.textContent = "● Safe in Pro Quota";
  } else if (subscriptionStatus === "WEEKLY_EXHAUSTED") {
    statusBadge.className = "badge";
    statusBadge.style.background = "rgba(239,68,68,0.15)";
    statusBadge.style.color = "#ef4444";
    statusBadge.style.border = "1px solid rgba(239,68,68,0.4)";
    statusBadge.textContent = "⚠️ Weekly Quota Exhausted";
  } else if (subscriptionStatus === "RECOVERED_COOLDOWN") {
    statusBadge.className = "badge blue";
    statusBadge.textContent = "● Recovered (Cooldown)";
  } else {
    statusBadge.className = "badge amber";
    statusBadge.textContent = "● Burning AI Credits";
  }

  const billingBadge = document.getElementById("billing-cycle-badge");
  if (billingBadge) {
    billingBadge.textContent = `Billing: Renews 24 Sep (${summary.monthly_renewal_human || "19 days"} left)`;
  }

  const tierBadge = document.getElementById("header-tier-badge");
  if (tierBadge) {
    const pName = (summary.temporal_provenance && summary.temporal_provenance.active_plan && summary.temporal_provenance.active_plan.name) || summary.subscription_name || "Pro Tier";
    tierBadge.textContent = pName.includes("Enterprise") ? "Enterprise Tier Active" : (pName.includes("Ultra") ? "Ultra Tier Active" : "Pro Tier Active");
  }

  // Populate 5h Window Box (safe checks)
  const r5h = quotas.rolling_5h || {};
  const peaks = quotas.historical_peaks || {};
  const q5hTokens = document.getElementById("quota-5h-tokens");
  if (q5hTokens) q5hTokens.textContent = formatNumber(r5h.total_processed_tokens);
  const q5hSub = document.getElementById("quota-5h-sub");
  if (q5hSub) q5hSub.textContent = `${formatNumber(r5h.turn_count)} turns • ${(r5h.cache_hit_ratio_pct || 0).toFixed(1)}% cache hit`;
  
  const peak5h = peaks.peak_5h_tokens || r5h.total_processed_tokens || 1;
  const pct5h = Math.min(100, Math.max(0, (r5h.total_processed_tokens / peak5h) * 100));
  const q5hProg = document.getElementById("quota-5h-progress");
  if (q5hProg) q5hProg.style.width = pct5h + "%";

  // Recovery schedule
  const sched = r5h.recovery_schedule || [];
  const recPill = document.getElementById("quota-5h-recovery");
  if (recPill) {
    if (sched.length > 0) {
      recPill.style.display = "inline-flex";
      const recText = document.getElementById("quota-5h-recovery-text");
      if (recText) {
        recText.textContent = `Next recovery in ${sched[0].minutes_remaining}m: +${formatNumber(sched[0].tokens_to_recover)} tokens from ${sched[0].model_name}`;
      }
    } else {
      recPill.style.display = "none";
    }
  }

  // Populate Weekly Allowance Cycle Box (safe checks)
  const weekly = quotas.weekly_cycle || quotas.rolling_1w || {};
  const q1wTokens = document.getElementById("quota-1w-tokens");
  if (q1wTokens) q1wTokens.textContent = formatNumber(weekly.total_processed_tokens);
  const q1wSub = document.getElementById("quota-1w-sub");
  if (q1wSub) q1wSub.textContent = `${formatNumber(weekly.turn_count)} turns • ${(weekly.cache_hit_ratio_pct || 0).toFixed(1)}% cache hit`;
  const peak1w = peaks.peak_1w_tokens || weekly.total_processed_tokens || 1;
  const pct1w = Math.min(100, Math.max(0, (weekly.total_processed_tokens / peak1w) * 100));
  const q1wProg = document.getElementById("quota-1w-progress");
  if (q1wProg) q1wProg.style.width = pct1w + "%";
  const weeklyResetText = document.getElementById("quota-weekly-reset-text");
  if (weeklyResetText) {
    const locReset = formatLocalizedResetTime(weekly.weekly_reset_utc, weekly.reset_display);
    weeklyResetText.textContent = `${locReset} (${weekly.human_remaining || "in 5 days"} remaining)`;
  }

  // Populate Dual-Track Provider Quotas (Antigravity IDE Surface - ADR-019 & ADR-021)
  const providers = quotas.providers || {};
  const geminiProv = providers.gemini || {};
  const claudeProv = providers.claude_gpt || {};
  const desktopSync = providers.desktop_sync || {};

  const desktopSyncBadge = document.getElementById("desktop-sync-badge");
  if (desktopSyncBadge) {
    if (desktopSync.active) {
      desktopSyncBadge.style.display = "inline-flex";
      desktopSyncBadge.className = "badge green";
      desktopSyncBadge.textContent = "● Live Desktop Sync";
    } else {
      desktopSyncBadge.style.display = "inline-flex";
      desktopSyncBadge.className = "badge muted";
      desktopSyncBadge.textContent = "○ Cost-Weighted Offline";
    }
  }

  const gWk = geminiProv.weekly || {};
  const g5h = geminiProv.five_hour || {};
  const cWk = claudeProv.weekly || {};
  const c5h = claudeProv.five_hour || {};

  // Gemini Weekly
  const geminiWkElem = document.getElementById("gemini-weekly-pct");
  if (geminiWkElem) {
    const gWkRem = gWk.remaining_pct !== undefined ? gWk.remaining_pct : 100;
    geminiWkElem.textContent = `${gWkRem}% Available`;
  }
  const geminiWkSub = document.getElementById("gemini-weekly-sub");
  if (geminiWkSub) {
    const locReset = formatLocalizedResetTime(gWk.weekly_reset_utc, gWk.reset_display);
    geminiWkSub.textContent = `${gWk.message || "It will fully refresh in 4 days, 6 hours"} • Resets ${locReset}`;
  }
  const geminiWkProg = document.getElementById("gemini-weekly-progress");
  if (geminiWkProg) {
    geminiWkProg.style.width = `${Math.min(100, Math.max(0, gWk.remaining_pct !== undefined ? gWk.remaining_pct : 100))}%`;
  }

  // Gemini 5h Burst
  const gemini5hElem = document.getElementById("gemini-5h-pct");
  if (gemini5hElem) {
    const g5hRem = g5h.remaining_pct !== undefined ? g5h.remaining_pct : 100;
    gemini5hElem.textContent = `${g5hRem}% Available`;
  }
  const spilloverOn = summary.use_ai_credits !== false;
  const spillBadge = document.getElementById("gemini-spillover-badge");
  if (spillBadge) {
    if (spilloverOn) {
      spillBadge.className = "badge blue";
      spillBadge.textContent = "Credit Spillover ON";
    } else {
      spillBadge.className = "badge muted";
      spillBadge.style.color = "var(--text-muted)";
      spillBadge.textContent = "Credit Overages OFF";
    }
  }
  const gemini5hSub = document.getElementById("gemini-5h-sub");
  if (gemini5hSub) {
    const g5hTokens = formatNumber(g5h.total_processed_tokens || 0);
    const g5hRem = g5h.remaining_pct !== undefined ? g5h.remaining_pct : 100;

    let refreshPrefix = "";
    if (g5hRem < 100) {
      if (g5h.reset_time) {
        const resetMs = new Date(g5h.reset_time).getTime();
        const diffSec = Math.max(0, Math.floor((resetMs - Date.now()) / 1000));
        if (diffSec > 0) {
          const hours = Math.floor(diffSec / 3600);
          const minutes = Math.floor((diffSec % 3600) / 60);
          refreshPrefix = hours > 0
            ? `It will fully refresh in ${hours} hour${hours > 1 ? "s" : ""}, ${minutes} minute${minutes !== 1 ? "s" : ""}. • `
            : `It will fully refresh in ${minutes} minute${minutes !== 1 ? "s" : ""}. • `;
        }
      } else if (g5h.message) {
        const match = g5h.message.match(/fully refresh in (.*?)(?:\.|$)/i);
        if (match) {
          refreshPrefix = `It will fully refresh in ${match[1]}. • `;
        }
      } else if (g5h.recovery_schedule && g5h.recovery_schedule.length > 0) {
        const lastRec = g5h.recovery_schedule[g5h.recovery_schedule.length - 1];
        if (lastRec && lastRec.minutes_remaining) {
          const h = Math.floor(lastRec.minutes_remaining / 60);
          const m = lastRec.minutes_remaining % 60;
          const timeStr = h > 0 ? `${h}h ${m}m` : `${m}m`;
          refreshPrefix = `It will fully refresh in ${timeStr}. • `;
        }
      }
    } else {
      refreshPrefix = "Fully refreshed • ";
    }

    const spillText = spilloverOn ? "Google One Credit Spillover active" : "Credit Overages disabled";
    gemini5hSub.textContent = `${refreshPrefix}${g5hTokens} tokens in 5h window (${g5h.turn_count || 0} turns) • ${spillText}`;
  }
  const gemini5hProg = document.getElementById("gemini-5h-progress");
  if (gemini5hProg) {
    gemini5hProg.style.width = `${Math.min(100, Math.max(0, g5h.remaining_pct !== undefined ? g5h.remaining_pct : 100))}%`;
  }

  // M3: Render Active 5-Hour Burst Sessions Drawer
  if (typeof renderActiveBurstSessions === "function") {
    const burstSessions = g5h.active_sessions_5h || (globalDashboardData && globalDashboardData.quotas && globalDashboardData.quotas.rolling_5h && globalDashboardData.quotas.rolling_5h.active_sessions_5h) || [];
    renderActiveBurstSessions(burstSessions);
  }

  // Claude/GPT Weekly
  const claudeWkElem = document.getElementById("claude-weekly-pct");
  if (claudeWkElem) {
    const cWkRem = cWk.remaining_pct !== undefined ? cWk.remaining_pct : 100;
    claudeWkElem.textContent = `${cWkRem}% Available`;
  }
  const claudeWkSub = document.getElementById("claude-weekly-sub");
  if (claudeWkSub) {
    claudeWkSub.textContent = `${cWk.message || "Fully refreshed"} • 7-day rolling window`;
  }
  const claudeWkProg = document.getElementById("claude-weekly-progress");
  if (claudeWkProg) {
    claudeWkProg.style.width = `${Math.min(100, Math.max(0, cWk.remaining_pct !== undefined ? cWk.remaining_pct : 100))}%`;
  }

  // Claude/GPT 5h Burst
  const claude5hElem = document.getElementById("claude-5h-pct");
  if (claude5hElem) {
    const c5hRem = c5h.remaining_pct !== undefined ? c5h.remaining_pct : 100;
    claude5hElem.textContent = `${c5hRem}% Available`;
  }
  const claude5hSub = document.getElementById("claude-5h-sub");
  if (claude5hSub) {
    const c5hTokens = formatNumber(c5h.total_processed_tokens || 0);
    const c5hRem = c5h.remaining_pct !== undefined ? c5h.remaining_pct : 100;
    let c5hPrefix = "";
    if (c5hRem < 100 && c5h.reset_time) {
      const resetMs = new Date(c5h.reset_time).getTime();
      const diffSec = Math.max(0, Math.floor((resetMs - Date.now()) / 1000));
      if (diffSec > 0) {
        const hours = Math.floor(diffSec / 3600);
        const minutes = Math.floor((diffSec % 3600) / 60);
        c5hPrefix = hours > 0
          ? `It will fully refresh in ${hours} hour${hours > 1 ? "s" : ""}, ${minutes} minute${minutes !== 1 ? "s" : ""}. • `
          : `It will fully refresh in ${minutes} minute${minutes !== 1 ? "s" : ""}. • `;
      }
    } else if (c5hRem >= 100) {
      c5hPrefix = "Fully refreshed • ";
    }
    claude5hSub.textContent = `${c5hPrefix}${c5hTokens} tokens in 5h window (${c5h.turn_count || 0} turns) • 0 credit spillover (hard-blocks on limit)`;
  }
  const claude5hProg = document.getElementById("claude-5h-progress");
  if (claude5hProg) {
    claude5hProg.style.width = `${Math.min(100, Math.max(0, c5h.remaining_pct !== undefined ? c5h.remaining_pct : 100))}%`;
  }

  // ================= M17: Center Runway & Throttle Governor (ADR-031) =================
  const runway = geminiProv.runway || (globalDashboardData && globalDashboardData.quotas && globalDashboardData.quotas.runway) || {};
  const runwayBadge = document.getElementById("runway-badge");
  const runwayResetText = document.getElementById("runway-reset-text");
  const runwayConsumedPct = document.getElementById("runway-consumed-pct");
  const runwayBarFill = document.getElementById("runway-bar-fill");
  const runwayTimeNeedle = document.getElementById("runway-time-needle");
  const runwayCeilingMarker = document.getElementById("runway-ceiling-marker");
  const runwayTimeLegend = document.getElementById("runway-time-legend");
  const runwayBviVal = document.getElementById("runway-bvi-val");
  const runwayBviSub = document.getElementById("runway-bvi-sub");
  const runwayDailyTarget = document.getElementById("runway-daily-target");
  const runwayExhaustionVal = document.getElementById("runway-exhaustion-val");
  const runwayExhaustionSub = document.getElementById("runway-exhaustion-sub");
  const runwayBurstFooter = document.getElementById("runway-burst-footer");
  const runwayBurstLeft = document.getElementById("runway-burst-left");
  const runwayBurstRight = document.getElementById("runway-burst-right");

  // Badge status & reset text
  if (runwayBadge) {
    const rawStatus = runway.status_text || "Sustainable (0.93x)";
    runwayBadge.textContent = rawStatus.replace(/^[✓✔]\s*/, "");
    if (runway.status_key === "green") {
      runwayBadge.className = "badge green";
    } else if (runway.status_key === "amber") {
      runwayBadge.className = "badge amber";
    } else if (runway.status_key === "red" || runway.status_key === "exhausted") {
      runwayBadge.className = "badge red";
    }
  }
  if (runwayResetText && (gWk.human_remaining || runway.calendar_days_remaining)) {
    const remStr = gWk.human_remaining || `${runway.calendar_days_remaining}d remaining`;
    runwayResetText.textContent = `Reset in ${remStr}`;
  }

  // Sacred Dual Benchmark Bar
  const gConsumed = runway.quota_consumed_pct !== undefined ? runway.quota_consumed_pct : Math.max(0, 100 - (gWk.remaining_pct !== undefined ? gWk.remaining_pct : 100));
  const tElapsed = runway.calendar_time_elapsed_pct !== undefined ? runway.calendar_time_elapsed_pct : 58.0;

  if (runwayConsumedPct) {
    runwayConsumedPct.textContent = `${gConsumed.toFixed(1)}% Consumed`;
  }
  if (runwayBarFill) {
    runwayBarFill.style.width = `${Math.min(100, Math.max(0, gConsumed))}%`;
    if (runway.status_key === "red" || runway.status_key === "exhausted") {
      runwayBarFill.style.background = "#ef4444";
    } else if (runway.status_key === "amber") {
      runwayBarFill.style.background = "#f59e0b";
    } else {
      runwayBarFill.style.background = "#10b981";
    }
  }
  if (runwayTimeNeedle) {
    runwayTimeNeedle.style.left = `${Math.min(100, Math.max(0, tElapsed))}%`;
  }
  const cCeiling = runway.daily_ceiling_pct !== undefined ? runway.daily_ceiling_pct : 28.6;
  const dIndex = runway.day_index || Math.max(1, Math.min(7, Math.ceil(tElapsed * 0.07)));
  if (runwayCeilingMarker) {
    runwayCeilingMarker.style.left = `${Math.min(100, Math.max(0, cCeiling))}%`;
    runwayCeilingMarker.title = `Day ${dIndex} Ceiling Marker: ${cCeiling}%`;
  }
  if (runwayTimeLegend) {
    const dElapsed = runway.calendar_days_elapsed !== undefined ? runway.calendar_days_elapsed : (tElapsed * 0.07).toFixed(1);
    runwayTimeLegend.innerHTML = `<span style="display: inline-flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #0ea5e9;"></span> Time: ${tElapsed}% (Day ${dElapsed}/7)</span><span style="color: var(--card-border);">•</span><span style="display: inline-flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 6px; height: 2px; background: #94a3b8;"></span> Day ${dIndex} ceiling: ${cCeiling}%</span>`;
  }

  // 3-Pillar KPIs
  if (runwayBviVal) {
    runwayBviVal.textContent = runway.bvi_display || "0.00x";
    if (runway.status_key === "red" || runway.status_key === "exhausted") {
      runwayBviVal.style.color = "#ef4444";
    } else if (runway.status_key === "amber") {
      runwayBviVal.style.color = "#f59e0b";
    } else {
      runwayBviVal.style.color = "var(--text-main)";
    }
  }
  if (runwayBviSub) {
    if (runway.status_sub) {
      const match = runway.status_sub.match(/^(.*?)\s*(\(.*?\))$/);
      if (match) {
        runwayBviSub.innerHTML = `<div>${escapeHtml(match[1])}</div><div style="font-size: 0.62rem; color: var(--text-muted); margin-top: 1px;">${escapeHtml(match[2])}</div>`;
      } else {
        runwayBviSub.textContent = runway.status_sub;
      }
      runwayBviSub.title = runway.status_sub;
    } else if (runway.status_key === "green") {
      runwayBviSub.textContent = "Sustainable pace";
    } else if (runway.status_key === "amber") {
      runwayBviSub.textContent = "Accelerated burn";
    } else if (runway.status_key === "red") {
      runwayBviSub.textContent = "Critical overburn";
    } else if (runway.status_key === "exhausted") {
      runwayBviSub.textContent = "Quota exhausted";
    } else {
      runwayBviSub.textContent = "Safe pace";
    }

    if (runway.status_key === "red" || runway.status_key === "exhausted") {
      runwayBviSub.style.color = "#ef4444";
    } else if (runway.status_key === "amber") {
      runwayBviSub.style.color = "#f59e0b";
    } else {
      runwayBviSub.style.color = "var(--accent-green)";
    }
  }

  if (runwayDailyTarget) {
    runwayDailyTarget.textContent = `${runway.target_daily_budget_pct !== undefined ? runway.target_daily_budget_pct : 15.8}%`;
  }

  if (runwayExhaustionVal) {
    runwayExhaustionVal.textContent = runway.exhaustion_eta || "None";
    if (runway.exhaustion_eta && runway.exhaustion_eta !== "None") {
      runwayExhaustionVal.style.color = (runway.status_key === "red" || runway.status_key === "exhausted") ? "#ef4444" : "#f59e0b";
    } else {
      runwayExhaustionVal.style.color = "var(--accent-green)";
    }
  }
  if (runwayExhaustionSub) {
    runwayExhaustionSub.textContent = runway.exhaustion_caption || "Survives to reset";
  }

  // In-Place Burst Governor Footer Slot
  if (runwayBurstFooter && runwayBurstLeft && runwayBurstRight) {
    if (runway.burst_cooldown_active) {
      runwayBurstFooter.style.border = "1px solid rgba(168, 85, 247, 0.5)";
      runwayBurstFooter.style.background = "rgba(168, 85, 247, 0.08)";
      runwayBurstLeft.innerHTML = `<span style="display: inline-flex; align-items: center; gap: 6px; font-weight: 700; color: #a855f7;"><span style="width: 8px; height: 8px; border-radius: 50%; background: #a855f7; animation: pulse 1s infinite;"></span> ⚡ Burst Limit Hit</span>`;
      startBurstCountdown(runway.burst_seconds_remaining || 1722);
    } else {
      runwayBurstFooter.style.border = "1px solid var(--card-border)";
      runwayBurstFooter.style.background = "var(--card-bg)";
      const bUsed = runway.burst_used_pct !== undefined ? runway.burst_used_pct : Math.max(0, 100 - (g5h.remaining_pct !== undefined ? g5h.remaining_pct : 100));
      runwayBurstLeft.innerHTML = `<span style="color: var(--text-muted);">5h Burst Governor:</span><span style="display: inline-flex; align-items: center; gap: 4px; font-weight: 600; color: var(--accent-green);"><span style="width: 6px; height: 6px; border-radius: 50%; background: #22c55e;"></span> Normal (${bUsed.toFixed(0)}% used)</span>`;
      runwayBurstRight.textContent = "No cooldown";
    }
  }

  // M16: Exhaustion Alarm State Rendering (ADR-028)
  const alarm = geminiProv.exhaustion_alarm || {};
  const geminiExhausted = alarm.gemini_weekly_exhausted === true;
  const claudeFallbackReady = alarm.claude_fallback_ready === true;

  // Gemini Card: Exhaustion Badge
  const exhaustionBadge = document.getElementById("gemini-exhaustion-badge");
  if (exhaustionBadge) {
    if (geminiExhausted) {
      exhaustionBadge.style.display = "inline-flex";
      exhaustionBadge.className = "badge";
      exhaustionBadge.style.background = "rgba(239,68,68,0.15)";
      exhaustionBadge.style.color = "#ef4444";
      exhaustionBadge.style.border = "1px solid rgba(239,68,68,0.4)";
      exhaustionBadge.textContent = "⚠️ EXHAUSTED (0%)";
    } else {
      exhaustionBadge.style.display = "none";
    }
  }

  // Gemini Card: Weekly pct styling override when exhausted
  if (geminiExhausted && geminiWkElem) {
    geminiWkElem.className = "";
    geminiWkElem.style.fontWeight = "700";
    geminiWkElem.style.fontSize = "0.9375rem";
    geminiWkElem.style.color = "#ef4444";
    geminiWkElem.textContent = "0% Available";
    if (geminiWkSub) {
      const locReset = formatLocalizedResetTime(gWk.weekly_reset_utc, gWk.reset_display);
      geminiWkSub.innerHTML = `Resets ${locReset} <span style="color: var(--accent-amber);">(in ${alarm.reset_countdown_human || ""})</span>`;
    }
    if (geminiWkProg) {
      geminiWkProg.style.width = "0%";
      geminiWkProg.style.background = "#ef4444";
    }
  }

  // Gemini Card: 5h Burst disabled/superseded styling when weekly exhausted
  if (alarm.gemini_5h_disabled && gemini5hElem) {
    gemini5hElem.className = "";
    gemini5hElem.style.fontWeight = "700";
    gemini5hElem.style.fontSize = "0.9375rem";
    gemini5hElem.style.color = "var(--text-muted)";
    gemini5hElem.textContent = "DISABLED / SUPERSEDED";
    if (gemini5hProg) {
      gemini5hProg.style.width = "0%";
      gemini5hProg.style.opacity = "0.4";
    }
    if (gemini5hSub) {
      gemini5hSub.textContent = "5-hour burst is subsumed when weekly limit is exhausted";
    }
  }

  // Claude Card: Fallback Callout
  const fallbackCallout = document.getElementById("claude-fallback-callout");
  const fallbackPct = document.getElementById("claude-fallback-pct");
  if (fallbackCallout) {
    if (claudeFallbackReady) {
      fallbackCallout.style.display = "block";
      const cWkRem = cWk.remaining_pct !== undefined ? cWk.remaining_pct : 100;
      if (fallbackPct) fallbackPct.textContent = `${cWkRem}% Available`;
    } else {
      fallbackCallout.style.display = "none";
    }
  }

  // Recovery Timeline Card: Paused notice
  const pausedNotice = document.getElementById("timeline-paused-notice");
  const pausedReset = document.getElementById("timeline-paused-reset");
  if (pausedNotice) {
    if (geminiExhausted) {
      pausedNotice.style.display = "block";
      if (pausedReset) {
        pausedReset.textContent = formatLocalizedResetTime(gWk.weekly_reset_utc, gWk.reset_display);
      }
      // Also update the Safe Zone badge to show Paused
      const badgeSafe2 = document.getElementById("badge-safe-zone");
      if (badgeSafe2) {
        badgeSafe2.textContent = "⏸ Quota Paused";
        badgeSafe2.className = "badge amber";
      }
    } else {
      pausedNotice.style.display = "none";
    }
  }

  // M16: Interactive vs. Subagent Breakdown Pills
  const subMetrics = summary.subagent_metrics || {};
  const pillAll = document.getElementById("pill-all-turns");
  const pillInteractive = document.getElementById("pill-interactive");
  const pillSubagent = document.getElementById("pill-subagent");
  if (pillAll && subMetrics.interactive && subMetrics.subagent) {
    const iM = subMetrics.interactive;
    const sM = subMetrics.subagent;
    const totalTokens = iM.total_tokens + sM.total_tokens;
    const totalCost = iM.imputed_cost_usd + sM.imputed_cost_usd;
    pillAll.textContent = `All: ${formatNumber(totalTokens)} (${formatCurrency(totalCost, totalCost * 0.79, 2)})`;
    pillInteractive.textContent = `💬 Interactive: ${formatNumber(iM.total_tokens)} (${formatCurrency(iM.imputed_cost_usd, iM.imputed_cost_usd * 0.79, 2)})`;
    pillSubagent.textContent = `🤖 Subagents: ${formatNumber(sM.total_tokens)} (${formatCurrency(sM.imputed_cost_usd, sM.imputed_cost_usd * 0.79, 2)}) • ${sM.quota_share_pct}%`;
  }

  // Populate Card 3: Monthly Subscription
  const subPlanTitle = document.getElementById("quota-sub-tier-title");
  if (subPlanTitle) {
    subPlanTitle.textContent = summary.subscription_name || "Monthly Subscription";
  }
  const subRenewalBadge = document.getElementById("quota-sub-renewal-badge");
  if (subRenewalBadge) {
    subRenewalBadge.textContent = summary.monthly_renewal_display ? `Renews ${summary.monthly_renewal_display}` : (summary.monthly_billing_day ? `Renews Day ${summary.monthly_billing_day}` : "Renews 13 Oct");
  }
  const subStatus = document.getElementById("quota-sub-status");
  if (subStatus) {
    subStatus.textContent = `Renews in ${summary.monthly_renewal_human || "19 days"} • £0 marginal cost in quota`;
  }
  const subRoiMultiplier = document.getElementById("quota-sub-roi-multiplier");
  if (subRoiMultiplier) {
    const roi = summary.monthly_subscription_roi !== undefined ? summary.monthly_subscription_roi : 1.0;
    subRoiMultiplier.textContent = `${roi.toFixed(1)}x ROI`;
  }

  // Populate Card 4: Prepaid Overage Credit Bank (2,500 Credits)
  const totalBurn = summary.total_ai_credits_burned || 0;
  const quotaCreditsBadge = document.getElementById("quota-credits-badge");
  if (quotaCreditsBadge) {
    if (totalBurn > 0) {
      quotaCreditsBadge.className = "badge amber";
      quotaCreditsBadge.textContent = `${formatNumber(totalBurn)} Credits Burned`;
    } else {
      quotaCreditsBadge.className = "badge green";
      quotaCreditsBadge.textContent = "0 Credits Burned";
    }
  }
  const creditsRemHero = document.getElementById("quota-credits-remaining-hero");
  if (creditsRemHero) {
    const rem = summary.credits_remaining !== undefined ? summary.credits_remaining : 2500;
    creditsRemHero.textContent = `${formatNumber(rem)} Left`;
  }
  const creditsProg = document.getElementById("quota-credits-progress");
  if (creditsProg) {
    const totalBank = summary.credit_bank_total || 2500;
    const pctBurn = Math.min(100, Math.max(0, (totalBurn / totalBank) * 100));
    creditsProg.style.width = pctBurn + "%";
  }
  const creditsBurnedCount = document.getElementById("quota-credits-burned-count");
  if (creditsBurnedCount) {
    creditsBurnedCount.textContent = formatNumber(totalBurn);
  }

  // Lifetime KPI cards
  document.getElementById("kpi-total-input").textContent = formatNumber(summary.total_input_tokens);
  document.getElementById("kpi-cached-tokens").textContent = formatNumber(summary.cached_tokens);
  document.getElementById("kpi-uncached-tokens").textContent = formatNumber(summary.prompt_tokens_uncached);

  const cacheRatio = summary.cache_hit_ratio_pct || 0.0;
  document.getElementById("kpi-cache-ratio").textContent = cacheRatio.toFixed(1) + "%";
  document.getElementById("kpi-cache-progress").style.width = Math.min(100, Math.max(0, cacheRatio)) + "%";

  document.getElementById("kpi-total-output").textContent = formatNumber(summary.total_output_tokens);
  document.getElementById("kpi-thinking-tokens").textContent = formatNumber(summary.thinking_tokens);
  document.getElementById("kpi-answer-tokens").textContent = formatNumber(summary.answer_tokens);

  // kpi-turns-sub is dynamically updated in updateCurrencyViews

  // Setup window toggles
  document.getElementById("btn-toggle-5h").addEventListener("click", () => {
    activeModelWindow = "5h";
    updateWindowToggleStyles();
    renderModelMatrix("5h");
  });

  document.getElementById("btn-toggle-1w").addEventListener("click", () => {
    activeModelWindow = "1w";
    updateWindowToggleStyles();
    renderModelMatrix("1w");
  });
  updateWindowToggleStyles();

  // Setup currency toggles
  const btnGbp = document.getElementById("btn-curr-gbp");
  const btnUsd = document.getElementById("btn-curr-usd");
  if (btnGbp) {
    btnGbp.addEventListener("click", () => {
      if (activeCurrency !== "GBP") {
        activeCurrency = "GBP";
        updateCurrencyViews();
      }
    });
  }
  if (btnUsd) {
    btnUsd.addEventListener("click", () => {
      if (activeCurrency !== "USD") {
        activeCurrency = "USD";
        updateCurrencyViews();
      }
    });
  }

  // Setup theme toggles
  const btnThemeLight = document.getElementById("btn-theme-light");
  const btnThemeDark = document.getElementById("btn-theme-dark");
  if (btnThemeLight) {
    btnThemeLight.addEventListener("click", () => {
      if (activeTheme !== "light") {
        activeTheme = "light";
        updateThemeViews();
      }
    });
  }
  if (btnThemeDark) {
    btnThemeDark.addEventListener("click", () => {
      if (activeTheme !== "dark") {
        activeTheme = "dark";
        updateThemeViews();
      }
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
        if (btnCopyStandupText) btnCopyStandupText.textContent = "Copied! 👍";
        setTimeout(() => {
          if (btnCopyStandupText) btnCopyStandupText.textContent = "Copy Summary";
        }, 2000);
      } catch (err) {
        console.error("Failed to copy standup digest:", err);
      }
    });
  }

  // Populate Workspace filter
  const wsSelect = document.getElementById("workspace-filter");
  workspaces.forEach(ws => {
    const opt = document.createElement("option");
    opt.value = ws.workspace;
    opt.textContent = `${ws.workspace} (${ws.conversation_count} sessions)`;
    wsSelect.appendChild(opt);
  });

  // Populate Conversation filter
  const convoSelect = document.getElementById("convo-filter");
  convos.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c.convo_id;
    opt.textContent = `${c.title} (${c.turn_count} turns)`;
    convoSelect.appendChild(opt);
  });

  // Event Listeners for Filters
  wsSelect.addEventListener("change", () => filterData(convos));
  convoSelect.addEventListener("change", () => filterData(convos));
  const searchInput = document.getElementById("convo-search-input");
  if (searchInput) {
    searchInput.addEventListener("input", () => filterData(convos));
  }

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

  // Initial theme and currency render
  updateThemeViews();
  renderRecoveryTimeline();
  initAutoRefresh();
  initPlanManagerModal();
  initSimulator();
  renderSwarmsView(globalDashboardData);
  renderToolAnalytics(globalDashboardData);
  if (typeof renderActiveBurstSessions === "function") {
    const q5h = (quotas.providers && quotas.providers.gemini && quotas.providers.gemini.five_hour) || quotas.rolling_5h || {};
    renderActiveBurstSessions(q5h.active_sessions_5h || []);
  }
  if (typeof renderCacheCoaching === "function") {
    renderCacheCoaching(summary.cache_coaching);
  }
  if (typeof initWeeklyTrends === "function") {
    initWeeklyTrends();
  }
  if (typeof renderWeeklyTrends === "function") {
    renderWeeklyTrends(globalDashboardData);
  }


  // Deep linking via URL parameters or stored active tab
  try {
    const urlParams = new URLSearchParams(window.location.search);
    let initialTab = urlParams.get("tab");
    if (!initialTab) {
      try { initialTab = localStorage.getItem("antigravity_active_tab"); } catch(e) {}
    }
    if (initialTab && ["tab-now", "tab-sessions", "tab-projects", "tab-swarms", "tab-billing", "tab-plan", "tab-quotas", "tab-credits", "tab-simulator"].includes(initialTab)) {
      switchTab(initialTab);
    } else {
      switchTab("tab-now");
    }
    if (urlParams.get("expand_project") !== null) {
      const pIdx = parseInt(urlParams.get("expand_project"), 10) || 0;
      setTimeout(() => toggleProjectBranches(pIdx), 50);
    }
    if (urlParams.get("open_turns") !== null && convos.length > 0) {
      const cIdx = parseInt(urlParams.get("open_turns"), 10) || 0;
      if (convos[cIdx]) {
        convoSelect.value = convos[cIdx].convo_id;
        activeConvoForTurns = convos[cIdx];
        renderTurnsTable(convos[cIdx]);
      }
    }
  } catch (e) {}
}

let liveTickTimer = null;
let autoRefreshTimer = null;
let autoRefreshEnabled = true;

function renderRecoveryTimeline() {
  // Obsolete 5-Hour Recovery Timeline card removed in favor of Runway Burst Governor hero deck.
}

function updateTimelineTick() {
  // Timeline tick retired.
}

function initAutoRefresh() {
  if (liveTickTimer) clearInterval(liveTickTimer);

  const btnRefresh = document.getElementById("btn-auto-refresh");
  if (btnRefresh) {
    const savedPref = localStorage.getItem("antigravity_auto_refresh");
    if (savedPref !== null) {
      autoRefreshEnabled = savedPref === "true";
    }
    updateAutoRefreshButton();

    btnRefresh.addEventListener("click", () => {
      autoRefreshEnabled = !autoRefreshEnabled;
      try {
        localStorage.setItem("antigravity_auto_refresh", String(autoRefreshEnabled));
      } catch(e) {}
      updateAutoRefreshButton();
      if (autoRefreshEnabled) {
        checkAndReloadTelemetry();
      }
    });
  }

  if (autoRefreshTimer) clearInterval(autoRefreshTimer);
  autoRefreshTimer = setInterval(() => {
    if (autoRefreshEnabled) {
      checkAndReloadTelemetry();
    }
  }, 30000);

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && autoRefreshEnabled) {
      checkAndReloadTelemetry();
    }
  });
}

function updateAutoRefreshButton() {
  const btn = document.getElementById("btn-auto-refresh");
  if (!btn) return;
  if (autoRefreshEnabled) {
    btn.textContent = "🔄 Live Auto-Refresh: ON (30s)";
    btn.style.color = "var(--accent-green)";
    btn.style.borderColor = "var(--accent-green)";
  } else {
    btn.textContent = "⏸ Auto-Refresh: PAUSED";
    btn.style.color = "var(--text-muted)";
    btn.style.borderColor = "var(--card-border)";
  }
}

let burstCountdownTimer = null;
function startBurstCountdown(initialSeconds) {
  if (burstCountdownTimer) clearInterval(burstCountdownTimer);
  let secs = initialSeconds;
  const target = document.getElementById("runway-burst-right");
  if (!target) return;
  const fmt = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}m ${sec < 10 ? '0' : ''}${sec}s left`;
  };
  target.innerHTML = `<span style="font-weight: 700; font-family: monospace; color: #a855f7;">${fmt(secs)}</span>`;
  burstCountdownTimer = setInterval(() => {
    secs--;
    if (secs <= 0) {
      clearInterval(burstCountdownTimer);
      burstCountdownTimer = null;
      const footer = document.getElementById("runway-burst-footer");
      const left = document.getElementById("runway-burst-left");
      if (footer) {
        footer.style.border = "1px solid var(--card-border)";
        footer.style.background = "var(--card-bg)";
      }
      if (left) {
        left.innerHTML = `<span style="color: var(--text-muted);">5h Burst Governor:</span><span style="display: inline-flex; align-items: center; gap: 4px; font-weight: 600; color: var(--accent-green);"><span style="width: 6px; height: 6px; border-radius: 50%; background: #22c55e;"></span> Normal</span>`;
      }
      if (target) target.textContent = "No cooldown";
    } else {
      target.innerHTML = `<span style="font-weight: 700; font-family: monospace; color: #a855f7;">${fmt(secs)}</span>`;
    }
  }, 1000);
}

let currentTelemetrySha1 = (window.__TELEMETRY_META__ && window.__TELEMETRY_META__.payload_sha1) || null;

function checkAndReloadTelemetry() {
  const metaScript = document.createElement("script");
  metaScript.src = `meta.js?t=${Date.now()}`;
  metaScript.onload = () => {
    metaScript.remove();
    const latestMeta = window.__TELEMETRY_META__;
    const newSha1 = latestMeta && latestMeta.payload_sha1;

    if (newSha1 && currentTelemetrySha1 && newSha1 === currentTelemetrySha1 && globalDashboardData) {
      return;
    }

    currentTelemetrySha1 = newSha1;
    const dataScript = document.createElement("script");
    dataScript.src = `data.js?t=${Date.now()}`;
    dataScript.onload = () => {
      if (window.__TELEMETRY_DATA__) {
        globalDashboardData = window.__TELEMETRY_DATA__;
        initDashboard();
      }
      dataScript.remove();
    };
    dataScript.onerror = () => {
      dataScript.remove();
    };
    document.head.appendChild(dataScript);
  };
  metaScript.onerror = () => {
    metaScript.remove();
    const dataScript = document.createElement("script");
    dataScript.src = `data.js?t=${Date.now()}`;
    dataScript.onload = () => {
      if (window.__TELEMETRY_DATA__) {
        globalDashboardData = window.__TELEMETRY_DATA__;
        initDashboard();
      }
      dataScript.remove();
    };
    dataScript.onerror = () => {
      dataScript.remove();
    };
    document.head.appendChild(dataScript);
  };
  document.head.appendChild(metaScript);
}

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

    tr.innerHTML = `
      <td><strong>${escapeHtml(item.hour_display || item.hour_timestamp)}</strong></td>
      <td><span class="code-pill">Google One AI Credit Burn</span></td>
      <td>${formatNumber(item.turns_count)}</td>
      <td><strong class="highlight-red">-${formatNumber(item.credits_burned)}</strong></td>
      <td><strong class="highlight-red">${formatCurrency(item.credit_burn_usd, item.credit_burn_gbp, 2)}</strong></td>
      <td style="font-size: 0.8125rem; color: var(--text-muted);">${modelsText}</td>
    `;
    tbody.appendChild(tr);
  });
}

function switchTab(tabId) {
  const tabMap = {
    "tab-now": "view-now",
    "tab-sessions": "view-sessions",
    "tab-projects": "view-projects",
    "tab-swarms": "view-swarms",
    "tab-billing": "view-billing",
    "tab-plan": "view-plan",
    // Backward-compatibility aliases
    "tab-quotas": "view-now",
    "tab-credits": "view-billing",
    "tab-simulator": "view-plan"
  };
  const activeViewId = tabMap[tabId] || "view-now";
  const normalizedTabId = (tabId === "tab-quotas") ? "tab-now" :
                          (tabId === "tab-credits") ? "tab-billing" :
                          (tabId === "tab-simulator") ? "tab-plan" : tabId;

  try {
    localStorage.setItem("antigravity_active_tab", normalizedTabId);
  } catch(e) {}

  // Update tab buttons
  ["tab-now", "tab-sessions", "tab-projects", "tab-swarms", "tab-billing", "tab-plan"].forEach(tid => {
    const btn = document.getElementById(tid);
    if (btn) {
      if (tid === normalizedTabId) {
        btn.classList.add("active");
      } else {
        btn.classList.remove("active");
      }
    }
  });

  // Update views
  ["view-now", "view-sessions", "view-projects", "view-swarms", "view-billing", "view-plan"].forEach(vid => {
    const v = document.getElementById(vid);
    if (v) {
      if (vid === activeViewId) {
        v.classList.add("active");
        v.style.display = "block";
      } else {
        v.classList.remove("active");
        v.style.display = "none";
      }
    }
  });

  if (activeViewId === "view-now") {
    renderRecentSessions();
  } else if (activeViewId === "view-sessions") {
    renderConversationsTable(activeFilteredConversations);
  } else if (activeViewId === "view-projects") {
    renderPortfolioView();
  } else if (activeViewId === "view-swarms") {
    renderSwarmsView(globalDashboardData);
    renderToolAnalytics(globalDashboardData);
  } else if (activeViewId === "view-billing") {
    renderHourlyCreditActivity();
    if (typeof renderWeeklyTrends === "function" && globalDashboardData) {
      renderWeeklyTrends(globalDashboardData);
    }
  } else if (activeViewId === "view-plan") {
    runSimulation();
    renderPlanManagerContent();
  }
}

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
      <div class="kpi-value highlight-blue">${formatNumber(totalProjects)}</div>
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
      coverageBadge = '<span class="code-pill" style="color: var(--accent-green); background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3); font-weight: 600;">✓ 100% Covered</span>';
    } else {
      coverageBadge = `<span class="code-pill" style="color: var(--accent-amber); background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); font-weight: 600;">⚠️ ${pCovPct.toFixed(1)}% Covered (${formatNumber(p.overage_turns)} in Overage)</span>`;
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
        <button class="tab-btn" style="padding: 4px 8px; font-size: 0.75rem;" onclick="event.stopPropagation(); toggleProjectBranches(${pIdx})">
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
    branches.forEach(b => {
      const bOvgCredits = b.actual_overage_credits || 0;
      const bOvgUsd = b.actual_overage_usd || 0.0;
      const bOvgGbp = b.actual_overage_gbp || 0.0;
      const bAvoidedUsd = b.avoided_cost_usd !== undefined ? b.avoided_cost_usd : (b.estimated_cost_usd || 0.0);
      const bAvoidedGbp = b.avoided_cost_gbp !== undefined ? b.avoided_cost_gbp : (b.estimated_cost_gbp || 0.0);

      let bStatusBadge = '';
      if (bOvgCredits === 0) {
        bStatusBadge = '<span class="code-pill" style="color: var(--accent-green); font-size: 0.75rem; background: rgba(34,197,94,0.1); border: 1px solid rgba(34,197,94,0.25);">✓ 100% Covered (£0.00)</span>';
      } else {
        bStatusBadge = `<span class="code-pill" style="color: var(--accent-amber); font-size: 0.75rem; background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.25);">⚠️ ${formatNumber(bOvgCredits)} credits (${formatCurrency(bOvgUsd, bOvgGbp, 2)})</span>`;
      }

      branchesHtml += `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; border-bottom: 1px solid var(--card-border); gap: 16px; flex-wrap: wrap;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="code-pill" style="font-weight: 600; color: var(--accent-purple);">🌿 ${escapeHtml(b.branch_name)}</span>
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
        <div style="font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 8px; font-weight: 600;">
          Branch Cost Attribution: ${escapeHtml(p.project_name)}
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
      <td><strong>${escapeHtml(m.model_name)}</strong><br><span style="font-size: 0.75rem; color: #6b7280;">ID: ${m.model_id}</span></td>
      <td>${formatNumber(m.turn_count)}</td>
      <td class="highlight-blue">${formatNumber(m.prompt_tokens_uncached)}</td>
      <td class="highlight-green">${formatNumber(m.cached_tokens)}</td>
      <td>${formatNumber(m.total_input_tokens)}</td>
      <td><strong>${(m.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></td>
      <td>${formatNumber(m.output_tokens_total)} <span style="font-size: 0.75rem; color: #a78bfa;">(${formatNumber(m.thinking_tokens)} thk)</span></td>
      <td><strong style="color: #60a5fa;">${formatNumber(m.total_processed_tokens)}</strong></td>
      <td><strong class="highlight-green">${formatCurrency(mAvoidedUsd, mAvoidedGbp, 4)}</strong></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderConversationsTable(list) {
  const tbody = document.getElementById("conversations-tbody");
  tbody.innerHTML = "";
  document.getElementById("convo-table-count").textContent = `${list.length} conversations`;

  if (list.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No conversations match the current filter.</td></tr>';
    return;
  }

  list.forEach(c => {
    const tr = document.createElement("tr");
    tr.style.cursor = "pointer";

    const cOvgCredits = c.actual_overage_credits || 0;
    const cOvgUsd = c.actual_overage_usd || 0.0;
    const cOvgGbp = c.actual_overage_gbp || 0.0;
    const cAvoidedUsd = c.avoided_cost_usd !== undefined ? c.avoided_cost_usd : (c.estimated_cost_usd || 0.0);
    const cAvoidedGbp = c.avoided_cost_gbp !== undefined ? c.avoided_cost_gbp : (c.estimated_cost_gbp || 0.0);
    const cCovPct = c.subscription_covered_pct !== undefined ? c.subscription_covered_pct : 100.0;

    let coverageBadge = '';
    if (cOvgCredits === 0) {
      coverageBadge = '<span class="code-pill" style="color: var(--accent-green); background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3); font-weight: 600;">✓ 100% Covered</span>';
    } else {
      coverageBadge = `<span class="code-pill" style="color: var(--accent-amber); background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); font-weight: 600;">⚠️ ${cCovPct.toFixed(1)}% Covered</span>`;
    }

    let overageDisplay = '';
    if (cOvgCredits === 0) {
      overageDisplay = `<span style="color: var(--text-muted); font-size: 0.8125rem;">${formatCurrency(0, 0, 2)} <span style="font-size: 0.75rem;">(0 credits)</span></span>`;
    } else {
      overageDisplay = `<strong style="color: var(--accent-amber); font-size: 0.875rem;">${formatCurrency(cOvgUsd, cOvgGbp, 2)}</strong><span style="font-size: 0.75rem; color: var(--accent-amber); display: block;">${formatNumber(cOvgCredits)} credits burned</span>`;
    }

    tr.innerHTML = `
      <td><strong>${escapeHtml(c.title || "Untitled")}</strong><br><span style="font-size: 0.75rem; color: #6b7280;">${c.convo_id}</span></td>
      <td><span class="code-pill">${escapeHtml(c.workspace || "Unknown")}</span></td>
      <td>${formatNumber(c.turn_count)}</td>
      <td>
        ${formatNumber(c.total_input_tokens)}
        <span style="font-size: 0.75rem; color: var(--text-muted); display: block;">${formatNumber(c.cached_tokens)} cached</span>
      </td>
      <td><strong class="highlight-green">${(c.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></td>
      <td>${coverageBadge}</td>
      <td>${overageDisplay}</td>
      <td><strong class="highlight-green">${formatCurrency(cAvoidedUsd, cAvoidedGbp, 4)}</strong></td>
    `;
    tr.addEventListener("click", () => {
      document.getElementById("convo-filter").value = c.convo_id;
      activeConvoForTurns = c;
      renderTurnsTable(c);
    });
    tbody.appendChild(tr);
  });
}

function renderTurnsTable(convo) {
  const turnsCard = document.getElementById("turns-card");
  if (!convo || !convo.turns || convo.turns.length === 0) {
    turnsCard.style.display = "none";
    return;
  }

  turnsCard.style.display = "block";
  document.getElementById("turns-title").textContent = `Turns for: ${convo.title}`;
  document.getElementById("turns-table-count").textContent = `${convo.turns.length} turns`;

  const tbody = document.getElementById("turns-tbody");
  tbody.innerHTML = "";

  convo.turns.forEach(t => {
    const tr = document.createElement("tr");
    const ts = t.timestamp ? formatUkTimestamp(t.timestamp) : "N/A";

    const isOvg = Boolean(t.is_overage);
    let statusBadge = '';
    if (isOvg) {
      statusBadge = '<span class="code-pill" style="color: var(--accent-amber); background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); font-weight: 600;">⚠️ 429 Overage</span>';
    } else {
      statusBadge = '<span class="code-pill" style="color: var(--accent-green); background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3); font-weight: 600;">✓ In Plan</span>';
    }

    const tAvoidedUsd = t.avoided_cost_usd !== undefined ? t.avoided_cost_usd : (t.estimated_cost_usd || 0.0);
    const tAvoidedGbp = t.avoided_cost_gbp !== undefined ? t.avoided_cost_gbp : (t.estimated_cost_gbp || 0.0);

    tr.innerHTML = `
      <td>#${t.step_idx}</td>
      <td style="font-size: 0.75rem; color: var(--text-muted);">${ts}</td>
      <td><span class="code-pill">${escapeHtml(t.model_name || t.model_id)}</span></td>
      <td class="highlight-blue">${formatNumber(t.prompt_tokens_uncached)}</td>
      <td class="highlight-green">${formatNumber(t.cached_tokens)}</td>
      <td>${formatNumber(t.total_input_tokens)}</td>
      <td><strong>${(t.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></td>
      <td>${formatNumber(t.output_tokens_total)} <span style="font-size: 0.75rem; color: #a78bfa;">(${formatNumber(t.thinking_tokens)} thk)</span></td>
      <td>${statusBadge}</td>
      <td><strong class="highlight-green">${formatCurrency(tAvoidedUsd, tAvoidedGbp, 4)}</strong></td>
      <td><span class="code-pill" style="max-width: 120px; display: inline-block; overflow: hidden; text-overflow: ellipsis;">${escapeHtml(t.response_id || "N/A")}</span></td>
    `;
    tbody.appendChild(tr);
  });
  turnsCard.scrollIntoView({ behavior: "smooth" });
}

let convoSortField = "turns";
let convoSortOrder = "desc";

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
      valA = a.total_input_tokens || 0;
      valB = b.total_input_tokens || 0;
    } else if (field === "cache") {
      valA = a.cache_hit_ratio_pct || 0;
      valB = b.cache_hit_ratio_pct || 0;
    } else if (field === "overage") {
      valA = a.actual_overage_credits || 0;
      valB = b.actual_overage_credits || 0;
    } else if (field === "cost") {
      valA = a.avoided_cost_usd || a.estimated_cost_usd || 0;
      valB = b.avoided_cost_usd || b.estimated_cost_usd || 0;
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
  const convoFilter = document.getElementById("convo-filter");
  if (convoFilter) convoFilter.value = "all";
  filterData();
}

function closeTurnsCard() {
  const card = document.getElementById("turns-card");
  if (card) card.style.display = "none";
  const convoFilter = document.getElementById("convo-filter");
  if (convoFilter) convoFilter.value = "all";
  activeConvoForTurns = null;
}

function renderRecentSessions() {
  const tbody = document.getElementById("recent-sessions-tbody");
  if (!tbody) return;
  const convos = (globalDashboardData && globalDashboardData.conversations) || [];
  if (convos.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No conversation sessions found.</td></tr>';
    return;
  }
  const recent = convos.slice(0, 6);
  tbody.innerHTML = "";
  recent.forEach(c => {
    const tr = document.createElement("tr");
    const cAvoidedUsd = c.avoided_cost_usd !== undefined ? c.avoided_cost_usd : (c.estimated_cost_usd || 0.0);
    const cAvoidedGbp = c.avoided_cost_gbp !== undefined ? c.avoided_cost_gbp : (c.estimated_cost_gbp || 0.0);
    const cCovPct = c.subscription_covered_pct !== undefined ? c.subscription_covered_pct : 100.0;
    const covBadge = (c.actual_overage_credits || 0) === 0
      ? '<span class="code-pill" style="color: var(--accent-green); background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3); font-weight: 600;">✓ 100% Covered</span>'
      : `<span class="code-pill" style="color: var(--accent-amber); background: rgba(245,158,11,0.12); border: 1px solid rgba(245,158,11,0.3); font-weight: 600;">⚠️ ${cCovPct.toFixed(0)}% Covered</span>`;

    tr.innerHTML = `
      <td><strong>${escapeHtml(c.title || "Untitled")}</strong><br><span style="font-size: 0.72rem; color: var(--text-muted);">${c.convo_id}</span></td>
      <td><span class="code-pill">${escapeHtml(c.workspace || "Unknown")}</span></td>
      <td>${formatNumber(c.turn_count)}</td>
      <td>${formatNumber(c.total_input_tokens)}</td>
      <td><strong class="highlight-green">${(c.cache_hit_ratio_pct || 0).toFixed(1)}%</strong></td>
      <td>${covBadge}</td>
      <td><strong class="highlight-green">${formatCurrency(cAvoidedUsd, cAvoidedGbp, 2)}</strong></td>
      <td><button class="badge" style="cursor: pointer; background: var(--card-bg); border: 1px solid var(--card-border); font-size: 0.75rem; padding: 2px 8px;" onclick="inspectSession('${c.convo_id}')">Inspect &rarr;</button></td>
    `;
    tbody.appendChild(tr);
  });
}

function inspectSession(convoId) {
  switchTab("tab-sessions");
  const convoFilter = document.getElementById("convo-filter");
  if (convoFilter) convoFilter.value = convoId;
  const convos = (globalDashboardData && globalDashboardData.conversations) || [];
  const selected = convos.find(c => c.convo_id === convoId);
  if (selected) {
    activeFilteredConversations = [selected];
    activeConvoForTurns = selected;
    renderConversationsTable(activeFilteredConversations);
    renderTurnsTable(selected);
  }
}

function filterData(convos) {
  convos = convos || (globalDashboardData && globalDashboardData.conversations) || [];
  const wsFilter = document.getElementById("workspace-filter");
  const convoFilter = document.getElementById("convo-filter");
  const searchInput = document.getElementById("convo-search-input");

  const wsVal = wsFilter ? wsFilter.value : "all";
  const convoVal = convoFilter ? convoFilter.value : "all";
  const query = (searchInput ? searchInput.value : "").trim().toLowerCase();

  let filtered = convos;
  if (wsVal !== "all") {
    filtered = filtered.filter(c => c.workspace === wsVal);
  }

  if (query) {
    filtered = filtered.filter(c => 
      (c.title && c.title.toLowerCase().includes(query)) ||
      (c.convo_id && c.convo_id.toLowerCase().includes(query)) ||
      (c.workspace && c.workspace.toLowerCase().includes(query))
    );
  }

  if (convoVal !== "all") {
    const selected = convos.find(c => c.convo_id === convoVal);
    activeFilteredConversations = selected ? [selected] : [];
    activeConvoForTurns = selected;
    renderConversationsTable(activeFilteredConversations);
    if (selected) renderTurnsTable(selected);
  } else {
    activeFilteredConversations = sortConversations(filtered, convoSortField, convoSortOrder);
    activeConvoForTurns = null;
    renderConversationsTable(activeFilteredConversations);
    const turnsCard = document.getElementById("turns-card");
    if (turnsCard) turnsCard.style.display = "none";
  }
}

function escapeHtml(str) {
  return (str || "").toString()
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function initPlanManagerModal() {
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
          btnCopyJson.textContent = "✓ Copied!";
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
          <td style="padding: 8px; font-family: monospace;">£${(h.monthly_price_gbp || 0).toFixed(2)}</td>
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
        if (fromDt && now < fromDt) status = '<span class="badge blue">Upcoming</span>';
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

  // 4. Rate History Table
  const rateTbody = document.getElementById("rate-history-tbody");
  const rateHistory = temporal.rate_history || {};
  const availability = temporal.availability || {};
  const pricingModels = temporal.models || (globalDashboardData && globalDashboardData.pricing && globalDashboardData.pricing.models) || {};

  const MODEL_TAXONOMY = {
    "1016": { name: "Gemini 3.1 Pro", reasoning: "High Reasoning", family: "gemini-pro" },
    "1036": { name: "Gemini 3.1 Pro", reasoning: "Low Reasoning", family: "gemini-pro" },
    "1318": { name: "Gemini 3.8 Flash", reasoning: "High Reasoning", family: "gemini-flash" },
    "1319": { name: "Gemini 3.8 Flash", reasoning: "Medium Reasoning", family: "gemini-flash" },
    "1320": { name: "Gemini 3.8 Flash", reasoning: "Low Reasoning", family: "gemini-flash" },
    "1298": { name: "Gemini 3.7 Flash", reasoning: "High Reasoning", family: "gemini-flash" },
    "1299": { name: "Gemini 3.7 Flash", reasoning: "Medium Reasoning", family: "gemini-flash" },
    "1300": { name: "Gemini 3.7 Flash", reasoning: "Low Reasoning", family: "gemini-flash" },
    "1071": { name: "Gemini 3.6 Flash", reasoning: "High Reasoning", family: "gemini-flash" },
    "1072": { name: "Gemini 3.6 Flash", reasoning: "Medium Reasoning", family: "gemini-flash" },
    "1073": { name: "Gemini 3.6 Flash", reasoning: "Low Reasoning", family: "gemini-flash" },
    "1035": { name: "Claude Sonnet 4.6", reasoning: "Thinking Enabled", family: "claude-sonnet" },
    "1026": { name: "Claude Opus 4.6", reasoning: "Thinking Enabled", family: "claude-opus" },
    "1050": { name: "Gemini Flash Lite", reasoning: "Autonomous Subagent", family: "gemini-flash-lite" },
    "1322": { name: "Gemini Fast Agent Assistant", reasoning: "Fast Assistant", family: "gemini-flash" },
    "1317": { name: "Gemini Flash Lite (Legacy)", reasoning: "Legacy Subagent", family: "gemini-flash-lite" },
    "1132": { name: "Gemini Fast Agent (Legacy)", reasoning: "Legacy Subagent", family: "gemini-flash" },
    "1301": { name: "Gemini Experimental Agent", reasoning: "Experimental Agent", family: "gemini-flash" },
    "1020": { name: "Gemini Search Agent", reasoning: "Grounding / Search", family: "gemini-flash" },
    "342": { name: "GPT-OSS 120B", reasoning: "Medium Reasoning", family: "gpt-oss" }
  };

  function resolveModelDisplay(mid) {
    const pm = pricingModels[mid] || {};
    const tax = MODEL_TAXONOMY[mid] || {};
    let rawName = pm.name || tax.name || `Model ${mid}`;
    let reasoning = tax.reasoning || "";

    if (!reasoning) {
      if (rawName.includes("(High)")) reasoning = "High Reasoning";
      else if (rawName.includes("(Medium)")) reasoning = "Medium Reasoning";
      else if (rawName.includes("(Low)")) reasoning = "Low Reasoning";
      else if (rawName.includes("(Thinking)")) reasoning = "Thinking Enabled";
      else if (rawName.includes("(Subagent)")) reasoning = "Autonomous Subagent";
    }

    let cleanName = rawName.replace(/\s*\((High|Medium|Low|Thinking|Subagent|Legacy)\)\s*/gi, "").trim();
    const baseRates = pm.rates_per_million || {
      prompt_uncached: 0.75,
      prompt_cached: 0.075,
      candidate_output: 3.75
    };

    return {
      name: cleanName || `Model ${mid}`,
      reasoning: reasoning,
      rates: baseRates
    };
  }

  function getModelSortRank(mid) {
    const explicitRanks = {
      "1318": 10, // Gemini 3.8 Flash (High)
      "1319": 11, // Gemini 3.8 Flash (Medium)
      "1320": 12, // Gemini 3.8 Flash (Low)
      "1298": 20, // Gemini 3.7 Flash (High)
      "1299": 21, // Gemini 3.7 Flash (Medium)
      "1300": 22, // Gemini 3.7 Flash (Low)
      "1071": 30, // Gemini 3.6 Flash (High)
      "1072": 31, // Gemini 3.6 Flash (Medium)
      "1073": 32, // Gemini 3.6 Flash (Low)
      "1016": 40, // Gemini 3.1 Pro (High)
      "1036": 41, // Gemini 3.1 Pro (Low)
      "1050": 50, // Gemini Flash Lite (Subagent)
      "1322": 51, // Gemini Fast Agent Assistant
      "1020": 52, // Gemini Search Agent
      "1301": 53, // Gemini Experimental Agent
      "1317": 54, // Gemini Flash Lite Legacy
      "1132": 55, // Gemini Fast Agent Legacy
      "1035": 80, // Claude Sonnet 4.6 (Thinking)
      "1026": 81, // Claude Opus 4.6 (Thinking)
      "342": 90   // GPT-OSS 120B (Medium)
    };
    if (explicitRanks[mid] !== undefined) return explicitRanks[mid];
    const info = resolveModelDisplay(mid);
    const n = (info.name + " " + info.reasoning).toLowerCase();
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

  if (rateTbody) {
    const rows = [];
    const allModelIds = Array.from(new Set([
      ...Object.keys(rateHistory),
      ...Object.keys(availability),
      ...Object.keys(MODEL_TAXONOMY),
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
      const avail = availability[mid] || { status: "ga" };
      const statusBadge = avail.status === "ga" ? '<span class="badge green">GA</span>'
        : (avail.status === "preview" ? '<span class="badge blue">Preview</span>'
        : (avail.status === "sunset" ? '<span class="badge red">Sunset</span>'
        : `<span class="badge">${escapeHtml(avail.status || "GA")}</span>`));

      const info = resolveModelDisplay(mid);
      const reasoningBadge = info.reasoning ? `<span class="badge purple" style="font-size: 0.6875rem; margin-top: 3px; display: inline-flex; align-items: center; gap: 3px;">🧠 ${escapeHtml(info.reasoning)}</span>` : '';

      const revisions = rateHistory[mid];
      if (revisions && revisions.length > 0) {
        revisions.forEach((rev, idx) => {
          const r = rev.rates_per_million || info.rates;
          const isHistorical = !!(rev.valid_to && new Date(rev.valid_to).getTime() < Date.now());
          const intervalText = `${rev.valid_from ? formatUkDate(rev.valid_from) : 'Start'} → ${rev.valid_to ? formatUkDate(rev.valid_to) : 'Present'}`;
          const eraBadge = isHistorical
            ? '<span class="badge" style="background: rgba(148, 163, 184, 0.15); color: var(--text-muted); font-size: 0.6875rem; margin-left: 6px; border: 1px solid rgba(148, 163, 184, 0.3);">Former Rate</span>'
            : '<span class="badge green" style="font-size: 0.6875rem; margin-left: 6px;">Active Current</span>';
          const revisionSub = revisions.length > 1
            ? `<div style="font-size: 0.6875rem; color: var(--text-muted); margin-top: 3px; font-weight: 500;">${isHistorical ? '⏳ Historical Revision' : '⚡ Current Active Revision'}</div>`
            : '';
          const rowStyle = isHistorical
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
              <td style="padding: 6px 8px; font-family: monospace;">
                <span>${escapeHtml(intervalText)}</span>
                ${eraBadge}
              </td>
              <td style="padding: 6px 8px; font-family: monospace;">$${(r.prompt_uncached || 0).toFixed(2)}</td>
              <td style="padding: 6px 8px; font-family: monospace;">$${(r.prompt_cached || 0).toFixed(3)}</td>
              <td style="padding: 6px 8px; font-family: monospace;">$${(r.candidate_output || 0).toFixed(2)}</td>
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
            <td style="padding: 6px 8px; font-family: monospace;">
              <span>Standard (Current)</span>
              <span class="badge green" style="font-size: 0.6875rem; margin-left: 6px;">Active Current</span>
            </td>
            <td style="padding: 6px 8px; font-family: monospace;">$${(r.prompt_uncached || 0).toFixed(2)}</td>
            <td style="padding: 6px 8px; font-family: monospace;">$${(r.prompt_cached || 0).toFixed(3)}</td>
            <td style="padding: 6px 8px; font-family: monospace;">$${(r.candidate_output || 0).toFixed(2)}</td>
          </tr>
        `);
      }
    });
    rateTbody.innerHTML = rows.join("");
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

  const presets = {
    free: {
      tier: "free",
      name: "Free Tier (Personal Google Account)",
      monthly_price_gbp: 0.00,
      monthly_price_usd: 0.00,
      renewal_day: 1,
      quota_limits: {
        burst_5h_tokens: 40000000,
        gemini_5h_capacity_usd: 5.00,
        gemini_weekly_capacity_usd: 25.00,
        claude_5h_capacity_usd: 0.00,
        claude_weekly_capacity_usd: 0.00
      }
    },
    plus_2tb: {
      tier: "plus_2tb",
      name: "Google AI Plus (2 TB)",
      monthly_price_gbp: 7.99,
      monthly_price_usd: 9.99,
      renewal_day: 24,
      quota_limits: {
        burst_5h_tokens: 80000000,
        gemini_5h_capacity_usd: 10.00,
        gemini_weekly_capacity_usd: 65.00,
        claude_5h_capacity_usd: 0.00,
        claude_weekly_capacity_usd: 0.00
      }
    },
    pro: {
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
    },
    pro_5tb: {
      tier: "pro_5tb",
      name: "Google AI Pro (5 TB)",
      monthly_price_gbp: 29.99,
      monthly_price_usd: 34.99,
      renewal_day: 24,
      quota_limits: {
        burst_5h_tokens: 168000000,
        gemini_5h_capacity_usd: 20.00,
        gemini_weekly_capacity_usd: 129.00,
        claude_5h_capacity_usd: 10.00,
        claude_weekly_capacity_usd: 35.00
      }
    },
    pro_10tb: {
      tier: "pro_10tb",
      name: "Google AI Pro (10 TB)",
      monthly_price_gbp: 39.99,
      monthly_price_usd: 49.99,
      renewal_day: 24,
      quota_limits: {
        burst_5h_tokens: 168000000,
        gemini_5h_capacity_usd: 20.00,
        gemini_weekly_capacity_usd: 129.00,
        claude_5h_capacity_usd: 10.00,
        claude_weekly_capacity_usd: 35.00
      }
    },
    ultra_5x: {
      tier: "ultra_5x",
      name: "Google AI Ultra (20 TB - 5x AI Usage)",
      monthly_price_gbp: 79.99,
      monthly_price_usd: 99.99,
      renewal_day: 13,
      quota_limits: {
        burst_5h_tokens: 840000000,
        gemini_5h_capacity_usd: 100.00,
        gemini_weekly_capacity_usd: 645.00,
        claude_5h_capacity_usd: 50.00,
        claude_weekly_capacity_usd: 175.00
      }
    },
    enterprise_5x: {
      tier: "enterprise_5x",
      name: "Google AI Ultra (20 TB - 5x AI Usage)",
      monthly_price_gbp: 79.99,
      monthly_price_usd: 99.99,
      renewal_day: 13,
      quota_limits: {
        burst_5h_tokens: 840000000,
        gemini_5h_capacity_usd: 100.00,
        gemini_weekly_capacity_usd: 645.00,
        claude_5h_capacity_usd: 50.00,
        claude_weekly_capacity_usd: 175.00
      }
    },
    ultra_20x: {
      tier: "ultra_20x",
      name: "Google AI Ultra (30 TB - 20x AI Usage)",
      monthly_price_gbp: 189.99,
      monthly_price_usd: 239.99,
      renewal_day: 24,
      quota_limits: {
        burst_5h_tokens: 3360000000,
        gemini_5h_capacity_usd: 400.00,
        gemini_weekly_capacity_usd: 2580.00,
        claude_5h_capacity_usd: 200.00,
        claude_weekly_capacity_usd: 700.00
      }
    },
    ultra_10x: {
      tier: "ultra_10x",
      name: "Google AI Ultra Max (10x Capacity)",
      monthly_price_gbp: 99.99,
      monthly_price_usd: 119.99,
      renewal_day: 24,
      quota_limits: {
        burst_5h_tokens: 1680000000,
        gemini_5h_capacity_usd: 200.00,
        gemini_weekly_capacity_usd: 1290.00,
        claude_5h_capacity_usd: 100.00,
        claude_weekly_capacity_usd: 350.00
      }
    },
    custom: {
      tier: "custom",
      name: "Custom Capacity Plan",
      monthly_price_gbp: 29.99,
      monthly_price_usd: 34.99,
      renewal_day: 1,
      quota_limits: {
        burst_5h_tokens: 250000000,
        gemini_5h_capacity_usd: 30.00,
        gemini_weekly_capacity_usd: 200.00,
        claude_5h_capacity_usd: 20.00,
        claude_weekly_capacity_usd: 60.00
      }
    }
  };

  let chosen = presets[tierKey] || presets.pro;
  if (tierKey === "custom") {
    const cGbp = parseFloat(document.getElementById("custom-fee-gbp")?.value || "0");
    const cUsd = parseFloat(document.getElementById("custom-fee-usd")?.value || "0");
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

/* =====================================================================
   WHAT-IF WORKLOAD SIMULATOR & STRESS PLANNER
   ===================================================================== */
const ARCHETYPE_PRESETS = {
  deep_refactor_swarm: {
    name: "Deep Refactor Swarm",
    model_id: "1016",
    turn_count: 40,
    prompt_tokens: 120000,
    cache_hit_ratio_pct: 88,
    thinking_tokens: 8000,
    answer_tokens: 1500,
    pace_minutes: 2.5,
    description: "Multi-agent deep architecture refactor using Gemini 3.1 Pro High reasoning."
  },
  codebase_audit: {
    name: "Codebase Audit & Security Scan",
    model_id: "1318",
    turn_count: 60,
    prompt_tokens: 200000,
    cache_hit_ratio_pct: 94,
    thinking_tokens: 2500,
    answer_tokens: 1000,
    pace_minutes: 1.5,
    description: "High-context whole-codebase scan with deep prompt caching on Gemini 3.8 Flash High."
  },
  rapid_prototyping_burst: {
    name: "Rapid Prototyping Burst",
    model_id: "1319",
    turn_count: 25,
    prompt_tokens: 45000,
    cache_hit_ratio_pct: 75,
    thinking_tokens: 1500,
    answer_tokens: 800,
    pace_minutes: 1.0,
    description: "Interactive fast-iteration development cycle with Gemini 3.8 Flash Medium."
  },
  claude_opus_deep_dive: {
    name: "Claude Opus 4.6 Stress Test",
    model_id: "1026",
    turn_count: 35,
    prompt_tokens: 95000,
    cache_hit_ratio_pct: 92,
    thinking_tokens: 6000,
    answer_tokens: 1200,
    pace_minutes: 2.0,
    description: "Tests Claude rate limits and the strict 30-95 turn boundary (Empirical Limit)."
  },
  subagent_fleet: {
    name: "Subagent Fleet (Lite/Fast)",
    model_id: "1050",
    turn_count: 100,
    prompt_tokens: 30000,
    cache_hit_ratio_pct: 85,
    thinking_tokens: 500,
    answer_tokens: 600,
    pace_minutes: 0.5,
    description: "Parallel background subagent workers executing mechanical tasks on Flash Lite."
  }
};

const SIM_MODEL_RATES = {
  "1318": { name: "Gemini 3.8 Flash (High)", track: "gemini", uncached: 0.75, cached: 0.075, output: 3.75, credits_per_turn: 2.501672 },
  "1319": { name: "Gemini 3.8 Flash (Medium)", track: "gemini", uncached: 0.75, cached: 0.075, output: 3.75, credits_per_turn: 2.5 },
  "1016": { name: "Gemini 3.1 Pro (High)", track: "gemini", uncached: 2.00, cached: 0.20, output: 12.00, credits_per_turn: 2.5 },
  "1036": { name: "Gemini 3.1 Pro (Low)", track: "gemini", uncached: 2.00, cached: 0.20, output: 12.00, credits_per_turn: 2.5 },
  "1050": { name: "Gemini Flash Lite", track: "gemini", uncached: 0.25, cached: 0.025, output: 1.50, credits_per_turn: 1.0 },
  "1298": { name: "Gemini 3.7 Flash (High)", track: "gemini", uncached: 0.75, cached: 0.075, output: 3.75, credits_per_turn: 2.5 },
  "1026": { name: "Claude Opus 4.6 Thinking", track: "claude_gpt", uncached: 15.00, cached: 1.50, output: 75.00, credits_per_turn: 0.0 },
  "1035": { name: "Claude Sonnet 4.6 Thinking", track: "claude_gpt", uncached: 3.00, cached: 0.30, output: 15.00, credits_per_turn: 0.0 },
  "342": { name: "GPT-OSS 120B (Medium)", track: "claude_gpt", uncached: 0.60, cached: 0.06, output: 2.40, credits_per_turn: 0.0 }
};

const SIM_PLAN_CAPACITIES = {
  plus_2tb: {
    name: "Google AI Plus (2 TB)",
    multiplier: 0.5,
    gemini_5h: 10.00,
    gemini_weekly: 65.00,
    claude_5h: 0.00,
    claude_weekly: 0.00
  },
  pro: {
    name: "Google AI Pro (2 TB / 5 TB / 10 TB)",
    multiplier: 1.0,
    gemini_5h: 20.00,
    gemini_weekly: 129.00,
    claude_5h: 10.00,
    claude_weekly: 35.00
  },
  ultra_5x: {
    name: "Google AI Ultra (20 TB - 5x AI Usage)",
    multiplier: 5.0,
    gemini_5h: 100.00,
    gemini_weekly: 645.00,
    claude_5h: 50.00,
    claude_weekly: 175.00
  },
  enterprise_5x: {
    name: "Google AI Ultra (20 TB - 5x AI Usage)",
    multiplier: 5.0,
    gemini_5h: 100.00,
    gemini_weekly: 645.00,
    claude_5h: 50.00,
    claude_weekly: 175.00
  },
  ultra_20x: {
    name: "Google AI Ultra (30 TB - 20x AI Usage)",
    multiplier: 20.0,
    gemini_5h: 400.00,
    gemini_weekly: 2580.00,
    claude_5h: 200.00,
    claude_weekly: 700.00
  },
  ultra_10x: {
    name: "Google AI Ultra Max (10x Quota)",
    multiplier: 10.0,
    gemini_5h: 200.00,
    gemini_weekly: 1290.00,
    claude_5h: 100.00,
    claude_weekly: 350.00
  }
};

function selectArchetypePreset(archetypeId) {
  document.querySelectorAll(".sim-archetype-card").forEach(el => {
    if (el.getAttribute("data-archetype") === archetypeId) {
      el.classList.add("active");
    } else {
      el.classList.remove("active");
    }
  });

  const selectEl = document.getElementById("sim-archetype-select");
  if (selectEl) selectEl.value = archetypeId;

  if (archetypeId === "custom") {
    runSimulation();
    return;
  }

  const preset = ARCHETYPE_PRESETS[archetypeId];
  if (!preset) return;

  const mSel = document.getElementById("sim-model-select");
  if (mSel) mSel.value = preset.model_id;

  const tSl = document.getElementById("sim-turns-slider");
  if (tSl) tSl.value = preset.turn_count;

  const pSl = document.getElementById("sim-prompt-slider");
  if (pSl) pSl.value = preset.prompt_tokens;

  const cSl = document.getElementById("sim-cache-slider");
  if (cSl) cSl.value = preset.cache_hit_ratio_pct;

  const thSl = document.getElementById("sim-thinking-slider");
  if (thSl) thSl.value = preset.thinking_tokens;

  const oSl = document.getElementById("sim-output-slider");
  if (oSl) oSl.value = preset.answer_tokens;

  const pcSl = document.getElementById("sim-pace-slider");
  if (pcSl) pcSl.value = preset.pace_minutes;

  runSimulation();
}

function onArchetypeSelectChange(val) {
  selectArchetypePreset(val);
}

function onSimulatorInputChange() {
  // Check if sliders drifted from active preset
  const currentModel = document.getElementById("sim-model-select") ? document.getElementById("sim-model-select").value : "";
  const activeCard = document.querySelector(".sim-archetype-card.active");
  const activeArch = activeCard ? activeCard.getAttribute("data-archetype") : null;
  if (activeArch && activeArch !== "custom") {
    const p = ARCHETYPE_PRESETS[activeArch];
    if (p) {
      const tVal = parseInt(document.getElementById("sim-turns-slider").value, 10);
      const pVal = parseInt(document.getElementById("sim-prompt-slider").value, 10);
      const cVal = parseInt(document.getElementById("sim-cache-slider").value, 10);
      const thVal = parseInt(document.getElementById("sim-thinking-slider").value, 10);
      const oVal = parseInt(document.getElementById("sim-output-slider").value, 10);
      if (currentModel !== p.model_id || tVal !== p.turn_count || pVal !== p.prompt_tokens ||
          cVal !== p.cache_hit_ratio_pct || thVal !== p.thinking_tokens || oVal !== p.answer_tokens) {
        document.querySelectorAll(".sim-archetype-card").forEach(el => {
          if (el.getAttribute("data-archetype") === "custom") el.classList.add("active");
          else el.classList.remove("active");
        });
        const sel = document.getElementById("sim-archetype-select");
        if (sel) sel.value = "custom";
      }
    }
  }

  runSimulation();
}

function runSimulation() {
  const modelSelect = document.getElementById("sim-model-select");
  const planSelect = document.getElementById("sim-plan-select");
  const baselineSelect = document.getElementById("sim-baseline-select");
  const turnsSlider = document.getElementById("sim-turns-slider");
  const promptSlider = document.getElementById("sim-prompt-slider");
  const cacheSlider = document.getElementById("sim-cache-slider");
  const thinkingSlider = document.getElementById("sim-thinking-slider");
  const outputSlider = document.getElementById("sim-output-slider");
  const paceSlider = document.getElementById("sim-pace-slider");

  if (!modelSelect || !turnsSlider) return;

  const modelId = modelSelect.value;
  const planTier = planSelect ? planSelect.value : "pro";
  const baselineMode = baselineSelect ? baselineSelect.value : "live";

  const turnCount = parseInt(turnsSlider.value, 10) || 1;
  const promptTokens = parseInt(promptSlider.value, 10) || 50000;
  const cachePct = parseInt(cacheSlider.value, 10) || 80;
  const thinkingTokens = parseInt(thinkingSlider.value, 10) || 0;
  const answerTokens = parseInt(outputSlider.value, 10) || 1000;
  const paceMinutes = parseFloat(paceSlider.value) || 2.0;

  // Update slider readout spans
  const turnsVal = document.getElementById("sim-turns-val");
  if (turnsVal) turnsVal.textContent = `${turnCount} turns`;
  const promptVal = document.getElementById("sim-prompt-val");
  if (promptVal) promptVal.textContent = `${promptTokens.toLocaleString()} tokens`;
  const cacheVal = document.getElementById("sim-cache-val");
  if (cacheVal) cacheVal.textContent = `${cachePct}%`;
  const thinkingVal = document.getElementById("sim-thinking-val");
  if (thinkingVal) thinkingVal.textContent = `${thinkingTokens.toLocaleString()} tokens`;
  const outputVal = document.getElementById("sim-output-val");
  if (outputVal) outputVal.textContent = `${answerTokens.toLocaleString()} tokens`;
  const paceVal = document.getElementById("sim-pace-val");
  if (paceVal) paceVal.textContent = `${paceMinutes.toFixed(1)} min/turn`;

  // Track badge update
  const rates = SIM_MODEL_RATES[modelId] || SIM_MODEL_RATES["1318"];
  const trackBadge = document.getElementById("sim-track-badge");
  if (trackBadge) {
    if (rates.track === "gemini") {
      trackBadge.textContent = "Track 1: Gemini";
      trackBadge.style.color = "var(--accent-blue)";
      trackBadge.style.borderColor = "var(--accent-blue)";
    } else {
      trackBadge.textContent = "Track 2: Claude/GPT (Zero Spillover)";
      trackBadge.style.color = "var(--accent-amber)";
      trackBadge.style.borderColor = "var(--accent-amber)";
    }
  }

  // Plan badge update
  const planBadge = document.getElementById("sim-plan-badge");
  const plan = SIM_PLAN_CAPACITIES[planTier] || SIM_PLAN_CAPACITIES["pro"];
  if (planBadge) {
    planBadge.textContent = `${plan.multiplier}x Capacity`;
  }

  // Calculations
  const uncached = Math.round(promptTokens * (1.0 - cachePct / 100.0));
  const cached = promptTokens - uncached;
  const totalOutput = thinkingTokens + answerTokens;
  const processedPerTurn = promptTokens + totalOutput;

  const turnCostUsd = (uncached * rates.uncached + cached * rates.cached + totalOutput * rates.output) / 1000000.0;
  const totalCostUsd = turnCostUsd * turnCount;

  const fxRate = (globalDashboardData && globalDashboardData.currency && globalDashboardData.currency.usd_to_gbp_fx_rate) || 0.79;
  const isGbp = (activeCurrency === "GBP");

  // Quota capacity lookup
  const promoMult = (rates.track === "gemini" && globalDashboardData && globalDashboardData.summary && globalDashboardData.summary.gemini_capacity_multiplier) || 1.0;
  const burstCapUsd = (rates.track === "gemini" ? plan.gemini_5h : plan.claude_5h) * promoMult;
  const weeklyCapUsd = (rates.track === "gemini" ? plan.gemini_weekly : plan.claude_weekly) * promoMult;

  // Starting live usage
  let starting5hUsd = 0.0;
  let startingWeeklyUsd = 0.0;
  let bankCreditsRem = (globalDashboardData && globalDashboardData.summary && globalDashboardData.summary.credits_remaining) || 0;

  if (baselineMode === "live" && globalDashboardData && globalDashboardData.quotas && globalDashboardData.quotas.providers) {
    const provData = globalDashboardData.quotas.providers[rates.track];
    if (provData) {
      if (provData.five_hour) starting5hUsd = provData.five_hour.imputed_value_usd || 0.0;
      if (provData.weekly_cycle) startingWeeklyUsd = provData.weekly_cycle.imputed_value_usd || 0.0;
    }
  }

  // Turn trajectory & exhaustion detection
  let currentLoad5h = starting5hUsd;
  let exhaustionTurn = null;
  const trajectoryPoints = [
    { turn: 0, loadUsd: starting5hUsd, usedPct: (starting5hUsd / burstCapUsd) * 100.0 }
  ];

  for (let t = 1; t <= turnCount; t++) {
    currentLoad5h += turnCostUsd;
    const usedPct = (currentLoad5h / burstCapUsd) * 100.0;
    if (currentLoad5h > burstCapUsd && exhaustionTurn === null) {
      exhaustionTurn = t;
    }
    trajectoryPoints.push({
      turn: t,
      loadUsd: currentLoad5h,
      usedPct: usedPct,
      remainingPct: Math.max(0, 100.0 - usedPct)
    });
  }

  const final5hUsd = currentLoad5h;
  const final5hPct = (final5hUsd / burstCapUsd) * 100.0;
  const remaining5hPct = Math.max(0, 100.0 - final5hPct);
  const burstExhausted = final5hUsd > burstCapUsd;
  const overBurstUsd = burstExhausted ? (final5hUsd - burstCapUsd) : 0.0;
  const overTurns = exhaustionTurn !== null ? (turnCount - exhaustionTurn + 1) : 0;

  const weeklyLoadAddedPct = (totalCostUsd / weeklyCapUsd) * 100.0;
  const finalWeeklyUsd = startingWeeklyUsd + totalCostUsd;
  const finalWeeklyPct = (finalWeeklyUsd / weeklyCapUsd) * 100.0;
  const weeklyExhausted = finalWeeklyUsd > weeklyCapUsd;

  // Credit spillover & 429 dynamics
  let creditSpilloverApplicable = (rates.track === "gemini");
  let creditsDebited = 0;
  let creditCostGbp = 0.0;
  let creditCostUsd = 0.0;
  let hard429Block = false;

  if (creditSpilloverApplicable) {
    if (burstExhausted) {
      creditsDebited = Math.round(overTurns * rates.credits_per_turn);
      creditCostGbp = creditsDebited * 0.009596;
      creditCostUsd = creditsDebited * 0.01;
    }
  } else {
    if (burstExhausted || weeklyExhausted) {
      hard429Block = true;
    }
  }

  // Determine Status & Risk
  let statusKey = "safe";
  let statusLabel = "Safe Zone";
  let riskLevel = "SAFE";
  let badgeClass = "badge green";
  let heroBorderColor = "var(--accent-green)";
  let fillBg = "var(--accent-green)";
  let recommendation = "";

  if (weeklyExhausted) {
    statusKey = "lockout";
    statusLabel = "Weekly Quota Lockout";
    riskLevel = "CRITICAL_429";
    badgeClass = "badge red";
    heroBorderColor = "var(--accent-red)";
    fillBg = "var(--accent-red)";
    const quotas = (globalDashboardData && globalDashboardData.quotas) || {};
    const resetDay = (quotas.weekly_cycle && quotas.weekly_cycle.reset_day_name) || "weekly";
    recommendation = `CRITICAL: Weekly quota limit of $${weeklyCapUsd.toFixed(2)} is exhausted. Upstream server will block execution until ${resetDay} weekly refresh. Upgrade to Google AI Ultra (5x capacity) to unlock headroom.`;
  } else if (rates.track === "claude_gpt" && burstExhausted) {
    statusKey = "lockout";
    statusLabel = "HTTP 429 Hard Lockout";
    riskLevel = "CRITICAL_429";
    badgeClass = "badge red";
    heroBorderColor = "var(--accent-red)";
    fillBg = "var(--accent-red)";
    recommendation = `CRITICAL: Claude burst limit of $${burstCapUsd.toFixed(2)} exceeded at turn ${exhaustionTurn} with ZERO credit spillover (Provider Policy). Immediate HTTP 429 rate limit lock! Switch to Gemini Flash/Pro or upgrade to Google AI Ultra (5x capacity).`;
  } else if (burstExhausted) {
    statusKey = "cooldown";
    statusLabel = "Burst Cooldown";
    riskLevel = "HIGH_EXHAUSTION";
    badgeClass = "badge amber";
    heroBorderColor = "var(--accent-amber)";
    fillBg = "var(--accent-amber)";
    recommendation = `5-hour burst capacity exceeded by $${overBurstUsd.toFixed(2)} at turn ${exhaustionTurn}. Spills over to Google One AI Credit Bank: ${creditsDebited.toLocaleString()} credits (${isGbp ? '£' + creditCostGbp.toFixed(2) : '$' + creditCostUsd.toFixed(2)}) will be debited.`;
  } else if (remaining5hPct < 50.0) {
    statusKey = "caution";
    statusLabel = "Caution (Heavy Load)";
    riskLevel = "MODERATE";
    badgeClass = "badge amber";
    heroBorderColor = "var(--accent-amber)";
    fillBg = "var(--accent-amber)";
    recommendation = `Headroom in Caution Zone (${remaining5hPct.toFixed(1)}% remaining). Session will complete within quota, but subsequent runs within the 5h window risk triggering cooldown.`;
  } else {
    statusKey = "safe";
    statusLabel = "Safe Zone";
    riskLevel = "SAFE";
    badgeClass = "badge green";
    heroBorderColor = "var(--accent-green)";
    fillBg = "var(--accent-green)";
    recommendation = `Safe to execute: Planned workload comfortably fits within active 5-hour rolling capacity with zero credit deduction or throttling risk.`;
  }

  // Update Hero Card
  const heroEl = document.getElementById("sim-status-hero");
  if (heroEl) heroEl.style.borderLeftColor = heroBorderColor;

  const statusBadge = document.getElementById("sim-status-badge");
  if (statusBadge) {
    statusBadge.className = badgeClass;
    statusBadge.textContent = statusLabel;
  }

  const riskBadge = document.getElementById("sim-risk-badge");
  if (riskBadge) {
    riskBadge.textContent = riskLevel.replace("_", " ");
  }

  const gaugePctEl = document.getElementById("sim-gauge-pct");
  if (gaugePctEl) {
    if (burstExhausted) {
      gaugePctEl.textContent = `Exceeded +${(final5hPct - 100.0).toFixed(1)}%`;
      gaugePctEl.style.color = "var(--accent-red)";
    } else {
      gaugePctEl.textContent = `${remaining5hPct.toFixed(1)}% Available`;
      gaugePctEl.style.color = "var(--text-main)";
    }
  }

  const gaugeFill = document.getElementById("sim-gauge-fill");
  if (gaugeFill) {
    gaugeFill.style.width = `${Math.min(100.0, final5hPct)}%`;
    gaugeFill.style.background = fillBg;
  }

  const recEl = document.getElementById("sim-recommendation");
  if (recEl) recEl.textContent = recommendation;

  // Update 4 KPI Cards
  const burstValEl = document.getElementById("sim-kpi-burst-val");
  const burstSubEl = document.getElementById("sim-kpi-burst-sub");
  if (burstValEl) burstValEl.textContent = `$${final5hUsd.toFixed(2)} / $${burstCapUsd.toFixed(2)}`;
  if (burstSubEl) {
    burstSubEl.textContent = burstExhausted
      ? `Exhaustion at turn ${exhaustionTurn} • ${final5hPct.toFixed(1)}%`
      : `${final5hPct.toFixed(1)}% consumed • ${remaining5hPct.toFixed(1)}% free`;
  }

  const weeklyValEl = document.getElementById("sim-kpi-weekly-val");
  const weeklySubEl = document.getElementById("sim-kpi-weekly-sub");
  if (weeklyValEl) weeklyValEl.textContent = `+${weeklyLoadAddedPct.toFixed(1)}% load`;
  if (weeklySubEl) weeklySubEl.textContent = `$${totalCostUsd.toFixed(2)} added to $${weeklyCapUsd.toFixed(2)} cap (${finalWeeklyPct.toFixed(1)}% total)`;

  const costValEl = document.getElementById("sim-kpi-cost-val");
  const costSubEl = document.getElementById("sim-kpi-cost-sub");
  if (costValEl) costValEl.textContent = isGbp ? `£${(totalCostUsd * fxRate).toFixed(2)}` : `$${totalCostUsd.toFixed(2)}`;
  if (costSubEl) {
    const altCurr = isGbp ? `$${totalCostUsd.toFixed(2)}` : `£${(totalCostUsd * fxRate).toFixed(2)}`;
    costSubEl.textContent = `${altCurr} API equiv (${turnCount} turns)`;
  }

  const riskValEl = document.getElementById("sim-kpi-risk-val");
  const riskSubEl = document.getElementById("sim-kpi-risk-sub");
  if (riskValEl) {
    if (hard429Block) {
      riskValEl.textContent = "CRITICAL 429";
      riskValEl.style.color = "var(--accent-red)";
    } else if (creditsDebited > 0) {
      riskValEl.textContent = `${creditsDebited.toLocaleString()} credits`;
      riskValEl.style.color = "var(--accent-amber)";
    } else {
      riskValEl.textContent = "0 Credits";
      riskValEl.style.color = "var(--accent-green)";
    }
  }
  if (riskSubEl) {
    if (hard429Block) {
      riskSubEl.textContent = "Hard rate limit lockout (Zero spillover)";
    } else if (creditsDebited > 0) {
      riskSubEl.textContent = `Estimated ${isGbp ? '£' + creditCostGbp.toFixed(2) : '$' + creditCostUsd.toFixed(2)} deduction`;
    } else {
      riskSubEl.textContent = "Zero out-of-pocket credit burn";
    }
  }

  // Render Trajectory SVG
  renderSimulationSvg(trajectoryPoints, burstCapUsd, exhaustionTurn);

  // Render Tier Sensitivity Comparison Table
  renderTierComparison(turnCostUsd, turnCount, rates, starting5hUsd);
}

function renderSimulationSvg(trajectory, burstCapUsd, exhaustionTurn) {
  const svg = document.getElementById("sim-trajectory-svg");
  if (!svg || trajectory.length === 0) return;

  const w = 500;
  const h = 160;
  const padLeft = 45;
  const padRight = 20;
  const padTop = 15;
  const padBottom = 25;

  const plotW = w - padLeft - padRight;
  const plotH = h - padTop - padBottom;

  const maxTurn = trajectory[trajectory.length - 1].turn || 1;
  const maxLoad = Math.max(burstCapUsd * 1.25, trajectory[trajectory.length - 1].loadUsd * 1.1);

  const getX = (t) => padLeft + (t / maxTurn) * plotW;
  const getY = (load) => padTop + plotH - (load / maxLoad) * plotH;

  const burstLimitY = getY(burstCapUsd);

  const points = trajectory.map(p => `${getX(p.turn).toFixed(1)},${getY(p.loadUsd).toFixed(1)}`).join(" ");

  const areaPath = `M ${getX(0)},${getY(trajectory[0].loadUsd)} ` +
    trajectory.map(p => `L ${getX(p.turn).toFixed(1)},${getY(p.loadUsd).toFixed(1)}`).join(" ") +
    ` L ${getX(maxTurn)},${padTop + plotH} L ${getX(0)},${padTop + plotH} Z`;

  let exhaustionMarker = "";
  if (exhaustionTurn !== null) {
    const pt = trajectory.find(p => p.turn === exhaustionTurn) || trajectory[trajectory.length - 1];
    const exX = getX(pt.turn);
    const exY = getY(pt.loadUsd);
    exhaustionMarker = `
      <circle cx="${exX.toFixed(1)}" cy="${exY.toFixed(1)}" r="5" fill="#ef4444" stroke="#fff" stroke-width="2"/>
      <text x="${Math.min(w - 70, exX + 8).toFixed(1)}" y="${Math.max(25, exY - 8).toFixed(1)}" fill="#ef4444" font-size="10" font-weight="700">
        Exhausted (T${exhaustionTurn})
      </text>
    `;
  }

  svg.innerHTML = `
    <defs>
      <linearGradient id="sim-grad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.3"/>
        <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.0"/>
      </linearGradient>
    </defs>

    <!-- Grid lines -->
    <line x1="${padLeft}" y1="${padTop + plotH}" x2="${w - padRight}" y2="${padTop + plotH}" stroke="var(--card-border)" stroke-width="1"/>
    <line x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${padTop + plotH}" stroke="var(--card-border)" stroke-width="1"/>

    <!-- 100% Burst Boundary -->
    <line x1="${padLeft}" y1="${burstLimitY.toFixed(1)}" x2="${w - padRight}" y2="${burstLimitY.toFixed(1)}" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="4,4"/>
    <text x="${w - padRight - 5}" y="${(burstLimitY - 4).toFixed(1)}" fill="#ef4444" font-size="9" text-anchor="end" font-weight="600">
      Burst Limit ($${burstCapUsd.toFixed(0)})
    </text>

    <!-- Area Fill -->
    <path d="${areaPath}" fill="url(#sim-grad)"/>

    <!-- Line -->
    <polyline fill="none" stroke="#2563eb" stroke-width="2.5" points="${points}"/>

    <!-- Start circle -->
    <circle cx="${getX(0).toFixed(1)}" cy="${getY(trajectory[0].loadUsd).toFixed(1)}" r="3.5" fill="#2563eb"/>

    <!-- End circle -->
    <circle cx="${getX(maxTurn).toFixed(1)}" cy="${getY(trajectory[trajectory.length - 1].loadUsd).toFixed(1)}" r="3.5" fill="#2563eb"/>

    <!-- Exhaustion marker if triggered -->
    ${exhaustionMarker}

    <!-- X Axis labels -->
    <text x="${padLeft}" y="${h - 6}" fill="var(--text-muted)" font-size="10">Turn 0</text>
    <text x="${(padLeft + plotW / 2).toFixed(1)}" y="${h - 6}" fill="var(--text-muted)" font-size="10" text-anchor="middle">Turn ${(maxTurn / 2).toFixed(0)}</text>
    <text x="${w - padRight}" y="${h - 6}" fill="var(--text-muted)" font-size="10" text-anchor="end">Turn ${maxTurn}</text>

    <!-- Y Axis labels -->
    <text x="${padLeft - 6}" y="${padTop + plotH}" fill="var(--text-muted)" font-size="9" text-anchor="end">$0</text>
    <text x="${padLeft - 6}" y="${burstLimitY.toFixed(1)}" fill="#ef4444" font-size="9" text-anchor="end">$${burstCapUsd.toFixed(0)}</text>
  `;
}

function renderTierComparison(turnCostUsd, turnCount, rates, starting5hUsd) {
  const tbody = document.getElementById("sim-tier-tbody");
  if (!tbody) return;

  const planTierSelect = document.getElementById("sim-plan-select");
  const currentSelectedTier = planTierSelect ? planTierSelect.value : "pro";
  const totalCostUsd = turnCostUsd * turnCount;
  const isGbp = (activeCurrency === "GBP");

  const tiers = [
    { id: "pro", name: "Google AI Pro (2 TB / 5 TB / 10 TB)", mult: 1.0, g5h: 20.00, c5h: 10.00 },
    { id: "ultra_5x", name: "Google AI Ultra (20 TB) 5x", mult: 5.0, g5h: 100.00, c5h: 50.00 },
    { id: "ultra_20x", name: "Google AI Ultra (30 TB) 20x", mult: 20.0, g5h: 400.00, c5h: 200.00 },
  ];

  const promoMult = (rates.track === "gemini" && globalDashboardData && globalDashboardData.summary && globalDashboardData.summary.gemini_capacity_multiplier) || 1.0;

  tbody.innerHTML = tiers.map(t => {
    const burstCap = (rates.track === "gemini" ? t.g5h : t.c5h) * promoMult;
    const finalLoad = starting5hUsd + totalCostUsd;
    const usedPct = (finalLoad / burstCap) * 100.0;
    const exhausted = finalLoad > burstCap;

    let exTurnStr = "Safe (No exhaustion)";
    let spilloverStr = "0 Credits (£0.00)";
    let statusBadge = '<span class="badge green">Safe</span>';

    if (exhausted) {
      let cur = starting5hUsd;
      let exT = null;
      for (let i = 1; i <= turnCount; i++) {
        cur += turnCostUsd;
        if (cur > burstCap) { exT = i; break; }
      }
      exTurnStr = exT ? `Turn ${exT}` : "Turn 1";

      if (rates.track === "gemini") {
        const overTurns = exT ? (turnCount - exT + 1) : turnCount;
        const credits = Math.round(overTurns * rates.credits_per_turn);
        const costGbp = credits * 0.009596;
        const costUsd = credits * 0.01;
        spilloverStr = `${credits.toLocaleString()} credits (${isGbp ? '£' + costGbp.toFixed(2) : '$' + costUsd.toFixed(2)})`;
        statusBadge = '<span class="badge amber">Cooldown</span>';
      } else {
        spilloverStr = '<strong style="color: var(--accent-red);">Zero Spillover (429 Block)</strong>';
        statusBadge = '<span class="badge red">429 Lockout</span>';
      }
    }

    const isCurrent = t.id === currentSelectedTier;
    const rowClass = isCurrent ? 'class="active-tier"' : '';
    const currentMarker = isCurrent ? ' <span class="code-pill">Selected</span>' : '';

    return `
      <tr ${rowClass}>
        <td><strong>${t.name}</strong>${currentMarker}</td>
        <td style="font-family: monospace;">$${burstCap.toFixed(2)}</td>
        <td style="font-family: monospace; ${exhausted ? 'color: var(--accent-red); font-weight: 700;' : ''}">${usedPct.toFixed(1)}%</td>
        <td>${statusBadge}</td>
        <td>${exTurnStr}</td>
        <td>${spilloverStr}</td>
      </tr>
    `;
  }).join("");
}

function initSimulator() {
  runSimulation();
}

/* ==========================================================================
   SUBAGENT SWARM LINEAGE EXPLORER & TOOL ANALYTICS (ADR-037 / M24)
   ========================================================================== */

let activeSwarmList = [];
let selectedSwarmId = null;
let activeSwarmProjectFilter = "all";
let activeSwarmSortOrder = "recent";

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
      kpiOverage.textContent = "100% Pro plan • £0.00 actual overage";
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
    const cacheHitClass = (s.cache_hit_pct >= 85) ? "green" : "blue";
    return `
      <div class="swarm-card ${activeClass}" id="swarm-card-${s.swarm_id.substring(0, 8)}" onclick="selectSwarmById('${s.swarm_id}')">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 4px;">
          <strong style="font-size: 0.875rem; color: var(--text-main); line-height: 1.3;">${escapeHtml(s.root_title || "Orchestrator Task")}</strong>
          <span class="badge-avoided" title="Imputed Developer API Value (Covered by subscription)">${avoidedStr} avoided</span>
        </div>
        <div style="display: flex; align-items: center; gap: 6px; font-size: 0.75rem; margin-bottom: 6px;">
          <span style="font-weight: 700; font-family: monospace; color: var(--text-main);">${formatNumber(s.total_swarm_tokens || 0)} toks</span>
          <span class="badge ${cacheHitClass}" style="font-size: 0.65rem; padding: 1px 5px;">${s.cache_hit_pct || 0}% cached</span>
          <span style="color: var(--text-muted); font-size: 0.72rem;">• ${formatNumber(s.tokens_per_turn || 0)}/t</span>
        </div>
        <div style="display: flex; gap: 6px; align-items: center; font-size: 0.72rem; color: var(--text-muted); flex-wrap: wrap;">
          <span class="badge" style="font-size: 0.65rem; padding: 1px 6px;">📁 ${escapeHtml(s.workspace_name || "Workspace")}</span>
          <span>🤖 ${s.subagents_count || 0} subagents</span>
          <span>⏱️ ${s.duration_formatted || "0s"}</span>
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

  const pill = document.getElementById("swarm-selected-pill");
  if (pill) pill.textContent = `Swarm ${swarm.swarm_id.substring(0, 8)}`;

  const titleEl = document.getElementById("swarm-detail-title");
  if (titleEl) titleEl.textContent = swarm.root_title || "Multi-Agent Swarm Orchestrator";

  const wsEl = document.getElementById("swarm-detail-ws");
  if (wsEl) {
    wsEl.textContent = `📁 ${swarm.workspace_name || "Workspace"}`;
    wsEl.onclick = () => jumpToProject(swarm.workspace_name);
  }

  const durEl = document.getElementById("swarm-detail-duration");
  if (durEl) durEl.textContent = `⏱️ Duration: ${swarm.duration_formatted || "0s"}`;

  const subEl = document.getElementById("swarm-detail-subagents");
  if (subEl) subEl.textContent = `🤖 ${swarm.subagents_count || 0} Subagents (${swarm.subagent_share_pct || 0}% share)`;

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
        <div class="ribbon-pill-value" style="color: var(--accent-blue);">${formatNumber(swarm.total_swarm_tokens)}</div>
        <div class="ribbon-pill-sub">${swarm.total_turns || 0} generation turns</div>
      </div>
      <div class="ribbon-pill">
        <div class="ribbon-pill-label">Prompt Cache Efficiency</div>
        <div class="ribbon-pill-value" style="color: var(--accent-green);">${swarm.cache_hit_pct || 0}%</div>
        <div class="ribbon-pill-sub">${formatNumber(swarm.total_cached_tokens || 0)} cached</div>
      </div>
      <div class="ribbon-pill">
        <div class="ribbon-pill-label">Reasoning / Thinking</div>
        <div class="ribbon-pill-value" style="color: #a855f7;">${formatNumber(swarm.total_thinking_tokens || 0)}</div>
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
      tierPills.push(`<span class="tier-pill tier-mechanical">⚙️ Tier 1 Mechanical: ${tb.mechanical.count} agent(s) (${formatNumber(tb.mechanical.tokens)} toks)</span>`);
    }
    if (tb.engineering && tb.engineering.count > 0) {
      tierPills.push(`<span class="tier-pill tier-engineering">⚡ Tier 2 Engineering: ${tb.engineering.count} agent(s) (${formatNumber(tb.engineering.tokens)} toks)</span>`);
    }
    if (tb.architecture && tb.architecture.count > 0) {
      tierPills.push(`<span class="tier-pill tier-architecture">🧠 Tier 3 Architecture: ${tb.architecture.count} agent(s) (${formatNumber(tb.architecture.tokens)} toks)</span>`);
    }
    if (tb.other && tb.other.count > 0) {
      tierPills.push(`<span class="tier-pill tier-other">🔹 Other: ${tb.other.count} agent(s) (${formatNumber(tb.other.tokens)} toks)</span>`);
    }
    tiersEl.innerHTML = tierPills.length > 0 ? tierPills.join("") : '<span style="font-size: 0.75rem; color: var(--text-muted);">Single-agent swarm</span>';
  }

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
  const children = nodes.filter(n => n !== rootNode);
  const childCount = children.length;

  const maxChildrenInRow = childCount <= 4 ? childCount : Math.ceil(childCount / 2);
  const minRequiredWidth = Math.max(760, maxChildrenInRow * 200 + 40);
  const width = Math.max(container.clientWidth || 760, minRequiredWidth);
  const height = childCount > 4 ? 490 : (childCount > 0 ? 370 : 220);

  // Layout positioning
  rootNode.x = width / 2;
  rootNode.y = 60;

  if (childCount <= 4) {
    const stepX = (width - 60) / Math.max(1, childCount);
    children.forEach((c, idx) => {
      c.x = 30 + (idx + 0.5) * stepX;
      c.y = 260;
    });
  } else {
    // 2-row layout for larger multi-agent swarms
    const half = Math.ceil(childCount / 2);
    const row1 = children.slice(0, half);
    const row2 = children.slice(half);

    const step1 = (width - 60) / row1.length;
    row1.forEach((c, idx) => {
      c.x = 30 + (idx + 0.5) * step1;
      c.y = 195;
    });

    const step2 = (width - 60) / row2.length;
    row2.forEach((c, idx) => {
      c.x = 30 + (idx + 0.5) * step2;
      c.y = 350;
    });
  }

  // Generate SVG Elements with high-visibility markers and Option B clean typography
  let svgHtml = `
    <svg class="swarm-dag-svg" viewBox="0 0 ${width} ${height}" style="width: 100%; height: ${height}px;">
      <defs>
        <marker id="arrow-orch" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#38bdf8" />
        </marker>
        <marker id="arrow-t1" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#22c55e" />
        </marker>
        <marker id="arrow-t2" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#0ea5e9" />
        </marker>
        <marker id="arrow-t3" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#a855f7" />
        </marker>
        <marker id="arrow-other" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#f59e0b" />
        </marker>
      </defs>
  `;

  // Draw Edges (High-visibility, dotted conduits with tier-matched colors and arrows)
  edges.forEach(edge => {
    const src = nodes.find(n => n.id === edge.source) || rootNode;
    const tgt = nodes.find(n => n.id === edge.target);
    if (src && tgt) {
      let edgeClass = "swarm-edge swarm-edge-orch";
      let markerUrl = "url(#arrow-orch)";
      if (tgt.tier === "mechanical") {
        edgeClass = "swarm-edge swarm-edge-t1";
        markerUrl = "url(#arrow-t1)";
      } else if (tgt.tier === "engineering") {
        edgeClass = "swarm-edge swarm-edge-t2";
        markerUrl = "url(#arrow-t2)";
      } else if (tgt.tier === "architecture") {
        edgeClass = "swarm-edge swarm-edge-t3";
        markerUrl = "url(#arrow-t3)";
      } else if (tgt.tier === "other") {
        edgeClass = "swarm-edge swarm-edge-other";
        markerUrl = "url(#arrow-other)";
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

  // Draw Nodes (Option B Clean Typography: Tokens & Cache Metrics inside each box, zero emojis)
  nodes.forEach(node => {
    let strokeColor = "#38bdf8";
    let bgColor = "rgba(56, 189, 248, 0.08)";
    let tierBadge = "ORCH";

    if (node.tier === "mechanical") {
      strokeColor = "#22c55e";
      bgColor = "rgba(34, 197, 94, 0.08)";
      tierBadge = "T1 LITE";
    } else if (node.tier === "engineering") {
      strokeColor = "#0ea5e9";
      bgColor = "rgba(14, 165, 233, 0.08)";
      tierBadge = "T2 FAST";
    } else if (node.tier === "architecture") {
      strokeColor = "#a855f7";
      bgColor = "rgba(168, 85, 247, 0.08)";
      tierBadge = "T3 PRO";
    } else if (node.tier === "other") {
      strokeColor = "#f59e0b";
      bgColor = "rgba(245, 158, 11, 0.08)";
      tierBadge = "CUSTOM";
    }

    if (node.is_root) {
      tierBadge = "ROOT";
      strokeColor = "#38bdf8";
      bgColor = "rgba(56, 189, 248, 0.12)";
    }

    const roleName = node.role || (node.is_root ? "Orchestrator Root" : "Specialist");
    const displayRole = roleName.length > 17 ? roleName.substring(0, 15) + "..." : roleName;

    const cacheHitPct = node.cache_hit_pct !== undefined ? node.cache_hit_pct : 0.0;
    const cachedToks = node.cached_tokens || 0;
    const inputToks = node.input_tokens || 0;
    const uncachedToks = Math.max(0, inputToks - cachedToks);
    const thinkingToks = node.thinking_tokens || 0;
    const avoidedCostStr = formatCurrency(node.cost_usd, node.cost_gbp, 2);

    // Dynamic cache color grading: >80% emerald, 50-80% sky blue, <50% amber
    let cacheColor = "#22c55e";
    let cacheSavedColor = "#86efac";
    if (cacheHitPct < 50) {
      cacheColor = "#f59e0b";
      cacheSavedColor = "#fcd34d";
    } else if (cacheHitPct < 80) {
      cacheColor = "#38bdf8";
      cacheSavedColor = "#93c5fd";
    }

    // Row 4: Thinking tokens if > 0, else uncached tokens
    let line4Left = "";
    if (thinkingToks > 0) {
      line4Left = `<text x="${node.x - 78}" y="${node.y + 30}" text-anchor="start" font-size="8.5" font-family="ui-monospace, monospace" font-weight="600" fill="#c084fc">${formatCompactNumber(thinkingToks)} thinking</text>`;
    } else {
      line4Left = `<text x="${node.x - 78}" y="${node.y + 30}" text-anchor="start" font-size="8.5" font-family="ui-monospace, monospace" fill="var(--text-muted)">${formatCompactNumber(uncachedToks)} uncached</text>`;
    }

    svgHtml += `
      <g class="swarm-node" onclick="inspectSwarmNode('${node.id}')" data-node-id="${node.id}">
        <!-- Node Box Card -->
        <rect x="${node.x - 90}" y="${node.y - 41}" width="180" height="82" rx="8"
              fill="${bgColor}" stroke="${strokeColor}" stroke-width="1.8"
              class="swarm-node-box" />

        <!-- Line 1: Role Title & Tier Pill -->
        <text x="${node.x - 78}" y="${node.y - 23}" text-anchor="start" font-size="10.5" font-weight="700" fill="var(--text-main)">
          ${escapeHtml(displayRole)}
        </text>
        <text x="${node.x + 78}" y="${node.y - 23}" text-anchor="end" font-size="8.5" font-weight="700" font-family="ui-monospace, monospace" fill="${strokeColor}">
          [${tierBadge}]
        </text>

        <!-- Divider Line -->
        <line x1="${node.x - 82}" y1="${node.y - 14}" x2="${node.x + 82}" y2="${node.y - 14}"
              stroke="${strokeColor}" stroke-opacity="0.25" stroke-width="1" />

        <!-- Line 2: Total Tokens & Turns -->
        <text x="${node.x - 78}" y="${node.y - 1}" text-anchor="start" font-size="9.5" font-family="ui-monospace, monospace" font-weight="600" fill="var(--text-main)">
          ${formatNumber(node.tokens_total || 0)} toks
        </text>
        <text x="${node.x + 78}" y="${node.y - 1}" text-anchor="end" font-size="8.5" font-family="ui-monospace, monospace" fill="var(--text-muted)">
          ${node.turn_count || 0} turns
        </text>

        <!-- Line 3: Cache Efficiency & Saved Tokens (Emerald Highlight) -->
        <text x="${node.x - 78}" y="${node.y + 15}" text-anchor="start" font-size="9.5" font-family="ui-monospace, monospace" font-weight="700" fill="${cacheColor}">
          ${cacheHitPct.toFixed(1)}% CACHED
        </text>
        <text x="${node.x + 78}" y="${node.y + 15}" text-anchor="end" font-size="8.5" font-family="ui-monospace, monospace" fill="${cacheSavedColor}">
          ${formatCompactNumber(cachedToks)} saved
        </text>

        <!-- Line 4: Reasoning / Uncached & Avoided Rate Card Value -->
        ${line4Left}
        <text x="${node.x + 78}" y="${node.y + 30}" text-anchor="end" font-size="8.5" font-family="ui-monospace, monospace" fill="var(--text-muted)">
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
  const costStr = isGbp ? `£${(node.cost_gbp || 0).toFixed(4)}` : `$${(node.cost_usd || 0).toFixed(4)}`;

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
          ${node.is_root ? '<span class="code-pill" style="font-size: 0.65rem; color: var(--accent-blue);">ORCHESTRATOR ROOT</span>' : ''}
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
        <div style="font-size: 0.875rem; font-weight: 700; font-family: monospace; color: #a855f7;">${formatNumber(thinkingToks)}</div>
        <div style="font-size: 0.7rem; color: var(--text-muted);">${formatNumber(answerToks)} answer toks</div>
      </div>
      <div>
        <div style="font-size: 0.68rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Uncached Prompt</div>
        <div style="font-size: 0.875rem; font-weight: 700; font-family: monospace; color: var(--accent-blue);">${formatNumber(uncachedToks)}</div>
        <div style="font-size: 0.7rem; color: var(--text-muted);">${formatNumber(outputToks)} output total</div>
      </div>
    </div>

    <div style="font-size: 0.72rem; color: var(--text-muted); border-top: 1px solid var(--card-border); padding-top: 6px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
      <span>ID: <code style="font-size: 0.7rem;">${node.id}</code></span>
      <span>Created: ${node.created_at || "Earlier in session"}</span>
    </div>
  `;
}

function renderToolAnalytics(data) {
  const toolData = (data && data.tool_analytics) || {};
  const totalCalls = toolData.total_tool_calls || 0;
  const tools = toolData.tools || {};
  const topTools = toolData.top_tools || [];
  const categories = toolData.categories || {};
  const skills = toolData.skills || [];

  // Update KPI and badges
  const kpiTools = document.getElementById("kpi-tool-calls");
  if (kpiTools) kpiTools.textContent = formatNumber(totalCalls);

  const totalBadge = document.getElementById("tool-total-badge");
  if (totalBadge) totalBadge.textContent = `${totalCalls.toLocaleString()} Total Calls`;

  const bypassBadge = document.getElementById("tool-bypass-badge");
  if (bypassBadge && tools.run_command) {
    bypassBadge.textContent = `${tools.run_command.sandbox_bypass_pct}% Sandbox Bypass (${tools.run_command.sandbox_bypass_count.toLocaleString()} calls)`;
  }

  // Render Category Cards
  const catGrid = document.getElementById("tool-categories-grid");
  if (catGrid) {
    const catKeys = Object.keys(categories);
    if (catKeys.length === 0) {
      catGrid.innerHTML = '<div style="font-size: 0.8125rem; color: var(--text-muted);">No categories available.</div>';
    } else {
      catGrid.innerHTML = catKeys.map(k => {
        const cat = categories[k];
        return `
          <div style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 10px 12px;">
            <div style="font-size: 0.7rem; text-transform: uppercase; font-weight: 700; color: var(--text-muted); letter-spacing: 0.05em;">
              ${escapeHtml(cat.category)}
            </div>
            <div style="font-size: 1.125rem; font-weight: 700; font-family: monospace; color: var(--text-main); margin: 2px 0;">
              ${cat.call_count.toLocaleString()}
            </div>
            <div style="font-size: 0.72rem; color: var(--text-muted);">${cat.frequency_pct}% of activity</div>
          </div>
        `;
      }).join("");
    }
  }

  // Render Tool Distribution Table
  const tbody = document.getElementById("tools-tbody");
  if (tbody) {
    if (topTools.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No tool invocations recorded.</td></tr>';
    } else {
      tbody.innerHTML = topTools.map(t => {
        let errBadgeClass = "badge green";
        if (t.error_rate_pct > 10) errBadgeClass = "badge red";
        else if (t.error_rate_pct > 2) errBadgeClass = "badge amber";

        let bypassColor = "var(--text-muted)";
        if (t.sandbox_bypass_pct > 20) bypassColor = "var(--accent-amber)";

        return `
          <tr>
            <td><code>${escapeHtml(t.tool_name)}</code></td>
            <td><span class="code-pill">${escapeHtml(t.category)}</span></td>
            <td style="font-family: monospace; font-weight: 600;">${t.call_count.toLocaleString()}</td>
            <td>
              <div class="tool-progress-bg">
                <div class="tool-progress-fill" style="width: ${Math.min(100, t.frequency_pct * 2)}%; background: var(--accent-blue);"></div>
              </div>
              <span style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace;">${t.frequency_pct}%</span>
            </td>
            <td>
              <span style="font-family: monospace; font-size: 0.8125rem; font-weight: 600; color: ${bypassColor};">
                ${t.sandbox_bypass_pct}%
              </span>
              <span style="font-size: 0.72rem; color: var(--text-muted);">(${t.sandbox_bypass_count})</span>
            </td>
            <td>
              <span class="${errBadgeClass}" style="font-size: 0.7rem; padding: 2px 6px;">
                ${t.error_rate_pct}% (${t.error_count})
              </span>
            </td>
          </tr>
        `;
      }).join("");
    }
  }

  // Render Skill Activations
  const skillsGrid = document.getElementById("skills-grid");
  if (skillsGrid) {
    if (skills.length === 0) {
      skillsGrid.innerHTML = '<div style="font-size: 0.8125rem; color: var(--text-muted);">No skill activations recorded.</div>';
    } else {
      skillsGrid.innerHTML = skills.map(sk => `
        <div style="background: var(--bg-alt); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px 14px;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px;">
            <strong style="font-size: 0.875rem; color: var(--text-main);">🎯 ${escapeHtml(sk.skill_name)}</strong>
            <span class="badge blue" style="font-size: 0.7rem; padding: 2px 6px;">${sk.activation_count} calls</span>
          </div>
          <div style="font-size: 0.72rem; color: var(--text-muted); font-family: monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(sk.skill_path)}">
            ${escapeHtml(sk.skill_path)}
          </div>
        </div>
      `).join("");
    }
  }
}

// ================= M25: Active Quota Intelligence & Cache Coaching (ADR-038) =================

function renderActiveBurstSessions(sessions) {
  const container = document.getElementById("burst-sessions-drawer");
  if (!container) return;
  if (!sessions || sessions.length === 0) {
    container.innerHTML = "";
    return;
  }

  const topSessions = sessions.slice(0, 5);
  const rowsHtml = topSessions.map((s, idx) => {
    const title = escapeHtml(s.title || "Untitled Session");
    const ws = escapeHtml(s.workspace_name || "");
    const tok = formatNumber(s.total_processed_tokens || 0);
    const turns = s.turn_count || 0;
    const cid = escapeHtml(s.convo_id || "");
    const model = escapeHtml(s.primary_model_name || "Flash");

    return `
      <div class="burst-session-row">
        <div style="display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1;">
          <div class="burst-session-title" onclick="inspectSessionById('${cid}')" title="${title} (${ws})">
            ${idx + 1}. ${title}
          </div>
          <div style="font-size: 0.6875rem; color: var(--text-muted); display: flex; gap: 6px; align-items: center;">
            <span>${turns} turns</span>
            <span>•</span>
            <span style="color: var(--accent-blue);">${model}</span>
          </div>
        </div>
        <div style="text-align: right; margin-left: 8px;">
          <div style="font-family: monospace; font-weight: 600; font-size: 0.75rem; color: var(--text-main);">${tok}</div>
          <div style="font-size: 0.6875rem; color: var(--accent-blue); cursor: pointer;" onclick="inspectSessionById('${cid}')">Inspect →</div>
        </div>
      </div>
    `;
  }).join("");

  container.innerHTML = `
    <div class="active-burst-sessions">
      <div class="burst-sessions-toggle" onclick="toggleBurstSessionsList()">
        <span style="display: flex; align-items: center; gap: 6px;">
          <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #0ea5e9;"></span>
          <span>Top Burst Sessions in 5h</span>
          <span class="badge blue" style="font-size: 0.65rem; padding: 1px 6px;">${sessions.length} Active</span>
        </span>
        <span id="burst-sessions-toggle-icon" style="font-size: 0.75rem; color: var(--text-muted); transition: transform 0.2s ease;">▶</span>
      </div>
      <div id="burst-sessions-list-container" class="burst-sessions-list" style="display: none;">
        ${rowsHtml}
      </div>
    </div>
  `;
}

function toggleBurstSessionsList() {
  const list = document.getElementById("burst-sessions-list-container");
  const icon = document.getElementById("burst-sessions-toggle-icon");
  if (!list) return;
  if (list.style.display === "flex") {
    list.style.display = "none";
    if (icon) icon.textContent = "▶";
  } else {
    list.style.display = "flex";
    if (icon) icon.textContent = "▼";
  }
}

function renderCacheCoaching(coaching) {
  const container = document.getElementById("cache-coaching-section");
  if (!container) return;
  if (!coaching) {
    container.innerHTML = "";
    return;
  }

  const flips = coaching.model_flips_detected || 0;
  const wastedTok = formatNumber(coaching.wasted_uncached_tokens || 0);
  const wastedCost = activeCurrency === "GBP"
    ? `£${(coaching.wasted_avoided_cost_gbp || 0).toFixed(2)}`
    : `$${(coaching.wasted_avoided_cost_usd || 0).toFixed(2)}`;
  const tip = escapeHtml(coaching.coaching_tip || "");
  const incidents = coaching.top_incidents || [];

  if (flips === 0) {
    container.innerHTML = `
      <div class="section-card" style="padding: 12px 18px; display: flex; align-items: center; justify-content: space-between; border-left: 4px solid #22c55e;">
        <div style="display: flex; align-items: center; gap: 10px;">
          <span style="font-size: 1.1rem; color: #22c55e;">✓</span>
          <div>
            <div style="font-weight: 600; font-size: 0.875rem; color: var(--text-main);">Cache Continuity Excellent</div>
            <div style="font-size: 0.75rem; color: var(--text-muted);">Zero cross-provider KV cache evictions detected across your sessions.</div>
          </div>
        </div>
        <span class="badge green" style="font-size: 0.7rem;">90%+ Cache Reuse</span>
      </div>
    `;
    return;
  }

  const incidentsHtml = incidents.slice(0, 3).map(inc => {
    const title = escapeHtml(inc.title || "Untitled Session");
    const ws = escapeHtml(inc.workspace_name || "");
    const fromM = escapeHtml(inc.from_model || "Prev Model");
    const toM = escapeHtml(inc.to_model || "Next Model");
    const wasted = formatNumber(inc.wasted_tokens || 0);
    const cid = escapeHtml(inc.convo_id || "");
    const cost = activeCurrency === "GBP" ? `£${(inc.wasted_cost_gbp || 0).toFixed(2)}` : `$${(inc.wasted_cost_usd || 0).toFixed(2)}`;

    return `
      <div style="background: var(--quota-bg); border: 1px solid var(--card-border); border-radius: 8px; padding: 10px 14px; margin-top: 8px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
        <div>
          <div style="font-weight: 600; font-size: 0.8125rem; color: var(--text-main); display: flex; align-items: center; gap: 8px;">
            <span>${title}</span>
            <span class="model-flip-tag">${fromM} ➔ ${toM}</span>
          </div>
          <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 2px;">
            ${ws} • Step #${inc.step_idx || "—"} • Incurred <strong>+${wasted}</strong> uncached replay tokens (${cost})
          </div>
        </div>
        <button class="btn-secondary" style="font-size: 0.72rem; padding: 4px 10px; cursor: pointer;" onclick="inspectSessionById('${cid}')">
          Inspect Session →
        </button>
      </div>
    `;
  }).join("");

  container.innerHTML = `
    <div class="cache-coaching-card">
      <div class="cache-coaching-header">
        <div>
          <div class="cache-coaching-title">
            <span>⚡ Cache-Efficiency Coaching: Cross-Provider Model-Flip Penalty</span>
            <span class="badge amber" style="font-size: 0.7rem;">${flips} Evictions Detected</span>
          </div>
          <div style="font-size: 0.78125rem; color: var(--text-muted); margin-top: 4px; max-width: 750px;">
            ${tip}
          </div>
        </div>
      </div>

      <div class="coaching-grid">
        <div class="coaching-stat-pill">
          <span class="coaching-stat-lbl">Model Flips Detected</span>
          <span class="coaching-stat-val" style="color: #f59e0b;">${flips}</span>
        </div>
        <div class="coaching-stat-pill">
          <span class="coaching-stat-lbl">Wasted Replay Tokens</span>
          <span class="coaching-stat-val" style="color: #ef4444;">${wastedTok}</span>
        </div>
        <div class="coaching-stat-pill">
          <span class="coaching-stat-lbl">Wasted Avoided Value</span>
          <span class="coaching-stat-val" style="color: #d97706;">${wastedCost}</span>
        </div>
        <div class="coaching-stat-pill">
          <span class="coaching-stat-lbl">Typical Cache Reuse</span>
          <span class="coaching-stat-val" style="color: #22c55e;">~90%</span>
        </div>
      </div>

      <div>
        <div style="font-size: 0.75rem; font-weight: 600; text-transform: uppercase; color: var(--text-muted); margin-bottom: 4px;">
          Top Replay Invalidation Incidents
        </div>
        ${incidentsHtml}
      </div>
    </div>
  `;
}

function inspectSessionById(convoId) {
  switchTab("tab-sessions");
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
  switchTab("tab-sessions");
  const searchInput = document.getElementById("convo-search-input");
  if (searchInput) {
    searchInput.value = titleOrId;
    filterData();
  }
}

window.selectSwarmById = selectSwarmById;
window.inspectSwarmNode = inspectSwarmNode;
window.handleSwarmFilterChange = handleSwarmFilterChange;
window.handleSwarmSortChange = handleSwarmSortChange;
window.jumpToProject = jumpToProject;
window.renderSwarmsView = renderSwarmsView;
window.renderToolAnalytics = renderToolAnalytics;
window.renderActiveBurstSessions = renderActiveBurstSessions;
window.toggleBurstSessionsList = toggleBurstSessionsList;
window.renderCacheCoaching = renderCacheCoaching;
window.inspectSessionById = inspectSessionById;
window.inspectSessionInExplorer = inspectSessionInExplorer;
window.renderWeeklyTrends = renderWeeklyTrends;
window.renderWeeklyTrendsSvg = renderWeeklyTrendsSvg;

// ==========================================
// Historical Weekly Trends & SVG Trendline Chart (M4 / ADR-039)
// ==========================================

let activeTrendMetric = "tokens"; // 'tokens' | 'cost' | 'bvi'

function initWeeklyTrends() {
  const btnTokens = document.getElementById("btn-trend-tokens");
  const btnCost = document.getElementById("btn-trend-cost");
  const btnBvi = document.getElementById("btn-trend-bvi");

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
}

function updateTrendMetricButtons() {
  const btnTokens = document.getElementById("btn-trend-tokens");
  const btnCost = document.getElementById("btn-trend-cost");
  const btnBvi = document.getElementById("btn-trend-bvi");

  if (btnTokens) btnTokens.classList.toggle("active", activeTrendMetric === "tokens");
  if (btnCost) btnCost.classList.toggle("active", activeTrendMetric === "cost");
  if (btnBvi) btnBvi.classList.toggle("active", activeTrendMetric === "bvi");
}

function formatCompactTokens(num) {
  if (num >= 1e9) return (num / 1e9).toFixed(2) + "B";
  if (num >= 1e6) return (num / 1e6).toFixed(1) + "M";
  if (num >= 1e3) return (num / 1e3).toFixed(1) + "k";
  return (num || 0).toString();
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
    kpiAvgTokens.textContent = summary.average_tokens_per_week ? formatCompactTokens(summary.average_tokens_per_week) : "—";
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
    kpiPeakTokens.textContent = summary.peak_week_tokens ? formatCompactTokens(summary.peak_week_tokens) : "—";
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
  let metricColor = "#0ea5e9";
  let metricName = "Processed Tokens";

  if (metric === "cost") {
    values = cycles.map(c => activeCurrency === "GBP" ? (c.estimated_cost_gbp || 0) : (c.estimated_cost_usd || 0));
    const sym = activeCurrency === "GBP" ? "£" : "$";
    formatVal = (v) => `${sym}${v.toFixed(2)}`;
    metricColor = "#22c55e";
    metricName = activeCurrency === "GBP" ? "Estimated Value (£)" : "Estimated Value ($)";
  } else if (metric === "bvi") {
    values = cycles.map(c => c.peak_bvi || 0);
    formatVal = (v) => `${v.toFixed(2)}x`;
    metricColor = "#a855f7";
    metricName = "Peak Burn Velocity (BVI)";
  } else {
    values = cycles.map(c => c.total_processed_tokens || 0);
    formatVal = (v) => formatCompactTokens(v);
    metricColor = "#0ea5e9";
    metricName = "Processed Tokens";
  }

  const maxVal = Math.max(...values, 0);
  let yCeil = maxVal;
  if (metric === "bvi") {
    yCeil = Math.max(2.0, maxVal * 1.2);
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

  // Build Area and Line paths
  const pointsStr = coords.map(pt => `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`).join(" L ");
  const linePath = `M ${pointsStr}`;
  const areaPath = `M ${coords[0].x.toFixed(1)},${(padding.top + plotH).toFixed(1)} L ${pointsStr} L ${coords[coords.length - 1].x.toFixed(1)},${(padding.top + plotH).toFixed(1)} Z`;

  // Grid lines & labels (4 levels)
  let gridHtml = "";
  const ticks = [0, 0.333, 0.666, 1.0];
  ticks.forEach(t => {
    const yVal = yCeil * t;
    const yPos = padding.top + plotH - (t * plotH);
    gridHtml += `
      <line x1="${padding.left}" y1="${yPos.toFixed(1)}" x2="${padding.left + plotW}" y2="${yPos.toFixed(1)}" stroke="var(--card-border)" stroke-dasharray="3 3" opacity="0.4" />
      <text x="${padding.left - 10}" y="${(yPos + 4).toFixed(1)}" text-anchor="end" fill="var(--text-muted)" font-size="10" font-family="monospace">${formatVal(yVal)}</text>
    `;
  });

  // Reference 1.0x line for BVI
  let refLineHtml = "";
  if (metric === "bvi" && yCeil >= 1.0) {
    const refY = getY(1.0);
    refLineHtml = `
      <line x1="${padding.left}" y1="${refY.toFixed(1)}" x2="${padding.left + plotW}" y2="${refY.toFixed(1)}" stroke="#22c55e" stroke-dasharray="4 2" stroke-width="1.2" opacity="0.7" />
      <text x="${padding.left + plotW - 4}" y="${(refY - 4).toFixed(1)}" text-anchor="end" fill="#22c55e" font-size="9" font-weight="600">1.0x Sustainable</text>
    `;
  }

  // Overage highlights
  let overageHtml = "";
  coords.forEach(pt => {
    if (pt.cycle.actual_overage_credits > 0) {
      const colW = Math.max(22, (plotW / n) * 0.8);
      overageHtml += `
        <rect x="${(pt.x - colW / 2).toFixed(1)}" y="${padding.top}" width="${colW.toFixed(1)}" height="${plotH}" fill="rgba(245, 158, 11, 0.1)" rx="4" />
        <text x="${pt.x.toFixed(1)}" y="${padding.top + 12}" text-anchor="middle" fill="#f59e0b" font-size="8.5" font-weight="700">⚠️ OVERAGE</text>
      `;
    }
  });

  // X Axis Labels (UK format: e.g. "03 Sep")
  let xLabelsHtml = "";
  coords.forEach((pt, i) => {
    const sDt = pt.cycle.cycle_start_utc ? formatUkDateShort(pt.cycle.cycle_start_utc) : `W${i + 1}`;
    const isCur = pt.cycle.is_current_cycle;
    const labelText = isCur ? `${sDt}*` : sDt;
    xLabelsHtml += `
      <text x="${pt.x.toFixed(1)}" y="${(padding.top + plotH + 18).toFixed(1)}" text-anchor="middle" fill="${isCur ? 'var(--accent-blue)' : 'var(--text-muted)'}" font-size="10" font-weight="${isCur ? '700' : '500'}" font-family="monospace">
        ${labelText}
      </text>
    `;
  });

  // Data Points
  let pointsHtml = "";
  coords.forEach(pt => {
    const isCur = pt.cycle.is_current_cycle;
    const hasOvg = pt.cycle.actual_overage_credits > 0;
    const pointClass = `trendline-point ${metric} ${hasOvg ? 'overage' : ''} ${isCur ? 'current' : ''}`;
    let halo = "";
    if (isCur) {
      halo = `<circle cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="8" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="2 2" opacity="0.8" />`;
    }
    pointsHtml += `
      ${halo}
      <circle class="${pointClass}" cx="${pt.x.toFixed(1)}" cy="${pt.y.toFixed(1)}" r="4.5" data-idx="${pt.idx}" />
    `;
  });

  // Assemble full SVG
  svg.innerHTML = `
    <defs>
      <linearGradient id="trends-area-grad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${metricColor}" stop-opacity="0.35" />
        <stop offset="100%" stop-color="${metricColor}" stop-opacity="0.0" />
      </linearGradient>
    </defs>
    ${overageHtml}
    ${gridHtml}
    ${refLineHtml}
    <path class="trendline-area" d="${areaPath}" fill="url(#trends-area-grad)" />
    <path class="trendline-stroke ${metric}" d="${linePath}" />
    ${xLabelsHtml}
    ${pointsHtml}
    <line id="trendline-cursor-line" x1="0" y1="${padding.top}" x2="0" y2="${padding.top + plotH}" class="trendline-cursor-line" style="display: none;" />
  `;

  // Attach mouse interaction
  const cursorLine = svg.getElementById("trendline-cursor-line");

  const updateScrubber = (clientX, clientY) => {
    const rect = svg.getBoundingClientRect();
    const scaleX = width / rect.width;
    const mouseSvgX = (clientX - rect.left) * scaleX;

    if (mouseSvgX < padding.left || mouseSvgX > padding.left + plotW) {
      if (cursorLine) cursorLine.style.display = "none";
      if (tooltip) tooltip.style.display = "none";
      return;
    }

    // Find nearest point
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
        ? `<div style="margin-top: 4px; padding: 3px 6px; background: rgba(245,158,11,0.15); border: 1px solid rgba(245,158,11,0.3); border-radius: 4px; color: #f59e0b; font-weight: 700;">⚠️ ${formatNumber(c.actual_overage_credits)} credits burned (${formatCurrency(c.actual_overage_usd, c.actual_overage_gbp, 2)})</div>`
        : "";
      const statusText = isCur
        ? `<div style="margin-top: 4px; color: #38bdf8; font-weight: 600;">● Active in-progress cycle</div>`
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
    const curBadge = isCur ? '<span class="badge blue" style="font-size: 0.65rem; margin-left: 6px;">Active</span>' : "";
    const ovgBadge = hasOvg
      ? `<span class="badge amber" style="font-size: 0.72rem; padding: 2px 6px;">-${formatNumber(c.actual_overage_credits)} credits (${formatCurrency(c.actual_overage_usd, c.actual_overage_gbp, 2)})</span>`
      : '<span style="color: var(--text-muted);">—</span>';

    const bviColor = c.peak_bvi > 1.0 ? "#f59e0b" : "#22c55e";
    const statusBadge = isCur
      ? '<span class="badge blue" style="font-size: 0.72rem;">In Progress</span>'
      : (hasOvg ? '<span class="badge amber" style="font-size: 0.72rem;">Exceeded Quota</span>' : '<span class="badge green" style="font-size: 0.72rem;">In Quota</span>');

    return `
      <tr>
        <td style="font-weight: 600; white-space: nowrap;">
          ${c.label} ${curBadge}
        </td>
        <td>${formatNumber(c.total_turns)}</td>
        <td>
          <strong style="color: #60a5fa;">${formatCompactTokens(c.total_processed_tokens)}</strong>
          <span style="font-size: 0.72rem; color: var(--text-muted); display: block;">
            ${formatCompactTokens(c.cached_tokens)} cached / ${formatCompactTokens(c.prompt_tokens_uncached)} uncached
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

window.addEventListener("DOMContentLoaded", initDashboard);


