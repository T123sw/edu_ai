import { expect, test } from "./fixtures/teacherApp";
import type { Page, Route } from "playwright/test";

async function openFactory(page: Page) {
  const factory = page.getByTestId("generation-factory");
  const switcher = page.getByRole("button", { name: /^(生成工厂|打开生成工厂)$/ });
  await expect.poll(async () => {
    if (await factory.isVisible()) return true;
    if (await switcher.isVisible()) await switcher.click({ timeout: 1_000 }).catch(() => undefined);
    return factory.isVisible();
  }, { timeout: 20_000 }).toBe(true);
  await expect(factory).toBeVisible();
}

async function openKnowledge(page: Page) {
  if ((page.viewportSize()?.width ?? 1366) <= 1024) {
    const compactSwitcher = page.getByRole("button", { name: "知识库", exact: true });
    await expect(compactSwitcher).toBeVisible();
    await compactSwitcher.click();
    return;
  }
  const expand = page.getByRole("button", { name: "展开知识库", exact: true });
  const personalTab = page.getByRole("tab", { name: /个人知识库/ });
  await expect.poll(async () => await expand.isVisible() || await personalTab.isVisible(), { timeout: 20_000 }).toBe(true);
  if (await expand.isVisible()) {
    await expand.click();
  }
  await expect(personalTab).toBeVisible();
}

async function fulfillAgentStream(route: Route) {
  const payload = {
    message: { role: "assistant", content: "已收到生成要求。" },
    conversation: { conversation_id: "factory-agent-conversation" },
    action: { name: "generate.report" },
    artifacts: [],
    sources: [],
    trace: { path: "deepseek-harness" },
  };
  await route.fulfill({
    contentType: "text/event-stream; charset=utf-8",
    body: `data: ${JSON.stringify({ type: "result", payload })}\n\ndata: ${JSON.stringify({ type: "done", payload: {} })}\n\n`,
  });
}

test("all generation buttons open the same concise Agent prompt", async ({ teacherPage: page }) => {
  await page.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await openFactory(page);

  const resources = [
    ["教学报告", "面向大一学生"],
    ["教案", "40 分钟"],
    ["教学博客", "零基础读者"],
    ["习题", "8 道中等难度"],
    ["闪卡", "12 张"],
    ["思维导图", "细胞呼吸"],
    ["课堂小游戏", "不规则动词"],
    ["AI 课堂", "牛顿第二定律"],
  ] as const;

  await expect(page.locator(".generation-factory__registry button")).toHaveCount(resources.length);
  for (const [label, example] of resources) {
    const opener = page.getByRole("button", { name: label, exact: true });
    await opener.click();
    const dialog = page.getByRole("dialog", { name: `创建${label}` });
    await expect(dialog).toBeVisible();
    const brief = dialog.getByRole("textbox", { name: "描述你想生成的内容" });
    await expect(brief).toHaveAttribute("placeholder", new RegExp(example));
    await expect(brief).toBeFocused();
    await expect(dialog.getByRole("textbox")).toHaveCount(1);
    await expect(dialog.getByRole("button", { name: /下一步|上一步|开始后台生成/ })).toHaveCount(0);
    await expect(dialog.getByRole("button", { name: "交给 AI" })).toBeDisabled();
    if (label === "教学报告") {
      const close = dialog.getByRole("button", { name: "关闭" });
      await close.focus();
      await page.keyboard.press("Shift+Tab");
      await expect(dialog.getByRole("button", { name: "取消" })).toBeFocused();
      await page.keyboard.press("Tab");
      await expect(close).toBeFocused();
      await brief.focus();
      await page.keyboard.press("Escape");
      await expect(opener).toBeFocused();
    } else {
      await dialog.getByRole("button", { name: "关闭" }).click();
    }
  }
});

