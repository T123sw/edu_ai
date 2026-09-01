import assert from 'node:assert/strict';
import { test } from 'node:test';
import { VideoRegistry } from './videoRegistry.ts';

type VideoEventName = 'ended' | 'error';

class FakeVideoElement {
  readonly dataset: Record<string, string> = {};
  muted = false;
  currentTime = 12;
  playCalls = 0;
  pauseCalls = 0;
  playError: Error | null = null;
  private readonly listeners = new Map<
    VideoEventName,
    Set<() => void>
  >();

  play(): Promise<void> {
    this.playCalls++;
    return this.playError === null
      ? Promise.resolve()
      : Promise.reject(this.playError);
  }

  pause(): void {
    this.pauseCalls++;
  }

  addEventListener(name: VideoEventName, listener: () => void): void {
    const listeners = this.listeners.get(name) ?? new Set();
    listeners.add(listener);
    this.listeners.set(name, listeners);
  }

  removeEventListener(name: VideoEventName, listener: () => void): void {
    this.listeners.get(name)?.delete(listener);
  }

  emit(name: VideoEventName): void {
    for (const listener of this.listeners.get(name) ?? []) listener();
  }
}

test('registers and unregisters a video by stable element id', () => {
  const registry = new VideoRegistry();
  const video = new FakeVideoElement();

  const unregister = registry.register(
    'video-1',
    video as unknown as HTMLVideoElement,
  );

  assert.equal(registry.isRegistered('video-1'), true);
  assert.equal(video.dataset.videoState, 'registered');

  unregister();
  assert.equal(registry.isRegistered('video-1'), false);
  assert.equal(video.dataset.videoState, 'unregistered');
});

test('degrades a missing video element without blocking playback', async () => {
  const registry = new VideoRegistry();

  assert.equal(await registry.play('missing'), 'missing');
});

test('waits for ended and records the controlled playback state', async () => {
  const registry = new VideoRegistry();
  const video = new FakeVideoElement();
  registry.register('video-1', video as unknown as HTMLVideoElement);

  let settled = false;
  const playback = registry.play('video-1').then((result) => {
    settled = true;
    return result;
  });
  await Promise.resolve();

  assert.equal(settled, false);
  assert.equal(video.playCalls, 1);
  assert.equal(video.currentTime, 0);
  assert.equal(video.muted, true);
  assert.equal(video.dataset.videoState, 'playing');

  video.emit('ended');
  assert.equal(await playback, 'ended');
  assert.equal(video.dataset.videoState, 'completed');
});

test('completes with failed when the video emits an error', async () => {
  const registry = new VideoRegistry();
  const video = new FakeVideoElement();
  registry.register('video-1', video as unknown as HTMLVideoElement);

  const playback = registry.play('video-1');
  video.emit('error');

  assert.equal(await playback, 'failed');
  assert.equal(video.dataset.videoState, 'failed');
});

test('dispose cancels playback and unregisters every video', async () => {
  const registry = new VideoRegistry();
  const video = new FakeVideoElement();
  registry.register('video-1', video as unknown as HTMLVideoElement);
  const playback = registry.play('video-1');

  registry.dispose();

  assert.equal(await playback, 'failed');
  assert.equal(video.pauseCalls, 1);
  assert.equal(video.dataset.videoState, 'unregistered');
  assert.equal(registry.isRegistered('video-1'), false);
});
