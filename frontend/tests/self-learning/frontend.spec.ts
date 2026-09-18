import { test, expect, type Page } from "playwright/test";

test("playback advances during generation and pauses for Agent; progress resumes", async ({
  page,
}) => {
  await page.goto("/?preview=student");
  await page
    .getByRole("textbox", { name: "学习知识点与目标" })
    .fill("学习 Agent");
  await page.getByRole("button", { name: "开始学习", exact: true }).click();
  await page
    .getByRole("button", { name: "播放讲解" })
    .click({ timeout: 10000 });
  // The mobile reader remains mounted but hidden while the Agent panel is active.
  const slider = page.getByRole("slider", {
    name: "讲解播放位置",
    includeHidden: true,
  });
  await expect
    .poll(async () => Number(await slider.inputValue()))
    .toBeGreaterThanOrEqual(2);
  await panel(page, "Agent");
  await page.getByRole("textbox", { name: "向学习 Agent 提问" }).focus();
  const stopped = await slider.inputValue();
  await page.waitForTimeout(1300);
  expect(await slider.inputValue()).toBe(stopped);
  await page.reload();
  await expect(page.getByRole("slider", { name: "讲解播放位置" })).toHaveValue(
    stopped,
  );
});

test("report scroll and quiz evidence restore without claiming mastery", async ({
  page,
}) => {
  await page.goto("/?preview=student#/classroom/sample-agent");
  await expect(
    page.getByRole("heading", { name: "Agent 基础概念", exact: true }),
  ).toBeVisible();
  await page.locator(".sl-reader-scroll").evaluate((el) => {
    el.scrollTop = 180;
  });
  await expect
    .poll(async () =>
      page.locator(".sl-reader-scroll").evaluate((el) => el.scrollTop),
    )
    .toBeGreaterThan(0);
  // Give React's persistence effect a chance to flush, then check a full reload.
  await expect
    .poll(async () =>
      page.evaluate(() => {
        const key = Object.keys(localStorage).find((k) =>
          k.includes("preview%3A"),
        );
        const state = JSON.parse(localStorage.getItem(key!)!);
        return state.rooms[0].progress["sample-agent-0-report"]?.position;
      }),
    )
    .toBeGreaterThan(0);
  await page.reload();
  await expect
    .poll(async () =>
      page.locator(".sl-reader-scroll").evaluate((el) => el.scrollTop),
    )
    .toBeGreaterThan(0);
  await panel(page, "目录");
  await page.getByRole("button", { name: "学习检查", exact: true }).click();
  await page
    .getByRole("radio", { name: "用自己的话解释，并尝试解决一个新例子" })
    .check();
  await page.getByRole("button", { name: "检查答案" }).click();
  await expect(page.getByRole("status")).toContainText("这道题回答正确");
  await expect(page.getByRole("button", { name: "标记学完" })).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("radio", { name: "用自己的话解释，并尝试解决一个新例子" }),
  ).toBeChecked();
  await panel(page, "Agent");
  await expect(page.locator(".sl-context")).toContainText("检查正确");
});

async function panel(page: Page, label: string) {
  const nav = page.getByRole("navigation", { name: "课堂面板" });
  if (await nav.isVisible())
    await nav.getByRole("button", { name: label, exact: true }).click();
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
}

test("minimal homepage, student permissions and direct classroom generation", async ({
  page,
}, info) => {
  // Exercise ID generation for LAN HTTP previews without secure-context randomUUID.
  await page.addInitScript(() =>
    Object.defineProperty(crypto, "randomUUID", { value: undefined }),
  );
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/?preview=student");
  await expect(
    page.getByRole("heading", { name: "让好奇，成为你的下一堂课。" }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "主导航" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "上传课堂" })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "开始学习", exact: true }),
  ).toBeDisabled();
  await noOverflow(page);
  await page.screenshot({ path: info.outputPath("home.png"), fullPage: true });
  await page
    .getByRole("textbox", { name: "学习知识点与目标" })
    .fill("系统学习 Agent，希望开发一个应用");
  await page.getByRole("button", { name: "开始学习", exact: true }).click();
  await expect(page).toHaveURL(/#\/classroom\//);
  await expect(
    page.getByRole("heading", { name: "正在为你准备这一节" }),
  ).toBeVisible();
  await expect(page.getByText("后台任务", { exact: true })).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Agent 基础概念", exact: true }),
  ).toBeVisible({ timeout: 10000 });
  await page.screenshot({ path: info.outputPath("classroom.png") });
  await noOverflow(page);
  await page.getByRole("link", { name: "返回首页" }).click();
  await expect(
    page.locator(".sl-class-card").filter({ hasText: "从零开始，理解 Agent" }),
  ).toHaveCount(2);
  expect(errors).toEqual([]);
});

