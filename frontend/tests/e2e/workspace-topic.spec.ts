import { expect, test } from './fixtures/teacherApp';

test('chat title precedes its topic subtitle and the picker directly offers leaf topics', async ({ teacherPage: page }) => {
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
  await expect(page.locator('.chat-panel__heading').getByTestId('workspace-context-bar')).toBeVisible();
  const titleBox = await page.locator('.chat-panel__title').boundingBox();
  const barBox = await bar.boundingBox();
  expect(barBox!.y).toBeGreaterThanOrEqual(titleBox!.y + titleBox!.height);
  const select = page.getByRole('combobox', {name:'选择讨论知识点'});
  await select.click();
  const options = page.locator('.ant-select-item-option-content');
  await expect(options).toHaveText(['数组', '链表']);
  await options.filter({hasText: '链表'}).click();
  await expect(page).toHaveURL(/scopeId=linked-list/);
  await expect(bar).toContainText('链表');
  await select.fill('数据组织');
  await expect(options).toHaveText(['数组', '链表']);
  await select.press('Escape');
  await page.screenshot({path:'/tmp/edu-ai-workspace-topic.png'});
  await page.setViewportSize({width:390,height:844});
  await expect(bar).toBeVisible();
  expect(await bar.evaluate(el => el.getBoundingClientRect().right <= window.innerWidth)).toBe(true);
});
