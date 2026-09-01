import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { Action } from '@openmaic/dsl';
import type {
  ActionEffectsState,
  ActionExecutionContext,
} from './actionEngine.ts';
import type { ClockSource } from './clock.ts';
import {
  PlaybackEngine,
  StalePlaybackCheckpointError,
  type ActionExecutor,
  type PlaybackCheckpoint,
} from './playbackEngine.ts';
import { compileLessonTimeline } from './timeline.ts';

class SequenceClock implements ClockSource {
  constructor(private readonly values: number[]) {}

  currentTimeMs(): number {
    const value = this.values.shift();
    if (value === undefined) throw new Error('Clock read more often than expected');
    return value;
  }
}

class ImmediateExecutor implements ActionExecutor {
  readonly executed: string[] = [];

  async execute(action: Action): Promise<void> {
    this.executed.push(action.id);
  }

  cancelCurrent(): void {}
  clearEffects(): void {}
  dispose(): void {}
}

class DeferredExecutor implements ActionExecutor {
  readonly executed: string[] = [];
  private releaseFirst: (() => void) | null = null;
  cancelCount = 0;

  execute(action: Action): Promise<void> {
    this.executed.push(action.id);
    if (this.executed.length > 1) return Promise.resolve();
    return new Promise((resolve) => {
      this.releaseFirst = resolve;
    });
  }

  release(): void {
    this.releaseFirst?.();
  }

  cancelCurrent(): void {
    this.cancelCount += 1;
    this.release();
  }

  clearEffects(): void {}
  dispose(): void {}
}

class ContextRecordingExecutor implements ActionExecutor {
  readonly contexts = new Map<string, ActionExecutionContext | undefined>();

  async execute(
    action: Action,
    context?: ActionExecutionContext,
  ): Promise<void> {
    this.contexts.set(action.id, context);
  }

  cancelCurrent(): void {}
  clearEffects(): void {}
  dispose(): void {}
}

class NonSettlingCancelExecutor implements ActionExecutor {
  readonly executed: string[] = [];
  private readonly releases: Array<() => void> = [];

  execute(action: Action): Promise<void> {
    this.executed.push(action.id);
    return new Promise((resolve) => {
      this.releases.push(resolve);
    });
  }

  release(index: number): void {
    this.releases[index]?.();
  }

  cancelCurrent(): void {}
  clearEffects(): void {}
  dispose(): void {}
}

class AlwaysDeferredExecutor implements ActionExecutor {
  readonly executed: string[] = [];
  cancelCount = 0;
  private activeRelease: (() => void) | null = null;

  execute(action: Action): Promise<void> {
    this.executed.push(action.id);
    return new Promise((resolve) => {
      this.activeRelease = resolve;
    });
  }

  cancelCurrent(): void {
    this.cancelCount += 1;
    this.activeRelease?.();
    this.activeRelease = null;
  }

  clearEffects(): void {}
  dispose(): void {}
}

function scenes() {
  return [
    {
      id: 'scene-2',
      order: 2,
      actions: [{ id: 'speech-2', type: 'speech', text: 'second' } as Action],
    },
    {
      id: 'scene-1',
      order: 1,
      actions: [{ id: 'speech-1', type: 'speech', text: 'first' } as Action],
    },
  ];
}

function twoSpeechScene() {
  return [
    {
      id: 'scene-1',
      order: 1,
      actions: [
        { id: 'speech-1', type: 'speech', text: 'first' } as Action,
        { id: 'speech-2', type: 'speech', text: 'second' } as Action,
      ],
    },
  ];
}

test('uses timeline scene order and injected clock for action timestamps', async () => {
  const sourceScenes = scenes();
  const timeline = compileLessonTimeline({
    lessonId: 'lesson-order',
    scenes: sourceScenes,
    actionDurationsMs: { 'speech-1': 1000, 'speech-2': 1000 },
  });
  const executor = new ImmediateExecutor();
  const events: Array<[string, string, number]> = [];
  let complete!: () => void;
  const completed = new Promise<void>((resolve) => {
    complete = resolve;
  });

  const engine = new PlaybackEngine(
    sourceScenes,
    new SequenceClock([10, 20, 30, 40]),
    {
      onActionStart: (action, timeMs) => events.push(['start', action.id, timeMs]),
      onActionEnd: (action, timeMs) => events.push(['end', action.id, timeMs]),
      onComplete: complete,
    },
    { timeline, actionExecutor: executor },
  );

  engine.start();
  await completed;

  assert.deepEqual(executor.executed, ['speech-1', 'speech-2']);
  assert.deepEqual(events, [
    ['start', 'speech-1', 10],
    ['end', 'speech-1', 20],
    ['start', 'speech-2', 30],
    ['end', 'speech-2', 40],
  ]);
});

test('emits action end only after synchronous execution resolves', async () => {
  const executor = new DeferredExecutor();
  const events: string[] = [];
  const engine = new PlaybackEngine(
    [{ id: 'scene-1', order: 1, actions: [{ id: 'speech-1', type: 'speech', text: 'wait' }] }],
    new SequenceClock([100, 500]),
    {
      onActionStart: () => events.push('start'),
      onActionEnd: () => events.push('end'),
    },
    { actionExecutor: executor },
  );

  engine.start();
  await Promise.resolve();
  assert.deepEqual(events, ['start']);

  executor.release();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(events, ['start', 'end']);
});

