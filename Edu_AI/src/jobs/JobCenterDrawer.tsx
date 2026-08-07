import { useEffect, useMemo, useState } from "react";
import { cancelJob, retryJob } from "./api";
import {
  jobKindLabel,
  presentJobDetail,
  summarizeJobs,
} from "./jobPresentation";
import { getJobResultHash } from "./jobResultTarget";
import { registerCreatedJob, useJobStore } from "./jobStore";
import { isActiveJob, type JobRecord } from "./types";
import { MaterialIcon } from "../stitch/shared";
import "./jobCenter.css";

const OPEN_JOB_CENTER_EVENT = "edu-ai:open-job-center";

export function JobCenterTrigger({
  placement = "floating",
}: {
  placement?: "floating" | "inline";
}) {
  const activeCount = useJobStore((state) => state.activeCount);
  const unreadIds = useJobStore((state) => state.unreadTerminalIds);
  const jobsById = useJobStore((state) => state.jobs);
  const hasUnreadFailure = unreadIds.some(
    (id) =>
      jobsById[id]?.status === "failed" ||
      jobsById[id]?.status === "partially_succeeded",
  );

  return (
    <button
      type="button"
      className={`job-center-launcher job-center-launcher--${placement}`}
      onClick={() => window.dispatchEvent(new Event(OPEN_JOB_CENTER_EVENT))}
      aria-label={`任务中心${activeCount ? `，${activeCount} 个进行中` : ""}`}
    >
      <MaterialIcon name="notifications" />
      {placement === "inline" ? (
        <span className="job-center-launcher__label">后台任务</span>
      ) : null}
      {activeCount ? (
        <span className="job-center-launcher__badge">{activeCount}</span>
      ) : null}
      {hasUnreadFailure ? (
        <span className="job-center-launcher__failure" aria-label="有失败任务" />
      ) : null}
    </button>
  );
}

