export type TeacherCourseRoute =
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
  { route: "ai", label: "问答", icon: "quiz" },
  { route: "knowledge", label: "课程知识库", icon: "menu_book" },
  { route: "graph", label: "知识图谱", icon: "hub" },
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
