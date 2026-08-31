import type {
  ResourceLearningEventPayload,
  ResourceLearningEventType,
} from '../stitch/api/types';


type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export type ResourceLearningTrackerOptions = {
  send: (events: ResourceLearningEventPayload[]) => Promise<unknown>;
  now?: () => number;
  wallNow?: () => Date;
  heartbeatMs?: number;
  maxRangeMs?: number;
  outboxKey?: string;
  storage?: StorageLike;
};

type ActiveScene = {
  id: string;
  kind: 'explanation' | 'exercise' | 'demo';
  totalMs: number;
  cursorMs: number;
};

const OUTBOX_PREFIX = 'resource-learning-outbox:';
const MAX_BATCH_EVENTS = 100;
const MAX_OUTBOX_EVENTS = 500;
const MAX_OUTBOX_BYTES = 2 * 1024 * 1024;

function defaultStorage(): StorageLike | undefined {
  try {
    return typeof window === 'undefined' ? undefined : window.localStorage;
  } catch {
    return undefined;
  }
}

function eventId(sequence: number) {
  const random = globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
  return `rle-${sequence}-${random}`;
}

export class ResourceLearningTracker {
  private readonly send: ResourceLearningTrackerOptions['send'];
  private readonly now: () => number;
  private readonly wallNow: () => Date;
  readonly heartbeatMs: number;
  private readonly maxRangeMs: number;
  private readonly storage?: StorageLike;
  private readonly storageKey: string;
  private sequence = 0;
  private scene: ActiveScene | null = null;
  private playingSince: number | null = null;
  private pending: ResourceLearningEventPayload[] = [];
  private sending: Promise<void> | null = null;

  constructor(options: ResourceLearningTrackerOptions) {
    this.send = options.send;
    this.now = options.now ?? (() => performance.now());
    this.wallNow = options.wallNow ?? (() => new Date());
    this.heartbeatMs = Math.max(1_000, options.heartbeatMs ?? 10_000);
    this.maxRangeMs = Math.min(15_000, Math.max(1_000, options.maxRangeMs ?? 15_000));
    this.storage = options.storage ?? defaultStorage();
    this.storageKey = `${OUTBOX_PREFIX}${options.outboxKey ?? 'default'}`;
    this.sequence = this.readOutbox().reduce(
      (maximum, event) => Math.max(maximum, event.sequence_number),
      0,
    );
  }

  enterExplanation(sceneId: string, totalMs: number) {
    this.leaveCurrentScene();
    this.scene = { id: sceneId, kind: 'explanation', totalMs: Math.max(0, totalMs), cursorMs: 0 };
    this.enqueue('scene_entered', sceneId);
  }

  enterExercise(sceneId: string) {
    this.leaveCurrentScene();
    this.scene = { id: sceneId, kind: 'exercise', totalMs: 0, cursorMs: 0 };
    this.enqueue('scene_entered', sceneId);
  }

  enterDemo(sceneId: string) {
    this.leaveCurrentScene();
    this.scene = { id: sceneId, kind: 'demo', totalMs: 0, cursorMs: 0 };
    this.enqueue('demo_entered', sceneId);
  }

  play() {
    if (!this.scene || this.playingSince !== null) return;
    this.playingSince = this.now();
  }

  pause() {
    this.capturePlayback();
    if (this.scene) this.enqueue('playback_paused', this.scene.id);
  }

  interrupt() {
    this.pause();
  }

  demoInteracted(actionId?: string) {
    if (this.scene?.kind !== 'demo') return;
    this.enqueue('demo_interacted', this.scene.id, actionId ? { action_id: actionId } : {});
  }

  completeScene() {
    if (!this.scene) return;
    this.capturePlayback();
    this.enqueue(
      this.scene.kind === 'demo' ? 'demo_completed' : 'scene_completed',
      this.scene.id,
    );
  }

