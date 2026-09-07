import { useCourseRoute } from "../course/CourseRouteProvider";
import { useAuthSession } from "../authSession";
import { AppSurface, MaterialIcon, routes } from "../shared";
import { buildRoleCourseHash } from "../shared/routes/roleCourseRouteResolver";
import { HomeDashboardPage } from "./HomeDashboard";
import { useCoursePreparation } from "./useCoursePreparation";
import { resumeHash } from "../resume/resumeRecord";
import { getCourseMaterialTypeMeta } from "../api/courseMaterialPresentation";
import "./CourseDetail.css";

export function CourseListPage() {
  return <HomeDashboardPage />;
}

function SectionIcon({ kind }: { kind: 'intro' | 'goals' | 'location' | 'material' }) {
  const paths = {
    intro: 'M5 4h14v16H5zM8 8h8M8 12h8M8 16h5',
    goals: 'M20 12a8 8 0 1 1-8-8m4 1 3-3v3h3l-3 3-3-3Zm0 0-4 7m4 0a4 4 0 1 1-4-4',
    location: 'M18 9c0 5-6 11-6 11S6 14 6 9a6 6 0 1 1 12 0ZM12 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4Z',
    material: 'M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6',
  };
  return <span className="course-overview__section-icon" aria-hidden="true"><svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={paths[kind]} /></svg></span>;
}

export function CourseDetailPage() {
  const { user } = useAuthSession();
  const { course } = useCourseRoute();
  const history = useCoursePreparation(user, course?.id);
  if (!course) return <AppSurface><main /></AppSurface>;
  const objectives = course.objectives?.filter((objective) => objective.trim()) ?? [];
  const previous = history.location?.status === 'valid' ? history.location : null;
  const workspaceHref = previous && user ? resumeHash(user, previous.record) : buildRoleCourseHash(user?.role, routes.ai, course.id);
  const locationText = history.loading ? '正在读取上次位置…'
    : previous ? previous.label || '课程工作台'
    : history.location?.status === 'retry' ? '暂时无法读取上次位置'
    : history.location?.status === 'fallback' || history.location?.status === 'invalid' ? '上次位置已不可用'
    : '尚无备课位置记录';

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
          </header>
          <section className="course-overview__introduction" aria-labelledby="course-introduction-title">
            <h2 id="course-introduction-title"><SectionIcon kind="intro" />课程简介</h2>
            <p>{course.description?.trim() || "暂未填写课程简介。"}</p>
          </section>
          {objectives.length ? <section className="course-overview__goals" aria-labelledby="course-objectives-title">
            <h2 id="course-objectives-title"><SectionIcon kind="goals" />教学目标</h2>
            <ol>{objectives.map((objective, index) => <li key={`${index}-${objective}`}>
              <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
              <p>{objective}</p>
            </li>)}</ol>
          </section> : null}
            <div className="course-overview__history" aria-busy={history.loading}>
              <section aria-labelledby="preparation-location-title">
                <h2 id="preparation-location-title"><SectionIcon kind="location" />上次{user?.role === 'student' ? '学习' : '备课'}位置</h2>
                <strong className={previous ? undefined : 'is-empty'}>{locationText}</strong>
                {previous ? <small>{new Date(previous.record.visitedAt).toLocaleString('zh-CN', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })}</small> : null}
              </section>
              <section aria-labelledby="recent-material-title">
                <h2 id="recent-material-title"><SectionIcon kind="material" />最近资料</h2>
                <strong className={history.material ? undefined : 'is-empty'}>{history.loading ? '正在读取最近资料…' : history.materialFailed ? '暂时无法读取资料' : history.material?.title || history.material?.topic || (history.material ? '未命名资料' : '还没有生成资料')}</strong>
                {history.material ? <small>{getCourseMaterialTypeMeta(history.material.material_type).label}{history.material.updated_at && Number.isFinite(Date.parse(history.material.updated_at)) ? ` · 更新于 ${new Date(history.material.updated_at).toLocaleDateString('zh-CN')}` : ''}</small> : null}
              </section>
            </div>
          <footer className="course-overview__continuation">
            <a className="course-overview__primary" href={workspaceHref}>
              {user?.role === "student" ? "开始学习" : "开始备课"}<MaterialIcon name="arrow_forward" />
            </a>
          </footer>
        </article>
      </main>
    </AppSurface>
  );
}
