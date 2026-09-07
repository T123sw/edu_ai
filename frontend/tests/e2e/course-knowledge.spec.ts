import { expect, test } from "./fixtures/teacherApp";

test("learning resource generation uses a compact progressive-disclosure modal", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  const pageHeight = await teacherPage.evaluate(() => document.documentElement.scrollHeight);
  const originalUrl = teacherPage.url();
  await teacherPage.getByRole("button", { name: "学习资源生成" }).click();

  await expect(teacherPage).toHaveURL(originalUrl);
  const dialog = teacherPage.getByRole("dialog", { name: "学习资源生成" });
  await expect(dialog).toBeVisible();
  expect(await teacherPage.evaluate(() => document.documentElement.scrollHeight)).toBe(pageHeight);
  await expect(dialog.locator(".standard-resource-card")).toHaveCount(0);
  await expect(dialog.getByRole("button", { name: /大学物理/ })).toHaveAttribute("aria-expanded", "true");
  await expect(dialog.getByRole("button", { name: /^光学/ })).toHaveAttribute("aria-expanded", "false");

  await dialog.getByRole("checkbox", { name: "力学" }).check();
  await expect(dialog.getByText("已选择 1 个知识点，将生成 3 项资源")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "开始生成 3 项资源" })).toBeEnabled();
  await dialog.getByRole("button", { name: "查看力学详情" }).click();
  await expect(dialog.locator(".standard-resource-card")).toHaveCount(3);

  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(dialog).toHaveCount(0);
});

test("course knowledge keeps one document uploader and the resource generation entry", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByRole("button", { name: "上传资料" })).toHaveCount(1);
  await expect(teacherPage.getByRole("button", { name: "学习资源生成" })).toBeVisible();
  await expect(teacherPage.getByRole("navigation", { name: "课程知识视图" })).toHaveCount(0);
});

test("course knowledge only displays the knowledge library, without generated course materials", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByRole("button", { name: "上传资料" })).toBeVisible();
  await expect(teacherPage.locator(".knowledge-library__documents")).toBeVisible();
  await expect(teacherPage.getByRole("region", { name: "课程资料", exact: true })).toHaveCount(0);
  await expect(teacherPage.locator(".knowledge-node-resources")).toHaveCount(0);
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
