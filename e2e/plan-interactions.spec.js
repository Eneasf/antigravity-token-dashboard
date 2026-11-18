import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

let cachedDataJs = null;
let cachedMetaJs = null;

function getFixtureScripts() {
  if (!cachedDataJs) {
    const jsonStr = execSync(
      'python3 scripts/export_dashboard.py --antigravity-dir tests/fixtures/antigravity --no-live-quota --reference-time 2026-09-05T14:30:00Z --json',
      { encoding: 'utf8', maxBuffer: 50 * 1024 * 1024 }
    );
    const payload = JSON.parse(jsonStr);
    cachedDataJs = `window.__TELEMETRY_DATA__ = ${jsonStr};\nwindow.__ANTIGRAVITY_DASHBOARD_DATA__ = window.__TELEMETRY_DATA__;\n`;
    cachedMetaJs = `window.__TELEMETRY_META__ = ${JSON.stringify({
      payload_sha1: 'fixture_deterministic_hash',
      payload_bytes: Buffer.byteLength(jsonStr, 'utf8'),
      conversations_count: (payload.conversations || []).length,
      generated_at: payload.temporal?.resolved_at_utc || '2026-09-05T14:30:00Z',
      ticker: payload.live_ticker || {}
    })};\n`;
  }
  return { dataJs: cachedDataJs, metaJs: cachedMetaJs };
}

