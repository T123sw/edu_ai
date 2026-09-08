import { expect, test } from './fixtures/teacherApp';

test.beforeEach(async ({ teacherPage: page }) => {
  // Vite module URLs also contain /api/; keep API mocks away from source files.
  await page.route('**/src/**', route => route.continue());
  await page.route('**/api/personal-knowledge/documents**', route => route.fulfill({ json: [] }));
});

const graph = { root: { id: 'root', label: '数据结构', children: [
  { id: 'array', label: '数组', data: { level: 1, hasChildren: false, type: 'concept' } },
  { id: 'list', label: '链表', data: { level: 1, hasChildren: false, type: 'concept' } },
] } };

test('scope bar resolves server labels and selection preserves hash contract', async ({ teacherPage: page }, testInfo) => {
  await page.route('**/api/courses/*/knowledge-graph', route => route.fulfill({ json: graph }));
  await page.goto('/#ai?course_id=course-physics&scopeType=knowledge_point&scopeId=array&scopeLabel=伪造名称');
  const bar = page.getByTestId('workspace-context-bar');
  await expect(bar).toBeVisible({ timeout: 15000 });
  await expect(bar).toContainText('数组');
  await expect(bar).not.toContainText('伪造名称');
  await bar.getByRole('button', { name: '调整', exact: true }).click();
  const select = page.getByRole('combobox', { name: '选择备课知识点' });
  await select.focus();
  await select.fill('链表');
  await page.locator('.workspace-topic-tree-popup .ant-select-tree-title').getByText('链表', { exact: true }).click();
  await expect(page).toHaveURL(/scopeId=list/);
  await page.screenshot({ path: testInfo.outputPath('knowledge-context-1366.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(bar).toBeVisible();
  expect(await bar.evaluate(el => el.getBoundingClientRect().right <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath('knowledge-context-390.png') });
});

test('clarification returns through result event and answer retains conversation', async ({ teacherPage: page }) => {
  await page.route('**/api/courses/*/knowledge-graph', route => route.fulfill({ json: graph }));
  const requests: Array<{ question: string; conversation_id?: string }> = [];
  await page.route('**/api/chat/v2/stream', async route => {
    requests.push(route.request().postDataJSON());
    const payload = { message: { role: 'assistant', content: requests.length === 1 ? '请指定知识点' : '已收到数组报告请求' },
      conversation: { conversation_id: 'scope-conv' }, action: { name: 'workspace.clarify' }, artifacts: [], sources: [], trace: { path: 'fast' },
      ...(requests.length === 1 ? { clarification: { status: 'needs_clarification', operation_id: 'op1', question: '请指定知识点', candidates: [{ scope_id: 'array', scope_title: '数组', scope_path: ['数据结构', '数组'] }] } } : {}) };
    await route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'result', payload })}\n\ndata: ${JSON.stringify({ type: 'done', payload: { conversation_id: 'scope-conv' } })}\n\n` });
  });
  await page.goto('/#ai?course_id=course-physics');
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await input.fill('为当前课程生成报告');
  await input.press('Enter');
  await page.getByRole('group', { name: '知识点澄清' }).getByRole('button', { name: '数据结构 › 数组' }).click();
  await expect.poll(() => requests.length).toBe(2);
  expect(requests[1].conversation_id).toBe('scope-conv');
  expect(requests[1].question).toBe('数据结构 › 数组');
});

test('late reply cannot overwrite a newly selected scope', async ({ teacherPage: page }) => {
  await page.route('**/api/courses/*/knowledge-graph', route => route.fulfill({ json: graph }));
  let release: (() => void) | undefined;
  let sent = false;
  await page.route('**/api/chat/v2/stream', async route => {
    sent = true;
    await new Promise<void>(resolve => { release = resolve; });
    const payload = { message: { role: 'assistant', content: '数组旧请求迟到结果' }, conversation: { conversation_id: 'old-array' }, action: { name: 'chat.reply' }, artifacts: [], sources: [], trace: { path: 'fast' } };
    await route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'result', payload })}\n\ndata: ${JSON.stringify({ type: 'done', payload: {} })}\n\n` });
  });
  await page.goto('/#ai?course_id=course-physics&scopeType=knowledge_point&scopeId=array');
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await input.fill('解释数组');
  await input.press('Enter');
  await expect.poll(() => sent).toBe(true);
  await page.evaluate(() => { window.location.hash = 'ai?course_id=course-physics&scopeType=knowledge_point&scopeId=list'; });
  await expect(page.getByTestId('workspace-context-bar')).toContainText('链表');
  release?.();
  await expect(input).toBeEnabled();
  await expect(page.getByText('数组旧请求迟到结果', { exact: true })).toHaveCount(0);
});

