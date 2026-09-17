import { defineConfig } from 'playwright/test';
export default defineConfig({
  testDir: './tests/live-learning', testMatch: 'agent-full.spec.ts', workers: 1,
  timeout: 600000, expect: { timeout: 30000 }, outputDir: './test-results/agent-full',
  reporter: [['list'], ['json', { outputFile: 'test-results/agent-full/results.json' }]],
  use: { baseURL: 'http://127.0.0.1:5198', actionTimeout: 30000, viewport: { width: 1440, height: 1000 }, trace: 'on', screenshot: 'only-on-failure' },
});
