import { test, expect, type Page } from 'playwright/test';
import { readFileSync } from 'node:fs';
import { seedState } from '../../src/selfLearning/model';
const choice = (id: string, text: string, next_id: string) => ({ id, text, next_id, feedback: `反馈：${text}` });
const content = { title: '网站变慢了', introduction: '你负责排查网站响应时间。', learning_objectives: ['依据证据定位问题'], start_id: 'start', scenes: [
  { id: 'start', title: '开始排查', situation: '访问耗时很长，先做什么？', choices: [choice('measure', '测量耗时', 'measure'), choice('restart', '直接重启', 'bad')], ending: '', takeaway: '' },
  { id: 'measure', title: '定位瓶颈', situation: '数据库耗时很高。', choices: [choice('query', '检查慢查询', 'good'), choice('cpu', '增加 Web CPU', 'bad')], ending: '', takeaway: '' },
  { id: 'good', title: '恢复正常', situation: '响应时间下降。', choices: [], ending: '你解决了查询瓶颈。', takeaway: '先测量，再行动。' },
  { id: 'bad', title: '仍然缓慢', situation: '问题仍在。', choices: [], ending: '需要进一步测量。', takeaway: '避免无依据地修改系统。' },
] };
const materials = [
  { material_id: 'cards', material_type: 'flashcard', title: '变量复习', content: { cards: ['甲', '乙', '丙'].map(id => ({ front: `卡片${id}的问题`, back: `卡片${id}的答案` })) } },
  { material_id: 'case', material_type: 'scenario', title: '故障排查', content },
  { material_id: 'audio', material_type: 'podcast', title: '变量播客', content: { title: '变量播客', summary: '听懂变量的含义', audio_url: '/api/personal-studio/resources/podcast/audio/audio', segments: [{ title: '先认识变量', text: '变量是名字到对象的绑定。' }, { title: '应用例子', text: '通过名字访问所绑定的对象。' }] } },
].map(item => ({ ...item, version: 1, studio_course_id: 'course', studio_course_title: 'Python 入门', updated_at: '2026-10-14T00:00:00Z' }));
async function fixture(page: Page, cards?: { front: string; back: string; source_title?: string }[]) {
  const state = seedState();
  await page.addInitScript(() => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user: { username: 'alice', role: 'student' } })));
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/resources/podcast/audio/audio')) return route.fulfill({ contentType: 'audio/mpeg', body: readFileSync('/tmp/edu-podcast-browser.mp3') });
    const material = materials.find(item => path.endsWith(`/resources/${item.material_type}/${item.material_id}`));
    const json = path.endsWith('/auth/verify') ? { valid: true, user: { username: 'alice', role: 'student' } }
      : path.endsWith('/self-learning/state') ? { ...state, shared: [], serverJobs: [] }
      : path.endsWith('/personal-studio') ? { resources: materials, jobs: [] }
      : (material && cards && material.material_type === 'flashcard' ? { ...material, content: { cards } } : material) || (path.endsWith('/course-preparations') ? { preparations: [] } : { items: [] });
    return route.fulfill({ json });
  });
  await page.goto('/#/my-resources');
}
test('flashcards finish one round; known cards leave and uncertain cards return', async ({ page }) => {
  await fixture(page);
  await page.locator('.studio-type-filters button').filter({ hasText: '闪卡' }).click();
  await page.locator('.studio-resource-row').filter({ hasText: '变量复习' }).click();
  const round = page.getByRole('region', { name: '本轮闪卡练习' });
  const mark = async (id: string, known: boolean) => {
    await expect(round.getByText(`卡片${id}的问题`, { exact: true })).toBeVisible();
    await expect(round.getByRole('button', { name: '已经掌握', exact: true })).toHaveCount(0);
    await round.getByRole('button', { name: '翻转卡片', exact: true }).click();
    await expect(round.getByText(`卡片${id}的答案`, { exact: true })).toBeVisible();
    await round.getByRole('button', { name: known ? '已经掌握' : '再练一次', exact: true }).click();
  };
  await mark('甲', true); await mark('乙', false); await mark('丙', true); await mark('乙', true);
  await expect(round.getByRole('heading', { name: '本轮完成' })).toBeVisible();
  await page.screenshot({ path: '../docs/acceptance/2026-10-15-flashcard-redesign/complete.png' });
  await expect(round).toContainText('共回忆 4 次');
  await expect(round).not.toContainText('今日复习'); await expect(round).not.toContainText('下次复习');
  await round.getByRole('button', { name: '再练一轮' }).click();
  await expect(round.getByText('卡片甲的问题', { exact: true })).toBeVisible();
});
for (const width of [1440, 390]) {
  test(`flashcard flip, keyboard, progress and responsive layout ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await fixture(page, Array.from({ length: 12 }, (_, index) => ({ front: `为什么变量可以指向不同的对象？（${index + 1}）`, back: '变量是名字与对象之间的绑定。重新赋值会改变绑定关系，而不是改变原对象。', source_title: '变量与对象' })));
    await page.locator('.studio-type-filters button').filter({ hasText: '闪卡' }).click();
    await page.locator('.studio-resource-row').filter({ hasText: '变量复习' }).click();
    const round = page.getByRole('region', { name: '本轮闪卡练习' });
    const progress = round.getByRole('progressbar');
    await expect(page.getByRole('button', { name: '导出', exact: true })).toHaveCount(0);
    await expect(round.getByRole('button', { name: '查看答案', exact: true })).toHaveCount(0);
    await expect(progress).toHaveAttribute('value', '0');
    await expect(progress).toHaveAttribute('max', '12');
    await expect(round.locator('.flashcard-round-back')).toBeHidden();
    await expect(round.getByRole('button', { name: '翻转卡片', exact: true })).toHaveAccessibleDescription('为什么变量可以指向不同的对象？（1）');
    await page.screenshot({ path: `../docs/acceptance/2026-10-15-flashcard-redesign/front-${width}.png` });
    await round.getByRole('button', { name: '翻转卡片', exact: true }).click();
    await expect(round.getByRole('button', { name: '翻回问题', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(round.locator('.flashcard-round-front')).toBeHidden();
    await expect(round.getByText('资料来源：变量与对象')).toBeVisible();
    await expect(round.locator('.flashcard-round-flipper')).toHaveCSS('transition-duration', '0.56s');
    await expect(round.locator('.flashcard-round-flipper')).toHaveCSS('transform', 'matrix3d(-1, 0, 0, 0, 0, 1, 0, 0, 0, 0, -1, 0, 0, 0, 0, 1)');
    await page.screenshot({ path: `../docs/acceptance/2026-10-15-flashcard-redesign/back-${width}.png` });
    await round.getByRole('button', { name: '翻回问题', exact: true }).press('Space');
    await expect(round.getByRole('button', { name: '已经掌握' })).toHaveCount(0);
    await round.getByRole('button', { name: '翻转卡片', exact: true }).press('Enter');
    await round.getByRole('button', { name: '已经掌握' }).click();
    await expect(progress).toHaveAttribute('value', '1');
    await expect(round.locator('.flashcard-round-remaining')).toHaveText('还剩 11 张');
    await expect(round.getByRole('button', { name: '翻转卡片', exact: true })).toBeFocused();
    await expect(round.locator('.flashcard-round-back')).toBeHidden();
    await expect(round.locator('.flashcard-round-front')).toContainText('（2）');
    await page.screenshot({ path: `../docs/acceptance/2026-10-15-flashcard-redesign/progress-${width}.png` });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    const bounds = await round.boundingBox();
    expect(bounds!.x).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
  });
}

test('one remaining flashcard resets to its question when retrying and respects reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await fixture(page, [{ front: '最后一张的问题', back: '最后一张的答案' }]);
  await page.locator('.studio-type-filters button').filter({ hasText: '闪卡' }).click();
  await page.locator('.studio-resource-row').filter({ hasText: '变量复习' }).click();
  const round = page.getByRole('region', { name: '本轮闪卡练习' });
  await round.getByRole('button', { name: '翻转卡片', exact: true }).press('Space');
  await expect(round.locator('.flashcard-round-flipper')).toHaveCSS('transition-duration', '0s');
  await round.getByRole('button', { name: '再练一次', exact: true }).click();
  await expect(round.locator('.flashcard-round-front')).toContainText('最后一张的问题');
  await expect(round.locator('.flashcard-round-back')).toBeHidden();
  await expect(round.getByRole('progressbar')).toHaveAttribute('value', '0');
  await round.getByRole('button', { name: '翻转卡片', exact: true }).press('Space');
  await round.getByRole('button', { name: '已经掌握', exact: true }).click();
  await expect(round.getByRole('heading', { name: '本轮完成' })).toBeFocused();
  await expect(round).toContainText('共回忆 2 次');
  await round.getByRole('button', { name: '再练一轮' }).click();
  await expect(round.getByRole('button', { name: '翻转卡片', exact: true })).toBeFocused();
  await expect(round.getByRole('progressbar')).toHaveAttribute('value', '0');
});

test('scenario choices lead to different endings and can restart', async ({ page }) => {
  await fixture(page);
  await page.locator('.studio-type-filters button').filter({ hasText: '情景案例' }).click();
  await page.locator('.studio-resource-row').filter({ hasText: '故障排查' }).click();
  const exercise = page.getByRole('region', { name: '情景案例练习' });
  await page.screenshot({ path: '../docs/acceptance/2026-10-14-podcast-scenario-flashcards/scenario.png' });
  await exercise.getByRole('button', { name: /测量耗时/ }).click();
  await expect(exercise.getByText('反馈：测量耗时', { exact: true })).toBeVisible();
  await exercise.getByRole('button', { name: '继续情景' }).click();
  await exercise.getByRole('button', { name: /检查慢查询/ }).click();
  await exercise.getByRole('button', { name: '继续情景' }).click();
  await expect(exercise.getByText('你解决了查询瓶颈。', { exact: true })).toBeVisible();
  await exercise.getByRole('button', { name: '重新体验' }).click();
  await expect(exercise.getByText(/本次选择记录/)).toHaveCount(0);
  await exercise.getByRole('button', { name: /直接重启/ }).click();
  await exercise.getByRole('button', { name: '继续情景' }).click();
  await expect(exercise.getByText('需要进一步测量。', { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
test('podcast fetches private audio and plays alongside readable transcript', async ({ page }) => {
  await fixture(page);
  const audioRequest = page.waitForRequest(r => r.url().endsWith('/resources/podcast/audio/audio'));
  await page.locator('.studio-type-filters button').filter({ hasText: '播客' }).click();
  await page.locator('.studio-resource-row').filter({ hasText: '变量播客' }).click();
  expect((await audioRequest).headers().authorization).toBe('Bearer fixture');
  const player = page.getByRole('region', { name: '播客播放器' });
  const audio = player.locator('audio');
  await expect(audio).toHaveAttribute('src', /^blob:/);
  await expect.poll(() => audio.evaluate((node: HTMLAudioElement) => node.readyState)).toBeGreaterThan(0);
  await audio.evaluate((node: HTMLAudioElement) => node.play());
  await expect.poll(() => audio.evaluate((node: HTMLAudioElement) => node.currentTime)).toBeGreaterThan(0);
  await expect(player.getByText('变量是名字到对象的绑定。', { exact: true })).toBeVisible();
  await player.getByText('2. 应用例子', { exact: true }).click();
  await expect(player.getByText('通过名字访问所绑定的对象。', { exact: true })).toBeVisible();
  await expect(player.getByRole('link', { name: '下载音频' })).toHaveAttribute('download', '变量播客.mp3');
  await page.screenshot({ path: '../docs/acceptance/2026-10-14-podcast-scenario-flashcards/podcast.png' });
});
