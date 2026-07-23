/**
 * PlaybackEngine — edu_ai port of OpenMAIC's `lib/playback/engine.ts` (MIT),
 * trimmed to the sequential actionIndex/sceneIndex state machine Phase 3
 * needs. Discussion/pause-resume/snapshot-restore are upstream features tied
 * to interactive live-discussion mode (out of scope this phase — Phase 2 MVP
 * never generates `discussion` actions) and are left out rather than ported
 * unused.
 */

import type { Action } from '@openmaic/dsl';
import { ActionEngine, type ActionEffectsState } from './actionEngine';
import type { ClockSource } from './clock';

export type PlaybackMode = 'idle' | 'playing';

export interface PlayableScene {
  id: string;
  actions?: Action[];
}

export interface PlaybackCallbacks {
  onModeChange?: (mode: PlaybackMode) => void;
  onEffectsChange?: (effects: ActionEffectsState) => void;
  onSceneChange?: (sceneId: string) => void;
  onActionStart?: (action: Action) => void;
  onComplete?: () => void;
}

export class PlaybackEngine {
  private readonly scenes: PlayableScene[];
  private readonly clock: ClockSource;
  private readonly callbacks: PlaybackCallbacks;
  private readonly actionEngine: ActionEngine;
  private sceneIndex = 0;
  private actionIndex = 0;
  private mode: PlaybackMode = 'idle';
  /** Bumped by stop()/dispose() so an in-flight await from a stale run gives up. */
  private runToken = 0;

  constructor(scenes: PlayableScene[], clock: ClockSource, callbacks: PlaybackCallbacks = {}) {
    this.scenes = scenes;
    this.clock = clock;
    this.callbacks = callbacks;
    this.actionEngine = new ActionEngine({ onEffectsChange: callbacks.onEffectsChange });
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

  private getCurrentAction(): { action: Action; sceneId: string } | null {
    while (this.sceneIndex < this.scenes.length) {
      const scene = this.scenes[this.sceneIndex];
      const actions = scene.actions ?? [];
      if (this.actionIndex < actions.length) {
        return { action: actions[this.actionIndex], sceneId: scene.id };
      }
      this.sceneIndex++;
      this.actionIndex = 0;
    }
    return null;
  }

  private async processNext(): Promise<void> {
    const token = this.runToken;
    if (this.mode !== 'playing') return;

    if (this.actionIndex === 0 && this.sceneIndex < this.scenes.length) {
      this.actionEngine.clearEffects();
      this.callbacks.onSceneChange?.(this.scenes[this.sceneIndex].id);
    }

    const current = this.getCurrentAction();
    if (!current) {
      this.actionEngine.clearEffects();
      this.setMode('idle');
      this.callbacks.onComplete?.();
      return;
    }

    const { action } = current;
    void this.clock.currentTimeMs(); // observability hook only — see clock.ts docstring
    this.callbacks.onActionStart?.(action);
    this.actionIndex++;

    await this.actionEngine.execute(action);
    if (token !== this.runToken) return; // stop()/dispose() fired while awaiting
    if (this.mode === 'playing') {
      void this.processNext();
    }
  }
}
