import {useRecentOpens} from '../recent/context';
import {materialRecentKey} from '../recent/store';
import { useCallback, useEffect, useRef, useState, type ComponentType } from 'react';
import { createPortal } from 'react-dom';
import { uid, type Classroom as Room, type Chapter, type LearningResource } from '../selfLearning/model';
import { Icon } from '../selfLearning/ui';
import { apiRequest, ApiError } from '../stitch/api/client';
import type { CourseMaterial } from '../stitch/api/types';
import type { JobRecord } from '../jobs/types';
import { cancelJob } from '../jobs/api';
import { CourseMaterialArtifactPreview } from '../stitch/pages/CourseMaterialArtifactPreview';
import { generationRegistry } from '../components/generation/generationRegistry';
import { studioRegistry, type StudioTool } from './learningTools';
import { PodcastForm, ScenarioForm } from './LearningToolForms';
import type { GenerationConfigDefinition, GenerationFormProps } from '../components/generation/definitions/types';
import { ReportForm } from '../components/generation/forms/ReportForm';
import { QuizForm } from '../components/generation/forms/QuizForm';
import { FlashcardForm } from '../components/generation/forms/FlashcardForm';
import { MindMapForm } from '../components/generation/forms/MindMapForm';
import { ToolArtwork } from './ToolArtwork';
import { ResearchReader } from './ResearchReader';
import './studio.css';

const base = '/api/personal-studio';
type Config = Record<string, unknown>;
type Resource = { material_id: string; material_type: string; title: string; studio_title?: string; studio_mode?: string; updated_at: string; version: number; studio_course_id?: string; studio_course_title?: string; studio_chapter_id?: string; studio_chapter_title?: string; legacy?: boolean; studio_library_saved?: boolean };
type ResourceDetail = CourseMaterial & { research_sources?: { title: string; url: string; content: string }[] };
const forms = { report: ReportForm, quiz: QuizForm, flashcard: FlashcardForm, mind_map: MindMapForm, podcast: PodcastForm, scenario: ScenarioForm } as unknown as Record<string, ComponentType<GenerationFormProps<Config>>>;
const active = (job: JobRecord) => ['queued', 'running', 'cancel_requested'].includes(job.status);
const label = (kind: string) => kind === 'research' ? '研究结论' : kind === 'report' ? '学习报告' : [...studioRegistry, ...generationRegistry].find(r => r.canonicalType === kind)?.label || '学习资源';
const failure = (reason: unknown) => reason instanceof ApiError && reason.status === 404 ? '工具服务正在更新，请稍后再试。' : '暂时无法完成操作，请稍后重试。';
const openedKey=(r:Resource)=>materialRecentKey(r.material_type,r.material_id,r.legacy?r.studio_course_id:undefined);
const resourcePath = (r: Resource) => r.legacy ? `/api/courses/${encodeURIComponent(r.studio_course_id!)}/materials/${encodeURIComponent(r.material_type)}/${encodeURIComponent(r.material_id)}` : `${base}/resources/${encodeURIComponent(r.material_type)}/${encodeURIComponent(r.material_id)}`;

function ResourceArtwork({ type, research = false }: { type: string; research?: boolean }) {
  return research ? <Icon name="search" size={24} /> : <ToolArtwork type={type} compact />;
}

