import { resolve } from "node:path";

import type { Page, TestInfo } from "playwright/test";

import {
  expect,
  learningCourseId,
  loginAs,
  test,
} from "./fixtures/learningLoop";

const teacherCredentials = { username: "teacher", password: "teacher123" };
const duplicateTitle = "汉字编码：从ASCII到UTF-8的演进";

async function screenshot(page: Page, testInfo: TestInfo, artifactDir: string, name: string) {
  const path = resolve(artifactDir, `${name}.png`);
  await page.screenshot({ path, fullPage: true });
  await testInfo.attach(name, { path, contentType: "image/png" });
}

test("teacher distinguishes duplicate resources and one overview failure stays local", async ({
  browser,
  learningBackend,
}, testInfo) => {
  const context = await browser.newContext({
    baseURL: learningBackend.frontendBaseUrl,
    viewport: testInfo.project.use.viewport,
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
    reducedMotion: "reduce",
  });
  const page = await context.newPage();

  try {
    await loginAs(page, teacherCredentials.username, teacherCredentials.password);
    await page.goto(`/#learning?course_id=${learningCourseId}`, { waitUntil: "domcontentloaded" });
    await page.getByRole("button", { name: /新建学习任务/ }).click();
    const createPanel = page.getByRole("region", { name: "新建学习任务" });
    await createPanel.getByPlaceholder("按名称、创建者或 ID 搜索").fill(duplicateTitle);
    const duplicateOptions = createPanel.locator(".learning-resource-picker > label").filter({ hasText: duplicateTitle });
    await expect(duplicateOptions.first()).toBeVisible();
    expect(await duplicateOptions.count()).toBeGreaterThanOrEqual(2);
    const optionTexts = await duplicateOptions.allTextContents();
    expect(new Set(optionTexts).size).toBe(optionTexts.length);
    await duplicateOptions.first().getByRole("checkbox").check();
    await expect(createPanel.getByText("已选 1 项")).toBeVisible();
    await createPanel.getByPlaceholder("按名称、创建者或 ID 搜索").fill("E2E-NO-MATCH-RESOURCE");
    await expect(createPanel.getByText("没有匹配的课程共享资源；已选资源保持不变。")).toBeVisible();
    await expect(createPanel.getByText("已选 1 项")).toBeVisible();
    await createPanel.getByLabel("任务标题").fill(`E2E-RESOURCE-IDENTITY-${Date.now()}`);
    const createRequest = page.waitForRequest((request) =>
      request.method() === "POST"
      && request.url().endsWith(`/api/courses/${learningCourseId}/learning/tasks`),
    );
    await createPanel.getByRole("button", { name: "保存草稿" }).click();
    const payload = (await createRequest).postDataJSON() as { resource_refs?: unknown[] };
    expect(payload.resource_refs).toHaveLength(1);
    await screenshot(page, testInfo, learningBackend.artifactDir, "10-duplicate-resource-identity");

    await page.route(
      new RegExp(`/api/courses/${learningCourseId}/learning/overview(?:\\?|$)`),
      (route) => route.fulfill({
        status: 503,
        contentType: "application/json; charset=utf-8",
        body: JSON.stringify({ detail: "isolated overview failure" }),
      }),
    );
    await page.goto("/#home", { waitUntil: "domcontentloaded" });
    const failedCourse = page.getByRole("link", { name: "计算思维" });
    await expect(failedCourse.getByText("学习任务暂不可用")).toBeVisible();
    const healthyCourse = page.locator(".teacher-course-card").filter({ hasNotText: "计算思维" }).first();
    await expect(healthyCourse).toBeVisible();
    await expect(healthyCourse.getByText("学习任务暂不可用")).toHaveCount(0);
    await screenshot(page, testInfo, learningBackend.artifactDir, "11-overview-local-degradation");
  } finally {
    await context.close();
  }
});
