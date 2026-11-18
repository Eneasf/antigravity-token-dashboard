import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

test.describe('Plain Header & Now Tab Copy (Milestone 52 / Row 7 / U1 + U2)', () => {
  const screenshotDir = path.resolve('dashboard/test-artifacts/m52_screenshots');

  test.beforeAll(() => {
    if (!fs.existsSync(screenshotDir)) {
      fs.mkdirSync(screenshotDir, { recursive: true });
    }
  });

  test('Desktop (1440x900) header height < 72px and zero overflow', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/index.html');
    await page.waitForSelector('#sub-status-badge');

    const header = page.locator('header');
    const box = await header.boundingBox();
    expect(box).not.toBeNull();
    console.log(`Desktop header height: ${box.height}px (requirement: < 72px)`);
    expect(box.height).toBeLessThan(72);

    // Assert zero document overflow
    const docOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth <= document.documentElement.clientWidth;
    });
    expect(docOverflow).toBe(true);

    // Capture after screenshots
    await page.screenshot({ path: path.join(screenshotDir, 'after-1440-now.png') });

    await page.locator('#dock-tab-plan').click();
    await page.waitForTimeout(250);
    await page.screenshot({ path: path.join(screenshotDir, 'after-1440-plan.png') });
  });

  test('Desktop (1440x900) header status badges have zero text clipping and zero h1 overlap (Row 6 / U2)', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/index.html');
    await page.waitForSelector('#sub-status-badge');

    const clipped = await page.evaluate(() => {
      const badges = Array.from(document.querySelectorAll('header .badge, header #btn-open-plan-manager'))
        .filter(b => window.getComputedStyle(b).display !== 'none');
      return badges.filter(b => b.scrollWidth > b.clientWidth).map(b => b.id || b.className);
    });
    expect(clipped).toEqual([]);

    const overlap = await page.evaluate(() => {
      const h1 = document.querySelector('header h1').getBoundingClientRect();
      const firstBadge = document.querySelector('#sub-status-badge').getBoundingClientRect();
      return firstBadge.left - h1.right;
    });
    expect(overlap).toBeGreaterThanOrEqual(8);
  });


  test('Mobile (375x812) header height < 160px and zero overflow', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/index.html');
    await page.waitForSelector('#sub-status-badge');

    const header = page.locator('header');
    const box = await header.boundingBox();
    expect(box).not.toBeNull();
    console.log(`Mobile header height: ${box.height}px (requirement: < 160px)`);
    expect(box.height).toBeLessThan(160);

    // Assert zero document overflow
    const docOverflow = await page.evaluate(() => {
      return document.documentElement.scrollWidth <= document.documentElement.clientWidth;
    });
    expect(docOverflow).toBe(true);

    // Capture after screenshots
    await page.screenshot({ path: path.join(screenshotDir, 'after-375-now.png') });

    await page.locator('#mob-tab-plan').click();
    await page.waitForTimeout(250);
    await page.screenshot({ path: path.join(screenshotDir, 'after-375-plan.png') });
  });

  test('Header overflow menu opens and closes on click', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/index.html');
    await page.waitForSelector('#btn-header-overflow');

    const overflowMenu = page.locator('#header-overflow-menu');
    await expect(overflowMenu).toBeHidden();

    // Click overflow button to open
    await page.locator('#btn-header-overflow').click();
    await expect(overflowMenu).toBeVisible();

    // Click outside to close
    await page.locator('h1').click();
    await expect(overflowMenu).toBeHidden();
  });

  test('Plain language copy on Now tab without engineering jargon', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/index.html');
    await page.waitForSelector('#sub-status-badge');

    const bodyText = await page.locator('#view-now').innerText();

    // Plain English expectations
    expect(bodyText).toMatch(/Quota right now/i);
    expect(bodyText).toMatch(/Weekly pace/i);
    expect(bodyText).toMatch(/pace/i);
    expect(bodyText).toMatch(/Claude & GPT/i);

    // Forbidden jargon assertions
    const forbidden = [
      /contamination/i,
      /spillover/i,
      /governor/i,
      /dual-track/i,
      /dual-benchmark/i,
      /family routing/i,
      /isolation policy/i,
    ];
    for (const pattern of forbidden) {
      expect(bodyText).not.toMatch(pattern);
    }
  });
});