test("learning position, notes, completion, context chat and back navigation persist", async ({
  page,
}, info) => {
  await page.goto("/?preview=student#/classroom/sample-agent");
  await expect(
    page.getByRole("heading", { name: "Agent 基础概念", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "我的笔记" }).click();
  await page
    .getByRole("textbox", { name: "记录你的理解" })
    .fill("模型理解目标，工具执行行动。");
  await page.getByRole("button", { name: "标记学完" }).click();
  await panel(page, "目录");
  await page
    .getByRole("button", { name: "ReAct：推理与行动 · 讲解", exact: true })
    .click();
  await page.getByRole("slider", { name: "讲解播放位置" }).fill("19");
  await page.reload();
  await expect(page.getByRole("slider", { name: "讲解播放位置" })).toHaveValue(
    "19",
  );
  await panel(page, "Agent");
  await expect(page.locator(".sl-context")).toContainText("ReAct：推理与行动");
  await expect(page.locator(".sl-context")).toContainText("00:19");
  await page
    .getByRole("textbox", { name: "向学习 Agent 提问" })
    .fill("接下来学什么？");
  await page.getByRole("button", { name: "发送问题" }).click();
  await expect(page.locator(".sl-chat-bubble.assistant").last()).toContainText(
    "2 / 9",
  );
  await page.screenshot({ path: info.outputPath("learning-agent.png") });
  await panel(page, "目录");
  await page
    .getByRole("button", { name: "Agent 基础概念 · 学习笔记", exact: true })
    .click();
  await page.getByRole("button", { name: "我的笔记" }).click();
  await expect(page.getByRole("textbox", { name: "记录你的理解" })).toHaveValue(
    "模型理解目标，工具执行行动。",
  );
  await expect(page.getByRole("button", { name: "标记学完" })).toHaveCount(0);
  await page.reload();
  await panel(page, "Agent");
  await expect(page.locator(".sl-chat-bubble.user")).toHaveCount(0);
  await page.goBack();
  await panel(page, "Agent");
  await expect(page.locator(".sl-chat-bubble.user")).toContainText("接下来学什么？");
  await panel(page, "学习");
  await expect(page.getByRole("slider", { name: "讲解播放位置" })).toHaveValue(
    "19",
  );
  await page.goForward();
  await expect(
    page.getByRole("heading", { name: "Agent 基础概念", exact: true }),
  ).toBeVisible();
  await noOverflow(page);
});

test("teacher-only publish, shared catalog and personal progress isolation", async ({
  page,
}, info) => {
  await page.goto("/?preview=teacher");
  await page.getByRole("button", { name: "上传课堂" }).click();
  await page.getByRole("textbox", { name: "课堂名称" }).fill("我的共享课程");
  await page
    .getByRole("textbox", { name: "学习目标", exact: true })
    .fill("学习 MCP 工具连接");
  await page.getByLabel("课堂学习文件").setInputFiles({
    name: "invalid.exe",
    mimeType: "application/octet-stream",
    buffer: Buffer.from("invalid"),
  });
  await expect(page.getByRole("alert")).toContainText("请选择支持的文件类型");
  await expect(
    page.getByRole("button", { name: "发布本地演示" }),
  ).toBeDisabled();
  await page.getByLabel("课堂学习文件").setInputFiles({
    name: "入门.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# MCP 入门"),
  });
  await page.screenshot({ path: info.outputPath("teacher-publish.png") });
  await page.getByRole("button", { name: "发布本地演示" }).click();
  await expect(page.locator(".sl-toast")).toContainText("尚未上传服务器");
  await page.goto("/?preview=student");
  await expect(page.getByRole("button", { name: "上传课堂" })).toHaveCount(0);
  await page
    .locator(".sl-class-card")
    .filter({ hasText: "我的共享课程" })
    .click();
  await page.getByRole("button", { name: "标记学完" }).click();
  await page.goto("/?preview=teacher");
  await page
    .locator(".sl-class-card")
    .filter({ hasText: "我的共享课程" })
    .click();
  await expect(page.getByRole("button", { name: "标记学完" })).toBeVisible();
  await noOverflow(page);
});

test("normal entry does not bypass authentication and invalid routes recover", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "登录 Edu AI" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => localStorage.getItem("edu-ai-auth")),
  ).toBeNull();
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "用户名或密码错误" }),
    }),
  );
  await page
    .getByRole("textbox", { name: "账号", exact: true })
    .fill("invalid");
  await page.getByLabel("密码", { exact: true }).fill("invalid");
  await page.getByRole("button", { name: /^登\s*录$/ }).click();
  await expect(page.getByRole("alert")).toContainText("用户名或密码错误");
  await page.goto("/?preview=student#/classroom/missing");
  await expect(
    page.getByRole("heading", { name: "这段学习旅程还未找到" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "返回首页" }).click();
  await expect(
    page.getByRole("textbox", { name: "学习知识点与目标" }),
  ).toBeVisible();
});
