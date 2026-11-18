import { test, expect } from '@playwright/test';

test.describe('Navigation & Tab Switching Architecture', () => {
  const tabs = [
    { name: 'now', tabId: 'tab-now', dockId: 'dock-tab-now', viewId: 'view-now', contentSelector: '#executive-hero-card' },
    { name: 'sessions', tabId: 'tab-sessions', dockId: 'dock-tab-sessions', viewId: 'view-sessions', contentSelector: '#convo-search-input' },
    { name: 'projects', tabId: 'tab-projects', dockId: 'dock-tab-projects', viewId: 'view-projects', contentSelector: '#projects-table' },
    { name: 'swarms', tabId: 'tab-swarms', dockId: 'dock-tab-swarms', viewId: 'view-swarms', contentSelector: '#kpi-swarm-count' },
    { name: 'billing', tabId: 'tab-billing', dockId: 'dock-tab-billing', viewId: 'view-billing', contentSelector: '#billing-history-table' },
    { name: 'plan', tabId: 'tab-plan', dockId: 'dock-tab-plan', viewId: 'view-plan', contentSelector: '#plan-tier-select' },
  ];

  test.beforeEach(async ({ page }) => {
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');
  });

  test('Sidebar Dock Navigation switches active view cleanly with zero overflow', async ({ page }) => {
    for (const target of tabs) {
      const dockBtn = page.locator(`#${target.dockId}`);
      await dockBtn.click();

      // Assert active button
      await expect(dockBtn).toHaveClass(/active/);

      // Assert target view is visible
      const activeView = page.locator(`#${target.viewId}`);
      await expect(activeView).toBeVisible();
      await expect(activeView).toHaveClass(/active/);

      // Assert specific unique content within that view becomes visible
      await expect(page.locator(target.contentSelector)).toBeVisible();

      // Assert all other views are hidden
      for (const other of tabs) {
        if (other.viewId !== target.viewId) {
          const otherView = page.locator(`#${other.viewId}`);
          await expect(otherView).toBeHidden();
        }
      }

      // Check horizontal overflow on every tab switch
      const hasOverflow = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      expect(hasOverflow).toBe(false);
    }
  });

  test('Top Bar Navigation switches views in Top Bar mode', async ({ page }) => {
    // Switch to Top Bar mode
    await page.locator('#btn-shell-top').click();
    await expect(page.locator('#app-layout-container')).toHaveClass(/shell-mode-top/);
    await expect(page.locator('#sidebar-dock')).toBeHidden();

    for (const target of tabs) {
      const topTabBtn = page.locator(`#${target.tabId}`);
      await topTabBtn.click();

      await expect(topTabBtn).toHaveClass(/active/);
      await expect(page.locator(`#${target.viewId}`)).toBeVisible();

      // Assert specific unique content within that view becomes visible
      await expect(page.locator(target.contentSelector)).toBeVisible();

      // Verify other views are hidden
      for (const other of tabs) {
        if (other.viewId !== target.viewId) {
          await expect(page.locator(`#${other.viewId}`)).toBeHidden();
        }
      }
    }
  });

  test('Inspector drawer opens and closes without shadow bleeding', async ({ page }) => {
    const drawer = page.locator('#desktop-inspector-drawer');
    const closeBtn = page.locator('.drawer-close-btn');

    // Initially closed
    await expect(drawer).not.toHaveClass(/open/);
    const initialVisibility = await drawer.evaluate(el => window.getComputedStyle(el).visibility);
    expect(initialVisibility).toBe('hidden');

    // Open drawer programmatically
    await page.evaluate(() => {
      if (typeof window.openInspectorDrawer === 'function') {
        window.openInspectorDrawer();
      } else {
        const d = document.getElementById('desktop-inspector-drawer');
        const b = document.getElementById('drawer-backdrop');
        if (d) d.classList.add('open');
        if (b) b.classList.add('open');
      }
    });

    await expect(drawer).toHaveClass(/open/);
    const openState = await drawer.evaluate(el => {
      const style = window.getComputedStyle(el);
      return {
        visibility: style.visibility,
        hasShadow: style.boxShadow !== 'none',
      };
    });
    expect(openState.visibility).toBe('visible');
    expect(openState.hasShadow).toBe(true);

    // Close drawer
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
    } else {
      await page.evaluate(() => {
        if (typeof window.closeInspectorDrawer === 'function') {
          window.closeInspectorDrawer();
        } else {
          const d = document.getElementById('desktop-inspector-drawer');
          const b = document.getElementById('drawer-backdrop');
          if (d) d.classList.remove('open');
          if (b) b.classList.remove('open');
        }
      });
    }

    await expect(drawer).not.toHaveClass(/open/);
    await page.waitForTimeout(350);
    const closedState = await drawer.evaluate(el => {
      const style = window.getComputedStyle(el);
      return {
        visibility: style.visibility,
        boxShadow: style.boxShadow,
      };
    });
    expect(closedState.visibility).toBe('hidden');
    expect(closedState.boxShadow).toBe('none');
  });
});
