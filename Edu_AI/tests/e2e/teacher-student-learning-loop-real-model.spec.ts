import { resolve } from "node:path";

import type { Page, Response, TestInfo } from "playwright/test";

import {
  attachJsonEvidence,
  expect,
  learningApiBaseUrl,
  learningCourseId,
  loginAs,
  loginToken,
  test,
} from "./fixtures/learningLoop";

const teacherCredentials = { username: "teacher", password: "teacher123" };
const studentCredentials = { username: "student", password: "student123" };

type SseFrame = { type?: string; payload?: Record<string, unknown> };

async function readSseFrames(response: Response): Promise<SseFrame[]> {
  const body = await response.text();
  return body
    .split("\n")
    .filter((line) => line.startsWith("data: "))
    .map((line) => JSON.parse(line.slice(6)) as SseFrame);
}

async function askLearningAgent(
  page: Page,
  question: string,
): Promise<{ frames: SseFrame[]; answer: string }> {
  const streamPromise = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && response.url().endsWith("/api/chat/v2/stream"),
  );
  const input = page.getByPlaceholder(/开始输入问题/);
  await input.fill(question);
  await input.press("Enter");
  const frames = await readSseFrames(await streamPromise);
  const result = frames.find((frame) => frame.type === "result")?.payload;
  const message = result?.message as Record<string, unknown> | undefined;
  return { frames, answer: String(message?.content ?? "") };
}

async function screenshot(page: Page, testInfo: TestInfo, artifactDir: string, name: string) {
  const path = resolve(artifactDir, `${name}.png`);
  await page.screenshot({ path, fullPage: true });
  await testInfo.attach(name, { path, contentType: "image/png" });
}

test("qwen answers teacher and student from role-scoped learning facts", async ({
  browser,
  request,
  learningBackend,
}, testInfo) => {
  test.skip(
    process.env.LEARNING_E2E_REAL_MODEL !== "1",
    "Set LEARNING_E2E_REAL_MODEL=1 and load the local model environment for manual acceptance.",
  );
  test.setTimeout(300_000);

  const teacherToken = await loginToken(request, teacherCredentials.username, teacherCredentials.password);
  const studentToken = await loginToken(request, studentCredentials.username, studentCredentials.password);
  const auth = (token: string) => ({ Authorization: `Bearer ${token}` });
  const title = `E2E-QWEN-${Date.now()}`;
  const createdResponse = await request.post(
    `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks`,
    {
      headers: auth(teacherToken),
      data: {
        title,
        instructions: "复习计算思维课程材料，并按真实学习记录说明完成口径。",
        resource_refs: [],
        knowledge_point_ids: ["computational-thinking-qwen-e2e"],
      },
    },
  );
  expect(createdResponse.ok()).toBeTruthy();
  const created = await createdResponse.json() as Record<string, unknown>;
  const taskId = String(created.task_id ?? "");
  expect(taskId).toMatch(/^lt_[a-z0-9]+$/);
  const publishResponse = await request.post(
    `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/publish`,
    { headers: auth(teacherToken) },
  );
  expect(publishResponse.ok()).toBeTruthy();
  const completeResponse = await request.post(
    `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/events`,
    {
      headers: auth(studentToken),
      data: {
        event_id: `evt-qwen-${taskId}`,
        event_type: "completed",
        progress_percent: 100,
      },
    },
  );
  expect(completeResponse.ok()).toBeTruthy();

  const contextOptions = {
    baseURL: learningBackend.frontendBaseUrl,
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
    await teacherPage.goto(`/#ai?course_id=${learningCourseId}`, { waitUntil: "domcontentloaded" });
    const teacherResult = await askLearningAgent(
      teacherPage,
      "请查询这门课最新学习任务完成情况。必须原样写出任务标题，只根据系统学习记录回答，说明人数和完成口径，不要查询后台生成任务。",
    );
    expect(teacherResult.answer).toContain(title);
    expect(teacherResult.answer).toContain("学生自报");
    expect(teacherResult.answer).toContain("不等于测评通过");
    expect(teacherResult.answer).not.toMatch(/已测评通过|已经掌握/);
    const teacherSerialized = JSON.stringify(teacherResult.frames);
    expect(teacherSerialized).toContain("course_learning");
    expect(teacherSerialized).not.toContain("query_generation_job_status");
    expect(teacherSerialized).not.toContain("query_task_status");
    await expect(teacherPage.locator(".chat-panel__markdown-paragraph").filter({ hasText: title }).last()).toBeVisible();
    await screenshot(teacherPage, testInfo, learningBackend.artifactDir, "08-teacher-agent-qwen");

    await loginAs(studentPage, studentCredentials.username, studentCredentials.password);
    await studentPage.goto(`/#student-ai?course_id=${learningCourseId}`, { waitUntil: "domcontentloaded" });
    const studentResult = await askLearningAgent(
      studentPage,
      "我刚完成了什么学习任务？必须原样写出任务标题，说明真实完成口径，并给我一个下一步建议。只查询我的学习记录。",
    );
    expect(studentResult.answer).toContain(title);
    expect(studentResult.answer).toContain("学生自报");
    expect(studentResult.answer).not.toMatch(/job_[a-z0-9]+/);
    expect(studentResult.answer).toContain("不等于测评通过");
    expect(studentResult.answer).not.toMatch(/已测评通过|已经掌握/);
    const studentSerialized = JSON.stringify(studentResult.frames);
    expect(studentSerialized).toContain("course_learning");
    expect(studentSerialized).not.toContain("query_generation_job_status");
    expect(studentSerialized).not.toContain("query_task_status");
    await expect(studentPage.locator(".chat-panel__markdown-paragraph").filter({ hasText: title }).last()).toBeVisible();
    await screenshot(studentPage, testInfo, learningBackend.artifactDir, "09-student-agent-qwen");

    await attachJsonEvidence(testInfo, "qwen-learning-agent-evidence", {
      model: "qwen environment configuration (secret omitted)",
      course_id: learningCourseId,
      task_id: taskId,
      title,
      teacher: teacherResult,
      student: studentResult,
    });
  } finally {
    await Promise.allSettled([teacherContext.close(), studentContext.close()]);
  }
});
