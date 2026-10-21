import { test, expect } from 'playwright/test';
import { seedState } from '../../src/selfLearning/model';

const integrated = Boolean(process.env.BUBBLE_APP_URL);
const entry = integrated ? '/#/practice/bubble-sort' : '/bubble-preview.html';
test.beforeEach(async ({ context }) => {
  if (!integrated) return;
  await context.addInitScript(() => {
    if (!localStorage.getItem('edu-ai-auth')) localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'bubble-check', role: 'student' } }));
  });
  await context.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    const user = await route.request().frame().evaluate(() => JSON.parse(localStorage.getItem('edu-ai-auth')!).user);
    const json = path.endsWith('/auth/verify') ? { valid: true, user } : path.endsWith('/auth/me') ? user : path.endsWith('/self-learning/state') ? { ...seedState(), shared: [], serverJobs: [] } : path.endsWith('/course-preparations') ? { preparations: [] } : { items: [] };
    await route.fulfill({ json });
  });
});

for (const width of [1440, 390]) test(`demonstration and genuinely manual two-round practice at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 });
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  const feedback = () => page.locator('.bubble-feedback:visible');
  const board = () => page.locator('.bubble-board');
  const select = (index: number) => page.getByRole('button', { name: new RegExp(`^第${index + 1}个元素，`) });
  await page.goto(entry);
  await expect(feedback()).toContainText('从最左边');
  await expect(page.getByRole('button', { name: /自动执行|下一步|自动运行/ })).toHaveCount(0);
  await page.getByRole('button', { name: /比较这两个数/ }).click();
  await expect(board()).toHaveAttribute('data-values', '5,3,4,1');
  await expect(feedback()).toContainText('5 > 3');
  await page.getByRole('button', { name: /执行交换/ }).click();
  await expect(board()).toHaveAttribute('data-values', '3,5,4,1');
  for (let i = 0; i < 2; i++) { await page.getByRole('button', { name: /比较这两个数/ }).click(); await page.getByRole('button', { name: /执行交换/ }).click(); }
  await expect(feedback()).toContainText('第一轮结束');
  await page.getByRole('button', { name: /看看无需交换/ }).click();
  await page.getByRole('button', { name: /比较这两个数/ }).click(); await page.getByRole('button', { name: /保持顺序/ }).click();
  await page.getByRole('button', { name: /开始手动练习/ }).click();
  await expect(page.locator('.bubble-element.selected')).toHaveCount(0);
  await select(0).click(); await select(2).click(); await expect(feedback()).toContainText('不相邻');
  await expect(board()).toHaveAttribute('data-values', '5,1,4,2,8,3');
  await page.getByRole('button', { name: '取消选择' }).click();
  await select(0).click(); await select(1).click(); await page.getByRole('button', { name: '保持顺序', exact: true }).click();
  await expect(feedback()).toContainText('这次尝试没有改变'); await expect(page.getByTestId('comparisons')).toHaveText('0');
  await page.screenshot({ path: `../.runtime/bubble-practice-error-${width}.png`, fullPage: true, animations: 'disabled' });
  await page.getByRole('button', { name: '本轮完成', exact: true }).click(); await expect(feedback()).toContainText('这一轮还没有结束');
  await page.getByRole('button', { name: '取消选择' }).click();
  for (let round = 0; round < 2; round++) {
    for (let i = 0; i < 5 - round; i++) {
      const values = (await board().getAttribute('data-values'))!.split(',').map(Number);
      await select(i).click(); await select(i + 1).click();
      await page.getByRole('button', { name: values[i] > values[i + 1] ? /^交换/ : /^保持顺序$/ }).click();
      await expect(page.locator('.bubble-element.selected')).toHaveCount(0);
      if (round === 0 && i === 0) { await page.reload(); await expect(board()).toHaveAttribute('data-values', '1,5,4,2,8,3'); }
    }
    await page.getByRole('button', { name: '本轮完成', exact: true }).click();
  }
  await expect(board()).toHaveAttribute('data-values', '1,2,4,3,5,8');
  await expect(page.getByTestId('comparisons')).toHaveText('9'); await expect(page.getByTestId('swaps')).toHaveText('6');
  await expect(page.locator('.bubble-completion')).toContainText('前面的元素仍可能无序');
  await page.getByRole('button', { name: /01.*原理演示/ }).click();
  await expect(page.locator('.bubble-round')).toHaveText('演示完成');
  await page.getByRole('button', { name: /02.*手动练习/ }).click(); await expect(page.locator('.bubble-round')).toHaveText('两轮完成');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  expect(errors).toEqual([]); await page.screenshot({ path: `../.runtime/bubble-practice-complete-${width}.png`, fullPage: true, animations: 'disabled' });
});

test('keyboard selection, staged hints, retry isolation, and corrupt draft recovery', async ({ page }) => {
  await page.goto(entry);
  await page.getByRole('button', { name: /比较这两个数/ }).click();
  await page.getByRole('button', { name: /02.*手动练习/ }).click();
  const element = page.getByRole('button', { name: '第1个元素，值5' }); await element.focus(); await page.keyboard.press('Enter');
  await expect(element).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: '给我一个提示' }).click(); await expect(page.locator('.bubble-feedback:visible')).toContainText('提示 1 / 3');
  await page.getByRole('button', { name: '再具体一点' }).click(); await page.getByRole('button', { name: '再具体一点' }).click();
  await expect(page.getByTestId('comparisons')).toHaveText('0');
  await page.getByRole('button', { name: '重新练习', exact: true }).click(); await page.getByRole('button', { name: '确认重新开始' }).click();
  await expect(page.locator('.bubble-element.selected')).toHaveCount(0);
  await page.getByRole('button', { name: /01.*原理演示/ }).click(); await expect(page.getByTestId('comparisons')).toHaveText('1');
  await page.evaluate(key => sessionStorage.setItem(key, '{broken'), `edu-bubble-teaching-prototype-v1${integrated ? ':bubble-check' : ''}`); await page.reload();
  await expect(page.getByRole('alert')).toContainText('无法恢复'); await expect(page.getByTestId('comparisons')).toHaveText('0');
});

for (const width of [320, 768, 1024, 1440]) test(`feedback stays visible after an action in a short ${width}px viewport`, async ({ page }) => {
  await page.setViewportSize({ width, height: 700 });
  await page.goto(entry); await page.getByRole('button', { name: /02.*手动练习/ }).click();
  await page.getByRole('button', { name: '本轮完成', exact: true }).click();
  const feedback = page.locator('.bubble-feedback:visible'); await expect(feedback).toContainText('这一轮还没有结束');
  const box = (await feedback.boundingBox())!;
  expect(box.y).toBeGreaterThanOrEqual(0); expect(box.y + box.height).toBeLessThanOrEqual(700);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
});


test('app entry, return navigation, and account progress isolation', async ({ page }) => {
  test.skip(!integrated, 'Application integration only');
  await page.goto('/#/practice');
  await page.getByRole('link', { name: /冒泡排序 · 分步体验/ }).click();
  await expect(page).toHaveURL(/#\/practice\/bubble-sort$/);
  await page.getByRole('button', { name: /比较这两个数/ }).click();
  await expect(page.getByTestId('comparisons')).toHaveText('1');
  await page.getByRole('link', { name: '返回模拟实验' }).click();
  await expect(page.getByRole('link', { name: /冒泡排序 · 分步体验/ })).toBeVisible();
  await page.getByRole('link', { name: /冒泡排序 · 分步体验/ }).click();
  await expect(page.getByTestId('comparisons')).toHaveText('1');
  await page.evaluate(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'bubble-second', role: 'student' } })));
  await page.reload();
  await expect(page.getByTestId('comparisons')).toHaveText('0');
  await page.getByRole('button', { name: /02.*手动练习/ }).click();
  await page.evaluate(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'bubble-check', role: 'student' } })));
  await page.reload();
  await expect(page.getByTestId('comparisons')).toHaveText('1');
  await expect(page.getByRole('button', { name: /执行交换/ })).toBeVisible();
});
