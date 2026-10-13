import { LecturePositionTracker, type LecturePosition } from './classroomReading';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Action } from '@openmaic/dsl';
import { ActionEngine, type ActionWidgetController } from './actionEngine';
import { WallClockSource } from './clock';
import {
  PlaybackEngine,
  type PlaybackMode,
  type PlayableScene,
} from './playbackEngine';
import type { PlaybackRuntimeHandle } from './pagePlaybackController';

export interface SceneActionPlaybackProps {
  sceneId: string;
  actions?: Array<Record<string, unknown>>;
  widget?: ActionWidgetController;
  autoPlay?: boolean;
  onComplete?: () => void;
  onNarrationChange?: (text: string) => void;
  onLectureChange?: (position: LecturePosition) => void;
  onModeChange?: (mode: PlaybackMode) => void;
  onRuntimeReady?: (runtime: PlaybackRuntimeHandle | null) => void;
  children: ReactNode;
}

/**
 * Runs an OpenMAIC action timeline for non-slide scenes. Completion stops the
 * narration/action track but deliberately leaves navigation to the learner.
 */
export function SceneActionPlayback({
  sceneId,
  actions,
  widget,
  autoPlay = true,
  onComplete,
  onNarrationChange,
  onLectureChange,
  onModeChange,
  onRuntimeReady,
  children,
}: SceneActionPlaybackProps) {
  const [mode, setMode] = useState<PlaybackMode>('idle');
  const widgetRef = useRef(widget);
  widgetRef.current = widget;
  const callbacksRef = useRef({ onComplete, onModeChange, onRuntimeReady, onNarrationChange, onLectureChange });
  callbacksRef.current = { onComplete, onModeChange, onRuntimeReady, onNarrationChange, onLectureChange };

  useEffect(() => {
    const playableScene: PlayableScene = {
      id: sceneId,
      order: 0,
      actions: (actions ?? []) as Action[],
    };
    const widgetController: ActionWidgetController = {
      postMessage(type, payload) {
        widgetRef.current?.postMessage(type, payload);
      },
    };
    const lecture = new LecturePositionTracker(sceneId, (position) => callbacksRef.current.onLectureChange?.(position));
    const actionEngine = new ActionEngine({
      onNarrationPosition: (id, index, alignment) => lecture.sentence(id, index, alignment),
      onNarrationChange: (text) => callbacksRef.current.onNarrationChange?.(text),
    }, { widget: widgetController });
    const engine = new PlaybackEngine(
      [playableScene],
      new WallClockSource(),
      {
        onModeChange: (nextMode) => {
          setMode(nextMode);
          callbacksRef.current.onModeChange?.(nextMode);
        },
        onActionStart: (action) => lecture.start(action),
        onActionEnd: (action) => lecture.end(action),
        onComplete: () => callbacksRef.current.onComplete?.(),
      },
      { actionExecutor: actionEngine },
    );
    const runtime: PlaybackRuntimeHandle = {
      play: () => { lecture.restart(); engine.start(); },
      suspend: () => { lecture.freeze(); return engine.suspend(); },
      resume: (checkpoint) => { lecture.resume(); engine.resume(checkpoint); },
      cancel: () => { lecture.freeze(); engine.stop(); },
      dispose: () => { lecture.freeze(); engine.dispose(); },
    };
    callbacksRef.current.onRuntimeReady?.(runtime);
    if (autoPlay) engine.start();
    return () => {
      callbacksRef.current.onRuntimeReady?.(null);
      lecture.freeze();
      engine.dispose();
    };
    // autoPlay is initial mount behavior. Parent playback state changes must
    // not recreate the checkpoint-owning engine during an interruption.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actions, sceneId]);

  return (
    <div className="h-full w-full" data-playback-mode={mode}>
      {children}
    </div>
  );
}
