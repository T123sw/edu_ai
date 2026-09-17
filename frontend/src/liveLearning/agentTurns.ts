import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import { uid } from '../selfLearning/model';
import type { ResourceRef, Locator } from './readingContext';
export type ReadingSnapshot = { resource_ref: ResourceRef; locator?: Locator; selected_text: string };
export type AnswerTurn = { turn_id: string; topic_id: string; request_id: string; status: 'accepted' | 'running' | 'succeeded' | 'failed' | 'canceled'; stage: string; error_code?: string };
export function answerErrorMessage(code?: string): string {
  if (code === 'DEADLINE_EXCEEDED') return '本次回答超时，可以重试或继续阅读。';
  if (code === 'MODEL_UNAVAILABLE' || code === 'MODEL_CONNECTION_INTERRUPTED') return '模型暂时不可用，可以重试或继续阅读。';
  if (code === 'SOURCE_CHANGED' || code === 'CONTEXT_UNAVAILABLE') return '引用资料已变化或不可读取，请重新打开资料后提问。';
  if (code === 'CONTEXT_BUDGET_EXCEEDED') return '引用内容过长，请缩小选区后重新提问。';
  return '本次答疑未完成，可以重试或继续阅读。';
}
export function useAnswerTurns(course: string, topic: string, enabled: boolean, owner: string) {
  const key = JSON.stringify([owner, course, topic]);
  const path = `/api/self-learning/courses/${encodeURIComponent(course)}/topics/${encodeURIComponent(topic)}/agent-turns`;
  const [cache, setCache] = useState<Record<string, AnswerTurn[]>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const generations = useRef(new Map<string, number>());
  const authorized = useCallback(() => {
    try { return JSON.parse(localStorage.getItem('edu-ai-auth') || '{}').user?.username === owner; } catch { return false; }
  }, [owner]);
  const inflight = useRef(new Map<string, { fingerprint: string; body: string }>());
  const load = useCallback(async () => {
    if (!authorized()) return;
    const generation = (generations.current.get(key) || 0) + 1;
    generations.current.set(key, generation);
    try {
      const turns = await apiRequest<AnswerTurn[]>(path);
      if (generations.current.get(key) !== generation) return;
      setCache(s => ({ ...s, [key]: turns }));
      setErrors(s => ({ ...s, [key]: '' }));
    } catch (e) { setErrors(s => ({ ...s, [key]: e instanceof Error ? e.message : '轮次读取失败' })); }
  }, [path, key, authorized]);
  useEffect(() => {
    if (!enabled) return;
    void load();
    const timer = setInterval(() => void load(), 1000);
    return () => clearInterval(timer);
  }, [enabled, load]);
  const submit = async (question: string, reading: ReadingSnapshot) => {
    if (!authorized()) throw new Error('账号已切换，请刷新页面');
    const fingerprint = JSON.stringify([question, reading]);
    let pending = inflight.current.get(key);
    if (!pending || pending.fingerprint !== fingerprint) {
      pending = { fingerprint, body: JSON.stringify({ request_id: uid(), question, reading_context: reading }) };
      inflight.current.set(key, pending);
    }
    const turn = await apiRequest<AnswerTurn>(path, { method: 'POST', body: pending.body });
    generations.current.set(key, (generations.current.get(key) || 0) + 1);
    inflight.current.delete(key);
    setCache(s => ({ ...s, [key]: [turn, ...(s[key] || []).filter(t => t.turn_id !== turn.turn_id)] }));
    setErrors(s => ({ ...s, [key]: '' }));
  };
  const control = async (id: string, operation: 'retry' | 'cancel') => {
    if (!authorized()) return;
    try { await apiRequest(`/api/self-learning/agent-turns/${encodeURIComponent(id)}/${operation}`, { method: 'POST' }); await load(); }
    catch (e) { setErrors(s => ({ ...s, [key]: e instanceof Error ? e.message : '操作失败' })); }
  };
  const turns = cache[key] || [];
  return { turns, error: errors[key], submit, control, active: turns.find(t => t.status === 'accepted' || t.status === 'running') };
}
