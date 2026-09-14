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
  await expect(dialog.getByText("已选择 1 个知识点，涉及 3 个资源槽位")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "检查 3 个资源槽位" })).toBeEnabled();
  await dialog.getByRole("button", { name: "查看力学详情" }).click();
  await expect(dialog.locator(".standard-resource-card")).toHaveCount(3);

  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await expect(dialog).toHaveCount(0);
});

test("existing resources are previewed before explicit regeneration and the batch recovers after reload", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await teacherPage.getByRole("button", { name: "学习资源生成" }).click();
  let dialog = teacherPage.getByRole("dialog", { name: "学习资源生成" });
  await dialog.getByRole("button", { name: /^光学/ }).click();
  await dialog.getByRole("checkbox", { name: "几何光学" }).check();

  await dialog.getByRole("button", { name: "检查 3 个资源槽位" }).click();
  await expect(dialog.getByText("补齐 2 项")).toBeVisible();
  await expect(dialog.getByText("保留 1 项")).toBeVisible();
  await expect(dialog.getByRole("button", { name: "确认生成 2 项资源" })).toBeEnabled();

  await dialog.getByRole("radio", { name: "为全部选中资源生成候选新版" }).check();
  await dialog.getByRole("button", { name: "检查 3 个资源槽位" }).click();
  await expect(dialog.getByText("候选新版 1 项")).toBeVisible();
  await dialog.getByRole("button", { name: "确认生成 3 项资源" }).click();
  await expect(dialog.getByText("本次生成进度")).toBeVisible();
  await expect(dialog.getByText("已完成 0/3 项")).toBeVisible();

  await dialog.getByRole("button", { name: "取消", exact: true }).click();
  await teacherPage.reload({ waitUntil: "domcontentloaded" });
  await teacherPage.getByRole("button", { name: "学习资源生成" }).click();
  dialog = teacherPage.getByRole("dialog", { name: "学习资源生成" });
  await expect(dialog.getByText("本次生成进度")).toBeVisible();
  await expect(dialog.getByText("已完成 0/3 项")).toBeVisible();
});

test("review version conflict is shown instead of approving an unseen candidate", async ({ teacherPage }) => {
  let reviewPayload: Record<string, unknown> | null = null;
  await teacherPage.route("**/standard-resources/standard-mechanics-guide/review", async (route) => {
    reviewPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ detail: { code: "VERSION_CHANGED", message: "资源已生成新版，请刷新后重新审核" } }),
    });
  });
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await teacherPage.getByRole("button", { name: "学习资源生成" }).click();
  const dialog = teacherPage.getByRole("dialog", { name: "学习资源生成" });
  await dialog.getByRole("button", { name: "查看力学详情" }).click();
  const guide = dialog.locator(".standard-resource-card").filter({ hasText: "学习指南" });
  await guide.getByRole("button", { name: "批准发布" }).click();

  await expect(dialog.getByRole("alert")).toContainText("资源已生成新版，请刷新后重新审核");
  expect(reviewPayload).toMatchObject({
    decision: "approved",
    expected_version: 1,
    expected_content_hash: "hash-standard-mechanics-guide-v1",
  });
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

test("knowledge browsing prioritizes the directory and searchable documents", async ({ teacherPage }) => {
  await teacherPage.goto("/#knowledge?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.locator(".knowledge-library__heading h2")).toHaveText("大学物理");
  await expect(teacherPage.getByText("历史版本与更多信息", { exact: true })).toHaveCount(0);
  await expect(teacherPage.getByText("资料查找、整理和质量检查会自动完成", { exact: true })).toHaveCount(0);
  await expect(teacherPage.getByText("归档位置", { exact: true })).toHaveCount(0);
  const documents = teacherPage.locator(".knowledge-library-document");
  await expect(documents.first()).toBeVisible();
  const initialCount = await documents.count();
  const firstTitle = await documents.first().locator("strong").innerText();
  const search = teacherPage.getByRole("searchbox", { name: "搜索当前目录资料" });
  await search.fill("不存在的资料-xyz");
  await expect(documents).toHaveCount(0);
  await expect(teacherPage.getByText("没有找到匹配的资料")).toBeVisible();
  await search.fill(firstTitle);
  await expect(documents.first().locator("strong")).toHaveText(firstTitle);
  await search.clear();
  await expect(documents).toHaveCount(initialCount);
  expect(await teacherPage.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await teacherPage.screenshot({ path: "/tmp/edu-ai-knowledge-redesign.png", fullPage: true });
});
