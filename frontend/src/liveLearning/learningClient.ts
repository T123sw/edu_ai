import { useCallback, useEffect, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import type { Message } from '../selfLearning/model';

export type SessionPage = { session_id: string; topic_id: string; items: Message[]; next_cursor: string | null };
type Cache = { page?: SessionPage; error?: string; loading?: boolean };

export function mergeSessionPage(previous: SessionPage | undefined, incoming: SessionPage): SessionPage {
  if (!previous || previous.session_id !== incoming.session_id) return incoming;
  const byId = new Map(previous.items.map(m => [m.id, m]));
  incoming.items.forEach(m => byId.set(m.id, m));
  const extendsBack = (incoming.items[0]?.position ?? Infinity) <= (previous.items[0]?.position ?? Infinity);
  return { ...incoming, items: [...byId.values()].sort((a, b) => (a.position ?? 0) - (b.position ?? 0)),
    next_cursor: extendsBack ? incoming.next_cursor : previous.next_cursor };
}

export function useTopicSession(courseId: string, topicId: string, enabled: boolean, owner: string) {
  const [cache, setCache] = useState<Record<string, Cache>>({});
  const key = JSON.stringify([owner, courseId, topicId]);
  const url = `/api/self-learning/courses/${encodeURIComponent(courseId)}/topics/${encodeURIComponent(topicId)}`;
  const load = useCallback(async (enter = false, before?: string, signal?: AbortSignal) => {
    setCache(c => ({ ...c, [key]: { ...c[key], loading: true, error: undefined } }));
    try {
      const page = await apiRequest<SessionPage>(`${url}/${enter ? 'enter' : 'session'}${before ? '?before=' + encodeURIComponent(before) : ''}`,
        { method: enter ? 'POST' : 'GET', signal });
      if (!signal?.aborted) setCache(c => ({ ...c, [key]: { page: mergeSessionPage(c[key]?.page, page), loading: false } }));
    } catch (cause) {
      if (!signal?.aborted) setCache(c => ({ ...c, [key]: { ...c[key], loading: false,
        error: cause instanceof Error ? cause.message : '会话读取失败，请重试' } }));
    }
  }, [key, url]);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    void load(true, undefined, controller.signal);
    const timer = setInterval(() => void load(false, undefined, controller.signal), 5000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [enabled, load]);
  const state = cache[key];
  return { messages: state?.page?.items ?? [], sessionId: state?.page?.session_id,
    loading: state?.loading, error: state?.error, hasOlder: !!state?.page?.next_cursor,
    refresh: () => load(), retry: () => load(true),
    loadOlder: () => state?.page?.next_cursor ? load(false, state.page.next_cursor) : Promise.resolve() };
}
