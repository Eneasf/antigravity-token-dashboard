/* =====================================================================
   WHAT-IF WORKLOAD SIMULATOR & STRESS PLANNER
   Hydrated dynamically from getCatalog() (ADR-066 / Row 13).
   ===================================================================== */

function getSimArchetypes() {
  const cat = typeof getCatalog === "function" ? getCatalog() : {};
  if (cat && cat.simulator_archetypes) {
    if (Array.isArray(cat.simulator_archetypes)) {
      const map = {};
      cat.simulator_archetypes.forEach(a => { if (a.id) map[a.id] = a; });
      return map;
    }
    if (typeof cat.simulator_archetypes === "object") return cat.simulator_archetypes;
  }
  return {
    deep_refactor_swarm: {
      name: "Deep Refactor Swarm",
      model_id: "1427",
      turn_count: 40,
      prompt_tokens: 120000,
      cache_hit_ratio_pct: 88,
      thinking_tokens: 8000,
      answer_tokens: 1500,
      pace_minutes: 2.5,
      description: "Multi-agent deep architecture refactor on Gemini 4 Carbon."
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
      description: "High-context whole-codebase scan with deep prompt caching on Gemini 3.8 Flash."
    },
    rapid_prototyping_burst: {
      name: "Rapid Prototyping Burst",
      model_id: "1418",
      turn_count: 25,
      prompt_tokens: 45000,
      cache_hit_ratio_pct: 75,
      thinking_tokens: 1500,
      answer_tokens: 800,
      pace_minutes: 1.0,
      description: "Interactive fast-iteration development cycle on Gemini 4 Argon."
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
      model_id: "1198",
      turn_count: 100,
      prompt_tokens: 30000,
      cache_hit_ratio_pct: 85,
      thinking_tokens: 500,
      answer_tokens: 600,
      pace_minutes: 0.5,
      description: "Parallel background subagent workers executing mechanical tasks on Flash Lite."
    },
    hydrogen_xhigh_sprint: {
      name: "Hydrogen XHigh Sprint",
      model_id: "1528",
      turn_count: 30,
      prompt_tokens: 110000,
      cache_hit_ratio_pct: 93,
      thinking_tokens: 900,
      answer_tokens: 450,
      pace_minutes: 1.5,
      description: "High-efficiency Gemini 4 Hydrogen (XHigh) coding sprint across warm 1M context at 1/6x quota burn weight."
    }
  };
}

function getSimModelRates(modelId) {
  const cat = typeof getCatalog === "function" ? getCatalog() : {};
  const cm = (cat && cat.models && (cat.models[modelId] || cat.models["1318"])) || {};
  const r = cm.rates_per_million || { prompt_uncached: 0.75, prompt_cached: 0.075, candidate_output: 3.75 };
  return {
    name: cm.name || cm.taxonomy_name || `Model ${modelId}`,
    track: cm.track_id || "gemini",
    uncached: r.prompt_uncached || 0.75,
    cached: r.prompt_cached || 0.075,
    output: r.candidate_output || 3.75,
    credits_per_turn: cm.credits_per_turn || 0.0,
    status: cm.status || "active",
    sunset_date: cm.sunset_date || null
  };
}

