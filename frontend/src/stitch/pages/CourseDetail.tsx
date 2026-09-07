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
import "./CourseDetail.css";

export function CourseListPage() {
  return <HomeDashboardPage />;
}

const entries = [
  { route: routes.ai, label: "问答与生成", note: "围绕课程资料问答或生成教学资源", icon: "auto_awesome" },
  { route: routes.knowledge, label: "课程知识", note: "管理课程资料和知识结构", icon: "menu_book" },
  { route: routes.classroomStudio, label: "AI 课堂", note: "生成和播放互动课堂", icon: "play_circle" },
  { route: routes.resources, label: "个人资源", note: "管理自己生成的学习与教学内容", icon: "folder_open" },
  { route: routes.edit, label: "课程设置", note: "维护课程介绍与教学目标", icon: "settings" },
] as const;

const studentEntryNotes: Partial<Record<(typeof entries)[number]["route"], string>> = {
  [routes.ai]: "基于课程资料提问，生成内容仅自己可见",
  [routes.knowledge]: "查看按课程结构组织的课程知识库",
  [routes.classroomStudio]: "生成和学习互动课堂",
  [routes.resources]: "管理自己生成的学习内容",
};

function materialTitle(material: CourseMaterial) {
  return material.title || material.topic || "未命名资源";
}

