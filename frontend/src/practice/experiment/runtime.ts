import { start, transition, allowed, copy, type Adapter, type Spec, type View, type Intent, type State } from './model';
declare global { interface Window { __experimentSpec: Spec; __experimentRevision: string; EduExperiment: { register(adapter: Adapter): void; dispatch(action: string, input?: State): Promise<void> } } }
const spec = window.__experimentSpec;
let adapter: Adapter | undefined, view: View | undefined, nonce = '', busy = false;
function report(error = '') {
  if (!view || !nonce) return;
  parent.postMessage({ type: 'edu-experiment-view', nonce, view, busy, error }, '*');
}
function render() { if (view && adapter) adapter.render(copy(view.state), { phase: view.phase, allowed_actions: allowed(spec, view), busy }); }
async function dispatch(intent: Intent) {
  if (!adapter || !view || busy) return;
  busy = true; report();
  try { render(); view = await transition(spec, view, intent, adapter.apply.bind(adapter)); render(); }
  catch (e) { report(e instanceof Error ? e.message : '实验执行失败'); }
  finally { busy = false; try { render(); } catch (e) { report(String(e)); } report(); }
}
window.EduExperiment = {
  register(value) {
    if (adapter || typeof value.apply !== 'function' || typeof value.render !== 'function') throw Error('实验适配器注册无效');
    adapter = value; render(); parent.postMessage({ type: 'edu-experiment-ready' }, '*');
  },
  dispatch(action, input = {}) { return dispatch({ type: 'action', command: { action, input } }); },
};
window.addEventListener('message', event => {
  if (event.source !== parent || !event.data || typeof event.data !== 'object') return;
  const data = event.data;
  if (data.type === 'edu-experiment-init' && !view && typeof data.nonce === 'string') {
    nonce = data.nonce;
    view = data.view || start(spec, window.__experimentRevision);
    if (view!.revision !== window.__experimentRevision) { view = undefined; return; }
    try { render(); report(); } catch (e) { report(String(e)); }
  }
  if (data.type === 'edu-experiment-intent' && data.nonce === nonce) void dispatch(data.intent);
});
window.addEventListener('error', e => report(e.message));
window.addEventListener('unhandledrejection', e => report(String(e.reason)));
