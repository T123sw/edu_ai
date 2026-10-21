import { test, expect } from 'playwright/test';
import fs from 'node:fs';
import type { View } from '../../src/practice/experiment/model';
for (const width of [1440, 390]) test(`real generated bubble demonstration and exploration (${width})`, async ({ page }) => {
  test.skip(!fs.existsSync('../.runtime/experiment-pages-check/isolated-bubble.json'), '可选真实模型验收样本尚未生成');
  const artifact = JSON.parse(fs.readFileSync('../.runtime/experiment-pages-check/isolated-bubble.json', 'utf8'));
  let saved: { view: View } | null = null; let frozen: { view: View; question: string } | null = null;
  await page.setViewportSize({ width, height: 1000 });
  await page.addInitScript(() => { if (window === window.top) localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'test', user: { username: 'alice', role: 'student' } })); });
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.startsWith('/src/')) return route.continue();
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
  await expect(page.getByRole('button', { name: '下一步', exact: true })).toBeEnabled();
  for (const _ of artifact.experiment.spec.demo_steps) await page.getByRole('button', { name: '下一步', exact: true }).click();
  await page.getByRole('button', { name: '进入自由探索' }).click();
  if (width <= 760) await page.locator('.experiment-mobile').getByRole('button', { name: 'AI 对话', exact: true }).click();
  await page.getByLabel('实验问题或回答').fill('为什么刚才要交换？');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByRole('button', { name: '回答或继续问', exact: true })).toBeVisible();
  await expect.poll(() => saved?.view.seq).toBe(frozen!.view.seq);
  if (width <= 760) await page.locator('.experiment-mobile').getByRole('button', { name: '步骤', exact: true }).click();
  await page.getByRole('button', { name: '2 自由探索', exact: true }).click();
  if (width <= 760) await page.locator('.experiment-mobile').getByRole('button', { name: '实验', exact: true }).click();
  await stage.locator('#customInput').fill('3,1,2');
  await stage.locator('#btn-apply').click();
  await stage.locator('#btn-step').click();
  await expect.poll(() => saved?.view.state.array).toEqual([1,3,2]);
  await stage.locator('#btn-run').click();
  await expect.poll(() => saved?.view.state.array).toEqual([1,2,3]);
  await stage.locator('#btn-pause').click();
  await expect.poll(() => saved?.view.state.running).toBe(false);
  const state=saved!.view.state;
  await page.reload();
  await expect(stage.locator('#btn-step')).toBeVisible();
  await expect.poll(() => saved?.view.state.array).toEqual(state.array);
  expect(saved!.view.events.some(e => e.command?.action === '动画状态采样')).toBe(true);
  expect(saved!.view.events.some(e => e.phase === 'guided')).toBe(false);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
  expect(errors).toEqual([]);
  fs.mkdirSync('../docs/acceptance/2026-10-15-experiment-pages', { recursive: true });
  await page.screenshot({path:`../docs/acceptance/2026-10-15-experiment-pages/real-explore-${width}.png`,fullPage:true});
  fs.writeFileSync(`../.runtime/experiment-pages-check/real-browser-view-${width}.json`, JSON.stringify(saved!.view));
});
