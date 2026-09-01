import type { CourseMaterialVisibility } from "../../stitch/api/types";

export function buildGenerationSavedMessage(options: {
  visibility: CourseMaterialVisibility;
}): string {
  return options.visibility === "course"
    ? "生成完成，已保存到“课程共享”，课程成员可见。"
    : "生成完成，已保存到“我的资源”，仅你可见。";
}

export function resolveGenerationReply(options: {
  generatedResourceCount: number;
  fallbackMessage: string;
}): string {
  if (options.generatedResourceCount > 0) {
    return buildGenerationSavedMessage({ visibility: "private" });
  }
  return options.fallbackMessage;
}
