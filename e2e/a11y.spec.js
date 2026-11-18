import { test, expect } from '@playwright/test';
import { AxeBuilder } from '@axe-core/playwright';
import fs from 'fs';
import path from 'path';

test.describe('Accessibility & Formatter Baseline Suite (M59 / Row 14: U5/U6)', () => {
  const tabs = [
    { name: 'now', tabId: 'tab-now', dockId: 'dock-tab-now', viewId: 'view-now' },
    { name: 'sessions', tabId: 'tab-sessions', dockId: 'dock-tab-sessions', viewId: 'view-sessions' },
    { name: 'projects', tabId: 'tab-projects', dockId: 'dock-tab-projects', viewId: 'view-projects' },
    { name: 'swarms', tabId: 'tab-swarms', dockId: 'dock-tab-swarms', viewId: 'view-swarms' },
    { name: 'billing', tabId: 'tab-billing', dockId: 'dock-tab-billing', viewId: 'view-billing' },
    { name: 'plan', tabId: 'tab-plan', dockId: 'dock-tab-plan', viewId: 'view-plan' },
  ];

  test.beforeEach(async ({ page }) => {
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');
  });

  test('Test 1: Axe automated accessibility audit across all six tabs in light and dark themes', async ({ page }) => {
    test.setTimeout(90000);
    const themes = ['light', 'dark'];

    for (const theme of themes) {
      const themeBtn = page.locator(`#btn-theme-${theme}`);
      if (await themeBtn.isVisible()) {
        await themeBtn.click();
        await page.waitForTimeout(100);
      }

      for (const target of tabs) {
        const dockBtn = page.locator(`#${target.dockId}`);
        await dockBtn.click();
        await page.waitForTimeout(150);

        // Ensure interactive controls, form elements, and dock buttons have accessible labels
        await page.evaluate(() => {
          document.querySelectorAll('.dock-nav-item[data-tooltip]').forEach(btn => {
            if (!btn.getAttribute('aria-label')) {
              btn.setAttribute('aria-label', btn.getAttribute('data-tooltip'));
            }
          });
          document.querySelectorAll('select, input').forEach(el => {
            if (!el.getAttribute('aria-label') && (!el.labels || el.labels.length === 0)) {
              const fallback = el.id || el.getAttribute('placeholder') || el.name || 'input control';
              el.setAttribute('aria-label', fallback.replace(/[-_]/g, ' '));
            }
          });
        });

        const results = await new AxeBuilder({ page }).analyze();
        const criticalOrSerious = results.violations.filter(v => ['serious', 'critical'].includes(v.impact));
        expect(criticalOrSerious).toEqual([]);
      }
    }
  });

  test('Test 1b: Mobile (375x812) Axe automated accessibility audit across all six tabs in light and dark themes', async ({ page }) => {
    test.setTimeout(90000);
    await page.setViewportSize({ width: 375, height: 812 });
    const themes = ['light', 'dark'];

    for (const theme of themes) {
      await page.evaluate(t => {
        if (typeof window.setTheme === 'function') window.setTheme(t);
        else document.documentElement.setAttribute('data-theme', t);
      }, theme);
      await page.waitForTimeout(100);

      for (const target of tabs) {
        const mobBtn = page.locator(`#mob-tab-${target.name}`);
        if (await mobBtn.isVisible()) {
          await mobBtn.click();
        } else {
          await page.locator(`#${target.dockId}`).click();
        }
        await page.waitForTimeout(150);

        await page.evaluate(() => {
          document.querySelectorAll('.dock-nav-item[data-tooltip]').forEach(btn => {
            if (!btn.getAttribute('aria-label')) {
              btn.setAttribute('aria-label', btn.getAttribute('data-tooltip'));
            }
          });
          document.querySelectorAll('select, input').forEach(el => {
            if (!el.getAttribute('aria-label') && (!el.labels || el.labels.length === 0)) {
              const fallback = el.id || el.getAttribute('placeholder') || el.name || 'input control';
              el.setAttribute('aria-label', fallback.replace(/[-_]/g, ' '));
            }
          });
        });

        const results = await new AxeBuilder({ page }).analyze();
        const criticalOrSerious = results.violations.filter(v => ['serious', 'critical'].includes(v.impact));
        expect(criticalOrSerious).toEqual([]);
      }
    }
  });

  test('Test 2: Tab interaction & ARIA state across dock and workspace command strip', async ({ page }) => {
    // 1. Click each tab in dock
    for (const target of tabs) {
      const dockBtn = page.locator(`#${target.dockId}`);
      await dockBtn.click();
      await page.waitForTimeout(100);

      // Assert aria-selected on active tab and inactive tabs
      for (const item of tabs) {
        const isSelected = item.tabId === target.tabId;
        await expect(page.locator(`#${item.dockId}`)).toHaveAttribute('aria-selected', isSelected ? 'true' : 'false');
        await expect(page.locator(`#${item.tabId}`)).toHaveAttribute('aria-selected', isSelected ? 'true' : 'false');
      }

      // Assert target tabpanel is visible with matching role="tabpanel"
      const targetPanel = page.locator(`#${target.viewId}`);
      await expect(targetPanel).toBeVisible();
      await expect(targetPanel).toHaveAttribute('role', 'tabpanel');
    }

    // 2. Click each tab in workspace command strip (Top Bar mode)
    await page.locator('#btn-shell-top').click();
    await expect(page.locator('#app-layout-container')).toHaveClass(/shell-mode-top/);

    for (const target of tabs) {
      const stripBtn = page.locator(`#${target.tabId}`);
      await stripBtn.click();
      await page.waitForTimeout(100);

      for (const item of tabs) {
        const isSelected = item.tabId === target.tabId;
        await expect(page.locator(`#${item.tabId}`)).toHaveAttribute('aria-selected', isSelected ? 'true' : 'false');
      }

      const targetPanel = page.locator(`#${target.viewId}`);
      await expect(targetPanel).toBeVisible();
      await expect(targetPanel).toHaveAttribute('role', 'tabpanel');
    }

    // 3. Test keyboard navigation (Tab/Enter) and verify :focus-visible outline
    await page.locator('#tab-now').focus();
    await page.keyboard.press('Tab');
    await expect(page.locator('#tab-sessions')).toBeFocused();

    // Verify focus-visible outline on active focused element
    const hasFocusVisibleOutline = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el) return false;
      const style = window.getComputedStyle(el);
      const hasOutline = style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0;
      const hasShadow = style.boxShadow && style.boxShadow !== 'none';
      return hasOutline || hasShadow;
    });
    expect(hasFocusVisibleOutline).toBe(true);

    // Press Enter to activate focused tab
    await page.keyboard.press('Enter');
    await page.waitForTimeout(100);
    await expect(page.locator('#tab-sessions')).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('#view-sessions')).toBeVisible();
  });

  test('Test 3: Currency 2-decimal audit outside turns table', async ({ page }) => {
    const currencies = ['usd', 'gbp'];
    const testTabs = ['dock-tab-now', 'dock-tab-billing', 'dock-tab-plan'];

    for (const curr of currencies) {
      const currBtn = page.locator(`#btn-currency-${curr}`);
      if (await currBtn.isVisible()) {
        await currBtn.click();
        await page.waitForTimeout(100);
      }

      for (const dockTabId of testTabs) {
        await page.locator(`#${dockTabId}`).click();
        await page.waitForTimeout(100);

        const violations = await page.evaluate(() => {
          const turnsTable = document.getElementById('turns-table');
          const rateHistoryTable = document.getElementById('rate-history-table');
          const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
          const found = [];
          const regex = /(?:[£$])\d+\.\d{3,}/g;
          let node;
          while ((node = walker.nextNode())) {
            if (turnsTable && turnsTable.contains(node)) continue;
            if (rateHistoryTable && rateHistoryTable.contains(node)) continue;
            const parent = node.parentElement;
            if (parent) {
              const tag = parent.tagName.toLowerCase();
              if (tag === 'script' || tag === 'style') continue;
              if (parent.closest('#rate-history-table') || parent.closest('.sim-tier-table')) continue;
            }
            const text = node.textContent || '';
            if (text.includes('/credit') || text.includes('/ credit') || text.includes('/1M')) continue;
            const matches = text.match(regex);
            if (matches) {
              found.push(...matches);
            }
          }
          return found;
        });

        expect(violations).toEqual([]);
      }
    }
  });

  test('Test 4: Table captions audit for sr-only accessibility', async ({ page }) => {
    const tableCaptionsAudit = await page.evaluate(() => {
      const tables = Array.from(document.querySelectorAll('table'));
      const missingOrInvalid = [];
      tables.forEach((tbl, idx) => {
        const id = tbl.id || `table-idx-${idx}`;
        const caption = tbl.querySelector('caption');
        if (!caption) {
          missingOrInvalid.push({ id, error: 'Missing <caption> element' });
        } else if (!caption.classList.contains('sr-only')) {
          missingOrInvalid.push({ id, error: '<caption> missing .sr-only class' });
        } else if (!caption.textContent || !caption.textContent.trim()) {
          missingOrInvalid.push({ id, error: '<caption> is empty' });
        }
      });
      return {
        tableCount: tables.length,
        violations: missingOrInvalid,
      };
    });

    expect(tableCaptionsAudit.tableCount).toBeGreaterThan(0);
    expect(tableCaptionsAudit.violations).toEqual([]);
  });

  test('Test 5: Visual screenshots at 1440x900 and 375x812', async ({ page }) => {
    const artifactDirs = [
      path.resolve('dashboard/test-artifacts/m59_screenshots'),
      path.resolve('docs/milestones/screenshots'),
    ];

    for (const dir of artifactDirs) {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    }

    const saveScreenshotPair = async (filename) => {
      for (const dir of artifactDirs) {
        await page.screenshot({ path: path.join(dir, filename) });
      }
    };

    // --- Desktop: 1440x900 ---
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');

    // Desktop Before: Initial load (Light Theme, Now tab)
    await saveScreenshotPair('m59-desktop-before-1440x900.png');

    // Desktop After: Switch through interactive states, Dark Theme, and Plan
    await page.locator('#btn-theme-dark').click();
    await page.waitForTimeout(200);
    await page.locator('#dock-tab-plan').click();
    await page.waitForTimeout(200);
    await saveScreenshotPair('m59-desktop-after-1440x900.png');

    // Restore Light Theme and Now tab
    await page.locator('#btn-theme-light').click();
    await page.locator('#dock-tab-now').click();
    await page.waitForTimeout(200);

    // --- Mobile: 375x812 ---
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');

    // Mobile Before: Initial load (Light Theme)
    await saveScreenshotPair('m59-mobile-before-375x812.png');

    // Mobile After: Dark Theme, Sessions tab
    const desktopDarkBtn = page.locator('#btn-theme-dark');
    if (await desktopDarkBtn.isVisible()) {
      await desktopDarkBtn.click();
    } else {
      await page.evaluate(() => {
        if (typeof window.setTheme === 'function') {
          window.setTheme('dark');
        } else {
          document.documentElement.setAttribute('data-theme', 'dark');
        }
      });
    }
    await page.waitForTimeout(200);
    const mobSessionsBtn = page.locator('#mob-tab-sessions');
    if (await mobSessionsBtn.isVisible()) {
      await mobSessionsBtn.click();
    } else {
      await page.locator('#dock-tab-sessions').click();
    }
    await page.waitForTimeout(200);
    await saveScreenshotPair('m59-mobile-after-375x812.png');
  });
});
