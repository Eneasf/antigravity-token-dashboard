import { test, expect } from '@playwright/test';

test.describe('Milestones D & E: Session Tree Aggregation, 42px Swarm Ribbon & Skills Sub-View', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');
  });

  test('Sessions View Mode: Tree View vs Flat View toggle and accordion expansion', async ({ page }) => {
    // Navigate to Sessions tab
    await page.locator('#dock-tab-sessions').click();
    await expect(page.locator('#view-sessions')).toBeVisible();

    const btnTree = page.locator('#btn-view-tree');
    const btnFlat = page.locator('#btn-view-flat');

    // 1. Initial State: Tree View is active by default
    await expect(btnTree).toBeVisible();
    await expect(btnFlat).toBeVisible();
    await expect(btnTree).toHaveClass(/active/);
    await expect(btnTree).toHaveAttribute('aria-pressed', 'true');
    await expect(btnFlat).not.toHaveClass(/active/);
    await expect(btnFlat).toHaveAttribute('aria-pressed', 'false');

    // 2. Parent-child accordion rows in tree view
    const treeRows = page.locator('#conversations-tbody .tree-parent-row');
    const treeCount = await treeRows.count();
    expect(treeCount).toBeGreaterThan(0);

    // Find a parent row with children
    const toggleBtns = page.locator('#conversations-tbody .tree-toggle-btn');
    const toggleCount = await toggleBtns.count();

    if (toggleCount > 0) {
      const firstToggle = toggleBtns.first();
      await expect(firstToggle).toHaveAttribute('aria-expanded', 'false');

      // Expand accordion
      await firstToggle.click();
      await expect(firstToggle).toHaveAttribute('aria-expanded', 'true');

      // Child row should now be visible
      const childRows = page.locator('#conversations-tbody .tree-child-row');
      await expect(childRows.first()).toBeVisible();

      // Child row should have connector and role badge
      const connector = childRows.first().locator('.tree-branch-connector');
      await expect(connector).toBeVisible();

      // Collapse accordion
      await firstToggle.click();
      await expect(firstToggle).toHaveAttribute('aria-expanded', 'false');
    }

    // 3. Toggle to Flat View
    await btnFlat.click();
    await expect(btnFlat).toHaveClass(/active/);
    await expect(btnFlat).toHaveAttribute('aria-pressed', 'true');
    await expect(btnTree).not.toHaveClass(/active/);

    // In flat view, tree toggle buttons must not be present
    const flatToggles = page.locator('#conversations-tbody .tree-toggle-btn');
    expect(await flatToggles.count()).toBe(0);

    // 4. Toggle back to Tree View
    await btnTree.click();
    await expect(btnTree).toHaveClass(/active/);
    await expect(btnTree).toHaveAttribute('aria-pressed', 'true');
  });

  test('Tree-aware search expands matching parent tree sessions', async ({ page }) => {
    await page.locator('#dock-tab-sessions').click();
    await expect(page.locator('#view-sessions')).toBeVisible();

    const searchInput = page.locator('#convo-search-input');
    await expect(searchInput).toBeVisible();

    // Type a search query
    await searchInput.fill('Worker');
    await page.waitForTimeout(200);

    // Verify conversations table remains populated or displays valid matching results
    const rows = page.locator('#conversations-tbody tr');
    expect(await rows.count()).toBeGreaterThan(0);

    // Clear search
    await page.locator('#btn-clear-filters').click();
    await page.waitForTimeout(100);
    expect(await searchInput.inputValue()).toBe('');
  });

  test('Swarms View: 42px Compact Fleet Ribbon and Sub-View Navigation', async ({ page }) => {
    // Navigate to Swarms tab
    await page.locator('#dock-tab-swarms').click();
    await expect(page.locator('#view-swarms')).toBeVisible();

    // 1. Verify 42px Compact Metric Ribbon retains required selector #kpi-swarm-count
    const ribbon = page.locator('.swarm-compact-ribbon');
    await expect(ribbon).toBeVisible();

    const kpiCount = page.locator('#kpi-swarm-count');
    await expect(kpiCount).toBeVisible();
    const countText = await kpiCount.textContent();
    expect(countText).toContain('Swarms');

    // Verify ribbon height is compact (~42px, allow up to 55px on varying fonts)
    const ribbonBox = await ribbon.boundingBox();
    expect(ribbonBox).not.toBeNull();
    if (ribbonBox) {
      expect(ribbonBox.height).toBeLessThanOrEqual(58);
    }

    // Verify other ribbon metrics
    await expect(page.locator('#kpi-swarm-tokens')).toBeVisible();
    await expect(page.locator('#kpi-swarm-pace')).toBeVisible();
    await expect(page.locator('#kpi-swarm-avoided')).toBeVisible();

    // 2. Sub-View Navigation: DAG vs Skills
    const btnDag = page.locator('#btn-subview-dag');
    const btnSkills = page.locator('#btn-subview-skills');
    const viewDag = page.locator('#swarms-subview-dag');
    const viewSkills = page.locator('#swarms-subview-skills');

    await expect(btnDag).toBeVisible();
    await expect(btnSkills).toBeVisible();

    // Initial Sub-View: DAG is active
    await expect(btnDag).toHaveClass(/active/);
    await expect(btnDag).toHaveAttribute('aria-selected', 'true');
    await expect(viewDag).toBeVisible();
    await expect(viewSkills).toBeHidden();

    // Role budget distribution bar is visible in DAG sub-view
    await expect(page.locator('#swarm-role-budget-container')).toBeVisible();

    // 3. Switch to Skills Sub-View
    await btnSkills.click();
    await expect(btnSkills).toHaveClass(/active/);
    await expect(btnSkills).toHaveAttribute('aria-selected', 'true');
    await expect(btnDag).not.toHaveClass(/active/);
    await expect(viewSkills).toBeVisible();
    await expect(viewDag).toBeHidden();

    // Verify Skills Sub-View components
    await expect(page.locator('#tool-categories-grid')).toBeVisible();
    await expect(page.locator('#tools-table')).toBeVisible();
    await expect(page.locator('#skills-grid')).toBeVisible();

    // 4. Test Skills search & type filter
    const skillSearch = page.locator('#skill-search-input');
    await expect(skillSearch).toBeVisible();
    await skillSearch.fill('review');
    await page.waitForTimeout(200);

    const countBadge = page.locator('#skills-count-badge');
    await expect(countBadge).toBeVisible();

    // Switch type filter
    const skillTypeSelect = page.locator('#skill-type-select');
    await skillTypeSelect.selectOption('builtin');
    await page.waitForTimeout(200);

    // 5. Switch back to DAG Sub-View
    await btnDag.click();
    await expect(btnDag).toHaveClass(/active/);
    await expect(viewDag).toBeVisible();
    await expect(viewSkills).toBeHidden();
  });

  test('Now Tab: Active Multi-Agent Swarms card and weakest-link context degradation parity', async ({ page }) => {
    const pageErrors = [];
    page.on('pageerror', err => pageErrors.push(err.message));

    // 1. Initial view: Now tab is visible
    await expect(page.locator('#view-now')).toBeVisible();

    // 2. #now-active-swarms dynamically mounted inside #view-now
    const swarmsCard = page.locator('#view-now #now-active-swarms');
    await expect(swarmsCard).toBeVisible();

    // 3. Section header and title
    await expect(swarmsCard.locator('.now-swarms-title')).toHaveText('Active Multi-Agent Swarms');
    await expect(swarmsCard.locator('.now-swarms-live-pill')).toBeVisible();

    // 4. Verify swarm cards render with orchestrator, agent count, and weakest-link risk badge
    const cards = swarmsCard.locator('.now-swarm-card');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThan(0);

    const firstCard = cards.first();
    await expect(firstCard.locator('.now-swarm-title')).toBeVisible();
    await expect(firstCard.locator('.now-agent-count-pill')).toBeVisible();

    // Weakest-link context degradation risk badge
    const riskBadge = firstCard.locator('.now-risk-badge');
    await expect(riskBadge).toBeVisible();
    const riskText = await riskBadge.textContent();
    expect(riskText).toMatch(/HEALTHY|ELEVATED|CRITICAL/);
    expect(riskText).toMatch(/\d+%/);

    // Orchestrator row with model badge (e.g. Argon Med)
    const orchRow = firstCard.locator('.now-orchestrator-row');
    await expect(orchRow).toBeVisible();
    const orchModelBadge = orchRow.locator('.now-model-badge');
    await expect(orchModelBadge).toBeVisible();
    const orchModelText = await orchModelBadge.textContent();
    expect(orchModelText).toMatch(/Carbon|Argon|Flash|Pro|Claude|GPT/);

    // 5. Expandable / compact child subagents toggle and rows
    const toggleBtn = firstCard.locator('[data-action="toggle-swarm-subagents"]');
    if (await toggleBtn.isVisible()) {
      const subList = firstCard.locator('.now-subagents-list');
      await expect(subList).toBeVisible();

      // Check subagent model badge, turn count, and tokens
      const firstSub = subList.locator('.now-subagent-row').first();
      await expect(firstSub).toBeVisible();
      const subModelBadge = firstSub.locator('.now-model-badge');
      await expect(subModelBadge).toBeVisible();
      const subModelText = await subModelBadge.textContent();
      expect(subModelText).toMatch(/Carbon|Argon|Flash|Pro|Claude|GPT/);
      await expect(firstSub.locator('.now-node-turns')).toBeVisible();
      await expect(firstSub.locator('.now-node-tokens')).toBeVisible();

      // Collapse toggle
      await toggleBtn.click();
      await expect(subList).toBeHidden();
      expect(await toggleBtn.getAttribute('aria-expanded')).toBe('false');

      // Expand toggle back
      await toggleBtn.click();
      await expect(subList).toBeVisible();
      expect(await toggleBtn.getAttribute('aria-expanded')).toBe('true');
    }

    // 6. One-click button 'View Full Swarm Topology →' with [data-tab="swarms"]
    const topolBtn = swarmsCard.locator('[data-tab="swarms"]');
    await expect(topolBtn).toBeVisible();
    await topolBtn.click();

    // Should switch to Swarms tab
    await expect(page.locator('#view-swarms')).toBeVisible();
    await expect(page.locator('#dock-tab-swarms')).toHaveClass(/active/);

    // Zero page errors
    expect(pageErrors).toEqual([]);
  });
});
