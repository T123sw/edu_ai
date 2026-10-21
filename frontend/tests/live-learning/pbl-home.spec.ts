import { test, expect, type Page } from 'playwright/test';
import { mkdir } from 'node:fs/promises';
const evidence = '../docs/acceptance/2026-10-14-unified-practice-home';
async function setup(page: Page, failProjects = false) {
  const projects = [{ exerciseId: 'pbl_saved', topic: '已保存的快速排序项目', status: 'ready', jobId: 'job_saved' }];
  const posts: { path: string; topic: string }[] = [];
  let fail = failProjects;
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'unified_fixture', role: 'student' } })));
  await page.route('**/api/**', async route => {
    const req = route.request(), path = new URL(req.url()).pathname.replace(/^\/backend/, '');
    if (!path.startsWith('/api/')) return route.continue();
    if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'unified_fixture', role: 'student' } } });
    if (path.endsWith('/self-learning/state')) return route.fulfill({ json: { version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: [] } });
    if (['/api/practice', '/api/pbl'].includes(path) && req.method() === 'POST') {
      posts.push({ path, topic: req.postDataJSON().topic });
      if (path === '/api/pbl') {
        projects.unshift({ exerciseId: 'pbl_created', topic: req.postDataJSON().topic, status: 'queued', jobId: 'job_created' });
        return route.fulfill({ json: { exerciseId: 'pbl_created', jobId: 'job_created', status: 'queued' } });
      }
      return route.fulfill({ json: { id: 'lab_created' } });
    }
    if (path === '/api/practice') return route.fulfill({ json: { items: [{ id: 'lab_saved', topic: '已保存的摩擦力实验', status: 'succeeded' }] } });
    if (path === '/api/pbl') return fail ? route.fulfill({ status: 503, json: { detail: '暂时不可用' } }) : route.fulfill({ json: { items: projects } });
    if (path.startsWith('/api/pbl/')) return route.fulfill({ json: { exerciseId: path.split('/').pop(), job: { status: 'queued' }, artifact: null } });
    if (path === '/api/practice/lab_created') return route.fulfill({ json: { id: 'lab_created', job: { status: 'queued' }, artifact: null } });
    return route.fulfill({ json: { items: [] } });
  });
  return { posts, recover: () => { fail = false; } };
}
for (const width of [1440, 390]) test(`统一入口切换、两类服务端列表和创建恢复 (${width})`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 });
  const fixture = await setup(page);
  await page.goto('/#/practice');
  const input = page.getByLabel('实验主题与目标');
  await input.fill('快速排序');
  await input.evaluate(el => el.setAttribute('data-preserved-input', 'yes'));
  const mode = page.getByRole('combobox', { name: '实践方式', exact: true });
  await mode.click(); await page.getByRole('option', { name: '编程练习（PBL）' }).click();
  await expect(page).toHaveURL(/#\/practice$/);
  await expect(input).toHaveValue('快速排序');
  await expect(input).toHaveAttribute('data-preserved-input', 'yes');
  await expect(page.getByRole('combobox', { name: '实验侧重' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: '把思路写成代码' })).toHaveCount(0);
  const labs = page.getByRole('region', { name: '我的实验', exact: true });
  const projects = page.getByRole('region', { name: '我的项目', exact: true });
  await expect(labs.getByRole('heading', { name: '已保存的摩擦力实验' })).toBeVisible();
  await expect(projects.getByRole('heading', { name: '已保存的快速排序项目' })).toBeVisible();
  expect((await projects.boundingBox())!.y).toBeGreaterThan((await labs.boundingBox())!.y);
  expect(fixture.posts).toHaveLength(0);
  await mkdir(evidence, { recursive: true });
  await page.screenshot({ path: `${evidence}/home-${width}.png`, fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: '生成项目', exact: true }).click();
  await expect(page).toHaveURL(/#\/practice$/);
  await expect(page.getByRole('dialog', { name: '编程项目准备' })).toBeVisible();
  expect(fixture.posts).toEqual([{ path: '/api/pbl', topic: '快速排序' }]);
  await page.getByRole('button', { name: '先去浏览' }).click();
  await expect(projects.getByRole('heading', { name: '快速排序', exact: true })).toBeVisible();
  await page.reload();
  await expect(projects.getByRole('heading', { name: '快速排序', exact: true })).toBeVisible();
  await projects.getByRole('button', { name: /搜索项目/ }).click();
  await projects.getByRole('textbox', { name: '搜索项目' }).fill('已保存');
  await expect(projects.getByRole('heading', { name: '快速排序', exact: true })).toHaveCount(0);
  await expect(labs.getByRole('heading', { name: '已保存的摩擦力实验' })).toBeVisible();
  await projects.getByRole('button', { name: /已保存的快速排序项目/ }).click();
  await expect(page).toHaveURL(/#\/practice\/code\/pbl_saved$/);
  // The previous programming-home URL remains compatible with the same shared page.
  await page.goto('/#/practice/code');
  await expect(page.getByRole('button', { name: '生成项目', exact: true })).toBeVisible();
  await input.fill('摩擦力');
  await mode.click(); await page.getByRole('option', { name: '模拟实验' }).click();
  await expect(page).toHaveURL(/#\/practice\/code$/);
  await expect(input).toHaveValue('摩擦力');
  await page.getByRole('button', { name: '生成互动实验', exact: true }).click();
  await expect(page).toHaveURL(/#\/practice\/code$/);
  await expect(page.getByRole('dialog', { name: '模拟实验准备' })).toBeVisible();
  expect(fixture.posts.at(-1)).toEqual({ path: '/api/practice', topic: '摩擦力' });
});
test('项目列表读取失败独立重试，不影响模拟实验和输入', async ({ page }) => {
  const fixture = await setup(page, true);
  await page.goto('/#/practice');
  await page.getByLabel('实验主题与目标').fill('保留这个主题');
  const projects = page.getByRole('region', { name: '我的项目', exact: true });
  await expect(projects).toContainText('暂时无法读取项目');
  await expect(page.getByRole('heading', { name: '已保存的摩擦力实验' })).toBeVisible();
  fixture.recover(); await projects.getByRole('button', { name: '重新加载' }).click();
  await expect(projects.getByRole('heading', { name: '已保存的快速排序项目' })).toBeVisible();
  await expect(page.getByLabel('实验主题与目标')).toHaveValue('保留这个主题');
});
