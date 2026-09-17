import { defineConfig } from 'playwright/test';
import base from './playwright.learning-agent.config';
export default defineConfig({ ...base, testMatch: ['understanding-check.spec.ts', 'learning-preferences.spec.ts'], outputDir: './test-results/learning-enrichment',
  webServer: (base.webServer as { command: string; env?: Record<string, string> }[]).map((server, index) => index === 0 ? { ...server, env: { ...server.env, LEARNING_BROWSER_ENRICHMENT: '1' } } : server) });
