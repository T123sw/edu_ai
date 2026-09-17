import { useEffect, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import { Modal } from '../selfLearning/ui';
type Notice = { event_id: string; course_id: string; read: boolean; result_ref: { manifest_version: number; course_ready: boolean } };
export function PreparationNotifications({ owner }: { owner: string }) {
  const [items, setItems] = useState<Notice[]>([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    const refresh = async () => { try { const result = await apiRequest<{ items: Notice[] }>('/api/self-learning/notifications'); if (active) setItems(result.items); } catch { /* Preparation capability may be disabled. */ } };
    void refresh(); const timer = setInterval(() => void refresh(), 5000);
    return () => { active = false; clearInterval(timer); };
  }, [owner]);
  return <><button aria-label="课程更新通知" onClick={() => setOpen(true)}>课程更新 {items.filter(n => !n.read).length || ''}</button>{open && <Modal title="课程更新" onClose={() => setOpen(false)}>
    {error && <p role="alert">{error}</p>}{!items.length && <p>暂无课程更新。</p>}{items.map(item => <article key={item.event_id}><p>课程版本 {item.result_ref.manifest_version} 已准备好。</p>
      {item.result_ref.course_ready && <button onClick={async () => { try { await apiRequest(`/api/self-learning/notifications/${item.event_id}/read`, { method: 'POST' }); location.assign(`?courseVersion=${item.result_ref.manifest_version}#/classroom/${encodeURIComponent(item.course_id)}`); } catch (e) { setError(e instanceof Error ? e.message : '课程暂不可访问'); } }}>打开新版本</button>}
    </article>)}
  </Modal>}</>;
}
