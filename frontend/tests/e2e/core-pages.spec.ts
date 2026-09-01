import { expect, test } from "./fixtures/teacherApp";
import { physicsCourse } from "./fixtures/apiRoutes";

test("login explains the teacher workspace and exposes concrete errors inline", async ({ teacherPage }) => {
  await teacherPage.goto("/#home", { waitUntil: "domcontentloaded" });
  await teacherPage.route("http://localhost:8001/api/auth/verify", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({ valid: false, user: null }),
    }),
  );
  await teacherPage.reload({ waitUntil: "domcontentloaded" });

  await expect(teacherPage.getByRole("heading", { name: "登录 Edu AI", exact: true })).toBeVisible();
  await expect(teacherPage.getByText("课程中心 · 教师工作台", { exact: true })).toBeVisible();
  await expect(teacherPage.getByText("开发演示账号已启用", { exact: false })).toHaveCount(0);
});

test("home renders one searchable factual course entry", async ({ teacherPage }) => {
  await teacherPage.goto("/#home", { waitUntil: "domcontentloaded" });
  const cards = teacherPage.locator(".teacher-course-card");
  await expect(cards).toHaveCount(1);
  await expect(cards).toContainText("课程资料");
  await expect(cards).toContainText("课程资源");
  await expect(cards).toContainText("进行中任务");
  await expect(cards).not.toContainText("%");

  await teacherPage.getByPlaceholder("搜索课程名称或简介").fill("不存在的课程");
  await expect(teacherPage.getByText("没有找到匹配的课程。", { exact: true })).toBeVisible();
});

test("course overview is compact, factual, and has six stable entries", async ({ teacherPage }) => {
  await teacherPage.goto("/#course-detail?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.locator(".course-overview__facts article")).toHaveCount(4);
  await expect(teacherPage.locator(".course-overview__entries a")).toHaveCount(6);
  await expect(teacherPage.getByRole("link", { name: "开始问答或生成" })).toBeVisible();
  await expect(teacherPage.locator(".course-overview img")).toHaveCount(0);
  expect(await teacherPage.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test("viewer settings is a factual read-only view", async ({ teacherPage }) => {
  await teacherPage.route(`http://localhost:8001/api/courses/${physicsCourse.id}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({ ...physicsCourse, membership_role: "viewer" }),
    }),
  );
  await teacherPage.goto("/#edit?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await expect(teacherPage.getByText("课程信息仅供查看。", { exact: false })).toBeVisible();
  await expect(teacherPage.getByRole("button", { name: "保存修改" })).toHaveCount(0);
  await expect(teacherPage.getByRole("link", { name: "课程设置" })).toHaveCount(0);
});
