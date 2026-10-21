import { useCallback, useEffect, useRef, useState } from 'react';
import { serialPolling } from '../liveLearning/serialPolling';
import { pblApi, type PblItem } from './api';
export function usePblHome() {
  const [items, setItems] = useState<PblItem[]>([]);
  const [loading, setLoading] = useState(true), [loadFailed, setLoadFailed] = useState(false);
  const [error, setError] = useState(''), [submitting, setSubmitting] = useState(false);
  const pending = useRef({ topic: '', id: '', active: false });
  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const result = await pblApi.list(signal);
      if (!signal?.aborted) { setItems(result.items); setLoadFailed(false); }
    } catch { if (!signal?.aborted) setLoadFailed(true); }
    finally { if (!signal?.aborted) setLoading(false); }
  }, []);
  useEffect(() => serialPolling(signal => refresh(signal), 4000), [refresh]);
  const create = async (text: string) => {
    const topic = text.trim();
    if (!topic || pending.current.active) return;
    if (pending.current.topic !== topic) pending.current = { topic, id: crypto.randomUUID(), active: false };
    pending.current.active = true; setSubmitting(true); setError('');
    try {
      const result = await pblApi.create(pending.current.topic, pending.current.id);
      pending.current.topic = '';
      void refresh();
      return result.exerciseId;
    } catch (e) { setError(e instanceof Error ? e.message : '提交失败，请重试'); }
    finally { pending.current.active = false; setSubmitting(false); }
  };
  return { items, loading, loadFailed, refresh, error, submitting, create };
}
