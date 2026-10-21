import { copy, uid, type Event, type Phase, type Spec, type State, type View } from './model';
export type PageTask = { id: string; title: string; initial: string; prompt: string; interaction: string; completion: string; success: string; retry: string; hints: string[]; submission?: never };
export type PageSpec = Pick<Spec, 'title' | 'overview' | 'teaching_context' | 'state_fields' | 'actions' | 'exploration_prompts'> & {
  protocol: 'edu-experiment/2'; demo_initial: string; demo_result?: State;
  phases?: Phase[]; action_protocol?: 'edu-actions/1'; capture_actions?: boolean;
  action_catalog?: ActionDefinition[];
  action_feedback?: Record<string, { pending: string; fail: string; passed: string }>;
  demo_steps: { id: string; action_id?: string; title: string; before: string; after: string; operation: string }[];
  tasks: PageTask[]; scientific_model: State;
};
export type PagePackage = { protocol: 'edu-experiment/2'; revision: string; spec: PageSpec; pages: Record<'demonstrate' | 'explore', string> & Partial<Record<'guided', string>>; teaching: { status: string } };
export type ActionDefinition = { id: string; label: string; rule: string; facts?: string[] };
export type DemoOutcome = { action_id: string; done: boolean; facts?: State };
export type PageAdapter = { actions?: ActionDefinition[]; initialize(index: number): void | Promise<void>; snapshot(): State; restore(state: State): void | Promise<void>; next?(index: number): void | DemoOutcome | Promise<void | DemoOutcome> };
export type Outcome = { verdict?: 'pending' | 'pass' | 'fail'; feedback?: string; action_id?: string; facts?: State } | void;

export function actionFeedback(template: string | undefined, context: State): string | undefined {
  if (!template) return undefined;
  let missing = false;
  const rendered = template.replace(/\{\{\s*([\w.]+)\s*\}\}/g, (_match, path: string) => {
    let value: unknown = context;
    for (const key of path.split('.')) value = value && typeof value === 'object' && Object.hasOwn(value, key) ? (value as State)[key] : undefined;
    if (value === undefined) { missing = true; return ''; }
    return typeof value === 'object' ? JSON.stringify(value) : String(value);
  });
  return missing || rendered.includes('{{') || rendered.includes('}}') ? undefined : rendered;
}
export function stateCopy(value: State): State {
  if (!value || Array.isArray(value) || typeof value !== 'object') throw Error('实验没有上报有效状态');
  const text = JSON.stringify(value, (_k, v: unknown) => {
    if (v === undefined || typeof v === 'function' || typeof v === 'number' && !Number.isFinite(v)) throw Error('实验状态必须是有限 JSON 数据');
    return v;
  });
  if (text.length > 50000) throw Error('当前实验状态过大');
  return JSON.parse(text) as State;
}
export function newView(revision: string, phase: Phase): View {
  return { run_id: uid(), revision, seq: 0, phase, index: 0, attempt_id: uid(), attempt_before: {}, last_input: {}, state: {}, feedback: '', verdict: '', events: [], snapshots: { '0': {} } };
}
export function append(view: View, spec: PageSpec, type: string, actor: Event['actor'], before: State, extra: Partial<Event> = {}) {
  const seq = view.seq + 1;
  const event: Event = { id: uid(), seq, at: Date.now(), actor, type, phase: view.phase, task_id: view.phase === 'guided' ? spec.tasks[view.index]?.id || null : null, attempt_id: view.attempt_id, before: `${seq}:before`, after: String(seq), ...extra };
  const snapshots = { ...view.snapshots, [event.before]: copy(before), [event.after]: copy(view.state) };
  if (seq > 2000 || JSON.stringify({ ...view, seq, snapshots, events: [...view.events, event] }).length > 1450000) throw Error('本轮记录已满，请保存后开始新一轮实验');
  view.seq = seq; view.events.push(event); view.snapshots = snapshots;
}
