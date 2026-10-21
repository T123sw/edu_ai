import { expect, test, type Page } from 'playwright/test';
import { seedState } from '../../src/selfLearning/model';

const root = {
  title: '快速排序：分治思想与整体流程',
  children: Array.from({ length: 6 }, (_, i) => ({
    id: `branch-${i}`, title: `分支 ${i + 1}`, summary: '通过选择基准、划分与递归理解快速排序。',
    children: Array.from({ length: i === 0 ? 5 : 2 }, (_, j) => ({
      id: `detail-${j}`, title: `要点 ${i + 1}.${j + 1}`, summary: '将小于基准的元素放在左侧，大于基准的元素放在右侧。',
      ...(i === 0 && j === 0 ? { children: [{ title: '第三级说明', children: [{ title: '第四级边界条件' }] }] } : {}),
    })),
  })),
};

async function openMap(page: Page) {
  const state = seedState();
  const room = state.rooms[0];
  const material = { material_id: 'viewport-map', material_type: 'graph', title: '全景导图', studio_title: '全景导图', version: 1, content: { root }, studio_course_id: room.id, studio_course_title: room.title, studio_chapter_id: room.chapters[0].id, studio_chapter_title: room.chapters[0].title };
  const report = { ...material, material_id: 'layout-report', material_type: 'report', title: '普通报告', studio_title: '普通报告', content: '# 普通报告\n\n用于验证其他资源弹窗保持原有尺寸。' };
  const user = { username: 'mind-map-fixture', role: 'student' };
  await page.addInitScript(user => localStorage.setItem('edu-ai-auth', JSON.stringify({ token: 'fixture', user })), user);
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path.startsWith('/src/')) return route.continue();
    const json = path.endsWith('/auth/verify') ? { valid: true, user }
      : path.endsWith('/auth/me') ? user
      : path.endsWith('/self-learning/state') ? { ...state, shared: [], serverJobs: [] }
      : path.endsWith('/personal-studio') ? { resources: [material, report], jobs: [] }
      : path.endsWith('/resources/graph/viewport-map') ? material
      : path.endsWith('/resources/report/layout-report') ? report
      : path.endsWith('/course-preparations') ? { preparations: [] }
      : path.endsWith('/api/courses') ? [] : { items: [] };
    return route.fulfill({ json });
  });
  await page.goto('/#/my-resources');
  await page.locator('.studio-type-filters button').filter({ hasText: '思维导图' }).click();
  await page.locator('.studio-resource-row').filter({ hasText: '全景导图' }).click();
  await expect(page.locator('.balanced-mind-map__diagram')).toBeVisible();
}

async function expectAllInView(page: Page) {
  await expect.poll(() => page.locator('.balanced-mind-map__viewport').evaluate(viewport => {
    const bounds = viewport.getBoundingClientRect();
    const nodes = [...viewport.querySelectorAll('article')].map(node => node.getBoundingClientRect());
    return nodes.every(node => node.left >= bounds.left && node.right <= bounds.right && node.top >= bounds.top && node.bottom <= bounds.bottom)
      && viewport.scrollWidth <= viewport.clientWidth + 1 && viewport.scrollHeight <= viewport.clientHeight + 1;
  })).toBe(true);
}

