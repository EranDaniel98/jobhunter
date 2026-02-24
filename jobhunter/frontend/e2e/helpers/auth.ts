import { Page } from "@playwright/test";

const API_URL = process.env.E2E_API_URL || "http://localhost:8000/api/v1";

/**
 * Log in via the API and inject tokens into localStorage.
 * Avoids repeating UI login in every test.
 */
export async function loginViaApi(
  page: Page,
  email = "test@example.com",
  password = "testpass123"
) {
  const resp = await page.request.post(`${API_URL}/auth/login`, {
    data: { email, password },
  });

  if (!resp.ok()) {
    throw new Error(`Login failed: ${resp.status()} ${await resp.text()}`);
  }

  const { access_token, refresh_token } = await resp.json();

  // Inject tokens into localStorage (matches auth-provider pattern)
  await page.goto("/");
  await page.evaluate(
    ({ access, refresh }) => {
      localStorage.setItem("access_token", access);
      localStorage.setItem("refresh_token", refresh);
    },
    { access: access_token, refresh: refresh_token }
  );
}
