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

test("course knowledge has one document uploader and two durable views", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics&view=documents", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByRole("navigation", { name: "课程知识视图" })).toBeVisible();
  await expect(teacherPage.getByRole("button", { name: "上传资料" })).toHaveCount(1);

  await teacherPage.getByRole("link", { name: "知识图谱", exact: true }).click();
  await expect(teacherPage).toHaveURL(/view=structure/);
  await expect(teacherPage.getByRole("button", { name: "上传资料" })).toHaveCount(0);
  await expect(teacherPage.getByRole("button", { name: "上传教材并解析" })).toHaveCount(0);
  await expect(teacherPage.getByRole("link", { name: "和 AI 聊一聊" })).toBeVisible();
});

test("knowledge structure deep link survives refresh and keeps an operable canvas", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics&view=structure", { waitUntil: "domcontentloaded" });
  await teacherPage.reload({ waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByRole("link", { name: "知识图谱", exact: true })).toHaveAttribute("aria-current", "page");
  await expect(teacherPage.locator(".knowledge-map__viewport")).toBeVisible();
  expect(await teacherPage.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("legacy graph links redirect into unified course knowledge", async ({ teacherPage }) => {
  await teacherPage.goto("/#graph?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await expect(teacherPage).toHaveURL(/#knowledge\?course_id=course-physics&view=structure/);
});
