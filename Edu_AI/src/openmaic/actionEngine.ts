/**
 * Executes the subset of OpenMAIC actions used by the lesson player.
 *
 * Spotlight and laser actions are fire-and-forget. Speech is synchronous and
 * follows a deterministic fallback chain:
 * generated audio -> browser speech synthesis -> reading-time dwell.
 */

import type { Action, SpeechAction } from '@openmaic/dsl';

const DEFAULT_EFFECT_AUTO_CLEAR_MS = 5000;

export interface SpotlightEffectState {
  elementId: string;
  dimOpacity?: number;
}

export interface LaserEffectState {
  elementId: string;
  color?: string;
}

export interface ActionEffectsState {
  spotlight?: SpotlightEffectState;
  laser?: LaserEffectState;
}

export interface ActionEngineCallbacks {
  onEffectsChange?: (effects: ActionEffectsState) => void;
}

export type ActionMediaResult = 'ended' | 'failed';

export interface ActionMediaAdapter {
  playAudio(
    url: string,
    onDurationKnown?: (durationMs: number) => void,
  ): Promise<ActionMediaResult>;
  speak(text: string, speed?: number, voice?: string): Promise<ActionMediaResult>;
  wait(durationMs: number): Promise<void>;
  cancel(): void;
}

export type VideoPlaybackResult = 'ended' | 'failed' | 'missing';

export interface ActionVideoController {
  play(elementId: string): Promise<VideoPlaybackResult>;
  cancel(): void;
}

export interface ActionExecutionContext {
  /**
   * The timeline compiler paired the current narration with a preceding
   * spotlight/laser clip. Paired focus remains active for the exact narration
   * lifetime instead of using the orphan safety timeout.
   */
  hasConcurrentFocus?: boolean;
}

export interface ActionEngineOptions {
  media?: ActionMediaAdapter;
  video?: ActionVideoController;
  effectAutoClearMs?: number;
}

export class ActionEngine {
  private effects: ActionEffectsState = {};
  private effectTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly callbacks: ActionEngineCallbacks;
  private readonly media: ActionMediaAdapter;
  private readonly video?: ActionVideoController;
  private readonly effectAutoClearMs: number;
  private disposed = false;

  constructor(
    callbacks: ActionEngineCallbacks = {},
    options: ActionEngineOptions = {},
  ) {
    this.callbacks = callbacks;
    this.media = options.media ?? new BrowserActionMediaAdapter();
    this.video = options.video;
    this.effectAutoClearMs =
      options.effectAutoClearMs ?? DEFAULT_EFFECT_AUTO_CLEAR_MS;
  }

  dispose(): void {
    this.disposed = true;
    this.media.cancel();
    this.video?.cancel();
    this.clearEffects();
  }

  clearEffects(): void {
    this.clearEffectTimer();
    this.effects = {};
    this.callbacks.onEffectsChange?.(this.effects);
  }

  async execute(
    action: Action,
    context: ActionExecutionContext = {},
  ): Promise<void> {
    if (this.disposed) return;

    switch (action.type) {
      case 'spotlight':
        this.effects = {
          ...this.effects,
          spotlight: {
            elementId: action.elementId,
            dimOpacity: action.dimOpacity,
          },
        };
        this.callbacks.onEffectsChange?.(this.effects);
        this.scheduleEffectClear();
        return;
      case 'laser':
        this.effects = {
          ...this.effects,
          laser: { elementId: action.elementId, color: action.color },
        };
        this.callbacks.onEffectsChange?.(this.effects);
        this.scheduleEffectClear();
        return;
      case 'speech':
        await this.executeSpeech(action, context);
        return;
      case 'play_video':
        await this.video?.play(action.elementId);
        return;
      default:
        return;
    }
  }

  private scheduleEffectClear(): void {
    this.clearEffectTimer();
    this.effectTimer = setTimeout(() => {
      this.effectTimer = null;
      this.effects = {};
      this.callbacks.onEffectsChange?.(this.effects);
    }, this.effectAutoClearMs);
  }

  private clearEffectTimer(): void {
    if (this.effectTimer !== null) {
      clearTimeout(this.effectTimer);
      this.effectTimer = null;
    }
  }

