/**
 * PlaybackEngine — edu_ai port of OpenMAIC's `lib/playback/engine.ts` (MIT),
 * trimmed to the sequential actionIndex/sceneIndex state machine Phase 3
 * needs. Discussion/pause-resume/snapshot-restore are upstream features tied
 * to interactive live-discussion mode (out of scope this phase — Phase 2 MVP
 * never generates `discussion` actions) and are left out rather than ported
 * unused.
 */

import type { Action } from '@openmaic/dsl';
import {
  ActionEngine,
  type ActionEffectsState,
  type ActionExecutionContext,
} from './actionEngine';
import type { ClockSource } from './clock';
import { compileLessonTimeline, type LessonTimeline } from './timeline';

export type PlaybackMode = 'idle' | 'playing';

export interface PlayableScene {
  id: string;
  order?: number;
  actions?: Action[];
}

export interface PlaybackCallbacks {
  onModeChange?: (mode: PlaybackMode) => void;
  onEffectsChange?: (effects: ActionEffectsState) => void;
  onSceneChange?: (sceneId: string) => void;
  onActionStart?: (action: Action, timeMs: number, sceneId: string) => void;
  onActionEnd?: (action: Action, timeMs: number, sceneId: string) => void;
  onComplete?: () => void;
}

export interface ActionExecutor {
  execute(action: Action, context?: ActionExecutionContext): Promise<void>;
  clearEffects(): void;
  dispose(): void;
}

export interface PlaybackEngineOptions {
  timeline?: LessonTimeline;
  actionExecutor?: ActionExecutor;
}

interface PlaybackActionEntry {
  action: Action;
  context: ActionExecutionContext;
}

interface CompiledPlayableScene {
  id: string;
  order: number;
  entries: PlaybackActionEntry[];
}

export class PlaybackEngine {
  private readonly scenes: CompiledPlayableScene[];
  private readonly clock: ClockSource;
  private readonly callbacks: PlaybackCallbacks;
  private readonly actionEngine: ActionExecutor;
  private sceneIndex = 0;
  private actionIndex = 0;
  private mode: PlaybackMode = 'idle';
  /** Bumped by stop()/dispose() so an in-flight await from a stale run gives up. */
  private runToken = 0;

  constructor(
    scenes: PlayableScene[],
    clock: ClockSource,
    callbacks: PlaybackCallbacks = {},
    options: PlaybackEngineOptions = {},
  ) {
    const timeline =
      options.timeline ??
      compileLessonTimeline({
        lessonId: 'playback',
        scenes: scenes.map((scene, index) => ({
          id: scene.id,
          order: scene.order ?? index,
          slideRef: scene.id,
          actions: scene.actions,
        })),
      });
    const sourceScenes = new Map(scenes.map((scene) => [scene.id, scene]));
    this.scenes = timeline.scenes.map((segment) => {
      const source = sourceScenes.get(segment.sceneId);
      const actionsById = new Map((source?.actions ?? []).map((action) => [action.id, action]));
      const pairedNarrationClipIds = new Set(
        segment.clips.flatMap((clip) =>
          clip.concurrentWith === undefined ? [] : [clip.concurrentWith],
        ),
      );
      return {
        id: segment.sceneId,
        order: segment.sceneIndex,
        entries: segment.clips.flatMap((clip) => {
          const action = actionsById.get(clip.actionId);
          return action === undefined
            ? []
            : [
                {
                  action,
                  context: {
                    hasConcurrentFocus: pairedNarrationClipIds.has(clip.id),
                  },
                },
              ];
        }),
      };
    });
    this.clock = clock;
    this.callbacks = callbacks;
    this.actionEngine =
      options.actionExecutor ?? new ActionEngine({ onEffectsChange: callbacks.onEffectsChange });
  }

  start(): void {
    if (this.mode !== 'idle') return;
    this.sceneIndex = 0;
    this.actionIndex = 0;
    this.setMode('playing');
    void this.processNext();
  }

  stop(): void {
    this.runToken++;
    this.setMode('idle');
    this.actionEngine.clearEffects();
    this.sceneIndex = 0;
    this.actionIndex = 0;
  }

  dispose(): void {
    this.runToken++;
    this.actionEngine.dispose();
  }

  private setMode(mode: PlaybackMode): void {
    if (this.mode === mode) return;
    this.mode = mode;
    this.callbacks.onModeChange?.(mode);
  }

  private getCurrentAction(): PlaybackActionEntry & { sceneId: string } | null {
    while (this.sceneIndex < this.scenes.length) {
      const scene = this.scenes[this.sceneIndex];
      if (this.actionIndex < scene.entries.length) {
        return { ...scene.entries[this.actionIndex], sceneId: scene.id };
      }
      this.sceneIndex++;
      this.actionIndex = 0;
    }
    return null;
  }

  private async processNext(): Promise<void> {
    const token = this.runToken;
    if (this.mode !== 'playing') return;

    const current = this.getCurrentAction();
    if (!current) {
      this.actionEngine.clearEffects();
      this.setMode('idle');
      this.callbacks.onComplete?.();
      return;
    }

    const { action, context, sceneId } = current;
    if (this.actionIndex === 0) {
      this.actionEngine.clearEffects();
      this.callbacks.onSceneChange?.(sceneId);
    }
    const startedAtMs = this.clock.currentTimeMs();
    this.callbacks.onActionStart?.(action, startedAtMs, sceneId);
    this.actionIndex++;

    await this.actionEngine.execute(action, context);
    if (token !== this.runToken) return; // stop()/dispose() fired while awaiting
    const endedAtMs = this.clock.currentTimeMs();
    this.callbacks.onActionEnd?.(action, endedAtMs, sceneId);
    if (this.mode === 'playing') {
      void this.processNext();
    }
  }
}
