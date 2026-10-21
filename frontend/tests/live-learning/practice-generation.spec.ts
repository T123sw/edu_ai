import { test, expect, type Page } from 'playwright/test';

async function fixture(page: Page, code: boolean, newRetryId = false) {
  const base = code ? '/api/pbl' : '/api/practice';
  const state = { status: 'running', ready: false, disconnected: false, posts: 0, controls: [] as string[], retried: false, retryReads: 0 };
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'animation', role: 'student' } })));
  const job = () => ({ edu_job_id: state.retried ? 'job-retried' : 'job-animation', status: state.status, message: '正在设计探索内容', input_summary: { topic: '动画测试' }, cancelable: state.status === 'running', retryable: state.status === 'failed', error_message: state.status === 'failed' ? '本次生成失败，请重试。' : '' });
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/^\/backend/, '');
    if (!path.startsWith('/api/')) return route.continue();
    if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'animation', role: 'student' } } });
    if (path.endsWith('/self-learning/state')) return route.fulfill({ json: { version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: [] } });
    if (path === base && route.request().method() === 'POST') {
      state.posts++;
      return route.fulfill({ json: { id: 'animation', exerciseId: 'animation' } });
    }
    if (path === base) return route.fulfill({ json: { items: state.posts ? [{ id: 'animation', exerciseId: 'animation', topic: '动画测试', status: state.status }] : [] } });
    if (code && path === `${base}/job-retried`) { state.retryReads++; return route.fulfill({status:404,json:{detail:'exercise not found'}}); }
    if (path === `${base}/animation` || path === `${base}/job-retried`) {
      if (path.endsWith('/job-retried')) state.retryReads++;
      if (state.disconnected) return route.fulfill({ status: 503, json: { detail: '连接中断' } });
      return route.fulfill({ json: { id: 'animation', exerciseId: 'animation', job: job(), artifact: state.ready ? { html: '<p>实验已就绪</p>', plan: { concept_name: '动画测试实验', steps: [] } } : null, journal: { observations: [], messages: [] } } });
    }
    if (path.startsWith('/api/jobs/job-animation/')) {
      const action = path.split('/').at(-1)!;
      state.controls.push(action); state.status = action === 'cancel' ? 'canceled' : 'running';
      if (action === 'retry' && newRetryId) state.retried = true;
      return route.fulfill({ json: job() });
    }
    return route.fulfill({ json: { items: [] } });
  });
  return state;
}

for (const code of [false, true]) test(`retry follows the new server job (${code ? 'PBL' : 'simulation'})`, async ({ page }) => {
  const state = await fixture(page, code, true);
  state.status = 'failed';
  await page.goto(`/#/practice/${code ? 'code/' : ''}animation`);
  await page.getByRole('button', { name: '重试生成', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`#/practice/${code ? 'code/animation' : 'job-retried'}$`));
  if (!code) await expect.poll(() => state.retryReads).toBeGreaterThan(0);
  await expect(page.getByRole('button', { name: '取消生成', exact: true })).toBeVisible();
  expect(state.controls).toEqual(['retry']);
  if (code) { await page.reload(); await expect(page.getByRole('button', {name:'取消生成',exact:true})).toBeVisible(); expect(state.retryReads).toBe(0); }
});

for (const code of [false, true]) for (const width of [1440, 390]) {
  test(`animation stays on home, closes and resumes (${code ? 'PBL' : 'simulation'}, ${width})`, async ({ page }) => {
    await page.setViewportSize({ width, height: 850 });
    const state = await fixture(page, code);
    const path = code ? '/practice/code' : '/practice';
    await page.goto(`/#${path}`);
    await page.getByLabel('实验主题与目标').fill('动画测试');
    await page.getByRole('button', { name: code ? '生成项目' : '生成互动实验', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: code ? '编程项目准备' : '模拟实验准备' });
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('.sl-prep-sheet')).toHaveCount(2);
    await expect(dialog.getByRole('button', { name: '取消生成', exact: true })).toBeVisible();
    expect(await dialog.locator('.sheet-front').evaluate(el => getComputedStyle(el).animationName)).toBe('prep-float');
    expect(new URL(page.url()).hash).toBe(`#${path}`);
    await expect(page.locator('.practice-progress,.pbl-generating')).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const box = (await dialog.boundingBox())!;
    expect(box.x).toBeGreaterThanOrEqual(0); expect(box.y + box.height).toBeLessThanOrEqual(850);
    await page.screenshot({ path: `test-results/generation-${code ? 'pbl' : 'simulation'}-${width}.png` });
    await page.getByRole('button', { name: '先去浏览' }).click();
    await expect(dialog).toHaveCount(0);
    expect(state.controls).toEqual([]);
    await expect(page.getByLabel('实验主题与目标')).toHaveValue('动画测试');
    await page.reload();
    const section = page.getByRole('region', { name: code ? '我的项目' : '我的实验', exact: true });
    await section.getByRole('button', { name: /动画测试/ }).click();
    await expect(dialog).toBeVisible();
    state.disconnected = true;
    await expect(dialog.getByRole('alert')).toContainText('重新连接');
    state.disconnected = false; state.status = 'failed';
    await expect(dialog.getByRole('button', { name: '重试生成' })).toBeVisible();
    await dialog.getByRole('button', { name: '重试生成' }).click();
    await expect(dialog.getByRole('button', { name: '取消生成', exact: true })).toBeVisible();
    await dialog.getByRole('button', { name: '取消生成', exact: true }).click();
    await dialog.getByRole('button', { name: '确认取消' }).click();
    await expect(dialog.getByRole('heading', { name: '已取消生成' })).toBeVisible();
    expect(state.controls).toEqual(['retry', 'cancel']);
    state.status = 'succeeded'; state.ready = true;
    await expect(dialog.getByRole('button', { name: code ? '进入项目' : '进入实验' })).toBeVisible();
    expect(new URL(page.url()).hash).toBe(`#${path}`);
    expect(state.posts).toBe(1);
  });
}

for (const code of [false, true]) test(`direct pending link uses modal and reduced motion (${code})`, async ({ page }) => {
  await fixture(page, code);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto(`/#/practice/${code ? 'code/' : ''}animation`);
  const dialog = page.getByRole('dialog', { name: code ? '编程项目准备' : '模拟实验准备' });
  await expect(dialog).toBeVisible();
  expect(await dialog.locator('.sheet-front').evaluate(el => getComputedStyle(el).animationName)).toBe('none');
  await expect(page.locator('.sl-home')).toHaveCount(1);
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(page.getByLabel('实验主题与目标')).toBeVisible();
});
