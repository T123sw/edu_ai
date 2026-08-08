import { useEffect, useLayoutEffect, useState, type PropsWithChildren } from "react";
import { createPortal } from "react-dom";

import { JobCenterTrigger } from "../../jobs/JobCenterDrawer";
import { PageState } from "../components/PageState";
import { MaterialIcon, UnifiedCourseShellProvider, cx, routeHref, routes } from "../shared";
import { buildTeacherCourseHash, type TeacherCourseRoute } from "../teacherRoutes";
import { useCourseRoute } from "./CourseRouteProvider";
import { getCourseNavigation, getCoursePageTitle } from "./courseNavigation";

export function CourseShellHeaderSlot({ children }: PropsWithChildren) {
  const [target, setTarget] = useState<HTMLElement | null>(null);

  useLayoutEffect(() => {
    setTarget(document.querySelector<HTMLElement>("[data-course-shell-page-actions]"));
  }, []);

  return target ? createPortal(children, target) : null;
}

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
            <strong>{item.label}</strong>
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
              <div className="course-shell__heading-row">
                <h1>{getCoursePageTitle(activeRoute)}</h1>
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
