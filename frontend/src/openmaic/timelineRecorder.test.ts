import assert from 'node:assert/strict';
import { test } from 'node:test';
import { compileLessonTimeline } from './timeline.ts';
import { TimelineRecorder } from './timelineRecorder.ts';

function template() {
  return compileLessonTimeline({
    lessonId: 'lesson-recorded',
    scenes: [
      {
        id: 'scene-1',
        order: 1,
        slideRef: 'slide-1',
        actions: [
          { id: 'spot-1', type: 'spotlight', elementId: 'title' },
          { id: 'speech-1', type: 'speech', text: '讲解' },
        ],
      },
      {
        id: 'scene-2',
        order: 2,
        slideRef: 'slide-2',
        actions: [{ id: 'speech-2', type: 'speech', text: '第二页' }],
      },
    ],
    actionDurationsMs: {
      'speech-1': 2000,
      'speech-2': 1500,
    },
  });
}

test('records measured action start and end relative to each scene', () => {
  const recorder = new TimelineRecorder(template());

  recorder.onActionStart('speech-1', 'scene-1', 100);
  recorder.onActionEnd('speech-1', 'scene-1', 2600);
  recorder.onActionStart('speech-2', 'scene-2', 3000);
  recorder.onActionEnd('speech-2', 'scene-2', 4200);

  const measured = recorder.snapshot();
  const firstSpeech = measured.scenes[0].clips.find((clip) => clip.actionId === 'speech-1');
  const secondSpeech = measured.scenes[1].clips.find((clip) => clip.actionId === 'speech-2');

  assert.deepEqual(
    [firstSpeech?.startMs, firstSpeech?.durationMs, firstSpeech?.durationSource],
    [0, 2500, 'measured'],
  );
  assert.deepEqual(
    [measured.scenes[1].startMs, secondSpeech?.startMs, secondSpeech?.durationMs],
    [2900, 0, 1200],
  );
  assert.equal(measured.durationMs, 4100);
});

test('copies measured narration timing to its concurrent focus clips', () => {
  const recorder = new TimelineRecorder(template());

  recorder.onActionStart('spot-1', 'scene-1', 50);
  recorder.onActionEnd('spot-1', 'scene-1', 50);
  recorder.onActionStart('speech-1', 'scene-1', 50);
  recorder.onActionEnd('speech-1', 'scene-1', 3050);

  const measured = recorder.snapshot();
  const focus = measured.scenes[0].clips.find((clip) => clip.actionId === 'spot-1');

  assert.deepEqual(
    [focus?.startMs, focus?.durationMs, focus?.durationSource, focus?.concurrentWith],
    [0, 3000, 'measured', 'speech-1:clip'],
  );
});

test('preserves its template and returns independent snapshots', () => {
  const source = template();
  const before = structuredClone(source);
  const recorder = new TimelineRecorder(source);

  recorder.onActionStart('speech-1', 'scene-1', 0);
  recorder.onActionEnd('speech-1', 'scene-1', 4000);
  const first = recorder.snapshot();
  first.scenes[0].clips[0].durationMs = 99999;

  assert.deepEqual(source, before);
  assert.notEqual(recorder.snapshot().scenes[0].clips[0].durationMs, 99999);
});
