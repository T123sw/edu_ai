import { useEffect, useMemo, useState } from "react";

import { useJobStore } from "../../../jobs/jobStore";
import { isActiveJob } from "../../../jobs/types";
import {
  backendCourseToSummary,
  getCourseMaterials,
  getKnowledgeBaseDocuments,
  joinCourseByCode,
  listCourses,
} from "../../api/courses";
import { getLearningOverview } from "../../api/learning";
import type { BackendCourse } from "../../api/types";
import { MaterialIcon, useAppShell } from "../../shared";
import { isCompleteCourseCode, normalizeCourseCodeInput } from "../../course/courseEnrollment";
import {
  toCourseCardPresentation,
  type CourseCardFacts,
} from "../../pages/courseCardPresentation";
import { buildStudentHash } from "../routes/studentRoutes";
import { loadRecentLearning, saveRecentLearningVisit, serializeRecentLearning, STUDENT_RECENT_LEARNING_KEY } from "./studentRecentLearning";
import "../../pages/HomeDashboard.css";
import "../styles/studentHome.css";

const emptyFacts: CourseCardFacts = {
  documentCount: 0,
  resourceCount: 0,
  activeJobCount: 0,
  learningOverview: null,
};

function formatUpdatedAt(value?: string | null): string {
  if (!value) return "课程内容可用";
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return "课程内容可用";
  return `更新于 ${new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "short", day: "numeric" }).format(timestamp)}`;
}

