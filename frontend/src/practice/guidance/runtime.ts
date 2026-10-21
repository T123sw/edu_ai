import { allowed, createSession, currentAttempt, EXPLORE, reduceSession, reportedState, type Command, type Manifest, type Session } from './model';

declare global {
  interface Window {
    EduGuidance: { register: (adapter: { render: (model: ReturnType<typeof currentAttempt>['model'], context: { step: string; kind: string }) => void }) => void; dispatch: (action: string, value?: unknown) => void; inspect: () => Session | undefined };
    EduPractice: { report: (value: Record<string, unknown>) => void };
    __practiceManifest: Manifest;
  }
}
const manifest = window.__practiceManifest;
const uid = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), byte => byte.toString(16).padStart(2, '0')).join('');
let session: Session | undefined, channel = '', ready = false, playing = false, timer: ReturnType<typeof setTimeout> | undefined;
let announcementTimer: ReturnType<typeof setInterval>;
let renderer: ((model: ReturnType<typeof currentAttempt>['model'], context: { step: string; kind: string }) => void) | undefined;
const replies = new Map<string, unknown>();
const send = (type: string, payload: Record<string, unknown> = {}) => parent.postMessage({ type: `edu-guidance-${type}`, channel, revision: manifest.revision, ...payload }, '*');
const stop = () => { playing = false; clearTimeout(timer); };
const escape = (value: unknown) => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
function button(action: string, text: string, value?: unknown, disabled = false) {
  return `<button type="button" data-guidance-action="${action}" ${value !== undefined ? `data-value="${escape(JSON.stringify(value))}"` : ''} ${disabled ? 'disabled' : ''}>${text}</button>`;
}
function render() {
  if (!session || !renderer) return;
  const attempt = currentAttempt(session), m = attempt.model, explore = session.active === EXPLORE;
  renderer(structuredClone(m), { step: session.active, kind: manifest.kind });
  const host = document.querySelector('[data-guidance-controls]');
  const feedback = document.querySelector('[data-guidance-feedback]');
  if (!host || !feedback) throw Error('实验缺少操作或反馈容器');
  const f = session.feedback;
  feedback.setAttribute('data-outcome', f.outcome);
  feedback.innerHTML = `<strong>${escape(f.summary)}</strong><p>${escape(f.explanation)}</p><p class="guidance-next">${escape(f.next)}</p>`;
  let html = '';
  if (manifest.kind === 'quicksort') {
    if (allowed(manifest, session, 'select') && m.phase === 'select') {
      html += '<p>选择基准元素</p><div class="guidance-values">' + m.array.map((n, i) => button('select', `${n}${m.selected === i ? ' ✓' : ''}`, i)).join('') + '</div>';
      html += button('confirm', '确认基准', undefined, m.selected < 0);
    }
    if (allowed(manifest, session, 'left') && m.phase === 'scan') {
      html += `<p>当前元素 <strong>${m.array[m.scan]}</strong>，基准 <strong>${m.pivot}</strong></p>`;
      html += button('left', '小于等于基准') + button('right', '大于基准');
    }
    if (allowed(manifest, session, 'range') && m.phase === 'range') html += '<p>选择待处理区间</p>' + m.stack.map(([lo, hi], i) => button('range', `区间 ${lo + 1}–${hi + 1}`, i)).join('');
  }
  const canAdvance = allowed(manifest, session, 'advance') && !(session.active === 'partition' && m.phase === 'scan');
  if (canAdvance) html += button('advance', m.phase === 'place' ? '基准归位' : '单步执行', undefined, attempt.complete && !explore);
  if (allowed(manifest, session, 'run')) html += button(playing ? 'pause' : 'run', playing ? '暂停' : '运行', undefined, !playing && (m.phase === 'done' || (attempt.complete && !explore)));
  if (allowed(manifest, session, 'run')) html += `<label>播放速度 <input data-guidance-param="speed" type="range" min="1" max="5" step="1" value="${m.speed}" /></label>`;
  if (explore && manifest.kind === 'quicksort') html += `<label>初始数组 <input data-guidance-array maxlength="200" value="${escape(m.initial.join(', '))}" /></label>${button('apply-array', '应用数组')}<label>基准策略 <select data-guidance-param="strategy">${[['last', '末尾元素'], ['first', '首个元素'], ['middle', '中间位置']].map(([id, label]) => `<option value="${id}" ${id === m.strategy ? 'selected' : ''}>${label}</option>`).join('')}</select></label>`;
  if (manifest.kind === 'friction') for (const [key, label, min, max, step] of [['mu', '摩擦系数', .1, 1, .1], ['velocity', '初速度 m/s', 1, 20, 1]] as const) {
    if (allowed(manifest, session, key)) html += `<label>${label} <input data-guidance-param="${key}" type="number" min="${min}" max="${max}" step="${step}" value="${m[key]}" ${attempt.complete && !explore ? 'disabled' : ''} /></label>`;
  }
  html += button('retry', explore ? '从初始数据重新运行' : '重试本步');
  const index = manifest.steps.findIndex(item => item.id === session!.active);
  if (attempt.complete && !explore) html += `<p class="guidance-complete">本步操作已完成</p>` + button('enter', index + 1 < manifest.steps.length ? '进入下一步' : '进入完整实验', manifest.steps[index + 1]?.id || EXPLORE);
  host.innerHTML = html;
  const history = document.querySelector('[data-guidance-history]');
  if (history) history.innerHTML = '<summary>最近操作反馈</summary>' + session.history.slice(-12).reverse().map(item => `<p>${escape(item.feedback.summary)}：${escape(item.feedback.explanation)}</p>`).join('');
  window.EduPractice?.report(reportedState(manifest, session).results);
}
function apply(command: Command, notify = true) {
  if (!session) return;
  const previous = session;
  try { session = reduceSession(manifest, session, command); render(); }
  catch (error) {
    session = previous; stop();
    send('error', { message: error instanceof Error ? error.message : '操作失败，已恢复原状态' }); return;
  }
  if (notify) send('event', { command, state: session, reported: reportedState(manifest, session) });
}
function tick() {
  if (!playing || !session) return;
  apply({ id: uid(), type: 'action', action: 'advance', attempt: currentAttempt(session).id });
  if (currentAttempt(session).model.phase === 'done' || (currentAttempt(session).complete && session.active !== EXPLORE)) { stop(); render(); return; }
  timer = setTimeout(tick, 1100 / currentAttempt(session).model.speed);
}
function dispatch(action: string, value?: unknown) {
  if (!session) return;
  if (action !== 'speed') stop();
  const command: Command = action === 'enter' ? { id: uid(), type: 'enter', step: String(value) } : action === 'retry' ? { id: uid(), type: 'retry' } : { id: uid(), type: 'action', action, value, attempt: currentAttempt(session).id };
  apply(command);
  if (action === 'run' && session.feedback.outcome === 'applied' && allowed(manifest, session, 'run')) { playing = true; render(); timer = setTimeout(tick, 1100 / currentAttempt(session).model.speed); }
}
function announce() { if (renderer && ready) send('ready', { version: 2 }); }
window.EduGuidance = { register(adapter) { if (renderer) throw Error('实验绘图器已注册'); renderer = adapter.render; announce(); }, dispatch, inspect: () => session && structuredClone(session) };
window.addEventListener('message', event => {
  if (event.source !== parent || !event.data || event.data.revision !== manifest.revision) return;
  const data = event.data;
  if (data.type === 'edu-guidance-init' && typeof data.channel === 'string') {
    stop(); clearInterval(announcementTimer); channel = data.channel;
    session = data.state || createSession(manifest);
    if (session!.revision !== manifest.revision) return;
    try { render(); send('initialized', { state: session, reported: reportedState(manifest, session!) }); }
    catch (e) { send('error', { message: String(e) }); }
  } else if (data.channel === channel && data.type === 'edu-guidance-command') {
    if (replies.has(data.command?.id)) { send('ack', { request: data.command.id, state: replies.get(data.command.id) }); return; }
    stop(); apply(data.command); replies.set(data.command.id, session); if (replies.size > 100) replies.delete(replies.keys().next().value!);
    send('ack', { request: data.command.id, state: session });
  }
});
document.addEventListener('visibilitychange', () => { if (document.hidden && playing) dispatch('pause'); });
document.addEventListener('click', event => {
  const element = (event.target as Element).closest<HTMLElement>('[data-guidance-action]');
  if (!element || element.hasAttribute('disabled')) return;
  let value: unknown = element.dataset.value ? JSON.parse(element.dataset.value) : undefined;
  let action = element.dataset.guidanceAction!;
  if (action === 'apply-array') { action = 'array'; value = (document.querySelector<HTMLInputElement>('[data-guidance-array]')?.value || '').split(/[,，\s]+/).filter(Boolean).map(Number); }
  dispatch(action, value);
});
document.addEventListener('change', event => {
  const element = event.target as HTMLInputElement;
  if (element.dataset.guidanceParam) dispatch(element.dataset.guidanceParam, element.type === 'number' || element.type === 'range' ? Number(element.value) : element.value);
});
const boot = () => {
  ready = true;
  const style = document.createElement('style'); style.textContent = '[data-guidance-feedback]{position:sticky;top:0;z-index:5;margin:16px 0;padding:16px;border:1px solid #c8ddd6;border-radius:10px;background:#f1f8f5;color:#203e42;font:15px/1.7 system-ui}[data-guidance-feedback] p{margin:6px 0}[data-guidance-feedback][data-outcome=incorrect],[data-guidance-feedback][data-outcome=invalid]{background:#fff5e9;border-color:#e6bb79}[data-guidance-controls]{padding:18px 0;border-top:1px solid #dce5e1;font:15px/1.7 system-ui}[data-guidance-controls] button{border:1px solid #b8ccc5;background:white;color:#245b52;border-radius:7px;padding:9px 14px;margin:5px;cursor:pointer}[data-guidance-controls] button:disabled{opacity:.5;cursor:default}[data-guidance-controls] label{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:14px 5px}[data-guidance-controls] input,[data-guidance-controls] select{max-width:100%;min-width:0;border:1px solid #b8ccc5;border-radius:6px;padding:7px;color:#203e42;background:white}[data-guidance-controls] input:not([type=range]){flex:1}[data-guidance-controls] button:focus-visible{outline:3px solid #24766c}[data-guidance-history]{font:14px/1.7 system-ui;padding:12px 0}.guidance-complete{color:#24766c}.guidance-next{color:#466b61}'; document.head.append(style);
  const feedback = document.querySelector('[data-guidance-feedback]'); feedback?.setAttribute('role', 'status'); feedback?.setAttribute('aria-live', 'polite');
  announce(); announcementTimer = setInterval(() => { if (!session) announce(); else clearInterval(announcementTimer); }, 500);
};
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true }); else boot();
