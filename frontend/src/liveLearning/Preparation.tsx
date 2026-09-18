import { useEffect, useId, useState, type Dispatch, type SetStateAction } from 'react';
import { apiRequest } from '../stitch/api/client';
import { Icon } from '../selfLearning/ui';

export type UploadRef = { document_id: string; version: number; filename?: string };
export type PreparationOptions = { uploads: UploadRef[]; overrides: { total_minutes?: number; language?: string; depth?: 'introductory' | 'intermediate' | 'advanced'; required_resource_types?: string[] } };
export const defaultOptions: PreparationOptions = { uploads: [], overrides: {} };
const base = '/api/course-preparations';
type Intermediate = { brief?: { topic?: string; learning_goal?: string; prior_knowledge?: string; total_minutes?: number; language?: string; depth?: string; assumptions?: string[]; desired_outcomes?: string[]; source_policy?: { mode: string } }; input_documents?: { document_id: string; filename: string; complete: boolean; parts: { kind: string; summary: string }[] }[]; research_summary?: { findings?: { claim: string }[] }; plan?: { title: string; nodes: { node_key: string; title: string; minutes: number; objectives: string[] }[] }; quality?: { decision: string; limitations?: string[] } };
type Task = { preparation_id: string; status: string; stage: string; revision: number; error_code?: string; result_ref?: { course_ready: boolean; course_id: string } };
const labels: Record<string, string> = { normalize: '理解学习目标', ingest: '读取上传资料', research_scope: '搜索并核验资料', plan: '规划学习路径', research_nodes: '检查各节点依据', produce: '生成学习资料', review: '检查课程质量', repair: '修复资料', commit: '保存课程' };

export function PreparationOptionsForm({ value, onChange, onUploadingChange }: { value: PreparationOptions; onChange: Dispatch<SetStateAction<PreparationOptions>>; onUploadingChange?: (value: boolean) => void }) {
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsId = useId();
  return <fieldset disabled={uploading} className="sl-preparation-options"><legend className="sl-intake-sr-only">添加学习资料（可选）</legend>
    <div className="sl-intake-toolbar">
    <label className="sl-intake-upload"><Icon name="upload" size={16} /><span>添加资料</span><input aria-label="添加资料" className="sl-intake-sr-only" type="file" multiple accept=".pdf,.doc,.docx,.md,.txt" onChange={async e => {
      const files = Array.from(e.target.files || []); e.target.value = '';
      if (!files.length) return;
      if (value.uploads.length + files.length > 30) { setError('最多添加 30 份资料'); return; }
      setUploading(true); onUploadingChange?.(true); setError('');
      const failures: string[] = [];
      try {
        for (const file of files) {
          try {
            if (file.size > 30 * 1024 * 1024) throw new Error('文件不能超过 30 MB');
            const body = new FormData(); body.append('file', file);
            const ref = await apiRequest<UploadRef>(`${base}/uploads`, { method: 'POST', body });
            onChange(previous => ({ ...previous, uploads: [...previous.uploads.filter(r => r.document_id !== ref.document_id), { document_id: ref.document_id, version: ref.version, filename: file.name }] }));
          } catch (cause) { failures.push(`${file.name}：${cause instanceof Error ? cause.message : '上传失败'}`); }
        }
        setError(failures.join('；'));
      } finally { setUploading(false); onUploadingChange?.(false); }
    }} /></label>
    <button type="button" className="sl-intake-settings-toggle" aria-expanded={settingsOpen} aria-controls={settingsId} onClick={() => setSettingsOpen(open => !open)}>补充安排（可选）<Icon name="chevron" size={14} /></button>
    </div>
    <p className="sl-intake-hint">上传岗位要求、学习材料或个人背景，让课程更适合你。<span>PDF / Word / Markdown / TXT · 每份最多 30 MB</span></p>
    {uploading && <span className="sl-intake-uploading" role="status"><span />正在上传…</span>}
    {value.uploads.length > 0 && <div className="sl-intake-files">{value.uploads.map((ref, index) => <div className="sl-intake-file" key={`${ref.document_id}:${ref.version}`}><Icon name="book" size={15} /><span title={ref.filename}>{ref.filename || `资料 ${index + 1}`}</span><button type="button" aria-label={`移除 ${ref.filename || `资料 ${index + 1}`}`} onClick={() => onChange(previous => ({ ...previous, uploads: previous.uploads.filter(r => r.document_id !== ref.document_id) }))}><Icon name="close" size={13} /></button></div>)}</div>}
    <div id={settingsId} hidden={!settingsOpen} className="sl-intake-settings"><p>留空即可自动安排，也可以直接在上方描述你的偏好。</p><div className="sl-intake-settings-grid">
      <label>学习时长（分钟）<input type="number" min={1} max={100000} placeholder="自动理解" value={value.overrides.total_minutes ?? ''} onChange={e => { const minutes = e.target.value ? Number(e.target.value) : undefined; onChange(previous => ({ ...previous, overrides: { ...previous.overrides, total_minutes: minutes } })); }} /></label>
      <label>输出语言<input placeholder="根据需求自动选择" value={value.overrides.language || ''} onChange={e => { const language = e.target.value; onChange(previous => ({ ...previous, overrides: { ...previous.overrides, language: language || undefined } })); }} /></label>
      <label>学习深度<select value={value.overrides.depth || ''} onChange={e => { const depth = e.target.value as PreparationOptions['overrides']['depth']; onChange(previous => ({ ...previous, overrides: { ...previous.overrides, depth: depth || undefined } })); }}><option value="">自动安排</option><option value="introductory">入门</option><option value="intermediate">进阶</option><option value="advanced">深入</option></select></label>
      <label>讲解形式<select value={value.overrides.required_resource_types?.includes('classroom') ? 'classroom' : ''} onChange={e => { const kinds = e.target.value ? ['classroom'] : undefined; onChange(previous => ({ ...previous, overrides: { ...previous.overrides, required_resource_types: kinds } })); }}><option value="">根据需求安排</option><option value="classroom">同时提供讲解课堂</option></select></label>
    </div></div>
    {error && <p className="sl-intake-error" role="alert">{error}</p>}
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
  if (!tasks.length && !error) return null;
  return <section className="sl-preparation-tasks" aria-label="课程准备任务"><h2>课程准备</h2>{error && <p role="alert">{error}</p>}{tasks.map(task => <article key={task.preparation_id}>
    <p>{task.status === 'succeeded' ? '课程已准备好' : labels[task.stage] || task.stage} · {{ queued: '排队中', running: '进行中', failed: '未完成', canceled: '已取消', succeeded: '已完成' }[task.status] || task.status}{task.error_code && ` · ${task.error_code}`}</p>
    <button onClick={async () => { try { const value = await apiRequest<Intermediate>(`${base}/${task.preparation_id}/intermediates`); setDetails(d => ({ ...d, [task.preparation_id]: value })); } catch (c) { setError(c instanceof Error ? c.message : '读取失败'); } }}>查看资料汇总与路径</button>
    {task.status === 'failed' && <button onClick={() => void control(task, 'retry')}>继续重试</button>}
    {!['succeeded', 'failed', 'canceled'].includes(task.status) && <button onClick={() => void control(task, 'cancel')}>取消任务</button>}
    {task.status === 'succeeded' && task.result_ref?.course_ready && <a href={`#/classroom/${encodeURIComponent(task.result_ref.course_id)}`}>进入学习</a>}
    {Boolean(details[task.preparation_id]) && <details open><summary>中间产物</summary><IntermediateView value={details[task.preparation_id]} /></details>}
  </article>)}</section>;
}

