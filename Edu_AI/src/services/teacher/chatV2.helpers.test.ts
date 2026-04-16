import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseChatReplyV2StreamChunk } from './chatV2';

test('parseChatReplyV2StreamChunk parses complete SSE frames and preserves remainder', () => {
  const parsed = parseChatReplyV2StreamChunk(
    '',
    'data: {"type":"metadata","payload":{"conversation_id":"conv-1"}}\n\n' +
      'data: {"type":"delta","payload":{"content":"he',
  );

  assert.equal(parsed.events.length, 1);
  assert.equal(parsed.events[0].type, 'metadata');
  assert.equal(parsed.remainder, 'data: {"type":"delta","payload":{"content":"he');
});
