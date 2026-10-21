import { test, expect, type Page } from 'playwright/test';
import path from 'node:path';
const evidence = path.resolve('../docs/acceptance/2026-10-15-profile-unified');

async function fixture(page: Page, role = 'student') {
  const user = { username: 'tang', role };
  let profile = { ...user, display_name: 'Tang', email: '', phone: '', department: '', bio: '', avatar_url: '', created_at: '', password_updated_at: '' };
  let passwordChanges = 0;
  let avatarChanges = 0;
  const configWrites: string[] = [];
  let active = false;
  let revision: Record<string, unknown> | null = null;
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aV9sAAAAASUVORK5CYII=', 'base64');
  await page.addInitScript(user => {
    if (!sessionStorage.getItem('profile-seeded')) {
      localStorage.setItem('edu-ai-auth', JSON.stringify({ user, token: 'fixture-token' }));
      localStorage.setItem('stitch-theme', 'forest');
      sessionStorage.setItem('profile-seeded', '1');
    }
  }, user);
  await page.route('**/api/**', async route => {
    const pathname = new URL(route.request().url()).pathname.replace(/^\/backend/, '');
    const method = route.request().method();
    let json: unknown = {};
    if (pathname === '/api/self-learning/state') json = { version: 1, rooms: [], resources: [], jobs: [], shared: [], serverJobs: [] };
    if (pathname === '/api/course-preparations') json = { preparations: [] };
    if (pathname === '/api/auth/verify') json = { valid: true, user };
    if (pathname === '/api/auth/me') {
      if (method === 'PUT') profile = { ...profile, ...route.request().postDataJSON() };
      json = profile;
    }
    if (pathname === '/api/auth/avatar') {
      if (method === 'GET') return route.fulfill({ body: png, contentType: 'image/png' });
      avatarChanges++; profile.avatar_url = '/api/auth/avatar'; json = profile;
    }
    if (pathname === '/api/auth/change-password') {
      const data = route.request().postDataJSON();
      expect(data).toEqual({ current_password: 'old-password', new_password: 'new-password' });
      passwordChanges++; json = { success: true };
    }
    if (pathname === '/api/courses') json = Array.from({ length: 22 }, (_, index) => ({ id: `course-${index}`, name: `课程 ${index}` }));
    if (pathname === '/api/runtime-config') json = {
      can_manage_system: role === 'admin',
      providers: ['llm', 'embedding', 'tts', 'web_search', 'pdf_parser', 'classroom'].map(provider => ({
        provider, fields: ['base_url', 'api_key', 'model'], effective_source: provider === 'llm' && active ? 'user' : 'environment',
        user: { scope: 'user', owner_id: 'tang', provider, active_revision_id: provider === 'llm' && active ? 'r1' : null, revisions: provider === 'llm' && revision ? [revision] : [] },
      })),
    };
    if (pathname.startsWith('/api/runtime-config/llm/')) {
      configWrites.push(pathname.split('/').at(-1)!);
      if (pathname.endsWith('/draft')) revision = { revision_id: 'r1', status: 'draft', values: route.request().postDataJSON().values };
      if (pathname.endsWith('/verify')) revision = { ...revision, status: 'verified' };
      if (pathname.endsWith('/activate')) { active = true; revision = { ...revision, status: 'active' }; }
      json = revision;
    }
    await route.fulfill({ json });
  });
  return { png, passwordChanges: () => passwordChanges, avatarChanges: () => avatarChanges, configWrites };
}

