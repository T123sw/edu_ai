import assert from 'node:assert/strict';
import test from 'node:test';

import { ResourceLearningTracker } from './resourceLearningTracker';
import type { ResourceLearningEventPayload } from '../stitch/api/types';


function fakeClock() {
  let value = 0;
  return {
    now: () => value,
    advance: (milliseconds: number) => { value += milliseconds; },
  };
}

function memoryStorage() {
  const data = new Map<string, string>();
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => { data.set(key, value); },
    removeItem: (key: string) => { data.delete(key); },
  };
}

test('flushes only contiguous explanation playback and pauses during QA', async () => {
  const sent: ResourceLearningEventPayload[][] = [];
  const clock = fakeClock();
  const tracker = new ResourceLearningTracker({
    heartbeatMs: 10_000,
    send: async (events) => { sent.push(events); },
    now: clock.now,
  });
  tracker.enterExplanation('scene-1', 60_000);
  tracker.play();
  clock.advance(12_000);
  await tracker.flush();
  tracker.interrupt();
  clock.advance(30_000);
  await tracker.flush();

  assert.deepEqual(
    sent.flat().filter((event) => event.event_type === 'timeline_heartbeat')
      .map(({ timeline_from_ms, timeline_to_ms }) => [timeline_from_ms, timeline_to_ms]),
    [[0, 12_000]],
  );
});

test('scene switch captures the old interval and resets the new scene cursor', async () => {
  const sent: ResourceLearningEventPayload[][] = [];
  const clock = fakeClock();
  const tracker = new ResourceLearningTracker({ send: async (events) => { sent.push(events); }, now: clock.now });
  tracker.enterExplanation('scene-1', 60_000);
  tracker.play();
  clock.advance(5_000);
  tracker.enterExplanation('scene-2', 30_000);
  tracker.play();
  clock.advance(3_000);
  await tracker.flush();

  assert.deepEqual(
    sent.flat().filter((event) => event.event_type === 'timeline_heartbeat')
      .map((event) => [event.scene_id, event.timeline_from_ms, event.timeline_to_ms]),
    [['scene-1', 0, 5_000], ['scene-2', 0, 3_000]],
  );
});

test('demo scenes emit behavior events and never explanation heartbeats', async () => {
  const sent: ResourceLearningEventPayload[][] = [];
  const clock = fakeClock();
  const tracker = new ResourceLearningTracker({ send: async (events) => { sent.push(events); }, now: clock.now });
  tracker.enterDemo('demo-1');
  tracker.play();
  clock.advance(40_000);
  tracker.demoInteracted('widget-1');
  tracker.completeScene();
  await tracker.flush();

  assert.deepEqual(
    sent.flat().map((event) => event.event_type),
    ['demo_entered', 'demo_interacted', 'demo_completed'],
  );
});

test('long playback is split into server-safe ranges and repeated flush does not duplicate', async () => {
  const sent: ResourceLearningEventPayload[][] = [];
  const clock = fakeClock();
  const tracker = new ResourceLearningTracker({
    maxRangeMs: 15_000,
    send: async (events) => { sent.push(events); },
    now: clock.now,
  });
  tracker.enterExplanation('scene-1', 60_000);
  tracker.play();
  clock.advance(32_000);
  await tracker.flush();
  await tracker.flush();

  const heartbeats = sent.flat().filter((event) => event.event_type === 'timeline_heartbeat');
  assert.deepEqual(
    heartbeats.map(({ timeline_from_ms, timeline_to_ms }) => [timeline_from_ms, timeline_to_ms]),
    [[0, 15_000], [15_000, 30_000], [30_000, 32_000]],
  );
});

test('failed events persist in a versioned outbox and clear after retry', async () => {
  const storage = memoryStorage();
  const clock = fakeClock();
  let shouldFail = true;
  const sent: ResourceLearningEventPayload[][] = [];
  const tracker = new ResourceLearningTracker({
    outboxKey: 'course-1:classroom-1:3:session-1',
    storage,
    send: async (events) => {
      if (shouldFail) throw new Error('offline');
      sent.push(events);
    },
    now: clock.now,
  });
  tracker.enterExplanation('scene-1', 60_000);
  tracker.play();
  clock.advance(10_000);

  await assert.rejects(tracker.flush(), /offline/);
  assert.ok(storage.getItem('resource-learning-outbox:course-1:classroom-1:3:session-1'));
  shouldFail = false;
  await tracker.flush();

  assert.equal(storage.getItem('resource-learning-outbox:course-1:classroom-1:3:session-1'), null);
  assert.deepEqual(sent[0].map((event) => event.sequence_number), [1, 2]);
});

