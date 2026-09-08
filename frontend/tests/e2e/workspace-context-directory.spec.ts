import { expect, test } from './fixtures/teacherApp';

test('preparation context changes leave the full course directory intact', async ({ teacherPage: page }, testInfo) => {
  const documentRequests: string[] = [];
  page.on('request', request => {
    if (request.url().includes('/knowledge-base/documents') && new URL(request.url()).searchParams.get('limit') === '500') documentRequests.push(request.url());
  });
  await page.route('**/api/courses/course-physics/knowledge-graph', route => route.fulfill({ json: { root: {
    id: 'physics', label: '大学物理', children: [
      { id: 'mechanics', label: '力学' }, { id: 'optics', label: '光学' },
    ],
  } } }));
  await page.goto('/#ai?course_id=course-physics&scopeType=knowledge_point&scopeId=mechanics');
  const context = page.getByTestId('workspace-context-bar');
  await expect(context.locator('.workspace-context-bar__current')).toHaveText('力学');
  await expect(context.getByRole('combobox')).toHaveCount(0);
  const openSources = () => page.getByRole('button', { name: testInfo.project.name === 'mobile' ? '知识库' : '展开知识库', exact: true }).click();
  const closeSources = () => page.getByRole('button', { name: testInfo.project.name === 'mobile' ? '知识库' : '折叠知识库', exact: true }).click();
  await openSources();
  const headers = page.locator('.source-panel__tree-node-header');
  await expect(headers).toHaveCount(3);
  await expect(headers.first()).toContainText('大学物理');
  await expect(headers.last()).toContainText('光学');
  await headers.first().click();
  await expect(headers.first()).toHaveAttribute('aria-expanded', 'false');
  await closeSources();
  await context.getByRole('button', { name: '调整', exact: true }).click();
  await page.locator('.workspace-context-bar__adjustment .ant-select-selector').click();
  await page.locator('.workspace-topic-tree-popup .ant-select-tree-title').getByText('光学', { exact: true }).click();
  await expect(context.locator('.workspace-context-bar__current')).toHaveText('光学');
  await expect(page).toHaveURL(/scopeId=optics/);
  await openSources();
  await expect(headers.first()).toHaveAttribute('aria-expanded', 'false');
  await headers.first().click();
  await expect(headers).toHaveCount(3);
  await closeSources();
  await context.getByRole('button', { name: '调整', exact: true }).click();
  await page.getByRole('button', { name: '课程整体', exact: true }).click();
  await expect(context.locator('.workspace-context-bar__current')).toHaveText('课程整体');
  await expect(page).toHaveURL(/scopeType=course/);
  await openSources();
  await expect(headers).toHaveCount(3);
  expect(documentRequests.length).toBeGreaterThan(0);
  for (const request of documentRequests) {
    const params = new URL(request).searchParams;
    expect(params.get('scope_type')).toBe('course');
    expect(params.get('scope_id')).toBeNull();
    expect(params.get('aggregate')).toBe('true');
  }
});
