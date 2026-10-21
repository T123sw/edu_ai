import { test, expect, type Page, type Locator } from 'playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import type { AnswerTurn } from '../../src/liveLearning/agentTurns';

let videoFile: Buffer;
test.beforeAll(() => {
  const dir = mkdtempSync(join(tmpdir(), 'edu-video-chat-'));
  try {
    const file = join(dir, 'video.mp4');
    execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'color=c=navy:s=640x360:d=30',
      '-f', 'lavfi', '-i', 'sine=frequency=440:duration=30', '-c:v', 'libx264', '-c:a', 'aac', '-movflags', '+faststart', '-shortest', file]);
    videoFile = readFileSync(file);
  } finally { rmSync(dir, { recursive: true, force: true }); }
});

async function openClassroom(page: Page, runtime = false) {
  page.on('pageerror', e => console.error(e.message));
  const digest = 'a'.repeat(64);
  const content = { format: 'hyperframes/v1', title: '播放回归视频', project: { id: 'fixture', digest, entry: 'index.html' },
    timeline: { duration: 30, segments: [{ id: 'intro', title: '第一段', start: 0, end: 30, narration: '测试讲解', visual_description: '蓝色画面' }] } };
  const resource = { id: 'video', title: content.title, topic: '播放回归', kind: 'video', ready: true, minutes: 1, createdAt: 1,
    remote: { courseId: 'video-chat', materialId: 'video', materialType: 'classroom', version: 1, visibility: 'course' } };
  const room = { id: 'video-chat', title: '视频提问回归', goal: '', tone: '', selectedId: 'video', progress: {}, messages: [] as object[], updatedAt: 1,
    live: true, agentRuntime: runtime, sessionPersistence: runtime, sessionOwner: 'fixture',
    chapters: [{ id: 'one', title: '第一节', resources: [resource] }] };
  const turns: AnswerTurn[] = [];
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'fixture', role: 'student' } })));
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname.replace(/^\/backend(?=\/api\/)/, '');
    if (!path.startsWith('/api/')) return route.continue();
    const json = (value: unknown) => route.fulfill({ json: value });
    if (path === '/api/auth/verify') return json({ valid: true, user: { username: 'fixture', role: 'student' } });
    if (path.endsWith('/lesson.mp4')) {
      const range = /^bytes=(\d+)-(\d*)$/.exec(route.request().headers().range || '');
      if (!range) return route.fulfill({ contentType: 'video/mp4', headers: { 'accept-ranges': 'bytes' }, body: videoFile });
      const start = Number(range[1]), end = range[2] ? Math.min(Number(range[2]), videoFile.length - 1) : videoFile.length - 1;
      return route.fulfill({ status: 206, contentType: 'video/mp4', headers: { 'accept-ranges': 'bytes',
        'content-range': `bytes ${start}-${end}/${videoFile.length}` }, body: videoFile.subarray(start, end + 1) });
    }
    if (path.endsWith('/playback')) return json({ project_digest: digest, project_url: '/api/hyperframes/projects/fixture/index.html',
      expires_at: Date.now() / 1000 + 3600, duration: 30, exports: { video: '/api/hyperframes/projects/fixture/exports/lesson.mp4',
        subtitles: '/api/hyperframes/projects/fixture/exports/lesson.srt', project: '/api/hyperframes/projects/fixture/exports/project.zip' } });
    if (path.includes('/materials/classroom/')) return json({ material_id: 'video', material_type: 'classroom', version: 1, content });
    if (path.endsWith('/agent-turns')) {
      if (route.request().method() === 'GET') return json(turns);
      const { question, request_id } = route.request().postDataJSON();
      const turn: AnswerTurn = { turn_id: request_id, request_id, topic_id: 'one', status: 'running', stage: 'reading_resources' };
      turns.unshift(turn);
      setTimeout(() => {
        turn.status = question.includes('失败') ? 'failed' : 'succeeded';
        turn.error_code = turn.status === 'failed' ? 'MODEL_UNAVAILABLE' : undefined;
        if (turn.status === 'succeeded') room.messages.push({ id: request_id, position: room.messages.length,
          role: 'assistant', text: `已回答：${question}`, chapterId: 'one', resourceId: 'video' });
      }, 1800);
      return json(turn);
    }
    if (path.endsWith('/enter') || path.endsWith('/session')) return json({ session_id: 'course-video-chat', topic_id: 'one', items: room.messages, next_cursor: null });
    if (path.endsWith('/turns')) {
      const question = route.request().postDataJSON().question;
      await new Promise(resolve => setTimeout(resolve, 350));
      room.messages.push({ id: String(room.messages.length), role: 'assistant', text: `已回答：${question}`, chapterId: 'one', resourceId: 'video' });
      return json(room);
    }
    if (path === '/api/self-learning/state') return json({ version: 1, rooms: [room], resources: [], jobs: [], serverJobs: [], shared: [] });
    if (path === '/api/self-learning/courses/video-chat') return json(room);
    if (path.endsWith('/progress')) return json(room);
    if (path.endsWith('/qa/session')) return json({ session_id: 'fixture', turns: [] });
    return json({ items: [], tasks: [], resources: [], jobs: [], role: 'viewer' });
  });
  await page.goto('/#/classroom/video-chat');
  await expect(page.locator('.sl-classroom')).toBeVisible();
  const video = page.frameLocator('iframe.sl-live-material').locator('video');
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState)).toBeGreaterThanOrEqual(2);
  return video;
}

