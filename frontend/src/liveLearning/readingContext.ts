import type { LearningResource } from '../selfLearning/model';
export type ResourceRef = { course_id: string; material_type: string; material_id: string; version: number };
export type Locator = { kind: 'document'; scroll_top: number } | { kind: 'classroom'; scene_id: string };
export type ReadingMessage = { type: 'learning-reading-context'; channel_id: string; resource_ref: ResourceRef; sequence: number; locator: Locator; reached_end: boolean; selected_text?: string };
export const resourceRef = (resource: LearningResource): ResourceRef | undefined => resource.remote && ({ course_id: resource.remote.courseId, material_type: resource.remote.materialType, material_id: resource.remote.materialId, version: resource.remote.version });
export const refKey = (ref: ResourceRef) => JSON.stringify([ref.course_id, ref.material_type, ref.material_id, ref.version]);
export function acceptReadingMessage(data: unknown, channel: string, ref: ResourceRef, lastSequence: number): data is ReadingMessage {
  if (!data || typeof data !== 'object') return false;
  const m = data as ReadingMessage;
  if (m.type !== 'learning-reading-context' || m.channel_id !== channel || !m.resource_ref || refKey(m.resource_ref) !== refKey(ref) || !Number.isSafeInteger(m.sequence) || m.sequence <= lastSequence || typeof m.reached_end !== 'boolean') return false;
  if (m.selected_text !== undefined && (typeof m.selected_text !== 'string' || m.selected_text.length > 10000)) return false;
  const l = m.locator;
  return !!l && (ref.material_type === 'classroom'
    ? l.kind === 'classroom' && typeof l.scene_id === 'string' && l.scene_id.length > 0
    : l.kind === 'document' && Number.isFinite(l.scroll_top) && l.scroll_top >= 0);
}
