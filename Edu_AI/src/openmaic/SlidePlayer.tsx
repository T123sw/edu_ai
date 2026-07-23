import { useEffect, useMemo, useRef, useState } from 'react';
import { SlideCanvas, type Slide } from '@openmaic/renderer';
import type { Action } from '@openmaic/dsl';
import { WallClockSource } from './clock';
import { PlaybackEngine, type PlaybackMode, type PlayableScene } from './playbackEngine';
import type { ActionEffectsState } from './actionEngine';

export interface SlidePlayerProps {
  slide: Slide;
  actions?: Action[];
  sceneId?: string;
  autoPlay?: boolean;
  onComplete?: () => void;
  className?: string;
}

/**
 * Plays a single Slide + its Scene.actions[] timeline. Wraps
 * `@openmaic/renderer`'s `<SlideCanvas>`, driven by {@link PlaybackEngine}
 * (ClockSource-injected — SPEC-08 §3.1 seam #1).
 *
 * Video elements always go through `renderVideo` (seam #3): this phase
 * returns a plain native `<video autoplay>`, matching the wall-clock "A"
 * branch; it must never fall through to SlideCanvas's own default `<video>`
 * so that swapping in an `<OffthreadVideo>`-based "B" implementation later
 * is a one-line change here, not a rewrite.
 *
 * Seam #2 (`localTimeMs?` optional prop on effect overlay components) does
 * not map cleanly onto this integration: `@openmaic/renderer` exposes
 * spotlight/laser/zoom as a plain `effects` config object on `<SlideCanvas>`,
 * not as directly-composable overlay components — that's the correct level
 * to integrate at (the alternative, `@openmaic/renderer/elements`, means
 * hand-assembling the whole canvas). The effect-timing seam therefore lives
 * one layer down, in {@link ClockSource}/{@link PlaybackEngine}: a future
 * frame-driven clock changes how long an effect stays active, not how
 * `effects` is threaded into `<SlideCanvas>`.
 */
export function SlidePlayer({
  slide,
  actions,
  sceneId,
  autoPlay = true,
  onComplete,
  className,
}: SlidePlayerProps) {
  const [effects, setEffects] = useState<ActionEffectsState>({});
  const [mode, setMode] = useState<PlaybackMode>('idle');
  const engineRef = useRef<PlaybackEngine | null>(null);

  const scenes = useMemo<PlayableScene[]>(
    () => [{ id: sceneId ?? slide.id, actions: actions ?? [] }],
    [sceneId, slide.id, actions],
  );

  useEffect(() => {
    const clock = new WallClockSource();
    const engine = new PlaybackEngine(scenes, clock, {
      onModeChange: setMode,
      onEffectsChange: setEffects,
      onComplete,
    });
    engineRef.current = engine;
    if (autoPlay) engine.start();
    return () => {
      engine.dispose();
      engineRef.current = null;
    };
    // scenes is memoized on the props that actually define it; autoPlay/onComplete
    // intentionally excluded so toggling them doesn't restart an in-flight playback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenes]);

  return (
    <div className={className} style={{ width: '100%', height: '100%' }} data-playback-mode={mode}>
      <SlideCanvas
        slide={slide}
        effects={effects}
        renderVideo={(el) => (
          <video
            src={el.src}
            autoPlay
            playsInline
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          />
        )}
      />
    </div>
  );
}
