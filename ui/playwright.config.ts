import { defineConfig, devices } from "@playwright/test";

const channel = process.env.PLAYWRIGHT_CHANNEL?.trim() || undefined;
const video =
  process.env.CI || process.env.PLAYWRIGHT_VIDEO === "on"
    ? "retain-on-failure"
    : "off";

export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
    ["junit", { outputFile: "../reports/ui/junit.xml" }]
  ],
  use: {
    baseURL: process.env.SAFEDESK_WEB_URL?.replace(/\/$/, "") || "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video,
    actionTimeout: 15_000,
    navigationTimeout: 30_000
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        ...(channel ? { channel } : {})
      }
    }
  ]
});
