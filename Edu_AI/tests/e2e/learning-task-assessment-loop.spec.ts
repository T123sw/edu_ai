import type { APIRequestContext, Page } from "playwright/test";

import {
  expect,
  learningApiBaseUrl,
  learningCourseId,
  loginAs,
  loginToken,
  test,
} from "./fixtures/learningLoop";

const teacherCredentials = { username: "teacher", password: "teacher123" };
const studentCredentials = { username: "student", password: "student123" };

function auth(token: string) {
  return { Authorization: `Bearer ${token}` };
}

async function installDeterministicAssessment(
  request: APIRequestContext,
  token: string,
  taskId: string,
) {
  const base = `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/assessment`;
  const detectedResponse = await request.post(`${base}/detect`, { headers: auth(token) });
  expect(detectedResponse.ok()).toBeTruthy();
  const draft = await detectedResponse.json() as Record<string, any>;
  const weights = [10, 15, 25, 50];
  const items = weights.map((maxScore, index) => ({
    assessment_item_id: `asi-e2e-${index + 1}`,
    assessment_version_id: draft.assessment_version_id,
    position: index + 1,
    item_type: "single_choice",
    prompt: {
      stem: `循环测评第 ${index + 1} 题`,
      options: [
        { id: "correct", text: "正确答案" },
        { id: "wrong", text: "错误答案" },
      ],
    },
    scoring_key: { correct_option_id: "correct" },
    rubric: {},
    max_score: maxScore,
    grading_provider: "deterministic",
    knowledge_point_ids: ["loops"],
    source_refs: [{ material_type: "learning_task", material_id: taskId }],
    source_exposure_state: "private",
    created_origin: "manual",
  }));
  const update = await request.put(`${base}/draft`, {
    headers: auth(token),
    data: {
      expected_revision: draft.draft_revision,
      pass_threshold: 60,
      mastery_threshold: 80,
      max_attempts: 3,
      assessment_mode: "closed_book",
      answer_reveal_policy: "after_finish_or_exhausted",
      shuffle_questions: false,
      shuffle_options: false,
      items,
    },
  });
  expect(update.ok()).toBeTruthy();
  return await update.json() as Record<string, any>;
}

async function createCodeReviewTask(
  request: APIRequestContext,
  token: string,
  title: string,
) {
  const taskResponse = await request.post(
    `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks`,
    {
      headers: auth(token),
      data: {
        title,
        instructions: "提交 Python 实现，由教师依据量规完成最终评分。",
        resource_refs: [],
        knowledge_point_ids: ["loops-code"],
      },
    },
  );
  expect(taskResponse.ok()).toBeTruthy();
  const task = await taskResponse.json() as Record<string, any>;
  const taskId = String(task.task_id);
  const base = `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/assessment`;
  const detectedResponse = await request.post(`${base}/detect`, { headers: auth(token) });
  expect(detectedResponse.ok()).toBeTruthy();
  const draft = await detectedResponse.json() as Record<string, any>;
  const itemId = `asi-code-${taskId}`;
  const updateResponse = await request.put(`${base}/draft`, {
    headers: auth(token),
    data: {
      expected_revision: draft.draft_revision,
      pass_threshold: 60,
      mastery_threshold: 80,
      max_attempts: 3,
      assessment_mode: "open_book",
      answer_reveal_policy: "after_finish_or_exhausted",
      shuffle_questions: false,
      shuffle_options: false,
      items: [{
        assessment_item_id: itemId,
        assessment_version_id: draft.assessment_version_id,
        position: 1,
        item_type: "code_implementation",
        prompt: { stem: "使用 Python 实现 sum_even(values)，返回所有偶数之和。", language: "python" },
        scoring_key: {},
        rubric: { criteria: ["结果正确", "能处理空列表", "代码清晰"] },
        max_score: 100,
        grading_provider: "rubric_ai_teacher",
        knowledge_point_ids: ["loops-code"],
        source_refs: [{ material_type: "learning_task", material_id: taskId }],
        source_exposure_state: "private",
        created_origin: "manual",
      }],
    },
  });
  expect(updateResponse.ok()).toBeTruthy();
  const updated = await updateResponse.json() as Record<string, any>;
  expect(updated.quality.publishable).toBe(true);
  const publishResponse = await request.post(
    `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/publish`,
    { headers: auth(token), data: { expected_revision: updated.draft_revision } },
  );
  expect(publishResponse.ok()).toBeTruthy();
  return { taskId, itemId };
}