test("all factory buttons submit their canonical hint through the Agent stream", async ({ teacherPage: page }) => {
  const requests: Array<Record<string, unknown>> = [];
  let directRequests = 0;
  const rejectDirect = async (route: Route) => {
    directRequests += 1;
    await route.fulfill({ status: 500, json: { detail: "direct route must not be used" } });
  };
  await page.route("**/api/chat/v2/*/direct", rejectDirect);
  await page.route("**/api/courses/*/classrooms/generate", rejectDirect);
  await page.route("**/api/chat/v2/stream", async (route) => {
    requests.push(route.request().postDataJSON());
    await fulfillAgentStream(route);
  });
  await page.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });

  const resources = [
    ["教学报告", "generate.report"],
    ["教案", "generate.lesson_plan"],
    ["教学博客", "generate.blog"],
    ["习题", "generate.quiz"],
    ["闪卡", "generate.flashcard"],
    ["思维导图", "generate.graph"],
    ["课堂小游戏", "generate.game"],
    ["AI 课堂", "generate.classroom"],
  ] as const;

  for (const [index, [label, actionHint]] of resources.entries()) {
    await openFactory(page);
    await page.getByRole("button", { name: label, exact: true }).click();
    const text = `请创建${label}，保留这段原始要求。`;
    const dialog = page.getByRole("dialog", { name: `创建${label}` });
    await dialog.getByRole("textbox", { name: "描述你想生成的内容" }).fill(text);
    await dialog.getByRole("button", { name: "交给 AI" }).click();
    await expect.poll(() => requests.length).toBe(index + 1);
    const request = requests.at(-1)!;
    expect(request.question).toBe(text);
    expect(request.action_hint).toBe(actionHint);
    expect(request.entry_mode).toBe("generation_factory");
    expect(request.conversation_id).toBeUndefined();
    expect(String(request.question)).not.toContain("例如：");
  }
  expect(directRequests).toBe(0);
});

test("factory submission enters the Agent stream with the exact brief and action hint", async ({ teacherPage: page }) => {
  const streamRequests: Array<Record<string, unknown>> = [];
  let directRequests = 0;
  await page.route("**/api/chat/v2/*/direct", async (route) => {
    directRequests += 1;
    await route.fulfill({ status: 500, json: { detail: "direct route must not be used" } });
  });
  await page.route("**/api/chat/v2/stream", async (route) => {
    streamRequests.push(route.request().postDataJSON());
    await fulfillAgentStream(route);
  });

  await page.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await openFactory(page);
  await page.getByRole("button", { name: "教学报告", exact: true }).press("Enter");
  const dialog = page.getByRole("dialog", { name: "创建教学报告" });
  const brief = "生成一份面向大一学生的牛顿运动定律复习报告，语言通俗，约 1500 字。";
  await dialog.getByRole("textbox", { name: "描述你想生成的内容" }).fill(brief);
  const submit = dialog.getByRole("button", { name: "交给 AI" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  expect(await submit.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return rect.top >= 0 && rect.bottom <= window.innerHeight;
  })).toBe(true);
  await submit.click();

  await expect(dialog).toHaveCount(0);
  if ((page.viewportSize()?.width ?? 1366) <= 1024) {
    await expect(page.getByTestId("generation-factory")).toBeHidden();
    await expect(page.getByRole("textbox", { name: "开始输入问题…（Shift + Enter 换行）" })).toBeVisible();
  }
  await expect.poll(() => streamRequests.length).toBe(1);
  expect(streamRequests[0].question).toBe(brief);
  expect(streamRequests[0].action_hint).toBe("generate.report");
  expect(streamRequests[0].entry_mode).toBe("generation_factory");
  expect(streamRequests[0].conversation_id).toBeUndefined();
  expect(streamRequests[0].course_id).toBe("course-physics");
  await expect(page.getByText(brief, { exact: true })).toHaveCount(0);
  await expect(page.getByText("已收到生成要求。", { exact: true })).toHaveCount(0);
  expect(directRequests).toBe(0);
});

