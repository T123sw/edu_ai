import { useEffect, useRef, useState, type PropsWithChildren } from "react";

import { JobCenterTrigger } from "../../jobs/JobCenterDrawer";
import { PageState } from "../components/PageState";
import { useAuthSession } from "../authSession";
import { MaterialIcon, UnifiedCourseShellProvider, cx, routeHref, routes } from "../shared";
import type { StudentRoute } from "../student/routes/studentRoutes";
import type { TeacherCourseRoute } from "../teacherRoutes";
import { buildRoleCourseHash, homeHashForRole } from "../shared/routes/roleCourseRouteResolver";
import { useCourseRoute } from "./CourseRouteProvider";
import { getCourseNavigation, getCoursePageTitle, type CourseNavigationId } from "./courseNavigation";

type CourseShellRoute = TeacherCourseRoute | StudentRoute;
type CourseNavigationVariant = "desktop" | "mobile";

const studentRouteByNavigationId: Record<CourseNavigationId, StudentRoute> = {
  workspace: "student-ai",
  knowledge: "student-course-knowledge",
  classroom: "student-classroom",
  resources: "student-resources",
  learning: "student-learning",
};

export function CourseShell({ activeRoute, children }: PropsWithChildren<{ activeRoute: CourseShellRoute }>) {
  const { user } = useAuthSession();
  const { courseId, course, loading, error, reload } = useCourseRoute();
  const [courseMenuOpen, setCourseMenuOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const courseMenuRef = useRef<HTMLDivElement | null>(null);
  const isStudent = user?.role === "student";
  const navigation = getCourseNavigation();
  const activeNavigation = navigation.find((item) => (
    isStudent
      ? studentRouteByNavigationId[item.id] === activeRoute
      : item.routes.includes(activeRoute as TeacherCourseRoute)
  ));
  const homeHref = homeHashForRole(user?.role);
  const pageTitle = activeNavigation?.label
    ?? (isStudent ? "课程概览" : getCoursePageTitle(activeRoute as TeacherCourseRoute));

  useEffect(() => {
    setCourseMenuOpen(false);
    setMobileMenuOpen(false);
  }, [activeRoute]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setCourseMenuOpen(false);
        setMobileMenuOpen(false);
      }
    };
    const closeCourseMenuOutside = (event: PointerEvent) => {
      if (!courseMenuRef.current?.contains(event.target as Node)) {
        setCourseMenuOpen(false);
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    document.addEventListener("pointerdown", closeCourseMenuOutside);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.removeEventListener("pointerdown", closeCourseMenuOutside);
    };
  }, []);

  const renderNavigation = (variant: CourseNavigationVariant) => (
    <nav
      className={cx(
        "course-navigation",
        variant === "desktop" ? "course-navigation--desktop" : "course-navigation--mobile",
      )}
      aria-label={variant === "desktop" ? "课程工作栏" : "移动端课程工作栏"}
    >
      {navigation.map((item) => {
        const active = item.id === activeNavigation?.id;
        return (
          <a
            key={item.id}
            href={buildRoleCourseHash(user?.role, item.hrefRoute, courseId)}
            className={cx("course-navigation__link", active && "is-active")}
            aria-current={active ? "page" : undefined}
            onClick={() => setMobileMenuOpen(false)}
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
        action: <a href={homeHref}>返回课程首页</a>,
      }} /></main>
    );
  }

  return (
    <UnifiedCourseShellProvider>
      <div className="course-shell" data-testid="course-shell">
        <header className="course-shell__workbar">
          <a href={homeHref} className="course-shell__brand" aria-label="返回全部课程">Edu AI</a>

          <div className="course-shell__course" ref={courseMenuRef}>
            {!isStudent ? (
              <button
                type="button"
                className="course-shell__course-trigger"
                aria-label="打开当前课程菜单"
                aria-haspopup="menu"
                aria-expanded={courseMenuOpen}
                title={course?.title ?? "当前课程"}
                onClick={() => {
                  setCourseMenuOpen((open) => !open);
                  setMobileMenuOpen(false);
                }}
              >
                <span>{course?.title ?? "当前课程"}</span>
                <MaterialIcon name={courseMenuOpen ? "expand_less" : "expand_more"} />
              </button>
            ) : (
              <span className="course-shell__course-name" title={course?.title ?? "当前课程"}>
                {course?.title ?? "当前课程"}
              </span>
            )}

            {!isStudent && courseMenuOpen ? (
              <div className="course-shell__course-menu" role="menu">
                <a
                  role="menuitem"
                  href={buildRoleCourseHash(user?.role, "course-detail", courseId)}
                  onClick={() => setCourseMenuOpen(false)}
                >
                  <MaterialIcon name="home" />
                  <span>课程首页</span>
                </a>
                <a
                  role="menuitem"
                  href={buildRoleCourseHash(user?.role, "edit", courseId)}
                  onClick={() => setCourseMenuOpen(false)}
                >
                  <MaterialIcon name="settings" />
                  <span>课程设置</span>
                </a>
              </div>
            ) : null}
          </div>

          {renderNavigation("desktop")}

          <div className="course-shell__actions">
            <JobCenterTrigger placement="inline" />
            <a className="course-shell__profile" href={routeHref(routes.profile)}>
              <MaterialIcon name="person" />
              <span>个人中心</span>
            </a>
            <button
              type="button"
              className="course-shell__mobile-menu"
              aria-label={mobileMenuOpen ? "关闭课程工作栏" : "打开课程工作栏"}
              aria-expanded={mobileMenuOpen}
              onClick={() => {
                setMobileMenuOpen((open) => !open);
                setCourseMenuOpen(false);
              }}
            ><MaterialIcon name={mobileMenuOpen ? "close" : "menu_book"} /></button>
          </div>
        </header>

        {mobileMenuOpen ? (
          <div className="course-shell__mobile-panel">
            {renderNavigation("mobile")}
          </div>
        ) : null}

        <h1 className="sr-only">{pageTitle}</h1>
        <div className="course-shell__page">{content}</div>
      </div>
    </UnifiedCourseShellProvider>
  );
}
