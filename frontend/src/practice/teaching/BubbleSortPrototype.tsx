import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { reducePrototype, type Feedback, type Phase, type PrototypeAction } from './domains/bubbleSort';
import { restorePrototype, STORAGE_KEY } from './prototypeStorage';
import './bubblePrototype.css';

const stages = ['原理演示', '手动练习', '性能测试', '自由探索'];
function Explanation({ feedback }: { feedback: Feedback }) {
  return <div className={`bubble-feedback ${feedback.kind}`} role="status" aria-live="polite" aria-atomic="true"><span className="bubble-feedback-label">{feedback.kind === 'error' ? '再试一次' : '当前讲解'}</span><h3>{feedback.title}</h3><p>{feedback.explanation}</p></div>;
}
export function BubbleSortPrototype({ owner = '', embedded = false }: { owner?: string; embedded?: boolean }) {
  const storageKey = owner ? `${STORAGE_KEY}:${encodeURIComponent(owner)}` : STORAGE_KEY;
  const [saved] = useState(() => { try { return restorePrototype(sessionStorage.getItem(storageKey)); } catch { return { ...restorePrototype(null), warning: '浏览器未允许保存，本次进度仅保留到页面关闭前。' }; } });
  const [state, setState] = useState(saved.state);
  const [warning, setWarning] = useState(saved.warning);
  const [resetting, setResetting] = useState(false);
  const actions = useRef(saved.actions);
  const stateRef = useRef(state);
  const [saveVersion, setSaveVersion] = useState(0);
  const lesson = state[state.phase];
  const demo = state.phase === 'demo';
  const completed = lesson.mode === 'done';
  const values = lesson.items.map(item => item.value);
  const pair = demo && ['compare', 'decide'].includes(lesson.mode) ? [lesson.cursor, lesson.cursor + 1] : lesson.selected;
  const sorted = demo ? (lesson.mode === 'round-end' || lesson.demoKeep ? 1 : 0) : lesson.round;
  const needsSwap = lesson.items[lesson.cursor]?.value > lesson.items[lesson.cursor + 1]?.value;
  const send = (action: PrototypeAction) => {
    const next = reducePrototype(stateRef.current, action);
    stateRef.current = next; setState(next); actions.current = [...actions.current, action]; setSaveVersion(version => version + 1);
    if (action.type === 'phase' || action.type === 'reset') setResetting(false);
  };
  useEffect(() => {
    try {
      if (actions.current.length > 4000) { setWarning('原型操作记录已达上限，刷新后可能无法恢复最新操作。'); return; }
      sessionStorage.setItem(storageKey, JSON.stringify({ version: 1, actions: actions.current }));
    } catch { setWarning('无法保存本页进度，请暂时不要刷新或关闭页面。'); }
  }, [saveVersion, storageKey]);
  const changePhase = (phase: Phase) => send({ type: 'phase', phase });
  return <div className="bubble-prototype">
    <header className="bubble-topbar"><div className="bubble-brand">{embedded ? <a className="bubble-back" href="#/practice">返回模拟实验</a> : <><span aria-hidden="true">✧</span> Edu AI</>}<span className="bubble-divider">/</span><h1>冒泡排序</h1></div><span className="bubble-preview-tag">交互原型 · 前两阶段</span></header>
    {warning && <p className="bubble-warning" role="alert">{warning}</p>}
    <div className="bubble-workspace">
      <nav className="bubble-rail" aria-label="教学阶段"><span className="bubble-eyebrow">实验路线</span><ol>{stages.map((name, index) => {
        const phase = index === 0 ? 'demo' : 'practice';
        return <li key={name}><button disabled={index > 1} aria-current={index < 2 && state.phase === phase ? 'step' : undefined} onClick={() => changePhase(phase)}><span className="bubble-step-number">0{index + 1}</span><span>{name}<small>{index > 1 ? '后续阶段' : state[phase].mode === 'done' ? '已完成' : index === 0 ? '跟着操作，理解规则' : '自己选择，自己判断'}</small></span></button></li>;
      })}</ol><p className="bubble-rail-note">升序排列<br/>相邻比较 · 从左向右</p></nav>
      <main className="bubble-main">
        <div className="bubble-stage-heading"><div><span className="bubble-eyebrow">{demo ? '01 / 观察与理解' : '02 / 动手与判断'}</span><h2>{demo ? '原理演示' : '手动练习'}</h2></div><span className={`bubble-round ${completed ? 'complete' : ''}`}>{completed ? demo ? '演示完成' : '两轮完成' : demo && lesson.demoKeep ? '保持顺序示例' : `第 ${Math.min(lesson.round + 1, lesson.targetRounds)} 轮`}</span></div>
        <p className="bubble-objective">{demo ? '每次只做一个动作，观察较大的元素怎样逐渐移向右侧。' : '请亲手完成两轮。选择相邻元素，判断是否交换，再判断本轮何时结束。'}</p>
        <section className="bubble-scene" aria-label="数组实验区">
          <div className="bubble-scene-top"><span>{demo ? lesson.demoKeep ? '第一轮后的数组' : '从左侧开始扫描' : '点击两个元素进行比较'}</span><span>小 <span aria-hidden="true">→</span> 大</span></div>
          <div className="bubble-board" data-values={values.join(',')} style={{ '--bubble-count': lesson.items.length } as CSSProperties}>
            {lesson.items.map((item, index) => <div key={item.id} className="bubble-slot" style={{ left: `${index * 100 / lesson.items.length}%` }}>
              <span className="bubble-element-state">{index >= lesson.items.length - sorted ? '已归位' : pair.includes(index) ? demo ? '比较中' : '已选择' : '\u00a0'}</span>
              <button className={`bubble-element ${pair.includes(index) ? 'selected' : ''} ${index >= lesson.items.length - sorted ? 'sorted' : ''}`} style={{ height: `${100 + item.value / Math.max(...values) * 140}px` }} disabled={demo || completed} aria-label={`第${index + 1}个元素，值${item.value}`} aria-pressed={!demo ? lesson.selected.includes(index) : undefined} onClick={() => send({ type: 'select', index })}><strong>{item.value}</strong></button>
              <span className="bubble-position">{index + 1}</span>
            </div>)}
          </div>
          <div className="bubble-scene-bottom"><span><i className="selected"/>{demo ? '当前比较' : '你的选择'}</span><span><i className="sorted"/>已归位</span><span className="bubble-initial">初始：{lesson.initial.join(' · ')}</span></div>
        </section>
        <div className="bubble-mobile-feedback"><Explanation feedback={lesson.feedback}/></div>
        <section className="bubble-controls" aria-label={demo ? '演示操作' : '练习操作'}>
          <div className="bubble-action-row">
            {demo ? <>
              {lesson.mode === 'compare' && <button className="bubble-primary" onClick={() => send({ type: 'compare' })}>比较这两个数 <span aria-hidden="true">→</span></button>}
              {lesson.mode === 'decide' && <button className="bubble-primary" onClick={() => send({ type: 'decide', swap: needsSwap })}>{needsSwap ? '执行交换' : '保持顺序'} <span aria-hidden="true">{needsSwap ? '⇄' : '='}</span></button>}
              {lesson.mode === 'round-end' && <button className="bubble-primary" onClick={() => send({ type: 'keep-example' })}>看看无需交换的情况 <span aria-hidden="true">→</span></button>}
              {completed && <button className="bubble-primary" onClick={() => changePhase('practice')}>开始手动练习 <span aria-hidden="true">→</span></button>}
            </> : <>
              <button className="bubble-primary" disabled={completed || lesson.selected.length !== 2} onClick={() => send({ type: 'decide', swap: true })}>交换 <span aria-hidden="true">⇄</span></button>
              <button disabled={completed || lesson.selected.length !== 2} onClick={() => send({ type: 'decide', swap: false })}>保持顺序</button>
              <button className="bubble-round-finish" disabled={completed} onClick={() => send({ type: 'finish-round' })}>本轮完成</button>
            </>}
          </div>
          <div className="bubble-secondary-actions">{!demo && <><button disabled={completed || !lesson.selected.length} onClick={() => send({ type: 'clear' })}>取消选择</button><button disabled={completed} onClick={() => send({ type: 'hint' })}>{lesson.hintLevel ? '再具体一点' : '给我一个提示'}</button></>}<button onClick={() => setResetting(true)}>重新{demo ? '演示' : '练习'}</button></div>
          {resetting && <div className="bubble-reset" role="group" aria-label="重新开始本阶段"><p>将从本阶段的初始数组重新开始，另一个阶段的进度会保留。</p><button className="bubble-primary" onClick={() => send({ type: 'reset' })}>确认重新开始</button><button onClick={() => setResetting(false)}>保留当前进度</button></div>}
        </section>
        <dl className="bubble-metrics"><div><dt>比较次数</dt><dd data-testid="comparisons">{lesson.comparisons}</dd></div><div><dt>交换次数</dt><dd data-testid="swaps">{lesson.swaps}</dd></div><div><dt>{demo ? '当前方式' : '提示使用'}</dt><dd className="bubble-metric-small">{demo ? '逐次操作' : `${lesson.hints} 次`}</dd></div></dl>
        {completed && !demo && <div className="bubble-completion"><h3>两轮练习已完成</h3><p>{lesson.hints ? `本次使用了 ${lesson.hints} 次提示。` : '本次没有使用提示。'}你完成了 {lesson.comparisons} 次比较和 {lesson.swaps} 次交换。末尾两个元素已归位，前面的元素仍可能无序。</p><p>性能测试和自由探索将在后续阶段开放。</p></div>}
        <details className="bubble-history"><summary>回看本阶段操作 <span>{lesson.history.length} 条最近记录</span></summary>{lesson.history.length ? <ol>{lesson.history.map((entry, index) => <li key={index} className={entry.kind}><strong>{entry.title}</strong><p>{entry.explanation}</p></li>)}</ol> : <p>完成一次操作后，讲解会保留在这里。</p>}</details>
        <p className="bubble-local-note">本页自动保留进度，刷新可继续。原型使用规则讲解，暂未接入 AI 对话。</p>
      </main>
      <aside className="bubble-guide" aria-label="操作讲解"><div className="bubble-guide-heading"><span aria-hidden="true">✧</span><div><h2>操作讲解</h2><p>跟随你的每一次比较与判断</p></div></div><Explanation feedback={lesson.feedback}/>
        <section className="bubble-rule"><span className="bubble-eyebrow">记住这条规则</span><h3>相邻比较，大的向右</h3><p>从最左侧的一对开始。左边大于右边时交换，否则保持顺序。</p><div className="bubble-rule-example" aria-label="5 大于 3，交换后 3 在左，5 在右"><span>5 · 3</span><span aria-hidden="true">→</span><span>3 · 5</span></div><p>到达未排序区间的右端，一轮才结束。最大值归位后，下一轮从左侧重新开始。</p></section>
        <div className="bubble-reflection"><span className="bubble-eyebrow">想一想</span><p>{demo ? '一轮结束时，为什么只有最右侧的元素可以确定已经归位？' : '完成两轮后，能否确定整个数组都已经有序？'}</p></div>
      </aside>
    </div>
  </div>;
}