async function play(video: Locator) {
  // Use the real native control's keyboard action, not a mocked play method.
  await video.focus();
  await video.press('Space');
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.paused)).toBe(false);
  const start = await video.evaluate((v: HTMLVideoElement) => v.currentTime);
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeGreaterThan(start + 0.25);
}
async function paused(video: Locator) {
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.paused)).toBe(true);
}

test('native video can resume after focus, answers and repeated questions without reload', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  const video = await openClassroom(page);
  await video.evaluate(v => { v.dataset.originalPlayer = 'yes'; });
  await play(video);
  const input = page.getByRole('textbox', { name: '向学习 Agent 提问' });
  await input.fill('解释这段视频');
  await paused(video);
  await play(video); // Previously blocked: the player's host remained inert.
  await input.focus();
  await paused(video);
  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(page.getByRole('log')).toContainText('已回答：解释这段视频');
  await paused(video); // Answer completion must not start audio unexpectedly.
  await play(video);
  await page.getByRole('button', { name: '举个例子', exact: true }).click();
  await expect(page.getByRole('log')).toContainText('已回答：举个例子');
  await paused(video);
  await page.getByRole('button', { name: '继续课堂' }).click();
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.paused)).toBe(false);
  await video.evaluate((v: HTMLVideoElement) => { v.pause(); v.currentTime = 12; v.playbackRate = 1.5; });
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.seeking)).toBe(false);
  await play(video);
  expect(await video.getAttribute('data-original-player')).toBe('yes');
  expect(await video.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeGreaterThan(12);
  expect(await video.evaluate((v: HTMLVideoElement) => v.playbackRate)).toBe(1.5);
  expect(errors).toEqual([]);
  if (process.env.VIDEO_CHAT_SCREENSHOTS) await page.screenshot({ path: `${process.env.VIDEO_CHAT_SCREENSHOTS}/desktop.png` });
});

test('mobile question and directory panels pause hidden video and leave playback usable on return', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const video = await openClassroom(page);
  await play(video);
  await page.getByRole('button', { name: 'Agent', exact: true }).click();
  await paused(video);
  await page.getByRole('textbox', { name: '向学习 Agent 提问' }).fill('手机提问');
  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(page.getByRole('log')).toContainText('已回答：手机提问');
  await page.getByRole('button', { name: '学习', exact: true }).click();
  await paused(video);
  await play(video);
  await page.getByRole('button', { name: '目录', exact: true }).click();
  await paused(video);
  await page.getByRole('button', { name: '学习', exact: true }).click();
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.paused)).toBe(false);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  if (process.env.VIDEO_CHAT_SCREENSHOTS) await page.screenshot({ path: `${process.env.VIDEO_CHAT_SCREENSHOTS}/mobile.png` });
});

test('course agent retains the sent video context while playback continues during an answer or after failure', async ({ page }) => {
  const video = await openClassroom(page, true);
  await video.evaluate((v: HTMLVideoElement) => { v.currentTime = 8; });
  await expect.poll(() => video.evaluate((v: HTMLVideoElement) => v.seeking)).toBe(false);
  await play(video);
  const input = page.getByRole('textbox', { name: '向学习 Agent 提问' });
  await input.fill('解释当前片段');
  await paused(video);
  const accepted = page.waitForRequest(r => r.url().endsWith('/agent-turns') && r.method() === 'POST');
  await page.getByRole('button', { name: '发送问题' }).click();
  const context = (await accepted).postDataJSON().reading_context;
  expect(context.resource_ref).toMatchObject({ material_id: 'video', version: 1 });
  expect(context.locator.kind).toBe('hyperframes');
  expect(context.locator.seconds).toBeGreaterThanOrEqual(8);
  await play(video);
  await expect(page.getByRole('log')).toContainText('已回答：解释当前片段');
  expect(await video.evaluate((v: HTMLVideoElement) => v.paused)).toBe(false);
  expect(await video.evaluate((v: HTMLVideoElement) => v.currentTime)).toBeGreaterThan(context.locator.seconds);
  await input.fill('模拟失败');
  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(page.getByRole('button', { name: '重试本次答疑' })).toBeVisible();
  await paused(video);
  await play(video);
});
