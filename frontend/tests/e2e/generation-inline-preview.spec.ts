import { expect, test } from './fixtures/teacherApp';

const title = '链表的实现';
const material = { material_id: 'inline-report', material_type: 'report', course_id: 'course-physics', title,
  owner_user_id: 'teacher-a', visibility: 'private', version: 1, content_hash: 'test-content-hash', content: '# 链表的实现\n\n## 节点结构\n\n节点包含数据域和指针域。\n\n## 插入操作\n\n先连接后继节点，再调整前驱指针。' };

test.beforeEach(async ({ teacherPage: page }) => {
  await page.route('**/api/personal-knowledge/documents**', route => route.fulfill({ json: [] }));
  const job = { edu_job_id: 'inline-job', kind: 'generate_report', status: 'succeeded', progress: 100,
    course_id: 'course-physics', owner_user_id: 'teacher-a', input_summary: { title },
    result_ref: { course_id: 'course-physics', material_type: 'report', material_id: 'inline-report' },
    created_at: '2026-09-08T07:00:00Z', updated_at: '2026-09-08T07:01:00Z' };
  await page.route('**/api/jobs**', route => route.fulfill({ json: { items: [job], next_cursor: null } }));
  await page.route('**/api/courses/course-physics/materials/report/inline-report', route => route.fulfill({ json: material }));
});

test('recent file opens in a wider right panel and returns without navigation', async ({ teacherPage: page }, testInfo) => {
  await page.goto('/#ai?course_id=course-physics');
  const switcher = page.getByRole('button', { name: '生成工厂', exact: true });
  if (page.viewportSize()!.width < 1200) await switcher.click();
  const factory = page.getByTestId('generation-factory');
  await expect(factory.getByRole('button', { name: /链表的实现/ })).toBeVisible();
  await expect(factory.getByRole('button', { name: '让 AI 修改' })).toHaveCount(0);
  const url = page.url();
  const panel = page.locator('.ai-studio-sider--right');
  const before = (await panel.boundingBox())!.width;
  await factory.getByRole('button', { name: /链表的实现/ }).click();
  const preview = page.getByRole('region', { name: '生成文件预览' });
  await expect(preview.getByText('节点包含数据域和指针域。', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(url);
  await expect.poll(async () => (await panel.boundingBox())!.width).toBeGreaterThan(before + 40);
  await page.screenshot({ path: testInfo.outputPath('inline-report-preview.png') });
  await preview.getByRole('button', { name: '返回生成工厂' }).click();
  await expect(factory).toBeVisible();
  await expect(page).toHaveURL(url);
  await expect.poll(async () => Math.abs((await panel.boundingBox())!.width - before)).toBeLessThan(2);
});

test('failed file read stays in place and can be retried', async ({ teacherPage: page }) => {
  let requests = 0;
  await page.route('**/api/courses/course-physics/materials/report/inline-report', route => {
    requests++;
    return route.fulfill(requests === 1 ? { status: 503, json: { detail: 'unavailable' } } : { json: material });
  });
  await page.goto('/#ai?course_id=course-physics');
  const switcher = page.getByRole('button', { name: '生成工厂', exact: true });
  if (page.viewportSize()!.width < 1200) await switcher.click();
  await page.getByTestId('generation-factory').getByRole('button', { name: /链表的实现/ }).click();
  const preview = page.getByRole('region', { name: '生成文件预览' });
  await expect(preview.getByRole('alert')).toContainText('文件暂时无法加载');
  await preview.getByRole('button', { name: '重新加载' }).click();
  await expect(preview.getByText('节点包含数据域和指针域。', { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/#ai\?course_id=course-physics$/);
});


test('reference inserts only the title and sends identity and hash; removing the draft reference clears it', async ({ teacherPage: page }) => {
  const requests: Record<string, any>[] = [];
  await page.route('**/api/chat/v2/stream', route => {
    requests.push(route.request().postDataJSON());
    const payload = { message: { role: 'assistant', content: '节点包含数据域和指针域。' }, conversation: { conversation_id: 'ref-conv' }, action: { name: 'artifact.read' }, artifacts: [], sources: [], trace: { path: 'fast' } };
    return route.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'result', payload })}\n\ndata: ${JSON.stringify({ type: 'done', payload: { conversation_id: 'ref-conv' } })}\n\n` });
  });
  await page.goto('/#ai?course_id=course-physics');
  if (page.viewportSize()!.width < 1200) await page.getByRole('button', { name: '生成工厂', exact: true }).click();
  await page.getByTestId('generation-factory').getByRole('button', { name: /链表的实现/ }).click();
  const preview = page.getByRole('region', { name: '生成文件预览' });
  await preview.getByRole('button', { name: '引用', exact: true }).click();
  if (page.viewportSize()!.width < 1200) await page.getByRole('button', { name: '生成工厂', exact: true }).click();
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await expect(input).toHaveValue('《链表的实现》 ');
  await expect(page.getByText(/正在修改：/)).toHaveCount(0);
  expect(requests).toHaveLength(0);
  await input.fill('《链表的实现》这个文档写了什么');
  await input.press('Enter');
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].artifact_reference).toMatchObject({ artifact_id: 'inline-report', version_id: 'v1', content_hash: 'test-content-hash' });
  expect(requests[0].question).not.toContain('test-content-hash');
  await expect(input).toBeEnabled();
  await input.fill('解释插入操作');
  await input.press('Enter');
  await expect.poll(() => requests.length).toBe(2);
  expect(requests[1].artifact_reference.artifact_id).toBe('inline-report');
  if (page.viewportSize()!.width < 1200) await page.getByRole('button', { name: '生成工厂', exact: true }).click();
  await preview.getByRole('button', { name: '引用', exact: true }).click();
  if (page.viewportSize()!.width < 1200) await page.getByRole('button', { name: '生成工厂', exact: true }).click();
  await expect(input).toHaveValue('《链表的实现》 ');
  await input.fill('普通问题');
  await input.press('Enter');
  await expect.poll(() => requests.length).toBe(3);
  expect(requests[2].artifact_reference).toBeUndefined();
});