test("factory submission appears in the task center during Agent preparation", async ({ teacherPage: page }) => {
  let submitted = false;
  const preparingJob = {
    schema_version: 2,
    version: 2,
    edu_job_id: "job-preparing-graph",
    kind: "generate_graph",
    status: "queued",
    step: "preparing",
    progress: 0,
    message: "Agent 正在整理生成要求",
    owner_user_id: "teacher-a",
    course_id: "course-physics",
    scope_type: "course",
    scope_id: null,
    input_summary: { title: "生成一张递归思维导图", resource_type: "graph" },
    result_ref: null,
    retryable: false,
    cancelable: false,
    created_at: "2026-09-11T05:00:00Z",
    updated_at: "2026-09-11T05:00:00Z",
  };
  await page.route("**/api/jobs**", route => route.fulfill({ json: {
    items: submitted ? [preparingJob] : [],
    next_cursor: null,
    server_time: "2026-09-11T05:00:01Z",
  } }));
  await page.route("**/api/chat/v2/stream", async route => {
    submitted = true;
    await route.fulfill({
      contentType: "text/event-stream; charset=utf-8",
      body: `data: ${JSON.stringify({ type: "task_submitted", payload: {
        task_id: preparingJob.edu_job_id,
        workflow_type: "graph",
        stage: "preparing",
      } })}\n\n`,
    });
  });

  await page.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await openFactory(page);
  await page.getByRole("button", { name: "思维导图", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "创建思维导图" });
  await dialog.getByRole("textbox", { name: "描述你想生成的内容" }).fill("生成一张递归思维导图");
  await dialog.getByRole("button", { name: "交给 AI" }).click();

  const taskCenter = page.getByRole("button", { name: /任务中心|后台任务/ }).first();
  await expect(taskCenter).toHaveAccessibleName(/1 个进行中/, { timeout: 20_000 });
  await taskCenter.click();
  const drawer = page.getByRole("dialog", { name: "任务中心" });
  await expect(drawer.getByText("思维导图生成", { exact: true })).toBeVisible();
  await expect(drawer.getByText("准备中", { exact: true })).toBeVisible();
  await expect(drawer.getByText("Agent 正在整理生成要求，完成后将自动进入生成队列。", { exact: true })).toBeVisible();
  await expect(page.locator(".chat-panel").getByText("生成一张递归思维导图", { exact: true })).toHaveCount(0);
});

test("personal documents checked on the left become the optional Agent source", async ({ teacherPage: page }) => {
  await page.route("**/api/personal-knowledge/documents*", route => route.fulfill({ json: [
    { id: "personal-1", name: "教师讲义.pdf", type: "file", library_type: "personal", status: "ready", owner_user_id: "teacher-a" },
  ] }));
  await page.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await openKnowledge(page);
  await page.getByRole("tab", { name: /个人知识库/ }).click();
  const documentRow = page.locator(".source-panel__item").filter({ hasText: "教师讲义.pdf" }).first();
  await expect(documentRow).toBeVisible();
  await documentRow.locator('input[type="checkbox"]').check();

  await openFactory(page);
  await page.getByRole("button", { name: "教学报告", exact: true }).click();
  const dialog = page.getByRole("dialog", { name: "创建教学报告" });
  await expect(dialog.getByText("资料范围：已选择 1 份文档")).toBeVisible();
  await dialog.getByText("资料范围：已选择 1 份文档").click();
  await expect(dialog.getByRole("radio", { name: "仅使用选中文档", exact: false })).toBeChecked();
  await expect(dialog.getByLabel("资料范围").getByText("教师讲义.pdf", { exact: true })).toBeVisible();
});

test("generation prompt keeps an unfinished brief for the same workspace", async ({ teacherPage: page }) => {
  await page.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await openFactory(page);
  await page.getByRole("button", { name: "教学报告", exact: true }).click();
  await page.getByRole("textbox", { name: "描述你想生成的内容" }).fill("恢复主题");
  await page.getByRole("button", { name: "取消" }).click();
  await page.getByRole("button", { name: "教学报告", exact: true }).click();
  await expect(page.getByRole("textbox", { name: "描述你想生成的内容" })).toHaveValue("恢复主题");
});
