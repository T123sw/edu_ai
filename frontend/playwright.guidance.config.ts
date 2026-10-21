import { defineConfig } from 'playwright/test';
export default defineConfig({testDir:'./tests/live-learning',testMatch:'practice-guidance.spec.ts',workers:1,timeout:60000,reporter:[['list']],use:{baseURL:process.env.PRACTICE_FRONTEND_URL||'http://127.0.0.1:5236',deviceScaleFactor:2,screenshot:'only-on-failure'}});