test.describe('Plan Manager, Simulator & Inspector Interactions', () => {
  test.beforeEach(async ({ page }) => {
    const { dataJs, metaJs } = getFixtureScripts();
    await page.route('**/data.js*', route => {
      route.fulfill({ status: 200, contentType: 'application/javascript', body: dataJs });
    });
    await page.route('**/meta.js*', route => {
      route.fulfill({ status: 200, contentType: 'application/javascript', body: metaJs });
    });
  });

  test('apply plan "pro" in the manager updates capacity, badges, persists to localStorage, and survives reload', async ({ page }) => {
    await page.goto('/index.html', { waitUntil: 'load' });
    await page.evaluate(() => localStorage.clear());
    await page.reload({ waitUntil: 'load' });
    await page.waitForSelector('#sub-status-badge');

    // (a) Open the plan manager modal (e.g. via #btn-open-plan-manager or data-action="open-plan-manager")
    const openBtn = page.locator('#btn-open-plan-manager, [data-action="open-plan-manager"]').first();
    await expect(openBtn).toBeVisible();
    await openBtn.click();
    await page.waitForTimeout(200);

    // Apply plan "pro" (click the Pro plan card or activate button, or dropdown + apply)
    const proCardOrBtn = page.locator(
      'button[data-action="activate-plan"][data-tier="pro"], ' +
      '.plan-card[data-tier="pro"] button, ' +
      '[data-tier="pro"] .btn-activate, ' +
      'button:has-text("Activate Pro"), ' +
      'button:has-text("Apply Pro"), ' +
      '.plan-card[data-tier="pro"]'
    );

    if (await proCardOrBtn.count() > 0 && await proCardOrBtn.first().isVisible()) {
      await proCardOrBtn.first().click();
    } else {
      const tierSelect = page.locator('#plan-tier-select');
      await expect(tierSelect).toBeVisible();
      await tierSelect.selectOption('pro');

      const saveBtn = page.locator('#btn-save-plan');
      await expect(saveBtn).toBeVisible();
      await saveBtn.click();
    }
    await page.waitForTimeout(200);

    // Verify gemini weekly capacity_usd becomes 129
    const geminiWeeklyCap = await page.evaluate(() => {
      const q = window.globalDashboardData?.quotas;
      return q?.providers?.gemini?.weekly?.capacity_usd ?? q?.subscription?.quota_limits?.gemini_weekly_capacity_usd;
    });
    expect(geminiWeeklyCap).toBe(129);

    // Header tier badge (#header-tier-badge) updates to "Pro"
    const headerTierBadge = page.locator('#header-tier-badge');
    await expect(headerTierBadge).toBeVisible();
    await expect(headerTierBadge).toContainText('Pro');

    // Close plan modal or navigate to Now tab to view hero weekly bar
    const closeBtn = page.locator('#btn-close-plan-modal, [data-action="close-plan-modal"]');
    if (await closeBtn.count() > 0 && await closeBtn.first().isVisible()) {
      await closeBtn.first().click();
    }
    await page.locator('#dock-tab-now').click();
    await expect(page.locator('#view-now')).toBeVisible();

    const heroBar = page.locator('#executive-hero-card, #exec-weekly-bar');
    await expect(heroBar.first()).toBeVisible();

    // localStorage "antigravity_selected_plan" is set
    const savedPlanStr = await page.evaluate(() => localStorage.getItem('antigravity_selected_plan'));
    expect(savedPlanStr).not.toBeNull();
    const savedPlan = JSON.parse(savedPlanStr);
    expect(savedPlan.tier).toBe('pro');
    expect(savedPlan.quota_limits?.gemini_weekly_capacity_usd).toBe(129);

    // Survives reload (page.reload() and verify tier / allowance is preserved)
    await page.reload({ waitUntil: 'load' });
    await page.waitForTimeout(300);

    await expect(page.locator('#header-tier-badge')).toContainText('Pro');
    const reloadedCap = await page.evaluate(() => {
      const q = window.globalDashboardData?.quotas;
      return q?.providers?.gemini?.weekly?.capacity_usd ?? q?.subscription?.quota_limits?.gemini_weekly_capacity_usd;
    });
    expect(reloadedCap).toBe(129);

    const reloadedSavedPlan = await page.evaluate(() => localStorage.getItem('antigravity_selected_plan'));
    expect(reloadedSavedPlan).not.toBeNull();
    expect(JSON.parse(reloadedSavedPlan).tier).toBe('pro');
  });

  test('select "Deep Refactor Swarm" preset in the simulator, nudge slider to Custom, and restore back', async ({ page }) => {
    await page.goto('/index.html', { waitUntil: 'load' });
    await page.waitForSelector('#sub-status-badge');

    // (b) Navigate to Plan / Simulator view
    await page.locator('#dock-tab-plan').click();
    await expect(page.locator('#view-plan')).toBeVisible();

    // Select "Deep Refactor Swarm" preset
    const deepRefactorCard = page.locator('.sim-archetype-card[data-archetype="deep_refactor_swarm"]');
    if (await deepRefactorCard.isVisible()) {
      await deepRefactorCard.click();
    } else {
      await page.locator('#sim-archetype-select').selectOption('deep_refactor_swarm');
    }
    await page.waitForTimeout(200);

    const turnsSlider = page.locator('#sim-turns-slider');
    await expect(turnsSlider).toBeVisible();
    const initialTurns = parseInt(await turnsSlider.inputValue(), 10);
    expect(initialTurns).toBe(40);

    // Nudge turns slider by one -> preset select becomes "Custom"
    const nudgedVal = String(initialTurns + 1);
    await turnsSlider.fill(nudgedVal);
    await turnsSlider.dispatchEvent('input');
    await turnsSlider.dispatchEvent('change');
    await page.waitForTimeout(100);

    const isCustom = await page.evaluate(() => {
      const sel = document.getElementById('sim-archetype-select');
      const activeCard = document.querySelector('.sim-archetype-card.active');
      return (sel && sel.value === 'custom') || (activeCard && activeCard.getAttribute('data-archetype') === 'custom');
    });
    expect(isCustom).toBe(true);

    // Set value back -> preset stays selected (Custom)
    await turnsSlider.fill(String(initialTurns));
    await turnsSlider.dispatchEvent('input');
    await turnsSlider.dispatchEvent('change');
    await page.waitForTimeout(100);

    const staysCustom = await page.evaluate(() => {
      const sel = document.getElementById('sim-archetype-select');
      const activeCard = document.querySelector('.sim-archetype-card.active');
      return (sel && sel.value === 'custom') || (activeCard && activeCard.getAttribute('data-archetype') === 'custom');
    });
    expect(staysCustom).toBe(true);
  });

  test('open a session in the inspector opens drawer and displays session title', async ({ page }) => {
    await page.goto('/index.html', { waitUntil: 'load' });
    await page.waitForSelector('#sub-status-badge');

    // (c) Go to Sessions tab, click a session
    await page.locator('#dock-tab-sessions').click();
    await expect(page.locator('#view-sessions')).toBeVisible();

    const sessionRow = page.locator('#conversations-tbody tr').first();
    await expect(sessionRow).toBeVisible();

    const expectedTitle = await sessionRow.locator('strong').first().innerText();
    expect(expectedTitle.length).toBeGreaterThan(0);

    const inspectBtn = sessionRow.locator('[data-action="inspect-session"]');
    if (await inspectBtn.count() > 0 && await inspectBtn.isVisible()) {
      await inspectBtn.click();
    } else {
      await sessionRow.click();
    }
    await page.waitForTimeout(200);

    // Verify #desktop-inspector-drawer opens and #drawer-heading displays that session's title
    const drawer = page.locator('#desktop-inspector-drawer');
    await expect(drawer).toHaveClass(/open/);
    await expect(drawer).toBeVisible();

    const drawerHeading = page.locator('#drawer-heading');
    await expect(drawerHeading).toHaveText(expectedTitle);
  });
});
