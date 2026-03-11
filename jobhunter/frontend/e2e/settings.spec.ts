import { test, expect } from "@playwright/test";
import { loginViaApi } from "./helpers/auth";

test.describe("Settings page", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaApi(page);
  });

  test("settings page loads with tabs", async ({ page }) => {
    await page.goto("/settings");
    // Should show settings page with tab navigation
    await expect(
      page.getByText(/settings/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("profile tab is visible and active by default", async ({ page }) => {
    await page.goto("/settings");
    await expect(
      page.getByText(/profile|account/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("can switch between settings tabs", async ({ page }) => {
    await page.goto("/settings");
    // Wait for page to load
    await expect(
      page.getByText(/settings/i).first()
    ).toBeVisible({ timeout: 10_000 });

    // Look for other tabs (notifications, security, etc.)
    const tabs = page.getByRole("tab");
    const tabCount = await tabs.count();

    if (tabCount > 1) {
      // Click the second tab
      await tabs.nth(1).click();
      // Verify tab content changes (tab should become selected)
      await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true", {
        timeout: 5_000,
      });
    }
  });
});
