import { useEffect, useState } from 'react';
import { apiRequest } from '../stitch/api/client';

export type UploadRef = { document_id: string; version: number; usage: 'primary' | 'reference' | 'coverage' };
export type PreparationOptions = { uploads: UploadRef[]; source_policy: { mode: 'open' | 'uploads_preferred' | 'uploaded_only' }; overrides: { total_minutes: number; required_resource_types: string[] } };
export const defaultOptions: PreparationOptions = { uploads: [], source_policy: { mode: 'open' }, overrides: { total_minutes: 60, required_resource_types: [] } };
const base = '/api/course-preparations';
type Intermediate = { brief?: { goal?: string }; research_summary?: { findings?: { claim: string }[] }; plan?: { title: string; nodes: { node_key: string; title: string; minutes: number; objectives: string[] }[] }; quality?: { decision: string; limitations?: string[] } };
type Task = { preparation_id: string; status: string; stage: string; revision: number; error_code?: string; result_ref?: { course_ready: boolean; course_id: string } };
const labels: Record<string, string> = { normalize: '理解学习目标', ingest: '读取上传资料', research_scope: '搜索并核验资料', plan: '规划学习路径', research_nodes: '检查各节点依据', produce: '生成学习资料', review: '检查课程质量', repair: '修复资料', commit: '保存课程' };

export function PreparationOptionsForm({ value, onChange, onUploadingChange }: { value: PreparationOptions; onChange: (v: PreparationOptions) => void; onUploadingChange?: (value: boolean) => void }) {
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  return <fieldset disabled={uploading} className="sl-preparation-options"><legend>学习安排与资料</legend>
    <label>学习时长（分钟）<input type="number" min={10} max={600} value={value.overrides.total_minutes} onChange={e => onChange({ ...value, overrides: { ...value.overrides, total_minutes: Number(e.target.value) } })} /></label>
    <label>资料范围<select value={value.source_policy.mode} onChange={e => onChange({ ...value, source_policy: { mode: e.target.value as PreparationOptions['source_policy']['mode'] } })}><option value="open">搜索公开资料</option><option value="uploads_preferred">优先上传资料，可搜索补充</option><option value="uploaded_only">仅使用上传资料</option></select></label>
    <label><input type="checkbox" checked={value.overrides.required_resource_types.includes('classroom')} onChange={e => onChange({ ...value, overrides: { ...value.overrides, required_resource_types: e.target.checked ? ['classroom'] : [] } })} />同时生成讲解课堂</label>
    <label>添加资料<input type="file" accept=".pdf,.doc,.docx,.md,.txt" onChange={async e => {
      const file = e.target.files?.[0]; if (!file) return;
      setUploading(true); onUploadingChange?.(true); setError('');
      try { const body = new FormData(); body.append('file', file); const ref = await apiRequest<UploadRef>(`${base}/uploads`, { method: 'POST', body }); onChange({ ...value, uploads: [...value.uploads, { ...ref, usage: 'primary' }], source_policy: { mode: value.source_policy.mode === 'open' ? 'uploads_preferred' : value.source_policy.mode } }); }
      catch (c) { setError(c instanceof Error ? c.message : '上传失败'); }
      finally { setUploading(false); onUploadingChange?.(false); }
    }} /></label>
    {uploading && <span role="status">正在上传…</span>}
    {value.uploads.map((ref, index) => <div key={`${ref.document_id}:${ref.version}`}>资料 {index + 1} <select aria-label={`资料 ${index + 1} 用途`} value={ref.usage} onChange={e => onChange({ ...value, uploads: value.uploads.map((r, i) => i === index ? { ...r, usage: e.target.value as UploadRef['usage'] } : r) })}><option value="primary">主要学习资料</option><option value="reference">参考资料</option></select><button type="button" onClick={() => onChange({ ...value, uploads: value.uploads.filter((_, i) => i !== index) })}>移除</button></div>)}
    {error && <p role="alert">{error}</p>}
  </fieldset>;
}

