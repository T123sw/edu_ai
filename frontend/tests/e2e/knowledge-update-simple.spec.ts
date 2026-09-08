import { expect, test } from './fixtures/teacherApp';
import { installCourseKnowledgeBuildRoutes } from './fixtures/courseKnowledgeBuild';

test('knowledge update begins with needs and optional textbooks', async ({ teacherPage: page }, testInfo) => {
  await installCourseKnowledgeBuildRoutes(page, { existingGraph: true });
  await page.goto('/#knowledge?course_id=course-physics');
  await page.getByRole('button', { name: '更新知识库', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '更新课程知识库' });
  await expect(dialog).toBeVisible();
  await expect(dialog).not.toContainText('修订');
  await expect(dialog.getByRole('radio')).toHaveCount(0);
  await expect(dialog.getByLabel('目录层级')).toHaveCount(0);
  await dialog.getByRole('textbox').fill('只补充循环结构的练习');
  await expect(dialog.getByRole('button', { name: '分析补充建议', exact: true })).toBeEnabled();
  const width = await dialog.evaluate(el => el.getBoundingClientRect().width / el.parentElement!.getBoundingClientRect().width);
  expect(width).toBeGreaterThan(.8);
  await page.screenshot({ path: testInfo.outputPath('knowledge-update-simple.png'), fullPage: true });
});
