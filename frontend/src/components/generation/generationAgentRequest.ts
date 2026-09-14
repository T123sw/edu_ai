import type { GenerationSourceMode } from "./GenerationSourceSelector";
import type { GenerationResourceType } from "./generationRegistry";

export type AgentGenerationResourceType =
  | "report"
  | "lesson_plan"
  | "blog"
  | "quiz"
  | "flashcard"
  | "graph"
  | "game"
  | "classroom";

export type GenerationActionHint = `generate.${AgentGenerationResourceType}`;

export type QueuedAgentRequest = Readonly<{
  requestId: string;
  text: string;
  resourceType: AgentGenerationResourceType;
  actionHint: GenerationActionHint;
  entryMode: "generation_factory";
  ownerUserId: string;
  courseId: string;
  scopeType: "course" | "knowledge_point";
  scopeId?: string;
  sourceMode: GenerationSourceMode;
  selectedDocumentIds: readonly string[];
  allowRag: boolean;
  allowWeb: boolean;
}>;

export type BuildQueuedAgentRequestOptions = {
  requestId: string;
  text: string;
  resourceType: GenerationResourceType;
  ownerUserId: string;
  courseId: string;
  scopeType?: "course" | "knowledge_point";
  scopeId?: string;
  sourceMode: GenerationSourceMode;
  selectedDocumentIds: readonly string[];
  allowWeb: boolean;
};

export function canonicalGenerationResourceType(
  resourceType: GenerationResourceType,
): AgentGenerationResourceType {
  return resourceType === "mind_map" ? "graph" : resourceType;
}

export function normalizeGenerationBrief(text: string): string {
  return String(text || "").trim();
}

export function buildQueuedAgentRequest(
  options: BuildQueuedAgentRequestOptions,
): QueuedAgentRequest {
  const text = normalizeGenerationBrief(options.text);
  const ownerUserId = String(options.ownerUserId || "").trim();
  const courseId = String(options.courseId || "").trim();
  const requestId = String(options.requestId || "").trim();
  const scopeType = options.scopeType || "course";
  const scopeId = String(options.scopeId || "").trim() || undefined;
  const selectedDocumentIds = [...new Set(
    options.selectedDocumentIds.map((id) => String(id || "").trim()).filter(Boolean),
  )];

  if (!text) throw new Error("请输入生成要求");
  if (!requestId) throw new Error("无法创建请求，请重试");
  if (!ownerUserId) throw new Error("请先登录后再生成资源");
  if (!courseId) throw new Error("请先选择课程");
  if (scopeType === "knowledge_point" && !scopeId) throw new Error("当前知识点无效，请重新选择");
  if (options.sourceMode === "selected_documents" && selectedDocumentIds.length === 0) {
    throw new Error("请至少选择一份资料");
  }

  const resourceType = canonicalGenerationResourceType(options.resourceType);
  const frozenDocumentIds = Object.freeze(selectedDocumentIds);
  return Object.freeze({
    requestId,
    text,
    resourceType,
    actionHint: `generate.${resourceType}` as GenerationActionHint,
    entryMode: "generation_factory",
    ownerUserId,
    courseId,
    scopeType,
    ...(scopeId ? { scopeId } : {}),
    sourceMode: options.sourceMode,
    selectedDocumentIds: frozenDocumentIds,
    allowRag: options.sourceMode !== "none",
    allowWeb: Boolean(options.allowWeb),
  });
}
