import { useCallback, useEffect, useRef, useState } from 'react';
import { apiRequest } from '../stitch/api/client';
import { Home, GeneratedResourceCard } from '../selfLearning/Home';
import { Icon } from '../selfLearning/ui';
import { retryJob } from '../jobs/api';
import { ExamGenerationProgress, type ExamGeneration as Generation } from './ExamGenerationProgress';
import './exam.css';

type Upload = {document_id: string; filename: string};
const endpoint = '/api/exam-generations';
const active = (status: string) => ['queued', 'running', 'pending', 'cancel_requested'].includes(status);
const labels: Record<string, string> = {queued: '排队中', pending: '排队中', running: '生成中', cancel_requested: '正在取消'};
const failure = (error: unknown) => error instanceof Error ? error.message : '操作未完成，请稍后重试';
const prompts = {
  custom: '- 我想练习 Python 循环与函数。\n- 难度适中，重点巩固基础概念。\n- 可以直接描述范围，也可上传资料。',
  mimic: '- 我想参照原卷的题型和考点练习。\n- 第一份材料请上传参考试卷（PDF）。\n- 还可以补充资料、难度或出题要求。',
};
const questionTypes = [['choice', '选择题'], ['fill_in_blank', '填空题'], ['short_answer', '简答题']] as const;

