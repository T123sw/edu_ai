import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { pblApi } from './api';
import type { TutorQuestion, TutorTurn } from './tutorTypes';

interface Props {
  exerciseId: string; artifactVersion: number; taskId: string;
  files: Record<string, string>; codeHash: string; embedded?: boolean; suggestion?: {id:string;text:string};
}

// The parent keys this component by step. A late response can never enter another step.
export function PblTutor({exerciseId, artifactVersion, taskId, files, codeHash, embedded=false, suggestion}: Props) {
  const [open, setOpen] = useState(embedded);
  const [turns, setTurns] = useState<TutorTurn[]>([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [cursor, setCursor] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const pending = useRef<TutorQuestion>();
  const alive = useRef(true);
  const sending = useRef(false);
  const draft = useRef(question); draft.current = question;
  useEffect(() => {alive.current = true; return () => {alive.current = false;};}, []);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setLoading(true); setError('');
    void pblApi.tutorHistory(exerciseId, artifactVersion, taskId, undefined, controller.signal).then(history => {
      if (controller.signal.aborted) return;
      setTurns(items => [...new Map([...history.items, ...items].map(turn => [turn.requestId, turn])).values()]
        .sort((a, b) => a.createdAt - b.createdAt || a.requestId.localeCompare(b.requestId)));
      setCursor(history.nextCursor); setLoaded(true);
    }).catch(() => {if (!controller.signal.aborted) setError('辅导记录读取失败，请重试');})
      .finally(() => {if (!controller.signal.aborted) setLoading(false);});
    return () => {controller.abort();};
  }, [open, exerciseId, artifactVersion, taskId, reload]);

  const ask = async (text: string) => {
    if (sending.current || !text.trim() || !loaded || loading) return;
    const request: TutorQuestion = {requestId: crypto.randomUUID(), artifactVersion, taskId, files: {...files}, question: text.trim()};
    const previous = pending.current;
    if (previous && previous.question === request.question && Object.keys(files).every(path => previous.files[path] === files[path])) {
      request.requestId = previous.requestId;
    }
    pending.current = request; sending.current = true; setBusy(true); setError('');
    const originalDraft = text;
    try {
      const turn = await pblApi.askTutor(exerciseId, request);
      if (!alive.current) return;
      setTurns(items => [...items.filter(item => item.requestId !== turn.requestId), turn]);
      if (draft.current === originalDraft) setQuestion('');
      pending.current = undefined;
    } catch (e) {
      if (alive.current) setError(e instanceof Error ? e.message : '辅导暂时不可用，请重试');
    } finally {
      sending.current = false;
      if (alive.current) setBusy(false);
    }
  };
  useEffect(()=>{if(suggestion){setQuestion(suggestion.text);setOpen(true);}},[suggestion]);
  const earlier = async () => {
    if (!cursor || loading || busy) return;
    setLoading(true); setError('');
    try {
      const history = await pblApi.tutorHistory(exerciseId, artifactVersion, taskId, cursor);
      if (alive.current) {setTurns(items => [...history.items, ...items]); setCursor(history.nextCursor);}
    } catch {if (alive.current) setError('更早的辅导记录读取失败，请重试');}
    finally {if (alive.current) setLoading(false);}
  };
  return <section className="pbl-tutor" aria-label="编程辅导">
    {!embedded && <button className="pbl-tutor-toggle" aria-expanded={open} onClick={() => setOpen(value => !value)}>
      <strong>编程辅导</strong><span>{open ? '收起' : '遇到困难，问一问'}</span>
    </button>}
    {open && <div className="pbl-tutor-body">
      <p className="pbl-note">结合本步任务、当前代码和检查结果，帮你找到下一步。</p>
      {loading && <p role="status">正在读取辅导记录…</p>}
      {cursor && <button disabled={loading || busy} onClick={() => void earlier()}>查看更早的问答</button>}
      <div className="pbl-tutor-history" aria-live="polite" aria-relevant="additions">
        {turns.map(turn => <article key={turn.requestId} className="pbl-tutor-turn">
          <p className="pbl-tutor-question">{turn.question}</p>
          <ReactMarkdown skipHtml>{turn.answer}</ReactMarkdown>
          <small>{turn.codeHash !== codeHash ? '代码已修改，这条建议基于提问时的代码。' : turn.runId ? '结合提问时的代码与检查记录' : '提问时没有匹配代码的检查记录，请实际运行验证。'}</small>
        </article>)}
      </div>
      {error && <p className="pbl-alert" role="alert">{error}{!loaded && <button onClick={() => setReload(value => value + 1)}>重试读取</button>}</p>}
      {busy && <p role="status">正在分析提问时的代码…</p>}
      <div className="pbl-tutor-shortcuts">
        {['给我一个下一步提示', '帮我分析检查失败的原因'].map(text => <button key={text} disabled={busy || loading || !loaded} onClick={() => {setQuestion(text); void ask(text);}}>{text}</button>)}
      </div>
      <form onSubmit={event => {event.preventDefault(); void ask(question);}}>
        <textarea aria-label="向编程辅导提问" placeholder="这段代码为什么没有达到预期？" maxLength={4000} value={question} onChange={event => setQuestion(event.target.value)}/>
        <button type="submit" disabled={busy || loading || !loaded || !question.trim()}>{busy ? '正在回答…' : '发送问题'}</button>
      </form>
    </div>}
  </section>;
}
