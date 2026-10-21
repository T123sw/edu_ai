import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { apiRequest } from '../stitch/api/client';
import type { JobRecord } from '../jobs/types';
import { Icon } from '../selfLearning/ui';
import ReactMarkdown from 'react-markdown';
import { practiceDocument } from './presentation';
import './practice.css';
import { PracticeGenerationProgress } from './PracticeGenerationProgress';
import { Experiment, type ExperimentPackage } from './experiment/Experiment';
import { useGuidance } from './guidance/useGuidance';
import { currentAttempt, reportedState, type Manifest } from './guidance/model';

type State = { parameters?: Record<string, unknown>; results?: Record<string, unknown> };
type Journal = { observations: { state: State; step: number; note: string; created_at: number }[]; messages: { role: string; content: string; session_id?: string; step_id?: string; attempt_id?: string }[] };
type Artifact = { html: string; experiment?: ExperimentPackage; guidance?: Manifest; guidance_version?: number; presentation?: string; plan: { concept_name: string; concept_overview: string; steps: { title: string; instruction: string; question: string }[] } };
type Detail = { id: string; job: JobRecord; artifact: Artifact | null; journal: Journal };
type Item = { id: string; topic: string; status: string };
const base = '/api/practice';
const statuses: Record<string, string> = { queued: '等待生成', running: '正在生成', succeeded: '可以体验', failed: '生成失败', canceled: '已取消', cancel_requested: '取消中' };
const errorText = (e: unknown) => e instanceof Error ? e.message : '请求未完成，请重试';
const values = (data?: Record<string, unknown>) => Object.entries(data || {}).map(([k, v]) => `${k}：${typeof v === 'object' ? JSON.stringify(v) : String(v)}`).join(' · ');

