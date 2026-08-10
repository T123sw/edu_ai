import { resolve } from "node:path";

import type { APIResponse, Page, Response, TestInfo } from "playwright/test";

import {
  attachJsonEvidence,
  captureApiEvidence,
  expect,
  installDeterministicLearningAgent,
  learningApiBaseUrl,
  learningCourseId,
  learningE2eTitle,
  loginAs,
  loginToken,
  test,
  type AgentEvidence,
  type ApiEvidence,
} from "./fixtures/learningLoop";

const teacherCredentials = { username: "teacher", password: "teacher123" };
const studentCredentials = { username: "student", password: "student123" };

async function attachScreenshot(
  page: Page,
  testInfo: TestInfo,
  artifactDir: string,
  name: string,
): Promise<void> {
  const path = resolve(artifactDir, `${name}.png`);
  await page.screenshot({ path, fullPage: true });
  await testInfo.attach(name, { path, contentType: "image/png" });
}

async function capturePageResponse(
  evidence: ApiEvidence[],
  label: string,
  response: Response,
): Promise<Record<string, unknown>> {
  const body = await response.json() as Record<string, unknown>;
  evidence.push({
    label,
    method: response.request().method(),
    url: response.url(),
    status: response.status(),
    body,
  });
  return body;
}

async function captureRequest(
  evidence: ApiEvidence[],
  label: string,
  response: APIResponse,
): Promise<Record<string, unknown>> {
  return await captureApiEvidence(evidence, label, response) as Record<string, unknown>;
}

async function clearAuthentication(page: Page): Promise<void> {
  await page.evaluate(() => window.localStorage.removeItem("edu-ai-auth"));
  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByText("登录 Edu AI")).toBeVisible();
}

