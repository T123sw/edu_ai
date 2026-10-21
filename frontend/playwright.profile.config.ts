import { defineConfig } from 'playwright/test';
export default defineConfig({
  testDir: './tests/self-learning', testMatch: 'profile-redesign.spec.ts',
  outputDir: './test-results/profile-redesign', timeout: 45000, workers: 3,
  reporter: [['list']],
  use: { baseURL: process.env.PROFILE_TEST_URL || 'http://127.0.0.1:5307', locale: 'zh-CN', reducedMotion: 'reduce', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  projects: [
    { name: 'desktop1440', use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'compact1024', use: { viewport: { width: 1024, height: 768 } } },
    { name: 'mobile390', use: { viewport: { width: 390, height: 844 } } },
  ],
});
