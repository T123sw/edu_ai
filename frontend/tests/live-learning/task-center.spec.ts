import { test, expect } from 'playwright/test';
import { seedState } from '../../src/selfLearning/model';

for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
  test(`task center filters, progress, retry and keyboard ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    const state = seedState();
    const course = state.rooms[0];
    const statuses = ['running', 'queued', 'cancel_requested', 'failed', 'partially_succeeded', 'canceled', 'succeeded'];
    const jobs = statuses.map((status, i) => ({ edu_job_id: `test-job-${i}`, kind: i % 2 ? 'generate_report' : 'generate_classroom', status, course_id: course.id, progress: status === 'queued' ? -8 : 62, retryable: status === 'failed', message: status === 'running' ? '正在为你整理课程内容与讲解。' : '', error_message: status === 'failed' ? '生成服务暂时不可用，请稍后重试。' : '' }));
    let retries = 0;
    const errors: string[] = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ user: { username: 'design-test', role: 'teacher' }, token: 'mock-only' })));
    await page.route('**/api/**', async route => {
      const url = route.request().url();
      if (url.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'design-test', role: 'teacher' } } });
      if (url.endsWith('/self-learning/state')) return route.fulfill({ json: { ...state, shared: [], serverJobs: jobs } });
      if (url.endsWith('/retry')) {
        retries++;
        await new Promise(resolve => setTimeout(resolve, 250));
        return route.fulfill({ status: retries === 1 ? 503 : 200, json: retries === 1 ? { detail: '暂时无法重试，请稍后再试。' } : { ok: true } });
      }
      return route.fulfill({ status: 404, json: { detail: 'Unexpected test request' } });
    });
    await page.goto('/');
    const launcher = page.getByRole('button', { name: '后台任务，3 项进行中', exact: true });
    await launcher.click();
    const dialog = page.getByRole('dialog', { name: '后台任务' });
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('.sl-task-card')).toHaveCount(7);
    await expect(dialog.locator('.sl-task-card').nth(1).getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0');
    const box = await dialog.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height);
    expect(await dialog.evaluate(e => e.scrollWidth <= e.clientWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath('tasks-all.png') });
    const filters = dialog.locator('.sl-task-filters');
    await filters.getByRole('button', { name: /进行中/ }).click();
    await expect(dialog.locator('.sl-task-card')).toHaveCount(3);
    await filters.getByRole('button', { name: /需处理/ }).click();
    await expect(dialog.locator('.sl-task-card')).toHaveCount(3);
    await dialog.getByText('查看失败原因', { exact: true }).first().click();
    await expect(dialog.getByText('生成服务暂时不可用，请稍后重试。', { exact: true })).toBeVisible();
    await page.screenshot({ path: info.outputPath('tasks-failed.png') });
    await dialog.getByRole('button', { name: '重新尝试' }).click();
    await expect(dialog.getByRole('button', { name: '正在提交…' })).toBeDisabled();
    await expect(dialog.getByRole('alert')).toHaveText('暂时无法重试，请稍后再试。');
    await dialog.getByRole('button', { name: '重新尝试' }).click();
    await expect(dialog.getByRole('status')).toHaveText('已提交重试');
    expect(retries).toBe(2);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    await expect(launcher).toBeFocused();
    await launcher.click();
    await filters.getByRole('button', { name: /已完成/ }).click();
    await expect(dialog.locator('.sl-task-card')).toHaveCount(1);
    await expect(dialog.getByRole('progressbar')).toHaveCount(0);
    await dialog.getByRole('link', { name: '进入课堂' }).click();
    await expect(dialog).toHaveCount(0);
    await expect(page).toHaveURL(new RegExp(course.id));
    expect(errors).toEqual([]);
  });
}

test('task center empty state', async ({ page }, info) => {
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ user: { username: 'design-test', role: 'teacher' }, token: 'mock-only' })));
  await page.route('**/api/**', route => route.fulfill({ json: route.request().url().endsWith('/auth/verify') ? { valid: true, user: { username: 'design-test', role: 'teacher' } } : { ...seedState(), shared: [], serverJobs: [] } }));
  await page.goto('/');
  await page.getByRole('button', { name: '后台任务', exact: true }).click();
  await expect(page.getByRole('heading', { name: '还没有生成任务' })).toBeVisible();
  await page.screenshot({ path: info.outputPath('tasks-empty.png') });
  await page.getByRole('button', { name: '关闭弹窗' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
});
