import type { Classroom, LearningResource } from './model';

export type ResearchSource = {
  courseId: string; courseTitle: string; chapterId: string; chapterTitle: string;
  resourceId: string; resourceTitle: string; version?: number;
};
export type ResearchDraft = {
  id: string; title: string; question: string; outcome: string; notes: string;
  source?: ResearchSource; updatedAt: number;
};

export const researchStorageKey = (owner: string) => `edu-ai:research-drafts:v1:${encodeURIComponent(owner)}`;

export function researchHref(room?: Classroom, resource?: LearningResource) {
  if (!room) return '#/research';
  const query = new URLSearchParams({ classroom: room.id });
  const id = resource?.id || room.selectedId;
  if (id) query.set('resource', id);
  return `#/research?${query}`;
}

export function researchSource(room?: Classroom, resourceId?: string): ResearchSource | undefined {
  const resource = room?.chapters.flatMap(c => c.resources).find(r => r.id === (resourceId || room.selectedId));
  const chapter = room?.chapters.find(c => c.resources.some(r => r.id === resource?.id));
  if (!room || !resource || !chapter) return;
  return { courseId: room.id, courseTitle: room.title, chapterId: chapter.id, chapterTitle: chapter.title,
    resourceId: resource.id, resourceTitle: resource.title, version: resource.remote?.version ?? resource.version };
}

export function sourceHref(source: ResearchSource) {
  return `#/classroom/${encodeURIComponent(source.courseId)}?${new URLSearchParams({ resource: source.resourceId })}`;
}

export function parseResearchDrafts(raw: string | null): ResearchDraft[] {
  if (!raw) return [];
  const value: unknown = JSON.parse(raw);
  if (!Array.isArray(value) || !value.every(item => {
    if (!item || typeof item !== 'object') return false;
    const draft = item as ResearchDraft;
    const source = draft.source;
    return ['id', 'title', 'question', 'outcome', 'notes'].every(k => typeof (item as Record<string, unknown>)[k] === 'string')
      && Number.isFinite(draft.updatedAt)
      && (source === undefined || (source !== null && typeof source === 'object' && ['courseId', 'courseTitle', 'chapterId', 'chapterTitle', 'resourceId', 'resourceTitle'].every(k => typeof (source as Record<string, unknown>)[k] === 'string')
        && (source.version === undefined || (Number.isInteger(source.version) && source.version > 0))));
  })) throw new Error('无法读取已有实践草稿，请保留浏览器数据并重试。');
  return value as ResearchDraft[];
}
