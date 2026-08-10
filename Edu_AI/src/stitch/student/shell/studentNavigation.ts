import type { StudentRoute } from "../routes/studentRoutes";

export const studentNavigationItems: ReadonlyArray<{
  route: StudentRoute;
  label: string;
  icon: string;
  requiresCourse: boolean;
}> = [
  { route: "student-home", label: "学习首页", icon: "school", requiresCourse: false },
  { route: "student-learning", label: "学习任务", icon: "fact_check", requiresCourse: true },
  { route: "student-ai", label: "AI问答", icon: "auto_awesome", requiresCourse: true },
  { route: "student-course-knowledge", label: "课程知识", icon: "hub", requiresCourse: true },
  { route: "student-personal-knowledge", label: "个人知识库", icon: "database", requiresCourse: false },
  { route: "student-classroom", label: "AI课堂", icon: "play_circle", requiresCourse: true },
  { route: "student-resources", label: "资源管理", icon: "folder_open", requiresCourse: true },
] as const;

export function studentRouteRequiresCourse(route: StudentRoute): boolean {
  return studentNavigationItems.find((item) => item.route === route)?.requiresCourse ?? false;
}
