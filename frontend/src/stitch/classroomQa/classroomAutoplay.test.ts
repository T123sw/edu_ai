import assert from 'node:assert/strict';
import test from 'node:test';
import { completeAndAdvance } from './classroomAutoplay.ts';

function createHarness({ complete = true, enterError = null as Error | null } = {}) {
  const events: string[] = [];
  const controller = {
    complete(sceneIndex: number, revision: number) {
      events.push(`complete:${sceneIndex}:${revision}`);
      return complete;
    },
    async enter(sceneIndex: number) {
      events.push(`enter:${sceneIndex}`);
      if (enterError) throw enterError;
    },
    async play() {
      events.push('play');
    },
  };
  return { controller, events };
}

test('a valid completion enters and plays the next page in order', async () => {
  const { controller, events } = createHarness();

  await completeAndAdvance({ controller, sceneIndex: 1, revision: 7, sceneCount: 3 });

  assert.deepEqual(events, ['complete:1:7', 'enter:2', 'play']);
});

test('the final page completes without wrapping', async () => {
  const { controller, events } = createHarness();

  await completeAndAdvance({ controller, sceneIndex: 2, revision: 7, sceneCount: 3 });

  assert.deepEqual(events, ['complete:2:7']);
});

test('a stale completion cannot navigate and a failed enter cannot play', async () => {
  const stale = createHarness({ complete: false });
  await completeAndAdvance({
    controller: stale.controller,
    sceneIndex: 1,
    revision: 6,
    sceneCount: 3,
  });
  assert.deepEqual(stale.events, ['complete:1:6']);

  const failed = createHarness({ enterError: new Error('enter failed') });
  await assert.rejects(
    completeAndAdvance({
      controller: failed.controller,
      sceneIndex: 1,
      revision: 7,
      sceneCount: 3,
    }),
    /enter failed/,
  );
  assert.deepEqual(failed.events, ['complete:1:7', 'enter:2']);
});
