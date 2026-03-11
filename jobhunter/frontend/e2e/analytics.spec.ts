import { test, expect } from "@playwright/test";
import { loginViaApi } from "./helpers/auth";

test.describe("Analytics page", () => {
  test.beforeEach(async ({ page }) => {
    await loginViaApi(page);
  });

  test("analytics page loads with content", async ({ page }) => {
    await page.goto("/analytics");
    await expect(
      page.getByText(/analytics|metrics|overview/i).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("analytics page shows stat cards or charts", async ({ page }) => {
    await page.goto("/analytics");
    // Wait for page load
    await expect(
      page.getByText(/analytics|metrics|overview/i).first()
    ).toBeVisible({ timeout: 10_000 });

    // Should show at least one metric card or chart container
    const hasCards = await page.locator("[class*=card]").count();
    const hasCharts = await page.locator("svg.recharts-surface, [class*=chart]").count();
    const hasContent = hasCards > 0 || hasCharts > 0;

    expect(hasContent).toBeTruthy();
  });

  test("analytics page does not show error state", async ({ page }) => {
    await page.goto("/analytics");
    await expect(
      page.getByText(/analytics|metrics|overview/i).first()
    ).toBeVisible({ timeout: 10_000 });

    // Should not show a full-page error
    const errorCount = await page
      .getByText(/something went wrong|unexpected error|500/i)
      .count();
    expect(errorCount).toBe(0);
  });
});
