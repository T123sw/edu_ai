import { expect, test } from "./fixtures/teacherApp";
import { physicsCourse } from "./fixtures/apiRoutes";

test("course owner can delete the whole course knowledge base", async ({ teacherPage }) => {
  await teacherPage.route("http://localhost:8001/api/courses/course-physics**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "DELETE" && path.endsWith("/knowledge-base")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "课程知识库已删除" }),
      });
    }
    if (request.method() === "GET" && path === `/api/courses/${physicsCourse.id}`) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...physicsCourse, membership_role: "owner" }),
      });
    }
    return route.fallback();
  });
  teacherPage.on("dialog", (dialog) => dialog.accept());

  await teacherPage.goto("/#knowledge?course_id=course-physics&view=documents", {
    waitUntil: "domcontentloaded",
  });
  const requestPromise = teacherPage.waitForRequest((request) =>
    request.method() === "DELETE"
      && new URL(request.url()).pathname === "/api/courses/course-physics/knowledge-base",
  );
  await teacherPage.getByRole("button", { name: "删除课程知识库" }).click();
  await requestPromise;
});

test("course owner must enter the exact title before deleting a course", async ({ teacherPage }) => {
  await teacherPage.route("http://localhost:8001/api/courses/course-physics**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (request.method() === "DELETE" && path === `/api/courses/${physicsCourse.id}`) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ message: "课程已删除" }),
      });
    }
    if (request.method() === "GET" && path === `/api/courses/${physicsCourse.id}/members`) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [] }),
      });
    }
    if (request.method() === "GET" && path === `/api/courses/${physicsCourse.id}`) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ...physicsCourse, membership_role: "owner" }),
      });
    }
    return route.fallback();
  });

  await teacherPage.goto("/#edit?course_id=course-physics", { waitUntil: "domcontentloaded" });
  const deleteButton = teacherPage.getByRole("button", { name: "永久删除课程" });
  await expect(deleteButton).toBeDisabled({ timeout: 20_000 });
  await teacherPage.getByLabel("输入课程名称确认删除").fill(physicsCourse.title);
  await expect(deleteButton).toBeEnabled();

  const requestPromise = teacherPage.waitForRequest((request) =>
    request.method() === "DELETE"
      && new URL(request.url()).pathname === `/api/courses/${physicsCourse.id}`,
  );
  await deleteButton.click();
  await requestPromise;
  await expect(teacherPage).toHaveURL(/#home$/);
});
