import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import { uid } from '../selfLearning/model';
import type { ResourceRef, Locator } from './readingContext';
import { serialPolling } from './serialPolling';
export type ReadingSnapshot = { resource_ref: ResourceRef; locator?: Locator; selected_text: string };
export type AnswerTurn = { turn_id: string; topic_id: string; request_id: string; status: 'accepted' | 'running' | 'succeeded' | 'failed' | 'canceled'; stage: string; error_code?: string };
export function useAnswerTurns(course: string, topic: string, enabled: boolean, owner: string) {
  const key = JSON.stringify([owner, course, topic]);
  const path = `/api/self-learning/courses/${encodeURIComponent(course)}/topics/${encodeURIComponent(topic)}/agent-turns`;
  const [cache, setCache] = useState<Record<string, AnswerTurn[]>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const inflight = useRef(new Map<string, { fingerprint: string; body: string }>());
  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      const turns = await apiRequest<AnswerTurn[]>(path, { signal });
      if (!signal?.aborted) setCache(s => ({ ...s, [key]: turns }));
    } catch (e) { if (!signal?.aborted) setErrors(s => ({ ...s, [key]: e instanceof Error ? e.message : '轮次读取失败' })); }
  }, [path, key]);
  const hasActive = (cache[key] || []).some(t => t.status === 'accepted' || t.status === 'running');
  useEffect(() => {
    if (!enabled) return;
    return serialPolling(load, hasActive ? 1000 : 5000);
  }, [enabled, load, hasActive]);
  const submit = async (question: string, reading: ReadingSnapshot) => {
    const fingerprint = JSON.stringify([question, reading]);
    let pending = inflight.current.get(key);
    if (!pending || pending.fingerprint !== fingerprint) {
      pending = { fingerprint, body: JSON.stringify({ request_id: uid(), question, reading_context: reading }) };
      inflight.current.set(key, pending);
    }
    const turn = await apiRequest<AnswerTurn>(path, { method: 'POST', body: pending.body });
    inflight.current.delete(key);
    setCache(s => ({ ...s, [key]: [turn, ...(s[key] || []).filter(t => t.turn_id !== turn.turn_id)] }));
    setErrors(s => ({ ...s, [key]: '' }));
  };
  const control = async (id: string, operation: 'retry' | 'cancel') => {
    try { await apiRequest(`/api/self-learning/agent-turns/${encodeURIComponent(id)}/${operation}`, { method: 'POST' }); await load(); }
    catch (e) { setErrors(s => ({ ...s, [key]: e instanceof Error ? e.message : '操作失败' })); }
  };
  const turns = cache[key] || [];
  return { turns, error: errors[key], submit, control, active: turns.find(t => t.status === 'accepted' || t.status === 'running') };
}
