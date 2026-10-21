import { test, expect } from 'playwright/test';
import { seedState } from '../../src/selfLearning/model';

for (const role of ['student', 'teacher', 'admin']) {
  test(`tools and resource filters are identical for legacy ${role} accounts`, async ({ page, context }) => {
    const state = seedState();
    const room = state.rooms[0];
    const user = { username: 'unified-fixture', role };
    await context.addInitScript(user => {
      localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user }));
    }, user);
    await context.route('**/api/**', route => {
      const path = new URL(route.request().url()).pathname;
      const json = path.endsWith('/auth/verify') ? { valid: true, user }
        : path.endsWith('/auth/me') ? user
        : path.endsWith('/self-learning/state') ? { ...state, shared: [], serverJobs: [] }
        : path.endsWith(`/courses/${room.id}`) ? room
        : path.endsWith('/personal-studio') ? { resources: [], jobs: [] }
        : path.endsWith('/course-preparations') ? { preparations: [] }
        : path.endsWith('/api/courses') ? [] : { items: [] };
      return route.fulfill({ json });
    });
    await page.goto('/');
    await expect(page.getByRole('button', { name: '共享我的课堂' })).toBeVisible();
    await page.goto(`/#/classroom/${room.id}`);
    await page.getByRole('button', { name: '打开生成工具' }).click();
    const dialog = page.getByRole('dialog', { name: '生成工具', exact: true });
    await expect(dialog.locator('.studio-tool-copy strong')).toHaveText(['学习报告', '习题', '闪卡', '思维导图', '播客', '情景案例']);
    for (const title of ['学习报告', '习题', '闪卡', '思维导图', '播客', '情景案例']) {
      await page.locator('.studio-tool-grid > button').filter({ has: page.locator('strong', { hasText: title }) }).click();
      await expect(page.getByRole('heading', { name: `制作一份${title}` })).toBeVisible();
      await expect(page.getByRole('button', { name: '开始生成' })).toBeEnabled();
      await page.getByRole('button', { name: '全部工具' }).click();
    }
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole('button', { name: '关闭工具面板' }).click();
    await page.goto('/#/my-resources');
    await expect(page.locator('.studio-type-filters button')).toHaveText(['学习报告', '习题', '闪卡', '思维导图', '播客', '情景案例', '研究结论'].map(label => `${label}0`));
  });
}
