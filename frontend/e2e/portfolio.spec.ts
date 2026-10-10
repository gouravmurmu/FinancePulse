import { expect, test } from "@playwright/test";
import { signIn } from "./auth";

test("create a portfolio, add trades and see P&L", async ({ page }) => {
  await signIn(page, "/portfolio");
  const name = `E2E ${Date.now()}`;
  const first = page.getByRole("heading", { name: "Create your first portfolio" });
  const existing = page.getByRole("button", { name: "New" });
  await expect(first.or(existing)).toBeVisible();
  if (await existing.isVisible()) await existing.click();
  await page.getByLabel("Name").fill(name);
  await page.getByRole("button", { name: "Create portfolio" }).click();
  await expect(page.getByRole("heading", { name: "Add a transaction" })).toBeVisible();

  const d = new Date(Date.now() - 120 * 86_400_000);
  while (d.getUTCDay() === 0 || d.getUTCDay() === 6) d.setUTCDate(d.getUTCDate() - 1);
  await page.getByRole("radio", { name: "Buy" }).click();
  await page.getByLabel("Instrument").selectOption("eq:us:AAPL");
  await page.getByLabel("Date").fill(d.toISOString().slice(0, 10));
  await page.getByLabel(/^Quantity/).fill("10");
  await page.getByLabel(/^Price per/).fill("100");
  await page.getByLabel(/^Fees/).fill("1");
  await page.getByRole("button", { name: "Add buy" }).click();
  await expect(page.getByText(/Transaction added/).first()).toBeVisible();

  // Selling more than is held is refused with an explanation.
  await page.getByRole("radio", { name: "Sell" }).click();
  await page.getByLabel("Instrument").selectOption("eq:us:AAPL");
  await page.getByLabel("Date").fill(d.toISOString().slice(0, 10));
  await page.getByLabel(/^Quantity/).fill("50");
  await page.getByLabel(/^Price per/).fill("110");
  await page.getByRole("button", { name: "Add sell" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /held/ })).toBeVisible();

  await page.getByRole("radio", { name: "Overview" }).click();
  await expect(page.getByRole("heading", { name: "Holdings" })).toBeVisible();
  await expect(page.getByText("Apple Inc.").first()).toBeVisible();
  await expect(page.getByText(/Unrealized|Unrealised/).first()).toBeVisible();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Holdings CSV" }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/holdings.*\.csv$/);

  await page.getByRole("button", { name: `Delete portfolio ${name}` }).click({ noWaitAfter: true });
});

test("the assistant explains when it is not switched on", async ({ page }) => {
  await signIn(page, "/assistant");
  await expect(page.getByText(/not switched on yet|Ask about any asset/).first()).toBeVisible();
});
