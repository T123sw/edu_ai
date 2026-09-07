import { test, expect as baseExpect, type Page } from 'playwright/test';
import { installTeacherApiRoutes, physicsCourse } from './fixtures/apiRoutes';

const expect = baseExpect.configure({ timeout: 30_000 });
const teacher = { username: 'T1', role: 'teacher' };
const student = { username: 'S1', role: 'student' };
const key = (user = teacher) => `edu-ai-resume:v1:${user.role}:${user.username}`;
const courseTitle = '数据结构';
async function setup(page: Page, user = teacher, title = courseTitle) {
  await installTeacherApiRoutes(page);
  await page.route('**/api/courses/course-physics/classrooms?*', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/auth/verify', (route) => route.fulfill({ json: { valid: true, user } }));
  await page.route('**/api/courses', (route) => route.fulfill({ json: [{ ...physicsCourse, title, membership_role: user.role === 'student' ? 'student' : 'editor' }] }));
  await page.route('**/api/courses/course-physics', (route) => route.fulfill({ json: { ...physicsCourse, title, membership_role: user.role === 'student' ? 'student' : 'editor' } }));
  await page.route('**/knowledge-graph', (route) => route.fulfill({ json: { root: { id: 'root', label: title, children: [{ id: 'array', label: '数组' }, { id: 'list', label: '链表' }] } } }));
  await page.addInitScript((user) => {
    if (!localStorage.getItem('edu-ai-auth')) localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user }));
    localStorage.setItem('stitch-theme', 'ocean');
  }, user);
}
async function go(page: Page, hash: string) { await page.evaluate((hash) => { window.location.hash = hash; }, hash); }
async function recorded(page: Page, user = teacher, scope?: string) {
  await expect.poll(async () => page.evaluate(({ key, scope }) => {
    const record = JSON.parse(localStorage.getItem(key) || 'null');
    return scope ? record?.params.scopeId : record?.courseId;
  }, { key: key(user), scope }), { timeout: 30_000 }).toBe(scope || 'course-physics');
}
async function seed(page: Page, user = teacher, route = 'ai', params: Record<string, string> = { scopeType: 'knowledge_point', scopeId: 'array' }) {
  await page.addInitScript(({ key, route, params }) => {
    if (!localStorage.getItem(key)) localStorage.setItem(key, JSON.stringify({ version: 1, courseId: 'course-physics', route, params, visitedAt: '2026-09-07T08:00:00Z' }));
  }, { key: key(user), route, params });
}
const entry = (page: Page) => page.locator('.resume-entry');