async function completeAttempt(
  page: Page,
  taskId: string,
  startLabel: "开始测评" | "再次测评" | "继续挑战",
  correctQuestionIndexes: number[],
) {
  const runner = page.getByRole("region", { name: "正式测评" });
  await runner.getByRole("button", { name: startLabel, exact: true }).click();
  const questions = runner.locator(".assessment-runner__question");
  await expect(questions).toHaveCount(4);
  for (const index of correctQuestionIndexes) {
    await questions.nth(index).getByLabel("正确答案", { exact: true }).check();
  }
  const submitted = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && response.url().includes(`/assessment/attempts/`)
    && response.url().endsWith("/submit"),
  );
  await runner.getByRole("button", { name: "提交测评", exact: true }).click();
  const response = await submitted;
  expect(response.status()).toBe(200);
  const body = await response.json() as Record<string, any>;
  expect(body.task_id).toBe(taskId);
  return body;
}

test("teacher and student finish the mandatory assessment loop end to end", async ({
  browser,
  request,
  learningBackend,
}, testInfo) => {
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
  const title = `E2E-ASSESSMENT-${Date.now()}`;

  try {
    await loginAs(teacherPage, teacherCredentials.username, teacherCredentials.password);
    await teacherPage.goto(`/#learning?course_id=${learningCourseId}`, { waitUntil: "domcontentloaded" });
    await teacherPage.getByRole("button", { name: /新建学习任务/ }).click();
    const createPanel = teacherPage.getByRole("region", { name: "新建学习任务" });
    await createPanel.getByLabel("任务标题").fill(title);
    await createPanel.getByLabel("学习说明").fill("阅读材料后完成正式循环测评。");
    await createPanel.getByLabel("知识点 ID").fill("loops");
    const createdResponse = teacherPage.waitForResponse((response) =>
      response.request().method() === "POST"
      && response.url().endsWith(`/api/courses/${learningCourseId}/learning/tasks`),
    );
    await createPanel.getByRole("button", { name: "保存草稿" }).click();
    const created = await (await createdResponse).json() as Record<string, any>;
    const taskId = String(created.task_id);
    const publishButton = teacherPage.getByRole("button", { name: "发布给学生", exact: true });
    await expect(publishButton).toBeDisabled();

    const teacherToken = await loginToken(request, teacherCredentials.username, teacherCredentials.password);
    const draft = await installDeterministicAssessment(request, teacherToken, taskId);
    expect(draft.quality.publishable).toBe(true);
    await teacherPage.reload({ waitUntil: "domcontentloaded" });
    await expect(teacherPage.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await expect(teacherPage.getByText("可发布", { exact: true })).toBeVisible();
    await expect(publishButton).toBeEnabled();
    const publishedResponse = teacherPage.waitForResponse((response) =>
      response.request().method() === "POST" && response.url().endsWith(`/learning/tasks/${taskId}/publish`),
    );
    await publishButton.click();
    expect((await publishedResponse).status()).toBe(200);

    await loginAs(studentPage, studentCredentials.username, studentCredentials.password);
    const studentTasksResponse = studentPage.waitForResponse((response) =>
      response.request().method() === "GET"
      && response.url().endsWith(`/api/courses/${learningCourseId}/learning/tasks`),
    );
    await studentPage.goto(`/#student-learning?course_id=${learningCourseId}`, { waitUntil: "domcontentloaded" });
    expect((await studentTasksResponse).status()).toBe(200);
    const taskCard = studentPage.getByRole("article").filter({ hasText: title });
    await expect(taskCard).toBeVisible({ timeout: 30_000 });
    await expect(taskCard.getByRole("button", { name: "我已完成" })).toHaveCount(0);
    const projectionResponse = await request.get(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/assessment`,
      { headers: auth(await loginToken(request, studentCredentials.username, studentCredentials.password)) },
    );
    const projectionText = JSON.stringify(await projectionResponse.json());
    expect(projectionText).not.toContain("scoring_key");
    expect(projectionText).not.toContain("correct_option_id");

    const first = await completeAttempt(studentPage, taskId, "开始测评", [3]);
    expect(first.final_score).toBe(50);
    expect(first.result).toBe("needs_retry");
    await expect(taskCard.getByText(/最佳成绩 50 分/)).toBeVisible();

    const second = await completeAttempt(studentPage, taskId, "再次测评", [2, 3]);
    expect(second.final_score).toBe(75);
    expect(second.result).toBe("passed");
    await expect(taskCard.getByRole("button", { name: "继续挑战", exact: true })).toBeVisible();
    await expect(taskCard.getByRole("button", { name: "查看答案与解析", exact: true })).toBeVisible();

    const third = await completeAttempt(studentPage, taskId, "继续挑战", [1, 3]);
    expect(third.final_score).toBe(65);
    expect(third.result).toBe("passed");
    await expect(taskCard.getByText(/最佳成绩 75 分/)).toBeVisible();
    const studentToken = await loginToken(request, studentCredentials.username, studentCredentials.password);
    const hiddenFeedback = await request.get(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/assessment/feedback`,
      { headers: auth(studentToken) },
    );
    const hiddenText = JSON.stringify(await hiddenFeedback.json());
    expect(hiddenText).not.toContain("solution");
    expect(hiddenText).not.toContain("scoring_key");

    const revealResponse = studentPage.waitForResponse((response) =>
      response.request().method() === "POST" && response.url().endsWith(`/assessment/reveal`),
    );
    await taskCard.getByRole("button", { name: "查看答案与解析", exact: true }).click();
    const revealed = await (await revealResponse).json() as Record<string, any>;
    expect(revealed.answers_revealed_at).toBeTruthy();
    expect(revealed.items[0].solution.correct_option_id).toBe("correct");
    expect(JSON.stringify(revealed)).not.toContain("scoring_key");
    await expect(taskCard.getByRole("button", { name: /再次测评|继续挑战|开始测评/ })).toHaveCount(0);

    const forbiddenAnalytics = await request.get(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/assessment/analytics`,
      { headers: auth(studentToken) },
    );
    expect(forbiddenAnalytics.status()).toBe(403);
    await teacherPage.reload({ waitUntil: "domcontentloaded" });
    await expect(teacherPage.getByRole("heading", { name: title, exact: true })).toBeVisible();
    await expect(teacherPage.getByText("75", { exact: true }).first()).toBeVisible();
    const analytics = await request.get(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${taskId}/assessment/analytics`,
      { headers: auth(teacherToken) },
    );
    const analyticsBody = await analytics.json() as Record<string, any>;
    expect(analyticsBody.submission).toEqual({ numerator: 1, denominator: 1, rate: 1 });
    expect(analyticsBody.pass).toEqual({ numerator: 1, denominator: 1, rate: 1 });
    expect(analyticsBody.students[0].best_final_score).toBe(75);

    const codeTitle = `E2E-CODE-REVIEW-${Date.now()}`;
    const codeTask = await createCodeReviewTask(request, teacherToken, codeTitle);
    await studentPage.reload({ waitUntil: "domcontentloaded" });
    const codeStudentCard = studentPage.getByRole("article").filter({ hasText: codeTitle });
    await expect(codeStudentCard).toBeVisible();
    const codeRunner = codeStudentCard.getByRole("region", { name: "正式测评" });
    await codeRunner.getByRole("button", { name: "开始测评", exact: true }).click();
    await codeRunner.locator("textarea.is-code").fill(
      "def sum_even(values):\n    return sum(value for value in values if value % 2 == 0)",
    );
    const codeSubmitResponse = studentPage.waitForResponse((response) =>
      response.request().method() === "POST"
      && response.url().includes(`/assessment/attempts/`)
      && response.url().endsWith("/submit"),
    );
    await codeRunner.getByRole("button", { name: "提交测评", exact: true }).click();
    const pendingCodeAttempt = await (await codeSubmitResponse).json() as Record<string, any>;
    expect(pendingCodeAttempt.status).toBe("pending_review");
    expect(pendingCodeAttempt.final_score).toBeNull();
    await expect(codeStudentCard.getByText(/正在等待教师复核/)).toBeVisible();

    await teacherPage.reload({ waitUntil: "domcontentloaded" });
    await expect(teacherPage.getByRole("heading", { name: codeTitle, exact: true })).toBeVisible();
    const codeAnalytics = teacherPage.getByRole("region", { name: "正式测评分析" });
    await codeAnalytics.getByRole("button", { name: "复核", exact: true }).click();
    await codeAnalytics.getByLabel(/最终得分/).fill("88");
    await codeAnalytics.getByLabel("学生可见评语").fill("实现正确，空列表也能返回 0。可继续补充类型标注。");
    await codeAnalytics.getByLabel("教师私有备注").fill("E2E private rubric note");
    const reviewResponse = teacherPage.waitForResponse((response) =>
      response.request().method() === "POST"
      && response.url().endsWith(`/assessment/attempts/${pendingCodeAttempt.attempt_id}/review`),
    );
    await codeAnalytics.getByRole("button", { name: "提交复核", exact: true }).click();
    const reviewedCodeAttempt = await (await reviewResponse).json() as Record<string, any>;
    expect(reviewedCodeAttempt.final_score).toBe(88);
    expect(reviewedCodeAttempt.result).toBe("mastered");

    const reviewAuditResponse = await request.get(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${codeTask.taskId}/assessment/attempts/${pendingCodeAttempt.attempt_id}/reviews`,
      { headers: auth(teacherToken) },
    );
    expect(reviewAuditResponse.ok()).toBeTruthy();
    const reviewAudits = await reviewAuditResponse.json() as Array<Record<string, any>>;
    expect(reviewAudits[0].comment_private).toBe("E2E private rubric note");

    await studentPage.reload({ waitUntil: "domcontentloaded" });
    const reviewedStudentCard = studentPage.getByRole("article").filter({ hasText: codeTitle });
    await expect(reviewedStudentCard.getByText(/最佳成绩 88 分/)).toBeVisible();
    await expect(reviewedStudentCard.getByText(/实现正确，空列表也能返回 0/)).toBeVisible();
    const codeFeedbackResponse = await request.get(
      `${learningApiBaseUrl}/api/courses/${learningCourseId}/learning/tasks/${codeTask.taskId}/assessment/feedback`,
      { headers: auth(studentToken) },
    );
    const codeFeedbackText = JSON.stringify(await codeFeedbackResponse.json());
    expect(codeFeedbackText).toContain("实现正确，空列表也能返回 0");
    expect(codeFeedbackText).not.toContain("E2E private rubric note");

    await teacherPage.screenshot({ path: `${learningBackend.artifactDir}/teacher-assessment-analytics.png`, fullPage: true });
    await studentPage.screenshot({ path: `${learningBackend.artifactDir}/student-assessment-revealed.png`, fullPage: true });
  } finally {
    await Promise.allSettled([teacherContext.close(), studentContext.close()]);
  }
});
