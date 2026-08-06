import { useCallback, useEffect, useMemo, useState } from "react";

import { cancelJob } from "../../../jobs/api";
import { registerCreatedJob, requestJobRefresh, useJobStore } from "../../../jobs/jobStore";
import type { JobRecord } from "../../../jobs/types";
import { apiRequest } from "../../../stitch/api/client";
import type { GenerationResourceType } from "./generationRegistry";
import type { GenerationSourceSelection } from "./GenerationSourceSelector";
import { blogDefinition } from "./definitions/blog";
import { lessonPlanDefinition } from "./definitions/lessonPlan";
import { reportDefinition } from "./definitions/report";
import { quizDefinition } from "./definitions/quiz";
import { flashcardDefinition } from "./definitions/flashcard";
import { gameDefinition } from "./definitions/game";
import { pptDefinition } from "./definitions/ppt";
import { mindMapDefinition } from "./definitions/mindMap";
import { classroomDefinition } from "./definitions/classroom";

export type GenerationDraft = {
  resourceType: GenerationResourceType;
  topic: string;
  audience: string;
  requirements: string;
  source: GenerationSourceSelection;
  config?: Record<string, unknown>;
};

type Submitted = { task_id?: string; edu_job_id?: string; draft_id?: string; draft?: { draft_id?: string }; outline?: unknown; [key: string]: unknown };

function sourcePayload(draft: GenerationDraft, courseId: string) {
  return {
    course_id: courseId,
    scope_type: "course",
    source_mode: draft.source.mode,
    selected_doc_ids: draft.source.selectedDocumentIds,
  };
}

export function buildGenerationRequest(draft: GenerationDraft, courseId: string, idempotencyKey = `ui-${draft.resourceType}-${courseId}`): { path: string; body: Record<string, unknown> } {
  const source = { ...sourcePayload(draft, courseId), idempotency_key: idempotencyKey };
  switch (draft.resourceType) {
    case "report": return { path: "/api/chat/v2/report/direct", body: { ...source, ...reportDefinition.serialize({ courseId, source: draft.source, config: draft.config as never }) } };
    case "lesson_plan": return { path: "/api/chat/v2/lesson-plan/direct", body: { ...source, ...lessonPlanDefinition.serialize({ courseId, source: draft.source, config: draft.config as never }) } };
    case "blog": return { path: "/api/chat/v2/blog/direct", body: { ...source, ...blogDefinition.serialize({ courseId, source: draft.source, config: draft.config as never }) } };
    case "quiz": return { path: "/api/chat/v2/quiz/direct", body: { ...source, ...quizDefinition.serialize({ courseId, source: draft.source, config: draft.config as never }) } };
    case "flashcard": return { path: "/api/chat/v2/flashcard/direct", body: { ...source, ...flashcardDefinition.serialize({ courseId, source: draft.source, config: draft.config as never }) } };
    case "mind_map": return { path: "/api/chat/v2/graph/direct", body: { ...source, ...mindMapDefinition.serialize({ courseId, source: draft.source, config: draft.config as never }) } };
    case "game": return { path: "/api/chat/v2/game/direct", body: { ...source, ...gameDefinition.serialize({ courseId, source: draft.source, config: draft.config as never }) } };
    case "classroom": return { path: `/api/courses/${encodeURIComponent(courseId)}/classrooms/generate`, body: { source_mode: draft.source.mode, selected_doc_ids: draft.source.selectedDocumentIds, ...classroomDefinition.serialize({ courseId, source: draft.source, config: draft.config as never }), idempotency_key: idempotencyKey } };
    case "ppt": { const serialized = pptDefinition.serialize({ courseId, source: draft.source, config: draft.config as never }); return { path: "/api/chat/v2/ppt/outline", body: { ...source, ppt_config: serialized.ppt_config } }; }
  }
}

export function useGenerationSubmission(courseId: string | undefined) {
  const storageKey = useMemo(() => `edu-ai:generation-draft:${courseId || "none"}`, [courseId]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [retainedDraft, setRetainedDraft] = useState<GenerationDraft | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const job = useJobStore((state) => jobId ? state.jobs[jobId] : undefined);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(storageKey);
      if (!stored) return;
      const value = JSON.parse(stored) as { jobId?: string; draft?: GenerationDraft };
      if (value.jobId) { setJobId(value.jobId); requestJobRefresh(value.jobId); }
      if (value.draft) setRetainedDraft(value.draft);
    } catch { window.localStorage.removeItem(storageKey); }
  }, [storageKey]);

  const submit = useCallback(async (draft: GenerationDraft) => {
    if (!courseId) throw new Error("请先进入一门课程");
    setSubmitting(true);
    setError(null);
    setRetainedDraft(draft);
    try {
      await apiRequest("/api/chat/v2/generation/preflight", {
        method: "POST",
        body: JSON.stringify({ course_id: courseId, resource_type: draft.resourceType, source_mode: draft.source.mode, selected_doc_ids: draft.source.selectedDocumentIds }),
      });
      const idempotencyKey = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `ui-${draft.resourceType}-${Date.now()}`;
      const request = buildGenerationRequest(draft, courseId, idempotencyKey);
      let submitted = await apiRequest<Submitted>(request.path, { method: "POST", body: JSON.stringify(request.body) });
      const pptDraftId = submitted.draft_id || submitted.draft?.draft_id;
      if (draft.resourceType === "ppt" && pptDraftId) {
        const configuredOutline = Array.isArray(draft.config?.outline) ? { slides: draft.config.outline } : submitted.outline;
        submitted = await apiRequest<Submitted>("/api/chat/v2/ppt/generate", { method: "POST", body: JSON.stringify({ draft_id: pptDraftId, outline: configuredOutline, confirm: true, idempotency_key: `${idempotencyKey}-generate` }) });
      }
      const nextJobId = submitted.edu_job_id || submitted.task_id;
      if (!nextJobId) throw new Error("生成任务未返回可恢复的任务编号");
      setJobId(nextJobId);
      if (submitted.edu_job_id && "status" in submitted) registerCreatedJob(submitted as unknown as JobRecord);
      else requestJobRefresh(nextJobId);
      window.localStorage.setItem(storageKey, JSON.stringify({ jobId: nextJobId, draft }));
      return nextJobId;
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "提交生成任务失败";
      setError(message);
      throw reason;
    } finally { setSubmitting(false); }
  }, [courseId, storageKey]);

  const cancel = useCallback(async () => {
    if (!jobId) return;
    await cancelJob(jobId);
    requestJobRefresh(jobId);
  }, [jobId]);

  return { jobId, job, retainedDraft, submitting, error, submit, cancel, retry: retainedDraft ? () => submit(retainedDraft) : null };
}
