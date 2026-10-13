import { test, expect } from "../e2e/fixtures/teacherApp";

for (const role of ["teacher", "student"] as const) test(`existing course opens the original three workspaces with learning navigation (${role})`, async ({ teacherPage: page }, info) => {
  if (role === "student") {
    await page.addInitScript(() => {
      localStorage.setItem("edu-ai-auth", JSON.stringify({ token: "student-fixture-token", user: { username: "student-a", role: "student" } }));
    });
    await page.route("**/api/auth/verify", route => route.fulfill({ json: { valid: true, user: { username: "student-a", role: "student" } } }));
  }
  await page.route("**/api/self-learning/state", route => route.fulfill({ json: { version: 1, rooms: [], resources: [], jobs: [], shared: [], serverJobs: [] } }));
  await page.route("**/api/course-preparations", route => route.fulfill({ json: { preparations: [] } }));
  await page.route("**/api/course-preparations/notifications", route => route.fulfill({ json: { items: [] } }));
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "主导航" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "我的课堂" })).toHaveCount(0);
  // The old workspace remains directly accessible; the homepage now uses recent learning.
  await page.goto(`/?workspace=1#${role === "teacher" ? "classroom-studio" : "student-classroom"}?course_id=course-physics`);
  const nav = page.getByRole("navigation", { name: "课程工作栏", exact: true });
  // The original workspace loads its renderer and editor modules on first entry.
  await expect(nav).toBeVisible({ timeout: 20000 });
  await expect(nav.getByRole("link")).toHaveText(["AI 课堂", "工作台", "资源中心"]);
  await expect(page.locator(".course-classroom-workspace")).toBeVisible();
  await expect(nav.getByRole("link", { name: "AI 课堂" })).toHaveAttribute("aria-current", "page");
  await page.screenshot({ path: info.outputPath("migrated-classroom.png") });
  await nav.getByRole("link", { name: "工作台", exact: true }).click();
  await expect(page).toHaveURL(role === "teacher" ? /#ai\?course_id=course-physics/ : /#student-ai\?course_id=course-physics/);
  await expect(page.locator(".ai-studio-page")).toBeVisible();
  await page.screenshot({ path: info.outputPath("migrated-studio.png") });
  await nav.getByRole("link", { name: "资源中心", exact: true }).click();
  await expect(page).toHaveURL(role === "teacher" ? /#resources\?course_id=course-physics/ : /#student-resources\?course_id=course-physics/);
  await expect(nav.getByRole("link", { name: "资源中心" })).toHaveAttribute("aria-current", "page");
  await expect(page.locator("main")).toBeVisible();
  await page.screenshot({ path: info.outputPath("migrated-resources.png") });
  await page.reload();
  await expect(nav).toBeVisible({ timeout: 20000 });
  await expect(nav.getByRole("link", { name: "资源中心" })).toHaveAttribute("aria-current", "page");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole("link", { name: "返回全部课程" }).click();
  await expect(page.getByRole("heading", { name: /学有所思/ })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "课程工作栏", exact: true })).toHaveCount(0);
  expect(errors).toEqual([]);
});
