import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

test.describe('Visual Screenshot Artifact Generation', () => {
  test('Generate full visual proof suite across tabs, themes, and shell modes', async ({ page }) => {
    const screenshotDir = path.resolve('dashboard/test-artifacts/screenshots');
    if (!fs.existsSync(screenshotDir)) {
      fs.mkdirSync(screenshotDir, { recursive: true });
    }

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');

    // 1. Now Tab (Light Theme, Sidebar Collapsed)
    await page.locator('#btn-theme-light').click();
    await page.locator('#dock-tab-now').click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(screenshotDir, '01-now-light-sidebar.png') });

    // 2. Now Tab (Dark Theme, Sidebar Collapsed)
    await page.locator('#btn-theme-dark').click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(screenshotDir, '02-now-dark-sidebar.png') });

    // 3. Now Tab (Light Theme, Sidebar Expanded)
    await page.locator('#btn-theme-light').click();
    await page.locator('#btn-sidebar-collapse-footer').click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(screenshotDir, '03-now-light-sidebar-expanded.png') });
    // Collapse back
    await page.locator('#btn-sidebar-collapse-footer').click();
    await page.waitForTimeout(300);

    // 4. Now Tab (Light Theme, Top Bar Mode)
    await page.locator('#btn-shell-top').click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(screenshotDir, '04-now-light-topbar.png') });
    // Switch back to Sidebar mode
    await page.locator('#btn-shell-side').click();
    await page.waitForTimeout(200);

    // 5. Sessions Tab (Light Theme)
    await page.locator('#dock-tab-sessions').click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(screenshotDir, '05-sessions-light.png') });

    // 6. Projects Tab (Light Theme)
    await page.locator('#dock-tab-projects').click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(screenshotDir, '06-projects-light.png') });

    // 7. Swarms Tab (Light Theme)
    await page.locator('#dock-tab-swarms').click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(screenshotDir, '07-swarms-light.png') });

    // 8. Billing Tab (Light Theme)
    await page.locator('#dock-tab-billing').click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(screenshotDir, '08-billing-light.png') });

    // 9. Plan Tab (Light Theme)
    await page.locator('#dock-tab-plan').click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(screenshotDir, '09-plan-light.png') });

    // 10. Plan Tab (Dark Theme)
    await page.locator('#btn-theme-dark').click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: path.join(screenshotDir, '10-plan-dark.png') });
  });
});
