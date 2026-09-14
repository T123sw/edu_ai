import { defineConfig } from "playwright/test";
export default defineConfig({
  testDir: "./tests/self-learning",
  outputDir: "./test-results/self-learning",
  timeout: 45000,
  fullyParallel: true,
  workers: 3,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5180",
    locale: "zh-CN",
    reducedMotion: "reduce",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop1440", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "compact1024", use: { viewport: { width: 1024, height: 768 } } },
    { name: "mobile390", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: "pnpm dev --host 127.0.0.1 --port 5180 --strictPort",
    url: "http://127.0.0.1:5180",
    reuseExistingServer: true,
    timeout: 60000,
  },
});
