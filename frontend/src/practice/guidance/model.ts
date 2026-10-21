/** Trusted, deterministic teaching model. No DOM, clocks, randomness or generated code. */
export type Kind = 'quicksort' | 'friction';
export type Step = { id: string; title: string; instruction: string; question: string; actions: string[]; parameters: string[] };
export type Manifest = { version: 2; kind: Kind; steps: Step[]; initial: number[]; revision: string };
export type Command = { id: string; type: 'action' | 'enter' | 'retry'; action?: string; value?: unknown; step?: string; attempt?: string };
export type Feedback = { outcome: 'applied' | 'incorrect' | 'blocked' | 'invalid' | 'no_change'; summary: string; explanation: string; next: string };
export type Model = { initial: number[]; array: number[]; phase: string; selected: number; lo: number; hi: number; scan: number; boundary: number; pivot: number; stack: number[][]; comparisons: number; swaps: number; speed: number; strategy: string; mu: number; velocity: number; time: number; distance: number; baseline: number; changed: boolean };
export type Attempt = { id: string; entry: Model; model: Model; complete: boolean };
export type Session = { version: 2; revision: string; seq: number; active: string; attempts: Record<string, Attempt>; feedback: Feedback; history: { event: string; step: string; attempt: string; feedback: Feedback }[] };
export const EXPLORE = 'explore';
const clone = <T>(v: T): T => JSON.parse(JSON.stringify(v));
const feedback = (summary: string, explanation = '', next = '', outcome: Feedback['outcome'] = 'applied'): Feedback => ({ outcome, summary, explanation, next });
export function initialModel(manifest: Manifest): Model {
  return { initial: [...manifest.initial], array: [...manifest.initial], phase: manifest.kind === 'quicksort' ? 'select' : 'ready', selected: -1, lo: 0, hi: manifest.initial.length - 1, scan: 0, boundary: 0, pivot: 0, stack: [], comparisons: 0, swaps: 0, speed: 2, strategy: 'last', mu: .3, velocity: 6, time: 0, distance: 0, baseline: 0, changed: false };
}
export function createSession(manifest: Manifest): Session {
  const model = initialModel(manifest), first = manifest.steps[0];
  return { version: 2, revision: manifest.revision, seq: 0, active: first.id, attempts: { [first.id]: { id: 'initial', entry: clone(model), model, complete: false } }, feedback: feedback('开始本步实验', first.instruction, first.question), history: [] };
}
export const currentAttempt = (state: Session) => state.attempts[state.active];
export function allowed(manifest: Manifest, state: Session, action: string): boolean {
  if (['pause', 'speed'].includes(action)) return true;
  if (state.active === EXPLORE) return (manifest.kind === 'quicksort' ? ['select', 'confirm', 'advance', 'range', 'run', 'array', 'strategy'] : ['advance', 'run', 'mu', 'velocity']).includes(action);
  const step = manifest.steps.find(item => item.id === state.active);
  return !!step && [...step.actions, ...step.parameters].includes(action);
}
function swap(m: Model, a: number, b: number) { if (a !== b) { [m.array[a], m.array[b]] = [m.array[b], m.array[a]]; m.swaps++; } }
function startPartition(m: Model, selected: number) {
  swap(m, selected, m.hi); m.selected = m.hi; m.pivot = m.array[m.hi]; m.scan = m.lo; m.boundary = m.lo; m.phase = 'scan';
}
function sorting(m: Model, action: string, value: unknown, guidedPartition: boolean): Feedback {
  if (action === 'select') {
    if (m.phase !== 'select') return feedback('当前不能更换基准', '已有分区操作，请重试本步后重新选择。', '', 'blocked');
    if (!Number.isInteger(value) || Number(value) < m.lo || Number(value) > m.hi) return feedback('请选择当前区间内的元素', '', '', 'invalid');
    if (m.selected === value) return feedback('仍是同一个基准', '数组没有变化。', '确认基准后继续。', 'no_change');
    m.selected = Number(value); return feedback(`已选择 ${m.array[m.selected]} 为基准`, '先用这个值判断其他元素应该放在哪一侧。', '点击“确认基准”。');
  }
  if (action === 'confirm') {
    if (m.phase !== 'select' || m.selected < 0) return feedback('请先选择基准元素', '', '点击图中的一个元素。', 'blocked');
    startPartition(m, m.selected); return feedback(`基准 ${m.pivot} 已确认`, '本实验使用 Lomuto 分区：基准先移到当前区间末尾。', '进入分区步骤，判断当前元素。');
  }
  if (action === 'range') {
    if (m.phase !== 'range') return feedback('当前区间尚未处理完成', '', '', 'blocked');
    if (!Number.isInteger(value) || Number(value) < 0 || Number(value) >= m.stack.length) return feedback('请选择待处理区间', '', '', 'invalid');
    const [lo, hi] = m.stack.splice(Number(value), 1)[0]; m.lo = lo; m.hi = hi;
    startPartition(m, m.strategy === 'first' ? lo : m.strategy === 'middle' ? Math.floor((lo + hi) / 2) : hi);
    return feedback(`开始处理区间 ${lo + 1}–${hi + 1}`, `本区间基准为 ${m.pivot}。单元素区间无需继续分区。`, '单步观察，或播放当前处理过程。');
  }
  if (action === 'left' || action === 'right' || action === 'advance') {
    if (m.phase === 'done') return feedback('排序已完成', '继续执行不会改变数组。', '重试或进入完整实验更换数据。', 'no_change');
    if (m.phase === 'select') {
      if (action !== 'advance') return feedback('尚未确认基准', '', '', 'blocked');
      m.selected = m.strategy === 'first' ? m.lo : m.strategy === 'middle' ? Math.floor((m.lo + m.hi) / 2) : m.hi;
      return sorting(m, 'confirm', undefined, false);
    }
    if (m.phase === 'range') return action === 'advance' ? sorting(m, 'range', 0, false) : feedback('本次分区已完成', '', '进入下一步处理子区间。', 'no_change');
    if (m.phase === 'scan') {
      const number = m.array[m.scan], left = number <= m.pivot;
      if (guidedPartition && action === 'advance') return feedback('先判断当前元素的归属', '', '选择“小于等于基准”或“大于基准”。', 'blocked');
      if (action !== 'advance' && (action === 'left') !== left) return feedback('再比较一下这两个数', `${number} ${left ? '≤' : '>'} ${m.pivot}；这次判断没有改变数组或算法计数。`, `请选择“${left ? '小于等于基准' : '大于基准'}”。`, 'incorrect');
      m.comparisons++; const moved = left && m.scan !== m.boundary;
      if (left) { swap(m, m.scan, m.boundary); m.boundary++; }
      m.scan++; if (m.scan === m.hi) m.phase = 'place';
      return feedback(`已比较 ${number} 与 ${m.pivot}`, left ? `${number} ≤ ${m.pivot}，${moved ? '交换到左侧区间' : '已在左侧，无需交换'}。` : `${number} > ${m.pivot}，保留在右侧候选区间。`, m.phase === 'place' ? '扫描结束，点击“基准归位”。' : '继续判断下一个高亮元素。');
    }
    if (m.phase === 'place') {
      if (action !== 'advance') return feedback('扫描已经结束', '', '点击“基准归位”。', 'blocked');
      swap(m, m.boundary, m.hi); m.selected = m.boundary;
      if (m.boundary - m.lo > 1) m.stack.push([m.lo, m.boundary - 1]);
      if (m.hi - m.boundary > 1) m.stack.push([m.boundary + 1, m.hi]);
      m.phase = m.stack.length ? 'range' : 'done';
      return feedback('基准归位，本次分区完成', `基准左侧元素均 ≤ ${m.pivot}，右侧元素均 > ${m.pivot}。${m.stack.length ? '两侧内部还需继续处理。' : '所有区间均已处理。'}`, m.stack.length ? '继续处理子区间。' : '可进入完整实验比较不同输入或策略。');
    }
  }
  return feedback('当前不能执行此操作', '', '', 'blocked');
}
function resetPhysics(m: Model) { m.phase = 'ready'; m.time = 0; m.distance = 0; }
function physics(m: Model, action: string, value: unknown): Feedback {
  if (action === 'mu' || action === 'velocity') {
    const n = Number(value), low = action === 'mu' ? .1 : 1, high = action === 'mu' ? 1 : 20;
    if (!Number.isFinite(n) || n < low || n > high) return feedback('参数不在有效范围', `范围为 ${low}–${high}。`, '', 'invalid');
    if (m[action] === n) return feedback('参数没有变化', '已有结果保持不变。', '', 'no_change');
    m[action] = n; m.changed = true; resetPhysics(m);
    return feedback(action === 'mu' ? `摩擦系数已设为 ${n}` : `初速度已设为 ${n} m/s`, '旧运行结果已清除；本实验为水平面恒定滑动摩擦，g = 9.8 m/s²。', '运行后再比较停车距离。');
  }
  if (action === 'advance') {
    if (m.phase === 'done') return feedback('小车已经停止', '继续运行不会改变距离。', '重试或修改本步参数。', 'no_change');
    const acceleration = m.mu * 9.8, stop = m.velocity / acceleration;
    m.time = Math.min(stop, m.time + .2); m.distance = m.velocity * m.time - acceleration * m.time * m.time / 2;
    m.phase = m.time >= stop ? 'done' : 'moving';
    return feedback(m.phase === 'done' ? '小车已停止' : '小车继续滑行', `已滑行 ${m.distance.toFixed(2)} m，当前速度 ${Math.max(0, m.velocity - acceleration * m.time).toFixed(2)} m/s。`, m.phase === 'done' && m.baseline ? `基线距离 ${m.baseline.toFixed(2)} m，本次变化 ${(m.distance - m.baseline).toFixed(2)} m。` : '观察速度和距离如何变化。');
  }
  return feedback('当前不能执行此操作', '', '', 'blocked');
}
export function reduceSession(manifest: Manifest, previous: Session, command: Command): Session {
  if (previous.revision !== manifest.revision) throw Error('实验版本不匹配');
  const state = clone(previous), current = currentAttempt(state), model = current.model;
  const index = manifest.steps.findIndex(step => step.id === state.active);
  let result: Feedback;
  if (command.type === 'enter') {
    const target = command.step || '', targetIndex = manifest.steps.findIndex(step => step.id === target);
    if (target !== EXPLORE && targetIndex < 0) result = feedback('步骤不存在', '', '', 'invalid');
    else if (target !== EXPLORE && targetIndex > 0 && !state.attempts[manifest.steps[targetIndex - 1].id]?.complete) result = feedback('请先完成前一步操作', '', '也可以直接进入完整实验自由探索。', 'blocked');
    else {
      if (!state.attempts[target]) {
        const entry = target === EXPLORE ? clone(model) : clone(state.attempts[manifest.steps[targetIndex - 1].id].model);
        if (manifest.kind === 'friction' && target !== EXPLORE) { entry.baseline = entry.distance; entry.changed = false; resetPhysics(entry); }
        state.attempts[target] = { id: command.id, entry: clone(entry), model: entry, complete: false };
      }
      state.active = target;
      result = feedback(target === EXPLORE ? '完整实验 · 自由探索' : `进入${manifest.steps[targetIndex].title}`, target === EXPLORE ? '全部配置已开放，自由探索不会覆盖分步记录。' : manifest.steps[targetIndex].instruction, '已恢复本步状态；播放处于暂停状态。');
    }
  } else if (command.type === 'retry') {
    let entry = clone(current.entry);
    if (state.active === EXPLORE) { entry = { ...initialModel(manifest), initial: [...model.initial], array: [...model.initial], strategy: model.strategy, speed: model.speed, mu: model.mu, velocity: model.velocity }; }
    state.attempts[state.active] = { id: command.id, entry: clone(entry), model: entry, complete: false };
    if (index >= 0) for (const step of manifest.steps.slice(index + 1)) delete state.attempts[step.id];
    result = feedback('已恢复本步起点', '旧尝试记录仍保留；依赖本次结果的后续步骤需要重做。', '重新尝试本步操作。');
  } else if (command.attempt && command.attempt !== current.id) result = feedback('此操作属于旧的尝试', '当前状态没有改变。', '', 'blocked');
  else if (!allowed(manifest, state, command.action || '')) result = feedback('本步未开放此操作', '只开放与当前学习目标相关的操作。', '可在完整实验中使用全部配置。', 'blocked');
  else {
    const action = command.action || '';
    if (current.complete && state.active !== EXPLORE && !['pause', 'speed'].includes(action)) result = feedback('本步操作已完成', '', '进入下一步，或点击“重试本步”。', 'blocked');
    else if (action === 'pause') result = feedback('已暂停', '当前位置和计数已保留。', '可以单步观察或继续播放。');
    else if (manifest.kind === 'friction' && index > 0 && ['run', 'advance'].includes(action) && !model.changed) result = feedback('请先改变本步参数', '这一阶段需要与上一轮保持其他条件相同，比较一个变量的影响。', '修改本步开放的参数后再运行。', 'blocked');
    else if (action === 'run') result = model.phase === 'done' ? feedback('本轮已经结束', '', '重试后可从初始数据重新运行。', 'no_change') : feedback('开始播放', '每次模型操作会更新画面和解释。', '可随时暂停。');
    else if (action === 'speed') {
      const value = Number(command.value);
      if (!Number.isInteger(value) || value < 1 || value > 5) result = feedback('速度必须为 1–5', '', '', 'invalid');
      else { model.speed = value; result = feedback(`播放速度设为 ${value}`, '只改变播放节奏，不改变实验规则或操作次数。'); }
    } else if (action === 'array') {
      const values = Array.isArray(command.value) ? command.value : [];
      if (values.length < 2 || values.length > 20 || values.some(v => !Number.isInteger(v) || Math.abs(v) > 999)) result = feedback('请输入 2–20 个整数，每个数在 -999–999 之间', '', '', 'invalid');
      else { Object.assign(model, initialModel({ ...manifest, initial: values })); result = feedback('初始数组已更新', '之前的排序结果和计数已清除。', '选择策略后运行，比较实际操作次数。'); }
    } else if (action === 'strategy') {
      if (!['first', 'middle', 'last'].includes(String(command.value))) result = feedback('未知的基准策略', '', '', 'invalid');
      else { const strategy = String(command.value), speed = model.speed; Object.assign(model, initialModel({ ...manifest, initial: model.initial }), { strategy, speed }); result = feedback('基准策略已更新', '已恢复相同初始数组，便于比较不同策略。', '运行后再比较结果。'); }
    } else result = manifest.kind === 'quicksort' ? sorting(model, action, command.value, index === 1) : physics(model, action, command.value);
    if (manifest.kind === 'friction' && index > 0 && ['mu', 'velocity'].includes(action) && result.outcome === 'applied') model.changed = index === 1 ? model.mu !== current.entry.mu : model.velocity !== current.entry.velocity;
    if (index >= 0) current.complete = manifest.kind === 'quicksort' ? index === 0 ? model.phase === 'scan' : index === 1 ? ['range', 'done'].includes(model.phase) : model.phase === 'done' : model.phase === 'done' && (index === 0 || model.changed);
  }
  state.seq++; state.feedback = result;
  state.history = [...state.history, { event: command.id, step: state.active, attempt: currentAttempt(state).id, feedback: result }].slice(-40);
  return state;
}
export function reportedState(manifest: Manifest, session: Session) {
  const m = currentAttempt(session).model;
  return manifest.kind === 'quicksort' ? { parameters: { 初始数组: m.initial, 基准策略: m.strategy, 播放速度: m.speed }, results: { 当前数组: m.array, 比较次数: m.comparisons, 交换次数: m.swaps, 当前阶段: m.phase } } : { parameters: { 摩擦系数: m.mu, 初速度: m.velocity }, results: { 滑行距离: Number(m.distance.toFixed(3)), 已用时间: Number(m.time.toFixed(3)), 当前速度: Number(Math.max(0, m.velocity - m.mu * 9.8 * m.time).toFixed(3)) } };
}