test('teacher records successful scope changes, ignores home/profile, and resumes after refresh', async ({ page }, info) => {
  await setup(page);
  await page.goto('/#ai?course_id=course-physics&scopeType=knowledge_point&scopeId=array');
  await recorded(page, teacher, 'array');
  await go(page, '#ai?course_id=course-physics&scopeType=knowledge_point&scopeId=list');
  await recorded(page, teacher, 'list');
  await go(page, '#profile');
  await expect(page).toHaveURL(/#profile/);
  await go(page, '#home');
  await expect(entry(page)).toContainText('数据结构 · 链表');
  await expect(page.locator('.teacher-home__main > :first-child')).toHaveClass('resume-entry');
  await expect(entry(page).getByRole('button')).toHaveCount(1);
  await page.reload();
  await expect(entry(page)).toContainText('链表');
  await page.screenshot({ path: info.outputPath('teacher-resume.png') });
  await entry(page).getByRole('button', { name: '继续备课 →' }).click();
  await expect(page).toHaveURL(/#ai\?course_id=course-physics&scopeType=knowledge_point&scopeId=list$/);
});

test('student has one compact entry and restores learning scope', async ({ page }, info) => {
  await setup(page, student);
  await page.goto('/#student-ai?course_id=course-physics&scopeType=knowledge_point&scopeId=array');
  await recorded(page, student, 'array');
  await go(page, '#student-home');
  await expect(entry(page)).toContainText('数据结构 · 数组');
  await expect(page.locator('.student-home > :first-child')).toHaveClass('resume-entry');
  await expect(page.getByText('最近学习', { exact: true })).toHaveCount(0);
  await expect(entry(page).getByRole('button')).toHaveCount(1);
  await expect(page.getByRole('button', { name: '加入课程', exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath('student-resume.png') });
  await entry(page).getByRole('button', { name: '继续学习 →' }).click();
  await expect(page).toHaveURL(/#student-ai\?course_id=course-physics&scopeType=knowledge_point&scopeId=array$/);
});

test('switching authenticated account never displays the prior account history', async ({ page }) => {
  await setup(page); await seed(page); await page.goto('/#home');
  await expect(entry(page)).toContainText('数据结构');
  const next = { username: 'T2', role: 'teacher' };
  await page.route('**/api/auth/verify', (route) => route.fulfill({ json: { valid: true, user: next } }));
  await page.evaluate((user) => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture-2', user })), next);
  await page.reload();
  await expect(page.getByRole('heading', { name: '全部课程' })).toBeVisible();
  await expect(entry(page)).toHaveCount(0);
  expect(await page.evaluate((key) => localStorage.getItem(key), key())).not.toBeNull();
});

for (const kind of ['new', 'corrupt', 'legacy', 'blocked'] as const) {
  test(`${kind} storage does not produce false history or break the home`, async ({ page }) => {
    await setup(page);
    await page.addInitScript(({ kind, key }) => {
      if (kind === 'corrupt') localStorage.setItem(key, '{broken');
      if (kind === 'legacy') localStorage.setItem('edu-ai-student-recent-learning', JSON.stringify({ version: 1, records: [{ courseId: 'course-physics', lastRoute: 'student-ai', visitedAt: new Date().toISOString() }] }));
      if (kind === 'blocked') {
        const get = Storage.prototype.getItem;
        const set = Storage.prototype.setItem;
        Storage.prototype.getItem = function (key) { if (key.startsWith('edu-ai-resume:')) throw new Error('disabled'); return get.call(this, key); };
        Storage.prototype.setItem = function (key, value) { if (key.startsWith('edu-ai-resume:')) throw new Error('disabled'); set.call(this, key, value); };
      }
    }, { kind, key: key() });
    await page.goto('/#home');
    await expect(page.getByRole('heading', { name: '全部课程' })).toBeVisible();
    await expect(entry(page)).toHaveCount(0);
  });
}

test('course loss clears history, temporary failure preserves it and offers retry', async ({ page }) => {
  await setup(page); await seed(page);
  let status = 503;
  await page.route('**/api/courses/course-physics', (route) => status === 200 ? route.fulfill({ json: { ...physicsCourse, title: courseTitle } }) : route.fulfill({ status, json: { detail: 'fixture error' } }));
  await page.goto('/#home');
  await expect(entry(page).getByRole('button', { name: '重试' })).toBeVisible();
  expect(await page.evaluate((key) => localStorage.getItem(key), key())).not.toBeNull();
  status = 200;
  await entry(page).getByRole('button', { name: '重试' }).click();
  await expect(entry(page)).toContainText('数据结构');
  status = 403;
  await entry(page).getByRole('button', { name: '继续备课 →' }).click();
  await expect(entry(page)).toHaveCount(0);
  expect(await page.evaluate((key) => localStorage.getItem(key), key())).toBeNull();
  await expect(page).toHaveURL(/#home$/);
});

test('missing scope explicitly falls back to the same course', async ({ page }) => {
  await setup(page); await seed(page, teacher, 'ai', { scopeType: 'knowledge_point', scopeId: 'deleted' });
  await page.goto('/#home');
  await expect(entry(page)).toContainText('原位置已不可用');
  await entry(page).getByRole('button', { name: '继续备课 →' }).click();
  await expect(page).toHaveURL(/#course-detail\?course_id=course-physics$/);
});

test('unsafe stored route is hidden; unknown fields never appear in restored URLs', async ({ page }) => {
  await setup(page); await seed(page, teacher, 'https://evil.test', {});
  await page.goto('/#home');
  await expect(page.getByRole('heading', { name: '全部课程' })).toBeVisible();
  await expect(entry(page)).toHaveCount(0);
  await page.evaluate((key) => localStorage.setItem(key, JSON.stringify({ version: 1, courseId: 'course-physics', route: 'ai', params: { scopeType: 'knowledge_point', scopeId: 'array', token: 'secret', redirect: 'https://evil.test' }, visitedAt: new Date().toISOString() })), key());
  await page.reload();
  await entry(page).getByRole('button', { name: '继续备课 →' }).click();
  await expect(page).toHaveURL(/#ai\?course_id=course-physics&scopeType=knowledge_point&scopeId=array$/);
});

for (const user of [teacher, student]) {
  test(`${user.role} long course name stays readable at 390px and supports keyboard`, async ({ page }, info) => {
    await setup(page, user, '数据结构与算法设计'.repeat(12));
    await seed(page, user, user.role === 'student' ? 'student-ai' : 'ai');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(user.role === 'student' ? '/#student-home' : '/#home');
    await expect(entry(page).getByRole('button')).toBeEnabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect((await entry(page).boundingBox())!.height).toBeLessThan(140);
    await expect(entry(page).locator('strong')).toHaveText('数据结构与算法设计'.repeat(12));
    const button = entry(page).getByRole('button');
    await button.focus();
    await expect(button).toBeFocused();
    expect(await button.evaluate((element) => getComputedStyle(element).outlineStyle)).toBe('solid');
    await page.screenshot({ path: info.outputPath(`${user.role}-resume-390.png`) });
    await button.press('Enter');
    await expect(page).toHaveURL(/scopeId=array$/);
  });
}

test('resource URL survives refresh and deletion falls back without choosing another material', async ({ page }) => {
  await setup(page);
  await page.goto('/#resources?course_id=course-physics&material_type=report&material_id=report-mechanics');
  await recorded(page);
  await go(page, '#home');
  await expect(entry(page)).toContainText('数据结构');
  await page.reload();
  await entry(page).getByRole('button', { name: '继续备课 →' }).click();
  await expect(page).toHaveURL(/#resources\?course_id=course-physics&material_type=report&material_id=report-mechanics$/);
  await go(page, '#home');
  await expect(entry(page).getByRole('button')).toBeEnabled();
  await page.route('**/api/courses/course-physics/materials?space=mine', (route) => route.fulfill({ json: [] }));
  await entry(page).getByRole('button', { name: '继续备课 →' }).click();
  await expect(entry(page)).toContainText('原位置已不可用');
  await expect(page).toHaveURL(/#home$/);
  await entry(page).getByRole('button', { name: '继续备课 →' }).click();
  await expect(page).toHaveURL(/#course-detail\?course_id=course-physics$/);
});

test('failed course and failed scope visits never overwrite the prior valid location', async ({ page }) => {
  await setup(page);
  await page.goto('/#ai?course_id=course-physics&scopeType=knowledge_point&scopeId=array');
  await recorded(page, teacher, 'array');
  await go(page, '#ai?course_id=course-physics&scopeType=knowledge_point&scopeId=deleted');
  await go(page, '#home');
  await expect(entry(page)).toContainText('数组');
  await page.route('**/api/courses/forbidden', (route) => route.fulfill({ status: 403, json: { detail: '无权访问' } }));
  await go(page, '#course-detail?course_id=forbidden');
  await expect(page.getByRole('heading', { name: '当前账号无权访问' })).toBeVisible();
  await go(page, '#home');
  await expect(entry(page)).toContainText('数组');
});

test('classroom replaceState updates are tracked and canonical route restores the exact resource', async ({ page }) => {
  await setup(page);
  await page.goto('/#classroom-studio?course_id=course-physics');
  await recorded(page);
  await page.evaluate(() => history.replaceState(null, '', '#teacher-classroom-studio?course_id=course-physics&node_id=mechanics&resource_id=standard-mechanics-classroom'));
  await expect.poll(() => page.evaluate((key) => JSON.parse(localStorage.getItem(key) || 'null')?.params.resource_id, key()), { timeout: 30_000 }).toBe('standard-mechanics-classroom');
  await go(page, '#home');
  await entry(page).getByRole('button', { name: '继续备课 →' }).click();
  await expect(page).toHaveURL(/#classroom-studio\?course_id=course-physics&node_id=mechanics&resource_id=standard-mechanics-classroom$/);
});
