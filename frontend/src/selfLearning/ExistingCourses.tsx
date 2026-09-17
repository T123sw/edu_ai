import { useEffect, useState } from "react";
import { apiRequest } from "../stitch/api/client";
import type { BackendCourse } from "../stitch/api/types";
import { Cover } from "./Home";
import { Icon } from "./ui";
import { courseWorkspaceHref } from "./workspaceRoutes";

export function ExistingCourses({ role }: { role?: string }) {
  const [courses, setCourses] = useState<BackendCourse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [expanded, setExpanded] = useState(false);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    apiRequest<BackendCourse[]>("/api/courses").then((items) => {
      if (!cancelled) setCourses([...items].sort((a, b) =>
        (b.last_used_at || b.updated_at || "").localeCompare(a.last_used_at || a.updated_at || ""),
      ));
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : "课堂加载失败");
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [retry]);

  return <section aria-label="我的课堂">
    <div className="sl-section-heading">
      <h2><Icon name="book" size={18} />我的课堂 <span>{courses.length}</span></h2>
      {courses.length > 3 && <button className="sl-text-button" onClick={() => setExpanded(!expanded)}>
        {expanded ? "收起" : "查看全部"}
      </button>}
    </div>
    {loading ? <p className="sl-inline-empty" role="status">正在加载课堂…</p>
      : error ? <div className="sl-inline-empty" role="alert">{error} <button className="sl-text-button" onClick={() => setRetry(retry + 1)}>重新加载</button></div>
      : courses.length ? <div className="sl-card-grid">
        {courses.slice(0, expanded ? undefined : 3).map((course, index) => <a
          key={course.id}
          className="sl-class-card"
          href={courseWorkspaceHref(course.id, role)}
        >
          <Cover room={{ tone: ["lavender", "mint", "peach"][index % 3] }} />
          <div className="sl-card-copy">
            <h3>{course.title}</h3>
            <p>{course.description || "继续探索这门课程"}</p>
            <div className="sl-card-meta"><span>AI 课堂 · 工作台 · 资源中心</span><span>进入课堂 <Icon name="arrow" size={14} /></span></div>
          </div>
        </a>)}
      </div> : <p className="sl-inline-empty">暂无已加入的课堂。</p>}
  </section>;
}
