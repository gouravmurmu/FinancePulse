import { expect, test } from "@playwright/test";

test("search finds an asset and opens its page", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: /Search/ })
    .first()
    .click();
  const dialog = page.getByRole("dialog", { name: "Search instruments" });
  await dialog.getByRole("combobox").fill("Apple");
  await dialog.getByRole("option", { name: /Apple Inc/ }).click();
  await expect(page).toHaveURL(/\/assets\/eq(%3A|:)us(%3A|:)AAPL/);
  await expect(page.getByRole("heading", { level: 1, name: "Apple Inc." })).toBeVisible();
  await expect(page.getByText(/End of day/).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Risk", exact: true })).toBeVisible();
});

test("Risk Lab compares the default assets and runs a simulation", async ({ page }) => {
  await page.goto("/risk-lab");
  await expect(page.getByRole("heading", { name: "Risk comparison" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Correlation", exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Run simulation/ }).click();
  await expect(page.getByText(/of simulated paths the/)).toBeVisible();
});

test("asset report downloads as a PDF", async ({ page }) => {
  await page.goto("/assets/eq:us:MSFT");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Report" }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/^eq-us-msft-.*\.pdf$/);
});
