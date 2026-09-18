import { test, expect } from 'playwright/test';

test('avatar opens existing account settings and returns to learning home', async ({ page }) => {
  const user = { username: 'account-test', role: 'student' };
  let profile = { ...user, display_name: '测试用户', email: '', phone: '', department: '', bio: '', avatar_url: '', created_at: '', password_updated_at: '' };
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(user => {
    if (!sessionStorage.getItem('account-test-seeded')) {
      localStorage.setItem('edu-ai-auth', JSON.stringify({ user, token: 'test-token' }));
      sessionStorage.setItem('account-test-seeded', '1');
    }
  }, user);
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (!path.startsWith('/api/')) return route.continue();
    let json: unknown = {};
    if (path === '/api/auth/verify') json = { valid: true, user };
    if (path === '/api/auth/me') {
      if (route.request().method() === 'PUT') profile = { ...profile, ...route.request().postDataJSON() };
      json = profile;
    }
    if (path === '/api/courses') json = [];
    if (path === '/api/self-learning/state') json = { version: 1, rooms: [], resources: [], jobs: [], shared: [], serverJobs: [] };
    if (path === '/api/runtime-config') json = { providers: [], can_manage_system: false };
    await route.fulfill({ json });
  });
  await page.goto('/');
  await page.getByRole('link', { name: '个人中心', exact: true }).click();
  await expect(page.getByRole('heading', { name: '测试用户', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '编辑资料' }).click();
  await page.getByLabel('显示名称', { exact: true }).fill('已更新用户');
  await page.getByRole('button', { name: /^保\s*存$/ }).click();
  await expect(page.getByRole('heading', { name: '已更新用户', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: '已更新用户', exact: true })).toBeVisible();
  await page.getByRole('link', { name: /AI 服务配置/ }).click();
  await expect(page.getByRole('heading', { name: 'AI 服务配置' })).toBeVisible();
  await page.getByRole('link', { name: '返回账号中心' }).click();
  await page.getByRole('link', { name: '返回首页' }).click();
  await expect(page.getByRole('link', { name: '个人中心', exact: true })).toBeVisible();
  await page.getByRole('link', { name: '个人中心', exact: true }).click();
  await page.getByRole('button', { name: '退出登录' }).click();
  await expect(page.getByRole('heading', { name: '登录 Edu AI' })).toBeVisible();
  expect(errors).toEqual([]);
});