export function CourseDetailPage() {
  const { user } = useAuthSession();
  const { course, courseRole } = useCourseRoute();
  const jobs = useJobStore((state) => state.jobs);
  const [documents, setDocuments] = useState<KnowledgeBaseDocument[]>([]);
  const [materials, setMaterials] = useState<CourseMaterial[]>([]);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [setupDismissed, setSetupDismissed] = useState(false);
  const [descriptionExpanded, setDescriptionExpanded] = useState(false);

  useEffect(() => {
    if (!course) return;
    let cancelled = false;
    setOverviewLoading(true);
    setDescriptionExpanded(false);
    try {
      setSetupDismissed(window.localStorage.getItem(`edu-ai-course-setup-dismissed:${course.id}`) === "true");
    } catch {
      setSetupDismissed(false);
    }
    void Promise.all([
      getKnowledgeBaseDocuments(course.id, {
        aggregate: true,
        libraryType: "course",
        limit: 1000,
      }).catch(() => []),
      getCourseMaterials(course.id, { space: "mine", sort: "updated_desc" }).catch(() => []),
    ]).then(([nextDocuments, nextMaterials]) => {
      if (!cancelled) {
        setDocuments(nextDocuments);
        setMaterials(nextMaterials);
        setOverviewLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [course]);

  const activeJobs = useMemo(
    () => Object.values(jobs).filter((job) => job.course_id === course?.id && isActiveJob(job)),
    [course?.id, jobs],
  );
  const readyDocuments = documents.filter((document) => document.status === "ready").length;
  const visibleEntries = entries.filter((entry) => entry.route !== routes.edit || canCourse(courseRole, "edit"));
  const showSetup = !overviewLoading
    && canCourse(courseRole, "edit")
    && documents.length === 0
    && materials.length === 0
    && activeJobs.length === 0
    && !setupDismissed;

  function dismissSetup() {
    setSetupDismissed(true);
    try {
      window.localStorage.setItem(`edu-ai-course-setup-dismissed:${course?.id}`, "true");
    } catch {
      // A blocked local preference store must not block course use.
    }
  }

  if (!course) return <AppSurface><main /></AppSurface>;

  return (
    <AppSurface className="min-h-screen">
      <main className="course-overview">
        <section className="course-overview__hero" aria-labelledby="course-title">
          <div className="course-overview__summary">
            <span className="course-overview__eyebrow"><MaterialIcon name="menu_book" />课程概览</span>
            <h1 id="course-title">{course.title}</h1>
            <p id="course-description" className={descriptionExpanded || (course.description?.length ?? 0) <= 150 ? "is-expanded" : ""}>{course.description || "暂未填写课程简介。"}</p>
            {(course.description?.length ?? 0) > 150 ? <button type="button" className="course-overview__expand" aria-expanded={descriptionExpanded} aria-controls="course-description" onClick={() => setDescriptionExpanded((value) => !value)}>{descriptionExpanded ? "收起简介" : "展开完整简介"}<MaterialIcon name={descriptionExpanded ? "expand_less" : "expand_more"} /></button> : null}
            <a className="course-overview__primary" href={buildRoleCourseHash(user?.role, routes.ai, course.id)}>
              <MaterialIcon name="auto_awesome" />{user?.role === "student" ? "开始AI问答" : "开始问答或生成"} <MaterialIcon name="arrow_forward" />
            </a>
          </div>
          <section className="course-overview__facts" aria-label="课程状态" aria-busy={overviewLoading}>
            <article><span className="course-overview__fact-icon"><MaterialIcon name="menu_book" /></span><div><span>课程资料</span><strong>{overviewLoading ? "—" : documents.length}</strong><small>{overviewLoading ? "正在加载资料…" : `${readyDocuments} 份可用于检索`}</small></div></article>
            <article><span className="course-overview__fact-icon"><MaterialIcon name="folder_open" /></span><div><span>个人资源</span><strong>{overviewLoading ? "—" : materials.length}</strong><small>当前账号生成的内容</small></div></article>
          </section>
        </section>

        {showSetup ? (
          <section className="course-setup" aria-labelledby="course-setup-title">
            <div className="course-setup__intro">
              <p>课程初始化</p>
              <h3 id="course-setup-title">为这门课程准备第一批知识</h3>
              <span>系统可以根据课程目标规划知识结构并审查开放来源；你也可以上传已有资料，或稍后再处理。</span>
            </div>
            <div className="course-setup__choices">
              <a className="is-primary" href={buildRoleCourseHash(user?.role, routes.knowledge, course.id, { action: "build" })}>
                <MaterialIcon name="auto_awesome" /><span><strong>一键构建课程知识库</strong><small>规划结构、发现来源并启动后台构建</small></span><MaterialIcon name="arrow_forward" />
              </a>
              <a href={buildRoleCourseHash(user?.role, routes.knowledge, course.id, { action: "upload" })}>
                <MaterialIcon name="description" /><span><strong>上传已有课程资料</strong><small>从本地教材、讲义或文档开始</small></span><MaterialIcon name="arrow_forward" />
              </a>
              <button type="button" onClick={dismissSetup}>
                <MaterialIcon name="schedule" /><span><strong>暂时跳过</strong><small>先进入空课程，稍后可在课程知识中继续</small></span><MaterialIcon name="arrow_forward" />
              </button>
            </div>
          </section>
        ) : null}

        <section className="course-overview__entries" aria-labelledby="quick-entry-title">
          <div className="course-overview__section-title"><p>课程工作区</p><h3 id="quick-entry-title">常用入口</h3></div>
          <div>{visibleEntries.map((entry) => <a key={entry.route} href={buildRoleCourseHash(user?.role, entry.route, course.id)}><span><MaterialIcon name={entry.icon} /></span><strong>{user?.role === "student" && entry.route === routes.ai ? "AI问答" : entry.label}</strong><small>{user?.role === "student" ? studentEntryNotes[entry.route] || entry.note : entry.note}</small></a>)}</div>
        </section>

        <div className="course-overview__columns">
          <GlassPanel className="course-overview__panel">
            <div className="course-overview__panel-head"><div><p>教学方向</p><h3>课程目标</h3></div><span className="course-overview__count">{course.objectives?.length || 0} 项目标</span></div>
            {course.objectives?.length ? (
              <ol className="course-overview__objectives">{course.objectives.map((objective, index) => <li key={`${index}-${objective}`}><span>{index + 1}</span>{objective}</li>)}</ol>
            ) : <p className="course-overview__empty">尚未设置教学目标，可在课程设置中补充。</p>}
          </GlassPanel>

          <GlassPanel className="course-overview__panel">
            <div className="course-overview__panel-head"><div><p>最近更新</p><h3>最新个人资源</h3></div><a href={buildRoleCourseHash(user?.role, routes.resources, course.id)}>查看全部</a></div>
            {overviewLoading ? <p className="course-overview__empty" role="status">正在加载个人资源…</p> : materials.length ? <ul className="course-overview__resources">{materials.slice(0, 4).map((material) => <li key={`${material.material_type}-${material.material_id}`}><a href={buildRoleCourseHash(user?.role, routes.resources, course.id, { material_type: material.material_type, material_id: material.material_id })}><span className="course-overview__resource-icon" aria-hidden="true"><MaterialIcon name="description" /></span><span className="course-overview__resource-text"><strong title={materialTitle(material)}>{materialTitle(material)}</strong><small>{getCourseMaterialTypeMeta(material.material_type).label}</small></span><MaterialIcon name="arrow_forward" /></a></li>)}</ul> : <p className="course-overview__empty">暂无生成资源，从问答与生成开始创建。</p>}
          </GlassPanel>
        </div>


      </main>
    </AppSurface>
  );
}
