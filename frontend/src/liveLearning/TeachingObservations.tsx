import { useEffect, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
type Observation = { turn_id: string; text: string; status: string };
export function TeachingObservations({ course, topic, refreshKey }: { course: string; topic: string; refreshKey: string }) {
  const [items, setItems] = useState<Observation[]>([]);
  const [error, setError] = useState('');
  useEffect(() => { let active = true; void apiRequest<{ items: Observation[] }>(`/api/self-learning/courses/${encodeURIComponent(course)}/topics/${encodeURIComponent(topic)}/observations`)
    .then(r => active && setItems(r.items)).catch(e => active && setError(e.message)); return () => { active = false; }; }, [course, topic, refreshKey]);
  async function change(id: string, status: 'resolved' | 'retracted') {
    try { await apiRequest(`/api/self-learning/observations/${encodeURIComponent(id)}`, { method:'POST', body:JSON.stringify({ status }) }); setItems(s => s.map(o => o.turn_id === id ? { ...o, status } : o)); }
    catch (e) { setError(e instanceof Error ? e.message : '保存失败'); }
  }
  const active = items.filter(i => i.status === 'hypothesis');
  return active.length || error ? <section aria-label="教学观察"><strong>AI 教学观察（待核实）</strong><small>不代表自评或掌握程度，你可以纠正。</small>{active.map(o => <div key={o.turn_id}><p>{o.text}</p><button onClick={() => void change(o.turn_id, 'resolved')}>已解决</button><button onClick={() => void change(o.turn_id, 'retracted')}>这项观察不准确</button></div>)}{error && <p role="alert">{error}</p>}</section> : null;
}
