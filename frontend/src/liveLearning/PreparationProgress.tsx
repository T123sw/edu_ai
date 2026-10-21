import { useState } from 'react';
import { Icon, Modal } from '../selfLearning/ui';
import { isPreparationActive, preparationCopy, preparationFailure, preparationStepIndex, preparationSteps, type PreparationTask } from './preparationProgress';
import './preparationProgress.css';
import { StageAnimation } from './StageAnimation';


export function PreparationProgress({ task, goal, submitting, submitError, connectionError, controlError, controlling, onClose, onControl, onEnter }: {
  task?: PreparationTask;
  goal: string;
  submitting: boolean;
  submitError: string;
  connectionError: string;
  controlError: string;
  controlling: boolean;
  onClose: () => void;
  onControl: (task: PreparationTask, action: 'cancel' | 'retry') => Promise<boolean>;
  onEnter: (courseId: string) => Promise<void>;
}) {
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [entering, setEntering] = useState(false);
  const [entryError, setEntryError] = useState('');
  const failed = task?.status === 'failed' || Boolean(submitError);
  const active = !task || isPreparationActive(task);
  const ready = task?.status === 'succeeded' && task.result_ref?.course_ready && Boolean(task.result_ref.course_id);
  const available = Boolean(task?.result_ref?.course_id && (ready || task.result_ref.course_available));
  const pathAvailable = Boolean(task?.result_ref?.course_id && task.result_ref.path_available);
  const finished = Boolean(task && !isPreparationActive(task));
  const index = preparationStepIndex(task);
  const [title, description] = submitError ? ['提交暂未确认', '请检查提示后重试，相同目标的重复提交不会重复创建任务。']
    : !task && !submitting ? ['正在读取任务进度', '正在同步已提交的课程准备任务。'] : preparationCopy(task);
  const paused = Boolean(connectionError) || finished || failed;
  const failure = preparationFailure(task);
  return <Modal title="课程准备" onClose={onClose} wide>
    <div className={`sl-prep-progress${paused ? ' is-paused' : ''}${failed ? ' has-error' : ''}`}>
      <div className="sl-prep-main">
        <span className={`sl-prep-state${available ? ' is-ready' : ''}`}><i />{ready ? '准备完成' : available ? '已有内容可学习' : pathAvailable && active ? '学习路径已就绪' : failed ? '需要处理' : finished ? '任务已结束' : connectionError ? '正在重连' : submitting ? '正在提交' : 'AI 正在为你备课'}</span>
        <StageAnimation stage={task?.stage || ''} done={Boolean(ready)} stopped={failed || (finished && !ready)} />
        <div className="sl-prep-caption" role="status" aria-live="polite" aria-atomic="true"><h3>{title}</h3><p>{description}</p></div>
        {goal && <p className="sl-prep-goal" title={goal}><Icon name="book" size={15} /><span>{goal}</span></p>}
        {!finished && !failed && <div className="sl-prep-activity" aria-hidden="true"><i /><i /><i /><i /><i /></div>}
        {connectionError && !finished && <p className="sl-prep-notice" role="alert">{connectionError}</p>}
        {failed && <div className="sl-prep-failure" role="alert">{submitError ? <p>{submitError}</p> : <>
          <strong>{failure.title}</strong><p>{failure.reason}</p>
          <p>停止环节：{failure.stage}</p>
          {failure.saved_resources > 0 && <p>{available ? `已开放 ${task?.result_ref?.available_resources || failure.saved_resources} 份资料，可以先开始学习。` : `已保存 ${failure.saved_resources} 份资料草稿，整课尚未完成。`}</p>}
          {failure.resource_issues.length > 0 && <details><summary>查看未完成的内容（{failure.resource_issues.length}）</summary>
            <ul>{failure.resource_issues.map((item, i) => <li key={i}><strong>{item.resource_title} · {item.resource_type}</strong><p>{item.step}：{item.reason}</p></li>)}</ul>
          </details>}
          <p><strong>接下来可以怎么做：</strong>{failure.next_step}</p>
        </>}</div>}
        {(controlError || entryError) && <p className="sl-prep-notice" role="alert">{controlError || entryError}</p>}
      </div>
      <aside className="sl-prep-stages" aria-label="课程准备阶段"><div className="sl-prep-stages-heading">从目标，到一堂好课<span>进度随实际任务更新</span></div>
        <ol>{preparationSteps.map((step, n) => {
          const complete = index > n;
          const current = index === n;
          return <li key={step.title} className={complete ? 'is-complete' : current ? 'is-current' : ''} aria-current={current ? 'step' : undefined}>
            <span className="sl-prep-step-icon"><Icon name={complete ? 'check' : step.icon} size={18} /></span>
            <div><strong>{step.title}</strong><span>{complete ? '已完成' : current ? failed ? '暂未完成' : finished ? '已停止' : '进行中' : '等待进行'}</span></div>
            {current && active && !failed && <i className="sl-prep-step-pulse" />}
          </li>;
        })}</ol>
      </aside>
      <footer className="sl-prep-footer">
        <p><Icon name="clock" size={15} />{finished ? '任务记录可在「后台任务」中查看' : '关闭窗口后继续准备，可在「后台任务」中查看'}</p>
        <div className="sl-prep-buttons">
          {confirmCancel && task && active ? <><span>停止剩余生成，已完成内容会保留。</span><button disabled={controlling} onClick={() => setConfirmCancel(false)}>继续准备</button><button disabled={controlling} className="sl-prep-danger" onClick={() => { void onControl(task, 'cancel').then(ok => { if (ok) setConfirmCancel(false); }); }}>{controlling ? '正在取消…' : '确认取消'}</button></>
            : <>
              {task && active && <button className="sl-prep-cancel" disabled={controlling} onClick={() => setConfirmCancel(true)}>取消任务</button>}
              <button className={ready || failed ? '' : 'sl-prep-primary'} onClick={onClose}>{finished || failed ? '关闭' : '先去浏览'}</button>
              {(task?.status === 'failed' || task?.status === 'canceled') && <button className="sl-prep-primary" disabled={controlling} onClick={() => void onControl(task, 'retry')}>{controlling ? '正在重试…' : available ? '补齐未完成内容' : '继续重试'}<Icon name="arrow" size={15} /></button>}
              {(available || pathAvailable) && <button className="sl-prep-primary" disabled={entering} onClick={async () => {
                setEntering(true); setEntryError('');
                try { await onEnter(task!.result_ref!.course_id!); } catch (cause) { setEntryError(cause instanceof Error ? cause.message : '课程暂时无法打开，请重试。'); } finally { setEntering(false); }
              }}>{entering ? '正在打开…' : ready ? '进入课堂' : available ? '先学习已完成内容' : '查看学习路径'}<Icon name="arrow" size={15} /></button>}
            </>}
        </div>
      </footer>
    </div>
  </Modal>;
}
