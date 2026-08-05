import { useEffect, useMemo, useRef, useState } from "react";
import { getCourseMaterials } from "../api/courses";
import { CLASSROOM_STEP_LABELS, generateClassroom } from "../api/classroom";
import type { ClassroomMaterial } from "../api/types";
import { AppSurface, GlassPanel, MaterialIcon, useAppShell } from "../shared";
import { buildClassroomPlayerHash } from "../../openmaic/classroomGenerationFlow";
import { buildTeacherCourseHash } from "../teacherRoutes";
import { registerCreatedJob, useCourseJobs } from "../../jobs/jobStore";
import { isActiveJob } from "../../jobs/types";

function useClassroomList(courseId: string | undefined, reloadToken: number) {
  const [items, setItems] = useState<ClassroomMaterial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!courseId) return;
    let cancelled = false;
    setLoading(true);
    getCourseMaterials(courseId, { materialType: "classroom" })
      .then((data) => {
        if (!cancelled) setItems(data as unknown as ClassroomMaterial[]);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "课件列表加载失败");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [courseId, reloadToken]);

  return { items, loading, error };
}

export function ClassroomStudioPage() {
  const { selectedCourse } = useAppShell();
  const courseId = selectedCourse?.id;
  const [requirement, setRequirement] = useState("");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const reloadedJobIdsRef = useRef(new Set<string>());
  const { items, loading, error } = useClassroomList(courseId, reloadToken);
  const classroomJobs = useCourseJobs(courseId, "generate_classroom");
  const job = useMemo(
    () =>
      classroomJobs.find((candidate) => candidate.edu_job_id === selectedJobId) ??
      classroomJobs.find(isActiveJob) ??
      classroomJobs[0] ??
      null,
    [classroomJobs, selectedJobId],
  );

  useEffect(() => {
    if (
      job?.status === "succeeded" &&
      !reloadedJobIdsRef.current.has(job.edu_job_id)
    ) {
      reloadedJobIdsRef.current.add(job.edu_job_id);
      setReloadToken((token) => token + 1);
    }
  }, [job?.edu_job_id, job?.status]);

  async function handleGenerate() {
    if (!courseId || !requirement.trim()) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await generateClassroom(courseId, { requirement: requirement.trim() });
      registerCreatedJob(created);
      setSelectedJobId(created.edu_job_id);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "提交生成任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  function openPlayer(classroomId: string) {
    if (!courseId) return;
    window.location.hash = buildClassroomPlayerHash(courseId, classroomId);
  }

  if (!courseId) {
    return (
      <AppSurface className="min-h-screen">
        <main className="w-full px-8 py-10">
          <GlassPanel className="border border-(--shell-border) bg-white/85 p-8 text-sm text-(--muted-text)">
            请先从"我的课程"里选择一门课程，再来生成课件。
          </GlassPanel>
        </main>
      </AppSurface>
    );
  }

  const isBusy = Boolean(job && isActiveJob(job));

  return (
    <AppSurface className="min-h-screen">
      <main className="w-full px-8 py-10">
        <div className="mb-8 flex items-center justify-between gap-4">
          <a
            href={buildTeacherCourseHash("ai", courseId)}
            className="inline-flex items-center gap-2 rounded-full border border-(--shell-border) bg-white px-4 py-2.5 text-sm font-semibold text-(--accent-strong)"
          >
            <MaterialIcon name="arrow_back" className="text-sm" />
            返回课程详情
          </a>
          <div className="text-right">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-(--accent-strong)">AI 课件生成</p>
            <h2 className="mt-1 text-xl font-black text-(--app-text)">{selectedCourse?.title}</h2>
          </div>
        </div>

        <GlassPanel className="mb-6 border border-(--shell-border) bg-white/88 p-6">
          <p className="mb-3 text-sm font-bold text-(--accent-strong)">生成新课件</p>
          <textarea
            value={requirement}
            onChange={(event) => setRequirement(event.target.value)}
            placeholder="描述这节课要讲什么，例如：讲一节课，介绍冒泡排序算法的基本原理和时间复杂度"
            rows={3}
            disabled={isBusy}
            className="w-full resize-none rounded-2xl border border-(--shell-border) bg-(--surface-subtle) p-4 text-sm outline-hidden focus:border-(--accent-border)"
          />
          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={handleGenerate}
              disabled={submitting || isBusy || !requirement.trim()}
              className="inline-flex items-center gap-2 rounded-2xl bg-(--accent) px-5 py-2.5 text-sm font-bold text-white disabled:opacity-50"
            >
              <MaterialIcon name="auto_awesome" className="text-base" />
              {submitting ? "提交中..." : "开始生成"}
            </button>
            {submitError ? <span className="text-sm text-rose-600">{submitError}</span> : null}
          </div>

          {job ? (
            <div className="mt-5 rounded-2xl border border-(--shell-border) bg-(--surface-subtle) p-4">
              <div className="flex items-center justify-between text-sm">
                <span className="font-semibold text-(--accent-strong)">
                  {CLASSROOM_STEP_LABELS[job.step] ?? job.step}
                </span>
                <span className="text-(--muted-text)">{job.progress}%</span>
              </div>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-(--track-color)">
                <div
                  className={`h-full rounded-full transition-all ${job.status === "failed" ? "bg-rose-500" : "bg-(--accent)"}`}
                  style={{ width: `${Math.max(job.status === "failed" ? 100 : job.progress, 4)}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-(--muted-text)">{job.message}</p>
              {job.status === "failed" ? (
                <p className="mt-2 text-xs text-rose-600">
                  生成失败：{job.error_message || job.error || "请在任务中心重试"}
                </p>
              ) : null}
              {job.status === "canceled" ? (
                <p className="mt-2 text-xs text-(--muted-text)">任务已取消</p>
              ) : null}
              {job.status === "succeeded" && typeof job.result_ref?.classroom_id === "string" ? (
                <button
                  type="button"
                  onClick={() => openPlayer(job.result_ref!.classroom_id as string)}
                  className="mt-3 inline-flex items-center gap-2 rounded-xl bg-(--accent) px-4 py-2 text-xs font-bold text-white"
                >
                  <MaterialIcon name="play_circle" className="text-sm" />
                  立即播放
                </button>
              ) : null}
            </div>
          ) : null}
        </GlassPanel>

        <GlassPanel className="border border-(--shell-border) bg-white/88 p-6">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm font-bold text-(--accent-strong)">已生成的课件</p>
            <span className="rounded-full bg-(--accent-soft) px-3 py-1 text-xs font-semibold text-(--accent-strong)">
              {items.length} 份
            </span>
          </div>
          {loading ? (
            <p className="text-sm text-(--muted-text)">加载中...</p>
          ) : error ? (
            <p className="text-sm text-rose-600">{error}</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-(--muted-text)">还没有生成过课件，在上面输入需求试试。</p>
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <button
                  key={item.material_id}
                  type="button"
                  onClick={() => openPlayer(item.material_id)}
                  className="flex w-full items-center justify-between rounded-2xl border border-(--shell-border) bg-(--surface-subtle) p-4 text-left hover:border-(--accent-border) hover:bg-white"
                >
                  <div>
                    <p className="font-bold text-(--app-text)">{item.title ?? item.material_id}</p>
                    <p className="mt-1 text-xs text-(--muted-text)">
                      {item.scenes_count ?? item.scenes?.length ?? 0} 个场景
                    </p>
                  </div>
                  <MaterialIcon name="play_circle" className="text-2xl text-(--accent)" />
                </button>
              ))}
            </div>
          )}
        </GlassPanel>
      </main>
    </AppSurface>
  );
}
