import { test, expect, type Page } from 'playwright/test';
async function login(page: Page, owner = 'alice') {
  await page.addInitScript(owner => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: owner, user: { username: owner, role: 'student' } })), owner);
  await page.goto('/#/classroom/learning-fixture?resource=a-core');
  await expect(page.locator('.sl-classroom')).toBeVisible();
}
test('quiet reading, acknowledged completion, self assessment, refresh and undo', async ({ page }) => {
  await login(page);
  const reader = page.frameLocator('iframe.sl-live-material');
  const endSaved = page.waitForResponse(r => r.url().endsWith('/events') && r.request().postDataJSON()?.type === 'resource_end_reached' && r.status() === 200);
  await reader.locator('[data-reading-end]').scrollIntoViewIfNeeded();
  await endSaved;
  await expect(page.getByText('资料已学完，理解尚未验证', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '本资料已学完', exact: true }).click();
  await expect(page.getByText('资料已学完，理解尚未验证', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /全局学习记忆/ }).click();
  await page.getByLabel('当前知识点的理解程度').selectOption('understood');
  await expect(page.getByLabel('当前知识点的理解程度')).toHaveValue('understood');
  await page.reload();
  await expect(page.getByText('资料已学完，理解尚未验证', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '撤销学完', exact: true }).click();
  await expect(page.getByRole('button', { name: '本资料已学完', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: '继续学习', exact: true }).click();
  await expect(page).toHaveURL(/resource=a-extra/);
  await expect(page.getByRole('log').locator('[data-message-kind="user"]')).toHaveCount(0);
});
test('offline completion retains event identity across reload, navigation stays available', async ({ page }) => {
  await login(page, 'bob');
  let blocked = true;
  const ids: string[] = [];
  await page.route('**/topics/*/events', async route => {
    const body = route.request().postDataJSON();
    if (body.type === 'resource_completion_set') { ids.push(body.event_id); if (blocked) { await route.abort(); return; } }
    await route.continue();
  });
  await page.getByRole('button', { name: '本资料已学完', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: '学习记录未同步' })).toBeVisible();
  await expect(page.getByRole('button', { name: '继续学习', exact: true })).toBeEnabled();
  await page.reload();
  await expect(page.getByRole('alert').filter({ hasText: '学习记录未同步' })).toBeVisible();
  blocked = false;
  await page.getByRole('button', { name: '重试保存', exact: true }).click();
  await expect(page.getByText('资料已学完，理解尚未验证', { exact: true })).toBeVisible();
  expect(ids.length).toBeGreaterThan(1);
  expect(new Set(ids).size).toBe(1);
  await page.getByRole('button', { name: '撤销学完', exact: true }).click();
  await expect(page.getByRole('button', { name: '本资料已学完', exact: true })).toBeEnabled();
});
test('model failure does not block completion or continuing', async ({ page }) => {
  await login(page);
  await page.getByRole('textbox', { name: '向学习 Agent 提问' }).fill('模型失败');
  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(page.locator('.sl-agent [role="alert"]').filter({ hasText: /失败/ })).toBeVisible();
  await page.getByRole('button', { name: '本资料已学完', exact: true }).click();
  await expect(page.getByText('资料已学完，理解尚未验证', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '继续学习', exact: true }).click();
  await expect(page).toHaveURL(/resource=a-extra/);
});
test('optional material does not prevent core completion and next-topic navigation', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'alice', user: { username: 'alice', role: 'student' } })));
  await page.goto('/#/classroom/manifest-fixture?resource=core');
  await page.getByRole('button', { name: '本资料已学完', exact: true }).click();
  await expect(page.getByText('资料已学完，理解尚未验证', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: /全局学习记忆/ }).click();
  await expect(page.getByText('核心资料 1/1 · 理解尚未验证', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '继续学习', exact: true }).click();
  await expect(page).toHaveURL(/resource=next/);
});
test('pending completion waits for receipt; account switch never sends old queue', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: '节点 B 核心文档', exact: true }).click();
  await page.route('**/topics/*/events', async route => {
    if (route.request().postDataJSON().type === 'resource_completion_set') { await route.abort(); return; }
    await route.continue();
  });
  await page.getByRole('button', { name: '本资料已学完', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: '学习记录未同步' })).toBeVisible();
  await expect(page.getByText('资料已学完，理解尚未验证', { exact: true })).toHaveCount(0);
  await page.unroute('**/topics/*/events');
  const sent: string[] = [];
  page.on('request', r => { if (r.url().endsWith('/events') && r.postDataJSON()?.type === 'resource_completion_set') sent.push(r.postDataJSON().event_id); });
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'bob', user: { username: 'bob', role: 'student' } })));
  await page.reload();
  await expect(page.getByRole('button', { name: '本资料已学完', exact: true })).toBeEnabled();
  await page.waitForTimeout(5500);
  expect(sent).toEqual([]);
});
test('material version mismatch does not emit reading observations', async ({ page }) => {
  await page.route('**/materials/report/a-extra/versions/1', async route => {
    const response = await route.fetch();
    await route.fulfill({ response, json: { ...(await response.json()), version: 2 } });
  });
  const observations: string[] = [];
  page.on('request', r => { if (r.url().endsWith('/events') && r.postDataJSON()?.resource_ref?.material_id === 'a-extra') observations.push(r.postDataJSON().type); });
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'alice', user: { username: 'alice', role: 'student' } })));
  await page.goto('/#/classroom/learning-fixture?resource=a-extra');
  await expect(page.frameLocator('iframe.sl-live-material').getByRole('alert')).toContainText('资料版本已变化');
  expect(observations).toEqual([]);
});
test('another device revision is surfaced and never silently overwritten', async ({ page }) => {
  await login(page, 'bob');
  await page.getByRole('button', { name: '节点 B 核心文档', exact: true }).click();
  const ref = { course_id: 'learning-fixture', material_type: 'report', material_id: 'b-core', version: 1 };
  const response = await page.request.post('http://127.0.0.1:8016/api/self-learning/courses/learning-fixture/topics/b/events', {
    headers: { Authorization: 'Bearer bob' }, data: { schema_version: 1, event_id: crypto.randomUUID(), type: 'resource_completion_set', manifest_ref: null,
      resource_ref: ref, expected_revision: 0, occurred_at: new Date().toISOString(), payload: { completed: true } },
  });
  expect(response.status()).toBe(200);
  await page.getByRole('button', { name: '本资料已学完', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: '完成记录已在其他页面更新' })).toBeVisible();
  await expect(page.getByRole('button', { name: '继续学习', exact: true })).toBeEnabled();
  await page.reload();
  await expect(page.getByRole('alert').filter({ hasText: '上次操作存在冲突' })).toBeVisible();
  await page.getByRole('button', { name: '放弃冲突操作并刷新', exact: true }).click();
  await expect(page.getByText('资料已学完，理解尚未验证', { exact: true })).toBeVisible();
});
test('phone layout keeps saved status and continuing visible', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, 'bob');
  await page.getByRole('button', { name: '本资料已学完', exact: true }).click();
  await expect(page.getByText('资料已学完，理解尚未验证', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '继续学习', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
