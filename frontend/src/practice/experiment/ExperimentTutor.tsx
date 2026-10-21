import { useCallback, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { apiEventStream, apiRequest } from '../../stitch/api/client';
import { copy, uid, type Event, type View } from './model';

type Turn = {
  request_id: string; question: string; answer: string; reply_to: string | null;
  revision: string; run_id: string; state_revision: number; phase: string;
  focus_label: string; status: 'pending' | 'complete' | 'failed'; error: string;
};
type History = { items: Turn[]; next_cursor: string | null };
type Question = { request_id: string; question: string; view: View; reply_to: string | null; focus_event_id: string | null };
type StreamEvent = { type: string; turn?: Turn; text?: string; message?: string };
const problem = (e: unknown) => e instanceof Error ? e.message : '回答未完成，请重试';

export function ExperimentTutor({ base, storageKey, view, focus, clearFocus }: {
  base: string; storageKey: string; view: View | undefined; focus: Event | undefined; clearFocus: () => void;
}) {
  const [turns, setTurns] = useState<Turn[]>([]), [cursor, setCursor] = useState<string | null>(null);
  const [question, setQuestion] = useState(() => { try { return localStorage.getItem(storageKey + ':question') || ''; } catch { return ''; } });
  const [replyTo, setReplyTo] = useState<Turn>(), [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [status, setStatus] = useState(''), [loaded, setLoaded] = useState(false);
  const [outbox, setOutbox] = useState<Question | undefined>(() => {
    try { return JSON.parse(localStorage.getItem(storageKey + ':outbox') || 'null') as Question | undefined; } catch { return undefined; }
  });
  const composer = useRef<HTMLTextAreaElement>(null);
  const panel = useRef<HTMLElement>(null), messages = useRef<HTMLDivElement>(null), followLatest = useRef(true);
  useEffect(() => {
    const element = panel.current;
    if (!element) return;
    const size = () => {
      const bounds = element.getBoundingClientRect();
      if (!bounds.width) return;
      const viewport = window.visualViewport;
      const bottom = viewport ? viewport.offsetTop + viewport.height : window.innerHeight;
      const height = `${Math.max(0, bottom - bounds.top)}px`;
      if (element.style.getPropertyValue('--tutor-available-height') !== height) element.style.setProperty('--tutor-available-height', height);
    };
    const observer = new ResizeObserver(size);
    observer.observe(element);
    window.addEventListener('resize', size);
    window.addEventListener('scroll', size, { passive: true });
    window.visualViewport?.addEventListener('resize', size);
    window.visualViewport?.addEventListener('scroll', size);
    size();
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', size);
      window.removeEventListener('scroll', size);
      window.visualViewport?.removeEventListener('resize', size);
      window.visualViewport?.removeEventListener('scroll', size);
    };
  }, []);
  const latest = turns.at(-1);
  useEffect(() => {
    if (followLatest.current && messages.current) messages.current.scrollTop = messages.current.scrollHeight;
  }, [latest?.request_id, latest?.answer, latest?.status]);
  const controller = useRef<AbortController>(), running = useRef(false), mounted = useRef(true), restoredReply = useRef(false);
  const merge = useCallback((items: Turn[]) => setTurns(previous => {
    const replacements = new Map(items.map(turn => [turn.request_id, turn]));
    return [...previous.map(turn => replacements.get(turn.request_id) || turn), ...items.filter(turn => !previous.some(old => old.request_id === turn.request_id))];
  }), []);
  const refresh = useCallback(async () => {
    const history = await apiRequest<History>(`${base}/tutor`);
    if (!mounted.current) return;
    merge(history.items); if (!restoredReply.current) setCursor(history.next_cursor); setLoaded(true);
    // A reload can happen after server acceptance but before its SSE reaches us.
    try {
      const pending = JSON.parse(localStorage.getItem(storageKey + ':outbox') || 'null') as Question | null;
      if (pending && history.items.some(turn => turn.request_id === pending.request_id)) {
        localStorage.removeItem(storageKey + ':outbox'); setOutbox(undefined);
        setQuestion(previous => previous === pending.question ? '' : previous);
      }
    } catch { /* Keep the retryable outbox if storage cannot be read. */ }
    if (!restoredReply.current) {
      restoredReply.current = true;
      try {
        const selected = localStorage.getItem(storageKey + ':reply');
        const parent = history.items.find(turn => turn.request_id === selected) || (selected ? await apiRequest<Turn>(`${base}/tutor/${encodeURIComponent(selected)}`) : undefined);
        if (parent?.status === 'complete' && mounted.current) setReplyTo(parent);
      } catch { if (mounted.current) setError('上次回应的消息暂时无法读取，可从历史对话重新选择。'); }
    }
  }, [base, merge, storageKey]);
  useEffect(() => {
    mounted.current = true;
    void refresh().catch(e => { if (mounted.current) setError(problem(e)); });
    return () => { mounted.current = false; controller.current?.abort(); };
  }, [refresh]);
  useEffect(() => { try { localStorage.setItem(storageKey + ':question', question); } catch { /* Draft is still in memory. */ } }, [question, storageKey]);
  useEffect(() => {
    if (busy || !turns.some(turn => turn.status === 'pending')) return;
    const timer = setInterval(() => void refresh().catch(() => {}), 4000);
    return () => clearInterval(timer);
  }, [busy, turns, refresh]);
  const selectReply = (turn: Turn | undefined) => {
    setReplyTo(turn);
    try { if (turn) localStorage.setItem(storageKey + ':reply', turn.request_id); else localStorage.removeItem(storageKey + ':reply'); } catch { /* Keep selection in memory. */ }
  };
  const beginReply = (turn: Turn | undefined) => {
    clearFocus(); selectReply(turn);
    // Keep focus in the click gesture so mobile browsers can open the keyboard.
    // Run even when this message is already selected, without replacing the draft.
    composer.current?.focus({ preventScroll: true });
    composer.current?.scrollIntoView({ block: 'center', behavior: 'instant' });
  };
  const suggestQuestion = (text: string) => {
    selectReply(undefined);
    setQuestion(text);
    composer.current?.focus({ preventScroll: true });
  };
  const saveOutbox = (value: Question | undefined) => {
    setOutbox(value);
    try { if (value) localStorage.setItem(storageKey + ':outbox', JSON.stringify(value)); else localStorage.removeItem(storageKey + ':outbox'); } catch { /* Server acceptance still persists the question. */ }
  };
  const transmit = async (path: string, payload?: Question) => {
    if (running.current) return;
    running.current = true; setBusy(true); setError(''); setStatus('正在结合操作记录思考…');
    controller.current = new AbortController();
    let active = payload?.request_id, terminal = false, accepted = false;
    try {
      await apiEventStream(path, { method: 'POST', body: payload ? JSON.stringify(payload) : undefined, signal: controller.current.signal }, raw => {
        if (!mounted.current) return;
        const event = raw as StreamEvent;
        if (event.turn) { active = event.turn.request_id; merge([event.turn]); }
        if (event.type === 'accepted') {
          accepted = true;
          if (payload) { saveOutbox(undefined); setQuestion(''); selectReply(undefined); clearFocus(); }
        }
        if (event.type === 'delta' && active) {
          setStatus('正在回答…');
          setTurns(previous => previous.map(turn => turn.request_id === active ? { ...turn, answer: turn.answer + (event.text || '') } : turn));
        }
        if (event.type === 'status') setStatus(event.message || '正在查看操作记录…');
        if (event.type === 'done' || event.type === 'error') {
          terminal = true;
          if (event.type === 'done' && event.turn?.status === 'complete') selectReply(event.turn);
          if (event.type === 'error') setError(event.turn?.error || event.message || '回答未完成，请重试');
        }
      });
      if (!terminal) throw Error('回答连接已中断，请重试原问题');
    } catch (e) {
      if (mounted.current) {
        setError(problem(e));
        if (accepted && active) setTurns(previous => previous.map(turn => turn.request_id === active ? { ...turn, status: 'failed', error: '回答连接已中断，可以重试原问题。' } : turn));
        void refresh().catch(() => {});
      }
    } finally {
      running.current = false;
      if (mounted.current) { setBusy(false); setStatus(''); }
    }
  };
  const send = () => {
    if (!view || !question.trim() || running.current) return;
    const payload: Question = { request_id: uid(), question: question.trim(), view: copy(view), reply_to: focus ? null : replyTo?.request_id || null, focus_event_id: focus?.id || null };
    followLatest.current = true;
    saveOutbox(payload); void transmit(`${base}/tutor`, payload);
  };
  const older = async () => {
    try {
      const history = await apiRequest<History>(`${base}/tutor?before=${encodeURIComponent(cursor!)}`);
      setTurns(previous => [...history.items.filter(turn => !previous.some(old => old.request_id === turn.request_id)), ...previous]);
      setCursor(history.next_cursor);
    } catch (e) { setError(problem(e)); }
  };
  const related = focus ? `关于操作：${focus.command?.action || focus.type}` : replyTo ? `回应：${replyTo.answer}` : '结合你发送时的实验状态回答';
  return <section ref={panel} className="experiment-tutor" aria-label="实验学习助手">
    <div className="experiment-tutor-heading"><h3>学习助手</h3><span>结合你的操作解答</span></div>
    <div ref={messages} className="experiment-tutor-scroll" onScroll={event => { const el = event.currentTarget; followLatest.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48; }}>
    {!loaded && <button onClick={() => void refresh().catch(e => setError(problem(e)))}>读取对话</button>}
    {cursor && <button className="experiment-text-button" onClick={() => void older()}>查看更早对话</button>}
    <div className="experiment-tutor-messages" aria-label="教学对话">
      {turns.map(turn => <article key={turn.request_id} className="experiment-tutor-turn">
        <div className="experiment-tutor-question"><strong>你</strong><p>{turn.question}</p></div>
        <small className="experiment-tutor-source">{turn.reply_to ? '回应之前的教学对话' : `关于：${turn.focus_label}`}{view && turn.run_id !== view.run_id ? ' · 上一轮实验' : ''}</small>
        <div className="experiment-tutor-answer"><strong>学习助手</strong>{turn.answer ? <ReactMarkdown skipHtml components={{ img: ({ alt }) => <span>{alt}</span> }}>{turn.answer}</ReactMarkdown> : turn.status === 'pending' ? <p>正在结合操作记录思考…</p> : null}</div>
        {turn.status === 'failed' && <div><p className="experiment-error" role="alert">{turn.error}</p><button disabled={busy} onClick={() => void transmit(`${base}/tutor/${turn.request_id}/retry`)}>重试回答</button></div>}
        {turn.status === 'complete' && turn.revision === view?.revision && <button type="button" className="experiment-text-button" aria-pressed={!focus && replyTo?.request_id === turn.request_id} disabled={busy} onClick={() => beginReply(turn)}>回答或继续问</button>}
      </article>)}
    </div>
    </div>
    <div className="experiment-tutor-composer">
    <form onSubmit={event => { event.preventDefault(); send(); }}>
      <div className="experiment-tutor-prompts" aria-label="快捷提问">
        {['这一步为什么？', '接下来观察什么？'].map(text => <button key={text} type="button" disabled={busy || !!outbox} onClick={() => suggestQuestion(text)}>{text}</button>)}
      </div>
      <textarea ref={composer} aria-label="实验问题或回答" value={question} onChange={event => setQuestion(event.target.value)} placeholder={replyTo && !focus ? '说说你的理解，或继续追问…' : '输入你的问题或想法…'} maxLength={2000} disabled={busy} />
      <p className="experiment-tutor-related" title={related}>{related}</p>
      {(focus || replyTo) && <button type="button" className="experiment-text-button" disabled={busy} onClick={() => beginReply(undefined)}>改问当前操作</button>}
      <div className="experiment-tutor-send"><button className="experiment-primary" disabled={busy || !view || !question.trim() || !!outbox}>发送</button>{busy && <span role="status">{status}</span>}</div>
    </form>
    {outbox && !busy && <div className="experiment-tutor-outbox"><p>有一条消息尚未确认送达，已保留当时的操作状态。</p><button onClick={() => void transmit(`${base}/tutor`, outbox)}>重试发送</button><button onClick={() => saveOutbox(undefined)}>取消待发送消息</button></div>}
    {error && <p role="alert" className="experiment-error">{error}</p>}
    </div>
  </section>;
}
