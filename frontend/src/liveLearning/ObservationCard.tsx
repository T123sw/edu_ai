import { useEffect, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
export function ObservationCard({ courseId, topicId, messageId, text }: { courseId: string; topicId: string; messageId: string; text: string }) {
  const [status, setStatus] = useState('hypothesis'); const [revision, setRevision] = useState(0); const [error, setError] = useState('');
  const base = `/api/self-learning/courses/${encodeURIComponent(courseId)}/topics/${encodeURIComponent(topicId)}/observations`;
  useEffect(() => {
    let active = true;
    void apiRequest<{ items: { message_id: string; status: string; revision: number }[] }>(base).then(data => {
      const value = data.items.find(x => x.message_id === messageId);
      if (active && value) { setStatus(value.status); setRevision(value.revision); }
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [base, messageId]);
  const update = async (next: 'resolved' | 'retracted') => {
    try {
      const value = await apiRequest<{ status: string; revision: number }>(`${base}/${encodeURIComponent(messageId)}`, { method: 'POST', body: JSON.stringify({ status: next, expected_revision: revision }) });
      setStatus(value.status); setRevision(value.revision); setError('');
    } catch (e) { setError(e instanceof Error ? e.message : '保存失败'); }
  };
  return <div><small>待验证的教学观察：{text} · {status === 'resolved' ? '你已确认解决' : status === 'retracted' ? '你已撤回' : '尚未确认'}</small>
    {status === 'hypothesis' && <div><button onClick={() => void update('resolved')}>这个问题已解决</button><button onClick={() => void update('retracted')}>这项观察不适用</button></div>}{error && <p role="alert">{error}</p>}</div>;
}
