import { useEffect, useMemo, useRef, useState } from "react";

import { registerCreatedJob, useCourseJobs } from "../../../jobs/jobStore";
import { isActiveJob } from "../../../jobs/types";
import {
  createCourseKnowledgeBuildDraft,
  getCourseKnowledgeBuild,
  listCourseKnowledgeVersions,
  retryCourseKnowledgeBuild,
  rollbackCourseKnowledgeVersion,
} from "../../api/courses";
import type { CourseKnowledgeBuild, CourseKnowledgeGraphVersion } from "../../api/types";
import { MaterialIcon } from "../../shared";
import { buildTeacherCourseHash } from "../../teacherRoutes";
import { CourseKnowledgeBuildWizard } from "./CourseKnowledgeBuildWizard";
import "./CourseKnowledgeBuildCard.css";

const PHASE_LABELS: Record<string, string> = {
  queued: "正在排队",
  running: "正在更新知识库",
  textbook_discovery: "正在发现完整教材",
  textbook_ingestion: "正在下载 PDF 并调用 MinerU",
  textbook_mapping: "正在将教材映射到知识点",
  gap_search: "正在补充知识点网页",
  ai_fallback: "正在处理最后的 AI 内容缺口",
  source_audit: "正在查找合适的课程资料",
  indexing: "正在整理课程资料",
  model_fallback: "正在补充缺少的内容",
  quality_check: "正在检查内容质量",
  quality_blocked: "内容需要进一步完善",
  publishing: "即将完成",
  completed: "更新完成",
};

function metricNumber(metrics: Record<string, unknown> | undefined, key: string) {
  const value = Number(metrics?.[key] ?? 0);
  return Number.isFinite(value) ? value : 0;
}

type Props = {
  courseId: string;
  documentCount: number;
  canBuild: boolean;
  requestedAction?: string | null;
};

function storageKey(courseId: string) {
  return `edu-ai:course-kb-build:${courseId}`;
}

