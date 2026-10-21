import { test, expect, type Page } from 'playwright/test';

async function login(page: Page, owner = 'bob') {
  await page.addInitScript(owner => localStorage.setItem('edu-ai-auth',
    JSON.stringify({ token: owner, user: { username: owner, role: 'student' } })), owner);
  await page.goto('/#/classroom/learning-fixture?resource=a-core');
  await expect(page.locator('.sl-classroom')).toBeVisible();
}

test('course conversation and draft survive topic switch and refresh; progress header is removed', async ({ page }) => {
  await login(page);
  const log = page.getByRole('log', { name: '当前课程对话记录' });
  await expect(log).toHaveAttribute('data-session-id', /learning-/);
  const sid = await log.getAttribute('data-session-id');
  await expect(page.locator('.sl-directory .sl-route-progress')).toHaveCount(0);
  await expect(page.getByRole('progressbar', { name: '学习进度' })).toHaveCount(0);
  const composer = page.getByRole('textbox', { name: '向学习 Agent 提问' });
  await composer.fill('课程共享标记');
  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(log.getByText('已回答：课程共享标记', { exact: true })).toBeVisible();
  await composer.fill('跨知识点草稿');
  await page.getByRole('button', { name: '节点 B 核心文档', exact: true }).click();
  await expect(log).toHaveAttribute('data-session-id', sid!);
  await expect(log.getByText('已回答：课程共享标记', { exact: true })).toBeVisible();
  await expect(composer).toHaveValue('跨知识点草稿');
  await composer.fill('B 节继续提问');
  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(log.getByText('已回答：B 节继续提问', { exact: true })).toBeVisible();
  await page.reload();
  await expect(log).toHaveAttribute('data-session-id', sid!);
  await expect(log.getByText('已回答：课程共享标记', { exact: true })).toBeVisible();
  await expect(log.getByText('已回答：B 节继续提问', { exact: true })).toBeVisible();
  await expect(log.locator('[data-message-kind="introduction"]')).toHaveCount(1);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: '目录', exact: true }).click();
  await expect(page.locator('.sl-directory')).toBeVisible();
  await expect(page.locator('.sl-directory .sl-route-progress')).toHaveCount(0);
});

test('late answer remains visible across topics with its original source and account isolation', async ({ page, browser }) => {
  await login(page);
  const log = page.getByRole('log');
  await expect(log).toHaveAttribute('data-session-id', /learning-/);
  const sid = await log.getAttribute('data-session-id');
  const accepted = page.waitForResponse(r => r.url().endsWith('/agent-turns') && r.request().method() === 'POST');
  await page.getByRole('textbox', { name: '向学习 Agent 提问' }).fill('慢回答：保留原始引用');
  await page.getByRole('button', { name: '发送问题' }).click();
  expect((await accepted).ok()).toBeTruthy();
  await page.getByRole('button', { name: '节点 B 核心文档', exact: true }).click();
  await expect(log).toHaveAttribute('data-session-id', sid!);
  await expect(log.getByText('已回答：慢回答：保留原始引用', { exact: true })).toBeVisible();
  const answer = log.locator('.sl-chat-bubble').filter({ hasText: '已回答：慢回答：保留原始引用' });
  await expect(answer.getByRole('link')).toContainText('节点 A 核心文档');
  const other = await browser.newContext();
  const alice = await other.newPage();
  await login(alice, 'alice');
  await expect(alice.getByRole('log')).not.toHaveAttribute('data-session-id', sid!);
  await expect(alice.getByRole('log').getByText('已回答：慢回答：保留原始引用', { exact: true })).toHaveCount(0);
  await other.close();
});

test('legacy topic history is retained in the course conversation with stable pagination', async ({ page }) => {
  await login(page, 'alice');
  const log = page.getByRole('log');
  await expect(log.locator('.sl-chat-bubble')).toHaveCount(50);
  for (let i = 0; i < 6; i++) {
    await log.getByRole('button', { name: '加载更早的对话' }).click();
    await expect(log.locator('.sl-chat-bubble')).toHaveCount(Math.min(301, 100 + i * 50));
  }
  await expect(log.getByText('历史问题0', { exact: true })).toHaveCount(1);
  await expect(log.getByText('历史回答149', { exact: true })).toHaveCount(1);
  await expect(log.locator('[data-message-kind="introduction"]')).toHaveCount(1);
  await page.getByRole('button', { name: '节点 B 核心文档', exact: true }).click();
  await expect(log.getByText('历史问题0', { exact: true })).toHaveCount(1);
});
