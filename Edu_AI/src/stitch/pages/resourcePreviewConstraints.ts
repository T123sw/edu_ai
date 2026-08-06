import type { CourseMaterial } from "../api/types";

export const RESOURCE_RICH_PREVIEW_CLASSNAME = "edu-rich-preview";

export type CourseMaterialPreviewKind =
  | "rich-text"
  | "blog"
  | "quiz"
  | "flashcard"
  | "ppt"
  | "mind-map"
  | "game"
  | "classroom"
  | "unknown";

export function getCourseMaterialPreviewKind(
  material: Pick<CourseMaterial, "material_type">,
): CourseMaterialPreviewKind {
  const kindByType: Record<string, CourseMaterialPreviewKind> = {
    report: "rich-text",
    lesson_plan: "rich-text",
    blog: "blog",
    quiz: "quiz",
    flashcard: "flashcard",
    ppt: "ppt",
    graph: "mind-map",
    game: "game",
    classroom: "classroom",
  };
  return kindByType[String(material.material_type || "").trim()] ?? "unknown";
}
