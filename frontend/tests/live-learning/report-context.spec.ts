import { test, expect } from 'playwright/test';

for (const mobile of [false, true]) {
  test(`report paragraph AI entry, pinned quote, clear and snapshot isolation (${mobile ? 'mobile' : 'desktop'})`, async ({ page }) => {
    // Exercise deployed static assets against the isolated fixture, never write to business data.
    if (process.env.REPORT_PRODUCTION_URL) await page.route('**/backend/**', async route => {
      const url = new URL(route.request().url());
      const response = await route.fetch({ url: 'http://127.0.0.1:8019' + url.pathname.replace(/^\/backend/, '') + url.search });
      await route.fulfill({ response });
    });
    // The learning fixture has no global job ledger; classroom polling still reads it.
    await page.route('**/api/jobs?*', route => route.fulfill({ json: { items: [], total: 0 } }));
    if (mobile) await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'alice', user: { username: 'alice', role: 'student' } })));
    await page.goto('/#/classroom/learning-fixture?resource=a-core');
    const frame = page.frameLocator('iframe.sl-live-material');
    const paragraphs = frame.locator('.report-reading p').filter({ hasText: '测试正文' });
    const second = paragraphs.nth(1);
    await second.hover();
    await frame.getByRole('button', { name: '问 AI' }).click();
    const quote = page.getByRole('note', { name: '已引用报告片段' });
    await expect(quote).toContainText('测试正文');
    const composer = page.getByRole('textbox', { name: '向学习 Agent 提问' });
    await expect(composer).toBeFocused();
    await expect(composer).toHaveValue('请解释这段内容。');
    await page.screenshot({ path: test.info().outputPath('report-reference.png'), fullPage: true });
    if (mobile) await page.getByRole('button', { name: '学习', exact: true }).click();
    expect(await second.evaluate(() => (CSS as typeof CSS & { highlights: { has: (key: string) => boolean } }).highlights.has('learning-reference'))).toBe(true);
    if (mobile) await page.getByRole('button', { name: 'Agent', exact: true }).click();
    const question = `慢回答：请解释这段（${mobile ? '手机' : '桌面'}）`;
    await composer.fill(question);
    const sent = page.waitForRequest(r => r.url().endsWith('/agent-turns') && r.method() === 'POST');
    await page.getByRole('button', { name: '发送问题' }).click();
    const snapshot = (await sent).postDataJSON().reading_context;
    expect(snapshot.selected_text).toContain('测试正文');
    expect(snapshot.locator.block_id).toMatch(/^report-v1:/);
    await page.getByRole('button', { name: '取消引用' }).click();
    await expect(quote).toHaveCount(0);
    await expect(page.getByRole('log').getByText('已回答：' + question, { exact: true })).toBeVisible({ timeout: 15000 });
    if (mobile) await page.getByRole('button', { name: '学习', exact: true }).click();
    await paragraphs.first().evaluate(el => { const r = document.createRange(); r.selectNodeContents(el); const s = window.getSelection()!; s.removeAllRanges(); s.addRange(r); });
    await frame.getByRole('button', { name: '问 AI' }).click();
    await expect(quote).toContainText('测试正文');
    const nextQuestion = `解释第一段（${mobile ? '手机' : '桌面'}）`;
    await composer.fill(nextQuestion);
    const next = page.waitForRequest(r => r.url().endsWith('/agent-turns') && r.method() === 'POST');
    await page.getByRole('button', { name: '发送问题' }).click();
    expect((await next).postDataJSON().reading_context.locator.block_id).not.toBe(snapshot.locator.block_id);
    await expect(page.getByRole('log').getByText('已回答：' + nextQuestion, { exact: true })).toBeVisible({ timeout: 15000 });
    if (process.env.REPORT_PRODUCTION_URL) await page.unrouteAll({ behavior: 'wait' });
  });
}
