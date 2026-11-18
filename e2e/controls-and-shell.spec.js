import { test, expect } from '@playwright/test';

test.describe('Interactive Controls & Dual Shell Architecture', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');
  });

  test('Sidebar expands to 240px with labels and collapses back to 64px rail', async ({ page }) => {
    const layout = page.locator('#app-layout-container');
    const dock = page.locator('#sidebar-dock');
    const collapseBtn = page.locator('#btn-sidebar-collapse-footer');

    // 1. Initial State: Collapsed 64px
    await expect(layout).not.toHaveClass(/sidebar-expanded/);
    const initialWidth = await dock.evaluate(el => el.getBoundingClientRect().width);
    expect(Math.round(initialWidth)).toBe(64);

    // Dock nav labels must be hidden in collapsed state
    const labelsHidden = await page.locator('.sidebar-dock .dock-nav-label').first().evaluate(el => {
      return window.getComputedStyle(el).display === 'none';
    });
    expect(labelsHidden).toBe(true);

    // 2. Expand Sidebar
    await collapseBtn.click();
    await expect(layout).toHaveClass(/sidebar-expanded/);
    // Wait for width transition
    await page.waitForTimeout(300);
    const expandedWidth = await dock.evaluate(el => el.getBoundingClientRect().width);
    expect(Math.round(expandedWidth)).toBe(240);

    // Dock nav labels must be visible in expanded state
    const labelsVisible = await page.locator('.sidebar-dock .dock-nav-label').first().evaluate(el => {
      return window.getComputedStyle(el).display !== 'none';
    });
    expect(labelsVisible).toBe(true);

    // 3. Collapse Sidebar
    await collapseBtn.click();
    await expect(layout).not.toHaveClass(/sidebar-expanded/);
    await page.waitForTimeout(300);
    const collapsedWidth = await dock.evaluate(el => el.getBoundingClientRect().width);
    expect(Math.round(collapsedWidth)).toBe(64);
  });

  test('Shell Mode toggle switches between Sidebar Rail and Top Bar layout', async ({ page }) => {
    const layout = page.locator('#app-layout-container');
    const dock = page.locator('#sidebar-dock');
    const viewport = page.locator('#app-main-viewport');

    // 1. Default is Sidebar mode
    await expect(layout).toHaveClass(/shell-mode-side/);
    await expect(dock).toBeVisible();

    // 2. Switch to Top Bar mode
    await page.locator('#btn-shell-top').click();
    await expect(layout).toHaveClass(/shell-mode-top/);
    await expect(dock).toBeHidden();

    const topViewportMargin = await viewport.evaluate(el => {
      return window.getComputedStyle(el).marginLeft;
    });
    expect(parseFloat(topViewportMargin)).toBeLessThanOrEqual(2);

    // Tab buttons group should be visible in Top Bar mode
    const tabGroupVisible = await page.locator('.tab-buttons-group').evaluate(el => {
      return window.getComputedStyle(el).display !== 'none';
    });
    expect(tabGroupVisible).toBe(true);

    // 3. Switch back to Sidebar mode
    await page.locator('#btn-shell-side').click();
    await expect(layout).toHaveClass(/shell-mode-side/);
    await expect(dock).toBeVisible();
  });

  test('Currency switcher updates global active currency and button state', async ({ page }) => {
    const btnGbp = page.locator('#btn-curr-gbp');
    const btnUsd = page.locator('#btn-curr-usd');

    // Click USD
    await btnUsd.click();
    await expect(btnUsd).toHaveClass(/active/);
    await expect(btnGbp).not.toHaveClass(/active/);
    const usdActive = await page.evaluate(() => window.activeCurrency);
    expect(usdActive).toBe('USD');

    // Click GBP
    await btnGbp.click();
    await expect(btnGbp).toHaveClass(/active/);
    await expect(btnUsd).not.toHaveClass(/active/);
    const gbpActive = await page.evaluate(() => window.activeCurrency);
    expect(gbpActive).toBe('GBP');
  });

  test('Theme switcher toggles between Light and Dark themes', async ({ page }) => {
    const btnLight = page.locator('#btn-theme-light');
    const btnDark = page.locator('#btn-theme-dark');
    const body = page.locator('body');

    // Click Light
    await btnLight.click();
    await expect(body).toHaveClass(/theme-light/);
    await expect(body).not.toHaveClass(/theme-dark/);
    await expect(btnLight).toHaveClass(/active/);

    const lightBg = await body.evaluate(el => {
      return window.getComputedStyle(el).backgroundColor;
    });
    // #F8FAFC is rgb(248, 250, 252)
    expect(lightBg).toContain('248, 250, 252');

    // Click Dark
    await btnDark.click();
    await expect(body).toHaveClass(/theme-dark/);
    await expect(body).not.toHaveClass(/theme-light/);
    await expect(btnDark).toHaveClass(/active/);

    const darkBg = await body.evaluate(el => {
      return window.getComputedStyle(el).backgroundColor;
    });
    // #080A0F is rgb(8, 10, 15)
    expect(darkBg).toContain('8, 10, 15');
  });
});
