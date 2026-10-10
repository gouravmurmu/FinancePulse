import { defineConfig, devices } from "@playwright/test";

/**
 * Local and CI runs use a seeded throwaway database (backend/scripts/seed_e2e.py)
 * and a stand-in for Supabase sign-in. The smoke project runs read-only checks
 * against a deployed site: E2E_BASE_URL=https://... npx playwright test --project smoke
 */
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    trace: "retain-on-failure",
    launchOptions: process.env.PW_CHROMIUM_PATH
      ? { executablePath: process.env.PW_CHROMIUM_PATH }
      : undefined,
  },
  projects: [
    { name: "e2e", testIgnore: /smoke\.spec\.ts/, use: { ...devices["Desktop Chrome"] } },
    {
      name: "smoke",
      testMatch: /smoke\.spec\.ts/,
      // A free-tier API can take about a minute to wake up.
      timeout: 180_000,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
