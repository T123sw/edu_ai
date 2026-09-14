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

async function fulfillAgentStream(route: Route) {
  const payload = {
    message: { role: "assistant", content: "已收到生成要求。" },
    conversation: { conversation_id: "practice-agent-conversation" },
    action: { name: "generate.resource" }, artifacts: [], sources: [], trace: { path: "deepseek-harness" },
  };
  await route.fulfill({
    contentType: "text/event-stream; charset=utf-8",
    body: `data: ${JSON.stringify({ type: "result", payload })}\n\ndata: ${JSON.stringify({ type: "done", payload: {} })}\n\n`,
  });
}

test("practice resources preserve detailed natural-language briefs and canonical Agent hints", async ({ teacherPage: page }) => {
  const requests: Array<Record<string, unknown>> = [];
  let directRequests = 0;
  await page.route("**/api/chat/v2/*/direct", async (route) => {
    directRequests += 1;
    await route.fulfill({ status: 500, json: { detail: "direct route must not be used" } });
  });
  await page.route("**/api/chat/v2/stream", async (route) => {
    requests.push(route.request().postDataJSON());
    await fulfillAgentStream(route);
  });
  await page.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });

  const resources = [
    ["习题", "请生成 14 道力学综合练习，包含选择题和简答题，附答案但不附解析。", "generate.quiz"],
    ["闪卡", "请生成 18 张核心概念闪卡，卡片中不显示资料来源。", "generate.flashcard"],
    ["课堂小游戏", "请生成概念配对记忆翻牌游戏，包含 12 张卡片，课堂用时 8 分钟。", "generate.game"],
  ] as const;

  for (const [index, [label, brief, hint]] of resources.entries()) {
    await openFactory(page);
    const opener = page.getByRole("button", { name: label, exact: true });
    await opener.focus();
    await opener.press("Enter");
    const dialog = page.getByRole("dialog", { name: `创建${label}` });
    const textbox = dialog.getByRole("textbox", { name: "描述你想生成的内容" });
    await expect(textbox).toBeFocused();
    await textbox.fill(brief);
    await dialog.getByRole("button", { name: "交给 AI" }).click();
    await expect.poll(() => requests.length).toBe(index + 1);
    expect(requests[index].question).toBe(brief);
    expect(requests[index].action_hint).toBe(hint);
  }

  expect(directRequests).toBe(0);
});
