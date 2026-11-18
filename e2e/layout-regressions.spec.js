import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';

let cachedDataJs = null;
let cachedMetaJs = null;

function getFixtureScripts() {
  if (!cachedDataJs) {
    const jsonStr = execSync(
      'python3 scripts/export_dashboard.py --antigravity-dir tests/fixtures/antigravity --no-live-quota --reference-time 2026-09-05T14:30:00Z --json',
      { encoding: 'utf8', maxBuffer: 50 * 1024 * 1024 }
    );
    const payload = JSON.parse(jsonStr);
    cachedDataJs = `window.__TELEMETRY_DATA__ = ${jsonStr};\nwindow.__ANTIGRAVITY_DASHBOARD_DATA__ = window.__TELEMETRY_DATA__;\n`;
    cachedMetaJs = `window.__TELEMETRY_META__ = ${JSON.stringify({
      payload_sha1: 'fixture_deterministic_hash',
      payload_bytes: Buffer.byteLength(jsonStr, 'utf8'),
      conversations_count: (payload.conversations || []).length,
      generated_at: payload.temporal?.resolved_at_utc || '2026-09-05T14:30:00Z',
      ticker: payload.live_ticker || {}
    })};\n`;
  }
  return { dataJs: cachedDataJs, metaJs: cachedMetaJs };
}

test.describe('Layout & Viewport Regressions', () => {
  test.beforeEach(async ({ page }) => {
    const { dataJs, metaJs } = getFixtureScripts();
    await page.route('**/data.js*', route => {
      route.fulfill({ status: 200, contentType: 'application/javascript', body: dataJs });
    });
    await page.route('**/meta.js*', route => {
      route.fulfill({ status: 200, contentType: 'application/javascript', body: metaJs });
    });
  });

  test('at 1440x900 viewport: header h1 is not clipped (scrollWidth <= clientWidth)', async ({ page }) => {
    // (d) at 1440x900 viewport:
    // header h1.scrollWidth <= header h1.clientWidth (no clipping of the title)
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/index.html', { waitUntil: 'load' });
    await page.waitForSelector('header h1');

    const h1 = page.locator('header h1');
    await expect(h1).toBeVisible();

    const isNotClipped = await h1.evaluate(el => el.scrollWidth <= el.clientWidth);
    expect(isNotClipped).toBe(true);
  });

  test('at 375x812 viewport: every card inside #executive-hero-card fits within section bounds', async ({ page }) => {
    // (e) at 375x812 viewport:
    // every card inside #executive-hero-card has its right edge <= section right edge (box.x + box.width <= secBox.x + secBox.width)
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/index.html', { waitUntil: 'load' });
    await page.waitForSelector('#executive-hero-card');

    const section = page.locator('#executive-hero-card');
    await expect(section).toBeVisible();

    const secBox = await section.boundingBox();
    expect(secBox).not.toBeNull();
    const secRightEdge = secBox.x + secBox.width;

    const cards = section.locator('.exec-panel');
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < count; i++) {
      const card = cards.nth(i);
      if (await card.isVisible()) {
        const box = await card.boundingBox();
        expect(box).not.toBeNull();
        const cardRightEdge = box.x + box.width;
        // Allow at most 1px sub-pixel rounding
        expect(cardRightEdge).toBeLessThanOrEqual(secRightEdge + 1);
      }
    }
  });
});
