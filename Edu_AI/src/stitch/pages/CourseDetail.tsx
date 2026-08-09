import { useEffect, useMemo, useState } from "react";

import { useJobStore } from "../../jobs/jobStore";
import { isActiveJob } from "../../jobs/types";
import { getCourseMaterialTypeMeta } from "../api/courseMaterialPresentation";
import { getCourseMaterials, getKnowledgeBaseDocuments } from "../api/courses";
import type { CourseMaterial, KnowledgeBaseDocument } from "../api/types";
import { useCourseRoute } from "../course/CourseRouteProvider";
import { canCourse } from "../course/coursePermissions";
import { useAuthSession } from "../authSession";
import { AppSurface, GlassPanel, MaterialIcon, routes } from "../shared";
import { buildRoleCourseHash } from "../shared/routes/roleCourseRouteResolver";
import { HomeDashboardPage } from "./HomeDashboard";

export function CourseListPage() {
  return <HomeDashboardPage />;
}

const entries = [
  { route: routes.ai, label: "问答与生成", note: "围绕课程资料问答或生成教学资源", icon: "auto_awesome" },
  { route: routes.knowledge, label: "课程知识", note: "管理课程资料和知识结构", icon: "menu_book" },
  { route: routes.classroomStudio, label: "AI 课堂", note: "生成和播放互动课堂", icon: "play_circle" },
  { route: routes.resources, label: "课程资源", note: "查看课程内已发布成果", icon: "folder_open" },
  { route: routes.edit, label: "课程设置", note: "维护课程介绍与教学目标", icon: "settings" },
] as const;

function materialTitle(material: CourseMaterial) {
  return material.title || material.topic || "未命名资源";
}

export function CourseDetailPage() {
  const { user } = useAuthSession();
  const { course, courseRole } = useCourseRoute();
  const jobs = useJobStore((state) => state.jobs);
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);

  useEffect(() => {
    if (!course) return;
    let cancelled = false;
    void Promise.all([
      getKnowledgeBaseDocuments(course.id, {
        aggregate: true,
        libraryType: "course",
        limit: 1000,
      }).catch(() => []),
      getCourseMaterials(course.id, { sort: "updated_desc" }).catch(() => []),
    ]).then(([nextDocuments, nextMaterials]) => {
      if (!cancelled) {
        setDocuments(nextDocuments);
        setMaterials(nextMaterials);
      }
    });
    return () => { cancelled = true; };
  }, [course]);

  const activeJobs = useMemo(
    () => Object.values(jobs).filter((job) => job.course_id === course?.id && isActiveJob(job)),
    [course?.id, jobs],
  );
  const completedJobs = useMemo(
    () => Object.values(jobs).filter(
      (job) => job.course_id === course?.id && job.status === "succeeded",
    ),
    [course?.id, jobs],
  );
  const failedJobs = useMemo(
    () => Object.values(jobs).filter(
      (job) =>
        job.course_id === course?.id
        && (job.status === "failed" || job.status === "partially_succeeded"),
    ),
    [course?.id, jobs],
  );
  const readyDocuments = documents.filter((document) => document.status === "ready").length;
  const visibleEntries = entries.filter((entry) => entry.route !== routes.edit || canCourse(courseRole, "edit"));

  if (!course) return <AppSurface><main /></AppSurface>;

  return (
    <AppSurface className="min-h-screen">
      <main className="course-overview">
        <section className="course-overview__summary">
          <div>
            <h2>{course.title}</h2>
            <p>{course.description || "暂未填写课程简介。"}</p>
          </div>
          <a className="course-overview__primary" href={buildRoleCourseHash(user?.role, routes.ai, course.id)}>
            {user?.role === "student" ? "开始AI问答" : "开始问答或生成"} <MaterialIcon name="arrow_forward" />
          </a>
        </section>

        <section className="course-overview__facts" aria-label="课程状态">
          <article><span>课程资料</span><strong>{documents.length}</strong><small>{readyDocuments} 份可用于检索</small></article>
          <article><span>课程资源</span><strong>{materials.length}</strong><small>最近生成与发布成果</small></article>
          <article><span>已完成任务</span><strong>{completedJobs.length}</strong><small>已成功生成资源</small></article>
          <article><span>进行中任务</span><strong>{activeJobs.length}</strong><small>可在右上角任务中心查看</small></article>
          <article><span>失败任务</span><strong>{failedJobs.length}</strong><small>可在任务中心重试</small></article>
        </section>

        <div className="course-overview__columns">
          <GlassPanel className="course-overview__panel">
            <div className="course-overview__panel-head"><div><p>教学方向</p><h3>课程目标</h3></div></div>
            {course.objectives?.length ? (
              <ol className="course-overview__objectives">{course.objectives.map((objective, index) => <li key={`${index}-${objective}`}><span>{index + 1}</span>{objective}</li>)}</ol>
            ) : <p className="course-overview__empty">尚未设置教学目标，可在课程设置中补充。</p>}
          </GlassPanel>

          <GlassPanel className="course-overview__panel">
            <div className="course-overview__panel-head"><div><p>最近更新</p><h3>最新课程资源</h3></div><a href={buildRoleCourseHash(user?.role, routes.resources, course.id)}>查看全部</a></div>
            {materials.length ? <ul className="course-overview__resources">{materials.slice(0, 4).map((material) => <li key={`${material.material_type}-${material.material_id}`}><a href={buildRoleCourseHash(user?.role, routes.resources, course.id, { material_type: material.material_type, material_id: material.material_id })}><span><strong>{materialTitle(material)}</strong><small>{getCourseMaterialTypeMeta(material.material_type).label}</small></span><MaterialIcon name="arrow_forward" /></a></li>)}</ul> : <p className="course-overview__empty">暂无生成资源，从问答与生成开始创建。</p>}
          </GlassPanel>
        </div>

        <section className="course-overview__entries" aria-labelledby="quick-entry-title">
          <div className="course-overview__section-title"><p>课程工作区</p><h3 id="quick-entry-title">常用入口</h3></div>
          <div>{visibleEntries.map((entry) => <a key={entry.route} href={buildRoleCourseHash(user?.role, entry.route, course.id)}><span><MaterialIcon name={entry.icon} /></span><strong>{user?.role === "student" && entry.route === routes.ai ? "AI问答" : user?.role === "student" && entry.route === routes.resources ? "资源管理" : entry.label}</strong><small>{entry.note}</small></a>)}</div>
        </section>
      </main>
    </AppSurface>
  );
}