test("teacher and student complete a truthful learning loop with role-scoped agents", async ({
  browser,
  request,
  learningBackend,
}, testInfo) => {
  const apiEvidence: ApiEvidence[] = [];
  const agentEvidence: AgentEvidence[] = [];
  const baseURL = learningBackend.frontendBaseUrl;
  const contextOptions = {
    baseURL,
    viewport: testInfo.project.use.viewport,
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
    reducedMotion: "reduce" as const,
  };
  const teacherContext = await browser.newContext(contextOptions);
  const studentContext = await browser.newContext(contextOptions);
  const teacherPage = await teacherContext.newPage();
  const studentPage = await studentContext.newPage();

  try {
    await loginAs(teacherPage, teacherCredentials.username, teacherCredentials.password);
    await teacherPage.goto(`/#learning?course_id=${learningCourseId}`, { waitUntil: "domcontentloaded" });
    await expect(teacherPage.getByRole("heading", { name: "发布任务，查看真实学习反馈" })).toBeVisible();
    await teacherPage.getByRole("button", { name: /新建学习任务/ }).click();
    const createPanel = teacherPage.getByRole("region", { name: "新建学习任务" });
    await createPanel.getByLabel("任务标题").fill(learningE2eTitle);
    await createPanel.getByLabel("学习说明").fill("打开指定课程资源，完成后按真实口径自报。 ");
    await createPanel.getByLabel("知识点 ID").fill("computational-thinking-loop2");
    const resourceCheckbox = createPanel.getByRole("checkbox").first();
    await expect(resourceCheckbox, "the real course must expose at least one shared resource").toBeVisible();
    await resourceCheckbox.check();

    const createResponsePromise = teacherPage.waitForResponse((response) =>
      response.request().method() === "POST"
      && response.url().endsWith(`/api/courses/${learningCourseId}/learning/tasks`),
    );
    await createPanel.getByRole("button", { name: "保存草稿" }).click();
    const created = await capturePageResponse(apiEvidence, "teacher-create-task", await createResponsePromise);
    const taskId = String(created.task_id ?? "");
    expect(taskId).toMatch(/^lt_[a-z0-9]+$/);
    expect(String(created.title)).toBe(learningE2eTitle);
    await expect(teacherPage.getByText("学习任务草稿已创建，可确认后发布给学生。")).toBeVisible();

    const publishResponsePromise = teacherPage.waitForResponse((response) =>
      response.request().method() === "POST"
      && response.url().endsWith(`/api/courses/${learningCourseId}/learning/tasks/${taskId}/publish`),
    );
    await teacherPage.getByRole("button", { name: "发布给学生" }).click();
    const published = await capturePageResponse(apiEvidence, "teacher-publish-task", await publishResponsePromise);
    expect(published.status).toBe("published");
    await expect(teacherPage.getByText("任务已发布，学生端现在可以开始学习。")).toBeVisible();
    await expect(teacherPage.getByText("课程学生").locator("..").getByText("1", { exact: true })).toBeVisible();
    await attachScreenshot(teacherPage, testInfo, learningBackend.artifactDir, "01-teacher-published");

    await loginAs(studentPage, studentCredentials.username, studentCredentials.password);
    await studentPage.goto("/#student-home", { waitUntil: "domcontentloaded" });
    const courseCard = studentPage.getByRole("link", { name: "计算思维" });
    await expect(courseCard.getByText("待学习任务")).toBeVisible();
    await expect(courseCard.getByText("1", { exact: true })).toBeVisible();
    await attachScreenshot(studentPage, testInfo, learningBackend.artifactDir, "02-student-home-pending");

    await studentPage.goto(`/#student-learning?course_id=${learningCourseId}`, { waitUntil: "domcontentloaded" });
    const studentTask = studentPage.getByRole("article").filter({ hasText: learningE2eTitle });
    await expect(studentTask).toBeVisible();
    const openResponsePromise = studentPage.waitForResponse((response) =>
      response.request().method() === "POST"
      && response.url().endsWith(`/api/courses/${learningCourseId}/learning/tasks/${taskId}/events`),
    );
    await studentTask.getByRole("button", { name: /打开资源/ }).click();
    const opened = await capturePageResponse(apiEvidence, "student-open-resource", await openResponsePromise);
    expect((opened.progress as Record<string, unknown>).progress_percent).toBe(1);

    await studentPage.goto(`/#student-learning?course_id=${learningCourseId}`, { waitUntil: "domcontentloaded" });
    const inProgressTask = studentPage.getByRole("article").filter({ hasText: learningE2eTitle });
    await expect(inProgressTask.getByText("进行中 · 1%")).toBeVisible();
    await attachScreenshot(studentPage, testInfo, learningBackend.artifactDir, "03-student-in-progress");

    studentPage.once("dialog", async (dialog) => {
      expect(dialog.message()).toContain("学生自报完成");
      expect(dialog.message()).toContain("不代表测评通过");
      await dialog.accept();
    });
    const completeResponsePromise = studentPage.waitForResponse((response) =>
      response.request().method() === "POST"
      && response.url().endsWith(`/api/courses/${learningCourseId}/learning/tasks/${taskId}/events`),
    );
    await inProgressTask.getByRole("button", { name: "我已完成" }).click();
    const completed = await capturePageResponse(apiEvidence, "student-self-report-complete", await completeResponsePromise);
    expect((completed.progress as Record<string, unknown>).completion_basis).toBe("self_reported");
    await expect(inProgressTask.getByText("完成口径：学生自报完成")).toBeVisible();
    await expect(studentPage.getByText(/不代表测评通过或已经掌握/)).toBeVisible();
    await attachScreenshot(studentPage, testInfo, learningBackend.artifactDir, "04-student-self-reported");

    await teacherPage.reload({ waitUntil: "domcontentloaded" });
    await expect(teacherPage.getByRole("heading", { name: learningE2eTitle, exact: true })).toBeVisible();
    const teacherProgressRow = teacherPage.locator(".learning-progress-table > div").filter({ hasText: "student" });
    await expect(teacherProgressRow.locator("span").nth(1)).toHaveText("已完成");
    await expect(teacherProgressRow.getByText("学生自报完成", { exact: true })).toBeVisible();
    await expect(teacherPage.getByText("已开始").locator("..").getByText("1", { exact: true })).toBeVisible();
    await expect(teacherPage.getByText("已完成").locator("..").getByText("1", { exact: true })).toBeVisible();
    await expect(teacherPage.getByText("完成率").locator("..").getByText("100%", { exact: true })).toBeVisible();
    await attachScreenshot(teacherPage, testInfo, learningBackend.artifactDir, "05-teacher-feedback");

    let teacherToken = await loginToken(request, teacherCredentials.username, teacherCredentials.password);
    let studentToken = await loginToken(request, studentCredentials.username, studentCredentials.password);
    const auth = (token: string) => ({ Authorization: `Bearer ${token}` });
    const initialSummary = await captureRequest(
      apiEvidence,
      "summary-after-ui-loop",
      await request.get(`${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/progress`, {
        headers: auth(teacherToken),
      }),
    );
    expect(initialSummary.completed_students).toBe(1);
    expect(((initialSummary.progress as Array<Record<string, unknown>>)[0]).completion_basis).toBe("self_reported");

    const studentCreate = await request.post(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks`,
      {
        headers: auth(studentToken),
        data: { title: "forbidden", instructions: "", resource_refs: [], knowledge_point_ids: [] },
      },
    );
    await captureRequest(apiEvidence, "student-create-task-forbidden", studentCreate);
    expect(studentCreate.status()).toBe(403);
    const studentSummary = await request.get(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/progress`,
      { headers: auth(studentToken) },
    );
    await captureRequest(apiEvidence, "student-read-class-summary-forbidden", studentSummary);
    expect(studentSummary.status()).toBe(403);
    const teacherWritesEvent = await request.post(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/events`,
      {
        headers: auth(teacherToken),
        data: { event_id: `e2e-teacher-${taskId}`, event_type: "started", progress_percent: 1 },
      },
    );
    await captureRequest(apiEvidence, "teacher-write-student-event-forbidden", teacherWritesEvent);
    expect(teacherWritesEvent.status()).toBe(403);

    const eventId = `e2e-idempotent-${taskId}`;
    const lateStarted = await request.post(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/events`,
      {
        headers: auth(studentToken),
        data: { event_id: eventId, event_type: "started", progress_percent: 1 },
      },
    );
    const lateStartedBody = await captureRequest(apiEvidence, "late-started-after-completion", lateStarted);
    expect(lateStartedBody.created).toBe(true);
    expect((lateStartedBody.progress as Record<string, unknown>).progress_percent).toBe(100);
    expect((lateStartedBody.progress as Record<string, unknown>).completion_basis).toBe("self_reported");
    const duplicate = await request.post(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/events`,
      {
        headers: auth(studentToken),
        data: { event_id: eventId, event_type: "started", progress_percent: 1 },
      },
    );
    const duplicateBody = await captureRequest(apiEvidence, "duplicate-event-id", duplicate);
    expect(duplicateBody.created).toBe(false);
    expect((duplicateBody.progress as Record<string, unknown>).evidence_count).toBe(
      (lateStartedBody.progress as Record<string, unknown>).evidence_count,
    );

    const summaryBeforeRestart = await captureRequest(
      apiEvidence,
      "summary-before-restart",
      await request.get(`${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/progress`, {
        headers: auth(teacherToken),
      }),
    );

    await learningBackend.restart();
    teacherToken = await loginToken(request, teacherCredentials.username, teacherCredentials.password);
    studentToken = await loginToken(request, studentCredentials.username, studentCredentials.password);
    const summaryAfterRestart = await captureRequest(
      apiEvidence,
      "summary-after-backend-restart-and-login",
      await request.get(`${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/progress`, {
        headers: auth(teacherToken),
      }),
    );
    expect(summaryAfterRestart).toEqual(summaryBeforeRestart);

    await clearAuthentication(teacherPage);
    await clearAuthentication(studentPage);
    await loginAs(teacherPage, teacherCredentials.username, teacherCredentials.password);
    await loginAs(studentPage, studentCredentials.username, studentCredentials.password);
    await teacherPage.goto(`/#learning?course_id=${learningCourseId}`, { waitUntil: "domcontentloaded" });
    await studentPage.goto(`/#student-learning?course_id=${learningCourseId}`, { waitUntil: "domcontentloaded" });
    await expect(teacherPage.getByRole("heading", { name: learningE2eTitle, exact: true })).toBeVisible();
    await expect(studentPage.getByRole("article").filter({ hasText: learningE2eTitle }).getByText("完成口径：学生自报完成")).toBeVisible();

    const teacherFacts = {
      task_id: taskId,
      title: learningE2eTitle,
      enrolled_students: summaryAfterRestart.enrolled_students,
      started_students: summaryAfterRestart.started_students,
      completed_students: summaryAfterRestart.completed_students,
      completion_rate: summaryAfterRestart.completion_rate,
      completion_basis_counts: { self_reported: 1 },
    };
    const teacherAnswer = `${learningE2eTitle}：课程学生 1 人，已开始 1 人，学生自报完成 1 人，完成率 100%。完成口径是学生自报完成，不等于测评通过或知识点已掌握。`;
    await installDeterministicLearningAgent(teacherPage, agentEvidence, {
      actor: "teacher",
      answer: teacherAnswer,
      structuredFacts: teacherFacts,
      toolName: "get_course_learning_progress",
    });
    await teacherPage.goto(`/#ai?course_id=${learningCourseId}`, { waitUntil: "domcontentloaded" });
    await teacherPage.getByPlaceholder(/开始输入问题/).fill("这门课最新学习任务完成情况怎样？只根据学习记录回答，并说明完成口径。");
    await teacherPage.getByPlaceholder(/开始输入问题/).press("Enter");
    const teacherAgentAnswer = teacherPage
      .locator(".chat-panel__markdown-paragraph")
      .filter({ hasText: learningE2eTitle })
      .last();
    await expect(teacherAgentAnswer).toContainText(learningE2eTitle);
    await expect(teacherAgentAnswer).toContainText("学生自报完成 1 人");
    await expect(teacherAgentAnswer).toContainText("完成率 100%");
    await attachScreenshot(teacherPage, testInfo, learningBackend.artifactDir, "06-teacher-agent-deterministic");

    const studentFacts = {
      projection: "student",
      completed_tasks: [{ task_id: taskId, title: learningE2eTitle, completion_basis: "self_reported" }],
    };
    const studentAnswer = `你刚完成了任务 ${taskId}（${learningE2eTitle}），口径为学生自报完成。下一步请复盘指定课程资源和 computational-thinking-loop2 知识点。`;
    await installDeterministicLearningAgent(studentPage, agentEvidence, {
      actor: "student",
      answer: studentAnswer,
      structuredFacts: studentFacts,
      toolName: "get_my_learning_progress",
      failHistoricalConversation: true,
    });
    await studentPage.goto(`/#student-ai?course_id=${learningCourseId}`, { waitUntil: "domcontentloaded" });
    await expect(studentPage.getByText("历史对话未能恢复")).toBeVisible();
    await studentPage.getByRole("button", { name: "新建对话" }).click();
    await studentPage.getByPlaceholder(/开始输入问题/).fill("我刚完成了什么学习任务？结合我的学习记录告诉我下一步做什么。");
    await studentPage.getByPlaceholder(/开始输入问题/).press("Enter");
    const studentAgentAnswer = studentPage
      .locator(".chat-panel__markdown-paragraph")
      .filter({ hasText: learningE2eTitle })
      .last();
    await expect(studentAgentAnswer).toContainText(learningE2eTitle);
    await expect(studentAgentAnswer).toContainText("学生自报完成");
    await expect(studentPage.getByText(/job_stale_should_not_leak/)).toHaveCount(0);
    await attachScreenshot(studentPage, testInfo, learningBackend.artifactDir, "07-student-agent-history-recovery");

    expect(agentEvidence).toHaveLength(2);
    expect(agentEvidence[0].trace.task_domain).toBe("course_learning");
    expect(agentEvidence[1].trace.task_domain).toBe("course_learning");
    const serializedAgentEvidence = JSON.stringify(agentEvidence);
    expect(serializedAgentEvidence).not.toContain("query_generation_job_status");
    expect(serializedAgentEvidence).not.toContain("query_task_status");
    expect(studentAnswer).not.toMatch(/job_[a-z0-9]+/);
    expect(studentAnswer).toContain(taskId);
  } finally {
    await attachJsonEvidence(testInfo, "learning-loop-api-summary", apiEvidence);
    await attachJsonEvidence(testInfo, "deterministic-agent-evidence", agentEvidence);
    await attachJsonEvidence(testInfo, "learning-loop-isolation", {
      apiBaseUrl: learningApiBaseUrl,
      courseId: learningCourseId,
      learningDbPath: learningBackend.dbPath,
      taskPrefix: "E2E-LOOP2-",
      retries: testInfo.retry,
      modelMode: "deterministic-learning-e2e (automation); real model requires separate manual acceptance",
    });
    await Promise.allSettled([teacherContext.close(), studentContext.close()]);
  }
});
