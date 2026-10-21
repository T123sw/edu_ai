/** Deterministic teaching prototype. Animation and explanations never advance the algorithm. */
export type Phase = 'demo' | 'practice';
export type Item = { id: string; value: number };
export type Feedback = { kind: 'info' | 'success' | 'error'; title: string; explanation: string };
export type Lesson = {
  items: Item[]; initial: number[]; cursor: number; round: number; targetRounds: number;
  comparisons: number; swaps: number; selected: number[]; mode: 'compare' | 'decide' | 'round-end' | 'done';
  feedback: Feedback; history: Feedback[]; hints: number; hintLevel: number; errors: number;
  demoKeep: boolean;
};
export type Action =
  | { type: 'select'; index: number }
  | { type: 'compare' }
  | { type: 'decide'; swap: boolean }
  | { type: 'finish-round' }
  | { type: 'keep-example' }
  | { type: 'clear' }
  | { type: 'hint' };
export type PrototypeAction = Action | { type: 'phase'; phase: Phase } | { type: 'reset' };
export type Prototype = { phase: Phase; demo: Lesson; practice: Lesson };
const message = (title: string, explanation: string, kind: Feedback['kind'] = 'info'): Feedback => ({ title, explanation, kind });
export function createLesson(phase: Phase, values = phase === 'demo' ? [5, 3, 4, 1] : [5, 1, 4, 2, 8, 3]): Lesson {
  if (values.length < 3 || values.some(value => !Number.isFinite(value))) throw Error('Invalid teaching array');
  return {
    initial: [...values], items: values.map((value, index) => ({ id: `element-${index}`, value })),
    cursor: 0, round: 0, targetRounds: phase === 'demo' ? 1 : 2, comparisons: 0, swaps: 0,
    selected: [], mode: 'compare', hints: 0, hintLevel: 0, errors: 0, demoKeep: false, history: [],
    feedback: phase === 'demo'
      ? message('从最左边的一对开始', `先比较 ${values[0]} 和 ${values[1]}。升序排列时，只有左边大于右边，才交换它们。`)
      : message('现在由你完成两轮', '从左侧开始，选择两个相邻元素，再决定交换还是保持顺序。你认为这一轮结束时，点击“本轮完成”。'),
  };
}
export const createPrototype = (): Prototype => ({ phase: 'demo', demo: createLesson('demo'), practice: createLesson('practice') });
function tell(state: Lesson, feedback: Feedback, record = true): Lesson {
  state.feedback = feedback;
  if (feedback.kind === 'error') state.errors++;
  if (record) state.history = [...state.history, feedback].slice(-12);
  return state;
}
export function hintFor(state: Lesson, level: number): string {
  if (state.mode === 'done') return '两轮任务已经完成。末尾两个元素已归位，前面的元素仍可能无序。';
  if (level === 1) return '每次只比较相邻元素，从左向右连续扫描；左边大于右边才交换。已归位的右侧元素不参加下一轮。';
  if (state.mode === 'round-end') return level === 2 ? '回想本轮是否已经比较到未排序区间的最右侧。' : '本轮的相邻比较已经做完，可以点击“本轮完成”。';
  const [left, right] = state.items.slice(state.cursor, state.cursor + 2);
  if (level === 2) return `检查第 ${state.cursor + 1}、${state.cursor + 2} 个位置。这两个元素应该是本次比较对象。`;
  return `${left.value} ${left.value > right.value ? '>' : '≤'} ${right.value}，这次应${left.value > right.value ? '交换' : '保持顺序'}。请你亲手完成这个操作。`;
}
export function reduceLesson(previous: Lesson, action: Action, phase: Phase): Lesson {
  const state: Lesson = structuredClone(previous);
  if (action.type === 'hint') {
    state.hints++; state.hintLevel = Math.min(3, state.hintLevel + 1);
    return tell(state, message(`提示 ${state.hintLevel} / 3`, hintFor(state, state.hintLevel)));
  }
  if (action.type === 'keep-example') {
    if (phase !== 'demo' || state.mode !== 'round-end' || state.demoKeep) return tell(state, message('先完成当前演示', '保持顺序的例子会在第一轮结束后开放。', 'error'));
    state.demoKeep = true; state.cursor = 0; state.mode = 'compare'; state.selected = [];
    return tell(state, message('再看一次不需要交换的情况', `第一轮已把最大值放到末尾。现在只观察 ${state.items[0].value} 和 ${state.items[1].value}，理解为什么有时要保持顺序。`));
  }
  if (state.mode === 'done') return tell(state, message('本阶段已经完成', '可以回看操作记录，或重新开始本阶段。'));
  if (action.type === 'clear') {
    state.selected = [];
    return tell(state, message('已取消选择', '数组和比较次数保持不变，你可以重新选择。'), false);
  }
  if (action.type === 'select') {
    if (phase !== 'practice') return tell(state, message('当前是原理演示', '使用下方的比较和交换按钮，逐次观察。', 'error'));
    if (!Number.isInteger(action.index) || action.index < 0 || action.index >= state.items.length) return tell(state, message('没有这个元素', '请选择数组中的元素。', 'error'));
    if (state.selected.includes(action.index)) state.selected = state.selected.filter(index => index !== action.index);
    else state.selected = state.selected.length >= 2 ? [action.index] : [...state.selected, action.index].sort((a, b) => a - b);
    if (state.selected.length < 2) return tell(state, message(state.selected.length ? `已选择 ${state.items[action.index].value}` : '已取消选择', state.selected.length ? '再选择一个元素，然后判断是否需要交换。' : '请选择你准备比较的两个元素。'), false);
    const [a, b] = state.selected;
    if (b !== a + 1) return tell(state, message('这两个元素不相邻', '冒泡排序每次只比较相邻元素。点击已选元素可取消，再重新选择。', 'error'));
    if (state.mode === 'round-end') return tell(state, message('先判断本轮是否结束', '回顾刚才的比较，再决定是否点击“本轮完成”。', 'error'));
    if (a !== state.cursor) return tell(state, message('检查本轮的比较顺序', '本轮需要从左向右连续比较；进入新一轮时，从最左边重新开始。', 'error'));
    return tell(state, message(`已选择 ${state.items[a].value} 和 ${state.items[b].value}`, '比较左、右两个值，选择“交换”或“保持顺序”。'), false);
  }
  if (action.type === 'finish-round') {
    if (phase !== 'practice') return tell(state, message('请按演示顺序操作', '完成比较和交换后，会显示本轮总结。', 'error'));
    if (state.mode !== 'round-end') return tell(state, message('这一轮还没有结束', '未排序区间中还有相邻元素没有按顺序比较。请继续本轮操作。', 'error'));
    state.round++; state.cursor = 0; state.selected = []; state.hintLevel = 0;
    state.mode = state.round >= state.targetRounds ? 'done' : 'compare';
    return tell(state, state.mode === 'done'
      ? message('两轮练习完成', `你完成了 ${state.comparisons} 次比较、${state.swaps} 次交换。末尾两个元素已归位，前面的元素仍可能无序；两轮完成不等于整个数组排好。`, 'success')
      : message('第一轮完成，开始第二轮', `最大值 ${state.items.at(-1)!.value} 已归位。第二轮从左侧重新开始，末尾已归位的元素不再参与比较。`, 'success'));
  }
  if (state.mode === 'round-end') return tell(state, message('本轮比较已结束', phase === 'practice' ? '请判断并点击“本轮完成”。' : '观察本轮结果，再查看保持顺序的例子。'));
  if (action.type === 'compare') {
    if (phase !== 'demo' || state.mode !== 'compare') return tell(state, message('当前不能重复比较', '请先完成这次比较对应的判断。', 'error'));
    state.comparisons++; state.mode = 'decide';
    const [left, right] = state.items.slice(state.cursor, state.cursor + 2);
    return tell(state, message(`比较 ${left.value} 和 ${right.value}`, left.value > right.value ? `${left.value} > ${right.value}，左边更大。请执行交换，让较大的元素向右移动。` : `${left.value} ≤ ${right.value}，当前顺序符合升序。保持顺序，仍然算完成了一次比较。`));
  }
  if (action.type === 'decide') {
    if (phase === 'demo' && state.mode !== 'decide') return tell(state, message('先比较，再决定', '请先比较当前高亮的两个元素。', 'error'));
    if (phase === 'practice' && (state.selected.length !== 2 || state.selected[0] !== state.cursor || state.selected[1] !== state.cursor + 1)) return tell(state, message('先选对比较对象', '需要选择本轮正在处理的一对相邻元素；按从左到右的顺序进行。', 'error'));
    const [left, right] = state.items.slice(state.cursor, state.cursor + 2);
    if (action.swap !== (left.value > right.value)) return tell(state, message('再判断一下是否需要交换', `${left.value} ${left.value > right.value ? '>' : '≤'} ${right.value}，升序排列应${left.value > right.value ? '交换' : '保持顺序'}。这次尝试没有改变数组和算法计数。`, 'error'));
    if (phase === 'practice') state.comparisons++;
    if (action.swap) { [state.items[state.cursor], state.items[state.cursor + 1]] = [right, left]; state.swaps++; }
    state.cursor++; state.selected = []; state.hintLevel = 0;
    state.mode = state.cursor >= state.items.length - 1 - state.round ? 'round-end' : 'compare';
    if (phase === 'demo' && state.demoKeep) state.mode = 'done';
    let why = action.swap ? `${left.value} > ${right.value}，交换后较大的 ${left.value} 向右移动了一格。` : `${left.value} ≤ ${right.value}，保持顺序，数组没有改变。`;
    if (phase === 'demo') {
      if (state.mode === 'round-end') why += ` 第一轮结束，最大值 ${state.items.at(-1)!.value} 已到最右侧，其他元素还不一定有序。`;
      else if (state.mode === 'done') why += ' 你已看过完整一轮和无需交换的情况，可以开始手动练习。';
      else why += ` 接下来比较 ${state.items[state.cursor].value} 和 ${state.items[state.cursor + 1].value}。`;
    } else why += ' 接下来由你判断继续比较，还是这一轮已经完成。';
    return tell(state, message(action.swap ? `已交换 ${left.value} 和 ${right.value}` : '保持顺序，判断正确', why, 'success'));
  }
  return state;
}
export function reducePrototype(state: Prototype, action: PrototypeAction): Prototype {
  if (action.type === 'phase') return { ...state, phase: action.phase };
  if (action.type === 'reset') return { ...state, [state.phase]: createLesson(state.phase) };
  return { ...state, [state.phase]: reduceLesson(state[state.phase], action, state.phase) };
}
