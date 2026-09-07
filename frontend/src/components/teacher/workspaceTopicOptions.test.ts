import assert from 'node:assert/strict';
import test from 'node:test';
import { getWorkspaceTopicOptions, getWorkspaceTopicTree, getWorkspaceTopicAncestors } from './workspaceTopicOptions';

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

test('topic tree retains chapters for navigation and expands the selected topic path', () => {
  const tree = getWorkspaceTopicTree({id:'root', label:'课程', children:[
    {id:'chapter', label:'章节', children:[{id:'leaf', label:'知识点'}]},
  ]});
  assert.equal(tree[0].selectable, false);
  assert.equal(tree[0].children![0].selectable, false);
  assert.deepEqual(tree[0].children![0].children![0], {
    value:'leaf', title:'知识点', path:'课程 › 章节 › 知识点', selectable:true,
  });
  assert.deepEqual(getWorkspaceTopicAncestors(tree, 'leaf'), ['root', 'chapter']);
  assert.deepEqual(getWorkspaceTopicAncestors(tree, 'missing'), []);
  assert.deepEqual(getWorkspaceTopicTree(undefined), []);
});
