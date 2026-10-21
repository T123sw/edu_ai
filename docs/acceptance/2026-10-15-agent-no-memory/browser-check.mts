import { chromium, expect } from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/test.mjs';
import model from '/home/zxqs_ep/Edu_AI/frontend/src/selfLearning/model.ts';
import { mkdir, writeFile } from 'node:fs/promises';
const { seedState } = model;
const base = process.env.AGENT_CHECK_URL || 'http://127.0.0.1:5313';
const output = '/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-15-agent-no-memory';
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const results = [];
try {
 for (const width of [1440, 390]) for (const role of ['teacher', 'student']) {
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  const errors: string[] = [];
  page.on('pageerror', e => { errors.push(e.message); console.log(e.stack); });
  const state = { ...seedState(true), shared: [], serverJobs: [] };
  const room = state.rooms[0];
  const resource = room.chapters.flatMap(c => c.resources).find(r => r.id === room.selectedId)!;
  const chapter = room.chapters.find(c => c.resources.some(r => r.id === resource.id))!;
  const originalProgress = JSON.stringify(room.progress);
  const originalUnderstanding = JSON.stringify(room.understanding);
  await page.addInitScript(role => localStorage.setItem('edu-ai-auth', JSON.stringify({ user: { username: 'agent-check', role }, token: 'mock-only' })), role);
  await page.route('**/api/**', route => {
    const url = route.request().url();
    if (url.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'agent-check', role } } });
    if (url.endsWith('/personal-studio')) return route.fulfill({ json: { resources: [], jobs: [] } });
    if (url.endsWith('/course-preparations')) return route.fulfill({ json: { preparations: [] } });
    if (url.endsWith('/self-learning/state')) return route.fulfill({ json: state });
    if (url.endsWith('/jobs?limit=100')) return route.fulfill({ json: { items: [] } });
    if (url.endsWith('/turns')) {
      const request = route.request().postDataJSON();
      room.messages.push({ id: 'mock-question', role: 'user', text: request.question, chapterId: chapter.id, resourceId: resource.id, resourceTitle: resource.topic }, { id: 'mock-answer', role: 'assistant', text: '模拟答复：可以继续提问。', chapterId: chapter.id, resourceId: resource.id, resourceTitle: resource.topic });
      return route.fulfill({ json: room });
    }
    if (url.endsWith('/courses/' + room.id)) return route.fulfill({ json: room });
    console.log('UNMOCKED', url); return route.fulfill({ json: {} });
  });
  await page.goto(`${base}/#/classroom/${room.id}?resource=${resource.id}`);
  if (width < 800) await page.getByRole('button', { name: 'Agent', exact: true }).click();
  const agent = page.getByRole('complementary', { name: '知识点对话' });
  await expect(agent).toBeVisible().catch(async e => { console.log(JSON.stringify({ errors, body: await page.locator('body').innerText() })); await page.screenshot({ path: output + '/debug.png' }); throw e; });
  await expect(page.getByText('全局学习记忆')).toHaveCount(0);
  await expect(page.locator('.sl-learning-memory')).toHaveCount(0);
  await expect(agent.getByRole('log')).toBeVisible();
  await expect(agent.getByRole('textbox', { name: '向学习 Agent 提问' })).toBeVisible();
  await expect(agent.getByText('上次你已完成第一份视频讲解。', { exact: false })).toBeVisible();
  await agent.getByRole('textbox', { name: '向学习 Agent 提问' }).fill('请解释当前知识点');
  await agent.getByRole('button', { name: '发送问题' }).click();
  await expect(agent.getByText('模拟答复：可以继续提问。', { exact: true })).toBeVisible();
  expect(JSON.stringify(room.progress)).toBe(originalProgress);
  expect(JSON.stringify(room.understanding)).toBe(originalUnderstanding);
  await page.screenshot({ path: `${output}/${base.includes('5313') ? 'preview' : 'published'}-${role}-${width}.png`, fullPage: true });
  expect(errors).toEqual([]);
  results.push({ role, width, memoryPanelRemoved: true, historyAndChatPassed: true });
  await page.close();
 }
 for (const width of [1440, 390]) {
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  await page.goto(`${base}/?review=1#/classroom/sample-agent`);
  if (width < 800) await page.getByRole('button', { name: 'Agent', exact: true }).click();
  await expect(page.getByRole('complementary', { name: '知识点对话' })).toBeVisible();
  await expect(page.locator('.sl-learning-memory')).toHaveCount(0);
  results.push({ review: true, width, memoryPanelRemoved: true });
  await page.close();
 }
 await writeFile(`${output}/${base.includes('5313') ? 'preview' : 'published'}-browser.json`, JSON.stringify({ base, mockedBusinessApi: true, results }, null, 2));
 console.log(JSON.stringify(results));
} finally { await browser.close(); }
