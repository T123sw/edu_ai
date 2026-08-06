import { expect, test } from "./fixtures/teacherApp";

test("course knowledge has one document uploader and two durable views", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics&view=documents", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByRole("navigation", { name: "课程知识视图" })).toBeVisible();
  await expect(teacherPage.getByRole("button", { name: "选择文件并上传" })).toHaveCount(1);

  await teacherPage.getByRole("link", { name: "知识结构", exact: true }).click();
  await expect(teacherPage).toHaveURL(/view=structure/);
  await expect(teacherPage.getByRole("button", { name: "选择文件并上传" })).toHaveCount(0);
  await expect(teacherPage.getByRole("button", { name: "上传教材并解析" })).toHaveCount(0);
  await expect(teacherPage.getByRole("link", { name: "关联课程资料" })).toBeVisible();
});

test("knowledge structure deep link survives refresh and keeps an operable canvas", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics&view=structure", { waitUntil: "domcontentloaded" });
  await teacherPage.reload({ waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByRole("link", { name: "知识结构", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(teacherPage.locator(".knowledge-structure-layout__canvas")).toBeVisible();
  expect(await teacherPage.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("legacy graph links redirect into unified course knowledge", async ({ teacherPage }) => {
  await teacherPage.goto("/#graph?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await expect(teacherPage).toHaveURL(/#knowledge\?course_id=course-physics&view=structure/);
});
