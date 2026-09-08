import { expect, test } from './fixtures/teacherApp';
const ref = { artifact_id: 'draft-report', artifact_type: 'report', version_id: 'v1', source_course_id: 'course-physics', title: '链表的实现', content_hash: 'original-hash' };
const savedRef = { ...ref, artifact_id: 'saved-report', title: '链表的实现（修改稿）', content_hash: 'saved-hash' };
const original = '# 链表的实现\n\n## 动态内存分配\n\n原来的例子。\n\n## 遍历\n\n遍历说明保持不变。';

test('colored draft iterates, restores after refresh and saves the shown revision', async ({ teacherPage: page }, info) => {
  const requests: any[] = [];
  let latest: any = null, revision = 0, saved = false;
  await page.route('**/api/personal-knowledge/documents**', r => r.fulfill({ json: [] }));
  await page.route('**/api/chat/conversations?**', r => r.fulfill({ json: { conversations: [{ conversation_id: 'draft-conv', course_id: 'course-physics', scope_type: 'course', title: '修改报告', message_count: 1 }], count: 1, total: 1, total_messages: 1 } }));
  await page.route('**/api/chat/conversations/draft-conv', r => r.fulfill({ json: {
    conversation_id: 'draft-conv', course_id: 'course-physics', scope_type: 'course', history: [], message_count: 0,
    state: { artifact_reference: ref, latest_revision_outcome: latest, pending_operation: latest?.draft ? { kind: 'artifact_revision', id: 'draft-op' } : null }
  } }));
  const originalMaterial = { material_id: ref.artifact_id, material_type: 'report', course_id: ref.source_course_id,
    title: ref.title, owner_user_id: 'teacher-a', visibility: 'private', version: 1, content: original, created_at: '2026-09-07T00:00:00Z' };
  const savedMaterial = { ...originalMaterial, material_id: savedRef.artifact_id, title: savedRef.title,
    content: original.replace('原来的例子。', '简洁的新例子。'), created_at: '2026-09-08T00:00:00Z' };
  await page.route('**/api/courses/course-physics/materials?**', r => r.fulfill({ json: saved ? [savedMaterial, originalMaterial] : [originalMaterial] }));
  await page.route('**/api/courses/course-physics/materials/report/draft-report', r => r.fulfill({ json: originalMaterial }));
  await page.route('**/api/courses/course-physics/materials/report/saved-report', r => r.fulfill({ json: savedMaterial }));
  await page.route('**/api/chat/v2/stream', r => {
    const body = r.request().postDataJSON(); requests.push(body);
    if (body.artifact_draft_action) {
      saved = body.artifact_draft_action.action === 'save';
      latest = { status: saved ? 'completed' : 'discarded', message: saved ? '已保存为新文档，原文档已保留。' : '已放弃修改，原文未改变。', artifact_reference: saved ? savedRef : ref, changes: [] };
    } else {
      revision++;
      latest = { status: 'preview', operation_id: 'draft-op', message: '补充具体例子帮助学生理解动态内存分配。修改稿尚未保存，要保存还是继续调整？', artifact_reference: ref,
        draft: { draft_id: 'draft-1', revision, reference: ref, focus: '动态内存分配', reason: '补充具体例子。', benefit: '帮助学生理解。', segments: [
          { kind: 'same', text: '# 链表的实现\n\n' }, { kind: 'focus', text: '## 动态内存分配\n\n' },
          { kind: 'delete', text: '原来的例子。\n\n' }, { kind: 'insert', text: revision === 1 ? '详细的新例子。\n\n' : '简洁的新例子。\n\n' },
          { kind: 'same', text: '## 遍历\n\n遍历说明保持不变。' }
        ] } };
    }
    const payload = { message: { role: 'assistant', content: latest.message }, conversation: { conversation_id: 'draft-conv' }, action: { name: 'artifact.revise' }, artifact_revision: latest, artifacts: [], sources: [], trace: { path: 'fast' } };
    return r.fulfill({ contentType: 'text/event-stream', body: `data: ${JSON.stringify({ type: 'result', payload })}\n\ndata: ${JSON.stringify({ type: 'done', payload: { conversation_id: 'draft-conv' } })}\n\n` });
  });
  await page.goto('/#ai?course_id=course-physics');
  const input = page.getByPlaceholder('开始输入问题…（Shift + Enter 换行）');
  await expect(input).toBeVisible();
  await input.fill('动态内存分配加几个例子'); await input.press('Enter');
  const draft = page.getByRole('region', { name: '文档修改稿' });
  await expect(draft).toBeVisible();
  await expect(draft.locator('[data-change="focus"]')).toContainText('动态内存分配');
  await expect(draft.locator('del[aria-label="拟删除内容"]')).toContainText('原来的例子');
  await expect(draft.locator('ins[aria-label="拟新增内容"]')).toContainText('详细的新例子');
  expect(saved).toBe(false); expect(requests).toHaveLength(1);
  await page.screenshot({ path: info.outputPath('colored-draft.png') });
  if (page.viewportSize()!.width < 1200) await page.getByRole('button', { name: '生成工厂', exact: true }).click();
  await input.fill('再简洁一点'); await input.press('Enter');
  await expect(draft.locator('ins[aria-label="拟新增内容"]')).toContainText('简洁的新例子');
  await expect(draft.locator('del[aria-label="拟删除内容"]')).toContainText('原来的例子');
  expect(saved).toBe(false);
  await page.reload();
  const factory = page.getByTestId('generation-factory');
  await expect(page.getByRole('region', { name: '生成文件预览' })).toHaveCount(0);
  if (page.viewportSize()!.width < 1200) await page.getByRole('button', { name: '生成工厂', exact: true }).click();
  await factory.getByRole('button', { name: /链表的实现/ }).click();
  await expect(draft).toBeVisible();
  await expect(draft).toContainText('简洁的新例子');
  await draft.getByRole('button', { name: '保存修改', exact: true }).click();
  await expect.poll(() => requests.length).toBe(3);
  expect(requests[2].artifact_draft_action).toEqual({ action: 'save', draft_id: 'draft-1', revision: 2 });
  await expect(draft).toHaveCount(0);
  await expect(page.getByRole('region', { name: '生成文件预览' })).toContainText('简洁的新例子');
  await page.getByRole('button', { name: '返回生成工厂' }).click();
  await expect(factory.getByRole('button', { name: /链表的实现（修改稿）/ })).toHaveCount(1);
  await page.reload();
  await expect(page.getByRole('region', { name: '生成文件预览' })).toHaveCount(0);
  if (page.viewportSize()!.width < 1200) await page.getByRole('button', { name: '生成工厂', exact: true }).click();
  await expect(factory.getByRole('button', { name: /链表的实现（修改稿）/ })).toBeVisible();
  await factory.getByRole('button', { name: /链表的实现（修改稿）/ }).click();
  await expect(page.getByRole('region', { name: '生成文件预览' })).toContainText('简洁的新例子');
  await page.getByRole('button', { name: '返回生成工厂' }).click();
  await factory.locator('button.generation-factory__job').filter({ hasText: '链表的实现' }).filter({ hasNotText: '修改稿' }).click();
  await expect(page.getByRole('region', { name: '生成文件预览' })).toContainText('原来的例子');
  await expect(page).toHaveURL(/#ai\?course_id=course-physics$/);
});
