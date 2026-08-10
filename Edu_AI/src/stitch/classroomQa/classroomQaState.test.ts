import assert from 'node:assert/strict';
import test from 'node:test';
import {
  INITIAL_CLASSROOM_QA_STATE,
  reduceClassroomQa,
} from './classroomQaState.ts';

const turn = {
  turn_id: 'turn-1',
  client_turn_id: 'client-1',
  question: '为什么？',
  answer_text: '因为这是划分步骤。',
  transition_text: '继续回到课堂。',
  tts_status: 'ready' as const,
  audio_url: '/api/audio/turn-1.mp3',
  created_at: '2026-08-10T00:00:00Z',
};

function submittingState() {
  const drafting = reduceClassroomQa(INITIAL_CLASSROOM_QA_STATE, {
    type: 'open',
  });
  return reduceClassroomQa(drafting, {
    type: 'submit',
    question: '为什么？',
    clientTurnId: 'client-1',
  });
}

test('a second submit is rejected while a turn is active', () => {
  const submitting = submittingState();
  assert.throws(
    () =>
      reduceClassroomQa(submitting, {
        type: 'submit',
        question: '第二问',
        clientTurnId: 'client-2',
      }),
    /turn already active/,
  );
});

test('successful server audio follows submitting loading playing and resuming phases', () => {
  let state = submittingState();
  state = reduceClassroomQa(state, {
    type: 'turn_received',
    clientTurnId: 'client-1',
    turn,
  });
  assert.equal(state.phase, 'loading_audio');

  state = reduceClassroomQa(state, {
    type: 'answer_playing',
    clientTurnId: 'client-1',
  });
  assert.equal(state.phase, 'playing_answer');

  state = reduceClassroomQa(state, {
    type: 'answer_finished',
    clientTurnId: 'client-1',
  });
  assert.equal(state.phase, 'resuming');

  state = reduceClassroomQa(state, { type: 'resume_complete', keepOpen: true });
  assert.equal(state.phase, 'drafting');
  assert.equal(state.activeTurn, null);
  assert.deepEqual(state.turns, [turn]);
});

test('TTS failure moves directly to browser answer playback', () => {
  const degradedTurn = { ...turn, tts_status: 'failed' as const, audio_url: null };
  const state = reduceClassroomQa(submittingState(), {
    type: 'turn_received',
    clientTurnId: 'client-1',
    turn: degradedTurn,
  });
  assert.equal(state.phase, 'playing_answer');
});

test('stale async results are ignored and retry keeps the same client turn id', () => {
  const submitting = submittingState();
  const stale = reduceClassroomQa(submitting, {
    type: 'turn_received',
    clientTurnId: 'old-client',
    turn,
  });
  assert.equal(stale, submitting);

  const failed = reduceClassroomQa(submitting, {
    type: 'fail',
    clientTurnId: 'client-1',
    message: '失败',
  });
  const retrying = reduceClassroomQa(failed, { type: 'retry' });
  assert.equal(retrying.phase, 'submitting');
  assert.equal(retrying.activeTurn?.clientTurnId, 'client-1');
});

test('draft cancellation closes while reset clears state on navigation', () => {
  const drafting = reduceClassroomQa(INITIAL_CLASSROOM_QA_STATE, {
    type: 'open',
  });
  assert.equal(
    reduceClassroomQa(drafting, { type: 'cancel_draft' }).phase,
    'closed',
  );

  const reset = reduceClassroomQa(submittingState(), { type: 'reset' });
  assert.deepEqual(reset, INITIAL_CLASSROOM_QA_STATE);
});
