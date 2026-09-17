import { test, expect } from 'playwright/test';
test('explicit course preference can be changed and deleted; another account cannot see it', async ({ page }) => {
  await page.addInitScript(() => !localStorage.getItem('edu-ai-auth') && localStorage.setItem('edu-ai-auth', JSON.stringify({ token:'alice', user:{ username:'alice', role:'student' } })));
  await page.goto('/#/classroom/learning-fixture?resource=b-core');
  await page.getByText('检查与学习偏好', { exact:true }).click();
  await page.getByLabel('偏好内容', { exact:true }).fill('先给一个具体例子');
  await page.getByRole('button', { name:'保存学习偏好', exact:true }).click();
  await expect(page.getByText('当前设置：先给一个具体例子', { exact:true })).toBeVisible();
  await page.reload();
  await page.getByText('检查与学习偏好', { exact:true }).click();
  await expect(page.getByText('当前设置：先给一个具体例子', { exact:true })).toBeVisible();
  await page.getByRole('button', { name:'删除这项偏好', exact:true }).click();
  await expect(page.getByText('当前设置：未设置', { exact:true })).toBeVisible();
  await page.evaluate(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token:'bob', user:{ username:'bob', role:'student' } })));
  await page.goto('/#/classroom/learning-fixture?resource=a-core');
  await page.reload();
  await page.getByText('检查与学习偏好', { exact:true }).click();
  await expect(page.getByText('当前设置：未设置', { exact:true })).toBeVisible();
});

test('the actual personal center exposes global learning preferences', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token:'bob', user:{ username:'bob', role:'student' } })));
  await page.goto('/?account=1#/profile');
  const preferences = page.getByRole('region', { name:'学习偏好', exact:true });
  await expect(preferences).toBeVisible();
  await preferences.getByLabel('偏好内容', { exact:true }).fill('先说明思路');
  await preferences.getByRole('button', { name:'保存学习偏好', exact:true }).click();
  await expect(preferences.getByText('当前设置：先说明思路', { exact:true })).toBeVisible();
  await preferences.getByRole('button', { name:'删除这项偏好', exact:true }).click();
  await expect(preferences.getByText('当前设置：未设置', { exact:true })).toBeVisible();
});