test('stops stale runs without executing later actions or emitting their events', async () => {
  const executor = new DeferredExecutor();
  const events: string[] = [];
  const engine = new PlaybackEngine(
    [
      {
        id: 'scene-1',
        order: 1,
        actions: [
          { id: 'speech-1', type: 'speech', text: 'first' },
          { id: 'speech-2', type: 'speech', text: 'second' },
        ],
      },
    ],
    new SequenceClock([0]),
    {
      onActionStart: (action) => events.push(`start:${action.id}`),
      onActionEnd: (action) => events.push(`end:${action.id}`),
      onEffectsChange: (_effects: ActionEffectsState) => {},
    },
    { actionExecutor: executor },
  );

  engine.start();
  await Promise.resolve();
  engine.stop();
  executor.release();
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.deepEqual(executor.executed, ['speech-1']);
  assert.deepEqual(events, ['start:speech-1']);
});

test('passes compiled focus concurrency to the paired narration action', async () => {
  const sourceScenes = [
    {
      id: 'scene-focus',
      order: 1,
      actions: [
        { id: 'spot-1', type: 'spotlight', elementId: 'title' } as Action,
        { id: 'speech-1', type: 'speech', text: 'paired' } as Action,
      ],
    },
  ];
  const timeline = compileLessonTimeline({
    lessonId: 'lesson-focus',
    scenes: sourceScenes,
    actionDurationsMs: { 'speech-1': 1000 },
  });
  const executor = new ContextRecordingExecutor();
  let complete!: () => void;
  const completed = new Promise<void>((resolve) => {
    complete = resolve;
  });
  const engine = new PlaybackEngine(
    sourceScenes,
    new SequenceClock([0, 0, 0, 1000]),
    { onComplete: complete },
    { timeline, actionExecutor: executor },
  );

  engine.start();
  await completed;

  assert.equal(executor.contexts.get('spot-1')?.hasConcurrentFocus, false);
  assert.equal(executor.contexts.get('speech-1')?.hasConcurrentFocus, true);
});

test('suspending an in-flight action resumes that action from the beginning', async () => {
  const executor = new AlwaysDeferredExecutor();
  const engine = new PlaybackEngine(
    twoSpeechScene(),
    new SequenceClock([0, 10]),
    {},
    { actionExecutor: executor },
  );

  engine.start();
  await Promise.resolve();

  const checkpoint = engine.suspend();
  assert.deepEqual(checkpoint, {
    sceneId: 'scene-1',
    actionIndex: 0,
    actionId: 'speech-1',
    phase: 'executing_action',
  });

  engine.resume(checkpoint);
  await Promise.resolve();

  assert.deepEqual(executor.executed, ['speech-1', 'speech-1']);
  engine.stop();
});

test('suspending between actions resumes at the next action', async () => {
  const executor = new ImmediateExecutor();
  let checkpoint: PlaybackCheckpoint | null = null;
  let releaseSuspended!: () => void;
  const suspended = new Promise<void>((resolve) => {
    releaseSuspended = resolve;
  });
  let releaseCompleted!: () => void;
  const completed = new Promise<void>((resolve) => {
    releaseCompleted = resolve;
  });
  const engineRef: { current: PlaybackEngine | null } = { current: null };
  const engine = new PlaybackEngine(
    twoSpeechScene(),
    new SequenceClock([0, 10, 20, 30]),
    {
      onActionEnd: (action) => {
        if (action.id === 'speech-1') {
          checkpoint = engineRef.current?.suspend() ?? null;
          releaseSuspended();
        }
      },
      onComplete: releaseCompleted,
    },
    { actionExecutor: executor },
  );
  engineRef.current = engine;

  engine.start();
  await suspended;

  const suspendedCheckpoint = checkpoint as PlaybackCheckpoint | null;
  assert.ok(suspendedCheckpoint);
  assert.equal(suspendedCheckpoint.phase, 'between_actions');
  assert.equal(suspendedCheckpoint.actionIndex, 1);
  assert.equal(suspendedCheckpoint.actionId, 'speech-2');

  engine.resume(suspendedCheckpoint);
  await completed;
  assert.deepEqual(executor.executed, ['speech-1', 'speech-2']);
});

test('resume rejects stale scene and action identities', async () => {
  const executor = new DeferredExecutor();
  const engine = new PlaybackEngine(
    twoSpeechScene(),
    new SequenceClock([0]),
    {},
    { actionExecutor: executor },
  );
  engine.start();
  await Promise.resolve();
  const checkpoint = engine.suspend();

  assert.throws(
    () => engine.resume({ ...checkpoint, sceneId: 'stale-scene' }),
    StalePlaybackCheckpointError,
  );
  assert.throws(
    () => engine.resume({ ...checkpoint, actionId: 'stale-action' }),
    StalePlaybackCheckpointError,
  );
});

test('repeated suspend returns the same checkpoint without cancelling twice', async () => {
  const executor = new AlwaysDeferredExecutor();
  const engine = new PlaybackEngine(
    twoSpeechScene(),
    new SequenceClock([0]),
    {},
    { actionExecutor: executor },
  );
  engine.start();
  await Promise.resolve();

  const first = engine.suspend();
  const second = engine.suspend();

  assert.deepEqual(second, first);
  assert.equal(executor.cancelCount, 1);
});

test('completion from the pre-suspend run cannot advance the resumed cursor', async () => {
  const executor = new NonSettlingCancelExecutor();
  const ended: string[] = [];
  const engine = new PlaybackEngine(
    twoSpeechScene(),
    new SequenceClock([0, 10, 20, 30]),
    { onActionEnd: (action) => ended.push(action.id) },
    { actionExecutor: executor },
  );
  engine.start();
  await Promise.resolve();
  const checkpoint = engine.suspend();
  engine.resume(checkpoint);
  await Promise.resolve();

  executor.release(0);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(ended, []);

  executor.release(1);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(ended, ['speech-1']);
  engine.stop();
});