export function ExamHome() {
  const [uploads, setUploads] = useState<Upload[]>([]), [mode, setMode] = useState<'mimic' | 'custom'>('custom');
  const [drafts, setDrafts] = useState({custom: '', mimic: ''});
  const requirement = drafts[mode];
  const setRequirement = (value: string) => setDrafts(previous => ({...previous, [mode]: value}));
  const [counts, setCounts] = useState({choice: 10, fill_in_blank: 5, short_answer: 5});
  const count = Object.values(counts).reduce((sum, value) => sum + value, 0);
  const validCounts = Object.values(counts).every(value => Number.isInteger(value) && value >= 0) && count >= 1 && count <= 100;
  const validTemplate = !!uploads.length && /\.pdf$/i.test(uploads[0].filename);
  const effectiveRequirement = requirement.trim() || (mode === 'mimic'
    ? '保持原卷题型、题数和考点，生成一套新的模拟试卷。'
    : '根据上传的学习资料，生成一套覆盖主要知识点的习题。');
  const [busy, setBusy] = useState(false), [error, setError] = useState('');
  const [items, setItems] = useState<Generation[]>([]);
  const [loading, setLoading] = useState(true);
  const [showProgress, setShowProgress] = useState(false), [tracked, setTracked] = useState<Generation | null>(null);
  const [submitting, setSubmitting] = useState(false), [submitError, setSubmitError] = useState(''), [pollError, setPollError] = useState('');
  const [search, setSearch] = useState(false), [query, setQuery] = useState(''), [expanded, setExpanded] = useState(false);
  const request = useRef<{signature: string; id: string}>();
  const refresh = useCallback(async (signal?: AbortSignal) => {
    const result = await apiRequest<{items: Generation[]}>(endpoint, {signal});
    if (signal?.aborted) return;
    setItems(result.items);setLoading(false);setPollError('');
    setTracked(previous => previous ? result.items.find(item => item.job_id === previous.job_id) || previous : null);
  }, []);
  useEffect(() => {
    const controller = new AbortController();let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {await refresh(controller.signal);} catch (e) {if (!controller.signal.aborted) {setPollError('暂时无法读取进度，正在重新连接。' + failure(e));setLoading(false);}}
      if (!controller.signal.aborted) timer = setTimeout(() => void poll(), 3000);
    };
    void poll();return () => {controller.abort();clearTimeout(timer);};
  }, [refresh]);
  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true);setError('');
    try {
      for (const file of Array.from(files)) {
        if (file.size > 30 * 1024 * 1024) throw Error('单个文件不能超过 30 MB');
        const form = new FormData();form.append('file', file);
        const item = await apiRequest<Upload>(endpoint + '/documents', {method: 'POST', body: form});
        setUploads(previous => [...previous, item]);
      }
    } catch (e) {setError(failure(e));} finally {setBusy(false);}
  };
  const generate = async () => {
    setBusy(true);setError('');
    try {
      const sources = uploads.map((file, index) => ({document_id: file.document_id, role: mode === 'mimic' && index === 0 ? 'template' : 'context'}));
      if (mode === 'mimic' && !validTemplate) throw Error('请将参考试卷 PDF 作为第一份材料上传');
      if (mode === 'custom' && (!validCounts || (!requirement.trim() && !uploads.length))) throw Error('请描述出题范围或上传学习资料，题目总数须为 1–100 道');
      const perTypeCounts = Object.fromEntries(Object.entries(counts).filter(([, value]) => value > 0));
      const payload = {mode, language: 'zh', requirement: effectiveRequirement, sources,
        ...(mode === 'custom' ? {num_questions: count, question_types: Object.keys(perTypeCounts), per_type_counts: perTypeCounts} : {})};
      const signature = JSON.stringify(payload);
      if (request.current?.signature !== signature) request.current = {signature, id: crypto.randomUUID()};
      setTracked(null);setSubmitError('');setSubmitting(true);setShowProgress(true);
      const created = await apiRequest<Generation>(endpoint, {method: 'POST', body: JSON.stringify({...payload, request_id: request.current.id})});
      setTracked({...created, requirement: effectiveRequirement});request.current = undefined;
      try {await refresh();} catch {setPollError('暂时无法读取进度，正在重新连接。');}
    } catch (e) {setError(failure(e));setSubmitError(failure(e));} finally {setBusy(false);setSubmitting(false);}
  };
  const retry = async (id: string) => {
    const previous = items.find(item => item.job_id === id) || tracked;
    setBusy(true);setError('');setSubmitError('');setTracked(previous);setShowProgress(true);setSubmitting(true);
    try {
      const next = await retryJob(id);
      if (previous) setTracked({...previous, job_id: next.edu_job_id, status: next.status, progress: next.progress, message: next.message});
      try {await refresh();} catch {setPollError('暂时无法读取进度，正在重新连接。');}
    }
    catch (e) {setError(failure(e));setSubmitError(failure(e));} finally {setBusy(false);setSubmitting(false);}
  };
  const view = (id: string) => {setShowProgress(false);location.hash = '/exam/' + encodeURIComponent(id);};
  // Keep failed jobs available to the progress dialog without listing them as papers.
  const visibleItems = items.filter(item => item.status === 'succeeded' || active(item.status));
  const matches = visibleItems.filter(item => `${item.title || ''} ${item.requirement}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <><Home live mode="exam" promptValue={requirement} onPromptChange={setRequirement}
    onCreate={() => void generate()} submitting={busy} createLabel={mode === 'mimic' ? '生成模拟试卷' : '生成习题'}
    canCreateFromUploads={uploads.length > 0}
    createDisabled={mode === 'mimic' ? !validTemplate : !validCounts}
    promptPlaceholder={prompts[mode]}
    preparationOptions={<div className="sl-module-options exam-options">
      <label>出题方式<select value={mode} disabled={busy} onChange={e => {setMode(e.target.value as typeof mode);setError('');}}><option value="custom">普通出题</option><option value="mimic">参考试卷仿题</option></select></label>
      <label className="exam-upload"><Icon name="upload" size={15} />上传资料<input type="file" aria-label="上传资料（单文件最多 30 MB）" multiple disabled={busy} accept=".pdf,.txt,.md,.markdown,.doc,.docx,.ppt,.pptx,.png,.jpg,.jpeg" onChange={e => {void upload(e.target.files);e.target.value = '';}} /></label>
      {mode === 'custom' && questionTypes.map(([type, label]) => <label key={type}>{label}<input type="number" min={0} max={100} value={counts[type]} disabled={busy} onChange={e => setCounts(previous => ({...previous, [type]: Number(e.target.value)}))} /></label>)}
    </div>}
    feedback={<>
      {!!uploads.length && <ul className="exam-files">{uploads.map((file, index) => <li key={file.document_id}><Icon name="report" size={15} /><span>{file.filename}</span><small>{mode === 'mimic' ? index === 0 ? '参考试卷' : '补充资料' : '学习资料'}</small><button className="sl-text-button" type="button" disabled={busy} aria-label={`移除 ${file.filename}`} onClick={() => setUploads(previous => previous.filter(p => p.document_id !== file.document_id))}>移除</button></li>)}</ul>}
      <p className="sl-module-feedback">{mode === 'mimic' ? '第一份材料为参考试卷（PDF），按原卷题型和题数仿题' : `直接描述或上传资料即可出题 · 共 ${count} 道题（可调整，合计 1–100 道）`} · 单文件最多 30 MB</p>
      {mode === 'mimic' && uploads.length > 0 && !validTemplate && <p role="alert" className="exam-error">第一份材料须为参考试卷 PDF，请移除前面的其他资料，或切换到普通出题。</p>}
      {mode === 'custom' && !validCounts && <p role="alert" className="exam-error">各题型数量须为非负整数，合计 1–100 道题。</p>}
      {error && <p role="alert" className="exam-error">{error}</p>}
      {pollError && !showProgress && <p role="alert" className="exam-error">{pollError}</p>}
    </>}
    resourceContent={<>
      <section aria-label="我的试卷">
        <div className="sl-section-heading"><h2><Icon name="clock" size={18} />我的试卷 <span>{visibleItems.length}</span></h2><div className="sl-inline">
          {search && <input className="sl-small-input" aria-label="搜索试卷" placeholder="搜索试卷…" autoFocus value={query} onChange={e => setQuery(e.target.value)} />}
          <button className="sl-icon-button" aria-label={search ? '关闭试卷搜索' : '搜索试卷'} onClick={() => {setSearch(!search);setQuery('');}}><Icon name={search ? 'close' : 'search'} size={18} /></button>
          {matches.length > 4 && <button className="sl-text-button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? '收起' : '查看全部'}</button>}
        </div></div>
        {loading ? <p className="sl-inline-empty" role="status">正在读取试卷…</p> : !matches.length ? <p className="sl-inline-empty">{query ? '没有找到相关试卷，换个关键词试试。' : '还没有试卷，描述出题范围或上传资料，开始准备下一场考试。'}</p> : <div className="sl-card-grid">{matches.slice(0, expanded ? undefined : 4).map(item => <article key={item.generation_id} className="exam-task">
          {item.status === 'succeeded' ? <GeneratedResourceCard title={item.title || item.requirement} label="模拟试卷" detail={item.practice_summary ? `${item.practice_summary.status === 'active' ? '练习中' : '已完成一轮'} · 已提交 ${item.practice_summary.submitted}/${item.practice_summary.total} 题` : '未开始作答'} meta={item.practice_summary?.status === 'active' ? '继续作答' : '查看试卷'} onOpen={() => void view(item.generation_id)} /> : <div className="exam-task-status"><span className="exam-status-label">{labels[item.status] || item.status}</span><h3>{item.title || item.requirement}</h3><p role="status">{item.message}</p><progress max="100" value={item.progress} aria-label="生成进度" /><button className="sl-text-button" onClick={() => {setTracked(item);setSubmitError('');setShowProgress(true);}}>查看进度 <Icon name="arrow" size={15} /></button></div>}
        </article>)}</div>}
      </section>

    </>}
  />{showProgress && <ExamGenerationProgress task={tracked} goal={tracked?.title || tracked?.requirement || effectiveRequirement} submitting={submitting}
    submitError={submitError} connectionError={pollError} busy={busy} onClose={() => setShowProgress(false)}
    onRetry={() => {if (tracked) void retry(tracked.job_id);}} onView={() => {if (tracked) void view(tracked.generation_id);}} />}</>;
}
