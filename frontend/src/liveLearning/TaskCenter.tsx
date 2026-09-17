import { useRef, useState } from 'react';
import { jobKindLabel } from '../jobs/jobPresentation';
import { Icon, Modal } from '../selfLearning/ui';
import type { Classroom } from '../selfLearning/model';
import './taskCenter.css';

export type LearningJob = {
  edu_job_id: string;
  status: string;
  kind?: string;
  message?: string;
  progress?: number;
  course_id?: string;
  retryable?: boolean;
  error_message?: string;
};
const activeStatuses = new Set(['running', 'queued', 'cancel_requested']);
const attentionStatuses = new Set(['failed', 'partially_succeeded', 'canceled', 'cancelled']);
const labels: Record<string, string> = {
  queued: '等待开始', running: '生成中', cancel_requested: '正在取消',
  succeeded: '已完成', partially_succeeded: '部分完成', failed: '生成失败',
  canceled: '已取消', cancelled: '已取消',
};
const filters = [
  { id: 'all', label: '全部' }, { id: 'active', label: '进行中' },
  { id: 'attention', label: '需处理' }, { id: 'done', label: '已完成' },
] as const;
type Filter = typeof filters[number]['id'];
function matches(job: LearningJob, filter: Filter) {
  return filter === 'all' || (filter === 'active' ? activeStatuses.has(job.status)
    : filter === 'attention' ? attentionStatuses.has(job.status) : job.status === 'succeeded');
}

export function TaskLauncher({ jobs, onClick, open }: { jobs: LearningJob[]; onClick: () => void; open: boolean }) {
  const active = jobs.filter(j => activeStatuses.has(j.status)).length;
  const attention = jobs.filter(j => j.status === 'failed' || j.status === 'partially_succeeded').length;
  return <button className={`sl-task-launcher ${active ? 'is-active' : ''}`} onClick={onClick} aria-haspopup="dialog" aria-expanded={open} aria-label={`后台任务${active ? `，${active} 项进行中` : ''}`}>
    <Icon name="clock" size={15} /><span>后台任务</span>
    {active > 0 ? <b>{active}</b> : attention > 0 ? <i title={`${attention} 项任务需处理`} /> : null}
  </button>;
}

export function TaskCenter({ jobs, rooms, onClose, onRetry }: {
  jobs: LearningJob[];
  rooms: Classroom[];
  onClose: () => void;
  onRetry: (id: string) => Promise<unknown>;
}) {
  const [filter, setFilter] = useState<Filter>('all');
  const [pending, setPending] = useState<string[]>([]);
  const pendingIds = useRef(new Set<string>());
  const [submitted, setSubmitted] = useState<string[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const active = jobs.filter(j => activeStatuses.has(j.status)).length;
  const visible = jobs.filter(j => matches(j, filter));
  const sorted = [...visible].sort((a, b) => Number(activeStatuses.has(b.status)) - Number(activeStatuses.has(a.status)));
  async function retry(id: string) {
    if (pendingIds.current.has(id)) return;
    pendingIds.current.add(id);
    setPending(ids => [...ids, id]);
    setErrors(value => ({ ...value, [id]: '' }));
    try {
      await onRetry(id);
      setSubmitted(ids => [...ids, id]);
    } catch (error) {
      setErrors(value => ({ ...value, [id]: error instanceof Error ? error.message : '重试未成功，请稍后再试。' }));
    } finally {
      pendingIds.current.delete(id);
      setPending(ids => ids.filter(value => value !== id));
    }
  }
  return <Modal title="后台任务" onClose={onClose}>
    <div className="sl-task-center">
      <div className="sl-task-summary">
        <span className="sl-task-summary-icon"><Icon name="spark" size={23} /></span>
        <div><h3>{active ? `${active} 项任务正在为你准备内容` : jobs.length ? '每一次探索，都在这里留下进展' : '把准备工作交给 AI'}</h3>
          <p>{active ? '可以继续学习，进度会自动更新。' : '查看生成进度与结果，继续你的学习。'}</p></div>
        <span className="sl-task-sync"><i />自动更新</span>
      </div>
      <div className="sl-task-filters" aria-label="任务筛选">
        {filters.map(item => <button key={item.id} aria-pressed={filter === item.id} onClick={() => setFilter(item.id)}>{item.label}<span>{jobs.filter(j => matches(j, item.id)).length}</span></button>)}
      </div>
      <div className="sl-task-list" aria-label="任务列表">
        {!sorted.length && <div className="sl-task-empty"><span><Icon name={filter === 'done' ? 'check' : 'folder'} size={28} /></span><h3>{jobs.length ? '这里暂时没有任务' : '还没有生成任务'}</h3><p>{jobs.length ? '切换分类，查看其他任务的进展。' : '在首页输入学习目标，任务进度会出现在这里。'}</p></div>}
        {sorted.map(job => {
          const running = activeStatuses.has(job.status);
          const done = job.status === 'succeeded';
          const failed = job.status === 'failed' || job.status === 'partially_succeeded';
          const tone = running ? 'active' : done ? 'done' : failed ? 'failed' : 'muted';
          const course = rooms.find(r => r.id === job.course_id);
          const title = jobKindLabel(job.kind || '');
          const progress = Number.isFinite(job.progress) ? Math.max(0, Math.min(100, Math.round(job.progress!))) : 0;
          const canRetry = job.retryable && attentionStatuses.has(job.status);
          return <article className={`sl-task-card ${tone}`} key={job.edu_job_id}>
            <div className="sl-task-card-top">
              <span className="sl-task-kind"><Icon name={done ? 'check' : failed ? 'close' : running ? 'spark' : 'clock'} size={19} /></span>
              <div className="sl-task-name"><h3>{title}</h3><p title={course?.title}>{course?.title || '学习内容生成'}</p></div>
              <span className="sl-task-status"><i />{labels[job.status] || '状态更新中'}</span>
            </div>
            {job.message && <p className="sl-task-message">{job.message}</p>}
            {running && <div className="sl-task-progress"><div className="sl-task-progress-label"><span>{job.status === 'queued' ? '已加入生成队列' : job.status === 'cancel_requested' ? '正在保存当前进度' : '生成进度'}</span><strong>{progress}%</strong></div><div className="sl-task-track" role="progressbar" aria-label={`${title}进度`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><i style={{ width: `${progress}%` }} /></div></div>}
            {failed && <details className="sl-task-error"><summary>查看失败原因</summary><p>{job.error_message || '任务未能全部完成，请稍后重试。'}</p></details>}
            {(canRetry || (course && done)) && <div className="sl-task-actions">
              {submitted.includes(job.edu_job_id) ? <span className="sl-task-retry-note" role="status"><Icon name="check" size={14} />已提交重试</span> : canRetry ? <button disabled={pending.includes(job.edu_job_id)} onClick={() => void retry(job.edu_job_id)}>{pending.includes(job.edu_job_id) ? '正在提交…' : '重新尝试'}<Icon name="arrow" size={14} /></button> : null}
              {course && done && <a href={`#/classroom/${encodeURIComponent(course.id)}`} onClick={onClose}>进入课堂<Icon name="arrow" size={14} /></a>}
            </div>}
            {errors[job.edu_job_id] && <p className="sl-task-inline-error" role="alert">{errors[job.edu_job_id]}</p>}
          </article>;
        })}
      </div>
      <footer className="sl-task-footer"><Icon name="clock" size={13} /><span>关闭面板后，任务仍会在后台继续。</span></footer>
    </div>
  </Modal>;
}
