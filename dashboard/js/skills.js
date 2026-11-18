/**
 * Skills & Capabilities Sub-View Component
 * Milestone E (Phase 3: Dedicated Skills Sub-View)
 *
 * Manages the Skills & Capabilities sub-view within Swarms:
 * - Tool Categories Summary grid
 * - Tool Invocations & Bypass analytics table
 * - Cleaned Skills inventory with Built-in/Plugin vs Custom classification
 * - Skill search and filter controls
 * Extracts skills rendering logic out of dashboard/js/swarms.js (ADR-066).
 */

var activeSkillSearchQuery = "";
var activeSkillTypeFilter = "all";

/**
 * Classify a skill path into 'built-in' (plugin / system) vs 'custom' (user / workspace).
 */
function classifySkillType(skillPath) {
  if (!skillPath) return { type: "custom", label: "Custom Skill", badgeClass: "badge-skill-custom" };
  const p = skillPath.toLowerCase();
  if (p.includes("/plugins/") || p.includes("plugin") || p.includes("/built-in/") || p.includes("devtools") || p.includes("android-cli") || p.includes("gemini-api")) {
    return { type: "builtin", label: "Plugin / Built-in", badgeClass: "badge-skill-builtin" };
  }
  return { type: "custom", label: "Custom Workspace", badgeClass: "badge-skill-custom" };
}

/**
 * Extract associated core tools based on skill name and context.
 */
function inferSkillTools(skillName) {
  const name = (skillName || "").toLowerCase();
  if (name.includes("a11y") || name.includes("chrome") || name.includes("devtools") || name.includes("lcp")) {
    return ["chrome-devtools", "evaluate_script", "take_screenshot"];
  }
  if (name.includes("git") || name.includes("review") || name.includes("audit") || name.includes("vdone")) {
    return ["run_command", "view_file", "grep_search"];
  }
  if (name.includes("bigquery") || name.includes("sql") || name.includes("spark") || name.includes("dataflow")) {
    return ["run_command", "bq_query", "view_file"];
  }
  if (name.includes("storage") || name.includes("gcs")) {
    return ["run_command", "gcloud_storage", "view_file"];
  }
  return ["run_command", "view_file", "replace_file_content"];
}

/**
 * Main renderer for Skills & Capabilities sub-view.
 */
