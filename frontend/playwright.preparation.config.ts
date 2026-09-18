import { defineConfig } from 'playwright/test';
export default defineConfig({
  testDir: './tests/live-learning', testMatch: 'preparation.spec.ts', workers: 1,
  outputDir: './test-results/preparation', timeout: 60000,
  reporter: [['list'], ['json', { outputFile: 'test-results/preparation/results.json' }]],
  use: { baseURL: 'http://127.0.0.1:5197', trace: 'on', screenshot: 'only-on-failure' },
  webServer: { command: 'pnpm dev --host 127.0.0.1 --port 5197 --strictPort', url: 'http://127.0.0.1:5197', reuseExistingServer: false },
});
