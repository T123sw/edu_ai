import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { apiRequest } from '../../stitch/api/client';
import { allowed, equal, read, type Action, type Intent, type Json, type Spec, type State, type View } from './model';
import './experiment.css';
import { presentExperimentPage } from './presentation';
import type { PagePackage } from './pagesModel';
import { ExperimentTutor } from './ExperimentTutor';
export type ExperimentPackage = { protocol: 'edu-experiment/1'; revision: string; spec: Spec; teaching: { status: string } } | PagePackage;
type Saved = { view: View };
const message = (e: unknown) => e instanceof Error ? e.message : '操作未完成';

function ActionForm({ action, disabled, send }: { action: Action; disabled: boolean; send: (intent: Intent) => void }) {
  const [input, setInput] = useState<State>(() => Object.fromEntries(action.parameters.map(p => [p.name, p.default])));
  return <form className="experiment-action" onSubmit={e => { e.preventDefault(); send({ type: 'action', command: { action: action.id, input } }); }}>
    <strong>{action.label}</strong><p>{action.description}</p>
    {action.parameters.map(p => <label key={p.name}>{p.label}{p.options.length ? <select disabled={disabled} value={JSON.stringify(input[p.name])} onChange={e => setInput({ ...input, [p.name]: JSON.parse(e.target.value) as Json })}>{p.options.map(v => <option key={JSON.stringify(v)} value={JSON.stringify(v)}>{String(v)}</option>)}</select> : p.type === 'boolean' ? <input type="checkbox" disabled={disabled} checked={!!input[p.name]} onChange={e => setInput({ ...input, [p.name]: e.target.checked })} /> : <input required disabled={disabled} type={p.type === 'string' ? 'text' : 'number'} min={p.minimum ?? undefined} max={p.maximum ?? undefined} step={p.type === 'integer' ? 1 : 'any'} value={String(input[p.name])} onChange={e => setInput({ ...input, [p.name]: p.type === 'string' ? e.target.value : e.target.value === '' ? '' : Number(e.target.value) })} />}</label>)}
    <button disabled={disabled}>{action.label}</button>
  </form>;
}