test('home resume restores the scope sent to the shared chat entry', async ({ teacherPage: page }) => {
  await page.route('**/api/courses/*/knowledge-graph', route => route.fulfill({ json: graph }));
  let submitted: { scope_id?: string; scope_type?: string } | undefined;
  await page.route('**/api/chat/v2/stream', route => {
    submitted = route.request().postDataJSON();
    const payload = { message: { role: 'assistant', content: '正在生成数组报告' }, conversation: { conversation_id: 'resume-array' }, action: { name: 'generate.report' }, artifacts: [], sources: [], trace: { path: 'fast' } };
    return route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'result', payload })}\n\ndata: ${JSON.stringify({ type: 'done', payload: {} })}\n\n` });
  });
  await page.goto('/#ai?course_id=course-physics&scopeType=knowledge_point&scopeId=array');
  await expect(page.getByTestId('workspace-context-bar')).toContainText('数组', { timeout: 15000 });
  await page.evaluate(() => { window.location.hash = 'home'; });
  await page.locator('.resume-entry').getByRole('button', { name: '继续备课 →' }).click();
  await expect(page.getByTestId('workspace-context-bar')).toContainText('数组');
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await input.fill('为当前课程生成报告');
  await input.press('Enter');
  await expect.poll(() => submitted?.scope_id).toBe('array');
  expect(submitted?.scope_type).toBe('knowledge_point');
});

test('shared revision result reads history and restores with the current base version', async ({ teacherPage: page }) => {
  const reference = { artifact_id: 'report1', artifact_type: 'report', version_id: 'v2', source_course_id: 'course-physics', title: '数组报告' };
  await page.route('**/api/courses/*/knowledge-graph', route => route.fulfill({ json: graph }));
  await page.route('**/api/chat/v2/stream', route => {
    const payload = { message: { role: 'assistant', content: '已保存新版本' }, conversation: { conversation_id: 'revision-history' }, action: { name: 'artifact.revise' }, artifacts: [], sources: [], trace: { path: 'fast' },
      artifact_revision: { status: 'completed', message: '已保存新版本', artifact_reference: reference, summary: '增加例子', changes: [] } };
    return route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'result', payload })}\n\ndata: ${JSON.stringify({ type: 'done', payload: {} })}\n\n` });
  });
  await page.route('**/api/chat/v2/artifacts/revisions/read', route => route.fulfill({ json: { material_id: 'report1', material_type: 'report', course_id: 'course-physics', title: '数组报告', version: 1, content: '# 历史数组说明' } }));
  let restoreRequest: { version: number; reference: { version_id: string } } | undefined;
  await page.route('**/api/chat/v2/artifacts/revisions/restore', route => {
    restoreRequest = route.request().postDataJSON();
    return route.fulfill({ json: { status: 'completed', message: '已恢复', artifact_reference: { ...reference, version_id: 'v3' }, summary: '恢复第1版', changes: [] } });
  });
  await page.goto('/#ai?course_id=course-physics');
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await input.fill('修改数组报告'); await input.press('Enter');
  await page.getByRole('button', { name: '恢复旧版', exact: true }).click();
  await page.getByRole('button', { name: '查看此版本' }).click();
  await expect(page.getByRole('heading', { name: '历史数组说明' })).toBeVisible();
  await page.getByRole('button', { name: '恢复为新版本' }).click();
  await expect(page.getByRole('region', { name: '资料修改结果' })).toContainText('第 3 版');
  expect(restoreRequest?.version).toBe(1);
  expect(restoreRequest?.reference.version_id).toBe('v2');
});
