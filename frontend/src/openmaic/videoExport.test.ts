import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { LessonTimeline } from './timeline.ts';
import {
  mergeMeasuredSceneTimelines,
  timelineToSrt,
  validateLessonTimeline,
} from './videoExport.ts';

function timeline(
  sceneId: string,
  startMs: number,
  speechStartMs: number,
  speechDurationMs: number,
  text: string,
): LessonTimeline {
  return {
    version: 1,
    lessonId: 'lesson-video',
    durationMs: startMs + speechStartMs + speechDurationMs,
    viewport: { width: 1920, height: 1080, ratio: 0.5625 },
    scenes: [
      {
        sceneId,
        sceneIndex: 0,
        startMs,
        durationMs: speechStartMs + speechDurationMs,
        slideRef: `${sceneId}-slide`,
        clips: [
          {
            id: `${sceneId}-speech:clip`,
            actionId: `${sceneId}-speech`,
            type: 'speech',
            track: 'narration',
            startMs: speechStartMs,
            durationMs: speechDurationMs,
            durationSource: 'measured',
            payload: { text },
          },
        ],
      },
    ],
    render: {
      fps: 30,
      resolution: { width: 1920, height: 1080 },
      codec: 'h264',
      container: 'mp4',
      audioMix: {
        narrationGain: 1,
        duckOnClipAudio: false,
        clipAudio: 'mute',
      },
      captions: 'sidecar-srt',
    },
  };
}

test('writes ordered multiline narration as SRT with millisecond precision', () => {
  const source: LessonTimeline = {
    ...timeline('scene-2', 2500, 250, 1250, '第二段\n继续'),
    scenes: [
      timeline('scene-2', 2500, 250, 1250, '第二段\n继续').scenes[0],
      timeline('scene-1', 0, 0, 2345, '第一段').scenes[0],
    ],
    durationMs: 4000,
  };

  assert.equal(
    timelineToSrt(source),
    [
      '1',
      '00:00:00,000 --> 00:00:02,345',
      '第一段',
      '',
      '2',
      '00:00:02,750 --> 00:00:04,000',
      '第二段',
      '继续',
      '',
    ].join('\n'),
  );
});

test('merges measured single-scene timelines at cumulative offsets immutably', () => {
  const first = timeline('scene-1', 0, 0, 2000, '一');
  const second = timeline('scene-2', 0, 300, 1200, '二');
  const before = structuredClone([first, second]);

  const merged = mergeMeasuredSceneTimelines('lesson-merged', [first, second]);

  assert.equal(merged.lessonId, 'lesson-merged');
  assert.equal(merged.durationMs, 3500);
  assert.deepEqual(
    merged.scenes.map((scene) => [
      scene.sceneId,
      scene.sceneIndex,
      scene.startMs,
      scene.durationMs,
    ]),
    [
      ['scene-1', 0, 0, 2000],
      ['scene-2', 1, 2000, 1500],
    ],
  );
  assert.deepEqual([first, second], before);
});

test('rejects overlapping scenes, overlapping narration, and clips past scene end', () => {
  const overlappingScenes = timeline('scene-1', 0, 0, 2000, '一');
  overlappingScenes.scenes.push({
    ...structuredClone(overlappingScenes.scenes[0]),
    sceneId: 'scene-2',
    startMs: 1500,
  });
  assert.throws(
    () => validateLessonTimeline(overlappingScenes),
    /scene-2 overlaps/,
  );

  const overlappingNarration = timeline('scene-1', 0, 0, 2000, '一');
  overlappingNarration.scenes[0].clips.push({
    ...structuredClone(overlappingNarration.scenes[0].clips[0]),
    id: 'speech-2:clip',
    actionId: 'speech-2',
    startMs: 1000,
    durationMs: 500,
  });
  assert.throws(
    () => validateLessonTimeline(overlappingNarration),
    /narration clips overlap/,
  );

  const pastEnd = timeline('scene-1', 0, 0, 2000, '一');
  pastEnd.scenes[0].durationMs = 1000;
  assert.throws(
    () => validateLessonTimeline(pastEnd),
    /ends after its scene/,
  );
});
