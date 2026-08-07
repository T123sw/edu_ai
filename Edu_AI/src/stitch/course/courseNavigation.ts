import type { CourseRole } from "./coursePermissions";
import type { TeacherCourseRoute } from "../teacherRoutes";

export type CourseNavigationId =
  | "overview"
  | "workspace"
  | "knowledge"
  | "classroom"
  | "resources"
  | "settings";

export type CourseNavigationItem = {
  id: CourseNavigationId;
  label: string;
  icon: string;
  hrefRoute: TeacherCourseRoute;
  routes: readonly TeacherCourseRoute[];
  editableOnly?: boolean;
};

const courseNavigation: readonly CourseNavigationItem[] = [
  { id: "overview", label: "课程概览", icon: "dashboard", hrefRoute: "course-detail", routes: ["course-detail"] },
  { id: "workspace", label: "问答与生成", icon: "auto_awesome", hrefRoute: "ai", routes: ["ai"] },
  { id: "knowledge", label: "课程知识", icon: "menu_book", hrefRoute: "knowledge", routes: ["knowledge", "graph"] },
  { id: "classroom", label: "AI 课堂", icon: "play_circle", hrefRoute: "classroom-studio", routes: ["classroom-studio"] },
  { id: "resources", label: "课程资源", icon: "folder_open", hrefRoute: "resources", routes: ["resources"] },
  { id: "settings", label: "课程设置", icon: "settings", hrefRoute: "edit", routes: ["edit"], editableOnly: true },
];

export function getCourseNavigation(role: CourseRole | null | undefined) {
  return courseNavigation.filter((item) => !item.editableOnly || role !== "viewer");
}

export function getCoursePageTitle(route: TeacherCourseRoute): string {
  return courseNavigation.find((item) => item.routes.includes(route))?.label ?? "课程工作区";
}

export function isCourseWorkspaceRoute(route: string): route is TeacherCourseRoute {
  return courseNavigation.some((item) => item.routes.includes(route as TeacherCourseRoute));
}
