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
    conversation: { conversation_id: "visual-agent-conversation" },
    action: { name: "generate.resource" }, artifacts: [], sources: [], trace: { path: "deepseek-harness" },
  };
  await route.fulfill({
    contentType: "text/event-stream; charset=utf-8",
    body: `data: ${JSON.stringify({ type: "result", payload })}\n\ndata: ${JSON.stringify({ type: "done", payload: {} })}\n\n`,
  });
}

test("visual resources use the shared concise Agent dialog without horizontal overflow", async ({ teacherPage: page }) => {
  const requests: Array<Record<string, unknown>> = [];
  await page.route("**/api/chat/v2/stream", async (route) => {
    requests.push(route.request().postDataJSON());
    await fulfillAgentStream(route);
  });
  await page.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });

  const resources = [
    ["思维导图", "生成四层电磁学思维导图，突出概念关系。", "generate.graph"],
    ["AI 课堂", "生成波的干涉 AI 课堂，共 8 个场景，配音使用 nova。", "generate.classroom"],
  ] as const;

  for (const [index, [label, brief, hint]] of resources.entries()) {
    await openFactory(page);
    await page.getByRole("button", { name: label, exact: true }).click();
    const dialog = page.getByRole("dialog", { name: `创建${label}` });
    await expect(dialog.getByRole("textbox")).toHaveCount(1);
    await dialog.getByRole("textbox", { name: "描述你想生成的内容" }).fill(brief);
    expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    const submit = dialog.getByRole("button", { name: "交给 AI" });
    await expect(submit).toBeInViewport();
    await submit.click();
    await expect.poll(() => requests.length).toBe(index + 1);
    expect(requests[index].question).toBe(brief);
    expect(requests[index].action_hint).toBe(hint);
  }
});
