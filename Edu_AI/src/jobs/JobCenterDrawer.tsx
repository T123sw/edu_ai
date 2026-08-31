import { useEffect, useMemo, useState } from "react";
import { cancelJob, retryJob } from "./api";
import { buildJobCourseGroups } from "./jobCourseGrouping";
import {
  getJobPrimaryAction,
  isJobCenterVisible,
  jobKindLabel,
  presentJobDetail,
  summarizeJobs,
} from "./jobPresentation";
import { getJobResultHash } from "./jobResultTarget";
import { registerCreatedJob, useJobStore } from "./jobStore";
import { isActiveJob, type JobRecord } from "./types";
import { MaterialIcon } from "../stitch/shared";
import { listCourses } from "../stitch/api/courses";
import { useCourseRoute } from "../stitch/course/CourseRouteProvider";
import "./jobCenter.css";

const OPEN_JOB_CENTER_EVENT = "edu-ai:open-job-center";

export function JobCenterTrigger({
  placement = "floating",
  courseId,
}: {
  placement?: "floating" | "inline";
  courseId?: string | null;
}) {
  const { courseId: routeCourseId } = useCourseRoute();
  const unreadIds = useJobStore((state) => state.unreadTerminalIds);
  const jobsById = useJobStore((state) => state.jobs);
  const scopedCourseId = courseId === undefined ? routeCourseId : courseId;
  const activeCount = Object.values(jobsById).filter(
    (job) =>
      isActiveJob(job) &&
      (!scopedCourseId || job.course_id === scopedCourseId),
  ).length;
  const hasUnreadFailure = unreadIds.some(
    (id) =>
      (!scopedCourseId || jobsById[id]?.course_id === scopedCourseId) &&
      (jobsById[id]?.status === "failed" ||
        jobsById[id]?.status === "partially_succeeded"),
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

export function JobCenterDrawer({
  showLauncher = true,
  currentCourseId = null,
  currentCourseTitle = null,
}: {
  showLauncher?: boolean;
  currentCourseId?: string | null;
  currentCourseTitle?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [courseTitles, setCourseTitles] = useState<ReadonlyMap<string, string>>(
    () => new Map(),
  );
  const jobsById = useJobStore((state) => state.jobs);
  const orderedIds = useJobStore((state) => state.orderedIds);
  const hydrated = useJobStore((state) => state.hydrated);
  const pollFailures = useJobStore((state) => state.pollFailures);
  const markAllRead = useJobStore((state) => state.markAllRead);
  const mergeJobs = useJobStore((state) => state.mergeJobs);
  const jobs = useMemo(
    () => orderedIds.map((id) => jobsById[id]).filter(Boolean),
    [jobsById, orderedIds],
  );
  const visibleJobCandidates = useMemo(
    () => jobs.filter(isJobCenterVisible),
    [jobs],
  );
  const courseGroups = useMemo(
    () =>
      buildJobCourseGroups(visibleJobCandidates, {
        currentCourseId,
        currentCourseTitle,
        courseTitles,
      }),
    [courseTitles, currentCourseId, currentCourseTitle, visibleJobCandidates],
  );
  const visibleJobs = useMemo(
    () => courseGroups.flatMap((group) => group.jobs),
    [courseGroups],
  );
  const visibleActiveCount = useMemo(
    () => visibleJobs.filter(isActiveJob).length,
    [visibleJobs],
  );
  const statusSummary = useMemo(
    () => summarizeJobs(visibleJobs),
    [visibleJobs],
  );

  useEffect(() => {
    const handleOpen = () => {
      setOpen(true);
      markAllRead();
    };
    window.addEventListener(OPEN_JOB_CENTER_EVENT, handleOpen);
    return () => window.removeEventListener(OPEN_JOB_CENTER_EVENT, handleOpen);
  }, [markAllRead]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    void listCourses()
      .then((courses) => {
        if (cancelled) return;
        setCourseTitles(
          new Map(courses.map((course) => [course.id, course.title])),
        );
      })
      .catch(() => undefined);

    return () => {
      cancelled = true;
    };
  }, [open]);

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
    } catch (reason) {
      setActionError(
        reason instanceof Error
          ? reason.message
          : "任务操作失败，请稍后重试",
      );
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      {showLauncher ? <JobCenterTrigger courseId={currentCourseId} /> : null}

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
                <p className="job-center-eyebrow">
                  {currentCourseId ? "当前课程后台任务" : "全部后台任务"}
                </p>
                <h2 id="job-center-title">任务中心</h2>
                <p>
                  {pollFailures
                    ? `连接暂时中断，正在第 ${pollFailures} 次重试`
                    : visibleActiveCount
                      ? `${visibleActiveCount} 个任务正在后台继续`
                      : currentCourseId
                        ? `${currentCourseTitle || "当前课程"}暂无进行中的任务`
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
              <section
                className="job-center-quality"
                aria-label="后台任务状态概览"
              >
                <div>
                  <span>已完成</span>
                  <strong>{statusSummary.completedCount}</strong>
                </div>
                <div>
                  <span>进行中</span>
                  <strong>{statusSummary.activeCount}</strong>
                </div>
                <div>
                  <span>失败</span>
                  <strong>{statusSummary.failedCount}</strong>
                </div>
              </section>
              {!hydrated ? (
                <JobEmpty
                  title="正在恢复后台任务"
                  detail="正在从服务器读取当前账号的任务记录…"
                />
              ) : visibleJobs.length === 0 ? (
                <JobEmpty
                  title={currentCourseId ? "这门课程还没有后台任务" : "还没有后台任务"}
                  detail={
                    currentCourseId
                      ? "在当前课程中发起生成或知识库任务后，可在这里持续查看进度。"
                      : "进入任一课程发起课堂、报告、PPT 等任务后，可在这里按课程查看进度。"
                  }
                />
              ) : (
                <div className="job-center-courses">
                  {courseGroups.map((group) => (
                    <CourseJobGroup
                      key={group.courseId ?? "unscoped"}
                      title={group.title}
                      courseId={group.courseId}
                      jobs={group.jobs}
                      isCurrentCourse={group.courseId === currentCourseId}
                      busyId={busyId}
                      onAction={runAction}
                    />
                  ))}
                </div>
              )}
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}

function CourseJobGroup({
  title,
  courseId,
  jobs,
  isCurrentCourse,
  busyId,
  onAction,
}: {
  title: string;
  courseId: string | null;
  jobs: JobRecord[];
  isCurrentCourse: boolean;
  busyId: string | null;
  onAction: (job: JobRecord, action: "cancel" | "retry") => Promise<void>;
}) {
  const groups = {
    active: jobs.filter(isActiveJob),
    failed: jobs.filter(
      (job) => job.status === "failed" || job.status === "partially_succeeded",
    ),
    completed: jobs
      .filter((job) => job.status === "succeeded")
      .slice(0, 20),
  };

  return (
    <section className="job-center-course">
      <header className="job-center-course__header">
        <span className="job-center-course__icon">
          <MaterialIcon name={courseId ? "school" : "language"} />
        </span>
        <div>
          <p>{isCurrentCourse ? "当前课程" : courseId ? "课程" : "未归入课程"}</p>
          <h3>{title}</h3>
        </div>
        <span className="job-center-course__count">{jobs.length} 个任务</span>
      </header>
      <JobGroup
        title="进行中"
        jobs={groups.active}
        busyId={busyId}
        onAction={onAction}
      />
      <JobGroup
        title="失败"
        jobs={groups.failed}
        busyId={busyId}
        onAction={onAction}
      />
      <JobGroup
        title="已完成"
        jobs={groups.completed}
        busyId={busyId}
        onAction={onAction}
      />
    </section>
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
  const primaryAction = getJobPrimaryAction(job, resultHash);
  return (
    <article className={`job-card is-${job.status}`}>
      <div className="job-card__top">
        <span className="job-card__icon">
          <MaterialIcon name={jobIcon(job.kind)} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="job-card__kind">{jobKindLabel(job.kind)}</p>
          <h4 title={title}>{title}</h4>
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
        {primaryAction === "cancel" ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void onAction(job, "cancel")}
          >
            {busy ? "处理中…" : "取消"}
          </button>
        ) : primaryAction === "retry" ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void onAction(job, "retry")}
          >
            {busy ? "处理中…" : "重试"}
          </button>
        ) : primaryAction === "open-result" && resultHash ? (
          <a href={resultHash}>打开结果</a>
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
