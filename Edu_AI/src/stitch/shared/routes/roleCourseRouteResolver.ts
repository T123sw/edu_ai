import type { AuthUser } from "../../authSession";
import {
  buildStudentHash,
  type StudentResourceSpace,
  type StudentRoute,
} from "../../student/routes/studentRoutes";
import {
  buildTeacherCourseHash,
  type TeacherCourseRoute,
} from "../../teacherRoutes";

const studentRouteByTeacherRoute: Record<TeacherCourseRoute, StudentRoute> = {
  "course-detail": "student-course-detail",
  learning: "student-learning",
  ai: "student-ai",
  knowledge: "student-course-knowledge",
  graph: "student-course-knowledge",
  "classroom-studio": "student-classroom",
  resources: "student-resources",
  edit: "student-course-detail",
};

export type RoleCourseHashTarget = Readonly<{
  view?: string | null;
  space?: string | null;
  material_type?: string | null;
  material_id?: string | null;
  classroom_id?: string | null;
  action?: string | null;
  scopeType?: string | null;
  scopeId?: string | null;
  scopeLabel?: string | null;
}>;

export function buildRoleCourseHash(
  role: AuthUser["role"] | null | undefined,
  route: TeacherCourseRoute,
  courseId: string | null | undefined,
  target?: RoleCourseHashTarget,
): string {
  if (role !== "student") {
    const { view: _legacyView, ...supportedTarget } = target ?? {};
    return buildTeacherCourseHash(route, courseId, supportedTarget);
  }

  return buildStudentHash(studentRouteByTeacherRoute[route], {
    courseId,
    space: target?.space === "course" ? "course" : target?.space === "mine" ? "mine" : undefined,
    materialType: target?.material_type ?? undefined,
    materialId: target?.material_id ?? undefined,
    classroomId: target?.classroom_id ?? undefined,
    scopeType: target?.scopeType === "knowledge_point" ? "knowledge_point" : target?.scopeType === "course" ? "course" : undefined,
    scopeId: target?.scopeId ?? undefined,
    scopeLabel: target?.scopeLabel ?? undefined,
  });
}

export function homeHashForRole(role: AuthUser["role"] | null | undefined): string {
  return role === "student" ? "#student-home" : "#home";
}

export function studentResourceSpace(value: string | null | undefined): StudentResourceSpace {
  return value === "course" ? "course" : "mine";
}
