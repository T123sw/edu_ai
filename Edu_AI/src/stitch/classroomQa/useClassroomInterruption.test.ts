import assert from 'node:assert/strict';
import test from 'node:test';
import type { PagePlaybackCheckpoint } from '../../openmaic/pagePlaybackController.ts';
import type { ClassroomQaTurnSubmission } from '../api/types.ts';
import {
  ClassroomInterruptionCoordinator,
  type AnswerAudioHandle,
} from './useClassroomInterruption.ts';

const checkpoint: PagePlaybackCheckpoint = {
  sceneId: 'scene-1',
  actionIndex: 0,
  actionId: 'speech-1',
  phase: 'executing_action',
  sceneIndex: 0,
  pageRevision: 1,
};

const readySubmission: ClassroomQaTurnSubmission = {
  session_id: 'cqa-1',
  turn: {
    turn_id: 'turn-1',
    client_turn_id: 'client-1',
    question: '为什么？',
    answer_text: '因为这是划分步骤。',
    transition_text: '继续回到课堂。',
    tts_status: 'ready',
    audio_url: '/api/audio/turn-1.mp3',
    created_at: '2026-08-10T00:00:00Z',
  },
};

class FakePlayback {
  interruptCalls = 0;
  resumeCalls = 0;
  resumeResult = true;
  interruptResult: PagePlaybackCheckpoint | null = checkpoint;
  current = { sceneIndex: 0, revision: 1 };

  interrupt() {
    this.interruptCalls += 1;
    return this.interruptResult ? { ...this.interruptResult } : null;
  }

  resumeInterrupted(_checkpoint: PagePlaybackCheckpoint) {
    this.resumeCalls += 1;
    return this.resumeResult;
  }

  snapshot() {
    return {
      sceneIndex: this.current.sceneIndex,
      revision: this.current.revision,
      status: 'interrupted' as const,
    };
  }
}

class FakeAnswerAudio implements AnswerAudioHandle {
  playCalls = 0;
  stopCalls = 0;
  disposeCalls = 0;
  private resolve: ((result: 'ended' | 'failed') => void) | null = null;

  play(): Promise<'ended' | 'failed'> {
    this.playCalls += 1;
    return new Promise((resolve) => {
      this.resolve = resolve;
    });
  }

  finish(result: 'ended' | 'failed' = 'ended') {
    this.resolve?.(result);
  }

  stop() {
    this.stopCalls += 1;
    this.finish();
  }

  dispose() {
    this.disposeCalls += 1;
  }
}

function createHarness(
  overrides: {
    submission?: ClassroomQaTurnSubmission;
    speakResult?: 'ended' | 'failed';
  } = {},
) {
  const playback = new FakePlayback();
  const answerAudio = new FakeAnswerAudio();
  const revoked: string[] = [];
  let resolveSubmission!: (value: ClassroomQaTurnSubmission) => void;
  let deferred = false;
  const controller = new ClassroomInterruptionCoordinator({
    courseId: 'course-1',
    classroomId: 'classroom-1',
    playback,
    loadSession: async () => ({
      session_id: 'cqa-1',
      course_id: 'course-1',
      classroom_id: 'classroom-1',
      owner_user_id: 'student-a',
      status: 'ready',
      turns: [],
    }),
    submitTurn: async () =>
      deferred
        ? new Promise((resolve) => {
            resolveSubmission = resolve;
          })
        : (overrides.submission ?? readySubmission),
    loadAudio: async () => 'blob:answer',
    createAudio: () => answerAudio,
    speakBrowser: async () => overrides.speakResult ?? 'ended',
    cancelBrowserSpeech: () => undefined,
    createClientTurnId: () => 'client-1',
    revokeObjectUrl: (url) => revoked.push(url),
  });
  return {
    controller,
    playback,
    answerAudio,
    revoked,
    deferSubmission() {
      deferred = true;
    },
    resolveSubmission(value = readySubmission) {
      resolveSubmission(value);
    },
  };
}

async function waitFor(predicate: () => boolean) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  throw new Error('condition was not reached');
}

test('opening and typing do not pause; submit pauses and successful audio resumes once', async () => {
  const harness = createHarness();
  harness.controller.openQuestion();
  assert.equal(harness.playback.interruptCalls, 0);

  const submitting = harness.controller.submitQuestion('为什么要选基准值？');
  assert.equal(harness.playback.interruptCalls, 1);
  assert.equal(harness.controller.state.activeTurn?.question, '为什么要选基准值？');
  await waitFor(() => harness.answerAudio.playCalls === 1);
  harness.answerAudio.finish();
  harness.answerAudio.finish();
  await submitting;

  assert.equal(harness.playback.resumeCalls, 1);
  assert.deepEqual(harness.revoked, ['blob:answer']);
});

