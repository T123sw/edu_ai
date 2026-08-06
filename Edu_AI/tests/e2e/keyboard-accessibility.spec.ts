import { expect, test } from "./fixtures/teacherApp";
import type { Locator, Page, Route } from "playwright/test";

function job(status: "running" | "canceled") {
  return {
    schema_version: 1,
    version: status === "running" ? 1 : 2,
    edu_job_id: "job-generated-fixture",
    kind: "report",
    status,
    step: status === "running" ? "generating" : "canceled",
    progress: status === "running" ? 35 : 35,
    message: status === "running" ? "正在生成报告" : "任务已取消",
    owner_user_id: "teacher-a",
    course_id: "course-physics",
    scope_type: "course",
    input_summary: { title: "键盘验收报告" },
    retryable: status === "canceled",
    cancelable: status === "running",
    created_at: "2026-08-07T01:00:00+08:00",
    updated_at: "2026-08-07T01:01:00+08:00",
  };
}

async function keyboardActivate(locator: Locator, page: Page, key = "Enter") {
  await locator.focus();
  await expect(locator).toBeFocused();
  await page.keyboard.press(key);
}

test("teacher completes the core workflow with the keyboard only", async ({ teacherPage }, testInfo) => {
  let currentJobStatus: "running" | "canceled" = "running";
  await teacherPage.route("http://localhost:8001/api/jobs/job-generated-fixture", (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(job(currentJobStatus)),
  }));
  await teacherPage.route("http://localhost:8001/api/chat/v2/report/direct", (route) => route.fulfill({
    status: 202,
    contentType: "application/json",
    body: JSON.stringify(job("running")),
  }));
  await teacherPage.route("http://localhost:8001/api/jobs/job-generated-fixture/cancel", (route: Route) => {
    currentJobStatus = "canceled";
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(job("canceled")) });
  });

  await teacherPage.goto("/#home", { waitUntil: "domcontentloaded" });
  const rejectVerify = (route: Route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ valid: false, user: null }),
  });
  await teacherPage.route("http://localhost:8001/api/auth/verify", rejectVerify);
  await teacherPage.reload({ waitUntil: "domcontentloaded" });
  await teacherPage.getByRole("textbox", { name: "账号", exact: true }).focus();
  await teacherPage.keyboard.type("teacher-a");
  await teacherPage.getByLabel("密码").focus();
  await teacherPage.keyboard.type("fixture-password");
  await keyboardActivate(teacherPage.getByRole("button", { name: /登\s*录/u }), teacherPage);
  await teacherPage.unroute("http://localhost:8001/api/auth/verify", rejectVerify);
  await expect(teacherPage.getByRole("link", { name: "大学物理" })).toBeVisible();

  await keyboardActivate(teacherPage.getByRole("link", { name: "大学物理" }), teacherPage);
  await expect(teacherPage).toHaveURL(/course_id=course-physics/u);

  if (testInfo.project.name === "compact1024") {
    await keyboardActivate(teacherPage.getByRole("button", { name: "打开课程导航" }), teacherPage);
    await keyboardActivate(teacherPage.getByTestId("course-navigation-drawer").getByRole("link", { name: "课程知识" }), teacherPage);
  } else {
    await keyboardActivate(
      teacherPage.getByRole("navigation", { name: "课程工作区" }).getByRole("link", { name: "课程知识", exact: false }),
      teacherPage,
    );
  }
  await keyboardActivate(teacherPage.getByRole("link", { name: "知识结构", exact: true }), teacherPage);
  await expect(teacherPage).toHaveURL(/view=structure/u);
  await keyboardActivate(teacherPage.getByRole("link", { name: "课程资料", exact: true }), teacherPage);
  await expect(teacherPage).toHaveURL(/view=documents/u);

  await teacherPage.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await teacherPage.evaluate(() => window.localStorage.removeItem("edu-ai:generation-draft:course-physics"));
  await teacherPage.reload({ waitUntil: "domcontentloaded" });
  await keyboardActivate(teacherPage.getByRole("button", { name: "打开生成工厂面板" }), teacherPage);
  await keyboardActivate(teacherPage.locator(".generation-factory__registry").getByRole("button", { name: "报告", exact: false }), teacherPage);
  await keyboardActivate(teacherPage.getByRole("button", { name: "下一步" }), teacherPage);
  await keyboardActivate(teacherPage.getByRole("radio", { name: "仅使用选中文档", exact: false }), teacherPage, "Space");
  await keyboardActivate(teacherPage.getByRole("checkbox", { name: /大学物理·力学/u }), teacherPage, "Space");
  await keyboardActivate(teacherPage.getByRole("button", { name: "下一步" }), teacherPage);
  await teacherPage.getByLabel("报告主题 *").focus();
  await teacherPage.keyboard.press("Control+A");
  await teacherPage.keyboard.type("键盘验收报告");
  await keyboardActivate(teacherPage.getByRole("button", { name: "下一步" }), teacherPage);
  await keyboardActivate(teacherPage.getByRole("button", { name: "开始后台生成" }), teacherPage);
  const cancel = teacherPage.getByRole("button", { name: "取消任务" });
  await expect(cancel).toBeVisible();
  await keyboardActivate(cancel, teacherPage);
  await expect.poll(() => currentJobStatus).toBe("canceled");

  await teacherPage.evaluate(() => window.localStorage.removeItem("edu-ai:generation-draft:course-physics"));
  await teacherPage.reload({ waitUntil: "domcontentloaded" });
  if (!(await teacherPage.getByTestId("generation-factory").isVisible())) {
    await keyboardActivate(teacherPage.getByRole("button", { name: "打开生成工厂面板" }), teacherPage);
  }
  await keyboardActivate(teacherPage.locator(".generation-factory__registry").getByRole("button", { name: "小游戏", exact: false }), teacherPage);
  await keyboardActivate(teacherPage.getByRole("button", { name: "下一步" }), teacherPage);
  await keyboardActivate(teacherPage.getByRole("radio", { name: "不使用资料", exact: false }), teacherPage, "Space");
  await keyboardActivate(teacherPage.getByRole("button", { name: "下一步" }), teacherPage);
  const memoryGame = teacherPage.getByRole("button", { name: "记忆翻牌", exact: false });
  await keyboardActivate(memoryGame, teacherPage);
  await expect(memoryGame).toHaveAttribute("aria-pressed", "true");

  await teacherPage.goto("/#resources?course_id=course-physics", { waitUntil: "domcontentloaded" });
  const flashcardResource = teacherPage.getByRole("button", { name: /力学核心概念闪卡/u });
  await keyboardActivate(flashcardResource, teacherPage);
  const firstCard = teacherPage.locator(".resource-flashcard-grid button").first();
  await keyboardActivate(firstCard, teacherPage);
  await expect(firstCard).toHaveAttribute("aria-pressed", "true");

  await teacherPage.goto("/#classroom-player?course_id=course-physics&classroom_id=classroom-mechanics", { waitUntil: "domcontentloaded" });
  const play = teacherPage.getByRole("button", { name: /播放当前页/u });
  await keyboardActivate(play, teacherPage);
  await expect(teacherPage.getByRole("button", { name: /暂停/u })).toBeFocused();

  for (const iconAction of [
    teacherPage.getByRole("link", { name: "返回 AI 课堂列表" }),
    teacherPage.getByRole("button", { name: "字幕" }),
    teacherPage.getByRole("button", { name: /全屏/u }),
  ]) {
    await expect(iconAction).toHaveAccessibleName(/\S/u);
  }
});

test("critical text and primary actions meet WCAG AA contrast", async ({ teacherPage }) => {
  await teacherPage.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await teacherPage.getByRole("button", { name: "打开生成工厂面板" }).click();
  const primary = teacherPage.locator(".generation-config-shell footer .is-primary");
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
