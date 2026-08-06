import { useEffect, useState, type PropsWithChildren } from "react";

import { JobCenterTrigger } from "../../jobs/JobCenterDrawer";
import { PageState } from "../components/PageState";
import { MaterialIcon, UnifiedCourseShellProvider, cx, routeHref, routes } from "../shared";
import { buildTeacherCourseHash, type TeacherCourseRoute } from "../teacherRoutes";
import { useCourseRoute } from "./CourseRouteProvider";
import { getCourseNavigation, getCoursePageTitle } from "./courseNavigation";

const roleLabels = { owner: "课程负责人", editor: "课程编辑者", viewer: "课程查看者" } as const;

export function CourseShell({ activeRoute, children }: PropsWithChildren<{ activeRoute: TeacherCourseRoute }>) {
  const { courseId, course, courseRole, loading, error, reload } = useCourseRoute();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const navigation = getCourseNavigation(courseRole);

  useEffect(() => setDrawerOpen(false), [activeRoute]);

  const nav = (compact = false) => (
    <nav className={cx("course-navigation", compact && "course-navigation--compact")} aria-label="课程工作区">
      {navigation.map((item) => {
        const active = item.routes.includes(activeRoute);
        return (
          <a
            key={item.id}
            href={buildTeacherCourseHash(item.hrefRoute, courseId)}
            className={cx("course-navigation__link", active && "is-active")}
            aria-current={active ? "page" : undefined}
            onClick={() => setDrawerOpen(false)}
          >
            <span className="course-navigation__icon"><MaterialIcon name={item.icon} /></span>
            <span><strong>{item.label}</strong><small>{item.description}</small></span>
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
        action: <a href={routeHref(routes.home)}>返回课程首页</a>,
      }} /></main>
    );
  }

  return (
    <UnifiedCourseShellProvider>
      <div className="course-shell" data-testid="course-shell">
        <aside className="course-shell__sidebar">
          <a href={routeHref(routes.home)} className="course-shell__brand">Edu AI</a>
          <div className="course-shell__identity">
            <span>当前课程</span>
            <strong data-course-title>{course?.title ?? "课程工作区"}</strong>
            {courseRole ? <small>{roleLabels[courseRole]}</small> : null}
          </div>
          {nav()}
          <a href={routeHref(routes.home)} className="course-shell__back"><MaterialIcon name="arrow_back" /> 返回全部课程</a>
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
              <p><a href={routeHref(routes.home)}>全部课程</a><span>/</span>{course?.title ?? "课程"}</p>
              <h1>{getCoursePageTitle(activeRoute)}</h1>
            </div>
            <JobCenterTrigger placement="inline" />
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
