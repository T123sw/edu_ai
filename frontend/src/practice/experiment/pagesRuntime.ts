import { copy, equal, uid, type Intent, type State, type View } from './model';
import { actionFeedback, append, newView, stateCopy, type ActionDefinition, type Outcome, type PageAdapter, type PageSpec } from './pagesModel';
import type { Phase } from './model';
declare global { interface Window {
  __stagePage: { phase: Phase; revision: string; spec: PageSpec };
  EduStage: { register(adapter: PageAdapter): void; readonly index: number; readonly busy: boolean; describeActions(): ActionDefinition[]; perform(label: string, input: State, operation: () => Outcome | Promise<Outcome>): Promise<void>; observe(label: string): void };
} }
const config = window.__stagePage, spec = config.spec;
let adapter: PageAdapter | undefined, view: View | undefined, nonce = '', busy = true;
let lastError = '';
let operations = 0;
let observationsPaused = false;
function completedTask() { return view?.phase === 'guided' && view.index >= spec.tasks.length; }
function lockCompletedControls() {
  for (const control of document.querySelectorAll<HTMLButtonElement | HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>('button,input,select,textarea')) {
    if (completedTask()) {
      if (!control.hasAttribute('data-edu-disabled')) control.setAttribute('data-edu-disabled', String(control.disabled));
      control.disabled = true;
    } else if (control.hasAttribute('data-edu-disabled')) {
      control.disabled = control.getAttribute('data-edu-disabled') === 'true'; control.removeAttribute('data-edu-disabled');
    }
  }
}
const snapshot = () => stateCopy(adapter!.snapshot());
const record = (type: string, actor: 'system' | 'user', before: State, extra = {}) => append(view!, spec, type, actor, before, extra);
function report() { if (view && nonce) parent.postMessage({ type: 'edu-experiment-view', nonce, view, busy, error: lastError }, '*'); }
async function deadline<T>(operation: () => T | Promise<T>): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try { return await Promise.race([Promise.resolve().then(operation), new Promise<never>((_, reject) => { timer = setTimeout(() => reject(Error('实验操作超时，请重置后重试')), 10000); })]); }
  finally { clearTimeout(timer); }
}
async function run(operation: () => Promise<void>) {
  if (!view || !adapter || busy || view.phase !== config.phase) return;
  const saved = copy(view); busy = true; lastError = ''; report();
  try { await deadline(operation); }
  catch (e) { view = saved; try { await deadline(() => adapter!.restore(copy(saved.state))); } catch { /* original error is more useful */ } lastError = e instanceof Error ? e.message : String(e); }
  finally { busy = false; report(); }
}
async function initialize() {
  const before = copy(view!.state);
  lockCompletedControls();
  await adapter!.initialize(view!.index); view!.state = snapshot(); view!.attempt_before = copy(view!.state); view!.attempt_id = uid();
  record('initialized', 'system', before);
}
async function intent(intent: Intent) {
  await run(async () => {
    const v = view!, before = copy(v.state);
    if (intent.type === 'phase') {
      if (!(spec.phases || ['demonstrate', 'guided', 'explore']).includes(intent.phase) || intent.phase === v.phase) return;
      record('phase_left', 'user', before);
      v.phase = intent.phase; v.index = 0; v.feedback = ''; v.verdict = ''; v.last_input = {}; v.attempt_id = uid(); v.state = {}; v.attempt_before = {};
      record('phase_changed', 'system', before);
      // Parent changes srcDoc. New page initializes its own state.
    } else if (intent.type === 'next' && v.phase === 'demonstrate' && (spec.action_protocol ? v.verdict !== 'complete' : v.index < spec.demo_steps.length)) {
      const step = spec.demo_steps[v.index];
      const outcome = await adapter!.next!(v.index); v.state = snapshot();
      if (spec.action_protocol) {
        if (!outcome || typeof outcome.action_id !== 'string' || !outcome.action_id || typeof outcome.done !== 'boolean') throw Error('演示动作需返回 action_id 和 done，以绑定实际动作讲解');
        v.last_input = stateCopy({ action_id: outcome.action_id, done: outcome.done, facts: outcome.facts || {} });
        v.feedback = step?.action_id === outcome.action_id ? step.after : '已执行操作：' + outcome.action_id;
        v.verdict = outcome.done ? 'complete' : '';
        record('action', 'system', before, { command: { action: outcome.action_id, input: v.last_input }, feedback: v.feedback });
      } else {
        v.feedback = step.after;
        record('action', 'system', before, { command: { action: step.title, input: {} }, feedback: step.after });
      }
      v.index++;
    } else if ((intent.type === 'back' || intent.type === 'replay') && v.phase === 'demonstrate') {
      const target = intent.type === 'back' ? Math.max(0, v.index - 1) : 0;
      await adapter!.initialize(0);
      v.verdict = '';
      v.last_input = {};
      for (let i = 0; i < target; i++) {
        const result = await adapter!.next!(i);
        if (result) { v.last_input = stateCopy(result); if (result.done) v.verdict = 'complete'; }
      }
      v.state = snapshot(); v.index = target;
      const previous = spec.demo_steps[target - 1];
      v.feedback = target ? (spec.action_protocol && previous?.action_id !== v.last_input.action_id ? '已回到对应实验状态。' : previous?.after || '') : spec.demo_steps[0]?.before || '';
      record(intent.type, 'system', before);
    } else if (intent.type === 'reset') {
      if (completedTask()) v.index = Math.max(0, spec.tasks.length - 1);
      v.last_input = {}; v.feedback = ''; v.verdict = ''; await initialize();
    } else if (intent.type === 'hint' && v.phase === 'guided') {
      const task = spec.tasks[v.index]; if (!task) return;
      const count = v.events.filter(e => e.type === 'hint' && e.attempt_id === v.attempt_id).length;
      v.feedback = task.hints[Math.min(count, task.hints.length - 1)] || task.prompt; record('hint', 'user', before, { feedback: v.feedback });
    }
  });
}
window.EduStage = {
  get index() { return view?.index ?? 0; },
  get busy() { return busy; },
  describeActions() { return adapter?.actions || []; },
  register(value) {
    if (adapter || ['initialize', 'snapshot', 'restore'].some(k => typeof value[k as keyof PageAdapter] !== 'function') || config.phase === 'demonstrate' && typeof value.next !== 'function') throw Error('实验页面接口不完整');
    adapter = value; parent.postMessage({ type: 'edu-experiment-ready' }, '*');
  },
  async perform(label, input, operation) {
    if (config.phase === 'demonstrate') return;
    operations++;
    await run(async () => {
      const v = view!, task = spec.tasks[v.index], before = copy(v.state);
      if (v.phase === 'guided' && !task) return;
      v.last_input = stateCopy(input);
      const result = await operation(); v.state = snapshot();
      const actual = spec.action_protocol && result?.action_id ? result.action_id : label;
      record('action', 'user', before, { command: { action: actual, input: spec.action_protocol ? { ...v.last_input, facts: result?.facts || {} } : v.last_input } });
      if (v.phase !== 'guided') return;
      if (!result?.verdict || !['pending', 'pass', 'fail'].includes(result.verdict)) throw Error('练习操作没有返回本地判定结果');
      v.verdict = result?.verdict || 'pending';
      const fallback = v.verdict === 'pass' ? task.success : v.verdict === 'fail' ? task.retry : '操作已记录，请继续完成当前任务。';
      if (spec.action_protocol) {
        const entry = result?.action_id ? spec.action_feedback?.[result.action_id] : undefined;
        const template = v.verdict === 'pass' ? entry?.passed : v.verdict === 'fail' ? entry?.fail : entry?.pending;
        v.feedback = actionFeedback(template, { before, after: v.state, input: v.last_input, facts: result?.facts || {} }) || fallback;
      } else v.feedback = result?.feedback || fallback;
      record(v.verdict === 'pending' ? 'operation_feedback' : 'attempt_submitted', 'user', v.state, { verdict: v.verdict, feedback: v.feedback });
      if (v.verdict === 'pass') {
        v.index++;
        // Completion must preserve the actual result. There is no next task to initialize.
        if (v.index < spec.tasks.length) await initialize();
        else lockCompletedControls();
      }
      else if (v.verdict === 'fail') {
        const failed = copy(v.state); await adapter!.restore(copy(before)); v.state = snapshot();
        record('retry_started', 'system', failed, { feedback: v.feedback }); v.attempt_id = uid();
      }
    });
  },
  observe(label) {
    if (busy || observationsPaused || !view || view.phase !== 'explore' || config.phase !== 'explore') return;
    const saved = copy(view);
    try { const before = copy(view.state); view.state = snapshot(); if (equal(before, view.state)) return; record('observation', 'system', before, { command: { action: label, input: {} } }); report(); }
    catch (e) { view = saved; lastError = String(e); observationsPaused = true; report(); }
  },
};
window.addEventListener('message', event => {
  if (event.source !== parent) return;
  const data = event.data;
  if (data?.type === 'edu-experiment-init' && adapter && !view && typeof data.nonce === 'string') {
    nonce = data.nonce; view = data.view ? copy(data.view) as View : newView(config.revision, config.phase);
    if (view.revision !== config.revision || view.phase !== config.phase) { view = undefined; return; }
    void deadline(async () => {
      const entering = !view!.seq || view!.events.at(-1)?.type === 'phase_changed';
      if (entering) await initialize();
      else {
        await adapter!.initialize(view!.index); await adapter!.restore(copy(view!.state));
        const restored = snapshot();
        if (!equal(restored, view!.state)) { const before = copy(view!.state); view!.state = restored; record('restored', 'system', before); }
      }
    }).then(() => { lockCompletedControls(); busy = false; report(); }).catch(e => { lastError = String(e); report(); });
  }
  if (data?.type === 'edu-experiment-intent' && data.nonce === nonce) void intent(data.intent);
});
window.addEventListener('error', event => { lastError = event.message; report(); });
window.addEventListener('unhandledrejection', event => { lastError = String(event.reason); report(); });

// Record local selection controls even if generated code wraps only its confirm
// button. Never infer a verdict from a DOM event.
for (const type of ['click', 'change']) document.addEventListener(type, event => {
  if (!view || !adapter || view.phase !== config.phase) return;
  const target = event.target instanceof Element ? event.target.closest('button,input,select,canvas,svg,[role="button"]') : null;
  if (!target) return;
  if (busy || config.phase === 'demonstrate' || completedTask()) { event.preventDefault(); event.stopImmediatePropagation(); return; }
  const count = operations;
  const label = (target.getAttribute('aria-label') || target.textContent || target.id || '选择对象').trim().slice(0, 120);
  const input = { control: target.id, value: 'value' in target ? String(target.value).slice(0, 2000) : label };
  queueMicrotask(() => {
    if (count !== operations || busy || !view || view.phase !== config.phase) return;
    void run(async () => { const before = copy(view!.state); view!.state = snapshot(); view!.last_input = input; record('action', 'user', before, { command: { action: label, input } }); });
  });
}, true);

// Animation observations are snapshots, explicitly distinct from user actions.
// Explicit observe() calls still capture each meaningful generated transition.
setInterval(() => { if (!busy && config.phase === 'explore') window.EduStage.observe('动画状态采样'); }, 300);
