export type PollDelayInput = {
  visible: boolean;
  hasRunning: boolean;
  hasQueued: boolean;
  failures: number;
};

const FAILURE_BACKOFF_MS = [2_000, 4_000, 8_000, 15_000, 30_000];

export function getJobPollDelay(input: PollDelayInput): number | null {
  if (input.failures > 0) {
    return FAILURE_BACKOFF_MS[
      Math.min(input.failures - 1, FAILURE_BACKOFF_MS.length - 1)
    ];
  }
  if (!input.hasRunning && !input.hasQueued) return null;
  if (!input.visible) return 8_000;
  return input.hasRunning ? 2_000 : 3_000;
}

export interface LeaseStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

type LeaseRecord = {
  owner: string;
  expiresAt: number;
};

export class JobLeaderLease {
  constructor(
    private readonly storage: LeaseStorage,
    private readonly tabId: string,
    private readonly key = "edu-ai-job-poll-leader",
    private readonly ttlMs = 12_000,
  ) {}

  claim(now = Date.now()): boolean {
    const current = this.read();
    if (
      current &&
      current.owner !== this.tabId &&
      current.expiresAt > now
    ) {
      return false;
    }
    const next: LeaseRecord = {
      owner: this.tabId,
      expiresAt: now + this.ttlMs,
    };
    this.storage.setItem(this.key, JSON.stringify(next));
    return this.read()?.owner === this.tabId;
  }

  release(): void {
    if (this.read()?.owner === this.tabId) {
      this.storage.removeItem(this.key);
    }
  }

  private read(): LeaseRecord | null {
    try {
      const parsed = JSON.parse(this.storage.getItem(this.key) || "null") as
        | LeaseRecord
        | null;
      return parsed &&
        typeof parsed.owner === "string" &&
        Number.isFinite(parsed.expiresAt)
        ? parsed
        : null;
    } catch {
      return null;
    }
  }
}
