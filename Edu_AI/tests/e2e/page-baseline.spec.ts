import { expect, test } from "./fixtures/teacherApp";

test("teacher can traverse every core course page", async ({ teacherPage }) => {
  test.fail(
    true,
    "统一课程导航将在 Plan 3 / Task 2 实现；当前失败作为结构基线。",
  );
  await teacherPage.goto("/#home", { waitUntil: "domcontentloaded" });
  const courseLink = teacherPage.getByRole("link", { name: "大学物理" });
  await expect(courseLink).toBeVisible({ timeout: 2_000 });
  await courseLink.click();
  await expect(teacherPage).toHaveURL(/course_id=course-physics/);

  for (const name of [
    "课程概览",
    "问答与生成",
    "课程知识",
    "AI 课堂",
    "课程资源",
    "课程设置",
  ]) {
    await teacherPage.getByRole("link", { name }).click();
    await expect(teacherPage.getByRole("heading", { name })).toBeVisible();
  }
});

const baselineRoutes = [
  ["login", "/#home?fixture_logged_out=1"],
  ["home", "/#home"],
  ["course-detail", "/#course-detail?course_id=course-physics"],
  ["workspace", "/#ai?course_id=course-physics"],
  ["knowledge-documents", "/#knowledge?course_id=course-physics"],
  ["knowledge-structure", "/#graph?course_id=course-physics"],
  ["classroom", "/#classroom-studio?course_id=course-physics"],
  ["resources", "/#resources?course_id=course-physics"],
  ["settings", "/#edit?course_id=course-physics"],
] as const;

test("capture diagnostic page inventory", async ({ teacherPage }, testInfo) => {
  let restoreTeacherSession = false;
  for (const [name, url] of baselineRoutes) {
    await teacherPage.goto(url, { waitUntil: "domcontentloaded" });
    if (name === "login") {
      await teacherPage.evaluate(() => {
        window.localStorage.removeItem("edu-ai-auth");
      });
      await teacherPage.reload({ waitUntil: "domcontentloaded" });
      restoreTeacherSession = true;
    } else if (restoreTeacherSession) {
      await teacherPage.evaluate(() => {
        window.localStorage.setItem(
          "edu-ai-auth",
          JSON.stringify({
            token: "teacher-fixture-token",
            user: { username: "teacher-a", role: "teacher" },
          }),
        );
      });
      await teacherPage.reload({ waitUntil: "domcontentloaded" });
      restoreTeacherSession = false;
    }
    await expect(teacherPage.locator("body")).toBeVisible();
    await teacherPage.screenshot({
      path: testInfo.outputPath(`baseline-${name}.png`),
      fullPage: false,
    });
  }
});
