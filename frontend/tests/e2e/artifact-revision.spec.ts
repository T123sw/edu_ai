import { expect, test } from './fixtures/teacherApp';

const material = { material_id: 'revision-report', material_type: 'report', course_id: 'course-physics', owner_user_id: 'teacher-a', visibility: 'private', version: 2, title: '数组基础报告', content: '# 数组\n\n独特段落\n\n原始案例', scope_type: 'knowledge_point', scope_id: 'arrays' };

for (const width of [1366, 390]) {
test(`resource button inserts a title with server ID/version without starting a task (${width}px)`, async ({ teacherPage: page }) => {
  await page.setViewportSize({ width, height: 844 });
  await page.route('**/api/courses/*/materials**', async route => {
    const path = new URL(route.request().url()).pathname;
    await route.fulfill({ json: path.endsWith('/materials') ? [material] : material });
  });
  const requests: Record<string, unknown>[] = [];
  await page.route('**/api/chat/v2/stream', async route => {
    requests.push(route.request().postDataJSON());
    const payload = { message: { role: 'assistant', content: '请说明具体修改方向' }, conversation: { conversation_id: 'revision-conv' }, action: { name: 'artifact.revise' }, artifacts: [], sources: [], trace: { path: 'fast' }, artifact_revision: { status: 'needs_clarification', message: '请说明具体修改方向', candidates: [] } };
    await route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'result', payload })}\n\ndata: ${JSON.stringify({ type: 'done', payload: { conversation_id: 'revision-conv' } })}\n\n` });
  });
  await page.goto('/#resources?course_id=course-physics');
  await page.getByRole('button', { name: '让 AI 修改', exact: true }).click();
  await expect(page).toHaveURL(/#ai/);
  await expect(page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）')).toHaveValue('《数组基础报告》 ');
  expect(requests).toHaveLength(0);
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await input.fill('《数组基础报告》增加两个案例');
  await input.press('Enter');
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].artifact_reference).toMatchObject({ artifact_id: 'revision-report', artifact_type: 'report', version_id: 'v2', source_course_id: 'course-physics' });
  await expect(page.getByText(/正在修改：/)).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(input).toBeVisible();
});

}
