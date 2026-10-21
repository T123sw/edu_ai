import test from 'node:test';
import assert from 'node:assert/strict';
import { actionFeedback } from './pagesModel';

test('feedback uses current operation facts including zero, false and arrays', () => {
  assert.equal(actionFeedback('比较 {{facts.left}} 与 {{facts.right}}；结果 {{after.arr}}；{{facts.swap}}', {
    facts: { left: 0, right: 2, swap: false }, after: { arr: [0, 2] },
  }), '比较 0 与 2；结果 [0,2]；false');
});
test('missing facts fall back instead of showing a partially invented explanation', () => {
  assert.equal(actionFeedback('左值 {{facts.left}}、右值 {{facts.right}}', { facts: { left: 3 } }), undefined);
  assert.equal(actionFeedback('{{facts.constructor}}', { facts: {} }), undefined);
});