function IntermediateView({ value }: { value: Intermediate }) {
  return <div>{value.brief && <section aria-label="需求理解"><h3>Agent 对需求的理解</h3><p>{value.brief.learning_goal || value.brief.topic}</p>{value.brief.prior_knowledge && <p>已有基础：{value.brief.prior_knowledge}</p>}<p>{value.brief.total_minutes} 分钟 · {value.brief.language}</p>{value.brief.source_policy?.mode === 'uploaded_only' && <p>仅依据上传资料，不搜索外部资料。</p>}{value.brief.desired_outcomes?.map((outcome, i) => <p key={i}>学习目标：{outcome}</p>)}{value.brief.assumptions?.map((assumption, i) => <p key={i}>采用的假设：{assumption}</p>)}</section>}
    {value.input_documents?.map(doc => <div key={doc.document_id}><strong>{doc.filename}</strong> · {doc.complete ? '已理解' : '正在理解'}{doc.parts.map((part, i) => <p key={i}>{part.summary}</p>)}</div>)}
    {value.plan && <><h3>{value.plan.title}</h3><ol>{value.plan.nodes.map(node => <li key={node.node_key}><strong>{node.title}</strong> · {node.minutes} 分钟<ul>{node.objectives.map(objective => <li key={objective}>{objective}</li>)}</ul></li>)}</ol></>}
    {value.research_summary?.findings && <><h3>资料汇总</h3><ul>{value.research_summary.findings.map((finding, i) => <li key={i}>{finding.claim}</li>)}</ul></>}
    {value.quality?.limitations?.map(item => <p key={item}>{item}</p>)}
    {!value.brief && !value.input_documents?.length && !value.plan && !value.research_summary && <p>正在整理资料，产出后会显示在这里。</p>}
  </div>;
}

export async function submitPreparation(owner: string, goal: string, options: PreparationOptions) {
  const payload = { operation: 'create_course', goal: goal.trim() || '请根据上传资料推断学习目标并安排课程；没有明确的信息请列为假设。', uploads: options.uploads.map(({ document_id, version }) => ({ document_id, version })), overrides: options.overrides };
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
