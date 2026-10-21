import { kindLabel, type Classroom, type LearningResource, type ResourceKind } from '../selfLearning/model';

/** Planned resources stay visible even before a material/version exists. */
export function withResourcePlaceholders(room: Classroom): Classroom {
  if (!room.preparationDelivery) return room;
  const order: ResourceKind[] = ['video', 'report', 'quiz', 'slides'];
  const kinds: Record<string, ResourceKind> = { classroom: 'video', report: 'report', quiz: 'quiz' };
  const chapters = room.chapters.map(chapter => {
    const pendingKinds = [...new Set((chapter.pendingResourceTypes || []).map(type => kinds[type]).filter(Boolean))];
    const resources = chapter.resources.filter(r => !pendingKinds.length || r.id !== `pending:${chapter.id}`);
    for (const kind of pendingKinds) {
      if (!resources.some(r => r.kind === kind)) resources.push({
        id: `pending:${chapter.id}:${kind}`, title: `${chapter.title} · ${kindLabel[kind]}`,
        topic: chapter.title, chapterId: chapter.id, kind, ready: false,
        minutes: 0, createdAt: 0, live: true,
      });
    }
    resources.sort((a, b) => order.indexOf(a.kind) - order.indexOf(b.kind));
    return resources.length === chapter.resources.length && resources.every((r, i) => r === chapter.resources[i])
      ? chapter : { ...chapter, resources };
  });
  if (chapters.every((c, i) => c === room.chapters[i])) return room;
  const selected = room.chapters.find(c => c.resources.some(r => r.id === room.selectedId));
  return { ...room, chapters, selectedId: chapters.some(c => c.resources.some(r => r.id === room.selectedId))
    ? room.selectedId : chapters.find(c => c.id === selected?.id)?.resources[0]?.id || room.selectedId };
}

function sameVersion(a: LearningResource, b: LearningResource) {
  if (a.id !== b.id || a.ready !== b.ready) return false;
  if (a.remote || b.remote) return a.remote?.courseId === b.remote?.courseId &&
    a.remote?.materialId === b.remote?.materialId && a.remote?.materialType === b.remote?.materialType &&
    a.remote?.version === b.remote?.version;
  return a.version === b.version && a.content === b.content;
}

/** Accept additive deliveries from this preparation, never silently replace a
 * playing resource with a different version or switch to a revised course. */
export function mergeProgressiveCourse(previous: Classroom, next: Classroom): Classroom {
  next = withResourcePlaceholders(next);
  const changed = previous.manifestRef && next.manifestRef?.version !== previous.manifestRef.version;
  if (changed) {
    const additive = previous.preparationDelivery?.state === 'partial' &&
      previous.preparationDelivery.preparationId === next.preparationDelivery?.preparationId &&
      previous.manifestRef?.manifest_id === next.manifestRef?.manifest_id &&
      (next.manifestRef?.version || 0) > (previous.manifestRef?.version || 0) &&
      previous.routeVersion === next.routeVersion &&
      previous.chapters.length === next.chapters.length &&
      previous.chapters.every((chapter, index) => chapter.id === next.chapters[index].id &&
        chapter.resources.filter(r => r.ready).every(r => next.chapters[index].resources.some(n => sameVersion(r, n))));
    if (!additive) return previous;
  }
  const oldResources = previous.chapters.flatMap(c => c.resources);
  const chapters = next.chapters.map(chapter => ({ ...chapter, resources: chapter.resources.map(resource => {
    const old = oldResources.find(r => r.id === resource.id);
    // Stable resource props also keep iframe/player subscriptions intact.
    return old && sameVersion(old, resource) && JSON.stringify(old) === JSON.stringify(resource) ? old : resource;
  }) }));
  const resources = chapters.flatMap(c => c.resources);
  let selectedId = previous.selectedId;
  if (!resources.some(r => r.id === selectedId)) {
    const chapter = previous.chapters.find(c => c.resources.some(r => r.id === selectedId));
    const old = chapter?.resources.find(r => r.id === selectedId);
    const updated = chapters.find(c => c.id === chapter?.id);
    selectedId = updated?.resources.find(r => r.kind === old?.kind)?.id || updated?.resources[0]?.id || next.selectedId;
  }
  return { ...next, chapters, selectedId,
    ...(changed ? { progress: { ...next.progress, ...previous.progress },
      understanding: { ...next.understanding, ...previous.understanding } } : {}) };
}

export function generationLabel(chapter: Classroom['chapters'][number]): string {
  const labels: Record<string, string> = { queued: '等待生成', generating: '正在生成', ready: '可学习', failed: '生成失败', stopped: '已停止' };
  return labels[chapter.generationState || ''] || '';
}
