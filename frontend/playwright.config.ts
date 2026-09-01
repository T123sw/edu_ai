import { defineConfig } from "playwright/test";

const e2ePort = process.env.PLAYWRIGHT_PORT || "5173";
const e2eBaseUrl = `http://127.0.0.1:${e2ePort}`;

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
    baseURL: e2eBaseUrl,
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
    command: `pnpm dev --host 127.0.0.1 --port ${e2ePort}`,
    url: e2eBaseUrl,
    reuseExistingServer: e2ePort === "5173",
    timeout: 120_000,
  },
});
