import { defineConfig } from 'playwright/test';
export default defineConfig({ testDir: './tests/live-learning', testMatch: 'preferences-real.spec.ts', workers: 1, timeout: 90000,
  expect: { timeout: 30000 }, outputDir: './test-results/preferences-real',
  reporter: [['list'], ['json', { outputFile: 'test-results/preferences-real/results.json' }]],
  use: { baseURL: 'http://127.0.0.1:5198', actionTimeout: 30000, viewport: { width: 1440, height: 1000 }, trace: 'on', screenshot: 'only-on-failure' },
});
