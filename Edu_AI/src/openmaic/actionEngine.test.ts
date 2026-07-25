import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { SpeechAction } from '@openmaic/dsl';
import {
  ActionEngine,
  type ActionMediaAdapter,
  type ActionMediaResult,
} from './actionEngine.ts';

class FakeMediaAdapter implements ActionMediaAdapter {
  readonly calls: string[] = [];
  audioResult: ActionMediaResult = 'ended';
  speechResult: ActionMediaResult = 'ended';
  waitedMs: number[] = [];
  cancelled = false;
  private pendingSpeechResolve: ((result: ActionMediaResult) => void) | null = null;
  deferSpeech = false;

  async playAudio(): Promise<ActionMediaResult> {
    this.calls.push('audio');
    return this.audioResult;
  }

  speak(): Promise<ActionMediaResult> {
    this.calls.push('speech');
    if (!this.deferSpeech) return Promise.resolve(this.speechResult);
    return new Promise((resolve) => {
      this.pendingSpeechResolve = resolve;
    });
  }

  async wait(durationMs: number): Promise<void> {
    this.calls.push('wait');
    this.waitedMs.push(durationMs);
  }

  finishSpeech(result: ActionMediaResult = 'ended'): void {
    this.pendingSpeechResolve?.(result);
  }

  cancel(): void {
    this.cancelled = true;
    this.pendingSpeechResolve?.('failed');
  }
}

const speech: SpeechAction = {
  id: 'speech-1',
  type: 'speech',
  text: '这是中文讲解',
  audioUrl: '/audio/lesson.wav',
};

test('falls back to browser TTS when audio loading or playback fails', async () => {
  const media = new FakeMediaAdapter();
  media.audioResult = 'failed';
  const engine = new ActionEngine({}, { media });

  await engine.execute(speech);

  assert.deepEqual(media.calls, ['audio', 'speech']);
});

test('falls back to deterministic reading dwell when browser TTS also fails', async () => {
  const media = new FakeMediaAdapter();
  media.audioResult = 'failed';
  media.speechResult = 'failed';
  const engine = new ActionEngine({}, { media });

  await engine.execute(speech);

  assert.deepEqual(media.calls, ['audio', 'speech', 'wait']);
  assert.deepEqual(media.waitedMs, [2000]);
});

test('keeps paired focus active until narration ends and then clears it', async () => {
  const media = new FakeMediaAdapter();
  media.deferSpeech = true;
  const changes: Array<{ spotlight?: { elementId: string } }> = [];
  const engine = new ActionEngine(
    { onEffectsChange: (effects) => changes.push(structuredClone(effects)) },
    { media, effectAutoClearMs: 10 },
  );

  await engine.execute({ id: 'spot-1', type: 'spotlight', elementId: 'title' });
  const narration = engine.execute(
    { ...speech, audioUrl: undefined },
    { hasConcurrentFocus: true },
  );
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.equal(changes.at(-1)?.spotlight?.elementId, 'title');

  media.finishSpeech();
  await narration;
  assert.deepEqual(changes.at(-1), {});
});

test('clears orphan focus after the fixed timeout', async () => {
  const changes: Array<{ spotlight?: { elementId: string } }> = [];
  const engine = new ActionEngine(
    { onEffectsChange: (effects) => changes.push(structuredClone(effects)) },
    { effectAutoClearMs: 5 },
  );

  await engine.execute({ id: 'spot-only', type: 'spotlight', elementId: 'orphan' });
  await new Promise((resolve) => setTimeout(resolve, 15));

  assert.deepEqual(changes.at(-1), {});
});

test('dispose cancels active narration and releases paired focus', async () => {
  const media = new FakeMediaAdapter();
  media.deferSpeech = true;
  const changes: Array<{ spotlight?: { elementId: string } }> = [];
  const engine = new ActionEngine(
    { onEffectsChange: (effects) => changes.push(structuredClone(effects)) },
    { media },
  );

  await engine.execute({ id: 'spot-1', type: 'spotlight', elementId: 'title' });
  const narration = engine.execute(
    { ...speech, audioUrl: undefined },
    { hasConcurrentFocus: true },
  );
  engine.dispose();
  await narration;

  assert.equal(media.cancelled, true);
  assert.deepEqual(changes.at(-1), {});
});