function getSimPlanCapacities(planTier) {
  const cat = typeof getCatalog === "function" ? getCatalog() : {};
  const pt = (cat && cat.plan_tiers && (cat.plan_tiers[planTier] || cat.plan_tiers.pro)) || {};
  const ql = pt.quota_limits || {};
  return {
    name: pt.name || "Google AI Pro",
    multiplier: parseFloat(pt.multiplier_label) || (planTier.includes("ultra_5x") ? 5.0 : 1.0),
    gemini_5h: ql.gemini_5h_capacity_usd || 20.00,
    gemini_weekly: ql.gemini_weekly_capacity_usd || 129.00,
    claude_5h: ql.claude_5h_capacity_usd !== undefined ? ql.claude_5h_capacity_usd : 10.00,
    claude_weekly: ql.claude_weekly_capacity_usd !== undefined ? ql.claude_weekly_capacity_usd : 35.00
  };
}

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

  const preset = getSimArchetypes()[archetypeId];
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
    const p = getSimArchetypes()[activeArch];
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
  const rates = getSimModelRates(modelId);
  const trackBadge = document.getElementById("sim-track-badge");
  if (trackBadge) {
    if (rates.track === "gemini") {
      trackBadge.textContent = "Track 1: Gemini";
      trackBadge.style.color = "var(--accent-primary, var(--camel-500))";
      trackBadge.style.borderColor = "var(--accent-primary, var(--camel-500))";
    } else {
      trackBadge.textContent = "Claude & GPT (Separate allowance)";
      trackBadge.style.color = "var(--accent-amber)";
      trackBadge.style.borderColor = "var(--accent-amber)";
    }
  }

  // Plan badge update
  const planBadge = document.getElementById("sim-plan-badge");
  const plan = getSimPlanCapacities(planTier);
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
    recommendation = `CRITICAL: Claude burst limit of $${burstCapUsd.toFixed(2)} exceeded at turn ${exhaustionTurn} with separate allowance (Provider Policy). Immediate HTTP 429 rate limit lock! Switch to Gemini Flash/Pro or upgrade to Google AI Ultra (5x capacity).`;
  } else if (burstExhausted) {
    statusKey = "cooldown";
    statusLabel = "Burst Cooldown";
    riskLevel = "HIGH_EXHAUSTION";
    badgeClass = "badge amber";
    heroBorderColor = "var(--accent-amber)";
    fillBg = "var(--accent-amber)";
    const useAiCredits = (globalDashboardData && globalDashboardData.summary && globalDashboardData.summary.use_ai_credits !== false);
    if (useAiCredits) {
      recommendation = `5-hour burst capacity exceeded by $${overBurstUsd.toFixed(2)} at turn ${exhaustionTurn}. Covered by Google One AI Credit Bank: ${creditsDebited.toLocaleString()} credits (${isGbp ? '£' + creditCostGbp.toFixed(2) : '$' + creditCostUsd.toFixed(2)}) will be debited.`;
    } else {
      recommendation = `5-hour burst capacity exceeded by $${overBurstUsd.toFixed(2)} at turn ${exhaustionTurn}. Credit overages disabled: hard stop at limit until window resets.`;
    }
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
    const customFeeUsd = parseFloat(document.getElementById("custom-fee-usd")?.value || "0");
    const isHighFee = customFeeUsd >= 500 || (globalDashboardData && globalDashboardData.summary && globalDashboardData.summary.monthly_subscription_price_usd >= 500);

    if (riskLevel === "CRITICAL_429" || statusKey === "lockout" || isHighFee) {
      riskBadge.textContent = "Critical Risk";
      riskBadge.className = "code-pill red";
    } else if (riskLevel === "HIGH_EXHAUSTION" || statusKey === "cooldown") {
      riskBadge.textContent = "High Risk";
      riskBadge.className = "code-pill amber";
    } else if (riskLevel === "MODERATE" || statusKey === "caution") {
      riskBadge.textContent = "Moderate Risk";
      riskBadge.className = "code-pill amber";
    } else {
      riskBadge.textContent = "Low Risk";
      riskBadge.className = "code-pill green";
    }
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
      riskSubEl.textContent = "Hard rate limit lockout (Separate allowance)";
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

  const w = svg.parentElement ? Math.max(500, Math.round(svg.parentElement.clientWidth || 500)) : 500;
  const h = 160;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.removeAttribute("preserveAspectRatio");
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

  const coords = trajectory.map(p => ({ x: getX(p.turn), y: getY(p.loadUsd) }));
  const simSpline = getSplinePath(coords);
  const areaBaseY = (padTop + plotH).toFixed(1);
  const areaPath = `${simSpline} L ${getX(maxTurn).toFixed(1)},${areaBaseY} L ${getX(0).toFixed(1)},${areaBaseY} Z`;

  let exhaustionMarker = "";
  if (exhaustionTurn !== null) {
    const pt = trajectory.find(p => p.turn === exhaustionTurn) || trajectory[trajectory.length - 1];
    const exX = getX(pt.turn);
    const exY = getY(pt.loadUsd);
    exhaustionMarker = `
      <circle cx="${exX.toFixed(1)}" cy="${exY.toFixed(1)}" r="5" fill="var(--status-alert, #EF4444)" stroke="var(--surface-card, #111827)" stroke-width="2"/>
      <text x="${Math.min(w - 70, exX + 8).toFixed(1)}" y="${Math.max(25, exY - 8).toFixed(1)}" fill="var(--status-alert, #EF4444)" font-size="10" font-weight="700" font-family="'Geist Mono', monospace">
        Exhausted (T${exhaustionTurn})
      </text>
    `;
  }

  svg.innerHTML = `
    <defs>
      <linearGradient id="sim-grad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--accent-primary, #3B82F6)" stop-opacity="0.18"/>
        <stop offset="100%" stop-color="var(--accent-primary, #3B82F6)" stop-opacity="0.0"/>
      </linearGradient>
    </defs>

    <!-- Grid lines -->
    <line x1="${padLeft}" y1="${padTop + plotH}" x2="${w - padRight}" y2="${padTop + plotH}" stroke="var(--card-border, #374151)" stroke-width="1"/>
    <line x1="${padLeft}" y1="${padTop}" x2="${padLeft}" y2="${padTop + plotH}" stroke="var(--card-border, #374151)" stroke-width="1"/>

    <!-- 100% Burst Boundary -->
    <line x1="${padLeft}" y1="${burstLimitY.toFixed(1)}" x2="${w - padRight}" y2="${burstLimitY.toFixed(1)}" stroke="var(--status-alert, #EF4444)" stroke-width="1.5" stroke-dasharray="4,4"/>
    <text x="${w - padRight - 5}" y="${(burstLimitY - 4).toFixed(1)}" fill="var(--status-alert, #EF4444)" font-size="9" text-anchor="end" font-weight="600" font-family="'Geist Mono', monospace">
      Burst Limit ($${burstCapUsd.toFixed(0)})
    </text>

    <!-- Area Fill -->
    <path d="${areaPath}" fill="url(#sim-grad)"/>

    <!-- Smooth Spline Trajectory -->
    <path d="${simSpline}" fill="none" stroke="var(--accent-primary, #3B82F6)" stroke-width="1.75"/>

    <!-- Start circle -->
    <circle cx="${getX(0).toFixed(1)}" cy="${getY(trajectory[0].loadUsd).toFixed(1)}" r="3.5" fill="var(--accent-primary, #3B82F6)"/>

    <!-- End circle -->
    <circle cx="${getX(maxTurn).toFixed(1)}" cy="${getY(trajectory[trajectory.length - 1].loadUsd).toFixed(1)}" r="3.5" fill="var(--accent-primary, #3B82F6)"/>

    <!-- Exhaustion marker if triggered -->
    ${exhaustionMarker}

    <!-- X Axis labels -->
    <text x="${padLeft}" y="${h - 6}" fill="var(--text-muted, #9CA3AF)" font-size="10" font-family="'Geist Mono', monospace">Turn 0</text>
    <text x="${(padLeft + plotW / 2).toFixed(1)}" y="${h - 6}" fill="var(--text-muted, #9CA3AF)" font-size="10" text-anchor="middle" font-family="'Geist Mono', monospace">Turn ${(maxTurn / 2).toFixed(0)}</text>
    <text x="${w - padRight}" y="${h - 6}" fill="var(--text-muted, #9CA3AF)" font-size="10" text-anchor="end" font-family="'Geist Mono', monospace">Turn ${maxTurn}</text>

    <!-- Y Axis labels -->
    <text x="${padLeft - 6}" y="${padTop + plotH}" fill="var(--text-muted, #9CA3AF)" font-size="9" text-anchor="end" font-family="'Geist Mono', monospace">$0</text>
    <text x="${padLeft - 6}" y="${burstLimitY.toFixed(1)}" fill="var(--status-alert, #EF4444)" font-size="9" text-anchor="end" font-family="'Geist Mono', monospace">$${burstCapUsd.toFixed(0)}</text>
  `;
}

