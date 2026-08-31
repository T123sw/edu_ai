import { expect, test } from "./fixtures/teacherApp";

test("learning resource generation opens a dedicated configuration page", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await teacherPage.getByRole("link", { name: "学习资源生成" }).click();

  await expect(teacherPage).toHaveURL(/#learning-resource-generation\?course_id=course-physics/);
  await expect(teacherPage.getByRole("heading", { name: "学习资源生成" })).toBeVisible();
  await expect(teacherPage.getByRole("link", { name: "返回课程知识" })).toBeVisible();
  await expect(teacherPage.getByText("力学", { exact: true })).toBeVisible();
  await teacherPage.getByRole("checkbox", { name: "力学" }).check();
  await expect(teacherPage.getByRole("button", { name: /生成 3 项资源/ })).toBeEnabled();
});

test("course knowledge keeps one document uploader and the resource generation entry", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByRole("button", { name: "上传资料" })).toHaveCount(1);
  await expect(teacherPage.getByRole("link", { name: "学习资源生成" })).toBeVisible();
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