function renderSkillsSubView(data) {
  const toolData = (data && data.tool_analytics) || {};
  const totalCalls = toolData.total_tool_calls || 0;
  const tools = toolData.tools || {};
  const topTools = toolData.top_tools || [];
  const categories = toolData.categories || {};
  const skills = toolData.skills || [];

  // 1. Update KPI badges
  const totalBadge = document.getElementById("tool-total-badge");
  if (totalBadge) totalBadge.textContent = `${totalCalls.toLocaleString()} Total Calls`;

  const bypassBadge = document.getElementById("tool-bypass-badge");
  if (bypassBadge && tools.run_command) {
    const bpPct = tools.run_command.sandbox_bypass_pct || 0;
    const bpCnt = tools.run_command.sandbox_bypass_count || tools.run_command.bypasses || 0;
    bypassBadge.textContent = `${bpPct}% Sandbox Bypass (${bpCnt.toLocaleString()} calls)`;
  }

  // 2. Render Tool Categories Summary
  const catGrid = document.getElementById("tool-categories-grid");
  if (catGrid) {
    const catKeys = Object.keys(categories);
    if (catKeys.length === 0) {
      catGrid.innerHTML = '<div style="font-size: 0.8125rem; color: var(--text-muted);">No categories available.</div>';
    } else {
      catGrid.innerHTML = catKeys.map(k => {
        const cat = categories[k];
        return `
          <div style="background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius-card, 6px); padding: 10px 12px;">
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

  // 3. Render Tool Distribution Table
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

        const callCount = t.call_count !== undefined ? t.call_count : (t.count || 0);
        const catName = t.category || "Execution";
        const freqPct = t.frequency_pct !== undefined ? t.frequency_pct : (t.pct_of_total || 0);
        const bpPct = t.sandbox_bypass_pct !== undefined ? t.sandbox_bypass_pct : (t.bypass_ratio_pct || 0);
        const bpCount = t.sandbox_bypass_count !== undefined ? t.sandbox_bypass_count : (t.bypass_count || 0);
        return `
          <tr>
            <td><code>${escapeHtml(t.tool_name)}</code></td>
            <td><span class="code-pill">${escapeHtml(catName)}</span></td>
            <td style="font-family: monospace; font-weight: 600;">${callCount.toLocaleString()}</td>
            <td>
              <div class="tool-progress-bg" role="progressbar" aria-valuenow="${Math.round(Math.min(100, freqPct * 2))}" aria-valuemin="0" aria-valuemax="100" aria-label="${escapeHtml(t.tool_name)} invocation frequency">
                <div class="tool-progress-fill" style="width: ${Math.min(100, freqPct * 2)}%; background: var(--camel-500);"></div>
              </div>
              <span style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace;">${freqPct}%</span>
            </td>
            <td>
              <span style="font-family: monospace; font-size: 0.8125rem; font-weight: 600; color: ${bypassColor};">
                ${bpPct}%
              </span>
              <span style="font-size: 0.72rem; color: var(--text-muted);">(${bpCount})</span>
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

  // 4. Render Filtered Skills Grid & Inventory
  renderSkillsInventory(skills);
}

/**
 * Filter and render skills inventory cards and count.
 */
function renderSkillsInventory(allSkills) {
  allSkills = allSkills || [];
  const skillsGrid = document.getElementById("skills-grid");
  if (!skillsGrid) return;

  const query = (activeSkillSearchQuery || "").trim().toLowerCase();
  const typeFilter = activeSkillTypeFilter || "all";

  const filtered = allSkills.filter(sk => {
    const classification = classifySkillType(sk.skill_path);
    if (typeFilter !== "all" && classification.type !== typeFilter) {
      return false;
    }
    if (query) {
      const name = (sk.skill_name || "").toLowerCase();
      const path = (sk.skill_path || "").toLowerCase();
      if (!name.includes(query) && !path.includes(query)) {
        return false;
      }
    }
    return true;
  });

  const countBadge = document.getElementById("skills-count-badge");
  if (countBadge) {
    countBadge.textContent = `${filtered.length} of ${allSkills.length} skills active`;
  }

  if (filtered.length === 0) {
    skillsGrid.innerHTML = `
      <div style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--text-muted); background: var(--bg-alt); border: 1px dashed var(--card-border); border-radius: var(--radius-card, 6px);">
        No skills match current search or type filter.
      </div>
    `;
    return;
  }

  skillsGrid.innerHTML = filtered.map(sk => {
    const classification = classifySkillType(sk.skill_path);
    const tools = inferSkillTools(sk.skill_name);
    const activations = sk.activation_count || sk.count || 1;

    return `
      <div class="skill-card" style="background: var(--bg-alt); border: 1px solid var(--card-border); border-radius: var(--radius-card, 6px); padding: 12px 14px; display: flex; flex-direction: column; justify-content: space-between; gap: 8px;">
        <div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 6px;">
            <strong style="font-size: 0.875rem; color: var(--text-main); font-family: var(--font-body);">${escapeHtml(sk.skill_name)}</strong>
            <span class="badge camel" style="font-size: var(--font-xs); padding: 2px 6px; white-space: nowrap;">${activations.toLocaleString()} calls</span>
          </div>
          <div style="margin-bottom: 8px;">
            <span class="badge-skill ${classification.badgeClass}" style="padding: 2px 6px;">${classification.label}</span>
          </div>
          <div style="font-size: var(--font-xs); color: var(--text-muted); font-family: monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-bottom: 6px;" title="${escapeHtml(sk.skill_path)}">
            ${escapeHtml(sk.skill_path)}
          </div>
        </div>
        <div style="border-top: 1px solid var(--card-border); padding-top: 6px; display: flex; gap: 4px; flex-wrap: wrap; align-items: center;">
          <span style="font-size: var(--font-xs); color: var(--text-muted); margin-right: 2px;">Tools:</span>
          ${tools.map(t => `<span class="code-pill" style="font-size: var(--font-xs); padding: 2px 6px;">${escapeHtml(t)}</span>`).join("")}
        </div>
      </div>
    `;
  }).join("");
}

/**
 * Handle skill search query changes.
 */
function handleSkillSearch(event) {
  activeSkillSearchQuery = (event && event.target) ? event.target.value : "";
  const allSkills = (typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.tool_analytics && globalDashboardData.tool_analytics.skills) || [];
  renderSkillsInventory(allSkills);
}

/**
 * Handle skill type filter change (All, Built-in, Custom).
 */
function handleSkillTypeFilter(type) {
  activeSkillTypeFilter = type || "all";
  const allSkills = (typeof globalDashboardData !== "undefined" && globalDashboardData && globalDashboardData.tool_analytics && globalDashboardData.tool_analytics.skills) || [];
  renderSkillsInventory(allSkills);
}

// Delegated change / click handler for skills filter
document.addEventListener("input", (event) => {
  if (event.target && event.target.id === "skill-search-input") {
    handleSkillSearch(event);
  }
});

document.addEventListener("change", (event) => {
  if (event.target && event.target.id === "skill-type-select") {
    handleSkillTypeFilter(event.target.value);
  }
});

// Window exports
if (typeof window !== "undefined") {
  window.classifySkillType = classifySkillType;
  window.inferSkillTools = inferSkillTools;
  window.renderSkillsSubView = renderSkillsSubView;
  window.renderSkillsInventory = renderSkillsInventory;
  window.handleSkillSearch = handleSkillSearch;
  window.handleSkillTypeFilter = handleSkillTypeFilter;
}
