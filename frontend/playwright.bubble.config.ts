import { defineConfig } from 'playwright/test';
export default defineConfig({
  testDir: './tests/bubble-prototype', workers: 1, timeout: 30000,
  reporter: [['list']], outputDir: '../.runtime/bubble-prototype-results',
  use: { baseURL: process.env.BUBBLE_APP_URL || 'http://127.0.0.1:5250', screenshot: 'only-on-failure', deviceScaleFactor: 2 },
});
