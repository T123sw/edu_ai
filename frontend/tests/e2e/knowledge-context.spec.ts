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

test('recognized topic updates scope without clearing conversation or opening adjustment', async ({ teacherPage: page }) => {
  await page.route('**/api/courses/*/knowledge-graph', route => route.fulfill({ json: graph }));
  const requests: Array<{ conversation_id?: string; scope_id?: string; allow_rag?: boolean }> = [];
  await page.route('**/api/chat/v2/stream', route => {
    requests.push(route.request().postDataJSON());
    const payload = { message: { role: 'assistant', content: requests.length === 1 ? '数组使用连续内存存储元素。' : '可以用下标访问演示。' },
      conversation: { conversation_id: 'auto-topic-conv' }, action: { name: 'chat.reply' }, artifacts: [], sources: [], trace: { path: 'deepseek-harness' },
      workspace_context: { course_id: 'course-physics', course_title: '数据结构', scope_type: 'knowledge_point', scope_id: 'array', scope_title: '数组', scope_path: ['数据结构', '数组'], resolution: 'resolved', explicit_course: false, update_workspace: requests.length === 1 } };
    return route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'result', payload })}\n\ndata: ${JSON.stringify({ type: 'done', payload: {} })}\n\n` });
  });
  await page.goto('/#ai?course_id=course-physics');
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await input.fill('数组如何实现？');
  await input.press('Enter');
  await expect(page).toHaveURL(/scopeId=array/);
  await expect(page.getByTestId('workspace-context-bar')).toContainText('数组');
  await expect(page.getByText('数组使用连续内存存储元素。', { exact: true })).toBeVisible();
  await expect(page.getByRole('combobox', { name: '选择备课知识点' })).not.toBeVisible();
  await input.fill('怎样给学生演示？');
  await input.press('Enter');
  await expect(page.getByText('可以用下标访问演示。', { exact: true })).toBeVisible();
  expect(requests[1].conversation_id).toBe('auto-topic-conv');
  expect(requests[1].scope_id).toBe('array');
  expect(requests[1].allow_rag).toBe(requests[0].allow_rag);
  await expect(page.getByText('数组使用连续内存存储元素。', { exact: true })).toBeVisible();
});

test('submitted job uses final user-facing message instead of streamed internal identifiers', async ({ teacherPage: page }) => {
  await page.route('**/api/courses/*/knowledge-graph', route => route.fulfill({ json: graph }));
  await page.route('**/api/chat/v2/stream', route => {
    const payload = { message: { role: 'assistant', content: '正在生成报告，完成后会在这里显示。' },
      conversation: { conversation_id: 'progress-conv' }, action: { name: 'generate.report' }, artifacts: [], sources: [],
      task_id: 'job_private_123', trace: { path: 'deepseek-harness' } };
    const events = [
      { type: 'metadata', payload: { conversation_id: 'progress-conv' } },
      { type: 'task_submitted', payload: { task_id: 'job_private_123', workflow_type: 'report' } },
      { type: 'delta', payload: { content: '大纲 outline_private_456，任务 job_private_123，状态 submitted' } },
      { type: 'result', payload }, { type: 'done', payload: {} },
    ];
    return route.fulfill({ contentType: 'text/event-stream', body: events.map(e => `data: ${JSON.stringify(e)}\n\n`).join('') });
  });
  await page.goto('/#ai?course_id=course-physics');
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await input.fill('可以');
  await input.press('Enter');
  await expect(page.getByText('正在生成报告，完成后会在这里显示。', { exact: true })).toBeVisible();
  await expect(page.locator('.chat-panel__bubble').filter({ hasText: /outline_private|job_private|submitted/ })).toHaveCount(0);
  await expect(input).toBeEnabled();
});

test('outline uses saved content and ordinary dialogue typography', async ({ teacherPage: page }, testInfo) => {
  await page.route('**/api/courses/*/knowledge-graph', route => route.fulfill({ json: graph }));
  let turn = 0;
  const outline = '链表报告大纲\n\n## 1. 节点结构\n### 1.1 数据域\n#### 1.1.1 元素类型\n### 1.2 指针域\n\n请确认是否按此结构继续。';
  await page.route('**/api/chat/v2/stream', route => {
    turn++;
    const payload = { message: { role: 'assistant', content: turn === 1 ? outline : '正在生成报告，完成后会在这里显示。' },
      conversation: { conversation_id: 'outline-consistency' }, action: { name: 'generate.report' }, artifacts: [], sources: [],
      trace: { path: 'deepseek-harness' } };
    const events = turn === 1 ? [
      { type: 'tool_call', payload: { tool: 'draft_report_outline', call_id: 'outline-call', args: {} } },
      { type: 'delta', payload: { content: '# 模型另写的大纲\n## 不同章节' } },
      { type: 'result', payload }, { type: 'done', payload: {} },
    ] : [{ type: 'result', payload }, { type: 'done', payload: {} }];
    return route.fulfill({ contentType: 'text/event-stream', body: events.map(e => `data: ${JSON.stringify(e)}\n\n`).join('') });
  });
  await page.goto('/#ai?course_id=course-physics');
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await input.fill('生成链表报告'); await input.press('Enter');
  const chapter = page.getByRole('heading', { name: '1. 节点结构', exact: true });
  await expect(chapter).toBeVisible();
  await expect(page.getByText('模型另写的大纲')).toHaveCount(0);
  const styles = await chapter.evaluate(el => {
    const paragraph = el.parentElement!.querySelector('p')!;
    const a = getComputedStyle(el), b = getComputedStyle(paragraph);
    return { heading: [a.fontFamily, a.fontSize, a.fontWeight], paragraph: [b.fontFamily, b.fontSize, b.fontWeight] };
  });
  expect(styles.heading).toEqual(styles.paragraph);
  const section = page.getByRole('heading', { name: '1.1 数据域', exact: true });
  const detail = page.getByRole('heading', { name: '1.1.1 元素类型', exact: true });
  const chapterBox = (await chapter.boundingBox())!;
  const sectionBox = (await section.boundingBox())!;
  const detailBox = (await detail.boundingBox())!;
  expect(sectionBox.x - chapterBox.x).toBeGreaterThanOrEqual(20);
  expect(detailBox.x - sectionBox.x).toBeGreaterThanOrEqual(20);
  await page.screenshot({ path: testInfo.outputPath('outline-indent-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  const mobileChapter = (await chapter.boundingBox())!;
  const mobileSection = (await section.boundingBox())!;
  expect(mobileSection.x - mobileChapter.x).toBeGreaterThanOrEqual(20);
  await page.screenshot({ path: testInfo.outputPath('outline-indent-mobile.png') });
  await page.setViewportSize({ width: 1366, height: 768 });
  await input.fill('可以'); await input.press('Enter');
  await expect(page.getByText('正在生成报告，完成后会在这里显示。', { exact: true })).toBeVisible();
  await expect(chapter).toBeVisible();
  await expect(page.getByRole('heading', { name: '1.1 数据域', exact: true })).toBeVisible();
});

test('result-only report task updates the conversation when the job completes', async ({ teacherPage: page }) => {
  await page.route('**/api/courses/*/knowledge-graph', route => route.fulfill({ json: graph }));
  let submitted = false;
  const job = { schema_version: 1, version: 2, edu_job_id: 'job_sync', kind: 'generate_report', status: 'succeeded',
    step: 'completed', progress: 100, message: '已完成', owner_user_id: 'teacher-a', course_id: 'course-physics',
    scope_type: 'course', input_summary: {}, retryable: false, cancelable: false,
    created_at: new Date().toISOString(), updated_at: new Date().toISOString() };
  await page.route('**/api/jobs**', route => route.fulfill({ json: route.request().url().includes('/api/jobs/job_sync') ? job : {
    items: submitted ? [job] : [], next_cursor: null, server_time: new Date().toISOString() } }));
  let resultPolls = 0;
  await page.route('**/api/chat/tasks/job_sync', route => route.fulfill({ json: ++resultPolls === 1 ? { task_id: 'job_sync', status: 'running' } : {
    task_id: 'job_sync', status: 'succeeded', result: { message: { role: 'assistant', content: '报告已完成，可查看资料。' },
      conversation: { conversation_id: 'task-sync-conv' }, artifacts: [], sources: [] } } }));
  await page.route('**/api/chat/v2/stream', route => {
    submitted = true;
    const payload = { message: { role: 'assistant', content: '正在生成报告，完成后会在这里显示。' },
      conversation: { conversation_id: 'task-sync-conv' }, task_id: 'job_sync', workflow: { type: 'report', status: 'running' },
      action: { name: 'generate.report' }, artifacts: [], sources: [], trace: { path: 'deepseek-harness' } };
    return route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'result', payload })}\n\ndata: ${JSON.stringify({ type: 'done', payload: {} })}\n\n` });
  });
  await page.goto('/#ai?course_id=course-physics');
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await input.fill('可以'); await input.press('Enter');
  await expect(page.getByText('报告已完成，可查看资料。', { exact: true })).toBeVisible({ timeout: 20000 });
  await expect(page.getByText('正在生成报告，完成后会在这里显示。', { exact: true })).toHaveCount(0);
});