function renderTierComparison(turnCostUsd, turnCount, rates, starting5hUsd) {
  const tbody = document.getElementById("sim-tier-tbody");
  if (!tbody) return;

  const planTierSelect = document.getElementById("sim-plan-select");
  const currentSelectedTier = planTierSelect ? planTierSelect.value : "pro";
  const totalCostUsd = turnCostUsd * turnCount;
  const isGbp = (activeCurrency === "GBP");

  const catalogTiers = (getCatalog() && getCatalog().plan_tiers) || {};
  let tiers = Object.keys(catalogTiers)
    .filter(k => catalogTiers[k].show_in_simulator !== false && catalogTiers[k].quota_limits)
    .map(k => {
      const t = catalogTiers[k];
      const ql = t.quota_limits || {};
      return {
        id: k,
        name: t.short_label || t.name || k,
        mult: t.multiplier || (t.multiplier_label ? parseFloat(t.multiplier_label) : 1.0) || 1.0,
        g5h: ql.gemini_5h_capacity_usd !== undefined ? ql.gemini_5h_capacity_usd : 20.00,
        c5h: ql.claude_5h_capacity_usd !== undefined ? ql.claude_5h_capacity_usd : 10.00
      };
    });
  if (tiers.length === 0) {
    tiers = [
      { id: "pro", name: "Pro (1×)", mult: 1.0, g5h: 20.00, c5h: 10.00 },
      { id: "ultra_5x", name: "Ultra (5×)", mult: 5.0, g5h: 25.00, c5h: 50.00 },
      { id: "ultra_20x", name: "Ultra (20×)", mult: 20.0, g5h: 400.00, c5h: 200.00 },
    ];
  }

  const promoMult = (rates.track === "gemini" && globalDashboardData && globalDashboardData.summary && globalDashboardData.summary.gemini_capacity_multiplier) || 1.0;

  tbody.innerHTML = tiers.map(t => {
    const burstCap = (rates.track === "gemini" ? t.g5h : t.c5h) * promoMult;
    const finalLoad = starting5hUsd + totalCostUsd;
    const usedPct = (finalLoad / burstCap) * 100.0;
    const exhausted = finalLoad > burstCap;

    let exTurnStr = "Safe (No exhaustion)";
    let creditsStr = "0 Credits (£0.00)";
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
        const useAiCredits = (globalDashboardData && globalDashboardData.summary && globalDashboardData.summary.use_ai_credits !== false);
        if (useAiCredits) {
          creditsStr = `${credits.toLocaleString()} credits (${isGbp ? '£' + costGbp.toFixed(2) : '$' + costUsd.toFixed(2)})`;
        } else {
          creditsStr = '<strong style="color: var(--accent-amber);">Disabled (hard stop at limit)</strong>';
        }
        statusBadge = '<span class="badge amber">Cooldown</span>';
      } else {
        creditsStr = '<strong style="color: var(--accent-red);">Separate allowance (429 Block)</strong>';
        statusBadge = '<span class="badge red">429 Lockout</span>';
      }
    }

    const isCurrent = t.id === currentSelectedTier;
    const rowClass = isCurrent ? 'class="active-tier"' : '';
    const currentMarker = isCurrent ? ' <span class="code-pill">Selected</span>' : '';

    return `
      <tr ${rowClass}>
        <td><strong>${escapeHtml(t.name)}</strong>${currentMarker}</td>
        <td class="num-col" style="text-align: right; font-variant-numeric: tabular-nums;">$${burstCap.toFixed(2)}</td>
        <td class="num-col" style="text-align: right; font-variant-numeric: tabular-nums; ${exhausted ? 'color: var(--status-alert, #EF4444); font-weight: 700;' : ''}">${usedPct.toFixed(1)}%</td>
        <td>${statusBadge}</td>
        <td>${exTurnStr}</td>
        <td>${creditsStr}</td>
      </tr>
    `;
  }).join("");
}

