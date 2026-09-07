import { useCourseRoute } from "../course/CourseRouteProvider";
import { useAuthSession } from "../authSession";
import { AppSurface, MaterialIcon, routes } from "../shared";
import { buildRoleCourseHash } from "../shared/routes/roleCourseRouteResolver";
import { HomeDashboardPage } from "./HomeDashboard";
import "./CourseDetail.css";

export function CourseListPage() {
  return <HomeDashboardPage />;
}

export function CourseDetailPage() {
  const { user } = useAuthSession();
  const { course } = useCourseRoute();
  if (!course) return <AppSurface><main /></AppSurface>;
  const objectives = course.objectives?.filter((objective) => objective.trim()) ?? [];

  return (
    <AppSurface className="min-h-screen">
      <main className="course-overview">
        <article className="course-overview__sheet" aria-labelledby="course-title">
          <header className="course-overview__header">
            <div className="course-overview__identity">
              <span className="course-overview__mark" aria-hidden="true">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 5C9 3 5 3 3 4v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-2-1-6-1-9 1Zm0 0v15M6 8h3m-3 4h3m6-4h3m-3 4h3" />
                </svg>
              </span>
              <div>
                <h1 id="course-title">{course.title}</h1>
                {course.audience ? <p className="course-overview__audience">适用对象 · {course.audience}</p> : null}
              </div>
            </div>
            <a className="course-overview__primary" href={buildRoleCourseHash(user?.role, routes.ai, course.id)}>
              {user?.role === "student" ? "开始学习" : "开始备课"}<MaterialIcon name="arrow_forward" />
            </a>
          </header>
          <section className="course-overview__introduction" aria-labelledby="course-introduction-title">
            <h2 id="course-introduction-title">课程简介</h2>
            <p>{course.description?.trim() || "暂未填写课程简介。"}</p>
          </section>
          {objectives.length ? <section className="course-overview__goals" aria-labelledby="course-objectives-title">
            <h2 id="course-objectives-title">教学目标</h2>
            <ol>{objectives.map((objective, index) => <li key={`${index}-${objective}`}>
              <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
              <p>{objective}</p>
            </li>)}</ol>
          </section> : null}
        </article>
      </main>
    </AppSurface>
  );
}
