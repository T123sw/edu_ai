import { expect, test } from "./fixtures/teacherApp";

test("keyboard publication flow preserves the personal source", async ({ teacherPage: page }) => {
  await page.goto("/#resources?course_id=course-physics", {
    waitUntil: "domcontentloaded",
  });

  const mineTab = page.getByRole("tab", { name: /我的资源/u });
  const courseTab = page.getByRole("tab", { name: /课程共享/u });
  await expect(mineTab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "牛顿运动定律教学报告" })).toBeVisible();

  const publishButton = page.getByRole("button", { name: "发布到课程" });
  await publishButton.focus();
  await publishButton.press("Enter");
  await expect(page.getByText("已发布", { exact: true })).toBeVisible();
  await expect(mineTab).toContainText("1");

  await courseTab.focus();
  await courseTab.press("Enter");
  await expect(courseTab).toHaveAttribute("aria-selected", "true");
  const publishedCard = page.getByRole("button", {
    name: /报告 课程共享 牛顿运动定律教学报告/u,
  });
  await publishedCard.focus();
  await publishedCard.press("Enter");

  page.once("dialog", (dialog) => dialog.accept());
  const withdrawButton = page.getByRole("button", { name: "从课程撤回" });
  await withdrawButton.focus();
  await withdrawButton.press("Enter");
  await expect(publishedCard).toHaveCount(0);

  await mineTab.focus();
  await mineTab.press("Enter");
  await expect(page.getByRole("heading", { name: "牛顿运动定律教学报告" })).toBeVisible();
  await expect(page.getByRole("button", { name: "发布到课程" })).toBeVisible();
});
