import { defineConfig } from 'playwright/test';
import base from './playwright.learning-acceptance.config';
export default defineConfig({ ...base, testMatch: 'ppt-context.spec.ts', outputDir: './test-results/learning-ppt',
  webServer: (base.webServer as { command: string; env?: Record<string, string> }[]).map((server, index) => index === 0
    ? { ...server, env: { ...server.env, LEARNING_BROWSER_PPT_CONTEXT: '1' } } : server) });
