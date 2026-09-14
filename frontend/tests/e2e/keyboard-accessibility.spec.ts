import { expect, test } from "./fixtures/teacherApp";
import type { Locator, Page, Route } from "playwright/test";

async function keyboardActivate(locator: Locator, page: Page, key = "Enter") {
  await locator.focus();
  await expect(locator).toBeFocused();
  await page.keyboard.press(key);
}

async function openFactory(factory: Locator, switcher: Locator) {
  await expect.poll(async () => {
    if (await factory.isVisible()) return true;
    if (await switcher.isVisible()) await switcher.press("Enter", { timeout: 1_000 }).catch(() => undefined);
    return factory.isVisible();
  }, { timeout: 20_000 }).toBe(true);
  await expect(factory).toBeVisible();
}

test("teacher completes the core workflow with the keyboard only", async ({ teacherPage }) => {
  let agentRequest: Record<string, unknown> | null = null;
  await teacherPage.route("**/api/chat/v2/stream", async (route) => {
    agentRequest = route.request().postDataJSON();
    const payload = {
      message: { role: "assistant", content: "已收到生成要求。" },
      conversation: { conversation_id: "keyboard-agent-conversation" },
      action: { name: "generate.report" }, artifacts: [], sources: [], trace: { path: "deepseek-harness" },
    };
    await route.fulfill({
      contentType: "text/event-stream; charset=utf-8",
      body: `data: ${JSON.stringify({ type: "result", payload })}\n\ndata: ${JSON.stringify({ type: "done", payload: {} })}\n\n`,
    });
  });

  await teacherPage.goto("/#home", { waitUntil: "domcontentloaded" });
  const rejectVerify = (route: Route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ valid: false, user: null }),
  });
  await teacherPage.route("**/api/auth/verify", rejectVerify);
  await teacherPage.reload({ waitUntil: "domcontentloaded" });
  await teacherPage.getByRole("textbox", { name: "账号", exact: true }).focus();
  await teacherPage.keyboard.type("teacher-a");
  await teacherPage.getByLabel("密码").focus();
  await teacherPage.keyboard.type("fixture-password");
  await keyboardActivate(teacherPage.getByRole("button", { name: /登\s*录/u }), teacherPage);
  await teacherPage.unroute("**/api/auth/verify", rejectVerify);
  await expect(teacherPage.getByRole("link", { name: "大学物理" })).toBeVisible();

  await keyboardActivate(teacherPage.getByRole("link", { name: "大学物理" }), teacherPage);
  await expect(teacherPage).toHaveURL(/course_id=course-physics/u);

  const courseNavigationButton = teacherPage.getByRole("button", { name: "打开课程导航" });
  if (await courseNavigationButton.isVisible()) {
    await keyboardActivate(courseNavigationButton, teacherPage);
    await keyboardActivate(teacherPage.getByTestId("course-navigation-drawer").getByRole("link", { name: "课程知识" }), teacherPage);
  } else {
    await keyboardActivate(
      teacherPage.getByRole("navigation", { name: "课程工作栏" }).getByRole("link", { name: "课程知识", exact: false }),
      teacherPage,
    );
  }
  await expect(teacherPage).toHaveURL(/#knowledge\?course_id=course-physics/u);
  await expect(teacherPage.getByRole("heading", { name: "课程知识", exact: true })).toBeVisible();

  await teacherPage.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await teacherPage.waitForTimeout(500);
  const factory = teacherPage.getByTestId("generation-factory");
  const factorySwitcher = teacherPage.getByRole("button", { name: /^(生成工厂|打开生成工厂)$/ });
  await openFactory(factory, factorySwitcher);
  await keyboardActivate(teacherPage.locator(".generation-factory__registry").getByRole("button", { name: "教学报告", exact: true }), teacherPage);
  const brief = teacherPage.getByRole("dialog", { name: "创建教学报告" }).getByRole("textbox", { name: "描述你想生成的内容" });
  await expect(brief).toBeFocused();
  await teacherPage.keyboard.type("键盘验收报告");
  await keyboardActivate(teacherPage.getByRole("dialog", { name: "创建教学报告" }).getByRole("button", { name: "交给 AI" }), teacherPage);
  await expect.poll(() => agentRequest).not.toBeNull();
  expect(agentRequest?.question).toBe("键盘验收报告");
  expect(agentRequest?.action_hint).toBe("generate.report");

  await openFactory(factory, factorySwitcher);
  await keyboardActivate(teacherPage.locator(".generation-factory__registry").getByRole("button", { name: "课堂小游戏", exact: true }), teacherPage);
  const gameDialog = teacherPage.getByRole("dialog", { name: "创建课堂小游戏" });
  await expect(gameDialog.getByRole("textbox", { name: "描述你想生成的内容" })).toBeFocused();
  await keyboardActivate(gameDialog.getByRole("button", { name: "取消" }), teacherPage);

  await teacherPage.goto("/#resources?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await keyboardActivate(teacherPage.getByRole("tree", { name: "资源目录" }).getByRole("button", { name: /未分类资源/ }), teacherPage);
  const reportResource = teacherPage.getByRole("button", { name: /牛顿运动定律教学报告/u });
  await keyboardActivate(reportResource, teacherPage);
  await expect(teacherPage.getByRole("heading", { name: "牛顿运动定律教学报告" })).toBeVisible();

  await teacherPage.goto("/#classroom-player?course_id=course-physics&classroom_id=classroom-mechanics", { waitUntil: "domcontentloaded" });
  const play = teacherPage.getByRole("button", { name: /播放当前页/u });
  await keyboardActivate(play, teacherPage);
  await expect(teacherPage.getByRole("button", { name: /暂停/u })).toBeFocused();

  for (const iconAction of [
    teacherPage.getByRole("button", { name: "导出 MP4" }),
  ]) {
    await expect(iconAction).toHaveAccessibleName(/\S/u);
  }
});

test("critical text and primary actions meet WCAG AA contrast", async ({ teacherPage }) => {
  await teacherPage.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await teacherPage.waitForTimeout(500);
  const factory = teacherPage.getByTestId("generation-factory");
  const switcher = teacherPage.getByRole("button", { name: /^(生成工厂|打开生成工厂)$/ });
  await openFactory(factory, switcher);
  await teacherPage.getByRole("button", { name: "教学报告", exact: true }).click();
  const primary = teacherPage.locator(".generation-factory__modal footer .is-primary");
  await expect(primary).toBeVisible();
  const ratio = await primary.evaluate((element) => {
    const parse = (value: string) => (value.match(/[\d.]+/gu) || []).slice(0, 3).map(Number);
    const luminance = (rgb: number[]) => {
      const values = rgb.map((value) => {
        const channel = value / 255;
        return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2];
    };
    const style = getComputedStyle(element);
    const foreground = luminance(parse(style.color));
    const background = luminance(parse(style.backgroundColor));
    return (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
  });
  expect(ratio).toBeGreaterThanOrEqual(4.5);
});
