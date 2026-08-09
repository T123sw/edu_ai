import { useEffect, useLayoutEffect, useState, type PropsWithChildren } from "react";
import { createPortal } from "react-dom";

import { JobCenterTrigger } from "../../jobs/JobCenterDrawer";
import { PageState } from "../components/PageState";
import { useAuthSession } from "../authSession";
import { MaterialIcon, UnifiedCourseShellProvider, cx, routeHref, routes } from "../shared";
import type { StudentRoute } from "../student/routes/studentRoutes";
import type { TeacherCourseRoute } from "../teacherRoutes";
import { buildRoleCourseHash, homeHashForRole } from "../shared/routes/roleCourseRouteResolver";
import { useCourseRoute } from "./CourseRouteProvider";
import { getCourseNavigation, getCoursePageTitle, type CourseNavigationId } from "./courseNavigation";

export function CourseShellHeaderSlot({ children }: PropsWithChildren) {
  const [target, setTarget] = useState<HTMLElement | null>(null);

  useLayoutEffect(() => {
    setTarget(document.querySelector<HTMLElement>("[data-course-shell-page-actions]"));
  }, []);

  return target ? createPortal(children, target) : null;
}

type CourseShellRoute = TeacherCourseRoute | StudentRoute;

const studentRouteByNavigationId: Partial<Record<CourseNavigationId, StudentRoute>> = {
  overview: "student-course-detail",
  workspace: "student-ai",
  knowledge: "student-course-knowledge",
  classroom: "student-classroom",
  resources: "student-resources",
};

const studentNavigationLabels: Partial<Record<CourseNavigationId, string>> = {
  overview: "课程概览",
  workspace: "AI问答",
  knowledge: "课程知识",
  classroom: "AI课堂",
  resources: "资源管理",
};

export function CourseShell({ activeRoute, children }: PropsWithChildren<{ activeRoute: CourseShellRoute }>) {
  const { user } = useAuthSession();
  const { courseId, course, courseRole, loading, error, reload } = useCourseRoute();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const isStudent = user?.role === "student";
  const navigation = getCourseNavigation(courseRole).filter((item) => !isStudent || item.id !== "settings");
  const activeStudentNavigation = navigation.find((item) => studentRouteByNavigationId[item.id] === activeRoute);
  const homeHref = homeHashForRole(user?.role);

  useEffect(() => setDrawerOpen(false), [activeRoute]);

  const nav = (compact = false) => (
    <nav className={cx("course-navigation", compact && "course-navigation--compact")} aria-label="课程工作区">
      {navigation.map((item) => {
        const active = isStudent
          ? studentRouteByNavigationId[item.id] === activeRoute
          : item.routes.includes(activeRoute as TeacherCourseRoute);
        return (
          <a
            key={item.id}
            href={buildRoleCourseHash(user?.role, item.hrefRoute, courseId)}
            className={cx("course-navigation__link", active && "is-active")}
            aria-current={active ? "page" : undefined}
            onClick={() => setDrawerOpen(false)}
          >
            <span className="course-navigation__icon"><MaterialIcon name={item.icon} /></span>
            <strong>{isStudent ? studentNavigationLabels[item.id] ?? item.label : item.label}</strong>
          </a>
        );
      })}
    </nav>
  );

  const retry = <button type="button" className="course-shell__state-action" onClick={() => void reload()}>重新加载</button>;
  let content = children;
  if (loading && !course) {
    content = <main><PageState state={{ kind: "loading", description: "正在同步最新课程信息…" }} /></main>;
  } else if (error) {
    const status = Number(error.status ?? 0);
    content = (
      <main><PageState state={
        status === 403
          ? { kind: "forbidden", action: retry }
          : status === 0
            ? { kind: "offline", action: retry }
            : { kind: "error", description: error.message, action: retry }
      } /></main>
    );
  } else if (!courseId || !course) {
    content = (
      <main><PageState state={{
        kind: "empty",
        title: "请先选择一门课程",
        description: "返回课程首页后再进入课程工作区。",
        action: <a href={homeHref}>返回课程首页</a>,
      }} /></main>
    );
  }

  return (
    <UnifiedCourseShellProvider>
      <div className="course-shell" data-testid="course-shell">
        <aside className="course-shell__sidebar">
          <a href={homeHref} className="course-shell__brand">Edu AI</a>
          {nav()}
          <a href={homeHref} className="course-shell__back"><MaterialIcon name="arrow_back" /> 返回全部课程</a>
        </aside>

        <div className="course-shell__content">
          <header className="course-shell__header">
            <button
              type="button"
              className="course-shell__menu"
              aria-label="打开课程导航"
              aria-expanded={drawerOpen}
              onClick={() => setDrawerOpen(true)}
            ><MaterialIcon name="menu_book" /></button>
            <div className="course-shell__heading">
              <p><a href={homeHref}>全部课程</a><span>/</span>{course?.title ?? "课程"}</p>
              <div className="course-shell__heading-row">
                <h1>{isStudent
                  ? activeStudentNavigation
                    ? studentNavigationLabels[activeStudentNavigation.id] ?? activeStudentNavigation.label
                    : "课程学习"
                  : getCoursePageTitle(activeRoute as TeacherCourseRoute)}</h1>
                <div className="course-shell__page-actions" data-course-shell-page-actions />
              </div>
            </div>
            <div className="course-shell__actions">
              <JobCenterTrigger placement="inline" />
              <a className="course-shell__profile" href={routeHref(routes.profile)}>
                <MaterialIcon name="person" />
                <span>个人中心</span>
              </a>
            </div>
          </header>
          <div className="course-shell__page">{content}</div>
        </div>

        {drawerOpen ? (
          <div className="course-shell__drawer-layer" data-testid="course-navigation-drawer">
            <button type="button" className="course-shell__drawer-backdrop" aria-label="关闭课程导航" onClick={() => setDrawerOpen(false)} />
            <aside className="course-shell__drawer" aria-label="课程导航菜单">
              <div className="course-shell__drawer-head">
                <strong>{course?.title ?? "课程工作区"}</strong>
                <button type="button" aria-label="关闭课程导航" onClick={() => setDrawerOpen(false)}><MaterialIcon name="close" /></button>
              </div>
              {nav(true)}
            </aside>
          </div>
        ) : null}
      </div>
    </UnifiedCourseShellProvider>
  );
}
