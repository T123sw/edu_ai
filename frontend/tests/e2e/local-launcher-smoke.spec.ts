import { expect, test } from "playwright/test";


test("local launcher exposes frontend and backend", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#root")).toBeVisible();
  await expect(page.locator("#root")).not.toBeEmpty();

  const backendStatus = await page.evaluate(async () => {
    const response = await fetch("http://127.0.0.1:8001/health");
    return response.status;
  });
  expect(backendStatus).toBeGreaterThanOrEqual(200);
  expect(backendStatus).toBeLessThan(300);

});
