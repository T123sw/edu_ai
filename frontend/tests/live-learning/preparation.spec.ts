import { test, expect } from 'playwright/test';

test('retry and refresh keep request identity; entry requires committed result', async ({ page }) => {
  const ids: string[] = []; let accepted = false; let ready = false;
  const task = () => ({ preparation_id: 'prep-test', status: ready ? 'succeeded' : 'running', stage: ready ? 'commit' : 'research_scope', revision: 2,
    result_ref: ready ? { course_ready: true, course_id: 'course-test' } : null });
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'test', user: { username: 'alice', role: 'student' } })));
  await page.route('**/api/**', async route => {
    const req = route.request(); const path = new URL(req.url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'alice', role: 'student' } } });
    if (path.endsWith('/self-learning/state')) return route.fulfill({ json: { version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: [] } });
    if (path === '/api/course-preparations' && req.method() === 'POST') {
      ids.push(req.postDataJSON().request_id); accepted = true;
      return route.fulfill({ status: ids.length === 1 ? 503 : 202, json: ids.length === 1 ? { detail: '响应丢失，请重试' } : task() });
    }
    if (path === '/api/course-preparations') return route.fulfill({ json: { preparations: accepted ? [task()] : [] } });
    if (path.endsWith('/intermediates')) return route.fulfill({ json: { plan: { title: 'Agent 面试学习路径', nodes: [] } } });
    return route.fulfill({ status: 404, json: { detail: 'unexpected route' } });
  });
  await page.goto('/?liveLearning=1');
  await page.getByLabel('学习知识点与目标').fill('学习 AI Agent，准备开发岗位面试');
  await page.getByRole('button', { name: '开始学习' }).click();
  await expect(page.getByRole('alert')).toContainText('响应丢失');
  await page.reload();
  await page.getByLabel('学习知识点与目标').fill('学习 AI Agent，准备开发岗位面试');
  await page.getByRole('button', { name: '开始学习' }).click();
  await expect.poll(() => ids.length).toBe(2);
  expect(ids[0]).toBe(ids[1]);
  await expect(page.getByRole('link', { name: '进入学习' })).toHaveCount(0);
  await page.getByRole('button', { name: '查看资料汇总与路径' }).click();
  await expect(page.getByText(/Agent 面试学习路径/)).toBeVisible();
  ready = true;
  await expect(page.getByRole('link', { name: '进入学习' })).toHaveAttribute('href', '#/classroom/course-test');
  expect(page.url()).not.toContain('/classroom/');
});


for (const initial of ['running', 'failed']) {
  test(`background ${initial} task remains controllable after refresh`, async ({ page }) => {
    let status = initial; const controls: string[] = [];
    const task = () => ({ preparation_id: 'control-task', status, stage: 'research_scope', revision: 4, error_code: status === 'failed' ? 'MODEL_UNAVAILABLE' : null, result_ref: null });
    await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'test', user: { username: 'alice', role: 'student' } })));
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname;
      if (!path.startsWith('/api/')) return route.continue();
      if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'alice', role: 'student' } } });
      if (path.endsWith('/self-learning/state')) return route.fulfill({ json: { version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: [] } });
      if (path === '/api/course-preparations') return route.fulfill({ json: { preparations: [task()] } });
      if (/control-task\/(cancel|retry)$/.test(path)) {
        const action = path.split('/').at(-1)!; controls.push(action);
        if (action === 'cancel') expect(route.request().postDataJSON().expected_revision).toBe(4);
        status = action === 'cancel' ? 'canceled' : 'running';
        return route.fulfill({ json: task() });
      }
      return route.fulfill({ json: { items: [] } });
    });
    await page.goto('/'); await page.reload();
    await page.getByRole('button', { name: initial === 'failed' ? '继续重试' : '取消任务' }).click();
    await expect.poll(() => controls).toEqual([initial === 'failed' ? 'retry' : 'cancel']);
    await page.reload();
    await expect(page.getByRole('link', { name: '进入学习' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '取消任务' })).toHaveCount(initial === 'failed' ? 1 : 0);
    expect(page.url()).not.toContain('/classroom/');
  });
}