export function Experiment({ id, html, experiment }: { id: string; html: string; experiment: ExperimentPackage }) {
  const { user } = useAuth();
  const spec = experiment.spec, base = `/api/practice/${encodeURIComponent(id)}/experiment`;
  const key = `edu-experiment:${user?.username}:${id}:${experiment.revision}`;
  const frame = useRef<HTMLIFrameElement>(null), current = useRef<View>(), savedSeq = useRef(-1), saving = useRef<Promise<void>>();
  const nonce = useMemo(() => crypto.randomUUID(), []);
  const [view, setView] = useState<View>(), [loaded, setLoaded] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(''), [status, setStatus] = useState('正在恢复记录');
  const [panel, setPanel] = useState('experiment');
  const [suggestion, setSuggestion] = useState(0), [showSuggestion, setShowSuggestion] = useState(true);
  const [focusId, setFocusId] = useState<string>();
  const [frameEpoch, setFrameEpoch] = useState(0);
  const [frameHeight, setFrameHeight] = useState(640);
  const teaching = useRef<HTMLElement>(null);
  const [teachingPosition, setTeachingPosition] = useState<{ top: number; phase: string; epoch: number }>();
  const teachingTop = teachingPosition?.phase === (view?.phase || 'demonstrate') && teachingPosition?.epoch === frameEpoch ? teachingPosition.top : undefined;
  const reportTeachingSize = useCallback(() => {
    const height = teaching.current?.getBoundingClientRect().height;
    if (!height) return;
    const stageTop = (frame.current?.getBoundingClientRect().top || 0) + window.scrollY;
    const visualHeight = Math.max(160, Math.min(420, window.innerHeight * .4, window.innerHeight - stageTop - height - 48));
    frame.current?.contentWindow?.postMessage({ type: 'edu-experiment-teaching-size', height, visualHeight }, '*');
  }, []);
  useEffect(() => {
    if (teachingTop === undefined || !teaching.current) return;
    const observer = new ResizeObserver(reportTeachingSize);
    observer.observe(teaching.current); window.addEventListener('resize', reportTeachingSize); reportTeachingSize();
    return () => { observer.disconnect(); window.removeEventListener('resize', reportTeachingSize); };
  }, [teachingTop, panel, view?.phase, frameEpoch, reportTeachingSize]);
  const flush = useCallback((): Promise<void> => {
    if (saving.current) return saving.current;
    saving.current = (async () => {
      while (current.current && current.current.seq !== savedSeq.current) {
        const value = current.current;
        setStatus('正在保存');
        await apiRequest<Saved>(`${base}/runs`, { method: 'POST', body: JSON.stringify({ expected_seq: savedSeq.current, view: value }) });
        savedSeq.current = value.seq;
      }
      setStatus('已保存');
    })().catch(e => { setStatus('尚未同步'); setError(message(e)); throw e; }).finally(() => { saving.current = undefined; });
    return saving.current;
  }, [base]);
  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const saved = await apiRequest<Saved | null>(`${base}/runs/latest`);
        let restored = saved?.view;
        if (restored && restored.revision !== experiment.revision) throw Error('保存记录属于其他实验版本');
        savedSeq.current = restored?.seq ?? -1;
        const text = localStorage.getItem(key); const draft = text ? JSON.parse(text) as View : undefined;
        if (draft && draft.revision === experiment.revision) {
          if (!restored) restored = draft;
          else {
            const [older, newer] = draft.seq < restored.seq ? [draft, restored] : [restored, draft];
            const sameHistory = draft.run_id === restored.run_id && equal(newer.events.slice(0, older.seq), older.events) && Object.entries(older.snapshots).every(([k, value]) => equal(newer.snapshots[k], value));
            if (!sameHistory || draft.seq === restored.seq && !equal(draft, restored)) throw Error('本地与服务器记录发生冲突。请先导出本地记录，再读取服务器进度。');
            if (draft.seq > restored.seq) restored = draft;
          }
        }
        if (!alive) return; current.current = restored; setView(restored); setLoaded(true); setStatus('记录已读取');
      } catch (e) { if (alive) setError(message(e)); }
    })();
    return () => { alive = false; };
  }, [base, key, experiment.revision]);
  useEffect(() => {
    const receive = (event: MessageEvent) => {
      if (event.source !== frame.current?.contentWindow) return;
      if (event.data?.type === 'edu-experiment-layout' && Number.isFinite(event.data.height)) {
        setFrameHeight(Math.max(440, Math.min(100000, Math.ceil(event.data.height))));
        if (Number.isFinite(event.data.teachingTop) && event.data.teachingTop >= 0) {
          const top = Math.ceil(event.data.teachingTop);
          setTeachingPosition(previous => previous?.top === top && previous.phase === (current.current?.phase || 'demonstrate') && previous.epoch === frameEpoch ? previous : { top, phase: current.current?.phase || 'demonstrate', epoch: frameEpoch });
        }
        reportTeachingSize();
        return;
      }
      if (event.data?.type === 'edu-experiment-ready') frame.current?.contentWindow?.postMessage({ type: 'edu-experiment-init', nonce, view: current.current }, '*');
      if (event.data?.type === 'edu-experiment-view' && event.data.nonce === nonce) {
        const next = event.data.view as View;
        if (!next || next.revision !== experiment.revision || !Array.isArray(next.events) || next.events.length > 2000) return;
        // Leave historical practice through the runtime so its event history stays intact.
        if (next.phase === 'guided' && !event.data.busy) frame.current?.contentWindow?.postMessage({ type: 'edu-experiment-intent', nonce, intent: { type: 'phase', phase: 'explore' } }, '*');
        setBusy(!!event.data.busy); if (event.data.error) setError(String(event.data.error));
        if (!current.current || current.current.seq !== next.seq) {
          current.current = next; setView(next);
          try { localStorage.setItem(key, JSON.stringify(next)); } catch { setError('浏览器未能保存离线副本，请保持网络连接并导出记录'); }
        }
      }
    };
    window.addEventListener('message', receive);
    return () => window.removeEventListener('message', receive);
  }, [nonce, key, experiment.revision, frameEpoch, reportTeachingSize]);
  useEffect(() => { if (!view) return; const timer = setTimeout(() => void flush().catch(() => {}), 300); return () => clearTimeout(timer); }, [view, flush]);
  // Sustained animation updates must not indefinitely postpone persistence.
  useEffect(() => { const timer = setInterval(() => void flush().catch(() => {}), 2000); return () => clearInterval(timer); }, [flush]);
  useEffect(() => {
    const leave = (event: BeforeUnloadEvent) => { if (current.current && current.current.seq !== savedSeq.current) { event.preventDefault(); event.returnValue = ''; } };
    window.addEventListener('beforeunload', leave); return () => window.removeEventListener('beforeunload', leave);
  }, []);
  const send = (intent: Intent) => { if (!busy && view) { setError(''); frame.current?.contentWindow?.postMessage({ type: 'edu-experiment-intent', nonce, intent }, '*'); } };
  const download = () => {
    const blob = new Blob([localStorage.getItem(key) || JSON.stringify(current.current || {})], { type: 'application/json' });
    const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = `${id}-experiment.json`; a.click(); URL.revokeObjectURL(url);
  };
  const newRound = async () => {
    try { await flush(); current.current = undefined; savedSeq.current = -1; localStorage.removeItem(key); setView(undefined); setError(''); setFrameEpoch(n => n + 1); } catch (e) { setError(message(e)); }
  };
  const demo = view?.phase === 'demonstrate' ? spec.demo_steps[view.index] : undefined;
  const actions = view && spec.protocol === 'edu-experiment/1' ? allowed(spec, view) : [];
  const demoComplete = experiment.protocol === 'edu-experiment/2' && experiment.spec.action_protocol ? view?.verdict === 'complete' : !demo;
  const pagePhase = view?.phase || 'demonstrate';
  const sourceHtml = experiment.protocol === 'edu-experiment/2' ? experiment.pages[pagePhase] : html;
  const pageHtml = useMemo(() => experiment.protocol === 'edu-experiment/2' ? presentExperimentPage(sourceHtml || '') : sourceHtml, [sourceHtml, experiment.protocol]);
  const phaseLabel = pagePhase === 'demonstrate' ? '原理演示' : '自由探索';
  const stepCount = spec.demo_steps.length;
  const prompts = spec.exploration_prompts.filter(p => p.trim());
  const demonstrationContent = view?.phase === 'demonstrate' ? <>
    <section className="experiment-current experiment-demo-summary">
      <div className="experiment-kicker">{demoComplete ? '演示完成' : view.index ? '本步讲解' : '开始观察'}</div>
      <div className="experiment-feedback" role="status">{demoComplete ? view.feedback || '演示已完成，试着改变条件，看看结果会怎样。' : view.index ? view.feedback || '观察刚才操作带来的变化。' : demo?.before || '点击下一步，开始观察实验。'}</div>
    </section>
    {!demoComplete && view.index > 0 && <p className="experiment-next-preview"><span>接下来：</span>{demo?.title || '继续观察实验变化'}</p>}
  </> : null;
  const demonstrationButtons = view?.phase === 'demonstrate' ? <div className="experiment-buttons"><button disabled={busy || !view.index} onClick={() => send({ type: 'back' })}>上一步</button><button className="experiment-text-button" disabled={busy} onClick={() => send({ type: 'replay' })}>重新演示</button>{!demoComplete ? <button className="experiment-primary" disabled={busy} onClick={() => send({ type: 'next' })}>下一步</button> : <button className="experiment-primary" disabled={busy} onClick={() => send({ type: 'phase', phase: 'explore' })}>进入自由探索</button>}</div> : null;
  const teachingControls = (
      <section ref={teaching} style={teachingTop === undefined ? undefined : { position: 'absolute', top: teachingTop, left: 0, right: 0 }} className={`experiment-controls${pagePhase === 'demonstrate' ? ' experiment-controls-demonstrate' : ''}`} aria-label="本阶段操作">
        <header className="experiment-teaching-heading"><h2>{pagePhase === 'demonstrate' ? '实验讲解' : '试着探索'}</h2>{pagePhase === 'demonstrate' && <span>观察变化 · 理解原理</span>}</header>
        {error && <p role="alert" className="experiment-error">{error}</p>}
        {demonstrationContent}
        {demonstrationButtons}
        {view?.phase === 'guided' && <p role="status">正在保留原有记录并进入自由探索…</p>}
        {view?.phase === 'explore' && <>
          {showSuggestion && <div className="experiment-suggestion" aria-live="polite"><span className="experiment-suggestion-label">可以试试{prompts.length > 1 ? ` · ${suggestion % prompts.length + 1}/${prompts.length}` : ''}</span><p>{prompts.length ? prompts[suggestion % prompts.length] : '从一个可调整的条件开始，每次只改一项，再运行实验观察变化。'}</p></div>}
          <div className="experiment-explore-buttons">
            {showSuggestion && prompts.length > 1 && <button className="experiment-text-button" onClick={() => setSuggestion(n => n + 1)}>换个方向 ↻</button>}
            <button className="experiment-text-button" aria-expanded={showSuggestion} onClick={() => setShowSuggestion(value => !value)}>{showSuggestion ? '收起建议' : '看看建议'}</button>
          </div>
        </>}
        {spec.actions.filter(a => view?.phase === 'explore' && actions.includes(a.id)).map(a => <ActionForm key={`${view?.phase}:${view?.attempt_id}:${a.id}`} action={a} disabled={busy} send={send} />)}
      </section>
  );
  return <main className={`experiment-page experiment-panel-${panel}`}>
    <nav className="experiment-mobile" aria-label="实验面板">{[['steps', '步骤'], ['experiment', '实验'], ['teaching', 'AI 对话']].map(([value, label]) => <button key={value} aria-pressed={panel === value} onClick={() => setPanel(value)}>{label}</button>)}</nav>
    <aside className="experiment-steps">
      <a className="experiment-back" href="#/practice">← 我的实验</a>
      <div className="experiment-kicker">互动实验</div><h1>{spec.title}</h1>
      <nav aria-label="实验阶段">{([['demonstrate', '原理演示'], ['explore', '自由探索']] as const).map(([phase, label], index) => <button key={phase} aria-current={view?.phase === phase ? 'step' : undefined} disabled={busy || !view} onClick={() => { send({ type: 'phase', phase }); setPanel('experiment'); }}><span className="experiment-phase-number">{index + 1}</span> {label}<span className="experiment-phase-arrow" aria-hidden="true">›</span></button>)}</nav>
      <p className="experiment-phase-note">{pagePhase === 'explore' ? '改变条件，观察与比较。' : '逐步观察，理解每一次变化。'}</p>
      <div className="experiment-sync"><span className="experiment-save-status" role="status">{status}</span><details><summary>实验记录与管理</summary><div><button onClick={() => void flush().catch(() => {})}>重新同步</button><button onClick={download}>导出记录</button><button disabled={busy || !view} onClick={() => void newRound()}>新一轮实验</button>{!loaded && <button onClick={() => { localStorage.removeItem(key); location.reload(); }}>读取服务器进度</button>}</div></details></div>
    </aside>
    <section className="experiment-center" aria-label="实验工作区">
      <header className="experiment-workspace-heading"><h2>{phaseLabel}</h2>{pagePhase === 'demonstrate' && view ? <span className="experiment-progress">{demoComplete ? '演示完成' : `步骤 ${view.index + 1} / ${stepCount}`}</span> : <span className="experiment-progress">改变条件，发现规律</span>}</header>
      <div className="experiment-stage-and-teaching">
      <div className="experiment-stage" style={experiment.protocol === 'edu-experiment/2' ? { height: frameHeight } : undefined}>{loaded ? <iframe key={`${frameEpoch}:${experiment.protocol === 'edu-experiment/2' ? pagePhase : 'single'}`} ref={frame} title="实验展示" sandbox="allow-scripts" referrerPolicy="no-referrer" srcDoc={pageHtml} /> : <p>正在恢复实验…</p>}</div>
      {teachingControls}
      </div>
      <section className="experiment-details" aria-label="实验数据与记录">
      {!!spec.state_fields.length && <dl>{spec.state_fields.map(f => <div key={f.path.join('.')}><dt title={f.description}>{f.label}</dt><dd>{JSON.stringify(read(view?.state, f.path)) ?? '—'} {f.unit}</dd></div>)}</dl>}
      <details className="experiment-background"><summary>实验背景</summary><p>{spec.overview}</p></details>
      <details className="experiment-history"><summary>操作记录 <span>{view?.events.filter(e => e.type === 'action').length || 0}</span></summary><ol>{view?.events.filter(e => e.type === 'action' || e.type === 'attempt_submitted').slice(-20).map(e => <li key={e.id}>{e.actor === 'system' ? '系统演示' : '你的操作'}：{spec.actions.find(a => a.id === e.command?.action)?.label || e.command?.action || e.feedback} <button className="experiment-text-button" onClick={() => { setFocusId(e.id); setPanel('teaching'); }}>问这一步</button></li>)}</ol><small>完整记录包含在导出文件和教学上下文中。</small></details>
      </section>
    </section>
    <aside className="experiment-teaching" aria-label="AI 对话">
      <ExperimentTutor key={key} base={base} storageKey={key} view={view} focus={view?.events.find(event => event.id === focusId)} clearFocus={() => setFocusId(undefined)} />
    </aside>
  </main>;
}
