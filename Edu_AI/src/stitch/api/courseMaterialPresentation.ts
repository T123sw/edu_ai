import { buildClassroomPlayerHash } from "../../openmaic/classroomGenerationFlow";
import type { CourseMaterial } from "./types";

export type CourseMaterialFilterKey =
  | "all"
  | "classroom"
  | "document"
  | "lesson_plan"
  | "ppt"
  | "flashcard"
  | "quiz"
  | "interactive"
  | "other";

export const COURSE_MATERIAL_FILTERS: ReadonlyArray<{
  key: CourseMaterialFilterKey;
  label: string;
}> = [
  { key: "all", label: "全部" },
  { key: "classroom", label: "AI 课堂" },
  { key: "document", label: "文稿" },
  { key: "lesson_plan", label: "教案" },
  { key: "ppt", label: "PPT" },
  { key: "flashcard", label: "闪卡" },
  { key: "quiz", label: "习题" },
  { key: "interactive", label: "互动" },
  { key: "other", label: "其他" },
] as const;

const MATERIAL_TYPE_META: Record<
  string,
  { label: string; icon: string; known: true }
> = {
  classroom: { label: "AI 课堂", icon: "slideshow", known: true },
  report: { label: "报告", icon: "description", known: true },
  lesson_plan: { label: "教案", icon: "menu_book", known: true },
  blog: { label: "教学博客", icon: "article", known: true },
  quiz: { label: "习题", icon: "quiz", known: true },
  game: { label: "小游戏", icon: "sports_esports", known: true },
  graph: { label: "思维导图", icon: "account_tree", known: true },
  ppt: { label: "PPT", icon: "co_present", known: true },
  flashcard: { label: "闪卡", icon: "style", known: true },
  video: { label: "视频", icon: "movie", known: true },
  audio: { label: "音频", icon: "headphones", known: true },
};

export function getCourseMaterialTypeMeta(materialType: string): {
  label: string;
  icon: string;
  known: boolean;
} {
  const normalized = String(materialType || "").trim();
  return (
    MATERIAL_TYPE_META[normalized] ?? {
      label: normalized || "未知类型",
      icon: "draft",
      known: false,
    }
  );
}

export function isCourseMaterialInFilter(
  material: Pick<CourseMaterial, "material_type">,
  filter: CourseMaterialFilterKey,
): boolean {
  const type = String(material.material_type || "").trim();
  if (filter === "all") return true;
  if (filter === "classroom") return type === "classroom";
  if (filter === "document") return type === "report" || type === "blog";
  if (filter === "lesson_plan") return type === "lesson_plan";
  if (filter === "ppt") return type === "ppt";
  if (filter === "flashcard") return type === "flashcard";
  if (filter === "quiz") return type === "quiz";
  if (filter === "interactive") return type === "game" || type === "graph";
  return !MATERIAL_TYPE_META[type];
}

export function getCourseMaterialOpenTarget(
  material: CourseMaterial,
): { kind: "route" | "preview"; value: string } {
  const materialId = String(material.material_id || "").trim();
  const materialType = String(material.material_type || "").trim();
  const courseId = String(material.course_id || "").trim();

  if (materialType === "classroom" && courseId && materialId) {
    return {
      kind: "route",
      value: buildClassroomPlayerHash(courseId, materialId),
    };
  }

  return { kind: "preview", value: materialId };
}
