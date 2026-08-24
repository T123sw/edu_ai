export type StudentRoute =
  | "student-home"
  | "student-course-detail"
  | "student-learning"
  | "student-ai"
  | "student-course-knowledge"
  | "student-personal-knowledge"
  | "student-classroom"
  | "student-resources";

export type StudentResourceSpace = "mine" | "course";

const studentRouteNames: readonly StudentRoute[] = [
  "student-home",
  "student-course-detail",
  "student-learning",
  "student-ai",
  "student-course-knowledge",
  "student-personal-knowledge",
  "student-classroom",
  "student-resources",
];

const studentRoutes = new Set<StudentRoute>(studentRouteNames);
const courseRoutes = new Set<StudentRoute>([
  "student-course-detail",
  "student-learning",
  "student-ai",
  "student-course-knowledge",
  "student-classroom",
  "student-resources",
]);

export function normalizeStudentCourseId(value: string | null | undefined): string | null {
  const normalized = String(value ?? "").trim();
  return normalized && normalized !== "undefined" && normalized !== "null" ? normalized : null;
}

export function isStudentRoute(value: string): value is StudentRoute {
  return studentRoutes.has(value as StudentRoute);
}

export function buildStudentHash(
  route: StudentRoute,
  options?: {
    courseId?: string | null;
    space?: StudentResourceSpace;
    materialType?: string;
    materialId?: string;
    classroomId?: string;
    scopeType?: "course" | "knowledge_point";
    scopeId?: string;
    scopeLabel?: string;
  },
): string {
  if (route === "student-home" || route === "student-personal-knowledge") {
    return `#${route}`;
  }
  const normalizedCourseId = normalizeStudentCourseId(options?.courseId);
  if (courseRoutes.has(route) && !normalizedCourseId) return "#student-home";

  const params = new URLSearchParams({ course_id: normalizedCourseId! });
  const target = {
    space: options?.space,
    material_type: options?.materialType,
    material_id: options?.materialId,
    classroom_id: options?.classroomId,
    scopeType: options?.scopeType,
    scopeId: options?.scopeId,
    scopeLabel: options?.scopeLabel,
  };
  for (const [key, value] of Object.entries(target)) {
    const normalized = String(value ?? "").trim();
    if (normalized) params.set(key, normalized);
  }
  return `#${route}?${params.toString()}`;
}

export function readStudentLocation(hash: string): {
  route: StudentRoute | null;
  courseId: string | null;
  space: StudentResourceSpace | undefined;
} {
  const normalized = String(hash || "").replace(/^#/, "");
  const [routeName, query = ""] = normalized.split("?");
  const route = isStudentRoute(routeName) ? routeName : null;
  const params = new URLSearchParams(query);
  const space = route === "student-resources" || route === "student-classroom"
    ? params.get("space") === "course" ? "course" : "mine"
    : undefined;
  return {
    route,
    courseId: normalizeStudentCourseId(params.get("course_id")),
    space,
  };
}
