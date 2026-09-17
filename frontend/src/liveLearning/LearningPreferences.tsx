import { useCallback, useEffect, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import { useAuth } from '../context/AuthContext';
const fields = { language: '回答语言', detail: '详细程度', example_order: '例子顺序', prior_knowledge: '已有基础', available_minutes: '可用分钟数' };
type Preference = { field: keyof typeof fields; value: string; scope: 'global' | 'course'; revision: number; status: string };
export function LearningPreferences({ course }: { course?: string }) {
  const { user } = useAuth();
  const [items, setItems] = useState<Preference[]>([]);
  const [selectedCourse, setSelectedCourse] = useState(course || '');
  const [courses, setCourses] = useState<{ id: string; title: string }[]>([]);
  const [scope, setScope] = useState<'global' | 'course'>(course ? 'course' : 'global');
  const [field, setField] = useState<keyof typeof fields>('example_order');
  const [value, setValue] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  const authorized = useCallback(() => { try { return JSON.parse(localStorage.getItem('edu-ai-auth') || '{}').user?.username === user?.username; } catch { return false; } }, [user?.username]);
  const path = '/api/self-learning/preferences' + (selectedCourse ? `?course_id=${encodeURIComponent(selectedCourse)}` : '');
  const load = useCallback(async () => {
    const result = await apiRequest<{ items: Preference[] }>(path);
    if (authorized()) setItems(result.items);
  }, [path, authorized]);
  useEffect(() => { let active = true; void load().catch(e => active && setStatus(e.message)); return () => { active = false; }; }, [load]);
  useEffect(() => { if (!course) void apiRequest<{ rooms: { id: string; title: string }[] }>('/api/self-learning/state').then(r => setCourses(r.rooms)).catch(() => undefined); }, [course]);
  const current = items.find(p => p.field === field && p.scope === scope);
  async function save(operation: 'set' | 'delete') {
    if (busy || !authorized()) return;
    setBusy(true); setStatus('');
    try {
      await apiRequest('/api/self-learning/preferences', { method: 'POST', body: JSON.stringify({ request_id: crypto.randomUUID(),
        field, scope, course_id: scope === 'course' ? selectedCourse : null, operation,
        value: operation === 'set' ? value : null, expected_revision: current?.revision || 0 }) });
      await load(); setValue(''); setStatus(operation === 'delete' ? '已删除，旧对话和摘要不会恢复这项偏好。原始聊天仍保留。' : '学习偏好已保存，当前问题中的要求仍优先。');
    } catch (e) { setStatus(e instanceof Error ? e.message : '保存失败'); }
    finally { setBusy(false); }
  }
  return <section className="sl-preferences" aria-label="学习偏好">
    <h2>学习偏好</h2><p>仅保存你明确设置的内容。全局与课程偏好分开；不记录掌握程度。</p>
    <label>作用域<select aria-label="偏好作用域" value={scope} onChange={e => setScope(e.target.value as 'global' | 'course')}><option value="global">所有课程</option><option value="course">指定课程</option></select></label>
    {scope === 'course' && !course && <label>课程<select aria-label="偏好课程" value={selectedCourse} onChange={e => setSelectedCourse(e.target.value)}><option value="">选择课程</option>{courses.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}</select></label>}
    <label>偏好字段<select aria-label="偏好字段" value={field} onChange={e => { setField(e.target.value as keyof typeof fields); setValue(''); }}>{Object.entries(fields).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
    <p>当前设置：{current?.status === 'active' ? current.value : '未设置'}</p>
    <input aria-label="偏好内容" value={value} onChange={e => setValue(e.target.value)} maxLength={600} placeholder="例如：先举例，再解释原理" />
    <button disabled={busy || !value.trim() || (scope === 'course' && !selectedCourse)} onClick={() => void save('set')}>保存学习偏好</button>
    <button disabled={busy || current?.status !== 'active'} onClick={() => void save('delete')}>删除这项偏好</button>
    {status && <p role="status">{status}</p>}
  </section>;
}
