import { expect, test } from "./fixtures/teacherApp";
import type { Page } from "playwright/test";

async function enterConfig(page: Page, resourceName: string) {
  await page.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await page.evaluate(() => window.localStorage.removeItem("edu-ai:generation-draft:course-physics"));
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "生成工厂", exact: true }).click();
  await page.getByRole("button", { name: resourceName, exact: false }).click();
  await page.getByText(/资料范围（/).click();
  await page.getByRole("radio", { name: "不使用资料", exact: false }).check();
}

test("visual resources use structured, shared, non-overflowing forms", async ({ teacherPage }) => {
  const requests: Array<{ url: string; body: Record<string, unknown> }> = [];
  teacherPage.on("request", (request) => {
    if (/\/graph\/direct$|\/classrooms\/generate$/u.test(request.url())) {
      requests.push({ url: request.url(), body: request.postDataJSON() as Record<string, unknown> });
    }
  });

  await enterConfig(teacherPage, "思维导图");
  await teacherPage.getByLabel("思维导图主题 *").fill("电磁学");
  await teacherPage.getByLabel("层级深度").fill("4");
  await teacherPage.getByText("更多设置").click();
  await teacherPage.getByLabel("关系侧重点").fill("突出概念关系");
  await teacherPage.getByRole("button", { name: "开始后台生成" }).click();

  await enterConfig(teacherPage, "AI 课堂");
  await teacherPage.getByLabel("研究主题 *").fill("波的干涉");
  await teacherPage.getByText("更多设置").click();
  await teacherPage.getByLabel("场景数量").fill("8");
  await teacherPage.getByLabel("声音").selectOption("nova");
  const submit = teacherPage.getByRole("button", { name: "开始后台生成" });
  await expect(submit).toBeInViewport();
  await submit.click();

  await expect.poll(() => requests.length).toBe(2);
  const graph = requests.find((item) => item.url.endsWith("/graph/direct"))!;
  expect(graph.body.description).toBe("突出概念关系");
  expect(graph.body.max_depth).toBe(4);
  const classroom = requests.find((item) => item.url.endsWith("/classrooms/generate"))!;
  expect(classroom.body.voice).toBe("nova");
  expect(classroom.body.scene_count).toBe(8);

  await teacherPage.goto("/#classroom-studio?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await teacherPage.getByRole("button", { name: "创建 AI 课堂" }).click();
  await expect(teacherPage.locator('[data-resource-form="classroom"]')).toBeVisible();
  await expect(teacherPage.getByLabel("研究主题 *")).toBeVisible();
});
