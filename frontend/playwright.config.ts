import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end Playwright config for TenderShield.
 * Runs against the local Next.js dev server + FastAPI backend.
 *
 *   npx playwright test              # headless
 *   npx playwright test --ui        # interactive
 *
 * Pre-requisites:
 *   cd backend && ./.venv/bin/uvicorn app.main:create_app --factory --reload --port 8000
 *   cd frontend && npm run dev
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false, // scenarios are sequential because they share backend state
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
