import type { TeacherCourseRoute } from "../teacherRoutes";

export type CourseNavigationId =
  | "workspace"
  | "knowledge"
  | "classroom"
  | "resources"
  | "learning";

export type CourseNavigationItem = {
  id: CourseNavigationId;
  label: string;
  icon: string;
  hrefRoute: TeacherCourseRoute;
  routes: readonly TeacherCourseRoute[];
};

const courseNavigation: readonly CourseNavigationItem[] = [
  { id: "workspace", label: "工作台", icon: "auto_awesome", hrefRoute: "ai", routes: ["ai"] },
  { id: "knowledge", label: "课程知识", icon: "menu_book", hrefRoute: "knowledge", routes: ["knowledge", "graph"] },
  { id: "classroom", label: "AI课堂", icon: "play_circle", hrefRoute: "classroom-studio", routes: ["classroom-studio"] },
  { id: "resources", label: "资源管理", icon: "folder_open", hrefRoute: "resources", routes: ["resources"] },
  { id: "learning", label: "学习任务", icon: "fact_check", hrefRoute: "learning", routes: ["learning"] },
];

const coursePageTitles: Readonly<Record<TeacherCourseRoute, string>> = {
  "course-detail": "课程概览",
  learning: "学习任务",
  ai: "工作台",
  knowledge: "课程知识",
  graph: "课程知识",
  "classroom-studio": "AI课堂",
  resources: "资源管理",
  edit: "课程设置",
};

export function getCourseNavigation() {
  return courseNavigation;
}

export function getCoursePageTitle(route: TeacherCourseRoute): string {
  return coursePageTitles[route] ?? "课程工作区";
}

export function isCourseWorkspaceRoute(route: string): route is TeacherCourseRoute {
  return Object.hasOwn(coursePageTitles, route);
}
