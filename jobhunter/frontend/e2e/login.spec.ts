import { test, expect } from "@playwright/test";

test.describe("Login page", () => {
  test("shows login form with email and password fields", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText("Sign in")).toBeVisible();
    await expect(page.locator("#email")).toBeVisible();
    await expect(page.locator("#password")).toBeVisible();
  });

  test("can sign in with valid credentials and redirects to dashboard", async ({
    page,
  }) => {
    await page.goto("/login");
    await page.locator("#email").fill("test@example.com");
    await page.locator("#password").fill("testpass123");
    await page.getByRole("button", { name: "Sign in" }).click();

    // Should redirect to dashboard after successful login
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 10_000 });
  });

  test("shows error for invalid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.locator("#email").fill("wrong@example.com");
    await page.locator("#password").fill("wrongpassword");
    await page.getByRole("button", { name: "Sign in" }).click();

    // Should show a toast or error message
    await expect(
      page.getByText(/failed|invalid|error/i).first()
    ).toBeVisible({ timeout: 5_000 });
  });
});
