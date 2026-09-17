import { test, expect, type Page } from 'playwright/test';
async function login(page: Page) {
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'alice', user: { username: 'alice', role: 'student' } })));
  await page.goto('/#/classroom/learning-fixture?resource=a-core');
  await expect(page.locator('.sl-classroom')).toBeVisible();
}
async function ask(page: Page, text: string) {
  await page.getByRole('textbox', { name: '向学习 Agent 提问' }).fill(text);
  await page.getByRole('button', { name: '发送问题' }).click();
}
test('selection and exact resource snapshot are fixed when sending; refresh recovers durable answer', async ({ page }) => {
  await login(page);
  const frame = page.frameLocator('iframe.sl-live-material');
  const paragraph = frame.locator('p').filter({ hasText: '测试正文' }).first();
  await paragraph.waitFor();
  await paragraph.evaluate(el => { const range = document.createRange(); range.selectNodeContents(el); const selection = window.getSelection()!; selection.removeAllRanges(); selection.addRange(range); });
  await expect(page.getByText('将结合选中文本回答', { exact: true })).toBeVisible();
  const accepted = page.waitForRequest(r => r.url().endsWith('/agent-turns') && r.method() === 'POST');
  await ask(page, '慢回答：解释这段内容');
  const request = (await accepted).postDataJSON();
  expect(request.reading_context.selected_text).toContain('测试正文');
  expect(request.reading_context.resource_ref.version).toBe(1);
  await page.reload();
  const log = page.getByRole('log');
  await expect(log.getByText('已回答：慢回答：解释这段内容', { exact: true })).toBeVisible();
  await expect(log.getByText('慢回答：解释这段内容', { exact: true })).toHaveCount(1);
  await expect(log.getByText('来源：节点 A 核心文档 · v1', { exact: true })).toBeVisible();
});
test('late answer stays in original topic; cancel and model failure do not block learning', async ({ page }) => {
  await login(page);
  await ask(page, '慢回答：只属于节点A');
  await expect(page.getByRole('button', { name: '取消本次答疑' })).toBeVisible();
  await page.getByRole('button', { name: '节点 B 核心文档', exact: true }).click();
  await expect(page.getByRole('log').getByText('已回答：慢回答：只属于节点A', { exact: true })).toHaveCount(0);
  await ask(page, '慢回答：取消这一条');
  await page.getByRole('button', { name: '取消本次答疑' }).click();
  await expect(page.getByRole('button', { name: '发送问题' })).toBeDisabled(); // empty composer
  await expect(page.getByRole('button', { name: '取消本次答疑' })).toHaveCount(0);
  await ask(page, '模型失败');
  await expect(page.getByRole('button', { name: '重试本次答疑' })).toBeVisible();
  await expect(page.getByRole('button', { name: '继续学习', exact: true })).toBeEnabled();
  await page.getByRole('button', { name: '节点 A 核心文档', exact: true }).click();
  await expect(page.getByRole('log').getByText('已回答：慢回答：只属于节点A', { exact: true })).toBeVisible();
});
test('retry preserves the original question and publishes only one final answer', async ({ page }) => {
  await login(page);
  await ask(page, '一次失败后重试');
  await expect(page.getByRole('button', { name: '重试本次答疑' })).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: '重试本次答疑' }).click();
  const log = page.getByRole('log');
  await expect(log.getByText('已回答：一次失败后重试', { exact: true })).toBeVisible();
  await expect(log.getByText('一次失败后重试', { exact: true })).toHaveCount(1);
});
