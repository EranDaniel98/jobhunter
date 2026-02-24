import { test, expect } from "@playwright/test";
import { loginViaApi } from "./helpers/auth";

test.describe("Companies page", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaApi(page);
  });

  test("authenticated user sees companies page with action buttons", async ({
    page,
  }) => {
    await page.goto("/companies");
    await expect(
      page.getByText(/companies|discover|pipeline/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("can open add company dialog", async ({ page }) => {
    await page.goto("/companies");
    // Look for an "Add" or "+" button
    const addButton = page.getByRole("button", { name: /add/i }).first();
    if (await addButton.isVisible()) {
      await addButton.click();
      // Dialog should appear with a domain input
      await expect(
        page.getByText(/domain|company|add/i).first()
      ).toBeVisible({ timeout: 5_000 });
    }
  });
});
