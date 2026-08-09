import { useEffect, useMemo, useState } from "react";

import { backendCourseToSummary, listCourses } from "../../api/courses";
import type { BackendCourse } from "../../api/types";
import { MaterialIcon, useAppShell } from "../../shared";
import { buildStudentHash } from "../routes/studentRoutes";
import { loadRecentLearning, saveRecentLearningVisit, serializeRecentLearning, STUDENT_RECENT_LEARNING_KEY } from "./studentRecentLearning";
import "../styles/studentHome.css";

function formatUpdatedAt(value?: string | null): string {
  if (!value) return "课程内容可用";
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return "课程内容可用";
  return `更新于 ${new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "short", day: "numeric" }).format(timestamp)}`;
}

export function StudentHomePage() {
  const { setSelectedCourse } = useAppShell();
  const [courses, setCourses] = useState<BackendCourse[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadVersion, setLoadVersion] = useState(0);

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

  const recentCourses = useMemo(() => {
    const byId = new Map(courses.map((course) => [course.id, course]));
    return loadRecentLearning(courses.map((course) => course.id))
      .map((record) => ({ record, course: byId.get(record.courseId) }))
      .filter((item): item is { record: typeof item.record; course: BackendCourse } => Boolean(item.course));
  }, [courses]);

  function enterCourse(course: BackendCourse, index: number, route: "student-ai" | "student-course-knowledge" | "student-classroom" | "student-resources" = "student-ai") {
    saveRecentLearningVisit(course.id, route);
    setSelectedCourse(backendCourseToSummary(course, index));
  }

  return (
    <div className="student-home">
      <section className="student-home__hero">
        <div><p>继续你的课程学习</p><h2>从问题出发，连接课程知识与个人资料</h2><span>选择课程即可进入 AI 问答；所有上传和生成内容默认仅自己可见。</span></div>
        <label className="student-home__search"><MaterialIcon name="search" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索课程名称或简介" /></label>
      </section>

      {recentCourses.length > 0 && !query ? (
        <section className="student-home__section" aria-labelledby="recent-learning-title">
          <div className="student-home__section-head"><div><h2 id="recent-learning-title">最近学习</h2><p>回到上次使用的课程功能</p></div></div>
          <div className="student-home__recent-list">
            {recentCourses.map(({ course, record }, index) => (
              <a key={course.id} href={buildStudentHash(record.lastRoute, { courseId: course.id })} onClick={() => enterCourse(course, index, record.lastRoute as "student-ai" | "student-course-knowledge" | "student-classroom" | "student-resources")}>
                <span className="student-home__recent-icon"><MaterialIcon name="menu_book" /></span>
                <span><strong>{course.title}</strong><small>{formatUpdatedAt(record.visitedAt)}</small></span>
                <MaterialIcon name="arrow_forward" />
              </a>
            ))}
          </div>
        </section>
      ) : null}

      <section className="student-home__section" aria-labelledby="my-courses-title">
        <div className="student-home__section-head"><div><h2 id="my-courses-title">我的课程</h2><p>{courses.length > 0 ? `${courses.length} 门已加入课程` : "查看已加入的课程"}</p></div></div>
        {loading ? <div className="student-home__state">正在加载课程…</div> : null}
        {error ? <div className="student-home__state is-error"><p>{error}</p><button type="button" onClick={() => setLoadVersion((value) => value + 1)}>重新加载</button></div> : null}
        {!loading && !error && courses.length === 0 ? <div className="student-home__state"><h3>暂未加入课程</h3><p>加入课程后，会在这里显示可学习的真实课程内容。</p></div> : null}
        {!loading && !error && courses.length > 0 && visibleCourses.length === 0 ? <div className="student-home__state">没有找到匹配的课程。</div> : null}
        <div className="student-home__grid">
          {visibleCourses.map((course, index) => (
            <a key={course.id} className="student-home__course-card" href={buildStudentHash("student-ai", { courseId: course.id })} onClick={() => enterCourse(course, index)}>
              <div className="student-home__course-top"><span>{course.icon || "课程"}</span><small>可学习</small></div>
              <h3>{course.title}</h3>
              <p>{course.description || "教师尚未添加课程简介。"}</p>
              <footer><span>{formatUpdatedAt(course.updated_at)}</span><strong>进入学习 <MaterialIcon name="arrow_forward" /></strong></footer>
            </a>
          ))}
        </div>
      </section>
    </div>
  );
}
