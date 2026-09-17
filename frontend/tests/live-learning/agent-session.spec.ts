import { test, expect, type Page } from 'playwright/test';

async function login(page: Page, owner = 'alice') {
  await page.addInitScript(owner => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: owner, user: { username: owner, role: 'student' } })), owner);
  await page.goto('/#/classroom/learning-fixture?resource=a-core');
  await expect(page.getByRole('heading', { name: '课堂目录' })).toBeVisible();
}

test('A B A, same-topic material switch and refresh preserve one session/introduction', async ({ page }) => {
  await login(page);
  const log = page.getByRole('log', { name: '当前知识点对话记录' });
  await expect(log.locator('[data-message-kind="introduction"]')).toHaveCount(1);
  const idA = await log.getAttribute('data-session-id');
  await page.getByRole('textbox', { name: '向学习 Agent 提问' }).fill('P1会话唯一问题');
  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(log.getByText('已回答：P1会话唯一问题', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '节点 A 补充文档', exact: true }).click();
  await expect(log).toHaveAttribute('data-session-id', idA!);
  await expect(log.getByText('已回答：P1会话唯一问题', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '节点 B 核心文档', exact: true }).click();
  await expect(log.locator('[data-message-kind="introduction"]')).toHaveCount(1);
  await expect(log).not.toHaveAttribute('data-session-id', idA!);
  await expect(log.getByText('P1会话唯一问题', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '节点 A 核心文档', exact: true }).click();
  await page.reload();
  await expect(log).toHaveAttribute('data-session-id', idA!);
  await expect(log.locator('[data-message-kind="introduction"]')).toHaveCount(1);
  await expect(log.getByText('已回答：P1会话唯一问题', { exact: true })).toBeVisible();
});

test('late answer remains in original topic and another account cannot see it', async ({ page, browser }) => {
  await login(page);
  const log = page.getByRole('log', { name: '当前知识点对话记录' });
  await expect(log).toHaveAttribute('data-session-id', /learning-/);
  const idA = await log.getAttribute('data-session-id');
  await page.getByRole('textbox', { name: '向学习 Agent 提问' }).fill('慢回答-原节点');
  await page.getByRole('button', { name: '发送问题' }).click();
  await page.getByRole('button', { name: '节点 B 核心文档', exact: true }).click();
  await expect(log).not.toHaveAttribute('data-session-id', idA!);
  await page.waitForTimeout(2500);
  await expect(log.getByText('已回答：慢回答-原节点', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '节点 A 核心文档', exact: true }).click();
  await expect(log.getByText('已回答：慢回答-原节点', { exact: true })).toBeVisible();
  const other = await browser.newContext();
  const bob = await other.newPage();
  await login(bob, 'bob');
  await expect(bob.getByRole('log')).not.toHaveAttribute('data-session-id', idA!);
  await expect(bob.getByText('已回答：慢回答-原节点', { exact: true })).toHaveCount(0);
  await other.close();
});

test('150 stored turns can be paged all the way back without duplicates', async ({ page }) => {
  await login(page);
  await page.getByRole('button', { name: '长历史文档', exact: true }).click();
  const log = page.getByRole('log', { name: '当前知识点对话记录' });
  await expect(log.locator('.sl-chat-bubble')).toHaveCount(50);
  for (let i = 0; i < 6; i++) {
    await log.getByRole('button', { name: '加载更早的对话' }).click();
    await expect(log.locator('.sl-chat-bubble')).toHaveCount(Math.min(301, 100 + i * 50));
  }
  await expect(log.locator('[data-message-kind="introduction"]')).toHaveCount(1);
  await expect(log.getByText('历史问题0', { exact: true })).toHaveCount(1);
  await expect(log.getByText('历史回答149', { exact: true })).toHaveCount(1);
  await expect(log.getByRole('button', { name: '加载更早的对话' })).toHaveCount(0);
});
