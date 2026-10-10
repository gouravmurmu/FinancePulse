import { expect, test } from "@playwright/test";

/** Read-only checks for a deployed site. Creates nothing. */
const API = process.env.E2E_API_URL;

test("API is healthy and has fresh data", async ({ request }) => {
  test.skip(!API, "E2E_API_URL not set");
  const res = await request.get(`${API}/api/v1/health`, { timeout: 150_000 });
  expect(res.ok()).toBeTruthy();
  expect((await res.json()).status).toBe("ok");
  const status = await (await request.get(`${API}/api/v1/status`)).json();
  const market = status.jobs.find((j: { job: string }) => j.job === "refresh_market_data");
  expect(market.overdue, "market data refresh is overdue").toBe(false);
  const late = status.jobs.filter(
    (j: { overdue: boolean; optional: boolean }) => j.overdue && !j.optional,
  );
  expect(
    late.map((j: { job: string }) => j.job),
    "required jobs overdue",
  ).toEqual([]);
});

test("Markets page shows real prices", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText(/End of day|Delayed|Live/).first()).toBeVisible({
    timeout: 150_000,
  });
});

test("an asset page loads its chart and risk panel", async ({ page }) => {
  await page.goto("/assets/eq:us:AAPL");
  await expect(page.getByRole("heading", { level: 1, name: "Apple Inc." })).toBeVisible({
    timeout: 150_000,
  });
  await page.mouse.wheel(0, 1500);
  await expect(page.getByRole("heading", { name: "Risk", exact: true })).toBeVisible({
    timeout: 150_000,
  });
});
