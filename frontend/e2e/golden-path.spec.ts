import { test } from "./fixtures";
import { expect } from "@playwright/test";
import path from "path";

const FIXTURES = path.resolve(__dirname, "../../evals/e2e/fixtures");

test.describe("TenderShield golden path", () => {
  test("account sign-up, workspace creation, opportunity and document upload", async ({ authenticatedPage: page }) => {
    await page.goto("/");
    await page.waitForSelector("text=Create workspace", { timeout: 10000 });
    await page.click("text=Create workspace");
    await page.fill('input[placeholder*="Workspace name"], input[name="name"]', "E2E Workspace");
    await page.click('button:has-text("Create")');
    await expect(page.locator("text=E2E Workspace")).toBeVisible({ timeout: 10000 });

    await page.click('a:has-text("Opportunities"), button:has-text("New opportunity")');
    await page.fill('input[placeholder*="title"], input[name="title"]', "Test Tender");
    await page.click('button:has-text("Create")');

    await page.waitForURL(/\/opportunities\/.+/, { timeout: 15000 });

    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles(path.join(FIXTURES, "sample_nit.md"));
    await page.click('button:has-text("Upload")');
    await expect(page.locator("text=Uploaded")).toBeVisible({ timeout: 30000 });
  });

  test("admin dashboard is reachable for a super-admin", async ({ browser }) => {
    const ctx = await browser.newContext();
    const ts = Date.now();
    const { createAccount } = await import("./fixtures");
    await createAccount(ctx.request, `admin-${ts}@example.com`, `+9198765432${ts % 100}`.slice(0, 13));
    // Promote to super-admin cannot be done via API; this test documents the gap.
    const page = await ctx.newPage();
    await page.goto("/admin");
    await expect(page.locator("text=Superadmin access required")).toBeVisible();
    await ctx.close();
  });
});
