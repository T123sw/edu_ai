import { useCallback, useEffect, useMemo, useState } from "react";

import { cancelJob } from "../../../jobs/api";
import { registerCreatedJob, requestJobRefresh, useJobStore } from "../../../jobs/jobStore";
import type { JobRecord } from "../../../jobs/types";
import { apiRequest } from "../../../stitch/api/client";
import type { GenerationResourceType } from "./generationRegistry";
import type { GenerationSourceSelection } from "./GenerationSourceSelector";

export type GenerationDraft = {
  resourceType: GenerationResourceType;
  topic: string;
  audience: string;
  requirements: string;
  source: GenerationSourceSelection;
  config?: Record<string, unknown>;
};

type Submitted = { task_id?: string; edu_job_id?: string; draft_id?: string; outline?: unknown; [key: string]: unknown };

function sourcePayload(draft: GenerationDraft, courseId: string) {
  return {
    course_id: courseId,
    scope_type: "course",
    source_mode: draft.source.mode,
    selected_doc_ids: draft.source.selectedDocumentIds,
  };
}

export function buildGenerationRequest(draft: GenerationDraft, courseId: string): { path: string; body: Record<string, unknown> } {
  const source = sourcePayload(draft, courseId);
  const commonTopic = draft.topic.trim();
  switch (draft.resourceType) {
    case "report": return { path: "/api/chat/v2/report/direct", body: { ...source, question: commonTopic, report_config: { audience: draft.audience, special_requirements: draft.requirements, ...draft.config } } };
    case "lesson_plan": return { path: "/api/chat/v2/lesson-plan/direct", body: { ...source, topic: commonTopic, audience: draft.audience, duration_minutes: 45, objectives: [draft.requirements || commonTopic], lesson_type: "new_lesson", special_requirements: draft.requirements } };
    case "blog": return { path: "/api/chat/v2/blog/direct", body: { ...source, topic: commonTopic, audience: draft.audience, ...draft.config } };
    case "quiz": return { path: "/api/chat/v2/quiz/direct", body: { ...source, quiz_config: { topic: commonTopic, audience: draft.audience, difficulty: "medium", question_count: 10, question_types: ["single_choice"], include_answers: true, include_explanations: true, ...draft.config } } };
    case "flashcard": return { path: "/api/chat/v2/flashcard/direct", body: { ...source, flashcard_config: { title: commonTopic, count: 12, difficulty: "medium", show_source: true, ...draft.config } } };
    case "mind_map": return { path: "/api/chat/v2/graph/direct", body: { ...source, title: commonTopic, max_depth: Number(draft.config?.depth ?? 3), description: draft.requirements } };
    case "game": return { path: "/api/chat/v2/game/direct", body: { ...source, game_type: String(draft.config?.gameType ?? "classification"), topic: commonTopic, card_count: Number(draft.config?.cardCount ?? 8) } };
    case "classroom": return { path: `/api/courses/${encodeURIComponent(courseId)}/classrooms/generate`, body: { source_mode: draft.source.mode, selected_doc_ids: draft.source.selectedDocumentIds, topic: commonTopic, audience: draft.audience, requirement: draft.requirements || commonTopic, scene_count: Number(draft.config?.sceneCount ?? 6), enable_web_search: false, enable_tts: Boolean(draft.config?.voiceEnabled ?? true) } };
    case "ppt": return { path: "/api/chat/v2/ppt/outline", body: { ...source, ppt_config: { deck_title: commonTopic, audience: draft.audience, slide_count: Number(draft.config?.slideCount ?? 10), special_requirements: draft.requirements, ...draft.config } } };
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
      const request = buildGenerationRequest(draft, courseId);
      let submitted = await apiRequest<Submitted>(request.path, { method: "POST", body: JSON.stringify(request.body) });
      if (draft.resourceType === "ppt" && submitted.draft_id) {
        submitted = await apiRequest<Submitted>("/api/chat/v2/ppt/generate", { method: "POST", body: JSON.stringify({ draft_id: submitted.draft_id, outline: submitted.outline, confirm: true }) });
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
