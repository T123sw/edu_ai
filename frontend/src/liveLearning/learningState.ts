import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest, ApiError } from '../stitch/api/client';
import { uid, type Classroom, type LearningResource } from '../selfLearning/model';
import { refKey, resourceRef, type ResourceRef, type Locator } from './readingContext';
export type Projection = {
  manifest_ref?: { manifest_id: string; version: number } | null;
  facts_revision: number;
  resources: { resource_ref: ResourceRef; completed: boolean; opened: boolean; reached_end: boolean; locator: Locator | null }[];
  resource_revisions: { resource_ref: ResourceRef; revision: number }[];
  self_assessments: Record<string, 'understood' | 'needs_review' | 'unset'>;
  self_assessment_revisions: Record<string, number>;
  topics: { topic_id: string; progress: string; judgment: string; total_core: number | null; completed_core: number }[];
  next_actions: Record<string, { kind: string; resource_ref?: ResourceRef; reason: string }[]>;
};
export type FactEvent = { schema_version: 1; event_id: string; type: string; manifest_ref: { manifest_id: string; version: number } | null; resource_ref: ResourceRef | null; expected_revision: number | null; occurred_at: string; payload: Record<string, unknown> };
export type PendingFact = { topic: string; event: FactEvent; blocked?: boolean };
export function coalesceReading(queue: PendingFact[], incoming: PendingFact, inFlight: string): PendingFact[] {
  if (incoming.event.type !== 'reading_position_set') return [...queue, incoming];
  return [...queue.filter(p => p.event.type !== 'reading_position_set' || p.event.event_id === inFlight || p.blocked ||
    p.event.payload.stream_id !== incoming.event.payload.stream_id || !p.event.resource_ref || !incoming.event.resource_ref ||
    refKey(p.event.resource_ref) !== refKey(incoming.event.resource_ref)), incoming];
}
export function readPending(storage: Pick<Storage, 'length' | 'key' | 'getItem'>, prefix: string): PendingFact[] {
  const result: PendingFact[] = [];
  for (let i = 0; i < storage.length; i++) {
    const key = storage.key(i);
    if (!key?.startsWith(prefix + ':')) continue;
    try { const item = JSON.parse(storage.getItem(key) || 'null'); if (item?.event?.event_id && typeof item.topic === 'string') result.push(item); } catch { /* Ignore unrelated or damaged local entries. */ }
  }
  return result.sort((a, b) => a.event.occurred_at.localeCompare(b.event.occurred_at));
}
export function applyProjection(room: Classroom, projection?: Projection): Classroom {
  if (!projection) return room;
  const progress = { ...room.progress };
  for (const resource of room.chapters.flatMap(c => c.resources)) {
    const ref = resourceRef(resource);
    const state = ref && projection.resources.find(s => refKey(s.resource_ref) === refKey(ref));
    const locator = state?.locator;
    progress[resource.id] = { note: progress[resource.id]?.note || '', completed: state?.completed || false,
      position: locator?.kind === 'document' ? locator.scroll_top : 0, locator: locator || undefined };
  }
  return { ...room, progress, learningProjection: projection,
    understanding: Object.fromEntries(Object.entries(projection.self_assessments).filter(([, v]) => v !== 'unset').map(([k, v]) => [k, v === 'needs_review' ? 'review' : 'understood'])) };
}
export function newerProjection(current: Projection | undefined, incoming: Projection): Projection {
  return !current || incoming.facts_revision >= current.facts_revision ? incoming : current;
}
export function useLearningProgress(input: Classroom) {
  const owner = input.progressOwner || '';
  const enabled = !!input.progressPersistence;
  const key = JSON.stringify(['learning-facts-v1', owner, input.id]);
  const base = `/api/self-learning/courses/${encodeURIComponent(input.id)}`;
  const [projection, setProjection] = useState(input.learningProjection);
  const latest = useRef(projection);
  const [pending, setPending] = useState<PendingFact[]>(() => {
    try { return readPending(localStorage, key); } catch { return []; }
  });
  const queue = useRef(pending);
  const [error, setError] = useState(() => pending.some(p => p.blocked) ? '上次操作存在冲突，请刷新后重新选择' : '');
  const running = useRef(false);
  const inFlight = useRef('');
  const active = useRef(true);
  const updateProjection = useCallback((value: Projection) => {
    latest.current = newerProjection(latest.current, value);
    if (active.current) setProjection(latest.current);
  }, []);
  const persist = useCallback(() => {
    // One key per event avoids overwriting another tab's queue. Replays are server-idempotent.
    for (const item of queue.current) localStorage.setItem(key + ':' + item.event.event_id, JSON.stringify(item));
    if (active.current) setPending([...queue.current]);
  }, [key]);
  const authorized = useCallback(() => {
    try { return JSON.parse(localStorage.getItem('edu-ai-auth') || '{}').user?.username === owner; } catch { return false; }
  }, [owner]);
  const refresh = useCallback(async () => {
    if (enabled && active.current && authorized()) updateProjection(await apiRequest<Projection>(`${base}/progress`));
  }, [enabled, authorized, updateProjection, base]);
  const flush = useCallback(async () => {
    if (running.current || !enabled || !active.current || !authorized()) return;
    running.current = true;
    try {
      while (queue.current.some(item => !item.blocked)) {
        const item = queue.current.find(item => !item.blocked)!;
        if (!active.current || !authorized()) break;
        try {
          inFlight.current = item.event.event_id;
          const receipt = await apiRequest<{ projection_delta: Projection }>(`${base}/topics/${encodeURIComponent(item.topic)}/events`, { method: 'POST', body: JSON.stringify(item.event) });
          updateProjection(receipt.projection_delta);
          localStorage.removeItem(key + ':' + item.event.event_id);
          queue.current = queue.current.filter(p => p.event.event_id !== item.event.event_id);
          persist();
          if (active.current && !queue.current.length) setError('');
        } catch (cause) {
          if (cause instanceof ApiError && [403, 404, 409, 422].includes(cause.status)) { item.blocked = true; persist(); }
          if (active.current) setError(cause instanceof Error ? cause.message : '保存失败');
          break;
        }
      }
    } finally { running.current = false; inFlight.current = ''; }
  }, [enabled, authorized, base, persist, updateProjection, key]);
  useEffect(() => {
    active.current = true;
    const sync = () => { void flush(); void refresh().catch(() => undefined); };
    sync();
    const timer = setInterval(sync, 5000);
    window.addEventListener('online', sync);
    return () => { active.current = false; clearInterval(timer); window.removeEventListener('online', sync); };
  }, [flush, refresh]);
  useEffect(() => { if (input.learningProjection) updateProjection(input.learningProjection); }, [input.learningProjection, updateProjection]);
  const enqueue = (topic: string, type: string, resource: LearningResource | undefined, payload: Record<string, unknown>) => {
    if (!enabled) return;
    const ref = resource && resourceRef(resource);
    const expected = type === 'resource_completion_set' ? latest.current?.resource_revisions.find(s => ref && refKey(s.resource_ref) === refKey(ref))?.revision || 0
      : type === 'self_assessment_set' ? latest.current?.self_assessment_revisions[topic] || 0 : null;
    // Explicit actions wait for their own receipt; no second mutation with the same base revision.
    if (expected !== null && queue.current.some(p => p.topic === topic && p.event.type === type && (ref ? p.event.resource_ref && refKey(p.event.resource_ref) === refKey(ref) : true))) return;
    const event: FactEvent = { schema_version: 1, event_id: uid(), type, manifest_ref: latest.current?.manifest_ref || null, resource_ref: ref || null,
      expected_revision: expected, occurred_at: new Date().toISOString(), payload };
    const next = coalesceReading(queue.current, { topic, event }, inFlight.current);
    const retained = new Set(next.map(p => p.event.event_id));
    for (const old of queue.current) {
      if (!retained.has(old.event.event_id)) localStorage.removeItem(key + ':' + old.event.event_id);
    }
    queue.current = next;
    try { persist(); } catch { setError('浏览器无法保存待同步记录，请保持此页打开'); }
    void flush();
  };
  return { room: applyProjection(input, projection), enqueue, pending, error,
    retry: () => { void flush(); void refresh().catch(() => undefined); },
    discardConflicts: () => { queue.current.filter(p => p.blocked).forEach(p => localStorage.removeItem(key + ':' + p.event.event_id)); queue.current = queue.current.filter(p => !p.blocked); persist(); setError(''); void refresh().catch(() => undefined); } };
}
