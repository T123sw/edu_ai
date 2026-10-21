import { defineConfig } from 'playwright/test';
export default defineConfig({
  testDir: './tests/live-learning', testMatch: 'pbl*.spec.ts', workers: 1,
  timeout: 120000, expect: { timeout: 90000 }, reporter: [['list']],
  use: { baseURL: process.env.PBL_FRONTEND_URL || 'http://127.0.0.1:5207', screenshot: 'only-on-failure' },
  webServer: process.env.PBL_FRONTEND_URL ? undefined : {
    command: 'pnpm exec vite --host 127.0.0.1 --port 5207 --strictPort',
    url: 'http://127.0.0.1:5207', reuseExistingServer: false, timeout: 120000,
  },
});