test('report readback keeps its explanation through final delivery and a follow-up', async ({ teacherPage: page }) => {
  await page.route('**/api/courses/*/knowledge-graph', route => route.fulfill({ json: graph }));
  const answer = '报告已经完成。文档中的链表节点包含数据域和指针域，插入时先连接后继节点。';
  const followUp = '继续刚才的插入操作：先让新节点指向后继，再让前驱指向新节点。';
  const requests: Array<{ conversation_id?: string }> = [];
  let taskPolls = 0;
  await page.route('**/api/chat/tasks/**', route => { taskPolls++; return route.fulfill({ json: {} }); });
  await page.route('**/api/chat/v2/stream', route => {
    requests.push(route.request().postDataJSON());
    const content = requests.length === 1 ? answer : followUp;
    const payload = { message: { role: 'assistant', content }, conversation: { conversation_id: 'read-existing-report' },
      action: { name: 'chat.reply' }, workflow: null, verification: { decision: 'pass' },
      artifacts: [{ artifact_id: 'existing-linked-list-report', artifact_type: 'report', title: '链表的实现', content: '# 链表的实现\n\n这是已经存在的报告正文。' }],
      sources: [], trace: { path: 'deepseek-harness' } };
    const events = [
      { type: 'tool_call', payload: { tool: 'query_report_job', call_id: 'read-only', args: { task_id: 'existing-job' } } },
      { type: 'delta', payload: { content } },
      { type: 'result', payload }, { type: 'done', payload: {} },
    ];
    return route.fulfill({ contentType: 'text/event-stream', body: events.map(e => `data: ${JSON.stringify(e)}\n\n`).join('') });
  });
  await page.goto('/#ai?course_id=course-physics');
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await input.fill('现在完成了吗，文档写了什么？'); await input.press('Enter');
  await expect(page.getByText(answer, { exact: true })).toBeVisible();
  await input.fill('继续解释插入操作'); await input.press('Enter');
  await expect(page.getByText(followUp, { exact: true })).toBeVisible();
  await expect(page.getByText(answer, { exact: true })).toBeVisible();
  await expect(page.getByText('生成完成，已保存到“我的资源”，仅你可见。', { exact: true })).toHaveCount(0);
  expect(requests[1].conversation_id).toBe('read-existing-report');
  expect(taskPolls).toBe(0);
});
