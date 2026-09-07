import { expect, test } from "./fixtures/teacherApp";

test("knowledge header shares one row and document actions open a menu", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics");
  const content = teacherPage.locator(".knowledge-library__content");
  await expect(content.getByRole("heading", { level: 2 })).toHaveCount(1);
  const build = content.getByRole("button", { name: "更新知识库", exact: true });
  const resource = content.getByRole("button", { name: "学习资源生成", exact: true });
  const search = content.getByRole("searchbox");
  const upload = content.getByRole("button", { name: "上传资料" });
  if (teacherPage.viewportSize()!.width > 1200) {
    const boxes = await Promise.all([build, resource, search, upload].map((item) => item.boundingBox()));
    expect(Math.max(...boxes.map((b) => b!.y)) - Math.min(...boxes.map((b) => b!.y))).toBeLessThan(15);
    expect(boxes[1]!.x).toBeLessThan(boxes[2]!.x);
  }
  const row = content.locator(".knowledge-library-document").first();
  await expect(row.getByRole("button", { name: /^删除/ })).toHaveCount(0);
  await row.getByRole("button", { name: /^文档操作/ }).click();
  await expect(teacherPage.getByRole("menuitem", { name: "查看详情" })).toBeVisible();
  await expect(teacherPage.getByRole("menuitem", { name: "修改资料名称" })).toBeVisible();
  await expect(teacherPage.getByRole("menuitem", { name: "删除", exact: true })).toBeVisible();
  await teacherPage.getByRole("menuitem", { name: "修改资料名称" }).click();
  const dialog = teacherPage.getByRole("dialog", { name: "修改资料名称" });
  await expect(dialog.getByLabel("资料名称")).not.toHaveValue("");
  await dialog.getByLabel("资料名称").fill("");
  await expect(dialog.getByRole("button", { name: /保\s*存/ })).toBeDisabled();
  await dialog.getByRole("button", { name: /取\s*消/ }).click();
  await expect(dialog).toBeHidden();
  await teacherPage.screenshot({ path: `/tmp/knowledge-toolbar-${teacherPage.viewportSize()!.width}.png`, fullPage: true });
});
