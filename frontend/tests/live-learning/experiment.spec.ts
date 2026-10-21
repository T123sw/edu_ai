import { test, expect } from 'playwright/test';
import fs from 'node:fs';
import type { View } from '../../src/practice/experiment/model';
for (const width of [1440, 390]) test(`legacy experiment with two stages and frozen question (${width})`, async ({ page }) => {
  const artifact = JSON.parse(fs.readFileSync('../.runtime/experiment-fixtures/quicksort.json', 'utf8'));
  let saved: { view: View } | null = null; let frozen: { view: View; question: string } | null = null;
  await page.setViewportSize({ width, height: 1000 });
  await page.addInitScript(() => { if (window === window.top) localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'test', user: { username: 'alice', role: 'student' } })); });
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'alice', role: 'student' } } });
    if (path.endsWith('/self-learning/state')) return route.fulfill({ json: { version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: [] } });
    if (path.endsWith('/experiment/runs/latest')) return route.fulfill({ json: saved });
    if (path.endsWith('/experiment/runs')) { const request = route.request().postDataJSON(); if (request.expected_seq !== (saved?.view.seq ?? -1) && request.view.seq !== saved?.view.seq) return route.fulfill({ status: 409, json: { detail: '保存冲突' } }); saved = { view: request.view }; return route.fulfill({ json: saved }); }
    if (path.endsWith('/experiment/tutor') && route.request().method() === 'GET') return route.fulfill({ json: { items: [], next_cursor: null } });
    if (path.endsWith('/experiment/tutor')) {
      const request = route.request().postDataJSON(); frozen = request;
      const turn = { request_id: request.request_id, question: request.question, reply_to: null, revision: request.view.revision, run_id: request.view.run_id, state_revision: request.view.seq, focus_label: '刚才的操作', answer: '已结合刚才的操作回答。', status: 'complete', error: '' };
      return route.fulfill({ contentType: 'text/event-stream', body: [ { type: 'accepted', turn: { ...turn, answer: '', status: 'pending' } }, { type: 'delta', text: turn.answer }, { type: 'done', turn } ].map(event => 'data: ' + JSON.stringify(event) + '\n\n').join('') });
    }
    if (path.endsWith('/practice/experiment')) return route.fulfill({ json: { id: 'experiment', job: { status: 'succeeded' }, artifact, journal: { observations: [], messages: [] } } });
    return route.fulfill({ json: { items: [] } });
  });
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/#/practice/experiment');
  const stage = page.frameLocator('iframe[title="实验展示"]');
  await expect(stage.locator('canvas')).toBeVisible();
  await expect(page.locator('.experiment-action')).toHaveCount(0);
  await stage.locator('canvas').click({ position: { x: 40, y: 200 } });
  await expect(stage.locator('#state')).toContainText('"selected":-1');
  await page.getByRole('button', { name: '下一步', exact: true }).click();
  await expect(stage.locator('#state')).toContainText('"selected":4');
  if (width > 760) {
    const left = (await page.locator('.experiment-steps').boundingBox())!, center = (await page.locator('.experiment-center').boundingBox())!, right = (await page.locator('.experiment-teaching').boundingBox())!;
    expect(left.x + left.width).toBeLessThanOrEqual(center.x + 1); expect(center.x + center.width).toBeLessThanOrEqual(right.x + 1); expect(right.width).toBeGreaterThan(300);
  }
  await page.getByRole('button', { name: '进入自由探索' }).click();
  await expect(page.getByRole('button', { name: '下一步', exact: true })).toHaveCount(0);
  const index = page.getByLabel('元素位置（从 0 开始）'); await index.fill('2');
  await page.getByRole('button', { name: '执行操作', exact: true }).click();
  await expect(stage.locator('#state')).toContainText('"selected":2');
  if (width <= 760) await page.locator('.experiment-mobile').getByRole('button', { name: 'AI 对话', exact: true }).click();
  await page.getByLabel('实验问题或回答').fill('这个基准会影响什么？'); await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByRole('button', { name: '回答或继续问', exact: true })).toBeVisible();
  await expect.poll(() => saved?.view.seq).toBe(frozen!.view.seq); expect(saved!.view.events.some(e => e.phase === 'guided')).toBe(false);
  if (width <= 760) await page.locator('.experiment-mobile').getByRole('button', { name: '实验', exact: true }).click();
  await expect(page.getByRole('heading', { name: '自由探索', exact: true })).toBeVisible();
  await index.fill('1'); await page.getByRole('button', { name: '执行操作', exact: true }).click();
  await expect(stage.locator('#state')).toContainText('"selected":1');
  await expect.poll(() => saved?.view.state.selected).toBe(1);
  await page.screenshot({ path: `../.runtime/experiment-two-stage/legacy-explore-${width}.png`, fullPage: true });
  await page.reload(); await expect(stage.locator('#state')).toContainText('"selected":1');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true); expect(errors).toEqual([]);
  await page.evaluate(() => { const key = Object.keys(localStorage).find(k => k.startsWith('edu-experiment:') && ![':question', ':outbox', ':reply'].some(suffix => k.endsWith(suffix)))!; const draft = JSON.parse(localStorage.getItem(key)!); draft.events[0].id = 'different-local-history'; localStorage.setItem(key, JSON.stringify(draft)); });
  await page.reload(); await expect(page.getByRole('alert')).toContainText('本地与服务器记录发生冲突');
  await expect(page.locator('iframe[title="实验展示"]')).toHaveCount(0);
});
