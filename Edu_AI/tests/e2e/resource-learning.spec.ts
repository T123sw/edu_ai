import type { APIRequestContext, Page } from "playwright/test";

import {
  expect,
  learningApiBaseUrl,
  learningCourseId,
  learningResourceId,
  learningResourceVersion,
  loginAs,
  loginToken,
  playExplanationToCoverage,
  test,
} from "./fixtures/learningLoop";


const teacherCredentials = { username: "teacher", password: "teacher123" };
const studentCredentials = { username: "student", password: "student123" };

function auth(token: string) {
  return { Authorization: `Bearer ${token}` };
}

function pathEndsWith(url: string, suffix: string) {
  return decodeURIComponent(new URL(url).pathname).endsWith(suffix);
}

async function createPublishedReadingTask(
  request: APIRequestContext,
  teacherToken: string,
  title: string,
) {
  const createdResponse = await request.post(
    `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks`,
    {
      headers: auth(teacherToken),
      data: {
        task_type: "reading",
        title,
        instructions: "学习指定 AI 课堂；资源学习记录与任务状态分别计算。",
        resource_refs: [
          { material_type: "classroom", material_id: learningResourceId },
        ],
        knowledge_point_ids: ["sequence-selection-loop"],
      },
    },
  );
  expect(createdResponse.ok()).toBeTruthy();
  const created = await createdResponse.json() as Record<string, any>;
  const publishedResponse = await request.post(
    `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${created.task_id}/publish`,
    { headers: auth(teacherToken) },
  );
  expect(publishedResponse.ok()).toBeTruthy();
  return await publishedResponse.json() as Record<string, any>;
}

async function resourceProgress(request: APIRequestContext, studentToken: string) {
  const response = await request.get(
    `${learningApiBaseUrl}/api/courses/${learningCourseId}/resources/${learningResourceId}/versions/${learningResourceVersion}/learning/me`,
    { headers: auth(studentToken) },
  );
  expect(response.ok()).toBeTruthy();
  return await response.json() as Record<string, any>;
}

async function goToPage(page: Page, target: number) {
  const count = page.locator(".classroom-page-count");
  for (let current = Number((await count.innerText()).split("/")[0].trim()); current < target; current += 1) {
    await page.getByRole("button", { name: "下一页" }).click();
    await expect(count).toHaveText(`${current + 1} / 5`);
  }
  for (let current = Number((await count.innerText()).split("/")[0].trim()); current > target; current -= 1) {
    await page.getByRole("button", { name: "上一页" }).click();
    await expect(count).toHaveText(`${current - 1} / 5`);
  }
}

