import { defineConfig } from 'playwright/test';
export default defineConfig({ testDir: './tests/live-learning', testMatch: 'check-real.spec.ts', workers: 1,
  timeout: 240000, expect: { timeout: 30000 }, outputDir: './test-results/check-real',
  reporter: [['list'], ['json', { outputFile: 'test-results/check-real/results.json' }]],
  use: { baseURL: 'http://127.0.0.1:5198', trace: 'on', screenshot: 'only-on-failure' } });
