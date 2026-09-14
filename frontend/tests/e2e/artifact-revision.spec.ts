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

test('new lesson plan handoff clears a report reference before confirmation', async ({ teacherPage: page }) => {
  await page.route('**/api/courses/*/materials**', route => route.fulfill({ json: new URL(route.request().url()).pathname.endsWith('/materials') ? [material] : material }));
  const requests: any[] = [];
  await page.route('**/api/chat/v2/stream', route => {
    requests.push(route.request().postDataJSON());
    const first = requests.length === 2;
    const payload = { message: { role: 'assistant', content: first ? '# 数组教案方案\n\n课堂活动与评价。' : '正在生成教案。' },
      conversation: { conversation_id: 'lesson-handoff' }, action: { name: 'generate.lesson_plan' }, artifacts: [], sources: [],
      workflow: { type: 'lesson_plan', status: first ? 'awaiting_confirm' : 'running', stage: first ? 'outline' : 'generating' },
      resource_creation_handoff: first, trace: { path: 'deepseek-harness' } };
    if (requests.length === 1) Object.assign(payload, {
      message: { role: 'assistant', content: '旧修改稿已展示，尚未保存。' }, resource_creation_handoff: false,
      artifact_revision: { status: 'preview', operation_id: 'old-operation', artifact_reference: { artifact_id: 'revision-report', artifact_type: 'report', source_course_id: 'course-physics', version_id: 'v2', title: '数组基础报告' },
        draft: { draft_id: 'old-draft', revision: 1, focus: '课堂案例', reference: { artifact_id: 'revision-report', artifact_type: 'report', source_course_id: 'course-physics', version_id: 'v2', title: '数组基础报告' },
          segments: [{ kind: 'unchanged', text: '# 旧报告正文' }, { kind: 'insert', text: '新增案例' }] } },
    });
    return route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'result', payload })}\n\ndata: ${JSON.stringify({ type: 'done', payload: {} })}\n\n` });
  });
  await page.goto('/#resources?course_id=course-physics');
  await page.getByRole('button', { name: '让 AI 修改', exact: true }).click();
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await expect(input).toHaveValue('《数组基础报告》 ');
  await input.fill('《数组基础报告》补充一个案例'); await input.press('Enter');
  await expect(page.getByRole('button', { name: '保存修改', exact: true })).toBeVisible();
  await input.fill('根据《数组基础报告》生成一份新的数组教案'); await input.press('Enter');
  await expect(page.getByRole('heading', { name: '数组教案方案', exact: true })).toBeVisible({ timeout: 15000 });
  expect(requests[0].artifact_reference.artifact_id).toBe('revision-report');
  await expect(page.getByRole('button', { name: '保存修改', exact: true })).toHaveCount(0);
  await expect(page.getByRole('region', { name: '文档修改稿' })).toHaveCount(0);
  await input.fill('可以'); await input.press('Enter');
  await expect.poll(() => requests.length).toBe(3);
  expect(requests[2].artifact_reference).toBeFalsy();
  await expect(page.getByRole('region', { name: '文档修改稿' })).toHaveCount(0);
});

test('recent resources refreshes saved documents and shows their actual type', async ({ teacherPage: page }) => {
  await page.route('**/src/**', route => route.continue());
  let saved = false;
  await page.route('**/api/courses/*/materials**', route => route.fulfill({ json: saved ? [
    { ...material, material_id: 'new-saved-report', title: '数组的实现（修改稿）', created_at: '2026-09-09T06:36:31Z', updated_at: '2026-09-09T06:36:31Z' },
  ] : [] }));
  await page.goto('/#ai?course_id=course-physics');
  const factoryToggle = page.getByRole('button', { name: '生成工厂', exact: true });
  if ((page.viewportSize()?.width || 1440) <= 1024) await factoryToggle.click({ timeout: 15000 });
  await expect(page.getByRole('button', { name: '刷新最近生成资源' })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText('暂无生成记录', { exact: true })).toBeVisible();
  saved = true;
  await page.getByRole('button', { name: '刷新最近生成资源' }).click();
  await expect(page.getByRole('button', { name: '数组的实现（修改稿） 教学报告 · 已完成', exact: true })).toBeVisible();
});
