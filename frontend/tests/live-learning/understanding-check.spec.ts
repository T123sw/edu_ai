import { test, expect } from 'playwright/test';
test('checks are optional; wrong answer survives reload without claiming mastery', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token:'alice', user:{ username:'alice', role:'student' } })));
  await page.goto('/#/classroom/learning-fixture?resource=a-core');
  await page.getByText('检查与学习偏好', { exact: true }).click();
  await page.getByRole('button', { name:'开始理解检查', exact:true }).click();
  await expect(page.getByText('哪一个是变量赋值？', { exact:true })).toBeVisible();
  await expect(page.getByText('赋值把值绑定给变量。', { exact:true })).toHaveCount(0);
  await page.getByLabel('print(x)', { exact:true }).check();
  await page.getByRole('button', { name:'提交检查答案', exact:true }).click();
  await expect(page.getByText('客观批改 · 建议回顾本题', { exact:true })).toBeVisible();
  await page.reload();
  await page.getByText('检查与学习偏好', { exact:true }).click();
  await expect(page.getByText('客观批改 · 建议回顾本题', { exact:true })).toBeVisible();
  await expect(page.getByRole('button', { name:'继续学习', exact:true })).toBeEnabled();
  await page.getByRole('button', { name:'再来一道检查', exact:true }).click();
  await page.getByRole('button', { name:'跳过这道检查', exact:true }).click();
  await expect(page.getByText('已跳过，未产生理解证据。', { exact:true })).toBeVisible();
});
