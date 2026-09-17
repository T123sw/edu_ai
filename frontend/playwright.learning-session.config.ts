import { defineConfig } from 'playwright/test';
export default defineConfig({
  testDir: './tests/live-learning', testMatch: 'agent-session.spec.ts',
  outputDir: './test-results/learning-session', workers: 1, timeout: 60000,
  use: { baseURL: 'http://127.0.0.1:5196', viewport: { width: 1440, height: 1000 }, trace: 'retain-on-failure' },
  webServer: [
    { command: 'python -m uvicorn tests.self_learning.browser_app:app --host 127.0.0.1 --port 8016', cwd: '../backend/src',
      url: 'http://127.0.0.1:8016/docs', reuseExistingServer: false },
    { command: 'pnpm dev --host 127.0.0.1 --port 5196 --strictPort',
      url: 'http://127.0.0.1:5196', reuseExistingServer: false, env: { VITE_API_BASE_URL: 'http://127.0.0.1:8016' } },
  ],
});
