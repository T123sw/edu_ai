import { defineConfig } from 'playwright/test';
import sessions from './playwright.learning-session.config';
export default defineConfig({ ...sessions, testMatch: ['quiet-learning.spec.ts', 'agent-session.spec.ts'], outputDir: './test-results/learning-progress' });
