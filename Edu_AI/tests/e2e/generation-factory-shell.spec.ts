import { expect, test } from "./fixtures/teacherApp";
import type { Page } from "playwright/test";

async function openFactory(page: Page, projectName: string) {
  void projectName;
  if (!(await page.getByTestId("generation-factory").isVisible())) {
    await page.getByRole("button", { name: "打开生成工厂面板" }).click();
  }
  await expect(page.getByTestId("generation-factory")).toBeVisible();
}

test("generation factory is keyboard operable and keeps its footer reachable", async ({ teacherPage }, testInfo) => {
  await teacherPage.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await openFactory(teacherPage, testInfo.project.name);

  await expect(teacherPage.locator(".generation-factory__registry button")).toHaveCount(9);
  await teacherPage.getByRole("button", { name: "下一步" }).press("Enter");
  const noSource = teacherPage.getByRole("radio", { name: "不使用资料", exact: false });
  await noSource.check();
  await teacherPage.getByRole("button", { name: "下一步" }).click();
  await teacherPage.getByLabel("报告主题 *").fill("牛顿运动定律复习");
  await teacherPage.getByRole("button", { name: "下一步" }).click();
  const submit = teacherPage.getByRole("button", { name: "开始后台生成" });
  await expect(submit).toBeVisible();
  expect(await submit.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return rect.top >= 0 && rect.bottom <= window.innerHeight;
  })).toBe(true);
  await submit.click();
  await expect(teacherPage.getByText("任务 job-generated-fixture 已保存", { exact: false })).toBeVisible();
});

test("generation draft and active job recover after refresh", async ({ teacherPage }, testInfo) => {
  await teacherPage.addInitScript(() => {
    window.localStorage.setItem("edu-ai:generation-draft:course-physics", JSON.stringify({
      jobId: "job-restored",
      draft: {
        resourceType: "report",
        topic: "恢复主题",
        audience: "本科生",
        requirements: "",
        source: { mode: "none", selectedDocumentIds: [] },
        config: {
          template: "detailed",
          topic: "恢复主题",
          audience: "本科生",
          depth: "standard",
          structureEmphasis: "结论、依据与可执行建议",
          specialRequirements: "",
        },
      },
    }));
  });
  await teacherPage.goto("/#ai?course_id=course-physics", { waitUntil: "domcontentloaded" });
  await openFactory(teacherPage, testInfo.project.name);
  await expect(teacherPage.getByText("恢复主题", { exact: false })).toHaveCount(0);
  await teacherPage.getByRole("button", { name: "下一步" }).click();
  await teacherPage.getByRole("radio", { name: "不使用资料", exact: false }).check();
  await teacherPage.getByRole("button", { name: "下一步" }).click();
  await expect(teacherPage.getByLabel("报告主题 *")).toHaveValue("恢复主题");
});
