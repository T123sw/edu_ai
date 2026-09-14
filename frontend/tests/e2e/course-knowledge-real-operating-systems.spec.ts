import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test, type APIRequestContext, type Page } from "playwright/test";

const apiBase = process.env.COURSE_KB_REAL_API_BASE || "http://127.0.0.1:8001";
const username = process.env.COURSE_KB_REAL_USERNAME || "teacher";
const password = process.env.COURSE_KB_REAL_PASSWORD || "teacher123";
const runId = process.env.COURSE_KB_REAL_E2E_RUN_ID || new Date().toISOString().replace(/[:.]/g, "-");
const resumeCourseId = process.env.COURSE_KB_REAL_RESUME_COURSE_ID || "";
const resumeBuildId = process.env.COURSE_KB_REAL_RESUME_BUILD_ID || "";
const resumeIncrementBuildId = process.env.COURSE_KB_REAL_RESUME_INCREMENT_BUILD_ID || "";
const resumeStage = process.env.COURSE_KB_REAL_RESUME_STAGE || "";
const evidenceDir = resolve(
  process.cwd(),
  "../docs/acceptance/evidence/2026-09-11-course-knowledge-real-operating-systems",
  runId,
);

type JsonRecord = Record<string, unknown>;

function saveJson(name: string, value: unknown) {
  mkdirSync(evidenceDir, { recursive: true });
  writeFileSync(resolve(evidenceDir, `${name}.json`), JSON.stringify(value, null, 2));
}

async function capture(page: Page, name: string) {
  mkdirSync(evidenceDir, { recursive: true });
  await page.screenshot({ path: resolve(evidenceDir, `${name}.png`), fullPage: true });
}

async function login(page: Page) {
  await page.goto("/#login", { waitUntil: "domcontentloaded" });
  await page.getByLabel("账号", { exact: true }).fill(username);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.locator('button[type="submit"]').click();
  await expect(page.getByText("登录 Edu AI")).toBeHidden({ timeout: 30_000 });
}

async function loginToken(request: APIRequestContext): Promise<string> {
  const response = await request.post(`${apiBase}/api/auth/login`, {
    data: { username, password },
  });
  expect(response.ok(), `真实后端登录失败：${response.status()}`).toBeTruthy();
  return ((await response.json()) as { token: string }).token;
}

async function getJson(
  request: APIRequestContext,
  token: string,
  path: string,
): Promise<JsonRecord | JsonRecord[]> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= 5; attempt += 1) {
    try {
      const response = await request.get(`${apiBase}${path}`, {
        headers: { Authorization: `Bearer ${token}` },
        timeout: 30_000,
      });
      expect(response.ok(), `${path} 返回 ${response.status()}`).toBeTruthy();
      return await response.json() as JsonRecord | JsonRecord[];
    } catch (error) {
      lastError = error;
      if (attempt < 5) await new Promise((resolveDelay) => setTimeout(resolveDelay, attempt * 1_000));
    }
  }
  throw lastError;
}