for (const role of ['student', 'teacher', 'admin']) {
  test(`${role}: role-neutral profile, editing, security and persistent appearance`, async ({ page }, info) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    const f = await fixture(page, role);
    await page.goto('/');
    const trigger = page.getByRole('button', { name: '页面配色', exact: true });
    await expect(trigger).toBeVisible();
    await expect(page.locator('.sl-live-account .theme-switcher + .sl-avatar')).toBeVisible();
    await trigger.click();
    const theme = role === 'teacher' ? '雾海蓝' : role === 'admin' ? '石墨夜' : '纸间绿';
    await page.getByRole('button', { name: new RegExp(theme) }).click();
    await expect(page.getByRole('dialog', { name: '页面配色' })).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await page.reload();
    await trigger.click();
    await expect(page.getByRole('button', { name: new RegExp(theme) })).toHaveAttribute('aria-pressed', 'true');
    const box = await page.getByRole('dialog', { name: '页面配色' }).boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(info.project.use.viewport!.width);
    await page.screenshot({ path: path.join(evidence, `${process.env.PROFILE_EVIDENCE_PREFIX || 'preview'}-appearance-${role}-${info.project.name}.png`), fullPage: true });
    await page.keyboard.press('Escape');
    await expect(trigger).toBeFocused();
    await trigger.click();
    await page.locator('.sl-brand').click();
    await expect(page.getByRole('dialog', { name: '页面配色' })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.getByRole('link', { name: '个人中心', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Tang', exact: true })).toBeVisible();
    await expect(page.locator('.profile-course-count')).toContainText('22');
    await expect(page.locator('main')).not.toContainText(/Account Center|教学职责|教师|学生|系统角色|所属部门/);
    await expect(page.getByRole('tab')).toHaveCount(0);
    await expect(page.getByRole('heading', { name: '账号资料', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '修改密码', exact: true })).toBeVisible();
    await expect(page.locator('.profile-sidebar, .profile-ai-art')).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: path.join(evidence, `${process.env.PROFILE_EVIDENCE_PREFIX || 'preview'}-${role}-${info.project.name}.png`), fullPage: true });
    await page.getByRole('button', { name: '编辑资料' }).click();
    await page.getByLabel('显示名称', { exact: true }).fill('新的名字');
    await page.getByLabel('邮箱', { exact: true }).fill('tang@example.com');
    await page.getByRole('button', { name: /^保\s*存$/ }).click();
    await expect(page.getByRole('heading', { name: '新的名字', exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByText('tang@example.com', { exact: true })).toBeVisible();
    await page.locator('input[type=file]').setInputFiles({ name: 'avatar.png', mimeType: 'image/png', buffer: f.png });
    await expect(page.getByRole('img', { name: '新的名字的头像' })).toBeVisible();
    expect(f.avatarChanges()).toBe(1);
    await page.getByRole('button', { name: '修改密码', exact: true }).click();
    await page.getByLabel('当前密码', { exact: true }).fill('old-password');
    await page.getByLabel('新密码', { exact: true }).fill('new-password');
    await page.getByLabel('确认新密码', { exact: true }).fill('new-password');
    await page.getByRole('button', { name: '确认修改' }).click();
    await expect(page.getByRole('dialog')).toBeHidden();
    expect(f.passwordChanges()).toBe(1);
    await page.getByRole('link', { name: /AI 服务配置/ }).click();
    await expect(page.getByRole('heading', { name: 'AI 服务配置', exact: true })).toBeVisible();
    await page.getByRole('link', { name: '返回账号中心' }).click();
    await page.getByRole('button', { name: '退出登录' }).click();
    await expect(page.getByRole('heading', { name: '登录 Edu AI' })).toBeVisible();
    expect(errors).toEqual([]);
  });
}

test('deployment-managed voice cannot misleadingly apply; model requires test then apply', async ({ page }) => {
  const f = await fixture(page);
  await page.goto('/?account=1#profile');
  await page.getByRole('link', { name: /AI 服务配置/ }).click();
  await page.getByRole('button', { name: /语音服务/ }).click();
  await expect(page.getByText('语音服务由部署统一管理', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '应用配置' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '测试连接' })).toHaveCount(0);
  await page.getByRole('button', { name: /AI 课堂/ }).click();
  await expect(page.getByLabel('模型或服务标识', { exact: true })).toHaveCount(0);
  await expect(page.getByLabel('服务地址', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /对话生成/ }).click();
  await expect(page.getByRole('button', { name: '应用配置' })).toBeDisabled();
  await page.getByLabel('服务地址', { exact: true }).fill('https://provider.example/v1');
  await page.getByLabel('API 密钥', { exact: true }).fill('test-key');
  await page.getByLabel('模型或服务标识', { exact: true }).fill('test-model');
  await page.getByRole('button', { name: '测试连接' }).click();
  await expect(page.getByRole('button', { name: '应用配置' })).toBeEnabled();
  expect(f.configWrites).toEqual(['draft', 'verify']);
  await page.getByRole('button', { name: '应用配置' }).click();
  await expect(page.getByText('个人配置正在生效', { exact: true })).toBeVisible();
  expect(f.configWrites).toEqual(['draft', 'verify', 'activate']);
  await page.reload();
  await expect(page.getByText('个人配置正在生效', { exact: true })).toBeVisible();
});


test('header themes apply immediately and follow system appearance', async ({ page }) => {
  await fixture(page);
  await page.goto('/');
  for (const [name, value] of [['纸间绿', 'forest'], ['雾海蓝', 'ocean'], ['暖杏', 'sunset'], ['石墨夜', 'dark']]) {
    await page.getByRole('button', { name: '页面配色', exact: true }).click();
    await page.getByRole('button', { name: new RegExp(name) }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', value);
    expect(await page.evaluate(() => localStorage.getItem('stitch-theme'))).toBe(value);
  }
  await page.getByRole('button', { name: '页面配色', exact: true }).click();
  await page.getByRole('button', { name: /跟随系统/ }).click();
  await page.emulateMedia({ colorScheme: 'light' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'forest');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme-preference', 'system');
});


test('preview keeps color control beside avatar', async ({ page }) => {
  await page.goto('/?review=1');
  await expect(page.locator('.sl-account .theme-switcher + .sl-avatar')).toBeVisible();
  await page.getByRole('button', { name: '页面配色', exact: true }).click();
  await page.getByRole('button', { name: /暖杏/ }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'sunset');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
