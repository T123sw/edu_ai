// Delivery metadata is simulated; both players use real saved HyperFrames MP4s.
// No generation, progress writes, or retry jobs are submitted to the live server.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base = process.env.PROGRESSIVE_TEST_BASE || 'http://127.0.0.1:18089';
const output = process.env.PROGRESSIVE_TEST_OUTPUT || '/tmp/progressive-course-browser';
const auth = JSON.parse(fs.readFileSync('/tmp/hf-demo-course-auth/auth.json', 'utf8'));
fs.mkdirSync(output, { recursive: true });
const course = 'bubble-sort-demo-20261019';
const response = await fetch(`${base}/backend/api/self-learning/courses/${course}`, { headers: { Authorization: `Bearer ${auth.token}` } });
assert.equal(response.status, 200);
const original = await response.json();
const videos = original.chapters.flatMap(c => c.resources).filter(r => r.kind === 'video');
assert.equal(videos.length, 2);
let phase = 0, polls = 0;
const result = { base, mode: 'simulated delivery metadata with real saved videos', retries: [], errors: [] };
function room() {
  const ready = phase >= 2 ? 2 : phase >= 1 ? 1 : 0;
  return { ...original, agentRuntime: false, progressPersistence: false, sessionPersistence: false,
    preparationEnabled: false, enrichmentEnabled: false, messages: [], progress: {}, understanding: {},
    learningProjection: undefined, manifestRef: { manifest_id: 'progressive-browser', version: phase + 1 }, routeVersion: 1,
    selectedId: ready ? videos[0].id : 'pending:node-1',
    preparationDelivery: { state: phase === 5 ? 'complete' : 'partial', preparationId: 'progressive-browser',
      availableResources: ready, status: phase === 3 ? 'failed' : 'running', pending: [] },
    chapters: [0, 1, 2].map((n) => ({ id: `node-${n + 1}`, title: `知识点 ${n + 1}`,
      generationState: n < ready ? 'ready' : phase === 3 ? 'failed' : 'generating',
      resources: n < ready ? [{ ...videos[n], chapterId: `node-${n + 1}` }] : [{ id: `pending:node-${n + 1}`,
        title: `知识点 ${n + 1} 资源`, kind: 'video', topic: '', ready: false, minutes: 0, createdAt: 0, live: true }] })) };
}
const browser = await chromium.launch({ headless: true,
  executablePath: '/home/zxqs_ep/.cache/hyperframes/chrome/chrome-headless-shell/linux-152.0.7977.30/chrome-headless-shell-linux64/chrome-headless-shell',
  args: ['--no-sandbox'] });
let page;
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 },
    storageState: { cookies: [], origins: [{ origin: base, localStorage: [{ name: 'edu-ai-auth', value: JSON.stringify(auth) }] }] } });
  page = await context.newPage();
  page.on('pageerror', e => result.errors.push(e.message));
  await page.route('**/backend/api/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    const fulfill = body => route.fulfill({ json: body });
    if (path === '/backend/api/auth/verify') return route.continue();
    if (path.endsWith('/playback')) return route.continue();
    if (path === '/backend/api/self-learning/state') return fulfill({ version: 1, rooms: [room()], resources: [], shared: [], jobs: [], serverJobs: [] });
    if (path === `/backend/api/self-learning/courses/${course}` && request.method() === 'GET') { polls++; return fulfill(room()); }
    if (path === '/backend/api/course-preparations/progressive-browser/retry') {
      result.retries.push(request.postDataJSON()); phase = 4; return fulfill({ status: 'accepted' });
    }
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method())) return fulfill({});
    return route.continue();
  });
  await page.goto(`${base}/#/classroom/${course}`);
  await page.getByRole('button', { name: '01 知识点 1' }).waitFor({ timeout: 45000 });
  assert.equal(await page.locator('.sl-course-generation').count(), 0);
  assert.equal(await page.locator('iframe').count(), 0);
  await page.screenshot({ path: `${output}/01-learning-path.png`, fullPage: true });
  phase = 1;
  await page.locator(`iframe[src*="${videos[0].id}"]`).waitFor({ timeout: 30000 });
  const frame = page.frames().find(f => f.url().includes('learningPlayer=1'));
  const video = frame.locator('.hf-player video');
  await video.waitFor({ timeout: 30000 });
  await frame.waitForFunction(() => document.querySelector('video')?.readyState >= 2, null, { timeout: 30000 });
  await page.locator('iframe').evaluate(el => { window.progressiveIframe = el; });
  await video.evaluate(v => { window.progressiveVideo = v; v.currentTime = 3; v.muted = true; v.playbackRate = 1.5; });
  await video.focus(); await video.press('Space');
  await frame.waitForFunction(() => !document.querySelector('video').paused && document.querySelector('video').currentTime > 4);
  result.before = await video.evaluate(v => ({ time: v.currentTime, rate: v.playbackRate }));
  phase = 2;
  await page.getByRole('button', { name: videos[1].title, exact: true }).waitFor({ timeout: 15000 });
  result.after = await video.evaluate(v => ({ time: v.currentTime, rate: v.playbackRate, paused: v.paused, sameElement: window.progressiveVideo === v }));
  assert.equal(result.after.sameElement, true);
  assert.equal(result.after.paused, false);
  assert.equal(result.after.rate, 1.5);
  assert.ok(result.after.time > result.before.time);
  assert.equal(await page.locator('iframe').evaluate(el => window.progressiveIframe === el), true);
  assert.equal(await page.getByRole('button', { name: videos[0].title, exact: true }).getAttribute('aria-current'), 'page');
  await video.evaluate(v => v.pause());
  await page.screenshot({ path: `${output}/02-live-addition.png`, fullPage: true });
  phase = 3;
  await page.getByRole('button', { name: '重试本节', exact: true }).waitFor({ timeout: 15000 });
  await page.getByRole('button', { name: '重试本节', exact: true }).click();
  await page.getByRole('button', { name: '重试本节', exact: true }).waitFor({ state: 'hidden', timeout: 15000 });
  assert.deepEqual(result.retries, [{ node_id: 'node-3' }]);
  assert.equal(await page.locator('iframe').evaluate(el => window.progressiveIframe === el), true);
  result.retryKeptPlayer = true;
  await page.getByRole('button', { name: videos[1].title, exact: true }).click();
  const second = page.frameLocator(`iframe[src*="${videos[1].id}"]`).locator('video');
  await second.waitFor({ timeout: 30000 });
  await second.evaluate(async v => { if (v.readyState < 2) await new Promise(resolve => v.addEventListener('loadeddata', resolve, { once: true })); });
  result.secondDuration = await second.evaluate(v => v.duration);
  assert.ok(result.secondDuration > 70);
  await page.reload();
  await page.getByRole('button', { name: videos[1].title, exact: true }).waitFor({ timeout: 30000 });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: `${output}/03-mobile.png`, fullPage: true });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  assert.equal(result.errors.length, 0);
  result.polls = polls; result.passed = true;
} finally {
  if (!result.passed && page) {
    result.body = await page.locator('body').innerText().catch(() => 'unavailable');
    result.frames = await Promise.all(page.frames().map(async f => ({ url: f.url(), body: await f.locator('body').innerText().catch(() => 'unavailable') })));
    await page.screenshot({ path: `${output}/failure.png`, fullPage: true }).catch(() => undefined);
  }
  fs.writeFileSync(`${output}/result.json`, JSON.stringify(result, null, 2));
  await browser.close();
}
console.log(JSON.stringify(result));
