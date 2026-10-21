import type { ClassroomReadingContext } from '../classroom/reading';
import type { LearningResource } from '../selfLearning/model';
export type ResourceRef = { course_id: string; material_type: string; material_id: string; version: number };
export type Locator = import('../hyperframes/types').HyperframesLocator | { kind: 'document'; scroll_top: number; block_id?: string } | { kind: 'classroom'; scene_id: string } | { kind: 'quiz'; question_index: number };
export type PracticeContext = { check_id: string; attempt_id?: string; draft?: { option_ids: string[]; text: string } };
export type ReadingMessage = { type: 'learning-reading-context'; channel_id: string; resource_ref: ResourceRef; sequence: number; locator: Locator; reached_end: boolean; selected_text?: string; classroom?: ClassroomReadingContext; practice?: PracticeContext; question_prompt?: string; intent?: 'ask' };
export const resourceRef = (resource: LearningResource): ResourceRef | undefined => resource.remote && ({ course_id: resource.remote.courseId, material_type: resource.remote.materialType, material_id: resource.remote.materialId, version: resource.remote.version });
export const refKey = (ref: ResourceRef) => JSON.stringify([ref.course_id, ref.material_type, ref.material_id, ref.version]);
export function acceptReadingMessage(data: unknown, channel: string, ref: ResourceRef, lastSequence: number): data is ReadingMessage {
  if (!data || typeof data !== 'object') return false;
  const m = data as ReadingMessage;
  if (m.type !== 'learning-reading-context' || m.channel_id !== channel || !m.resource_ref || refKey(m.resource_ref) !== refKey(ref) || !Number.isSafeInteger(m.sequence) || m.sequence <= lastSequence || typeof m.reached_end !== 'boolean') return false;
  if (m.selected_text !== undefined && (typeof m.selected_text !== 'string' || m.selected_text.length > 10000)) return false;
  if (m.intent !== undefined && (m.intent !== 'ask' || !m.selected_text)) return false;
  if (m.practice !== undefined && (ref.material_type !== 'quiz' || !validPracticeContext(m.practice))) return false;
  if (m.question_prompt !== undefined && (m.intent !== 'ask' || typeof m.question_prompt !== 'string' || m.question_prompt.length > 2000)) return false;
  if (m.classroom !== undefined && (ref.material_type !== 'classroom' || !validClassroomContext(m.classroom))) return false;
  const l = m.locator;
  return !!l && (ref.material_type === 'classroom'
    ? (l.kind === 'hyperframes' ? Number.isFinite(l.seconds) && l.seconds >= 0 && (l.segment_id === undefined || typeof l.segment_id === 'string' && l.segment_id.length > 0 && l.segment_id.length <= 240) && (l.content_hash === undefined || typeof l.content_hash === 'string' && l.content_hash.length <= 240) : l.kind === 'classroom' && typeof l.scene_id === 'string' && l.scene_id.length > 0)
    : (ref.material_type === 'quiz' && l.kind === 'quiz')
      ? Number.isSafeInteger(l.question_index) && l.question_index >= 0 && l.question_index <= 9999
      : l.kind === 'document' && Number.isFinite(l.scroll_top) && l.scroll_top >= 0 && (l.block_id === undefined || (typeof l.block_id === 'string' && /^report-v1:\d+:\d+:[0-9a-f]{8}$/.test(l.block_id) && l.block_id.length <= 240)));
}

export function validPracticeContext(value: unknown): value is PracticeContext {
  if (!value || typeof value !== 'object') return false;
  const p = value as PracticeContext;
  const id = (s: unknown) => typeof s === 'string' && s.length > 0 && s.length <= 240;
  if (!id(p.check_id) || (p.attempt_id !== undefined && !id(p.attempt_id)) || (p.attempt_id !== undefined && p.draft !== undefined)) return false;
  return p.draft === undefined || (!!p.draft && Array.isArray(p.draft.option_ids) && p.draft.option_ids.length <= 8 && p.draft.option_ids.every(s => id(s) && s.length <= 80) && typeof p.draft.text === 'string' && p.draft.text.length <= 4000);
}

function validClassroomContext(value: unknown): value is ClassroomReadingContext {
  if (!value || typeof value !== 'object') return false;
  const context = value as ClassroomReadingContext;
  if (!['idle', 'playing', 'paused', 'interrupted', 'completed'].includes(context.status)) return false;
  if (context.position !== undefined && (!context.position || !Number.isFinite(context.position.seconds) || context.position.seconds < 0 || (context.position.segment_id !== undefined && (typeof context.position.segment_id !== 'string' || !context.position.segment_id || context.position.segment_id.length > 240)))) return false;
  if (context.position !== undefined && context.lecture !== undefined) return false;
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
