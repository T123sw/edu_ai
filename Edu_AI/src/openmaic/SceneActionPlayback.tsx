import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { Action } from '@openmaic/dsl';
import { ActionEngine, type ActionWidgetController } from './actionEngine';
import { WallClockSource } from './clock';
import {
  PlaybackEngine,
  type PlaybackMode,
  type PlayableScene,
} from './playbackEngine';

export interface SceneActionPlaybackProps {
  sceneId: string;
  actions?: Array<Record<string, unknown>>;
  widget?: ActionWidgetController;
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
  children,
}: SceneActionPlaybackProps) {
  const [mode, setMode] = useState<PlaybackMode>('idle');
  const widgetRef = useRef(widget);
  widgetRef.current = widget;

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
    const actionEngine = new ActionEngine({}, { widget: widgetController });
    const engine = new PlaybackEngine(
      [playableScene],
      new WallClockSource(),
      { onModeChange: setMode },
      { actionExecutor: actionEngine },
    );
    engine.start();
    return () => engine.dispose();
  }, [actions, sceneId]);

  return (
    <div className="h-full w-full" data-playback-mode={mode}>
      {children}
    </div>
  );
}
