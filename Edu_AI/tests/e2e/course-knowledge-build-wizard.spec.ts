import { expect, test } from "./fixtures/teacherApp";
import { installCourseKnowledgeBuildRoutes } from "./fixtures/courseKnowledgeBuild";

async function openBuildWizard(teacherPage: Parameters<typeof installCourseKnowledgeBuildRoutes>[0]) {
  await teacherPage.goto("/#knowledge?course_id=course-physics&view=documents", { waitUntil: "domcontentloaded" });
  await teacherPage.getByRole("button", { name: /更新知识库|一键构建知识库/ }).click();
  await expect(teacherPage.getByRole("dialog", { name: /课程知识库.*向导/ })).toBeVisible();
}

async function configureSmallBuild(teacherPage: Parameters<typeof installCourseKnowledgeBuildRoutes>[0]) {
  await teacherPage.getByLabel("图谱深度").fill("3");
  await teacherPage.getByLabel("模块数量").fill("2");
  await teacherPage.getByLabel("每模块知识点").fill("2");
  await teacherPage.getByLabel("每知识点有效覆盖目标").fill("2");
  await teacherPage.getByLabel("外部非 AI 来源下限").fill("1");
  await teacherPage.getByLabel("每知识点 AI 补充上限").fill("1");
  await teacherPage.getByLabel("每知识点搜索候选上限").fill("4");
  await teacherPage.getByRole("button", { name: "保存并选择教材" }).click();
  await expect(teacherPage.getByRole("heading", { name: "添加教材（可跳过）" })).toBeVisible();
}

async function reviewConfirmAndWaitForBuild(
  teacherPage: Parameters<typeof installCourseKnowledgeBuildRoutes>[0],
  expectedTextbookCopy: string,
  expectedLeafCount = 4,
) {
  await expect(teacherPage.getByRole("heading", { name: "审核知识图谱" })).toBeVisible({ timeout: 15_000 });
  await expect(teacherPage.getByText(expectedTextbookCopy, { exact: false })).toBeVisible();
  const overview = teacherPage.getByLabel("图谱审核概览");
  await expect(overview.locator(".course-kb-graph__stats > span").filter({ hasText: "知识点" })).toContainText(String(expectedLeafCount));
  await teacherPage.getByRole("treeitem", { name: /大学物理/ }).click();
  await teacherPage.getByLabel("大学物理说明").fill("大学物理课程知识结构（教师已审核）");
  await teacherPage.getByRole("button", { name: "保存草案" }).click();
  await expect(teacherPage.getByRole("button", { name: "保存草案" })).toBeDisabled();
  await teacherPage.getByLabel(/我已审核图谱/).check();
  await teacherPage.getByRole("button", { name: "确认图谱并开始构建" }).click();
  await expect(teacherPage.getByText("知识库已更新", { exact: true })).toBeVisible({ timeout: 15_000 });
  await teacherPage.getByText("历史版本与更多信息").click();
  await expect(teacherPage.getByText("100 分质量评分")).toBeVisible();
  await expect(teacherPage.locator(".course-kb-builder__quality li")).toHaveCount(8);
  await expect(teacherPage.locator(".course-kb-builder__quality li.is-passed")).toHaveCount(8);
}

test("无教材：配置规模、模型生成图谱、人工确认后才检索并发布", async ({ teacherPage }) => {
  const fixture = await installCourseKnowledgeBuildRoutes(teacherPage);
  await openBuildWizard(teacherPage);
  await configureSmallBuild(teacherPage);

  expect(fixture.events).not.toContain("build:start");
  expect(fixture.events).not.toContain("web:discover-and-ingest");
  await teacherPage.getByRole("button", { name: "跳过教材并生成图谱" }).click();
  await reviewConfirmAndWaitForBuild(teacherPage, "本次未使用教材");

  expect(fixture.events.indexOf("graph:confirm")).toBeLessThan(fixture.events.indexOf("build:start"));
  expect(fixture.events.indexOf("build:start")).toBeLessThan(fixture.events.indexOf("web:discover-and-ingest"));
  expect(fixture.build().metrics?.web_material_count).toBe(4);
  expect(fixture.build().source_candidates.every((source) => source.license_name === null)).toBe(true);
  await expect(teacherPage.getByText("4 份已确认来源")).toBeVisible();
});

