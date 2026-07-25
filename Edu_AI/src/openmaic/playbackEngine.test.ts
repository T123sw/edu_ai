import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { Action } from '@openmaic/dsl';
import type {
  ActionEffectsState,
  ActionExecutionContext,
} from './actionEngine.ts';
import type { ClockSource } from './clock.ts';
import { PlaybackEngine, type ActionExecutor } from './playbackEngine.ts';
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

  clearEffects(): void {}
  dispose(): void {}
}

class DeferredExecutor implements ActionExecutor {
  readonly executed: string[] = [];
  private releaseFirst: (() => void) | null = null;

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
