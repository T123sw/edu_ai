import assert from 'node:assert/strict';
import test from 'node:test';
import {
  ManagedPagePlaybackController,
  type PagePlaybackRuntime,
  type PagePlaybackSnapshot,
} from './pagePlaybackController.ts';

function createHarness() {
  const events: string[] = [];
  const snapshots: PagePlaybackSnapshot[] = [];
  const controller = new ManagedPagePlaybackController(
    (sceneIndex): PagePlaybackRuntime => ({
      async play() {
        events.push(`play:${sceneIndex}`);
      },
      pause() {
        events.push(`pause:${sceneIndex}`);
      },
      dispose() {
        events.push(`dispose:${sceneIndex}`);
      },
    }),
    (snapshot) => snapshots.push(snapshot),
  );
  return { controller, events, snapshots };
}

test('entering another page disposes all playback owned by the previous page', async () => {
  const { controller, events } = createHarness();

  await controller.enter(0);
  await controller.play();
  await controller.enter(1);

  assert.deepEqual(events, ['play:0', 'dispose:0']);
  assert.deepEqual(controller.snapshot(), {
    sceneIndex: 1,
    status: 'idle',
    revision: 3,
  });
});

test('pause and replay operate only on the current page', async () => {
  const { controller, events } = createHarness();

  await controller.enter(2);
  await controller.play();
  controller.pause();
  await controller.replay();

  assert.deepEqual(events, [
    'play:2',
    'pause:2',
    'dispose:2',
    'play:2',
  ]);
  assert.equal(controller.snapshot().sceneIndex, 2);
  assert.equal(controller.snapshot().status, 'playing');
});

test('completion never advances to the next page', async () => {
  const { controller } = createHarness();

  await controller.enter(4);
  await controller.play();
  const playing = controller.snapshot();
  controller.complete(playing.sceneIndex, playing.revision);

  assert.deepEqual(controller.snapshot(), {
    sceneIndex: 4,
    status: 'completed',
    revision: playing.revision,
  });
});

test('stale completion cannot finish a newly entered page', async () => {
  const { controller } = createHarness();

  await controller.enter(0);
  await controller.play();
  const stale = controller.snapshot();
  await controller.enter(1);
  controller.complete(stale.sceneIndex, stale.revision);

  assert.equal(controller.snapshot().sceneIndex, 1);
  assert.equal(controller.snapshot().status, 'idle');
});

test('leave and dispose are idempotent and reject further commands', async () => {
  const { controller, events } = createHarness();

  await controller.enter(0);
  controller.leave();
  controller.leave();
  controller.dispose();
  await controller.play();

  assert.deepEqual(events, ['dispose:0']);
  assert.deepEqual(controller.snapshot(), {
    sceneIndex: -1,
    status: 'idle',
    revision: 2,
  });
});
