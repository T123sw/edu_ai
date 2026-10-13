import type { ResourceRef } from './readingContext';

export type Citation = { resource_ref: ResourceRef; visibility?: string; locator?: {
  kind: string; block_id?: string; question_index?: number; scene_id?: string;
} | null };

export function citationUrl(citation: Citation): string {
  const ref = citation.resource_ref;
  const params = new URLSearchParams({ course_id: ref.course_id, material_type: ref.material_type, material_id: ref.material_id, version: String(ref.version), visibility: citation.visibility || 'private', citation: '1' });
  const locator = citation.locator;
  if (locator?.kind === 'document' && /^report-v1:\d+:\d+:[0-9a-f]{8}$/.test(locator.block_id || '')) params.set('block_id', locator.block_id!);
  if (locator?.kind === 'quiz' && Number.isSafeInteger(locator.question_index) && locator.question_index! >= 0) params.set('question_index', String(locator.question_index));
  if (locator?.kind === 'classroom' && locator.scene_id) params.set('scene_id', locator.scene_id);
  return `?learningPlayer=1#ai?${params}`;
}
