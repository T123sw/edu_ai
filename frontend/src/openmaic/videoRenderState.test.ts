import assert from 'node:assert/strict';
import test from 'node:test';
import type { ClassroomScene } from '../stitch/api/types.ts';
import type { LessonTimeline } from './timeline.ts';
import {
  completeVideoRenderSession,
  failVideoRenderSession,
  selectVideoRenderScene,
} from './videoRenderState.ts';

function slideScene(id: string): ClassroomScene {
  return {
    id,
    type: 'slide',
    content: {
      type: 'slide',
      canvas: {
        id: `${id}-canvas`,
        viewportSize: 1920,
        viewportRatio: 0.5625,
        elements: [],
      },
    },
    actions: [],
  };
}

function measuredTimeline(sceneId: string, durationMs: number): LessonTimeline {
  return {
    version: 1,
    lessonId: sceneId,
    durationMs,
    viewport: { width: 1920, height: 1080, ratio: 0.5625 },
    scenes: [
      {
        sceneId,
        sceneIndex: 0,
        startMs: 0,
        durationMs,
        slideRef: `${sceneId}-canvas`,
        clips: [],
      },
    ],
  };
}

test('selectVideoRenderScene keeps source order while skipping unsupported scenes', () => {
  const scenes: ClassroomScene[] = [
    { id: 'quiz', type: 'interactive' },
    slideScene('slide-a'),
    { id: 'discussion', type: 'discussion', content: { type: 'discussion' } },
    slideScene('slide-b'),
  ];

  assert.deepEqual(selectVideoRenderScene(scenes, 0), {
    scene: scenes[1],
    sourceIndex: 1,
    renderIndex: 0,
    sceneCount: 2,
  });
  assert.deepEqual(selectVideoRenderScene(scenes, 1), {
    scene: scenes[3],
    sourceIndex: 3,
    renderIndex: 1,
    sceneCount: 2,
  });
});

test('selectVideoRenderScene rejects an unavailable render index', () => {
  assert.throws(
    () => selectVideoRenderScene([slideScene('only')], 2),
    /render scene index 2 is unavailable \(1 renderable scene\)/,
  );
});

test('completeVideoRenderSession merges measured scene timelines', () => {
  const result = completeVideoRenderSession('lesson-42', [
    measuredTimeline('slide-a', 900),
    measuredTimeline('slide-b', 600),
  ]);

  assert.equal(result.status, 'completed');
  assert.equal(result.sceneCount, 2);
  assert.equal(result.timeline.lessonId, 'lesson-42');
  assert.equal(result.timeline.durationMs, 1500);
  assert.deepEqual(
    result.timeline.scenes.map((scene) => [scene.sceneId, scene.sceneIndex, scene.startMs]),
    [
      ['slide-a', 0, 0],
      ['slide-b', 1, 900],
    ],
  );
});

test('failVideoRenderSession exposes a stable error message', () => {
  assert.deepEqual(failVideoRenderSession(new Error('audio failed')), {
    status: 'failed',
    error: 'audio failed',
  });
  assert.deepEqual(failVideoRenderSession('unknown failure'), {
    status: 'failed',
    error: 'unknown failure',
  });
});
