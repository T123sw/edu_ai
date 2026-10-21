import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import { serialPolling } from '../liveLearning/serialPolling';

type Item = { id: string; topic: string; status: string };

export function usePracticeHome(active: boolean, initialTopic: string) {
  const [prompt, setPrompt] = useState('');
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [submitFailed, setSubmitFailed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const request = useRef({ topic: '', id: '', pending: false });
  useEffect(() => { if (initialTopic) setPrompt(initialTopic.slice(0, 1800)); }, [initialTopic]);
  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const result = await apiRequest<{ items: Item[] }>('/api/practice', { signal });
      if (!signal?.aborted) { setItems(result.items); setLoadFailed(false); }
    } catch { if (!signal?.aborted) setLoadFailed(true); }
    finally { if (!signal?.aborted) setLoading(false); }
  }, []);
  useEffect(() => {
    if (active) return serialPolling(signal => refresh(signal), 5000);
  }, [active, refresh]);
  const create = async (text: string) => {
    if (!text.trim() || request.current.pending) return;
    const topic = text.trim();
    if (request.current.topic !== topic) request.current = { topic, id: crypto.randomUUID(), pending: false };
    request.current.pending = true;
    setSubmitting(true); setSubmitFailed(false);
    try {
      const result = await apiRequest<{ id: string }>('/api/practice', { method: 'POST', body: JSON.stringify({ topic, request_id: request.current.id }) });
      request.current.topic = '';
      void refresh();
      return result.id;
    } catch { setSubmitFailed(true); }
    finally { request.current.pending = false; setSubmitting(false); }
  };
  return { prompt, setPrompt, items, loading, loadFailed, submitFailed, submitting, refresh, create };
}