test("student resource learning remains versioned and separate from teacher tasks", async ({
  browser,
  request,
  learningBackend,
}, testInfo) => {
  test.setTimeout(240_000);
  const contextOptions = {
    baseURL: learningBackend.frontendBaseUrl,
    viewport: testInfo.project.use.viewport,
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
    reducedMotion: "reduce" as const,
  };
  const studentContext = await browser.newContext(contextOptions);
  const studentPage = await studentContext.newPage();
  await studentPage.addInitScript(() => {
    const speech = window.speechSynthesis;
    const timers = new Set<number>();
    Object.defineProperty(speech, "speak", {
      configurable: true,
      value: (utterance: SpeechSynthesisUtterance) => {
        const timer = window.setTimeout(() => {
          timers.delete(timer);
          utterance.onend?.(new Event("end") as unknown as SpeechSynthesisEvent);
        }, 10_000);
        timers.add(timer);
      },
    });
    Object.defineProperty(speech, "cancel", {
      configurable: true,
      value: () => {
        timers.forEach((timer) => window.clearTimeout(timer));
        timers.clear();
      },
    });
    Object.defineProperty(speech, "getVoices", {
      configurable: true,
      value: () => [],
    });
  });
  const teacherToken = await loginToken(
    request,
    teacherCredentials.username,
    teacherCredentials.password,
  );
  const studentToken = await loginToken(
    request,
    studentCredentials.username,
    studentCredentials.password,
  );
  const sameVersionTitle = `E2E 同版本资源任务 ${Date.now()}`;
  const differentVersionTitle = `E2E 不同版本资源任务 ${Date.now()}`;

  try {
    await loginAs(studentPage, studentCredentials.username, studentCredentials.password);
    await studentPage.goto(
      `/#student-classroom?course_id=${learningCourseId}&node_id=sequence-selection-loop&resource_id=${learningResourceId}`,
      { waitUntil: "domcontentloaded" },
    );
    const directory = studentPage.getByRole("tree", { name: "课程目录" });
    await expect(directory).toBeVisible({ timeout: 30_000 });
    await expect(directory.getByRole("treeitem", {
      name: /顺序、分支与循环结构 AI 课堂/,
    })).toBeVisible();

    const sameVersionTask = await createPublishedReadingTask(
      request,
      teacherToken,
      sameVersionTitle,
    );
    const pendingTasksResponse = await request.get(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks`,
      { headers: auth(studentToken) },
    );
    const pendingTasks = await pendingTasksResponse.json() as Array<Record<string, any>>;
    const pendingTask = pendingTasks.find((item) => item.task_id === sameVersionTask.task_id);
    expect(pendingTask?.resource_evidence).toEqual([
      expect.objectContaining({
        resource_id: learningResourceId,
        resource_version: learningResourceVersion,
        condition_status: "pending",
      }),
    ]);

    const capturedEventBatches: Array<Record<string, any>> = [];
    studentPage.on("request", (requestValue) => {
      if (
        requestValue.method() === "POST"
        && pathEndsWith(requestValue.url(), "/events:batch")
      ) {
        const body = requestValue.postDataJSON();
        if (body) capturedEventBatches.push(body as Record<string, any>);
      }
    });
    const sessionResponsePromise = studentPage.waitForResponse((response) =>
      response.request().method() === "POST"
      && response.url().endsWith(`/versions/${learningResourceVersion}/learning/sessions`),
    );
    await studentPage.getByRole("link", { name: "进入课堂学习" }).click();
    let session = await (await sessionResponsePromise).json() as Record<string, any>;
    await expect(studentPage.getByRole("heading", {
      name: "顺序、分支与循环结构 AI 课堂",
    })).toBeVisible();
    await studentPage.getByRole("link", { name: "返回 AI 课堂列表" }).click();
    await expect(studentPage).toHaveURL(new RegExp(
      `student-classroom\\?course_id=${learningCourseId}.*node_id=sequence-selection-loop.*resource_id=${learningResourceId}`,
    ));
    await expect(studentPage.getByRole("tree", { name: "课程目录" })
      .getByRole("treeitem", { name: /顺序、分支与循环结构 AI 课堂/ })).toBeVisible();
    const reopenedSessionResponse = studentPage.waitForResponse((response) =>
      response.request().method() === "POST"
      && response.url().endsWith(`/versions/${learningResourceVersion}/learning/sessions`),
    );
    await studentPage.getByRole("link", { name: "进入课堂学习" }).click();
    session = await (await reopenedSessionResponse).json() as Record<string, any>;
    await expect(studentPage.getByRole("heading", {
      name: "顺序、分支与循环结构 AI 课堂",
    })).toBeVisible();
    capturedEventBatches.length = 0;
    const progress = studentPage.locator(".resource-learning-progress").first();
    await expect(progress).toContainText("讲解完整度 0%");

    // 翻页和互动演示只记行为，不增加讲解完整度。
    await goToPage(studentPage, 5);
    await studentPage.frameLocator('iframe[title="互动场景 demo-1"]')
      .getByRole("button", { name: "执行一次演示" })
      .click();
    await expect(progress).toContainText("讲解完整度 0%");
    await goToPage(studentPage, 1);

    // 问答中断会立即切断连续播放，等待回答的时间不会继续累计。
    await studentPage.route("**/qa/turns", async (route) => {
      await new Promise((resolvePromise) => setTimeout(resolvePromise, 900));
      await route.abort("failed");
    });
    await studentPage.getByRole("button", { name: "播放当前页", exact: true }).click();
    await studentPage.waitForTimeout(300);
    await studentPage.getByLabel("课堂问题").fill("为什么需要分支结构？");
    await studentPage.getByRole("button", { name: "发送", exact: true }).click();
    await expect(studentPage.getByRole("button", { name: "问答中", exact: true })).toBeVisible();
    await expect(studentPage.getByRole("button", { name: "放弃并继续授课" })).toBeVisible();
    const coverageDuringQa = (await resourceProgress(request, studentToken))
      .explanation_covered_ms;
    await studentPage.waitForTimeout(500);
    expect((await resourceProgress(request, studentToken)).explanation_covered_ms)
      .toBe(coverageDuringQa);
    await studentPage.getByRole("button", { name: "放弃并继续授课" }).click();
    await expect(studentPage.getByRole("button", { name: "暂停", exact: true })).toBeVisible();
    await studentPage.getByRole("button", { name: "暂停", exact: true }).click();

    await playExplanationToCoverage(studentPage, 80);
    await expect.poll(
      async () => Number((await progress.innerText()).match(/讲解完整度\s*(\d+)%/)?.[1] ?? 0),
    ).toBeGreaterThanOrEqual(80);
    await expect(progress).toContainText("习题进度 0/3");
    await expect(progress).toContainText("学习中");

    await goToPage(studentPage, 4);
    const quiz = studentPage.getByRole("region", { name: "课堂舞台" });
    await quiz.getByText("哪种结构适合按条件选择路径？")
      .locator("xpath=ancestor::article")
      .getByLabel(/A\. 顺序结构/)
      .check();
    await quiz.getByText("哪种结构适合重复执行？")
      .locator("xpath=ancestor::article")
      .getByLabel(/B\. 顺序结构/)
      .check();
    await quiz.getByPlaceholder("在这里输入你的答案").fill("完全错误的答案");
    const submittedQuestions = studentPage.waitForResponse((response) =>
      response.request().method() === "POST"
      && pathEndsWith(
        response.url(),
        `/versions/${learningResourceVersion}/learning/questions:submit`,
      ),
    );
    await quiz.getByRole("button", { name: "提交并查看解析" }).click();
    expect((await submittedQuestions).status()).toBe(200);
    await expect(progress).toContainText("习题进度 3/3");
    await expect(progress).toContainText("已完成");
    await expect(quiz.getByText("回答有误")).toHaveCount(2);

    const completed = await resourceProgress(request, studentToken);
    expect(completed.status).toBe("completed");
    expect(completed.explanation_coverage_percent).toBeGreaterThanOrEqual(80);
    expect(completed.answered_question_count).toBe(3);
    expect(completed.correct_count_latest).toBe(0);
    expect(completed.demo_interaction_count).toBeGreaterThanOrEqual(1);

    // 重放完全相同的事件批次不得重复增加区间；客户端伪造百分比会被拒绝。
    const eventsPath = `${learningApiBaseUrl}/api/courses/${learningCourseId}/resources/${learningResourceId}/versions/${learningResourceVersion}/learning/sessions/${session.session_id}/events:batch`;
    expect(capturedEventBatches.length).toBeGreaterThan(0);
    const beforeReplay = await resourceProgress(request, studentToken);
    const replay = await request.post(eventsPath, {
      headers: auth(studentToken),
      data: capturedEventBatches[0],
    });
    expect(replay.ok()).toBeTruthy();
    expect((await resourceProgress(request, studentToken)).explanation_covered_ms)
      .toBe(beforeReplay.explanation_covered_ms);
    const forged = await request.post(eventsPath, {
      headers: auth(studentToken),
      data: {
        events: [{
          event_id: "forged-progress-percent",
          sequence_number: 99999,
          event_type: "timeline_heartbeat",
          scene_id: "explain-1",
          timeline_from_ms: 0,
          timeline_to_ms: 2_000,
          occurred_at: new Date().toISOString(),
          progress_percent: 100,
        }],
      },
    });
    expect(forged.status()).toBe(422);

    const analyticsResponse = await request.get(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/resources/${learningResourceId}/versions/${learningResourceVersion}/learning/analytics`,
      { headers: auth(teacherToken) },
    );
    const analytics = await analyticsResponse.json() as Record<string, any>;
    expect(analytics.completed_student_count).toBe(1);
    expect(analytics.demo_interaction_count).toBeGreaterThanOrEqual(1);

    await studentPage.goto(
      `/#student-learning?course_id=${learningCourseId}`,
      { waitUntil: "domcontentloaded" },
    );
    const sameVersionCard = studentPage.getByRole("article").filter({
      hasText: sameVersionTitle,
    });
    await expect(sameVersionCard).toContainText("资源条件已满足 · 证据版本 3");
    await expect(sameVersionCard).toContainText("未开始");
    await expect(sameVersionCard.getByRole("button", { name: "开始学习" })).toBeVisible();

    // 重启并重新登录后仍从数据库恢复相同的课程资源学习投影。
    await learningBackend.restart();
    const recoveryContext = await browser.newContext(contextOptions);
    const recoveryPage = await recoveryContext.newPage();
    await loginAs(recoveryPage, studentCredentials.username, studentCredentials.password);
    await recoveryPage.goto(
      `/#student-classroom?course_id=${learningCourseId}&node_id=sequence-selection-loop&resource_id=${learningResourceId}`,
      { waitUntil: "domcontentloaded" },
    );
    const recoveredResource = recoveryPage.getByRole("tree", { name: "课程目录" })
      .getByRole("treeitem", { name: /顺序、分支与循环结构 AI 课堂.*已完成/ });
    await expect(recoveredResource).toBeVisible({ timeout: 30_000 });
    await recoveryPage.screenshot({
      path: `${learningBackend.artifactDir}/student-resource-learning-completed.png`,
      fullPage: true,
    });
    await recoveryContext.close();

    // 发布 v4 后，新任务严格绑定 v4；既有 v3 证据不能满足它。
    await learningBackend.approveResourceVersion(4);
    const differentVersionTask = await createPublishedReadingTask(
      request,
      teacherToken,
      differentVersionTitle,
    );
    const versionedTasksResponse = await request.get(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks`,
      { headers: auth(studentToken) },
    );
    const versionedTasks = await versionedTasksResponse.json() as Array<Record<string, any>>;
    const v3Task = versionedTasks.find((item) => item.task_id === sameVersionTask.task_id);
    const v4Task = versionedTasks.find((item) => item.task_id === differentVersionTask.task_id);
    expect(v3Task?.resource_evidence[0]).toEqual(expect.objectContaining({
      resource_version: 3,
      condition_status: "satisfied",
    }));
    expect(v4Task?.resource_evidence[0]).toEqual(expect.objectContaining({
      resource_version: 4,
      condition_status: "pending",
    }));
    expect(v4Task?.my_progress?.status ?? "not_started").toBe("not_started");
  } finally {
    await studentContext.close();
  }
});
