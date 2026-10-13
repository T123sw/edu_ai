import { test, expect } from 'playwright/test';

test('PPT question freezes page, sentence and focus across pause, navigation and replay', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'alice', user: { username: 'alice', role: 'student' } }));
    class FixtureAudio extends EventTarget {
      duration = 30; currentTime = 0;
      constructor() { super(); (window as unknown as { fixtureAudio: FixtureAudio }).fixtureAudio = this; }
      play() { return Promise.resolve(); }
      pause() {}
    }
    Object.defineProperty(window, 'Audio', { value: FixtureAudio });
    window.addEventListener('message', e => {
      if (e.data?.type === 'learning-reading-context') (window as unknown as { reading: unknown }).reading = e.data;
    });
  });
  await page.goto('/#/classroom/learning-fixture?resource=b-ppt');
  const frame = page.frameLocator('iframe.sl-live-material');
  await expect(frame.getByRole('region', { name: '课堂舞台' })).toBeVisible();
  const reading = () => page.evaluate(() => (window as unknown as { reading: { locator: { scene_id: string }; classroom: { status: string; lecture?: { scene_id: string; sentence_index?: number; highlighted_element_ids: string[] } } } }).reading);
  await expect.poll(async () => (await reading())?.classroom).toEqual({ status: 'idle' });
  await frame.getByRole('button', { name: '播放当前页', exact: true }).click();
  await expect.poll(async () => (await reading())?.classroom.lecture?.sentence_index).toBe(0);
  await frame.locator('body').evaluate(() => {
    const audio = (window as unknown as { fixtureAudio: { currentTime: number; dispatchEvent: (e: Event) => void } }).fixtureAudio;
    audio.currentTime = 15; audio.dispatchEvent(new Event('timeupdate'));
  });
  await expect.poll(async () => (await reading())?.classroom.lecture?.sentence_index).toBe(1);
  await frame.getByRole('button', { name: '暂停', exact: true }).click();
  await expect.poll(async () => (await reading())?.classroom.status).toBe('paused');
  expect((await reading()).classroom.lecture?.highlighted_element_ids).toEqual(['text-1']);
  await frame.getByRole('button', { name: '下一页', exact: true }).click();
  await expect.poll(async () => (await reading())?.locator.scene_id).toBe('ppt-2');
  expect((await reading()).classroom.lecture?.scene_id).toBe('ppt-1');

  await page.getByRole('textbox', { name: '向学习 Agent 提问' }).fill('慢回答：刚才那句话是什么意思？');
  const accepted = page.waitForRequest(r => r.url().endsWith('/agent-turns') && r.method() === 'POST');
  await page.getByRole('button', { name: '发送问题' }).click();
  const snapshot = (await accepted).postDataJSON().reading_context;
  expect(snapshot.locator.scene_id).toBe('ppt-2');
  expect(snapshot.classroom.lecture).toMatchObject({ scene_id: 'ppt-1', speech_action_id: 'speech-1', sentence_index: 1 });
  await frame.getByRole('button', { name: '上一页', exact: true }).click();
  await expect(page.getByRole('log').getByText('已回答：慢回答：刚才那句话是什么意思？', { exact: true })).toBeVisible({ timeout: 15000 });
  await frame.getByRole('button', { name: '播放当前页', exact: true }).click();
  await expect.poll(async () => (await reading())?.classroom.lecture?.sentence_index).toBe(0);
  expect(snapshot.classroom.lecture.sentence_index).toBe(1);
  await page.getByRole('button', { name: '节点 B 核心文档', exact: true }).click();
  await expect(page.frameLocator('iframe.sl-live-material').getByText('测试正文。', { exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: 'PPT 上下文测试', exact: true }).click();
  await expect.poll(async () => (await reading())?.classroom).toEqual({ status: 'idle' });
});
