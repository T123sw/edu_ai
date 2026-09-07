import assert from 'node:assert/strict';
import test from 'node:test';
import { narrationSentences, sentenceAtProgress } from './narrationSentences';
test('paragraph narration presents one sentence at a time', () => {
  const text = '先选择基准。再进行分区！最后递归。';
  assert.deepEqual(narrationSentences(text), ['先选择基准。', '再进行分区！', '最后递归。']);
  assert.equal(sentenceAtProgress(text, 0), '先选择基准。');
  assert.equal(sentenceAtProgress(text, 0.5), '再进行分区！');
  assert.equal(sentenceAtProgress(text, 1), '最后递归。');
});
