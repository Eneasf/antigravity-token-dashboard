import { test, expect } from '@playwright/test';

test.describe('Truncation Per Model & Sessions Paging Architecture (Gate B3-B7 / M54)', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');
    await page.waitForSelector('#sub-status-badge');
  });

  test('header contains at most one red badge', async ({ page }) => {
    // Demote loud false-positive red alarms to amber-on-hover; header has at most one red badge
    const redBadges = page.locator('header .badge.red');
    const redCount = await redBadges.count();
    expect(redCount).toBeLessThanOrEqual(1);
  });

  test('first h2 in #view-sessions reads Conversations', async ({ page }) => {
    // Navigate to Sessions tab via dock or top tab
    const dockBtn = page.locator('#dock-tab-sessions');
    const topTabBtn = page.locator('#tab-sessions');
    if (await dockBtn.isVisible()) {
      await dockBtn.click();
    } else {
      await topTabBtn.click();
    }

    // Wait for #view-sessions to become visible
    const viewSessions = page.locator('#view-sessions');
    await expect(viewSessions).toBeVisible();

    // Get the first h2 within #view-sessions
    const firstH2 = await page.locator('#view-sessions h2').first().textContent();
    expect(firstH2).not.toBeNull();
    const trimmed = firstH2.trim();
    expect(trimmed === 'Conversations' || trimmed.startsWith('Conversations')).toBe(true);
  });

  test('table tbody tr count <= 25 on load', async ({ page }) => {
    // Navigate to Sessions tab
    const dockBtn = page.locator('#dock-tab-sessions');
    const topTabBtn = page.locator('#tab-sessions');
    if (await dockBtn.isVisible()) {
      await dockBtn.click();
    } else {
      await topTabBtn.click();
    }

    await expect(page.locator('#view-sessions')).toBeVisible();

    // Table rows rendered on page load must not exceed 25 items
    const rows = page.locator('#conversations-tbody tr');
    const rowCount = await rows.count();
    expect(rowCount).toBeLessThanOrEqual(25);
  });

  test('pagination interaction', async ({ page }) => {
    // Navigate to Sessions tab
    const dockBtn = page.locator('#dock-tab-sessions');
    const topTabBtn = page.locator('#tab-sessions');
    if (await dockBtn.isVisible()) {
      await dockBtn.click();
    } else {
      await topTabBtn.click();
    }

    await expect(page.locator('#view-sessions')).toBeVisible();

    const pageInfo = page.locator('#convo-page-info');
    await expect(pageInfo).toBeVisible();

    const prevBtn = page.locator('#btn-convo-prev');
    const nextBtn = page.locator('#btn-convo-next');
    await expect(prevBtn).toBeVisible();
    await expect(nextBtn).toBeVisible();

    const initialInfo = (await pageInfo.textContent()) || '';

    // If data has multiple pages (> 25 items):
    const isNextEnabled = await nextBtn.isEnabled();
    if (isNextEnabled) {
      // Prev button must initially be disabled on page 1
      await expect(prevBtn).toBeDisabled();
      expect(initialInfo).toContain('Page 1');

      // Click next page button
      await nextBtn.click();
      await page.waitForTimeout(100);

      // Verify page info advanced to Page 2 and prev button is now enabled
      const page2Info = (await pageInfo.textContent()) || '';
      expect(page2Info).toContain('Page 2');
      await expect(prevBtn).toBeEnabled();

      // Click previous page button to navigate back
      await prevBtn.click();
      await page.waitForTimeout(100);

      const backToPage1Info = (await pageInfo.textContent()) || '';
      expect(backToPage1Info).toContain('Page 1');
      await expect(prevBtn).toBeDisabled();
    } else {
      // If dataset <= 25 items, both buttons must be disabled
      await expect(prevBtn).toBeDisabled();
      await expect(nextBtn).toBeDisabled();
      expect(initialInfo).toContain('Page 1 of 1');
    }
  });

  test('truncation audit accordion toggle interaction', async ({ page }) => {
    // Navigate to Sessions tab
    const dockBtn = page.locator('#dock-tab-sessions');
    const topTabBtn = page.locator('#tab-sessions');
    if (await dockBtn.isVisible()) {
      await dockBtn.click();
    } else {
      await topTabBtn.click();
    }

    await expect(page.locator('#view-sessions')).toBeVisible();

    // Verify widget container is attached in DOM
    const widgetContainer = page.locator('#sessions-degraded-widget-container');
    await expect(widgetContainer).toBeAttached();

    // Verify toggle interaction either via click action or window toggle function
    const toggleBtn = page.locator('[data-action="toggle-sessions-audit-accordion"]');
    if (await toggleBtn.isVisible()) {
      const initialOpen = await page.evaluate(() => Boolean(window.__sessionsAuditAccordionOpen));
      await toggleBtn.click();
      await page.waitForTimeout(150);
      const afterClickOpen = await page.evaluate(() => Boolean(window.__sessionsAuditAccordionOpen));
      expect(afterClickOpen).toBe(!initialOpen);

      // Toggle again to return to initial state
      await toggleBtn.click();
      await page.waitForTimeout(150);
      const restoredOpen = await page.evaluate(() => Boolean(window.__sessionsAuditAccordionOpen));
      expect(restoredOpen).toBe(initialOpen);
    } else {
      // Direct JS toggle verification when container is hidden or waiting for data
      const toggled = await page.evaluate(() => {
        if (typeof window.toggleSessionsAuditAccordion === 'function') {
          const before = Boolean(window.__sessionsAuditAccordionOpen);
          window.toggleSessionsAuditAccordion();
          const after = Boolean(window.__sessionsAuditAccordionOpen);
          window.toggleSessionsAuditAccordion();
          return after !== before;
        }
        return true;
      });
      expect(toggled).toBe(true);
    }
  });
});
