import { test, expect } from '@playwright/test';

test.describe('Simulator & Plan Interactions', () => {
  test('changing custom fee to 500.00 updates risk badge to Critical Risk', async ({ page }) => {
    // Navigate to dashboard
    await page.goto('/index.html');
    await page.waitForLoadState('networkidle');

    // Click #dock-tab-plan to open Plan and Simulator view
    await page.locator('#dock-tab-plan').click();
    await expect(page.locator('#view-plan')).toBeVisible();

    // Select Custom Capacity Plan preset so custom fields become visible
    await page.locator('#plan-tier-select').selectOption('custom');

    // Change the value of #custom-fee-usd to '500.00' (using locator.fill)
    const customFeeLocator = page.locator('#custom-fee-usd');
    await customFeeLocator.fill('500.00');

    // Click #btn-save-plan
    await page.locator('#btn-save-plan').click();

    // Assert that #sim-risk-badge has the text 'Critical Risk' and contains the class 'red'
    const riskBadge = page.locator('#sim-risk-badge');
    await expect(riskBadge).toHaveText('Critical Risk');
    await expect(riskBadge).toHaveClass(/red/);
  });
});
