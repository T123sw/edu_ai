import { defineConfig } from 'playwright/test';
export default defineConfig({
  testDir: './tests/live-learning',
  testMatch: ['practice-generation.spec.ts', 'pbl-home.spec.ts', 'practice.spec.ts', 'preparation-progress.spec.ts'],
  workers: 2, timeout: 45000, reporter: [['list']],
  webServer: process.env.PRACTICE_GENERATION_URL ? undefined : {
    command: 'pnpm exec vite preview --outDir dist-practice-generation --host 127.0.0.1 --port 5220 --strictPort',
    url: 'http://127.0.0.1:5220', reuseExistingServer: false,
  },
  use: { baseURL: process.env.PRACTICE_GENERATION_URL || 'http://127.0.0.1:5220', screenshot: 'only-on-failure' },
});
