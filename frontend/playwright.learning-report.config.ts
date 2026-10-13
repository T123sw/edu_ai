import { defineConfig } from 'playwright/test';
import base from './playwright.learning-agent.config';
const production = process.env.REPORT_PRODUCTION_URL;
export default defineConfig({ ...base, testMatch: 'report-context.spec.ts', outputDir: './test-results/learning-report',
  use: { ...base.use, baseURL: production || 'http://127.0.0.1:5199' },
  webServer: [
    { command: 'python -m uvicorn tests.self_learning.browser_app:app --host 127.0.0.1 --port 8019', cwd: '../backend/src',
      url: 'http://127.0.0.1:8019/docs', reuseExistingServer: false, env: { LEARNING_BROWSER_AGENT: '1', LEARNING_BROWSER_ORIGIN: 'http://127.0.0.1:5199' } },
    ...(production ? [] : [{ command: 'pnpm dev --host 127.0.0.1 --port 5199 --strictPort', url: 'http://127.0.0.1:5199', reuseExistingServer: false,
      env: { VITE_API_BASE_URL: 'http://127.0.0.1:8019' } }]),
  ],
});