export function JobCenterDrawer({ showLauncher = true }: { showLauncher?: boolean }) {
  const [open, setOpen] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const jobsById = useJobStore((state) => state.jobs);
  const orderedIds = useJobStore((state) => state.orderedIds);
  const activeCount = useJobStore((state) => state.activeCount);
  const hydrated = useJobStore((state) => state.hydrated);
  const pollFailures = useJobStore((state) => state.pollFailures);
  const markAllRead = useJobStore((state) => state.markAllRead);
  const mergeJobs = useJobStore((state) => state.mergeJobs);
  const jobs = useMemo(
    () => orderedIds.map((id) => jobsById[id]).filter(Boolean),
    [jobsById, orderedIds],
  );
  const groups = useMemo(
    () => ({
      active: jobs.filter(isActiveJob),
      attention: jobs.filter(
        (job) =>
          job.status === "failed" || job.status === "partially_succeeded",
      ),
      completed: jobs
        .filter(
          (job) => job.status === "succeeded" || job.status === "canceled",
        )
        .slice(0, 20),
    }),
    [jobs],
  );
  const qualitySummary = useMemo(() => summarizeJobs(jobs), [jobs]);

  useEffect(() => {
    const handleOpen = () => {
      setOpen(true);
      markAllRead();
    };
    window.addEventListener(OPEN_JOB_CENTER_EVENT, handleOpen);
    return () => window.removeEventListener(OPEN_JOB_CENTER_EVENT, handleOpen);
  }, [markAllRead]);

  const runAction = async (
    job: JobRecord,
    action: "cancel" | "retry",
  ) => {
    setBusyId(job.edu_job_id);
    setActionError(null);
    try {
      const updated =
        action === "cancel"
          ? await cancelJob(job.edu_job_id)
          : await retryJob(job.edu_job_id);
      if (action === "retry") registerCreatedJob(updated);
      else mergeJobs([updated]);
    } catch {
      setActionError("任务操作失败，请稍后重试");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      {showLauncher ? <JobCenterTrigger /> : null}

      {open ? (
        <div className="job-center-layer" role="presentation">
          <button
            type="button"
            className="job-center-backdrop"
            onClick={() => setOpen(false)}
            aria-label="关闭任务中心"
          />
          <aside
            className="job-center-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="job-center-title"
          >
            <header className="job-center-header">
              <div>
                <p className="job-center-eyebrow">全局后台任务</p>
                <h2 id="job-center-title">任务中心</h2>
                <p>
                  {pollFailures
                    ? `连接暂时中断，正在第 ${pollFailures} 次重试`
                    : activeCount
                      ? `${activeCount} 个任务正在后台继续`
                      : "当前没有进行中的任务"}
                </p>
              </div>
              <button
                type="button"
                className="job-center-close"
                onClick={() => setOpen(false)}
                aria-label="关闭任务中心"
              >
                <MaterialIcon name="close" />
              </button>
            </header>

            {actionError ? (
              <div className="job-center-action-error" role="alert">
                {actionError}
              </div>
            ) : null}

            <div className="job-center-content">
              {qualitySummary.completedCount ? (
                <section
                  className="job-center-quality"
                  aria-label="最近后台任务质量概览"
                >
                  <div>
                    <span>已结束</span>
                    <strong>{qualitySummary.completedCount}</strong>
                  </div>
                  <div>
                    <span>需关注率</span>
                    <strong>{qualitySummary.failureRate}%</strong>
                  </div>
                  <div>
                    <span>平均耗时</span>
                    <strong>
                      {formatDuration(qualitySummary.averageDurationMs)}
                    </strong>
                  </div>
                </section>
              ) : null}
              {!hydrated ? (
                <JobEmpty
                  title="正在恢复后台任务"
                  detail="正在从服务器读取当前账号的任务记录…"
                />
              ) : jobs.length === 0 ? (
                <JobEmpty
                  title="还没有后台任务"
                  detail="从生成工厂发起课堂、报告、PPT 等任务后，可在这里跨页面查看进度。"
                />
              ) : (
                <>
                  <JobGroup
                    title="进行中"
                    jobs={groups.active}
                    busyId={busyId}
                    onAction={runAction}
                  />
                  <JobGroup
                    title="需要处理"
                    jobs={groups.attention}
                    busyId={busyId}
                    onAction={runAction}
                  />
                  <JobGroup
                    title="最近完成"
                    jobs={groups.completed}
                    busyId={busyId}
                    onAction={runAction}
                  />
                </>
              )}
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}

function JobGroup({
  title,
  jobs,
  busyId,
  onAction,
}: {
  title: string;
  jobs: JobRecord[];
  busyId: string | null;
  onAction: (job: JobRecord, action: "cancel" | "retry") => Promise<void>;
}) {
  if (jobs.length === 0) return null;
  return (
    <section className="job-center-group">
      <div className="job-center-group__title">
        <h3>{title}</h3>
        <span>{jobs.length}</span>
      </div>
      <div className="job-center-list">
        {jobs.map((job) => (
          <JobCard
            key={job.edu_job_id}
            job={job}
            busy={busyId === job.edu_job_id}
            onAction={onAction}
          />
        ))}
      </div>
    </section>
  );
}

function JobCard({
  job,
  busy,
  onAction,
}: {
  job: JobRecord;
  busy: boolean;
  onAction: (job: JobRecord, action: "cancel" | "retry") => Promise<void>;
}) {
  const title =
    typeof job.input_summary.title === "string"
      ? job.input_summary.title
      : jobKindLabel(job.kind);
  const resultHash = getJobResultHash(job);
  return (
    <article className={`job-card is-${job.status}`}>
      <div className="job-card__top">
        <span className="job-card__icon">
          <MaterialIcon name={jobIcon(job.kind)} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="job-card__kind">{jobKindLabel(job.kind)}</p>
          <h4 title={title}>{title}</h4>
          <p className="job-card__course">
            {job.course_id ? `课程：${job.course_id}` : "全局任务"}
          </p>
        </div>
        <span className={`job-card__status is-${job.status}`}>
          {jobStatusLabel(job.status)}
        </span>
      </div>
      <div className="job-card__progress" aria-label={`任务进度 ${job.progress}%`}>
        <span style={{ width: `${Math.max(job.progress, isActiveJob(job) ? 4 : 0)}%` }} />
      </div>
      <div className="job-card__detail">
        <p>{presentJobDetail(job)}</p>
        <time dateTime={job.updated_at}>{formatTime(job.updated_at)}</time>
      </div>
      <div className="job-card__actions">
        <button
          type="button"
          onClick={() => void navigator.clipboard?.writeText(job.edu_job_id)}
        >
          复制任务 ID
        </button>
        {job.cancelable && isActiveJob(job) ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void onAction(job, "cancel")}
          >
            {busy ? "处理中…" : "取消"}
          </button>
        ) : null}
        {job.retryable ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void onAction(job, "retry")}
          >
            {busy ? "处理中…" : "重试"}
          </button>
        ) : null}
        {resultHash ? (
          <a href={resultHash} onClick={() => undefined}>
            打开结果
          </a>
        ) : null}
      </div>
    </article>
  );
}

function JobEmpty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="job-center-empty">
      <MaterialIcon name="schedule" />
      <h3>{title}</h3>
      <p>{detail}</p>
    </div>
  );
}

function formatDuration(durationMs: number): string {
  if (durationMs <= 0) return "—";
  if (durationMs < 1000) return `${durationMs}ms`;
  if (durationMs < 60_000) return `${Math.round(durationMs / 100) / 10}s`;
  const minutes = Math.floor(durationMs / 60_000);
  const seconds = Math.round((durationMs % 60_000) / 1000);
  return `${minutes}m ${seconds}s`;
}

function jobIcon(kind: string) {
  if (kind === "generate_classroom") return "slideshow";
  if (kind === "render_video") return "play_circle";
  if (kind.includes("ppt")) return "picture_as_pdf";
  if (kind.includes("quiz")) return "quiz";
  if (kind.includes("graph")) return "hub";
  if (kind.includes("document") || kind.includes("index")) return "menu_book";
  return "auto_awesome";
}

function jobStatusLabel(status: JobRecord["status"]) {
  return (
    {
      queued: "排队中",
      running: "进行中",
      cancel_requested: "取消中",
      succeeded: "已完成",
      partially_succeeded: "部分完成",
      failed: "失败",
      canceled: "已取消",
    }[status] || status
  );
}

function formatTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
}
