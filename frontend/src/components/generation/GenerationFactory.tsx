import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { getCourseMaterials, getKnowledgeBaseDocuments } from "../../stitch/api/courses";
import { listPersonalKnowledgeDocuments } from "../../stitch/api/personalKnowledge";
import type { CourseMaterial, KnowledgeBaseDocument } from "../../stitch/api/types";
import { MaterialIcon } from "../../stitch/shared";
import type { GenerationToolId } from "../../stitch/shared/generation/generationCatalog";
import { useCourseJobs } from "../../jobs/jobStore";
import { initialGenerationSource, type GenerationSourceSelection } from "./GenerationSourceSelector";
import { presentGenerationJob } from "./generationJobPresentation";
import { getGenerationResource, selectGenerationResources, type GenerationResourceType } from "./generationRegistry";
import { buildQueuedAgentRequest } from "./generationAgentRequest";
import { GenerationPromptDialog } from "./GenerationPromptDialog";
import {
  generationPromptDraftKey,
  readGenerationPromptDraft,
  writeGenerationPromptDraft,
} from "./generationPromptDraft";
import "./generationFactory.css";

import { useAuthSession } from "../../stitch/authSession";
import { useDraftPreview } from "../../stitch/artifactRevision/draftPreview";
import { useStore } from "../../store/teacher/useStore";

const GENERATION_KINDS = new Set([
  "generate_report", "generate_lesson_plan", "generate_blog", "generate_quiz",
  "generate_flashcard", "generate_graph", "generate_game", "generate_classroom",
]);

