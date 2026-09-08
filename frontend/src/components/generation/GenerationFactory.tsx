import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";

import { getCourseMaterials, getKnowledgeBaseDocuments } from "../../stitch/api/courses";
import { listPersonalKnowledgeDocuments } from "../../stitch/api/personalKnowledge";
import type { CourseMaterial, KnowledgeBaseDocument } from "../../stitch/api/types";
import { MaterialIcon } from "../../stitch/shared";
import type { GenerationToolId } from "../../stitch/shared/generation/generationCatalog";
import { useCourseJobs } from "../../jobs/jobStore";
import { GenerationSourceSelector, initialGenerationSource, type GenerationSourceSelection } from "./GenerationSourceSelector";
import { presentGenerationJob } from "./generationJobPresentation";
import { getGenerationResource, selectGenerationResources, type GenerationResourceType } from "./generationRegistry";
import { useGenerationSubmission, type GenerationDraft } from "./useGenerationSubmission";
import { defaultGenerationConfig, generationConfigAudience, generationConfigRequirements, generationConfigTopic, validateGenerationConfig } from "./definitions";
import type { ReportConfig } from "./definitions/report";
import type { LessonPlanConfig } from "./definitions/lessonPlan";
import type { BlogConfig } from "./definitions/blog";
import type { QuizConfig } from "./definitions/quiz";
import type { FlashcardConfig } from "./definitions/flashcard";
import type { GameConfig } from "./definitions/game";
import type { MindMapConfig } from "./definitions/mindMap";
import type { ClassroomConfig } from "./definitions/classroom";
import { ReportForm } from "./forms/ReportForm";
import { LessonPlanForm } from "./forms/LessonPlanForm";
import { BlogForm } from "./forms/BlogForm";
import { QuizForm } from "./forms/QuizForm";
import { FlashcardForm } from "./forms/FlashcardForm";
import { GameForm } from "./forms/GameForm";
import { MindMapForm } from "./forms/MindMapForm";
import { ClassroomForm } from "./forms/ClassroomForm";
import "./generationFactory.css";

import { useAuthSession } from "../../stitch/authSession";
import { useDraftPreview } from "../../stitch/artifactRevision/draftPreview";

