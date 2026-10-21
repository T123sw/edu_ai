import { test, expect } from 'playwright/test';
import fs from 'node:fs';
import type { View } from '../../src/practice/experiment/model';

for (const width of [1440, 390]) test(`restore historical practice into exploration without losing history (${width})`, async ({ page }) => {
  const artifact = JSON.parse(fs.readFileSync('../.runtime/experiment-fixtures/pages.json', 'utf8'));
  const event = { id: 'old-event', seq: 1, at: 1, actor: 'user', type: 'hint', phase: 'guided', task_id: 'task-1', attempt_id: 'old-attempt', before: '1:before', after: '1', feedback: '历史提示' };
  let saved = { view: { run_id: 'old-run', revision: artifact.experiment.revision, seq: 1, phase: 'guided', index: 0, attempt_id: 'old-attempt', attempt_before: { count: 0 }, last_input: {}, state: { count: 0 }, feedback: '历史提示', verdict: '', events: [event], snapshots: { '0': { count: 0 }, '1:before': { count: 0 }, '1': { count: 0 } } } as View };
  await page.setViewportSize({ width, height: 768 });
  await page.addInitScript(() => { if (window === window.top) localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'test', user: { username: 'alice', role: 'student' } })); });
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'alice', role: 'student' } } });
    if (path.endsWith('/self-learning/state')) return route.fulfill({ json: { version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: [] } });
    if (path.endsWith('/experiment/runs/latest')) return route.fulfill({ json: saved });
    if (path.endsWith('/experiment/runs')) { saved = { view: route.request().postDataJSON().view }; return route.fulfill({ json: saved }); }
    if (path.endsWith('/experiment/tutor')) return route.fulfill({ json: { items: [], next_cursor: null } });
    if (path.endsWith('/practice/experiment')) return route.fulfill({ json: { id: 'experiment', job: { status: 'succeeded' }, artifact, journal: { observations: [], messages: [] } } });
    return route.fulfill({ json: { items: [] } });
  });
  await page.goto('/#/practice/experiment');
  await expect(page.getByRole('heading', { name: '自由探索', exact: true })).toBeVisible();
  await expect.poll(() => saved.view.phase).toBe('explore');
  expect(saved.view.run_id).toBe('old-run');
  expect(saved.view.events[0]).toEqual(event);
  expect(saved.view.snapshots['1']).toEqual({ count: 0 });
  const stage = page.frameLocator('iframe[title="实验展示"]');
  await stage.locator('#correct').click();
  await expect.poll(() => saved.view.state.count).toBe(1);
  await page.reload();
  await expect(stage.locator('#state')).toHaveText('{"count":1}');
  expect(saved.view.events[0]).toEqual(event);
  await expect(page.getByRole('button', { name: /动手实践/ })).toHaveCount(0);
});
