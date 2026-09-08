import { expect, test } from './fixtures/teacherApp';
import { installCourseKnowledgeBuildRoutes } from './fixtures/courseKnowledgeBuild';

test('knowledge update keeps defaults simple and detailed settings available', async ({ teacherPage: page }, testInfo) => {
  const fixture = await installCourseKnowledgeBuildRoutes(page, { existingGraph: true });
  await page.goto('/#knowledge?course_id=course-physics');
  await page.getByRole('button', { name: '更新知识库', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '更新课程知识库' });
  await expect(dialog).toBeVisible();
  await expect(dialog).not.toContainText('修订');
  await expect(dialog.getByRole('radio', { name: /适量补充/ })).toHaveAttribute('aria-checked', 'true');
  await expect(dialog.getByLabel('目录层级')).not.toBeVisible();
  const width = await dialog.evaluate(el => el.getBoundingClientRect().width / el.parentElement!.getBoundingClientRect().width);
  expect(width).toBeGreaterThan(.8);
  await page.screenshot({ path: testInfo.outputPath('knowledge-update-simple.png'), fullPage: true });
  await dialog.getByText('更多设置', { exact: true }).click();
  await expect(dialog.getByLabel('目录层级')).toBeVisible();
  await dialog.getByLabel('每个知识点的资料数量', { exact: true }).fill('4');
  await dialog.getByText('更多设置', { exact: true }).click();
  await dialog.getByRole('button', { name: '下一步：添加教材' }).click();
  await expect(dialog.getByRole('heading', { name: '添加教材（可跳过）' })).toBeVisible();
  expect(fixture.build().config.target_materials_per_leaf).toBe(4);
});
