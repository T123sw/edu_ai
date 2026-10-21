import { chromium, expect } from '/home/zxqs_ep/Edu_AI/frontend/node_modules/playwright/test.mjs';
import model from '/home/zxqs_ep/Edu_AI/frontend/src/selfLearning/model.ts';
const { seedState, sharedSeeds } = model;
import { mkdir, writeFile } from 'node:fs/promises';
const base = process.env.HOME_CHECK_URL || 'http://127.0.0.1:5311';
const output = '/home/zxqs_ep/Edu_AI/docs/acceptance/2026-10-15-home-no-sharing';
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const results = [];
try {
 for (const width of [1440, 390]) for (const role of ['teacher', 'student']) {
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  const state = { ...seedState(true), shared: sharedSeeds(), serverJobs: [] };
  await page.addInitScript(role => localStorage.setItem('edu-ai-auth', JSON.stringify({ user: { username: 'home-check', role }, token: 'mock-only' })), role);
  await page.route('**/api/**', route => {
    const url = route.request().url();
    if (url.endsWith('/auth/verify')) return route.fulfill({ json: { valid: true, user: { username: 'home-check', role } } });
    if (url.endsWith('/course-preparations')) return route.fulfill({ json: { preparations: [] } });
    if (url.endsWith('/self-learning/state')) return route.fulfill({ json: state });
    if (url.endsWith('/jobs?limit=100')) return route.fulfill({ json: { items: [] } });
    const room = state.rooms.find(r => url.endsWith('/courses/' + r.id));
    if (room) return route.fulfill({ json: room });
    if (url.endsWith('/learning')) return route.fulfill({ json: {} });
    return route.fulfill({ json: {} });
  });
  await page.goto(base);
  await expect(page.getByRole('heading', { name: /最近学习/ })).toBeVisible();
  await expect(page.getByText(/共享课堂|共享我的课堂|上传课堂|发现共享/)).toHaveCount(0);
  await expect(page.getByLabel('课堂来源')).toHaveCount(0);
  await expect(page.locator('.sl-class-card')).toHaveCount(state.rooms.length);
  await expect(page.getByRole('button', { name: '开始学习', exact: true })).toBeDisabled();
  await page.getByLabel('学习知识点与目标').fill('学习 Python');
  await expect(page.getByRole('button', { name: '开始学习', exact: true })).toBeEnabled();
  await page.screenshot({ path: `${output}/${base.includes('5311') ? 'preview' : 'published'}-${role}-${width}.png`, fullPage: true });
  await page.getByRole('button', { name: '搜索课堂', exact: true }).click();
  await page.getByRole('textbox', { name: '搜索课堂', exact: true }).fill('no-match-12345');
  await expect(page.getByText('没有找到相关课堂，换个关键词试试。')).toBeVisible();
  await expect(page.locator('.sl-class-card')).toHaveCount(0);
  await page.getByRole('button', { name: '关闭课堂搜索' }).click();
  await expect(page.locator('.sl-class-card')).toHaveCount(state.rooms.length);
  await page.locator('.sl-class-card').first().click();
  await expect(page).toHaveURL(/#\/classroom\//);
  expect(errors).toEqual([]);
  await page.close();
  results.push({ role, width, passed: true });
 }
 for (const role of ['teacher', 'student']) {
  const page = await browser.newPage();
  await page.goto(`${base}/?review=1&role=${role}`);
  await expect(page.getByRole('heading', { name: /最近学习/ })).toBeVisible();
  await expect(page.getByText(/共享课堂|共享我的课堂|上传课堂|发现共享/)).toHaveCount(0);
  results.push({ review: role, passed: true });
  await page.close();
 }
 await writeFile(`${output}/${base.includes('5311') ? 'preview' : 'published'}-browser.json`, JSON.stringify({ base, mockedBusinessApi: true, results }, null, 2));
 console.log(JSON.stringify(results));
} finally { await browser.close(); }
