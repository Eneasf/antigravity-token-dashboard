import { test, expect } from '@playwright/test';

test.describe('Layout & Viewport Invariants', () => {
  const viewports = [
    { name: 'Desktop Standard', width: 1440, height: 900 },
    { name: 'Desktop Wide', width: 1920, height: 1080 },
    { name: 'Laptop / Tablet Landscape', width: 1280, height: 800 },
  ];

  for (const vp of viewports) {
    test(`Zero horizontal overflow at ${vp.name} (${vp.width}x${vp.height})`, async ({ page }) => {
      const consoleErrors = [];
      page.on('console', msg => {
        if (msg.type() === 'error') consoleErrors.push(msg.text());
      });
      page.on('pageerror', err => {
        consoleErrors.push(err.message);
      });

      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/index.html');
      await page.waitForLoadState('networkidle');

      // Check document overflow
      const overflow = await page.evaluate(() => {
        const docEl = document.documentElement;
        const body = document.body;
        return {
          docScrollWidth: docEl.scrollWidth,
          docClientWidth: docEl.clientWidth,
          bodyScrollWidth: body.scrollWidth,
          bodyClientWidth: body.clientWidth,
          windowWidth: window.innerWidth,
        };
      });

      expect(overflow.docScrollWidth).toBeLessThanOrEqual(overflow.docClientWidth);
      expect(overflow.bodyScrollWidth).toBeLessThanOrEqual(overflow.windowWidth);
      expect(consoleErrors).toEqual([]);

      // 1. Dimensional / geometric assertions for .main-viewport
      const mainViewport = page.locator('.main-viewport');
      const sideBox = await mainViewport.boundingBox();
      expect(sideBox).not.toBeNull();
      // Sidebar mode: occupies window.innerWidth - 64
      expect(sideBox.width).toBeCloseTo(overflow.windowWidth - 64, 0);

      // Top bar mode: occupies window.innerWidth
      await page.locator('#btn-shell-top').click();
      await expect(page.locator('#app-layout-container')).toHaveClass(/shell-mode-top/);
      await expect.poll(async () => {
        const box = await mainViewport.boundingBox();
        return box ? box.width : 0;
      }).toBeCloseTo(overflow.windowWidth, 0);

      // Reset back to sidebar mode for cleanliness
      await page.locator('#btn-shell-side').click();
      await expect(page.locator('#app-layout-container')).toHaveClass(/shell-mode-side/);
    });
  }

  test('Mobile viewport (375x812) collapses sidebar dock and displays mobile bottom nav', async ({ page }) => {
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');

    await page.setViewportSize({ width: 375, height: 812 });

    await expect(page.locator('#sidebar-dock')).toBeHidden();
    await expect(page.locator('#mobile-bottom-nav')).toBeVisible();
  });

  test('Closed inspector drawer projects zero shadow bleed and is hidden', async ({ page }) => {
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');

    const drawerState = await page.evaluate(() => {
      const drawer = document.getElementById('desktop-inspector-drawer');
      if (!drawer) return null;
      const style = window.getComputedStyle(drawer);
      const rect = drawer.getBoundingClientRect();
      return {
        isOpen: drawer.classList.contains('open'),
        visibility: style.visibility,
        boxShadow: style.boxShadow,
        rectLeft: rect.left,
        windowWidth: window.innerWidth,
      };
    });

    expect(drawerState).not.toBeNull();
    expect(drawerState.isOpen).toBe(false);
    expect(drawerState.visibility).toBe('hidden');
    expect(drawerState.boxShadow).toBe('none');
    expect(drawerState.rectLeft).toBeGreaterThanOrEqual(drawerState.windowWidth);
  });
});
