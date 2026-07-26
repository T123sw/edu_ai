import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { SpeechAction } from '@openmaic/dsl';
import {
  ActionEngine,
  selectPreferredBrowserVoice,
  type ActionMediaAdapter,
  type ActionMediaResult,
  type ActionVideoController,
  type ActionWidgetController,
  type VideoPlaybackResult,
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

class FakeVideoController implements ActionVideoController {
  readonly calls: string[] = [];
  cancelled = false;
  private finishPlayback: ((result: VideoPlaybackResult) => void) | null = null;

  play(elementId: string): Promise<VideoPlaybackResult> {
    this.calls.push(elementId);
    return new Promise((resolve) => {
      this.finishPlayback = resolve;
    });
  }

  finish(result: VideoPlaybackResult = 'ended'): void {
    this.finishPlayback?.(result);
  }

  cancel(): void {
    this.cancelled = true;
    this.finishPlayback?.('failed');
  }
}

class FakeWidgetController implements ActionWidgetController {
  readonly calls: Array<{
    type: string;
    payload: Record<string, unknown>;
  }> = [];

  postMessage(type: string, payload: Record<string, unknown>): void {
    this.calls.push({ type, payload });
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

test('waits for controlled embedded video completion', async () => {
  const video = new FakeVideoController();
  const engine = new ActionEngine({}, { video });
  let settled = false;

  const playback = engine
    .execute({ id: 'play-1', type: 'play_video', elementId: 'video-1' })
    .then(() => {
      settled = true;
    });
  await Promise.resolve();

  assert.deepEqual(video.calls, ['video-1']);
  assert.equal(settled, false);

  video.finish();
  await playback;
  assert.equal(settled, true);
});

test('dispose cancels active embedded video playback', async () => {
  const video = new FakeVideoController();
  const engine = new ActionEngine({}, { video });
  const playback = engine.execute({
    id: 'play-1',
    type: 'play_video',
    elementId: 'video-1',
  });

  engine.dispose();
  await playback;

  assert.equal(video.cancelled, true);
});

test('forwards widget actions through the active iframe controller', async () => {
  const widget = new FakeWidgetController();
  const media = new FakeMediaAdapter();
  const engine = new ActionEngine({}, { widget, media });

  await engine.execute({
    id: 'state',
    type: 'widget_setState',
    state: { pivot: 6 },
    content: '设置基准',
  });
  await engine.execute({
    id: 'highlight',
    type: 'widget_highlight',
    target: '#pivot',
    content: '观察基准',
  });
  await engine.execute({
    id: 'annotation',
    type: 'widget_annotation',
    target: '#left',
    content: '左指针',
  });
  await engine.execute({
    id: 'reveal',
    type: 'widget_reveal',
    target: '#answer',
    content: '显示结果',
  });

  assert.deepEqual(widget.calls, [
    {
      type: 'SET_WIDGET_STATE',
      payload: { state: { pivot: 6 }, content: '设置基准' },
    },
    {
      type: 'HIGHLIGHT_ELEMENT',
      payload: { target: '#pivot', content: '观察基准' },
    },
    {
      type: 'ANNOTATE_ELEMENT',
      payload: { target: '#left', content: '左指针' },
    },
    {
      type: 'REVEAL_ELEMENT',
      payload: { target: '#answer', content: '显示结果' },
    },
  ]);
  assert.deepEqual(media.waitedMs, [300, 300, 300, 300]);
});

test('selects an exact requested voice before the language fallback', () => {
  const voices = [
    { name: '中文普通话', lang: 'zh-CN' },
    { name: 'Requested Voice', lang: 'en-US' },
  ] as SpeechSynthesisVoice[];

  assert.equal(
    selectPreferredBrowserVoice(voices, 'Requested Voice', 'zh')?.name,
    'Requested Voice',
  );
});

test('falls back to an available Chinese voice when the requested voice is absent', () => {
  const voices = [
    { name: 'English', lang: 'en-US' },
    { name: '中文普通话', lang: 'zh-CN' },
  ] as SpeechSynthesisVoice[];

  assert.equal(
    selectPreferredBrowserVoice(voices, 'missing-voice', 'zh')?.name,
    '中文普通话',
  );
});
