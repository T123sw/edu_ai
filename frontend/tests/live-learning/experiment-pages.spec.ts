import { test, expect } from 'playwright/test';
import fs from 'node:fs';
import type { View } from '../../src/practice/experiment/model';
for (const width of [1440, 390]) test(`HTML-first two stages, suggestions, history and restore (${width})`, async ({ page }) => {
  const artifact = JSON.parse(fs.readFileSync('../.runtime/experiment-fixtures/pages.json', 'utf8'));
  delete artifact.experiment.pages.guided;
  artifact.experiment.spec.tasks = [];
  artifact.experiment.spec.phases = ['demonstrate', 'explore'];
  artifact.experiment.spec.exploration_prompts = ['操作一次，观察计数的变化。', '重置后再操作两次，比较计数。'];
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
  await expect(stage.locator('#state')).toHaveText('{"count":0}');
  await expect(stage.locator('#correct')).toBeHidden();
  await page.getByRole('button', { name: '下一步', exact: true }).click();
  await expect(stage.locator('#state')).toHaveText('{"count":1}');
  await page.getByRole('button', { name: '上一步', exact: true }).click();
  await expect(stage.locator('#state')).toHaveText('{"count":0}');
  await page.getByRole('button', { name: '下一步', exact: true }).click();
  await page.getByRole('button', { name: '进入自由探索' }).click();
  await expect(page.getByRole('button', { name: '下一步', exact: true })).toHaveCount(0);
  await expect(stage.locator('#state')).toHaveText('{"count":0}');
  await stage.locator('#correct').click();
  await expect(stage.locator('#state')).toHaveText('{"count":1}');
  await expect.poll(() => saved?.view.state.count).toBe(1);
  expect(saved!.view.events.some(e => e.phase === 'guided')).toBe(false);
  const beforeSuggestion = saved!.view.seq;
  const suggestion = page.locator('.experiment-suggestion p');
  const first = await suggestion.textContent();
  await page.getByRole('button', { name: '换个方向 ↻' }).click();
  await expect(suggestion).not.toHaveText(first!);
  expect(saved!.view.seq).toBe(beforeSuggestion);
  if (width <= 760) await page.locator('.experiment-mobile').getByRole('button', { name: 'AI 对话', exact: true }).click();
  await page.getByLabel('实验问题或回答').fill('为什么这个操作会改变结果？');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByRole('button', { name: '回答或继续问', exact: true })).toBeVisible();
  await expect.poll(() => saved?.view.seq).toBe(frozen!.view.seq);
  const composer = page.getByLabel('实验问题或回答');
  const reply = page.getByRole('button', { name: '回答或继续问', exact: true });
  await composer.fill('保留我的回答草稿');
  // The latest completed turn is already selected; repeated clicks must still
  // reveal and focus the composer instead of relying on a selection change.
  for (let click = 0; click < 2; click++) {
    await reply.click();
    await expect(composer).toBeFocused();
    await expect(composer).toHaveValue('保留我的回答草稿');
    await expect(reply).toHaveAttribute('aria-pressed', 'true');
    const box = await composer.boundingBox();
    expect(box!.y).toBeGreaterThanOrEqual(0);
    expect(box!.y + box!.height).toBeLessThanOrEqual(1000);
  }
  await page.getByRole('button', { name: '改问当前操作' }).click();
  await expect(composer).toBeFocused();
  await expect(reply).toHaveAttribute('aria-pressed', 'false');
  await expect(composer).toHaveValue('保留我的回答草稿');
  if (width <= 760) await page.locator('.experiment-mobile').getByRole('button', { name: '实验', exact: true }).click();
  await expect(page.getByRole('button', { name: '恢复初始设置', exact: true })).toHaveCount(0);
  await expect(page.getByText('自由操作，无需按顺序完成', { exact: true })).toHaveCount(0);
  await expect.poll(() => saved?.view.state.count).toBe(1);
  const events = saved!.view.events.length;
  await page.reload();
  await expect(stage.locator('#state')).toHaveText('{"count":1}');
  expect(saved!.view.events.length).toBe(events);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
  expect(errors).toEqual([]);
  fs.mkdirSync('../.runtime/experiment-pages-check', { recursive: true });
  fs.writeFileSync(`../.runtime/experiment-pages-check/browser-view-${width}.json`, JSON.stringify(saved!.view));
});