const GENERATION_KINDS = new Set([
  "generate_report", "generate_lesson_plan", "generate_blog", "generate_quiz",
  "generate_flashcard", "generate_graph", "generate_game", "generate_classroom",
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

export type GenerationResultTarget = { courseId: string; materialType: string; materialId: string; title: string };

export type GenerationFactoryProps = {
  courseId?: string;
  allowedTools: readonly GenerationToolId[];
  resultHref: (material: { courseId?: string; materialType?: string; materialId?: string }) => string;
  sourceLibraries: readonly ("personal" | "course")[];
  selectedDocumentIds?: readonly string[];
  scopeType?: "course" | "knowledge_point";
  scopeId?: string;
  onOpenResult?: (target: GenerationResultTarget) => void;
};

export function GenerationFactory({
  courseId,
  allowedTools,
  resultHref,
  sourceLibraries,
  selectedDocumentIds = [],
  scopeType,
  scopeId,
  onOpenResult,
}: GenerationFactoryProps) {
  const [resourceType, setResourceType] = useState<GenerationResourceType | null>(null);
  const [source, setSource] = useState<GenerationSourceSelection>(() => initialGenerationSource([]));
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [configs, setConfigs] = useState<Partial<Record<GenerationResourceType, Record<string, unknown>>>>({});
  const [showErrors, setShowErrors] = useState(false);
  const submission = useGenerationSubmission(courseId);
  const jobs = useCourseJobs(courseId).filter((job) => GENERATION_KINDS.has(job.kind));
  const { user } = useAuthSession();
  const draftEntry = useDraftPreview(state => state.entry);
  const savedId = draftEntry?.owner === user?.username && draftEntry?.courseId === courseId
    && draftEntry.outcome.status === "completed" ? draftEntry.outcome.artifact_reference?.artifact_id : undefined;
  const [materials, setMaterials] = useState<{ owner?: string; courseId?: string; items: CourseMaterial[] }>({ items: [] });
  const jobsVersion = jobs.map(job => `${job.edu_job_id}:${job.status}`).join("|");
  useEffect(() => {
    let cancelled = false;
    if (!courseId || !user?.username) return;
    void getCourseMaterials(courseId, { space: "mine", aggregate: true, limit: 8, sort: "created_desc" })
      .then(items => { if (!cancelled) setMaterials({ owner: user.username, courseId, items }); })
      .catch(() => { /* Keep the last successful list when a refresh fails. */ });
    return () => { cancelled = true; };
  }, [courseId, user?.username, savedId, jobsVersion]);
  const visibleMaterials = materials.owner === user?.username && materials.courseId === courseId ? materials.items : [];
  const materialKeys = new Set(visibleMaterials.map(item => `${item.material_type}:${item.material_id}`));
  const recent = [
    ...visibleMaterials.map(item => {
      const resource = getGenerationResource(item.material_type as GenerationResourceType);
      return { id: `material:${item.material_type}:${item.material_id}`, status: "succeeded", created_at: item.created_at || "",
        ref: { course_id: item.course_id || courseId, material_type: item.material_type, material_id: item.material_id },
        presentation: { title: item.title || item.topic || resource.label, icon: resource.icon, accent: resource.accent } };
    }),
    ...jobs.filter(job => !materialKeys.has(`${job.result_ref?.material_type}:${job.result_ref?.material_id}`))
      .map(job => ({ id: job.edu_job_id, status: job.status, created_at: job.created_at, ref: job.result_ref, presentation: presentGenerationJob(job) })),
  ].sort((a, b) => Date.parse(b.created_at || '1970-01-01') - Date.parse(a.created_at || '1970-01-01')).slice(0, 8);

  useEffect(() => {
    let cancelled = false;
    const requests: Array<Promise<KnowledgeBaseDocument[]>> = [];
    if (courseId && sourceLibraries.includes("course")) {
      requests.push(getKnowledgeBaseDocuments(courseId, { libraryType: "course", aggregate: true, limit: 200, sort: "created_desc" }));
    }
    if (sourceLibraries.includes("personal")) {
      requests.push(listPersonalKnowledgeDocuments({ limit: 200 }).then((items) => items.map((item) => ({
        ...item,
        course_id: item.course_context_id ?? courseId ?? "personal",
        library_type: "personal" as const,
      }))));
    }
    void Promise.all(requests)
      .then((groups) => { if (!cancelled) setDocuments(groups.flat()); })
      .catch(() => { if (!cancelled) setDocuments([]); });
    return () => { cancelled = true; };
  }, [courseId, sourceLibraries]);

  useEffect(() => {
    if (submission.jobId) setResourceType(null);
  }, [submission.jobId]);

  const resource = resourceType ? getGenerationResource(resourceType) : null;
  const config = useMemo(
    () => resourceType ? (configs[resourceType] || defaultGenerationConfig(resourceType)) : {},
    [configs, resourceType],
  );
  const errors = resourceType ? validateGenerationConfig(resourceType, config) : {};
  const visibleResources = useMemo(
    () => selectGenerationResources(allowedTools as readonly GenerationResourceType[]),
    [allowedTools],
  );

  function open(type: GenerationResourceType) {
    setSource(initialGenerationSource([...selectedDocumentIds]));
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
      scopeType,
      scopeId,
      topic: generationConfigTopic(config),
      audience: generationConfigAudience(config),
      requirements: generationConfigRequirements(config),
      config,
    };
    try {
      await submission.submit(draft);
    } catch {
      // The submission hook retains the draft and displays the server error.
    }
  }

  return (
    <div className="generation-factory generation-factory--direct" data-testid="generation-factory">
      <header className="generation-factory__header">
        <h2>生成工厂</h2>
        <p>选择要创建的资源</p>
      </header>
      <div className="generation-factory__registry">
        {visibleResources.map((item) => (
          <button key={item.resourceType} type="button" onClick={() => open(item.resourceType)} style={{ "--resource-accent": item.accent } as React.CSSProperties}>
            <MaterialIcon name={item.icon} />
            <strong>{item.label}</strong>
          </button>
        ))}
      </div>

      <section className="generation-factory__recent">
        <div className="generation-factory__recent-title"><strong>最近生成</strong><span>按时间排序</span></div>
        <div className="generation-factory__recent-list">
          {recent.length === 0 ? <p>暂无生成记录</p> : recent.map((job) => {
            const ref = job.ref;
            const presentation = job.presentation;
            const href = ref?.material_type && ref?.material_id
              ? resultHref({ courseId, materialType: ref.material_type, materialId: ref.material_id })
              : undefined;
            const content = (
              <>
                <span
                  className="generation-factory__job-icon"
                  style={{
                    backgroundColor: `${presentation.accent}14`,
                    color: presentation.accent,
                  }}
                >
                  <MaterialIcon name={presentation.icon} />
                </span>
                <div><strong title={presentation.title}>{presentation.title}</strong></div>
                <span className={`generation-factory__job-state is-${job.status}`}>{statusLabel(job.status)}</span>
              </>
            );
            const targetCourseId = ref?.course_id || courseId;
            if (onOpenResult && targetCourseId && ref?.material_type && ref?.material_id) {
              return <button key={job.id} type="button" className="generation-factory__job generation-factory__job--open"
                onClick={() => onOpenResult({ courseId: targetCourseId, materialType: ref.material_type!, materialId: ref.material_id!, title: presentation.title })}>{content}</button>;
            }
            return href ? <a key={job.id} href={href} className="generation-factory__job">{content}</a> : <article key={job.id} className="generation-factory__job">{content}</article>;
          })}
        </div>
      </section>

      {resourceType && resource && typeof document !== "undefined" && createPortal((
        <div className="generation-factory__modal-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setResourceType(null)}>
          <section className="generation-factory__modal" role="dialog" aria-modal="true" aria-label={`配置${resource.label}`}>
            <header>
              <div><span>创建资源</span><h2>{resource.label}</h2></div>
              <button type="button" aria-label="关闭" onClick={() => setResourceType(null)}><MaterialIcon name="close" /></button>
            </header>
            <div className="generation-factory__modal-body">
              <ConfigForm type={resourceType} config={config} errors={showErrors ? errors : {}} onChange={(next) => setConfigs((current) => ({ ...current, [resourceType]: next }))} />
              <details className="generation-factory__source-details">
                <summary>{source.mode === "selected_documents" ? `资料范围（已选 ${source.selectedDocumentIds.length} 份文档）` : source.mode === "course_auto" ? "资料范围（检索课程全部资料）" : "资料范围（不使用知识库）"}</summary>
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
      ), document.body)}
    </div>
  );
}