function statusLabel(status: string, step?: string) {
  if (status === "queued" && step === "preparing") return "准备中";
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
  onAgentQueued?: () => void;
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
  onAgentQueued,
}: GenerationFactoryProps) {
  const [resourceType, setResourceType] = useState<GenerationResourceType | null>(null);
  const [source, setSource] = useState<GenerationSourceSelection>(() => initialGenerationSource([]));
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [brief, setBrief] = useState("");
  const [promptError, setPromptError] = useState<string | null>(null);
  const openerRef = useRef<HTMLButtonElement | null>(null);
  const jobs = useCourseJobs(courseId).filter((job) => GENERATION_KINDS.has(job.kind));
  const { user } = useAuthSession();
  const allowRag = useStore((state) => state.allowRag);
  const allowWeb = useStore((state) => state.allowWeb);
  const queuedAgentRequest = useStore((state) => state.queuedAgentRequest);
  const enqueueAgentRequest = useStore((state) => state.enqueueAgentRequest);
  const draftEntry = useDraftPreview(state => state.entry);
  const savedId = draftEntry?.owner === user?.username && draftEntry?.courseId === courseId
    && draftEntry?.outcome.status === "completed" ? draftEntry.outcome.artifact_reference?.artifact_id : undefined;
  const [materials, setMaterials] = useState<{ owner?: string; courseId?: string; items: CourseMaterial[] }>({ items: [] });
  const [materialsRefresh, setMaterialsRefresh] = useState(0);
  const [materialsError, setMaterialsError] = useState(false);
  const jobsVersion = jobs.map(job => `${job.edu_job_id}:${job.status}:${job.version}:${job.result_ref?.material_id || ''}`).join("|");
  useEffect(() => {
    const refresh = () => { if (document.visibilityState === 'visible') setMaterialsRefresh(value => value + 1); };
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => { window.removeEventListener('focus', refresh); document.removeEventListener('visibilitychange', refresh); };
  }, []);
  useEffect(() => {
    let cancelled = false;
    if (!courseId || !user?.username) return;
    setMaterialsError(false);
    void getCourseMaterials(courseId, { space: "mine", aggregate: true, limit: 8, sort: "updated_desc" })
      .then(items => { if (!cancelled) setMaterials({ owner: user.username, courseId, items }); })
      .catch(() => { if (!cancelled) setMaterialsError(true); });
    return () => { cancelled = true; };
  }, [courseId, user?.username, savedId, jobsVersion, materialsRefresh]);
  const visibleMaterials = materials.owner === user?.username && materials.courseId === courseId ? materials.items : [];
  const materialKeys = new Set(visibleMaterials.map(item => `${item.material_type}:${item.material_id}`));
  const recent = [
    ...visibleMaterials.map(item => {
      const resource = getGenerationResource(item.material_type as GenerationResourceType);
      return { id: `material:${item.material_type}:${item.material_id}`, status: "succeeded", created_at: item.updated_at || item.created_at || "",
        ref: { course_id: item.course_id || courseId, material_type: item.material_type, material_id: item.material_id },
        presentation: { title: item.title || item.topic || resource.label, icon: resource.icon, accent: resource.accent } };
    }),
    ...jobs.filter(job => !materialKeys.has(`${job.result_ref?.material_type}:${job.result_ref?.material_id}`))
      .map(job => ({ id: job.edu_job_id, status: job.status, step: job.step, created_at: job.created_at, ref: job.result_ref, presentation: presentGenerationJob(job) })),
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

  const resource = resourceType ? getGenerationResource(resourceType) : null;
  const visibleResources = useMemo(
    () => selectGenerationResources(allowedTools as readonly GenerationResourceType[]),
    [allowedTools],
  );

  function draftKey(type: GenerationResourceType) {
    return generationPromptDraftKey({
      ownerUserId: user?.username || "anonymous",
      courseId: courseId || "missing",
      scopeType,
      scopeId,
      resourceType: type,
    });
  }

  function open(type: GenerationResourceType, opener: HTMLButtonElement) {
    openerRef.current = opener;
    setSource(initialGenerationSource([...selectedDocumentIds], allowRag));
    setBrief(readGenerationPromptDraft(draftKey(type)));
    setResourceType(type);
    setPromptError(null);
  }

  function closePrompt(restoreFocus = true) {
    setResourceType(null);
    setPromptError(null);
    if (restoreFocus) window.requestAnimationFrame(() => openerRef.current?.focus());
  }

  function updateBrief(value: string) {
    setBrief(value);
    if (resourceType) writeGenerationPromptDraft(draftKey(resourceType), value);
    if (promptError) setPromptError(null);
  }

  function submit() {
    if (!resourceType) return;
    try {
      const request = buildQueuedAgentRequest({
        requestId: crypto.randomUUID(),
        text: brief,
        resourceType,
        ownerUserId: user?.username || "",
        courseId: courseId || "",
        scopeType,
        scopeId,
        sourceMode: source.mode,
        selectedDocumentIds: source.selectedDocumentIds,
        allowWeb,
      });
      if (enqueueAgentRequest(request) === "conflict") {
        setPromptError("已有一个生成要求等待发送，请稍后再试。");
        return;
      }
      writeGenerationPromptDraft(draftKey(resourceType), "");
      setBrief("");
      closePrompt(false);
      onAgentQueued?.();
    } catch (error) {
      setPromptError(error instanceof Error ? error.message : "无法提交生成要求，请重试。");
    }
  }

  return (
    <div className="generation-factory generation-factory--agent" data-testid="generation-factory">
      <header className="generation-factory__header">
        <h2>生成工厂</h2>
        <p>选择资源，用一句话交给 Agent</p>
      </header>
      {queuedAgentRequest ? <p className="generation-factory__queue-state" role="status">正在提交后台生成…</p> : null}
      <div className="generation-factory__registry">
        {visibleResources.map((item) => (
          <button key={item.resourceType} type="button" onClick={(event) => open(item.resourceType, event.currentTarget)} style={{ "--resource-accent": item.accent } as React.CSSProperties}>
            <MaterialIcon name={item.icon} />
            <strong>{item.label}</strong>
          </button>
        ))}
      </div>

      <section className="generation-factory__recent">
        <div className="generation-factory__recent-title"><strong>最近生成</strong><button type="button" aria-label="刷新最近生成资源" onClick={() => setMaterialsRefresh(value => value + 1)}>刷新</button><span>按时间排序</span></div>
        <div className="generation-factory__recent-list">
          {materialsError && <p role="status">列表更新失败，请点击刷新重试。</p>}
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
                <span className={`generation-factory__job-state is-${job.status}`}>{ref?.material_type ? `${getGenerationResource(ref.material_type as GenerationResourceType).label} · ` : ""}{statusLabel(job.status, "step" in job ? job.step : undefined)}</span>
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
        <GenerationPromptDialog
          resource={resource}
          value={brief}
          source={source}
          documents={documents}
          error={promptError}
          queued={Boolean(queuedAgentRequest)}
          onValueChange={updateBrief}
          onSourceChange={setSource}
          onClose={closePrompt}
          onSubmit={submit}
        />
      ), document.body)}
    </div>
  );
}
