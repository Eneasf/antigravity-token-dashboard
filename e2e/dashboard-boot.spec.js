import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

test.describe('Dashboard Boot & Render Split E2E (Milestone 51 / Row 6 / C3)', () => {
  test('Boot once, pure render, delegated event listeners, and plan tier defaults', async ({ page }) => {
    const screenshotDir = path.resolve('dashboard/test-artifacts/m51_screenshots');
    if (!fs.existsSync(screenshotDir)) fs.mkdirSync(screenshotDir, { recursive: true });

    // 1. Initial load with cleared localStorage
    await page.addInitScript(() => {
      localStorage.clear();
    });

    const pageErrors = [];
    page.on('pageerror', err => pageErrors.push(err.message));

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/index.html');
    await page.waitForSelector('#sub-status-badge');

    // Verify initial boot
    const docTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    expect(docTheme).toBe('light');

    // Verify delegated tab switching works
    await page.locator('#dock-tab-sessions').click();
    await page.waitForTimeout(200);
    const sessionsViewVisible = await page.locator('#view-sessions').isVisible();
    expect(sessionsViewVisible).toBe(true);

    // Verify delegated currency toggle works
    await page.locator('#btn-curr-usd').click();
    await page.waitForTimeout(200);
    const activeCurrBtn = await page.locator('#btn-curr-usd').getAttribute('class');
    expect(activeCurrBtn).toContain('active');

    // Switch back to GBP and Now tab
    await page.locator('#btn-curr-gbp').click();
    await page.locator('#dock-tab-now').click();
    await page.waitForTimeout(200);

    // Milestone M96: Verify Horizon Analytics elements are present and visible on Now tab
    await expect(page.locator('#horizon-pill-bar')).toBeVisible();
    await expect(page.locator('#progression-chart-svg')).toBeVisible();
    await expect(page.locator('#diurnal-rhythm-svg')).toBeVisible();

    // Verify horizon pill switching without error
    const activeWeekPill = page.locator('.horizon-pill-btn[data-horizon="active_week"]');
    await activeWeekPill.click();
    await page.waitForTimeout(100);
    await expect(activeWeekPill).toHaveClass(/active/);

    const eraComparePill = page.locator('.horizon-pill-btn[data-horizon="era_compare"]');
    await eraComparePill.click();
    await page.waitForTimeout(100);
    await expect(eraComparePill).toHaveClass(/active/);

    const lifetimePill = page.locator('.horizon-pill-btn[data-horizon="lifetime"]');
    await lifetimePill.click();
    await page.waitForTimeout(100);
    await expect(lifetimePill).toHaveClass(/active/);

    expect(pageErrors).toEqual([]);

    // Capture AFTER screenshot 1440x900 Now Tab
    await page.screenshot({ path: path.join(screenshotDir, 'after-1440-now.png') });

    // 2. Navigate to Plan tab
    await page.locator('#dock-tab-plan').click();
    await page.waitForTimeout(300);

    // Verify Plan Profile preset tier select defaults to summary.tier ('ultra_5x')
    const planTierPreset = await page.locator('#plan-tier-select').inputValue();
    expect(planTierPreset).toBe('ultra_5x');

    // Verify Simulator plan select also defaults to summary.tier ('ultra_5x')
    const simPlanTier = await page.locator('#sim-plan-select').inputValue();
    expect(simPlanTier).toBe('ultra_5x');

    // Verify archetype selection via delegated click
    await page.locator('.sim-archetype-card[data-archetype="codebase_audit"]').click();
    await page.waitForTimeout(200);
    const activeArch = await page.locator('.sim-archetype-card[data-archetype="codebase_audit"]').getAttribute('class');
    expect(activeArch).toContain('active');

    // Capture AFTER screenshot 1440x900 Plan Tab
    await page.screenshot({ path: path.join(screenshotDir, 'after-1440-plan.png') });

    // 3. Test Reload Idempotence & Zero Duplicate Options
    // Check initial filter option count
    const initialWsOptionCount = await page.locator('#workspace-filter option').count();
    const initialConvoOptionCount = await page.locator('#convo-filter option').count();

    // Trigger render() multiple times in the page context
    await page.evaluate(() => {
      if (typeof window.render === 'function') {
        window.render(window.__TELEMETRY_DATA__);
        window.render(window.__TELEMETRY_DATA__);
        window.render(window.__TELEMETRY_DATA__);
      } else if (typeof render === 'function') {
        render(globalDashboardData);
        render(globalDashboardData);
        render(globalDashboardData);
      }
    });

    // Assert that filter option counts remain unchanged (zero duplication)
    const afterWsOptionCount = await page.locator('#workspace-filter option').count();
    const afterConvoOptionCount = await page.locator('#convo-filter option').count();
    expect(afterWsOptionCount).toBe(initialWsOptionCount);
    expect(afterConvoOptionCount).toBe(initialConvoOptionCount);

    // 4. Mobile Viewport (375x812)
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/index.html');
    await page.waitForSelector('#sub-status-badge');
    await page.screenshot({ path: path.join(screenshotDir, 'after-375-now.png') });

    await page.locator('#mob-tab-plan').click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(screenshotDir, 'after-375-plan.png') });
  });
});