export function StudentHomePage() {
  const { setSelectedCourse } = useAppShell();
  const jobs = useJobStore((state) => state.jobs);
  const [courses, setCourses] = useState<BackendCourse[]>([]);
  const [facts, setFacts] = useState<Record<string, CourseCardFacts>>({});
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadVersion, setLoadVersion] = useState(0);
  const [courseCode, setCourseCode] = useState("");
  const [joining, setJoining] = useState(false);
  const [joinFeedback, setJoinFeedback] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const result = await listCourses();
        if (cancelled) return;
        setCourses(result);
        const validRecent = loadRecentLearning(result.map((course) => course.id));
        window.localStorage.setItem(STUDENT_RECENT_LEARNING_KEY, serializeRecentLearning(validRecent));
        const factEntries = await Promise.all(result.map(async (course) => {
          const [documents, resources, learning] = await Promise.all([
            getKnowledgeBaseDocuments(course.id, {
              aggregate: true,
              libraryType: "course",
              limit: 1000,
            }).catch(() => []),
            getCourseMaterials(course.id, { space: "course" }).catch(() => []),
            getLearningOverview(course.id).catch(() => null),
          ]);
          return [course.id, {
            documentCount: documents.length,
            resourceCount: resources.length,
            activeJobCount: 0,
            learningOverview: learning,
          }] as const;
        }));
        if (!cancelled) setFacts(Object.fromEntries(factEntries));
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "课程列表加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => { cancelled = true; };
  }, [loadVersion]);

  const visibleCourses = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return courses;
    return courses.filter((course) => `${course.title} ${course.description}`.toLocaleLowerCase().includes(normalized));
  }, [courses, query]);

  const recentCourse = useMemo(() => {
    const byId = new Map(courses.map((course) => [course.id, course]));
    const record = loadRecentLearning(courses.map((course) => course.id))[0];
    if (!record) return null;
    const course = byId.get(record.courseId);
    return course ? { record, course } : null;
  }, [courses]);

  function enterCourse(course: BackendCourse, index: number, route: "student-course-detail" | "student-ai" | "student-course-knowledge" | "student-classroom" | "student-resources" = "student-course-detail") {
    saveRecentLearningVisit(course.id, route);
    setSelectedCourse(backendCourseToSummary(course, index));
  }

  function cardFacts(courseId: string): CourseCardFacts {
    const activeJobCount = Object.values(jobs).filter(
      (job) => job.course_id === courseId && isActiveJob(job),
    ).length;
    return { ...(facts[courseId] ?? emptyFacts), activeJobCount };
  }

  async function handleJoinCourse() {
    if (!isCompleteCourseCode(courseCode)) {
      setJoinFeedback("请输入教师提供的 8 位课程码。");
      return;
    }
    setJoining(true);
    setJoinFeedback(null);
    try {
      const joined = await joinCourseByCode(courseCode);
      setCourses((current) => current.some((course) => course.id === joined.id) ? current : [joined, ...current]);
      setCourseCode("");
      setJoinFeedback(`已加入课程“${joined.title}”。`);
      setLoadVersion((value) => value + 1);
    } catch (reason) {
      setJoinFeedback(reason instanceof Error ? reason.message : "暂时无法加入课程，请稍后重试。");
    } finally {
      setJoining(false);
    }
  }

  return (
    <div className="student-home">
      <section className="teacher-home__intro student-home__intro">
        <div>
          <p className="teacher-home__eyebrow">学生课程工作台</p>
          <h1>选择课程，继续学习</h1>
          <p>查看课程知识、继续 AI 问答，个人上传和生成内容默认仅自己可见。</p>
        </div>
        <label className="teacher-home__search">
          <MaterialIcon name="search" />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索课程名称或简介" />
        </label>
      </section>

      <section className="student-home__section rounded-[28px] border border-blue-100 bg-white p-6 shadow-sm" aria-labelledby="join-course-title">
        <div className="grid items-end gap-4 md:grid-cols-[1fr_minmax(260px,420px)]">
          <div>
            <p className="teacher-home__eyebrow">加入新课程</p>
            <h2 id="join-course-title" className="mt-1 text-2xl font-bold">输入教师提供的课程码</h2>
            <p className="mt-2 text-sm text-(--muted-text)">加入后，课程知识图谱、学习资料与教师发布的资源会出现在你的课程空间中。</p>
          </div>
          <div>
            <div className="flex gap-2">
              <input
                value={courseCode}
                onChange={(event) => setCourseCode(normalizeCourseCodeInput(event.target.value))}
                onKeyDown={(event) => { if (event.key === "Enter") void handleJoinCourse(); }}
                className="min-w-0 flex-1 rounded-xl border border-blue-200 px-4 py-3 font-mono text-lg tracking-[0.16em] uppercase outline-none focus:border-blue-500"
                placeholder="例如 ABCD2345"
                aria-label="课程码"
                maxLength={8}
              />
              <button type="button" disabled={joining || !isCompleteCourseCode(courseCode)} onClick={() => void handleJoinCourse()} className="rounded-xl bg-blue-600 px-5 py-3 font-bold text-white disabled:opacity-50">
                {joining ? "加入中…" : "加入课程"}
              </button>
            </div>
            {joinFeedback ? <p className="mt-2 text-sm text-(--muted-text)" role="status">{joinFeedback}</p> : null}
          </div>
        </div>
      </section>

      {recentCourse && !query ? (
        <section className="student-home__section" aria-labelledby="recent-learning-title">
          <div className="student-home__section-head"><div><h2 id="recent-learning-title">最近学习</h2><p>回到上次使用的课程功能</p></div></div>
          <div className="student-home__recent-list">
            <a href={buildStudentHash(recentCourse.record.lastRoute, { courseId: recentCourse.course.id })} onClick={() => enterCourse(recentCourse.course, courses.findIndex((course) => course.id === recentCourse.course.id), recentCourse.record.lastRoute as "student-course-detail" | "student-ai" | "student-course-knowledge" | "student-classroom" | "student-resources")}>
              <span className="student-home__recent-icon"><MaterialIcon name="menu_book" /></span>
              <span><strong>{recentCourse.course.title}</strong><small>{formatUpdatedAt(recentCourse.record.visitedAt)}</small></span>
              <MaterialIcon name="arrow_forward" />
            </a>
          </div>
        </section>
      ) : null}

      <section className="student-home__section" aria-labelledby="my-courses-title">
        <div className="teacher-home__section-head"><div><h2 id="my-courses-title">我的课程</h2><p>{courses.length > 0 ? `${courses.length} 门已加入课程` : "查看已加入的课程"}</p></div></div>
        {loading ? <div className="teacher-home__state">正在加载课程…</div> : null}
        {error ? <div className="teacher-home__state is-error"><p>{error}</p><button type="button" onClick={() => setLoadVersion((value) => value + 1)}>重新加载</button></div> : null}
        {!loading && !error && courses.length === 0 ? <div className="teacher-home__state"><h3>暂未加入课程</h3><p>加入课程后，会在这里显示可学习的真实课程内容。</p></div> : null}
        {!loading && !error && courses.length > 0 && visibleCourses.length === 0 ? <div className="teacher-home__state">没有找到匹配的课程。</div> : null}
        <div className="teacher-course-grid">
          {visibleCourses.map((course, index) => {
            const card = toCourseCardPresentation(course, cardFacts(course.id), "student");
            return (
              <a
                key={course.id}
                className="teacher-course-card"
                href={buildStudentHash("student-course-detail", { courseId: course.id })}
                aria-label={course.title}
                onClick={() => enterCourse(course, index)}
              >
                <h3>{card.title}</h3>
                <p className="teacher-course-card__description">{card.description}</p>
                <dl className="teacher-course-card__metrics">
                  {card.metrics.map((metric) => <div key={metric.label}><dt>{metric.label}</dt><dd>{metric.value}</dd></div>)}
                </dl>
                {card.learningStatusLabel ? <p className="teacher-course-card__learning-status">{card.learningStatusLabel}</p> : null}
                <div className="teacher-course-card__footer">
                  <span>{card.updatedLabel}</span>
                  <strong>进入学习 <MaterialIcon name="arrow_forward" /></strong>
                </div>
              </a>
            );
          })}
        </div>
      </section>
    </div>
  );
}
