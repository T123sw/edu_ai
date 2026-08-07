import { expect, test } from "./fixtures/teacherApp";

test("course workspace has one stable navigation and main landmark", async ({
  teacherPage,
}, testInfo) => {
  await teacherPage.goto("/#course-detail?course_id=course-physics", {
    waitUntil: "domcontentloaded",
  });

  await expect(teacherPage.getByTestId("course-shell")).toBeVisible();
  await expect(teacherPage.locator("main")).toHaveCount(1);
  await expect(teacherPage.locator("[aria-current='page']")).toHaveCount(1);
  await expect(teacherPage.getByText("当前课程")).toHaveCount(0);
  await expect(teacherPage.getByRole("button", { name: /任务中心/ })).toBeVisible();
  await expect(teacherPage.getByRole("link", { name: "个人中心" })).toBeVisible();

  const overflows = await teacherPage.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(overflows).toBe(false);

  if (testInfo.project.name === "compact1024") {
    const menuButton = teacherPage.getByRole("button", { name: "打开课程导航" });
    await menuButton.focus();
    await menuButton.press("Enter");
    await expect(teacherPage.getByTestId("course-navigation-drawer")).toBeVisible();
  }
});

test("course navigation keeps global actions and changes the task page", async ({
  teacherPage,
}) => {
  await teacherPage.goto("/#course-detail?course_id=course-physics", {
    waitUntil: "domcontentloaded",
  });

  await teacherPage.getByRole("link", { name: "课程资源" }).click();
  await expect(teacherPage).toHaveURL(/#resources\?course_id=course-physics/);
  await expect(teacherPage.getByRole("heading", { name: "课程资源", exact: true })).toBeVisible();
  await expect(teacherPage.getByRole("button", { name: /任务中心/ })).toBeVisible();
  await expect(teacherPage.getByRole("link", { name: "个人中心" })).toBeVisible();
  await expect(teacherPage.getByText("当前课程")).toHaveCount(0);
});
