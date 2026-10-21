import { test, expect } from 'playwright/test';
import fs from 'node:fs';
import type { View } from '../../src/practice/experiment/model';

for (const width of [1440, 900, 390, 320]) test(`reference disclosure and center teaching (${width})`, async ({ page }) => {
  const artifact = JSON.parse(fs.readFileSync('../.runtime/experiment-concise/local/artifact.json', 'utf8'));
  let saved: { view: View } | null = null;
  await page.setViewportSize({ width, height: width <= 760 ? 740 : 768 });
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
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/#/practice/experiment');
  const stage = page.frameLocator('iframe[title="实验展示"]');
  const fold = stage.locator('.edu-frame-reference');
  const summary = fold.locator(':scope > summary');
  const formula = fold.locator('.katex').first();
  await expect(page.getByRole('button', { name: '下一步', exact: true })).toBeEnabled();
  await expect(formula).toBeHidden();
  await expect.poll(() => saved?.view.seq).toBeDefined();
  const initialSeq = saved?.view.seq;
  const closedHeight = (await page.locator('.experiment-stage').boundingBox())!.height;
  await summary.click();
  await expect(fold).toHaveAttribute('open', '');
  await expect(formula).toBeVisible();
  await expect.poll(async () => (await page.locator('.experiment-stage').boundingBox())!.height).toBeGreaterThan(closedHeight);
  await expect.poll(async () => stage.locator('body').evaluate(el => el.scrollHeight <= innerHeight + 2)).toBe(true);
  expect(saved?.view.seq).toBe(initialSeq);
  await summary.press('Enter'); await expect(formula).toBeHidden();
  await summary.press('Space'); await expect(formula).toBeVisible();
  const center = page.locator('.experiment-controls'), right = page.locator('.experiment-teaching');
  await expect(center.getByRole('heading', { name: '实验讲解' })).toBeVisible();
  await expect(center.getByRole('button', { name: '下一步', exact: true })).toHaveCount(1);
  await expect(right.locator(':scope > *')).toHaveCount(1);
  await expect(right.locator('.experiment-tutor')).toHaveCount(1);
  await page.evaluate(() => window.scrollTo(0, 0));
  const graphic = stage.locator('.edu-frame-visual');
  const graphicBox = (await graphic.boundingBox())!;
  const controlsBox = (await center.boundingBox())!;
  expect(controlsBox.y - graphicBox.y - graphicBox.height).toBeGreaterThanOrEqual(0);
  expect(controlsBox.y - graphicBox.y - graphicBox.height).toBeLessThanOrEqual(20);
  expect(controlsBox.y + controlsBox.height).toBeLessThanOrEqual(width <= 760 ? 740 : 768);
  expect((await fold.boundingBox())!.y).toBeGreaterThan(controlsBox.y + controlsBox.height);
  // Growing result data must not separate the graphic from the step controls.
  await stage.locator('.edu-frame-root').evaluate(root => {
    const data = document.createElement('section'); data.id = 'dense-results';
    for (let i = 0; i < 150; i++) { const row = document.createElement('p'); row.textContent = `结果 ${i}: 1, 2, 3, 4, 5`; data.append(row); }
    root.append(data);
  });
  await expect.poll(async () => (await page.locator('.experiment-stage').boundingBox())!.height).toBeGreaterThan(3000);
  expect(Math.abs((await center.boundingBox())!.y - controlsBox.y)).toBeLessThan(2);
  await stage.locator('#dense-results').evaluate(el => el.remove());
  await center.getByRole('button', { name: '下一步', exact: true }).click();
  await expect.poll(() => saved?.view.index).toBe(1);
  await center.getByRole('button', { name: '上一步', exact: true }).click();
  await expect.poll(() => saved?.view.index).toBe(0);
  await center.getByRole('button', { name: '下一步', exact: true }).click();
  await expect.poll(() => saved?.view.index).toBe(1);
  await page.locator('.experiment-history summary').click();
  await page.getByRole('button', { name: '问这一步' }).first().click();
  await expect(page.getByLabel('实验问题或回答')).toBeVisible();
  await expect(page.locator('.experiment-tutor-related')).toContainText('关于操作');
  if (width <= 760) await page.locator('.experiment-mobile').getByRole('button', { name: '实验', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
  // Re-entering a phase creates a new frame, including when the slot has the same offset.
  for (const phase of ['2 自由探索', '1 原理演示']) {
    if (width <= 760) await page.locator('.experiment-mobile').getByRole('button', { name: '步骤', exact: true }).click();
    await page.getByRole('button', { name: phase, exact: true }).click();
    if (width <= 760) await page.locator('.experiment-mobile').getByRole('button', { name: '实验', exact: true }).click();
    await expect(stage.locator('.edu-frame-teaching-slot')).toHaveCount(1);
    await expect.poll(async () => {
      const slot = (await stage.locator('.edu-frame-teaching-slot').boundingBox())!;
      const controls = (await center.boundingBox())!;
      return Math.abs(slot.height - controls.height) + Math.abs(slot.y - controls.y);
    }).toBeLessThan(3);
    if (phase === '2 自由探索') {
      await expect(center.getByRole('button', { name: '收起建议' })).toBeVisible();
      await center.getByRole('button', { name: '收起建议' }).click();
      await expect(center.locator('.experiment-suggestion')).toHaveCount(0);
      await center.getByRole('button', { name: '看看建议' }).click();
      await expect(center.locator('.experiment-suggestion')).toBeVisible();
    }
  }
  expect(errors).toEqual([]);
  await page.screenshot({ path: `../.runtime/experiment-two-stage/layout-${width}.png`, fullPage: true });
});
