import type { PlaybackCheckpoint } from './playbackEngine';

export type PagePlaybackStatus =
  | 'idle'
  | 'playing'
  | 'paused'
  | 'interrupted'
  | 'completed';

export interface PagePlaybackSnapshot {
  sceneIndex: number;
  status: PagePlaybackStatus;
  revision: number;
}

export interface PagePlaybackRuntime {
  play(): Promise<void>;
  pause(): void;
  dispose(): void;
}

export interface PlaybackRuntimeHandle {
  play(): void;
  suspend(): PlaybackCheckpoint;
  resume(checkpoint: PlaybackCheckpoint): void;
  cancel(): void;
  dispose(): void;
}

export type PagePlaybackCheckpoint = PlaybackCheckpoint & {
  sceneIndex: number;
  pageRevision: number;
};

export interface PagePlaybackController {
  enter(sceneIndex: number): Promise<void>;
  play(): Promise<void>;
  pause(): void;
  replay(): Promise<void>;
  bindRuntime(
    sceneIndex: number,
    revision: number,
    runtime: PlaybackRuntimeHandle,
  ): void;
  complete(sceneIndex: number, revision: number): boolean;
  interrupt(): PagePlaybackCheckpoint | null;
  resumeInterrupted(checkpoint: PagePlaybackCheckpoint): boolean;
  leave(): void;
  dispose(): void;
}

type RuntimeFactory = (sceneIndex: number) => PagePlaybackRuntime;
type SnapshotListener = (snapshot: PagePlaybackSnapshot) => void;

export function createRendererManagedPagePlaybackController(
  onSnapshot: SnapshotListener = () => undefined,
): ManagedPagePlaybackController {
  return new ManagedPagePlaybackController(
    () => ({
      async play() {},
      pause() {},
      dispose() {},
    }),
    onSnapshot,
  );
}

/**
 * Owns exactly one classroom page runtime.
 *
 * The public classroom player remounts its scene renderer whenever `revision`
 * changes. Page navigation and hard replay advance that revision. A Q&A
 * interruption keeps the revision stable so the renderer-owned playback
 * engine can preserve and resume its sentence checkpoint.
 */
export class ManagedPagePlaybackController implements PagePlaybackController {
  private current: PagePlaybackSnapshot = {
    sceneIndex: -1,
    status: 'idle',
    revision: 0,
  };
  private pageRuntime: PagePlaybackRuntime | null = null;
  private playbackRuntime: PlaybackRuntimeHandle | null = null;
  private interruptedCheckpoint: PagePlaybackCheckpoint | null = null;
  private disposed = false;

  constructor(
    private readonly createRuntime: RuntimeFactory,
    private readonly onSnapshot: SnapshotListener = () => undefined,
  ) {}

  snapshot(): PagePlaybackSnapshot {
    return { ...this.current };
  }

  async enter(sceneIndex: number): Promise<void> {
    if (this.disposed || !Number.isInteger(sceneIndex) || sceneIndex < 0) return;
    this.disposeRuntimes();
    this.pageRuntime = this.createRuntime(sceneIndex);
    this.updateWithRevision(sceneIndex, 'idle');
  }

  async play(): Promise<void> {
    if (this.disposed || !this.pageRuntime) return;
    await this.pageRuntime.play();
    this.playbackRuntime?.play();
    this.updateStatus('playing');
  }

  pause(): void {
    if (
      this.disposed ||
      !this.pageRuntime ||
      this.current.status !== 'playing'
    ) return;
    this.pageRuntime.pause();
    this.playbackRuntime?.cancel();
    this.interruptedCheckpoint = null;
    this.updateStatus('paused');
  }

  async replay(): Promise<void> {
    if (this.disposed || this.current.sceneIndex < 0) return;
    const sceneIndex = this.current.sceneIndex;
    this.disposeRuntimes();
    this.pageRuntime = this.createRuntime(sceneIndex);
    await this.pageRuntime.play();
    this.updateWithRevision(sceneIndex, 'playing');
  }

  bindRuntime(
    sceneIndex: number,
    revision: number,
    runtime: PlaybackRuntimeHandle,
  ): void {
    if (
      this.disposed ||
      sceneIndex !== this.current.sceneIndex ||
      revision !== this.current.revision
    ) {
      runtime.dispose();
      return;
    }
    this.playbackRuntime?.dispose();
    this.playbackRuntime = runtime;
  }

  interrupt(): PagePlaybackCheckpoint | null {
    if (
      this.disposed ||
      this.current.status !== 'playing' ||
      !this.playbackRuntime
    ) return null;

    try {
      const checkpoint: PagePlaybackCheckpoint = {
        ...this.playbackRuntime.suspend(),
        sceneIndex: this.current.sceneIndex,
        pageRevision: this.current.revision,
      };
      this.interruptedCheckpoint = checkpoint;
      this.updateStatus('interrupted');
      return { ...checkpoint };
    } catch {
      return null;
    }
  }

  resumeInterrupted(checkpoint: PagePlaybackCheckpoint): boolean {
    if (
      this.disposed ||
      this.current.status !== 'interrupted' ||
      !this.playbackRuntime ||
      !this.interruptedCheckpoint ||
      checkpoint.sceneIndex !== this.current.sceneIndex ||
      checkpoint.pageRevision !== this.current.revision ||
      checkpoint.sceneId !== this.interruptedCheckpoint.sceneId ||
      checkpoint.actionIndex !== this.interruptedCheckpoint.actionIndex ||
      checkpoint.actionId !== this.interruptedCheckpoint.actionId ||
      checkpoint.phase !== this.interruptedCheckpoint.phase
    ) return false;

    this.interruptedCheckpoint = null;
    try {
      this.playbackRuntime.resume(checkpoint);
      this.updateStatus('playing');
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Completion belongs to the exact rendered revision. Stale callbacks from a
   * page that has already been left are ignored. Navigation is orchestrated by
   * the classroom player only after this method confirms ownership.
   */
  complete(sceneIndex: number, revision: number): boolean {
    if (
      this.disposed ||
      this.current.sceneIndex !== sceneIndex ||
      this.current.revision !== revision ||
      this.current.status !== 'playing'
    ) {
      return false;
    }
    this.current = { ...this.current, status: 'completed' };
    this.onSnapshot(this.snapshot());
    return true;
  }

  leave(): void {
    if (this.disposed || this.current.sceneIndex < 0) return;
    this.disposeRuntimes();
    this.updateWithRevision(-1, 'idle');
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposeRuntimes();
    this.disposed = true;
  }

  private disposeRuntimes(): void {
    this.playbackRuntime?.dispose();
    this.playbackRuntime = null;
    this.pageRuntime?.dispose();
    this.pageRuntime = null;
    this.interruptedCheckpoint = null;
  }

  private updateWithRevision(
    sceneIndex: number,
    status: PagePlaybackStatus,
  ): void {
    this.current = {
      sceneIndex,
      status,
      revision: this.current.revision + 1,
    };
    this.onSnapshot(this.snapshot());
  }

  private updateStatus(status: PagePlaybackStatus): void {
    this.current = { ...this.current, status };
    this.onSnapshot(this.snapshot());
  }
}
