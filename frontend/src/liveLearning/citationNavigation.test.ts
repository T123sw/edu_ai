import test from 'node:test';
import assert from 'node:assert/strict';
import { citationUrl } from './citationNavigation';
import { acceptReadingMessage } from './readingContext';
const ref = { course_id: '课程', material_type: 'quiz', material_id: '练习', version: 3 };
test('quiz pointers are version and type bound', () => {
  const message = { type: 'learning-reading-context', channel_id: 'c', resource_ref: ref, sequence: 1, reached_end: false, selected_text: '第二题', intent: 'ask', locator: { kind: 'quiz', question_index: 1 } };
  assert.ok(acceptReadingMessage(message, 'c', ref, 0));
  assert.equal(acceptReadingMessage({ ...message, locator: { kind: 'quiz', question_index: -1 } }, 'c', ref, 0), false);
  const report = { ...ref, material_type: 'report' };
  assert.equal(acceptReadingMessage({ ...message, resource_ref: report }, 'c', report, 0), false);
  assert.equal(acceptReadingMessage(message, 'c', { ...ref, version: 4 }, 0), false);
});
test('citation links preserve source version and supported locations without guessing', () => {
  for (const locator of [{ kind: 'quiz', question_index: 1 }, { kind: 'document', block_id: 'report-v1:3:15:12345678' }, { kind: 'classroom', scene_id: 'scene & 2' }]) {
    const url = citationUrl({ resource_ref: ref, locator });
    const params = new URLSearchParams(url.split('#ai?')[1]);
    assert.equal(params.get('version'), '3');
    assert.equal(params.get('course_id'), '课程');
    const key = Object.keys(locator)[1];
    assert.equal(params.get(key), String(locator[key as keyof typeof locator]));
  }
  assert.ok(!citationUrl({ resource_ref: ref }).includes('question_index'));
});