for (const width of [1440, 920, 390]) {
  test(`mind map fits every expanded node and keeps deep branches connected at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 911 });
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await openMap(page);
    await expectAllInView(page);
    await expect(page.locator('.balanced-mind-map__toggle')).toHaveCount(0);
    const branch = page.locator('.balanced-mind-map__node').filter({ has: page.getByText('分支 1', { exact: true }) });
    await branch.locator('strong').click();
    await expect(branch).toHaveAttribute('aria-expanded', 'true');
    const detail = page.locator('.balanced-mind-map__node').filter({ has: page.getByText('要点 1.1', { exact: true }) });
    await detail.click();
    await expect(page.getByText('第三级说明', { exact: true })).toBeVisible();
    await branch.locator('small').click();
    await expect(page.getByText('第三级说明', { exact: true })).toHaveCount(0);
    await branch.click();
    await expect(page.getByText('第三级说明', { exact: true })).toBeVisible();
    // Keyboard activation and parent collapse retain the nested expansion state.
    await branch.focus();
    await page.keyboard.press('Space');
    await expect(branch).toHaveAttribute('aria-expanded', 'false');
    await page.keyboard.press('Enter');
    await expect(branch).toHaveAttribute('aria-expanded', 'true');
    const leaf = page.locator('.balanced-mind-map__node').filter({ has: page.getByText('要点 1.2', { exact: true }) });
    const nodeCount = await page.locator('.balanced-mind-map article').count();
    await leaf.click();
    await expect(page.locator('.balanced-mind-map article')).toHaveCount(nodeCount);
    // A drag beginning on a clickable node pans without toggling it.
    const beforeNodeDrag = (await branch.boundingBox())!;
    await page.mouse.move(beforeNodeDrag.x + beforeNodeDrag.width / 2, beforeNodeDrag.y + beforeNodeDrag.height / 2);
    await page.mouse.down();
    await page.mouse.move(beforeNodeDrag.x + beforeNodeDrag.width / 2 + 28, beforeNodeDrag.y + beforeNodeDrag.height / 2 + 18, { steps: 5 });
    await page.mouse.up();
    await expect(branch).toHaveAttribute('aria-expanded', 'true');
    await expect.poll(async () => Math.round((await branch.boundingBox())!.x - beforeNodeDrag.x)).toBe(28);
    await branch.click();
    await expect(branch).toHaveAttribute('aria-expanded', 'false');
    const center = page.locator('.balanced-mind-map__root');
    await center.click();
    await expect(page.locator('.balanced-mind-map article')).toHaveCount(1);
    await center.click();
    await expect(branch).toBeVisible();
    await page.getByRole('button', { name: '概览', exact: true }).click();
    if (width === 390) {
      await branch.tap();
      await expect(branch).toHaveAttribute('aria-expanded', 'true');
      await branch.tap();
      await expect(branch).toHaveAttribute('aria-expanded', 'false');
    }
    await expect(page.getByRole('button', { name: '适应画布', exact: true })).toHaveCount(0);
    await expect(page.getByRole('dialog').getByRole('button', { name: '导出', exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '导出导图', exact: true })).toBeVisible();
    await page.getByRole('button', { name: '展开全部', exact: true }).click();
    await expect(page.getByText('第四级边界条件', { exact: true })).toBeVisible();
    await expect(page.locator('.balanced-mind-map article')).toHaveCount(24);
    await expectAllInView(page);
    // Every visible child has a curve terminating at its actual edge, including
    // the deliberately asymmetric fourth-level branch on the left.
    const geometry = await page.locator('.balanced-mind-map__diagram').evaluate(diagram => {
      const paths = [...diagram.querySelectorAll<SVGPathElement>('path')];
      const nodes = [...diagram.querySelectorAll<HTMLElement>('.balanced-mind-map__branch')];
      const boxes = [...diagram.querySelectorAll('article')].map(node => node.getBoundingClientRect());
      const overlaps = boxes.some((a, i) => boxes.slice(i + 1).some(b => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1));
      const endpoints = paths.every((path, i) => {
        const box = nodes[i].querySelector('article')!.getBoundingClientRect();
        const end = path.getPointAtLength(path.getTotalLength()).matrixTransform(path.getScreenCTM()!);
        const expectedX = nodes[i].classList.contains('balanced-mind-map__branch--left') ? box.right : box.left;
        return Math.abs(end.x - expectedX) < 2 && Math.abs(end.y - (box.top + box.height / 2)) < 2;
      });
      return { overlaps, endpoints, edgeCount: paths.length, nodeCount: nodes.length };
    });
    expect(geometry.overlaps).toBe(false);
    expect(geometry.endpoints).toBe(true);
    expect(geometry.edgeCount).toBe(geometry.nodeCount);
    await page.screenshot({ path: `test-results/mind-map-expanded-${width}.png` });
    for (let i = 0; i < 8; i++) await page.getByRole('button', { name: '放大', exact: true }).click();
    const viewport = page.locator('.balanced-mind-map__viewport');
    await expect(viewport).toHaveCSS('background-color', 'rgb(255, 255, 255)');
    await expect(viewport).toHaveCSS('background-image', 'none');
    const bounds = (await viewport.boundingBox())!;
    expect(bounds.height).toBeGreaterThan(911 * 0.55);
    const dialog = (await page.getByRole('dialog').boundingBox())!;
    expect(dialog.width).toBeGreaterThanOrEqual(width - (width > 600 ? 50 : 26));
    const diagram = page.locator('.balanced-mind-map__diagram');
    const beforeDrag = (await diagram.boundingBox())!;
    await page.mouse.move(bounds.x + 18, bounds.y + 18);
    await page.mouse.down();
    await page.mouse.move(bounds.x + 98, bounds.y + 78, { steps: 6 });
    await page.mouse.up();
    await expect(viewport).not.toHaveClass(/is-dragging/);
    const afterDrag = (await diagram.boundingBox())!;
    expect(Math.abs(afterDrag.x - beforeDrag.x - 80)).toBeLessThan(2);
    expect(Math.abs(afterDrag.y - beforeDrag.y - 60)).toBeLessThan(2);
    const anchor = { x: bounds.x + bounds.width * 0.65, y: bounds.y + bounds.height * 0.4 };
    await page.mouse.move(anchor.x, anchor.y);
    const beforeWheel = (await diagram.boundingBox())!;
    const scrollBefore = await page.evaluate(() => ({ page: scrollY, modal: document.querySelector('.studio-body')!.scrollTop }));
    await page.mouse.wheel(0, 100);
    await expect.poll(async () => (await diagram.boundingBox())!.width).toBeLessThan(beforeWheel.width);
    const afterWheel = (await diagram.boundingBox())!;
    expect(Math.abs((anchor.x - beforeWheel.x) / beforeWheel.width - (anchor.x - afterWheel.x) / afterWheel.width)).toBeLessThan(0.002);
    expect(Math.abs((anchor.y - beforeWheel.y) / beforeWheel.height - (anchor.y - afterWheel.y) / afterWheel.height)).toBeLessThan(0.002);
    expect(await page.evaluate(() => ({ page: scrollY, modal: document.querySelector('.studio-body')!.scrollTop }))).toEqual(scrollBefore);
    await page.mouse.wheel(0, -100);
    await expect.poll(async () => (await diagram.boundingBox())!.width).toBeGreaterThan(afterWheel.width);
    await page.getByRole('button', { name: '展开全部', exact: true }).click();
    await expectAllInView(page);
    await page.getByRole('button', { name: '全屏查看', exact: true }).click();
    await expect(page.getByRole('button', { name: '退出全屏', exact: true })).toBeVisible();
    await expectAllInView(page);
    await page.getByRole('button', { name: '退出全屏', exact: true }).click();
    await expectAllInView(page);
    await page.setViewportSize({ width: width === 390 ? 1440 : 390, height: 700 });
    await expectAllInView(page);
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: '导出导图', exact: true }).click();
    const stream = await (await download).createReadStream();
    const chunks: Buffer[] = [];
    for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
    expect(JSON.parse(Buffer.concat(chunks).toString()).root).toEqual(root);
    await page.getByRole('button', { name: '复位', exact: true }).click();
    await expect(page.locator('.balanced-mind-map article')).toHaveCount(7);
    await expectAllInView(page);
    if (width === 1440) {
      await page.setViewportSize({ width, height: 911 });
      await page.getByRole('button', { name: '关闭工具面板' }).click();
      await page.locator('.studio-type-filters button').filter({ hasText: '学习报告' }).click();
      await page.locator('.studio-resource-row').filter({ hasText: '普通报告' }).click();
      await expect(page.getByRole('heading', { name: '普通报告', exact: true })).toBeVisible();
      expect((await page.getByRole('dialog').boundingBox())!.width).toBeLessThanOrEqual(920);
    }
    expect(errors).toEqual([]);
  });
}
