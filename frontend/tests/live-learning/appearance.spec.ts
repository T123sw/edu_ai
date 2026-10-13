import { test, expect, type BrowserContext } from 'playwright/test';
import { seedState } from '../../src/selfLearning/model';

async function fixture(context: BrowserContext) {
  const state = seedState();
  const room = state.rooms[0];
  const resource = room.chapters.flatMap(c => c.resources).find(r => r.kind === 'report')!;
  resource.remote = { courseId: room.id, materialId: 'theme-report', materialType: 'report', version: 1, visibility: 'course' };
  await context.addInitScript(() => { if (location.protocol === 'http:' || location.protocol === 'https:') localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'learner', role: 'student' } })); });
  await context.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/api/') && !path.startsWith('/backend/api/')) return route.continue();
    const user = { username: 'learner', role: 'student', display_name: '学习者', email: '', phone: '', department: '', bio: '', avatar_url: '', created_at: '', password_updated_at: '' };
    const json = path.endsWith('/auth/verify') ? { valid: true, user }
      : path.endsWith('/auth/me') ? user
      : path.endsWith('/self-learning/state') ? { ...state, shared: [], serverJobs: [] }
      : path.endsWith('/courses/' + room.id) ? room
      : path.endsWith('/materials/report/theme-report/versions/1') ? { course_id: room.id, material_id: 'theme-report', material_type: 'report', version: 1, title: '配色测试报告', content: '# 配色测试报告\n\n报告正文保持清晰可读。' }
      : path.endsWith('/api/courses') ? []
      : path.endsWith('/course-preparations') ? { preparations: [] } : { items: [] };
    return route.fulfill({ json });
  });
  return { room, resource };
}

test('palettes persist across account, home and embedded reports without changing layout', async ({ page, context }) => {
  const { room, resource } = await fixture(context);
  const choices = [['forest', '纸间绿'], ['ocean', '雾海蓝'], ['sunset', '暖杏'], ['dark', '石墨夜']] as const;
  let homeGeometry: unknown;
  let classroomGeometry: unknown;
  const colors = new Set<string>();
  for (const [id, label] of choices) {
    await page.goto('/?account=1#profile');
    await page.getByRole('group', { name: '界面主题' }).getByRole('button', { name: new RegExp('^' + label) }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', id);
    await page.goto('/');
    await expect(page.locator('.sl-home-editorial')).toBeVisible();
    await expect(page.locator('html')).toHaveAttribute('data-theme', id);
    const geometry = await page.locator('.sl-prompt').boundingBox();
    if (homeGeometry) expect(geometry).toEqual(homeGeometry); else homeGeometry = geometry;
    colors.add(await page.locator('.sl-home-editorial').evaluate(e => getComputedStyle(e).backgroundColor));
    await page.screenshot({ path: `/tmp/edu-appearance-home-${id}.png` });
    await page.goto(`/#/classroom/${room.id}?resource=${resource.id}`);
    await expect(page.locator('.sl-classroom')).toBeVisible();
    const readerGeometry = await page.locator('.sl-reader').boundingBox();
    if (classroomGeometry) expect(readerGeometry).toEqual(classroomGeometry); else classroomGeometry = readerGeometry;
    const frame = page.frameLocator('iframe.sl-live-material');
    await expect(frame.locator('html')).toHaveAttribute('data-theme', id);
    await expect(frame.getByText('报告正文保持清晰可读。')).toBeVisible();
    await page.screenshot({ path: `/tmp/edu-appearance-classroom-${id}.png` });
  }
  expect(colors.size).toBe(4);
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

test('system follows live device changes; explicit choices ignore them and sync to other tabs', async ({ page, context }) => {
  const { room, resource } = await fixture(context);
  await page.emulateMedia({ colorScheme: 'light' });
  await page.goto('/?account=1#profile');
  await page.getByRole('button', { name: /跟随系统/ }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'forest');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await expect(page.getByRole('button', { name: /跟随系统/ })).toHaveAttribute('aria-pressed', 'true');
  const other = await context.newPage();
  await other.goto(`/#/classroom/${room.id}?resource=${resource.id}`);
  await expect(other.frameLocator('iframe.sl-live-material').getByText('报告正文保持清晰可读。')).toBeVisible();
  await page.getByRole('button', { name: /雾海蓝/ }).click();
  await expect(other.locator('html')).toHaveAttribute('data-theme', 'ocean');
  await expect(other.frameLocator('iframe.sl-live-material').locator('html')).toHaveAttribute('data-theme', 'ocean');
  await page.emulateMedia({ colorScheme: 'light' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'ocean');
  await other.close();
});

test('mobile appearance choices remain usable without horizontal overflow', async ({ page, context }) => {
  await fixture(context);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/?account=1#profile');
  await page.getByRole('button', { name: /^石墨夜/ }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '/tmp/edu-appearance-profile-mobile.png', fullPage: true });
  await page.goto('/');
  await expect(page.locator('.sl-home-editorial')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '/tmp/edu-appearance-home-mobile.png', fullPage: true });
});

test('unavailable preference storage does not prevent switching', async ({ page, context }) => {
  await fixture(context);
  await page.addInitScript(() => {
    const get = Storage.prototype.getItem, set = Storage.prototype.setItem;
    Storage.prototype.getItem = function (key) { if (key === 'stitch-theme') throw new Error('blocked'); return get.call(this, key); };
    Storage.prototype.setItem = function (key, value) { if (key === 'stitch-theme') throw new Error('blocked'); return set.call(this, key, value); };
  });
  await page.goto('/?account=1#profile');
  await page.getByRole('button', { name: /暖杏/ }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'sunset');
});
