import { defineConfig } from 'playwright/test';
import base from './playwright.learning-navigation.config';
export default defineConfig({ ...base, expect: { timeout: 15000 }, testMatch: ['teaching-activities.spec.ts', 'source-navigation.spec.ts'], outputDir: './test-results/learning-activities',
  webServer: (base.webServer as { command: string; env?: Record<string, string> }[]).map((server, index) => index === 0
    ? { ...server, env: { ...server.env, LEARNING_BROWSER_ACTIVITY_FAILURE: '1' } } : server) });
