import { test, expect } from 'playwright/test';
import { readFileSync } from 'node:fs';
const credentials = JSON.parse(readFileSync(process.env.AGENT_CREDENTIALS || '../artifacts/full-application/credentials.json', 'utf8'));
const state = JSON.parse(readFileSync('../artifacts/full-application/state.json', 'utf8'));
const room = process.env.AGENT_ACCEPTANCE_RUN
  ? JSON.parse(readFileSync(`../artifacts/frozen-acceptance/${process.env.AGENT_ACCEPTANCE_RUN}/learning-room.json`, 'utf8'))
  : state.rooms.find((r: any) => r.id === credentials.course_id);

test('real login, report/classroom/quiz, answer and refresh', async ({ page }, info) => {
  const failures: string[] = [];
  page.on('pageerror', error => failures.push(error.message));
  await page.goto('/');
  await page.getByLabel('账号', { exact: true }).fill(credentials.username);
  await page.getByLabel('密码', { exact: true }).fill(credentials.password);
  await page.getByRole('button', { name: /^登\s*录$/ }).click();
  await expect(page.getByRole('heading', { name: '最近学习' })).toBeVisible();
  const first = room.chapters[0];
  const report = first.resources.find((r: any) => r.remote.materialType === 'report');
  await page.goto(`/#/classroom/${room.id}?resource=${report.id}`);
  const frame = page.frameLocator('iframe.sl-live-material');
  await expect(frame.locator('[data-reading-end]')).toBeAttached();
  await expect(page.getByRole('log', { name: '当前课程对话记录' })).toBeVisible();
  await page.screenshot({ path: info.outputPath('report.png') });
  const before = await page.getByRole('log').locator('[data-message-kind="assistant_content"]').count();
  await page.getByRole('textbox', { name: '向学习 Agent 提问' }).fill('请基于这份资料解释模型与工具执行程序的职责，给一个天气查询的面试回答例子。不需要生成新资料。');
  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(page.getByRole('log').locator('[data-message-kind="assistant_content"]')).toHaveCount(before + 1, { timeout: 180000 });
  await page.reload();
  await expect(page.getByRole('log').locator('[data-message-kind="assistant_content"]')).toHaveCount(before + 1);
  const classroom = first.resources.find((r: any) => r.remote.materialType === 'classroom');
  await page.goto(`/#/classroom/${room.id}?resource=${classroom.id}`);
  await expect(frame.getByRole('button', { name: '播放当前页', exact: true })).toBeVisible();
  await frame.getByRole('button', { name: '播放当前页', exact: true }).click();
  await page.screenshot({ path: info.outputPath('classroom.png') });
  const quiz = first.resources.find((r: any) => r.remote.materialType === 'quiz');
  await page.goto(`/#/classroom/${room.id}?resource=${quiz.id}`);
  await expect(frame.getByRole('button', { name: '保存作答' }).first()).toBeVisible();
  const question = frame.locator('fieldset:has(input[type="radio"]), fieldset:has(input[type="checkbox"])').first();
  await question.locator('input[type="radio"], input[type="checkbox"]').first().check();
  await question.getByRole('button', { name: '保存作答' }).click();
  await expect(frame.getByRole('status').first()).toContainText(/本题|答案已保存/);
  await page.screenshot({ path: info.outputPath('quiz-attempt.png') });
  await page.reload();
  await expect(frame.getByRole('status').first()).toContainText(/本题|答案已保存/);
  expect(failures).toEqual([]);
});


test('all committed core resources render at their recorded versions', async ({ page }, info) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await page.getByLabel('账号', { exact: true }).fill(credentials.username);
  await page.getByLabel('密码', { exact: true }).fill(credentials.password);
  await page.getByRole('button', { name: /^登\s*录$/ }).click();
  await expect(page.getByRole('heading', { name: '最近学习' })).toBeVisible();
  for (const chapter of room.chapters) {
    for (const resource of chapter.resources.filter((r: any) => r.ready)) {
      await page.goto(`/#/classroom/${room.id}?resource=${resource.id}`);
      const frame = page.frameLocator('iframe.sl-live-material');
      if (resource.remote.materialType === 'classroom') {
        await expect(frame.getByRole('button', { name: '播放当前页', exact: true })).toBeVisible();
        await frame.getByRole('button', { name: '播放当前页', exact: true }).click();
      } else if (resource.remote.materialType === 'quiz') {
        await expect(frame.getByRole('button', { name: '保存作答' }).first()).toBeVisible();
      } else await expect(frame.locator('[data-reading-end]')).toBeAttached();
      await page.screenshot({ path: info.outputPath(`${chapter.id}-${resource.remote.materialType}-${resource.remote.version}.png`) });
    }
  }
  expect(errors).toEqual([]);
});
