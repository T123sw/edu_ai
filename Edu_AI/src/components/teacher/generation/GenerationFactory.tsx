import { useEffect, useMemo, useState } from "react";

import { getKnowledgeBaseDocuments } from "../../../stitch/api/courses";
import type { KnowledgeBaseDocument } from "../../../stitch/api/types";
import { MaterialIcon } from "../../../stitch/shared";
import { buildTeacherCourseHash } from "../../../stitch/teacherRoutes";
import { jobKindLabel, presentJobError } from "../../../jobs/jobPresentation";
import { useCourseJobs } from "../../../jobs/jobStore";
import { isActiveJob } from "../../../jobs/types";
import { GenerationSourceSelector, type GenerationSourceSelection } from "./GenerationSourceSelector";
import { generationRegistry, getGenerationResource, type GenerationResourceType } from "./generationRegistry";
import { useGenerationSubmission, type GenerationDraft } from "./useGenerationSubmission";
import { defaultGenerationConfig, generationConfigAudience, generationConfigRequirements, generationConfigTopic, validateGenerationConfig } from "./definitions";
import type { ReportConfig } from "./definitions/report";
import type { LessonPlanConfig } from "./definitions/lessonPlan";
import type { BlogConfig } from "./definitions/blog";
import type { QuizConfig } from "./definitions/quiz";
import type { FlashcardConfig } from "./definitions/flashcard";
import type { GameConfig } from "./definitions/game";
import type { PptConfig } from "./definitions/ppt";
import type { MindMapConfig } from "./definitions/mindMap";
import type { ClassroomConfig } from "./definitions/classroom";
import { ReportForm } from "./forms/ReportForm";
import { LessonPlanForm } from "./forms/LessonPlanForm";
import { BlogForm } from "./forms/BlogForm";
import { QuizForm } from "./forms/QuizForm";
import { FlashcardForm } from "./forms/FlashcardForm";
import { GameForm } from "./forms/GameForm";
import { PptForm } from "./forms/PptForm";
import { MindMapForm } from "./forms/MindMapForm";
import { ClassroomForm } from "./forms/ClassroomForm";
import "./generationFactory.css";

const GENERATION_KINDS = new Set([
  "generate_report", "generate_lesson_plan", "generate_blog", "generate_quiz",
  "generate_ppt", "generate_flashcard", "generate_graph", "generate_game", "generate_classroom",
]);

function ConfigForm({ type, config, errors, onChange }: {
  type: GenerationResourceType;
  config: Record<string, unknown>;
  errors: Record<string, string>;
  onChange: (next: Record<string, unknown>) => void;
}) {
  if (type === "report") return <ReportForm value={config as unknown as ReportConfig} onChange={(next) => onChange(next as unknown as Record<string, unknown>)} errors={errors} />;
  if (type === "lesson_plan") return <LessonPlanForm value={config as unknown as LessonPlanConfig} onChange={(next) => onChange(next as unknown as Record<string, unknown>)} errors={errors} />;
  if (type === "blog") return <BlogForm value={config as unknown as BlogConfig} onChange={(next) => onChange(next as unknown as Record<string, unknown>)} errors={errors} />;
  if (type === "quiz") return <QuizForm value={config as unknown as QuizConfig} onChange={(next) => onChange(next as unknown as Record<string, unknown>)} errors={errors} />;
  if (type === "flashcard") return <FlashcardForm value={config as unknown as FlashcardConfig} onChange={(next) => onChange(next as unknown as Record<string, unknown>)} errors={errors} />;
  if (type === "game") return <GameForm value={config as unknown as GameConfig} onChange={(next) => onChange(next as unknown as Record<string, unknown>)} errors={errors} />;
  if (type === "ppt") return <PptForm value={config as unknown as PptConfig} onChange={(next) => onChange(next as unknown as Record<string, unknown>)} errors={errors} />;
  if (type === "mind_map") return <MindMapForm value={config as unknown as MindMapConfig} onChange={(next) => onChange(next as unknown as Record<string, unknown>)} errors={errors} />;
  return <ClassroomForm value={config as unknown as ClassroomConfig} onChange={(next) => onChange(next as unknown as Record<string, unknown>)} errors={errors} />;
}

function statusLabel(status: string) {
  if (status === "queued") return "排队中";
  if (status === "running" || status === "cancel_requested") return "进行中";
  if (status === "succeeded") return "已完成";
  if (status === "partially_succeeded") return "部分完成";
  if (status === "canceled") return "已取消";
  return "未完成";
}

