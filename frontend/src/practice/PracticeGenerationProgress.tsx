import { useEffect, useState } from 'react';
import { cancelJob, retryJob } from '../jobs/api';
import { isActiveJob, type JobRecord } from '../jobs/types';
import { StageAnimation } from '../liveLearning/StageAnimation';
import { serialPolling } from '../liveLearning/serialPolling';
import { Icon, Modal } from '../selfLearning/ui';
import { apiRequest } from '../stitch/api/client';
import type { PracticeMode } from './PracticeModeSelect';
import '../liveLearning/preparationProgress.css';
import './practiceGenerationProgress.css';

type Props = {
  mode: PracticeMode;
  goal?: string;
  job?: JobRecord | null;
  ready?: boolean;
  submitting?: boolean;
  error?: string;
  submitError?: string;
  onClose: () => void;
  onEnter?: () => void;
  onJobChange?: (job: JobRecord) => void;
};

export function PracticeGenerationProgress({ mode, goal, job, ready, submitting, error, submitError, onClose, onEnter, onJobChange }: Props) {
  const [controlling, setControlling] = useState(false);
  const [controlError, setControlError] = useState('');
  const [confirmCancel, setConfirmCancel] = useState(false);
  const label = mode === 'code' ? '编程项目' : '模拟实验';
  const failed = job?.status === 'failed' || job?.status === 'partially_succeeded' || Boolean(submitError);
  const finished = Boolean(job && !isActiveJob(job));
  const stopped = failed || job?.status === 'canceled';
  const title = ready ? `${label}已准备好` : submitError ? '暂时无法提交' : failed ? '生成暂未完成' : job?.status === 'canceled' ? '已取消生成' : job?.status === 'cancel_requested' ? '正在取消生成' : submitting ? '正在提交' : job?.status === 'queued' ? '正在等待生成' : `正在准备${label}`;
  const control = async (retry: boolean) => {
    if (!job || controlling) return;
    setControlling(true); setControlError('');
    try {
      const next = await (retry ? retryJob(job.edu_job_id) : cancelJob(job.edu_job_id));
      // PBL retries replace the job, but keep the exercise and its polling URL.
      // Simulation resources are still addressed by their generation job ID.
      if (retry && mode !== 'code' && next.edu_job_id !== job.edu_job_id) {
        location.hash = `/practice/${encodeURIComponent(next.edu_job_id)}`;
        return;
      }
      onJobChange?.(next); setConfirmCancel(false);
    } catch { setControlError('操作失败，请稍后重试。'); }
    finally { setControlling(false); }
  };
  return <Modal title={`${label}准备`} onClose={onClose}>
    <div className={`sl-prep-progress sl-practice-generation${finished || stopped || error ? ' is-paused' : ''}`}>
      <div className="sl-prep-main">
        <span className={`sl-prep-state${ready ? ' is-ready' : ''}`}><i />{ready ? '准备完成' : stopped ? '任务已停止' : error ? '正在重连' : 'AI 正在为你准备'}</span>
        <StageAnimation stage="produce" done={Boolean(ready)} stopped={stopped} />
        <div className="sl-prep-caption" role="status" aria-live="polite" aria-atomic="true"><h3>{title}</h3><p>{ready ? '准备好了，随时可以开始动手探索。' : stopped ? '可以关闭窗口，稍后再来。' : job?.message || '正在根据你的目标设计内容，请稍候。'}</p></div>
        {goal && <p className="sl-prep-goal" title={goal}><Icon name="book" size={15} /><span>{goal}</span></p>}
        {!finished && !stopped && <div className="sl-prep-activity" aria-hidden="true"><i /><i /><i /><i /><i /></div>}
        {(submitError || job?.error_message || job?.error) && <p className="sl-prep-failure" role="alert">{submitError || job?.error_message || job?.error}</p>}
        {(error || controlError) && <p className="sl-prep-notice" role="alert">{controlError || error}</p>}
      </div>
      <footer className="sl-prep-footer">
        <p><Icon name="clock" size={15} />{finished || submitError ? '可在首页或「后台任务」中查看' : '关闭窗口后继续生成，可稍后从首页查看'}</p>
        <div className="sl-prep-buttons">
          {confirmCancel && job?.cancelable ? <><span>确定停止本次生成？</span><button disabled={controlling} onClick={() => setConfirmCancel(false)}>继续生成</button><button className="sl-prep-danger" disabled={controlling} onClick={() => void control(false)}>确认取消</button></> : <>
            {job?.cancelable && <button className="sl-prep-cancel" disabled={controlling} onClick={() => setConfirmCancel(true)}>取消生成</button>}
            <button onClick={onClose}>{finished || submitError ? '关闭' : '先去浏览'}</button>
            {job?.retryable && <button className="sl-prep-primary" disabled={controlling} onClick={() => void control(true)}>{controlling ? '正在重试…' : '重试生成'}</button>}
            {ready && onEnter && <button className="sl-prep-primary" onClick={onEnter}>{mode === 'code' ? '进入项目' : '进入实验'}<Icon name="arrow" size={15} /></button>}
          </>}
        </div>
      </footer>
    </div>
  </Modal>;
}

export function TrackedPracticeGeneration({ id, ...props }: Omit<Props, 'job' | 'ready' | 'error' | 'onJobChange'> & { id?: string }) {
  const [detail, setDetail] = useState<{ job: JobRecord | null; artifact: unknown }>();
  const [error, setError] = useState('');
  useEffect(() => {
    if (!id) return;
    return serialPolling(async signal => {
      try {
        const next = await apiRequest<{ job: JobRecord | null; artifact: unknown }>(`/api/${props.mode === 'code' ? 'pbl' : 'practice'}/${encodeURIComponent(id)}`, { signal });
        if (!signal.aborted) { setDetail(next); setError(''); }
      } catch { if (!signal.aborted) setError('暂时无法读取进度，正在重新连接。'); }
    }, 2000);
  }, [id, props.mode]);
  return <PracticeGenerationProgress {...props} job={detail?.job} ready={Boolean(detail?.artifact)} error={error} onJobChange={job => setDetail(previous => ({ artifact: previous?.artifact, job }))} />;
}