export function Practice({ id, initialTopic, pendingContent }: { id?: string; initialTopic: string; pendingContent?: ReactNode }) {
  const [topic, setTopic] = useState(initialTopic);
  const [items, setItems] = useState<Item[]>([]);
  const [detail, setDetail] = useState<Detail>();
  const [error, setError] = useState('');
  const [pollRevision, setPollRevision] = useState(0);
  const [busy, setBusy] = useState('');
  const [step, setStep] = useState(0);
  const [state, setState] = useState<State>({});
  const [runtimeError, setRuntimeError] = useState('');
  const [note, setNote] = useState('');
  const [question, setQuestion] = useState('');
  const [notice, setNotice] = useState('');
  const [focused, setFocused] = useState(false);
  const [panel, setPanel] = useState<'steps' | 'experiment' | 'chat'>('experiment');
  const [centerTab, setCenterTab] = useState<'experiment' | 'observations'>('experiment');
  const [frameHeight, setFrameHeight] = useState(640);
  const messagesEnd = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLIFrameElement>(null);
  const guidance = useGuidance(id, detail?.artifact?.guidance || undefined, frame);
  const activeContext = useRef('');
  activeContext.current = guidance.session ? `${guidance.session.active}:${currentAttempt(guidance.session).id}` : String(step);
  const submitted = useRef(false);
  const requestId = useRef(crypto.randomUUID());
  const create = useCallback(async (value: string) => {
    if (!value.trim() || submitted.current) return;
    submitted.current = true; setBusy('create'); setError('');
    try {
      const result = await apiRequest<{ id: string }>(base, { method: 'POST', body: JSON.stringify({ topic: value, request_id: requestId.current }) });
      location.hash = `/practice/${result.id}`;
    } catch (e) { submitted.current = false; setError(errorText(e)); }
    finally { setBusy(''); }
  }, []);
  useEffect(() => { if (!id && initialTopic) void create(initialTopic); }, [id, initialTopic, create]);
  useEffect(() => {
    let active = true; let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        if (id) {
          const next = await apiRequest<Detail>(`${base}/${encodeURIComponent(id)}`);
          if (!active) return;
          setDetail(next); setError('');
          if (['queued', 'running', 'cancel_requested'].includes(next.job.status)) timer = setTimeout(refresh, 2500);
        } else {
          const result = await apiRequest<{ items: Item[] }>(base);
          if (active) { setItems(result.items); if (result.items.some(item => ['queued', 'running', 'cancel_requested'].includes(item.status))) timer = setTimeout(refresh, 5000); }
        }
      } catch (e) { if (active) { setError(errorText(e)); timer = setTimeout(refresh, 5000); } }
    };
    void refresh();
    return () => { active = false; clearTimeout(timer); };
  }, [id, pollRevision]);
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (!frame.current || event.source !== frame.current.contentWindow) return;
      const data = event.data;
      if (data?.type === 'edu-practice-exit-focus') setFocused(false);
      if (data?.type === 'edu-practice-step' && Number.isInteger(data.step) && data.step >= 0 && data.step < (detail?.artifact?.plan.steps.length || 0)) setStep(data.step);
      if (data?.type === 'edu-practice-size' && typeof data.height === 'number' && Number.isFinite(data.height)) setFrameHeight(Math.max(320, Math.min(4000, Math.ceil(data.height))));
      if (data?.type === 'edu-practice-error') setRuntimeError(String(data.message).slice(0, 300));
      if (data?.type === 'edu-practice-state' && data.state && typeof data.state === 'object') {
        try { if (JSON.stringify(data.state).length <= 12000) setState(data.state as State); } catch { /* Ignore invalid sandbox payloads. */ }
      }
    };
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, [detail?.artifact?.plan.steps.length]);
  const save = async () => {
    setBusy('save'); setError(''); setNotice('');
    try {
      const journal = await apiRequest<Journal>(`${base}/${id}/observations`, { method: 'POST', body: JSON.stringify({ state: guidance.session && detail?.artifact?.guidance ? reportedState(detail.artifact.guidance, guidance.session) : state, step: detail?.artifact?.guidance ? guidance.index : step, note, ...(detail?.artifact?.guidance ? await guidance.context() : {}) }) });
      setDetail(previous => previous && { ...previous, journal }); setNote(''); setNotice('这次操作的参数、结果和笔记已保存。');
    } catch (e) { setError(errorText(e)); } finally { setBusy(''); }
  };
  const ask = async (text: string) => {
    if (!text.trim() || busy) return;
    setBusy('ask'); setError('');
    const requestContext = activeContext.current;
    try {
      const journal = await apiRequest<Journal>(`${base}/${id}/ask`, { method: 'POST', body: JSON.stringify({ question: text, state: guidance.session && detail?.artifact?.guidance ? reportedState(detail.artifact.guidance, guidance.session) : state, step: detail?.artifact?.guidance ? guidance.index : step, ...(detail?.artifact?.guidance ? await guidance.context() : {}) }) });
      setDetail(previous => previous && { ...previous, journal }); if (activeContext.current === requestContext) setQuestion('');
    } catch (e) { setError(errorText(e)); } finally { setBusy(''); }
  };
  useEffect(() => {
    const exit = (event: KeyboardEvent) => { if (event.key === 'Escape') setFocused(false); };
    window.addEventListener('keydown', exit);
    return () => window.removeEventListener('keydown', exit);
  }, []);
  useEffect(() => {
    const end = messagesEnd.current;
    if (end?.parentElement) end.parentElement.scrollTop = detail?.journal.messages.length || busy === 'ask' ? end.parentElement.scrollHeight : 0;
  }, [detail?.journal.messages.length, busy]);
  const artifact = detail?.artifact;
  const native = artifact?.presentation === 'maic-ui-native-v1';
  const sourceHtml = artifact?.html;
  const documentHtml = useMemo(() => sourceHtml ? practiceDocument(sourceHtml, native) : '', [sourceHtml, native]);
  const steps = artifact?.guidance ? [...artifact.guidance.steps, { id: 'explore', title: '完整实验 · 自由探索', instruction: '全部按钮与配置已开放。改变输入、运行并比较结果，探索记录与分步记录分别保存。', question: '改变一个条件，结果会怎样变化？' }] : artifact?.plan.steps;
  const selectedStep = artifact?.guidance ? guidance.index : step;
  const current = steps?.[selectedStep];
  const selectStep = (index: number) => { if (artifact?.guidance) guidance.enter(index === artifact.guidance.steps.length ? 'explore' : artifact.guidance.steps[index].id); else setStep(index); setPanel('experiment'); };
  const observed = artifact?.guidance && guidance.session ? reportedState(artifact.guidance, guidance.session) : state;
  const visibleMessages = detail?.journal.messages.filter(m => !artifact?.guidance || (m.session_id === guidance.sessionId && m.step_id === guidance.session?.active && m.attempt_id === (guidance.session && currentAttempt(guidance.session).id))) || [];
  if (artifact?.experiment && id) return <Experiment key={`${id}:${artifact.experiment.revision}`} id={id} html={artifact.html} experiment={artifact.experiment} />;
  if (id && !artifact) return <>{pendingContent}<PracticeGenerationProgress mode="simulation" job={detail?.job} error={error}
    goal={String(detail?.job.input_summary?.topic || '')} onClose={() => { location.hash = '/practice'; }}
    onJobChange={job => { setDetail(previous => previous && { ...previous, job }); setPollRevision(value => value + 1); }} /></>;
  return <main className={`practice-page ${artifact ? 'practice-detail' : ''} ${focused ? 'practice-focused' : ''} ${native ? 'practice-native' : ''} practice-panel-${panel}`}>
    {!artifact && <div className="practice-heading">
      <a className="practice-back" href={id ? '#/practice' : '#/'}><Icon name="back" size={15} /><span>{id ? '我的实验' : '学习首页'}</span></a>
      <div className="practice-title"><h1>互动实验室</h1></div>
    </div>}
    {artifact && <nav className="practice-mobile-panels" aria-label="实验工作区视图">{([['steps', '步骤'], ['experiment', '实验'], ['chat', '问答']] as const).map(([key, label]) => <button key={key} aria-pressed={panel === key} onClick={() => { setPanel(key); if (key !== 'experiment') setFocused(false); }}>{label}</button>)}</nav>}
    {error && <div className="practice-error" role="alert">{error}</div>}
    {!id && <>
      <form className="practice-create" onSubmit={e => { e.preventDefault(); void create(topic); }}><label htmlFor="practice-topic">想动手探索什么？</label><textarea id="practice-topic" value={topic} onChange={e => { setTopic(e.target.value); requestId.current = crypto.randomUUID(); }} maxLength={2000} placeholder="例如：改变摩擦系数和初速度，观察小车能滑多远" /><div><span>系统会设计步骤、计算模型和可操作的实验。</span><button disabled={!topic.trim() || !!busy}>{busy ? '正在提交…' : '生成实验'}</button></div></form>
      <div className="practice-examples">试试这些主题：{['摩擦力与小车滑行距离', '学习率如何影响梯度下降', '排队人数与服务效率'].map(value => <button key={value} onClick={() => { setTopic(value); requestId.current = crypto.randomUUID(); }}>{value}</button>)}</div>
      <h2>我的实验</h2><div className="practice-list">{items.map(item => <a key={item.id} href={`#/practice/${item.id}`}><span>{statuses[item.status] || item.status}</span><h3>{item.topic}</h3><small>查看实验 →</small></a>)}</div>{!items.length && <p className="practice-muted">生成的实验会保存在这里，之后可以随时回来体验。</p>}
    </>}
    {artifact && current && <div className="practice-workspace">
      <aside className="practice-directory" aria-label="实验步骤">
        <div className="practice-rail-heading practice-directory-heading"><a href="#/practice" aria-label="返回我的实验" title="返回我的实验"><Icon name="back" size={17} /></a><h1 title={artifact.plan.concept_name}>{artifact.plan.concept_name}</h1></div>
        <div className="practice-directory-scroll">
          <div className="practice-route-intro"><h2>实验步骤</h2><span>{String(selectedStep + 1).padStart(2, '0')} / {String(steps!.length).padStart(2, '0')}</span></div>
          <nav className="practice-steps" aria-label="探索路线"><ol>{steps!.map((item, index) => <li key={index}><button disabled={!!artifact.guidance && (guidance.pending || !guidance.session || (index > 0 && index < artifact.guidance.steps.length && !guidance.session.attempts[artifact.guidance.steps[index - 1].id]?.complete))} aria-current={index === selectedStep ? 'step' : undefined} onClick={() => selectStep(index)}><span className="practice-step-number">{String(index + 1).padStart(2, '0')}</span><span>{item.title}<small>{index === selectedStep ? '当前步骤' : artifact.guidance && index < artifact.guidance.steps.length && guidance.session?.attempts[artifact.guidance.steps[index].id]?.complete ? '操作完成' : artifact.guidance && index === artifact.guidance.steps.length ? '全部操作与配置' : `第 ${index + 1} 步`}</small></span></button></li>)}</ol></nav>
        </div>
      </aside>
      <section className="practice-main" aria-label="实验与观察">
        <div className="practice-center-toolbar"><nav aria-label="实验内容"><button aria-pressed={centerTab === 'experiment'} onClick={() => setCenterTab('experiment')}><Icon name="slides" size={15} />交互实验</button><button aria-pressed={centerTab === 'observations'} onClick={() => setCenterTab('observations')}><Icon name="report" size={15} />观察记录{detail.journal.observations.length > 0 && <span>{detail.journal.observations.length}</span>}</button></nav><button className="practice-focus-toggle" aria-pressed={focused} onClick={() => { setFocused(!focused); setPanel('experiment'); }}><Icon name="slides" size={15} />{focused ? '退出专注' : '专注实验'}</button></div>
        <div className="practice-center-scroll" hidden={centerTab !== 'experiment'}>
          <section className="practice-stage" aria-label="实验操作区">{artifact.guidance && <div className="practice-sync" role="status"><span>{guidance.status}</span>{guidance.problem && <span>{guidance.problem}</span>}{['保存冲突','未同步','恢复失败'].includes(guidance.status) && <><button onClick={() => void guidance.flush().catch(() => {})}>重新同步</button><button onClick={guidance.exportDraft}>导出本地记录</button><button onClick={() => void guidance.restore()}>读取已保存进度</button></>}</div>}{runtimeError && <div className="practice-error" role="alert">实验运行异常：{runtimeError}。可尝试重置，或重新生成实验。</div>}<iframe ref={frame} title="互动实验" sandbox="allow-scripts" referrerPolicy="no-referrer" style={native ? undefined : { height: frameHeight }} srcDoc={documentHtml} /></section>
          {!native && <div className="practice-experiment-footnote"><span>留下这次操作的参数、结果与发现。</span><button onClick={() => setCenterTab('observations')}><Icon name="report" size={14} />记录本次观察<Icon name="arrow" size={14} /></button></div>}
        </div>
        <div className="practice-center-scroll practice-notebook" hidden={centerTab !== 'observations'}>
          <div className="practice-notebook-heading"><span>实验手记</span><h2>把观察变成发现</h2><p>保存当前参数与结果，比较每次尝试有什么不同。</p></div>
          <section className="practice-observation"><div className="practice-state"><div className="practice-section-label"><Icon name="studio" size={16} /><h2>本次观察</h2><span>随操作更新</span></div>{Object.keys(observed.results || {}).length ? <dl className="practice-metrics">{Object.entries(observed.results || {}).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{typeof value === 'number' ? new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 4 }).format(value) : typeof value === 'object' ? JSON.stringify(value) : String(value)}</dd></div>)}</dl> : <p className="practice-muted">操作实验后，计算结果会显示在这里。</p>}<details className="practice-parameters"><summary>查看当前参数</summary><p>{values(observed.parameters) || '等待实验参数…'}</p></details></div><div className="practice-record"><label htmlFor="practice-note"><Icon name="report" size={16} />记录你的发现</label><textarea id="practice-note" value={note} onChange={e => setNote(e.target.value)} maxLength={2000} placeholder="改了什么参数？结果有什么不同？" /><div><span>同时保存当前参数与结果</span><button disabled={!!busy || !Object.keys(observed.results || {}).length} onClick={() => void save()}>{busy === 'save' ? '保存中…' : '保存本次观察'}</button></div>{notice && <p role="status">{notice}</p>}</div></section>
          <section className="practice-history"><div className="practice-section-label"><Icon name="clock" size={16} /><h2>观察记录</h2><span>{detail.journal.observations.length} 条</span></div>{!detail.journal.observations.length ? <p className="practice-muted">每次保存的发现会留在这里，方便比较不同参数下的结果。</p> : <div className="practice-history-grid">{detail.journal.observations.map((o, i) => <article key={`${o.created_at}-${i}`}><div><strong>观察 {String(i + 1).padStart(2, '0')} · 第 {o.step + 1} 步</strong><time>{new Date(o.created_at * 1000).toLocaleString()}</time></div>{o.note && <blockquote>{o.note}</blockquote>}<p>{values(o.state.results)}</p><details><summary>实验参数</summary><p>{values(o.state.parameters)}</p></details></article>)}</div>}</section>
        </div>
      </section>
      <aside id="practice-guide" className="practice-guide" aria-label="实验问答">
        <div className="practice-rail-heading practice-guide-heading"><span className="practice-agent-icon"><Icon name="spark" size={18} /></span><div><h2>AI 实验伙伴</h2><p>一起观察，一起想清楚</p></div></div>
        <details className="practice-task" key={selectedStep} open><summary>本步任务<span>实验设计</span></summary><p>{current.instruction}</p><div className="practice-reflection"><span>观察与思考</span><p>{current.question}</p></div></details>
        <div className="practice-messages" aria-live="polite">
          <div className="practice-message assistant practice-intro-message"><strong>实验伙伴</strong><div><ReactMarkdown>{artifact.plan.concept_overview}</ReactMarkdown></div></div>
          {visibleMessages.map((m, i) => <div key={i} className={`practice-message ${m.role}`}><strong>{m.role === 'user' ? '你' : '实验伙伴'}</strong><div>{m.role === 'assistant' ? <ReactMarkdown>{m.content}</ReactMarkdown> : <p>{m.content}</p>}</div></div>)}
          {busy === 'ask' && <p className="practice-thinking" role="status">正在结合实验状态思考…</p>}<div ref={messagesEnd} />
        </div>
        <div className="practice-guide-composer"><button className="practice-hint" disabled={!!busy} onClick={() => void ask('请结合我当前的实验状态，给我一个下一步操作提示，不直接告诉我结论。')}><Icon name="spark" size={14} />给我一个操作提示<Icon name="arrow" size={14} /></button><form onSubmit={e => { e.preventDefault(); void ask(question); }}><textarea aria-label="向实验伙伴提问" value={question} onChange={e => setQuestion(e.target.value)} maxLength={2000} placeholder="这一步为什么会这样？" /><div><span>结合当前步骤与实验结果</span><button disabled={!!busy || !question.trim()} aria-label="发送问题"><Icon name="arrow" size={16} /></button></div></form></div>
      </aside>
    </div>}
  </main>;
}
