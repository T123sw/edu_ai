import { defineConfig } from 'playwright/test';
import base from './playwright.learning-enrichment.config';
export default defineConfig({ ...base, testMatch: 'preparation-handoff.spec.ts', outputDir: './test-results/learning-preparation',
  webServer: (base.webServer as { command: string; env?: Record<string, string> }[]).map((server, index) => index === 0 ? { ...server, env: { ...server.env, LEARNING_BROWSER_PREPARATION: '1' } } : server) });
