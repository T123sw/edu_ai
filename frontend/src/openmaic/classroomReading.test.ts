import test from 'node:test';
import assert from 'node:assert/strict';
import { LecturePositionTracker, type LecturePosition } from './classroomReading';
import { ActionEngine, type ActionMediaAdapter } from './actionEngine';

test('sentence positions distinguish repeats, freeze at pause, and reset on replay', () => {
  const updates: LecturePosition[] = [];
  const tracker = new LecturePositionTracker('slide-1', p => updates.push(p));
  const speech = { id: 'speech-1', type: 'speech' as const, text: '再试一次。再试一次。' };
  tracker.start({ id: 'focus', type: 'spotlight', elementId: 'formula' });
  tracker.effects({ spotlight: { elementId: 'formula' } });
  tracker.start(speech);
  tracker.sentence(speech.id, 1, 'sentence');
  const frozen = structuredClone(updates.at(-1));
  tracker.freeze();
  tracker.effects({});
  tracker.end(speech);
  tracker.sentence(speech.id, 0, 'sentence');
  assert.deepEqual(updates.at(-1), frozen);
  assert.equal(frozen?.sentence_index, 1);
  assert.deepEqual(frozen?.highlighted_element_ids, ['formula']);
  tracker.restart();
  tracker.start(speech);
  tracker.sentence(speech.id, 0, 'sentence');
  assert.equal(updates.at(-1)?.sentence_index, 0);
  assert.deepEqual(updates.at(-1)?.highlighted_element_ids, []);
  assert.equal(frozen?.sentence_index, 1, 'published snapshots are immutable');
});

test('audio position is estimated, browser sentence playback carries exact sentence index', async () => {
  const positions: unknown[] = [];
  let audioFails = false;
  const media: ActionMediaAdapter = {
    async playAudio(_url, _duration, progress) { progress?.(0.75); return audioFails ? 'failed' : 'ended'; },
    async speak() { return 'ended'; }, async wait() {}, cancel() {},
  };
  const engine = new ActionEngine({ onNarrationPosition: (...args) => positions.push(args) }, { media });
  const speech = { id: 'speech', type: 'speech' as const, text: '相同。相同。', audioUrl: '/audio' };
  await engine.execute(speech);
  assert.deepEqual(positions, [['speech', 0, 'estimated'], ['speech', 1, 'estimated'], ['speech', 1, 'estimated']]);
  positions.length = 0;
  audioFails = true;
  await engine.execute(speech);
  assert.deepEqual(positions.slice(-2), [['speech', 0, 'sentence'], ['speech', 1, 'sentence']]);
  engine.dispose();
});
