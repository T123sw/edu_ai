import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { apiRequest, ApiError } from '../../stitch/api/client';
import { currentAttempt, reportedState, EXPLORE, type Command, type Manifest, type Session } from './model';
import { readDraft, writeDraft, type Draft, type Saved } from './cache';

function tabId() { const key = 'edu-practice-guidance-tab'; let id = sessionStorage.getItem(key); if (!id) { id = crypto.randomUUID(); sessionStorage.setItem(key, id); } return id; }

export function useGuidance(id: string | undefined, manifest: Manifest | undefined, frame: RefObject<HTMLIFrameElement>) {
  const tab = useMemo(tabId, []);
  const key = id && manifest ? `${id}:${manifest.revision}:${tab}` : '';
  const channel = useMemo(() => `${key}:${crypto.randomUUID()}`, [key]);
  const [session, setSession] = useState<Session>();
  const [status, setStatus] = useState('');
  const [problem, setProblem] = useState('');
  const [pending, setPending] = useState(false);
  const draft = useRef<Draft>(); const ready = useRef(false); const blocked = useRef(false);
  const saving = useRef<Promise<void>>(); const timer = useRef<ReturnType<typeof setTimeout>>();
  const requests = useRef(new Map<string, { resolve: () => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> }>());
  const saveChain = useRef(Promise.resolve());
  const persist = useCallback(() => {
    if (!key || !draft.current) return;
    const copy = structuredClone(draft.current);
    saveChain.current = saveChain.current.catch(() => {}).then(() => writeDraft(key, copy));
    void saveChain.current.catch(() => setProblem('浏览器无法保存离线副本，请保持网络连接。'));
  }, [key]);
  const initialize = useCallback(() => {
    if (ready.current && draft.current && manifest) frame.current?.contentWindow?.postMessage({ type: 'edu-guidance-init', revision: manifest.revision, channel, state: draft.current.state }, '*');
  }, [frame, manifest, channel]);
  const flush = useCallback((): Promise<void> => {
    if (saving.current) return saving.current;
    if (!id || !manifest || !draft.current || blocked.current) return Promise.reject(new Error('实验记录尚未就绪或存在版本冲突'));
    saving.current = (async () => {
      while (draft.current?.pending.length) {
        const current = draft.current;
        const batch = current.inflight || { batch_id: crypto.randomUUID(), revision: manifest.revision, expected_seq: current.saved_seq, commands: current.pending.slice(0, 60) };
        current.inflight = batch; persist(); await saveChain.current.catch(() => {}); setStatus('正在保存');
        try {
          const result = await apiRequest<Saved>(`/api/practice/${id}/sessions/${current.session_id}/events`, { method: 'POST', body: JSON.stringify(batch) });
          if (draft.current !== current) return;
          const ids = new Set(batch.commands.map(c => c.id));
          current.pending = current.pending.filter(c => !ids.has(c.id)); current.saved_seq = result.saved_seq; delete current.inflight;
          // New local operations may already be ahead of the saved checkpoint.
          if (!current.pending.length && current.state.seq === result.saved_seq) { current.state = result.state; setSession(result.state); }
          persist(); setProblem('');
        } catch (e) {
          const text = e instanceof Error ? e.message : '保存失败';
          if ((e instanceof ApiError && e.status === 409) || /冲突|其他页面|版本|批次|重复/.test(text)) { blocked.current = true; setStatus('保存冲突'); }
          else setStatus('未同步');
          setProblem(text); throw e;
        }
      }
      setStatus('已保存');
    })().finally(() => { saving.current = undefined; });
    return saving.current;
  }, [id, manifest, persist]);
  const schedule = useCallback(() => { clearTimeout(timer.current); timer.current = setTimeout(() => { void flush().catch(() => {}); }, 350); }, [flush]);
  useEffect(() => {
    if (!key || !manifest || !id) return;
    let alive = true;
    draft.current = undefined; blocked.current = false; setStatus('正在恢复'); setSession(undefined); setProblem('');
    void (async () => {
      let cached: Draft | undefined;
      try { cached = await readDraft(key); } catch { /* Online state can still be restored. */ }
      try {
        const saved = await apiRequest<Saved>(`/api/practice/${id}/sessions`, { method: 'POST', body: '{}' });
        if (!alive) return;
        if (cached?.pending.length && cached.revision === saved.revision) {
          draft.current = cached;
          if (cached.saved_seq !== saved.saved_seq && !cached.inflight) { blocked.current = true; setStatus('保存冲突'); setProblem('其他页面已更新实验；本地操作保留在浏览器中。'); }
        } else draft.current = { ...saved, pending: [] };
      } catch (e) {
        if (!alive) return;
        if (!cached || cached.revision !== manifest.revision) { setStatus('恢复失败'); setProblem(e instanceof Error ? e.message : '无法读取实验进度'); return; }
        draft.current = cached; setStatus('未同步');
      }
      if (!alive || !draft.current) return;
      setSession(draft.current.state); persist(); initialize();
      if (!blocked.current) { setStatus(draft.current.pending.length ? '未同步' : '已保存'); if (draft.current.pending.length) schedule(); }
    })();
    return () => { alive = false; clearTimeout(timer.current); };
  }, [key, id, manifest, persist, initialize, schedule]);
  useEffect(() => {
    if (!manifest) return;
    const receive = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow || event.data?.revision !== manifest.revision) return;
      const data = event.data;
      if (data.type === 'edu-guidance-ready') { ready.current = true; initialize(); return; }
      if (data.channel !== channel) return;
      if (data.type === 'edu-guidance-error') { setProblem(`实验运行异常：${data.message}`); setPending(false); }
      if (data.type === 'edu-guidance-event' && draft.current && data.state?.seq === draft.current.state.seq + 1 && data.command?.id) {
        draft.current.state = data.state; draft.current.pending.push(data.command); setSession(data.state); setStatus(blocked.current ? '保存冲突' : '未同步'); persist(); schedule();
      }
      if (data.type === 'edu-guidance-ack') { const request = requests.current.get(data.request); if (request) { clearTimeout(request.timer); request.resolve(); requests.current.delete(data.request); setPending(false); } }
    };
    window.addEventListener('message', receive);
    const online = () => { void flush().catch(() => {}); };
    window.addEventListener('online', online);
    return () => { window.removeEventListener('message', receive); window.removeEventListener('online', online); };
  }, [manifest, frame, channel, initialize, persist, schedule, flush]);
  const send = useCallback((command: Command) => new Promise<void>((resolve, reject) => {
    if (!draft.current || !ready.current || !manifest) { reject(new Error('实验尚未就绪')); return; }
    setPending(true);
    const requestTimer = setTimeout(() => { requests.current.delete(command.id); setPending(false); setProblem('实验切换未收到回执，请重试。'); reject(new Error('实验响应超时')); }, 4000);
    requests.current.set(command.id, { resolve, reject, timer: requestTimer });
    frame.current?.contentWindow?.postMessage({ type: 'edu-guidance-command', channel, revision: manifest.revision, command }, '*');
  }), [channel, frame, manifest]);
  const enter = useCallback((step: string) => { void send({ id: crypto.randomUUID(), type: 'enter', step }).catch(() => {}); }, [send]);
  const context = useCallback(async () => {
    await send({ id: crypto.randomUUID(), type: 'action', action: 'pause' }); await flush();
    const current = draft.current!;
    if (current.pending.length) throw Error('操作尚未保存，请重试');
    return { session_id: current.session_id, step_id: current.state.active, attempt_id: currentAttempt(current.state).id, state_revision: current.saved_seq, step: current.state.active === EXPLORE ? manifest!.steps.length : manifest!.steps.findIndex(s => s.id === current.state.active), state: reportedState(manifest!, current.state) };
  }, [send, flush, manifest]);
  const restore = useCallback(async () => {
    if (!id || !manifest || !draft.current) return;
    try {
      await writeDraft(`${key}:conflict:${Date.now()}`, draft.current);
      const saved = await apiRequest<Saved>(`/api/practice/${id}/sessions/${draft.current.session_id}`);
      draft.current = { ...saved, pending: [] }; blocked.current = false; setSession(saved.state); setStatus('已保存'); setProblem(''); persist(); initialize();
    } catch (e) { setProblem(e instanceof Error ? e.message : '读取失败'); }
  }, [id, manifest, key, persist, initialize]);
  const exportDraft = useCallback(() => {
    if (!draft.current) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(draft.current, null, 2)], { type: 'application/json' })); const a = document.createElement('a'); a.href = url; a.download = '实验操作记录.json'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, []);
  const index = session && manifest ? session.active === EXPLORE ? manifest.steps.length : manifest.steps.findIndex(s => s.id === session.active) : 0;
  return { sessionId: draft.current?.session_id, session, status, problem, pending, index, enter, context, restore, exportDraft, flush };
}
