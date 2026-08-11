import { useEffect, useMemo, useRef, useState } from "react";

import { useCourseJobs } from "../../../jobs/jobStore";
import { isActiveJob } from "../../../jobs/types";
import {
  createCourseKnowledgeBuildDraft,
  getCourseKnowledgeBuild,
  listCourseKnowledgeVersions,
  rollbackCourseKnowledgeVersion,
} from "../../api/courses";
import type { CourseKnowledgeBuild, CourseKnowledgeGraphVersion } from "../../api/types";
import { MaterialIcon } from "../../shared";
import { CourseKnowledgeBuildWizard } from "./CourseKnowledgeBuildWizard";
import "./CourseKnowledgeBuildCard.css";

const PHASE_LABELS: Record<string, string> = {
  queued: "正在排队",
  running: "正在更新知识库",
  source_audit: "正在查找合适的课程资料",
  indexing: "正在整理课程资料",
  model_fallback: "正在补充缺少的内容",
  quality_check: "正在检查内容质量",
  quality_blocked: "内容需要进一步完善",
  publishing: "即将完成",
  completed: "更新完成",
};

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
      : documentCount
          ? "更新知识库"
          : "一键构建知识库";
  const approvedSourceCount = plan?.source_candidates.filter(
    (item) => item.selected && item.review_status === "ready",
  ).length ?? 0;

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
        {canBuild ? (
          <button type="button" className="course-kb-builder__primary" disabled={isWorking} onClick={() => void buildKnowledgeBase()}>
            <MaterialIcon name={documentCount ? "refresh" : "auto_awesome"} />
            {buttonText}
          </button>
        ) : <p>你可以查看课程知识库，但没有更新权限。</p>}
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
                {plan.quality_score != null ? <span><strong>{Math.round(plan.quality_score)}</strong> 分质量评分</span> : null}
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
