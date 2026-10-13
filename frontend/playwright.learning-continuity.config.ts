import { defineConfig } from 'playwright/test';
import base from './playwright.learning-enrichment.config';
export default defineConfig({ ...base, testMatch: 'teaching-continuity.spec.ts', outputDir: './test-results/learning-continuity',
  webServer: (base.webServer as { command: string; env?: Record<string, string> }[]).map((server, index) => index === 0
    ? { ...server, env: { ...server.env, LEARNING_BROWSER_CONTINUITY: '1' } } : server) });
