export type PagePlaybackStatus = 'idle' | 'playing' | 'paused' | 'completed';

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

export interface PagePlaybackController {
  enter(sceneIndex: number): Promise<void>;
  play(): Promise<void>;
  pause(): void;
  replay(): Promise<void>;
  leave(): void;
  dispose(): void;
}

type RuntimeFactory = (sceneIndex: number) => PagePlaybackRuntime;
type SnapshotListener = (snapshot: PagePlaybackSnapshot) => void;

/**
 * Owns exactly one classroom page runtime.
 *
 * The public classroom player remounts its scene renderer whenever `revision`
 * changes. That makes pause, replay and page navigation a hard cancellation
 * boundary: speech, video, focus effects and timers from the previous runtime
 * are disposed before a new page can start.
 */
export class ManagedPagePlaybackController implements PagePlaybackController {
  private current: PagePlaybackSnapshot = {
    sceneIndex: -1,
    status: 'idle',
    revision: 0,
  };
  private runtime: PagePlaybackRuntime | null = null;
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
    this.disposeRuntime();
    this.runtime = this.createRuntime(sceneIndex);
    this.update(sceneIndex, 'idle');
  }

  async play(): Promise<void> {
    if (this.disposed || !this.runtime) return;
    await this.runtime.play();
    this.update(this.current.sceneIndex, 'playing');
  }

  pause(): void {
    if (this.disposed || !this.runtime || this.current.status !== 'playing') return;
    this.runtime.pause();
    this.update(this.current.sceneIndex, 'paused');
  }

  async replay(): Promise<void> {
    if (this.disposed || this.current.sceneIndex < 0) return;
    const sceneIndex = this.current.sceneIndex;
    this.disposeRuntime();
    this.runtime = this.createRuntime(sceneIndex);
    await this.runtime.play();
    this.update(sceneIndex, 'playing');
  }

  /**
   * Completion belongs to the exact rendered revision. Stale callbacks from a
   * page that has already been left are ignored and completion never navigates.
   */
  complete(sceneIndex: number, revision: number): void {
    if (
      this.disposed ||
      this.current.sceneIndex !== sceneIndex ||
      this.current.revision !== revision ||
      this.current.status !== 'playing'
    ) {
      return;
    }
    this.current = { ...this.current, status: 'completed' };
    this.onSnapshot(this.snapshot());
  }

  leave(): void {
    if (this.disposed || this.current.sceneIndex < 0) return;
    this.disposeRuntime();
    this.update(-1, 'idle');
  }

  dispose(): void {
    if (this.disposed) return;
    this.disposeRuntime();
    this.disposed = true;
  }

  private disposeRuntime(): void {
    this.runtime?.dispose();
    this.runtime = null;
  }

  private update(sceneIndex: number, status: PagePlaybackStatus): void {
    this.current = {
      sceneIndex,
      status,
      revision: this.current.revision + 1,
    };
    this.onSnapshot(this.snapshot());
  }
}
