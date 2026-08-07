import { expect, test } from "./fixtures/teacherApp";
import type { Page, Route } from "playwright/test";

const approvedPages = [
  ["login", "/#home", false],
  ["course-home", "/#home", true],
  ["course-overview", "/#course-detail?course_id=course-physics", true],
  ["question-generation", "/#ai?course_id=course-physics", true],
  ["knowledge-documents", "/#knowledge?course_id=course-physics&view=documents", true],
  ["knowledge-structure", "/#knowledge?course_id=course-physics&view=structure", true],
  ["classroom-list", "/#classroom-studio?course_id=course-physics", true],
  ["classroom-player", "/#classroom-player?course_id=course-physics&classroom_id=classroom-mechanics", true],
  ["course-resources", "/#resources?course_id=course-physics", true],
  ["course-settings", "/#edit?course_id=course-physics", true],
  ["profile", "/#profile", true],
] as const;

async function setSession(page: Page, authenticated: boolean, theme: "ocean" | "dark") {
  await page.evaluate(({ authenticated: nextAuthenticated, theme: nextTheme }) => {
    if (nextAuthenticated) {
      window.localStorage.setItem("edu-ai-auth", JSON.stringify({
        token: "teacher-fixture-token",
        user: { username: "teacher-a", role: "teacher" },
      }));
    } else {
      window.localStorage.removeItem("edu-ai-auth");
    }
    window.localStorage.setItem("stitch-theme", nextTheme);
  }, { authenticated, theme });
}

async function waitForCssBackground(page: Page, selector: string) {
  await page.locator(selector).evaluate(async (element) => {
    const match = getComputedStyle(element).backgroundImage.match(/url\(["']?([^"')]+)["']?\)/u);
    if (!match?.[1]) return;
    const background = new Image();
    background.src = match[1];
    if (background.complete && background.naturalWidth > 0) return;
    await new Promise<void>((resolve) => {
      background.onload = () => resolve();
      background.onerror = () => resolve();
    });
  });
}

async function captureMatrix(page: Page, theme: "light" | "dark") {
  for (const [name, url, authenticated] of approvedPages) {
    if (process.env.PLAYWRIGHT_VISUAL_PAGE && process.env.PLAYWRIGHT_VISUAL_PAGE !== name) {
      continue;
    }
    const rejectVerify = (route: Route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ valid: false, user: null }),
    });
    if (!authenticated) {
      await page.route("http://localhost:8001/api/auth/verify", rejectVerify);
    }
    await page.goto(url, { waitUntil: "domcontentloaded" });
    await setSession(page, authenticated, theme === "dark" ? "dark" : "ocean");
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    if (name === "login") {
      await waitForCssBackground(page, ".login-page");
    }
    await expect(page).toHaveScreenshot(`${theme}-${name}.png`, {
      animations: "disabled",
      caret: "hide",
      fullPage: false,
      maxDiffPixelRatio: 0.01,
    });
    if (!authenticated) {
      await page.unroute("http://localhost:8001/api/auth/verify", rejectVerify);
    }
  }
}

test("approved teacher pages match the light visual baseline", async ({ teacherPage }) => {
  await captureMatrix(teacherPage, "light");
});

test("critical teacher pages match the dark visual baseline", async ({ teacherPage }, testInfo) => {
  test.skip(!["desktop1366", "compact1024"].includes(testInfo.project.name), "dark review is required at 1366×768 and 1024×768");
  await captureMatrix(teacherPage, "dark");
});
