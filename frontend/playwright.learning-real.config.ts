import { defineConfig } from 'playwright/test';
import base from './playwright.learning-acceptance.config';
export default defineConfig({ ...base, testMatch: 'agent-real.spec.ts', outputDir: './test-results/learning-real', timeout: 360000,
  webServer: (base.webServer as { command: string; env?: Record<string, string> }[]).map((server, index) => index === 0 ? { ...server, env: { ...server.env, LEARNING_BROWSER_REAL: '1' }, timeout: 90000 } : server) });
