import { defineConfig } from 'playwright/test';

export default defineConfig({
  testDir: './tests/live-learning',
  testMatch: 'video-chat.spec.ts',
  workers: 1,
  timeout: 45000,
  expect: { timeout: 15000 },
  reporter: [['list']],
  use: { baseURL: process.env.VIDEO_CHAT_URL || 'http://127.0.0.1:5262', viewport: { width: 1440, height: 1000 }, screenshot: 'only-on-failure' },
  webServer: process.env.VIDEO_CHAT_URL ? undefined : {
    command: 'pnpm dev --host 127.0.0.1 --port 5262 --strictPort',
    url: 'http://127.0.0.1:5262',
    reuseExistingServer: false,
  },
});
