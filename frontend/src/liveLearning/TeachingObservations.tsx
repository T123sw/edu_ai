import { useEffect, useRef, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import { citationUrl, type Citation } from './citationNavigation';
type Source = { message_id: string; quote: string; role?: string };
type Observation = Partial<Citation> & { turn_id: string; text: string; kind: string; status: string; sources?: Source[] };
type Summary = { items: { text: string; kind: string; category?: string; sources?: Source[] }[] };
const labels: Record<string, string> = { difficulty: '曾遇到的困难', open_question: '待讨论问题', helpful_explanation: '有帮助的讲法', discussion: '讨论重点' };
export function TeachingObservations({ course, topic, owner, refreshKey }: { course: string; topic: string; owner: string; refreshKey: string }) {
  const [items, setItems] = useState<Observation[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState<string>();
  const scope = JSON.stringify([owner, course, topic]);
  const current = useRef(scope);
  current.current = scope;
  const authorized = () => { try { return JSON.parse(localStorage.getItem('edu-ai-auth') || '{}').user?.username === owner; } catch { return false; } };
  useEffect(() => {
    let active = true;
    setItems([]); setSummary(null); setError('');
    void apiRequest<{ items: Observation[]; summary?: Summary | null }>(`/api/self-learning/courses/${encodeURIComponent(course)}/topics/${encodeURIComponent(topic)}/observations`)
      .then(r => { if (active) { setItems(r.items); setSummary(r.summary || null); } }).catch(e => active && setError(e.message));
    return () => { active = false; };
  }, [course, topic, owner, refreshKey]);
  async function change(id: string, status: 'resolved' | 'retracted') {
    if (busy || !authorized()) return;
    setBusy(id); setError('');
    try {
      await apiRequest(`/api/self-learning/observations/${encodeURIComponent(id)}`, { method: 'POST', body: JSON.stringify({ status }) });
      if (current.current === scope) { setItems(s => s.map(o => o.turn_id === id ? { ...o, status } : o)); setSummary(null); }
    } catch (e) { if (current.current === scope) setError(e instanceof Error ? e.message : '保存失败'); }
    finally { if (current.current === scope) setBusy(undefined); }
  }
  return <section aria-label="本知识点教学记录">
    <strong>本知识点教学记录</strong><p>AI 根据对话整理，可纠正；不代表已掌握。</p>
    {items.map(o => <article key={o.turn_id}>
      <strong>{labels[o.kind] || '教学观察'} · {o.status === 'resolved' ? '你已标记解决' : o.status === 'retracted' ? '已撤回' : '待核实'}</strong><p>{o.text}</p>
      <details><summary>查看依据</summary>{o.sources?.map(s => <blockquote key={s.message_id}>{s.quote}</blockquote>)}
        {o.resource_ref && <a target="_blank" rel="noopener noreferrer" href={citationUrl({ resource_ref: o.resource_ref, locator: o.locator })}>打开当时的资料 · v{o.resource_ref.version}</a>}
      </details>
      {o.status === 'hypothesis' && <>{o.kind !== 'helpful_explanation' && <button disabled={!!busy} onClick={() => void change(o.turn_id, 'resolved')}>已解决</button>}<button disabled={!!busy} onClick={() => void change(o.turn_id, 'retracted')}>这项记录不准确</button></>}
    </article>)}
    {!!summary?.items.length && <details><summary>较早对话的摘要</summary>{summary.items.map((item, index) => <div key={index}><p>{labels[item.category || 'discussion']}：{item.text}</p><small>对话摘要，不作为教材事实</small><details><summary>查看原话</summary>{item.sources?.map(s => <blockquote key={s.message_id}>{s.role === 'assistant' ? '学习 Agent：' : '你：'}{s.quote}</blockquote>) || <p>旧版摘要未附原话，可从历史对话查看。</p>}</details></div>)}</details>}
    {!items.length && !summary?.items.length && !error && <p>暂无教学记录，可继续阅读或随时提问。</p>}
    {error && <p role="alert">{error}，仍可继续阅读。</p>}
  </section>;
}
