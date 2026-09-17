import { defineConfig } from 'playwright/test';
import base from './playwright.learning-preparation.config';
export default defineConfig({ ...base, testMatch: 'agent-acceptance.spec.ts', outputDir: './test-results/learning-acceptance',
  webServer: (base.webServer as { command: string; env?: Record<string, string> }[]).map((server, index) => index === 0 ? { ...server, env: { ...server.env, LEARNING_BROWSER_ACCEPTANCE: '1' } } : server) });
