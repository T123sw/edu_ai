import type { CourseMaterial } from "../api/types";

export const ARTIFACT_REVISION_TYPES = ["report", "report_outline", "lesson_plan", "blog", "quiz", "flashcard", "graph", "game", "classroom"] as const;
export type ArtifactRevisionType = typeof ARTIFACT_REVISION_TYPES[number];
export type ArtifactRevisionReference = {
  artifact_id: string;
  artifact_type: ArtifactRevisionType;
  version_id: string;
  title?: string;
  source_course_id: string;
  source_conversation_id?: string;
};
export type RevisionIntent = { reference: ArtifactRevisionReference; ownerUserId: string };
const listeners = new Set<(intent: RevisionIntent) => void>();
// One in-memory handoff survives route unmount only; never persisted across accounts.
let pending: RevisionIntent | undefined;

export function createRevisionIntent(material: CourseMaterial, ownerUserId: string): RevisionIntent | null {
  if (!ownerUserId || material.owner_user_id !== ownerUserId || material.visibility !== "private"
    || material.published_from_material_id || !material.course_id || !material.material_id
    || !Number.isInteger(material.version) || (material.version ?? 0) < 1) return null;
  const kind = ARTIFACT_REVISION_TYPES.find((type) => type === material.material_type);
  if (!kind) return null;
  return { ownerUserId, reference: {
    artifact_id: material.material_id, artifact_type: kind,
    version_id: `v${material.version}`, title: material.title || material.topic || material.material_id,
    source_course_id: material.course_id,
  } };
}

export function dispatchRevisionIntent(intent: RevisionIntent): void {
  pending = intent;
  for (const listener of listeners) listener(intent);
  if (listeners.size) pending = undefined;
}

export function clearRevisionIntent(): void { pending = undefined; }

export function subscribeRevisionIntent(listener: (intent: RevisionIntent) => void): () => void {
  listeners.add(listener);
  if (pending) {
    const intent = pending;
    // Deliver after mount effects start history initialization. Immediate delivery
    // races ChatPanel's initial historyLoading=false effect and loses the target.
    queueMicrotask(() => {
      if (pending !== intent || !listeners.has(listener)) return;
      pending = undefined;
      listener(intent);
    });
  }
  return () => { listeners.delete(listener); };
}
