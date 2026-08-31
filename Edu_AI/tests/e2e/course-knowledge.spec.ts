import { expect, test } from "./fixtures/teacherApp";

test("learning resource generation opens inline without changing the route", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  const originalUrl = teacherPage.url();
  await teacherPage.getByRole("button", { name: "学习资源生成" }).click();

  await expect(teacherPage).toHaveURL(originalUrl);
  const resourcePanel = teacherPage.getByRole("dialog", { name: "学习资源生成" });
  await expect(resourcePanel).toBeVisible();
  await expect(resourcePanel.getByRole("button", { name: "收起", exact: true })).toBeVisible();
  await expect(resourcePanel.getByText("力学", { exact: true })).toBeVisible();
  await resourcePanel.getByRole("checkbox", { name: "力学" }).check();
  await expect(resourcePanel.getByRole("button", { name: /生成 3 项资源/ })).toBeEnabled();

  await resourcePanel.getByRole("button", { name: "收起", exact: true }).click();
  await expect(resourcePanel).toHaveCount(0);
});

test("course knowledge keeps one document uploader and the resource generation entry", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByRole("button", { name: "上传资料" })).toHaveCount(1);
  await expect(teacherPage.getByRole("button", { name: "学习资源生成" })).toBeVisible();
  await expect(teacherPage.getByRole("navigation", { name: "课程知识视图" })).toHaveCount(0);
});

test("legacy knowledge view parameters do not restore the retired graph canvas", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics&view=structure", { waitUntil: "domcontentloaded" });
  await teacherPage.reload({ waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByRole("button", { name: "上传资料" })).toHaveCount(1);
  await expect(teacherPage.locator(".knowledge-map__viewport")).toHaveCount(0);
  expect(await teacherPage.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("legacy graph links redirect into unified course knowledge", async ({ teacherPage }) => {
  await teacherPage.goto("/#graph?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await expect(teacherPage).toHaveURL(/#knowledge\?course_id=course-physics$/);
});
