import { expect, test } from './fixtures/teacherApp';

test('only personal sources are selectable and the RAG toggle remains available', async ({ teacherPage: page }, testInfo) => {
  await page.route('**/api/personal-knowledge/documents?**', route => route.fulfill({ json: [
    { id: 'personal-1', name: '教师讲义.pdf', type: 'file', library_type: 'personal', status: 'ready', owner_user_id: 'teacher-a' },
    { id: 'personal-2', name: '补充练习.pdf', type: 'file', library_type: 'personal', status: 'ready', owner_user_id: 'teacher-a' },
  ] }));
  await page.goto('/#ai?course_id=course-physics&scopeType=knowledge_point&scopeId=mechanics');
  await page.getByRole('button', { name: testInfo.project.name === 'mobile' ? '知识库' : '展开知识库', exact: true }).click();
  const panel = page.locator('.source-panel:not(.source-panel--collapsed)');
  await expect(panel.getByRole('tab', { name: /课程知识库/ })).toBeVisible();
  await expect(panel.locator('.source-panel__tree-node').first()).toBeVisible();
  await expect(panel.getByRole('checkbox')).toHaveCount(0);
  await panel.getByRole('tab', { name: /个人知识库/ }).click();
  await expect(panel.getByRole('checkbox')).toHaveCount(3);
  await panel.getByRole('checkbox', { name: '选择资料：教师讲义.pdf' }).check();
  await panel.getByRole('tab', { name: /课程知识库/ }).click();
  await expect(panel.getByRole('checkbox')).toHaveCount(0);
  await panel.getByRole('tab', { name: /个人知识库/ }).click();
  await expect(panel.getByRole('checkbox', { name: '选择资料：教师讲义.pdf' })).toBeChecked();
  await expect(panel.getByRole('checkbox', { name: '选择资料：补充练习.pdf' })).not.toBeChecked();
  await panel.getByRole('checkbox', { name: '选择全部个人资料' }).check();
  await expect(panel.getByRole('checkbox', { name: '选择资料：补充练习.pdf' })).toBeChecked();
  await panel.getByRole('checkbox', { name: '选择全部个人资料' }).uncheck();
  await expect(panel.getByRole('checkbox', { name: '选择资料：教师讲义.pdf' })).not.toBeChecked();
  await page.getByRole('button', { name: testInfo.project.name === 'mobile' ? '知识库' : '折叠知识库', exact: true }).click();
  const rag = page.getByRole('button', { name: 'RAG知识库', exact: true });
  await expect(rag).toBeVisible();
  const before = await rag.getAttribute('aria-pressed');
  await rag.click();
  await expect(rag).toHaveAttribute('aria-pressed', before === 'true' ? 'false' : 'true');
});