async function pollBuild(
  page: Page,
  request: APIRequestContext,
  token: string,
  courseId: string,
  buildId: string,
  prefix: string,
): Promise<JsonRecord> {
  const deadline = Date.now() + 20 * 60_000;
  const phases: JsonRecord[] = [];
  let lastMarker = "";
  while (Date.now() < deadline) {
    const build = await getJson(
      request,
      token,
      `/api/courses/${courseId}/knowledge-builds/${buildId}`,
    ) as JsonRecord;
    const marker = `${String(build.status || "unknown")}-${String(build.phase || "unknown")}-${String(build.progress || 0)}`;
    phases.push({
      observed_at: new Date().toISOString(),
      status: build.status,
      phase: build.phase,
      progress: build.progress,
      quality_score: build.quality_score,
      error: build.error,
    });
    if (marker !== lastMarker) {
      lastMarker = marker;
      await page.goto(`/#knowledge?course_id=${courseId}`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(800);
      await capture(page, `${prefix}-${String(phases.length).padStart(2, "0")}-${marker.replace(/[^a-zA-Z0-9_-]+/g, "-")}`);
    }
    if (["succeeded", "failed", "blocked", "canceled"].includes(String(build.status))) {
      saveJson(`${prefix}-phase-history`, phases);
      saveJson(`${prefix}-final-build`, build);
      return build;
    }
    await page.waitForTimeout(5_000);
  }
  saveJson(`${prefix}-phase-history`, phases);
  throw new Error(`${prefix} 构建在 20 分钟内未结束`);
}

function buildIdFromHref(href: string): string {
  const match = href.match(/[?&]build_id=([^&]+)/);
  if (!match) throw new Error(`审核链接缺少 build_id：${href}`);
  return decodeURIComponent(match[1]);
}

function nodeIds(root: unknown): string[] {
  if (!root || typeof root !== "object") return [];
  const value = root as JsonRecord;
  const children = Array.isArray(value.children) ? value.children : [];
  return [String(value.id || ""), ...children.flatMap(nodeIds)].filter(Boolean);
}

test("操作系统课程真实首次构建与增量补充", async ({ page, request }) => {
  test.skip(
    process.env.COURSE_KB_REAL_E2E !== "1",
    "设置 COURSE_KB_REAL_E2E=1 后才运行真实模型、检索和发布验收。",
  );
  test.setTimeout(30 * 60_000);

  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));

  const token = await loginToken(request);
  await login(page);
  await capture(page, "01-login-home");

  let courseId = resumeCourseId;
  let firstBuildId = resumeBuildId;
  let courseTitle = "";
  if (resumeStage === "verify-final") {
    expect(courseId, "最终页面核验需要 COURSE_KB_REAL_RESUME_COURSE_ID").not.toBe("");
    let finalBuild: JsonRecord | undefined;
    if (resumeIncrementBuildId) {
      finalBuild = await getJson(
        request,
        token,
        `/api/courses/${courseId}/knowledge-builds/${resumeIncrementBuildId}`,
      ) as JsonRecord;
      saveJson("16-increment-build-final-build", finalBuild);
      expect(finalBuild.status, JSON.stringify(finalBuild.error)).toBe("succeeded");
      expect(Number(finalBuild.quality_score || 0)).toBeGreaterThanOrEqual(80);
      const readyDomains = ((finalBuild.source_candidates || []) as JsonRecord[])
        .filter((item) => item.review_status === "ready")
        .map((item) => String(item.domain || ""));
      expect(readyDomains).toContain("docs.docker.com");
      expect(readyDomains).toContain("docs.kernel.org");
      expect(readyDomains.some((domain) => /csdn|juejin|jianshu/.test(domain))).toBeFalsy();
      const intentCheck = ((finalBuild.metrics as JsonRecord | undefined)?.checks as JsonRecord[] | undefined)
        ?.find((item) => item.check_type === "intent_adherence");
      expect((intentCheck?.details as JsonRecord | undefined)?.missing_deliverables).toEqual([]);
    }
    if (resumeBuildId && finalBuild) {
      const baselineBuild = await getJson(
        request,
        token,
        `/api/courses/${courseId}/knowledge-builds/${resumeBuildId}`,
      ) as JsonRecord;
      const baselineIds = nodeIds(baselineBuild.graph_draft);
      const finalIds = nodeIds(finalBuild.graph_draft);
      const preservedIds = baselineIds.filter((id) => finalIds.includes(id));
      saveJson("comparison", {
        course_id: courseId,
        first_build_id: resumeBuildId,
        increment_build_id: resumeIncrementBuildId,
        first_status: baselineBuild.status,
        increment_status: finalBuild.status,
        first_quality_score: baselineBuild.quality_score,
        increment_quality_score: finalBuild.quality_score,
        first_node_count: baselineIds.length,
        increment_node_count: finalIds.length,
        preserved_node_count: preservedIds.length,
        all_first_nodes_preserved: baselineIds.every((id) => finalIds.includes(id)),
      });
      expect(baselineIds.every((id) => finalIds.includes(id))).toBeTruthy();
    }
    saveJson(
      "versions-after-increment",
      await getJson(request, token, `/api/courses/${courseId}/knowledge-base/versions`),
    );
    saveJson(
      "final-knowledge-graph",
      await getJson(request, token, `/api/courses/${courseId}/knowledge-graph`),
    );
    await page.goto(`/#knowledge?course_id=${courseId}`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: "展开进程与线程" }).click();
    const addedTopic = page.getByRole("button", { name: "Linux cgroups 与容器资源隔离", exact: true });
    await expect(addedTopic).toBeVisible({ timeout: 30_000 });
    await addedTopic.click();
    const resourceCount = page.getByText(/^\d+ 份资料$/, { exact: true });
    await expect(resourceCount).toBeVisible({ timeout: 30_000 });
    const countText = await resourceCount.textContent();
    expect(Number.parseInt(countText || "0", 10)).toBeGreaterThanOrEqual(4);
    await capture(page, "17-increment-published-detail");
    return;
  }
  if (courseId && firstBuildId) {
    const course = await getJson(request, token, `/api/courses/${courseId}`) as JsonRecord;
    courseTitle = String(course.title || "操作系统");
    saveJson("course", course);
    await page.goto(`/#ai?course_id=${courseId}`, { waitUntil: "domcontentloaded" });
    await page.getByText(/三档方案的比较/).waitFor({ timeout: 30_000 }).catch(() => undefined);
    await capture(page, "05-agent-proposal-ready");
    await page.goto(
      `/#knowledge?course_id=${courseId}&build_id=${firstBuildId}&action=build`,
      { waitUntil: "domcontentloaded" },
    );
  } else {
    await page.getByRole("button", { name: "创建课程" }).click();
    const createDialog = page.getByRole("dialog", { name: "创建课程并准备知识库" });
    await expect(createDialog).toBeVisible();
    await capture(page, "02-new-course-empty-form");

    courseTitle = `操作系统（真实E2E-${runId.slice(0, 19)}）`;
    await createDialog.getByLabel("课程名称").fill(courseTitle);
    await createDialog.getByLabel("课程简介").fill(
      "面向计算机专业大二学生的操作系统基础课程，共 8 课时，覆盖进程与线程、CPU 调度、进程同步、死锁和虚拟内存。",
    );
    await createDialog.getByLabel("教学对象 / 年级").fill("掌握 C 语言和数据结构的计算机专业大二学生");
    await createDialog.getByLabel("课程目标").fill([
      "能解释进程、线程和系统调用的核心机制",
      "能比较常见 CPU 调度算法并计算等待时间",
      "能使用信号量分析并解决典型同步问题",
      "能解释分页、缺页和页面置换算法",
    ].join("\n"));
    await createDialog.getByLabel("知识库构建要求").fill(
      "共 8 课时，覆盖进程与线程、CPU 调度、进程同步、死锁和虚拟内存，达到本科基础到应用深度；优先使用大学课程和公认开放教材，资料不足时允许 AI 基于权威来源补充；每个主题需要机制讲解、可验证例子、练习和实验建议。",
    );
    await capture(page, "03-new-course-filled-form");

    const createResponsePromise = page.waitForResponse((response) =>
      response.request().method() === "POST" && /\/api\/courses$/.test(response.url()),
    );
    const streamResponsePromise = page.waitForResponse((response) =>
      response.request().method() === "POST" && response.url().endsWith("/api/chat/v2/stream"),
      { timeout: 5 * 60_000 },
    );
    await createDialog.getByRole("button", { name: "创建并继续" }).click();
    const createResponse = await createResponsePromise;
    expect(createResponse.ok(), `创建课程失败：${createResponse.status()}`).toBeTruthy();
    const course = await createResponse.json() as JsonRecord;
    courseId = String(course.id || "");
    expect(courseId).not.toBe("");
    saveJson("course", course);

    await expect(page).toHaveURL(new RegExp(`#ai\\?course_id=${courseId}`), { timeout: 30_000 });
    await page.getByText(/正在|规划|课程知识库/).first().waitFor({ timeout: 30_000 }).catch(() => undefined);
    await capture(page, "04-agent-planning");
    const streamResponse = await streamResponsePromise;
    expect(streamResponse.ok(), `Agent 流返回 ${streamResponse.status()}`).toBeTruthy();

    const reviewLink = page.getByRole("link", { name: "审核方案" }).last();
    await expect(reviewLink).toBeVisible({ timeout: 5 * 60_000 });
    const reviewHref = await reviewLink.getAttribute("href");
    expect(reviewHref).toBeTruthy();
    firstBuildId = buildIdFromHref(reviewHref!);
    await capture(page, "05-agent-proposal-ready");
    await reviewLink.click();
  }

  let firstDraft: JsonRecord;
  if (resumeStage === "first-running") {
    firstDraft = await getJson(
      request,
      token,
      `/api/courses/${courseId}/knowledge-builds/${firstBuildId}`,
    ) as JsonRecord;
  } else {
    const firstWizard = page.getByRole("dialog", { name: "创建课程知识库" });
    await expect(firstWizard.getByRole("heading", { name: "比较课程大纲" })).toBeVisible({ timeout: 30_000 });
    await capture(page, "06-new-outline-options");
    await firstWizard.getByRole("button", { name: "选择简明大纲" }).click();
    await expect(firstWizard.getByRole("heading", { name: "审核知识图谱" })).toBeVisible({ timeout: 30_000 });
    await capture(page, "07-new-graph-review");

    firstDraft = await getJson(
      request,
      token,
      `/api/courses/${courseId}/knowledge-builds/${firstBuildId}`,
    ) as JsonRecord;
    saveJson("new-build-before-confirm", firstDraft);
    await firstWizard.getByRole("checkbox", { name: "我已检查课程目录和本次更新内容" }).check();
    const firstStartPromise = page.waitForResponse((response) =>
      response.request().method() === "POST"
      && response.url().endsWith(`/knowledge-builds/${firstBuildId}/start`),
    );
    await firstWizard.getByRole("button", { name: "确认并更新知识库" }).click();
    expect((await firstStartPromise).ok()).toBeTruthy();
    await expect(firstWizard).toBeHidden({ timeout: 30_000 });
    await capture(page, "08-new-build-started");
  }

  const firstFinal = await pollBuild(page, request, token, courseId, firstBuildId, "09-new-build");
  expect(firstFinal.status, JSON.stringify(firstFinal.error)).toBe("succeeded");
  const versionsAfterCreate = await getJson(request, token, `/api/courses/${courseId}/knowledge-base/versions`);
  saveJson("versions-after-create", versionsAfterCreate);
  await page.goto(`/#knowledge?course_id=${courseId}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1_000);
  await capture(page, "10-new-build-published");

  let incrementBuildId = resumeIncrementBuildId;
  if (incrementBuildId) {
    await page.goto(
      `/#knowledge?course_id=${courseId}&build_id=${incrementBuildId}&action=build`,
      { waitUntil: "domcontentloaded" },
    );
    // The hash router can retain the mounted knowledge page when only query
    // parameters change; reload so the build card consumes the linked draft.
    await page.reload({ waitUntil: "domcontentloaded" });
  } else {
    const updateButton = page.getByRole("button", { name: "更新知识库", exact: true });
    await expect(updateButton).toBeEnabled({ timeout: 30_000 });
    const draftResponsePromise = page.waitForResponse((response) =>
      response.request().method() === "POST" && /\/knowledge-builds$/.test(response.url()),
    );
    await updateButton.click();
    const draftResponse = await draftResponsePromise;
    expect(draftResponse.ok(), `增量草案创建失败：${draftResponse.status()}`).toBeTruthy();
    const incrementDraft = await draftResponse.json() as JsonRecord;
    incrementBuildId = String(incrementDraft.build_id || "");
  }
  const updateWizard = page.getByRole("dialog", { name: "更新课程知识库" });
  await expect(updateWizard).toBeVisible({ timeout: 30_000 });
  await capture(page, "11-increment-empty-requirements");

  const incrementRequirements = [
    "本次新增知识点“Linux cgroups 与容器资源隔离”",
    "补充内容：CPU、内存和 I/O 资源限制机制，1 个 Docker 配置案例，3 道带解析练习",
    "保留范围：保留现有目录和全部已有资料，不修改其他章节",
    "资料偏好：优先检索 Linux Kernel 与 Docker 官方资料，资料不足时允许 AI 补充",
  ].join("\n");
  await updateWizard.locator("textarea").fill(incrementRequirements);
  await capture(page, "12-increment-filled-requirements");
  const proposalResponsePromise = page.waitForResponse((response) =>
    response.request().method() === "POST" && response.url().endsWith(`/knowledge-builds/${incrementBuildId}/proposal`),
    { timeout: 5 * 60_000 },
  );
  await updateWizard.getByRole("button", { name: "分析补充建议", exact: true }).click();
  const proposalResponse = await proposalResponsePromise;
  const proposalResponseBody = await proposalResponse.json() as JsonRecord;
  saveJson("increment-proposal-response", {
    status: proposalResponse.status(),
    body: proposalResponseBody,
  });
  if (!proposalResponse.ok()) await capture(page, "13-increment-proposal-rejected");
  expect(
    proposalResponse.ok(),
    `增量方案生成失败：${proposalResponse.status()} ${JSON.stringify(proposalResponseBody)}`,
  ).toBeTruthy();
  await expect(updateWizard.getByRole("heading", { name: "确认本次补充内容" })).toBeVisible({ timeout: 30_000 });
  await capture(page, "13-increment-proposal");
  const supplementBuild = await getJson(
    request,
    token,
    `/api/courses/${courseId}/knowledge-builds/${incrementBuildId}`,
  ) as JsonRecord;
  saveJson("increment-proposal", supplementBuild);
  const supplementItems = ((supplementBuild.knowledge_proposal as JsonRecord | undefined)?.items || []) as unknown[];
  expect(supplementItems.length, "真实增量方案没有返回补充项").toBeGreaterThan(0);

  await updateWizard.getByRole("button", { name: /检查目录并继续/ }).click();
  await expect(updateWizard.getByRole("heading", { name: "审核知识图谱" })).toBeVisible({ timeout: 30_000 });
  await capture(page, "14-increment-graph-review");
  const incrementBeforeConfirm = await getJson(
    request,
    token,
    `/api/courses/${courseId}/knowledge-builds/${incrementBuildId}`,
  ) as JsonRecord;
  saveJson("increment-before-confirm", incrementBeforeConfirm);

  await updateWizard.getByRole("checkbox", { name: "我已检查课程目录和本次更新内容" }).check();
  const incrementStartPromise = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && response.url().endsWith(`/knowledge-builds/${incrementBuildId}/start`),
  );
  await updateWizard.getByRole("button", { name: "确认并更新知识库" }).click();
  expect((await incrementStartPromise).ok()).toBeTruthy();
  await expect(updateWizard).toBeHidden({ timeout: 30_000 });
  await capture(page, "15-increment-build-started");

  const incrementFinal = await pollBuild(page, request, token, courseId, incrementBuildId, "16-increment-build");
  expect(incrementFinal.status, JSON.stringify(incrementFinal.error)).toBe("succeeded");
  const versionsAfterIncrement = await getJson(request, token, `/api/courses/${courseId}/knowledge-base/versions`);
  const finalGraph = await getJson(request, token, `/api/courses/${courseId}/knowledge-graph`);
  saveJson("versions-after-increment", versionsAfterIncrement);
  saveJson("final-knowledge-graph", finalGraph);

  const firstNodeIds = nodeIds(firstDraft.graph_draft);
  const incrementNodeIds = nodeIds(incrementFinal.graph_draft);
  const preservedNodeIds = firstNodeIds.filter((id) => incrementNodeIds.includes(id));
  saveJson("comparison", {
    course_id: courseId,
    course_title: courseTitle,
    first_build_id: firstBuildId,
    increment_build_id: incrementBuildId,
    first_status: firstFinal.status,
    increment_status: incrementFinal.status,
    first_quality_score: firstFinal.quality_score,
    increment_quality_score: incrementFinal.quality_score,
    first_node_count: firstNodeIds.length,
    increment_node_count: incrementNodeIds.length,
    preserved_node_count: preservedNodeIds.length,
    all_first_nodes_preserved: firstNodeIds.every((id) => incrementNodeIds.includes(id)),
    version_count_after_create: Array.isArray(versionsAfterCreate) ? versionsAfterCreate.length : null,
    version_count_after_increment: Array.isArray(versionsAfterIncrement) ? versionsAfterIncrement.length : null,
    console_errors: consoleErrors,
  });
  expect(firstNodeIds.every((id) => incrementNodeIds.includes(id))).toBeTruthy();
  expect(Array.isArray(versionsAfterIncrement) ? versionsAfterIncrement.length : 0).toBeGreaterThan(
    Array.isArray(versionsAfterCreate) ? versionsAfterCreate.length : 0,
  );

  await page.goto(`/#knowledge?course_id=${courseId}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1_000);
  await capture(page, "17-increment-published");
});
