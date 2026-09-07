import assert from 'node:assert/strict';
import test from 'node:test';

import { flattenWorkspaceNodes } from './workspaceScope';

test('knowledge choices preserve duplicate labels and chapter paths', () => {
  const options = flattenWorkspaceNodes({ id: 'root', label: '数据结构', children: [
    { id: 'one', label: '章节一', children: [{ id: 'a', label: '遍历' }] },
    { id: 'two', label: '章节二', children: [{ id: 'b', label: '遍历' }] },
  ] });
  assert.equal(options.find((item) => item.value === 'a')?.label, '数据结构 › 章节一 › 遍历');
  assert.equal(options.find((item) => item.value === 'b')?.label, '数据结构 › 章节二 › 遍历');
  assert.equal(options.some((item) => item.value === 'root'), false);
});
