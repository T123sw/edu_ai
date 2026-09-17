import { expect, test, type Page } from "playwright/test";

async function agentPanel(page: Page) {
  await expect(page.locator(".sl-classroom")).toBeVisible();
  const tab = page.getByRole("navigation", { name: "课堂面板" }).getByRole("button", { name: "Agent", exact: true });
  if (await tab.isVisible()) await tab.click();
}

test("recent learning contains created and joined classrooms with origin filters", async ({ page }) => {
  await page.goto("/?review=1");
  await expect(page.getByRole("heading", { name: "我的课堂", exact: true })).toHaveCount(0);
  await page.locator(".sl-class-card").filter({ hasText: "Agent 入门：从原理到实践" }).click();
  await page.getByRole("link", { name: "返回首页", exact: true }).click();
  const recent = page.getByRole("region", { name: "最近学习" });
  await recent.locator(".sl-recent-filters").getByRole("button", { name: /共享课堂/ }).click();
  await expect(recent.locator(".sl-class-card")).toHaveCount(1);
  await expect(recent.locator(".sl-class-card")).toContainText("Agent 入门：从原理到实践");
  await recent.locator(".sl-recent-filters").getByRole("button", { name: /自己生成/ }).click();
  await expect(recent.locator(".sl-class-card").filter({ hasText: "从零开始，理解 Agent" })).toBeVisible();
  await expect(recent.locator(".sl-room-origin.shared")).toHaveCount(0);
  await page.reload();
  await expect(recent.locator(".sl-class-card").filter({ hasText: "Agent 入门：从原理到实践" })).toBeVisible();
});

test("persistent Agent keeps separate knowledge point histories, drafts and shared learning memory", async ({ page }, info) => {
  const requests: string[] = [];
  page.on("request", r => { if (/^\/(backend\/)?api\//.test(new URL(r.url()).pathname)) requests.push(r.url()); });
  await page.goto("/?review=1#/classroom/sample-agent");
  await agentPanel(page);
  const agent = page.getByRole("complementary", { name: "知识点对话" });
  await expect(agent).toBeVisible();
  await expect(agent.getByRole("textbox", { name: "向学习 Agent 提问" })).toBeVisible();
  const chapter = page.getByRole("combobox", { name: "对话知识点" });
  const ids = await chapter.locator("option").evaluateAll(options => options.map(o => (o as HTMLOptionElement).value));
  const input = page.getByRole("textbox", { name: "向学习 Agent 提问" });
  await input.fill("只属于第一个知识点的问题");
  await page.getByRole("button", { name: "发送问题" }).click();
  await chapter.selectOption(ids[1]);
  await expect(page.locator(".sl-chat-bubble.user")).toHaveCount(0);
  await page.getByRole("button", { name: /全局学习记忆/ }).click();
  await page.getByRole("combobox", { name: "当前知识点的理解程度" }).selectOption("review");
  await input.fill("第二个知识点的草稿");
  await chapter.selectOption(ids[0]);
  await expect(input).toHaveValue("");
  await expect(page.locator(".sl-chat-bubble.user")).toContainText("只属于第一个知识点的问题");
  await expect(page.locator(".sl-chat-bubble.assistant").last()).toContainText("我记下了你的问题");
  await page.getByRole("button", { name: /全局学习记忆/ }).click();
  await input.fill("查看我的学习记忆");
  await page.getByRole("button", { name: "发送问题" }).click();
  await expect(page.locator(".sl-chat-bubble.assistant").last()).toContainText("待巩固");
  await chapter.selectOption(ids[1]);
  await expect(input).toHaveValue("第二个知识点的草稿");
  await expect(page.locator(".sl-chat-bubble.user")).toHaveCount(0);
  await page.reload();
  await agentPanel(page);
  await expect(page.locator(".sl-chat-bubble.user")).toHaveCount(0);
  await page.getByRole("button", { name: /全局学习记忆/ }).click();
  await expect(page.getByRole("combobox", { name: "当前知识点的理解程度" })).toHaveValue("review");
  await chapter.selectOption(ids[0]);
  await expect(page.locator(".sl-chat-bubble.user")).toHaveCount(2);
  const panels = page.getByRole("navigation", { name: "课堂面板" });
  if (await panels.isVisible()) await panels.getByRole("button", { name: "目录", exact: true }).click();
  await page.locator(".sl-directory-scroll > section").first().locator(".sl-resource-row").nth(1).click();
  await agentPanel(page);
  await expect(page.locator(".sl-chat-bubble.user")).toHaveCount(2);
  await page.screenshot({ path: info.outputPath("persistent-agent.png") });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(requests).toEqual([]);
});
