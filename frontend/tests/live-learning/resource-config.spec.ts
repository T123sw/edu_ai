import { test, expect, type Page } from 'playwright/test';
import { seedState } from '../../src/selfLearning/model';
const evidence = '/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-15-resource-config';

async function fixture(page: Page) {
  const state = seedState(), room = state.rooms[0];
  const user = { username: 'resource-config-fixture', role: 'student' };
  const resources = [true, false].map(show => ({ material_id: show ? 'shown' : 'hidden', material_type: 'flashcard',
    title: show ? '显示来源样例' : '隐藏来源样例', version: 1, studio_course_id: room.id,
    content: { cards: [{ front: '变量是什么？', back: '用于保存数据。', ...(show ? { source_title: '当前知识点资料' } : {}) }] } }));
  await page.addInitScript(user => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user })), user);
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    const resource = resources.find(r => path.endsWith(`/resources/flashcard/${r.material_id}`));
    const json = path.endsWith('/auth/verify') ? { valid: true, user }
      : path.endsWith('/auth/me') ? user
      : path.endsWith('/self-learning/state') ? { ...state, shared: [], serverJobs: [] }
      : path.endsWith(`/courses/${room.id}`) ? room
      : path.endsWith('/personal-studio/generate') ? { edu_job_id: 'config-check', status: 'queued', progress: 0, input_summary: {}, kind: 'generate_flashcard', created_at: new Date().toISOString() }
      : path.endsWith('/personal-studio') ? { resources, jobs: [] }
      : resource || (path.endsWith('/course-preparations') ? { preparations: [] } : { items: [] });
    return route.fulfill({ json });
  });
  await page.goto(`/#/classroom/${room.id}`);
  return room;
}
async function choose(page: Page, name: string) {
  await page.getByRole('button', { name: '打开生成工具' }).click();
  await page.locator('.studio-tool-grid > button').filter({ has: page.locator('strong', { hasText: name }) }).click();
}
for (const width of [1440, 390]) {
  test(`flashcard supplemental instructions submit as their own field ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await fixture(page); await choose(page, '闪卡');
    await page.getByText('更多设置', { exact: true }).click();
    await expect(page.getByLabel('分类', { exact: true })).toHaveCount(0);
    await page.getByLabel('更多补充', { exact: true }).fill('多练易混淆概念，每张附例子');
    await page.getByLabel('卡片数量').fill('7');
    await page.getByRole('combobox', { name: /^难度/ }).selectOption('hard');
    await page.getByLabel('卡片中显示资料来源').uncheck();
    await page.screenshot({ path: `${evidence}/flashcard-${width}.png` });
    const request = page.waitForRequest(r => r.url().endsWith('/personal-studio/generate') && r.method() === 'POST');
    await page.getByRole('button', { name: '开始生成' }).click();
    const body = (await request).postDataJSON();
    expect(body.config.flashcard_config).toMatchObject({ count: 7, difficulty: 'hard', special_requirements: '多练易混淆概念，每张附例子', show_sources: false });
    expect(body.config.flashcard_config).not.toHaveProperty('category');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
  test(`graph focus stays visible next to depth and reaches request ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await fixture(page); await choose(page, '思维导图');
    await expect(page.getByText('更多设置', { exact: true })).toHaveCount(0);
    const depth = page.getByLabel('层级深度'), focus = page.getByLabel('关系侧重点');
    await expect(focus).toBeVisible();
    const a = await depth.locator('..').boundingBox(), b = await focus.locator('..').boundingBox();
    expect(Math.abs(a!.y - b!.y)).toBeLessThan(2); expect(b!.x).toBeGreaterThan(a!.x);
    await depth.fill('4'); await focus.fill('重点比较分治与递归的关系');
    await page.screenshot({ path: `${evidence}/graph-${width}.png` });
    const request = page.waitForRequest(r => r.url().endsWith('/personal-studio/generate') && r.method() === 'POST');
    await page.getByRole('button', { name: '开始生成' }).click();
    expect((await request).postDataJSON().config).toMatchObject({ max_depth: 4, description: '重点比较分治与递归的关系' });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
  test(`flashcard source appears only when saved by enabled configuration ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await fixture(page); await page.goto('/#/my-resources');
    await page.locator('.studio-type-filters button').filter({ hasText: '闪卡' }).click();
    for (const title of ['显示来源样例', '隐藏来源样例']) {
      await page.locator('.studio-resource-row').filter({ hasText: title }).click();
      await page.getByRole('button', { name: '翻转卡片', exact: true }).click();
      if (title === '显示来源样例') await expect(page.getByText('资料来源：当前知识点资料', { exact: true })).toBeVisible();
      else await expect(page.getByText('资料来源：当前知识点资料', { exact: true })).toHaveCount(0);
      await page.getByRole('button', { name: '关闭工具面板' }).click();
    }
  });
}
