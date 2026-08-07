import { expect, test } from "./fixtures/teacherApp";
import type { Page } from "playwright/test";

async function openFactory(page: Page, projectName: string) {
  void projectName;
  await page.waitForTimeout(500);
  const factory = page.getByTestId("generation-factory");
  const switcher = page.getByRole("button", { name: "生成工厂", exact: true });
  if (!(await factory.isVisible()) && await switcher.isVisible()) await switcher.click();
  await expect(factory).toBeVisible();
}

test("generation factory is keyboard operable and keeps its footer reachable", async ({ teacherPage }, testInfo) => {
  await teacherPage.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await openFactory(teacherPage, testInfo.project.name);

  await expect(teacherPage.locator(".generation-factory__registry button")).toHaveCount(9);
  await teacherPage.getByRole("button", { name: "教学报告", exact: true }).press("Enter");
  await expect(teacherPage.getByRole("dialog", { name: "配置教学报告" })).toBeVisible();
  await expect(teacherPage.getByRole("button", { name: /下一步|上一步/ })).toHaveCount(0);
  await teacherPage.getByLabel("报告主题 *").fill("牛顿运动定律复习");
  const submit = teacherPage.getByRole("button", { name: "开始后台生成" });
  await expect(submit).toBeVisible();
  expect(await submit.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return rect.top >= 0 && rect.bottom <= window.innerHeight;
  })).toBe(true);
  await submit.click();
  await expect(teacherPage.getByRole("dialog", { name: "配置教学报告" })).toHaveCount(0);
});

test("generation modal keeps a teacher's unfinished configuration", async ({ teacherPage }, testInfo) => {
  await teacherPage.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await openFactory(teacherPage, testInfo.project.name);
  await teacherPage.getByRole("button", { name: "教学报告", exact: true }).click();
  await teacherPage.getByLabel("报告主题 *").fill("恢复主题");
  await teacherPage.getByRole("button", { name: "取消" }).click();
  await teacherPage.getByRole("button", { name: "教学报告", exact: true }).click();
  await expect(teacherPage.getByLabel("报告主题 *")).toHaveValue("恢复主题");
});
