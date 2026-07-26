import type { ClassroomScene } from '../stitch/api/types.ts';

export type ClassroomSceneKind =
  | 'slide'
  | 'interactive'
  | 'quiz'
  | 'invalid'
  | 'unsupported';

const SUPPORTED_SCENE_TYPES = new Set(['slide', 'interactive', 'quiz']);

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