function initSimulator() {
  const cat = getCatalog();
  const modelSelect = document.getElementById("sim-model-select");
  if (modelSelect && cat.models && Object.keys(cat.models).length > 0) {
    const curVal = modelSelect.value;
    const tracks = (cat.quota_tracks && cat.quota_tracks.length > 0) ? cat.quota_tracks : [
      { id: "gemini", display_name: "Gemini Models" },
      { id: "claude_gpt", display_name: "Claude & GPT Models (Hard 429 limit)" }
    ];
    let html = "";
    tracks.forEach(tr => {
      const mList = Object.entries(cat.models)
        .filter(([, m]) => (m.provider_track || m.track) === tr.id && m.is_active !== false)
        .sort((a, b) => (a[1].sort_rank || 999) - (b[1].sort_rank || 999));
      if (mList.length > 0) {
        html += `<optgroup label="${escapeHtml(tr.display_name || tr.name || tr.id)}">`;
        mList.forEach(([mid, m]) => {
          html += `<option value="${mid}">${escapeHtml(m.display_name || m.name || mid)} - [${mid}]</option>`;
        });
        html += `</optgroup>`;
      }
    });
    if (html) {
      modelSelect.innerHTML = html;
      if (Array.from(modelSelect.options).some(o => o.value === curVal)) {
        modelSelect.value = curVal;
      }
    }
  }

  const planSelect = document.getElementById("sim-plan-select");
  if (planSelect && cat.plan_tiers && Object.keys(cat.plan_tiers).length > 0) {
    const curPlan = planSelect.value;
    const simTiers = Object.entries(cat.plan_tiers).filter(([, t]) => t.show_in_simulator !== false);
    if (simTiers.length > 0) {
      planSelect.innerHTML = simTiers.map(([k, t]) => {
        return `<option value="${k}">${escapeHtml(t.short_label || t.name || k)}</option>`;
      }).join("");
      if (Array.from(planSelect.options).some(o => o.value === curPlan)) {
        planSelect.value = curPlan;
      }
    }
  }

  if (planSelect && globalDashboardData && globalDashboardData.summary && globalDashboardData.summary.tier) {
    const summaryTier = globalDashboardData.summary.tier;
    if (Array.from(planSelect.options).some(opt => opt.value === summaryTier)) {
      planSelect.value = summaryTier;
    }
  }
  runSimulation();
}
