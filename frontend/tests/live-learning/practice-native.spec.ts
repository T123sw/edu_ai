import { test, expect } from 'playwright/test';
import fs from 'node:fs';

test.use({ deviceScaleFactor: 2 });

for (const width of [1440, 1100, 390]) test(`native experiment keeps three columns, sharp canvas and journal (${width})`, async ({ page }) => {
  const artifactPath = process.env.PRACTICE_NATIVE_ARTIFACT;
  test.skip(!artifactPath, 'Set PRACTICE_NATIVE_ARTIFACT to a real native generated experiment.');
  const artifact = JSON.parse(fs.readFileSync(artifactPath!, 'utf8'));
  const observations: { state: { results: Record<string, unknown> } }[] = [];
  await page.setViewportSize({ width, height: 1000 });
  await page.addInitScript(() => { if (window === window.top) localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'test', user: { username: 'alice', role: 'student' } })); });
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/^\/backend/, '');
    if (path.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'alice', role: 'student' } } });
    if (path.endsWith('/self-learning/state')) return route.fulfill({ json: { version: 1, rooms: [], resources: [], jobs: [], serverJobs: [], shared: [] } });
    if (path.endsWith('/observations')) {
      observations.push({ ...route.request().postDataJSON(), created_at: Date.now() / 1000 });
      return route.fulfill({ json: { observations, messages: [] } });
    }
    if (path.endsWith('/practice/native')) return route.fulfill({ json: { id: 'native', job: { status: 'succeeded' }, artifact, journal: { observations, messages: [] } } });
    return route.fulfill({ json: { items: [] } });
  });
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/#/practice/native');
  const frame = page.frameLocator('iframe[title="互动实验"]');
  await expect(frame.locator('canvas')).toBeVisible();
  if (width > 1000) {
    await expect(page.locator('.practice-directory')).toBeVisible();
    await expect(page.locator('.practice-guide')).toBeVisible();
    const left = (await page.locator('.practice-directory').boundingBox())!;
    const center = (await page.locator('.practice-main').boundingBox())!;
    const right = (await page.locator('.practice-guide').boundingBox())!;
    expect(left.x + left.width).toBeLessThanOrEqual(center.x + 1);
    expect(center.x + center.width).toBeLessThanOrEqual(right.x + 1);
    expect(center.width).toBeGreaterThan(width * .45);
    expect(right.width).toBeGreaterThanOrEqual(360);
    expect(right.width).toBeGreaterThanOrEqual(width * .29);
  } else {
    await expect(page.locator('.practice-directory')).toBeHidden();
    await expect(page.locator('.practice-guide')).toBeHidden();
  }
  const notes = frame.locator('[data-practice-native-notes]');
  await expect(notes).toHaveCount(1);
  await expect(notes).not.toHaveAttribute('open');
  await expect(frame.locator('[data-practice-presentation]')).toHaveCount(0);
  await frame.locator('body').evaluate(body => { const math = document.createElement('p'); math.id = 'formula-probe'; math.textContent = '\\(x^2\\)'; body.appendChild(math); });
  await expect(frame.locator('#formula-probe .katex')).toHaveCount(1);
  await frame.locator('#formula-probe').evaluate(element => element.remove());
  await frame.locator('#btnPivot').click();
  await frame.locator('#btnNext').click();
  await expect(frame.locator('#statCompare')).toHaveText('1');
  await page.waitForTimeout(600);
  const value = await frame.locator('#sizeRange').inputValue();
  if (width <= 1000) await page.getByRole('navigation', { name: '实验工作区视图' }).getByRole('button', { name: '步骤', exact: true }).click();
  await page.getByRole('navigation', { name: '探索路线' }).getByRole('button').nth(1).click();
  if (width <= 1000) await page.getByRole('navigation', { name: '实验工作区视图' }).getByRole('button', { name: '问答', exact: true }).click();
  await expect(page.locator('.practice-guide')).toBeVisible();
  await expect(page.locator('.practice-task')).toContainText(artifact.plan.steps[1].instruction);
  if (width <= 1000) await page.getByRole('navigation', { name: '实验工作区视图' }).getByRole('button', { name: '实验', exact: true }).click();
  await expect(frame.locator('#sizeRange')).toHaveValue(value);
  await expect(frame.locator('#statCompare')).toHaveText('1');
  await page.getByRole('button', { name: '专注实验', exact: true }).click();
  await expect(page.locator('.practice-directory')).toBeHidden();
  await expect(page.locator('.practice-guide')).toBeHidden();
  await page.keyboard.press('Escape');
  await expect(frame.locator('#statCompare')).toHaveText('1');
  await page.getByRole('button', { name: /^观察记录/ }).click();
  await page.getByLabel('记录你的发现').fill('原生实验：一次比较只增加一次计数');
  await page.getByRole('button', { name: '保存本次观察', exact: true }).click();
  await expect(page.locator('.practice-history')).toContainText('一次比较');
  expect(observations[0].state.results['比较次数']).toBe(1);
  await page.getByRole('button', { name: '交互实验', exact: true }).click();
  await expect(frame.locator('#statCompare')).toHaveText('1');
  await expect(frame.locator('body>header')).toBeHidden();
  await frame.locator('canvas').scrollIntoViewIfNeeded();
  await expect.poll(() => frame.locator('canvas').evaluate((canvas: HTMLCanvasElement) => Math.abs(canvas.width - canvas.getBoundingClientRect().width * devicePixelRatio))).toBeLessThanOrEqual(2);
  expect(await frame.locator('body').evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
  expect(errors).toEqual([]);
  await page.screenshot({ path: `test-results/practice-native-${width}.png` });
  await page.reload();
  await page.getByRole('button', { name: /^观察记录/ }).click();
  await expect(page.locator('.practice-history')).toContainText('一次比较');
});
