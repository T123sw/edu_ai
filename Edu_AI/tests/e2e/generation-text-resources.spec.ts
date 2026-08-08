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

test("long-form fields stay reachable and reach their exact requests", async ({ teacherPage }) => {
  const requests: Array<{ url: string; body: Record<string, unknown> }> = [];
  teacherPage.on("request", (request) => {
    if (/\/(report|lesson-plan|blog)\/direct$/u.test(request.url())) {
      requests.push({ url: request.url(), body: request.postDataJSON() as Record<string, unknown> });
    }
  });

  await enterConfig(teacherPage, "教学报告");
  await teacherPage.getByLabel("报告主题 *").fill("学习行为分析");
  await teacherPage.getByLabel("分析深度").selectOption("deep");
  await teacherPage.getByText("更多设置").click();
  await teacherPage.getByLabel("补充要求（选填）").fill("列出三项建议");
  await teacherPage.getByRole("button", { name: "开始后台生成" }).click();

  await enterConfig(teacherPage, "教案",);
  await teacherPage.getByLabel("教学主题 *").fill("牛顿第二定律");
  await teacherPage.getByText("更多设置").click();
  await teacherPage.getByLabel("教学过程").fill("导入—探究—应用");
  await teacherPage.getByRole("button", { name: "开始后台生成" }).click();

  await enterConfig(teacherPage, "教学博客");
  await teacherPage.getByLabel("博客主题 *").fill("量子隧穿");
  await teacherPage.getByLabel("表达语气").selectOption("academic");
  await teacherPage.getByLabel("文章长度").selectOption("long");
  await teacherPage.getByText("更多设置").click();
  await teacherPage.getByLabel("补充要求").fill("加入生活类比");
  const submit = teacherPage.getByRole("button", { name: "开始后台生成" });
  await expect(submit).toBeInViewport();
  await submit.click();

  await expect.poll(() => requests.length).toBe(3);
  const report = requests[0].body.report_config as Record<string, unknown>;
  expect(report.depth).toBe("deep");
  expect(report.special_requirements).toBe("列出三项建议");
  expect(requests[1].body.teaching_process).toBe("导入—探究—应用");
  expect(requests[2].body.tone).toBe("academic");
  expect(requests[2].body.length).toBe("long");
  expect(requests[2].body.special_requirements).toBe("加入生活类比");
});