function StudioModal({ title, close, children, resourceType, wide = false, mode = 'preview' }: { resourceType?: string; mode?: string; title: string; close: () => void; children: React.ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLElement>(null);
  const closeRef = useRef(close); closeRef.current = close;
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    ref.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current();
      if (event.key !== 'Tab') return;
      const nodes = Array.from(ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), textarea:not(:disabled), select:not(:disabled), summary, [tabindex="0"]') || []).filter(n => n.getClientRects().length);
      const first = nodes[0], last = nodes[nodes.length - 1];
      if (!first) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === ref.current)) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', keydown);
    return () => { document.body.style.overflow = overflow; document.removeEventListener('keydown', keydown); before?.focus(); };
  }, []);
  return createPortal(<div className="studio-overlay" onMouseDown={e => { if (e.target === e.currentTarget) close(); }}>
    <section ref={ref} className={`studio-drawer studio-mode-${mode}${wide ? ' studio-drawer-wide' : ''}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}>
      <header><div className="studio-modal-title">{resourceType ? <ResourceArtwork type={resourceType} research={resourceType === 'research'} /> : <Icon name={mode === 'research' ? 'search' : mode === 'preview' ? 'report' : 'spark'} size={20} />}<h2>{title}</h2></div><button aria-label="关闭工具面板" onClick={close}><Icon name="close" size={21} /></button></header>
      <div className="studio-body">{children}</div>
    </section>
  </div>, document.body);
}

export function Studio({ owner, rooms, room, chapter, view, legacyResources = [] }: { owner: string; rooms: Room[]; room?: Room; chapter?: Chapter; view: 'course' | 'resources'; legacyResources?: LearningResource[] }) {
  const recent=useRecentOpens();
  const [researchJobId, setResearchJobId] = useState<string | null>(null);
  const [newResearch, setNewResearch] = useState(false);
  const [panel, setPanel] = useState<'research' | 'tools' | 'preview' | null>(null);
  const [tool, setTool] = useState<StudioTool | null>(null);
  const [config, setConfig] = useState<Config>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [query, setQuery] = useState('');
  const [resources, setResources] = useState<Resource[]>([]);
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [notice, setNotice] = useState('');
  const [connection, setConnection] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<Resource | null>(null);
  const [detail, setDetail] = useState<ResourceDetail | null>(null);
  const [filter, setFilter] = useState('report');
  const [search, setSearch] = useState('');
  const [expanded, setExpanded] = useState(false);
  const pendingRequest = useRef<{ key: string; id: string } | null>(null);
  const alive = useRef(true);
  const previewSequence = useRef(0);
  const lock = useRef(false);
  const reload = useCallback(async () => {
    try {
      const data = await apiRequest<{ resources: Resource[]; jobs: JobRecord[] }>(base);
      if (alive.current) { setResources(data.resources); setJobs(data.jobs); setConnection(''); }
    } catch (reason) { if (alive.current) setConnection(failure(reason)); }
    finally { if (alive.current) setLoading(false); }
  }, []);
  useEffect(() => {
    alive.current = true;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => { await reload(); if (alive.current) timer = setTimeout(poll, 5000); };
    void poll();
    return () => { alive.current = false; clearTimeout(timer); };
  }, [reload, owner]);
  const tools = studioRegistry;
  const item = studioRegistry.find(r => r.resourceType === tool);
  const definition = item?.definition as GenerationConfigDefinition<Config> | undefined;
  const Form = tool ? forms[tool] : null;
  const inCourse = (r: Resource) => (view !== 'course' || r.studio_course_id === room?.id) && (r.studio_mode !== 'research' || r.studio_library_saved !== false);
  const catalog: Resource[] = [...resources, ...legacyResources.filter(r => r.remote).map(r => ({ material_id: r.remote!.materialId, material_type: r.remote!.materialType, title: r.title, updated_at: String(r.createdAt), version: r.remote!.version, studio_course_id: r.remote!.courseId, studio_course_title: rooms.find(c => c.id === r.remote!.courseId)?.title || '原课程', studio_chapter_id: r.chapterId, studio_chapter_title: rooms.find(c => c.id === r.remote!.courseId)?.chapters.find(c => c.id === r.chapterId)?.title, legacy: true }))];
  const scopedJobs = jobs.filter(j => j.input_summary.studio_mode !== 'research' && (view !== 'course' || j.input_summary.studio_course_id === room?.id));
  const typeOf = (r: Pick<Resource, 'studio_mode' | 'material_type'>) => r.studio_mode === 'research' ? 'research' : r.material_type;
  const categories = [...tools.map(t => [t.canonicalType, label(t.canonicalType)]), ['research', label('research')]];
  const currentJobs = scopedJobs.filter(j => active(j) && (filter === 'all' || (j.input_summary.studio_mode === 'research' ? 'research' : j.input_summary.resource_type) === filter));
  const researchHistory = jobs.filter(j => j.input_summary.studio_mode === 'research' && j.input_summary.studio_course_id === room?.id && j.input_summary.studio_chapter_id === chapter?.id);
  const readingJob = researchJobId || (!newResearch ? researchHistory[0]?.edu_job_id : undefined);
  const filtered = recent.sort(catalog,openedKey).filter(r => inCourse(r) && (filter === 'all' || typeOf(r) === filter) && (r.studio_title || r.title).toLowerCase().includes(search.trim().toLowerCase()));
  function choose(type: StudioTool) {
    const def = studioRegistry.find(r => r.resourceType === type)!.definition as GenerationConfigDefinition<Config>;
    const defaults = def.defaultConfig();
    setTool(type); setConfig({ ...defaults, ...('topic' in defaults ? { topic: chapter?.title || '' } : {}), ...('title' in defaults ? { title: chapter?.title || '' } : {}), ...(type === 'report' ? { audience: '自主学习者' } : {}) }); setErrors({}); setNotice('');
  }
  async function submit() {
    if (lock.current || !room || !chapter) return;
    const validation = panel === 'research' ? (query.trim().length >= 2 ? {} : { query: '请输入更具体的研究问题' }) : definition?.validate(config) || {};
    setErrors(validation);
    if (Object.keys(validation).length) return;
    const title = panel === 'research' ? query.trim() : String(config.topic || config.title || '').trim();
    const content = { course_id: room.id, chapter_id: chapter.id, mode: panel === 'research' ? 'research' : 'generate', resource_type: item?.canonicalType || 'report', title,
      config: panel === 'research' ? {} : definition!.serialize({ courseId: room.id, config, source: { mode: 'none', selectedDocumentIds: [] } }) };
    const key = JSON.stringify(content);
    if (pendingRequest.current?.key !== key) pendingRequest.current = { key, id: uid() };
    lock.current = true; setBusy(true); setNotice('');
    try {
      const job = await apiRequest<JobRecord>(`${base}/generate`, { method: 'POST', body: JSON.stringify({ ...content, request_id: pendingRequest.current.id }) });
      if (!alive.current) return;
      setJobs(old => [job, ...old.filter(j => j.edu_job_id !== job.edu_job_id)]); pendingRequest.current = null;
      if (content.mode === 'research') { setResearchJobId(job.edu_job_id); setNewResearch(false); }
      else setNotice('任务已开始，完成后自动保存到「我的资源」。可以关闭面板，继续学习。');
      await reload();
    } catch (reason) { if (alive.current) setNotice(failure(reason)); }
    finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  async function preview(resource: Resource) {
    recent.mark(openedKey(resource));
    if (resource.studio_mode === 'research' && jobs.some(j => j.edu_job_id === resource.material_id)) { setResearchJobId(resource.material_id); setNewResearch(false); setPanel('research'); setNotice(''); return; }
    const sequence = ++previewSequence.current;
    setSelected(resource); setDetail(null); setPanel('preview'); setNotice('');
    try { const value = await apiRequest<ResourceDetail>(resourcePath(resource)); if (alive.current && sequence === previewSequence.current) setDetail(value); }
    catch (reason) { if (alive.current && sequence === previewSequence.current) setNotice(failure(reason)); }
  }
  async function cancelGeneration(job: JobRecord) {
    if (lock.current) return;
    lock.current = true; setBusy(true);
    try { await cancelJob(job.edu_job_id); await reload(); }
    catch (reason) { setConnection(failure(reason)); }
    finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  const previewTitle = [selected?.studio_course_title, selected?.studio_chapter_title].filter(Boolean).join(' · ') || selected?.studio_title || selected?.title || '资源预览';
  const close = () => { previewSequence.current++; setPanel(null); setNotice(''); };
  const resourceContent = <section className="studio-library" aria-label={view === 'course' ? '本课资源' : '我的资源'}>
    <div className="sl-section-heading"><h2><Icon name="report" size={18} />{view === 'course' ? '本课资源' : '资源列表'} <span>{catalog.filter(r => inCourse(r) && categories.some(([id]) => id === typeOf(r))).length}</span></h2>
      <div className="studio-type-filters" aria-label="资源类型">{categories.map(([id, name]) => <button key={id} aria-pressed={filter === id} onClick={() => { setFilter(id); setExpanded(false); }}>{name}<span>{catalog.filter(r => inCourse(r) && (id === 'all' || typeOf(r) === id)).length}</span></button>)}</div>
      <input className="sl-small-input" aria-label="搜索我的资源" placeholder="搜索资源…" value={search} onChange={e => setSearch(e.target.value)} />
    </div>
    {connection && <p className="studio-message" role="status">{connection}<button onClick={() => void reload()}>重新加载</button></p>}
    {currentJobs.length > 0 && <div className="studio-jobs">{currentJobs.map(j => <div key={j.edu_job_id}><Icon name="spark" size={18} /><div><strong>{String(j.input_summary?.title || '正在生成')}</strong><span>{String(j.input_summary.studio_course_title || '历史任务')} · {j.message || '已进入后台队列'} · {j.progress}%</span><progress value={j.progress} max={100} /></div>{j.cancelable && <button disabled={busy || j.status === 'cancel_requested'} onClick={() => void cancelGeneration(j)}>取消</button>}</div>)}</div>}
    {view === 'course' ? <div className="sl-card-grid">{filtered.slice(0, expanded ? undefined : 8).map(r => <button key={`${r.studio_course_id}:${r.material_type}:${r.material_id}`} className="studio-course-resource" onClick={() => void preview(r)}><ResourceArtwork type={r.material_type} research={r.studio_mode === 'research'} /><span><strong>{r.studio_title || r.title}</strong><small>{r.studio_chapter_title || label(typeOf(r))}</small></span><Icon name="arrow" size={15} /></button>)}</div> : filtered.length > 0 && <div className="studio-resource-list">
      <div className="studio-resource-columns" aria-hidden="true"><span>资源名称</span><span>类型</span><span>所属课程</span><span /></div>
      <ul aria-label="已保存的资源">{filtered.map(r => <li key={`${r.studio_course_id}:${r.material_type}:${r.material_id}`}>
        <button className="studio-resource-row" onClick={() => void preview(r)}>
          <span className="studio-resource-name"><span className="studio-resource-icon"><ResourceArtwork type={r.material_type} research={r.studio_mode === 'research'} /></span><span className="studio-resource-title"><strong title={r.studio_title || r.title}>{r.studio_title || r.title}</strong>{r.studio_chapter_title && <small title={r.studio_chapter_title}>{r.studio_chapter_title}</small>}</span></span>
          <span className="studio-resource-type">{label(typeOf(r))}</span>
          <span className="studio-resource-course" title={r.studio_course_title || '历史独立资源'}>{r.studio_course_title || '历史独立资源'}</span>
          <span className="studio-resource-open"><span>打开</span><Icon name="arrow" size={15} /></span>
        </button>
      </li>)}</ul>
    </div>}
    {!filtered.length && <p className="sl-inline-empty">{loading ? '正在读取资源…' : search ? '没有找到匹配的资源。' : filter === 'research' ? '在深度研究中收藏结论后，会显示在这里。' : '生成的资料会按类型保存在这里。'}</p>}
    {view === 'course' && filtered.length > 8 && <button className="sl-text-button" onClick={() => setExpanded(v => !v)}>{expanded ? '收起' : '查看全部'}</button>}
  </section>;
  return <>
    {view === 'resources' ? <main className="sl-home sl-home-editorial studio-resources-page"><header className="studio-library-heading"><Icon name="folder" size={32} /><div><h1>我的资源</h1><p>报告、习题、闪卡，按类型整理你的学习积累。</p></div></header>{resourceContent}</main> : <aside className="studio-rail" aria-label="学习工具栏">
      <button onClick={() => { setPanel('research'); setNotice(''); }} aria-label="打开深度研究"><Icon name="search" size={21} /><span>深度研究</span></button>
      <button onClick={() => { setPanel('tools'); setTool(null); setNotice(''); }} aria-label="打开生成工具"><Icon name="folder" size={21} /><span>生成工具</span></button>
    </aside>}
    {panel && <StudioModal resourceType={panel === 'preview' ? (selected ? typeOf(selected) : undefined) : panel === 'tools' ? tool || undefined : undefined} mode={panel === 'tools' && tool ? 'configure' : panel} title={panel === 'research' ? '深度研究' : panel === 'preview' ? previewTitle : item ? label(item.canonicalType) : '生成工具'} close={close} wide={panel === 'preview' || (panel === 'research' && !!readingJob)}>
      {panel !== 'preview' && !(panel === 'research' && readingJob) && room && chapter && <div className="studio-course-context"><Icon name="book" size={15} /><strong>{room.title}</strong><span>/</span><small>{chapter.title}</small></div>}
      {panel === 'research' && (readingJob ? <ResearchReader key={readingJob} jobId={readingJob} onNew={() => { setResearchJobId(null); setNewResearch(true); setQuery(''); }} onUpdated={() => void reload()} /> : <section className="studio-research-compose"><div className="studio-compose-heading"><span className="studio-eyebrow">探索一个问题</span><h3>你想深入了解什么？</h3><p>从课程里的一个疑问出发，找到解释与依据。</p></div><div className="studio-research-input"><label className="studio-query"><span className="studio-visually-hidden">想深入了解什么？</span><textarea value={query} maxLength={200} onChange={e => setQuery(e.target.value)} placeholder={`例如：「${chapter?.title || '这个知识点'}」在实际场景中如何运用？`} /></label><div className="studio-compose-actions"><span><Icon name="search" size={14} />查阅资料 · 整理结论</span><button className="studio-primary" disabled={busy || query.trim().length < 2} onClick={() => void submit()}>{busy ? '正在提交…' : '开始研究'}<Icon name="arrow" size={16} /></button></div></div>{errors.query && <p role="alert">{errors.query}</p>}<div className="studio-suggestions"><span>换个角度</span>{[['理解原理', `深入解释${chapter?.title || '当前知识点'}的原理和成立条件`], ['实际应用', `${chapter?.title || '当前知识点'}在实际中有哪些应用？请结合具体案例`], ['常见误区', `学习${chapter?.title || '当前知识点'}时有哪些常见误区？为什么容易出错？`]].map(([name, question]) => <button key={name} onClick={() => setQuery(question.slice(0, 200))}>{name}<Icon name="arrow" size={12} /></button>)}</div><p className="studio-storage-note"><Icon name="folder" size={14} />收藏的结论可在本课资源的「研究结论」中查看。</p></section>)}
      {panel === 'research' && researchHistory.length > 0 && <details className="studio-research-history"><summary>本知识点的研究记录 · {researchHistory.length}</summary>{researchHistory.map(j => <button key={j.edu_job_id} onClick={() => { setResearchJobId(j.edu_job_id); setNewResearch(false); }}>{String(j.input_summary.title || '研究记录')}<Icon name="arrow" size={14} /></button>)}</details>}
      {panel === 'tools' && (!tool ? <><div className="studio-tool-grid">{tools.map(t => <button key={t.resourceType} onClick={() => choose(t.resourceType)}><ToolArtwork type={t.resourceType} /><span className="studio-tool-copy"><strong>{label(t.canonicalType)}</strong></span><Icon name="arrow" size={16} /></button>)}</div></> : <section className="studio-configure"><button className="studio-back" onClick={() => { setTool(null); setNotice(''); }}><Icon name="back" size={15} />全部工具</button><div className="studio-configure-heading"><h3>制作一份{label(item!.canonicalType)}</h3><ToolArtwork type={tool} /></div>{Form && <Form value={config} onChange={setConfig} errors={errors} />}<div className="studio-form-actions"><span><Icon name="folder" size={15} />保存到本课资源</span><button className="studio-primary" disabled={busy} onClick={() => void submit()}>{busy ? '正在提交…' : '开始生成'}<Icon name="arrow" size={16} /></button></div></section>)}
      {panel === 'preview' && (detail ? <>
        <CourseMaterialArtifactPreview material={detail} />
        {!!detail.research_sources?.length && <details className="studio-sources"><summary>参考来源 · {detail.research_sources.length}</summary>{detail.research_sources.map((s, i) => <article key={s.url}><a href={s.url} target="_blank" rel="noreferrer">{i + 1}. {s.title}<Icon name="arrow" size={14} /></a><p>{s.content.slice(0, 220)}…</p></article>)}</details>}</> : <p role="status">{notice ? '资源暂时无法读取。' : '正在打开资源…'}</p>)}
      {notice && <p className="studio-message" role="status">{notice}</p>}
      {panel === 'tools' && !tool && <section className="studio-related">{resourceContent}</section>}
    </StudioModal>}
  </>;
}
