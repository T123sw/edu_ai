import { expect, test } from "./fixtures/teacherApp";


test("teacher reviews and publishes a resource from the curriculum directory", async ({ teacherPage }) => {
  await teacherPage.goto("/#classroom-studio?course_id=course-physics", {
    waitUntil: "domcontentloaded",
  });

  const tree = teacherPage.getByRole("tree", { name: "课程目录" });
  await expect(tree).toBeVisible();
  await tree.getByRole("treeitem", { name: /1\.1 力与运动/ }).getByRole("button").click();
  await tree.getByRole("treeitem", { name: /力学学习指南.*待审核/ }).getByRole("button").click();

  await expect(teacherPage.getByRole("heading", { name: "力学学习指南", exact: true, level: 2 })).toBeVisible();
  const review = teacherPage.getByRole("complementary", { name: "审核与发布" });
  await expect(review).toContainText("第 1 版待审核");
  const reviewResponse = teacherPage.waitForResponse((response) =>
    response.request().method() === "POST"
      && response.url().endsWith("/standard-resources/standard-mechanics-guide/review"),
  );
  await review.getByRole("button", { name: "批准并发布" }).click();
  expect((await reviewResponse).status()).toBe(200);
  await expect(review).toContainText("已发布第 1 版");
  await expect(tree.getByRole("treeitem", { name: /力学学习指南.*已发布/ })).toBeVisible();
});


test("compact classroom keeps the curriculum directory in a usable drawer", async ({ teacherPage }) => {
  await teacherPage.setViewportSize({ width: 820, height: 900 });
  await teacherPage.goto("/#classroom-studio?course_id=course-physics", {
    waitUntil: "domcontentloaded",
  });

  await teacherPage.getByRole("button", { name: "课程目录", exact: true }).click();
  const directory = teacherPage.locator(".course-classroom-catalog__directory");
  await expect(directory).toHaveClass(/is-open/);
  await expect(directory.getByRole("tree", { name: "课程目录" })).toBeVisible();
  await directory.getByRole("button", { name: "关闭课程目录" }).click();
  await expect(directory).not.toHaveClass(/is-open/);
  expect(await teacherPage.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
