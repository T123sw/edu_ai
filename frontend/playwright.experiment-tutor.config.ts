import { defineConfig } from 'playwright/test';
export default defineConfig({ testDir: './tests/live-learning', testMatch: ['experiment.spec.ts', 'experiment-pages.spec.ts'], workers: 1, timeout: 45000, reporter: [['list']], use: { baseURL: process.env.EXPERIMENT_TUTOR_URL || 'http://127.0.0.1:5251', screenshot: 'only-on-failure' } });