export function PreparationTasks({ owner, refreshKey }: { owner: string; refreshKey: number }) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [error, setError] = useState('');
  const [details, setDetails] = useState<Record<string, Intermediate>>({});
  useEffect(() => {
    let active = true; setTasks([]); setDetails({});
    const refresh = async () => { try { const result = await apiRequest<{ preparations: Task[] }>(base); if (active) { setTasks(result.preparations); setError(''); } } catch (c) { if (active) setError(c instanceof Error ? c.message : '任务状态读取失败'); } };
    void refresh(); const timer = setInterval(() => void refresh(), 3000);
    return () => { active = false; clearInterval(timer); };
  }, [owner, refreshKey]);
  const control = async (task: Task, action: 'retry' | 'cancel') => {
    try { const next = await apiRequest<Task>(`${base}/${task.preparation_id}/${action}`, { method: 'POST', body: JSON.stringify(action === 'cancel' ? { expected_revision: task.revision } : {}) }); setTasks(all => all.map(t => t.preparation_id === next.preparation_id ? next : t)); }
    catch (c) { setError(c instanceof Error ? c.message : '操作失败'); }
  };
  return <section className="sl-preparation-tasks" aria-label="课程准备任务"><h2>课程准备</h2>{error && <p role="alert">{error}</p>}{tasks.map(task => <article key={task.preparation_id}>
    <p>{task.status === 'succeeded' ? '课程已准备好' : labels[task.stage] || task.stage} · {task.status}{task.error_code && ` · ${task.error_code}`}</p>
    <button onClick={async () => { try { const value = await apiRequest<Intermediate>(`${base}/${task.preparation_id}/intermediates`); setDetails(d => ({ ...d, [task.preparation_id]: value })); } catch (c) { setError(c instanceof Error ? c.message : '读取失败'); } }}>查看资料汇总与路径</button>
    {task.status === 'failed' && <button onClick={() => void control(task, 'retry')}>继续重试</button>}
    {!['succeeded', 'failed', 'canceled'].includes(task.status) && <button onClick={() => void control(task, 'cancel')}>取消任务</button>}
    {task.status === 'succeeded' && task.result_ref?.course_ready && <a href={`#/classroom/${encodeURIComponent(task.result_ref.course_id)}`}>进入学习</a>}
    {Boolean(details[task.preparation_id]) && <details open><summary>中间产物</summary><IntermediateView value={details[task.preparation_id]} /></details>}
  </article>)}</section>;
}

function IntermediateView({ value }: { value: Intermediate }) {
  return <div>{value.plan && <><h3>{value.plan.title}</h3><ol>{value.plan.nodes.map(node => <li key={node.node_key}><strong>{node.title}</strong> · {node.minutes} 分钟<ul>{node.objectives.map(objective => <li key={objective}>{objective}</li>)}</ul></li>)}</ol></>}
    {value.research_summary?.findings && <><h3>资料汇总</h3><ul>{value.research_summary.findings.map((finding, i) => <li key={i}>{finding.claim}</li>)}</ul></>}
    {value.quality?.limitations?.map(item => <p key={item}>{item}</p>)}
    {!value.plan && !value.research_summary && <p>正在整理资料，产出后会显示在这里。</p>}
  </div>;
}

export async function submitPreparation(owner: string, goal: string, options: PreparationOptions) {
  const payload = { operation: 'create_course', goal, ...options };
  const key = `preparation:pending:${owner}`;
  const serialized = JSON.stringify(payload);
  let previous: { serialized: string; request_id: string } | undefined;
  try { previous = JSON.parse(localStorage.getItem(key) || 'null'); } catch { /* Invalid local data is not a submitted request. */ }
  const request_id = previous?.serialized === serialized ? previous.request_id : crypto.randomUUID();
  localStorage.setItem(key, JSON.stringify({ serialized, request_id }));
  const result = await apiRequest<Task>(base, { method: 'POST', body: JSON.stringify({ ...payload, request_id }) });
  // Retain the accepted request ID: repeating the same input after refresh stays idempotent.
  return result;
}
