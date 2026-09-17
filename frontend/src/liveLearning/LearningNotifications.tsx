import { useEffect, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import type { Classroom } from '../selfLearning/model';

type Ref = { material_id: string; material_type: string; version: number };
type Notice = { notification_id: string; preparation_id: string; type: string; read: boolean; result: { resource_refs?: Ref[]; change_summary?: string; error_code?: string } };
type Task = { preparation_id: string; status: string; stage: string };
const statuses: Record<string, string> = { accepted: '已接收', running: '准备中', checking: '检查中', succeeded: '已交付', failed: '准备失败', canceled: '已取消' };

export function LearningNotifications({ room, active, onSelect }: { room: Classroom; active: boolean; onSelect: (id: string) => void }) {
  const [notices, setNotices] = useState<Notice[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const course = encodeURIComponent(room.id);
  useEffect(() => {
    const controller = new AbortController();
    const authorized = () => { try { return JSON.parse(localStorage.getItem('edu-ai-auth') || '{}').user?.username === room.sessionOwner; } catch { return false; } };
    async function load() {
      if (!authorized()) return;
      try {
        const [notifications, preparations] = await Promise.all([
          apiRequest<{ items: Notice[] }>(`/api/self-learning/courses/${course}/notifications`, { signal: controller.signal }),
          apiRequest<{ items: Task[] }>(`/api/self-learning/courses/${course}/preparations`, { signal: controller.signal }),
        ]);
        if (!controller.signal.aborted && authorized()) { setNotices(notifications.items); setTasks(preparations.items); setError(''); }
      } catch (e) { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : '通知读取失败'); }
    }
    void load(); const timer = setInterval(() => void load(), 2000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [course, room.sessionOwner]);
  async function open(notice: Notice, ref: Ref) {
    setBusy(true);
    try {
      // Reauthorize through the task endpoint immediately before navigation.
      await apiRequest(`/api/self-learning/preparations/${encodeURIComponent(notice.preparation_id)}`);
      await apiRequest(`/api/self-learning/notifications/${encodeURIComponent(notice.notification_id)}/read`, { method: 'POST' });
      setNotices(items => items.map(n => n.notification_id === notice.notification_id ? { ...n, read: true } : n));
      onSelect(ref.material_id);
    } catch (e) { setError(e instanceof Error ? e.message : '资料暂不可用'); }
    finally { setBusy(false); }
  }
  async function control(task: Task, action: 'cancel' | 'retry') {
    setBusy(true);
    try {
      const updated = await apiRequest<Task>(`/api/self-learning/preparations/${encodeURIComponent(task.preparation_id)}/control`, { method: 'POST', body: JSON.stringify({ action }) });
      setTasks(items => items.map(t => t.preparation_id === updated.preparation_id ? updated : t));
    } catch (e) { setError(e instanceof Error ? e.message : '操作失败'); }
    finally { setBusy(false); }
  }
  return <section aria-label="资料准备通知">
    <details><summary>资料准备 · {notices.filter(n => !n.read).length} 条未读{active ? '（可稍后查看）' : ''}</summary>
      <p>结果到达后保留当前阅读位置；由你选择何时打开。</p>
      {tasks.map(task => <div key={task.preparation_id}><span>{statuses[task.status] || task.status}</span>
        {['accepted', 'running', 'checking'].includes(task.status) && <button disabled={busy} onClick={() => void control(task, 'cancel')}>取消准备</button>}
        {['failed', 'canceled'].includes(task.status) && <button disabled={busy} onClick={() => void control(task, 'retry')}>重试准备</button>}
      </div>)}
      {notices.map(notice => <article key={notice.notification_id} data-preparation-id={notice.preparation_id}>
        <p>{notice.type === 'succeeded' ? '新资料已准备好' : notice.type === 'unavailable' ? '结果暂不可读取' : statuses[notice.type] || notice.type}</p>
        <small>{notice.result.change_summary || notice.result.error_code}</small>
        {notice.result.resource_refs?.map(ref => <div key={ref.material_id}><button disabled={busy || !room.chapters.some(t => t.resources.some(r => r.id === ref.material_id))} onClick={() => void open(notice, ref)}>打开新{ref.material_type === 'quiz' ? '练习' : '资料'} · v{ref.version}</button><small>新资料从开头阅读，旧资料的完成标记和引用保留。</small></div>)}
      </article>)}
    </details>{error && <small role="alert">{error}</small>}
  </section>;
}
