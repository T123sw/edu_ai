import { test, expect } from 'playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'alice', user: { username: 'alice', role: 'student' } })));
});

test('ask second question preserves location and citation opens the same question', async ({ page }) => {
  await page.goto('/#/classroom/learning-fixture?resource=a-quiz');
  const frame = page.frameLocator('iframe.sl-live-material');
  await frame.locator('[data-quiz-question="1"]').getByRole('button', { name: '讲解', exact: true }).click();
  const composer = page.getByRole('textbox', { name: '向学习 Agent 提问' });
  await expect(composer).toBeFocused();
  await composer.fill('慢回答：解释这道乘法题');
  const sending = page.waitForRequest(r => r.url().endsWith('/agent-turns') && r.method() === 'POST');
  await page.getByRole('button', { name: '发送问题' }).click();
  const snapshot = (await sending).postDataJSON().reading_context;
  expect(snapshot.locator).toEqual({ kind: 'quiz', question_index: 1 });
  expect(snapshot.selected_text).toContain('第二题乘法');
  await frame.locator('[data-quiz-question="0"]').getByRole('button', { name: '讲解', exact: true }).click();
  const citation = page.getByRole('link', { name: /来源：定位练习/ }).last();
  await expect(citation).toHaveAttribute('href', /question_index=1/);
  const popupPromise = page.waitForEvent('popup');
  await citation.click();
  const popup = await popupPromise;
  await expect(popup.locator('[data-quiz-question="1"]')).toHaveClass('report-reference-fallback');
  await expect(popup.locator('[data-quiz-question="1"]')).toContainText('第二题乘法');
  await expect(popup.locator('[data-quiz-question="1"]')).toBeInViewport();
  await popup.close();
  await page.getByRole('button', { name: '取消引用' }).click();
  await expect(page.getByRole('note', { name: '已引用报告片段' })).toHaveCount(0);
});

test('late report passage retrieval opens a highlighted source and stale anchor is explicit', async ({ page }) => {
  await page.goto('/#/classroom/learning-fixture?resource=a-core');
  await expect(page.frameLocator('iframe.sl-live-material').getByText('背景介绍。', { exact: true }).first()).toBeVisible();
  await page.getByRole('textbox', { name: '向学习 Agent 提问' }).fill('递归终止条件是什么？');
  await page.getByRole('button', { name: '发送问题' }).click();
  const citation = page.getByRole('link', { name: /来源：长篇递归报告/ }).last();
  await expect(citation).toHaveAttribute('href', /block_id=report-v1/);
  const popupPromise = page.waitForEvent('popup');
  await citation.click();
  const popup = await popupPromise;
  await expect(popup.locator('.report-reference-fallback')).toContainText('递归终止条件是 n 等于零');
  await expect(popup.locator('.report-reference-fallback')).toBeInViewport();
  const stale = popup.url().replace(/block_id=[^&]+/, 'block_id=report-v1%3A1%3A20%3A00000000');
  await popup.goto(stale);
  await popup.reload();
  await expect(popup.getByRole('alert')).toContainText('引用段落位置不可用');
  await expect(popup.locator('.report-reference-fallback')).toHaveCount(0);
});
