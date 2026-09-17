import { defineConfig } from 'playwright/test';
import checks from './playwright.check-real.config';
export default defineConfig({ ...checks, testMatch: 'notification-real.spec.ts', outputDir: './test-results/notification-real',
  reporter: [['list'], ['json', { outputFile: 'test-results/notification-real/results.json' }]] });