export function GenerationFactory({ courseId }: { courseId?: string }) {
  const [resourceType, setResourceType] = useState<GenerationResourceType | null>(null);
  const [source, setSource] = useState<GenerationSourceSelection>({ mode: "course_auto", selectedDocumentIds: [] });
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [configs, setConfigs] = useState<Partial<Record<GenerationResourceType, Record<string, unknown>>>>({});
  const [showErrors, setShowErrors] = useState(false);
  const submission = useGenerationSubmission(courseId);
  const jobs = useCourseJobs(courseId).filter((job) => GENERATION_KINDS.has(job.kind)).slice(0, 8);

  useEffect(() => {
    if (!courseId) return;
    void getKnowledgeBaseDocuments(courseId, { libraryType: "course", aggregate: true, limit: 200, sort: "created_desc" })
      .then(setDocuments)
      .catch(() => setDocuments([]));
  }, [courseId]);

  useEffect(() => {
    if (submission.jobId) setResourceType(null);
  }, [submission.jobId]);

  const resource = resourceType ? getGenerationResource(resourceType) : null;
  const config = useMemo(
    () => resourceType ? (configs[resourceType] || defaultGenerationConfig(resourceType)) : {},
    [configs, resourceType],
  );
  const errors = resourceType ? validateGenerationConfig(resourceType, config) : {};

  function open(type: GenerationResourceType) {
    setResourceType(type);
    setShowErrors(false);
    setConfigs((current) => current[type] ? current : { ...current, [type]: defaultGenerationConfig(type) });
  }

  async function submit() {
    if (!resourceType) return;
    if (source.mode === "selected_documents" && source.selectedDocumentIds.length === 0) {
      setShowErrors(true);
      return;
    }
    if (Object.keys(errors).length > 0) {
      setShowErrors(true);
      return;
    }
    const draft: GenerationDraft = {
      resourceType,
      source,
      topic: generationConfigTopic(config),
      audience: generationConfigAudience(config),
      requirements: generationConfigRequirements(config),
      config,
    };
    await submission.submit(draft);
  }

  return (
    <div className="generation-factory generation-factory--direct" data-testid="generation-factory">
      <header className="generation-factory__header">
        <span>生成工具</span>
        <h2>选择要创建的资源</h2>
      </header>
      <div className="generation-factory__registry">
        {generationRegistry.map((item) => (
          <button key={item.resourceType} type="button" onClick={() => open(item.resourceType)} style={{ "--resource-accent": item.accent } as React.CSSProperties}>
            <MaterialIcon name={item.icon} />
            <strong>{item.label}</strong>
          </button>
        ))}
      </div>

      <section className="generation-factory__recent">
        <div className="generation-factory__recent-title"><strong>最近生成</strong><span>按时间排序</span></div>
        <div className="generation-factory__recent-list">
          {jobs.length === 0 ? <p>暂无生成记录</p> : jobs.map((job) => {
            const ref = job.result_ref;
            const href = ref?.material_type && ref?.material_id
              ? buildTeacherCourseHash("resources", courseId, { material_type: ref.material_type, material_id: ref.material_id })
              : undefined;
            const content = (
              <>
                <span className={`generation-factory__job-icon is-${job.status}`}><MaterialIcon name={isActiveJob(job) ? "hourglass_top" : job.status === "succeeded" ? "check" : "priority_high"} /></span>
                <div><strong>{jobKindLabel(job.kind)}</strong><small>{job.status === "failed" ? presentJobError(job).title : String(job.input_summary?.topic || job.input_summary?.title || "课程资源")}</small></div>
                <span className={`generation-factory__job-state is-${job.status}`}>{statusLabel(job.status)}</span>
              </>
            );
            return href ? <a key={job.edu_job_id} href={href} className="generation-factory__job">{content}</a> : <article key={job.edu_job_id} className="generation-factory__job">{content}</article>;
          })}
        </div>
      </section>

      {resourceType && resource && (
        <div className="generation-factory__modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setResourceType(null)}>
          <section className="generation-factory__modal" role="dialog" aria-modal="true" aria-label={`配置${resource.label}`}>
            <header>
              <div><span>创建资源</span><h2>{resource.label}</h2></div>
              <button type="button" aria-label="关闭" onClick={() => setResourceType(null)}><MaterialIcon name="close" /></button>
            </header>
            <div className="generation-factory__modal-body">
              <ConfigForm type={resourceType} config={config} errors={showErrors ? errors : {}} onChange={(next) => setConfigs((current) => ({ ...current, [resourceType]: next }))} />
              <details className="generation-factory__source-details">
                <summary>资料范围（默认使用课程资料）</summary>
                <GenerationSourceSelector documents={documents} value={source} onChange={setSource} />
              </details>
              {submission.error && <p className="generation-factory__error" role="alert">{submission.error}</p>}
            </div>
            <footer>
              <button type="button" onClick={() => setResourceType(null)}>取消</button>
              <button type="button" className="is-primary" disabled={submission.submitting} onClick={() => void submit()}>{submission.submitting ? "正在提交…" : "开始后台生成"}</button>
            </footer>
          </section>
        </div>
      )}
    </div>
  );
}
