/**
 * ClockSource — playback-time seam #1 (SPEC-08 §3.1 / ACC-08 AC-08-7).
 *
 * Phase 3 only wires the wall-clock implementation (real narration timing).
 * Phase 5/B would swap in a virtual frame clock driven by a deterministic
 * renderer; nothing else in {@link PlaybackEngine} needs to change because it
 * only ever asks the clock "what time is it", never reaches for
 * `performance.now()`/`Date.now()` directly.
 */
export interface ClockSource {
  currentTimeMs(): number;
}

export class WallClockSource implements ClockSource {
  private readonly startedAt = performance.now();

  currentTimeMs(): number {
    return performance.now() - this.startedAt;
  }
}
