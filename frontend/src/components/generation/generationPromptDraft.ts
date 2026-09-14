import type { GenerationResourceType } from "./generationRegistry";

export function generationPromptDraftKey(options: {
  ownerUserId: string;
  courseId: string;
  scopeType?: "course" | "knowledge_point";
  scopeId?: string;
  resourceType: GenerationResourceType;
}): string {
  const scopeType = options.scopeType || "course";
  const scopeId = scopeType === "knowledge_point" ? options.scopeId || "missing" : "course";
  return [
    "edu-ai-generation-brief",
    options.ownerUserId,
    options.courseId,
    scopeType,
    scopeId,
    options.resourceType,
  ].map(encodeURIComponent).join(":");
}

export function readGenerationPromptDraft(key: string): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(key) || "";
  } catch {
    return "";
  }
}

export function writeGenerationPromptDraft(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    if (value) window.localStorage.setItem(key, value);
    else window.localStorage.removeItem(key);
  } catch {
    // Draft persistence is best effort; generation remains available.
  }
}
