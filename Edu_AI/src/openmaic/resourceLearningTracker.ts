import type {
  ResourceLearningEventPayload,
  ResourceLearningEventType,
} from '../stitch/api/types';


type StorageLike = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export type ResourceLearningTrackerOptions = {
  send: (events: ResourceLearningEventPayload[]) => Promise<unknown>;
  now?: () => number;
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
    const events = [...this.readOutbox(), ...this.pending];
    this.pending = [];
    if (events.length === 0) return;
    this.sending = this.send(events)
      .then(() => { this.clearOutbox(); })
      .catch((error) => {
        this.writeOutbox(events);
        throw error;
      })
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
      occurred_at: new Date(this.now()).toISOString(),
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
      this.storage.setItem(this.storageKey, JSON.stringify(events));
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

