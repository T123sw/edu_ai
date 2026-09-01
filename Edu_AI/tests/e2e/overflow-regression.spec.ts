import { expect, test } from "./fixtures/teacherApp";
import type { Page } from "playwright/test";

const pageMatrix = [
  ["course home", "/#home"],
  ["course overview", "/#course-detail?course_id=course-physics"],
  ["question and generation", "/#ai?course_id=course-physics"],
  ["knowledge documents", "/#knowledge?course_id=course-physics&view=documents"],
  ["knowledge structure", "/#knowledge?course_id=course-physics&view=structure"],
  ["classroom list", "/#classroom-studio?course_id=course-physics"],
  ["classroom player", "/#classroom-player?course_id=course-physics&classroom_id=classroom-mechanics"],
  ["course resources", "/#resources?course_id=course-physics"],
  ["course settings", "/#edit?course_id=course-physics"],
  ["profile", "/#profile"],
] as const;

async function expectNoPageOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => ({
    root: document.documentElement.scrollWidth <= document.documentElement.clientWidth,
    body: document.body.scrollWidth <= document.body.clientWidth,
  }))).toEqual({ root: true, body: true });
}

test("every approved page stays within the viewport without new React warnings", async ({ teacherPage }) => {
  const forbiddenWarnings: string[] = [];
  teacherPage.on("console", (message) => {
    if (message.type() === "warning" || message.type() === "error") {
      const value = message.text();
      if (/unique.*key|validateDOMNesting|uncontrolled|controlled.*input|deprecated (?:property|prop)/iu.test(value)) {
        forbiddenWarnings.push(value);
      }
    }
  });

  for (const [, url] of pageMatrix) {
    await teacherPage.goto(url, { waitUntil: "domcontentloaded" });
    await expect(teacherPage.locator("body")).toBeVisible();
    await expectNoPageOverflow(teacherPage);
  }
  expect(forbiddenWarnings).toEqual([]);
});

test("all eight generation configuration shells keep title and action reachable", async ({ teacherPage }) => {
  const resources = [
    ["教学报告", "report"],
    ["教案", "lesson_plan"],
    ["教学博客", "blog"],
    ["习题", "quiz"],
    ["闪卡", "flashcard"],
    ["思维导图", "mind_map"],
    ["课堂小游戏", "game"],
    ["AI 课堂", "classroom"],
  ] as const;

  for (const [label, type] of resources) {
    await teacherPage.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
    await teacherPage.waitForTimeout(500);
    const factory = teacherPage.getByTestId("generation-factory");
    const switcher = teacherPage.getByRole("button", { name: "生成工厂", exact: true });
    if (!(await factory.isVisible()) && await switcher.isVisible()) await switcher.click();
    await expect(factory).toBeVisible();
    await teacherPage.locator(".generation-factory__registry").getByRole("button", { name: label, exact: true }).click();

    const form = teacherPage.locator(`[data-resource-form="${type}"]`);
    const dialog = teacherPage.getByRole("dialog", { name: `配置${label}` });
    const title = dialog.getByRole("heading", { name: label, exact: true });
    const primary = dialog.getByRole("button", { name: "开始后台生成" });
    await expect(form).toBeVisible();
    await expect(title).toBeInViewport();
    await expect(primary).toBeInViewport();
    await expectNoPageOverflow(teacherPage);

    const scrollableAncestors = await primary.evaluate((element) => {
      let current: HTMLElement | null = element.parentElement;
      let count = 0;
      while (current) {
        const style = getComputedStyle(current);
        if (/(auto|scroll)/u.test(`${style.overflowY} ${style.overflow}`) && current.scrollHeight > current.clientHeight) count += 1;
        current = current.parentElement;
      }
      return count;
    });
    expect(scrollableAncestors).toBeLessThanOrEqual(2);
    await dialog.getByRole("button", { name: "关闭" }).click();
  }
});

test("loading, empty, error, and permission states remain usable", async ({ teacherPage }) => {
  const loadingCourseUrl = "http://localhost:8001/api/courses/course-loading";
  await teacherPage.route(loadingCourseUrl, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 350));
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
      id: "course-loading", title: "加载验收课程", description: "", icon: "", color: "#3157d5", revision: 4, membership_role: "editor",
    }) });
  });
  await teacherPage.goto("/#course-detail?course_id=course-loading", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByRole("heading", { name: "正在加载课程" })).toBeVisible();
  await expectNoPageOverflow(teacherPage);
  await expect(teacherPage.getByRole("heading", { name: "课程概览", exact: true })).toBeVisible();

  const emptyMaterials = (route: import("playwright/test").Route) => route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  await teacherPage.route("**/api/courses/course-physics/materials*", emptyMaterials);
  await teacherPage.goto("/#resources?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByText("你还没有生成资源", { exact: true })).toBeVisible();
  await expectNoPageOverflow(teacherPage);
  await teacherPage.unroute("**/api/courses/course-physics/materials*", emptyMaterials);

  await teacherPage.route("http://localhost:8001/api/courses/course-error", (route) => route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "固定错误" }) }));
  await teacherPage.goto("/#course-detail?course_id=course-error", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByRole("heading", { name: "页面加载失败" })).toBeVisible();
  await expect(teacherPage.getByRole("button", { name: "重新加载" })).toBeInViewport();

  await teacherPage.route("http://localhost:8001/api/courses/course-forbidden", (route) => route.fulfill({ status: 403, contentType: "application/json", body: JSON.stringify({ detail: "forbidden" }) }));
  await teacherPage.goto("/#course-detail?course_id=course-forbidden", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByRole("heading", { name: "当前账号无权访问" })).toBeVisible();
  await expectNoPageOverflow(teacherPage);
});