test('a second question from the open panel creates a fresh interruption', async () => {
  const harness = createHarness();
  harness.controller.openQuestion();
  const first = harness.controller.submitQuestion('第一个问题');
  await waitFor(() => harness.answerAudio.playCalls === 1);
  harness.answerAudio.finish();
  await first;

  const second = harness.controller.submitQuestion('第二个问题');
  await waitFor(() => harness.answerAudio.playCalls === 2);
  harness.answerAudio.finish();
  await second;

  assert.equal(harness.playback.interruptCalls, 2);
  assert.equal(harness.playback.resumeCalls, 2);
});

test('cancel before submit closes the draft without touching playback', () => {
  const harness = createHarness();
  harness.controller.openQuestion();
  harness.controller.cancelDraft();

  assert.equal(harness.playback.interruptCalls, 0);
  assert.equal(harness.playback.resumeCalls, 0);
  assert.equal(harness.controller.state.phase, 'closed');
});

test('invalid questions and checkpoint failures do not create optimistic turns', async () => {
  const harness = createHarness();
  harness.controller.openQuestion();

  await harness.controller.submitQuestion('   ');
  assert.equal(harness.playback.interruptCalls, 0);
  assert.equal(harness.controller.state.activeTurn, null);

  harness.playback.interruptResult = null;
  await harness.controller.submitQuestion('有效问题');
  assert.equal(harness.playback.interruptCalls, 1);
  assert.equal(harness.controller.state.activeTurn, null);
  assert.equal(harness.controller.state.phase, 'drafting');
});

test('the optimistic question is committed before the deferred request resolves', async () => {
  const harness = createHarness();
  harness.deferSubmission();
  harness.controller.openQuestion();

  const submitting = harness.controller.submitQuestion('立即显示的问题');
  assert.equal(harness.controller.state.phase, 'submitting');
  assert.equal(harness.controller.state.activeTurn?.question, '立即显示的问题');

  harness.resolveSubmission();
  await waitFor(() => harness.answerAudio.playCalls === 1);
  harness.answerAudio.finish();
  await submitting;
});

test('server TTS failure uses browser speech before resuming', async () => {
  const degraded = {
    ...readySubmission,
    turn: {
      ...readySubmission.turn,
      tts_status: 'failed' as const,
      audio_url: null,
    },
  };
  const harness = createHarness({ submission: degraded });
  harness.controller.openQuestion();
  await harness.controller.submitQuestion('为什么？');

  assert.equal(harness.answerAudio.playCalls, 0);
  assert.equal(harness.playback.resumeCalls, 1);
});

test('both speech paths failing waits for an explicit resume', async () => {
  const degraded = {
    ...readySubmission,
    turn: {
      ...readySubmission.turn,
      tts_status: 'failed' as const,
      audio_url: null,
    },
  };
  const harness = createHarness({ submission: degraded, speakResult: 'failed' });
  harness.controller.openQuestion();
  await harness.controller.submitQuestion('为什么？');

  assert.equal(harness.playback.resumeCalls, 0);
  assert.equal(harness.controller.state.phase, 'error');

  harness.controller.stopAnswerAndResume();
  assert.equal(harness.playback.resumeCalls, 1);
});

test('stop answer disposes audio and resumes once', async () => {
  const harness = createHarness();
  harness.controller.openQuestion();
  const submitting = harness.controller.submitQuestion('为什么？');
  await waitFor(() => harness.answerAudio.playCalls === 1);

  harness.controller.stopAnswerAndResume();
  await submitting;

  assert.equal(harness.answerAudio.stopCalls, 1);
  assert.equal(harness.playback.resumeCalls, 1);
});

test('rejected stale checkpoint becomes an error without repeated resume', async () => {
  const harness = createHarness({
    submission: {
      ...readySubmission,
      turn: { ...readySubmission.turn, tts_status: 'failed', audio_url: null },
    },
  });
  harness.playback.resumeResult = false;
  harness.controller.openQuestion();
  await harness.controller.submitQuestion('为什么？');

  assert.equal(harness.playback.resumeCalls, 1);
  assert.equal(harness.controller.state.phase, 'error');
  harness.controller.stopAnswerAndResume();
  assert.equal(harness.playback.resumeCalls, 1);
});

test('navigation and dispose ignore late responses without audio or resume', async () => {
  for (const action of ['navigation', 'dispose'] as const) {
    const harness = createHarness();
    harness.deferSubmission();
    harness.controller.openQuestion();
    const submitting = harness.controller.submitQuestion('为什么？');
    await Promise.resolve();

    if (action === 'navigation') harness.controller.resetForNavigation();
    else harness.controller.dispose();
    harness.resolveSubmission();
    await submitting;

    assert.equal(harness.answerAudio.playCalls, 0);
    assert.equal(harness.playback.resumeCalls, 0);
  }
});
