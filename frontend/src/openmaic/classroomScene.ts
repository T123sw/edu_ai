import type { ClassroomScene } from '../stitch/api/types.ts';

export type ClassroomSceneKind =
  | 'slide'
  | 'interactive'
  | 'quiz'
  | 'invalid'
  | 'unsupported';

const SUPPORTED_SCENE_TYPES = new Set(['slide', 'interactive', 'quiz']);

export interface ClassroomScenePresentation {
  title: string;
  narration: string[];
  hasPlayback: boolean;
  kindLabel: string;
}

export function resolveClassroomSceneKind(
  scene: ClassroomScene,
): ClassroomSceneKind {
  const contentType = scene.content?.type;
  if (typeof contentType !== 'string' || contentType !== scene.type) {
    return 'invalid';
  }
  if (SUPPORTED_SCENE_TYPES.has(scene.type)) {
    return scene.type as 'slide' | 'interactive' | 'quiz';
  }
  return 'unsupported';
}

export function getClassroomScenePresentation(
  scene: ClassroomScene,
  index: number,
): ClassroomScenePresentation {
  const kind = resolveClassroomSceneKind(scene);
  const narration = (scene.actions ?? [])
    .filter(
      (action) =>
        action.type === 'speech' &&
        typeof action.text === 'string' &&
        action.text.trim().length > 0,
    )
    .map((action) => String(action.text).trim());

  return {
    title: scene.title?.trim() || `第 ${index + 1} 页`,
    narration,
    hasPlayback: (scene.actions?.length ?? 0) > 0,
    kindLabel:
      kind === 'slide'
        ? '课件页'
        : kind === 'interactive'
          ? '互动演示'
          : kind === 'quiz'
            ? '互动练习'
            : '内容页',
  };
}
