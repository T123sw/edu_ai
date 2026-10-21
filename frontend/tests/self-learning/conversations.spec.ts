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

test("course Agent shares history and drafts across knowledge points", async ({ page }, info) => {
  await page.goto("/?review=1#/classroom/sample-agent");
  await agentPanel(page);
  const agent = page.getByRole("complementary", { name: "课程对话" });
  await expect(agent).toBeVisible();
  const input = page.getByRole("textbox", { name: "向学习 Agent 提问" });
  await input.fill("课程共享的第一个问题");
  await page.getByRole("button", { name: "发送问题" }).click();
  await expect(agent.locator(".sl-chat-bubble.assistant").last()).toContainText("我记下了你的问题");
  await input.fill("切换后保留的草稿");
  const panels = page.getByRole("navigation", { name: "课堂面板" });
  if (await panels.isVisible()) await panels.getByRole("button", { name: "目录", exact: true }).click();
  await page.locator(".sl-directory-scroll > section").nth(1).locator(".sl-resource-row").first().click();
  await agentPanel(page);
  await expect(input).toHaveValue("切换后保留的草稿");
  await expect(agent.getByText("课程共享的第一个问题", { exact: true })).toBeVisible();
  await page.reload();
  await agentPanel(page);
  await expect(agent.getByText("课程共享的第一个问题", { exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath("course-agent.png") });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
