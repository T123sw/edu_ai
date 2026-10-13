import test from 'node:test';
import assert from 'node:assert/strict';
import { acceptReadingMessage } from './readingContext';
const ref = { course_id: 'course', material_type: 'report', material_id: 'doc', version: 1 };
const message = { type: 'learning-reading-context', channel_id: 'channel', resource_ref: ref, sequence: 2, locator: { kind: 'document', scroll_top: 200 }, reached_end: true };
test('bind observations to channel, full resource version and sequence', () => {
  assert.ok(acceptReadingMessage(message, 'channel', ref, 1));
  assert.equal(acceptReadingMessage(message, 'old-channel', ref, 1), false);
  assert.equal(acceptReadingMessage(message, 'channel', { ...ref, version: 2 }, 1), false);
  assert.equal(acceptReadingMessage(message, 'channel', ref, 2), false);
  assert.equal(acceptReadingMessage({ ...message, locator: { kind: 'document', scroll_top: NaN } }, 'channel', ref, 1), false);
  assert.ok(acceptReadingMessage({ ...message, sequence: 3, locator: { kind: 'document', scroll_top: 10 } }, 'channel', ref, 2));
});

test('classroom snapshot accepts separate viewed/lecture pages and rejects invalid pointers', () => {
  const pptRef = { ...ref, material_type: 'classroom' };
  const lecture = { scene_id: 'previous', action_id: 'speech', speech_action_id: 'speech', sentence_index: 1,
    sentence_alignment: 'estimated', speech_completed: false, highlighted_element_ids: ['formula'] };
  const ppt = { ...message, resource_ref: pptRef, locator: { kind: 'classroom', scene_id: 'viewed' }, classroom: { status: 'idle', lecture } };
  assert.ok(acceptReadingMessage(ppt, 'channel', pptRef, 1));
  assert.equal(acceptReadingMessage({ ...ppt, classroom: { status: 'made-up' } }, 'channel', pptRef, 1), false);
  assert.equal(acceptReadingMessage({ ...ppt, classroom: { status: 'playing', lecture: { ...lecture, sentence_index: -1 } } }, 'channel', pptRef, 1), false);
  assert.equal(acceptReadingMessage({ ...message, classroom: ppt.classroom }, 'channel', ref, 1), false);
});
