import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mergeSessionPage, type SessionPage } from './learningClient';

function page(session: string, positions: number[], cursor: string | null): SessionPage {
  return { session_id: session, topic_id: session, next_cursor: cursor,
    items: positions.map(position => ({ id: `${session}:${position}`, position, role: 'assistant', text: String(position), resourceId: 'r', resourceTitle: '' })) };
}
test('late latest page does not discard loaded history or duplicate messages', () => {
  const latest = page('a', [4, 5], 'older');
  const full = mergeSessionPage(latest, page('a', [0, 1, 2, 3], null));
  const refreshed = mergeSessionPage(full, page('a', [4, 5, 6], 'older'));
  assert.deepEqual(refreshed.items.map(m => m.position), [0, 1, 2, 3, 4, 5, 6]);
  assert.equal(refreshed.next_cursor, null);
});
test('different session never merges private histories', () => {
  const next = mergeSessionPage(page('a', [0, 1], null), page('b', [0], null));
  assert.deepEqual(next.items.map(m => m.id), ['b:0']);
});
