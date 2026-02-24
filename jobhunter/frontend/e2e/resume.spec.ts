import { test, expect } from "@playwright/test";
import { loginViaApi } from "./helpers/auth";

test.describe("Resume page", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaApi(page);
  });

  test("authenticated user sees resume page", async ({ page }) => {
    await page.goto("/resume");
    // Should show the resume page content (upload zone or resume display)
    await expect(
      page.getByText(/resume|upload|drag/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });
});
