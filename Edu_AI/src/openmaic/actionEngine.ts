/**
 * ActionEngine — edu_ai port of OpenMAIC's `lib/action/engine.ts` (MIT),
 * trimmed to what Phase 3 needs: `speech` (sync) + `spotlight`/`laser`
 * (fire-and-forget). Other action types (whiteboard/discussion/widget/
 * play_video) are no-ops for now — none of them appear in Phase 2 MVP
 * generated classrooms (media/TTS/widgets all deferred, see SPEC-04 §0.1
 * D1/D2), so faithfully porting them is deferred until Phase 3 needs to
 * render a real generated lesson rather than the hand-written smoke sample.
 *
 * Mirrors the upstream semantics exactly for the two action kinds it does
 * implement: fire-and-forget actions set effect state and resolve
 * immediately (don't block the timeline); the caller advances to the next
 * action right away, so a spotlight authored immediately *before* a speech
 * action naturally overlaps that speech's duration — that's the whole
 * "concurrency semantics" (SPEC-02 §3.2), no explicit pairing logic needed.
 */

import type { Action, SpeechAction } from '@openmaic/dsl';

/** Mirrors upstream ActionEngine's EFFECT_AUTO_CLEAR_MS. */
const EFFECT_AUTO_CLEAR_MS = 5000;

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

export class ActionEngine {
  private effects: ActionEffectsState = {};
  private effectTimer: ReturnType<typeof setTimeout> | null = null;
  /** Wall-clock deadline the current `effectTimer` is armed for — lets
   * {@link extendEffectClearFor} tell whether a proposed new deadline would
   * actually push the clear out further, without needing to track a
   * separate "armed at" timestamp. */
  private effectClearDeadline: number | null = null;
  private readonly callbacks: ActionEngineCallbacks;

  constructor(callbacks: ActionEngineCallbacks = {}) {
    this.callbacks = callbacks;
  }

  dispose(): void {
    this.clearEffectTimer();
  }

  clearEffects(): void {
    this.clearEffectTimer();
    this.effects = {};
    this.callbacks.onEffectsChange?.(this.effects);
  }

  /**
   * Execute a single action. Fire-and-forget actions (spotlight/laser)
   * return immediately; `speech` returns a Promise that resolves when the
   * narration finishes (real audio, browser TTS, or a reading-time
   * estimate — same three-tier fallback as upstream).
   */
  async execute(action: Action): Promise<void> {
    switch (action.type) {
      case 'spotlight':
        this.effects = { ...this.effects, spotlight: { elementId: action.elementId, dimOpacity: action.dimOpacity } };
        this.callbacks.onEffectsChange?.(this.effects);
        this.scheduleEffectClear();
        return;
      case 'laser':
        this.effects = { ...this.effects, laser: { elementId: action.elementId, color: action.color } };
        this.callbacks.onEffectsChange?.(this.effects);
        this.scheduleEffectClear();
        return;
      case 'speech':
        return this.executeSpeech(action);
      default:
        // Not yet ported — see module docstring.
        return;
    }
  }

  private scheduleEffectClear(delayMs: number = EFFECT_AUTO_CLEAR_MS): void {
    this.armEffectClearTimer(delayMs);
  }

  /**
   * Push the currently-armed spotlight/laser auto-clear out to cover a
   * speech that turns out to run longer than `EFFECT_AUTO_CLEAR_MS` —
   * without this, any real TTS clip longer than 5s (verified: 8-14s is
   * common with real Qwen TTS output) goes dark mid-narration, then the
   * highlight only reappears when the *next* pair's spotlight fires. Only
   * ever extends, never shortens, an already-armed clear — a spotlight/laser
   * with nothing timed after it still auto-clears at the original delay
   * (defends against a highlight lingering forever if a scene stalls on a
   * lone fire-and-forget action).
   */
  private extendEffectClearFor(durationMs: number): void {
    if (this.effectTimer === null) return; // no active spotlight/laser to extend
    const buffer = 300; // covers audio decode/start jitter so the clear doesn't beat 'ended'
    const proposedDeadline = Date.now() + durationMs + buffer;
    if (this.effectClearDeadline !== null && proposedDeadline <= this.effectClearDeadline) return;
    this.armEffectClearTimer(proposedDeadline - Date.now());
  }

  private armEffectClearTimer(delayMs: number): void {
    this.clearEffectTimer();
    this.effectClearDeadline = Date.now() + delayMs;
    this.effectTimer = setTimeout(() => {
      this.effects = {};
      this.callbacks.onEffectsChange?.(this.effects);
      this.effectTimer = null;
      this.effectClearDeadline = null;
    }, delayMs);
  }

  private clearEffectTimer(): void {
    if (this.effectTimer) {
      clearTimeout(this.effectTimer);
      this.effectTimer = null;
      this.effectClearDeadline = null;
    }
  }

  /**
   * Three-tier fallback, mirrors upstream: pre-generated `audioUrl` → browser
   * TTS (Web Speech API) → estimated reading-time dwell (CJK ~150ms/char,
   * min 2s). A spotlight/laser authored immediately before a speech action
   * (SPEC-02 §3.2's overlap semantics) has its auto-clear extended to match
   * whichever tier actually ends up running, so the highlight stays lit for
   * the real narration length instead of the fixed 5s default.
   */
  private async executeSpeech(action: SpeechAction): Promise<void> {
    if (action.audioUrl) {
      await playAudioUrl(action.audioUrl, (durationMs) => this.extendEffectClearFor(durationMs));
      return;
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window && action.text.trim()) {
      await speakWithBrowserTts(action.text, action.speed);
      return;
    }
    const dwellMs = readingTimeMs(action.text);
    this.extendEffectClearFor(dwellMs);
    await new Promise<void>((resolve) => setTimeout(resolve, dwellMs));
  }
}

function playAudioUrl(url: string, onDurationKnown?: (durationMs: number) => void): Promise<void> {
  return new Promise((resolve) => {
    const audio = new Audio(url);
    audio.addEventListener(
      'loadedmetadata',
      () => {
        if (Number.isFinite(audio.duration)) onDurationKnown?.(audio.duration * 1000);
      },
      { once: true },
    );
    audio.addEventListener('ended', () => resolve(), { once: true });
    audio.addEventListener('error', () => resolve(), { once: true });
    audio.play().catch(() => resolve());
  });
}

function speakWithBrowserTts(text: string, speed?: number): Promise<void> {
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text);
    if (speed) utterance.rate = speed;
    const cjkRatio = (text.match(/[一-鿿㐀-䶿]/g) || []).length / Math.max(text.length, 1);
    utterance.lang = cjkRatio > 0.3 ? 'zh-CN' : 'en-US';
    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
  });
}

function readingTimeMs(text: string): number {
  const cjkCount = (text.match(/[一-鿿㐀-䶿぀-ゟ゠-ヿ가-힯]/g) || []).length;
  const isCjk = cjkCount > text.length * 0.3;
  return isCjk
    ? Math.max(2000, text.length * 150)
    : Math.max(2000, text.split(/\s+/).filter(Boolean).length * 240);
}
