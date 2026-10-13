import { test, expect, type Page } from 'playwright/test';

async function login(page: Page, resource: string, owner = 'alice') {
  await page.addInitScript(owner => {
    localStorage.setItem('edu-ai-auth', JSON.stringify({ token: owner, user: { username: owner, role: 'student' } }));
    class FixtureAudio extends EventTarget {
      duration = 30; currentTime = 0;
      constructor() { super(); (window as unknown as { fixtureAudio: FixtureAudio }).fixtureAudio = this; }
      play() { return Promise.resolve(); }
      pause() {}
    }
    Object.defineProperty(window, 'Audio', { value: FixtureAudio });
  }, owner);
  await page.goto(`/#/classroom/learning-fixture?resource=${resource}`);
  await expect(page.locator('.sl-classroom')).toBeVisible();
}

test('simplified classroom keeps the full player and controls inside desktop and mobile viewports', async ({ page }) => {
  await login(page, 'b-ppt');
  await expect(page.locator('.sl-course-heading h2')).toHaveText('会话测试课程');
  await expect(page.locator('.sl-course-heading a')).toHaveAttribute('href', '#/');
  await expect(page.locator('.sl-reader-toolbar, .sl-reader-footer, .sl-context, .sl-studio-link, .sl-agent-extra')).toHaveCount(0);
  for (const text of ['当前知识点 · 独立会话', '检查与学习偏好', '前往教学工作台', '资料准备 · 0 条未读']) {
    await expect(page.getByText(text, { exact: true })).toHaveCount(0);
  }
  const frame = page.frameLocator('iframe.sl-live-material');
  await expect(frame.getByRole('button', { name: '播放当前页', exact: true })).toBeVisible();
  for (const [width, height] of [[1440, 900], [1024, 768], [390, 844]]) {
    await page.setViewportSize({ width, height });
    await expect(frame.locator('.classroom-console__controls')).toBeInViewport();
    await expect.poll(() => page.locator('.sl-reader-scroll').evaluate(e => e.scrollHeight - e.clientHeight)).toBeLessThanOrEqual(1);
    const dimensions = await frame.locator('html').evaluate(e => ({ height: e.scrollHeight - window.innerHeight, width: e.scrollWidth - window.innerWidth }));
    expect(dimensions.height).toBeLessThanOrEqual(1);
    expect(dimensions.width).toBeLessThanOrEqual(1);
    for (const selector of ['.classroom-stage-shell', '.classroom-console__controls']) {
      const bounds = await frame.locator(selector).boundingBox();
      expect(bounds).toBeTruthy();
      expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(height + 1);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width + 1);
    }
    await page.screenshot({ path: `/tmp/edu-classroom-cleanup-${width}.png` });
  }
});

test('reading progress waits for a backend receipt, retries the same event and survives reload', async ({ page }) => {
  await login(page, 'a-core');
  const progress = page.getByRole('progressbar', { name: '学习进度' });
  await expect(progress).toHaveAttribute('aria-valuenow', '0');
  let blocked = true;
  const ids: string[] = [];
  await page.route('**/topics/*/events', async route => {
    const event = route.request().postDataJSON();
    if (event.type === 'resource_end_reached') {
      ids.push(event.event_id);
      if (blocked) return route.abort();
    }
    await route.continue();
  });
  const reader = page.frameLocator('iframe.sl-live-material');
  await reader.locator('[data-reading-end]').scrollIntoViewIfNeeded();
  await expect(page.getByRole('alert').filter({ hasText: '学习记录未同步' })).toBeVisible();
  await expect(progress).toHaveAttribute('aria-valuenow', '0');
  blocked = false;
  await page.getByRole('button', { name: '重试保存' }).click();
  await expect(progress).toHaveAttribute('aria-valuenow', '1');
  expect(new Set(ids).size).toBe(1);
  const restored = page.waitForResponse(r => r.url().endsWith('/learning-fixture/progress') && r.request().method() === 'GET');
  await page.reload();
  await expect(progress).toHaveAttribute('aria-valuenow', '1');
  const response = await restored;
  expect(response.ok()).toBe(true);
  const fact = (await response.json()).resources.find((r: { resource_ref: { material_id: string } }) => r.resource_ref.material_id === 'a-core');
  expect(fact).toMatchObject({ reached_end: true, completed: false });
});

test('PPT playback to the end updates persisted progress; merely opening the last page does not', async ({ page }) => {
  await login(page, 'b-ppt', 'bob');
  const progress = page.getByRole('progressbar', { name: '学习进度' });
  const frame = page.frameLocator('iframe.sl-live-material');
  await frame.getByRole('button', { name: '下一页', exact: true }).click();
  await expect(progress).toHaveAttribute('aria-valuenow', '0');
  await frame.getByRole('button', { name: '播放当前页', exact: true }).click();
  await expect(frame.getByRole('button', { name: '暂停', exact: true })).toBeVisible();
  await expect.poll(() => frame.locator('body').evaluate(() => !!(window as unknown as { fixtureAudio: unknown }).fixtureAudio)).toBe(true);
  await frame.locator('body').evaluate(() => {
    const audio = (window as unknown as { fixtureAudio: { currentTime: number; dispatchEvent: (event: Event) => void } }).fixtureAudio;
    audio.currentTime = 30;
    audio.dispatchEvent(new Event('ended'));
  });
  await expect(progress).toHaveAttribute('aria-valuenow', '1');
  await page.reload();
  await expect(progress).toHaveAttribute('aria-valuenow', '1');
});
