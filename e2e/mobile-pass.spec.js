import { test, expect } from '@playwright/test';

/**
 * Mobile Viewport Polish, Ticker Clipping Fix & Table Scroll Wrappers E2E Spec
 * Milestone 61 (Row 16 / U8).
 *
 * Verifies:
 * 1. At 375x812 viewport (iPhone X standard mobile baseline), #token-ticker-hud is visible
 *    and its bounding box left edge satisfies left >= 0 (no left-clipping).
 * 2. Across all 6 views (Now, Sessions, Projects, Swarms, Billing, Plan), switching tabs
 *    via mobile bottom nav reveals each view with zero left-clipped visible elements (left >= -0.5).
 * 3. Horizontal scrolling on table scroll wrappers triggers delegated scroll listener and
 *    correctly toggles the .is-scrolled-end class on the parent .table-scroll-container.
 */

const tabs = [
  { name: 'Now', navId: 'mob-tab-now', viewId: 'view-now' },
  { name: 'Sessions', navId: 'mob-tab-sessions', viewId: 'view-sessions' },
  { name: 'Projects', navId: 'mob-tab-projects', viewId: 'view-projects' },
  { name: 'Swarms', navId: 'mob-tab-swarms', viewId: 'view-swarms' },
  { name: 'Billing', navId: 'mob-tab-billing', viewId: 'view-billing' },
  { name: 'Plan', navId: 'mob-tab-plan', viewId: 'view-plan' },
];

test.describe('Mobile Viewport & Table Scroll Wrappers (M61 / U8)', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
  });

  test('at 375x812 viewport: #token-ticker-hud is visible with bounding box left >= 0', async ({ page }) => {
    await page.goto('/index.html', { waitUntil: 'networkidle' });

    const ticker = page.locator('#token-ticker-hud');
    await expect(ticker).toBeVisible();

    const box = await ticker.boundingBox();
    expect(box).not.toBeNull();
    // Verify ticker left coordinate is non-negative (no clipping on left screen edge)
    expect(box.x).toBeGreaterThanOrEqual(0);
  });

  for (const tab of tabs) {
    test(`at 375x812 viewport on tab '${tab.name}': all visible elements have left >= -0.5`, async ({ page }) => {
      await page.goto('/index.html', { waitUntil: 'networkidle' });

      const navBtn = page.locator(`#${tab.navId}`);
      await navBtn.click();
      await expect(page.locator(`#${tab.viewId}`)).toBeVisible();

      // Small delay to allow any layout transitions or renders to settle
      await page.waitForTimeout(100);

      const violations = await page.evaluate((viewId) => {
        const results = [];
        const viewEl = document.getElementById(viewId);
        if (!viewEl) return [{ error: `View #${viewId} not found` }];
        const all = viewEl.querySelectorAll('*');
        for (const el of all) {
          // Exclude invisible, detached, or display: none elements
          if (el.offsetParent === null && el.tagName !== 'BODY' && el.tagName !== 'HTML') continue;
          if (el.namespaceURI === 'http://www.w3.org/2000/svg' && el.tagName.toLowerCase() !== 'svg') continue;

          const style = window.getComputedStyle(el);
          if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;

          // Exclude drawers, modals, backdrops, and visually hidden screen-reader helpers
          if (el.closest('#desktop-inspector-drawer') || el.closest('#drawer-backdrop') || el.closest('#plan-profile-modal')) continue;
          if (el.classList.contains('sr-only') || el.closest('.sr-only')) continue;

          // Exclude elements residing inside inactive tab views
          const parentView = el.closest('[id^="view-"]');
          if (parentView && !parentView.classList.contains('active')) continue;

          const rect = el.getBoundingClientRect();
          if (rect.width === 0 || rect.height === 0) continue;
          if (rect.bottom < 0 || rect.top > window.innerHeight) continue;

          // Check for negative left boundary with half-pixel tolerance for subpixel antialiasing
          if (rect.left < -0.5) {
            results.push({
              tag: el.tagName,
              id: el.id,
              className: el.className,
              left: rect.left,
              top: rect.top,
            });
          }
        }
        return results;
      }, tab.viewId);

      expect(violations).toEqual([]);
    });
  }

  test('table scroll wrapper horizontal scroll updates is-scrolled-end class on container', async ({ page }) => {
    await page.goto('/index.html', { waitUntil: 'networkidle' });

    // Navigate to Now tab to target #models-table
    await page.locator('#mob-tab-now').click();
    const modelsTable = page.locator('#models-table');
    await expect(modelsTable).toBeVisible();

    const wrapper = page.locator('#models-table').locator('xpath=ancestor::*[contains(@class, "table-scroll-wrapper")]');
    await expect(wrapper).toBeVisible();

    const scrollResults = await wrapper.evaluate(el => {
      const container = el.closest('.table-scroll-container');
      if (!container) return { error: 'No parent .table-scroll-container found' };

      // 1. Reset to start (scrollLeft = 0)
      el.scrollLeft = 0;
      el.dispatchEvent(new Event('scroll', { bubbles: true }));
      const atStartHasEnd = container.classList.contains('is-scrolled-end');

      // 2. Scroll to max end
      const maxScroll = Math.max(0, el.scrollWidth - el.clientWidth);
      el.scrollLeft = maxScroll;
      el.dispatchEvent(new Event('scroll', { bubbles: true }));
      const atEndHasEnd = container.classList.contains('is-scrolled-end');

      // 3. Scroll to intermediate offset
      el.scrollLeft = 100;
      el.dispatchEvent(new Event('scroll', { bubbles: true }));
      const at100HasEnd = container.classList.contains('is-scrolled-end');

      // 4. Reset back to start
      el.scrollLeft = 0;
      el.dispatchEvent(new Event('scroll', { bubbles: true }));
      const backAtStartHasEnd = container.classList.contains('is-scrolled-end');

      return {
        atStartHasEnd,
        atEndHasEnd,
        at100HasEnd,
        backAtStartHasEnd,
        maxScroll,
      };
    });

    expect(scrollResults.error).toBeUndefined();
    // At beginning, it must NOT have is-scrolled-end (unless table content is narrower than viewport)
    if (scrollResults.maxScroll > 10) {
      expect(scrollResults.atStartHasEnd).toBe(false);
      expect(scrollResults.atEndHasEnd).toBe(true);
      expect(scrollResults.backAtStartHasEnd).toBe(false);
    }
  });
});
