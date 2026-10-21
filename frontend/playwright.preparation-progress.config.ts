import { defineConfig } from 'playwright/test';

export default defineConfig({
  testDir: './tests/live-learning',
  testMatch: ['preparation-progress.spec.ts', 'task-center.spec.ts', 'preparation-center-sync.spec.ts'],
  workers: 1,
  timeout: 45000,
  expect: { timeout: 10000 },
  outputDir: './test-results/preparation-progress',
  reporter: [['list']],
  use: { baseURL: process.env.PROGRESS_FRONTEND_URL || 'http://127.0.0.1:5199', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: process.env.PROGRESS_FRONTEND_URL ? undefined : {
    command: 'pnpm exec vite preview --outDir dist-preparation-progress --host 127.0.0.1 --port 5199 --strictPort',
    url: 'http://127.0.0.1:5199', reuseExistingServer: false,
  },
});
