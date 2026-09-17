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
