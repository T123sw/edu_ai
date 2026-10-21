export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export type State = Record<string, Json>;
export type Phase = 'demonstrate' | 'guided' | 'explore';
export type Parameter = { name: string; label: string; type: 'number' | 'integer' | 'string' | 'boolean'; default: Json; minimum?: number | null; maximum?: number | null; options: Json[] };
export type Action = { id: string; label: string; description: string; phases: Phase[]; parameters: Parameter[] };
export type Command = { action: string; input: State };
export type Condition = { path: (string | number)[]; op: 'eq' | 'ne' | 'lt' | 'lte' | 'gt' | 'gte' | 'contains' | 'near'; value: Json; right_path?: (string | number)[] | null; tolerance: number };
export type Task = { id: string; title: string; objective: string; prompt: string; checkpoint?: string | null; allowed_actions: string[]; submission: 'on_action' | 'explicit_submit'; submit_action?: string | null; assessment: 'deterministic' | 'rubric'; checks: Condition[]; rubric: string[]; success: string; retry: string; recovery: 'rollback' | 'keep'; hints: string[] };
export type Spec = { protocol: 'edu-experiment/1'; title: string; subject: string; overview: string; objectives: string[]; scientific_model: { assumptions: string[]; rules: string[]; limitations: string[] }; state_fields: { path: (string | number)[]; label: string; description: string; unit: string }[]; actions: Action[]; checkpoints: Record<string, State>; demo_checkpoint: string; demo_steps: { id: string; title: string; before: string; after: string; commands: Command[]; assertions: Condition[] }[]; guided_checkpoint: string; tasks: Task[]; explore_checkpoint: string; exploration_prompts: string[]; teaching_context: { background: string; misconceptions: string[] }; validation_cases: { id: string; task_id: string; commands: Command[]; expected: string; assertions: Condition[] }[] };
export type Event = { id: string; seq: number; at: number; actor: 'user' | 'system'; type: string; phase: Phase; task_id: string | null; attempt_id: string; before: string; after: string; command?: Command; verdict?: string; feedback?: string };
export type View = { run_id: string; revision: string; seq: number; phase: Phase; index: number; attempt_id: string; attempt_before: State; last_input: State; state: State; feedback: string; verdict: string; events: Event[]; snapshots: Record<string, State> };
export type Adapter = { apply(state: State, command: Command): State | Promise<State>; render(state: State, policy: { phase: Phase; allowed_actions: string[]; busy: boolean }): void };
export type Intent = { type: 'next' | 'back' | 'replay' | 'submit' | 'hint' | 'reset' } | { type: 'phase'; phase: Phase } | { type: 'action'; command: Command };
export const copy = <T>(v: T): T => JSON.parse(JSON.stringify(v));
export function uid(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16)); bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes].map(v => v.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
export function equal(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object' || Array.isArray(a) !== Array.isArray(b)) return false;
  const x = a as Record<string, unknown>, y = b as Record<string, unknown>;
  return Object.keys(x).length === Object.keys(y).length && Object.keys(x).every(k => Object.hasOwn(y, k) && equal(x[k], y[k]));
}
export function read(root: unknown, path: (string | number)[]): unknown {
  return path.reduce<unknown>((v, k) => v && typeof v === 'object' && !['__proto__', 'constructor', 'prototype'].includes(String(k)) && Object.hasOwn(v, k) ? (v as Record<string, unknown>)[k] : undefined, root);
}
export function matches(check: Condition, context: { before: State; after: State; input: State }): boolean {
  const a = read(context, check.path), b = check.right_path ? read(context, check.right_path) : check.value;
  if (a === undefined || b === undefined) return false;
  if (check.op === 'eq') return equal(a, b);
  if (check.op === 'ne') return !equal(a, b);
  if (check.op === 'contains') return Array.isArray(a) ? a.some(v => equal(v, b)) : typeof a === 'string' && typeof b === 'string' && a.includes(b);
  if (typeof a !== 'number' || typeof b !== 'number' || !Number.isFinite(a) || !Number.isFinite(b)) return false;
  if (check.op === 'near') return Math.abs(a - b) <= check.tolerance;
  return check.op === 'lt' ? a < b : check.op === 'lte' ? a <= b : check.op === 'gt' ? a > b : a >= b;
}
function validState(state: State) {
  if (!state || Array.isArray(state) || typeof state !== 'object') throw Error('实验适配器没有返回状态');
  const text = JSON.stringify(state, (_k, v: unknown) => { if (typeof v === 'number' && !Number.isFinite(v) || v === undefined || typeof v === 'function') throw Error('实验状态必须为有限 JSON 值'); return v; });
  if (text.length > 50000) throw Error('单次实验状态过大，请减少样本后重试');
}
export function allowed(spec: Spec, view: View) {
  if (view.phase === 'demonstrate') return [];
  return spec.actions.filter(a => a.phases.includes(view.phase) && (view.phase === 'explore' || spec.tasks[view.index]?.allowed_actions.includes(a.id))).map(a => a.id);
}
export function start(spec: Spec, revision: string): View {
  const state = copy(spec.checkpoints[spec.demo_checkpoint]); validState(state);
  return { run_id: uid(), revision, seq: 0, phase: 'demonstrate', index: 0, attempt_id: uid(), attempt_before: copy(state), last_input: {}, state, feedback: spec.demo_steps[0].before, verdict: '', events: [], snapshots: { '0': copy(state) } };
}
function validateAction(spec: Spec, command: Command, phase: Phase) {
  const action = spec.actions.find(a => a.id === command.action && a.phases.includes(phase));
  if (!action || Object.keys(command.input).length !== action.parameters.length) throw Error('操作或参数不可用');
  for (const p of action.parameters) {
    const v = command.input[p.name];
    if (p.type === 'number' || p.type === 'integer') {
      if (typeof v !== 'number' || !Number.isFinite(v) || p.type === 'integer' && !Number.isInteger(v) || p.minimum != null && v < p.minimum || p.maximum != null && v > p.maximum) throw Error(`${p.label}超出允许范围`);
    } else if (typeof v !== p.type) throw Error(`${p.label}类型错误`);
    if (p.options.length && !p.options.some(o => equal(o, v))) throw Error(`${p.label}不在选项中`);
  }
}
export async function transition(spec: Spec, previous: View, intent: Intent, apply: Adapter['apply']): Promise<View> {
  const v = copy(previous);
  const append = (type: string, actor: Event['actor'], before: State, extra: Partial<Event> = {}) => {
    validState(v.state); const seq = v.seq + 1;
    v.snapshots[`${seq}:before`] = copy(before); v.snapshots[String(seq)] = copy(v.state);
    v.events.push({ id: uid(), seq, at: Date.now(), actor, type, phase: v.phase, task_id: v.phase === 'guided' ? spec.tasks[v.index]?.id || null : null, attempt_id: v.attempt_id, before: `${seq}:before`, after: String(seq), ...extra }); v.seq = seq;
  };
  const execute = async (command: Command, actor: Event['actor']) => {
    validateAction(spec, command, v.phase); const before = copy(v.state);
    let timer: ReturnType<typeof setTimeout> | undefined;
    try { v.state = await Promise.race([Promise.resolve(apply(copy(v.state), copy(command))), new Promise<State>((_resolve, reject) => { timer = setTimeout(() => reject(Error('操作超时，请重试或重新生成实验')), 8000); })]); } finally { clearTimeout(timer); }
    validState(v.state); v.last_input = copy(command.input);
    append('action', actor, before, { command });
  };
  const initTask = () => { const task = spec.tasks[v.index]; if (task?.checkpoint) v.state = copy(spec.checkpoints[task.checkpoint]); v.attempt_before = copy(v.state); v.attempt_id = uid(); v.last_input = {}; };
  const assess = () => {
    const task = spec.tasks[v.index]; if (!task) throw Error('任务已完成');
    const before = copy(v.state);
    const context = { before: v.attempt_before, after: v.state, input: v.last_input };
    const incomplete = task.checks.some(c => {
      const left = read(context, c.path), right = c.right_path ? read(context, c.right_path) : c.value;
      return left === undefined || right === undefined || ['lt', 'lte', 'gt', 'gte', 'near'].includes(c.op) && (typeof left !== 'number' || typeof right !== 'number');
    });
    v.verdict = task.assessment === 'rubric' ? 'awaiting_review' : incomplete ? 'unknown' : task.checks.every(c => matches(c, context)) ? 'pass' : 'fail';
    v.feedback = v.verdict === 'pass' ? task.success : v.verdict === 'fail' ? task.retry : v.verdict === 'unknown' ? '当前实验缺少判定所需的状态，暂时无法判断。请重置或重新生成实验；这不算操作错误。' : '操作已记录，开放回答需由后续教学服务评价。可以继续修改或进入自由探索。';
    append('attempt_submitted', 'user', before, { verdict: v.verdict, feedback: v.feedback });
    if (v.verdict === 'pass') { v.index++; initTask(); append('task_advanced', 'system', before); }
    else if (v.verdict === 'fail') {
      if (task.recovery === 'rollback') v.state = copy(v.attempt_before);
      v.attempt_before = copy(v.state); v.attempt_id = uid(); v.last_input = {};
      append('retry_started', 'system', before, { feedback: v.feedback });
    }
  };
  if (intent.type === 'phase') {
    const before = copy(v.state);
    if (intent.phase === 'guided' && !(v.phase === 'demonstrate' && v.index === spec.demo_steps.length)) throw Error('请先完成演示');
    v.phase = intent.phase; v.index = 0; v.verdict = ''; v.feedback = '';
    v.state = copy(spec.checkpoints[intent.phase === 'demonstrate' ? spec.demo_checkpoint : intent.phase === 'guided' ? spec.guided_checkpoint : spec.explore_checkpoint]);
    initTask(); if (v.phase !== 'guided') { v.state = copy(spec.checkpoints[v.phase === 'demonstrate' ? spec.demo_checkpoint : spec.explore_checkpoint]); v.attempt_before = copy(v.state); }
    append('phase_entered', 'user', before, { feedback: intent.phase === 'explore' ? '进入探索不代表已掌握前面的任务' : '' });
  } else if (intent.type === 'next' || intent.type === 'back' || intent.type === 'replay') {
    if (v.phase !== 'demonstrate') throw Error('手动实践没有下一步按钮');
    if (intent.type === 'next') {
      const step = spec.demo_steps[v.index]; if (!step) throw Error('演示已完成'); const before = copy(v.state);
      for (const cmd of step.commands) await execute(cmd, 'system');
      if (!step.assertions.every(c => matches(c, { before, after: v.state, input: v.last_input }))) throw Error('演示结果未通过检查，未推进步骤');
      v.feedback = step.after; v.index++; append('demo_completed', 'system', before, { feedback: step.after });
    } else {
      const target = intent.type === 'replay' ? 0 : Math.max(0, v.index - 1), before = copy(v.state);
      v.state = copy(spec.checkpoints[spec.demo_checkpoint]); v.index = 0;
      for (let i = 0; i < target; i++) { for (const cmd of spec.demo_steps[i].commands) await execute(cmd, 'system'); v.index++; }
      v.feedback = spec.demo_steps[v.index]?.before || ''; append('demo_restored', 'user', before);
    }
  } else if (intent.type === 'action') {
    if (!allowed(spec, v).includes(intent.command.action)) throw Error('当前阶段不允许此操作');
    await execute(intent.command, 'user');
    if (v.phase === 'guided' && spec.tasks[v.index]?.submission === 'on_action' && spec.tasks[v.index].submit_action === intent.command.action) assess();
    else { v.feedback = '操作已执行，观察展示区的变化。'; v.verdict = ''; }
  } else if (intent.type === 'submit') {
    if (v.phase !== 'guided' || spec.tasks[v.index]?.submission !== 'explicit_submit') throw Error('当前任务无需手动提交'); assess();
  } else if (intent.type === 'hint') {
    const task = v.phase === 'guided' ? spec.tasks[v.index] : undefined; if (!task) throw Error('当前没有待完成任务');
    const n = v.events.filter(e => e.type === 'hint_requested' && e.task_id === task.id).length;
    v.feedback = task.hints[Math.min(n, task.hints.length - 1)]; append('hint_requested', 'user', v.state, { feedback: v.feedback });
  } else if (intent.type === 'reset') {
    const before = copy(v.state); v.state = copy(v.phase === 'guided' ? v.attempt_before : spec.checkpoints[v.phase === 'explore' ? spec.explore_checkpoint : spec.demo_checkpoint]);
    if (v.phase === 'demonstrate') v.index = 0;
    v.attempt_id = uid(); v.attempt_before = copy(v.state); v.last_input = {}; v.verdict = ''; v.feedback = '已恢复本次操作的初始状态'; append('reset', 'user', before);
  }
  if (v.events.length > 2000 || JSON.stringify(v).length > 1500000) throw Error('本轮记录已达上限，请保存记录后开启新一轮实验');
  return v;
}
