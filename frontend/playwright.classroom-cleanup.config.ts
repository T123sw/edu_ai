import { defineConfig } from 'playwright/test';
import base from './playwright.learning-ppt.config';

export default defineConfig({ ...base,
  testMatch: ['classroom-cleanup.spec.ts', 'ppt-context.spec.ts'],
  outputDir: './test-results/classroom-cleanup',
  use: { ...base.use, baseURL: 'http://127.0.0.1:5297' },
  webServer: (base.webServer as { command: string; url: string; env?: Record<string, string> }[]).map(server => ({
    ...server,
    command: server.command.replace('8016', '8117').replace('5196', '5297'),
    url: server.url.replace('8016', '8117').replace('5196', '5297'),
    env: { ...server.env, LEARNING_BROWSER_ORIGIN: 'http://127.0.0.1:5297',
      ...(server.env?.VITE_API_BASE_URL ? { VITE_API_BASE_URL: 'http://127.0.0.1:8117' } : {}) },
  })),
});
