import { test, expect } from 'playwright/test';
test('background preparation allows questions; delivery never switches reading; revision is personal', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'alice', user: { username: 'alice', role: 'student' } })));
  await page.goto('/#/classroom/learning-fixture?resource=a-core');
  const ask = async (text: string) => {
    await page.getByRole('textbox', { name: '向学习 Agent 提问' }).fill(text);
    await page.getByRole('button', { name: '发送问题' }).click();
  };
  await ask('请生成并保存一份变量补充文档');
  await expect(page.getByRole('log').getByText('准备任务已接收，可以继续学习，完成后从资料准备通知打开。', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '节点 B 核心文档', exact: true }).click();
  await ask('解释这个节点');
  await expect(page.getByRole('log').getByText('已回答：解释这个节点', { exact: true })).toBeVisible();
  const notices = page.getByRole('region', { name: '资料准备通知' });
  await expect(notices.locator('summary')).toContainText('1 条未读');
  await expect(page.getByRole('combobox', { name: '对话知识点' })).toHaveValue('b');
  await notices.locator('summary').click();
  await expect(notices.getByText('新资料已准备好', { exact: true })).toBeVisible();
  await notices.getByRole('button', { name: '打开新资料 · v1', exact: true }).click();
  await expect(page.getByRole('combobox', { name: '对话知识点' })).toHaveValue('a');
  await expect(page.frameLocator('iframe.sl-live-material').getByRole('heading', { name: '变量的新例子' })).toBeVisible();
  await ask('请修改当前这份文档，增加一个例子并保存个人版本');
  await expect(notices.getByText('新资料已准备好', { exact: true })).toHaveCount(2, { timeout: 20000 });
  await expect(page.frameLocator('iframe.sl-live-material').getByRole('heading', { name: '变量的新例子' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: '节点 A 核心文档', exact: true })).toBeVisible();
});
