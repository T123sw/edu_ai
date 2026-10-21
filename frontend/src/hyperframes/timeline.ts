import type { HyperframesContent, HyperframesLocator } from './types';
export function positionAt(content: HyperframesContent, seconds: number): HyperframesLocator {
  const time = Number.isFinite(seconds) ? Math.max(0, Math.min(content.timeline.duration, seconds)) : 0;
  const segments = content.timeline.segments;
  const segment = segments.find(s => time >= s.start && time < s.end) ?? (time === content.timeline.duration ? segments.findLast(s => s.end === time) : undefined);
  return { kind: 'hyperframes', seconds: time, ...(segment ? { segment_id: segment.id } : {}), content_hash: content.project.digest };
}
/** Only contiguous observed playback contributes watch time. Jumps and suspension do not. */
export class WatchedIntervals {
  private previous?: { seconds: number; wall: number };
  reset() { this.previous = undefined; }
  sample(seconds: number, playing: boolean, rate: number, wall = performance.now()): [number, number] | undefined {
    const previous = this.previous;
    this.previous = playing ? { seconds, wall } : undefined;
    if (!playing || !previous) return;
    const delta = seconds - previous.seconds;
    const expected = (wall - previous.wall) / 1000 * rate;
    if (delta <= 0 || expected < 0 || expected > 2 || Math.abs(delta - expected) > 0.25) return;
    return [previous.seconds, seconds];
  }
}
export function formatTime(seconds: number) { return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`; }
