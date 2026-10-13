import { defineConfig } from 'playwright/test';
export default defineConfig({
  testDir: './tests/live-learning', testMatch: 'appearance.spec.ts',
  outputDir: './test-results/appearance', workers: 1, timeout: 45000,
  use: { baseURL: process.env.APPEARANCE_BASE_URL || 'http://127.0.0.1:5301', viewport: { width: 1440, height: 900 }, trace: 'retain-on-failure' },
  webServer: process.env.APPEARANCE_BASE_URL ? undefined : { command: 'pnpm dev --host 127.0.0.1 --port 5301 --strictPort',
    url: 'http://127.0.0.1:5301', reuseExistingServer: false },
});