test("有教材：教材解析参与模型图谱，并与网络和 AI 资料共同入库", async ({ teacherPage }) => {
  const fixture = await installCourseKnowledgeBuildRoutes(teacherPage);
  await openBuildWizard(teacherPage);
  await configureSmallBuild(teacherPage);

  const chooser = teacherPage.locator('input[type="file"][accept*=".md"]');
  await chooser.setInputFiles({
    name: "大学物理验收教材.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# 第一章 运动学\n\n# 第二章 牛顿定律\n\n# 第三章 功与能\n\n# 第四章 能量守恒", "utf8"),
  });
  await expect(teacherPage.getByText("大学物理验收教材.md", { exact: true })).toBeVisible();
  await expect(teacherPage.getByText(/4 章 \/ 8 块/)).toBeVisible();
  await teacherPage.getByRole("button", { name: "生成知识图谱草案" }).click();
  await reviewConfirmAndWaitForBuild(teacherPage, "已参考 1 份教材生成");

  expect(fixture.events).toContain("textbook:upload");
  expect(fixture.build().metrics?.textbook_chunk_count).toBe(8);
  await teacherPage.reload({ waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByText("牛顿运动定律公开课程资料.md", { exact: true })).toBeVisible();
  await expect(teacherPage.getByText("大学物理验收教材.md", { exact: true })).toBeVisible();
  await expect(teacherPage.getByText("机械能守恒学习材料（AI 补充）.md", { exact: true })).toBeVisible();
});

test("已有知识库：增量生成只追加新节点并保留全部现有节点", async ({ teacherPage }) => {
  const fixture = await installCourseKnowledgeBuildRoutes(teacherPage, { existingGraph: true });
  await openBuildWizard(teacherPage);
  await expect(teacherPage.getByRole("heading", { name: "课程知识库增量更新向导" })).toBeVisible();
  await expect(teacherPage.getByText("增量追加", { exact: true })).toBeVisible();
  await configureSmallBuild(teacherPage);

  await teacherPage.getByRole("button", { name: "跳过教材并生成图谱" }).click();
  await expect(teacherPage.getByRole("heading", { name: "审核知识图谱" })).toBeVisible({ timeout: 15_000 });
  await teacherPage.getByRole("treeitem", { name: /牛顿运动定律/ }).click();
  await expect(teacherPage.getByText("现有节点的名称、类型和位置受保护", { exact: false })).toBeVisible();
  await expect(teacherPage.getByLabel("牛顿运动定律名称")).toBeDisabled();
  await teacherPage.getByRole("treeitem", { name: /角动量/ }).click();
  await expect(teacherPage.getByLabel("角动量名称")).toBeEnabled();
  await reviewConfirmAndWaitForBuild(teacherPage, "本次未使用教材", 5);

  const finalRoot = fixture.build().graph_draft!;
  const finalNodeIds = [finalRoot, ...(finalRoot.children || []), ...(finalRoot.children || []).flatMap((node) => node.children || [])]
    .map((node) => node.id);
  expect(fixture.baselineNodeIds.every((nodeId) => finalNodeIds.includes(nodeId))).toBe(true);
  expect(finalNodeIds).toContain("angular-momentum");
  expect(fixture.build().config?.update_strategy).toBe("incremental");
});

test("窄屏使用图谱与节点详情分页且页面无横向滚动", async ({ teacherPage }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop1366", "响应式验收只需运行一次");
  await teacherPage.setViewportSize({ width: 375, height: 812 });
  await installCourseKnowledgeBuildRoutes(teacherPage, { existingGraph: true });
  await openBuildWizard(teacherPage);
  await configureSmallBuild(teacherPage);
  await teacherPage.getByRole("button", { name: "跳过教材并生成图谱" }).click();

  await expect(teacherPage.getByRole("tab", { name: "图谱" })).toBeVisible({ timeout: 15_000 });
  await teacherPage.getByRole("treeitem", { name: /角动量/ }).click();
  await expect(teacherPage.getByRole("tab", { name: "节点详情" })).toHaveAttribute("aria-selected", "true");
  await expect(teacherPage.getByLabel("角动量名称")).toBeVisible();
  expect(await teacherPage.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

  await teacherPage.setViewportSize({ width: 768, height: 900 });
  await expect(teacherPage.getByRole("tab", { name: "图谱" })).toBeHidden();
  await expect(teacherPage.getByRole("tree")).toBeVisible();
  await expect(teacherPage.getByLabel("角动量名称")).toBeVisible();
  expect(await teacherPage.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});
