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

test("practice configurations are keyboard operable and auditable", async ({ teacherPage }) => {
  const requests: Record<string, Record<string, unknown>> = {};
  teacherPage.on("request", (request) => {
    const match = request.url().match(/\/(quiz|flashcard|game)\/direct$/u);
    if (match) requests[match[1]] = request.postDataJSON() as Record<string, unknown>;
  });

  await enterConfig(teacherPage, "习题");
  await teacherPage.getByLabel("习题主题 *").fill("力学综合练习");
  await teacherPage.getByLabel("题目数量 *").fill("14");
  await teacherPage.getByLabel("简答题").check();
  await teacherPage.getByText("更多设置").click();
  await teacherPage.getByLabel("附带解析").uncheck();
  await teacherPage.getByRole("button", { name: "开始后台生成" }).click();

  await enterConfig(teacherPage, "闪卡");
  await teacherPage.getByLabel("闪卡标题 *").fill("核心概念闪卡");
  await teacherPage.getByLabel("卡片数量 *").fill("18");
  await teacherPage.getByText("更多设置").click();
  await teacherPage.getByLabel("卡片中显示资料来源").uncheck();
  await teacherPage.getByRole("button", { name: "开始后台生成" }).click();

  await enterConfig(teacherPage, "课堂小游戏");
  await teacherPage.getByRole("button", { name: "记忆翻牌", exact: false }).focus();
  await teacherPage.getByRole("button", { name: "记忆翻牌", exact: false }).press("Enter");
  await teacherPage.getByLabel("游戏主题 *").fill("概念配对");
  await teacherPage.getByLabel("卡片 / 题目数量 *").fill("12");
  await teacherPage.getByText("更多设置").click();
  await teacherPage.getByLabel("课堂用时（分钟）").fill("8");
  await expect(teacherPage.getByRole("region", { name: "游戏配置预览" })).toContainText("12 张卡片");
  const submit = teacherPage.getByRole("button", { name: "开始后台生成" });
  await expect(submit).toBeInViewport();
  await submit.click();

  await expect.poll(() => Object.keys(requests).length).toBe(3);
  const quiz = requests.quiz.quiz_config as Record<string, unknown>;
  expect(quiz.question_count).toBe(14);
  expect(quiz.question_types).toEqual(["choice", "short"]);
  expect(quiz.include_answers).toBe(true);
  expect(quiz.include_explanations).toBe(false);
  const flashcard = requests.flashcard.flashcard_config as Record<string, unknown>;
  expect(flashcard.count).toBe(18);
  expect(flashcard.show_sources).toBe(false);
  expect(requests.game.game_type).toBe("memory_flip");
  expect(requests.game.card_count).toBe(12);
  expect(requests.game.duration_minutes).toBe(8);
});
