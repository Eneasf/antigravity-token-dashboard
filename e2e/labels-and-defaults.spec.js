import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

test.describe('Labels, Simulator Defaults & Light Theme E2E (Milestone 50)', () => {
  test('Theme default is light, labels are dynamic, simulator defaults to payload tier', async ({ page }) => {
    const screenshotDir = path.resolve('dashboard/test-artifacts/m50_screenshots');
    if (!fs.existsSync(screenshotDir)) fs.mkdirSync(screenshotDir, { recursive: true });

    // 1. Initial load with cleared localStorage to verify default theme
    await page.addInitScript(() => {
      localStorage.clear();
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/index.html');
    await page.waitForSelector('#sub-status-badge');

    // Verify Light Mode is default
    const docTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    expect(docTheme).toBe('light');

    // Verify Header status badge is tier-calibrated (Ultra tier in live payload)
    const statusText = await page.locator('#sub-status-badge').innerText();
    expect(statusText).not.toContain('Safe in Pro Quota');
    expect(statusText).toMatch(/Safe (?:in|·) Ultra Quota|Burning AI Credits|Recovered \(Cooldown\)/);

    // Verify Billing renewal badge is dynamic
    const billingText = await page.locator('#billing-cycle-badge').innerText();
    expect(billingText).not.toContain('Renews 24 Sep');
    expect(billingText).toContain('Billing: Renews');

    // Verify Data freshness pill
    const freshnessText = await page.locator('#data-freshness-badge').innerText();
    expect(freshnessText).toContain('Local · read-only');

    // Capture AFTER screenshot 1440x900 Now Tab
    await page.screenshot({ path: path.join(screenshotDir, 'after-1440-now.png') });

    // 2. Navigate to Plan tab
    await page.locator('#dock-tab-plan').click();
    await page.waitForTimeout(300);

    // Verify Simulator default plan tier matches payload tier ('ultra_5x')
    const selectedPlan = await page.locator('#sim-plan-select').inputValue();
    expect(selectedPlan).toBe('ultra_5x');

    // Verify plain English labels on sliders (zero LaTeX)
    const promptLabel = await page.locator('label[for="sim-prompt-slider"]').innerText();
    expect(promptLabel).toBe('Average prompt size (tokens)');
    const paceLabel = await page.locator('label[for="sim-pace-slider"]').innerText();
    expect(paceLabel).toBe('Minutes between turns');

    // Trigger burst exhaustion by selecting Pro tier and maxing prompt/turns with 0% cache
    await page.locator('#sim-plan-select').selectOption('pro');
    await page.locator('#sim-prompt-slider').fill('500000');
    await page.locator('#sim-prompt-slider').dispatchEvent('input');
    await page.locator('#sim-cache-slider').fill('0');
    await page.locator('#sim-cache-slider').dispatchEvent('input');
    await page.locator('#sim-turns-slider').fill('150');
    await page.locator('#sim-turns-slider').dispatchEvent('input');
    await page.waitForTimeout(200);

    // Verify recommendation contains "hard stop" because use_ai_credits is false
    const recText = await page.locator('#sim-recommendation').innerText();
    expect(recText).toContain('hard stop');

    // Capture AFTER screenshot 1440x900 Plan Tab
    await page.screenshot({ path: path.join(screenshotDir, 'after-1440-plan.png') });

    // 3. Mobile Viewport (375x812)
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/index.html');
    await page.waitForSelector('#sub-status-badge');
    await page.screenshot({ path: path.join(screenshotDir, 'after-375-now.png') });

    await page.locator('#mob-tab-plan').click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(screenshotDir, 'after-375-plan.png') });
  });
});
