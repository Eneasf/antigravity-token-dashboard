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

test.describe('App JS Split & Demo Unification E2E (Milestone 53 / Row 7.5)', () => {
  test('All 6 tabs render cleanly with active views on modular script architecture', async ({ page }) => {
    const { dataJs, metaJs } = getFixtureScripts();
    await page.route('**/data.js*', route => {
      route.fulfill({ status: 200, contentType: 'application/javascript', body: dataJs });
    });
    await page.route('**/meta.js*', route => {
      route.fulfill({ status: 200, contentType: 'application/javascript', body: metaJs });
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/index.html', { waitUntil: 'load' });
    await page.waitForTimeout(500);

    const tabs = [
      { name: 'now', dockId: 'dock-tab-now', viewId: 'view-now', keySelector: '#executive-hero-card' },
      { name: 'sessions', dockId: 'dock-tab-sessions', viewId: 'view-sessions', keySelector: '#convo-search-input' },
      { name: 'projects', dockId: 'dock-tab-projects', viewId: 'view-projects', keySelector: '#projects-table' },
      { name: 'swarms', dockId: 'dock-tab-swarms', viewId: 'view-swarms', keySelector: '#kpi-swarm-count' },
      { name: 'billing', dockId: 'dock-tab-billing', viewId: 'view-billing', keySelector: '#billing-history-table' },
      { name: 'plan', dockId: 'dock-tab-plan', viewId: 'view-plan', keySelector: '#plan-tier-select' },
    ];

    for (const tab of tabs) {
      if (tab.name !== 'now') {
        await page.locator('#' + tab.dockId).click();
        await page.waitForTimeout(200);
      }
      const activeView = page.locator('#' + tab.viewId);
      await expect(activeView).toBeVisible();
      await expect(page.locator(tab.keySelector)).toBeVisible();

      const innerHtml = await activeView.innerHTML();
      expect(innerHtml.trim().length).toBeGreaterThan(100);
    }
  });

  test('index.html?demo=1 activates demo showcase mode and displays banner', async ({ page }) => {
    await page.goto('/index.html?demo=1', { waitUntil: 'load' });
    await page.waitForTimeout(600);

    // Verify demo banner is injected and visible
    const banner = page.locator('#demo-mode-banner');
    await expect(banner).toBeVisible();
    await expect(banner).toContainText('Interactive Showcase Demo');
  });
});