  async flush(): Promise<void> {
    this.capturePlayback(true);
    if (this.sending) return this.sending;
    const events = compactOutbox([...this.readOutbox(), ...this.pending]);
    this.pending = [];
    if (events.length === 0) return;
    this.sequence = events.reduce(
      (maximum, event) => Math.max(maximum, event.sequence_number),
      0,
    );
    this.sending = (async () => {
      let remaining = events;
      this.writeOutbox(remaining);
      try {
        while (remaining.length > 0) {
          const batch = remaining.slice(0, MAX_BATCH_EVENTS);
          await this.send(batch);
          remaining = remaining.slice(batch.length);
          if (remaining.length) this.writeOutbox(remaining);
          else this.clearOutbox();
        }
      } catch (error) {
        this.writeOutbox(remaining);
        throw error;
      }
    })()
      .finally(() => { this.sending = null; });
    return this.sending;
  }

  async dispose(): Promise<void> {
    this.capturePlayback();
    await this.flush();
    this.scene = null;
    this.playingSince = null;
  }

  private leaveCurrentScene() {
    this.capturePlayback();
    this.scene = null;
    this.playingSince = null;
  }

  private capturePlayback(keepPlaying = false) {
    if (!this.scene || this.playingSince === null) return;
    const capturedAt = this.now();
    const elapsed = Math.max(0, Math.round(capturedAt - this.playingSince));
    this.playingSince = keepPlaying ? capturedAt : null;
    if (this.scene.kind !== 'explanation' || elapsed <= 0) return;
    const start = this.scene.cursorMs;
    const end = Math.min(this.scene.totalMs, start + elapsed);
    this.scene.cursorMs = end;
    for (let rangeStart = start; rangeStart < end; rangeStart += this.maxRangeMs) {
      this.enqueue('timeline_heartbeat', this.scene.id, {
        timeline_from_ms: rangeStart,
        timeline_to_ms: Math.min(end, rangeStart + this.maxRangeMs),
      });
    }
  }

  private enqueue(
    eventType: ResourceLearningEventType,
    sceneId: string,
    extra: Partial<ResourceLearningEventPayload> = {},
  ) {
    this.sequence += 1;
    this.pending.push({
      event_id: eventId(this.sequence),
      sequence_number: this.sequence,
      event_type: eventType,
      scene_id: sceneId,
      occurred_at: this.wallNow().toISOString(),
      ...extra,
    });
  }

  private readOutbox(): ResourceLearningEventPayload[] {
    if (!this.storage) return [];
    try {
      const raw = this.storage.getItem(this.storageKey);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed as ResourceLearningEventPayload[] : [];
    } catch {
      return [];
    }
  }

  private writeOutbox(events: ResourceLearningEventPayload[]) {
    if (!this.storage) return;
    try {
      const compacted = compactOutbox(events);
      this.sequence = compacted.reduce(
        (maximum, event) => Math.max(maximum, event.sequence_number),
        0,
      );
      this.storage.setItem(this.storageKey, JSON.stringify(compacted));
    } catch {
      // The caller still receives the send failure; storage failure adds no new failure mode.
    }
  }

  private clearOutbox() {
    if (!this.storage) return;
    try {
      this.storage.removeItem(this.storageKey);
    } catch {
      // Successful network delivery is authoritative even if local cleanup is unavailable.
    }
  }
}

function compactOutbox(
  events: ResourceLearningEventPayload[],
): ResourceLearningEventPayload[] {
  if (
    events.length <= MAX_OUTBOX_EVENTS &&
    JSON.stringify(events).length <= MAX_OUTBOX_BYTES
  ) {
    return events;
  }
  const merged: ResourceLearningEventPayload[] = [];
  for (const event of events) {
    const previous = merged.at(-1);
    if (
      previous?.event_type === 'timeline_heartbeat' &&
      event.event_type === 'timeline_heartbeat' &&
      previous.scene_id === event.scene_id &&
      previous.timeline_to_ms === event.timeline_from_ms &&
      (event.timeline_to_ms ?? 0) - (previous.timeline_from_ms ?? 0) <= 20_000
    ) {
      previous.timeline_to_ms = event.timeline_to_ms;
    } else {
      merged.push({ ...event });
    }
  }
  const bounded = merged.length > MAX_OUTBOX_EVENTS
    ? merged.slice(merged.length - MAX_OUTBOX_EVENTS)
    : merged;
  return bounded.map((event, index) => ({ ...event, sequence_number: index + 1 }));
}
