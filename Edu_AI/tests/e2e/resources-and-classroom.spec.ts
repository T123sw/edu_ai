import { expect, test } from "./fixtures/teacherApp";

test("course resources constrain hostile content and expose factual metadata", async ({ teacherPage }) => {
  await teacherPage.goto(
    "/#resources?course_id=course-physics&material_type=report&material_id=report-hostile-content",
    { waitUntil: "domcontentloaded" },
  );

  await expect(teacherPage.getByRole("heading", { name: /极端内容边界验收报告/ })).toBeVisible();
  await expect(teacherPage.getByText("唐老师", { exact: true })).toBeVisible();
  await expect(teacherPage.getByText("已选课程资料", { exact: true })).toBeVisible();
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
