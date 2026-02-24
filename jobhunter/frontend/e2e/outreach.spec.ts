import { test, expect } from "@playwright/test";
import { loginViaApi } from "./helpers/auth";

test.describe("Outreach page", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaApi(page);
  });

  test("authenticated user sees outreach page", async ({ page }) => {
    await page.goto("/outreach");
    await expect(
      page.getByText(/outreach|email|campaign/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });
});