test('creation waits for the selected upload and includes its immutable reference', async ({ page }) => {
  let release: () => void = () => {}; const gate = new Promise<void>(resolve => { release = resolve; });
  const requests: any[] = [];
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'test', user: { username: 'alice', role: 'student' } })));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'alice', role: 'student' } } });
    if (path.endsWith('/self-learning/state')) return route.fulfill({ json: { version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: [] } });
    if (path.endsWith('/course-preparations/uploads')) {
      await gate;
      return route.fulfill({ json: { document_id: 'uploaded-interview', version: 1 } });
    }
    if (path === '/api/course-preparations' && route.request().method() === 'POST') {
      requests.push(route.request().postDataJSON());
      return route.fulfill({ status: 202, json: { preparation_id: 'upload-task', status: 'accepted', stage: 'normalize', revision: 1 } });
    }
    return route.fulfill({ json: { preparations: [], items: [] } });
  });
  await page.goto('/');
  await page.getByLabel('学习知识点与目标').fill('只根据上传资料学习 Agent');
  await page.getByLabel('添加资料').setInputFiles({ name: 'agent.md', mimeType: 'text/markdown', buffer: Buffer.from('# Agent interview') });
  await expect(page.getByText('正在上传…')).toBeVisible();
  await page.getByRole('button', { name: '开始学习' }).click();
  await expect(page.getByRole('alert')).toContainText('资料仍在上传');
  expect(requests).toHaveLength(0);
  release();
  await expect(page.getByRole('button', { name: '移除 agent.md' })).toBeVisible();
  await expect(page.getByLabel('资料 1 用途')).toHaveCount(0);
  await expect(page.getByLabel('资料范围')).toHaveCount(0);
  await page.getByRole('button', { name: '开始学习' }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].uploads).toEqual([{ document_id: 'uploaded-interview', version: 1 }]);
  expect(requests[0].source_policy).toBeUndefined();
  expect(requests[0].overrides.total_minutes).toBeUndefined();
});

test('files alone require no classification; optional settings and understood intent are visible', async ({ page }) => {
  const requests: any[] = []; let uploads = 0;
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'test', user: { username: 'alice', role: 'student' } })));
  await page.route('**/api/**', async route => {
    const req = route.request(); const path = new URL(req.url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'alice', role: 'student' } } });
    if (path.endsWith('/self-learning/state')) return route.fulfill({ json: { version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: [] } });
    if (path.endsWith('/uploads')) return route.fulfill({ json: { document_id: `doc-${++uploads}`, version: 1 } });
    const task = { preparation_id: 'intake', status: 'running', stage: 'research_scope', revision: 3 };
    if (path === '/api/course-preparations' && req.method() === 'POST') { requests.push(req.postDataJSON()); return route.fulfill({ status: 202, json: task }); }
    if (path === '/api/course-preparations') return route.fulfill({ json: { preparations: requests.length ? [task] : [] } });
    if (path.endsWith('/intermediates')) return route.fulfill({ json: { brief: { topic: 'Agent', learning_goal: '准备 Agent 面试', prior_knowledge: '会 Python', total_minutes: 120, language: '中文', assumptions: ['根据岗位要求推断目标'] }, input_documents: [{ document_id: 'doc-1', filename: 'job.md', complete: true, parts: [{ kind: 'job_description', summary: '岗位要求掌握工具调用与评估' }] }] } });
    return route.fulfill({ json: { items: [] } });
  });
  await page.goto('/');
  await expect(page.getByRole('button', { name: '开始学习' })).toBeDisabled();
  await page.getByLabel('添加资料').setInputFiles([
    { name: 'job.md', mimeType: 'text/markdown', buffer: Buffer.from('岗位要求') },
    { name: 'background.txt', mimeType: 'text/plain', buffer: Buffer.from('会 Python') },
  ]);
  await expect(page.getByRole('button', { name: '移除 background.txt' })).toBeVisible();
  await page.getByText('补充安排（可选）', { exact: true }).click();
  await expect(page.getByLabel('学习时长（分钟）')).toHaveValue('');
  await page.getByLabel('学习时长（分钟）').fill('120');
  await page.getByLabel('输出语言').fill('中文');
  await page.getByLabel('学习深度').selectOption('intermediate');
  await page.getByRole('button', { name: '开始学习' }).click();
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].uploads).toEqual([{ document_id: 'doc-1', version: 1 }, { document_id: 'doc-2', version: 1 }]);
  expect(requests[0].overrides).toEqual({ total_minutes: 120, language: '中文', depth: 'intermediate' });
  expect(requests[0].goal).toContain('推断学习目标');
  await page.getByRole('button', { name: '查看资料汇总与路径' }).click();
  await expect(page.getByRole('region', { name: '需求理解' })).toContainText('准备 Agent 面试');
  await expect(page.getByText('岗位要求掌握工具调用与评估')).toBeVisible();
});
