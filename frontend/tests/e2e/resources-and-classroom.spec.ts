import { expect, test } from "./fixtures/teacherApp";

test("course resources constrain hostile content and focus on the document", async ({ teacherPage }) => {
  await teacherPage.goto(
    "/#resources?course_id=course-physics&material_type=report&material_id=report-hostile-content",
    { waitUntil: "domcontentloaded" },
  );

  await expect(teacherPage.getByRole("heading", { name: /极端内容边界验收报告/ })).toBeVisible();
  await expect(teacherPage.locator(".resource-factual-meta")).toHaveCount(0);
  await expect(teacherPage.getByRole("navigation", { name: "按知识点浏览资源" })).toBeVisible();
  await expect(teacherPage.getByText("已选课程资料", { exact: true })).toHaveCount(0);
  await expect(teacherPage.getByText("private-rag-key")).toHaveCount(0);
  await expect(teacherPage.getByText("rag_index_key")).toHaveCount(0);

  const rootWidth = await teacherPage.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  expect(rootWidth.document).toBeLessThanOrEqual(rootWidth.viewport);
  expect(rootWidth.body).toBeLessThanOrEqual(rootWidth.viewport);

  const richPreview = teacherPage.locator(".edu-rich-preview").first();
  await expect(richPreview).toBeVisible();
  const internalScrollers = await richPreview.locator("table, pre").evaluateAll((nodes) =>
    nodes.map((node) => ({ clientWidth: node.clientWidth, scrollWidth: node.scrollWidth })),
  );
  expect(internalScrollers.length).toBeGreaterThanOrEqual(2);
  expect(internalScrollers.some((item) => item.scrollWidth >= item.clientWidth)).toBe(true);
});

test("classroom player keeps core controls on the first screen", async ({ teacherPage }) => {
  await teacherPage.goto(
    "/#classroom-player?course_id=course-physics&classroom_id=classroom-mechanics",
    { waitUntil: "domcontentloaded" },
  );

  const controls = teacherPage.getByTestId("classroom-core-controls");
  await expect(controls).toBeVisible();
  await expect(controls).toBeInViewport();
  await expect(teacherPage.getByRole("button", { name: "上一页" })).toBeInViewport();
  await expect(teacherPage.getByRole("button", { name: /播放当前页|暂停|重新播放当前页/ })).toBeInViewport();
  await expect(teacherPage.getByRole("button", { name: "下一页" })).toBeInViewport();
  await expect(teacherPage.getByLabel("语音状态")).toBeInViewport();
  await expect(teacherPage.getByRole("region", { name: "课堂舞台" })).toBeInViewport();
  await expect(teacherPage.getByText("scene-internal-mechanics-1")).toHaveCount(0);

  if (teacherPage.viewportSize()?.width === 1280) {
    await expect(teacherPage.getByRole("button", { name: "打开课堂目录" })).toBeVisible();
    await teacherPage.getByRole("button", { name: "打开课堂目录" }).click();
    await expect(teacherPage.getByRole("navigation").filter({ hasText: "从受力图判断运动状态" })).toBeVisible();
  }
});

