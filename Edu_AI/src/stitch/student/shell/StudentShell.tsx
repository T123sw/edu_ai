import { useEffect, useMemo, useState, type PropsWithChildren } from "react";

import { JobCenterTrigger } from "../../../jobs/JobCenterDrawer";
import { listCourses } from "../../api/courses";
import type { BackendCourse } from "../../api/types";
import { useAuthSession } from "../../authSession";
import { MaterialIcon, cx, useAppShell } from "../../shared";
import { useCourseRoute } from "../../course/CourseRouteProvider";
import { buildStudentHash, readStudentLocation, type StudentRoute } from "../routes/studentRoutes";
import { studentNavigationItems, studentRouteRequiresCourse } from "./studentNavigation";
import "../styles/studentShell.css";

const pageTitles: Record<StudentRoute, string> = {
  "student-home": "学习首页",
  "student-ai": "AI问答",
  "student-course-knowledge": "课程知识",
  "student-personal-knowledge": "个人知识库",
  "student-classroom": "AI课堂",
  "student-resources": "资源管理",
};

export function StudentShell({ activeRoute, children }: PropsWithChildren<{ activeRoute: StudentRoute }>) {
  const { user } = useAuthSession();
  const { logout } = useAppShell();
  const { courseId, course, loading: courseLoading, error: courseError, reload } = useCourseRoute();
  const [courses, setCourses] = useState<BackendCourse[]>([]);
  const [coursesLoading, setCoursesLoading] = useState(true);
  const [coursesError, setCoursesError] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const location = useMemo(() => readStudentLocation(window.location.hash), []);
  const requiresCourse = studentRouteRequiresCourse(activeRoute);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setCoursesLoading(true);
      setCoursesError(null);
      try {
        const result = await listCourses();
        if (!cancelled) setCourses(result);
      } catch (reason) {
        if (!cancelled) setCoursesError(reason instanceof Error ? reason.message : "课程列表加载失败");
      } finally {
        if (!cancelled) setCoursesLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => setDrawerOpen(false), [activeRoute]);

  function hrefFor(route: StudentRoute) {
    const target = studentNavigationItems.find((item) => item.route === route);
    return buildStudentHash(route, {
      courseId: target?.requiresCourse ? courseId : undefined,
      view: route === "student-course-knowledge" ? "structure" : undefined,
      space: route === "student-resources" || route === "student-classroom" ? "mine" : undefined,
    });
  }

  function changeCourse(nextCourseId: string) {
    window.location.hash = buildStudentHash(activeRoute, {
      courseId: nextCourseId,
      view: location.view,
      space: location.space,
    });
  }

  const navigation = (
    <nav className="student-shell__nav" aria-label="学生工作区">
      {studentNavigationItems.map((item) => (
        <a
          key={item.route}
          href={hrefFor(item.route)}
          className={cx("student-shell__nav-link", activeRoute === item.route && "is-active")}
          aria-current={activeRoute === item.route ? "page" : undefined}
          onClick={() => setDrawerOpen(false)}
        >
          <MaterialIcon name={item.icon} />
          <span>{item.label}</span>
        </a>
      ))}
    </nav>
  );

  let content = children;
  if (requiresCourse && (!courseId || (!course && !courseLoading))) {
    content = (
      <section className="student-shell__empty" aria-live="polite">
        <MaterialIcon name="school" />
        <h2>请选择课程</h2>
        <p>选择一门已加入的课程后，即可使用本页的学习内容。</p>
        {coursesError ? <p className="student-shell__error">{coursesError}</p> : null}
        <select
          aria-label="选择课程"
          value=""
          disabled={coursesLoading || courses.length === 0}
          onChange={(event) => changeCourse(event.target.value)}
        >
          <option value="">{coursesLoading ? "正在加载课程…" : "选择一门课程"}</option>
          {courses.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
        </select>
      </section>
    );
  } else if (requiresCourse && courseError) {
    content = (
      <section className="student-shell__empty">
        <h2>课程加载失败</h2>
        <p>{courseError.message}</p>
        <button type="button" onClick={() => void reload()}>重新加载</button>
      </section>
    );
  } else if (requiresCourse && courseLoading && !course) {
    content = <div className="student-shell__loading">正在加载课程…</div>;
  }

  return (
    <div className="student-shell" data-testid="student-shell">
      <aside className="student-shell__sidebar">
        <a className="student-shell__brand" href="#student-home"><span>Edu</span> AI</a>
        <div className="student-shell__identity">
          <span>{user?.username.slice(0, 1).toUpperCase()}</span>
          <div><strong>{user?.username}</strong><small>学生工作区</small></div>
        </div>
        {navigation}
        <button type="button" className="student-shell__profile-link" onClick={logout}>
          <MaterialIcon name="logout" />退出登录
        </button>
      </aside>

      <div className="student-shell__main">
        <header className="student-shell__header">
          <button type="button" className="student-shell__menu" aria-label="打开导航" onClick={() => setDrawerOpen(true)}>
            <MaterialIcon name="menu_book" />
          </button>
          <div className="student-shell__title"><small>学生学习空间</small><h1>{pageTitles[activeRoute]}</h1></div>
          <div className="student-shell__header-actions">
            {requiresCourse ? (
              <label className="student-shell__course-select">
                <span>当前课程</span>
                <select
                  aria-label="当前课程"
                  value={courseId ?? ""}
                  disabled={coursesLoading}
                  onChange={(event) => changeCourse(event.target.value)}
                >
                  <option value="">请选择课程</option>
                  {courses.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
                </select>
              </label>
            ) : null}
            <JobCenterTrigger placement="inline" />
          </div>
        </header>
        <main className="student-shell__page" data-route-scroll-root>{content}</main>
      </div>

      {drawerOpen ? (
        <div className="student-shell__drawer-layer">
          <button className="student-shell__backdrop" aria-label="关闭导航" onClick={() => setDrawerOpen(false)} />
          <aside className="student-shell__drawer">
            <div className="student-shell__drawer-head"><strong>学生工作区</strong><button aria-label="关闭导航" onClick={() => setDrawerOpen(false)}><MaterialIcon name="close" /></button></div>
            {navigation}
          </aside>
        </div>
      ) : null}
    </div>
  );
}
