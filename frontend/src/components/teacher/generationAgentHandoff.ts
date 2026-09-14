import type { QueuedAgentRequest } from "../generation/generationAgentRequest";
import {
  generationPromptDraftKey,
  writeGenerationPromptDraft,
} from "../generation/generationPromptDraft";

export type ActiveAgentWorkspace = {
  ownerUserId: string;
  courseId: string;
  scopeType: "course" | "knowledge_point";
  scopeId?: string;
};

export function validateQueuedAgentWorkspace(
  request: QueuedAgentRequest,
  active: ActiveAgentWorkspace,
): string | null {
  if (request.ownerUserId !== active.ownerUserId) {
    return "账号已经变化，原账号的生成要求未发送。";
  }
  if (request.courseId !== active.courseId) {
    return "课程已经变化，生成要求已保存到原课程草稿。";
  }
  if (request.scopeType !== active.scopeType || (request.scopeId || "") !== (active.scopeId || "")) {
    return "知识点范围已经变化，生成要求已保存到原范围草稿。";
  }
  return null;
}

export function queuedAgentPromptDraftKey(request: QueuedAgentRequest): string {
  return generationPromptDraftKey({
    ownerUserId: request.ownerUserId,
    courseId: request.courseId,
    scopeType: request.scopeType,
    scopeId: request.scopeId,
    resourceType: request.resourceType === "graph" ? "mind_map" : request.resourceType,
  });
}

export function restoreQueuedAgentPromptDraft(request: QueuedAgentRequest): void {
  writeGenerationPromptDraft(queuedAgentPromptDraftKey(request), request.text);
}
