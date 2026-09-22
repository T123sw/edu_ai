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

test('mount refresh and polling wait for the same slow enter; history is read only afterwards', async () => {
  const { createSessionReader } = await import('./learningClient');
  const calls: boolean[] = [];
  let finish!: (value: SessionPage) => void;
  const pending = new Promise<SessionPage>(resolve => { finish = resolve; });
  const read = createSessionReader(async enter => {
    calls.push(enter);
    return enter ? pending : page('a', [0, 1], null);
  });
  const enter = read(true), refresh = read(), poll = read();
  assert.deepEqual(calls, [true]);
  finish(page('a', [0], null));
  assert.equal((await enter).session_id, 'a');
  await Promise.all([refresh, poll]);
  assert.deepEqual(calls, [true]);
  assert.equal((await read()).items.length, 2);
  assert.deepEqual(calls, [true, false]);
});

test('failed enter can retry without premature history reads', async () => {
  const { createSessionReader } = await import('./learningClient');
  let calls = 0;
  const read = createSessionReader(async enter => {
    assert.equal(enter, true);
    if (++calls === 1) throw new Error('offline');
    return page('b', [0], null);
  });
  await assert.rejects(read(), /offline/);
  assert.equal((await read()).session_id, 'b');
});
