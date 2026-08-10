export type TeacherCourseRoute =
  | "course-detail"
  | "learning"
  | "ai"
  | "knowledge"
  | "graph"
  | "classroom-studio"
  | "resources"
  | "edit";

export const teacherSidebarItems: ReadonlyArray<{
  route: TeacherCourseRoute;
  label: string;
  icon: string;
}> = [
  { route: "course-detail", label: "课程概览", icon: "dashboard" },
  { route: "learning", label: "学习任务", icon: "fact_check" },
  { route: "ai", label: "问答与生成", icon: "auto_awesome" },
  { route: "knowledge", label: "课程知识", icon: "menu_book" },
  { route: "classroom-studio", label: "AI 课堂", icon: "play_circle" },
  { route: "resources", label: "课程资源", icon: "folder_open" },
  { route: "edit", label: "课程设置", icon: "settings" },
];

function normalizeCourseId(courseId: string | null | undefined): string | null {
  const normalized = String(courseId ?? "").trim();
  if (!normalized || normalized === "undefined" || normalized === "null") {
    return null;
  }
  return normalized;
}

export function buildTeacherCourseHash(
  route: TeacherCourseRoute,
  courseId: string | null | undefined,
  target?: Readonly<Record<string, string | null | undefined>>,
): string {
  const normalizedCourseId = normalizeCourseId(courseId);
  if (!normalizedCourseId) {
    return "#course";
  }

  const params = new URLSearchParams({ course_id: normalizedCourseId });
  for (const [key, value] of Object.entries(target ?? {})) {
    const normalizedValue = String(value ?? "").trim();
    if (normalizedValue) {
      params.set(key, normalizedValue);
    }
  }
  return `#${route}?${params.toString()}`;
}

export function readTeacherCourseId(hash: string): string | null {
  const query = String(hash || "").split("?")[1] ?? "";
  return normalizeCourseId(new URLSearchParams(query).get("course_id"));
}

export type CourseKnowledgeView = "documents" | "structure";

export function readTeacherCourseLocation(hash: string): {
  route: TeacherCourseRoute | null;
  courseId: string | null;
  view?: CourseKnowledgeView;
} {
  const normalized = String(hash || "").replace(/^#/, "");
  const [routeName, query = ""] = normalized.split("?");
  const route = ["course-detail", "learning", "ai", "knowledge", "graph", "classroom-studio", "resources", "edit"].includes(routeName)
    ? routeName as TeacherCourseRoute
    : null;
  const params = new URLSearchParams(query);
  const courseId = normalizeCourseId(params.get("course_id"));
  if (route === "knowledge") {
    return {
      route,
      courseId,
      view: params.get("view") === "documents" ? "documents" : "structure",
    };
  }
  return { route, courseId };
}
