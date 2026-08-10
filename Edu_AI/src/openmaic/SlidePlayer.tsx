import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { SlideCanvas, type Slide } from '@openmaic/renderer';
import type { Action, PPTVideoElement } from '@openmaic/dsl';
import { WallClockSource } from './clock';
import { PlaybackEngine, type PlaybackMode, type PlayableScene } from './playbackEngine';
import { ActionEngine, type ActionEffectsState } from './actionEngine';
import { compileLessonTimeline, type LessonTimeline } from './timeline';
import { TimelineRecorder } from './timelineRecorder';
import { VideoRegistry } from './videoRegistry';
import type { PlaybackRuntimeHandle } from './pagePlaybackController';

export interface SlidePlayerProps {
  slide: Slide;
  actions?: Action[];
  sceneId?: string;
  autoPlay?: boolean;
  onComplete?: () => void;
  onModeChange?: (mode: PlaybackMode) => void;
  onRuntimeReady?: (runtime: PlaybackRuntimeHandle | null) => void;
  onTimelineChange?: (timeline: LessonTimeline) => void;
  className?: string;
}

/**
 * Plays a single Slide + its Scene.actions[] timeline. Wraps
 * `@openmaic/renderer`'s `<SlideCanvas>`, driven by {@link PlaybackEngine}
 * (ClockSource-injected — SPEC-08 §3.1 seam #1).
 *
 * Video elements always go through `renderVideo` (seam #3) and register their
 * native element by stable DSL ID. They never autoplay: a `play_video` action
 * owns start/completion timing through the same playback engine as narration.
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
  onModeChange,
  onRuntimeReady,
  onTimelineChange,
  className,
}: SlidePlayerProps) {
  const [effects, setEffects] = useState<ActionEffectsState>({});
  const [mode, setMode] = useState<PlaybackMode>('idle');
  const engineRef = useRef<PlaybackEngine | null>(null);
  const videoRegistry = useMemo(() => new VideoRegistry(), []);
  const callbacksRef = useRef({
    onComplete,
    onModeChange,
    onRuntimeReady,
    onTimelineChange,
  });
  callbacksRef.current = {
    onComplete,
    onModeChange,
    onRuntimeReady,
    onTimelineChange,
  };

  const scenes = useMemo<PlayableScene[]>(
    () => [{ id: sceneId ?? slide.id, order: 0, actions: actions ?? [] }],
    [sceneId, slide.id, actions],
  );
  const timeline = useMemo(
    () =>
      compileLessonTimeline({
        lessonId: sceneId ?? slide.id,
        scenes: [
          {
            id: sceneId ?? slide.id,
            order: 0,
            slideRef: slide.id,
            actions: actions ?? [],
          },
        ],
        viewport: {
          width: slide.viewportSize,
          height: slide.viewportSize * slide.viewportRatio,
          ratio: slide.viewportRatio,
        },
      }),
    [actions, sceneId, slide.id, slide.viewportRatio, slide.viewportSize],
  );

  useEffect(() => {
    const clock = new WallClockSource();
    const recorder = new TimelineRecorder(timeline);
    const actionEngine = new ActionEngine(
      { onEffectsChange: setEffects },
      { video: videoRegistry },
    );
    const engine = new PlaybackEngine(scenes, clock, {
      onModeChange: (nextMode) => {
        setMode(nextMode);
        callbacksRef.current.onModeChange?.(nextMode);
      },
      onActionStart: (action, timeMs, currentSceneId) => {
        recorder.onActionStart(action.id, currentSceneId, timeMs);
      },
      onActionEnd: (action, timeMs, currentSceneId) => {
        recorder.onActionEnd(action.id, currentSceneId, timeMs);
        callbacksRef.current.onTimelineChange?.(recorder.snapshot());
      },
      onComplete: () => {
        callbacksRef.current.onTimelineChange?.(recorder.snapshot());
        callbacksRef.current.onComplete?.();
      },
    }, { timeline, actionExecutor: actionEngine });
    engineRef.current = engine;
    const runtime: PlaybackRuntimeHandle = {
      play: () => engine.start(),
      suspend: () => engine.suspend(),
      resume: (checkpoint) => engine.resume(checkpoint),
      cancel: () => engine.stop(),
      dispose: () => engine.dispose(),
    };
    callbacksRef.current.onRuntimeReady?.(runtime);
    if (autoPlay) engine.start();
    return () => {
      callbacksRef.current.onRuntimeReady?.(null);
      engine.dispose();
      engineRef.current = null;
    };
    // scenes/timeline are memoized on playback data. Callback props are read
    // through callbacksRef so parent renders do not restart an in-flight lesson.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenes, timeline]);

  return (
    <div
      className={className}
      style={{ width: '100%', height: '100%' }}
      data-playback-mode={mode}
      data-timeline-version={timeline.version}
    >
      <SlideCanvas
        slide={slide}
        effects={effects}
        renderVideo={(el) => (
          <RegisteredVideo element={el} registry={videoRegistry} />
        )}
      />
    </div>
  );
}

function RegisteredVideo({
  element,
  registry,
}: {
  element: PPTVideoElement;
  registry: VideoRegistry;
}) {
  const unregisterRef = useRef<(() => void) | null>(null);
  const attachVideo = useCallback(
    (video: HTMLVideoElement | null) => {
      unregisterRef.current?.();
      unregisterRef.current = video
        ? registry.register(element.id, video)
        : null;
    },
    [element.id, registry],
  );

  return (
    <video
      ref={attachVideo}
      src={element.src}
      poster={element.poster}
      muted
      playsInline
      preload="metadata"
      controls={Boolean(element.src)}
      data-video-element-id={element.id}
      style={{ width: '100%', height: '100%', objectFit: 'contain' }}
    />
  );
}
