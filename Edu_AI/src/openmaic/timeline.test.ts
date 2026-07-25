import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { Action } from '@openmaic/dsl';
import { compileLessonTimeline, type TimelineSourceScene } from './timeline.ts';

function scene(
  id: string,
  order: number,
  actions: Action[],
  slideRef = `slide:${id}`,
): TimelineSourceScene {
  return { id, order, actions, slideRef };
}

test('compiles stable clip ids and absolute scene offsets', () => {
  const timeline = compileLessonTimeline({
    lessonId: 'lesson-1',
    scenes: [
      scene('scene-2', 2, [{ id: 'speech-2', type: 'speech', text: 'second' }]),
      scene('scene-1', 1, [{ id: 'speech-1', type: 'speech', text: 'first' }]),
    ],
    actionDurationsMs: {
      'speech-1': 1200,
      'speech-2': 800,
    },
  });

  assert.equal(timeline.lessonId, 'lesson-1');
  assert.equal(timeline.durationMs, 2000);
  assert.deepEqual(
    timeline.scenes.map(({ sceneId, startMs, durationMs }) => ({ sceneId, startMs, durationMs })),
    [
      { sceneId: 'scene-1', startMs: 0, durationMs: 1200 },
      { sceneId: 'scene-2', startMs: 1200, durationMs: 800 },
    ],
  );
  assert.equal(timeline.scenes[0].clips[0].id, 'speech-1:clip');
  assert.equal(timeline.scenes[1].clips[0].id, 'speech-2:clip');
});

test('pairs pending spotlight and laser clips with the following speech', () => {
  const timeline = compileLessonTimeline({
    lessonId: 'lesson-focus',
    scenes: [
      scene('scene-focus', 1, [
        { id: 'spot-1', type: 'spotlight', elementId: 'title' },
        { id: 'laser-1', type: 'laser', elementId: 'title' },
        { id: 'speech-1', type: 'speech', text: '讲解标题' },
      ]),
    ],
    actionDurationsMs: { 'speech-1': 3600 },
  });

  const [spotlight, laser, speech] = timeline.scenes[0].clips;
  assert.deepEqual(
    [spotlight.startMs, spotlight.durationMs, spotlight.concurrentWith],
    [0, 3600, 'speech-1:clip'],
  );
  assert.deepEqual(
    [laser.startMs, laser.durationMs, laser.concurrentWith],
    [0, 3600, 'speech-1:clip'],
  );
  assert.deepEqual([speech.startMs, speech.durationMs, speech.track], [0, 3600, 'narration']);
});

test('keeps synchronous actions serial while focus actions do not advance time', () => {
  const timeline = compileLessonTimeline({
    lessonId: 'lesson-serial',
    scenes: [
      scene('scene-serial', 1, [
        { id: 'speech-a', type: 'speech', text: 'A' },
        { id: 'spot-b', type: 'spotlight', elementId: 'b' },
        { id: 'speech-b', type: 'speech', text: 'B' },
        { id: 'wb-open', type: 'wb_open' },
      ]),
    ],
    actionDurationsMs: {
      'speech-a': 1000,
      'speech-b': 2000,
      'wb-open': 500,
    },
  });

  const clips = timeline.scenes[0].clips;
  assert.deepEqual(
    clips.map(({ actionId, startMs }) => [actionId, startMs]),
    [
      ['speech-a', 0],
      ['spot-b', 1000],
      ['speech-b', 1000],
      ['wb-open', 3000],
    ],
  );
  assert.equal(timeline.scenes[0].durationMs, 3500);
});

test('uses fixed duration for orphan focus actions', () => {
  const timeline = compileLessonTimeline({
    lessonId: 'lesson-orphan',
    scenes: [scene('scene-orphan', 1, [{ id: 'spot-only', type: 'spotlight', elementId: 'x' }])],
    orphanFocusDurationMs: 4321,
  });

  assert.deepEqual(timeline.scenes[0].clips[0], {
    id: 'spot-only:clip',
    actionId: 'spot-only',
    type: 'spotlight',
    track: 'focus',
    startMs: 0,
    durationMs: 4321,
    durationSource: 'fixed',
    payload: { elementId: 'x' },
  });
  assert.equal(timeline.durationMs, 4321);
});

test('skips live-only discussion actions in the linear timeline', () => {
  const timeline = compileLessonTimeline({
    lessonId: 'lesson-linear',
    scenes: [
      scene('scene-linear', 1, [
        { id: 'discussion-1', type: 'discussion', topic: '自由讨论' },
        { id: 'speech-1', type: 'speech', text: '线性讲解' },
      ]),
    ],
    actionDurationsMs: { 'speech-1': 900 },
  });

  assert.deepEqual(timeline.scenes[0].clips.map((clip) => clip.actionId), ['speech-1']);
  assert.equal(timeline.durationMs, 900);
});

test('keeps source actions immutable', () => {
  const actions: Action[] = [
    { id: 'spot-1', type: 'spotlight', elementId: 'immutable' },
    { id: 'speech-1', type: 'speech', text: 'do not mutate' },
  ];
  const before = structuredClone(actions);

  compileLessonTimeline({
    lessonId: 'lesson-immutable',
    scenes: [scene('scene-immutable', 1, actions)],
    actionDurationsMs: { 'speech-1': 1000 },
  });

  assert.deepEqual(actions, before);
});