export function CourseKnowledgeBuildCard({ courseId, documentCount, canBuild, requestedAction }: Props) {
  const jobs = useCourseJobs(courseId, "build_knowledge_index");
  const activeJob = useMemo(() => jobs.find(isActiveJob) ?? null, [jobs]);
  const latestJob = jobs[0] ?? null;
  const [plan, setPlan] = useState<CourseKnowledgeBuild | null>(null);
  const [planning, setPlanning] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [versions, setVersions] = useState<CourseKnowledgeGraphVersion[]>([]);
  const [rollingBack, setRollingBack] = useState<number | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const cardRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (requestedAction !== "build") return;
    cardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    cardRef.current?.focus({ preventScroll: true });
  }, [requestedAction]);

  useEffect(() => {
    const buildId = window.localStorage.getItem(storageKey(courseId));
    if (!buildId) {
      setPlan(null);
      return;
    }
    let canceled = false;
    void getCourseKnowledgeBuild(courseId, buildId)
      .then((value) => { if (!canceled) setPlan(value); })
      .catch(() => { window.localStorage.removeItem(storageKey(courseId)); });
    return () => { canceled = true; };
  }, [courseId, latestJob?.status, latestJob?.updated_at]);

  useEffect(() => {
    let canceled = false;
    void listCourseKnowledgeVersions(courseId)
      .then((value) => { if (!canceled) setVersions(value); })
      .catch(() => { if (!canceled) setVersions([]); });
    return () => { canceled = true; };
  }, [courseId, latestJob?.status, latestJob?.updated_at]);

  async function buildKnowledgeBase() {
    if (!canBuild || planning || activeJob) return;
    setSubmitError("");

    try {
      if (plan?.status === "draft") {
        setWizardOpen(true);
        return;
      }
      setPlanning(true);
      const buildPlan = await createCourseKnowledgeBuildDraft(courseId);
      window.localStorage.setItem(storageKey(courseId), buildPlan.build_id);
      setPlan(buildPlan);
      setWizardOpen(true);
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : "知识库更新失败，请稍后重试。");
    } finally {
      setPlanning(false);
    }
  }

  async function rollbackVersion(version: number) {
    if (!canBuild || rollingBack !== null) return;
    if (!window.confirm(`确认恢复到版本 ${version}？系统会保留当前版本，方便以后再次恢复。`)) return;
    setRollingBack(version);
    setSubmitError("");
    try {
      await rollbackCourseKnowledgeVersion(courseId, version);
      setVersions(await listCourseKnowledgeVersions(courseId));
      window.dispatchEvent(new CustomEvent("edu-ai:knowledge-document-updated", { detail: { courseId } }));
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : "恢复历史版本失败，请稍后重试。");
    } finally {
      setRollingBack(null);
    }
  }

  async function retryBuild() {
    if (!plan || !["blocked", "failed"].includes(plan.status) || retrying) return;
    setRetrying(true);
    setSubmitError("");
    try {
      const job = await retryCourseKnowledgeBuild(courseId, plan.build_id);
      registerCreatedJob(job);
      setPlan(await getCourseKnowledgeBuild(courseId, plan.build_id));
    } catch (reason) {
      setSubmitError(reason instanceof Error ? reason.message : "重试构建失败，请稍后再试。");
    } finally {
      setRetrying(false);
    }
  }

  const status = activeJob ?? latestJob;
  const isWorking = Boolean(activeJob) || planning;
  const failed = status?.status === "failed" || status?.status === "partially_succeeded";
  const succeeded = status?.status === "succeeded";
  const statusText = planning
    ? "正在分析课程内容"
    : status
        ? PHASE_LABELS[status.step] || PHASE_LABELS[status.status] || status.message || "正在处理"
        : documentCount
          ? "知识库已可用"
          : "尚未构建";
  const buttonText = planning
    ? "正在准备…"
    : activeJob
      ? "正在更新…"
      : plan?.status === "draft"
        ? "继续构建方案"
        : plan && ["blocked", "failed"].includes(plan.status)
          ? "新建方案调整配置"
      : documentCount
          ? "更新知识库"
          : "一键构建知识库";
  const approvedSourceCount = plan?.source_candidates.filter(
    (item) => item.selected && item.review_status === "ready",
  ).length ?? 0;
  const textbookCount = metricNumber(plan?.metrics, "textbook_ingested");
  const mineruCount = metricNumber(plan?.metrics, "mineru_parsed");
  const nonAiCoverageRate = metricNumber(plan?.metrics, "non_ai_coverage_rate");
  const aiMaterialRatio = metricNumber(plan?.metrics, "ai_material_ratio");
  const leafCoverage = plan?.metrics?.leaf_coverage && typeof plan.metrics.leaf_coverage === "object"
    ? plan.metrics.leaf_coverage as Record<string, { title?: string; unmet?: string[] }>
    : {};
  const unmetLeaves = Object.entries(leafCoverage).filter(([, value]) => value.unmet?.length);
  const failedByCode = plan?.metrics?.fetch_failed_by_code && typeof plan.metrics.fetch_failed_by_code === "object"
    ? plan.metrics.fetch_failed_by_code as Record<string, number>
    : {};

  return (
    <section ref={cardRef} tabIndex={-1} className="course-kb-builder" aria-labelledby="course-kb-builder-title">
      <header className="course-kb-builder__header">
        <span className="course-kb-builder__icon" aria-hidden="true">
          <MaterialIcon name="auto_awesome" />
        </span>
        <div className="course-kb-builder__heading">
          <span>课程知识库</span>
          <h2 id="course-kb-builder-title">{documentCount ? "更新课程知识库" : "构建课程知识库"}</h2>
          <p>系统会自动整理课程知识结构，并为每个知识点准备合适的学习资料。</p>
        </div>
        <span className={`course-kb-builder__badge${isWorking ? " is-working" : succeeded ? " is-success" : failed ? " is-error" : ""}`}>
          {isWorking ? "更新中" : succeeded || documentCount ? "已构建" : "未构建"}
        </span>
      </header>

      {isWorking ? (
        <div className="course-kb-builder__progress" aria-live="polite">
          <div>
            <span>{statusText}</span>
            <strong>{status?.progress ?? 0}%</strong>
          </div>
          <div className="course-kb-builder__progress-track">
            <span style={{ width: `${Math.max(4, Math.min(100, status?.progress ?? 4))}%` }} />
          </div>
          <small>可以离开此页面，完成后系统会通知你。</small>
        </div>
      ) : failed ? (
        <div className="course-kb-builder__notice is-error" role="alert">
          <MaterialIcon name="error" />
          <div><strong>本次更新未完成</strong><span>{status?.error_message || status?.error || "请稍后重试。"}</span></div>
        </div>
      ) : succeeded ? (
        <div className="course-kb-builder__notice is-success">
          <MaterialIcon name="check_circle" />
          <div><strong>知识库已更新</strong><span>课程图谱和学习资料已经可以使用。</span></div>
        </div>
      ) : null}

      <div className="course-kb-builder__actions">
        {canBuild && plan && ["blocked", "failed"].includes(plan.status) ? (
          <button type="button" className="course-kb-builder__primary" disabled={retrying || isWorking} onClick={() => void retryBuild()}>
            <MaterialIcon name="replay" />
            {retrying ? "正在重新排队…" : "重试本方案"}
          </button>
        ) : null}
        {canBuild ? (
          <button type="button" className="course-kb-builder__primary" disabled={isWorking} onClick={() => void buildKnowledgeBase()}>
            <MaterialIcon name={documentCount ? "refresh" : "auto_awesome"} />
            {buttonText}
          </button>
        ) : <p>你可以查看课程知识库，但没有更新权限。</p>}
        {canBuild ? (
          <a
            className="course-kb-builder__secondary"
            href={buildTeacherCourseHash("learning-resource-generation", courseId)}
          >
            <MaterialIcon name="auto_awesome" />
            学习资源生成
          </a>
        ) : null}
        {!isWorking && canBuild ? <span>资料查找、整理和质量检查会自动完成</span> : null}
      </div>

      {wizardOpen && plan?.status === "draft" ? (
        <CourseKnowledgeBuildWizard
          courseId={courseId}
          build={plan}
          onBuildChange={setPlan}
          onClose={() => setWizardOpen(false)}
        />
      ) : null}

      {plan || versions.length || status ? (
        <details className="course-kb-builder__details">
          <summary>
            <MaterialIcon name="history" />
            <span>历史版本与更多信息</span>
          </summary>
          <div className="course-kb-builder__details-body">
            {plan ? (
              <div className="course-kb-builder__summary">
                <span><strong>{plan.topics.length}</strong> 个知识点</span>
                <span><strong>{approvedSourceCount}</strong> 份已确认来源</span>
                <span><strong>{textbookCount}</strong> 本在线教材</span>
                <span><strong>{mineruCount}</strong> 份 MinerU 解析</span>
                <span><strong>{Math.round(nonAiCoverageRate * 100)}</strong>% 非 AI 覆盖</span>
                <span><strong>{Math.round(aiMaterialRatio * 100)}</strong>% AI 占比</span>
                {plan.quality_score != null ? <span><strong>{Math.round(plan.quality_score)}</strong> 分质量评分</span> : null}
              </div>
            ) : null}

            {unmetLeaves.length ? (
              <div className="course-kb-builder__quality">
                <h3>仍有内容缺口</h3>
                <ul>{unmetLeaves.map(([topicId, value]) => (
                  <li key={topicId} className="is-failed">
                    <MaterialIcon name="error" />
                    <span>{value.title || topicId}：{value.unmet?.join("；")}</span>
                  </li>
                ))}</ul>
              </div>
            ) : null}

            {Object.keys(failedByCode).length ? (
              <div className="course-kb-builder__quality">
                <h3>采集失败分类</h3>
                <ul>{Object.entries(failedByCode).map(([code, count]) => (
                  <li key={code} className="is-failed">
                    <MaterialIcon name="error" /><span>{code}</span><strong>{count}</strong>
                  </li>
                ))}</ul>
              </div>
            ) : null}

            {versions.length ? (
              <div className="course-kb-builder__versions">
                <h3>历史版本</h3>
                <ul>
                  {versions.slice(0, 4).map((version, index) => (
                    <li key={version.version}>
                      <div>
                        <strong>版本 {version.version}{index === 0 ? " · 当前" : ""}</strong>
                        <span>{new Date(version.published_at || version.created_at).toLocaleString()}</span>
                      </div>
                      {index > 0 && canBuild ? (
                        <button type="button" disabled={rollingBack !== null} onClick={() => void rollbackVersion(version.version)}>
                          {rollingBack === version.version ? "正在恢复…" : "恢复此版本"}
                        </button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {plan?.quality_checks?.length ? (
              <div className="course-kb-builder__quality">
                <h3>质量门禁</h3>
                <ul>
                  {plan.quality_checks.map((check) => (
                    <li key={check.check_type} className={check.status === "passed" ? "is-passed" : "is-failed"}>
                      <MaterialIcon name={check.status === "passed" ? "check_circle" : "error"} />
                      <span>{check.check_type}</span>
                      <strong>{check.status === "passed" ? "通过" : "未通过"}</strong>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {status ? (
              <button type="button" className="course-kb-builder__job-link" onClick={() => window.dispatchEvent(new Event("edu-ai:open-job-center"))}>
                查看后台任务
              </button>
            ) : null}
          </div>
        </details>
      ) : null}

      {plan?.error?.message ? <div className="course-kb-builder__error" role="alert">{plan.error.message}</div> : null}
      {submitError ? <div className="course-kb-builder__error" role="alert">{submitError}</div> : null}
    </section>
  );
}
