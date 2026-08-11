import { useEffect, useMemo, useState } from "react";

import { useJobStore } from "../../jobs/jobStore";
import { isActiveJob } from "../../jobs/types";
import {
  backendCourseToSummary,
  getCourseMaterials,
  getKnowledgeBaseDocuments,
  listCourses,
} from "../api/courses";
import { getLearningOverview } from "../api/learning";
import type { BackendCourse } from "../api/types";
import { useAuthSession } from "../authSession";
import { CourseCreateDialog } from "../course/CourseCreateDialog";
import { AppSurface, MaterialIcon, routeHref, routes, useAppShell } from "../shared";
import { buildTeacherCourseHash } from "../teacherRoutes";
import { toCourseCardPresentation, type CourseCardFacts } from "./courseCardPresentation";
import "./HomeDashboard.css";

const emptyFacts: CourseCardFacts = {
  documentCount: 0,
  resourceCount: 0,
  activeJobCount: 0,
  learningOverview: null,
};

function getStoredUsername() {
  try {
    const raw = window.localStorage.getItem("edu-ai-auth");
    const parsed = raw ? JSON.parse(raw) as { user?: { username?: string } } : null;
    return parsed?.user?.username?.trim() || "教师";
  } catch {
    return "教师";
  }
}

export function HomeDashboardPage() {
  const { user } = useAuthSession();
  const { setSelectedCourse } = useAppShell();
  const jobs = useJobStore((state) => state.jobs);
  const [courses, setCourses] = useState<BackendCourse[]>([]);
  const [facts, setFacts] = useState<Record<string, CourseCardFacts>>({});
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const username = useMemo(getStoredUsername, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const loaded = await listCourses();
        if (cancelled) return;
        setCourses(loaded);
        const entries = await Promise.all(loaded.map(async (course) => {
          const [documents, resources, learning] = await Promise.all([
            getKnowledgeBaseDocuments(course.id, {
              aggregate: true,
              libraryType: "course",
              limit: 1000,
            }).catch(() => []),
            getCourseMaterials(course.id).catch(() => []),
            getLearningOverview(course.id).catch(() => null),
          ]);
          return [course.id, {
            documentCount: documents.length,
            resourceCount: resources.length,
            activeJobCount: 0,
            learningOverview: learning,
          }] as const;
        }));
        if (!cancelled) setFacts(Object.fromEntries(entries));
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "课程列表加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  const visibleCourses = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return normalized
      ? courses.filter((course) => `${course.title} ${course.description}`.toLocaleLowerCase().includes(normalized))
      : courses;
  }, [courses, query]);

  function cardFacts(courseId: string): CourseCardFacts {
    const activeJobCount = Object.values(jobs).filter((job) => job.course_id === courseId && isActiveJob(job)).length;
    return { ...(facts[courseId] ?? emptyFacts), activeJobCount };
  }

  function courseCreated(course: BackendCourse) {
    const courseIndex = courses.length;
    setCourses((current) => [...current, course]);
    setSelectedCourse(backendCourseToSummary(course, courseIndex));
    setCreateOpen(false);
    window.location.hash = buildTeacherCourseHash("course-detail", course.id);
  }

  return (
    <AppSurface className="teacher-home">
      <header className="teacher-home__topbar">
        <a href={routeHref(routes.home)} className="teacher-home__brand">Edu AI</a>
        <a href={routeHref(routes.profile)} className="teacher-home__account">
          <span>{username.slice(0, 1).toUpperCase()}</span>
          <strong>{username}</strong>
        </a>
      </header>

      <main className="teacher-home__main">
        <section className="teacher-home__intro">
          <div>
            <p className="teacher-home__eyebrow">教师课程工作台</p>
            <h1>选择课程，继续今天的教学工作</h1>
          </div>
          <div className="teacher-home__actions">
            {user?.role !== "student" ? (
              <button type="button" className="teacher-home__create" onClick={() => setCreateOpen(true)}>
                <MaterialIcon name="add" /> 创建课程
              </button>
            ) : null}
            <label className="teacher-home__search">
              <MaterialIcon name="search" />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索课程名称或简介" />
            </label>
          </div>
        </section>

        <section aria-labelledby="course-grid-title">
          <div className="teacher-home__section-head">
            <div><h2 id="course-grid-title">全部课程</h2><p>{courses.length} 门可访问课程</p></div>
          </div>

          {loading ? <div className="teacher-home__state">正在加载课程…</div> : null}
          {error ? <div className="teacher-home__state is-error">{error}</div> : null}
          {!loading && !error && visibleCourses.length === 0 ? (
            courses.length === 0 && user?.role !== "student" ? (
              <div className="teacher-home__state teacher-home__empty">
                <span><MaterialIcon name="menu_book" /></span>
                <h3>创建第一门课程</h3>
                <p>填写课程目标和教学对象，随后可以一键规划并构建课程知识库。</p>
                <button type="button" onClick={() => setCreateOpen(true)}>创建第一门课程</button>
              </div>
            ) : <div className="teacher-home__state">没有找到匹配的课程。</div>
          ) : null}

          <div className="teacher-course-grid">
            {visibleCourses.map((course, index) => {
              const card = toCourseCardPresentation(course, cardFacts(course.id), "teacher");
              return (
                <a
                  key={course.id}
                  className="teacher-course-card"
                  href={buildTeacherCourseHash("course-detail", course.id)}
                  aria-label={course.title}
                  onClick={() => setSelectedCourse(backendCourseToSummary(course, index))}
                >
                  <h3>{card.title}</h3>
                  <p className="teacher-course-card__description">{card.description}</p>
                  <dl className="teacher-course-card__metrics">
                    {card.metrics.map((metric) => <div key={metric.label}><dt>{metric.label}</dt><dd>{metric.value}</dd></div>)}
                  </dl>
                  {card.learningStatusLabel ? <p className="teacher-course-card__learning-status">{card.learningStatusLabel}</p> : null}
                  <div className="teacher-course-card__footer">
                    <span>{card.updatedLabel}</span>
                    <strong>进入课程 <MaterialIcon name="arrow_forward" /></strong>
                  </div>
                </a>
              );
            })}
          </div>
        </section>
      </main>
      <CourseCreateDialog open={createOpen} onClose={() => setCreateOpen(false)} onCreated={courseCreated} />
    </AppSurface>
  );
}
