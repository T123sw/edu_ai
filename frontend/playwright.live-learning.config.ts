import { defineConfig } from 'playwright/test';
export default defineConfig({
  testDir: './tests/live-learning', outputDir: './test-results/live-learning',
  timeout: 180000, expect: { timeout: 20000 }, workers: 1, fullyParallel: false,
  reporter: [['list'], ['json', { outputFile: 'test-results/live-learning/results.json' }]],
  use: { reducedMotion: 'reduce', actionTimeout: 20000, baseURL: process.env.LIVE_FRONTEND_URL || 'http://127.0.0.1:5173', viewport: { width: 1440, height: 1000 }, locale: 'zh-CN', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
});
