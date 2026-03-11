import { test, expect } from "@playwright/test";

test.describe("Smoke tests", () => {
  test("app loads and shows login page for unauthenticated users", async ({
    page,
  }) => {
    await page.goto("/");
    // Unauthenticated users should be redirected to login
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 });
    await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();
  });

  test("login page has expected form elements", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("#email")).toBeVisible();
    await expect(page.locator("#password")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /sign in/i })
    ).toBeVisible();
  });

  test("login with valid credentials reaches dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.locator("#email").fill("test@example.com");
    await page.locator("#password").fill("testpass123");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10_000 });
  });

  test("navigation sidebar is visible after login", async ({ page }) => {
    await page.goto("/login");
    await page.locator("#email").fill("test@example.com");
    await page.locator("#password").fill("testpass123");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10_000 });

    // Sidebar should contain key navigation items
    await expect(
      page.getByRole("link", { name: /dashboard/i }).first()
    ).toBeVisible({ timeout: 5_000 });
  });
});
