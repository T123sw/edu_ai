import type { ClassroomReadingContext } from '../openmaic/classroomReading';
import type { LearningResource } from '../selfLearning/model';
export type ResourceRef = { course_id: string; material_type: string; material_id: string; version: number };
export type Locator = { kind: 'document'; scroll_top: number } | { kind: 'classroom'; scene_id: string };
export type ReadingMessage = { type: 'learning-reading-context'; channel_id: string; resource_ref: ResourceRef; sequence: number; locator: Locator; reached_end: boolean; selected_text?: string; classroom?: ClassroomReadingContext };
export const resourceRef = (resource: LearningResource): ResourceRef | undefined => resource.remote && ({ course_id: resource.remote.courseId, material_type: resource.remote.materialType, material_id: resource.remote.materialId, version: resource.remote.version });
export const refKey = (ref: ResourceRef) => JSON.stringify([ref.course_id, ref.material_type, ref.material_id, ref.version]);
export function acceptReadingMessage(data: unknown, channel: string, ref: ResourceRef, lastSequence: number): data is ReadingMessage {
  if (!data || typeof data !== 'object') return false;
  const m = data as ReadingMessage;
  if (m.type !== 'learning-reading-context' || m.channel_id !== channel || !m.resource_ref || refKey(m.resource_ref) !== refKey(ref) || !Number.isSafeInteger(m.sequence) || m.sequence <= lastSequence || typeof m.reached_end !== 'boolean') return false;
  if (m.selected_text !== undefined && (typeof m.selected_text !== 'string' || m.selected_text.length > 10000)) return false;
  if (m.classroom !== undefined && (ref.material_type !== 'classroom' || !validClassroomContext(m.classroom))) return false;
  const l = m.locator;
  return !!l && (ref.material_type === 'classroom'
    ? l.kind === 'classroom' && typeof l.scene_id === 'string' && l.scene_id.length > 0
    : l.kind === 'document' && Number.isFinite(l.scroll_top) && l.scroll_top >= 0);
}

function validClassroomContext(value: unknown): value is ClassroomReadingContext {
  if (!value || typeof value !== 'object') return false;
  const context = value as ClassroomReadingContext;
  if (!['idle', 'playing', 'paused', 'interrupted', 'completed'].includes(context.status)) return false;
  const p = context.lecture;
  if (p === undefined) return true;
  const id = (v: unknown) => typeof v === 'string' && v.length > 0 && v.length <= 240;
  return !!p && id(p.scene_id) && id(p.action_id)
    && (p.speech_action_id === undefined || id(p.speech_action_id))
    && (p.sentence_index === undefined || (Number.isSafeInteger(p.sentence_index) && p.sentence_index >= 0 && p.sentence_index <= 10000 && !!p.speech_action_id))
    && (p.sentence_alignment === undefined || ['estimated', 'sentence'].includes(p.sentence_alignment))
    && typeof p.speech_completed === 'boolean'
    && Array.isArray(p.highlighted_element_ids) && p.highlighted_element_ids.length <= 20 && p.highlighted_element_ids.every(id);
}
