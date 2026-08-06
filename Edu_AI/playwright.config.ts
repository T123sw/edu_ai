import { defineConfig } from "playwright/test";

const viewports = {
  desktop1366: { width: 1366, height: 768 },
  desktop1440: { width: 1440, height: 900 },
  desktop1920: { width: 1920, height: 1080 },
  compact1280: { width: 1280, height: 720 },
  compact1024: { width: 1024, height: 768 },
} as const;

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: "./test-results/e2e",
  fullyParallel: false,
  timeout: 120_000,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    colorScheme: "light",
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
    reducedMotion: "reduce",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: Object.entries(viewports).map(([name, viewport]) => ({
    name,
    use: { viewport },
  })),
  webServer: {
    command: "pnpm dev --host 127.0.0.1",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