  private async executeSpeech(
    action: SpeechAction,
    context: ActionExecutionContext,
  ): Promise<void> {
    const ownsConcurrentFocus =
      context.hasConcurrentFocus === true &&
      (this.effects.spotlight !== undefined || this.effects.laser !== undefined);

    if (ownsConcurrentFocus) this.clearEffectTimer();

    try {
      if (action.audioUrl) {
        const audioResult = await this.media.playAudio(action.audioUrl);
        if (audioResult === 'ended' || this.disposed) return;
      }

      const speechResult = await this.media.speak(
        action.text,
        action.speed,
        action.voice,
      );
      if (speechResult === 'ended' || this.disposed) return;

      await this.media.wait(readingTimeMs(action.text));
    } finally {
      if (ownsConcurrentFocus) this.clearEffects();
    }
  }
}

class BrowserActionMediaAdapter implements ActionMediaAdapter {
  private cancelActive: (() => void) | null = null;

  playAudio(
    url: string,
    onDurationKnown?: (durationMs: number) => void,
  ): Promise<ActionMediaResult> {
    if (typeof Audio === 'undefined') return Promise.resolve('failed');

    this.cancel();
    return new Promise((resolve) => {
      const audio = new Audio(url);
      let settled = false;

      const settle = (result: ActionMediaResult) => {
        if (settled) return;
        settled = true;
        audio.removeEventListener('loadedmetadata', handleMetadata);
        audio.removeEventListener('ended', handleEnded);
        audio.removeEventListener('error', handleError);
        if (this.cancelActive === cancel) this.cancelActive = null;
        resolve(result);
      };
      const handleMetadata = () => {
        if (Number.isFinite(audio.duration)) {
          onDurationKnown?.(audio.duration * 1000);
        }
      };
      const handleEnded = () => settle('ended');
      const handleError = () => settle('failed');
      const cancel = () => {
        audio.pause();
        settle('failed');
      };

      this.cancelActive = cancel;
      audio.addEventListener('loadedmetadata', handleMetadata);
      audio.addEventListener('ended', handleEnded, { once: true });
      audio.addEventListener('error', handleError, { once: true });
      audio.play().catch(handleError);
    });
  }

  speak(
    text: string,
    speed?: number,
    voice?: string,
  ): Promise<ActionMediaResult> {
    if (
      typeof window === 'undefined' ||
      !('speechSynthesis' in window) ||
      typeof SpeechSynthesisUtterance === 'undefined' ||
      !text.trim()
    ) {
      return Promise.resolve('failed');
    }

    this.cancel();
    return new Promise((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      let settled = false;
      const settle = (result: ActionMediaResult) => {
        if (settled) return;
        settled = true;
        utterance.onend = null;
        utterance.onerror = null;
        if (this.cancelActive === cancel) this.cancelActive = null;
        resolve(result);
      };
      const cancel = () => {
        window.speechSynthesis.cancel();
        settle('failed');
      };

      if (speed !== undefined) utterance.rate = speed;
      const isCjk = cjkCharacterCount(text) > text.length * 0.3;
      utterance.lang = isCjk ? 'zh-CN' : 'en-US';
      const matchingVoice = selectPreferredBrowserVoice(
        window.speechSynthesis.getVoices(),
        voice,
        isCjk ? 'zh' : 'en',
      );
      if (matchingVoice) utterance.voice = matchingVoice;

      utterance.onend = () => settle('ended');
      utterance.onerror = () => settle('failed');
      this.cancelActive = cancel;
      window.speechSynthesis.speak(utterance);
    });
  }

  wait(durationMs: number): Promise<void> {
    this.cancel();
    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        if (this.cancelActive === cancel) this.cancelActive = null;
        resolve();
      }, durationMs);
      const cancel = () => {
        clearTimeout(timer);
        if (this.cancelActive === cancel) this.cancelActive = null;
        resolve();
      };
      this.cancelActive = cancel;
    });
  }

  cancel(): void {
    const cancel = this.cancelActive;
    this.cancelActive = null;
    cancel?.();
  }
}

function cjkCharacterCount(text: string): number {
  return (text.match(/[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]/g) ?? [])
    .length;
}

export function selectPreferredBrowserVoice(
  voices: readonly SpeechSynthesisVoice[],
  requestedName: string | undefined,
  languagePrefix: 'zh' | 'en',
): SpeechSynthesisVoice | undefined {
  return (
    voices.find((candidate) => candidate.name === requestedName) ??
    voices.find((candidate) =>
      candidate.lang.toLowerCase().startsWith(languagePrefix),
    )
  );
}

function readingTimeMs(text: string): number {
  const isCjk = cjkCharacterCount(text) > text.length * 0.3;
  return isCjk
    ? Math.max(2000, text.length * 150)
    : Math.max(2000, text.split(/\s+/).filter(Boolean).length * 240);
}
