import { defineConfig } from 'playwright/test';
import checks from './playwright.check-real.config';
export default defineConfig({ ...checks, testMatch: 'observation-real.spec.ts', outputDir: './test-results/observation-real' });
