import { expect, test } from "./fixtures/teacherApp";

test("keyboard publication flow preserves the personal source", async ({ teacherPage: page }) => {
  await page.goto("/#resources?course_id=course-physics", {
    waitUntil: "domcontentloaded",
  });

  const mineTab = page.getByRole("tab", { name: /我的资源/u });
  const courseTab = page.getByRole("tab", { name: /课程共享/u });
  await expect(page.locator(".course-shell__header").getByRole("tablist", { name: "资源空间" })).toBeVisible();
  await expect(page.locator(".course-shell__heading-row").getByRole("tablist", { name: "资源空间" })).toBeVisible();
  const resourceToolbar = page.locator("main > header");
  await expect(resourceToolbar.getByRole("radiogroup", { name: "资源类型筛选" })).toBeVisible();
  await expect(resourceToolbar.getByPlaceholder("搜索资源")).toBeVisible();
  await expect(page.getByText("个人结果默认仅自己可见，需要时可发布给课程成员。")).toHaveCount(0);
  await expect(page.getByText("这里的资源只有你能看到；发布后会生成独立的课程共享版本。")).toHaveCount(0);
  await expect(mineTab).toHaveAttribute("aria-selected", "true");
  await expect(mineTab).toHaveAttribute("tabindex", "0");
  await expect(courseTab).toHaveAttribute("tabindex", "-1");
  await expect(mineTab).toHaveAttribute("aria-controls", "resource-space-panel");
  await expect(courseTab).toHaveAttribute("aria-controls", "resource-space-panel");
  const resourcePanel = page.locator("#resource-space-panel");
  await expect(resourcePanel).toHaveRole("tabpanel");
  await expect(resourcePanel).toHaveAttribute(
    "aria-labelledby",
    "resource-space-tab-mine",
  );
  await expect(page.getByRole("heading", { name: "牛顿运动定律教学报告" })).toBeVisible();
  await expect(page.locator(".resource-factual-meta").getByText("可见范围", { exact: true })).toHaveCount(0);
  await expect(page.locator(".resource-factual-meta > div")).toHaveCount(4);

  const publishButton = page.getByRole("button", { name: "发布到课程" });
  await publishButton.focus();
  await publishButton.press("Enter");
  await expect(page.getByText("已发布", { exact: true })).toBeVisible();
  await expect(mineTab).toContainText("1");

  await mineTab.focus();
  await mineTab.press("ArrowRight");
  await expect(courseTab).toHaveAttribute("aria-selected", "true");
  await expect(courseTab).toBeFocused();
  await expect(courseTab).toHaveAttribute("tabindex", "0");
  await expect(resourcePanel).toHaveAttribute(
    "aria-labelledby",
    "resource-space-tab-course",
  );
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

  await courseTab.press("Home");
  await expect(mineTab).toBeFocused();
  await expect(mineTab).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("heading", { name: "牛顿运动定律教学报告" })).toBeVisible();
  await expect(page.getByRole("button", { name: "发布到课程" })).toBeVisible();
});
