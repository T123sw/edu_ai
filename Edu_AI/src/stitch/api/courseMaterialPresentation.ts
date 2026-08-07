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

export type CourseMaterialPresentation = {
  title: string;
  typeLabel: string;
  statusLabel: string;
  meta: ReadonlyArray<{ label: string; value: string }>;
};

function formatCreatedTime(value: string | undefined): string {
  if (!value) return "未记录";
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return "未记录";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

function sourceScopeLabel(material: CourseMaterial): string {
  const snapshot = material.source_snapshot ?? material.source ?? {};
  const mode = String(snapshot.mode ?? snapshot.source_mode ?? "");
  if (mode === "selected_documents") return "已选课程资料";
  if (mode === "course_auto") return "课程资料（自动）";
  if (mode === "none") return "未使用课程资料";
  if (material.scope_type === "knowledge_point") return "指定知识点";
  return "课程级资源";
}

export function toCourseMaterialPresentation(
  material: CourseMaterial,
): CourseMaterialPresentation {
  const typeLabel = getCourseMaterialTypeMeta(material.material_type).label;
  const status = String(material.status || "completed");
  const statusLabel = status === "failed"
    ? "生成失败"
    : status === "processing" || status === "pending"
      ? "生成中"
      : "可使用";
  return {
    title: material.title || material.topic || "未命名资源",
    typeLabel,
    statusLabel,
    meta: [
      { label: "类型", value: typeLabel },
      { label: "创建者", value: material.created_by || material.owner_user_id || "未记录" },
      {
        label: "可见范围",
        value: material.visibility === "private" ? "仅自己可见" : "课程成员可见",
      },
      { label: "资料来源", value: sourceScopeLabel(material) },
      { label: "创建时间", value: formatCreatedTime(material.created_at) },
    ],
  };
}
