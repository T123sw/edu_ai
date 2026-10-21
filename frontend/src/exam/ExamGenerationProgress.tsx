import { StageAnimation } from '../liveLearning/StageAnimation';
import { Icon, Modal } from '../selfLearning/ui';
import '../liveLearning/preparationProgress.css';

export type ExamGeneration = {
  generation_id: string; job_id: string; status: string; progress: number;
  message: string; requirement: string; title?: string; error_code?: string;
  practice_summary?: {status: string; submitted: number; total: number} | null;
};

export function ExamGenerationProgress({ task, goal, submitting, submitError, connectionError, busy, onClose, onRetry, onView }: {
  task: ExamGeneration | null; goal: string; submitting: boolean; submitError: string;
  connectionError: string; busy: boolean; onClose: () => void; onRetry: () => void; onView: () => void;
}) {
  const ready = task?.status === 'succeeded';
  const failed = task?.status === 'failed' || Boolean(submitError);
  const stopped = failed || task?.status === 'canceled';
  const title = ready ? '试卷已准备好' : failed ? '生成暂未完成' : stopped ? '已取消生成'
    : submitting ? '正在提交' : task?.status === 'queued' || task?.status === 'pending' ? '正在等待生成' : '正在准备模拟试卷';
  return <Modal title="试卷准备" onClose={onClose}>
    <div className={`sl-prep-progress sl-exam-generation${ready || stopped || connectionError ? ' is-paused' : ''}`}>
      <div className="sl-prep-main">
        <span className={`sl-prep-state${ready ? ' is-ready' : ''}`}><i />{ready ? '准备完成' : stopped ? '任务已停止' : connectionError ? '正在重连' : 'AI 正在为你准备'}</span>
        <StageAnimation stage="produce" done={ready} stopped={stopped} />
        <div className="sl-prep-caption" role="status" aria-live="polite" aria-atomic="true">
          <h3>{title}</h3><p>{ready ? '试卷已生成，可以查看题目。' : submitError || task?.message || '正在根据你的要求准备题目，请稍候。'}</p>
        </div>
        {goal && <p className="sl-prep-goal" title={goal}><Icon name="quiz" size={15} /><span>{goal}</span></p>}
        {!ready && !stopped && <>
          <div className="sl-prep-activity" aria-hidden="true"><i /><i /><i /><i /><i /></div>
          <progress className="exam-generation-meter" max="100" value={task ? Math.max(0, Math.min(100, task.progress)) : undefined} aria-label="试卷生成进度" />
        </>}
        {failed && <p className="sl-prep-failure">本次未生成完整试卷，可重试生成。</p>}
        {connectionError && <p className="sl-prep-notice" role="alert">{connectionError}</p>}
      </div>
      <footer className="sl-prep-footer">
        <p><Icon name="clock" size={15} />{ready ? '可从“我的试卷”查看试卷' : stopped ? '本次任务不会保留在“我的试卷”中' : '关闭窗口后继续生成，可稍后从首页查看'}</p>
        <div className="sl-prep-buttons">
          <button onClick={onClose}>{ready || stopped ? '关闭' : '先去浏览'}</button>
          {task?.status === 'failed' && <button className="sl-prep-primary" disabled={busy} onClick={onRetry}>{busy ? '正在重试…' : '重试生成'}</button>}
          {ready && <button className="sl-prep-primary" disabled={busy} onClick={onView}>查看试卷<Icon name="arrow" size={15} /></button>}
        </div>
      </footer>
    </div>
  </Modal>;
}
