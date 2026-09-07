import assert from 'node:assert/strict';
import test from 'node:test';
import { getWorkspaceTopicOptions } from './workspaceTopicOptions';

test('only leaves are offered while duplicate topic names retain distinct paths', () => {
  const options = getWorkspaceTopicOptions({ id: 'root', label: '课程', children: [
    { id: 'chapter-a', label: '章节一', children: [{ id: 'leaf-a', label: '基本概念' }] },
    { id: 'chapter-b', label: '章节二', children: [{ id: 'leaf-b', label: '基本概念', children: [] }] },
  ] });
  assert.deepEqual(options, [
    { value: 'leaf-a', label: '基本概念', title: '课程 › 章节一 › 基本概念' },
    { value: 'leaf-b', label: '基本概念', title: '课程 › 章节二 › 基本概念' },
  ]);
  assert.deepEqual(getWorkspaceTopicOptions(undefined), []);
  assert.deepEqual(getWorkspaceTopicOptions({id:'root', label:'空课程'}), []);
});
