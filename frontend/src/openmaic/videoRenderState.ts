import type { ClassroomScene } from '../stitch/api/types.ts';
import type { LessonTimeline } from './timeline.ts';
import { mergeMeasuredSceneTimelines } from './videoExport.ts';

export type SelectedVideoRenderScene = {
  scene: ClassroomScene;
  sourceIndex: number;
  renderIndex: number;
  sceneCount: number;
};

export type CompletedVideoRenderSession = {
  status: 'completed';
  sceneCount: number;
  timeline: LessonTimeline;
};

export type FailedVideoRenderSession = {
  status: 'failed';
  error: string;
};

function isRenderableSlideScene(scene: ClassroomScene): boolean {
  return scene.content?.type === 'slide' && Boolean(scene.content.canvas);
}

export function selectVideoRenderScene(
  scenes: readonly ClassroomScene[],
  renderIndex: number,
): SelectedVideoRenderScene {
  const renderable = scenes
    .map((scene, sourceIndex) => ({ scene, sourceIndex }))
    .filter(({ scene }) => isRenderableSlideScene(scene));
  const selected = renderable[renderIndex];

  if (!selected) {
    const noun = renderable.length === 1 ? 'scene' : 'scenes';
    throw new RangeError(
      `render scene index ${renderIndex} is unavailable (${renderable.length} renderable ${noun})`,
    );
  }

  return {
    ...selected,
    renderIndex,
    sceneCount: renderable.length,
  };
}

export function completeVideoRenderSession(
  lessonId: string,
  sceneTimelines: readonly LessonTimeline[],
): CompletedVideoRenderSession {
  return {
    status: 'completed',
    sceneCount: sceneTimelines.length,
    timeline: mergeMeasuredSceneTimelines(lessonId, sceneTimelines),
  };
}

export function failVideoRenderSession(error: unknown): FailedVideoRenderSession {
  return {
    status: 'failed',
    error: error instanceof Error ? error.message : String(error),
  };
}