test("teacher can edit and export a private generated report", async ({ teacherPage }) => {
  await teacherPage.goto(
    "/#resources?course_id=course-physics&space=mine&material_type=report&material_id=report-mechanics",
    { waitUntil: "domcontentloaded" },
  );

  await teacherPage.getByRole("button", { name: "编辑内容" }).click();
  const editor = teacherPage.getByLabel("资源内容");
  await expect(editor).toBeVisible();
  await editor.fill("# 已修订的牛顿定律\n\n这是教师保存后的内容。");
  await teacherPage.getByRole("button", { name: "保存内容" }).click();

  await expect(teacherPage.getByText("资源内容已保存")).toBeVisible();
  await expect(teacherPage.getByRole("heading", { name: "已修订的牛顿定律" })).toBeVisible();

  const downloadPromise = teacherPage.waitForEvent("download");
  await teacherPage.getByRole("button", { name: "导出", exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.md$/);
});


test("knowledge directory switches documents and reveals management actions on demand", async ({ teacherPage }) => {
  await teacherPage.route("**/api/courses/course-physics/materials?*", async route => {
    await route.fulfill({ json: [
      { material_id: "linked-report", material_type: "report", title: "力学阅读资料", content: "# 力学正文", scope_type: "knowledge_point", scope_id: "mechanics", visibility: "private" },
      { material_id: "legacy-report", material_type: "report", title: "历史资源", content: "# 历史正文", visibility: "private" },
    ] });
  });
  await teacherPage.goto("/#resources?course_id=course-physics", { waitUntil: "domcontentloaded" });
  const directory = teacherPage.getByRole("navigation", { name: "按知识点浏览资源" });
  await expect(directory.getByRole("button", { name: "力学 1", exact: true })).toBeVisible();
  const directoryBox = await directory.boundingBox();
  const documentBox = await teacherPage.locator(".resource-document").boundingBox();
  expect(directoryBox!.x + directoryBox!.width).toBeLessThan(documentBox!.x);
  await expect(teacherPage.getByRole("heading", { name: "力学正文", exact: true })).toBeVisible();
  await directory.getByRole("button", { name: "未分类资源 1" }).click();
  await directory.getByRole("button", { name: "历史资源 教学报告" }).click();
  await expect(teacherPage.getByRole("heading", { name: "历史正文", exact: true })).toBeVisible();
  await expect(teacherPage.getByRole("button", { name: "删除", exact: true })).toBeHidden();
  await teacherPage.getByText("更多操作", { exact: true }).click();
  await expect(teacherPage.getByRole("button", { name: "删除", exact: true })).toBeVisible();
  await teacherPage.getByText("更多操作", { exact: true }).click();
  await teacherPage.getByPlaceholder("搜索资源").fill("力学阅读");
  await expect(directory.getByRole("button", { name: "历史资源 教学报告" })).toHaveCount(0);
  await expect(teacherPage.getByRole("heading", { name: "力学正文", exact: true })).toBeVisible();
});


test("resource collections keep root and chapter documents from burying the curriculum", async ({ teacherPage }, testInfo) => {
  await teacherPage.route("**/api/courses/course-physics/knowledge-graph", route => route.fulfill({ json: {
    root: { id: "physics", label: "大学物理", children: [
      { id: "mechanics", label: "第一章 力学", children: [{ id: "motion", label: "运动与相互作用" }] },
      { id: "electricity", label: "第二章 电磁学", children: [{ id: "field", label: "电场与磁场" }] },
    ] },
  } }));
  await teacherPage.route("**/api/courses/course-physics/materials?*", route => route.fulfill({ json: [
    ...Array.from({ length: 35 }, (_, index) => ({ material_id: `course-report-${index}`, material_type: "report", title: `课程教学资料 ${index + 1}`, content: "# 课程教学资料\n\n整理课程的核心概念与教学安排。", scope_type: "course", visibility: "private" })),
    { material_id: "chapter-report", material_type: "report", title: "力学章节综述", content: "# 力学综述正文", scope_type: "knowledge_point", scope_id: "mechanics", visibility: "private" },
    { material_id: "leaf-report", material_type: "report", title: "运动阅读资料", content: "# 运动正文", scope_type: "knowledge_point", scope_id: "motion", visibility: "private" },
  ] }));
  await teacherPage.goto("/#resources?course_id=course-physics", { waitUntil: "domcontentloaded" });
  const directory = teacherPage.getByRole("navigation", { name: "按知识点浏览资源" });
  await expect(teacherPage.getByRole("radiogroup", { name: "资源类型筛选" })).toHaveCount(0);
  await expect(directory.getByRole("button", { name: "第二章 电磁学 0" })).toBeInViewport();
  const collection = directory.getByRole("treeitem", { name: "课程资源 35", exact: true });
  await expect(collection).toHaveAttribute("aria-expanded", "false");
  await expect(directory.getByRole("button", { name: "课程教学资料 1 教学报告", exact: true })).toHaveCount(0);
  await directory.getByRole("button", { name: "第一章 力学 2" }).click();
  await expect(directory.getByRole("treeitem", { name: "本节资源 1", exact: true })).toHaveAttribute("aria-expanded", "false");
  await directory.getByRole("button", { name: "本节资源 1" }).click();
  await directory.getByRole("button", { name: "力学章节综述 教学报告" }).click();
  await expect(teacherPage.getByRole("heading", { name: "力学综述正文" })).toBeVisible();
  await expect(directory.getByRole("treeitem", { name: "力学章节综述 教学报告" })).toHaveAttribute("aria-selected", "true");
  await teacherPage.screenshot({ path: testInfo.outputPath("resource-collections.png"), fullPage: true });
  await directory.getByRole("button", { name: "课程资源 35" }).click();
  await directory.getByRole("button", { name: "课程教学资料 1 教学报告", exact: true }).click();
  await expect(teacherPage.getByRole("heading", { name: "课程教学资料 1", exact: true })).toBeVisible();
  await directory.getByRole("button", { name: "课程资源 35" }).click();
  await teacherPage.getByPlaceholder("搜索资源").fill("课程教学资料 35");
  await expect(directory.getByRole("button", { name: "课程教学资料 35 教学报告" })).toBeVisible();
});
