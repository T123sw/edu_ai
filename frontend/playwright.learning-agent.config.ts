import { defineConfig } from 'playwright/test';
import base from './playwright.learning-session.config';
export default defineConfig({ ...base, testMatch: 'agent-turns.spec.ts', outputDir: './test-results/learning-agent',
  webServer: (base.webServer as { command: string; env?: Record<string, string> }[]).map((server, index) => index === 0 ? { ...server, env: { ...server.env, LEARNING_BROWSER_AGENT: '1' } } : server) });
