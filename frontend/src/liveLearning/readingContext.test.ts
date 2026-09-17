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
