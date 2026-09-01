import { test as base, expect, type Page } from "playwright/test";
import { installTeacherApiRoutes } from "./apiRoutes";

type TeacherFixtures = {
  teacherPage: Page;
};

export const test = base.extend<TeacherFixtures>({
  teacherPage: async ({ page }, use) => {
    await installTeacherApiRoutes(page);
    await page.addInitScript(() => {
      window.localStorage.setItem(
        "edu-ai-auth",
        JSON.stringify({
          token: "teacher-fixture-token",
          user: { username: "teacher-a", role: "teacher" },
        }),
      );
      window.localStorage.setItem("stitch-theme", "ocean");
    });
    await use(page);
  },
});

export { expect };

