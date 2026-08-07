import { useEffect, useMemo, useRef, useState } from "react";
import { getCourseMaterials } from "../api/courses";
import { generateClassroom } from "../api/classroom";
import type { ClassroomMaterial } from "../api/types";
import { AppSurface, GlassPanel, MaterialIcon } from "../shared";
import { buildClassroomPlayerHash } from "../../openmaic/classroomGenerationFlow";
import { registerCreatedJob, useCourseJobs } from "../../jobs/jobStore";
import { isActiveJob } from "../../jobs/types";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { canCourse } from "../course/coursePermissions";
import { classroomDefinition } from "../../components/teacher/generation/definitions/classroom";
import { ClassroomForm } from "../../components/teacher/generation/forms/ClassroomForm";
import "../../components/teacher/generation/generationFactory.css";
import { classroomPageDefinition } from "./classroomPageDefinition";
import { presentJobError } from "../../jobs/jobPresentation";

export { classroomPageDefinition } from "./classroomPageDefinition";

function useClassroomList(courseId: string | undefined, reloadToken: number) {
  const [items, setItems] = useState<ClassroomMaterial[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!courseId) return;
    let cancelled = false;
    setLoading(true);
    getCourseMaterials(courseId, { materialType: "classroom", sort: "updated_desc" })
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
  const { courseId: routeCourseId, courseRole } = useCourseRoute();
  const courseId = routeCourseId ?? undefined;
  const canGenerate = canCourse(courseRole, "generate");
  const [classroomConfig, setClassroomConfig] = useState(() => classroomPageDefinition.defaultConfig());
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [showErrors, setShowErrors] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
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
    if (!courseId || !canGenerate) return;
    if (Object.keys(classroomDefinition.validate(classroomConfig)).length > 0) {
      setShowErrors(true);
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const request = classroomDefinition.serialize({ courseId, source: { mode: "course_auto", selectedDocumentIds: [] }, config: classroomConfig }) as Parameters<typeof generateClassroom>[1];
      const created = await generateClassroom(courseId, request);
      registerCreatedJob(created);
      setSelectedJobId(created.edu_job_id);
      setConfigOpen(false);
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
    <AppSurface className="min-h-[calc(100vh-var(--course-header-height))]">
      <main className="mx-auto w-full max-w-6xl px-6 py-7 sm:px-8">
        <GlassPanel className="mb-6 flex items-center justify-between gap-6 border border-(--shell-border) bg-white/88 p-6">
          <div>
            <p className="text-xs font-bold tracking-[0.12em] text-(--accent-strong)">互动课堂</p>
            <h2 className="mt-2 text-2xl font-black text-(--app-text)">把一个研究主题变成可播放课堂</h2>
            <p className="mt-2 text-sm text-(--muted-text)">系统会自动组织讲解、提问与课堂场景，你只需提供主题。</p>
          </div>
          {canGenerate && <button type="button" disabled={isBusy} onClick={() => setConfigOpen(true)} className="inline-flex shrink-0 items-center gap-2 rounded-2xl bg-(--accent) px-5 py-3 text-sm font-bold text-white disabled:opacity-50"><MaterialIcon name="add" />创建 AI 课堂</button>}
        </GlassPanel>

        {job && isActiveJob(job) ? <GlassPanel className="mb-6 border border-blue-200 bg-blue-50/80 p-5">
          <div className="flex items-center justify-between"><strong className="text-sm text-blue-900">课堂正在后台生成</strong><span className="text-sm text-blue-700">{job.progress}%</span></div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-blue-100"><div className="h-full rounded-full bg-blue-600 transition-all" style={{ width: `${Math.max(job.progress, 4)}%` }} /></div>
          <p className="mt-2 text-xs text-blue-700">可以离开本页，完成后会出现在下方列表和后台任务中心。</p>
        </GlassPanel> : null}

        {job?.status === "failed" ? <div className="mb-6 rounded-2xl bg-rose-50 px-5 py-4 text-sm text-rose-700">{presentJobError(job).title}：{presentJobError(job).detail}</div> : null}

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

        {configOpen ? <div className="generation-factory__modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setConfigOpen(false)}>
          <section className="generation-factory__modal" role="dialog" aria-modal="true" aria-label="创建 AI 课堂">
            <header><div><span>创建资源</span><h2>AI 课堂</h2></div><button type="button" aria-label="关闭" onClick={() => setConfigOpen(false)}><MaterialIcon name="close" /></button></header>
            <div className="generation-factory__modal-body">
              <ClassroomForm value={classroomConfig} onChange={setClassroomConfig} errors={showErrors ? classroomDefinition.validate(classroomConfig) : {}} />
              {submitError ? <p className="generation-factory__error">{submitError}</p> : null}
            </div>
            <footer><button type="button" onClick={() => setConfigOpen(false)}>取消</button><button type="button" className="is-primary" disabled={submitting} onClick={() => void handleGenerate()}>{submitting ? "正在提交…" : "开始后台生成"}</button></footer>
          </section>
        </div> : null}
      </main>
    </AppSurface>
  );
}
