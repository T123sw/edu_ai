import { expect, test } from './fixtures/teacherApp';

test('chat title precedes its topic subtitle and the picker expands chapters to reveal leaf topics', async ({ teacherPage: page }) => {
  await page.route('**/api/personal-knowledge/documents**', route => route.fulfill({json: []}));
  await page.route('**/api/courses/*/knowledge-graph', route => route.fulfill({json: {
    root: { id: 'root', label: '计算思维', children: [
      { id: 'chapter', label: '数据组织', children: [
        { id: 'array', label: '数组' }, { id: 'linked-list', label: '链表' },
      ] },
    ] },
  }}));
  await page.goto('/#ai?course_id=course-physics');
  const bar = page.getByTestId('workspace-context-bar');
  // The AI workspace is lazy-loaded; parallel cold starts can exceed five seconds.
  await expect(page.locator('.chat-panel__heading').getByTestId('workspace-context-bar')).toBeVisible({ timeout: 15000 });
  const titleBox = await page.locator('.chat-panel__title').boundingBox();
  const barBox = await bar.boundingBox();
  expect(barBox!.y).toBeGreaterThanOrEqual(titleBox!.y + titleBox!.height);
  const select = page.getByRole('combobox', {name:'选择备课知识点'});
  await bar.getByRole('button', { name: '调整', exact: true }).click();
  await page.locator('.workspace-context-bar__adjustment .ant-select-selector').click();
  const popup = page.locator('.workspace-topic-tree-popup');
  const titles = popup.locator('.ant-select-tree-title');
  await expect(titles).toHaveText(['计算思维', '数据组织']);
  await titles.filter({hasText: '数据组织'}).click();
  await expect(titles).toHaveText(['计算思维', '数据组织', '数组', '链表']);
  await expect(page).not.toHaveURL(/scopeId=chapter/);
  await titles.filter({hasText: '数据组织'}).click();
  await expect(titles).toHaveText(['计算思维', '数据组织']);
  await titles.filter({hasText: '数据组织'}).click();
  await titles.filter({hasText: '链表'}).click();
  await expect(page).toHaveURL(/scopeId=linked-list/);
  await expect(bar).toContainText('链表');
  await bar.getByRole('button', { name: '调整', exact: true }).click();
  await page.locator('.workspace-context-bar__adjustment .ant-select-selector').click();
  await expect(titles).toHaveText(['计算思维', '数据组织', '数组', '链表']);
  await select.fill('数组');
  await expect(titles).toHaveText(['计算思维', '数据组织', '数组']);
  await select.fill('');
  await page.screenshot({path:'/tmp/edu-ai-topic-tree-expanded.png'});
  await select.press('Escape');
  await page.screenshot({path:'/tmp/edu-ai-workspace-topic.png'});
  await page.setViewportSize({width:390,height:844});
  await expect(bar).toBeVisible();
  expect(await bar.evaluate(el => el.getBoundingClientRect().right <= window.innerWidth)).toBe(true);
});
