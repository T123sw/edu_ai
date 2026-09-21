import { defineConfig } from 'playwright/test';
const baseURL = process.env.PREPARATION_FRONTEND_URL || 'http://127.0.0.1:5199';
if (!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(baseURL)) throw new Error('Dedicated loopback frontend required');
export default defineConfig({
  testDir: './tests/live-learning', testMatch: 'preparation-chain-real.spec.ts',
  workers: 1, retries: 0, timeout: 2_400_000, expect: { timeout: 30_000 },
  outputDir: './test-results/preparation-chain-real',
  reporter: [['list'], ['json', { outputFile: 'test-results/preparation-chain-real/results.json' }]],
  use: { baseURL, actionTimeout: 30_000, trace: 'on', screenshot: 'on', video: 'retain-on-failure' },
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'narrow', use: { viewport: { width: 390, height: 844 } } },
  ],
});
