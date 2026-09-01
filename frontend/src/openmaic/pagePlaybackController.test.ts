import assert from 'node:assert/strict';
import test from 'node:test';
import {
  ManagedPagePlaybackController,
  type PagePlaybackRuntime,
  type PagePlaybackSnapshot,
  type PlaybackRuntimeHandle,
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

class FakePlaybackRuntime implements PlaybackRuntimeHandle {
  readonly events: string[] = [];

  play(): void {
    this.events.push('runtime:play');
  }

  suspend() {
    this.events.push('runtime:suspend');
    return {
      sceneId: 'scene-2',
      actionIndex: 0,
      actionId: 'speech-1',
      phase: 'executing_action' as const,
    };
  }

  resume(): void {
    this.events.push('runtime:resume');
  }

  cancel(): void {
    this.events.push('runtime:cancel');
  }

  dispose(): void {
    this.events.push('runtime:dispose');
  }
}

async function createBoundHarness() {
  const harness = createHarness();
  const runtime = new FakePlaybackRuntime();
  await harness.controller.enter(2);
  harness.controller.bindRuntime(
    2,
    harness.controller.snapshot().revision,
    runtime,
  );
  return { ...harness, runtime };
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
    revision: 2,
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

test('completion succeeds once for the exact playing revision', async () => {
  const { controller } = createHarness();

  await controller.enter(4);
  await controller.play();
  const playing = controller.snapshot();
  assert.equal(controller.complete(playing.sceneIndex, playing.revision), true);
  assert.equal(controller.complete(playing.sceneIndex, playing.revision), false);

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
  assert.equal(controller.complete(stale.sceneIndex, stale.revision), false);

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

test('interrupt decorates the runtime checkpoint and resumes the bound revision', async () => {
  const { controller, runtime } = await createBoundHarness();
  await controller.play();

  const checkpoint = controller.interrupt();

  assert.equal(controller.snapshot().status, 'interrupted');
  assert.equal(checkpoint?.sceneIndex, 2);
  assert.equal(checkpoint?.pageRevision, controller.snapshot().revision);
  assert.equal(controller.resumeInterrupted(checkpoint!), true);
  assert.equal(controller.snapshot().status, 'playing');
  assert.deepEqual(runtime.events, [
    'runtime:play',
    'runtime:suspend',
    'runtime:resume',
  ]);
});

test('rejects a runtime bound to a stale scene revision', async () => {
  const { controller } = createHarness();
  const runtime = new FakePlaybackRuntime();
  await controller.enter(1);

  controller.bindRuntime(1, controller.snapshot().revision - 1, runtime);

  assert.deepEqual(runtime.events, ['runtime:dispose']);
});

test('an interrupted checkpoint can only resume once', async () => {
  const { controller } = await createBoundHarness();
  await controller.play();
  const checkpoint = controller.interrupt();

  assert.equal(controller.resumeInterrupted(checkpoint!), true);
  assert.equal(controller.resumeInterrupted(checkpoint!), false);
});

test('page navigation disposes the bound concrete runtime', async () => {
  const { controller, runtime } = await createBoundHarness();

  await controller.enter(3);

  assert.deepEqual(runtime.events, ['runtime:dispose']);
});

test('manual replay invalidates an interrupted checkpoint', async () => {
  const { controller, runtime } = await createBoundHarness();
  await controller.play();
  const checkpoint = controller.interrupt();
  const interruptedRevision = controller.snapshot().revision;

  await controller.replay();

  assert.equal(controller.snapshot().revision, interruptedRevision + 1);
  assert.equal(controller.snapshot().status, 'playing');
  assert.equal(controller.resumeInterrupted(checkpoint!), false);
  assert.equal(runtime.events.at(-1), 'runtime:dispose');
});
