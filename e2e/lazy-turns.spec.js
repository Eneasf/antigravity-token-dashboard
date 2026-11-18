import { test, expect } from '@playwright/test';

test.describe('Lazy Turns & Session Inspector Architecture (Gate B6 / Milestone 55)', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('#sub-status-badge');
  });

  test('opening session inspector lazily loads turns.js and renders turn trajectory', async ({ page }) => {
    // 1. Switch to Sessions tab via dock button or top tab
    const dockBtn = page.locator('#dock-tab-sessions');
    const topTabBtn = page.locator('#tab-sessions');
    if (await dockBtn.isVisible()) {
      await dockBtn.click();
    } else {
      await topTabBtn.click();
    }

    const viewSessions = page.locator('#view-sessions');
    await expect(viewSessions).toBeVisible();

    // 2. Find the first session row and click it (or its inspect button) to open inspector
    const sessionRow = page.locator('#conversations-tbody tr').first();
    await expect(sessionRow).toBeVisible({ timeout: 10000 });
    const inspectBtn = sessionRow.locator('[data-action="inspect-session"]');
    if (await inspectBtn.count() > 0 && await inspectBtn.isVisible()) {
      await inspectBtn.click();
    } else {
      await sessionRow.click();
    }

    // 3. Wait for desktop inspector drawer to open and become visible
    const drawer = page.locator('#desktop-inspector-drawer');
    await expect(drawer).toBeVisible({ timeout: 10000 });

    // 4. Verify turn trajectory table renders rows with turns (triggering lazy turns load)
    const drawerTableRows = page.locator('#desktop-inspector-drawer table tbody tr');
    await expect(drawerTableRows.first()).toBeVisible({ timeout: 10000 });
    const rowCount = await drawerTableRows.count();
    expect(rowCount).toBeGreaterThan(0);

    // 5. Assert that window.__TELEMETRY_TURNS__ is defined and populated
    const turnsPopulated = await page.evaluate(() => {
      return Boolean(
        window.__TELEMETRY_TURNS__ &&
        typeof window.__TELEMETRY_TURNS__ === 'object' &&
        Object.keys(window.__TELEMETRY_TURNS__).length > 0
      );
    });
    expect(turnsPopulated).toBe(true);
  });

  test('inspector drawer close button and Escape key dismiss drawer', async ({ page }) => {
    const dockBtn = page.locator('#dock-tab-sessions');
    const topTabBtn = page.locator('#tab-sessions');
    if (await dockBtn.isVisible()) {
      await dockBtn.click();
    } else {
      await topTabBtn.click();
    }

    const viewSessions = page.locator('#view-sessions');
    await expect(viewSessions).toBeVisible();

    const sessionRow = page.locator('#conversations-tbody tr').first();
    await expect(sessionRow).toBeVisible({ timeout: 10000 });
    const inspectBtn = sessionRow.locator('[data-action="inspect-session"]');
    if (await inspectBtn.count() > 0 && await inspectBtn.isVisible()) {
      await inspectBtn.click();
    } else {
      await sessionRow.click();
    }
    const drawer = page.locator('#desktop-inspector-drawer');
    await expect(drawer).toBeVisible({ timeout: 10000 });

    // Close drawer via close button
    const closeBtn = page.locator('.drawer-close-btn, [data-action="close-inspector-drawer"]').first();
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
      await expect(drawer).not.toBeVisible({ timeout: 5000 });
    }

    // Reopen and verify Escape key dismiss
    if (await inspectBtn.count() > 0 && await inspectBtn.isVisible()) {
      await inspectBtn.click();
    } else {
      await sessionRow.click();
    }
    await expect(drawer).toBeVisible({ timeout: 10000 });
    await page.keyboard.press('Escape');
    await expect(drawer).not.toBeVisible({ timeout: 5000 });
  });
});
